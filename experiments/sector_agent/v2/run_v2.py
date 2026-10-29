"""Sector-constraint agent v2: Tony's constraint set (see RULE_v2.md).

    python run_v2.py

Reuses v1's config (forecast, gamma, overlay parameters), agent decisions and overlay code.
Writes only inside this folder.
"""
from dataclasses import replace
from datetime import datetime
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
sys.path.insert(0, str(V1))

import cvxpy as cp
import numpy as np
import pandas as pd

import run_all as R

E = R.E
DECISIONS_SHA = 'eaedf4b1c7580bfca8c8624ba62557d62fc80dcd8d9dbfaacbdf63c3f3fa1c19'
MONTH_KEY_SHA = '196f8dc757b58987c01aef57840811428b072068bcff94e6aa4dd41d5df1b96a'
BANDS = (0.01, 0.02, 0.03)
CAPS = (1.25, 1.5, None)
G = 2.0
CONTROL_BAND = 0.02


def log(msg):
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(HERE / 'run_log_v2.md', 'a', encoding='utf-8') as f:
        f.write(f'- {stamp}: {msg}\n')
    print(msg, flush=True)


def v2_builder(band, cap, shares):
    """Tony's base constraints plus a sector band and an optional sector gross-share cap."""
    def build(w, inputs, settings):
        side = inputs['side']
        S = inputs['sector_matrix']
        rules = {
            'gross': cp.norm1(w) <= G,
            'dollar_neutral': cp.sum(w) == 0,
            'position_cap': cp.abs(w) <= 0.035,
            'long_floor': w[side > 0] >= 0.001,
            'short_floor': w[side < 0] <= -0.001,
            'beta_neutral': inputs['beta'] @ w == 0,
            'sector_band': cp.abs(S @ w) <= band,
        }
        if cap is not None:
            limit = np.array([cap * shares.get(s, 0.0) * G for s in inputs['sector_names']])
            rules['sector_gross_cap'] = S @ cp.abs(w) <= limit
        return rules
    return build


def run_arm(name, schedule, history, cash, settings, mod, shares, decisions=None):
    previous = pd.Series(dtype=float)
    out, attempts = [], []
    for month, g in schedule:
        cov = E.covariance_for(history, month, g, settings)[0]
        if decisions is None:
            tries = [(CONTROL_BAND, None)]
        else:
            band, cap = decisions[month]
            tries = [(b, c) for c in CAPS[CAPS.index(cap):] for b in BANDS[BANDS.index(band):]]
        for i, (band, cap) in enumerate(tries):
            inputs = E.sizing_inputs(g, previous, settings)
            try:
                w, _, status = E.solve_weights(g, cov, inputs, settings,
                                               v2_builder(band, cap, shares[month]), mod.build_objective)
                break
            except ValueError as exc:
                attempts.append({'arm': name, 'target_month': month, 'band': band, 'cap': cap,
                                 'outcome': 'infeasible', 'detail': str(exc)[:120]})
                if decisions is None:
                    log(f'CONTROL INFEASIBLE in {month}: {exc}. Stopping as RULE_v2.md requires.')
                    sys.exit(4)
        else:
            log(f'AGENT INFEASIBLE in {month} even at band 3% and no cap. Stopping.')
            sys.exit(5)
        if i > 0:
            attempts.append({'arm': name, 'target_month': month, 'band': band, 'cap': cap,
                             'outcome': 'used fallback', 'detail': ''})
        _, drifted, raw, _ = E.account(month, g, w, previous, history.loc[month],
                                       float(cash.loc[month]), cov, settings)
        out.append({'target_month': month, 'w': w, 'previous': previous, 'raw': raw.fillna(0.),
                    'cash': float(cash.loc[month]), 'sector': g.sector, 'ticker': g.ticker,
                    'me': g.me, 'side': g.side, 'beta': g.beta_use,
                    'band_used': band, 'cap_used': cap, 'fallback': i > 0})
        previous = drifted
        print(f'{name} {month} {status} band={band} cap={cap}', flush=True)
    return out, attempts


def mandate(arm, m):
    """Monthly mandate checks on the scaled book (RULE_v2.md)."""
    rows = []
    for a, (_, r) in zip(arm, m.iterrows()):
        w = r.k * a['w']
        sec_net = w.groupby(a['sector']).sum()
        sec_gross = w.abs().groupby(a['sector']).sum()
        shorts = a['side'] < 0
        rows.append({'target_month': a['target_month'],
                     'names': int((w.abs() > 1e-6).sum()), 'gross': w.abs().sum(), 'net': w.sum(),
                     'max_name': w.abs().max(), 'min_short_me_musd': a['me'][shorts].min(),
                     'sectors_held': int((sec_gross > 1e-6).sum()), 'max_sector_net': sec_net.abs().max(),
                     'ex_ante_beta': float(a['w'] @ a['beta']), 'fallback': a['fallback']})
    c = pd.DataFrame(rows)
    tol = 1e-6
    c['breach_names'] = ~c.names.between(200, 500)
    c['breach_gross'] = c.gross > 2 + tol
    c['breach_net'] = c.net.abs() > 0.5 + tol
    c['breach_name5'] = c.max_name > 0.05 + tol
    c['breach_short_me500'] = c.min_short_me_musd < 500
    c['breach_sectors5'] = c.sectors_held < 5
    c['breach_sector20'] = c.max_sector_net > 0.20 + tol
    c['breaches'] = c.filter(like='breach_').sum(axis=1)
    return c


def beta_se(m, market):
    y = (m.net_return - m.cash).to_numpy()
    x = (m.target_month.map(market) - m.cash).to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    s2 = resid @ resid / (len(y) - 2)
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    return coef[1], se


def main():
    for f, sha in (('agent_decisions.csv', DECISIONS_SHA), ('month_key.csv', MONTH_KEY_SHA)):
        got = hashlib.sha256((V1 / f).read_bytes()).hexdigest()
        if got != sha:
            raise SystemExit(f'{f} changed since RULE_v2.md (sha {got[:12]}); stopping.')
    cfg = R.parse_yaml(V1 / 'base_config.yaml')
    log(f'run_v2 start: forecast {cfg["forecast"]}, gamma {cfg["optimizer_params"].get("cost_penalty")}, '
        'v1 decisions verified unchanged')
    stages = E.load_stages(Path(cfg['optimizer']).name)
    mod = stages['constraints']
    # Objective parameters only (lambda, gamma, c); v2 constraints come from v2_builder.
    settings = replace(mod.SETTINGS, **cfg['optimizer_params'])
    pred = E.resolve_predictions(None if cfg['predictions'] == 'default' else cfg['predictions'])
    scores, history, cash = E.load_inputs(pred, cfg['forecast'], E.C.CHARS_PARQUET, settings, stages=stages)
    schedule = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, settings)
                if str(cfg['start']) <= m <= str(cfg['end'])]
    shares = {m: (u.sector.value_counts() / len(u)).to_dict() for m, u in scores.groupby('target_month')}
    dec = pd.read_csv(V1 / 'agent_decisions.csv').merge(pd.read_csv(V1 / 'month_key.csv'), on='ID',
                                                         validate='one_to_one')
    to_num = lambda v: None if str(v).lower() == 'none' else float(str(v).rstrip('x%')) / (100 if str(v).endswith('%') else 1)
    decisions = {r.target_month: (to_num(r.band), to_num(r.cap)) for r in dec.itertuples()}
    market = E.benchmark_returns()
    ov = dict(cfg['overlay'], hedge_min=10 ** 9)  # no SPX hedge: h_t = 0 in every month

    control, att_c = run_arm('control', schedule, history, cash, settings, mod, shares)
    agent, att_a = run_arm('agent', schedule, history, cash, settings, mod, shares, decisions)
    pd.DataFrame(att_c + att_a, columns=['arm', 'target_month', 'band', 'cap', 'outcome', 'detail']) \
        .to_csv(HERE / 'fallbacks_v2.csv', index=False)

    table = {}
    for name, arm in (('Control', control), ('Agent', agent)):
        m = R.overlay(arm, market, ov, cfg['nav_usd'])
        m = m.drop(columns=[c for c in m if c.startswith('breach')] + ['short_usd'])
        chk = mandate(arm, m)
        m = m.merge(chk.drop(columns=['gross', 'net', 'max_name', 'max_sector_net', 'names', 'sectors_held']),
                    on='target_month')
        m.to_csv(HERE / f'monthly_{name.lower()}_v2.csv', index=False)
        b, se = beta_se(m, market)
        stats = R.metrics(m)
        for k in ('Constraint breaches (month-rules)', 'Months with any breach'):
            stats.pop(k)
        vol = stats['Vol (ann.)']
        stats.update({'Monthly beta to S&P 500': b, 'Beta s.e.': se,
                      'Max |ex-ante beta| (pre-overlay)': m.ex_ante_beta.abs().max(),
                      'Realised vol vs 12-14% cap': 'within' if 0.12 <= vol <= 0.14 else ('below' if vol < 0.12 else 'ABOVE'),
                      'Infeasible months (choice relaxed)': int(m.fallback.sum()),
                      'Fallback attempts logged': sum(a['arm'] == name.lower() and a['outcome'] == 'infeasible'
                                                      for a in att_c + att_a),
                      'Mandate breaches (month-rules)': int(chk.breaches.sum()),
                      'Months with any breach': int((chk.breaches > 0).sum()),
                      'Min short-name market cap ($m)': chk.min_short_me_musd.min(),
                      'Max single name': chk.max_name.max(), 'Max |net|': chk.net.abs().max(),
                      'Min names': chk.names.min(), 'Min sectors held': chk.sectors_held.min()})
        table[name] = stats
    summary = pd.DataFrame(table)
    summary.to_csv(HERE / 'summary_v2.csv')
    print(summary.to_string())
    log('run_v2 finished.')


if __name__ == '__main__':
    main()

"""Sector-constraint agent experiment, Steps 3-7, driven by base_config.yaml (see RULE.md).

    python run_all.py

1. Builds agent_inputs.csv from the config's forecast column. If agent_decisions.csv is missing,
   or was made from different inputs, it archives the old files, logs it, and stops (exit 2):
   the agent must decide before any optimizer runs.
2. Runs the control arm (config as is), applies the overlay, and checks it against the
   reference holdings. If that fails, it writes reproduction_check.csv and stops (exit 3).
3. Runs the agent arm, applies the overlay and costs, writes summary.csv and monthly CSVs.

Writes only inside this folder. Nothing in sizing/ or 06_final/ is edited.
"""
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('FIAM_DATA_DIR', r'C:\Users\b0079\Desktop')
sys.path.insert(0, str(ROOT / 'sizing'))

import cvxpy as cp
import numpy as np
import pandas as pd

import _engine as E

BANDS = (0.01, 0.02, 0.03)
CAPS = (1.25, 1.5, None)
GICS = ['10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60']
HEALTH_CARE = '35'
SEED = 20261029


# ---------------------------------------------------------------- config

def parse_yaml(path):
    """Minimal parser for the flat two-level `key: value` file in this folder."""
    out, block = {}, None
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        key, _, value = line.strip().partition(':')
        value = value.strip()
        target = out if not raw.startswith(' ') else out[block]
        if not raw.startswith(' ') and value == '':
            block = key
            out[key] = {}
            continue
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.lower() in ('none', 'null'):
            value = None
        else:
            try:
                value = int(value) if value.isdigit() else float(value)
            except ValueError:
                pass
        target[key] = value
    return out


def log(msg):
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(HERE / 'decision_log.md', 'a', encoding='utf-8') as f:
        f.write(f'- {stamp}: {msg}\n')
    print(msg, flush=True)


# ---------------------------------------------------------------- step 3: agent inputs

def build_inputs(scores, history, cfg):
    keys = pd.Series(np.random.default_rng(SEED).permutation(list('ABCDEFGHIJK')), index=GICS)
    months = sorted(scores.target_month.unique())
    months = [m for m in months if str(cfg['start']) <= m <= str(cfg['end'])]
    order = np.random.default_rng(SEED + 1).permutation(len(months))
    ids = {months[j]: f'R{i + 1:02d}' for i, j in enumerate(order)}
    rows = []
    for m in months:
        u = scores[scores.target_month == m]
        row = {'ID': ids[m]}
        past = [str(pd.Period(m) - k) for k in (3, 2, 1)]
        for s in GICS:
            us = u[u.sector == s]
            ew = history.reindex(index=past, columns=us.permno).mean(axis=1)
            lab = keys[s]
            row[f'{lab}_share'] = len(us) / len(u)
            row[f'{lab}_disp'] = us.forecast.std(ddof=1)
            row[f'{lab}_vol'] = ew.std(ddof=1) * np.sqrt(12)
        rows.append(row)
    table = pd.DataFrame(rows).set_index('ID').sort_index()
    table = table[[f'{l}_{k}' for l in 'ABCDEFGHIJK' for k in ('share', 'disp', 'vol')]].round(4)
    month_key = pd.DataFrame({'ID': list(ids.values()), 'target_month': list(ids.keys())}).sort_values('ID')
    sector_key = keys.rename('label').rename_axis('gics_sector').reset_index()
    return table, month_key, sector_key


def ensure_inputs(scores, history, cfg):
    table, month_key, sector_key = build_inputs(scores, history, cfg)
    text = table.to_csv(lineterminator='\n')
    sha = hashlib.sha256(text.encode()).hexdigest()
    meta_path = HERE / 'decisions_meta.json'
    dec_path = HERE / 'agent_decisions.csv'
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if dec_path.exists() and meta.get('inputs_sha256') == sha and meta.get('forecast') == cfg['forecast']:
        return month_key, sector_key
    if dec_path.exists() or (HERE / 'agent_inputs.csv').exists():
        arch = HERE / 'archive' / datetime.now().strftime('%Y%m%d_%H%M%S')
        arch.mkdir(parents=True)
        for f in ('agent_inputs.csv', 'agent_decisions.csv', 'decisions_meta.json'):
            if (HERE / f).exists():
                shutil.copy2(HERE / f, arch / f)
        log(f'Inputs changed (forecast {meta.get("forecast")} -> {cfg["forecast"]}, sha {str(meta.get("inputs_sha256"))[:12]} -> {sha[:12]}); '
            f'old files copied to {arch.name}; new decisions required.')
    (HERE / 'agent_inputs.csv').write_text(text, encoding='utf-8')
    month_key.to_csv(HERE / 'month_key.csv', index=False)
    sector_key.to_csv(HERE / 'sector_key.csv', index=False)
    (HERE / 'agent_inputs_meta.json').write_text(json.dumps(
        {'forecast': cfg['forecast'], 'inputs_sha256': sha, 'rows': len(table),
         'built': datetime.now().isoformat(timespec='minutes')}, indent=2))
    log(f'Built agent_inputs.csv ({len(table)} rows, forecast {cfg["forecast"]}, sha {sha[:12]}). '
        'Agent decisions needed before any optimizer run.')
    sys.exit(2)


# ---------------------------------------------------------------- optimizer arms

def cap_builder(base_builder, cap, shares, gross_limit):
    def build(w, inputs, settings):
        rules = base_builder(w, inputs, settings)
        if cap is not None:
            limit = np.array([cap * shares.get(s, 0.0) * gross_limit for s in inputs['sector_names']])
            rules['sector_gross_cap'] = inputs['sector_matrix'] @ cp.abs(w) <= limit
        return rules
    return build


def run_arm(name, schedule, history, cash, settings, mod, decisions=None, shares=None):
    previous = pd.Series(dtype=float)
    out, fallbacks = [], []
    for month, g in schedule:
        cov = E.covariance_for(history, month, g, settings)[0]
        tried = [(settings.sector_limit, None, 'control')]
        if decisions is not None:
            band, cap = decisions[month]
            caps = list(CAPS[CAPS.index(cap):])
            bands = [band] + ([0.02] if band == 0.01 else [])
            tried = [(b, c, 'agent') for c in caps for b in bands] + [(settings.sector_limit, None, 'control fallback')]
        for i, (band, cap, label) in enumerate(tried):
            s = replace(settings, sector_limit=band)
            inputs = E.sizing_inputs(g, previous, s)
            builder = cap_builder(mod.build_constraints, cap, shares.get(month, {}) if shares else {}, s.gross_limit)
            try:
                w, _, status = E.solve_weights(g, cov, inputs, s, builder, mod.build_objective)
                break
            except ValueError as exc:
                fallbacks.append({'arm': name, 'target_month': month, 'band': band, 'cap': cap,
                                  'error': str(exc)[:120]})
        else:
            raise RuntimeError(f'{name} {month}: no feasible setting')
        if decisions is not None and i > 0:
            fallbacks.append({'arm': name, 'target_month': month, 'band': band, 'cap': cap,
                              'error': f'USED fallback ({label})'})
        row, drifted, raw, sector = E.account(month, g, w, previous, history.loc[month],
                                              float(cash.loc[month]), cov, s)
        out.append({'target_month': month, 'w': w, 'previous': previous, 'raw': raw.fillna(0.),
                    'cash': float(cash.loc[month]), 'sector': g.sector, 'ticker': g.ticker,
                    'band_used': band, 'cap_used': cap})
        previous = drifted
        print(f'{name} {month} {status} band={band} cap={cap}', flush=True)
    return out, fallbacks


# ---------------------------------------------------------------- overlay, costs, metrics

def ols_beta(y, x):
    x = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(x, y, rcond=None)[0][1]


def overlay(arm, market, ov, nav0):
    tc, br = ov['trading_cost_bps'] / 1e4, ov['borrow_bps_annual'] / 1e4 / 12
    on = ov['enabled']
    base, spx_ex, rows = [], [], []
    prev_scaled, prev_raw, prev_R = pd.Series(dtype=float), None, None
    nav = nav0
    for t, a in enumerate(arm):
        w, raw, c = a['w'], a['raw'], a['cash']
        sx = float(market[a['target_month']]) - c
        short = float(-w[w < 0].sum())
        traded_u = float(w.subtract(a['previous'], fill_value=0).abs().sum())
        base_ex = float(w @ (raw - c)) - tc * traded_u - br * short
        h = ols_beta(np.array(base[-ov['hedge_window']:]), np.array(spx_ex[-ov['hedge_window']:])) \
            if on and len(base) >= ov['hedge_min'] else 0.0
        hedged_hist = [b - hb * s for b, hb, s in zip(base, [r['h'] for r in rows], spx_ex)]
        if on and len(hedged_hist) >= ov['vol_min']:
            sigma = np.std(hedged_hist[-ov['vol_window']:], ddof=1) * np.sqrt(12)
            k = float(np.clip(ov['vol_target'] / sigma, ov['k_min'], ov['k_max']))
        else:
            k = 1.0
        ws = k * w
        if prev_raw is not None:
            drift = prev_scaled * (1 + prev_raw.reindex(prev_scaled.index).fillna(0)) / (1 + prev_R)
        else:
            drift = pd.Series(dtype=float)
        traded = float(ws.subtract(drift, fill_value=0).abs().sum())
        cost = tc * traded + br * k * short
        gross_ret = c + k * float(w @ (raw - c)) - k * h * sx
        R = gross_ret - cost
        sec = w.groupby(a['sector'])
        sgross = w.abs().groupby(a['sector']).sum()
        rows.append(dict(target_month=a['target_month'], k=k, h=h, gross_return=gross_ret, net_return=R,
                         cost=cost, traded=traded, one_way_turnover=traded / 2, cash=c,
                         hurdle=c + 0.04 / 12, nav_start=nav, gross=k * w.abs().sum(), net=k * w.sum(),
                         short_usd=k * short * nav, names=int((w.abs() > 1e-6).sum()),
                         max_name=k * w.abs().max(), sectors_held=int((sgross > 1e-6).sum()),
                         max_sector_net=k * sec.sum().abs().max(),
                         largest_sector_gross_share=(sgross / sgross.sum()).max(),
                         largest_sector=(sgross / sgross.sum()).idxmax(),
                         hc_gross_share=sgross.get(HEALTH_CARE, 0.0) / sgross.sum(),
                         band_used=a['band_used'], cap_used=a['cap_used']))
        base.append(base_ex)
        spx_ex.append(sx)
        prev_scaled, prev_raw, prev_R = ws, raw, R
        nav *= 1 + R
    m = pd.DataFrame(rows)
    tol = 1e-6
    m['breach_names'] = ~m.names.between(200, 500)
    m['breach_gross'] = m.gross > 2 + tol
    m['breach_net'] = m.net.abs() > 0.5 + tol
    m['breach_name5'] = m.max_name > 0.05 + tol
    m['breach_short500'] = m.short_usd < 5e8
    m['breach_sectors5'] = m.sectors_held < 5
    m['breach_sector20'] = m.max_sector_net > 0.20 + tol
    m['breaches'] = m.filter(like='breach_').sum(axis=1)
    return m


def metrics(m):
    def ir(r):
        a = r - m.hurdle
        return np.sqrt(12) * a.mean() / a.std(ddof=1)
    wealth = (1 + m.net_return).cumprod()
    return {'Net IR': ir(m.net_return), 'Gross IR': ir(m.gross_return),
            'Vol (ann.)': m.net_return.std(ddof=1) * np.sqrt(12),
            'Max drawdown': float((wealth / wealth.cummax() - 1).min()),
            'Max sector net (% NAV)': m.max_sector_net.max(),
            'Largest sector gross share, median': m.largest_sector_gross_share.median(),
            'Largest sector gross share, max': m.largest_sector_gross_share.max(),
            'Health Care gross share, median': m.hc_gross_share.median(),
            'Health Care gross share, max': m.hc_gross_share.max(),
            'Monthly one-way turnover': m.one_way_turnover.mean(),
            'Cost (% NAV a year)': m.cost.mean() * 12,
            'Mean k (overlay)': m.k.mean(),
            'Constraint breaches (month-rules)': int(m.breaches.sum()),
            'Months with any breach': int((m.breaches > 0).sum())}


# ---------------------------------------------------------------- reproduction gate

def reproduction(arm, m, ref_path):
    ref = pd.read_csv(ref_path)
    ref = ref[ref.ticker != 'SPY']
    pos = 'position_usd' if 'position_usd' in ref else 'position'
    rows = []
    for a, (_, r) in zip(arm, m.iterrows()):
        date = (pd.Period(a['target_month']) - 1).end_time.strftime('%Y-%m-%d')
        rf = ref[ref.date == date].groupby('ticker')[pos].sum()
        w = a['w']
        o = pd.Series(w.to_numpy(), index=a['ticker'].to_numpy())
        no_ticker = int(pd.isna(o.index).sum())  # panel has no ticker that month; cannot match by name
        o = o[o.index.notna()].groupby(level=0).sum()
        j = pd.concat([(rf / rf.abs().sum()).rename('ref'), (o / w.abs().sum()).rename('ours')], axis=1)
        both = j.dropna()
        # same names: every unmatched reference name is one of ours without a ticker, and none of ours is unmatched
        names = int(j.ours.isna().sum()) == no_ticker and int(j.ref.isna().sum()) == 0
        diff = float((both.ref - both.ours).abs().max())
        expected = r.k * w.abs().sum() * r.nav_start
        rows.append({'date': date, 'target_month': a['target_month'], 'ref_names': len(rf),
                     'matched_names': len(both), 'our_no_ticker': no_ticker, 'same_names': names,
                     'sign_agree': float((both.ref * both.ours > 0).mean()),
                     'max_norm_weight_diff': diff,
                     'ref_gross_usd': rf.abs().sum(), 'k': r.k, 'nav_start': r.nav_start,
                     'k_x_gross_x_nav': expected, 'gross_x_1bn': a['w'].abs().sum() * 1e9,
                     'scale_ratio_vs_overlay': rf.abs().sum() / expected})
    rep = pd.DataFrame(rows)
    rep['shape_ok'] = rep.same_names & (rep.max_norm_weight_diff < 1e-4)
    rep['scale_ok'] = (rep.scale_ratio_vs_overlay - 1).abs() < 0.01
    return rep


# ---------------------------------------------------------------- main

def main():
    cfg = parse_yaml(HERE / 'base_config.yaml')
    log(f'run_all start: config {cfg["name"]}, forecast {cfg["forecast"]}, params {cfg["optimizer_params"]}, overlay {cfg["overlay"]["enabled"]}')
    stages = E.load_stages(Path(cfg['optimizer']).name)
    mod = stages['constraints']
    settings = replace(mod.SETTINGS, **cfg['optimizer_params'])
    mod.validate(settings)
    stages['selection'].validate(settings)
    pred = E.resolve_predictions(None if cfg['predictions'] == 'default' else cfg['predictions'])
    scores, history, cash = E.load_inputs(pred, cfg['forecast'], E.C.CHARS_PARQUET, settings, stages=stages)

    month_key, sector_key = ensure_inputs(scores, history, cfg)

    dec = pd.read_csv(HERE / 'agent_decisions.csv').merge(month_key, on='ID', validate='one_to_one')
    to_num = lambda v: None if str(v).lower() == 'none' else float(str(v).rstrip('x%')) / (100 if str(v).endswith('%') else 1)
    decisions = {r.target_month: (to_num(r.band), to_num(r.cap)) for r in dec.itertuples()}
    assert all(b in BANDS and c in CAPS for b, c in decisions.values()), 'Decision outside the menus'

    schedule = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, settings)
                if str(cfg['start']) <= m <= str(cfg['end'])]
    shares = {m: (u.sector.value_counts() / len(u)).to_dict() for m, u in scores.groupby('target_month')}
    market = E.benchmark_returns()
    ov = cfg['overlay']

    control, _ = run_arm('control', schedule, history, cash, settings, mod)
    mc = overlay(control, market, ov, cfg['nav_usd'])
    rep = reproduction(control, mc, cfg['reference_holdings'])
    rep.to_csv(HERE / 'reproduction_check.csv', index=False)
    gap = (f'shape ok {rep.shape_ok.sum()}/{len(rep)} months (same names {rep.same_names.sum()}/{len(rep)}, '
           f'max weight diff median {rep.max_norm_weight_diff.median():.6f} max {rep.max_norm_weight_diff.max():.6f} of gross), '
           f'scale ratio {rep.scale_ratio_vs_overlay.min():.4f}-{rep.scale_ratio_vs_overlay.max():.4f}')
    if not (rep.shape_ok.all() and rep.scale_ok.all()):
        print(rep.describe(include='all').T.to_string())
        if not cfg.get('allow_approximate_control'):
            log(f'REPRODUCTION FAILED: {gap}. Stopping before the agent arm.')
            sys.exit(3)
        log(f'Reproduction NOT exact, continuing as allow_approximate_control is set: {gap}.')
    else:
        log(f'Reproduction check passed: {gap}.')

    agent, fallbacks = run_arm('agent', schedule, history, cash, settings, mod, decisions, shares)
    ma = overlay(agent, market, ov, cfg['nav_usd'])
    pd.DataFrame(fallbacks).to_csv(HERE / 'agent_fallbacks.csv', index=False)
    for arm, m in (('control', mc), ('agent', ma)):
        m.assign(arm=arm).to_csv(HERE / f'monthly_{arm}.csv', index=False)
    table = pd.DataFrame({'Control': metrics(mc), 'Agent': metrics(ma)})
    table.to_csv(HERE / 'summary.csv')
    print(table.to_string())
    log('run_all finished.')


if __name__ == '__main__':
    main()

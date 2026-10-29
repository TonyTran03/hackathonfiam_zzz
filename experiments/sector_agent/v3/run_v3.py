"""Sector-constraint agent v3: Tony's new objective over the full eligible universe (RULE_v3.md).

    python run_v3.py test            # 2021-01 only, both arms, plus a check of the factor-form risk
    python run_v3.py control         # all months, control arm; checkpoints state_control.pkl
    python run_v3.py agent           # all months, agent arm;   checkpoints state_agent.pkl

Imports the engine and v1/v2 helpers without editing them. Writes only inside this folder.
"""
from dataclasses import replace
from datetime import datetime
import hashlib
from pathlib import Path
import pickle
import sys
import time

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
sys.path.insert(0, str(V1))
sys.path.insert(0, str(V1 / 'v2'))

import cvxpy as cp
import numpy as np
import pandas as pd
from sklearn.covariance import ledoit_wolf_shrinkage

import run_all as R
import run_v2 as V2

E = R.E
TC = 0.024
GROSS, CAP_NAME, FLOOR, N_SIDE = 2.0, 0.035, 0.001, 150
CONTROL_BAND = 0.02
BANDS, CAPS = V2.BANDS, V2.CAPS


def log(msg):
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(HERE / 'run_log_v3.md', 'a', encoding='utf-8') as f:
        f.write(f'- {stamp}: {msg}\n')
    print(msg, flush=True)


def load():
    for f, sha in (('agent_decisions.csv', V2.DECISIONS_SHA), ('month_key.csv', V2.MONTH_KEY_SHA)):
        if hashlib.sha256((V1 / f).read_bytes()).hexdigest() != sha:
            raise SystemExit(f'{f} changed since RULE_v3.md; stopping.')
    cfg = R.parse_yaml(V1 / 'base_config.yaml')
    stages = E.load_stages(Path(cfg['optimizer']).name)
    settings = replace(stages['constraints'].SETTINGS, **cfg['optimizer_params'])
    pred = E.resolve_predictions(None if cfg['predictions'] == 'default' else cfg['predictions'])
    scores, history, cash = E.load_inputs(pred, cfg['forecast'], E.C.CHARS_PARQUET, settings, stages=stages)
    months = sorted(m for m in scores.target_month.unique() if str(cfg['start']) <= m <= str(cfg['end']))
    dec = pd.read_csv(V1 / 'agent_decisions.csv').merge(pd.read_csv(V1 / 'month_key.csv'), on='ID')
    to_num = lambda v: None if str(v).lower() == 'none' else float(str(v).rstrip('x%')) / (100 if str(v).endswith('%') else 1)
    decisions = {r.target_month: (to_num(r.band), to_num(r.cap)) for r in dec.itertuples()}
    return cfg, stages, settings, scores, history, cash, months, decisions


def risk_parts(history, month, U, settings):
    """covariance_for's estimate over U, kept in factor form (never N x N)."""
    past = history.loc[history.index < month].tail(settings.covariance_months)
    x = past.reindex(columns=U.index).replace([np.inf, -np.inf], np.nan)
    if len(x) < settings.covariance_min_observations:
        raise ValueError(f'{month}: insufficient history')
    counts = x.notna().sum().to_numpy()
    sample_sd = x.std(ddof=0).to_numpy()
    reliable = (counts >= settings.covariance_min_observations) & np.isfinite(sample_sd) & (sample_sd > 1e-8)
    sd = np.maximum(np.where(reliable, sample_sd, U.rvol_21d.to_numpy() * np.sqrt(21)), 1e-4)
    z = ((x - x.mean()) / sd).fillna(0).to_numpy()
    z[:, ~reliable] = 0
    T, N = z.shape
    zc = z - z.mean(axis=0)
    s_jj = (zc ** 2).sum(axis=0) / T
    mu = s_jj.sum() / N
    delta = float(ledoit_wolf_shrinkage(z))
    diag = np.maximum((1 - delta) * s_jj + delta * mu, 1e-12)
    a = np.where(reliable, sd / np.sqrt(diag), 0.0)
    return {'B': zc * a, 'a': a, 'sd_unrel': np.where(reliable, 0.0, sd), 'delta': delta, 'mu': mu, 'T': T}


def risk_value(w, p):
    return ((1 - p['delta']) / p['T'] * np.sum((p['B'] @ w) ** 2) + p['delta'] * p['mu'] * np.sum((p['a'] * w) ** 2)
            + np.sum((p['sd_unrel'] * w) ** 2) + 1e-10 * np.sum(w ** 2))


def solve(U, p, alpha, wprev, lo, hi, band, cap, shares, smat, names):
    w = cp.Variable(len(U))
    risk = ((1 - p['delta']) / p['T'] * cp.sum_squares(p['B'] @ w)
            + p['delta'] * p['mu'] * cp.sum_squares(cp.multiply(p['a'], w))
            + cp.sum_squares(cp.multiply(p['sd_unrel'], w)) + 1e-10 * cp.sum_squares(w))
    obj = cp.Minimize(-alpha @ w + TC * cp.norm1(w - wprev) + 0.5 * risk)
    cons = [w >= lo, w <= hi, cp.norm1(w) <= GROSS, cp.sum(w) == 0,
            U.beta_use.to_numpy() @ w == 0, cp.abs(smat @ w) <= band]
    if cap is not None:
        cons.append(smat @ cp.abs(w) <= np.array([cap * shares.get(s, 0.0) * GROSS for s in names]))
    prob = cp.Problem(obj, cons)
    prob.solve(solver='CLARABEL')
    if prob.status not in ('optimal', 'optimal_inaccurate') or w.value is None:
        raise ValueError(f'status {prob.status}')
    worst = max(float(np.max(c.violation())) for c in cons)
    if worst > 1e-6:
        raise ValueError(f'violation {worst:.2g}')
    return w.value


def month_solve(month, U, p, previous, band, cap, shares):
    alpha = (U.score - U.score.mean()).to_numpy()  # RULE_v3 amendment: alpha = ranked score
    long_c = (U.forecast > 0).to_numpy()
    short_c = ((U.forecast < 0) & (U.me >= 500)).to_numpy()
    if long_c.sum() < N_SIDE or short_c.sum() < N_SIDE:
        raise ValueError(f'too few candidates: {long_c.sum()} long, {short_c.sum()} short')
    wprev = previous.reindex(U.index, fill_value=0).to_numpy()
    dummies = pd.get_dummies(U.sector, dtype=float).T
    smat, names = dummies.to_numpy(), dummies.index.tolist()
    lo = np.where(short_c, -CAP_NAME, 0.0)
    hi = np.where(long_c, CAP_NAME, 0.0)
    t0 = time.time()
    wa = solve(U, p, alpha, wprev, lo, hi, band, cap, shares, smat, names)
    ta = time.time() - t0
    longs = np.argsort(-np.where(long_c, wa, -np.inf))[:N_SIDE]
    shorts = np.argsort(np.where(short_c, wa, np.inf))[:N_SIDE]
    lo, hi = np.zeros(len(U)), np.zeros(len(U))
    lo[longs], hi[longs] = FLOOR, CAP_NAME
    lo[shorts], hi[shorts] = -CAP_NAME, -FLOOR
    t0 = time.time()
    wb = solve(U, p, alpha, wprev, lo, hi, band, cap, shares, smat, names)
    tb = time.time() - t0
    keep = np.zeros(len(U), bool)
    keep[longs] = keep[shorts] = True
    w = pd.Series(np.where(keep, wb, 0.0), index=U.index)[keep]
    return w, ta, tb, int((np.abs(wa) > 1e-6).sum())


def run_month(month, U, history, cash, settings, previous, tries, shares):
    p = risk_parts(history, month, U, settings)
    attempts = []
    for i, (band, cap) in enumerate(tries):
        try:
            w, ta, tb, na = month_solve(month, U, p, previous, band, cap, shares)
            break
        except ValueError as exc:
            attempts.append({'target_month': month, 'band': band, 'cap': cap, 'outcome': 'infeasible',
                             'detail': str(exc)[:120]})
    else:
        return None, attempts
    raw = history.loc[month].reindex(w.index).fillna(0.)
    c = float(cash.loc[month])
    gross_ret = c + float(w @ (raw - c))
    rec = {'target_month': month, 'w': w, 'previous': previous, 'raw': raw, 'cash': c,
           'sector': U.sector.loc[w.index], 'ticker': U.ticker.loc[w.index], 'me': U.me.loc[w.index],
           'side': np.sign(w), 'beta': U.beta_use.loc[w.index], 'band_used': band, 'cap_used': cap,
           'fallback': i > 0, 'secs_a': ta, 'secs_b': tb, 'names_stage_a': na, 'universe': len(U),
           'delta': p['delta']}
    drifted = w * (1 + raw) / (1 + gross_ret)
    if i > 0:
        attempts.append({'target_month': month, 'band': band, 'cap': cap, 'outcome': 'used fallback', 'detail': ''})
    return (rec, drifted), attempts


def describe(rec):
    w, k = rec['w'], rec['sector']
    return (f"{rec['target_month']} band={rec['band_used']} cap={rec['cap_used']} universe={rec['universe']} "
            f"stage-a names={rec['names_stage_a']} solve a={rec['secs_a']:.1f}s b={rec['secs_b']:.1f}s | "
            f"names={int((w.abs() > 1e-6).sum())} gross={w.abs().sum():.4f} net={w.sum():+.2e} "
            f"beta={float(w @ rec['beta']):+.2e} max sector net={w.groupby(k).sum().abs().max():.4f} "
            f"min |w|={w.abs().min():.4f} max |w|={w.abs().max():.4f}")


def main(mode):
    cfg, stages, settings, scores, history, cash, months, decisions = load()
    universe = {m: u.set_index('permno') for m, u in scores.groupby('target_month')}
    shares = {m: (u.sector.value_counts() / len(u)).to_dict() for m, u in universe.items()}
    if mode == 'test':
        m = months[0]
        sched = dict(stages['selection'].candidate_schedule(scores, settings))
        g = sched[m]
        dense = E.covariance_for(history, m, g, settings)[0]
        p = risk_parts(history, m, g, settings)
        rng = np.random.default_rng(0)
        errs = [abs(risk_value(w, p) / (w @ dense @ w) - 1) for w in rng.normal(size=(5, len(g)))]
        log(f'Factor-form check on {m} candidates ({len(g)}): max relative error {max(errs):.2e}')
        for name, tries in (('control', [(CONTROL_BAND, None)]), ('agent', [decisions[m]])):
            out, att = run_month(m, universe[m], history, cash, settings, pd.Series(dtype=float), tries, shares[m])
            log(f'TEST {name}: ' + (describe(out[0]) if out else f'INFEASIBLE {att}'))
        return
    state, attempts, previous = [], [], pd.Series(dtype=float)
    for m in months:
        if mode == 'control':
            tries = [(CONTROL_BAND, None)]
        else:
            band, cap = decisions[m]
            tries = [(b, c) for c in CAPS[CAPS.index(cap):] for b in BANDS[BANDS.index(band):]]
        out, att = run_month(m, universe[m], history, cash, settings, previous, tries, shares[m])
        attempts += [dict(a, arm=mode) for a in att]
        pd.DataFrame(attempts, columns=['arm', 'target_month', 'band', 'cap', 'outcome', 'detail']) \
            .to_csv(HERE / f'fallbacks_{mode}.csv', index=False)
        if out is None:
            log(f'{mode.upper()} INFEASIBLE in {m} after all permitted relaxations. Stopping.')
            sys.exit(4)
        rec, previous = out
        state.append(rec)
        with open(HERE / f'state_{mode}.pkl', 'wb') as f:
            pickle.dump(state, f)
        log(f'{mode}: ' + describe(rec))
    log(f'{mode} finished all {len(state)} months.')


if __name__ == '__main__':
    main(sys.argv[1])

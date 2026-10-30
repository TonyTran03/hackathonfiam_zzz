"""Mentor-review build: sector + size neutral sizing, wider short pool, optional daily covariance.

    python run_neutral.py <name> <sector_limit|none> <size_limit|none> <m|d> [start] [end] [predictions]

m = engine covariance (36 monthly returns); d = 36 months of DAILY returns (~750 observations),
Ledoit-Wolf shrunk the same way as the engine, scaled by 21 to monthly so risk_penalty keeps its units.
Writes outputs/<name>_monthly.csv and prints the summary plus a sector/stock-selection split of P&L.
"""
import os
import sys
from dataclasses import replace
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _engine as E

name, sec, size, covmode = sys.argv[1:5]
start = sys.argv[5] if len(sys.argv) > 5 else '2021-01'
end = sys.argv[6] if len(sys.argv) > 6 else '2026-08'
pred = Path(sys.argv[7]) if len(sys.argv) > 7 else E.HERE.parent / 'prediction/saved_forecasts/predictions.parquet'
lim = lambda v: None if v.lower() == 'none' else float(v)
# OBJECTIVE=score: Tony's s'w - 100 w'Sw - 0.002|dw|. OBJECTIVE=mv_ann: the mentor's annualized form.
OBJECTIVE = os.environ.get('OBJECTIVE', 'score')
ALPHA = os.environ.get('ALPHA', 'grinold')
IC = float(os.environ.get('IC', 0.035))             # signal_check.py: rank IC vs alpha, 2021-26
ANNUAL_COST = float(os.environ.get('ANNUAL_COST', 0.024))  # mentor's board: 0.024 = 20bp per trade x 12
K_SHORT = int(os.environ.get('K_SHORT', 0))  # >0: two-stage pick of K shorts from the wide pool
RISK_AVERSION = float(os.environ.get('RISK_AVERSION', 1.0))  # lambda in 0.5*lambda*w'Sw; ex ante ~ IR/target vol = 1/0.10

stages = E.load_stages('neutral'); mod = stages['constraints']
s = replace(mod.SETTINGS, sector_limit=lim(sec), size_limit=lim(size),
            minimum_position_weight=float(os.environ.get('LONG_FLOOR', mod.SETTINGS.minimum_position_weight)),
            short_minimum_weight=None if os.environ.get('SHORT_FLOOR') is None else float(os.environ['SHORT_FLOOR']))
if os.environ.get('GROSS') is not None:  # house gross limit, mandate allows up to 2.0
    s = replace(s, gross_limit=float(os.environ['GROSS']))
if os.environ.get('VOL_LIMIT') is not None:  # ex-ante annual vol ceiling, e.g. 0.12
    s = replace(s, annual_vol_limit=float(os.environ['VOL_LIMIT']))
if os.environ.get('NET_LIMIT') is not None:  # house net band, e.g. 0 = dollar neutral
    s = replace(s, net_min=-float(os.environ['NET_LIMIT']), net_max=float(os.environ['NET_LIMIT']))
mod.validate(s); stages['selection'].validate(s)
scores, history, cash = E.load_inputs(pred, 'current_gbm_no8k', E.C.CHARS_PARQUET, s, stages=stages)
market = E.benchmark_returns()
# Agent hook: SECTOR_SCHEDULE=<csv with target_month and band_used (or sector_limit)> sets the
# sector band month by month, e.g. experiments/sector_agent/decision_log_by_date.csv.
schedule = {}
if os.environ.get('SECTOR_SCHEDULE'):
    _sch = pd.read_csv(os.environ['SECTOR_SCHEDULE'], dtype={'target_month': str})
    _col = 'band_used' if 'band_used' in _sch else 'sector_limit'
    schedule = dict(zip(_sch.target_month.str[:7], _sch[_col].astype(float)))
if os.environ.get('SHORT_CAP'):
    # One-solve way to force breadth: each short <= SHORT_CAP, so a 37.5% short leg needs >= 100 names.
    _sizing_inputs, _cap = E.sizing_inputs, float(os.environ['SHORT_CAP'])
    def _capped(g, previous, settings):
        d = _sizing_inputs(g, previous, settings)
        d['short_limits'] = np.where(g.side.to_numpy() < 0, min(_cap, settings.position_limit), 0)
        return d
    E.sizing_inputs = _capped

if covmode == 'd':
    dsf = pd.read_parquet(E.HERE.parent / '06_final/data/dsf.parquet', columns=['permno', 'date', 'daily_return'])
    daily = dsf.pivot(index='date', columns='permno', values='daily_return').sort_index()
    del dsf


def daily_covariance(month, g):
    formation = pd.Period(month, 'M').start_time  # first day of the holding month
    past = daily.loc[(daily.index < formation) & (daily.index >= formation - pd.DateOffset(months=36))]
    x = past.reindex(columns=g.index).replace([np.inf, -np.inf], np.nan)
    counts = x.notna().sum().to_numpy()
    sample_sd = x.std(ddof=0).to_numpy()
    reliable = (counts >= 250) & np.isfinite(sample_sd) & (sample_sd > 1e-8)
    sd = np.maximum(np.where(reliable, sample_sd, g.rvol_21d.to_numpy()), 1e-5)
    z = ((x - x.mean()) / sd).fillna(0).to_numpy()
    z[:, ~reliable] = 0
    shrunk = LedoitWolf().fit(z).covariance_
    d = np.sqrt(np.maximum(np.diag(shrunk), 1e-12))
    corr = shrunk / np.outer(d, d)
    corr[~reliable, :] = 0; corr[:, ~reliable] = 0
    np.fill_diagonal(corr, 1)
    return 21 * corr * np.outer(sd, sd) + np.eye(len(g)) * 1e-10


prev, rows, split, held = pd.Series(dtype=float), [], [], []
for month, g in stages['selection'].candidate_schedule(scores, s):
    s_base, s = s, replace(s, sector_limit=schedule.get(month, s.sector_limit))
    if not start <= month <= end:
        continue
    cov = daily_covariance(month, g) if covmode == 'd' else E.covariance_for(history, month, g, s)[0]
    uni = scores.loc[scores.target_month == month]
    uni_sd, f_mean, f_sd = uni.score.std(), uni.forecast.mean(), uni.forecast.std()

    def objective_for(g, cov):
        if OBJECTIVE != 'mv_ann':
            return mod.build_objective
        # Mentor's whiteboard: min -alpha'w + c |w - w_prev|_1 + 0.5 lambda w' Sigma w, all annualized
        # (solved as the equivalent max). How alpha is built (ALPHA):
        #   grinold   12 x IC x sigma x z          (expected return from the score's IC)
        #   forecast  12 x (forecast - month mean)  (the model's own monthly return forecast)
        #   score     12 x score in forecast units  (neutralised, smoothed score, scaled to sd of forecast)
        if ALPHA == 'forecast':
            alpha = 12 * (g.forecast - f_mean).to_numpy()
        elif ALPHA == 'score':
            alpha = 12 * (g.score / uni_sd * f_sd).to_numpy()
        else:
            alpha = 12 * IC * np.sqrt(np.diag(cov)) * (g.score / uni_sd).to_numpy()
        cov_ann = 12 * cov

        def objective(w, sc, covariance, previous, forced, settings):
            return cp.Maximize(alpha @ w - ANNUAL_COST * cp.norm1(w - previous)
                               - 0.5 * RISK_AVERSION * cp.quad_form(w, cp.psd_wrap(cov_ann)))
        return objective
    w, audit, _ = E.solve_weights(g, cov, E.sizing_inputs(g, prev, s), s, mod.build_constraints, objective_for(g, cov))
    if K_SHORT:
        # Stage 2: the free solve above picks from the wide short pool; keep its K_SHORT largest
        # shorts (score breaks ties) and re-solve with each held at the floor, so the book stays
        # within the mandate's 200-500 names.
        shorts = g.index[g.side < 0]
        keep = (pd.DataFrame(dict(w=-w[shorts], s=-g.score[shorts]))
                .sort_values(['w', 's'], ascending=False).head(K_SHORT).index)
        idx = np.flatnonzero(g.index.isin(g.index[g.side > 0].union(keep)))
        g, cov = g.iloc[idx], cov[np.ix_(idx, idx)]
        s2 = replace(s, short_minimum_weight=s.minimum_position_weight)
        w, audit, _ = E.solve_weights(g, cov, E.sizing_inputs(g, prev, s2), s2, mod.build_constraints,
                                      objective_for(g, cov))
    row, prev, raw, _ = E.account(month, g, w, prev, history.loc[month], float(cash.loc[month]), cov, s)
    row['sector_limit_used'] = s.sector_limit
    s = s_base
    row.update(market_return=float(market.loc[month]), positions_1bp=int((w.abs() >= 1e-4).sum()),
               long_names=int((w >= 1e-4).sum()), short_names=int((w <= -1e-4).sum()))
    rows.append(row)
    held.append(pd.DataFrame(dict(month=month, permno=g.index, ticker=g.ticker.values, company_name=g.company_name.values,
                                  sector=g.sector.values, weight=w.values)))
    # P&L split: sector bets (net sector weight x sector return) vs stock selection within sector.
    uni = scores[scores.target_month == month].set_index('permno')
    r = history.loc[month].reindex(uni.index)
    ok = r.notna()
    R = (r[ok] * uni.me[ok]).groupby(uni.sector[ok]).sum() / uni.me[ok].groupby(uni.sector[ok]).sum()
    rs = g.sector.map(R).fillna(raw.fillna(0)).to_numpy()
    c = float(cash.loc[month]); ri = raw.fillna(0).to_numpy()
    split.append(dict(target_month=month, sector_pnl=float(w @ (rs - c)), selection_pnl=float(w @ (ri - rs))))

m = E.attach_final_reporting(pd.DataFrame(rows).assign(method=name)).merge(pd.DataFrame(split), on='target_month')
(HERE / 'outputs').mkdir(exist_ok=True)
m.to_csv(HERE / 'outputs' / f'{name}_monthly.csv', index=False)
pd.concat(held).to_csv(HERE / 'outputs' / f'{name}_holdings.csv', index=False)
r = E.summarize(m).iloc[0]
ir0 = lambda x: x.mean() / x.std() * np.sqrt(12)
sel_net = m.selection_pnl - m.cost
print(f'{name}: sector {sec} size {size} cov {covmode} | {start}..{end} {len(m)} months\n'
      f'  IR {r.information_ratio:.2f}  CAGR {r.cagr:.1%}  vol {r.annual_vol:.1%}  DD {r.max_drawdown:.1%}  '
      f'beta {r.realized_market_beta:.2f}  turnover/yr {r.annual_one_way_turnover:.2f}\n'
      f'  max sector net {m.max_sector_net.max():.2%}  max |size exp| {m.size_exposure.abs().max():.3f}  '
      f'positions>=1bp {m.positions_1bp.min()}-{m.positions_1bp.max()} (long {m.long_names.min()}-{m.long_names.max()}, '
      f'short {m.short_names.min()}-{m.short_names.max()})\n'
      f'  sector P&L {m.sector_pnl.mean()*12:.2%}/yr  selection P&L {m.selection_pnl.mean()*12:.2%}/yr '
      f'(after 20bp: IR vs 0 {ir0(sel_net):.2f})', flush=True)

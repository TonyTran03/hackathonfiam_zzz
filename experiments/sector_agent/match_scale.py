"""Reproduction diagnostics for the control arm: shape on ticker-matched names, and dollar scale
under alternative trading-cost assumptions in the overlay. Positions only; no agent arm."""
from dataclasses import replace

import pandas as pd

import run_all as R

cfg = R.parse_yaml(R.HERE / 'base_config.yaml')
stages = R.E.load_stages('optimizer')
mod = stages['constraints']
settings = replace(mod.SETTINGS, **cfg['optimizer_params'])
scores, history, cash = R.E.load_inputs(R.E.resolve_predictions(None), cfg['forecast'],
                                        R.E.C.CHARS_PARQUET, settings, stages=stages)
sched = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, settings)
         if str(cfg['start']) <= m <= str(cfg['end'])]
arm, _ = R.run_arm('control', sched, history, cash, settings, mod)
market = R.E.benchmark_returns()
ref = pd.read_csv(cfg['reference_holdings'])
ref = ref[ref.ticker != 'SPY']

# Shape on ticker-matched names, each side normalised by its FULL gross.
rows = []
for a in arm:
    date = (pd.Period(a['target_month']) - 1).end_time.strftime('%Y-%m-%d')
    rf = ref[ref.date == date].groupby('ticker').position_usd.sum()
    w = a['w']
    o = pd.Series(w.to_numpy(), index=a['ticker'].to_numpy())
    no_ticker = int(pd.isna(o.index).sum())
    o = o[o.index.notna()].groupby(level=0).sum()
    j = pd.concat([(rf / rf.abs().sum()).rename('ref'), (o / w.abs().sum()).rename('ours')], axis=1)
    both = j.dropna()
    rows.append({'target_month': a['target_month'], 'matched': len(both), 'our_no_ticker': no_ticker,
                 'ref_only': int(j.ours.isna().sum()), 'ours_only': int(j.ref.isna().sum()),
                 'max_diff_matched': (both.ref - both.ours).abs().max(),
                 'sign_agree': float((both.ref * both.ours > 0).mean())})
shape = pd.DataFrame(rows)
shape.to_csv(R.HERE / 'reproduction_shape_matched.csv', index=False)
print(shape.describe().round(6).to_string())

# Dollar scale under alternative overlay trading costs.
for tc in (65, 85):
    ov = dict(cfg['overlay'], trading_cost_bps=tc)
    m = R.overlay(arm, market, ov, cfg['nav_usd'])
    ratio = [ref[ref.date == (pd.Period(a['target_month']) - 1).end_time.strftime('%Y-%m-%d')]
             .position_usd.abs().sum() / (r.k * a['w'].abs().sum() * r.nav_start)
             for a, (_, r) in zip(arm, m.iterrows())]
    s = pd.Series(ratio)
    print(f'trading {tc}bp: scale ratio first {s.iloc[0]:.4f} median {s.median():.4f} '
          f'min {s.min():.4f} max {s.max():.4f} last {s.iloc[-1]:.4f}')

"""Diagnose the failed reproduction check on the first months only (no agent arm, no results)."""
from dataclasses import replace
import sys
import pandas as pd
import run_all as R

cfg = R.parse_yaml(R.HERE / 'base_config.yaml')
stages = R.E.load_stages('optimizer')
mod = stages['constraints']
settings = replace(mod.SETTINGS, **cfg['optimizer_params'])
scores, history, cash = R.E.load_inputs(R.E.resolve_predictions(None), cfg['forecast'],
                                        R.E.C.CHARS_PARQUET, settings, stages=stages)
sched = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, settings) if m >= '2021-01'][:2]
arm, _ = R.run_arm('control', sched, history, cash, settings, mod)
ref = pd.read_csv(cfg['reference_holdings'])
ref = ref[ref.ticker != 'SPY']
for a in arm:
    date = (pd.Period(a['target_month']) - 1).end_time.strftime('%Y-%m-%d')
    rf = ref[ref.date == date].set_index('ticker').position_usd / 1e9
    ours = pd.DataFrame({'w': a['w'], 'ticker': a['ticker']})
    print(f"\n{a['target_month']}: our tickers missing {ours.ticker.isna().sum()}, "
          f"ref names {len(rf)}, ours {len(ours)}")
    o = ours.dropna().set_index('ticker').w
    j = pd.concat([rf.rename('ref'), o.rename('ours')], axis=1)
    print('only in ref', j.ours.isna().sum(), '| only ours', j.ref.isna().sum())
    j = j.dropna()
    j['diff'] = j.ref - j.ours
    print('matched', len(j), 'corr %.4f' % j.ref.corr(j.ours), 'max |diff| %.4f' % j['diff'].abs().max(),
          'sign agree %.3f' % (j.ref.mul(j.ours) > 0).mean())
    print(j.reindex(j['diff'].abs().sort_values(ascending=False).index).head(5).round(4).to_string())

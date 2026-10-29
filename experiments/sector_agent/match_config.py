"""Find which optimizer settings reproduce holdings_final in 2021-02 (positions only, no returns).

Runs 2021-01 then 2021-02 for each candidate (2021-02 depends on 2021-01's drifted holdings)
and compares 2021-02 weights with the reference, matched on ticker, as fractions of $1bn.
Writes match_config_fine2.csv. Agent files are not read or touched.
"""
from dataclasses import replace
import itertools
import time

import pandas as pd

import run_all as R

cfg = R.parse_yaml(R.HERE / 'base_config.yaml')
stages = R.E.load_stages('optimizer')
mod = stages['constraints']
base = replace(mod.SETTINGS, **cfg['optimizer_params'])
scores, history, cash = R.E.load_inputs(R.E.resolve_predictions(None), cfg['forecast'],
                                        R.E.C.CHARS_PARQUET, base, stages=stages)
sched = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, base) if m >= '2021-01'][:2]
ref = pd.read_csv(cfg['reference_holdings'])
ref = ref[(ref.ticker != 'SPY') & (ref.date == '2021-01-31')].set_index('ticker').position_usd / 1e9


def score(s):
    arm, _ = R.run_arm('try', sched, history, cash, s, mod)
    a = arm[1]
    o = pd.Series(a['w'].to_numpy(), index=a['ticker'].to_numpy()).dropna()
    o = o[o.index.notna()]
    j = pd.concat([ref.rename('ref'), o.rename('ours')], axis=1).dropna()
    d = (j.ref - j.ours).abs()
    return {'matched': len(j), 'max_abs_diff': d.max(), 'mean_abs_diff': d.mean(),
            'within_1bp': (d < 1e-4).mean(), 'corr': j.ref.corr(j.ours)}


grid = []
for gamma, tl in itertools.product([215, 220, 222.5, 225, 227.5, 230, 235, 240], [None]):
    grid.append({'cost_penalty': float(gamma), 'turnover_limit': tl})
for tl in []:
    grid.append({'cost_penalty': 1.0, 'turnover_limit': tl})
for rp in []:
    grid.append({'cost_penalty': 1.0, 'turnover_limit': None, 'risk_penalty': rp})
rows = []
for params in grid:
    t = time.time()
    try:
        r = score(replace(base, **params))
    except Exception as exc:
        r = {'error': str(exc)[:80]}
    rows.append({**params, **r, 'secs': round(time.time() - t, 1)})
    print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(R.HERE / 'match_config_fine2.csv', index=False)

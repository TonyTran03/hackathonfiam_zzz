"""Mentor review: does the ranking work on its own, before any optimizer? Apples with apples.

Each month, on the tradeable universe (price >= $5, no nano/micro), the realized return is
regressed cross-sectionally on sector dummies + size (market-cap rank) + estimated beta; the
residual is the stock's 'alpha' that month. We then ask whether the score ranks that alpha.

    python signal_check.py [start] [end] [predictions]
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _engine as E

start = sys.argv[1] if len(sys.argv) > 1 else '2021-01'
end = sys.argv[2] if len(sys.argv) > 2 else '2026-08'
pred = Path(sys.argv[3]) if len(sys.argv) > 3 else E.HERE.parent / 'prediction/saved_forecasts/predictions.parquet'
TOP = 100

stages = E.load_stages('neutral')
scores, history, _ = E.load_inputs(pred, 'current_gbm_no8k', E.C.CHARS_PARQUET, stages['constraints'].SETTINGS, stages=stages)
rows, deciles = [], []
for month, g in scores.groupby('target_month'):
    if not start <= month <= end:
        continue
    g = g.set_index('permno')
    g['r'] = history.loc[month].reindex(g.index)
    g = g[g.r.notna()]
    X = np.column_stack([pd.get_dummies(g.sector, dtype=float).to_numpy(), g['size'], g.beta_use])
    g['alpha'] = g.r - X @ np.linalg.lstsq(X, g.r.to_numpy(), rcond=None)[0]
    top = g.nlargest(TOP, 'score'); bot = g.nsmallest(TOP, 'score')
    rows.append(dict(month=month, n=len(g),
                     ic_raw=g.score.corr(g.r, method='spearman'),
                     ic_alpha=g.score.corr(g.alpha, method='spearman'),
                     spread_raw=top.r.mean() - bot.r.mean(),
                     spread_alpha=top.alpha.mean() - bot.alpha.mean(),
                     corr_score_size=g.score.corr(g['size']), corr_score_beta=g.score.corr(g.beta_use)))
    g['decile'] = pd.qcut(g.score.rank(method='first'), 10, labels=range(1, 11))
    deciles.append(g.groupby('decile', observed=True).alpha.mean().rename(month))

m = pd.DataFrame(rows).set_index('month')
t = lambda x: x.mean() / x.std() * np.sqrt(len(x))
print(f'Signal check {start}..{end}: {len(m)} months, ~{int(m.n.median())} tradeable stocks/month\n')
print(f"{'':28s}{'mean':>9s}{'t-stat':>8s}{'hit':>6s}")
for c, label in [('ic_raw', 'rank IC, raw return'), ('ic_alpha', 'rank IC, alpha (resid.)'),
                 ('spread_raw', f'top{TOP}-bot{TOP}, raw /mo'), ('spread_alpha', f'top{TOP}-bot{TOP}, alpha /mo')]:
    print(f'{label:28s}{m[c].mean():9.4f}{t(m[c]):8.2f}{(m[c] > 0).mean():6.0%}')
print(f"\nTop-minus-bottom alpha, annualized: {m.spread_alpha.mean()*12:.1%}, IR {m.spread_alpha.mean()/m.spread_alpha.std()*np.sqrt(12):.2f}")
print(f'Score vs size corr {m.corr_score_size.mean():.3f}, vs beta {m.corr_score_beta.mean():.3f} (0 = signal already neutral)')
d = pd.concat(deciles, axis=1).mean(axis=1)
print('Mean monthly alpha by score decile (1 = worst):', ' '.join(f'{v:+.2%}' for v in d))
print('\nBy year:'); m['year'] = m.index.str[:4]
print(m.groupby('year').agg(ic_alpha=('ic_alpha', 'mean'), spread_alpha=('spread_alpha', 'mean')).round(4).to_string())
m.to_csv(HERE / 'outputs' / f'signal_check_{start}_{end}.csv')

"""STEP 3: eligibility and which ranked names become long/short candidates.

Eligibility establishes the ranking universe; candidate selection follows ranking.
The weights themselves are chosen later by constraints.py / the sizing engine.
"""
import numpy as np
import pandas as pd

MIN_PRICE = 5.0
N_PER_LEG = 100

def prepare_universe(g, settings):
    # ONLY this price screen. Missing ranking controls are imputed, not filtered.
    g = g.loc[np.isfinite(g.prc) & (g.prc.abs() >= MIN_PRICE)].copy().reset_index(drop=True)
    for column, fallback in [('me',1.0),('beta_use',1.0),('rvol_21d',.02)]:
        g[column]=g[column].replace([np.inf,-np.inf],np.nan)
        g[column]=g[column].fillna(g.groupby('target_month')[column].transform('median')).fillna(fallback)
    return g


def candidate_schedule(scores, settings):
    for month,g in scores.groupby('target_month',sort=True):
        order=g.sort_values(['score','permno'],ascending=[False,True],kind='stable')
        if len(order)<2*N_PER_LEG:
            raise ValueError(f'{month}: insufficient price-eligible names')
        chosen=pd.concat([order.head(N_PER_LEG),order.tail(N_PER_LEG)]).set_index('permno').copy()
        chosen['side']=np.r_[np.ones(N_PER_LEG),-np.ones(N_PER_LEG)]
        yield month,chosen

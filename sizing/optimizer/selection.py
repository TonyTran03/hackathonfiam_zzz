"""STEP 3: eligibility and which ranked names become long/short candidates.

Eligibility establishes the ranking universe; candidate selection follows ranking.
The weights themselves are chosen later by constraints.py / the sizing engine.
"""
import numpy as np
import pandas as pd

N_PER_LEG = 150
BUFFER_MULT = 2.5
SHORT_MIN_ME_MUSD = 500.0
MIN_PRICE = 5.0
EXCLUDED_SIZE_GROUPS = ('nano', 'micro')


def validate(settings):
    if not 100 <= N_PER_LEG <= 250:
        raise ValueError('Select 200-500 names total.')
    if BUFFER_MULT < 1:
        raise ValueError('BUFFER_MULT must be at least 1.')
    if 2*N_PER_LEG*settings.minimum_position_weight > settings.gross_limit:
        raise ValueError('Minimum allocations exceed the gross limit.')


def prepare_universe(g, settings):
    keep = ((g.prc.abs() >= MIN_PRICE)
            & ~g.size_grp.isin(EXCLUDED_SIZE_GROUPS)
            & np.isfinite(g.beta_use) & np.isfinite(g.rvol_21d) & (g.rvol_21d > 0)
            & np.isfinite(g.me) & (g.me > 0))
    return g.loc[keep].copy().reset_index(drop=True)

def candidate_schedule(scores, settings):
    """Select long/short candidates from rankings, without consulting outcomes."""
    held_long, held_short = set(), set()
    for month, g in scores.groupby('target_month', sort=True):
        order = g.sort_values(['score', 'permno'], ascending=[False, True], kind='stable')
        wide = int(N_PER_LEG * BUFFER_MULT)
        # Same rank/retention recipe as the inherited selection, with short eligibility.
        long_zone = set(order.head(wide).permno)
        long_ids = [p for p in order.permno if p in held_long and p in long_zone][:N_PER_LEG]
        long_ids += [p for p in order.permno if p not in long_ids and p not in held_short][
            :N_PER_LEG - len(long_ids)]
        short_order = order[order.me >= SHORT_MIN_ME_MUSD].iloc[::-1]
        short_zone = set(short_order.head(wide).permno)
        short_ids = [p for p in short_order.permno
                     if p in held_short and p in short_zone and p not in long_ids][:N_PER_LEG]
        short_ids += [p for p in short_order.permno if p not in short_ids and p not in long_ids][
            :N_PER_LEG - len(short_ids)]
        if len(long_ids) != N_PER_LEG or len(short_ids) != N_PER_LEG:
            raise ValueError(f'{month}: not enough eligible stocks for both legs.')
        chosen = g.set_index('permno').loc[long_ids + short_ids].copy()
        chosen['side'] = np.r_[np.ones(len(long_ids)), -np.ones(len(short_ids))]
        held_long, held_short = set(long_ids), set(short_ids)
        yield month, chosen

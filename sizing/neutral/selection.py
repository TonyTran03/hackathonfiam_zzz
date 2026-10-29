"""STEP 3: eligibility and which ranked names become long/short candidates.

Mentor review (2026-10-29): take the top names for the long leg, but let the short leg
draw from a wider bottom pool so the optimizer can meet sector and size neutrality.
Candidates are not forced into the book: the optimizer may give any of them ~zero weight.
"""
import os

import numpy as np
import pandas as pd

N_LONG = int(os.environ.get('N_LONG', 150))
N_SHORT = int(os.environ.get('N_SHORT', 300))
BUFFER_MULT = 2.5
SHORT_MIN_ME_MUSD = 500.0
MIN_PRICE = 5.0
EXCLUDED_SIZE_GROUPS = ('nano', 'micro')


def validate(settings):
    # With a zero short floor the pool can exceed 500: the held count is checked after solving.
    if settings.short_minimum_weight is None and not 200 <= N_LONG + N_SHORT <= 500:
        raise ValueError('Candidate pool must keep the book within 200-500 names.')
    if BUFFER_MULT < 1:
        raise ValueError('BUFFER_MULT must be at least 1.')
    if N_LONG * settings.minimum_position_weight > settings.gross_limit:
        raise ValueError('Minimum allocations exceed the gross limit.')


def prepare_universe(g, settings):
    keep = ((g.prc.abs() >= MIN_PRICE)
            & ~g.size_grp.isin(EXCLUDED_SIZE_GROUPS)
            & np.isfinite(g.beta_use) & np.isfinite(g.rvol_21d) & (g.rvol_21d > 0)
            & np.isfinite(g.me) & (g.me > 0))
    return g.loc[keep].copy().reset_index(drop=True)


def _leg(order, held, n, exclude):
    zone = set(order.head(int(n * BUFFER_MULT)).permno)
    ids = [p for p in order.permno if p in held and p in zone and p not in exclude][:n]
    ids += [p for p in order.permno if p not in ids and p not in exclude][:n - len(ids)]
    return ids


def candidate_schedule(scores, settings):
    """Select long/short candidates from rankings, without consulting outcomes."""
    held_long, held_short = set(), set()
    for month, g in scores.groupby('target_month', sort=True):
        order = g.sort_values(['score', 'permno'], ascending=[False, True], kind='stable')
        long_ids = _leg(order, held_long, N_LONG, held_short)
        short_order = order[order.me >= SHORT_MIN_ME_MUSD].iloc[::-1]
        short_ids = _leg(short_order, held_short, N_SHORT, set(long_ids))
        if len(long_ids) != N_LONG or len(short_ids) != N_SHORT:
            raise ValueError(f'{month}: not enough eligible stocks for both legs.')
        chosen = g.set_index('permno').loc[long_ids + short_ids].copy()
        chosen['side'] = np.r_[np.ones(len(long_ids)), -np.ones(len(short_ids))]
        held_long, held_short = set(long_ids), set(short_ids)
        yield month, chosen

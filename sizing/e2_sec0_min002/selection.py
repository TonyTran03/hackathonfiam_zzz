"""STEP 3: sector-balanced candidate selection.

Instead of taking the globally top-ranked 150 names per leg, allocate each
leg's slots across sectors in proportion to the sector's share of the eligible
universe, then rank WITHIN each sector. Both legs get the same count in every
sector, so no sector carries a structural long or short tilt from selection.

Why this costs little: ranking.py already regresses the score on sector
dummies, so the score is sector-demeaned by construction. Selecting within
sector therefore discards information the signal is not supposed to contain.

Equal COUNTS per sector does not by itself give equal WEIGHTS -- the optimiser
still sizes positions. What this does is make a tight sector_limit FEASIBLE,
which it was not before: with global ranking, 2.5 sectors a month had more
longs than the short leg could ever offset given the 0.1% minimum per name.
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
    if 2 * N_PER_LEG * settings.minimum_position_weight > settings.gross_limit:
        raise ValueError('Minimum allocations exceed the gross limit.')


def prepare_universe(g, settings):
    keep = ((g.prc.abs() >= MIN_PRICE)
            & ~g.size_grp.isin(EXCLUDED_SIZE_GROUPS)
            & np.isfinite(g.beta_use) & np.isfinite(g.rvol_21d) & (g.rvol_21d > 0)
            & np.isfinite(g.me) & (g.me > 0))
    return g.loc[keep].copy().reset_index(drop=True)


def _quota(g, short_ok, n):
    """Slots per sector: proportional to universe share, capped by what each
    sector can actually supply on BOTH legs, with the remainder redistributed."""
    sectors = sorted(g.sector.unique())
    cap = {s: min(int((g.sector == s).sum()), int((short_ok.sector == s).sum()))
           for s in sectors}
    # Floor first so we can only ever be SHORT of n, never over it.
    want = {s: min(cap[s], (n * int((g.sector == s).sum())) // len(g)) for s in sectors}
    while sum(want.values()) < n:
        room = [s for s in sectors if want[s] < cap[s]]
        if not room:
            raise ValueError('no sector has spare capacity for both legs')
        room.sort(key=lambda s: (cap[s] - want[s], s), reverse=True)
        want[room[0]] += 1
    return want


def candidate_schedule(scores, settings):
    held_long, held_short = set(), set()
    for month, g in scores.groupby('target_month', sort=True):
        short_ok = g[g.me >= SHORT_MIN_ME_MUSD]
        want = _quota(g, short_ok, N_PER_LEG)
        longs, shorts = [], []
        for s, k in want.items():
            if k <= 0:
                continue
            gs = g[g.sector == s].sort_values(['score', 'permno'],
                                              ascending=[False, True], kind='stable')
            ss = short_ok[short_ok.sector == s].sort_values(
                ['score', 'permno'], ascending=[True, True], kind='stable')
            # Retention buffer, applied inside the sector so incumbents that are
            # still ranked well in their own sector keep their slot.
            wide = int(k * BUFFER_MULT)
            lz, sz = set(gs.permno.head(wide)), set(ss.permno.head(wide))
            pick_l = [p for p in gs.permno if p in held_long and p in lz][:k]
            pick_l += [p for p in gs.permno if p not in pick_l][:k - len(pick_l)]
            taken = set(pick_l)
            pick_s = [p for p in ss.permno if p in held_short and p in sz
                      and p not in taken][:k]
            pick_s += [p for p in ss.permno if p not in pick_s and p not in taken][
                :k - len(pick_s)]
            longs += pick_l
            shorts += pick_s
        if len(longs) != N_PER_LEG or len(shorts) != N_PER_LEG:
            raise ValueError(f'{month}: sector quotas filled {len(longs)}/{len(shorts)}.')
        chosen = g.set_index('permno').loc[longs + shorts].copy()
        chosen['side'] = np.r_[np.ones(len(longs)), -np.ones(len(shorts))]
        held_long, held_short = set(longs), set(shorts)
        yield month, chosen

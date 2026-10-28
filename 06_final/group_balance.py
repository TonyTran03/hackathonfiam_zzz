import numpy as np
import pandas as pd


def group_balance(target, perms_n, g, nav, gross_goal, industry_cap=None, iters=30, fill_rounds=25):
    """Sector-neutral (optionally industry-capped) book at formation.

    Phase A, SHRINK (unchanged from v1): industry cap -> sector net 0 (heavier
    side down; one-sided sector closed) -> per-name caps, repeated until stable.

    Phase B, REFILL (v2; replaces v1's single uniform scale-up, which any one
    name sitting at its cap blocked, so gross fell to ~90-115%): scale every
    name that still has room up toward the gross goal, each clipped at its own
    cap, then run Phase A again to restore the constraints. Repeat until gross
    stops rising. Constraints hold after every round because Phase A ends it.
    Returns new target ($), max |sector net| and max |industry net| (% of NAV),
    and the gross reached (fraction of NAV).
    """
    gics = np.full(perms_n, "", dtype=object)
    gics[g["pi"].values] = [("%.0f" % float(v)) if pd.notna(v) else "" for v in g["gics"].values]
    sec = np.array([s[:2] if s else "zz" for s in gics], dtype=object)
    ind = np.array([s[:6] if s else "zz" for s in gics], dtype=object)
    caps = np.full(perms_n, np.inf)
    caps[g["pi"].values] = g["cap"].values * nav
    t = target.astype(float).copy()

    def shrink_heavy(mask, allowed):
        L, S = t[mask & (t > 0)].sum(), -t[mask & (t < 0)].sum()
        net = L - S
        if abs(net) <= allowed + 1e-9:
            return
        side = mask & ((t > 0) if net > 0 else (t < 0))
        H = L if net > 0 else S
        t[side] *= max(H - (abs(net) - allowed), 0.0) / H

    def shrink_phase():
        nonlocal t
        for _ in range(iters):
            before = t.copy()
            if industry_cap is not None:
                for k in np.unique(ind[t != 0]):
                    shrink_heavy(ind == k, industry_cap * nav)
            for k in np.unique(sec[t != 0]):
                m = sec == k
                if (t[m] > 0).any() and (t[m] < 0).any():
                    shrink_heavy(m, 0.0)
                else:
                    t[m] = 0.0
            t = np.clip(t, -caps, caps)
            if np.abs(t - before).max() < 1.0:
                break

    shrink_phase()
    goal = gross_goal * nav
    for _ in range(fill_rounds):
        gross = np.abs(t).sum()
        if gross <= 0 or gross >= goal * 0.999:
            break
        room = (t != 0) & (np.abs(t) < caps - 1.0)
        if not room.any():
            break
        f = goal / gross
        t[room] = np.sign(t[room]) * np.minimum(np.abs(t[room]) * f, caps[room])
        shrink_phase()
        if np.abs(t).sum() <= gross * 1.0005:          # no more progress
            break

    held = t != 0
    sn = max([abs(t[sec == k].sum()) for k in np.unique(sec[held])] or [0.0]) / nav
    inn = max([abs(t[ind == k].sum()) for k in np.unique(ind[held])] or [0.0]) / nav
    return t, 100 * sn, 100 * inn, np.abs(t).sum() / nav

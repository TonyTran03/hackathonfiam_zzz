import numpy as np
import pandas as pd


def group_balance(target, perms_n, g, nav, gross_goal, industry_cap=None, iters=30):
    """Sector-neutral, optionally industry-capped, book at formation.

    target      : $ positions per permno index (len = perms_n), output of the usual
                  selection / inverse-vol sizing / no-trade band
    g           : this month's rows with columns pi, gics, cap (fraction of NAV)
    gross_goal  : gross we would like to keep (fraction of NAV), e.g. GROSS_TARGET
    industry_cap: max |net| per GICS 6-digit industry, fraction of NAV (e.g. 0.02);
                  None = sector-neutral only

    Every step below only SHRINKS positions, so nothing re-breaks a cap:
      1. industry: if |net| > cap, scale the heavier side of that industry down
      2. sector  : scale the heavier side down to the lighter side (net = 0);
                   a one-sided sector is closed
      3. per-name liquidity / 5% caps
    Repeated until stable. Then ONE uniform scale-up restores gross as far as
    the caps and the industry limit allow; a uniform scale keeps every sector
    at exactly 0 and every industry inside its cap.
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
        if np.abs(t - before).max() < 1.0:          # $1 tolerance
            break

    gross = np.abs(t).sum()
    if gross > 0:
        f = gross_goal * nav / gross
        held = t != 0
        f = min(f, np.min(caps[held] / np.abs(t[held])))
        if industry_cap is not None:
            nets = [abs(t[ind == k].sum()) for k in np.unique(ind[held])]
            mx = max(nets) if nets else 0.0
            if mx > 1e-9:
                f = min(f, industry_cap * nav / mx)
        t *= max(f, 1.0)

    held = t != 0
    sn = max([abs(t[sec == k].sum()) for k in np.unique(sec[held])] or [0.0]) / nav
    inn = max([abs(t[ind == k].sum()) for k in np.unique(ind[held])] or [0.0]) / nav
    return t, 100 * sn, 100 * inn, np.abs(t).sum() / nav

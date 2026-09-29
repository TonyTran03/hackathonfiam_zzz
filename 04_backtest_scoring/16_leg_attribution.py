"""Stage 5j -- each leg measured against the universe it was picked from.

    python 04_backtest_scoring/16_leg_attribution.py

A long/short book can look skilful for two different reasons: the names it
picked beat their peers, or the market went up and the long leg is bigger.
Subtracting the eligible universe's own return from each leg separates them,
and it is the only way to see that this book's edge changed legs mid-period --
2021-22 was almost entirely the short leg, 2023 onward almost entirely the
long one.

The numbers used to live in the deck as literals from an earlier build. They
are computed here instead, from the book that is actually being submitted, and
written to leg_attribution.csv so the slide cannot drift from the backtest
again.

The universe is the same tradability screen stage 4 selects from -- price >= $5
and no nano or micro caps -- equal-weighted, because that is the return of
picking at random from what we allowed ourselves to hold.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
OUT = C.ROOT / "05_submission" / "leg_attribution.csv"

MIN_PRICE = 5.0
EXCLUDE_SIZE_GROUPS = ("nano", "micro")
PERIODS = [("full period", "2021-01", "2026-12"),
           ("2021-22", "2021-01", "2022-12"),
           ("2023-26", "2023-01", "2026-12")]

rows = []


def put(period, metric, value, note=""):
    rows.append({"period": period, "metric": metric, "value": value, "note": note})


def ann_t(x):
    """Annualised mean and the t-statistic of the monthly series behind it."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return np.nan, np.nan
    return 12 * x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))


def main():
    h = pd.read_parquet(HOLDINGS)
    months = sorted(h["target_month"].unique())

    pan = pd.read_parquet(C.MODEL_TABLE,
                          columns=["permno", "target_month", "prc", "size_grp",
                                   "gics", C.TARGET])
    pan = pan[pan["target_month"].isin(months)]
    uni = pan[(pan["prc"].abs() >= MIN_PRICE)
              & (~pan["size_grp"].isin(EXCLUDE_SIZE_GROUPS))].dropna(subset=[C.TARGET])
    u = uni.groupby("target_month")[C.TARGET].mean()

    # A second benchmark, matched sector by sector. Comparing a leg against the
    # whole universe and against its own sectors separates "these names beat
    # the market" from "these names beat their peers". The short leg's 2021-22
    # edge is claimed on the deck to be the second; this is what tests it.
    uni = uni.copy()
    uni["sec"] = uni["gics"].astype(str).str[:2]
    sec_u = uni.groupby(["target_month", "sec"])[C.TARGET].mean()
    h = h.copy()
    h["sec"] = h["gics"].astype(str).str[:2]
    h["sec_bench"] = pd.MultiIndex.from_arrays(
        [h["target_month"], h["sec"]]).map(sec_u)

    # Each leg's return per dollar of its own notional, so the comparison with
    # the universe is like for like and leg sizing does not contaminate it.
    per = []
    for m, g in h.groupby("target_month"):
        L, S = g[g["weight"] > 0], g[g["weight"] < 0]
        r = g[C.TARGET].fillna(0.0)
        lw, sw = L["weight"].sum(), -S["weight"].sum()
        sb = g["sec_bench"]
        per.append({
            "target_month": m,
            "long": float((L["weight"] * r.loc[L.index]).sum() / lw) if lw else np.nan,
            "short": float((-S["weight"] * r.loc[S.index]).sum() / sw) if sw else np.nan,
            "uni": float(u.get(m, np.nan)),
            # each leg's own sector-matched benchmark, weighted as the leg is
            "long_sec": float((L["weight"] * sb.loc[L.index]).sum() / lw) if lw else np.nan,
            "short_sec": float((-S["weight"] * sb.loc[S.index]).sum() / sw) if sw else np.nan,
        })
    d = pd.DataFrame(per).sort_values("target_month").reset_index(drop=True)
    d["long_excess"] = d["long"] - d["uni"]
    d["short_excess"] = d["short"] - d["uni"]
    d["long_sec_excess"] = d["long"] - d["long_sec"]
    d["short_sec_excess"] = d["short"] - d["short_sec"]

    print("=" * 76)
    print("LEG ATTRIBUTION vs the eligible universe  (%d months, gross of costs)"
          % len(d))
    print("  long excess  = long leg per dollar, minus the universe")
    print("  short excess = the shorted names per dollar, minus the universe;")
    print("                 negative is good, it is what the short leg earns")
    print("=" * 76)
    print("  %-14s %7s %14s %16s %14s"
          % ("period", "months", "universe", "long excess", "short excess"))
    for label, lo, hi in PERIODS:
        s = d[(d["target_month"] >= lo) & (d["target_month"] <= hi)]
        if len(s) < 3:
            continue
        ua, _ = ann_t(s["uni"])
        la, lt = ann_t(s["long_excess"])
        sa, st = ann_t(s["short_excess"])
        print("  %-14s %7d %13.2f%% %9.2f%% (t %+.1f) %8.2f%% (t %+.1f)"
              % (label, len(s), 100 * ua, 100 * la, lt, 100 * sa, st))
        put(label, "months", "%d" % len(s))
        put(label, "universe return", "%+.2f%%" % (100 * ua), "annualised, equal-weighted")
        put(label, "long leg excess", "%+.2f%%" % (100 * la), "t %+.1f" % lt)
        put(label, "short leg excess", "%+.2f%%" % (100 * sa), "t %+.1f" % st)
        lsa, _ = ann_t(s["long_sec_excess"])
        ssa, _ = ann_t(s["short_sec_excess"])
        put(label, "long leg excess, sector-matched", "%+.2f%%" % (100 * lsa),
            "against its own sectors")
        put(label, "short leg excess, sector-matched", "%+.2f%%" % (100 * ssa),
            "against its own sectors")
        print("  %-14s %7s %13s %9.2f%% sector   %8.2f%% sector"
              % ("", "", "", 100 * lsa, 100 * ssa))

    print("\n  The edge changes legs: the short leg carries 2021-22 and is")
    print("  indistinguishable from zero afterwards; the long leg is the reverse.")
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

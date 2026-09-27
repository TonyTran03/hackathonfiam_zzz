"""Is the sector-neutral verdict robust, or an artefact of how I built it?

    python 03_portfolio_construction/exp_sector_robustness.py

exp_sector_neutral.py found that picking inside sectors (B) loses on the clean
validation window and gains nothing on the evaluation period. Before that is
written down as a finding, the arbitrary choices inside it have to be varied,
because any one of them could be doing the work:

  quota rule      seats proportional to each sector's share of the universe,
                  or the same number of seats for every sector, or seats
                  proportional to each sector's share of market value
  smoothing       how many months of score are averaged before ranking
  buffer          how far a held name may drift before it is sold
  timing          is the loss spread across months, or three bad ones

A verdict that survives all of them is a finding. One that flips is a
parameter choice wearing a finding's clothes.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import config as C

_spec = importlib.util.spec_from_file_location(
    "sn", ROOT / "03_portfolio_construction" / "exp_sector_neutral.py")
sn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sn)
bp = sn.bp

OUT = C.ROOT / "05_submission" / "exp_sector_robustness.csv"


def quotas_equal(sec, n):
    """Same number of seats for every sector present this month."""
    names = sec.unique()
    base = n // len(names)
    q = pd.Series(base, index=names)
    short = n - int(q.sum())
    if short > 0:
        q[sec.value_counts().index[:short]] += 1
    return q


def make_quota_by_value(me):
    """Seats proportional to each sector's share of market value."""
    def f(sec, n):
        # `sec` covers one month; `me` spans the window, so align on the index
        # the selector passed in rather than assuming equal lengths.
        val = me.reindex(sec.index).groupby(sec.values).sum()
        raw = val / val.sum() * n
        q = raw.astype(int)
        short = n - int(q.sum())
        if short > 0:
            q[(raw - q).sort_values(ascending=False).index[:short]] += 1
        return q
    return f


def build_B(pred, smooth, buf, market, quota_fn):
    """Variant B with a swappable quota rule."""
    orig = sn.quotas
    if quota_fn is not None:
        sn.quotas = quota_fn
    try:
        return sn.make_book(pred, smooth, buf, market, within_sector=True)
    finally:
        sn.quotas = orig


def spread_of(book):
    b = book.copy()
    b["pnl"] = b["weight"] * b[C.TARGET].fillna(0.0)
    return b.groupby("target_month")["pnl"].sum()


def ir_of(spread):
    a = spread.values - bp.PREMIUM_M
    return np.sqrt(12) * a.mean() / a.std(ddof=1)


def main():
    market = bp.load_market()
    rows = []

    # ------------------------------------------------ the two windows -------
    bj = json.loads((C.PROCESSED_DIR / "blend.json").read_text(encoding="utf-8"))
    parts = bj["per_fold"][sorted(bj["per_fold"])[0]]["parts"]
    val = pd.read_parquet(C.PROCESSED_DIR / "validation_predictions.parquet")
    val = val[val["target_month"] <= bp.TUNE_END].drop_duplicates(
        ["permno", "target_month"], keep="first")
    if "avg_linear" in parts and "avg_linear" not in val.columns:
        val["avg_linear"] = val[["ols", "lasso", "ridge", "en"]].mean(axis=1)
    z = val.groupby("target_month")[parts].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
    val[bp.MODEL] = z.mean(axis=1)
    SV = bp.screen(val, quiet=True)

    pred = pd.read_parquet(bp.PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    ST = bp.screen(pred[(pred["target_month"] >= lo)
                        & (pred["target_month"] <= hi)].copy(), quiet=True)
    WIN = [("validation", SV), ("evaluation", ST)]

    # ------------------------------------------------ 1. quota rule ---------
    print("=" * 78)
    print("1. DOES THE QUOTA RULE DECIDE IT?   (smoothing 3, buffer 2.5)")
    print("=" * 78)
    print("  %-14s %-26s %10s %10s" % ("window", "rule", "IR", "vs baseline"))
    for wname, W in WIN:
        base = ir_of(spread_of(sn.make_book(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market)))
        print("  %-14s %-26s %+10.2f %10s" % (wname, "baseline (no quota)", base, "--"))
        rules = [("B: share of names", None),
                 ("B: equal seats", quotas_equal),
                 ("B: share of market value", make_quota_by_value(W["me"]))]
        for label, fn in rules:
            v = ir_of(spread_of(build_B(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market, fn)))
            print("  %-14s %-26s %+10.2f %+10.2f" % (wname, label, v, v - base))
            rows.append({"test": "quota rule", "window": wname, "variant": label,
                         "IR": v, "vs_baseline": v - base})

    # ------------------------------------------------ 2. smoothing/buffer ---
    print("\n" + "=" * 78)
    print("2. DOES THE TURNOVER SETTING DECIDE IT?   (quota = share of names)")
    print("=" * 78)
    for wname, W in WIN:
        print("  %s" % wname)
        print("    %-22s %10s %10s %10s" % ("smooth / buffer", "baseline", "B", "B - base"))
        for sm in [1, 3, 6]:
            for bf in [1.6, 2.5]:
                a = ir_of(spread_of(sn.make_book(W, sm, bf, market)))
                b = ir_of(spread_of(build_B(W, sm, bf, market, None)))
                flag = "  <-- B wins" if b > a else ""
                print("    %-22s %+10.2f %+10.2f %+10.2f%s"
                      % ("%d months / %.1fx" % (sm, bf), a, b, b - a, flag))
                rows.append({"test": "turnover setting", "window": wname,
                             "variant": "smooth %d buffer %.1f" % (sm, bf),
                             "IR": b, "vs_baseline": b - a})

    # ------------------------------------------------ 3. timing -------------
    print("\n" + "=" * 78)
    print("3. IS THE GAP A FEW MONTHS, OR ALL OF THEM?")
    print("=" * 78)
    for wname, W in WIN:
        a = spread_of(sn.make_book(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market))
        b = spread_of(build_B(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market, None))
        d = (b - a).dropna()
        wins = int((d > 0).sum())
        print("  %-12s B beats baseline in %2d of %2d months (%.0f%%)   "
              "mean gap %+.3f%%/month  t %+.2f"
              % (wname, wins, len(d), 100 * wins / len(d), 100 * d.mean(),
                 d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))))
        worst = d.nsmallest(3)
        print("               worst 3 months for B: %s"
              % ", ".join("%s %+.1f%%" % (m, 100 * v) for m, v in worst.items()))
        ex = d.drop(worst.index)
        print("               excluding those 3: mean gap %+.3f%%/month  -> B %s"
              % (100 * ex.mean(), "still behind" if ex.mean() < 0 else "AHEAD"))
        rows.append({"test": "timing", "window": wname, "variant": "B minus baseline",
                     "IR": np.nan, "vs_baseline": 12 * d.mean()})

    # ------------------------------------------------ 4. sub-windows --------
    print("\n" + "=" * 78)
    print("4. WITHIN THE VALIDATION WINDOW, IS IT BOTH YEARS?")
    print("=" * 78)
    a = spread_of(sn.make_book(SV, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market))
    b = spread_of(build_B(SV, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market, None))
    for yr in ["2019", "2020"]:
        k = [m for m in a.index if m.startswith(yr)]
        print("  %s   baseline IR %+.2f   B IR %+.2f   %s"
              % (yr, ir_of(a[k]), ir_of(b[k]),
                 "B better" if ir_of(b[k]) > ir_of(a[k]) else "B worse"))
        rows.append({"test": "sub-window", "window": yr, "variant": "B",
                     "IR": ir_of(b[k]), "vs_baseline": ir_of(b[k]) - ir_of(a[k])})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    beat = [r for r in rows if r["test"] in ("quota rule", "turnover setting")
            and r["vs_baseline"] > 0]
    tot = [r for r in rows if r["test"] in ("quota rule", "turnover setting")]
    print("\n" + "=" * 78)
    print("VERDICT: B beats the baseline in %d of %d configurations tested."
          % (len(beat), len(tot)))
    for r in beat:
        print("  the exceptions: %s / %s  %+.2f" % (r["window"], r["variant"], r["vs_baseline"]))
    print("wrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

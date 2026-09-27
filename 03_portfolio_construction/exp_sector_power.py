"""Can this evidence settle the sector-neutrality question at all?

    python 03_portfolio_construction/exp_sector_power.py

Two earlier experiments left the verdict at "cannot tell": B beat the baseline
in 7 of 18 configurations, and no t-statistic came near significance. That is
not the same as "B does not work", and the difference matters, because one of
them is a statement about the idea and the other is a statement about our
sample. This script separates them.

  1 POWER        how large an improvement would a 24-month window have to see
                 before it could call it real? If the smallest detectable gain
                 is bigger than any gain worth having, the window can never
                 return anything but "cannot tell", and the two experiments
                 before this one were never capable of deciding.
  2 BOOTSTRAP    resample months and look at the whole distribution of the
                 difference, not one point estimate.
  3 THE SWEEP    under a true null, how often would 18 configurations throw up
                 a winner as good as our best one? If the answer is "usually",
                 the best config is noise rather than a finding.
  4 RISK         IR is one question; a market-neutral mandate also cares about
                 drawdown and tails. A change can be flat on return and still
                 be worth making, or not.

A pre-specified configuration is used throughout: seats proportional to each
sector's share of market value -- how a sector-neutral book is actually run --
at the production turnover settings, which were fixed long before any of this.
Choosing the configuration after seeing the sweep is the mistake the sweep was
written to expose.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import config as C

_spec = importlib.util.spec_from_file_location(
    "sn", ROOT / "03_portfolio_construction" / "exp_sector_neutral.py")
sn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sn)
bp = sn.bp

_spec2 = importlib.util.spec_from_file_location(
    "rb", ROOT / "03_portfolio_construction" / "exp_sector_robustness.py")
rb = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(rb)

OUT = C.ROOT / "05_submission" / "exp_sector_power.csv"
RNG = np.random.default_rng(20260927)


def spread_of(book):
    b = book.copy()
    b["pnl"] = b["weight"] * b[C.TARGET].fillna(0.0)
    return b.groupby("target_month")["pnl"].sum()


def ir_of(s):
    a = np.asarray(s) - bp.PREMIUM_M
    return np.sqrt(12) * a.mean() / a.std(ddof=1)


def windows():
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
    pred = pd.read_parquet(bp.PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    return [("validation", bp.screen(val, quiet=True)),
            ("evaluation", bp.screen(
                pred[(pred["target_month"] >= lo)
                     & (pred["target_month"] <= hi)].copy(), quiet=True))]


def main():
    market = bp.load_market()
    rows = []
    series = {}
    for wname, W in windows():
        a = spread_of(sn.make_book(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market))
        b = spread_of(rb.build_B(W, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market,
                                 rb.make_quota_by_value(W["me"])))
        series[wname] = (a, b)

    # ------------------------------------------------------------- 1. POWER
    print("=" * 80)
    print("1. POWER -- what is the smallest improvement each window could detect?")
    print("=" * 80)
    print("  %-12s %7s %12s %14s %16s"
          % ("window", "months", "sd of diff", "observed diff", "min detectable"))
    for wname, (a, b) in series.items():
        d = (b - a).dropna().values
        n = len(d)
        # two-sided, 5%, 80% power: |mu| >= (z_a/2 + z_b) * sd / sqrt(n)
        mde = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * d.std(ddof=1) / np.sqrt(n)
        print("  %-12s %7d %11.3f%% %13.3f%% %15.3f%%/month"
              % (wname, n, 100 * d.std(ddof=1), 100 * d.mean(), 100 * mde))
        # express it as the IR gap that would be needed
        ir_gap = np.sqrt(12) * mde / a.std(ddof=1)
        print("  %-12s %s an IR gap below %+.2f is invisible to this window"
              % ("", " " * 28, ir_gap))
        rows.append({"test": "power", "window": wname, "n": n,
                     "observed_diff_pm": 100 * d.mean(),
                     "min_detectable_pm": 100 * mde, "detectable_IR_gap": ir_gap})

    # --------------------------------------------------------- 2. BOOTSTRAP
    print("\n" + "=" * 80)
    print("2. BOOTSTRAP -- the whole distribution of the IR difference")
    print("=" * 80)
    for wname, (a, b) in series.items():
        n = len(a)
        diffs = np.empty(10000)
        for i in range(10000):
            k = RNG.integers(0, n, n)
            diffs[i] = ir_of(b.values[k]) - ir_of(a.values[k])
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        print("  %-12s B - baseline IR:  point %+.2f   95%% interval [%+.2f, %+.2f]"
              % (wname, ir_of(b) - ir_of(a), lo, hi))
        print("  %-12s %sP(B better) = %.0f%%   interval %s zero"
              % ("", " " * 18, 100 * (diffs > 0).mean(),
                 "straddles" if lo < 0 < hi else "excludes"))
        rows.append({"test": "bootstrap", "window": wname,
                     "point": ir_of(b) - ir_of(a), "lo": lo, "hi": hi,
                     "p_better": (diffs > 0).mean()})

    # ---------------------------------------------------------- 3. THE SWEEP
    print("\n" + "=" * 80)
    print("3. THE SWEEP -- is our best configuration better than luck?")
    print("=" * 80)
    prev = pd.read_csv(C.ROOT / "05_submission" / "exp_sector_robustness.csv")
    sweep = prev[prev["test"].isin(["quota rule", "turnover setting"])]
    wins, tot = int((sweep["vs_baseline"] > 0).sum()), len(sweep)
    best = sweep["vs_baseline"].max()
    p_binom = stats.binomtest(wins, tot, 0.5).pvalue
    print("  configurations tested: %d   B ahead in %d (%.0f%%)   binomial p = %.2f"
          % (tot, wins, 100 * wins / tot, p_binom))
    print("  best configuration: %+.2f IR" % best)
    # under a null of no effect, draw 18 independent differences with the
    # bootstrap's own spread and ask how often the best of them reaches ours
    a, b = series["validation"]
    n = len(a)
    sd = np.std([ir_of(b.values[RNG.integers(0, n, n)]) - ir_of(a.values[RNG.integers(0, n, n)])
                 for _ in range(2000)], ddof=1)
    draws = RNG.normal(0.0, sd, size=(20000, tot))
    print("  under a true null with the same spread (sd %.2f), the best of %d"
          % (sd, tot))
    print("  configurations reaches %+.2f or more %.0f%% of the time"
          % (best, 100 * (draws.max(axis=1) >= best).mean()))
    rows.append({"test": "sweep", "n": tot, "wins": wins, "p_binom": p_binom,
                 "best": best,
                 "p_best_by_luck": float((draws.max(axis=1) >= best).mean())})

    # ---------------------------------------------------------------- 4. RISK
    print("\n" + "=" * 80)
    print("4. RISK -- flat on return is not the same as flat on risk")
    print("=" * 80)
    bm = pd.read_csv(C.BENCHMARK_CSV).set_index("target_month")["cash_monthly"]
    print("  %-12s %-10s %8s %9s %10s %11s %10s"
          % ("window", "book", "vol", "maxDD", "worst mo", "worst 5%", "downside sd"))
    for wname, (a, b) in series.items():
        for lab, s in [("baseline", a), ("B", b)]:
            tot_r = bm.reindex(s.index).values + s.values
            curve = (1 + pd.Series(tot_r)).cumprod()
            dd = 100 * (curve / curve.cummax() - 1).min()
            tail = 100 * np.mean(np.sort(s.values)[:max(1, len(s) // 20)])
            dn = 100 * np.sqrt(12) * s.values[s.values < 0].std(ddof=1)
            print("  %-12s %-10s %7.2f%% %+8.2f%% %+9.2f%% %+10.2f%% %9.2f%%"
                  % (wname, lab, 100 * np.sqrt(12) * s.std(ddof=1), dd,
                     100 * s.min(), tail, dn))
            rows.append({"test": "risk", "window": wname, "book": lab,
                         "vol": 100 * np.sqrt(12) * s.std(ddof=1), "maxdd": dd,
                         "worst": 100 * s.min(), "tail5": tail, "downside_sd": dn})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

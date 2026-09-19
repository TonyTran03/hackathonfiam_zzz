"""Turn 8-K filings into stock-month signals -- without reading the text.

    python 01_data/filing_features.py            # build the feature table
    python 01_data/filing_features.py --explore  # + training-only sanity check

Three families of signal, cheapest first:

  disclosure delay   how long after the reported event the filing appeared.
                     `days_filing_after_content_report` is supplied directly.
                     Most reportable events carry a four-business-day deadline,
                     so filings past that are the interesting tail (12% of all).

  filing burst       this month's filing count against the stock's own trailing
                     twelve months. Computed on a gap-filled grid, so eleven
                     quiet months followed by two filings counts as a burst.

  event flags        item codes only, no text. 4.01/4.02 (auditor change,
                     financials no longer reliable) are described in the rules
                     as the two strongest distress signals in the corpus; they
                     are far too rare to sort a book on, so they are meant as a
                     veto overlay, not a predictor.

Timing: only filings dated inside month t may inform month t+1, so every row
is keyed by `target_month` = filing month + 1. Filing timestamps are
date-precision placeholders, so nothing here assumes an intraday cutoff.

Coverage: about half of the evaluation-window stock-months have no filing at
all. Those stocks are absent from this table by construction -- join with a
LEFT join and leave the gap missing. Dropping them would let filing coverage
silently redefine the universe.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

OUT = C.PROCESSED_DIR / "filing_features.parquet"

# Most Form 8-K items are due within four business days of the event.
DEADLINE_DAYS = 4
# Item codes worth flagging on their own. Everything else stays a count.
DISTRESS_ITEMS = {"4.01", "4.02"}
OFFICER_ITEMS = {"5.02"}
EARNINGS_ITEMS = {"2.02"}
AGREEMENT_ITEMS = {"1.01", "1.02"}

TRAILING_MONTHS = 12
MIN_HISTORY = 6          # months of history before a burst score is meaningful


def load_filings():
    if not C.FILINGS_PARQUET.exists():
        raise SystemExit(
            "missing dataset: %s\nPut the supplied Parquet files in 01_data/raw/ "
            "(see README)." % C.FILINGS_PARQUET)
    cols = ["permno", "filing_date", "items", "days_filing_after_content_report",
            "word_count", "document_id"]
    f = pq.read_table(C.FILINGS_PARQUET, columns=cols).to_pandas()
    f["filing_month"] = pd.to_datetime(f["filing_date"]).dt.to_period("M")
    f["delay_days"] = pd.to_numeric(f["days_filing_after_content_report"], errors="coerce")
    return f


def _has_item(items, wanted):
    if items is None:
        return False
    return any(code in wanted for code in items)


def per_filing_flags(f):
    f = f.copy()
    f["is_distress"] = [_has_item(i, DISTRESS_ITEMS) for i in f["items"]]
    f["is_officer"] = [_has_item(i, OFFICER_ITEMS) for i in f["items"]]
    f["is_earnings"] = [_has_item(i, EARNINGS_ITEMS) for i in f["items"]]
    f["is_agreement"] = [_has_item(i, AGREEMENT_ITEMS) for i in f["items"]]
    # negative delays mean the filing predates the reported event date; treat
    # them as same-day rather than as negative lateness
    f["late_days"] = f["delay_days"].clip(lower=0)
    f["is_late"] = f["late_days"] > DEADLINE_DAYS
    return f


def aggregate_to_month(f):
    """One row per stock-filing-month. Repeated filings must be collapsed here:
    joining them to the panel unaggregated would duplicate the panel's returns."""
    g = f.groupby(["permno", "filing_month"])
    out = pd.DataFrame({
        "n_filings": g.size(),
        "n_distress": g["is_distress"].sum(),
        "n_officer": g["is_officer"].sum(),
        "n_earnings": g["is_earnings"].sum(),
        "n_agreement": g["is_agreement"].sum(),
        "max_delay_days": g["late_days"].max(),
        "mean_delay_days": g["late_days"].mean(),
        "n_late": g["is_late"].sum(),
        "total_words": g["word_count"].sum(),
    }).reset_index()
    out["share_late"] = out["n_late"] / out["n_filings"]
    out["has_distress"] = (out["n_distress"] > 0).astype(int)
    out["has_officer_change"] = (out["n_officer"] > 0).astype(int)
    out["has_earnings"] = (out["n_earnings"] > 0).astype(int)
    return out


def add_filing_burst(monthly):
    """This month's count against the stock's own recent history.

    The grid is gap-filled so that quiet months count as zero -- otherwise a
    stock that files nothing for a year and then twice looks unremarkable.
    The trailing window is shifted by one month, so the current month never
    contributes to its own baseline.
    """
    last_month = monthly["filing_month"].max()
    frames = []
    for permno, grp in monthly.groupby("permno", sort=False):
        grid = pd.period_range(grp["filing_month"].min(), last_month, freq="M")
        s = (grp.set_index("filing_month")["n_filings"]
                .reindex(grid, fill_value=0)
                .astype(float))
        prior = s.shift(1)
        base = prior.rolling(TRAILING_MONTHS, min_periods=MIN_HISTORY).mean()
        frames.append(pd.DataFrame({
            "permno": permno,
            "filing_month": grid,
            "trailing_mean_filings": base.values,
        }))
    base = pd.concat(frames, ignore_index=True)
    monthly = monthly.merge(base, on=["permno", "filing_month"], how="left")
    # +0.5 keeps the ratio finite for stocks that normally file nothing
    monthly["filing_burst"] = monthly["n_filings"] / (monthly["trailing_mean_filings"] + 0.5)
    return monthly


def build():
    f = per_filing_flags(load_filings())
    monthly = add_filing_burst(aggregate_to_month(f))

    # only filings dated inside month t may inform month t+1
    monthly["target_month"] = (monthly["filing_month"] + 1).astype(str)
    monthly["filing_month"] = monthly["filing_month"].astype(str)

    cols = ["permno", "target_month", "filing_month",
            "n_filings", "filing_burst", "trailing_mean_filings",
            "max_delay_days", "mean_delay_days", "share_late",
            "has_distress", "has_officer_change", "has_earnings",
            "n_distress", "n_officer", "n_earnings", "n_agreement", "total_words"]
    monthly = monthly[cols].sort_values(["target_month", "permno"]).reset_index(drop=True)

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(OUT, index=False, compression="zstd")

    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    ev = monthly[(monthly["target_month"] >= lo) & (monthly["target_month"] <= hi)]
    print("wrote %s (%s rows, %s stocks)"
          % (OUT.name, format(len(monthly), ","), format(monthly["permno"].nunique(), ",")))
    print("  target months          : %s .. %s"
          % (monthly["target_month"].min(), monthly["target_month"].max()))
    print("  rows in evaluation win : %s" % format(len(ev), ","))
    print("  with a distress flag   : %s" % format(int(ev["has_distress"].sum()), ","))
    print("  with an officer change : %s" % format(int(ev["has_officer_change"].sum()), ","))
    print("  late beyond %d days     : %s (%.1f%%)"
          % (DEADLINE_DAYS, format(int((ev["share_late"] > 0).sum()), ","),
             100 * (ev["share_late"] > 0).mean()))
    print("  burst score available  : %.1f%% of rows" % (100 * ev["filing_burst"].notna().mean()))
    return monthly


# --------------------------------------------------------------------------
# sanity check -- TRAINING MONTHS ONLY
# --------------------------------------------------------------------------
def _contrast(label, flag, pool):
    """Mean return with the flag against the rest of the SAME pool."""
    flag = flag.reindex(pool.index, fill_value=False).fillna(False).astype(bool)
    a, b = pool.loc[flag, C.TARGET], pool.loc[~flag, C.TARGET]
    if len(a) < 30:
        print("  %-28s n=%-8s (too few to read)" % (label, format(len(a), ",")))
        return
    diff = a.mean() - b.mean()
    se = np.sqrt(a.var() / len(a) + b.var() / len(b))
    print("  %-28s n=%-8s %+.3f%%  vs rest %+.3f%%  diff %+.3f%%  t=%+.1f"
          % (label, format(len(a), ","), 100 * a.mean(), 100 * b.mean(),
             100 * diff, diff / se if se else float("nan")))


def explore(monthly):
    """Does any of this associate with next-month returns?

    Restricted to target months in the training window. Looking at the
    evaluation period here would be choosing signals with the answer in hand,
    which is the exact thing the rules audit for.

    The control group matters more than it looks. A filing-conditional signal
    must be compared against OTHER FILERS, not against every stock-month:
    "this company filed anything at all" is itself worth about +0.24%/month in
    the training window, and it is largely a size effect (filers average
    2.6x the market cap of non-filers). Comparing against all stock-months
    hands every filing-conditional signal that same +0.24% for free, which is
    how a dead signal reads as a live one.
    """
    train_end = next(C.training_schedule())[0]          # "2018-12"
    print("\n--- association with next-month excess return, TRAINING ONLY "
          "(target months <= %s) ---" % train_end)

    panel = pd.read_parquet(C.MODEL_TABLE,
                            columns=["permno", "target_month", C.TARGET, "size_grp"])
    panel = panel[(panel["target_month"] <= train_end) & panel[C.TARGET].notna()]
    df = panel.merge(monthly, on=["permno", "target_month"], how="left")

    print("\nCoverage effect (confounded with size -- read with care):")
    _contrast("filed anything that month", df["n_filings"].notna(), df)
    print("  same split within each size bucket:")
    for grp, sub in df.groupby("size_grp"):
        a = sub.loc[sub["n_filings"].notna(), C.TARGET]
        b = sub.loc[sub["n_filings"].isna(), C.TARGET]
        if len(a) < 50 or len(b) < 50:
            continue
        diff = a.mean() - b.mean()
        se = np.sqrt(a.var() / len(a) + b.var() / len(b))
        print("    %-10s filed %-7s not %-7s diff %+.3f%%  t=%+.1f"
              % (grp, format(len(a), ","), format(len(b), ","),
                 100 * diff, diff / se if se else float("nan")))

    filers = df[df["n_filings"].notna()]
    print("\nWithin filers only (n=%s) -- the honest comparison:"
          % format(len(filers), ","))
    tests = [
        ("distress flag (4.01/4.02)", filers["has_distress"] == 1),
        ("officer change (5.02)", filers["has_officer_change"] == 1),
        ("any filing late > %dd" % DEADLINE_DAYS, filers["share_late"] > 0),
        ("filing burst > 2x", filers["filing_burst"] > 2),
    ]
    for label, flag in tests:
        _contrast(label, flag, filers)

    print("\n%d comparisons were made here; log them. With that many looks, a "
          "single t near 2 is not on its own evidence of anything -- what makes "
          "the distress flag worth keeping is the size of the effect and a "
          "prior reason to expect it, not the t-statistic." % (len(tests) + 1))
    print("These are in-sample associations on the training window, not "
          "evidence that a trade works.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--explore", action="store_true",
                    help="also print training-window associations with returns")
    args = ap.parse_args()
    table = build()
    if args.explore:
        if not C.MODEL_TABLE.exists():
            raise SystemExit("--explore needs %s; run 01_data/01_load_data.py first"
                             % C.MODEL_TABLE)
        explore(table)

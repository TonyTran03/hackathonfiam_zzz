"""Stage 2 -- preprocess the 147 predictors.

Two steps, both deliberately simple for the baseline:

  fill    missing values take that month's cross-sectional median
  rank    each predictor is ranked within the month and mapped to [-1, 1]

Both are computed *within a single month across stocks*, so neither can see
any other month -- there is no window to leak through. That is why this stage
can run once for the whole panel instead of once per training fold. The
train-only fitting that does matter (standardising to the training mean and
variance) happens in stage 3, where the folds are.

Ranking rather than winsorising is what the supplied teaching template does,
and it is the right default here: the characteristics have wildly different
units and heavy tails, and a rank is immune to both.

Rows whose answer is missing are KEPT. They are part of the month's universe
and must still receive a prediction; dropping them would let the outcome
decide which stocks were investable.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

OUT = C.PROCESSED_DIR / "features_ranked.parquet"
OUT_SPARSE = C.PROCESSED_DIR / "features_ranked_sparse.parquet"
KEYS = ["permno", "target_month", "eom", "me", "size_grp", "gics", "ticker", "company_name"]

# Measured and rejected. Validation rank correlation was +0.1087 without the
# 8-K columns and +0.1082 with them -- no gain, a hair worse. Feature
# importance says the same thing from another angle: of 156 inputs the three
# event flags rank 152nd, 155th and 156th, and all nine columns together take
# 1.75% of the model's attention against the 5.77% an average feature would.
# Flip this to True to reproduce the comparison; the traded model runs without
# them, because the rule was that validation decides and validation said no.
INCLUDE_FILING_FEATURES = False

FILING_FEATURES = C.PROCESSED_DIR / "filing_features.parquet"
# Added only to the SPARSE table, the one the trees read. About half the
# evaluation-window stock-months have no filing at all, and "no filing" is not
# "an average amount of filing" -- the linear models would need a number
# invented for it, while a tree simply learns which way to send a blank.
# The traded forecast is the tree, so this is where the comparison belongs.
FILING_CONTINUOUS = ["n_filings", "filing_burst", "max_delay_days",
                     "mean_delay_days", "share_late", "total_words"]
FILING_FLAGS = ["has_distress", "has_officer_change", "has_earnings"]


def rank_to_unit(s):
    """Cross-sectional rank -> [-1, 1]. Ties share a rank; all-missing -> 0."""
    filled = s.fillna(s.median())
    r = filled.rank(method="dense") - 1
    top = r.max()
    if not np.isfinite(top) or top <= 0:
        return pd.Series(0.0, index=s.index)
    return (r / top) * 2 - 1


def rank_keep_missing(s):
    """Same ranking, but a missing value STAYS missing.

    Filling with the month's median tells the model "this firm is average on
    this measure". Often the truth is "this measure does not apply to this
    firm" -- no R&D line, no five-year history, a ratio with a negative
    denominator. Missingness is not random either: stocks missing the most
    characteristics have a median market cap of $282m against $1,687m for
    those missing the fewest.

    Gradient-boosted trees learn which way to send a missing value at each
    split, so they need no invented number. The linear models cannot accept
    one, which is why both versions of this table exist.
    """
    r = s.rank(method="dense") - 1          # rank() already skips NaN
    top = r.max()
    if not np.isfinite(top) or top <= 0:
        return pd.Series(np.nan, index=s.index)
    return (r / top) * 2 - 1


def attach_filing_features(df):
    """Join the 8-K signals on, LEFT, leaving non-filers blank.

    Two states that must stay distinguishable: "this company filed nothing
    this month" and "it filed, and nothing was flagged". Filling the first
    with zero collapses them and quietly tells the model the company was
    checked and found clean. A tree can hold the difference -- blank goes one
    way at a split, zero the other -- so the gap is left as a gap.

    Dropping the non-filers instead would be worse still: it would let filing
    coverage decide the universe, and coverage is roughly half.
    """
    if not INCLUDE_FILING_FEATURES:
        print("  filing features measured and excluded "
              "(validation +0.1087 without vs +0.1082 with); "
              "set INCLUDE_FILING_FEATURES=True to reproduce")
        return df
    if not FILING_FEATURES.exists():
        print("  no filing features found; skipping (run 01_data/filing_features.py)")
        return df
    f = pd.read_parquet(FILING_FEATURES)
    keep = ["permno", "target_month"] + FILING_CONTINUOUS + FILING_FLAGS
    f = f[[c for c in keep if c in f.columns]]

    # rank the continuous ones within the month, among filers only; the flags
    # are already 0/1 and mean the same thing in every month
    out = []
    for month, grp in f.groupby("target_month", sort=True):
        g = grp.copy()
        g[FILING_CONTINUOUS] = g[FILING_CONTINUOUS].apply(rank_keep_missing)
        out.append(g)
    f = pd.concat(out, ignore_index=True)

    before = df.shape[1]
    df = df.merge(f, on=["permno", "target_month"], how="left")
    matched = df["n_filings"].notna().mean()
    print("  filing features: +%d columns, matched on %.1f%% of stock-months"
          % (df.shape[1] - before, 100 * matched))
    return df


def build():
    if not C.MODEL_TABLE.exists():
        raise SystemExit("missing %s -- run 01_data/01_load_data.py first" % C.MODEL_TABLE)

    features = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    df = pd.read_parquet(C.MODEL_TABLE, columns=KEYS + features + [C.TARGET])
    print("read %s rows" % format(len(df), ","))

    missing_before = df[features].isna().mean().mean()
    filled, sparse = [], []
    for month, grp in df.groupby("target_month", sort=True):
        a = grp.copy()
        a[features] = a[features].apply(rank_to_unit)
        filled.append(a)
        b = grp.copy()
        b[features] = b[features].apply(rank_keep_missing)
        sparse.append(b)
    df = pd.concat(filled, ignore_index=True)
    df_sparse = pd.concat(sparse, ignore_index=True)

    assert not df[features].isna().any().any(), "ranking left missing values behind"
    lo, hi = df[features].min().min(), df[features].max().max()
    assert lo >= -1.0001 and hi <= 1.0001, "ranked values escaped [-1, 1]"

    df_sparse = attach_filing_features(df_sparse)

    df.to_parquet(OUT, index=False, compression="zstd")
    df_sparse.to_parquet(OUT_SPARSE, index=False, compression="zstd")
    print("wrote %s (%.0f MB)  -- median-filled, for the linear models"
          % (OUT.name, OUT.stat().st_size / 1e6))
    print("wrote %s (%.0f MB)  -- missing preserved, for the trees"
          % (OUT_SPARSE.name, OUT_SPARSE.stat().st_size / 1e6))
    print("  predictors        : %d, ranked into [-1, 1]" % len(features))
    print("  missing cells     : %.1f%% -- filled in one file, kept in the other"
          % (100 * missing_before))
    print("  months            : %s .. %s" % (df["target_month"].min(), df["target_month"].max()))
    print("  rows kept with no answer: %s (they still get a prediction)"
          % format(int(df[C.TARGET].isna().sum()), ","))
    return df


if __name__ == "__main__":
    build()

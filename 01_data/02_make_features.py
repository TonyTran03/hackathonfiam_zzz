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
KEYS = ["permno", "target_month", "eom", "me", "size_grp", "gics", "ticker", "company_name"]


def rank_to_unit(s):
    """Cross-sectional rank -> [-1, 1]. Ties share a rank; all-missing -> 0."""
    filled = s.fillna(s.median())
    r = filled.rank(method="dense") - 1
    top = r.max()
    if not np.isfinite(top) or top <= 0:
        return pd.Series(0.0, index=s.index)
    return (r / top) * 2 - 1


def build():
    if not C.MODEL_TABLE.exists():
        raise SystemExit("missing %s -- run 01_data/01_load_data.py first" % C.MODEL_TABLE)

    features = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    df = pd.read_parquet(C.MODEL_TABLE, columns=KEYS + features + [C.TARGET])
    print("read %s rows" % format(len(df), ","))

    missing_before = df[features].isna().mean().mean()
    out = []
    for month, grp in df.groupby("target_month", sort=True):
        g = grp.copy()
        g[features] = g[features].apply(rank_to_unit)
        out.append(g)
    df = pd.concat(out, ignore_index=True)

    assert not df[features].isna().any().any(), "ranking left missing values behind"
    lo, hi = df[features].min().min(), df[features].max().max()
    assert lo >= -1.0001 and hi <= 1.0001, "ranked values escaped [-1, 1]"

    df.to_parquet(OUT, index=False, compression="zstd")
    print("wrote %s (%.0f MB)" % (OUT.name, OUT.stat().st_size / 1e6))
    print("  predictors        : %d, all ranked into [-1, 1]" % len(features))
    print("  missing filled    : %.1f%% of predictor cells were blank" % (100 * missing_before))
    print("  months            : %s .. %s" % (df["target_month"].min(), df["target_month"].max()))
    print("  rows kept with no answer: %s (they still get a prediction)"
          % format(int(df[C.TARGET].isna().sum()), ","))
    return df


if __name__ == "__main__":
    build()

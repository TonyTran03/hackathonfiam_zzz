"""Only the paths and prediction helpers used by the active notebooks/model."""
import os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data'
EXTERNAL_DIR = RAW_DIR / 'external'
FACTOR_LIST_CSV = RAW_DIR / 'factor_char_list.csv'
_source_dir = Path(os.environ.get('FIAM_DATA_DIR', str(RAW_DIR)))
CHARS_PARQUET = _source_dir / 'chars_final_with_names.parquet'
SP500_CSV = EXTERNAL_DIR / 'SP500_fred.csv'
TB3MS_CSV = EXTERNAL_DIR / 'TB3MS.csv'
TARGET = 'ret_exc_lead1m'
COMPETITION = {'oos_end': '2026-08', 'benchmark_premium_annual': 0.04}
# Optional production-forecast comparison in the notebook; no pipeline build needed.
PROCESSED_DIR = ROOT / 'prediction' / 'saved_predictions'

GBM_GRID = [
    dict(num_leaves=15, min_child_samples=500, learning_rate=0.02),
    dict(num_leaves=31, min_child_samples=200, learning_rate=0.02),
    dict(num_leaves=63, min_child_samples=100, learning_rate=0.01),
]

GBM_FIXED = dict(objective="l2", n_estimators=3000, subsample=0.7,
                 subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
                 verbose=-1, n_jobs=-1)

GBM_EARLY_STOP = 50

def demean_and_clip(y, months, clip=3.0):
    """Remove each month's cross-sectional mean, then trim the tails.

    Fitting raw monthly returns does not work. Almost all of their variance is
    the month itself -- everything rises and falls together -- and no stock
    characteristic predicts that. Worse, boosting starts from the TRAINING mean
    return, so when the validation years have a different average the level is
    wrong from the first tree and validation error rises immediately. The first
    attempt here stopped after one round for exactly that reason.

    Subtracting the month's own mean leaves only the cross-sectional part,
    which is the only part a long/short book trades. It is computed within a
    single month across stocks, so it looks at no other period.

    Clipping matters too: holdings in this panel run past +1200% in a month,
    and squared error would let a handful of them write the model.
    """
    s = pd.Series(y).groupby(months.values).transform(lambda v: v - v.mean())
    sd = s.std(ddof=0)
    return s.clip(-clip * sd, clip * sd).values

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

def training_schedule(first_test_year=2021, last_test_year=2026):
    """Expanding training window, rolling two-year validation, one-year test.

    Yields (train_end, val_start, val_end, test_start, test_end) as YYYY-MM,
    keyed by the TARGET month. Matches the rules PDF worked example: the 2021
    model trains through 2018-12, validates 2019-01..2020-12, tests 2021.
    """
    for test_year in range(first_test_year, last_test_year + 1):
        train_end = f"{test_year - 3}-12"
        val_start = f"{test_year - 2}-01"
        val_end = f"{test_year - 1}-12"
        test_start = f"{test_year}-01"
        # the panel stops in 2026-08, so the final test year is a short one
        test_end = min(f"{test_year}-12", COMPETITION["oos_end"])
        yield train_end, val_start, val_end, test_start, test_end

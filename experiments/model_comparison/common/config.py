"""Shared paths and competition constants.

Every number in COMPETITION comes from the rules PDF; nothing here is a
modelling choice. Keep it that way, so the compliance checks stay auditable.

Imported by every stage script:

    from common import config as C
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "01_data" / "raw"
EXTERNAL_DIR = RAW_DIR / "external"
PROCESSED_DIR = ROOT / "01_data" / "processed"

FACTOR_LIST_CSV = RAW_DIR / "factor_char_list.csv"


def _find_dataset(filename):
    """Datasets are gitignored, so look in the documented location, then the
    repo root, then wherever FIAM_DATA_DIR points -- whichever the teammate
    actually used."""
    candidates = [RAW_DIR / filename, ROOT / filename]
    env_dir = os.environ.get("FIAM_DATA_DIR")
    if env_dir:
        candidates.insert(0, Path(env_dir) / filename)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return RAW_DIR / filename          # documented location, for the error message


CHARS_PARQUET = _find_dataset("chars_final_with_names.parquet")
FILINGS_PARQUET = _find_dataset("8k_20150101_20260831_identified.parquet")

# --- generated ------------------------------------------------------------
MODEL_TABLE = PROCESSED_DIR / "model_table.parquet"
BENCHMARK_CSV = PROCESSED_DIR / "benchmark_monthly.csv"

TB3MS_CSV = EXTERNAL_DIR / "TB3MS.csv"
SP500_CSV = EXTERNAL_DIR / "SP500_fred.csv"
FF3_ZIP = EXTERNAL_DIR / "ff3.zip"

# --- the answer column, and columns that must never be predictors ---------
TARGET = "ret_exc_lead1m"
# ret / ret_exc describe month t, so they are NOT look-ahead -- but the rules
# say to take baseline predictors from factor_char_list.csv, and ret_1_0
# already carries the same information. Treated as "warn", not "fail".
CONTEMPORANEOUS_RETURNS = ["ret", "ret_exc", "ret_exc_wins", "ret_local"]

# identifiers and evaluation helpers carried alongside the 147 predictors
AUX_COLUMNS = [
    "permno", "permco", "gvkey", "iid",
    "date", "eom",
    "me", "me_lag1", "shares", "dolvol", "tvol", "prc_local",
    "gics", "sic", "naics", "ff49", "size_grp", "exch_main", "primary_sec", "common",
    "ticker", "company_name", "ticker_name_status",
]

COMPETITION = {
    # rules PDF, "Trading Criteria"
    "min_positions": 100,
    "max_positions": 500,
    "max_gross": 2.00,          # 200% of capital
    "net_band": (-0.50, 0.50),  # -50% .. +50% of capital
    # rules PDF, "Universe and Sample Period" / "Training Procedures"
    "oos_start": "2021-01",
    "oos_end": "2026-08",
    "first_target_month": "2015-02",
    "benchmark_premium_annual": 0.04,
}


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

"""Run every rule-compliance check against the generated work table.

    python run_checks.py                 # look-ahead checks only
    python run_checks.py holdings.csv    # also check a book

The holdings file needs columns permno / weight and either target_month
(YYYY-MM) or a date column naming the holding month.

Exit status is non-zero if anything FAILS, so this can gate a commit.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import checks
from common import config as C


BUILT_HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"


def load_holdings(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "target_month" not in df.columns:
        date_col = next((c for c in ["date", "trade_date", "month", "eom"]
                         if c in df.columns), None)
        if date_col is None:
            raise SystemExit("holdings file needs target_month or a date column")
        df["target_month"] = pd.to_datetime(df[date_col]).dt.to_period("M").astype(str)
    return df[["target_month", "permno", "weight"]]


def attach_betas(h):
    """Add the beta each position was sized on, so neutrality can be checked.

    Preference order matters. `beta_use` from stage 4 is the number the book
    was actually built with, so checking against it answers "did the
    construction do what it intended". Falling back to the panel's raw
    `beta_60m` answers a slightly different and weaker question, so the source
    is printed either way.
    """
    if BUILT_HOLDINGS.exists():
        built = pd.read_parquet(BUILT_HOLDINGS,
                                columns=["permno", "target_month", "beta_use"])
        merged = h.merge(built.rename(columns={"beta_use": "beta"}),
                         on=["permno", "target_month"], how="left")
        if merged["beta"].notna().any():
            print("  betas from holdings.parquet (beta_use, as the book was sized)")
            return merged

    try:
        panel = pd.read_parquet(C.MODEL_TABLE,
                                columns=["permno", "target_month", "beta_60m"])
    except (OSError, ValueError, KeyError):
        print("  no beta source found; beta neutrality will not be checked")
        return h

    merged = h.merge(panel.rename(columns={"beta_60m": "beta"}),
                     on=["permno", "target_month"], how="left")
    print("  betas from the panel (beta_60m) -- stage 4's beta_use was unavailable")
    return merged


def main(holdings_path=None):
    if not C.MODEL_TABLE.exists():
        raise SystemExit("missing %s -- run `python 01_data/01_load_data.py` first"
                         % C.MODEL_TABLE)

    df = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "target_month", C.TARGET])
    features = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    total_fail = total_warn = 0

    f, w = checks.report(checks.check_features(features), "predictors")
    total_fail += f
    total_warn += w

    tm = df["target_month"]
    for train_end, val_start, val_end, test_start, test_end in C.training_schedule():
        train = tm <= train_end
        val = (tm >= val_start) & (tm <= val_end)
        test = (tm >= test_start) & (tm <= test_end)
        label = "test %s" % test_start[:4]
        findings = checks.check_split(df, train, val, test, label)
        findings += checks.check_fit_rows(train, df, train_end, label)
        f, w = checks.report(findings, label)
        total_fail += f
        total_warn += w

    if holdings_path:
        h = attach_betas(load_holdings(holdings_path))
        panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "target_month"])
        findings, stats = checks.check_holdings(h, panel=panel)
        f, w = checks.report(findings, "trading criteria")
        total_fail += f
        total_warn += w
        out = C.PROCESSED_DIR / "exposure_by_month.csv"
        stats.to_csv(out)
        print("  per-month exposures written to %s" % out)

    print("\n%d failures, %d warnings" % (total_fail, total_warn))
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))

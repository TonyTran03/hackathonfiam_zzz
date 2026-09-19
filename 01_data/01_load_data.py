"""Stage 1 -- load the supplied panel and the benchmark series.

Produces two files in 01_data/processed/ :

  model_table.parquet     147 predictors + identifiers + the answer, with an
                          explicit `target_month` key
  benchmark_monthly.csv   the cash-plus-4% hurdle, and two market series

The one alignment rule that matters: a row labelled `eom` = month t carries
predictors for month t, and `ret_exc_lead1m` is ALREADY the month t+1 answer.
`target_month` = t+1. Assign train/validation/test by `target_month`, never
by `eom`.
"""
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12


def load_feature_names():
    names = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    assert len(names) == 147, "expected 147 predictors, got %d" % len(names)
    assert len(set(names)) == 147, "duplicate name in factor_char_list.csv"
    return names


# --------------------------------------------------------------------------
# the stock-month panel
# --------------------------------------------------------------------------
def build_model_table():
    if not C.CHARS_PARQUET.exists():
        raise SystemExit(
            "missing dataset: %s\nPut the supplied Parquet files in 01_data/raw/ "
            "(see README)." % C.CHARS_PARQUET)

    features = load_feature_names()
    keep = list(dict.fromkeys(
        C.AUX_COLUMNS + features + [C.TARGET] + C.CONTEMPORANEOUS_RETURNS))

    available = set(pq.ParquetFile(C.CHARS_PARQUET).schema_arrow.names)
    missing = [c for c in keep if c not in available]
    assert not missing, "columns absent from the panel: %s" % missing

    df = pq.read_table(C.CHARS_PARQUET, columns=keep).to_pandas()
    print("read %s rows x %d cols" % (format(len(df), ","), df.shape[1]))

    df["eom"] = pd.to_datetime(df["eom"])
    df["date"] = pd.to_datetime(df["date"])

    target_period = df["eom"].dt.to_period("M") + 1
    df["target_eom"] = target_period.dt.to_timestamp("M")
    df["target_month"] = target_period.astype(str)
    # the trade date the legacy templates expect: first day of the holding month
    df["trade_date"] = target_period.dt.to_timestamp()
    df["year"] = target_period.dt.year
    df["month"] = target_period.dt.month

    df = df.sort_values(["target_eom", "permno"]).reset_index(drop=True)

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(C.MODEL_TABLE, index=False, compression="zstd")

    labelled = df[C.TARGET].notna()
    print("wrote %s (%.0f MB)" % (C.MODEL_TABLE.name, C.MODEL_TABLE.stat().st_size / 1e6))
    print("  feature months  : %s .. %s" % (df["eom"].min().strftime("%Y-%m"),
                                            df["eom"].max().strftime("%Y-%m")))
    print("  target months   : %s .. %s" % (df["target_month"].min(), df["target_month"].max()))
    print("  rows with answer: %s  /  without: %s"
          % (format(int(labelled.sum()), ","), format(int((~labelled).sum()), ",")))

    per_month = df[labelled].groupby("target_month").size()
    oos = per_month.loc[C.COMPETITION["oos_start"]:C.COMPETITION["oos_end"]]
    print("  evaluation window: %d months, %s-%s stocks per month"
          % (len(oos), format(int(oos.min()), ","), format(int(oos.max()), ",")))
    return df


# --------------------------------------------------------------------------
# benchmark and market series
# --------------------------------------------------------------------------
def load_tb3ms():
    """FRED reports TB3MS as an ANNUALIZED PERCENT -- both divisions are needed."""
    s = pd.read_csv(C.TB3MS_CSV, parse_dates=["observation_date"])
    s["target_month"] = s["observation_date"].dt.to_period("M").astype(str)
    s = s.rename(columns={"TB3MS": "tb3ms_annual_pct"})
    s["cash_monthly"] = s["tb3ms_annual_pct"] / 100 / 12
    s["hurdle_monthly"] = s["cash_monthly"] + PREMIUM_M
    return s[["target_month", "tb3ms_annual_pct", "cash_monthly", "hurdle_monthly"]]


def load_sp500():
    """Daily index levels -> monthly price return (no dividends)."""
    s = pd.read_csv(C.SP500_CSV, parse_dates=["observation_date"])
    s["SP500"] = pd.to_numeric(s["SP500"], errors="coerce")
    monthly = (s.dropna(subset=["SP500"]).set_index("observation_date")["SP500"]
                .resample("ME").last().dropna())
    out = pd.DataFrame({"target_month": monthly.index.to_period("M").astype(str),
                        "sp500_level": monthly.values})
    out["sp500_ret"] = out["sp500_level"].pct_change()
    return out.dropna(subset=["sp500_ret"])


def load_factor_file():
    """Market return in excess of cash, dividends included. One month shorter."""
    with zipfile.ZipFile(C.FF3_ZIP) as z:
        raw = z.read(z.namelist()[0]).decode("latin-1")
    rows = [l for l in raw.splitlines() if len(l) > 7 and l[:6].isdigit() and l[6] == ","]
    df = pd.read_csv(io.StringIO("\n".join(rows)), header=None,
                     names=["ym", "mkt_rf", "smb", "hml", "rf"])
    df = df[df["ym"].astype(str).str.len() == 6]
    df["target_month"] = pd.PeriodIndex(df["ym"].astype(str), freq="M").astype(str)
    for c in ["mkt_rf", "rf"]:
        df[c] = pd.to_numeric(df[c], errors="coerce") / 100      # percent -> decimal
    return df[["target_month", "mkt_rf", "rf"]].rename(columns={"rf": "ff_rf"})


def build_benchmark():
    bm = (load_tb3ms()
          .merge(load_sp500(), on="target_month", how="outer")
          .merge(load_factor_file(), on="target_month", how="outer")
          .sort_values("target_month").reset_index(drop=True))

    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    bm = bm[(bm["target_month"] >= "2015-01") & (bm["target_month"] <= hi)]

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    bm.to_csv(C.BENCHMARK_CSV, index=False)

    oos = bm[(bm["target_month"] >= lo) & (bm["target_month"] <= hi)]
    print("wrote %s (%d months, %d in the evaluation window)"
          % (C.BENCHMARK_CSV.name, len(bm), len(oos)))
    print("  hurdle over %s..%s: %.2f%% a year on average (%.2f%% low, %.2f%% high)"
          % (lo, hi, oos["hurdle_monthly"].mean() * 1200,
             oos["hurdle_monthly"].min() * 1200, oos["hurdle_monthly"].max() * 1200))
    for col in ["hurdle_monthly", "sp500_ret", "mkt_rf"]:
        gaps = oos.loc[oos[col].isna(), "target_month"].tolist()
        print("  %-16s missing in evaluation window: %s" % (col, gaps if gaps else "none"))
    return bm


def main():
    build_model_table()
    print()
    build_benchmark()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

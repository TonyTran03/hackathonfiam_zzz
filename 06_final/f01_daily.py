"""Final stage 1 -- daily tables: returns, trading calendar, cash, hurdle, market.

    python 06_final/f01_daily.py

Writes into 06_final/data/ (gitignored):
  dsf.parquet        permno, date, prc, daily_return     (from the supplied CSV)
  calendar.parquet   one row per trading day: month, formation flags, daily
                     cash rate, daily hurdle, S&P 500 price return
  last_day.parquet   last date each permno has a daily return (delisting map)

Conventions, stated once here and asserted below:
  * cash per day   rf_d = TB3MS_m / 25200          (Section 9.2)
  * hurdle per day b_d  = TB3MS_m / 25200 + 0.04 / 252
    TB3MS_m is the bill rate of the calendar month the day falls in. FRED's
    monthly TB3MS is the month's average, published at the start of the next
    month; it is used only to SCORE the strategy, never to form it, so the
    instructions' own formula is applied as written.
  * the trading calendar is the set of dates on which at least 1,000 stocks
    report a return, which drops the handful of partial-day rows in the file
  * formation day of month m = first trading day of m. Monthly
    characteristics are dated at end of month m-1, so under the Section 7
    convention the book built on them is formed at the close of that first
    trading day and first earns on the second.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
from common import config as C  # noqa: E402


def load_dsf():
    if F.DSF_PARQUET.exists():
        return pd.read_parquet(F.DSF_PARQUET)
    src = next((p for p in F.DSF_CSV_CANDIDATES if p.exists()), None)
    if src is None:
        raise SystemExit("missing dsf_mini_from_2014.csv -- put it in 01_data/raw/")
    d = pd.read_csv(src, dtype={"permno": "int32", "date": "int32",
                                "prc": "float64", "daily_return": "float64"})
    d["date"] = pd.to_datetime(d["date"].astype(str), format="%Y%m%d")
    F.DATA.mkdir(parents=True, exist_ok=True)
    d.to_parquet(F.DSF_PARQUET, index=False, compression="zstd")
    return d


def build():
    d = load_dsf()
    assert not d.duplicated(["permno", "date"]).any(), "duplicate permno-date rows"

    # data hygiene: report, do not silently drop
    bad = d["daily_return"].abs() > 1.0
    print("daily rows %s; |return| > 100%% on %d rows (kept; held names are flagged by the engine)"
          % (format(len(d), ","), int(bad.sum())))

    counts = d.groupby("date").size()
    cal = pd.DataFrame({"date": counts.index[counts >= 1000]})
    cal["month"] = cal["date"].dt.to_period("M")
    cal["is_formation"] = ~cal["month"].duplicated()
    # week formation: first trading day of each ISO week
    wk = cal["date"].dt.isocalendar()
    cal["week"] = wk["year"].astype(str) + "-" + wk["week"].astype(str).str.zfill(2)
    cal["is_week_start"] = ~cal["week"].duplicated()

    tb = pd.read_csv(C.TB3MS_CSV)
    tb.columns = ["date", "tb3ms"]
    tb["month"] = pd.to_datetime(tb["date"]).dt.to_period("M")
    cal = cal.merge(tb[["month", "tb3ms"]], on="month", how="left")
    assert cal.loc[cal["date"] <= F.FINAL["oos_end"], "tb3ms"].notna().all(), \
        "TB3MS missing inside the window"
    cal["rf_d"] = cal["tb3ms"] / 25200.0
    cal["hurdle_d"] = cal["rf_d"] + F.FINAL["premium_annual"] / 252.0

    sp = pd.read_csv(C.SP500_CSV)
    sp.columns = ["date", "sp500"]
    sp["date"] = pd.to_datetime(sp["date"])
    sp["sp500"] = pd.to_numeric(sp["sp500"], errors="coerce")
    sp = sp.dropna()
    cal = cal.merge(sp, on="date", how="left")
    # a missing index level on a trading day carries the last level, so the
    # return is booked on the next day it prints rather than lost
    cal["sp500"] = cal["sp500"].ffill()
    cal["sp_ret"] = cal["sp500"].pct_change()
    cal["mkt_ex"] = cal["sp_ret"] - cal["rf_d"]

    w = cal[(cal["date"] >= "2019-01-01") & (cal["date"] <= F.FINAL["oos_end"])]
    assert w["sp_ret"].notna().all(), "S&P 500 daily return missing in window"
    print("calendar %s .. %s, %d trading days; window 2019-2026: %d days"
          % (cal["date"].min().date(), cal["date"].max().date(), len(cal), len(w)))

    last = d.dropna(subset=["daily_return"]).groupby("permno")["date"].max().rename("last_day")
    last.to_frame().to_parquet(F.DATA / "last_day.parquet")
    cal.to_parquet(F.DATA / "calendar.parquet", index=False)
    print("wrote calendar.parquet, last_day.parquet")
    return cal


if __name__ == "__main__":
    build()

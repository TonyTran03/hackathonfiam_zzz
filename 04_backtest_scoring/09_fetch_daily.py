"""Stage 5e (optional) -- download daily prices for the stocks we actually hold.

The rules devote a section to this: selection stays monthly, but once the
month's weights are set you can mark the book every trading day, and the
monthly series hides a great deal. A month that falls 6% mid-month and
finishes flat shows no volatility and no drawdown monthly; daily it is a 6%
drawdown, and margin is computed on the daily path, not the monthly one.
The rules call the daily view "a differentiator, not a requirement".

WHAT THIS CANNOT DO, and it must be said in the deck. Free daily history is
keyed on TICKER, and a company that was acquired, taken private or renamed
during the period no longer answers to its old symbol. On a 24-name sample
20 resolved and 4 did not -- Splunk, Cloudera and Proofpoint (all acquired)
and Overstock (renamed). So the daily path is computed on the surviving
subset, which biases it optimistic: the names that vanish are exactly the
ones whose paths were worst. The monthly backtest has no such gap, because
the supplied panel carries delisted stocks properly.

Results are cached per ticker, so an interrupted run resumes instead of
starting over. Requests are spaced out deliberately; this is someone else's
free service.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

CACHE = C.PROCESSED_DIR / "daily_cache"
OUT = C.PROCESSED_DIR / "daily_prices.parquet"
HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
       "?interval=1d&period1=%d&period2=%d")
START, END = 1604188800, 1790000000        # Nov 2020 .. late 2026
PAUSE = 0.4


def fetch(ticker):
    req = urllib.request.Request(URL % (ticker, START, END), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def parse(payload):
    res = payload.get("chart", {}).get("result")
    if not res or not res[0].get("timestamp"):
        return None
    r = res[0]
    closes = r["indicators"]["adjclose"][0]["adjclose"] \
        if r["indicators"].get("adjclose") else r["indicators"]["quote"][0]["close"]
    df = pd.DataFrame({"ts": r["timestamp"], "adj_close": closes}).dropna()
    df["date"] = pd.to_datetime(df["ts"], unit="s").dt.tz_localize(None).dt.normalize()
    return df[["date", "adj_close"]]


def main():
    if not HOLDINGS.exists():
        raise SystemExit("missing %s -- run stage 4 first" % HOLDINGS)
    CACHE.mkdir(parents=True, exist_ok=True)

    h = pd.read_parquet(HOLDINGS)
    wanted = (h[["permno", "ticker"]].dropna().drop_duplicates()
                .sort_values(["permno", "ticker"]))
    print("%d stocks held over the period, %d distinct tickers"
          % (wanted["permno"].nunique(), wanted["ticker"].nunique()))

    frames, missing, fetched = [], [], 0
    tickers = sorted(wanted["ticker"].unique())
    for i, t in enumerate(tickers, 1):
        safe = "".join(ch for ch in t if ch.isalnum() or ch in "-._")
        path = CACHE / ("%s.parquet" % safe)
        miss = CACHE / ("%s.missing" % safe)
        if path.exists():
            frames.append(pd.read_parquet(path).assign(ticker=t))
            continue
        if miss.exists():
            missing.append(t)
            continue
        try:
            df = parse(fetch(t))
            fetched += 1
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            df = None
        if df is None or df.empty:
            miss.write_text("no data", encoding="utf-8")
            missing.append(t)
        else:
            df.to_parquet(path, index=False)
            frames.append(df.assign(ticker=t))
        time.sleep(PAUSE)
        if i % 100 == 0:
            print("  %d/%d  (%d newly fetched, %d unavailable)"
                  % (i, len(tickers), fetched, len(missing)), flush=True)

    if not frames:
        raise SystemExit("nothing downloaded")
    daily = pd.concat(frames, ignore_index=True)
    daily.to_parquet(OUT, index=False, compression="zstd")

    have = set(daily["ticker"])
    covered = wanted[wanted["ticker"].isin(have)]
    print("\nwrote %s" % OUT.name)
    print("  tickers resolved   : %d of %d (%.0f%%)"
          % (len(have), len(tickers), 100 * len(have) / len(tickers)))
    print("  trading days       : %s .. %s"
          % (daily["date"].min().date(), daily["date"].max().date()))
    print("  unavailable        : %d -- %s%s"
          % (len(missing), ", ".join(missing[:10]), "..." if len(missing) > 10 else ""))
    print("\n  These are companies acquired, taken private or renamed during the")
    print("  period. Their absence biases any daily risk figure optimistic and")
    print("  must be stated wherever the daily numbers appear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

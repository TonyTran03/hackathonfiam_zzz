"""Stage 5f (optional) -- mark the book every trading day.

Selection stays monthly. This holds each month's weights fixed and revalues
the book daily, which is what the rules ask for: "a month in which the book is
down 6% by the middle of the month and claws its way back to finish flat"
contributes zero volatility and zero drawdown to a monthly series, while the
daily path shows a 6% drawdown -- and margin is computed on the daily path.

READ THE COVERAGE LINE BEFORE QUOTING ANY NUMBER FROM HERE. Free daily history
is keyed on ticker, so companies acquired, taken private or renamed mid-period
cannot be resolved: 1,092 of 1,372 tickers came back, which is 84.5% of the
book by weight on average and as little as 67% in early 2021. Weights are
renormalised inside the covered subset each month, so what follows is the
daily path of the part of the book that survived under its own name. The names
that vanish are disproportionately the ones whose paths were worst, so every
figure here is biased optimistic. The monthly backtest has no such gap.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

DAILY = C.PROCESSED_DIR / "daily_prices.parquet"
HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
MONTHLY = C.ROOT / "05_submission" / "portfolio_returns.csv"
OUT = C.ROOT / "05_submission" / "daily_returns.csv"


def daily_returns():
    d = pd.read_parquet(DAILY)
    d = d.sort_values(["ticker", "date"])
    d["ret"] = d.groupby("ticker")["adj_close"].pct_change()
    d = d.dropna(subset=["ret"])
    d = d[d["ret"].abs() < 0.9]           # drop split artefacts the feed missed
    d["month"] = d["date"].dt.to_period("M").astype(str)
    return d


def build_path(h, d):
    rows, coverage = [], []
    for month, book in h.groupby("target_month", sort=True):
        held = book[["ticker", "weight"]].dropna(subset=["ticker"])
        days = d[d["month"] == month]
        if days.empty:
            continue
        merged = days.merge(held, on="ticker", how="inner")
        covered = merged["ticker"].drop_duplicates()
        w_cov = held[held["ticker"].isin(set(covered))]["weight"].abs().sum()
        w_all = held["weight"].abs().sum()
        if w_cov == 0:
            continue
        # renormalise inside the covered subset so gross stays at the target
        scale = w_all / w_cov
        merged["contrib"] = merged["weight"] * scale * merged["ret"]
        by_day = merged.groupby("date")["contrib"].sum()
        rows.append(by_day)
        coverage.append({"target_month": month, "weight_covered": w_cov / w_all,
                         "names_covered": len(covered), "names_held": len(held)})
    path = pd.concat(rows).sort_index()
    return path, pd.DataFrame(coverage)


def main():
    if not DAILY.exists():
        raise SystemExit("missing %s -- run 09_fetch_daily.py first" % DAILY)
    h = pd.read_parquet(HOLDINGS)
    d = daily_returns()
    path, cov = build_path(h, d)
    m = pd.read_csv(MONTHLY)

    # the daily series is a spread on gross capital; add the cash leg pro rata
    cash = m.set_index("target_month")["cash_monthly"]
    per_month = path.groupby(path.index.to_period("M").astype(str)).size()
    daily_cash = path.index.to_period("M").astype(str).map(cash) / \
        path.index.to_period("M").astype(str).map(per_month)
    total = path + daily_cash.values

    curve = (1 + total).cumprod()
    dd = curve / curve.cummax() - 1
    ann_vol_daily = total.std(ddof=1) * np.sqrt(252)
    ann_vol_monthly = m["total"].std(ddof=1) * np.sqrt(12)
    mdd_monthly = ((1 + m["total"]).cumprod() /
                   (1 + m["total"]).cumprod().cummax() - 1).min()

    print("=" * 70)
    print("DAILY RISK  %s .. %s  (%d trading days)"
          % (path.index.min().date(), path.index.max().date(), len(path)))
    print("=" * 70)
    print("\nCOVERAGE -- quote this next to every number below")
    print("  weight covered   : %.1f%% on average, %.1f%% at worst (%s)"
          % (100 * cov["weight_covered"].mean(), 100 * cov["weight_covered"].min(),
             cov.loc[cov["weight_covered"].idxmin(), "target_month"]))
    print("  names covered    : %.0f of %.0f per month on average"
          % (cov["names_covered"].mean(), cov["names_held"].mean()))

    print("\nWHAT THE MONTHLY SERIES HIDES")
    print("  %-34s %12s %12s" % ("", "from monthly", "from daily"))
    print("  %-34s %11.1f%% %11.1f%%"
          % ("annualised volatility", 100 * ann_vol_monthly, 100 * ann_vol_daily))
    print("  %-34s %11.2f%% %11.2f%%"
          % ("maximum drawdown", 100 * mdd_monthly, 100 * dd.min()))
    print("  %-34s %11s %11.2f%%"
          % ("worst single day", "n/a", 100 * total.min()))
    print("  %-34s %11s %11.2f%%"
          % ("5% worst-day threshold (VaR)", "n/a", 100 * total.quantile(0.05)))
    print("  %-34s %11s %11.2f%%"
          % ("1% worst-day threshold", "n/a", 100 * total.quantile(0.01)))

    print("\nINTRA-MONTH DRAWDOWNS THE MONTHLY SERIES CANNOT SHOW")
    per = []
    for month, grp in total.groupby(total.index.to_period("M").astype(str)):
        c = (1 + grp).cumprod()
        per.append({"month": month, "intramonth_dd": (c / c.cummax() - 1).min(),
                    "month_return": c.iloc[-1] - 1})
    per = pd.DataFrame(per)
    hidden = per[(per["month_return"] > -0.01) & (per["intramonth_dd"] < -0.03)]
    print("  %d months finished flat or up while falling more than 3%% inside the month"
          % len(hidden))
    for _, r in hidden.nlargest(5, "month_return").iterrows():
        print("    %s  finished %+.2f%%  but was down %.2f%% intramonth"
              % (r["month"], 100 * r["month_return"], 100 * r["intramonth_dd"]))

    out = pd.DataFrame({"date": path.index, "spread": path.values,
                        "total": total.values})
    out.to_csv(OUT, index=False)
    cov.to_csv(C.ROOT / "05_submission" / "daily_coverage.csv", index=False)
    print("\nwrote %s and daily_coverage.csv" % OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stage 5g -- every statistic the rules list for pages 4 to 7, in one place.

The rules enumerate the performance pack by name. This prints all of it and
writes deck_pack.csv, so the slides can be filled from one source instead of
from whatever number happened to be on screen. Anything the rules ask for and
we cannot compute is printed as a gap rather than silently skipped.
"""
import sys
import zipfile
import io
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

RETURNS = C.ROOT / "05_submission" / "portfolio_returns.csv"
HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
DAILY = C.ROOT / "05_submission" / "daily_returns.csv"
OUT = C.ROOT / "05_submission" / "deck_pack.csv"

rows = []


def put(section, label, value, note=""):
    rows.append({"section": section, "metric": label, "value": value, "note": note})
    print("  %-42s %s%s" % (label, value, ("   " + note) if note else ""))


def main():
    m = pd.read_csv(RETURNS)
    m["excess_over_cash"] = m["spread"]
    m["sp500_excess"] = m["sp500_ret"] - m["cash_monthly"]
    h = pd.read_parquet(HOLDINGS)
    n, yrs = len(m), len(m) / 12

    print("=" * 74)
    print("DECK PACK  %s .. %s  (%d months).  Gross of trading costs unless"
          % (m["target_month"].iloc[0], m["target_month"].iloc[-1], n))
    print("stated; see the cost table for net figures.")
    print("=" * 74)

    print("\nRETURN STATISTICS")
    cum = (1 + m["total"]).prod() - 1
    put("returns", "average monthly return", "%+.3f%%" % (100 * m["total"].mean()))
    put("returns", "annualised, arithmetic", "%+.2f%%" % (100 * 12 * m["total"].mean()))
    put("returns", "annualised, geometric (CAGR)",
        "%+.2f%%" % (100 * ((1 + cum) ** (1 / yrs) - 1)))
    put("returns", "cumulative over the period", "%+.2f%%" % (100 * cum))
    put("returns", "benchmark cumulative (cash+4%)",
        "%+.2f%%" % (100 * ((1 + m["hurdle"]).prod() - 1)))
    put("returns", "S&P 500 cumulative (price only)",
        "%+.2f%%" % (100 * ((1 + m["sp500_ret"]).prod() - 1)))
    put("returns", "best month",
        "%+.2f%%" % (100 * m["total"].max()), m.loc[m["total"].idxmax(), "target_month"])
    put("returns", "worst month",
        "%+.2f%%" % (100 * m["total"].min()), m.loc[m["total"].idxmin(), "target_month"])
    put("returns", "hit rate (months beating the hurdle)",
        "%.1f%%" % (100 * (m["active"] > 0).mean()))
    put("returns", "long leg, average month", "%+.3f%%" % (100 * m["long_leg"].mean()))
    put("returns", "short leg, average month", "%+.3f%%" % (100 * m["short_leg"].mean()))

    print("\nCALENDAR YEARS (strategy / hurdle / S&P 500)")
    m["year"] = m["target_month"].str[:4]
    for y, d in m.groupby("year"):
        s = "%+7.2f%% / %+6.2f%% / %+7.2f%%" % (
            100 * ((1 + d["total"]).prod() - 1), 100 * ((1 + d["hurdle"]).prod() - 1),
            100 * ((1 + d["sp500_ret"]).prod() - 1))
        put("calendar", y, s, "%d months" % len(d))

    print("\nRISK-ADJUSTED PERFORMANCE")
    ir = np.sqrt(12) * m["active"].mean() / m["active"].std(ddof=1)
    sharpe = np.sqrt(12) * m["excess_over_cash"].mean() / m["excess_over_cash"].std(ddof=1)
    reg = smf.ols("excess_over_cash ~ sp500_excess", data=m).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True)
    put("risk", "INFORMATION RATIO vs cash+4%", "%+.2f" % ir, "annualised, the headline")
    put("risk", "Sharpe ratio over cash", "%+.2f" % sharpe, "annualised")
    put("risk", "alpha vs S&P 500, annualised",
        "%+.2f%%" % (100 * 12 * reg.params["Intercept"]),
        "t=%+.2f" % reg.tvalues["Intercept"])
    put("risk", "BETA vs S&P 500", "%+.3f" % reg.params["sp500_excess"],
        "se=%.3f -- the neutrality evidence" % reg.bse["sp500_excess"])
    put("risk", "correlation with the S&P 500",
        "%+.2f" % m["excess_over_cash"].corr(m["sp500_ret"]))
    curve = (1 + m["total"]).cumprod()
    put("risk", "maximum drawdown (monthly marks)",
        "%+.2f%%" % (100 * (curve / curve.cummax() - 1).min()))
    if DAILY.exists():
        d = pd.read_csv(DAILY)
        c = (1 + d["total"]).cumprod()
        put("risk", "maximum drawdown (daily marks)",
            "%+.2f%%" % (100 * (c / c.cummax() - 1).min()),
            "82.3% of book covered -- optimistic")
        put("risk", "worst single day", "%+.2f%%" % (100 * d["total"].min()),
            "same coverage caveat")

    print("\nEXPOSURE, CONCENTRATION AND IMPLEMENTATION")
    g = h.groupby("target_month")
    stats = pd.DataFrame({
        "n": g.size(),
        "n_long": h[h["weight"] > 0].groupby("target_month").size(),
        "n_short": h[h["weight"] < 0].groupby("target_month").size(),
        "gross": g["weight"].apply(lambda w: w.abs().sum()),
        "net": g["weight"].sum(),
        "max_abs": g["weight"].apply(lambda w: w.abs().max()),
        "mean_abs": g["weight"].apply(lambda w: w.abs().mean()),
        "top10": g["weight"].apply(lambda w: w.abs().nlargest(10).sum() / w.abs().sum()),
    })
    piv = h.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1).iloc[1:]
    turn = (traded / (2 * piv.abs().sum(axis=1).iloc[1:]))

    put("exposure", "average holdings", "%.0f" % stats["n"].mean(),
        "%.0f long / %.0f short" % (stats["n_long"].mean(), stats["n_short"].mean()))
    put("exposure", "average gross exposure", "%.1f%%" % (100 * stats["gross"].mean()),
        "range %.1f%%-%.1f%%" % (100 * stats["gross"].min(), 100 * stats["gross"].max()))
    put("exposure", "average net exposure", "%+.1f%%" % (100 * stats["net"].mean()),
        "range %+.1f%% to %+.1f%%" % (100 * stats["net"].min(), 100 * stats["net"].max()))
    put("exposure", "average single position", "%.3f%%" % (100 * stats["mean_abs"].mean()))
    put("exposure", "maximum single position", "%.2f%%" % (100 * stats["max_abs"].max()))
    put("exposure", "share of book in the top 10 names",
        "%.1f%%" % (100 * stats["top10"].mean()))
    put("exposure", "average monthly turnover", "%.1f%%" % (100 * turn.mean()),
        "range %.0f%%-%.0f%%" % (100 * turn.min(), 100 * turn.max()))
    put("exposure", "notional traded per month",
        "%.0f%% of capital" % (100 * traded.mean()))

    print("\nSHORT BOOK -- BORROWABILITY")
    S, L = h[h["weight"] < 0], h[h["weight"] > 0]
    put("short_book", "median market cap, short leg", "$%.0fm" % S["me"].median(),
        "long leg $%.0fm" % L["me"].median())
    if "dolvol" in h.columns and h["dolvol"].notna().any():
        put("short_book", "median daily dollar volume, short leg",
            "$%.1fm" % (S["dolvol"].median() / 1e6),
            "long leg $%.1fm" % (L["dolvol"].median() / 1e6))
    else:
        put("short_book", "median dollar volume, short leg", "NOT COMPUTED",
            "add dolvol to PANEL_COLS in stage 4")
    put("short_book", "median price, short leg", "$%.2f" % S["prc"].median())
    put("short_book", "share of short leg in small caps or below",
        "%.1f%%" % (100 * S["size_grp"].isin(["nano", "micro", "small"]).mean()),
        "nano/micro excluded by screen")

    print("\nCOST SENSITIVITY (the number that decides whether this is tradable)")
    notional = traded.reindex(m["target_month"]).fillna(0.0).values
    for bps in [0, 10, 20, 30, 50]:
        net = m["total"].values - notional * bps / 10000
        act = net - m["hurdle"].values
        put("costs", "IR at %d bps per trade" % bps,
            "%+.2f" % (np.sqrt(12) * act.mean() / act.std(ddof=1)),
            "annualised %+.2f%%" % (100 * (((1 + pd.Series(net)).prod()) ** (1 / yrs) - 1)))

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

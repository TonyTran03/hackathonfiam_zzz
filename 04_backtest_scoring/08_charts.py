"""Stage 5d -- the exhibits the deck needs.

The rules list these by name. Each one is written to 05_submission/figures/
at a size that drops straight onto a slide.

  cumulative     strategy against the cash+4% hurdle and the S&P 500
  underwater     drawdown, with the S&P 500 overlaid
  rolling_beta   12-month beta -- the clearest picture of whether the book
                 stayed neutral throughout or only on average
  rolling_ir     12-month active return and information ratio
  histogram      monthly returns with the hurdle marked
  contributors   the 10 largest positive and negative contributors to P&L

Plus two tables the deck asks for by name:

  top_holdings.csv      the 10 largest average long and short positions
  contributors.csv      the same names behind the contributors chart

Every holding is identified by ticker AND full company name, as required.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

FIGS = C.ROOT / "05_submission" / "figures"
RETURNS = C.ROOT / "05_submission" / "portfolio_returns.csv"
HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12

STRAT, HURDLE, MARKET = "#1f4e79", "#7f7f7f", "#c00000"
plt.rcParams.update({"figure.dpi": 130, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / ("%s.png" % name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("  wrote %s" % path.relative_to(C.ROOT))


def months(m):
    return pd.PeriodIndex(m["target_month"], freq="M").to_timestamp()


def chart_cumulative(m):
    x = months(m)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(x, 100 * ((1 + m["total"]).cumprod() - 1), color=STRAT, lw=1.8,
            label="Strategy")
    ax.plot(x, 100 * ((1 + m["hurdle"]).cumprod() - 1), color=HURDLE, lw=1.4,
            ls="--", label="3M T-bill + 4%/yr")
    ax.plot(x, 100 * ((1 + m["sp500_ret"]).cumprod() - 1), color=MARKET, lw=1.2,
            alpha=0.8, label="S&P 500 (price)")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylabel("cumulative return, %")
    ax.set_title("Cumulative return, %s to %s (gross of trading costs)"
                 % (m["target_month"].iloc[0], m["target_month"].iloc[-1]))
    ax.legend(frameon=False, loc="upper left")
    save(fig, "cumulative")


def chart_underwater(m):
    x = months(m)
    def dd(r):
        c = (1 + r).cumprod()
        return 100 * (c / c.cummax() - 1)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.fill_between(x, dd(m["total"]), 0, color=STRAT, alpha=0.75, label="Strategy")
    ax.plot(x, dd(m["sp500_ret"]), color=MARKET, lw=1.2, label="S&P 500")
    ax.set_ylabel("drawdown, %")
    ax.set_title("Underwater plot, %s to %s"
                 % (m["target_month"].iloc[0], m["target_month"].iloc[-1]))
    ax.legend(frameon=False, loc="lower left")
    save(fig, "underwater")


def rolling_stats(m, w=12):
    betas, irs, act = [], [], []
    for i in range(w, len(m) + 1):
        d = m.iloc[i - w:i]
        betas.append(smf.ols("excess_over_cash ~ sp500_excess", data=d)
                     .fit().params["sp500_excess"])
        irs.append(np.sqrt(12) * d["active"].mean() / d["active"].std(ddof=1))
        act.append((1 + d["active"]).prod() - 1)
    idx = months(m)[w - 1:]
    return idx, np.array(betas), np.array(irs), np.array(act)


def chart_rolling_beta(m):
    x, betas, _, _ = rolling_stats(m)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(x, betas, color=STRAT, lw=1.6)
    ax.axhline(0, color="black", lw=0.8)
    ax.axhspan(-0.3, 0.3, color=HURDLE, alpha=0.15,
               label="within $\\pm$0.3 of zero")
    ax.set_ylabel("beta vs S&P 500")
    ax.set_title("Rolling 12-month beta (full period %+.2f)"
                 % smf.ols("excess_over_cash ~ sp500_excess", data=m)
                        .fit().params["sp500_excess"])
    ax.legend(frameon=False, loc="lower left")
    save(fig, "rolling_beta")


def chart_rolling_ir(m):
    x, _, irs, act = rolling_stats(m)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 4.2), sharex=True)
    a1.bar(x, 100 * act, width=22, color=STRAT, alpha=0.85)
    a1.axhline(0, color="black", lw=0.8)
    a1.set_ylabel("12M active return, %")
    a2.plot(x, irs, color=STRAT, lw=1.6)
    a2.axhline(0, color="black", lw=0.8)
    a2.set_ylabel("12M information ratio")
    a1.set_title("Rolling 12-month active return and information ratio vs cash+4%")
    save(fig, "rolling_ir")


def chart_histogram(m):
    fig, ax = plt.subplots(figsize=(6, 3.0))
    ax.hist(100 * m["total"], bins=22, color=STRAT, alpha=0.85, edgecolor="white")
    ax.axvline(100 * m["hurdle"].mean(), color=MARKET, lw=1.6,
               label="average monthly hurdle %.2f%%" % (100 * m["hurdle"].mean()))
    ax.set_xlabel("monthly total return, %")
    ax.set_ylabel("months")
    ax.set_title("Distribution of monthly returns (%d months)" % len(m))
    ax.legend(frameon=False)
    save(fig, "histogram")


def contributors(h):
    h = h.copy()
    h["pnl"] = h["weight"] * h[C.TARGET].fillna(0.0)
    h["side"] = np.where(h["weight"] > 0, "long", "short")
    by = (h.groupby(["permno", "ticker", "company_name"])
            .agg(pnl=("pnl", "sum"), months=("pnl", "size"),
                 side=("side", lambda s: s.mode().iat[0]))
            .reset_index().sort_values("pnl"))
    worst, best = by.head(10), by.tail(10).iloc[::-1]
    table = pd.concat([best.assign(rank="top 10"), worst.assign(rank="bottom 10")])
    table.to_csv(C.ROOT / "05_submission" / "contributors.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4.4))
    show = pd.concat([worst, best.iloc[::-1]])
    labels = ["%s  %s" % (r.ticker, str(r.company_name)[:28]) for r in show.itertuples()]
    ax.barh(range(len(show)), 100 * show["pnl"],
            color=[MARKET if v < 0 else STRAT for v in show["pnl"]])
    ax.set_yticks(range(len(show)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("total contribution to portfolio return, %")
    ax.set_title("10 largest positive and 10 largest negative contributors")
    save(fig, "contributors")
    return table


def top_holdings(h):
    h = h.copy()
    rows = []
    for side, sub in [("long", h[h["weight"] > 0]), ("short", h[h["weight"] < 0])]:
        agg = (sub.groupby(["permno", "ticker", "company_name"])
                  .agg(avg_weight=("weight", "mean"), months_held=("weight", "size"))
                  .reset_index())
        agg["avg_weight_overall"] = agg["avg_weight"] * agg["months_held"] / h["target_month"].nunique()
        agg = agg.reindex(agg["avg_weight_overall"].abs().sort_values(ascending=False).index)
        rows.append(agg.head(10).assign(side=side))
    table = pd.concat(rows)
    table.to_csv(C.ROOT / "05_submission" / "top_holdings.csv", index=False)
    print("\n  top 10 long and top 10 short by average weight over the period:")
    for side in ["long", "short"]:
        print("    %s:" % side)
        for r in table[table["side"] == side].itertuples():
            print("      %-6s %-34s %+6.3f%% avg, held %d/%d months"
                  % (r.ticker, str(r.company_name)[:34], 100 * r.avg_weight_overall,
                     r.months_held, h["target_month"].nunique()))
    return table


def main():
    m = pd.read_csv(RETURNS)
    m["excess_over_cash"] = m["spread"]
    m["sp500_excess"] = m["sp500_ret"] - m["cash_monthly"]
    h = pd.read_parquet(HOLDINGS)

    print("figures and tables for the deck:")
    chart_cumulative(m)
    chart_underwater(m)
    chart_rolling_beta(m)
    chart_rolling_ir(m)
    chart_histogram(m)
    contributors(h)
    top_holdings(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Final stage 6 -- the standardised table (Section 9.1) and the exhibits (9.4).

    python 06_final/f06_report.py <run_tag> [<label>]

Every number written here comes from 06_final/data/runs/<run_tag>/ and lands in
06_final/output/<label>/, so any figure on a slide can be traced to a file.

Conventions (Section 9.2), stated once:
  * the strategy is marked DAILY, so the risk-adjusted ratios use daily
    moments annualised by 252 and sqrt(252); monthly versions (12, sqrt 12)
    are reported beside them and labelled
  * "annualised return" is the arithmetic mean x 252; CAGR is reported
    separately and is what ties to the ending endowment
  * IR vs T-bill + 4% in the table is BEFORE trading and borrow costs; the
    last row is the same ratio net of all costs, which is the honest number
  * alpha and beta: OLS of (strategy - rf) on (S&P 500 - rf). Daily beta is
    the lag-0 slope as the instructions specify; a Dimson (lag 0 + 1) beta is
    reported beside it because a small-cap long book trades on stale prices
  * turnover: 1/2 x sum |w_after - w_before| on each rebalance date
  * holding period: measured directly, the position-weighted average number
    of trading days a name stays in the book
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402


def label_table():
    """Ticker and name per permno: the latest LABELLED month in the panel.
    The panel leaves some stock-months unlabelled on purpose; a holding is
    named from its nearest labelled month, as in round 1 (04_build_portfolio
    fill_labels), and label_month says which month that was."""
    from common import config as C
    pnl_ = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "target_month", "ticker", "company_name"])
    pnl_ = pnl_.dropna(subset=["ticker"]).sort_values("target_month")
    return pnl_.drop_duplicates("permno", keep="last").set_index("permno")[
        ["ticker", "company_name", "target_month"]].rename(columns={"target_month": "label_month"})

NAVY, RED, GREY, BLUE = "#1f2a5c", "#c0392b", "#888888", "#2f6690"


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X))
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    s2 = res @ res / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return coef, se, 1 - res.var() / y.var()


def max_dd(nav):
    return float((nav / nav.cummax() - 1).min())


def holding_period(pnl):
    """Position-weighted average run length, in trading days."""
    p = pnl[["di", "permno", "x"]].copy()
    p["side"] = np.sign(p["x"])
    p = p.sort_values(["permno", "di"])
    brk = (p["permno"].ne(p["permno"].shift()) | p["di"].ne(p["di"].shift() + 1)
           | p["side"].ne(p["side"].shift()))
    p["run"] = brk.cumsum()
    runs = p.groupby("run").agg(days=("di", "size"), size=("x", lambda v: np.abs(v).mean()))
    return float(np.average(runs["days"], weights=runs["size"])), runs


def monthly(d):
    g = d.groupby("month")
    m = pd.DataFrame({
        "ret": g["ret"].apply(lambda s: np.prod(1 + s) - 1),
        "ret_gross": g["ret_gross"].apply(lambda s: np.prod(1 + s) - 1),
        "hurdle": g["hurdle"].apply(lambda s: np.prod(1 + s) - 1),
        "rf": g["rf"].apply(lambda s: np.prod(1 + s) - 1),
        "sp": g["sp_ret"].apply(lambda s: np.prod(1 + s) - 1),
    })
    return m


def table(run, sig):
    d, pnl, trades = run["daily"], run["pnl"], run["trades"]
    nav0 = F.FINAL["start_nav"]
    yrs = len(d) / 252
    ex = d["ret"] - d["rf"]
    exg = d["ret_gross"] - d["rf"]
    mk = d["sp_ret"] - d["rf"]
    act_g = d["ret_gross"] - d["hurdle"]
    act_n = d["ret"] - d["hurdle"]
    m = monthly(d)

    cb, sb, _ = ols(exg.values, [mk.values])                   # daily, lag 0
    cd, sd, _ = ols(exg.values[1:], [mk.values[1:], mk.values[:-1]])
    mm = m["ret_gross"] - m["rf"]
    cm, sm_, _ = ols(mm.values, [(m["sp"] - m["rf"]).values])

    hurdle_nav = nav0 * np.cumprod(1 + d["hurdle"].values)
    sp_nav = nav0 * np.cumprod(1 + d["sp_ret"].values)
    nav_g = nav0 * np.cumprod(1 + d["ret_gross"].values)

    hp, _ = holding_period(pnl)
    reb = d[d["turnover"] > 0]
    n_reb_year = len(reb) / yrs
    form = run["formations"]

    # short book median market cap, at each formation (from the engine's inputs)
    sh = run["short_me"]

    rows = [
        ("Ending value of the endowment", "US$ billion",
         d["nav"].iloc[-1] / 1e9, hurdle_nav[-1] / 1e9, sp_nav[-1] / 1e9),
        ("Ending value, before costs", "US$ billion", nav_g[-1] / 1e9, None, None),
        ("Cumulative return over the period", "%",
         100 * (d["nav"].iloc[-1] / nav0 - 1), 100 * (hurdle_nav[-1] / nav0 - 1),
         100 * (sp_nav[-1] / nav0 - 1)),
        ("Annualised return (arithmetic, daily x 252)", "% per year",
         100 * 252 * d["ret"].mean(), 100 * 252 * d["hurdle"].mean(), 100 * 252 * d["sp_ret"].mean()),
        ("CAGR (ties to the endowment)", "% per year",
         100 * ((d["nav"].iloc[-1] / nav0) ** (1 / yrs) - 1),
         100 * ((hurdle_nav[-1] / nav0) ** (1 / yrs) - 1),
         100 * ((sp_nav[-1] / nav0) ** (1 / yrs) - 1)),
        ("Annualised volatility (daily x sqrt 252)", "% per year",
         100 * np.sqrt(252) * d["ret"].std(), 100 * np.sqrt(252) * d["hurdle"].std(),
         100 * np.sqrt(252) * d["sp_ret"].std()),
        ("Annualised alpha vs S&P 500, monthly regression", "% per year (s.e.)",
         "%.2f (%.2f)" % (1200 * cm[0], 1200 * sm_[0]), "n/a", "n/a"),
        ("Annualised alpha vs S&P 500, daily regression", "% per year (s.e.)",
         "%.2f (%.2f)" % (25200 * cb[0], 25200 * sb[0]), "n/a", "n/a"),
        ("Beta vs S&P 500 - monthly coefficient", "(s.e.)",
         "%.3f (%.3f)" % (cm[1], sm_[1]), "n/a", "1.000"),
        ("Beta vs S&P 500 - daily coefficient", "(s.e.)",
         "%.3f (%.3f)" % (cb[1], sb[1]), "n/a", "1.000"),
        ("Beta vs S&P 500 - daily, Dimson lag 0+1", "(s.e. of lag-0 term)",
         "%.3f (%.3f)" % (cd[1] + cd[2], sd[1]), "n/a", "n/a"),
        ("Sharpe ratio (daily, net of all costs)", "annualised",
         np.sqrt(252) * ex.mean() / ex.std(), "n/a (riskless premium)", np.sqrt(252) * mk.mean() / mk.std()),
        ("Sharpe ratio (daily, before costs)", "annualised",
         np.sqrt(252) * exg.mean() / exg.std(), "n/a", "n/a"),
        ("Information ratio vs T-bill + 4%, before costs", "annualised (daily)",
         np.sqrt(252) * act_g.mean() / act_g.std(), "n/a", "n/a"),
        ("Information ratio vs T-bill + 4%, before costs", "annualised (monthly)",
         np.sqrt(12) * (m["ret_gross"] - m["hurdle"]).mean() / (m["ret_gross"] - m["hurdle"]).std(),
         "n/a", "n/a"),
        ("Tracking error vs T-bill + 4%", "% per year",
         100 * np.sqrt(252) * act_n.std(), "n/a", "n/a"),
        ("Maximum drawdown (daily marks)", "%", 100 * max_dd(d["nav"]),
         100 * max_dd(pd.Series(hurdle_nav)), 100 * max_dd(pd.Series(sp_nav))),
        ("Maximum one-month loss", "%", 100 * m["ret"].min(), 100 * m["hurdle"].min(), 100 * m["sp"].min()),
        ("Maximum one-day loss", "%", 100 * d["ret"].min(), 100 * d["hurdle"].min(), 100 * d["sp_ret"].min()),
        ("Positions held", "average / min / max",
         "%.0f / %d / %d" % ((d["n_long"] + d["n_short"]).mean(),
                             (d["n_long"] + d["n_short"]).iloc[1:].min(),
                             (d["n_long"] + d["n_short"]).max()), "n/a", "n/a"),
        ("Long / short names", "average",
         "%.0f / %.0f" % (d["n_long"].mean(), d["n_short"].mean()), "n/a", "n/a"),
        ("Gross exposure", "average / maximum, % of capital",
         "%.1f / %.1f" % (100 * d["gross"].iloc[1:].mean(), 100 * d["gross"].max()), "n/a", "n/a"),
        ("Net exposure", "average / min / max, % of capital",
         "%+.1f / %+.1f / %+.1f" % (100 * d["net"].iloc[1:].mean(), 100 * d["net"].iloc[1:].min(),
                                    100 * d["net"].iloc[1:].max()), "n/a", "n/a"),
        ("Largest single position", "max % of capital", 100 * d["max_w"].max(), "n/a", "n/a"),
        ("One-way turnover", "% per rebalance / annualised",
         "%.1f / %.0f" % (100 * reb["turnover"].mean(), 100 * d["turnover"].sum() / yrs), "n/a", "n/a"),
        ("Rebalances", "per year", n_reb_year, "n/a", "n/a"),
        ("Average holding period", "trading days, measured", hp, "n/a", "n/a"),
        ("Holding period, approximation", "avg gross / annual turnover x 252",
         252 * d["gross"].iloc[1:].mean() / (d["turnover"].sum() / yrs), "n/a", "n/a"),
        ("Average position size", "US$ million",
         (pnl["x"].abs().mean()) / 1e6, "n/a", "n/a"),
        ("Short book median market cap", "US$ million", sh, "n/a", "n/a"),
        ("Trading cost", "% of NAV per year",
         100 * d["cost"].sum() / d["nav"].mean() / yrs, "n/a", "n/a"),
        ("Borrow cost", "% of NAV per year",
         100 * d["borrow"].sum() / d["nav"].mean() / yrs, "n/a", "n/a"),
        ("Information ratio, net of all costs", "annualised (daily)",
         np.sqrt(252) * act_n.mean() / act_n.std(), "n/a", "n/a"),
        ("Information ratio, net of all costs", "annualised (monthly)",
         np.sqrt(12) * (m["ret"] - m["hurdle"]).mean() / (m["ret"] - m["hurdle"]).std(), "n/a", "n/a"),
        ("Correlation with S&P 500", "daily / monthly",
         "%.3f / %.3f" % (np.corrcoef(d["ret"], d["sp_ret"])[0, 1], np.corrcoef(m["ret"], m["sp"])[0, 1]),
         "n/a", "n/a"),
        ("Hit rate: months beating the hurdle", "%",
         100 * (m["ret"] > m["hurdle"]).mean(), "n/a", "n/a"),
    ]
    t = pd.DataFrame(rows, columns=["metric", "units", "strategy", "benchmark_tbill_4pct", "sp500_context"])
    return t, m


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return "%.2f" % v


# ------------------------------------------------------------------ exhibits
def exhibits(run, sig, outdir, m):
    d, pnl = run["daily"], run["pnl"]
    fig_dir = outdir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    nav0 = F.FINAL["start_nav"]

    # 1 cumulative: strategy, hurdle, S&P; and cumulative active
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    ax[0].plot(d["date"], 100 * (d["nav"] / nav0 - 1), color=NAVY, lw=1.8, label="Strategy, net of costs")
    ax[0].plot(d["date"], 100 * (np.cumprod(1 + d["ret_gross"]) - 1), color=BLUE, lw=1, ls=":",
               label="Strategy, before costs")
    ax[0].plot(d["date"], 100 * (np.cumprod(1 + d["hurdle"]) - 1), color=GREY, ls="--", label="3M T-bill + 4%")
    ax[0].plot(d["date"], 100 * (np.cumprod(1 + d["sp_ret"]) - 1), color=RED, lw=1, label="S&P 500 (price)")
    ax[0].set_title("Cumulative return, daily marks, %s to %s" % (d["date"].iloc[0].date(), d["date"].iloc[-1].date()))
    ax[0].set_ylabel("%"); ax[0].legend(frameon=False, fontsize=8)
    act = np.cumprod(1 + d["ret"]) / np.cumprod(1 + d["hurdle"]) - 1
    actg = np.cumprod(1 + d["ret_gross"]) / np.cumprod(1 + d["hurdle"]) - 1
    ax[1].plot(d["date"], 100 * act, color=NAVY, label="net of costs")
    ax[1].plot(d["date"], 100 * actg, color=BLUE, ls=":", label="before costs")
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set_title("Cumulative active return vs T-bill + 4%"); ax[1].set_ylabel("%")
    ax[1].legend(frameon=False, fontsize=8)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "cumulative.png", dpi=160); plt.close(fig)

    # 2 rolling 252-day beta (lag 0 and Dimson)
    y = d["ret_gross"] - d["rf"]; x = d["mkt_ex"]
    rb = y.rolling(252).cov(x) / x.rolling(252).var()
    xl = x.shift(1)
    rb1 = rb + y.rolling(252).cov(xl) / xl.rolling(252).var()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.axhspan(-0.3, 0.3, color="#eeeeee")
    ax.plot(d["date"], rb, color=NAVY, label="daily OLS, lag 0")
    ax.plot(d["date"], rb1, color=BLUE, ls=":", label="Dimson lag 0 + 1 (approx.)")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_title("Rolling 252-day beta to the S&P 500"); ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "rolling_beta.png", dpi=160); plt.close(fig)
    pd.DataFrame({"date": d["date"], "beta_252d": rb, "beta_252d_dimson_approx": rb1}).to_csv(
        outdir / "rolling_beta.csv", index=False)

    # 3 calendar-year returns, before / after costs, benchmark, S&P
    d2 = d.assign(year=d["date"].dt.year)
    cy = d2.groupby("year").agg(
        strategy_net=("ret", lambda s: np.prod(1 + s) - 1),
        strategy_before_costs=("ret_gross", lambda s: np.prod(1 + s) - 1),
        benchmark=("hurdle", lambda s: np.prod(1 + s) - 1),
        sp500=("sp_ret", lambda s: np.prod(1 + s) - 1)) * 100
    cy.to_csv(outdir / "calendar_years.csv")
    fig, ax = plt.subplots(figsize=(8, 3.6))
    xs = np.arange(len(cy)); wdt = 0.27
    ax.bar(xs - wdt, cy["strategy_before_costs"], wdt, color=BLUE, label="before costs")
    ax.bar(xs, cy["strategy_net"], wdt, color=NAVY, label="net of costs")
    ax.bar(xs + wdt, cy["benchmark"], wdt, color=GREY, label="T-bill + 4%")
    ax.set_xticks(xs, [str(y) + ("*" if y == 2026 else "") for y in cy.index])
    ax.axhline(0, color="k", lw=0.6); ax.set_ylabel("%")
    ax.set_title("Calendar-year returns (*2026: Jan-Aug)"); ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "calendar_years.png", dpi=160); plt.close(fig)

    # 4 exposures through time
    fig, ax = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    ax[0].plot(d["date"], 100 * d["gross"], color=NAVY, label="gross")
    ax[0].plot(d["date"], 100 * d["net"], color=RED, label="net")
    ax[0].axhline(200, color="k", lw=0.6, ls="--"); ax[0].axhline(50, color=GREY, lw=0.6, ls="--")
    ax[0].axhline(-50, color=GREY, lw=0.6, ls="--")
    ax[0].set_ylabel("% of capital"); ax[0].legend(frameon=False, fontsize=8, ncol=2)
    ax[1].plot(d["date"], d["n_long"] + d["n_short"], color=NAVY, label="positions")
    ax[1].axhline(200, color="k", lw=0.6, ls="--"); ax[1].axhline(500, color="k", lw=0.6, ls="--")
    ax[1].set_ylabel("names")
    ax[0].set_title("Gross and net exposure and position count, every trading day")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "exposures.png", dpi=160); plt.close(fig)

    # 5 top/bottom 10 by average weight; 6 contributors
    names = label_table()
    navs = d["nav"].shift(1).fillna(F.FINAL["start_nav"]).values
    pnl = pnl.copy()
    pnl["w"] = pnl["x"] / navs[pnl["di"].astype(int)]
    ndays = len(d)
    avgw = pnl.groupby("permno")["w"].sum() / ndays
    top = avgw.sort_values(ascending=False).head(10)
    bot = avgw.sort_values().head(10)
    hold = pd.concat([top.rename("avg_weight").to_frame().assign(side="long"),
                      bot.rename("avg_weight").to_frame().assign(side="short")])
    hold = hold.join(names).reset_index()
    hold["avg_weight_pct"] = 100 * hold["avg_weight"]
    hold.to_csv(outdir / "top_holdings.csv", index=False)

    contrib = (pnl.groupby("permno")["pnl"].sum() / F.FINAL["start_nav"] * 100).rename("contribution_pct_of_start_nav")
    cb = pd.concat([contrib.sort_values(ascending=False).head(10),
                    contrib.sort_values().head(10)]).to_frame().join(names).reset_index()
    cb.to_csv(outdir / "contributors.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 5.5))
    cbs = cb.sort_values("contribution_pct_of_start_nav")
    lab = cbs["ticker"].fillna("?") + "  " + cbs["company_name"].fillna("").str.slice(0, 26)
    ax.barh(range(len(cbs)), cbs["contribution_pct_of_start_nav"],
            color=[NAVY if v > 0 else RED for v in cbs["contribution_pct_of_start_nav"]])
    ax.set_yticks(range(len(cbs)), lab, fontsize=7)
    ax.set_xlabel("P&L, % of starting NAV"); ax.set_title("10 largest positive and negative contributors")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "contributors.png", dpi=160); plt.close(fig)

    # 7 short-book cap and dollar volume at formation; 8 position size in days of ADV
    shorts = run["short_rows"]
    longs = run["long_rows"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    bins = np.logspace(2, 6.5, 40)
    ax[0].hist(shorts["me_form"], bins=bins, color=NAVY)
    ax[0].axvline(500, color=RED, ls="--", label="US$500m floor")
    ax[0].set_xscale("log"); ax[0].set_xlabel("market cap at formation, US$m")
    ax[0].set_title("Short book: market cap at formation (min %.0f)" % shorts["me_form"].min())
    ax[0].legend(frameon=False, fontsize=8)
    ax[1].hist(shorts["dolvol_126d"] / 1e6, bins=np.logspace(0, 4.5, 40), color=NAVY)
    ax[1].axvline(np.median(shorts["dolvol_126d"]) / 1e6, color=RED, ls=":", label="median")
    ax[1].set_xscale("log"); ax[1].set_xlabel("average daily dollar volume, US$m")
    ax[1].set_title("Short book: ADV at formation")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "short_book.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    b = np.linspace(0, 0.4, 41)
    ax.hist(longs["days_adv"], bins=b, alpha=0.7, color=NAVY, label="long leg")
    ax.hist(shorts["days_adv"], bins=b, alpha=0.6, color=RED, label="short leg")
    ax.set_xlabel("position size in days of average daily volume")
    ax.set_title("Position size vs liquidity at formation (cap: 0.3 days)")
    ax.legend(frameon=False, fontsize=8); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "days_adv.png", dpi=160); plt.close(fig)
    pd.concat([longs.assign(leg="long"), shorts.assign(leg="short")]).to_csv(
        outdir / "formation_positions.csv", index=False)

    # 9 underwater + rolling 12m active and IR (kept from round 1)
    dd = d["nav"] / d["nav"].cummax() - 1
    spn = np.cumprod(1 + d["sp_ret"]); spdd = spn / spn.cummax() - 1
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.fill_between(d["date"], 100 * dd, color=NAVY, alpha=0.7, label="strategy")
    ax.plot(d["date"], 100 * spdd, color=RED, lw=1, label="S&P 500")
    ax.set_title("Underwater, daily marks"); ax.set_ylabel("%"); ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(fig_dir / "underwater.png", dpi=160); plt.close(fig)


def formation_rows(run_dir, sig):
    """The book as FORMED each month: target weights set at the close of the
    formation day, with market cap at that close and ADV at month end. Names
    still being worked out of last month's book are not part of the formed
    book and are excluded here (they are in the daily holdings file)."""
    t = pd.read_parquet(run_dir / "targets.parquet")
    t["days_adv"] = t["target_usd"].abs() / t["dolvol_126d"]
    t["x"] = t["target_usd"]
    t["me_form"] = t["me_formation"]
    return t[t["x"] > 0], t[t["x"] < 0]


def report(tag, label=None, window="test"):
    label = label or tag
    run_dir = F.DATA / "runs" / tag
    outdir = F.OUT / label
    outdir.mkdir(parents=True, exist_ok=True)
    run = {k: pd.read_parquet(run_dir / (k + ".parquet"))
           for k in ["daily", "pnl", "trades", "formations"]}
    sig = pd.read_parquet(F.DATA / ("signal_%s.parquet" % window))
    run["long_rows"], run["short_rows"] = formation_rows(run_dir, sig)
    run["short_me"] = float(run["short_rows"]["me_form"].median())
    t, m = table(run, sig)
    t2 = t.copy()
    for c in ["strategy", "benchmark_tbill_4pct", "sp500_context"]:
        t2[c] = t2[c].map(fmt)
    t2.to_csv(outdir / "standard_table.csv", index=False)
    m.to_csv(outdir / "monthly_returns.csv")
    run["daily"].to_csv(outdir / "daily_returns.csv", index=False)
    exhibits(run, sig, outdir, m)
    print(t2.to_string(index=False))
    return t2


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None,
           "design" if sys.argv[1].startswith("design") else "test")

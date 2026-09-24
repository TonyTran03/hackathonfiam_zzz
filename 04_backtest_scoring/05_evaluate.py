"""Stage 5 -- score the book against the competition's benchmark.

Accounting convention, stated explicitly because the rules ask for it:

  Capital is 1.0 and sits as collateral earning the cash rate. The short
  proceeds finance the long leg, so with weights that sum to zero

      portfolio total return = cash_t + sum_i w_i * excess_return_i

  and the active return against the hurdle is

      active_t = portfolio_total_t - (cash_t + 0.04/12)

  which reduces to the weighted excess-return spread minus 0.04/12 whenever
  the collateral rate equals the benchmark cash rate. We use the same cash
  series for both, so it does.

One caveat carried from the data: the risk-free rate used to build the
panel's excess returns is not necessarily the same series as the cash rate
here. The rules warn about exactly this; the residual difference is small but
it is not zero, and it is not netted out anywhere.

The information ratio is computed from active returns, NOT as alpha over
residual volatility -- the supplied teaching template does the latter and
labels it the same thing.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
RETURNS_CSV = C.ROOT / "05_submission" / "portfolio_returns.csv"
PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12


def monthly_returns(h):
    """Weighted excess-return spread, and each leg separately."""
    h = h.copy()
    unavailable = h[C.TARGET].isna()
    # A held position with no realised return (delisted, acquired, or the
    # panel simply stops) is marked at config.TEAM["delisting_return"]. The
    # mark is a team convention, not a rule, so it lives in TEAM and the
    # sensitivity grid next to it is reported by 11_deck_pack.py. Shumway
    # (1997) is the usual reference for -0.30; 0.0 is the optimistic default.
    h["r"] = h[C.TARGET].fillna(C.TEAM["delisting_return"])
    h["contrib"] = h["weight"] * h["r"]

    g = h.groupby("target_month")
    out = pd.DataFrame({
        "spread": g["contrib"].sum(),
        "long_leg": h[h["weight"] > 0].groupby("target_month")["contrib"].sum(),
        "short_leg": h[h["weight"] < 0].groupby("target_month")["contrib"].sum(),
        "n": g.size(),
        "gross": g["weight"].apply(lambda w: w.abs().sum()),
        "net": g["weight"].sum(),
        "max_abs_w": g["weight"].apply(lambda w: w.abs().max()),
        "n_missing_ret": unavailable.groupby(h["target_month"]).sum(),
    }).reset_index()
    return out


def turnover(h):
    """Share of the book replaced each month, averaged over the period."""
    piv = h.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    changed = piv.diff().abs().sum(axis=1)
    gross = piv.abs().sum(axis=1)
    return (changed / (2 * gross)).iloc[1:]      # one-way turnover


def drawdown(total_returns):
    curve = (1 + total_returns).cumprod()
    peak = curve.cummax()
    return (curve / peak - 1)


def evaluate():
    if not HOLDINGS.exists():
        raise SystemExit("missing %s -- run stage 4 first" % HOLDINGS)

    h = pd.read_parquet(HOLDINGS)
    bm = pd.read_csv(C.BENCHMARK_CSV)

    m = monthly_returns(h).merge(bm, on="target_month", how="left")
    m = m.sort_values("target_month").reset_index(drop=True)

    m["total"] = m["cash_monthly"] + m["spread"]
    m["hurdle"] = m["cash_monthly"] + PREMIUM_M
    m["active"] = m["total"] - m["hurdle"]
    m["excess_over_cash"] = m["spread"]
    m["sp500_excess"] = m["sp500_ret"] - m["cash_monthly"]

    to = turnover(h)
    n_months = len(m)
    yrs = n_months / 12

    ir = np.sqrt(12) * m["active"].mean() / m["active"].std(ddof=1)
    sharpe = np.sqrt(12) * m["excess_over_cash"].mean() / m["excess_over_cash"].std(ddof=1)
    reg = smf.ols("excess_over_cash ~ sp500_excess", data=m).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True)
    alpha_m, beta = reg.params["Intercept"], reg.params["sp500_excess"]
    dd = drawdown(m["total"])

    cum = (1 + m["total"]).prod() - 1
    cagr = (1 + cum) ** (1 / yrs) - 1
    sp_cum = (1 + m["sp500_ret"]).prod() - 1
    hurdle_cum = (1 + m["hurdle"]).prod() - 1

    print("=" * 66)
    print("BASELINE  %s .. %s  (%d months)"
          % (m["target_month"].iloc[0], m["target_month"].iloc[-1], n_months))
    print("=" * 66)
    print("\nRETURNS")
    print("  mean monthly total return      %+8.3f%%" % (100 * m["total"].mean()))
    print("  annualised (geometric)         %+8.2f%%" % (100 * cagr))
    print("  cumulative over the period     %+8.2f%%" % (100 * cum))
    print("  benchmark  cash + 4%%/yr        %+8.2f%%  cumulative" % (100 * hurdle_cum))
    print("  S&P 500 (price only)           %+8.2f%%  cumulative" % (100 * sp_cum))
    print("  long leg / short leg           %+8.3f%% / %+8.3f%%  per month"
          % (100 * m["long_leg"].mean(), 100 * m["short_leg"].mean()))
    print("  best month  %s  %+7.2f%%" % (m.loc[m["total"].idxmax(), "target_month"],
                                          100 * m["total"].max()))
    print("  worst month %s  %+7.2f%%" % (m.loc[m["total"].idxmin(), "target_month"],
                                          100 * m["total"].min()))

    print("\nRISK-ADJUSTED   <- the headline is the information ratio")
    print("  INFORMATION RATIO vs cash+4%%   %+8.2f" % ir)
    print("  Sharpe ratio (over cash)       %+8.2f" % sharpe)
    print("  annualised alpha vs S&P 500    %+8.2f%%   t=%+.2f"
          % (100 * alpha_m * 12, reg.tvalues["Intercept"]))
    print("  BETA vs S&P 500                %+8.3f   se=%.3f   <- neutrality evidence"
          % (beta, reg.bse["sp500_excess"]))
    print("  correlation with S&P 500       %+8.2f" % m["excess_over_cash"].corr(m["sp500_ret"]))
    print("  hit rate (months beating hurdle) %6.1f%%" % (100 * (m["active"] > 0).mean()))
    print("  maximum drawdown               %+8.2f%%" % (100 * dd.min()))

    print("\nEXPOSURE AND IMPLEMENTATION")
    print("  names per month                %8.0f" % m["n"].mean())
    print("  gross exposure                 %8.0f%%  (max %.0f%%)"
          % (100 * m["gross"].mean(), 100 * m["gross"].max()))
    print("  net exposure                   %+8.1f%%  (range %+.1f%% .. %+.1f%%)"
          % (100 * m["net"].mean(), 100 * m["net"].min(), 100 * m["net"].max()))
    print("  largest single position        %8.2f%%" % (100 * m["max_abs_w"].max()))
    print("  monthly turnover               %8.1f%%  (range %.0f%% .. %.0f%%)"
          % (100 * to.mean(), 100 * to.min(), 100 * to.max()))
    print("  positions with no return data  %8d  of %s   (marked at %+.0f%%; "
          "sensitivity in deck_pack.csv)"
          % (int(m["n_missing_ret"].sum()), format(len(h), ","),
             100 * C.TEAM["delisting_return"]))

    print("\nBY CALENDAR YEAR")
    m["year"] = m["target_month"].str[:4]
    yr = m.groupby("year").apply(
        lambda d: pd.Series({
            "strategy": 100 * ((1 + d["total"]).prod() - 1),
            "hurdle": 100 * ((1 + d["hurdle"]).prod() - 1),
            "sp500": 100 * ((1 + d["sp500_ret"]).prod() - 1),
        }), include_groups=False)
    print(yr.round(2).to_string())

    RETURNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    m[["target_month", "total", "hurdle", "active", "spread",
       "long_leg", "short_leg", "sp500_ret", "cash_monthly"]].to_csv(RETURNS_CSV, index=False)
    print("\nwrote %s" % RETURNS_CSV.relative_to(C.ROOT))
    return m


if __name__ == "__main__":
    evaluate()

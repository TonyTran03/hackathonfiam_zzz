"""Stage 5b -- is the result real, or did we get lucky?

Six tests, in rough order of how often they kill a strategy:

  subperiods        does it work in every regime, or only in 2022?
  trading costs     at what cost per trade does the edge disappear?
  drop the best     remove the biggest winners; is anything left?
  factor attribution is the "alpha" just momentum and size in disguise?
  rolling beta      neutral throughout, or only on average?
  short book        could the short leg actually be borrowed?

None of these is optional. The rules ask for most of them by name, and a
strategy that passes only the headline number is the kind that unwinds.
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

HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
OUT_CSV = C.ROOT / "05_submission" / "robustness.csv"

# Collected as we go so the deck reads these rather than having them typed in.
_rows = []


RETURNS = C.ROOT / "05_submission" / "portfolio_returns.csv"
PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12

REGIMES = [
    ("2021 rebound",        "2021-01", "2021-12"),
    ("2022 drawdown",       "2022-01", "2022-12"),
    ("2023-25 concentration", "2023-01", "2025-12"),
    ("2026 so far",         "2026-01", "2026-08"),
]


def rec(section, metric, value, note=""):
    _rows.append({"section": section, "metric": metric, "value": value, "note": note})


def ir(active):
    return np.sqrt(12) * active.mean() / active.std(ddof=1)


def traded_notional(h):
    """Fraction of capital traded each month, from the change in weights."""
    piv = h.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    return piv.diff().abs().sum(axis=1).iloc[1:]


def subperiods(m):
    print("\n=== 1. SUBPERIODS -- does it work in every regime? ===")
    print("  %-24s %7s %9s %9s %8s" % ("", "months", "return", "vs hurdle", "IR"))
    for label, lo, hi in REGIMES:
        d = m[(m["target_month"] >= lo) & (m["target_month"] <= hi)]
        if len(d) < 6:
            continue
        cum = (1 + d["total"]).prod() - 1
        hur = (1 + d["hurdle"]).prod() - 1
        print("  %-24s %7d %+8.1f%% %+9.1f%% %+8.2f"
              % (label, len(d), 100 * cum, 100 * (cum - hur), ir(d["active"])))
        rec("subperiod", label, "%+.2f" % ir(d["active"]),
            "%d months, %+.1f%% vs hurdle" % (len(d), 100 * (cum - hur)))
    half = len(m) // 2
    for label, d in [("first half", m.iloc[:half]), ("second half", m.iloc[half:])]:
        print("  %-24s %7d %+8.1f%% %+9.1f%% %+8.2f"
              % (label, len(d), 100 * ((1 + d["total"]).prod() - 1),
                 100 * ((1 + d["total"]).prod() - (1 + d["hurdle"]).prod()),
                 ir(d["active"])))
        rec("subperiod", label, "%+.2f" % ir(d["active"]), "%d months" % len(d))


def costs(m, h):
    print("\n=== 2. TRADING COSTS -- where does the edge break even? ===")
    notional = traded_notional(h).reindex(m["target_month"]).fillna(0.0).values
    print("  average notional traded per month: %.0f%% of capital" % (100 * notional.mean()))
    print("  %-14s %10s %10s %8s" % ("cost per trade", "ann. return", "vs hurdle", "IR"))
    for bps in [0, 5, 10, 20, 30, 50, 100]:
        net = m["total"].values - notional * bps / 10000
        active = net - m["hurdle"].values
        cum = (1 + pd.Series(net)).prod() - 1
        ann = (1 + cum) ** (12 / len(m)) - 1
        print("  %-14s %+9.2f%% %+10.2f%% %+8.2f"
              % ("%d bps" % bps, 100 * ann,
                 100 * (cum - ((1 + m["hurdle"]).prod() - 1)), ir(pd.Series(active))))
    # break-even: the cost at which the information ratio hits zero
    lo, hi = 0.0, 500.0
    for _ in range(40):
        mid = (lo + hi) / 2
        a = m["total"].values - notional * mid / 10000 - m["hurdle"].values
        if a.mean() > 0:
            lo = mid
        else:
            hi = mid
    print("  break-even cost: %.0f bps per trade -- above this the strategy "
          "stops clearing the hurdle" % lo)
    rec("costs", "break-even cost", "%.0f bps" % lo, "per trade")


def drop_the_best(m, h):
    print("\n=== 3. DROP THE BEST -- is it a strategy or a lottery ticket? ===")
    base = ir(m["active"])
    print("  all months                          IR %+.2f" % base)
    rec("stress", "all months", "%+.2f" % base)
    for k in [1, 3, 5]:
        d = m.drop(m["active"].nlargest(k).index)
        print("  minus the %d best months            IR %+.2f" % (k, ir(d["active"])))
        rec("stress", "minus the %d best months" % k, "%+.2f" % ir(d["active"]))

    hh = h.copy()
    hh["pnl"] = hh["weight"] * hh[C.TARGET].fillna(0.0)
    by_stock = hh.groupby("permno")["pnl"].sum().nlargest(20)
    for k in [5, 10, 20]:
        drop = set(by_stock.index[:k])
        kept = hh[~hh["permno"].isin(drop)]
        spread = kept.groupby("target_month")["pnl"].sum()
        d = m.set_index("target_month")
        act = (d["cash_monthly"] + spread - d["hurdle"]).dropna()
        print("  minus the %2d best stocks           IR %+.2f" % (k, ir(act)))
        rec("stress", "minus the %d best stocks" % k, "%+.2f" % ir(act))
    top = hh.groupby(["permno", "ticker"])["pnl"].sum().nlargest(5)
    print("  biggest contributors: %s"
          % ", ".join("%s %+.1f%%" % (t if isinstance(t, str) else p, 100 * v)
                      for (p, t), v in top.items()))


def factor_attribution(m):
    print("\n=== 4. FACTOR ATTRIBUTION -- is the alpha already known? ===")
    with zipfile.ZipFile(C.FF3_ZIP) as z:
        raw = z.read(z.namelist()[0]).decode("latin-1")
    rows = [l for l in raw.splitlines() if len(l) > 7 and l[:6].isdigit() and l[6] == ","]
    ff = pd.read_csv(io.StringIO("\n".join(rows)), header=None,
                     names=["ym", "mkt_rf", "smb", "hml", "rf"])
    ff = ff[ff["ym"].astype(str).str.len() == 6]
    ff["target_month"] = pd.PeriodIndex(ff["ym"].astype(str), freq="M").astype(str)
    for c in ["mkt_rf", "smb", "hml", "rf"]:
        ff[c] = pd.to_numeric(ff[c], errors="coerce") / 100

    d = m.merge(ff[["target_month", "mkt_rf", "smb", "hml"]], on="target_month", how="inner")
    d = d.dropna(subset=["mkt_rf", "smb", "hml"])
    print("  %d months overlap with the factor file (it ends one month early)" % len(d))
    for label, formula in [("market only", "excess_over_cash ~ mkt_rf"),
                           ("market + size + value", "excess_over_cash ~ mkt_rf + smb + hml")]:
        r = smf.ols(formula, data=d).fit(cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True)
        print("  %-22s annualised alpha %+6.2f%%  t=%+.2f   R2 %.2f"
              % (label, 100 * 12 * r.params["Intercept"], r.tvalues["Intercept"], r.rsquared))
        rec("attribution", label, "%+.2f%%" % (100 * 12 * r.params["Intercept"]),
            "t=%+.2f, R2 %.2f" % (r.tvalues["Intercept"], r.rsquared))
        loads = "  ".join("%s %+.2f (t %+.1f)" % (k, r.params[k], r.tvalues[k])
                          for k in r.params.index if k != "Intercept")
        print("      %s" % loads)


def rolling(m):
    print("\n=== 5. ROLLING -- neutral throughout, or only on average? ===")
    w = 12
    betas, irs = [], []
    for i in range(w, len(m) + 1):
        d = m.iloc[i - w:i]
        r = smf.ols("excess_over_cash ~ sp500_excess", data=d).fit()
        betas.append(r.params["sp500_excess"])
        irs.append(ir(d["active"]))
    betas, irs = pd.Series(betas), pd.Series(irs)
    print("  rolling 12-month beta   mean %+.2f   range %+.2f .. %+.2f   "
          "outside +/-0.3 in %.0f%% of windows"
          % (betas.mean(), betas.min(), betas.max(), 100 * (betas.abs() > 0.3).mean()))
    rec("rolling", "12-month beta", "%+.2f" % betas.mean(),
        "range %+.2f..%+.2f, outside +/-0.3 in %.0f%% of windows"
        % (betas.min(), betas.max(), 100 * (betas.abs() > 0.3).mean()))
    print("  rolling 12-month IR     mean %+.2f   range %+.2f .. %+.2f   "
          "negative in %.0f%% of windows"
          % (irs.mean(), irs.min(), irs.max(), 100 * (irs < 0).mean()))


def short_book(h):
    print("\n=== 6. SHORT BOOK -- could it actually be borrowed? ===")
    L, S = h[h["weight"] > 0], h[h["weight"] < 0]
    print("  %-26s %12s %12s" % ("", "long", "short"))
    print("  %-26s %11.0f %12.0f" % ("median market cap ($m)", L["me"].median(), S["me"].median()))
    print("  %-26s %11.2f %12.2f" % ("median price ($)", L["prc"].median(), S["prc"].median()))
    for grp in ["nano", "micro", "small", "large", "mega"]:
        print("  %-26s %10.1f%% %11.1f%%"
              % ("share in %s caps" % grp,
                 100 * (L["size_grp"] == grp).mean(), 100 * (S["size_grp"] == grp).mean()))


def main():
    m = pd.read_csv(RETURNS)
    m["excess_over_cash"] = m["spread"]
    m["sp500_excess"] = m["sp500_ret"] - m["cash_monthly"]
    h = pd.read_parquet(HOLDINGS)

    print("=" * 70)
    print("ROBUSTNESS  %s .. %s  (%d months)"
          % (m["target_month"].iloc[0], m["target_month"].iloc[-1], len(m)))
    print("=" * 70)
    subperiods(m)
    costs(m, h)
    drop_the_best(m, h)
    factor_attribution(m)
    rolling(m)
    short_book(h)
    pd.DataFrame(_rows).to_csv(OUT_CSV, index=False)
    print("")
    print("wrote %s" % OUT_CSV.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

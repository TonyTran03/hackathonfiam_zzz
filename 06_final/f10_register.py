"""Final stage 10 -- the run register and the holdings files.

    python 06_final/f10_register.py

run_register.csv   every engine run that exists, adopted or not, with how it
                   came to be run (pre-registered, design-only, post-hoc). This
                   is the denominator Section 5.2 asks for.
holdings_*.csv     the headline book: weights after trading on every day the
                   book changed (each rebalancing date), and the end-of-day
                   book on every trading day for the Arcana upload.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402

HEADLINE = "test_M"

ORIGIN = {
    "design_M": "design window, D1 candidate (chosen)",
    "design_W": "design window, D1 candidate",
    "design_D": "design window, D1 candidate",
    "design_M_rule": "design window, risk-layer smoke test",
    "design_B": "design window, post-hoc check of B",
    "test_M": "PRE-REGISTERED HEADLINE (D1 = monthly, D2 = no overlay)",
    "test_W": "pre-registered register entry",
    "test_D": "pre-registered register entry",
    "test_M_E": "pre-registered register entry (overlay rejected by D2)",
    "test_M_rule": "pre-registered register entry (fixed-rule risk layer)",
    "test_M_nav250m": "pre-registered capacity check",
    "test_M_nav4000m": "pre-registered capacity check",
    "test_B": "POST-HOC: run after seeing the alpha-decay result on the test window",
    "test_Q": "POST-HOC: run after seeing the alpha-decay result on the test window",
}


def stats(d):
    a_g = d["ret_gross"] - d["hurdle"]
    a_n = d["ret"] - d["hurdle"]
    y = (d["ret_gross"] - d["rf"]).values
    x = d["mkt_ex"].values
    X = np.column_stack([np.ones(len(y)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0][1]
    m = d.groupby("month").agg(r=("ret_gross", lambda s: np.prod(1 + s) - 1),
                               rf=("rf", lambda s: np.prod(1 + s) - 1),
                               sp=("sp_ret", lambda s: np.prod(1 + s) - 1))
    bm = np.polyfit((m["sp"] - m["rf"]).values, (m["r"] - m["rf"]).values, 1)[0]
    yrs = len(d) / 252
    nav0 = d["nav"].iloc[0] / (1 + d["ret"].iloc[0])
    return {
        "ir_before_costs": np.sqrt(252) * a_g.mean() / a_g.std(),
        "ir_net_all_costs": np.sqrt(252) * a_n.mean() / a_n.std(),
        "beta_daily": b, "beta_monthly": bm,
        "cagr_net_pct": 100 * ((d["nav"].iloc[-1] / nav0) ** (1 / yrs) - 1),
        "ending_nav_usd_bn": d["nav"].iloc[-1] / 1e9,
        "trading_cost_pct_nav_yr": 100 * d["cost"].sum() / d["nav"].mean() / yrs,
        "borrow_pct_nav_yr": 100 * d["borrow"].sum() / d["nav"].mean() / yrs,
        "turnover_pct_yr": 100 * d["turnover"].sum() / yrs,
        "max_dd_pct": 100 * (d["nav"] / d["nav"].cummax() - 1).min(),
    }


def register():
    rows = []
    for rd in sorted((F.DATA / "runs").iterdir()):
        d = pd.read_parquet(rd / "daily.parquet")
        tag = rd.name
        origin = ORIGIN.get(tag)
        if origin is None:
            origin = ("pre-registered cost / borrow sensitivity" if "cost-" in tag
                      and not tag.startswith(("test_B", "test_Q"))
                      else "post-hoc cost sensitivity of a post-hoc variant" if "cost-" in tag
                      else "other")
        rows.append({"run": tag, "window": tag.split("_")[0], "origin": origin, **stats(d)})
    r = pd.DataFrame(rows)
    F.OUT.mkdir(parents=True, exist_ok=True)
    r.to_csv(F.OUT / "run_register.csv", index=False)
    pd.set_option("display.width", 220)
    print(r.round(3).to_string(index=False))
    return r


def holdings(tag=HEADLINE):
    rd = F.DATA / "runs" / tag
    d = pd.read_parquet(rd / "daily.parquet")
    p = pd.read_parquet(rd / "pnl.parquet")
    sig = pd.read_parquet(F.DATA / "signal_test.parquet")
    names = (sig.sort_values("target_month")
                .drop_duplicates("permno", keep="last")
                .set_index("permno")[["ticker", "company_name"]])
    # a position earning on day k+1 is the book held after the close of day k
    p = p.copy()
    p["book_date"] = d["date"].values[(p["di"] - 1).clip(lower=0).astype(int)]
    p = p[p["di"] >= 1]
    navs = d.set_index("date")["nav"]
    # x in the pnl file is the position at the OPEN of day di, i.e. after the
    # close of di-1, so dividing by that close's NAV gives the weight held
    p["weight"] = p["x"] / navs.reindex(p["book_date"]).values
    p = p.join(names, on="permno")
    out = p[["book_date", "permno", "ticker", "company_name", "weight"]].rename(
        columns={"book_date": "date"}).sort_values(["date", "weight"], ascending=[True, False])
    out.to_csv(F.OUT / "holdings_daily_end_of_day.csv", index=False)
    reb_days = set(d.loc[d["turnover"] > 0, "date"])
    out[out["date"].isin(reb_days)].to_csv(F.OUT / "holdings_rebalance_dates.csv", index=False)
    print("holdings: %d end-of-day rows over %d days; %d rebalancing dates"
          % (len(out), out["date"].nunique(), len(reb_days)))


if __name__ == "__main__":
    register()
    holdings()

"""Leakage assertions for the daily engine (Section 8.1.3): one per data join.

    python 06_final/f08_leakage_tests.py <run_tag>

Each test reads a finished run and fails loudly if the timing convention was
broken anywhere in it. They are cheap, and they are the ones that catch the
leaks Section 7 says are most likely this year.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
import f02_signal as S  # noqa: E402


def check(run_tag):
    rd = F.DATA / "runs" / run_tag
    d = pd.read_parquet(rd / "daily.parquet")
    pnl = pd.read_parquet(rd / "pnl.parquet")
    trades = pd.read_parquet(rd / "trades.parquet")
    window = "design" if run_tag.startswith("design") else "test"
    sig = pd.read_parquet(F.DATA / ("signal_%s.parquet" % window))
    cal = pd.read_parquet(F.DATA / "calendar.parquet")
    failures = []

    def ok(cond, msg):
        print(("PASS  " if cond else "FAIL  ") + msg)
        if not cond:
            failures.append(msg)

    # 1 characteristics -> formation: every name traded on a formation day
    #   comes from a panel row dated at the PREVIOUS month end, strictly
    #   before the trade date
    form = trades[trades["reason"].str.startswith("formation")].copy()
    form["month"] = form["date"].dt.to_period("M").astype(str)
    j = form.merge(sig[["permno", "target_month", "eom"]], left_on=["permno", "month"],
                   right_on=["permno", "target_month"], how="left")
    entering = j[j["eom"].notna()]
    ok((entering["eom"] < entering["date"]).all(),
       "characteristics dated strictly before the formation trade (%d trades)" % len(entering))
    ok(((pd.PeriodIndex(entering["date"], freq="M") - pd.PeriodIndex(entering["eom"], freq="M"))
        .map(lambda x: x.n) == 1).all(),
       "characteristics are from exactly the previous month end")

    # 2 formation day is the FIRST trading day of the month
    fd = cal[cal["is_formation"]]["date"]
    ok(form["date"].isin(set(fd)).all(), "formation trades happen only on first trading days")

    # 3 first return: a name bought at the close of day t first earns on t+1
    di_of = {dt: i for i, dt in enumerate(d["date"])}
    p = pnl.sort_values(["permno", "di"])
    first = p.groupby("permno")["di"].min()
    tr_first = trades.groupby("permno")["date"].min().map(di_of)
    both = pd.concat([first.rename("first_pnl"), tr_first.rename("first_trade")], axis=1).dropna()
    ok((both["first_pnl"] > both["first_trade"]).all(),
       "no position earns the return of the day it was traded (%d names)" % len(both))

    # 4 the realised return is not visible to selection
    ok("stub_ret" not in S.select_inputs(sig.head(5)).columns,
       "selection inputs exclude the realised monthly return")

    # 5 daily benchmark follows Section 9.2 exactly
    dd = d.merge(cal[["date", "tb3ms"]], on="date")
    ok(np.allclose(dd["hurdle"], dd["tb3ms"] / 25200 + 0.04 / 252),
       "daily hurdle = TB3MS/25200 + 0.04/252")

    # 6 mandate, every day
    n = d["n_long"] + d["n_short"]
    live = d.index >= d.index[d["n_long"] > 0][0] + 1 if (d["n_long"] > 0).any() else d.index
    ok((n[live] >= 200).all() and (n[live] <= 500).all(), "200-500 names every day after inception")
    ok((d["gross"] <= 2.0 + 1e-9).all(), "gross <= 200% at every close")
    ok((d["net"].abs() <= 0.5 + 1e-9).all(), "net within +/-50% at every close")
    ok((d["max_w"] <= 0.05 + 1e-9).all(), "no position above 5% of capital at any close")

    # 7 short floor at formation (shares x formation-day close)
    sh = j[j["delta"] < 0].merge(sig[["permno", "target_month", "shares"]],
                                 on=["permno", "target_month"], how="left")
    dsf = pd.read_parquet(F.DSF_PARQUET, columns=["permno", "date", "prc"])
    sh = sh.merge(dsf, on=["permno", "date"], how="left")
    # a short sale at formation either opens/extends a short or trims a long;
    # check the names that END the day short
    shorts_after = set()
    for dt in form["date"].unique():
        k = di_of[dt]
        shorts_after |= {(dt, pm) for pm in pnl.loc[(pnl["di"] == k + 1) & (pnl["x"] < 0), "permno"]}
    sh["is_short_after"] = [(a, b) in shorts_after for a, b in zip(sh["date"], sh["permno"])]
    s2 = sh[sh["is_short_after"]]
    me = s2["shares"] * s2["prc"].abs()
    ok((me >= F.FINAL["short_min_me_musd"]).all(),
       "every short formed has market cap >= $500m on its formation day (%d checked, min $%.0fm)"
       % (len(s2), me.min()))

    print("\n%d failure(s)" % len(failures))
    return failures


if __name__ == "__main__":
    sys.exit(1 if check(sys.argv[1]) else 0)

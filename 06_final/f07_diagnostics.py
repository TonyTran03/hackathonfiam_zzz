"""Final stage 7 -- the questions the judges will ask through Arcana, answered first.

    python 06_final/f07_diagnostics.py <run_tag> [<label>]
    python 06_final/f07_diagnostics.py --survivorship     # the Section 6.3 test on the 8-K corpus

Section 11 lists what the economic review looks at. Each function below
answers one of them from our own files, so nothing on Arcana is a surprise:

  factor_attribution   factor vs idiosyncratic return (monthly FF3, and daily
                       market/size/value/momentum built from the panel)
  sizing_vs_selection  did we make money picking names or sizing them?
  hit_rate             share of winning positions vs the win/loss ratio
  alpha_decay          how fast the signal's edge fades after formation
  earnings_split       P&L inside earnings windows vs outside them
  stress               the book in named episodes, inside and outside sample
  survivorship_8k      does the supplied 8-K corpus cover firms that left?

Everything is descriptive of a finished run; none of it feeds back into the book.
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
from common import config as C  # noqa: E402


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X))
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    s2 = res @ res / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return coef, se, 1 - res.var() / y.var(), res


# ------------------------------------------------------------ factors
def ff3_monthly():
    raw = zipfile.ZipFile(C.FF3_ZIP).read("F-F_Research_Data_Factors.csv").decode("latin-1")
    lines = raw.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith(",Mkt-RF"))
    rows = []
    for l in lines[start + 1:]:
        p = [x.strip() for x in l.split(",")]
        if len(p) < 5 or not p[0].isdigit() or len(p[0]) != 6:
            break
        rows.append(p)
    f = pd.DataFrame(rows, columns=["ym", "mkt_rf", "smb", "hml", "rf"])
    f["month"] = f["ym"].str[:4] + "-" + f["ym"].str[4:]
    for c in ["mkt_rf", "smb", "hml", "rf"]:
        f[c] = f[c].astype(float) / 100
    return f.set_index("month")


def daily_factors(start, end):
    """Market-cap-weighted 2x3 sorts on size and on value / momentum, formed
    each month from the previous month-end panel, held for the month."""
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "target_month", "me", "be_me",
                                                    "ret_12_1", "size_grp", "prc"])
    panel = panel[(panel["target_month"] >= start[:7]) & (panel["target_month"] <= end[:7])
                  & ~panel["size_grp"].isin(["nano"]) & (panel["prc"].abs() >= 1)]
    dsf = pd.read_parquet(F.DSF_PARQUET, columns=["permno", "date", "daily_return"])
    dsf = dsf[(dsf["date"] >= start) & (dsf["date"] <= end)]
    dsf["target_month"] = dsf["date"].dt.to_period("M").astype(str)
    out = []
    for m, g in panel.groupby("target_month"):
        g = g.copy()
        big = g["me"] >= g["me"].median()
        legs = {}
        for name, col in [("hml", "be_me"), ("umd", "ret_12_1")]:
            v = g[col]
            lo, hi = v.quantile(0.3), v.quantile(0.7)
            hi_set = g.index[v >= hi]; lo_set = g.index[v <= lo]
            legs[name] = (hi_set, lo_set)
        dm = dsf[dsf["target_month"] == m].merge(g[["permno", "me"]], on="permno")
        dm = dm.dropna(subset=["daily_return"])

        def vw(perms):
            x = dm[dm["permno"].isin(perms)]
            return x.groupby("date").apply(lambda s: np.average(s["daily_return"], weights=s["me"]),
                                          include_groups=False)
        res = {}
        res["smb"] = vw(g.loc[~big, "permno"]) - vw(g.loc[big, "permno"])
        for name, (hs, ls) in legs.items():
            res[name] = 0.5 * (vw(g.loc[hs.intersection(g.index[~big]), "permno"])
                               + vw(g.loc[hs.intersection(g.index[big]), "permno"])) \
                - 0.5 * (vw(g.loc[ls.intersection(g.index[~big]), "permno"])
                         + vw(g.loc[ls.intersection(g.index[big]), "permno"]))
        out.append(pd.DataFrame(res))
    return pd.concat(out).sort_index()


def factor_attribution(d, m):
    rows = []
    ff = ff3_monthly()
    mm = m.join(ff, how="inner")
    y = (mm["ret_gross"] - mm["rf_y"] if "rf_y" in mm else mm["ret_gross"] - mm["rf"]).values
    for name, cols in [("monthly: market only", ["mkt_rf"]),
                       ("monthly: FF3", ["mkt_rf", "smb", "hml"])]:
        c, s, r2, _ = ols(y, [mm[k].values for k in cols])
        rows.append({"model": name, "n": len(y), "alpha_ann_pct": 1200 * c[0],
                     "alpha_t": c[0] / s[0], "r2": r2,
                     **{"beta_" + k: c[i + 1] for i, k in enumerate(cols)},
                     **{"t_" + k: c[i + 1] / s[i + 1] for i, k in enumerate(cols)}})
    fac = daily_factors(str(d["date"].iloc[0].date()), str(d["date"].iloc[-1].date()))
    dd = d.set_index("date").join(fac, how="inner")
    y = (dd["ret_gross"] - dd["rf"]).values
    cols = ["mkt_ex", "smb", "hml", "umd"]
    X = [dd[k].values for k in cols]
    c, s, r2, res = ols(y, X)
    factor_part = sum(c[i + 1] * dd[k].mean() for i, k in enumerate(cols))
    rows.append({"model": "daily: market, size, value, momentum (panel-built)", "n": len(y),
                 "alpha_ann_pct": 25200 * c[0], "alpha_t": c[0] / s[0], "r2": r2,
                 **{"beta_" + k: c[i + 1] for i, k in enumerate(cols)},
                 **{"t_" + k: c[i + 1] / s[i + 1] for i, k in enumerate(cols)},
                 "factor_share_of_mean_excess_return": factor_part / y.mean(),
                 "idiosyncratic_share_of_variance": 1 - r2})
    # how the factor loadings move year by year (drift, Section 11 point 2)
    yr = []
    for year, g in dd.groupby(dd.index.year):
        cc, ss, rr, _ = ols((g["ret_gross"] - g["rf"]).values, [g[k].values for k in cols])
        yr.append({"year": year, **{k: cc[i + 1] for i, k in enumerate(cols)},
                   **{"t_" + k: cc[i + 1] / ss[i + 1] for i, k in enumerate(cols)}, "r2": rr})
    return pd.DataFrame(rows), pd.DataFrame(yr)


# ------------------------------------------------------------ sizing / selection
def sizing_vs_selection(d, pnl, sig):
    """Actual P&L vs the same names at equal weight inside each leg, same
    leg notionals; and each leg against its eligible universe (EW)."""
    p = pnl.copy()
    p["side"] = np.sign(p["x"])
    g = p.groupby(["di", "side"])
    leg = g.agg(notional=("x", lambda v: np.abs(v).sum()), n=("x", "size"),
                pnl=("pnl", "sum"), mean_r=("r", "mean")).reset_index()
    leg["ew_pnl"] = leg["side"] * leg["notional"] * leg["mean_r"]
    nav_prev = d["nav"].shift(1).fillna(F.FINAL["start_nav"]).values
    leg["nav"] = nav_prev[leg["di"].astype(int)]
    agg = leg.groupby("side").apply(lambda x: pd.Series({
        "actual_pct_per_yr": 252 * (x["pnl"] / x["nav"]).sum() / len(d) * 100,
        "equal_weight_pct_per_yr": 252 * (x["ew_pnl"] / x["nav"]).sum() / len(d) * 100}),
        include_groups=False)
    agg["sizing_pct_per_yr"] = agg["actual_pct_per_yr"] - agg["equal_weight_pct_per_yr"]
    agg.index = agg.index.map({1.0: "long", -1.0: "short"})
    tot = agg.sum().rename("book")
    out = pd.concat([agg, tot.to_frame().T])
    # leg vs the universe it was picked from, before costs (selection skill)
    dsf = pd.read_parquet(F.DSF_PARQUET, columns=["permno", "date", "daily_return"])
    days = d[["date"]].assign(di=np.arange(len(d)), month=d["month"])
    univ = sig[["permno", "target_month", "short_ok_eom"]]
    dsf = dsf[dsf["date"].isin(days["date"])].merge(days, on="date")
    dsf = dsf.merge(univ, left_on=["permno", "month"], right_on=["permno", "target_month"])
    u_all = dsf.groupby("di")["daily_return"].mean()
    u_short = dsf[dsf["short_ok_eom"]].groupby("di")["daily_return"].mean()
    lr = leg.set_index(["di", "side"])["mean_r"].unstack()
    sel = pd.DataFrame({
        "long_minus_universe": lr[1.0] - u_all.reindex(lr.index),
        "short_names_minus_short_universe": lr[-1.0] - u_short.reindex(lr.index)})
    sel["year"] = d["date"].dt.year.values[sel.index.astype(int)]
    by_year = sel.groupby("year").agg(lambda s: 252 * s.mean() * 100)
    tstat = sel.drop(columns="year").apply(lambda s: s.mean() / s.std() * np.sqrt(len(s.dropna())))
    by_year.loc["t (full period)"] = tstat.values
    return out, by_year


def hit_rate(pnl, d):
    p = pnl[["di", "permno", "x", "pnl"]].copy()
    p["side"] = np.sign(p["x"])
    p = p.sort_values(["permno", "di"])
    brk = (p["permno"].ne(p["permno"].shift()) | p["di"].ne(p["di"].shift() + 1)
           | p["side"].ne(p["side"].shift()))
    p["run"] = brk.cumsum()
    ep = p.groupby("run").agg(side=("side", "first"), pnl=("pnl", "sum"), days=("di", "size"))
    rows = []
    for name, g in [("all positions", ep), ("long", ep[ep["side"] > 0]), ("short", ep[ep["side"] < 0])]:
        w, l = g.loc[g["pnl"] > 0, "pnl"], g.loc[g["pnl"] <= 0, "pnl"]
        rows.append({"set": name, "episodes": len(g), "hit_rate": len(w) / len(g),
                     "avg_win_usd_m": w.mean() / 1e6, "avg_loss_usd_m": l.mean() / 1e6,
                     "win_loss_ratio": w.mean() / abs(l.mean()), "median_days_held": g["days"].median()})
    act = d["ret"] - d["hurdle"]
    rows.append({"set": "book days beating the hurdle", "episodes": len(d),
                 "hit_rate": (act > 0).mean(),
                 "win_loss_ratio": act[act > 0].mean() / abs(act[act <= 0].mean())})
    m = d.groupby("month").agg(r=("ret", lambda s: np.prod(1 + s) - 1), h=("hurdle", lambda s: np.prod(1 + s) - 1))
    a = m["r"] - m["h"]
    rows.append({"set": "book months beating the hurdle", "episodes": len(m),
                 "hit_rate": (a > 0).mean(), "win_loss_ratio": a[a > 0].mean() / abs(a[a <= 0].mean())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------ decay
def alpha_decay(sig, window_start, window_end):
    """Rank IC of the formation-day score with forward returns, by horizon
    and by delay. Day 1 = the first return a book formed at the close of the
    formation day can earn."""
    cal = pd.read_parquet(F.DATA / "calendar.parquet")
    cal = cal[(cal["date"] >= window_start)].reset_index(drop=True)
    dsf = pd.read_parquet(F.DSF_PARQUET, columns=["permno", "date", "daily_return"])
    dsf = dsf[(dsf["date"] >= window_start)]
    R = dsf.pivot(index="date", columns="permno", values="daily_return").reindex(cal["date"])
    horizons = [1, 2, 3, 5, 10, 21, 42, 63]
    delays = [0, 5, 10, 15, 21, 42]
    rows = []
    for m, g in sig.groupby("target_month"):
        fidx = cal.index[(cal["month"].astype(str) == m) & cal["is_formation"]]
        if not len(fidx):
            continue
        f0 = fidx[0] + 1
        perms = [p for p in g["permno"] if p in R.columns]
        sc = g.set_index("permno").loc[perms, "score"]
        lr = np.log1p(R[perms].fillna(0.0).values)
        for h in horizons:
            if f0 + h > len(cal):
                continue
            cr = lr[f0:f0 + h].sum(0)
            rows.append({"month": m, "kind": "horizon", "k": h,
                         "ic": pd.Series(cr, index=perms).corr(sc, method="spearman")})
        for j in delays:
            if f0 + j + 21 > len(cal):
                continue
            cr = lr[f0 + j:f0 + j + 21].sum(0)
            rows.append({"month": m, "kind": "delay (21-day return starting k days late)", "k": j,
                         "ic": pd.Series(cr, index=perms).corr(sc, method="spearman")})
    df = pd.DataFrame(rows)
    s = df.groupby(["kind", "k"])["ic"].agg(["mean", "std", "count"])
    s["t"] = s["mean"] / (s["std"] / np.sqrt(s["count"]))
    return s.reset_index()


# ------------------------------------------------------------ earnings
def earnings_split(pnl, d):
    f = pq.read_table(C.FILINGS_PARQUET, columns=["permno", "filing_date", "items"]).to_pandas()
    f = f[[i is not None and "2.02" in list(i) for i in f["items"]]]
    f["filing_date"] = pd.to_datetime(f["filing_date"]).dt.normalize()
    days = d["date"].reset_index(drop=True)
    pos = days.searchsorted(f["filing_date"])
    win = set()
    for p_, k in zip(f["permno"].values, pos):
        for j in (-1, 0, 1, 2):             # filed after the close reacts next day
            if 0 <= k + j < len(days):
                win.add((int(p_), int(k + j)))
    p = pnl[["di", "permno", "pnl", "x"]].copy()
    p["earn"] = [(int(a), int(b)) in win for a, b in zip(p["permno"], p["di"])]
    rows = []
    for flag, g in p.groupby("earn"):
        rows.append({"window": "earnings (-1..+2 days of an item 2.02 8-K)" if flag else "ex-earnings",
                     "share_of_position_days": len(g) / len(p),
                     "share_of_gross_exposure": g["x"].abs().sum() / p["x"].abs().sum(),
                     "pnl_usd_m": g["pnl"].sum() / 1e6,
                     "share_of_pnl": g["pnl"].sum() / p["pnl"].sum()})
    return pd.DataFrame(rows)


# ------------------------------------------------------------ stress
EPISODES = [
    ("2021-01-25", "2021-02-05", "meme-stock short squeeze"),
    ("2021-11-08", "2021-12-31", "speculative-growth unwind begins"),
    ("2022-01-03", "2022-06-16", "2022 rate shock drawdown"),
    ("2023-03-08", "2023-03-24", "regional bank failures (SVB)"),
    ("2023-05-01", "2023-07-31", "AI mega-cap concentration rally"),
    ("2024-07-10", "2024-08-09", "small-cap rotation and yen-carry unwind"),
    ("2025-04-01", "2025-04-30", "tariff shock"),
]


def stress(d):
    rows = []
    for a, b, name in EPISODES:
        g = d[(d["date"] >= a) & (d["date"] <= b)]
        if len(g) < 3:
            continue
        y, x = (g["ret"] - g["rf"]).values, g["mkt_ex"].values
        beta = np.polyfit(x, y, 1)[0]
        nav = np.cumprod(1 + g["ret"])
        rows.append({"episode": name, "from": a, "to": b, "days": len(g),
                     "strategy_pct": 100 * (nav.iloc[-1] - 1),
                     "active_vs_hurdle_pct": 100 * (nav.iloc[-1] / np.prod(1 + g["hurdle"]) - 1),
                     "sp500_pct": 100 * (np.prod(1 + g["sp_ret"]) - 1),
                     "max_dd_in_episode_pct": 100 * (nav / nav.cummax() - 1).min(),
                     "beta_in_episode": beta,
                     "long_leg_pct": 100 * (np.prod(1 + g["long_ret"]) - 1),
                     "shorted_names_pct": 100 * (np.prod(1 + g["short_ret"]) - 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------ survivorship
NAMED = ["SEARS", "BON-TON", "PIER 1", "GNC", "ASCENA", "PENNEY"]


def survivorship_8k():
    """Section 6.3 on the corpus we were given in round 1."""
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "eom", "company_name", "me",
                                                    C.TARGET, "size_grp", "prc"])
    panel["ym"] = pd.PeriodIndex(panel["eom"], freq="M")
    last = panel.groupby("permno")["ym"].max()
    exited = last[last < pd.Period("2026-07", "M")].index
    panel["exited"] = panel["permno"].isin(exited)
    f = pq.read_table(C.FILINGS_PARQUET, columns=["permno", "filing_date"]).to_pandas()
    f["ym"] = pd.to_datetime(f["filing_date"]).dt.to_period("M")
    cov = f.drop_duplicates(["permno", "ym"]).assign(covered=True)
    panel = panel.merge(cov[["permno", "ym", "covered"]], on=["permno", "ym"], how="left")
    panel["covered"] = panel["covered"].fillna(False).astype(bool)

    # 1 coverage by later-exit status, by year
    panel["year"] = panel["ym"].dt.year
    by_year = panel.groupby(["year", "exited"])["covered"].mean().unstack()
    by_year.columns = ["survivors_coverage", "later_exited_coverage"]
    # 2 coverage in a firm's final 12 months in the panel vs its earlier months
    panel["months_to_exit"] = (panel["permno"].map(last) - panel["ym"]).map(lambda x: x.n)
    ex = panel[panel["exited"]]
    final12 = ex[ex["months_to_exit"] < 12]["covered"].mean()
    earlier = ex[ex["months_to_exit"] >= 24]["covered"].mean()
    ever = panel.groupby("permno")["covered"].any()
    firm = pd.DataFrame({"exited": ever.index.isin(exited), "ever_covered": ever.values})
    firm_cov = firm.groupby("exited")["ever_covered"].mean()
    # 3 the complementary return test: covered vs uncovered, same month
    t = panel[(panel["prc"].abs() >= 5) & ~panel["size_grp"].isin(["nano", "micro"])].dropna(subset=[C.TARGET])
    diff = t.groupby("ym").apply(lambda g: g.loc[g["covered"], C.TARGET].mean()
                                 - g.loc[~g["covered"], C.TARGET].mean(), include_groups=False)
    ret_test = {"mean_monthly_diff_pct_covered_minus_uncovered": 100 * diff.mean(),
                "t": diff.mean() / diff.std() * np.sqrt(len(diff)), "months": len(diff)}
    # 4 the named firms the instructions suggest
    names = panel.dropna(subset=["company_name"])
    named = []
    for n in NAMED:
        hit = names[names["company_name"].str.upper().str.contains(n, regex=False)]
        perms = hit["permno"].unique()
        nf = f[f["permno"].isin(perms)]
        named.append({"name_search": n, "permnos_in_panel": len(perms),
                      "panel_months": len(hit), "filings_in_corpus": len(nf),
                      "last_panel_month": str(hit["ym"].max()) if len(hit) else "",
                      "last_filing": str(nf["filing_date"].max()) if len(nf) else ""})
    summary = pd.DataFrame([
        {"measure": "firms that later exit: share with ANY 8-K in corpus", "value": firm_cov.get(True)},
        {"measure": "surviving firms: share with ANY 8-K in corpus", "value": firm_cov.get(False)},
        {"measure": "exiting firms: monthly coverage in final 12 months", "value": final12},
        {"measure": "exiting firms: monthly coverage 24+ months before exit", "value": earlier},
        {"measure": "covered minus uncovered next-month return, %/month", "value": ret_test["mean_monthly_diff_pct_covered_minus_uncovered"]},
        {"measure": "  t-statistic (monthly)", "value": ret_test["t"]},
    ])
    out = F.OUT / "survivorship_8k"
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "summary.csv", index=False)
    by_year.to_csv(out / "coverage_by_year.csv")
    pd.DataFrame(named).to_csv(out / "named_delisted_firms.csv", index=False)
    print(summary.to_string(index=False)); print(by_year.round(3).to_string()); print(pd.DataFrame(named).to_string(index=False))
    return summary


def run(tag, label=None):
    label = label or tag
    rd = F.DATA / "runs" / tag
    out = F.OUT / label
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(rd / "daily.parquet")
    pnl = pd.read_parquet(rd / "pnl.parquet")
    window = "design" if tag.startswith("design") else "test"
    sig = pd.read_parquet(F.DATA / ("signal_%s.parquet" % window))
    m = d.groupby("month").agg(ret_gross=("ret_gross", lambda s: np.prod(1 + s) - 1),
                               rf_m=("rf", lambda s: np.prod(1 + s) - 1))
    m = m.rename(columns={"rf_m": "rf_y"})
    fa, fy = factor_attribution(d, m)
    fa.to_csv(out / "factor_attribution.csv", index=False)
    fy.to_csv(out / "factor_loadings_by_year.csv", index=False)
    ss, sel = sizing_vs_selection(d, pnl, sig)
    ss.to_csv(out / "sizing_vs_selection.csv")
    sel.to_csv(out / "selection_vs_universe_by_year.csv")
    hr = hit_rate(pnl, d)
    hr.to_csv(out / "hit_rate.csv", index=False)
    dec = alpha_decay(sig, str(d["date"].iloc[0].date()), str(d["date"].iloc[-1].date()))
    dec.to_csv(out / "alpha_decay.csv", index=False)
    es = earnings_split(pnl, d)
    es.to_csv(out / "earnings_split.csv", index=False)
    st = stress(d)
    st.to_csv(out / "stress.csv", index=False)
    pd.set_option("display.width", 200)
    for name, t in [("factor", fa), ("factor by year", fy), ("sizing/selection", ss),
                    ("selection by year", sel), ("hit rate", hr), ("decay", dec),
                    ("earnings", es), ("stress", st)]:
        print("\n== %s ==" % name)
        print(t.round(4).to_string())


if __name__ == "__main__":
    if "--survivorship" in sys.argv:
        survivorship_8k()
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

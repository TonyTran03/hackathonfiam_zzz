"""Data due-diligence self-test: the six Carbon Arc rules run on our own competition data.

Follows RULE.md (written 2026-10-29 11:14, before any result). Read-only: both parquets are
opened for reading, and the planted errors live only in memory. Prints aggregates and single
example rows; nothing from the datasets is written to disk.

Run:  python -I dd_selftest.py > dd_selftest_output.txt
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

CHARS = Path(r"C:\Users\b0079\Desktop\chars_final_with_names.parquet")
FILINGS = Path(r"C:\$Recycle.Bin\S-1-5-21-4171694947-3614074431-3931483665-1001\$RKLGOC1"
               r"\MCGILL FIAM ASSET MANAGEMENT HACKATHON FINALS OCTOBER 2026"
               r"\8k_20150101_20260831_identified.parquet")
FEATURES = Path(__file__).resolve().parents[2] / "data" / "factor_char_list.csv"

LAST = pd.Timestamp("2026-08-31")
EARLY = pd.Timestamp("2025-01-01")
SLICE = (pd.Timestamp("2019-01-31"), pd.Timestamp("2020-12-31"))
SHIFT_FROM, SHIFT_TO = pd.Timestamp("2019-12-31"), pd.Timestamp("2020-01-31")
AUX = ["permno", "eom", "date", "ticker", "company_name", "gvkey", "iid", "me", "ret",
       "size_grp", "ticker_name_status"]
FILING_COLS = ["document_id", "permno", "filing_date", "content_report_date", "ticker", "cik",
               "sec_accepted_at_utc", "filing_time_precision", "form_type", "is_amendment",
               "text_sha256", "company_name"]


def show(title, obj=""):
    print(f"\n### {title}")
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        print(obj.to_string())
    elif obj != "":
        print(obj)


def load():
    chars = pd.read_csv(FEATURES)["variable"].tolist()
    p = pd.read_parquet(CHARS, columns=AUX + [c for c in chars if c not in AUX])
    for c in ("eom", "date"):
        p[c] = pd.to_datetime(p[c])
    p["miss_share"] = p[chars].isna().mean(axis=1)
    f = pd.read_parquet(FILINGS, columns=FILING_COLS)
    for c in ("filing_date", "content_report_date"):
        f[c] = pd.to_datetime(f[c])
    f["eom"] = f["filing_date"] + pd.offsets.MonthEnd(0)
    return p, f, chars


def groups(p, end=LAST):
    life = p.groupby("permno")["eom"].agg(first="min", last="max")
    life["group"] = np.where(life["last"] == end, "listed",
                             np.where(life["last"] < EARLY, "left early", "left 2025-26"))
    return life


# ---------------------------------------------------------------- panel rules

def panel_rule1(p):
    """Timing consistency: ret_1_0 should equal the same row's ret, market_equity its me."""
    d = p[["eom"]].copy()
    d["ret_ok"] = (p["ret_1_0"] - p["ret"]).abs() < 1e-4
    d["me_ok"] = ((p["market_equity"] - p["me"]).abs() / p["me"].abs()) < 1e-4
    m = d.groupby("eom")[["ret_ok", "me_ok"]].mean()
    flagged = m[(m["ret_ok"] < m["ret_ok"].median() - 0.5) | (m["me_ok"] < m["me_ok"].median() - 0.5)]
    avail_cols = [c for c in p.columns if any(k in c.lower() for k in ("avail", "publish", "release", "asof", "as_of"))]
    return {"flag": len(flagged) > 0, "flagged_months": flagged, "median": m.median(),
            "min": m.min(), "avail_cols": avail_cols}


def panel_rule2(p):
    vint = [c for c in p.columns if any(k in c.lower() for k in ("vintage", "asof", "as_of", "revis", "restat"))]
    return {"vintage_cols": vint,
            "dup_permno_eom": int(p.duplicated(["permno", "eom"]).sum()),
            "dup_gvkey_iid_eom": int(p.duplicated(["gvkey", "iid", "eom"]).sum())}


def panel_rule3(p):
    q = p.sort_values(["permno", "eom"])
    dup = int(q.duplicated(["permno", "eom"]).sum())
    t = q.dropna(subset=["ticker"]).groupby(["ticker", "eom"])["permno"].nunique()
    multi = t[t > 1]
    key = q["gvkey"] + "-" + q["iid"]
    changed = key.ne(key.groupby(q["permno"]).shift()) & q["permno"].eq(q["permno"].shift())
    n_change = q.loc[changed, "permno"].nunique()
    # switch and switch back: a permno whose gvkey-iid sequence revisits an earlier key
    runs = pd.DataFrame({"permno": q["permno"], "key": key})[changed | ~q["permno"].eq(q["permno"].shift())]
    back = runs.groupby("permno")["key"].apply(lambda s: s.duplicated().any())
    reused = q.dropna(subset=["ticker"]).groupby("ticker")["permno"].nunique()
    # RULE.md: PASS needs unique keys and 1:1 dated tickers; dated gvkey-iid changes are evidence only
    flag = dup > 0 or len(multi) > 0
    return {"flag": flag, "dup": dup, "ticker_month_multi": len(multi),
            "ticker_month_multi_ex": multi.head(5), "permno_key_change": n_change,
            "switch_back": int(back.sum()), "tickers_reused": int((reused > 1).sum()),
            "changed_ex": q.loc[changed, ["permno", "eom", "ticker", "gvkey", "iid"]].head(3)}


def panel_rule4(p, chars):
    high = p["miss_share"] > 0.5
    def ratio(g):
        h = g.loc[g["miss_share"] > 0.5, "me"]
        o = g.loc[g["miss_share"] <= 0.5, "me"]
        return h.median() / o.median() if len(h) and len(o) else np.nan
    monthly = p.groupby("eom")[["me", "miss_share"]].apply(ratio)
    r = float(monthly.median())
    tab = (p.assign(miss_band=pd.cut(p["miss_share"], [-0.01, 0.1, 0.25, 0.5, 1.0],
                                     labels=["<=10%", "10-25%", "25-50%", ">50%"]))
           .groupby("miss_band", observed=True)
           .agg(rows=("me", "size"), median_me_musd=("me", "median"),
                share_micro_nano=("size_grp", lambda s: s.isin(["micro", "nano"]).mean())))
    ex = p[high & p["company_name"].notna()].sort_values("eom").tail(1)[
        ["permno", "eom", "ticker", "company_name", "me", "miss_share"]]
    return {"flag": r < 0.5, "ratio": r, "high_rows": int(high.sum()), "rows": len(p), "table": tab,
            "months": int(monthly.notna().sum()), "example": ex}


def panel_rule5(p, end):
    life = groups(p, end)
    p = p.join(life["group"], on="permno")
    by_year = p.groupby([p["eom"].dt.year, "group"])["permno"].nunique().unstack(fill_value=0)
    by_year["all"] = p.groupby(p["eom"].dt.year)["permno"].nunique()
    exit_share = float((life["last"] < end).mean())
    lit = None
    if 2024 in by_year.index:
        lit = by_year.loc[2021:, "all"] / by_year.loc[2024, "all"]
    return {"flag": exit_share < 0.01, "exit_share": exit_share, "firms": len(life),
            "by_year": by_year, "literal": lit, "life": life}


def rule6(counts):
    """counts: monthly row counts indexed by month-end."""
    if not (counts.index.year == 2024).any():
        return {"start": None, "pass": None}
    level = counts[counts.index.year == 2024].mean()
    start = counts[counts >= 0.5 * level].index.min()
    return {"start": start, "pass": start <= pd.Timestamp("2019-12-31"), "level": level,
            "first": counts.iloc[:3]}


def run_panel(p, chars, end, label):
    out = {"r1": panel_rule1(p), "r2": panel_rule2(p), "r3": panel_rule3(p),
           "r4": panel_rule4(p, chars), "r5": panel_rule5(p, end),
           "r6": rule6(p.groupby("eom").size())}
    r = out
    print(f"\n======== PANEL checks: {label} ({len(p):,} rows, {p['permno'].nunique():,} permnos)")
    show("R1 timing: months flagged", r["r1"]["flagged_months"] if r["r1"]["flag"] else "none")
    show("R1 match shares, median month / worst month",
         pd.concat([r["r1"]["median"], r["r1"]["min"]], axis=1, keys=["median", "min"]))
    show("R1 availability columns", r["r1"]["avail_cols"] or "none")
    show("R2", {k: v for k, v in r["r2"].items()})
    show("R3", {k: v for k, v in r["r3"].items() if not k.endswith("_ex")})
    show("R3 ticker-month with >1 permno (first 5)", r["r3"]["ticker_month_multi_ex"])
    show("R3 gvkey-iid changes (first 3)", r["r3"]["changed_ex"])
    show("R4 median me ratio (rows >50% missing / others), median of monthly ratios",
         f"{r['r4']['ratio']:.3f} over {r['r4']['months']} months; {r['r4']['high_rows']:,} of {r['r4']['rows']:,} rows >50% missing")
    show("R4 by missing band", r["r4"]["table"])
    show("R4 example", r["r4"]["example"])
    show("R5 firms per year by group", r["r5"]["by_year"])
    show("R5 literal (firms vs 2024)", r["r5"]["literal"] if r["r5"]["literal"] is not None else "n/a: no 2024 in window")
    show("R5 survivorship: share of firms whose last month < window end",
         f"{r['r5']['exit_share']:.4f} of {r['r5']['firms']:,} firms -> flag={r['r5']['flag']}")
    show("R6 start", r["r6"])
    return out


# ---------------------------------------------------------------- 8-K rules

def filings_checks(f, p):
    print(f"\n======== 8-K checks ({len(f):,} filings, {f['permno'].nunique():,} permnos)")
    # R1
    show("R1 sec_accepted_at_utc non-null", int(f["sec_accepted_at_utc"].notna().sum()))
    show("R1 filing_time_precision", f["filing_time_precision"].value_counts())
    lag = (f["filing_date"] - f["content_report_date"]).dt.days
    show("R1 filing_date - content_report_date (days)",
         pd.Series({"report date missing": int(lag.isna().sum()), "negative (filed before event)": int((lag < 0).sum()),
                    "0": int((lag == 0).sum()), "1-4": int(lag.between(1, 4).sum()),
                    ">4": int((lag > 4).sum()), "median": lag.median()}))
    show("R1 example (IBM)", f[f["permno"] == 12490].sort_values("filing_date").head(1)[
        ["permno", "ticker", "filing_date", "content_report_date", "sec_accepted_at_utc", "filing_time_precision"]])
    # R2
    vint = [c for c in pq.ParquetFile(FILINGS).schema_arrow.names
            if any(k in c.lower() for k in ("vintage", "asof", "as_of", "revis", "restat"))]
    show("R2 vintage-like columns", vint or "none")
    show("R2 duplicates", {"document_id": int(f["document_id"].duplicated().sum()),
                           "permno+filing_date+text_sha256": int(f.duplicated(["permno", "filing_date", "text_sha256"]).sum()),
                           "amendments (8-K/A)": int(f["is_amendment"].sum())})
    # R3
    m = f.merge(p[["permno", "eom", "ticker"]].rename(columns={"ticker": "panel_ticker"}),
                on=["permno", "eom"], how="left")
    both = m["ticker"].notna() & m["panel_ticker"].notna()
    conflict = both & (m["ticker"] != m["panel_ticker"])
    owner = p.dropna(subset=["ticker"]).drop_duplicates(["ticker", "eom"])[["ticker", "eom", "permno"]] \
             .rename(columns={"permno": "owner"})
    m = m.merge(owner, on=["ticker", "eom"], how="left")
    other = m["owner"].notna() & (m["owner"] != m["permno"])
    show("R3 ticker vs panel", {"both tickers present": int(both.sum()),
                                "ticker differs from panel": int(conflict.sum()),
                                "share differs": round(conflict.sum() / both.sum(), 4),
                                "ticker owned by another permno that month": int(other.sum()),
                                "cik missing": int(f["cik"].isna().sum())})
    show("R3 conflict examples", m.loc[other, ["permno", "filing_date", "ticker", "panel_ticker", "owner", "company_name"]]
         .drop_duplicates("permno").head(5))
    # R4 + known answer (a)
    life = groups(p)
    last12 = life["last"] - pd.offsets.MonthEnd(11)
    fl = f[["permno", "eom"]].join(life[["last"]], on="permno")
    fl = fl[(fl["eom"] <= fl["last"]) & (fl["eom"] >= fl["last"] - pd.offsets.MonthEnd(11))]
    life["has_8k_last12"] = life.index.isin(fl["permno"])
    life["has_8k_ever"] = life.index.isin(f["permno"])
    size_last = p.sort_values("eom").groupby("permno")["size_grp"].last()
    life["size_last"] = size_last
    life["me_last"] = p.sort_values("eom").groupby("permno")["me"].last()
    ka = life.groupby("group").agg(firms=("last", "size"), pct_8k_last12=("has_8k_last12", "mean"),
                                   pct_8k_ever=("has_8k_ever", "mean"))
    show("R4 / known answer (a): coverage by group", ka)
    size = life.pivot_table(index="size_last", columns="group", values="has_8k_last12", aggfunc="mean")
    size_n = life.pivot_table(index="size_last", columns="group", values="has_8k_last12", aggfunc="size")
    show("R4 % with 8-K in last 12 months, by size at last month", size)
    show("R4 n by size", size_n)
    ex = life[(life["group"] == "left early") & ~life["has_8k_ever"]].sort_values("me_last").tail(1)
    exr = p[p["permno"].isin(ex.index)].sort_values("eom")
    exn = exr.tail(1)[["permno", "eom", "me"]].assign(
        last_known_ticker=exr["ticker"].dropna().iloc[-1] if exr["ticker"].notna().any() else None,
        last_known_name=exr["company_name"].dropna().iloc[-1] if exr["company_name"].notna().any() else None)
    show("R4 example: largest left-early firm with no 8-K ever", exn)
    # R5 split by year
    pg = p[["permno", "eom"]].join(life["group"], on="permno")
    pg["year"] = pg["eom"].dt.year
    present = pg.drop_duplicates(["permno", "year"])
    fy = f.assign(year=f["eom"].dt.year)[["permno", "year"]].drop_duplicates()
    present["has"] = present.set_index(["permno", "year"]).index.isin(fy.set_index(["permno", "year"]).index)
    cov = present.pivot_table(index="year", columns="group", values="has", aggfunc="mean")
    cov["all"] = present.groupby("year")["has"].mean()
    rows = f.groupby(f["eom"].dt.year).size().rename("filings")
    show("R5 % of panel firms with >=1 8-K that year, by group", cov.join(rows))
    lit = pd.DataFrame({"filings_vs_2024": rows.loc[2021:] / rows.loc[2024],
                        "covered_share_vs_2024": cov.loc[2021:, "all"] / cov.loc[2024, "all"]})
    show("R5 literal rule (2026 is Jan-Aug)", lit)
    # R6
    r6 = rule6(f.groupby("eom").size())
    show("R6 start", r6)
    return ka, life


# ---------------------------------------------------------------- planted errors

def pick_ticker(s):
    q = s.dropna(subset=["ticker"])
    n = q.groupby(["ticker", "permno"]).size()
    n = n[n >= 6]
    k = n.groupby(level=0).size()
    t = sorted(k[k >= 2].index)[0]
    holders = q[q["ticker"] == t].groupby("permno")["eom"].min().sort_values()
    holders = holders[holders.index.isin(n.loc[t].index)]
    return t, holders.index[0], holders.index[1]


def planted(p, chars):
    s = p[(p["eom"] >= SLICE[0]) & (p["eom"] <= SLICE[1])].copy()
    end = SLICE[1]

    def e1(d, cols=chars):
        d = d.copy()
        src = d[d["eom"] == SHIFT_TO].set_index("permno")[cols]
        idx = d.index[(d["eom"] == SHIFT_FROM) & d["permno"].isin(src.index)]
        d.loc[idx, cols] = src.loc[d.loc[idx, "permno"]].to_numpy()
        return d

    def e2(d):
        last = d.groupby("permno")["eom"].max()
        return d[d["permno"].isin(last[last == end].index)]

    t, a, b = pick_ticker(s)

    def e3(d):
        d = d.copy()
        d.loc[(d["permno"] == b) & (d["ticker"] == t), "permno"] = a
        return d

    print("\n======== PLANTED-ERROR TEST, slice", SLICE[0].date(), "to", SLICE[1].date())
    print(f"error 3 ticker {t}: earlier holder permno {a}, later holder permno {b}")
    print(s[s["ticker"] == t].groupby("permno").agg(first=("eom", "min"), last=("eom", "max"),
                                                     months=("eom", "size"), name=("company_name", "last")).to_string())
    nonmkt = [c for c in chars if c not in ("ret_1_0", "market_equity")]
    runs = {"clean": s, "error 1 look-ahead": e1(s), "error 2 survivorship": e2(s),
            "error 3 wrong ticker map": e3(s), "all three": e3(e2(e1(s))),
            "extra: error 1 without ret_1_0/market_equity": e1(s, nonmkt)}
    res = {k: run_panel(v, chars, end, k) for k, v in runs.items()}
    summ = pd.DataFrame({k: {"R1 timing flag": r["r1"]["flag"],
                             "R1 flagged months": ", ".join(f"{d:%Y-%m}" for d in r["r1"]["flagged_months"].index),
                             "R3 flag": r["r3"]["flag"], "R3 dup keys": r["r3"]["dup"],
                             "R3 permnos w/ key change": r["r3"]["permno_key_change"],
                             "R3 switch-back": r["r3"]["switch_back"],
                             "R4 me ratio": round(r["r4"]["ratio"], 3),
                             "R5 survivorship flag": r["r5"]["flag"],
                             "R5 exit share": round(r["r5"]["exit_share"], 4)}
                         for k, r in res.items()})
    show("PLANTED SUMMARY", summ)


def main():
    pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_colwidth", 50)
    p, f, chars = load()
    print(f"panel {len(p):,} rows; filings {len(f):,} rows; {len(chars)} characteristics")
    run_panel(p, chars, LAST, "full panel")
    filings_checks(f, p)
    planted(p, chars)


if __name__ == "__main__":
    main()

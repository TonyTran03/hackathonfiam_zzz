"""Design evidence for the E overlay, from data that ends before the test window.

    python 06_final/f05_event_study.py

Question: after a distress 8-K (items 4.01 auditor change, 4.02 non-reliance,
1.03 bankruptcy, 3.01 delisting notice), do tradable stocks keep falling over
the days a daily book could still act in?

Timing follows Section 7 exactly. A filing dated t is acted on at the close of
t+1, so the first return a book could capture is t+2. The window here is
t+2 .. t+21 (20 trading days), measured against the equal-weighted average of
the screened universe on the same day.

Sample: filings dated 2015-01-01 .. 2020-12-31 only. The decision to adopt the
overlay is taken here, before any 2021-2026 number exists.

Survivorship caveat (Section 6.4): the supplied corpus under-represents firms
that later delisted, and those are disproportionately the ones whose distress
filings were followed by the worst returns. Any bias therefore makes the
measured drift LESS negative than the truth, which works against adopting the
overlay -- the conservative direction for this decision.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
from common import config as C  # noqa: E402

ITEMS = {"4.01", "4.02", "1.03", "3.01"}
END = "2020-12-31"
H0, H1 = 2, 21


def main():
    f = pq.read_table(C.FILINGS_PARQUET, columns=["permno", "filing_date", "items"]).to_pandas()
    f["filing_date"] = pd.to_datetime(f["filing_date"]).dt.normalize()
    f = f[(f["filing_date"] <= END)]
    f["hit"] = [sorted(set(i) & ITEMS) if i is not None else [] for i in f["items"]]
    f = f[f["hit"].map(len) > 0].drop_duplicates(["permno", "filing_date"])

    # tradability on the previous month end, first-round screen
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "eom", "prc", "size_grp", "me"])
    panel["fm"] = (pd.PeriodIndex(panel["eom"], freq="M") + 1).astype(str)
    f["fm"] = f["filing_date"].dt.to_period("M").astype(str)
    f = f.merge(panel[["permno", "fm", "prc", "size_grp", "me"]], on=["permno", "fm"], how="inner")
    f = f[(f["prc"].abs() >= 5) & ~f["size_grp"].isin(["nano", "micro"])]

    dsf = pd.read_parquet(F.DSF_PARQUET)
    dsf = dsf[(dsf["date"] >= "2014-12-01") & (dsf["date"] <= "2021-03-31")]
    univ = set(panel.loc[(panel["prc"].abs() >= 5) & ~panel["size_grp"].isin(["nano", "micro"]),
                         "permno"])
    ew = dsf[dsf["permno"].isin(univ)].groupby("date")["daily_return"].mean()
    dates = ew.index
    pos = {d: k for k, d in enumerate(dates)}
    R = dsf.pivot(index="date", columns="permno", values="daily_return").reindex(dates)

    rows = []
    for _, e in f.iterrows():
        k = dates.searchsorted(e["filing_date"])      # day t (or next trading day)
        if k + H1 >= len(dates) or e["permno"] not in R.columns:
            continue
        r = R[e["permno"]].values[k + H0:k + H1 + 1]
        m = ew.values[k + H0:k + H1 + 1]
        ok = ~np.isnan(r)
        if ok.sum() < 5:
            car = np.nan
        else:
            car = np.prod(1 + r[ok]) - np.prod(1 + m[ok])
        r01 = R[e["permno"]].values[k:k + 2]
        rows.append({"permno": e["permno"], "filing_date": e["filing_date"],
                     "items": ",".join(e["hit"]), "size_grp": e["size_grp"],
                     "car_t2_t21": car, "ret_t0_t1": np.nansum(r01),
                     "delisted_in_window": int(ok.sum() < H1 - H0 + 1)})
    d = pd.DataFrame(rows)
    out = []
    for name, g in [("all", d)] + [(it, d[d["items"].str.contains(it, regex=False)]) for it in sorted(ITEMS)]:
        c = g["car_t2_t21"].dropna()
        # cluster by month: events in the same month are not independent
        mon = g.dropna(subset=["car_t2_t21"]).groupby(g["filing_date"].dt.to_period("M"))["car_t2_t21"].mean()
        t_month = mon.mean() / (mon.std(ddof=1) / np.sqrt(len(mon))) if len(mon) > 2 else np.nan
        out.append({"items": name, "n_events": len(g), "n_with_window": len(c),
                    "mean_car_t2_t21_pct": 100 * c.mean(), "median_car_pct": 100 * c.median(),
                    "share_negative": (c < 0).mean(), "t_monthly_clustered": t_month,
                    "mean_ret_t0_t1_pct": 100 * g["ret_t0_t1"].mean()})
    res = pd.DataFrame(out)
    F.OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(F.OUT / "design_event_study.csv", index=False)
    d.to_csv(F.DATA / "design_event_study_events.csv", index=False)
    pd.set_option("display.width", 160)
    print(res.round(3).to_string(index=False))
    a = res.iloc[0]
    adopt = a["mean_car_t2_t21_pct"] < 0 and a["t_monthly_clustered"] < -2
    print("\nadoption rule (PROTOCOL_FINAL D2): mean CAR(t+2..t+21) < 0 with monthly-"
          "clustered t < -2  ->  %s" % ("ADOPT" if adopt else "DO NOT ADOPT"))
    return res


if __name__ == "__main__":
    main()

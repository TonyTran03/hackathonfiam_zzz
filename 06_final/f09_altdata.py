"""Day-1 kit for Carbon Arc: point-in-time joins and the four-question screen.

Most teams lose the first event day to a join (first-round rules, p.16). This
module is the join, written and tested before the data arrives.

    from f09_altdata import pit_join_daily, pit_join_monthly, screen_asset

pit_join_daily(feature, key, value_cols, lag_days, ...)
    Attach a dated feature to (permno, decision_date) rows so that a value
    dated t, with publication lag L, is usable only from the close of
    t + L + 1 trading days (the Section 7 convention on top of the source
    lag). Asserts, per join, that max(available date) <= decision date.

pit_join_monthly(feature, ...)
    Same, collapsed to the monthly panel key (permno, target_month): the value
    must have been available by the formation day of target_month.

screen_asset(feature, ...)
    The four questions of Section 6.6, answered from the data itself:
    (i) history start vs 2021, (ii) lag as declared, (iii) revisions present?
    (does a versioning column show the same key with different values),
    (iv) coverage of our universe and whether covered names out- or
    under-perform uncovered ones (the Section 6.3 return test), plus the
    later-delisted resolution rate.

Entity keys. Carbon Arc resolves to tickers and CIKs; our panel is keyed by
permno. Map through CIK where the asset has one (stable, never reassigned),
using the CIK-permno pairs in the supplied 8-K file as the bridge, and through
ticker only with a date-bounded link (a ticker is reassigned after a delisting).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
from common import config as C  # noqa: E402


def trading_calendar():
    return pd.read_parquet(F.DATA / "calendar.parquet")["date"]


def available_from(dates, lag_days, cal=None):
    """First trading day whose CLOSE may use a value dated `dates` with a
    calendar-day publication lag `lag_days`: published at date + lag, then
    the Section 7 rule (data through t forms the book at the close of t+1).

    lag_days is the source lag BEYOND the record's date. The Section 7 day is
    added here, so do not add it again: CA0035 (Benzinga, "T+1"), which the
    instructions allow into a feature from t+1, is lag_days=0; a metric
    published at T+9 is lag_days=9."""
    cal = trading_calendar() if cal is None else cal
    pub = pd.to_datetime(dates) + pd.to_timedelta(lag_days, unit="D")
    k = cal.searchsorted(pub, side="right")         # first trading day after publication
    k = np.minimum(k, len(cal) - 1)
    return pd.Series(cal.values[k], index=getattr(dates, "index", None))


def cik_permno_bridge():
    """CIK -> permno pairs with the date range each was observed, from the
    supplied 8-K file. Only a bridge for assets keyed by CIK."""
    import pyarrow.parquet as pq
    f = pq.read_table(C.FILINGS_PARQUET, columns=["cik", "permno", "filing_date"]).to_pandas()
    f["filing_date"] = pd.to_datetime(f["filing_date"])
    return f.groupby(["cik", "permno"])["filing_date"].agg(["min", "max"]).reset_index()


def pit_join_daily(rows, feature, value_cols, date_col="date", lag_days=1,
                   key="permno", agg="last"):
    """rows: DataFrame with [key, decision_date]. feature: [key, date_col, values].
    Returns rows with value_cols attached as of each decision_date's close."""
    f = feature[[key, date_col] + value_cols].copy()
    f["avail"] = available_from(f[date_col], lag_days)
    f = f.sort_values("avail")
    r = rows.sort_values("decision_date")
    out = pd.merge_asof(r, f.drop(columns=[date_col]).rename(columns={"avail": "_avail"}),
                        left_on="decision_date", right_on="_avail", by=key, direction="backward")
    used = out.dropna(subset=["_avail"])
    assert (used["_avail"] <= used["decision_date"]).all(), "LEAK: feature available after decision"
    return out


def pit_join_monthly(panel_rows, feature, value_cols, date_col="date", lag_days=1, key="permno"):
    """Attach to (permno, target_month): available by that month's formation day."""
    cal = pd.read_parquet(F.DATA / "calendar.parquet")
    fd = cal[cal["is_formation"]].assign(target_month=lambda c: c["month"].astype(str))
    rows = panel_rows.merge(fd[["target_month", "date"]].rename(columns={"date": "decision_date"}),
                            on="target_month", how="left")
    return pit_join_daily(rows, feature, value_cols, date_col, lag_days, key)


def screen_asset(name, feature, value_col, date_col="date", key="permno",
                 declared_lag_days=None, version_cols=None):
    """Answer Section 6.6's four questions from the data. Writes a one-row CSV."""
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "eom", C.TARGET, "prc", "size_grp"])
    panel["ym"] = pd.PeriodIndex(panel["eom"], freq="M")
    last = panel.groupby("permno")["ym"].max()
    exited = set(last[last < pd.Period("2026-07", "M")].index)
    f = feature.copy()
    f[date_col] = pd.to_datetime(f[date_col])
    start = f[date_col].min()
    revised = None
    if version_cols:
        dup = f.groupby([key, date_col])[value_col].nunique()
        revised = float((dup > 1).mean())
    f["ym"] = f[date_col].dt.to_period("M")
    cov = f[[key, "ym"]].drop_duplicates().assign(cov=True)
    p = panel[(panel["ym"] >= pd.Period("2021-01", "M"))].merge(cov, on=[key, "ym"], how="left")
    p["cov"] = p["cov"].fillna(False).astype(bool)
    t = p[(p["prc"].abs() >= 5)].dropna(subset=[C.TARGET])
    diff = t.groupby("ym").apply(lambda g: g.loc[g["cov"], C.TARGET].mean()
                                 - g.loc[~g["cov"], C.TARGET].mean(), include_groups=False).dropna()
    firms = f[key].dropna().unique()
    res = {
        "asset": name,
        "q1_history_start": str(start.date()),
        "q1_years_before_2021": round((pd.Timestamp("2021-01-01") - start).days / 365.25, 1),
        "q2_declared_lag_days": declared_lag_days,
        "q3_share_keys_with_revisions": revised,
        "q4_coverage_of_universe_2021_26": p["cov"].mean(),
        "q4_covered_minus_uncovered_ret_pct_m": 100 * diff.mean() if len(diff) else np.nan,
        "q4_t": diff.mean() / diff.std() * np.sqrt(len(diff)) if len(diff) > 2 else np.nan,
        "later_exited_firms_resolved": len(set(firms) & exited) / max(len(exited), 1),
        "surviving_firms_resolved": len(set(firms) - exited) / max(len(set(last.index) - exited), 1),
    }
    out = F.OUT / "altdata_screens"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([res]).to_csv(out / ("%s.csv" % name), index=False)
    return res


if __name__ == "__main__":
    # self-test on the supplied 8-K corpus: an asset we already understand
    import pyarrow.parquet as pq
    f = pq.read_table(C.FILINGS_PARQUET, columns=["permno", "filing_date"]).to_pandas()
    f["n"] = 1
    print(screen_asset("selftest_8k_corpus", f.rename(columns={"filing_date": "date"}), "n",
                       declared_lag_days=1))
    rows = pd.DataFrame({"permno": [10107, 10107], "decision_date": pd.to_datetime(["2021-03-01", "2021-03-02"])})
    feat = pd.DataFrame({"permno": [10107], "date": pd.to_datetime(["2021-02-26"]), "x": [1.0]})
    print(pit_join_daily(rows, feat, ["x"], lag_days=1))

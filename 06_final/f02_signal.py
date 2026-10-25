"""Final stage 2 -- monthly scores and eligibility, the input to the daily engine.

The forecast is the first round's, untouched: the per-fold blend of the
gradient-boosted trees and the linear models from stage 3, refit annually,
chosen on each fold's own validation block. What changes is everything that
turns it into positions, because the mandate changed.

Score    neutralised on sector, size and beta inside the screened universe,
         then averaged over 3 months -- the first round's recipe, unchanged.
Long     price >= $5, no nano or micro caps (first-round screen, unchanged).
Short    the same screen PLUS market cap >= $500m. The cap is checked twice:
         at month-end with a 10% cushion when the candidate list is drawn,
         and again by the engine on the formation day itself, which is the
         date the mandate measures it on.

The realised return column never leaves this module except as `stub_ret`,
which the engine reads only to book the last-day return of a name that
delists while held (accounting, never selection). select_inputs() returns a
frame WITHOUT it, and the engine's selection code only ever sees that frame.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
from common import config as C  # noqa: E402

H = F.HOUSE
BETA_SOURCES = ["betabab_1260d", "betadown_252d", "beta_60m"]
PANEL_COLS = ["permno", "target_month", "eom", "prc", "me", "shares", "size_grp",
              "gics", "dolvol_126d", "rvol_21d", "ivol_capm_252d", "bidaskhl_21d",
              "ticker", "company_name", C.TARGET] + BETA_SOURCES


def unit_rank(s):
    r = s.rank(method="average")
    sd = r.std(ddof=0)
    return (r - r.mean()) / (sd if sd else 1.0)


def neutralise(g):
    """Residual of the forecast after sector dummies, size rank and beta level."""
    y = unit_rank(g["fcst"]).values
    sector = g["sector"]
    X = [np.ones(len(g)), unit_rank(g["me"]).values, g["beta_use"].values]
    dummies = pd.get_dummies(sector, drop_first=True).values.astype(float)
    M = np.column_stack(X + ([dummies] if dummies.size else []))
    coef, *_ = np.linalg.lstsq(M, y, rcond=None)
    return pd.Series(y - M @ coef, index=g.index)


def forecast_frame(which):
    """The traded forecast `avg` for the test window, or the same recipe
    rebuilt on the 2019-2020 validation block for the design window."""
    if which == "test":
        p = pd.read_parquet(C.PROCESSED_DIR / "predictions.parquet",
                            columns=["permno", "target_month", "avg"])
        lo, hi = F.FINAL["oos_start"][:7], F.FINAL["oos_end"][:7]
        p = p[(p["target_month"] >= lo) & (p["target_month"] <= hi)]
    else:
        v = pd.read_parquet(C.PROCESSED_DIR / "validation_predictions.parquet")
        # validation_predictions stacks every fold's block; the first fold's
        # (2019-2020) is the only one wholly before the test window
        v = v[v["target_month"] <= F.DESIGN_END[:7]].drop_duplicates(
            ["permno", "target_month"], keep="first")
        bj = json.loads((C.PROCESSED_DIR / "blend.json").read_text())
        parts = bj["per_fold"][sorted(bj["per_fold"])[0]]["parts"]
        if "avg_linear" in parts:
            v["avg_linear"] = v[["ols", "lasso", "ridge", "en"]].mean(axis=1)
        z = v.groupby("target_month")[parts].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
        v["avg"] = z.mean(axis=1)
        p = v[["permno", "target_month", "avg"]]
    return p.rename(columns={"avg": "fcst"})


def build(which):
    p = forecast_frame(which)
    panel = pd.read_parquet(C.MODEL_TABLE, columns=PANEL_COLS)
    df = p.merge(panel, on=["permno", "target_month"], how="left")
    assert df["eom"].notna().all(), "forecast rows without a panel row"
    # leakage guard: the characteristics behind month m are dated end of m-1
    eom_m = pd.PeriodIndex(df["eom"], freq="M")
    tgt_m = pd.PeriodIndex(df["target_month"], freq="M")
    assert ((tgt_m - eom_m).map(lambda x: x.n) == 1).all(), \
        "a forecast row uses characteristics not dated exactly one month earlier"

    df["beta_use"] = df[BETA_SOURCES[0]]
    for nxt in BETA_SOURCES[1:]:
        df["beta_use"] = df["beta_use"].fillna(df[nxt])
    df["sector"] = df["gics"].astype(str).str[:2].where(df["gics"].notna(), "na")

    keep = ((df["prc"].abs() >= H["min_price"])
            & (~df["size_grp"].isin(("nano", "micro")))
            & df["beta_use"].notna() & df["rvol_21d"].notna()
            & df["dolvol_126d"].notna() & (df["dolvol_126d"] > 0))
    n0 = len(df)
    df = df[keep].copy()
    df["beta_use"] = df["beta_use"].clip(-0.5, 3.5)

    df["score"] = df.groupby("target_month", group_keys=False).apply(
        neutralise, include_groups=False)
    df = df.sort_values(["permno", "target_month"])
    df["score"] = (df.groupby("permno")["score"]
                     .transform(lambda s: s.rolling(H["smooth_months"], min_periods=1).mean()))

    df["short_ok_eom"] = df["me"] >= F.FINAL["short_min_me_musd"] * H["short_floor_cushion"]
    # Corwin-Schultz is biased up when true spreads are tiny (it reads
    # intraday volatility as spread): half of it gives a 36 bp median for MEGA
    # caps in 2019-2020. So it is capped by a size-group ceiling as well.
    size_cap = df["size_grp"].map(H["half_spread_cap_by_size_bps"]).fillna(H["half_spread_cap_bps"])
    df["half_spread"] = np.minimum(0.5 * df["bidaskhl_21d"].fillna(1.0), size_cap / 1e4).clip(
        lower=H["half_spread_floor_bps"] / 1e4)
    df["ivol_top_decile"] = df.groupby("target_month")["ivol_capm_252d"].transform(
        lambda s: s >= s.quantile(0.9))
    df = df.rename(columns={C.TARGET: "stub_ret"})

    per = df.groupby("target_month").agg(n=("permno", "size"), short_ok=("short_ok_eom", "sum"))
    print("[%s] %s of %s stock-months screened in; per month %d-%d names, "
          "%d-%d short-eligible at month end"
          % (which, format(len(df), ","), format(n0, ","), per["n"].min(), per["n"].max(),
             per["short_ok"].min(), per["short_ok"].max()))
    out = F.DATA / ("signal_%s.parquet" % which)
    df.to_parquet(out, index=False)
    return df


def select_inputs(df):
    """What selection is allowed to see: everything except the realised return."""
    return df.drop(columns=["stub_ret"])


if __name__ == "__main__":
    for which in sys.argv[1:] or ["design", "test"]:
        build(which)

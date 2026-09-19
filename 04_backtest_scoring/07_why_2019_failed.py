"""Stage 5c -- why did the strategy lose money in 2019-2020?

Every smoothing/buffer combination produced a negative net information ratio
on the 24 clean validation months. That is the single most important open
question in this project, because it is the only genuinely out-of-sample
evidence we have that was not used to build anything.

Three explanations, and this script tries to separate them:

  A  the period was hard      -- COVID and the momentum reversal, not the model
  B  the model was untrained  -- fold 1 has the shortest training set of any
  C  the edge is not real     -- 2021-2026 was a good draw

Diagnostics: month-by-month losses, whether the signal or the book failed,
how the two periods differ in cross-sectional dispersion, and what the
validation book was actually exposed to.
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "03_portfolio_construction"))
from common import config as C

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "build4", C.ROOT / "03_portfolio_construction" / "04_build_portfolio.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

VAL_FILE = C.PROCESSED_DIR / "validation_predictions.parquet"
PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12


def load_validation_book():
    val = pd.read_parquet(VAL_FILE)
    val = val[val["target_month"] <= B.TUNE_END].drop_duplicates(
        ["permno", "target_month"], keep="first")
    z = val.groupby("target_month")[["gbm"]].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
    val[B.MODEL] = z.mean(axis=1)
    screened = B.screen(val, quiet=True)
    return screened, B.make_book(screened, B.SMOOTH_MONTHS, B.BUFFER_MULT)


def monthly_table(book, bm):
    book = book.copy()
    book["pnl"] = book["weight"] * book[C.TARGET].fillna(0.0)
    piv = book.pivot_table(index="target_month", columns="permno",
                           values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1)
    traded.iloc[0] = piv.abs().sum(axis=1).iloc[0]
    g = book.groupby("target_month")
    m = pd.DataFrame({
        "spread": g["pnl"].sum(),
        "long_leg": book[book["weight"] > 0].groupby("target_month")["pnl"].sum(),
        "short_leg": book[book["weight"] < 0].groupby("target_month")["pnl"].sum(),
        "traded": traded,
    }).reset_index().merge(bm, on="target_month", how="left")
    m["net20"] = m["spread"] - m["traded"] * 20 / 10000
    m["active"] = m["net20"] - PREMIUM_M
    m["mkt"] = m["sp500_ret"] - m["cash_monthly"]
    return m


def ic_by_month(frame, col):
    ok = frame[frame[C.TARGET].notna()]
    return ok.groupby("target_month").apply(
        lambda d: d[col].corr(d[C.TARGET], method="spearman"), include_groups=False)


def main():
    bm = pd.read_csv(C.BENCHMARK_CSV)[["target_month", "cash_monthly", "sp500_ret"]]
    screened_val, vbook = load_validation_book()
    vm = monthly_table(vbook, bm)

    print("=" * 74)
    print("WHY 2019-2020 LOST MONEY")
    print("=" * 74)

    print("\n--- month by month, net of 20 bps ---")
    print("  %-9s %9s %9s %9s %9s %9s" %
          ("month", "net", "long", "short", "market", "cum"))
    cum = 1.0
    for _, r in vm.iterrows():
        cum *= 1 + r["net20"]
        print("  %-9s %+8.2f%% %+8.2f%% %+8.2f%% %+8.2f%% %+8.2f%%"
              % (r["target_month"], 100 * r["net20"], 100 * r["long_leg"],
                 100 * r["short_leg"], 100 * r["mkt"], 100 * (cum - 1)))

    worst = vm.nsmallest(4, "net20")
    print("\n  the four worst months account for %+.1f%% of the %+.1f%% total"
          % (100 * worst["net20"].sum(), 100 * vm["net20"].sum()))
    rest = vm.drop(worst.index)
    print("  without them the other %d months compound to %+.1f%%, IR %+.2f"
          % (len(rest), 100 * ((1 + rest["net20"]).prod() - 1),
             np.sqrt(12) * rest["active"].mean() / rest["active"].std(ddof=1)))

    print("\n--- was it the SIGNAL or the BOOK? ---")
    vic = ic_by_month(screened_val, B.MODEL)
    test_pred = pd.read_parquet(C.PROCESSED_DIR / "predictions.parquet")
    z = test_pred.groupby("target_month")[["gbm"]].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
    test_pred[B.MODEL] = z.mean(axis=1)
    tic = ic_by_month(test_pred, B.MODEL)
    print("  rank correlation with the answer, 2019-2020: mean %+.4f, positive in %.0f%% of months"
          % (vic.mean(), 100 * (vic > 0).mean()))
    print("  rank correlation with the answer, 2021-2026: mean %+.4f, positive in %.0f%% of months"
          % (tic.mean(), 100 * (tic > 0).mean()))
    print("  worst validation months by rank correlation: %s"
          % ", ".join("%s %+.3f" % (k, v) for k, v in vic.nsmallest(4).items()))

    print("\n--- how different was the market? ---")
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["target_month", C.TARGET])
    panel = panel[panel[C.TARGET].notna()]
    disp = panel.groupby("target_month")[C.TARGET].std()
    for label, lo, hi in [("2015-2018 (training)", "2015-02", "2018-12"),
                          ("2019-2020 (validation)", "2019-01", "2020-12"),
                          ("2021-2026 (test)", "2021-01", "2026-08")]:
        d = disp.loc[lo:hi]
        print("  %-24s cross-sectional spread of returns: mean %.1f%%, max %.1f%% (%s)"
              % (label, 100 * d.mean(), 100 * d.max(), d.idxmax()))

    print("\n--- what was the validation book exposed to? ---")
    with zipfile.ZipFile(C.FF3_ZIP) as z2:
        raw = z2.read(z2.namelist()[0]).decode("latin-1")
    rows = [l for l in raw.splitlines() if len(l) > 7 and l[:6].isdigit() and l[6] == ","]
    ff = pd.read_csv(io.StringIO("\n".join(rows)), header=None,
                     names=["ym", "mkt_rf", "smb", "hml", "rf"])
    ff = ff[ff["ym"].astype(str).str.len() == 6]
    ff["target_month"] = pd.PeriodIndex(ff["ym"].astype(str), freq="M").astype(str)
    for c in ["mkt_rf", "smb", "hml"]:
        ff[c] = pd.to_numeric(ff[c], errors="coerce") / 100
    d = vm.merge(ff[["target_month", "mkt_rf", "smb", "hml"]], on="target_month")
    r = smf.ols("spread ~ mkt_rf + smb + hml", data=d).fit()
    print("  2019-2020 book: annualised alpha %+.1f%% (t %+.2f), "
          "market %+.2f, size %+.2f, value %+.2f"
          % (100 * 12 * r.params["Intercept"], r.tvalues["Intercept"],
             r.params["mkt_rf"], r.params["smb"], r.params["hml"]))
    print("  realised beta to the S&P 500: %+.2f"
          % smf.ols("spread ~ mkt", data=vm).fit().params["mkt"])
    print("  turnover: %.0f%% of capital traded per month" % (100 * vm["traded"].mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

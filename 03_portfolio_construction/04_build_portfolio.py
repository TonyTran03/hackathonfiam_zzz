"""Stage 4 -- turn predictions into monthly signed weights.

The baseline book, deliberately the plainest thing that satisfies the rules:

  each month, rank every stock by predicted excess return
  buy the top 100, short the bottom 100, equal weight inside each leg
  long leg +100% of capital, short leg -100%

That is 200 names, 200% gross, 0% net -- inside all four trading limits, and
sitting at the centre of the net-exposure band rather than at its edge.

Nothing here is neutralised beyond dollar terms. A dollar-neutral book that
happens to be long high-beta names and short low-beta ones is not market
neutral, and stage 5 will report the realised beta that gives it away. Fixing
that is the next piece of work, not this one.

Selection never consults the realized return, so stocks that were delisted in
the holding month can still be picked. Their return is unavailable, and
stage 5 reports how many positions that affected.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

PRED_FILE = C.PROCESSED_DIR / "predictions.parquet"
OUT = C.PROCESSED_DIR / "holdings.parquet"
SUBMISSION_CSV = C.ROOT / "05_submission" / "holdings.csv"

MODEL = "avg"          # which prediction column drives the book
N_PER_LEG = 100        # 200 names total: inside the 100-500 limit
LEG_EXPOSURE = 1.00    # +100% long, -100% short -> 200% gross, 0% net

# Tradability screen. Without it the short leg fills with penny stocks -- a
# median market cap around $50m and a median price near $2.60 -- and the
# backtest reports a return nobody could have earned: those names cannot be
# borrowed in size, and a squeeze takes the book apart (January 2021 cost the
# unscreened version 48% in a single month). The rules say they will read the
# short book with borrow costs in mind, so the screen is part of the strategy,
# not a convenience. About 1,980 stocks a month survive it -- ample for 200.
MIN_PRICE = 5.0
EXCLUDE_SIZE_GROUPS = ("nano", "micro")


def apply_tradability_screen(pred):
    panel = pd.read_parquet(C.MODEL_TABLE,
                            columns=["permno", "target_month", "prc", "me", "size_grp"])
    pred = pred.merge(panel, on=["permno", "target_month"], how="left")
    before = len(pred)
    keep = (pred["prc"].abs() >= MIN_PRICE) & (~pred["size_grp"].isin(EXCLUDE_SIZE_GROUPS))
    pred = pred[keep].copy()
    per_month = pred.groupby("target_month").size()
    print("tradability screen: price >= $%.0f, excluding %s"
          % (MIN_PRICE, "/".join(EXCLUDE_SIZE_GROUPS)))
    print("  %s of %s stock-months kept (%.0f%%); %.0f per month, min %d"
          % (format(len(pred), ","), format(before, ","), 100 * len(pred) / before,
             per_month.mean(), per_month.min()))
    return pred


def build():
    if not PRED_FILE.exists():
        raise SystemExit("missing %s -- run 02_prediction/03_train_predict.py first" % PRED_FILE)

    pred = pd.read_parquet(PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    pred = pred[(pred["target_month"] >= lo) & (pred["target_month"] <= hi)].copy()
    pred = apply_tradability_screen(pred)

    rows = []
    for month, g in pred.groupby("target_month", sort=True):
        g = g.sort_values(MODEL, ascending=False)
        if len(g) < 2 * N_PER_LEG:
            raise SystemExit("%s has only %d stocks, cannot fill both legs" % (month, len(g)))
        longs = g.head(N_PER_LEG).copy()
        shorts = g.tail(N_PER_LEG).copy()
        longs["weight"] = LEG_EXPOSURE / N_PER_LEG
        shorts["weight"] = -LEG_EXPOSURE / N_PER_LEG
        rows.append(pd.concat([longs, shorts]))

    h = pd.concat(rows, ignore_index=True)[
        ["permno", "target_month", "weight", MODEL, C.TARGET]]

    # labels for the submission file
    labels = pd.read_parquet(C.MODEL_TABLE,
                             columns=["permno", "target_month", "ticker", "company_name"])
    h = h.merge(labels, on=["permno", "target_month"], how="left")
    h["date"] = pd.PeriodIndex(h["target_month"], freq="M").to_timestamp()

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    h.to_parquet(OUT, index=False, compression="zstd")

    SUBMISSION_CSV.parent.mkdir(parents=True, exist_ok=True)
    (h[["date", "permno", "ticker", "company_name", "weight"]]
       .rename(columns={"date": "DATE", "permno": "PERMNO", "ticker": "TICKER",
                        "company_name": "COMPANY_NAME", "weight": "WEIGHT"})
       .to_csv(SUBMISSION_CSV, index=False))

    stats = h.groupby("target_month")["weight"].agg(
        n="size", gross=lambda w: w.abs().sum(), net="sum")
    print("wrote %s and %s" % (OUT.name, SUBMISSION_CSV.relative_to(C.ROOT)))
    print("  driven by       : %s" % MODEL)
    print("  months          : %d  (%s .. %s)"
          % (len(stats), h["target_month"].min(), h["target_month"].max()))
    print("  names per month : %d  (%d long, %d short)"
          % (stats["n"].iloc[0], N_PER_LEG, N_PER_LEG))
    print("  gross exposure  : %.0f%%   net exposure: %+.0f%%"
          % (100 * stats["gross"].mean(), 100 * stats["net"].mean()))
    missing = h[C.TARGET].isna().sum()
    print("  positions whose return is unavailable: %d of %s (%.2f%%)"
          % (missing, format(len(h), ","), 100 * missing / len(h)))
    return h


if __name__ == "__main__":
    build()

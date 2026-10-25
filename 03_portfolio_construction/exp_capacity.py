"""Which book survives the finals mandate's US$1bn fund size?

    python 03_portfolio_construction/exp_capacity.py

Round one left fund size open and we never checked liquidity, so the book we
submitted holds positions it could not have built: median long position 36% of
a day's volume, 63% of longs above 20%. The finals name the number, which
makes the omission a disqualifying one rather than an oversight.

Two levers, and they interact:

  LIQUIDITY SCREEN   require enough volume to build the position in BUILD_DAYS
                     at PARTICIPATION of daily volume. Directly removes the
                     names that cannot absorb us.
  POSITION COUNT     the mandate's floor rose from 100 names to 200 and the
                     ceiling is 500. Every extra name shrinks the position, so
                     breadth is itself a capacity instrument -- 400 names
                     halves the order size of 200.

Both are scored on the clean 2019-20 validation window FIRST. The evaluation
period is printed second and is a report, not the basis for the choice; the
same discipline the sector experiments used, for the same reason.

Nothing here overwrites the submitted book.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import config as C

_spec = importlib.util.spec_from_file_location(
    "bp", ROOT / "03_portfolio_construction" / "04_build_portfolio.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

OUT = C.ROOT / "05_submission" / "exp_capacity.csv"
FUND_USD = 1_000_000_000.0
PARTICIPATION = 0.10

# name, names per leg, liquidity screen on
ARMS = [
    ("round one (200, no screen)", 100, False),
    ("200 names, screened", 100, True),
    ("300 names, screened", 150, True),
    ("400 names, screened", 200, True),
    ("500 names, screened", 250, True),
]


def build(pred, n_per_leg, screen_on, market):
    """One arm. N_PER_LEG and the screen are module globals in bp."""
    old_n, old_s = bp.N_PER_LEG, bp.LIQUIDITY_SCREEN
    bp.N_PER_LEG, bp.LIQUIDITY_SCREEN = n_per_leg, screen_on
    try:
        screened = bp.screen(pred.copy(), quiet=True)
        return bp.make_book(screened, bp.SMOOTH_MONTHS, bp.BUFFER_MULT,
                            market=market)
    finally:
        bp.N_PER_LEG, bp.LIQUIDITY_SCREEN = old_n, old_s


def score(book):
    b = book.copy()
    b["pnl"] = b["weight"] * b[C.TARGET].fillna(0.0)
    sp = b.groupby("target_month")["pnl"].sum()
    piv = b.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1)
    traded.iloc[0] = piv.abs().sum(axis=1).iloc[0]
    act = sp.values - bp.PREMIUM_M
    net20 = sp.values - traded.values * 20 / 10000 - bp.PREMIUM_M
    out = {
        "IR": np.sqrt(12) * act.mean() / act.std(ddof=1),
        "IR_20bps": np.sqrt(12) * net20.mean() / net20.std(ddof=1),
        "spread": 100 * 12 * sp.mean(),
        "turnover": 100 * (traded / (2 * piv.abs().sum(axis=1))).mean(),
        "names": b.groupby("target_month").size().mean(),
    }
    # capacity, which is the point of the exercise
    if bp.ADV_COL in b.columns:
        b = b.dropna(subset=[bp.ADV_COL])
        usd = FUND_USD * b["weight"].abs()
        pct = usd / b[bp.ADV_COL]
        L = b["weight"] > 0
        out["pos_usd_m"] = usd.median() / 1e6
        out["adv_long"] = 100 * pct[L].median()
        out["adv_short"] = 100 * pct[~L].median()
        out["over20"] = 100 * (pct > 0.20).mean()
        out["inside_limit"] = 100 * (pct <= PARTICIPATION).mean()
    if "me" in b.columns:
        s = b[b["weight"] < 0]
        out["below_500m"] = int((s["me"] < 500).sum())
    return out


def show(title, rows):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print("  %-28s %7s %9s %9s %8s %9s %9s %8s %9s"
          % ("book", "IR", "IR@20bps", "turnover", "names",
             "pos US$m", "long %ADV", "over20%", "<500m"))
    for r in rows:
        print("  %-28s %+7.2f %+9.2f %8.1f%% %8.0f %9.1f %8.0f%% %7.0f%% %9d"
              % (r["book"], r["IR"], r["IR_20bps"], r["turnover"], r["names"],
                 r.get("pos_usd_m", float("nan")), r.get("adv_long", float("nan")),
                 r.get("over20", float("nan")), r.get("below_500m", -1)))


def main():
    market = bp.load_market()
    rows = []

    # ---- the clean window, which decides -----------------------------------
    vf = C.PROCESSED_DIR / "validation_predictions.parquet"
    if vf.exists():
        bj = json.loads((C.PROCESSED_DIR / "blend.json").read_text(encoding="utf-8"))
        parts = bj["per_fold"][sorted(bj["per_fold"])[0]]["parts"]
        val = pd.read_parquet(vf)
        val = val[val["target_month"] <= bp.TUNE_END].drop_duplicates(
            ["permno", "target_month"], keep="first")
        if "avg_linear" in parts and "avg_linear" not in val.columns:
            val["avg_linear"] = val[["ols", "lasso", "ridge", "en"]].mean(axis=1)
        z = val.groupby("target_month")[parts].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
        val[bp.MODEL] = z.mean(axis=1)
        vrows = []
        for label, n, s in ARMS:
            r = score(build(val, n, s, market))
            r["book"], r["window"] = label, "validation"
            vrows.append(r)
        show("VALIDATION 2019-2020 -- the only pre-test evidence, and it decides", vrows)
        rows += vrows

    # ---- the evaluation period, reported ------------------------------------
    pred = pd.read_parquet(bp.PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    pred = pred[(pred["target_month"] >= lo) & (pred["target_month"] <= hi)]
    erows = []
    for label, n, s in ARMS:
        r = score(build(pred, n, s, market))
        r["book"], r["window"] = label, "evaluation"
        erows.append(r)
    show("EVALUATION 2021-2026 -- reported, NOT the basis for choosing", erows)
    rows += erows

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\n  'long %ADV' is the median long position as a share of one day's")
    print("  volume. Desks stay under 10-20%. 'over20%' is the share of all")
    print("  positions above that line; '<500m' counts short positions below")
    print("  the mandate's market-cap floor.")
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stage 5k -- what the cash leg actually is, measured rather than assumed.

    python 04_backtest_scoring/17_cash_convention.py

The rules warn that the risk-free rate subtracted inside `ret_exc` is the data
pipeline's own, not necessarily the 3-month T-bill we benchmark against, and
that the two should not be assumed to cancel. The deck said they cancel. This
checks it instead, and writes cash_convention.csv so the slide reports the
residual rather than a claim.

How the book's return is actually built, written out:

    spread(t)  = sum over holdings of  w(i) * ret_exc_lead1m(i, t)
    total(t)   = rf_tb(t) + spread(t)
    hurdle(t)  = rf_tb(t) + 4%/12
    active(t)  = total(t) - hurdle(t) = spread(t) - 4%/12

with w the weight as a fraction of NAV, positive long and negative short, and
rf_tb the 3-month T-bill from the pinned FRED snapshot.

The economics this is standing in for: NAV buys L of longs, shorting S raises S
in proceeds, so the cash balance is 1 - L + S = 1 - net and earns rf on that.
Writing total as rf_tb + sum(w * excess) reproduces exactly that, because
sum(w * (r - rf_pipe)) = sum(w * r) - rf_pipe * net, and the rf_tb we add back
covers the whole NAV. The two agree only when rf_tb equals rf_pipe; the gap
between them, multiplied by net exposure, is the error. That is the number
below.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
RETURNS = C.ROOT / "05_submission" / "portfolio_returns.csv"
OUT = C.ROOT / "05_submission" / "cash_convention.csv"

rows = []


def put(metric, value, note=""):
    rows.append({"metric": metric, "value": value, "note": note})
    print("  %-46s %-16s %s" % (metric, value, note))


def main():
    m = pd.read_csv(RETURNS)
    months = set(m["target_month"])

    # The pipeline's own risk-free rate, backed out of the data it ships:
    # ret_exc = ret - rf_pipe, so rf_pipe = ret - ret_exc, month by month.
    pan = pd.read_parquet(C.MODEL_TABLE,
                          columns=["permno", "target_month", "ret", "ret_exc"])
    pan = pan.dropna(subset=["ret", "ret_exc"])
    pan["rf_implied"] = pan["ret"] - pan["ret_exc"]

    print("=" * 78)
    print("THE CASH LEG: is the pipeline's risk-free rate the one we benchmark to?")
    print("=" * 78)

    spread_within = pan.groupby("target_month")["rf_implied"].std(ddof=0)
    put("implied rf is constant within a month",
        "max sd %.2e" % spread_within.max(),
        "one series, not per-stock" if spread_within.max() < 1e-6 else "VARIES BY STOCK")

    rf_pipe = pan.groupby("target_month")["rf_implied"].median()
    # ret_exc is the CURRENT month; the book is scored on ret_exc_lead1m, so the
    # rate that matters for holding month t is the one attached to month t.
    rf_pipe = rf_pipe[rf_pipe.index.isin(months)]
    rf_tb = m.set_index("target_month")["cash_monthly"].reindex(rf_pipe.index)

    d = (rf_tb - rf_pipe).dropna()
    put("months compared", "%d" % len(d))
    put("3-month T-bill, annualised", "%.3f%%" % (100 * 12 * rf_tb.mean()))
    put("pipeline's own rf, annualised", "%.3f%%" % (100 * 12 * rf_pipe.mean()))
    put("difference, annualised", "%+.3f%%" % (100 * 12 * d.mean()),
        "range %+.3f%% to %+.3f%%" % (100 * 12 * d.min(), 100 * 12 * d.max()))

    print("\nWHAT THE DIFFERENCE COSTS US")
    h = pd.read_parquet(HOLDINGS)
    net = h.groupby("target_month")["weight"].sum().reindex(d.index)
    err = net * d
    put("average net exposure", "%+.1f%%" % (100 * net.mean()))
    put("error in monthly return", "%+.4f%% per month" % (100 * err.mean()),
        "net exposure x the rate difference")
    put("error, annualised", "%+.3f%%" % (100 * 12 * err.mean()),
        "worst month %+.3f%%" % (100 * err.abs().max()))

    ir = np.sqrt(12) * m["active"].mean() / m["active"].std(ddof=1)
    adj = m["active"].values - err.reindex(m["target_month"]).fillna(0.0).values
    ir_adj = np.sqrt(12) * adj.mean() / adj.std(ddof=1)
    put("information ratio as reported", "%+.4f" % ir)
    put("information ratio with the residual removed", "%+.4f" % ir_adj,
        "changes the headline by %+.4f" % (ir_adj - ir))

    print("")
    if abs(12 * err.mean()) < 0.0005:
        print("  The rates do differ. What the book carries is that gap times its")
        print("  net exposure, which is under five basis points a year and moves")
        print("  the information ratio in the third decimal. Small enough to state")
        print("  and move on -- but stated, not assumed, which is the point.")
    else:
        print("  The rates differ enough to matter. The deck must state the residual.")

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

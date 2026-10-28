"""POST-HOC (mentor review, Oct 28): index-futures beta overlay on a finished run.

    python 06_final/f11_beta_hedge.py test_M test_M_secneu
    python 06_final/f11_beta_hedge.py design_M design_M_secneu

For each run in data/runs/<label>/daily.parquet: every day, estimate the
book's beta to the S&P 500 on the previous WINDOW days only (no look-ahead),
and hold minus that beta in S&P futures. Hedged return:

    ret_h = ret - h_t * mkt_ex - FUT_COST * |h_t - h_{t-1}|

mkt_ex is the S&P 500 return over cash, which is what a fully collateralised
futures position earns. FUT_COST (1 bp of notional traded) covers commission
and slippage; margin financing is ignored. Prints IR vs the hurdle, beta and
turnover before and after, plus the sector balance if the run logged it.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402

WINDOW = 126
FUT_COST = 1e-4


def stats(ret, d):
    a = ret - d["hurdle"]
    ir = np.sqrt(252) * a.mean() / a.std(ddof=1)
    y = ret - d["rf"]
    X = np.column_stack([np.ones(len(d)), d["mkt_ex"]])
    beta = np.linalg.lstsq(X, y, rcond=None)[0][1]
    return ir, beta


def hedge(d):
    y = (d["ret"] - d["rf"]).values
    m = d["mkt_ex"].values
    h = np.zeros(len(d))
    for t in range(WINDOW, len(d)):
        yy, mm = y[t - WINDOW:t], m[t - WINDOW:t]
        h[t] = np.cov(yy, mm)[0, 1] / np.var(mm, ddof=1)
    cost = FUT_COST * np.abs(np.diff(h, prepend=0.0))
    return d["ret"].values - h * m - cost, h, cost


def main(labels):
    for lab in labels:
        d = pd.read_parquet(F.DATA / "runs" / lab / "daily.parquet")
        ir0, b0 = stats(d["ret"], d)
        ret_h, h, cost = hedge(d)
        ir1, b1 = stats(pd.Series(ret_h, index=d.index), d)
        # daily hedge ratio, so the futures leg can be added to an Arcana upload
        pd.DataFrame({"date": d["date"], "h": h}).to_csv(F.DATA / "runs" / lab / "hedge_ratio.csv", index=False)
        yrs = len(d) / 252
        print("%-24s IR %+.2f -> %+.2f   beta %+.3f -> %+.3f   avg hedge %+.2f   futures cost %.1f bp/yr"
              % (lab, ir0, ir1, b0, b1, h.mean(), 1e4 * cost.sum() / yrs))
        fp = F.DATA / "runs" / lab / "formations.parquet"
        if fp.exists():
            fl = pd.read_parquet(fp)
            if "max_abs_sector_net" in fl and fl["max_abs_sector_net"].notna().any():
                s = fl["max_abs_sector_net"].dropna()
                print("%-24s max |sector net| per formation, %% of NAV: mean %.2f, worst %.2f"
                      % ("", s.mean(), s.max()))


if __name__ == "__main__":
    main(sys.argv[1:] or ["test_M"])

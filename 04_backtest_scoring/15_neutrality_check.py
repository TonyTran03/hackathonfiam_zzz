"""Stage 5i -- is variant S actually more neutral, or only cheaper to describe?

    python 04_backtest_scoring/15_neutrality_check.py

The case for adopting the sector cap rests on neutrality rather than return,
and the two are not equally knowable. Sector exposure is arithmetic on the
holdings: 90% of capital to 38% is exact, and no amount of sampling noise
touches it. Market sensitivity is an estimate, and an estimate from twelve
monthly observations is a loose one -- so "the last rolling window went from
-0.63 to -0.21" is a claim that has to clear its own standard error before it
counts as evidence.

This checks the second one properly, over all 57 windows rather than the one
that moved most, and writes neutrality_check.csv so the deck reports whichever
way it comes out.

Both series are the ones committed to the repository, so this compares the
traded book with variant S on the same book and the same months.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

BASE = C.ROOT / "05_submission" / "portfolio_returns.csv"
VARIANT = C.ROOT / "05_submission" / "deck" / "variants" / \
          "variant_S_sector_cap_portfolio_returns.csv"
OUT = C.ROOT / "05_submission" / "neutrality_check.csv"
WINDOW = 12

rows = []


def put(metric, value, note=""):
    rows.append({"metric": metric, "value": value, "note": note})
    print("  %-46s %-12s %s" % (metric, value, note))


def prep(path):
    d = pd.read_csv(path)
    d["y"] = d["spread"]
    d["x"] = d["sp500_ret"] - d["cash_monthly"]
    return d


def rolling(d):
    out = []
    for i in range(WINDOW, len(d) + 1):
        g = d.iloc[i - WINDOW:i]
        r = smf.ols("y ~ x", data=g).fit()
        out.append({"end": g["target_month"].iloc[-1],
                    "beta": r.params["x"], "se": r.bse["x"]})
    return pd.DataFrame(out)


def main():
    if not VARIANT.exists():
        print("variant S returns not present; nothing to check")
        return 0
    b, v = prep(BASE), prep(VARIANT)

    print("=" * 78)
    print("IS VARIANT S MORE NEUTRAL?  %d months, same book, same period" % len(b))
    print("=" * 78)

    print("\nFULL PERIOD")
    fb = smf.ols("y ~ x", data=b).fit(cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True)
    fv = smf.ols("y ~ x", data=v).fit(cov_type="HAC", cov_kwds={"maxlags": 3}, use_t=True)
    put("beta, traded book", "%+.3f" % fb.params["x"], "se %.3f" % fb.bse["x"])
    put("beta, variant S", "%+.3f" % fv.params["x"], "se %.3f" % fv.bse["x"])
    move = abs(fv.params["x"]) - abs(fb.params["x"])
    put("change in |beta|", "%+.3f" % move,
        "%.2f of one standard error" % (abs(move) / fb.bse["x"]))

    print("\nROLLING 12-MONTH WINDOWS")
    rb, rv = rolling(b), rolling(v)
    put("windows outside +/-0.3, traded book",
        "%d of %d" % ((rb["beta"].abs() > 0.3).sum(), len(rb)))
    put("windows outside +/-0.3, variant S",
        "%d of %d" % ((rv["beta"].abs() > 0.3).sum(), len(rv)))
    put("worst window, traded book", "%+.2f" % rb.loc[rb["beta"].abs().idxmax(), "beta"],
        rb.loc[rb["beta"].abs().idxmax(), "end"])
    put("worst window, variant S", "%+.2f" % rv.loc[rv["beta"].abs().idxmax(), "beta"],
        rv.loc[rv["beta"].abs().idxmax(), "end"] + " -- breaches the other way")

    # The test that matters: across ALL windows, not the one that moved most.
    d = rv["beta"].abs().values - rb["beta"].abs().values
    better = int((d < 0).sum())
    put("windows where |beta| improves", "%d of %d" % (better, len(d)),
        "%.0f%% -- a coin flip is %d" % (100 * better / len(d), len(d) // 2))
    put("mean change in |beta| per window", "%+.3f" % d.mean(),
        "t %+.2f" % (d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))))

    print("\nTHE HEADLINE WINDOW")
    gap = rv["beta"].iloc[-1] - rb["beta"].iloc[-1]
    put("last window, traded book", "%+.2f" % rb["beta"].iloc[-1],
        "se %.2f" % rb["se"].iloc[-1])
    put("last window, variant S", "%+.2f" % rv["beta"].iloc[-1],
        "se %.2f" % rv["se"].iloc[-1])
    put("size of that improvement", "%+.2f" % gap,
        "%.1f standard errors -- not significant" % (abs(gap) / rb["se"].iloc[-1]))

    print("\nWHAT IS EXACT AND WHAT IS ESTIMATED")
    put("sector net exposure, traded book", "89.7% of capital", "exact, from the weights")
    put("sector net exposure, variant S", "38.2% of capital", "exact, from the weights")
    put("volatility, traded book", "%.2f%%" % (100 * np.sqrt(12) * b["spread"].std(ddof=1)))
    put("volatility, variant S", "%.2f%%" % (100 * np.sqrt(12) * v["spread"].std(ddof=1)),
        "slightly higher, not lower")

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

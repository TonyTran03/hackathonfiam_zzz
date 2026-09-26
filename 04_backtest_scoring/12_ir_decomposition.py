"""Stage 5h -- when the information ratio moves, did return or risk move it?

    python 04_backtest_scoring/12_ir_decomposition.py BASE.csv NEW.csv

The information ratio is a ratio, so any change in it is two changes wearing
one number: the active return in the numerator and its volatility in the
denominator. A constraint that removes uncompensated risk should show up
almost entirely in the denominator, and should cost a little in the numerator.
If instead the numerator jumps, the constraint is not doing what it claims and
the implementation is worth re-reading before the result is trusted.

Both effects are reported as IR points that sum exactly to the observed move,
using the symmetric two-factor split: each factor is credited with the average
of its effect applied first and applied last, which is the only split of a
product that does not depend on the order you take them in.

Each file needs `target_month` and `active`; the pipeline's
05_submission/portfolio_returns.csv is already in that form.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANN = np.sqrt(12)


def load(path):
    d = pd.read_csv(path)
    for c in ("target_month", "active"):
        if c not in d.columns:
            raise SystemExit("%s has no '%s' column" % (path, c))
    return d[["target_month", "active"]].dropna().sort_values("target_month")


def ir(mean, sd):
    return ANN * mean / sd


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__)
    a, b = load(argv[0]), load(argv[1])

    # Compare like with like: the same months, or the conclusion is a calendar
    # difference dressed up as an improvement.
    common = sorted(set(a.target_month) & set(b.target_month))
    if len(common) < len(a) or len(common) < len(b):
        print("NOTE  %d months in base, %d in new, %d shared -- comparing the shared set"
              % (len(a), len(b), len(common)))
    a = a[a.target_month.isin(common)].reset_index(drop=True)
    b = b[b.target_month.isin(common)].reset_index(drop=True)

    m0, s0 = a.active.mean(), a.active.std(ddof=1)
    m1, s1 = b.active.mean(), b.active.std(ddof=1)
    ir0, ir1 = ir(m0, s0), ir(m1, s1)

    print("=" * 70)
    print("IR DECOMPOSITION  %s .. %s  (%d months)" % (common[0], common[-1], len(common)))
    print("=" * 70)
    print("  %-34s %12s %12s" % ("", "base", "new"))
    print("  %-34s %11.3f%% %11.3f%%" % ("active return, monthly mean", 100 * m0, 100 * m1))
    print("  %-34s %11.3f%% %11.3f%%" % ("active return, monthly sd", 100 * s0, 100 * s1))
    print("  %-34s %11.2f%% %11.2f%%" % ("annualised active return", 100 * 12 * m0, 100 * 12 * m1))
    print("  %-34s %11.2f%% %11.2f%%" % ("annualised volatility", 100 * ANN * s0, 100 * ANN * s1))
    print("  %-34s %12.2f %12.2f" % ("information ratio", ir0, ir1))

    # Symmetric split of the move into its two causes.
    ret_first = ir(m1, s0) - ir0
    ret_last = ir1 - ir(m0, s1)
    vol_first = ir(m0, s1) - ir0
    vol_last = ir1 - ir(m1, s0)
    ret = 0.5 * (ret_first + ret_last)
    vol = 0.5 * (vol_first + vol_last)
    total = ir1 - ir0

    print("\n  total move %+.2f IR points, split into:" % total)
    print("    higher/lower return   %+.2f  (%.0f%% of the move)"
          % (ret, 100 * ret / total if total else 0))
    print("    higher/lower risk     %+.2f  (%.0f%% of the move)"
          % (vol, 100 * vol / total if total else 0))
    print("    check: %+.2f + %+.2f = %+.2f" % (ret, vol, ret + vol))

    print("\n  %-34s %+11.1f%% %s" % ("change in active return",
          100 * (m1 / m0 - 1) if m0 else float("nan"), ""))
    print("  %-34s %+11.1f%%" % ("change in volatility", 100 * (s1 / s0 - 1)))

    print("")
    if abs(total) < 0.02:
        print("  NO MATERIAL CHANGE: the information ratio moved less than 0.02 points.")
        return 0
    share = abs(vol) / (abs(vol) + abs(ret)) if (vol or ret) else 0
    if share > 0.7:
        print("  READS AS RISK REDUCTION: the move is mostly the denominator, which is")
        print("  what removing an uncompensated exposure is supposed to look like.")
    elif share < 0.3:
        print("  READS AS A RETURN INCREASE: a constraint that is meant to remove risk")
        print("  should not raise the numerator this much. Re-read the implementation")
        print("  before quoting the new number -- check that the constraint uses only")
        print("  information available at the rebalance date.")
    else:
        print("  MIXED: return and risk both moved materially. Worth saying which is")
        print("  which on the slide rather than quoting the ratio alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Check the scoring arithmetic against answers worked out by hand.

test_checks.py proves the compliance checker notices a broken book. Nothing
proved the SCORING was right, and every number on pages 4 to 7 of the deck
comes out of stage 5. A wrong sign or a stray factor of two there would reach
the judges unchallenged.

Each case below has an answer computable on paper, so a failure here means the
scorer is wrong, not that the data drifted.

    python tests/test_scoring.py
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import checks
from common import config as C


def _load(relpath, name):
    """Stage scripts start with a digit, so they cannot be imported normally."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load("04_backtest_scoring/05_evaluate.py", "stage5_evaluate")

FAILURES = []


def expect(condition, description, got=None):
    if condition:
        print("  [ ok ] %s" % description)
        return True
    detail = "" if got is None else "   got: %s" % (got,)
    print("  [FAIL] %s%s" % (description, detail))
    FAILURES.append(description)
    return False


def close(a, b, tol=1e-12):
    return abs(float(a) - float(b)) <= tol


# --------------------------------------------------------------------------
# monthly_returns
# --------------------------------------------------------------------------

def book(rows):
    """rows: (target_month, permno, weight, target_return_or_None)"""
    return pd.DataFrame(
        [{"target_month": m, "permno": p, "weight": w, C.TARGET: r}
         for m, p, w, r in rows]
    )


def test_monthly_returns():
    print("\nmonthly_returns")

    # 0.5 * 10% + (-0.5) * 2% = 5% - 1% = 4%
    h = book([("2021-01", 1, 0.5, 0.10), ("2021-01", 2, -0.5, 0.02)])
    m = ev.monthly_returns(h)
    expect(close(m["spread"].iloc[0], 0.04), "spread is the weighted excess-return sum",
           m["spread"].iloc[0])
    expect(close(m["long_leg"].iloc[0], 0.05), "long leg is the positive-weight contribution",
           m["long_leg"].iloc[0])
    expect(close(m["short_leg"].iloc[0], -0.01), "short leg is the negative-weight contribution",
           m["short_leg"].iloc[0])
    expect(close(m["long_leg"].iloc[0] + m["short_leg"].iloc[0], m["spread"].iloc[0]),
           "the two legs sum back to the spread")

    expect(close(m["gross"].iloc[0], 1.0), "gross is the sum of absolute weights",
           m["gross"].iloc[0])
    expect(close(m["net"].iloc[0], 0.0), "net is the signed sum", m["net"].iloc[0])
    expect(close(m["max_abs_w"].iloc[0], 0.5), "max_abs_w is the largest absolute weight")
    expect(int(m["n"].iloc[0]) == 2, "n counts positions")

    # A short that pays off must ADD to the spread. Sign errors here are the
    # classic way a long-short backtest ends up backwards.
    h = book([("2021-01", 1, 0.5, 0.0), ("2021-01", 2, -0.5, -0.20)])
    m = ev.monthly_returns(h)
    expect(close(m["spread"].iloc[0], 0.10),
           "a short position gains when the stock falls", m["spread"].iloc[0])


def test_missing_returns_are_counted_and_filled():
    print("\nmissing (delisted) returns")

    h = book([("2021-01", 1, 0.5, 0.10), ("2021-01", 2, -0.5, None)])
    m = ev.monthly_returns(h)
    expect(int(m["n_missing_ret"].iloc[0]) == 1,
           "a position with no realised return is counted")
    # Current convention is a zero fill, so the missing short contributes nothing.
    expect(close(m["spread"].iloc[0], 0.05),
           "the documented zero fill is what the scorer actually applies",
           m["spread"].iloc[0])
    expect(C.TEAM["delisting_return"] == 0.0,
           "config.TEAM records the zero fill so the sensitivity is a one-line change")

    # The scorer must READ the mark from config, not hardcode it. Flip it to
    # the Shumway -30% and the missing short (weight -0.5) must now gain 0.15.
    saved = C.TEAM["delisting_return"]
    try:
        C.TEAM["delisting_return"] = -0.30
        m = ev.monthly_returns(h)
        expect(close(m["spread"].iloc[0], 0.05 + 0.15),
               "a -30% delisting mark on a missing short adds |w| * 0.30 to the spread",
               m["spread"].iloc[0])
    finally:
        C.TEAM["delisting_return"] = saved


# --------------------------------------------------------------------------
# turnover
# --------------------------------------------------------------------------

def test_turnover():
    print("\nturnover")

    # Same book two months running: nothing traded.
    h = book([("2021-01", 1, 0.5, 0.0), ("2021-01", 2, -0.5, 0.0),
              ("2021-02", 1, 0.5, 0.0), ("2021-02", 2, -0.5, 0.0)])
    t = ev.turnover(h)
    expect(close(t.iloc[0], 0.0), "an unchanged book has zero turnover", t.iloc[0])

    # Swap both names for two others: the whole book is replaced.
    # changed = |0-0.5| + |0-(-0.5)| + |0.5-0| + |-0.5-0| = 2.0
    # gross in month 2 = 1.0, so one-way turnover = 2.0 / (2 * 1.0) = 1.0
    h = book([("2021-01", 1, 0.5, 0.0), ("2021-01", 2, -0.5, 0.0),
              ("2021-02", 3, 0.5, 0.0), ("2021-02", 4, -0.5, 0.0)])
    t = ev.turnover(h)
    expect(close(t.iloc[0], 1.0), "replacing the whole book is 100% one-way turnover",
           t.iloc[0])

    # Replace half the long leg only.
    # changed = |0.25-0.5| + |0.25-0| = 0.5; gross = 1.0; one-way = 0.25
    h = book([("2021-01", 1, 0.5, 0.0), ("2021-01", 2, -0.5, 0.0),
              ("2021-02", 1, 0.25, 0.0), ("2021-02", 3, 0.25, 0.0),
              ("2021-02", 2, -0.5, 0.0)])
    t = ev.turnover(h)
    expect(close(t.iloc[0], 0.25), "swapping half the long leg is 25% one-way turnover",
           t.iloc[0])

    expect(len(t) == 1,
           "the first month is dropped, so the entry trade is not charged as turnover")


# --------------------------------------------------------------------------
# drawdown
# --------------------------------------------------------------------------

def test_drawdown():
    print("\ndrawdown")

    # 1.10, then 0.88, then 0.792, then 0.8316
    # worst = 0.792 / 1.10 - 1 = -0.28
    r = pd.Series([0.10, -0.20, -0.10, 0.05])
    dd = ev.drawdown(r)
    expect(close(dd.min(), -0.28, 1e-12), "peak-to-trough, not start-to-trough", dd.min())
    expect(dd.idxmin() == 2, "the trough is located at the right month", dd.idxmin())
    expect(close(dd.iloc[0], 0.0), "a new high is zero drawdown, not positive")

    expect(close(ev.drawdown(pd.Series([0.01] * 12)).min(), 0.0),
           "a monotonically rising curve never draws down")


# --------------------------------------------------------------------------
# the headline ratios, recomputed the way stage 5 does
# --------------------------------------------------------------------------

def test_information_ratio_definition():
    print("\ninformation ratio")

    rng = np.random.default_rng(11)
    active = pd.Series(rng.normal(0.004, 0.02, 60))
    ir = np.sqrt(12) * active.mean() / active.std(ddof=1)

    # Same series, scaled up. The IR is scale-free, so it must not move.
    ir_scaled = np.sqrt(12) * (3 * active).mean() / (3 * active).std(ddof=1)
    expect(close(ir, ir_scaled, 1e-9), "the information ratio is scale-free", ir_scaled)

    # An IR computed on TOTAL return rather than ACTIVE return would be a
    # different, larger number. The rules ask for the active one.
    cash = 0.0031
    total = active + cash + C.COMPETITION["benchmark_premium_annual"] / 12
    ir_wrong = np.sqrt(12) * total.mean() / total.std(ddof=1)
    expect(ir_wrong > ir,
           "scoring total return instead of active return would flatter the IR",
           "%.2f vs %.2f" % (ir_wrong, ir))


def test_oos_r2_benchmarks_against_zero():
    print("\nout-of-sample R2")

    def r2(y, yhat):
        y, yhat = np.asarray(y, float), np.asarray(yhat, float)
        return 1 - np.sum((y - yhat) ** 2) / np.sum(y ** 2)

    y = np.array([0.02, -0.01, 0.03, -0.02])
    expect(close(r2(y, y), 1.0), "a perfect forecast scores 1.0")
    expect(close(r2(y, np.zeros_like(y)), 0.0),
           "a zero forecast scores exactly 0, because zero IS the benchmark")

    # Under the textbook definition, forecasting the mean scores 0. Under the
    # rules' definition it scores n*mean^2 / sum(y^2), which is positive.
    # If this came out as 0.0 the denominator has been demeaned by mistake.
    mean_forecast = np.full_like(y, y.mean())
    expected = len(y) * y.mean() ** 2 / np.sum(y ** 2)
    expect(close(r2(y, mean_forecast), expected),
           "the denominator is sum(y^2), NOT the demeaned sum of squares",
           r2(y, mean_forecast))
    expect(r2(y, -y) < 0, "a systematically inverted forecast scores below zero")


# --------------------------------------------------------------------------
# beta neutrality
# --------------------------------------------------------------------------

MONTHS = list(pd.period_range(C.COMPETITION["oos_start"], C.COMPETITION["oos_end"],
                              freq="M").astype(str))


def holdings_with_betas(long_beta, short_beta, n=110, gross=2.0):
    """A dollar-neutral book whose two legs carry the betas we choose."""
    rows = []
    for m in MONTHS:
        for i in range(n):
            rows.append((m, 10000 + i, gross / 2 / n, long_beta))
            rows.append((m, 20000 + i, -gross / 2 / n, short_beta))
    return pd.DataFrame(rows, columns=["target_month", "permno", "weight", "beta"])


def levels(findings, substring):
    return [f.level for f in findings if substring in f.check]


def test_beta_neutrality():
    print("\nbeta neutrality")

    # Both legs beta 1.0: dollar neutral AND beta neutral.
    f, stats = checks.check_holdings(holdings_with_betas(1.0, 1.0))
    expect("OK" in levels(f, "beta neutrality"), "a genuinely neutral book passes")
    expect(close(stats["beta_net"].abs().max(), 0.0, 1e-12),
           "beta-weighted net is zero when the legs match", stats["beta_net"].abs().max())

    # The trap from the rules: long high-beta, short low-beta, still dollar
    # neutral. beta_net = 1.0*1.8 + (-1.0)*0.4 = +1.4
    f, stats = checks.check_holdings(holdings_with_betas(1.8, 0.4))
    expect("FAIL" in levels(f, "beta neutrality"),
           "a dollar-neutral book long high-beta names is caught")
    expect(close(stats["beta_net"].iloc[0], 1.4, 1e-9),
           "beta-weighted net is computed correctly", stats["beta_net"].iloc[0])
    expect("FAIL" not in levels(f, "net exposure"),
           "and the net-exposure rule alone does NOT catch it -- that is the point")

    # A mild tilt should warn, not fail. 1.0*1.15 - 1.0*1.0 = +0.15
    f, _ = checks.check_holdings(holdings_with_betas(1.15, 1.0))
    expect("WARN" in levels(f, "beta neutrality"), "a mild beta tilt warns")
    expect("FAIL" not in levels(f, "beta neutrality"), "a mild beta tilt does not fail")

    # Short high-beta, long low-beta: negative exposure, equally directional.
    f, _ = checks.check_holdings(holdings_with_betas(0.4, 1.8))
    expect("FAIL" in levels(f, "beta neutrality"),
           "a negative beta tilt is caught too, not just a positive one")

    # No beta column at all: the checker must say so rather than stay quiet.
    no_beta = holdings_with_betas(1.0, 1.0).drop(columns="beta")
    f, _ = checks.check_holdings(no_beta)
    expect("WARN" in levels(f, "beta neutrality"),
           "a missing beta column warns instead of silently passing")

    # Partial coverage must be flagged, because zero-filling understates it.
    partial = holdings_with_betas(1.8, 0.4)
    partial.loc[partial.index[:50], "beta"] = np.nan
    f, _ = checks.check_holdings(partial)
    expect("WARN" in levels(f, "beta coverage"), "missing betas are reported")


def test_beta_thresholds_are_house_standards_not_rules():
    print("\nconfig hygiene")
    expect("beta_net_warn" not in C.COMPETITION and "beta_net_fail" not in C.COMPETITION,
           "beta thresholds are NOT in COMPETITION, which transcribes the PDF")
    expect("beta_net_warn" in C.TEAM and "beta_net_fail" in C.TEAM,
           "they live in TEAM, so the report can distinguish rule from house standard")
    expect(C.TEAM["beta_net_warn"] < C.TEAM["beta_net_fail"],
           "the warn threshold is tighter than the fail threshold")

    f, _ = checks.check_holdings(holdings_with_betas(1.8, 0.4))
    named = [x for x in f if "beta neutrality" in x.check]
    expect(all("not a rule" in x.check for x in named),
           "the finding says on its face that it is not a competition rule")


def main():
    for fn in (test_monthly_returns,
               test_missing_returns_are_counted_and_filled,
               test_turnover,
               test_drawdown,
               test_information_ratio_definition,
               test_oos_r2_benchmarks_against_zero,
               test_beta_neutrality,
               test_beta_thresholds_are_house_standards_not_rules):
        fn()

    print()
    if FAILURES:
        print("%d CHECK(S) FAILED:" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("ALL SCORING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

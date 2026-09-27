"""Deliberately break things, and prove the checker notices.

A checker nobody has tested is worse than no checker, because it tells you
everything is fine. Run this whenever checks.py changes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import checks
from common import config as C

RNG = np.random.default_rng(0)
MONTHS = list(pd.period_range(C.COMPETITION["oos_start"], C.COMPETITION["oos_end"],
                              freq="M").astype(str))


def clean_holdings(n_long=110, n_short=110, gross=2.0, long_beta=1.0, short_beta=1.0):
    """A book that obeys every rule: dollar neutral, 220 names, 200% gross.

    Both legs carry beta 1.0 by default, so the book is beta neutral as well
    as dollar neutral and check_beta_neutrality has something to pass on.
    Override the betas to build the disguised-directional case; the dedicated
    tests for that live in test_scoring.py.
    """
    rows = []
    for m in MONTHS:
        longs = np.arange(10000, 10000 + n_long)
        shorts = np.arange(20000, 20000 + n_short)
        wl = gross / 2 / n_long
        ws = gross / 2 / n_short
        for p in longs:
            rows.append((m, p, wl, long_beta))
        for p in shorts:
            rows.append((m, p, -ws, short_beta))
    return pd.DataFrame(rows, columns=["target_month", "permno", "weight", "beta"])


def fake_panel(df):
    tm = pd.DataFrame({"target_month": np.repeat(MONTHS, 3)})
    tm["permno"] = 0
    return df[["permno", "target_month"]].drop_duplicates()


def levels(findings, check_substring):
    return [f.level for f in findings if check_substring in f.check]


def expect(cond, label):
    print(("  PASS  " if cond else "  ** MISSED **  ") + label)
    return bool(cond)


def main():
    ok = True
    features = sorted(checks.allowed_features())

    print("\n=== look-ahead checks ===")
    f = checks.check_features(features)
    ok &= expect(all(x.level == "OK" for x in f), "clean 147-predictor list passes")

    f = checks.check_features(features + [C.TARGET])
    ok &= expect("FAIL" in levels(f, "target-as-predictor"), "answer column used as a predictor")

    f = checks.check_features(features + ["ret_exc"])
    ok &= expect("WARN" in levels(f, "same-month returns"), "same-month return slipped in")

    f = checks.check_features(features + ["my_secret_signal"])
    ok &= expect("WARN" in levels(f, "outside the supplied list"), "undocumented outside predictor")

    f = checks.check_features(features + [features[0]])
    ok &= expect("FAIL" in levels(f, "duplicate predictors"), "duplicated predictor")

    # a tiny panel keyed by target month, with a realized answer everywhere
    panel = pd.DataFrame({
        "target_month": np.repeat(pd.period_range("2015-02", "2026-08", freq="M").astype(str), 5),
    })
    panel["permno"] = np.tile(np.arange(5), len(panel) // 5)
    panel[C.TARGET] = RNG.normal(0, 0.1, len(panel))

    tm = panel["target_month"]
    train = tm <= "2018-12"
    val = (tm >= "2019-01") & (tm <= "2020-12")
    test = (tm >= "2021-01") & (tm <= "2021-12")

    f = checks.check_split(panel, train, val, test, "2021")
    ok &= expect(all(x.level == "OK" for x in f), "correct split passes")

    leaky_train = tm <= "2021-06"      # training on months inside the test year
    f = checks.check_split(panel, leaky_train, val, test, "leaky")
    ok &= expect("FAIL" in levels(f, "future answers in train"), "training on test-period answers")

    f = checks.check_split(panel, train, train, test, "overlap")
    ok &= expect("FAIL" in levels(f, "train/val overlap"), "same rows in train and validation")

    # the classic: split by feature month instead of target month, so the
    # December-2020 row (whose answer is January 2021) lands in training
    feature_month_split = tm <= "2021-01"
    f = checks.check_split(panel, feature_month_split, val, test, "by-eom")
    ok &= expect("FAIL" in levels(f, "future answers in train"), "split keyed on the wrong month")

    f = checks.check_fit_rows(train | val, panel, "2018-12", "fit")
    ok &= expect("FAIL" in levels(f, "preprocessing fitted on future"),
                 "scaler fitted on validation data too")

    f = checks.check_fit_rows(train, panel, "2018-12", "fit")
    ok &= expect(all(x.level == "OK" for x in f), "scaler fitted on training months only")

    print("\n=== trading-criteria checks ===")
    good = clean_holdings()
    f, stats = checks.check_holdings(good, panel=fake_panel(good))
    ok &= expect(all(x.level == "OK" for x in f), "compliant book passes all four limits")

    thin = clean_holdings(n_long=40, n_short=40)
    f, _ = checks.check_holdings(thin)
    ok &= expect("FAIL" in levels(f, "position count"), "only 80 names")

    fat = clean_holdings(n_long=300, n_short=300)
    f, _ = checks.check_holdings(fat)
    ok &= expect("FAIL" in levels(f, "position count"), "600 names")

    levered = clean_holdings(gross=2.4)
    f, _ = checks.check_holdings(levered)
    ok &= expect("FAIL" in levels(f, "gross exposure"), "240% gross exposure")

    # drift the book long: 150% long against 50% short
    tilted = clean_holdings()
    tilted.loc[tilted["weight"] > 0, "weight"] *= 1.5
    tilted.loc[tilted["weight"] < 0, "weight"] *= 0.5
    f, _ = checks.check_holdings(tilted)
    ok &= expect("FAIL" in levels(f, "net exposure"), "+100% net exposure")

    long_only = clean_holdings()
    long_only["weight"] = long_only["weight"].abs() / 2
    f, _ = checks.check_holdings(long_only)
    ok &= expect("FAIL" in levels(f, "not long/short"), "long-only book")

    gap = clean_holdings()
    gap = gap[gap["target_month"] != "2022-07"]
    f, _ = checks.check_holdings(gap)
    ok &= expect("FAIL" in levels(f, "missing months"), "a month with no holdings")

    dupes = pd.concat([good, good.head(3)])
    f, _ = checks.check_holdings(dupes)
    ok &= expect("FAIL" in levels(f, "duplicate positions"), "same stock twice in one month")

    concentrated = clean_holdings(n_long=55, n_short=55)   # ~1.8% each, then spike one
    concentrated.loc[concentrated.index[0], "weight"] = 0.25
    f, _ = checks.check_holdings(concentrated)
    ok &= expect("WARN" in levels(f, "single-position size"), "25% in a single name")

    ghost = good.copy()
    ghost.loc[ghost.index[0], "permno"] = 999999
    f, _ = checks.check_holdings(ghost, panel=fake_panel(good))
    ok &= expect("FAIL" in levels(f, "untradable positions"), "a stock not in the panel")

    # The rules' own warning: dollar neutral is not the same as neutral. This
    # book breaks no numeric rule, so every check above passes it.
    disguised = clean_holdings(long_beta=1.8, short_beta=0.4)
    f, _ = checks.check_holdings(disguised)
    ok &= expect("FAIL" in levels(f, "beta neutrality"),
                 "long high-beta / short low-beta, still dollar neutral")
    ok &= expect("FAIL" not in levels(f, "net exposure"),
                 "  ...and no other check catches it")

    f, _ = checks.check_holdings(good.drop(columns="beta"))
    ok &= expect("WARN" in levels(f, "beta neutrality"),
                 "a book with no betas warns rather than silently passing")

    print("\n" + ("ALL CHECKS BEHAVED AS EXPECTED" if ok else "SOME CHECKS FAILED TO FIRE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Stage 3 -- fit the baseline models and predict next-month excess returns.

Deliberately the simplest thing that respects the rules: four linear models,
refit once a year on an expanding window, with the penalty chosen on a rolling
two-year validation block. This exists to produce a number to beat, not to win.

Discipline enforced here, and checked by run_checks.py:

  splits are keyed on target_month, never on eom
  the scaler is fitted on training rows only
  training rows need a realized answer; TEST ROWS DO NOT -- every stock in the
    month gets a prediction, so the outcome never decides the universe
"""
import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

FEATURES_FILE = C.PROCESSED_DIR / "features_ranked.parquet"
SPARSE_FILE = C.PROCESSED_DIR / "features_ranked_sparse.parquet"
OUT = C.PROCESSED_DIR / "predictions.parquet"

# Coarse grids: this is a baseline, and a finer search is not what decides the
# competition. Refine once something depends on it.
LASSO_GRID = np.logspace(-5, -1, 13)
RIDGE_GRID = np.logspace(0, 6, 13)
EN_GRID = np.logspace(-5, -1, 13)
MAX_ITER = 3000

LINEAR_MODELS = ["ols", "lasso", "ridge", "en"]
MODELS = LINEAR_MODELS + ["gbm"]

# Gradient-boosted trees, trained on the table that KEEPS missing values.
# Filling a blank R&D ratio with the month's median asserts "average R&D" when
# the truth is usually "no R&D line at all"; a tree learns which way to send a
# missing value at each split and needs no invented number. Shallow trees and
# a small learning rate because the signal here is tiny -- the whole panel
# carries an out-of-sample R2 measured in hundredths of a percent, so anything
# with capacity to spare memorises noise.
GBM_GRID = [
    dict(num_leaves=15, min_child_samples=500, learning_rate=0.02),
    dict(num_leaves=31, min_child_samples=200, learning_rate=0.02),
    dict(num_leaves=63, min_child_samples=100, learning_rate=0.01),
]
GBM_FIXED = dict(objective="l2", n_estimators=3000, subsample=0.7,
                 subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
                 verbose=-1, n_jobs=-1)
GBM_EARLY_STOP = 50


def demean_and_clip(y, months, clip=3.0):
    """Remove each month's cross-sectional mean, then trim the tails.

    Fitting raw monthly returns does not work. Almost all of their variance is
    the month itself -- everything rises and falls together -- and no stock
    characteristic predicts that. Worse, boosting starts from the TRAINING mean
    return, so when the validation years have a different average the level is
    wrong from the first tree and validation error rises immediately. The first
    attempt here stopped after one round for exactly that reason.

    Subtracting the month's own mean leaves only the cross-sectional part,
    which is the only part a long/short book trades. It is computed within a
    single month across stocks, so it looks at no other period.

    Clipping matters too: holdings in this panel run past +1200% in a month,
    and squared error would let a handful of them write the model.
    """
    s = pd.Series(y).groupby(months.values).transform(lambda v: v - v.mean())
    sd = s.std(ddof=0)
    return s.clip(-clip * sd, clip * sd).values


def fit_gbm(Xtr, ytr, Xva, yva, Xte):
    """Pick the configuration and the tree count on the validation block."""
    best, best_mse, best_rounds, best_cfg = None, np.inf, 0, None
    for cfg in GBM_GRID:
        m = lgb.LGBMRegressor(**GBM_FIXED, **cfg)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="l2",
              callbacks=[lgb.early_stopping(GBM_EARLY_STOP, verbose=False)])
        mse = np.mean((yva - m.predict(Xva)) ** 2)
        if mse < best_mse:
            best, best_mse, best_rounds, best_cfg = m, mse, m.best_iteration_, cfg
    return best.predict(Xte), best.predict(Xva), best_rounds, best_cfg


def monthly_ic(df, col, target):
    """Average within-month rank correlation with the realized return."""
    ok = df[df[target].notna()]
    return ok.groupby("target_month").apply(
        lambda d: d[col].corr(d[target], method="spearman"),
        include_groups=False).mean()


def choose_blend(val):
    """Decide what to trade using the VALIDATION blocks only.

    The tree and the linear models could be combined, or the tree traded on
    its own. Reading that off the test period is how a backtest gets chosen
    rather than measured, so the comparison happens here, on data the final
    scoring never sees.
    """
    candidates = {
        "gbm": ["gbm"],
        "avg_linear": LINEAR_MODELS,
        "avg": ["avg_linear", "gbm"],
        "ridge_gbm": ["ridge", "gbm"],
    }
    scores = {}
    for name, parts in candidates.items():
        z = val.groupby("target_month")[parts].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
        tmp = val.assign(_blend=z.mean(axis=1))
        scores[name] = monthly_ic(tmp, "_blend", C.TARGET)
    print("\nblend selection, on the VALIDATION blocks only:")
    for name, ic in sorted(scores.items(), key=lambda kv: -kv[1]):
        print("  %-12s validation rank correlation %+.4f" % (name, ic))
    winner = max(scores, key=scores.get)
    print("  -> trading '%s'" % winner)
    return winner, candidates[winner]


def pick_penalty(make, grid, Xtr, ytr, Xva, yva, ymean):
    best, best_mse = grid[0], np.inf
    for a in grid:
        m = make(a).fit(Xtr, ytr)
        mse = np.mean((yva - (m.predict(Xva) + ymean)) ** 2)
        if mse < best_mse:
            best, best_mse = a, mse
    return best


def run():
    if not FEATURES_FILE.exists():
        raise SystemExit("missing %s -- run 01_data/02_make_features.py first" % FEATURES_FILE)

    features = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    df = pd.read_parquet(FEATURES_FILE,
                         columns=["permno", "target_month", C.TARGET] + features)
    sparse = pd.read_parquet(SPARSE_FILE,
                             columns=["permno", "target_month"] + features)
    assert (df["permno"].values == sparse["permno"].values).all() \
        and (df["target_month"].values == sparse["target_month"].values).all(), \
        "the filled and sparse feature tables are not row-aligned"
    tm = df["target_month"]
    answered = df[C.TARGET].notna()

    out, val_out = [], []
    for train_end, val_start, val_end, test_start, test_end in C.training_schedule():
        t0 = time.time()
        train = (tm <= train_end) & answered
        val = (tm >= val_start) & (tm <= val_end) & answered
        test = (tm >= test_start) & (tm <= test_end)          # answered or not

        scaler = StandardScaler().fit(df.loc[train, features])
        Xtr = scaler.transform(df.loc[train, features]).astype(np.float32)
        Xva = scaler.transform(df.loc[val, features]).astype(np.float32)
        Xte = scaler.transform(df.loc[test, features]).astype(np.float32)
        ytr = df.loc[train, C.TARGET].values
        yva = df.loc[val, C.TARGET].values

        # fitted without an intercept, so centre the answer on the training mean
        ymean = ytr.mean()
        ytr_c = ytr - ymean

        preds = df.loc[test, ["permno", "target_month", C.TARGET]].copy()
        vpred = df.loc[val, ["permno", "target_month", C.TARGET]].copy()

        m = LinearRegression(fit_intercept=False).fit(Xtr, ytr_c)
        preds["ols"], vpred["ols"] = m.predict(Xte) + ymean, m.predict(Xva) + ymean

        a = pick_penalty(lambda v: Lasso(alpha=v, max_iter=MAX_ITER, fit_intercept=False),
                         LASSO_GRID, Xtr, ytr_c, Xva, yva, ymean)
        m = Lasso(alpha=a, max_iter=MAX_ITER, fit_intercept=False).fit(Xtr, ytr_c)
        preds["lasso"], vpred["lasso"] = m.predict(Xte) + ymean, m.predict(Xva) + ymean

        r = pick_penalty(lambda v: Ridge(alpha=v, fit_intercept=False),
                         RIDGE_GRID, Xtr, ytr_c, Xva, yva, ymean)
        m = Ridge(alpha=r, fit_intercept=False).fit(Xtr, ytr_c)
        preds["ridge"], vpred["ridge"] = m.predict(Xte) + ymean, m.predict(Xva) + ymean

        e = pick_penalty(lambda v: ElasticNet(alpha=v, max_iter=MAX_ITER, fit_intercept=False),
                         EN_GRID, Xtr, ytr_c, Xva, yva, ymean)
        m = ElasticNet(alpha=e, max_iter=MAX_ITER, fit_intercept=False).fit(Xtr, ytr_c)
        preds["en"], vpred["en"] = m.predict(Xte) + ymean, m.predict(Xva) + ymean

        # trees get the un-filled table and a month-demeaned, clipped answer
        gbm_test, gbm_val, rounds, cfg = fit_gbm(
            sparse.loc[train, features], demean_and_clip(ytr, tm[train]),
            sparse.loc[val, features], demean_and_clip(yva, tm[val]),
            sparse.loc[test, features])
        # add the training mean back so the column is a return forecast again
        preds["gbm"], vpred["gbm"] = gbm_test + ymean, gbm_val + ymean

        out.append(preds)
        val_out.append(vpred)
        print("test %s  train<=%s n=%s  test n=%s  lasso=%.1e ridge=%.1e en=%.1e  "
              "gbm leaves=%d rounds=%d  %.0fs"
              % (test_start[:4], train_end, format(int(train.sum()), ","),
                 format(int(test.sum()), ","), a, r, e,
                 cfg["num_leaves"], rounds, time.time() - t0), flush=True)

    pred = pd.concat(out, ignore_index=True)
    val = pd.concat(val_out, ignore_index=True)
    for frame in (pred, val):
        frame["avg_linear"] = frame[LINEAR_MODELS].mean(axis=1)

    winner, parts = choose_blend(val)
    z = pred.groupby("target_month")[parts].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
    pred["avg"] = z.mean(axis=1)
    pred.attrs["blend"] = winner
    (C.PROCESSED_DIR / "blend.json").write_text(
        json.dumps({"blend": winner, "parts": parts}), encoding="utf-8")
    val.to_parquet(C.PROCESSED_DIR / "validation_predictions.parquet", index=False,
                   compression="zstd")
    pred.to_parquet(OUT, index=False, compression="zstd")

    print("\nwrote %s (%s rows, %s months)"
          % (OUT.name, format(len(pred), ","), pred["target_month"].nunique()))

    # out-of-sample R-squared, benchmarked against zero as the rules specify.
    # Only forecasts in return units qualify; `avg` is a within-month ranking
    # score, so an R2 on it would be meaningless.
    have = pred[pred[C.TARGET].notna()]
    y = have[C.TARGET].values
    print("\nout-of-sample R2 (benchmark = zero, not the historical mean):")
    for m in MODELS + ["avg_linear"]:
        r2 = 1 - np.sum((y - have[m].values) ** 2) / np.sum(y ** 2)
        print("  %-11s %+.4f%%" % (m, 100 * r2))
    print("  %-11s  (ranking score, not in return units -- no R2)" % "avg")

    # rank correlation with the realized answer says more about a long/short
    # book than squared error does
    print("\nmonthly rank correlation with the realized return:")
    for m in MODELS + ["avg_linear", "avg"]:
        ic = have.groupby("target_month").apply(
            lambda d: d[m].corr(d[C.TARGET], method="spearman"), include_groups=False)
        print("  %-11s mean %+.4f   positive in %.0f%% of months"
              % (m, ic.mean(), 100 * (ic > 0).mean()))

    print("\nThe rules note that 1-2%% R2 is typical even for neural networks, and "
          "that any positive number means some predictability. A large positive "
          "number means a leak.")
    return pred


if __name__ == "__main__":
    run()

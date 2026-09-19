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
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

FEATURES_FILE = C.PROCESSED_DIR / "features_ranked.parquet"
OUT = C.PROCESSED_DIR / "predictions.parquet"

# Coarse grids: this is a baseline, and a finer search is not what decides the
# competition. Refine once something depends on it.
LASSO_GRID = np.logspace(-5, -1, 13)
RIDGE_GRID = np.logspace(0, 6, 13)
EN_GRID = np.logspace(-5, -1, 13)
MAX_ITER = 3000

MODELS = ["ols", "lasso", "ridge", "en"]


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
    tm = df["target_month"]
    answered = df[C.TARGET].notna()

    out = []
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

        preds["ols"] = LinearRegression(fit_intercept=False).fit(Xtr, ytr_c).predict(Xte) + ymean

        a = pick_penalty(lambda v: Lasso(alpha=v, max_iter=MAX_ITER, fit_intercept=False),
                         LASSO_GRID, Xtr, ytr_c, Xva, yva, ymean)
        preds["lasso"] = Lasso(alpha=a, max_iter=MAX_ITER, fit_intercept=False)\
            .fit(Xtr, ytr_c).predict(Xte) + ymean

        r = pick_penalty(lambda v: Ridge(alpha=v, fit_intercept=False),
                         RIDGE_GRID, Xtr, ytr_c, Xva, yva, ymean)
        preds["ridge"] = Ridge(alpha=r, fit_intercept=False)\
            .fit(Xtr, ytr_c).predict(Xte) + ymean

        e = pick_penalty(lambda v: ElasticNet(alpha=v, max_iter=MAX_ITER, fit_intercept=False),
                         EN_GRID, Xtr, ytr_c, Xva, yva, ymean)
        preds["en"] = ElasticNet(alpha=e, max_iter=MAX_ITER, fit_intercept=False)\
            .fit(Xtr, ytr_c).predict(Xte) + ymean

        out.append(preds)
        print("test %s  train<=%s n=%s  val %s..%s  test n=%s  "
              "lasso=%.1e ridge=%.1e en=%.1e  %.0fs"
              % (test_start[:4], train_end, format(int(train.sum()), ","),
                 val_start, val_end, format(int(test.sum()), ","), a, r, e,
                 time.time() - t0), flush=True)

    pred = pd.concat(out, ignore_index=True)
    # average of the four -- forecast combination is the cheapest reliable gain
    pred["avg"] = pred[MODELS].mean(axis=1)
    pred.to_parquet(OUT, index=False, compression="zstd")

    print("\nwrote %s (%s rows, %s months)"
          % (OUT.name, format(len(pred), ","), pred["target_month"].nunique()))

    # out-of-sample R-squared, benchmarked against zero as the rules specify
    have = pred[pred[C.TARGET].notna()]
    y = have[C.TARGET].values
    print("\nout-of-sample R2 (benchmark = zero, not the historical mean):")
    for m in MODELS + ["avg"]:
        r2 = 1 - np.sum((y - have[m].values) ** 2) / np.sum(y ** 2)
        print("  %-6s %+.4f%%" % (m, 100 * r2))
    print("\nThe rules note that 1-2%% is typical even for neural networks, and that "
          "any positive number means some predictability. A large positive number "
          "means a leak.")
    return pred


if __name__ == "__main__":
    run()

"""Prediction model training. Run directly, or set RETRAIN_PREDICTIONS=True in root main.py."""
import os
os.environ.setdefault('MPLBACKEND','Agg')

from pathlib import Path
import sys, importlib.util, json, hashlib, platform
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import lightgbm as lgb
import matplotlib.pyplot as plt
def display(value):
    print(value)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prediction"))
import prediction_helpers as C

TRAIN = C
FEATURES = C

RUN_MODE = "full"  # "smoke": bounded 2021 check; "full": complete 2021–2026 folds
assert RUN_MODE in {"smoke", "full"}
SEED = 2026
TEST_YEARS = [2021] if RUN_MODE == "smoke" else list(range(2021, 2027))
MAX_TREES = 50 if RUN_MODE == "smoke" else TRAIN.GBM_FIXED["n_estimators"]
GRID = TRAIN.GBM_GRID[:1] if RUN_MODE == "smoke" else TRAIN.GBM_GRID
ROW_LIMITS = {"train": 20_000, "validation": 5_000, "test": 5_000}
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
OUT = ROOT / "prediction/outputs/next_month_prediction" / RUN_MODE / RUN_ID
OUT.mkdir(parents=True, exist_ok=True)
print(f"Mode: {RUN_MODE} | years: {TEST_YEARS} | output: {OUT}")
if RUN_MODE == "smoke":
    print("SMOKE TEST ONLY: sampled rows, reduced trees and grid. Do not use as strategy evidence.")

feature_names = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
assert len(feature_names) == len(set(feature_names)) == 147
assert C.TARGET not in feature_names
source = C.CHARS_PARQUET
columns = ["permno", "eom", "ticker", "company_name", C.TARGET] + feature_names
data = pq.read_table(source, columns=columns).to_pandas()
data["eom"] = pd.to_datetime(data["eom"])
data["target_month"] = (data.eom.dt.to_period("M") + 1).astype(str)
data = data.sort_values(["target_month", "permno"]).reset_index(drop=True)
assert not data.duplicated(["permno", "target_month"]).any()
assert ((pd.PeriodIndex(data.target_month, freq="M") - 1).astype(str)
        == data.eom.dt.to_period("M").astype(str)).all()
assert not np.isinf(data[feature_names].to_numpy()).any(), "Infinite source feature values"
# ret_exc_lead1m is already led: do not shift its values again.
display(data[["permno", "ticker", "eom", "target_month", C.TARGET]].head())
print(f"{len(data):,} rows; {data.permno.nunique():,} securities; {len(feature_names)} inputs; no filing columns read.")

X = pd.DataFrame(np.nan, index=data.index, columns=feature_names, dtype="float32")
for _, indexes in data.groupby("target_month", sort=True).groups.items():
    ranked = data.loc[indexes, feature_names].apply(FEATURES.rank_keep_missing)
    X.loc[indexes, feature_names] = ranked.astype("float32")
assert X.columns.tolist() == feature_names
observed = X.to_numpy()
assert np.nanmin(observed) >= -1.0001 and np.nanmax(observed) <= 1.0001
print(f"Missing ranked inputs: {X.isna().mean().mean():.1%}; LightGBM handles them directly.")
display(X.head())

folds = []
for train_end, val_start, val_end, test_start, test_end in C.training_schedule():
    if int(test_start[:4]) not in TEST_YEARS:
        continue
    tm = data.target_month
    answered = data[C.TARGET].notna()
    indexes = {
        "train": data.index[(tm <= train_end) & answered].to_numpy(),
        "validation": data.index[(tm >= val_start) & (tm <= val_end) & answered].to_numpy(),
        "test": data.index[(tm >= test_start) & (tm <= test_end)].to_numpy(),
    }
    full_sizes = {k: len(v) for k, v in indexes.items()}
    if RUN_MODE == "smoke":
        rng = np.random.default_rng(SEED)
        indexes = {k: np.sort(rng.choice(v, min(len(v), ROW_LIMITS[k]), replace=False))
                   for k, v in indexes.items()}
    assert all(len(v) for v in indexes.values())
    assert tm.iloc[indexes["train"]].max() < tm.iloc[indexes["validation"]].min()
    assert tm.iloc[indexes["validation"]].max() < tm.iloc[indexes["test"]].min()
    folds.append(dict(year=int(test_start[:4]), train_end=train_end,
                      validation_start=val_start, validation_end=val_end,
                      test_start=test_start, test_end=test_end,
                      full_sizes=full_sizes, indexes=indexes))
display(pd.DataFrame([{k: v for k, v in f.items() if k != "indexes"}
                     | {f"used_{k}": len(v) for k, v in f["indexes"].items()} for f in folds]))

def fit_variant(train_idx, val_idx, test_idx, raw_target):
    raw_train = data.loc[train_idx, C.TARGET].to_numpy()
    raw_val = data.loc[val_idx, C.TARGET].to_numpy()
    if raw_target:
        ytr, yva, offset = raw_train, raw_val, 0.0
    else:
        ytr = TRAIN.demean_and_clip(raw_train, data.loc[train_idx, "target_month"])
        yva = TRAIN.demean_and_clip(raw_val, data.loc[val_idx, "target_month"])
        offset = float(raw_train.mean())
    trials, best_model, best_loss = [], None, np.inf
    fixed = dict(TRAIN.GBM_FIXED)
    fixed.update(n_estimators=MAX_TREES, n_jobs=2, random_state=SEED,
                 deterministic=True, force_col_wise=True)
    for cfg in GRID:
        model = lgb.LGBMRegressor(**fixed, **cfg)
        model.fit(X.loc[train_idx], ytr, eval_set=[(X.loc[val_idx], yva)], eval_metric="l2",
                  callbacks=[lgb.early_stopping(TRAIN.GBM_EARLY_STOP, verbose=False)])
        loss = float(np.mean((yva - model.predict(X.loc[val_idx])) ** 2))
        trial = dict(config=cfg, validation_training_objective_mse=loss,
                     best_iteration=int(model.best_iteration_))
        trials.append(trial)
        if loss < best_loss:
            best_loss, best_model, best_trial = loss, model, trial
    return best_model, offset, dict(selected=best_trial, trials=trials)

predictions, training_log, importances = [], [], []
for fold in folds:
    tr, va, te = [fold["indexes"][k] for k in ("train", "validation", "test")]
    result = data.loc[te, ["permno", "ticker", "company_name", "eom", "target_month", C.TARGET]].copy()
    for name, raw_target in [("current_gbm_no8k", False), ("raw_return_gbm_no8k", True)]:
        model, offset, log = fit_variant(tr, va, te, raw_target)
        result[name] = model.predict(X.loc[te]) + offset
        assert np.isfinite(result[name]).all()
        model.booster_.save_model(str(OUT / f"{name}_{fold['year']}.txt"))
        training_log.append(dict(year=fold["year"], variant=name, prediction_offset=offset, **log))
        importances.append(pd.DataFrame({"feature": feature_names,
            "gain": model.booster_.feature_importance(importance_type="gain"),
            "variant": name, "year": fold["year"]}))
        print(f"{fold['year']} | {name} | {model.best_iteration_} trees", flush=True)
    predictions.append(result)
pred = pd.concat(predictions, ignore_index=True)
assert not pred.duplicated(["permno", "target_month"]).any()
# Missing future outcomes are retained and still receive predictions.
assert len(pred) == sum(len(f["indexes"]["test"]) for f in folds)
print(f"Predicted {len(pred):,} rows; {pred[C.TARGET].isna().sum():,} have unavailable future outcomes.")

variants = ["current_gbm_no8k", "raw_return_gbm_no8k"]
metric_rows, ic_rows = [], []
for scope, block in [("all", pred), *list(pred.groupby(pred.target_month.str[:4]))]:
    observed = block.dropna(subset=[C.TARGET])
    for name in variants:
        y, forecast = observed[C.TARGET], observed[name]
        monthly = observed.groupby("target_month").apply(
            lambda g: g[name].corr(g[C.TARGET], method="spearman")
                      if g[name].nunique() > 1 and g[C.TARGET].nunique() > 1 else np.nan,
            include_groups=False)
        denominator = float((y ** 2).sum())
        metric_rows.append(dict(scope=scope, variant=name, predicted_rows=len(block),
            scored_rows=len(observed), mse=float(((y - forecast)**2).mean()),
            oos_r2_vs_zero=1-float(((y-forecast)**2).sum())/denominator if denominator else np.nan,
            mean_monthly_rank_ic=monthly.mean(), scored_ic_months=int(monthly.notna().sum())))
        if scope == "all":
            ic_rows.extend(dict(target_month=m, variant=name, rank_ic=v) for m, v in monthly.items())
metrics = pd.DataFrame(metric_rows)
monthly_ic = pd.DataFrame(ic_rows)
display(metrics)
print("Both variants scored on original next-month excess returns. Training losses use different targets and are not directly comparable.")
if RUN_MODE == "smoke":
    print("Sampled-month demeaning and limited tuning are NOT the full production recipe; rerun with RUN_MODE='full'.")

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
ic_chart = monthly_ic.pivot(index="target_month", columns="variant", values="rank_ic")
ic_chart.index = pd.PeriodIndex(ic_chart.index, freq="M").to_timestamp()
ic_chart.plot(ax=axes[0], title=f"Monthly rank IC — {RUN_MODE}")
axes[0].axhline(0, color="gray", linewidth=.7)
axes[0].set_ylabel("Spearman correlation")
summary = metrics[metrics.scope.eq("all")].set_index("variant")
summary[["mse"]].plot.bar(ax=axes[1], legend=False, title="MSE against original next-month return")
axes[1].tick_params(axis="x", rotation=15)
fig.tight_layout()
fig.savefig(OUT / "prediction_comparison.png", dpi=140)
plt.show()
importance = pd.concat(importances, ignore_index=True)
display(importance.groupby(["variant", "feature"]).gain.mean().rename("mean_gain")
        .reset_index().sort_values(["variant", "mean_gain"], ascending=[True, False])
        .groupby("variant").head(10))

saved = C.PROCESSED_DIR / "predictions.parquet"
if not saved.exists():
    print("No saved production predictions found. The controlled no-8K GBM comparison above is available.")
else:
    original = pd.read_parquet(saved, columns=["permno", "target_month", "gbm", "avg"])
    assert not original.duplicated(["permno", "target_month"]).any()
    matched = pred.merge(original.rename(columns={"gbm": "saved_gbm", "avg": "saved_blend_score"}),
                         on=["permno", "target_month"], how="inner", validate="one_to_one")
    print(f"Matched {len(matched):,}/{len(pred):,} test rows. Saved provenance/8-K inclusion must be checked separately.")
    rows = []
    for col in variants + ["saved_gbm", "saved_blend_score"]:
        scored = matched.dropna(subset=[C.TARGET, col])
        ic = scored.groupby("target_month").apply(
            lambda g: g[col].corr(g[C.TARGET], method="spearman")
                      if g[col].nunique() > 1 and g[C.TARGET].nunique() > 1 else np.nan,
            include_groups=False)
        rows.append({"variant": col, "matched_scored_rows": len(scored), "mean_monthly_rank_ic": ic.mean()})
    display(pd.DataFrame(rows))
    print("Saved avg is a ranking score: do not interpret it as a return forecast or calculate return MSE on it.")

pred.to_parquet(OUT / "predictions.parquet", index=False)
pred.to_csv(OUT / "predictions.csv", index=False)
metrics.to_csv(OUT / "metrics.csv", index=False)
monthly_ic.to_csv(OUT / "monthly_rank_ic.csv", index=False)
importance.to_csv(OUT / "feature_importance.csv", index=False)
(OUT / "training_choices.json").write_text(json.dumps(training_log, indent=2), encoding="utf-8")
manifest = {"run_mode": RUN_MODE, "seed": SEED, "test_years": TEST_YEARS,
    "max_trees": MAX_TREES, "grid": GRID, "features": feature_names, "filing_features": False,
    "target": C.TARGET, "source": str(source), "source_bytes": source.stat().st_size,
    "source_mtime_ns": source.stat().st_mtime_ns,
    "versions": {"python": platform.python_version(), "pandas": pd.__version__, "lightgbm": lgb.__version__},
    "script_sha256": {s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in
       ["prediction/prediction_helpers.py", "prediction/predict.py"]},
    "folds": [{k: v for k, v in f.items() if k != "indexes"} for f in folds]}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Saved comparison: {OUT}")
print("Prediction export ready. Run an experiment main.py to size the portfolio.")

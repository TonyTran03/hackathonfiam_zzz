"""Evaluate held-out predictions independently of the model that made them."""

import numpy as np
import pandas as pd


def make_prediction_frame(test_df, y_pred):
    """Attach an ordered prediction array to stock-month outcomes.

    eom is the feature month; target_month is the following return month.
    Models must return one finite prediction per input row, in input order.
    """
    predictions = np.asarray(y_pred, dtype=float)
    if predictions.ndim != 1 or len(predictions) != len(test_df):
        raise ValueError("Return a 1D prediction array with one value per test row.")
    if not np.isfinite(predictions).all():
        raise ValueError("Predictions must be finite.")
    result = test_df[["permno", "eom", "ret_exc_lead1m"]].copy()
    result = result.rename(columns={"ret_exc_lead1m": "y_true"})
    result["target_month"] = pd.to_datetime(result["eom"]).dt.to_period("M") + 1
    result["y_pred"] = predictions
    return result


def evaluate_predictions(pred_df):
    """Return pooled errors and equally weighted monthly IC summaries.

    OOS R2 uses zero as the baseline prediction. Missing outcomes are excluded
    and counted. Constant cross-sections have undefined IC, represented as NaN.
    """
    required = ["permno", "target_month", "y_true", "y_pred"]
    frame = pred_df[required].copy()
    if frame[["permno", "target_month"]].isna().any().any():
        raise ValueError("Stock identifiers and target months must not be missing.")
    frame["target_month"] = frame["target_month"].map(lambda x: pd.Period(x, freq="M"))
    if frame.duplicated(["permno", "target_month"]).any():
        raise ValueError("Expected one prediction per stock and target month.")
    if not np.isfinite(frame["y_pred"].to_numpy(dtype=float)).all():
        raise ValueError("Predictions must be finite.")
    scored = frame.dropna(subset=["y_true"])
    if scored.empty:
        raise ValueError("No observed outcomes to evaluate.")
    actual = scored["y_true"].to_numpy(dtype=float)
    predicted = scored["y_pred"].to_numpy(dtype=float)
    if not np.isfinite(actual).all():
        raise ValueError("Observed outcomes must be finite.")
    errors = actual - predicted
    denominator = np.sum(actual ** 2)
    monthly = []
    for month, group in scored.groupby("target_month", sort=True):
        valid = len(group) >= 2 and group["y_true"].nunique() > 1 and group["y_pred"].nunique() > 1
        monthly.append({
            "target_month": month,
            "n_predictions": len(group),
            "pearson_ic": group["y_true"].corr(group["y_pred"]) if valid else np.nan,
            "rank_ic": group["y_true"].rank().corr(group["y_pred"].rank()) if valid else np.nan,
        })
    monthly_ic = pd.DataFrame(monthly)
    return {
        "n_predictions": len(scored),
        "n_missing_outcomes": len(frame) - len(scored),
        "mse": float(np.mean(errors ** 2)),
        "mae": float(np.mean(np.abs(errors))),
        "oos_r2": float(1 - np.sum(errors ** 2) / denominator) if denominator > 0 else np.nan,
        "pearson_ic": float(monthly_ic["pearson_ic"].mean()),
        "rank_ic": float(monthly_ic["rank_ic"].mean()),
        "monthly_ic": monthly_ic,
    }

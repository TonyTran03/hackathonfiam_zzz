# Our model evaluation

`evaluate_predictions.py` is our evaluator. `portfolio_analysis_hackathon.py` is
still a supplied reference demo with placeholder paths.

```python
from tests.evaluate_predictions import make_prediction_frame, evaluate_predictions

y_pred = model.predict(test_df[features])
pred_df = make_prediction_frame(test_df, y_pred)
stats = evaluate_predictions(pred_df)
```

Run project code from the repository root. Shared paths are in `project_paths.py`.
The model returns a 1D array in test-row order. Test rows retain `permno`, `eom`,
and `ret_exc_lead1m`. The evaluator derives the next target month from `eom`;
it does not shift the supplied outcome again.

Metrics: MSE, MAE, zero-baseline OOS R2, and monthly Pearson/rank IC averaged
equally across months. `monthly_ic` retains monthly results and sample counts.
Undefined correlations are NaN and excluded from averages. Missing outcomes are
excluded and counted. Invalid predictions and duplicate stock-months raise errors.

Realized outcomes are already in `ret_exc_lead1m`. Benchmark returns are not
needed for prediction metrics. Portfolio construction and scoring remain to be
implemented. Models must be trained and selected without test outcomes; this
module cannot verify the upstream training process.

Run correctness checks with `python -m unittest tests.test_evaluate_predictions`.

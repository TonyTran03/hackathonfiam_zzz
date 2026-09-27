# Fair model comparison for the McGill–FIAM challenge

Start with `REPORT.md` and the tables in `results/`. `PROTOCOL.md` was written before fitting. This experiment is separate from the team pipeline and does not overwrite its submissions.

## Run

Python 3.12 was used. From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export FIAM_DATA_DIR="/absolute/path/to/folder/containing/the/parquet/file"
python run_comparison.py
python test_experiment.py
python make_report.py
```

Only `chars_final_with_names.parquet` is needed. It is intentionally not bundled. The filing dataset is not used. Supplied cash and market snapshots and the 147-feature list are bundled.

On Windows, activate `.venv\Scripts\activate` and set the environment variable using PowerShell's `$env:FIAM_DATA_DIR` syntax.

The code uses two threads by default to avoid excessive CPU and memory use. Allow several minutes for training and portfolio evaluation. Cached monthly feature matrices and model tables are generated locally; they are not bundled. Annual forecast checkpoints in `results/` allow interrupted runs to resume. To reproduce training from scratch, move the supplied `results/` directory aside before running. A new empty results directory is created automatically. Never reuse caches/checkpoints after changing data, features, or protocol: use a fresh directory or remove `cache/`, `01_data/processed/`, and generated `results/` together.

`python run_comparison.py --evaluate-only` rebuilds portfolio tables from saved predictions, after loading/preparing the supplied original data. No models are retrained.

## Files

- `run_comparison.py`: preparation, annual model fitting and fold-specific selection.
- `evaluate_comparison.py`: common portfolio evaluation, cash/financing reconciliation, drift-aware transaction costs, uncertainty and plots.
- `test_experiment.py`: timing, smoothing, cash accounting and initial-loss drawdown checks.
- `baseline_portfolio.py`, `data_loader.py`, `common/`: code copied from the uploaded feat-pipeline snapshot. The experiment reuses screening, neutralization and position construction. Imports are adjusted for this standalone layout; stable tie ordering is added; calendar-month smoothing is overridden in the experiment. Their original standalone build/evaluate entry points are not the experiment's entry points.
- `results/annual_choices.json`: actual hyperparameters and blend chosen separately for each year, with validation scores.
- `results/prediction_metrics.csv`: prediction R2 and rank IC, on the full and common eligible universes.
- `results/portfolio_metrics.csv`: gross and cost-adjusted results for every model.
- `results/monthly_returns.csv`, `results/yearly_returns.csv`: complete comparative time series.
- `results/paired_uncertainty.csv`: paired six-month block-bootstrap comparisons.
- `results/holdings_*.parquet`: each model's 68 monthly portfolios, including unresolved outcomes and original historical labels.
- `results/verification.json`: direct target alignment and monthly trading-rule checks.

## Integrating with the team repository

Keep this as an experiment folder or a separate branch. Do not copy its selected model back as a 'winner' merely because it looks best in the already-viewed 2021–2026 window.

The annual-selection repair belongs inside the yearly training loop: calculate validation scores using only that fold, select its recipe, and write that fold's test scores before moving to the next year. Do not concatenate later validation periods to select a recipe for earlier test years. This experiment implements that repair in `select_annual` and `train`.

These comparisons deliberately use a common original-return objective. They do NOT reproduce the original pipeline's LightGBM-only monthly target demeaning/clipping, nor its median-before-ranking preprocessing. No claim about the best possible LightGBM strategy follows from this limited experiment.

The inherited portfolio policy was developed after the team had inspected historical results. These results are therefore retrospective. Raw missing returns are marked as zero for the base case and separately stress-tested, not assumed known. The benchmark regression uses S&P 500 price returns, not dividend-inclusive returns. Borrow costs and separate borrowing/collateral rates remain unmodeled. Original period-supported labels are retained; unresolved labels require verification before a final competition submission.

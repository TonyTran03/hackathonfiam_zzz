"""Shared runner used by the small main.py files. No command-line arguments."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def execute(experiments, *, retrain=False, predictions=None,
            forecast='current_gbm_no8k', start=None, end=None, max_months=None):
    sys.path.insert(0, str(ROOT / 'sizing'))
    import pandas as pd
    import _engine as engine
    if not engine.C.CHARS_PARQUET.is_file():
        raise FileNotFoundError(
            'Missing monthly stock data. Copy chars_final_with_names.parquet into '
            f'{ROOT / "data"}, or set FIAM_DATA_DIR to its folder. See README.md.')
    if retrain:
        if predictions is not None:
            raise ValueError('Choose retraining OR an existing prediction file.')
        try:
            before = engine.resolve_predictions(None)
        except FileNotFoundError:
            before = None
        subprocess.run([sys.executable, str(ROOT / 'prediction/predict.py')], cwd=ROOT, check=True)
        if engine.resolve_predictions(None) == before:
            raise RuntimeError('No new full forecast export produced; check RUN_MODE="full" in prediction/predict.py.')
    source = engine.resolve_predictions(predictions)
    print(f'All experiments use: {source}\nForecast: {forecast}', flush=True)
    outputs = {}
    summaries = []
    for name in experiments:
        options = dict(predictions=str(source), forecast=forecast,
                       start=start, end=end, max_months=max_months)
        out = engine.run_price_only(**options) if name == 'price_only' else engine.run(name, **options)
        outputs[name] = out
        frame = pd.read_csv(out / 'summary.csv')
        frame.insert(0, 'experiment', name)
        summaries.append(frame)
        print(f'\n{name}: OPEN {out / "report.html"}', flush=True)
    if not summaries:
        raise ValueError('Choose at least one experiment.')
    comparison = pd.concat(summaries, ignore_index=True)
    print('\nRuns just executed:')
    print(comparison[['experiment', 'months', 'cagr', 'information_ratio',
                      'max_drawdown', 'realized_market_beta', 'min_positions']].to_string(index=False))
    print(f'\nLatest experiments: {ROOT / "sizing/comparison.csv"}')
    return outputs

"""Run prediction (optional), portfolio experiments and comparison from one file.
Open this file in your editor and click Run. No GUI, notebook or CLI arguments.
"""
from pathlib import Path
import sys

RETRAIN_PREDICTIONS = False
EXPERIMENTS = ['price_only', 'optimizer']
FORECAST = 'current_gbm_no8k'
START = None
END = None
MAX_MONTHS = None  # 2 for a quick execution check; None for the complete window.

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'sizing'))
    from run import execute
    execute(EXPERIMENTS, retrain=RETRAIN_PREDICTIONS, forecast=FORECAST,
            start=START, end=END, max_months=MAX_MONTHS)

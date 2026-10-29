"""Open this file and click your editor's Run button. Edit the four step files beside it."""
from pathlib import Path
import sys

FORECAST = 'current_gbm_no8k'
START = None
END = None
MAX_MONTHS = None  # 2 for a quick execution check; None for all months.

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from run import execute
    execute([Path(__file__).resolve().parent.name], forecast=FORECAST,
            start=START, end=END, max_months=MAX_MONTHS)

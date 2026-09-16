from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
STAGES = (
    "01_data/01_load_data.py",
    "01_data/02_make_features.py",
    "02_prediction/03_train_predict.py",
    "03_portfolio_construction/04_build_portfolio.py",
    "04_backtest_scoring/05_evaluate.py",
)


def main():

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

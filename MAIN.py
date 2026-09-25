"""Run the five pipeline stages in order, then verify rule compliance.

    python MAIN.py                # full chain
    python MAIN.py --no-check     # stages only, skip the compliance gate

Each stage runs with the same interpreter and the project root as the working
directory. The chain stops at the first failure. Stages that have not been
written yet are reported, and nothing is run.
"""
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
CHECKS = "run_checks.py"

# Reporting runs in the same chain as the model. Keeping them separate is how
# 05_submission/ ended up holding holdings.csv from one configuration and the
# figures and deck_pack.csv from a run four days older -- a deck built from
# that mix would have had charts that did not match its own numbers. Anything
# whose inputs are missing is skipped rather than failing the chain.
REPORTS = (
    "04_backtest_scoring/08_charts.py",
    "04_backtest_scoring/11_deck_pack.py",
    "04_backtest_scoring/06_robustness.py",
    "04_backtest_scoring/10_daily_risk.py",
)


def run(script):
    print("\n" + "=" * 70)
    print("RUN  %s" % script)
    print("=" * 70, flush=True)
    return subprocess.call([sys.executable, str(ROOT / script)], cwd=str(ROOT))


def main(argv):
    missing = [s for s in STAGES if not (ROOT / s).exists()]
    if missing:
        print("Not run -- %d of %d stages are not written yet:" % (len(missing), len(STAGES)))
        for s in STAGES:
            print("  %-48s %s" % (s, "MISSING" if s in missing else "ready"))
        print("\nWrite the missing stage scripts, then run this again.")
        return 1

    for stage in STAGES:
        code = run(stage)
        if code != 0:
            print("\nStopped: %s exited with status %d" % (stage, code))
            return code

    if "--no-check" in argv:
        print("\nAll stages finished. Compliance gate skipped (--no-check).")
        return 0

    code = run(CHECKS)
    if code != 0:
        print("\nAll stages finished, but the compliance check FAILED.")
        print("The book or the data splits break a competition rule -- fix before submitting.")
        return code

    print("\nAll stages finished and the compliance check passed.")

    print("\n" + "=" * 70)
    print("REGENERATING THE SUBMISSION EXHIBITS")
    print("=" * 70, flush=True)
    for script in REPORTS:
        if not (ROOT / script).exists():
            print("  skip %s (not present)" % script)
            continue
        if run(script) != 0:
            print("  %s did not finish; its outputs may be stale" % script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

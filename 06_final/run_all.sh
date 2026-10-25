#!/usr/bin/env bash
# Rebuild every final-round artefact from the round-1 forecasts.
#   prerequisites: python MAIN.py --no-check   (stages 1-3: model table, forecasts)
#                  dsf_mini_from_2014.csv(.gz) in 01_data/raw/
set -euo pipefail
cd "$(dirname "$0")"
python3 f01_daily.py
python3 f02_signal.py design test
python3 f05_event_study.py

rm -rf data/runs
E="python3 f03_engine.py"
# design window: D1 candidates and the risk-layer smoke test
for f in M W D; do $E --window design --freq $f; done
$E --window design --freq M --layer rule
# test window: the pre-registered register
for f in M W D; do $E --window test --freq $f; done
$E --window test --freq M --overlay E
$E --window test --freq M --layer rule
$E --window test --freq M --nav 250e6
$E --window test --freq M --nav 4e9
for c in sqrt:0.25 sqrt:0.5 sqrt:1.0 almgren flat:0 flat:10 flat:20 flat:30 flat:50; do
  $E --window test --freq M --cost $c
done
$E --window test --freq M --borrow flat
$E --window test --freq M --cost almgren --borrow flat
$E --window test --freq M --cost flat:20 --borrow flat
# post-hoc, labelled as such in the register
$E --window design --freq B
for f in B Q; do $E --window test --freq $f; $E --window test --freq $f --cost almgren; done

python3 f08_leakage_tests.py test_M
python3 f06_report.py test_M
python3 f06_report.py test_Q
python3 f07_diagnostics.py test_M
python3 f07_diagnostics.py --survivorship
python3 f10_register.py

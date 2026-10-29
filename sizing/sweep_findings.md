# Allocation sweep findings

> **Universe limitation:** These allocation results include nano/micro-cap and under-$5 stocks. An independent check of the saved 2021–2026 forecasts found mean monthly rank IC of 0.171 in that tiny/low-price group versus 0.040 in the screened remainder. These results do not establish implementable alpha; the screened universe must be evaluated separately.

84 configurations attempted over January 2021–August 2026 with identical forecasts, rankings, and candidates. 67 completed all 68 months; 16 were infeasible and one had a solver failure. No constraints were relaxed.

| Choice | CAGR | Volatility | IR | Max drawdown | Monthly turnover | IR 2021–2023 | IR 2024–2026 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | 44.8% | 31.0% | 1.11 | -27.5% | 70.0% | 1.23 | 0.97 |
| Highest full-period IR | 54.7% | 28.6% | 1.42 | -13.0% | 63.0% | 1.49 | 1.32 |
| Intermediate risk | 41.8% | 23.8% | 1.29 | -12.2% | 66.3% | 1.03 | 1.63 |
| Lower volatility | 32.7% | 19.2% | 1.20 | -10.2% | 60.4% | 1.02 | 1.44 |
| Lower turnover | 40.7% | 24.0% | 1.24 | -16.5% | 49.5% | 1.10 | 1.39 |

## Configuration shortlist

- **Highest full-period IR**: `refine_r30.0_sector` — {'risk_penalty': 30.0, 'position_limit': 0.025, 'sector_limit': 0.05, 'cost_penalty': 10.0}.
- **Intermediate risk**: `refine_r10.0_p0.025_v0.125` — {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.125}.
- **Lower volatility**: `refine_r30.0_p0.015_v0.1` — {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.1}.
- **Lower turnover**: `refine_r30.0_p0.025_g1.5` — {'risk_penalty': 30.0, 'position_limit': 0.025, 'gross_limit': 1.5}.

The highest-IR configuration is an unscreened historical allocation result, not a validated tradable baseline. Its IR improves in both historical subperiods and its full-period drawdown is smaller, but the stock-universe limitation takes priority over allocation tuning. Its realized market beta remains -0.54, so estimated-beta neutrality has not solved realized market exposure.

The lower-volatility choice has 19.2% realized volatility despite a 10% forecast budget. Forecast volatility bounds must not be treated as realized volatility guarantees.

Baseline cost stress: 50 bps reduces IR to 0.95; 100 bps reduces it to 0.69. These stress trials reoptimize the baseline under the higher charge; they are not cost stress tests of the selected winner. Borrow and market impact remain omitted.

The 26 refinement configurations were chosen after examining the broad pass. All comparisons and period splits are retrospective; neither period is an untouched holdout. Ranking, candidate selection, and prediction models were held fixed.

Verification: baseline reproduced; all 67 successful trials have 68 unique monthly observations; every recorded constraint violation is at most 1e-6; all enabled forecast volatility ceilings pass. Failures and their dates are in sweep_failures.json.

Run `python sizing/optimizer/sweep.py` for the broad pass, then `python sizing/optimizer/sweep.py --refine` for the focused pass. Repeating refinement resumes unfinished trials. Settings remain editable in constraint.csv.

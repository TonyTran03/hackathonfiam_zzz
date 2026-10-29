# Model comparison

> **Universe limitation:** These allocation results include nano/micro-cap and under-$5 stocks. An independent check of the saved 2021–2026 forecasts found mean monthly rank IC of 0.171 in that tiny/low-price group versus 0.040 in the screened remainder. These results do not establish implementable alpha; the screened universe must be evaluated separately.

2021-01 to 2026-08 · `current_gbm_no8k`

| Experiment | What changed | Vol | IR | Beta | Max drawdown | Return (CAGR) | Monthly turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| refine_r30.0_sector | {'risk_penalty': 30.0, 'position_limit': 0.025, 'sector_limit': 0.05, 'cost_penalty': 10.0} | 28.6% | 1.42 | -0.54 | -13.0% | 54.7% | 63.0% |
| risk_penalty_10.0 | {'risk_penalty': 10.0} | 40.4% | 1.40 | -0.71 | -22.2% | 74.6% | 73.1% |
| risk_penalty_30.0 | {'risk_penalty': 30.0} | 33.5% | 1.39 | -0.65 | -22.8% | 61.4% | 72.0% |
| covariance_months_12 | {'covariance_months': 12} | 30.8% | 1.32 | -0.45 | -25.5% | 53.6% | 71.2% |
| refine_r10.0_p0.025_v0.125 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.125} | 23.8% | 1.29 | -0.45 | -12.2% | 41.8% | 66.3% |
| refine_r30.0_p0.025_v0.15 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'annual_vol_limit': 0.15} | 26.7% | 1.28 | -0.46 | -17.0% | 45.9% | 66.3% |
| beta_limit_None | {'beta_limit': None} | 30.3% | 1.27 | -0.22 | -29.5% | 50.6% | 70.5% |
| refine_r10.0_sector | {'risk_penalty': 10.0, 'position_limit': 0.025, 'sector_limit': 0.05, 'cost_penalty': 10.0} | 29.9% | 1.26 | -0.58 | -14.2% | 49.6% | 64.0% |
| refine_r10.0_p0.025_v0.15 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.15} | 26.8% | 1.25 | -0.47 | -17.0% | 44.9% | 66.4% |
| refine_r30.0_p0.025_g1.5 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 24.0% | 1.24 | -0.45 | -16.5% | 40.7% | 49.5% |
| position_limit_0.025 | {'position_limit': 0.025} | 24.2% | 1.22 | -0.45 | -16.3% | 39.9% | 65.9% |
| covariance_months_60 | {'covariance_months': 60} | 30.8% | 1.20 | -0.54 | -21.1% | 48.4% | 71.0% |
| refine_r10.0_p0.025_v0.1 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.1} | 21.4% | 1.20 | -0.40 | -10.6% | 35.8% | 65.6% |
| refine_r30.0_p0.025_v0.1 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'annual_vol_limit': 0.1} | 21.4% | 1.20 | -0.40 | -10.6% | 35.8% | 65.6% |
| annual_vol_limit_0.125 | {'annual_vol_limit': 0.125} | 27.2% | 1.20 | -0.44 | -23.4% | 43.4% | 70.3% |
| refine_r30.0_p0.015_v0.1 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.1} | 19.2% | 1.20 | -0.39 | -10.2% | 32.7% | 60.4% |
| refine_r10.0_p0.015_v0.1 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.1} | 19.2% | 1.20 | -0.39 | -10.2% | 32.7% | 60.4% |
| refine_r30.0_p0.025_g2.0 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 27.7% | 1.18 | -0.52 | -21.8% | 43.5% | 66.1% |
| annual_vol_limit_0.1 | {'annual_vol_limit': 0.1} | 23.7% | 1.18 | -0.36 | -20.6% | 38.1% | 69.0% |
| sector_limit_0.1 | {'sector_limit': 0.1} | 29.0% | 1.18 | -0.32 | -24.1% | 45.0% | 71.9% |
| risk_penalty_300.0 | {'risk_penalty': 300.0} | 25.3% | 1.17 | -0.40 | -20.9% | 39.7% | 69.5% |
| position_limit_0.015 | {'position_limit': 0.015} | 21.0% | 1.16 | -0.40 | -13.6% | 34.1% | 61.2% |
| beta_limit_0.2 | {'beta_limit': 0.2} | 30.6% | 1.15 | -0.42 | -26.9% | 46.0% | 70.2% |
| annual_vol_limit_0.15 | {'annual_vol_limit': 0.15} | 29.7% | 1.15 | -0.52 | -25.7% | 44.8% | 70.5% |
| gross_limit_1.5 | {'gross_limit': 1.5} | 26.0% | 1.15 | -0.45 | -26.1% | 39.9% | 53.1% |
| refine_r10.0_p0.015_v0.125 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.125} | 21.6% | 1.14 | -0.41 | -12.1% | 34.3% | 61.5% |
| refine_r30.0_p0.015_v0.125 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.125} | 21.6% | 1.14 | -0.41 | -12.1% | 34.2% | 61.4% |
| sector_limit_0.05 | {'sector_limit': 0.05} | 29.6% | 1.14 | -0.34 | -30.2% | 44.1% | 71.8% |
| beta_limit_0.1 | {'beta_limit': 0.1} | 30.8% | 1.13 | -0.48 | -27.5% | 45.3% | 70.2% |
| covariance_months_24 | {'covariance_months': 24} | 31.7% | 1.13 | -0.54 | -28.0% | 46.2% | 70.9% |
| beta_limit_0.05 | {'beta_limit': 0.05} | 30.9% | 1.12 | -0.50 | -27.5% | 45.1% | 70.1% |
| turnover_limit_2.0 | {'turnover_limit': 2.0} | 31.0% | 1.12 | -0.53 | -27.5% | 45.0% | 69.9% |
| cost_penalty_10.0 | {'cost_penalty': 10.0} | 31.0% | 1.12 | -0.54 | -26.7% | 45.1% | 65.8% |
| baseline | Current optimizer | 31.0% | 1.11 | -0.54 | -27.5% | 44.8% | 70.0% |
| annual_vol_limit_0.2 | {'annual_vol_limit': 0.2} | 31.0% | 1.11 | -0.54 | -27.5% | 44.8% | 70.0% |
| gross_limit_1.75 | {'gross_limit': 1.75} | 28.7% | 1.11 | -0.50 | -27.3% | 41.9% | 61.7% |
| gross_limit_1.25 | {'gross_limit': 1.25} | 23.0% | 1.11 | -0.39 | -26.8% | 35.0% | 44.3% |
| cost_penalty_50.0 | {'cost_penalty': 50.0} | 31.2% | 1.11 | -0.61 | -25.5% | 44.6% | 53.8% |
| position_limit_0.01 | {'position_limit': 0.01} | 18.4% | 1.10 | -0.34 | -11.7% | 29.4% | 53.5% |
| refine_r10.0_p0.025_g2.0 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 28.8% | 1.09 | -0.56 | -22.2% | 41.1% | 66.8% |
| turnover_limit_1.5 | {'turnover_limit': 1.5} | 31.3% | 1.08 | -0.54 | -27.5% | 43.8% | 66.9% |
| refine_r10.0_p0.025_g1.5 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 25.1% | 1.08 | -0.48 | -16.6% | 36.5% | 50.4% |
| refine_r3.0_p0.025_g2.0 | {'risk_penalty': 3.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 29.0% | 1.07 | -0.57 | -19.1% | 40.7% | 67.1% |
| refine_r30.0_p0.015_g1.5 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 19.0% | 1.05 | -0.41 | -13.5% | 28.8% | 47.2% |
| turnover_limit_1.0 | {'turnover_limit': 1.0} | 31.5% | 1.05 | -0.57 | -30.1% | 42.5% | 50.0% |
| sector_limit_0.025 | {'sector_limit': 0.025} | 30.1% | 1.04 | -0.35 | -36.3% | 40.4% | 71.1% |
| cost_penalty_100.0 | {'cost_penalty': 100.0} | 30.6% | 1.04 | -0.59 | -30.7% | 41.0% | 45.3% |
| cost_stress_35.0bps | {'trading_cost_bps': 35.0} | 31.0% | 1.03 | -0.54 | -29.8% | 41.4% | 69.6% |
| refine_r30.0_p0.015_v0.15 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.15} | 23.1% | 1.01 | -0.46 | -15.9% | 32.0% | 61.7% |
| refine_r10.0_p0.015_v0.15 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.15} | 23.2% | 1.01 | -0.47 | -15.9% | 32.1% | 61.9% |
| refine_r3.0_p0.025_g1.5 | {'risk_penalty': 3.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 25.6% | 1.00 | -0.49 | -17.4% | 34.4% | 50.8% |
| refine_r10.0_p0.015_g1.5 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 19.5% | 1.00 | -0.40 | -13.4% | 28.1% | 47.6% |
| turnover_limit_0.75 | {'turnover_limit': 0.75} | 31.9% | 1.00 | -0.59 | -35.2% | 40.7% | 37.5% |
| refine_r3.0_p0.015_g1.5 | {'risk_penalty': 3.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 19.7% | 1.00 | -0.40 | -12.3% | 28.3% | 47.9% |
| cost_penalty_300.0 | {'cost_penalty': 300.0} | 29.7% | 1.00 | -0.54 | -26.0% | 38.4% | 31.0% |
| refine_r30.0_p0.015_g2.0 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 23.0% | 0.99 | -0.46 | -15.0% | 31.4% | 61.9% |
| annual_vol_limit_0.075 | {'annual_vol_limit': 0.075} | 19.1% | 0.96 | -0.30 | -17.2% | 26.6% | 64.1% |
| cost_stress_50.0bps | {'trading_cost_bps': 50.0} | 31.0% | 0.95 | -0.54 | -32.3% | 38.0% | 69.3% |
| refine_r3.0_p0.015_g2.0 | {'risk_penalty': 3.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 24.1% | 0.92 | -0.49 | -16.0% | 30.3% | 62.2% |
| gross_limit_1.0 | {'gross_limit': 1.0} | 19.3% | 0.91 | -0.30 | -29.5% | 25.7% | 34.6% |
| risk_penalty_1000.0 | {'risk_penalty': 1000.0} | 17.9% | 0.90 | -0.28 | -15.1% | 24.3% | 62.4% |
| refine_r10.0_p0.015_g2.0 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 23.5% | 0.89 | -0.50 | -16.3% | 29.0% | 62.0% |
| gross_limit_0.75 | {'gross_limit': 0.75} | 15.9% | 0.78 | -0.19 | -27.4% | 20.2% | 24.9% |
| risk_penalty_3000.0 | {'risk_penalty': 3000.0} | 14.4% | 0.74 | -0.16 | -10.6% | 18.4% | 52.1% |
| annual_vol_limit_0.05 | {'annual_vol_limit': 0.05} | 13.6% | 0.71 | -0.15 | -9.6% | 17.2% | 49.8% |
| position_limit_0.005 | {'position_limit': 0.005} | 11.9% | 0.70 | -0.27 | -9.9% | 16.1% | 27.9% |
| cost_stress_100.0bps | {'trading_cost_bps': 100.0} | 31.0% | 0.69 | -0.54 | -40.0% | 27.4% | 68.3% |

Vol and return are annualized; returns are net of modeled trading costs. IR is against cash + 4%; beta is realized against the S&P 500. Turnover is monthly one-way trades / NAV. Same ranking and candidates for all rows.

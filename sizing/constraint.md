# Model comparison

Screened stocks. Follow-up starting-cap trials are included; see position_caps.md for month-end drift checks. Daily compliance is not certified.

2021-01 to 2026-08 · `current_gbm_no8k`

| Experiment | What changed | Vol | IR | Beta | Max drawdown | Return (CAGR) | Monthly turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| risk_penalty_10.0 | {'risk_penalty': 10.0} | 26.4% | 1.39 | -0.42 | -23.9% | 49.6% | 69.0% |
| gross_limit_1.5 | {'gross_limit': 1.5} | 16.9% | 1.35 | -0.16 | -19.2% | 32.9% | 53.3% |
| risk_penalty_30.0 | {'risk_penalty': 30.0} | 25.1% | 1.34 | -0.29 | -25.5% | 45.5% | 68.7% |
| covariance_months_60 | {'covariance_months': 60} | 20.0% | 1.32 | -0.23 | -21.5% | 37.1% | 70.7% |
| turnover_limit_1.0 | {'turnover_limit': 1.0} | 20.2% | 1.31 | -0.14 | -19.9% | 37.0% | 49.8% |
| gross_limit_1.25 | {'gross_limit': 1.25} | 14.6% | 1.30 | -0.16 | -17.4% | 28.5% | 44.3% |
| gross_limit_1.0 | {'gross_limit': 1.0} | 12.5% | 1.28 | -0.10 | -15.9% | 25.2% | 35.1% |
| gross_limit_1.75 | {'gross_limit': 1.75} | 19.6% | 1.28 | -0.14 | -21.4% | 35.3% | 61.7% |
| covariance_months_24 | {'covariance_months': 24} | 21.8% | 1.25 | -0.21 | -25.7% | 37.8% | 69.9% |
| beta_limit_None | {'beta_limit': None} | 22.6% | 1.25 | -0.10 | -22.4% | 38.7% | 70.6% |
| cost_penalty_100.0 | {'cost_penalty': 100.0} | 19.6% | 1.25 | -0.19 | -20.6% | 34.5% | 40.9% |
| cost_penalty_50.0 | {'cost_penalty': 50.0} | 21.1% | 1.24 | -0.12 | -23.0% | 36.4% | 51.3% |
| beta_limit_0.2 | {'beta_limit': 0.2} | 22.6% | 1.24 | -0.10 | -22.3% | 38.3% | 70.5% |
| beta_limit_0.1 | {'beta_limit': 0.1} | 22.3% | 1.22 | -0.11 | -22.6% | 37.5% | 70.4% |
| turnover_limit_2.0 | {'turnover_limit': 2.0} | 21.9% | 1.22 | -0.12 | -23.0% | 36.9% | 69.9% |
| beta_limit_0.05 | {'beta_limit': 0.05} | 22.1% | 1.22 | -0.11 | -22.7% | 37.1% | 70.3% |
| turnover_limit_1.5 | {'turnover_limit': 1.5} | 22.1% | 1.22 | -0.10 | -21.6% | 37.0% | 66.8% |
| annual_vol_limit_0.2 | {'annual_vol_limit': 0.2} | 21.9% | 1.22 | -0.12 | -23.2% | 36.8% | 70.2% |
| baseline | Current optimizer | 21.9% | 1.22 | -0.12 | -23.2% | 36.8% | 70.2% |
| annual_vol_limit_0.15 | {'annual_vol_limit': 0.15} | 21.9% | 1.21 | -0.12 | -23.2% | 36.6% | 70.1% |
| mix_g2.0_p0.025_c100.0 | {'gross_limit': 2.0, 'position_limit': 0.025, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 17.6% | 1.19 | -0.11 | -12.6% | 30.5% | 38.4% |
| cost_penalty_10.0 | {'cost_penalty': 10.0} | 22.1% | 1.17 | -0.13 | -24.0% | 35.8% | 65.4% |
| refine_r30.0_sector | {'risk_penalty': 30.0, 'position_limit': 0.025, 'sector_limit': 0.05, 'cost_penalty': 10.0} | 21.9% | 1.17 | -0.18 | -21.1% | 35.6% | 61.8% |
| annual_vol_limit_0.125 | {'annual_vol_limit': 0.125} | 21.1% | 1.17 | -0.09 | -22.4% | 34.4% | 70.3% |
| size_limit_0.1 | {'size_limit': 0.1} | 21.7% | 1.15 | -0.12 | -23.9% | 34.7% | 71.4% |
| size_limit_0.0 | {'size_limit': 0.0} | 21.9% | 1.15 | -0.13 | -24.5% | 34.8% | 71.7% |
| size_limit_0.05 | {'size_limit': 0.05} | 21.8% | 1.15 | -0.13 | -24.2% | 34.7% | 71.5% |
| gross_limit_0.75 | {'gross_limit': 0.75} | 9.7% | 1.15 | -0.06 | -12.2% | 19.7% | 24.2% |
| refine_r10.0_sector | {'risk_penalty': 10.0, 'position_limit': 0.025, 'sector_limit': 0.05, 'cost_penalty': 10.0} | 22.7% | 1.14 | -0.22 | -21.5% | 35.8% | 62.4% |
| g075_cap0.025 | 75% gross; 2.5% starting position cap | 8.3% | 1.13 | -0.12 | -8.9% | 17.7% | 23.6% |
| g075_cap0.020 | 75% gross; 2.0% starting position cap | 7.9% | 1.11 | -0.11 | -7.4% | 17.0% | 23.2% |
| cost_stress_35.0bps | {'trading_cost_bps': 35.0} | 22.0% | 1.10 | -0.12 | -24.4% | 33.4% | 69.8% |
| mix_g1.5_p0.025_c100.0 | {'gross_limit': 1.5, 'position_limit': 0.025, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 16.0% | 1.08 | -0.11 | -13.0% | 26.3% | 29.3% |
| sector_limit_0.1 | {'sector_limit': 0.1} | 22.0% | 1.05 | 0.05 | -23.6% | 32.3% | 76.6% |
| mix_g2.0_p0.025_c10.0 | {'gross_limit': 2.0, 'position_limit': 0.025, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 18.5% | 1.05 | -0.12 | -16.6% | 28.5% | 62.5% |
| mix_g1.5_p0.025_c10.0 | {'gross_limit': 1.5, 'position_limit': 0.025, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 16.3% | 1.04 | -0.10 | -14.5% | 25.7% | 48.7% |
| covariance_months_12 | {'covariance_months': 12} | 21.6% | 1.03 | -0.24 | -28.2% | 31.0% | 69.5% |
| mix_g1.0_p0.025_c10.0 | {'gross_limit': 1.0, 'position_limit': 0.025, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 12.1% | 1.02 | -0.02 | -13.4% | 20.9% | 32.8% |
| cost_penalty_300.0 | {'cost_penalty': 300.0} | 18.7% | 1.02 | -0.38 | -19.7% | 27.7% | 26.0% |
| annual_vol_limit_0.1 | {'annual_vol_limit': 0.1} | 19.2% | 1.00 | -0.03 | -21.2% | 27.8% | 70.7% |
| cost_stress_50.0bps | {'trading_cost_bps': 50.0} | 22.0% | 0.98 | -0.12 | -25.5% | 30.1% | 69.4% |
| g075_cap0.015 | 75% gross; 1.5% starting position cap | 7.6% | 0.98 | -0.10 | -7.0% | 15.5% | 22.2% |
| refine_r30.0_p0.025_g1.5 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 16.8% | 0.97 | -0.21 | -19.1% | 24.6% | 49.2% |
| sector_limit_0.05 | {'sector_limit': 0.05} | 22.1% | 0.94 | 0.04 | -24.1% | 29.1% | 76.5% |
| risk_penalty_300.0 | {'risk_penalty': 300.0} | 18.2% | 0.92 | -0.03 | -18.8% | 25.0% | 70.7% |
| refine_r10.0_p0.025_g1.5 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 18.1% | 0.91 | -0.26 | -20.1% | 24.8% | 48.9% |
| mix_g1.5_p0.01_c100.0 | {'gross_limit': 1.5, 'position_limit': 0.01, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 11.5% | 0.89 | -0.12 | -8.1% | 18.3% | 27.7% |
| mix_g1.0_p0.01_c100.0 | {'gross_limit': 1.0, 'position_limit': 0.01, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 9.1% | 0.89 | -0.08 | -5.7% | 16.2% | 18.7% |
| sector_limit_0.025 | {'sector_limit': 0.025} | 21.7% | 0.85 | 0.03 | -26.5% | 26.4% | 76.3% |
| refine_r3.0_p0.025_g1.5 | {'risk_penalty': 3.0, 'position_limit': 0.025, 'gross_limit': 1.5} | 18.7% | 0.85 | -0.29 | -20.1% | 23.9% | 48.8% |
| mix_g1.0_p0.025_c100.0 | {'gross_limit': 1.0, 'position_limit': 0.025, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 12.7% | 0.84 | -0.05 | -12.5% | 18.7% | 19.9% |
| refine_r30.0_p0.025_g2.0 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 20.6% | 0.81 | -0.25 | -25.3% | 24.3% | 65.7% |
| mix_g1.5_p0.01_c10.0 | {'gross_limit': 1.5, 'position_limit': 0.01, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 11.8% | 0.80 | -0.17 | -9.8% | 17.5% | 40.4% |
| position_limit_0.025 | {'position_limit': 0.025} | 18.5% | 0.79 | -0.19 | -22.4% | 22.4% | 65.0% |
| refine_r10.0_p0.025_g2.0 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 22.3% | 0.79 | -0.32 | -27.8% | 25.1% | 65.6% |
| mix_g2.0_p0.01_c100.0 | {'gross_limit': 2.0, 'position_limit': 0.01, 'cost_penalty': 100.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 14.5% | 0.77 | -0.16 | -9.7% | 19.1% | 36.9% |
| refine_r30.0_p0.025_v0.125 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'annual_vol_limit': 0.125} | 19.5% | 0.77 | -0.19 | -24.9% | 22.6% | 65.7% |
| refine_r30.0_p0.025_v0.15 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'annual_vol_limit': 0.15} | 20.4% | 0.76 | -0.23 | -25.3% | 23.1% | 65.7% |
| mix_g1.0_p0.01_c10.0 | {'gross_limit': 1.0, 'position_limit': 0.01, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 9.1% | 0.76 | -0.09 | -7.3% | 14.8% | 28.3% |
| refine_r30.0_p0.025_v0.1 | {'risk_penalty': 30.0, 'position_limit': 0.025, 'annual_vol_limit': 0.1} | 17.9% | 0.76 | -0.16 | -23.1% | 21.1% | 65.6% |
| refine_r10.0_p0.025_v0.1 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.1} | 17.9% | 0.76 | -0.16 | -23.1% | 21.1% | 65.6% |
| refine_r3.0_p0.025_g2.0 | {'risk_penalty': 3.0, 'position_limit': 0.025, 'gross_limit': 2.0} | 23.3% | 0.74 | -0.36 | -27.7% | 24.4% | 66.2% |
| refine_r10.0_p0.025_v0.125 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.125} | 19.9% | 0.74 | -0.20 | -27.2% | 22.1% | 65.8% |
| refine_r10.0_p0.025_v0.15 | {'risk_penalty': 10.0, 'position_limit': 0.025, 'annual_vol_limit': 0.15} | 21.1% | 0.72 | -0.24 | -27.3% | 22.4% | 66.0% |
| refine_r10.0_p0.015_g2.0 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 17.2% | 0.70 | -0.30 | -15.2% | 19.5% | 60.4% |
| annual_vol_limit_0.075 | {'annual_vol_limit': 0.075} | 16.3% | 0.69 | -0.04 | -17.1% | 18.7% | 69.2% |
| refine_r10.0_p0.015_v0.15 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.15} | 17.2% | 0.69 | -0.29 | -15.2% | 19.3% | 60.4% |
| refine_r30.0_p0.015_g2.0 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 16.6% | 0.68 | -0.26 | -16.0% | 18.7% | 60.0% |
| refine_r30.0_p0.015_v0.15 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.15} | 16.6% | 0.68 | -0.26 | -16.0% | 18.7% | 60.0% |
| refine_r10.0_p0.015_v0.125 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.125} | 16.3% | 0.66 | -0.25 | -15.4% | 18.2% | 60.1% |
| refine_r3.0_p0.015_g1.5 | {'risk_penalty': 3.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 15.5% | 0.66 | -0.26 | -15.9% | 17.6% | 46.1% |
| mix_g2.0_p0.01_c10.0 | {'gross_limit': 2.0, 'position_limit': 0.01, 'cost_penalty': 10.0, 'sector_limit': 0.05, 'size_limit': 0.1, 'annual_vol_limit': 0.1} | 14.3% | 0.65 | -0.18 | -12.2% | 16.8% | 48.2% |
| refine_r30.0_p0.015_v0.125 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.125} | 16.3% | 0.64 | -0.26 | -16.0% | 17.9% | 60.0% |
| refine_r3.0_p0.015_g2.0 | {'risk_penalty': 3.0, 'position_limit': 0.015, 'gross_limit': 2.0} | 18.0% | 0.64 | -0.30 | -15.6% | 18.8% | 60.5% |
| refine_r30.0_p0.015_g1.5 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 14.3% | 0.64 | -0.20 | -16.0% | 16.6% | 46.3% |
| g075_cap0.010 | 75% gross; 1.0% starting position cap | 7.0% | 0.63 | -0.09 | -7.1% | 12.2% | 21.6% |
| refine_r10.0_p0.015_v0.1 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'annual_vol_limit': 0.1} | 15.1% | 0.63 | -0.21 | -16.9% | 16.9% | 59.9% |
| refine_r30.0_p0.015_v0.1 | {'risk_penalty': 30.0, 'position_limit': 0.015, 'annual_vol_limit': 0.1} | 15.1% | 0.63 | -0.21 | -16.9% | 16.9% | 59.9% |
| position_limit_0.015 | {'position_limit': 0.015} | 15.0% | 0.63 | -0.22 | -15.5% | 16.8% | 59.4% |
| refine_r10.0_p0.015_g1.5 | {'risk_penalty': 10.0, 'position_limit': 0.015, 'gross_limit': 1.5} | 15.0% | 0.60 | -0.24 | -15.8% | 16.4% | 46.2% |
| cost_stress_100.0bps | {'trading_cost_bps': 100.0} | 22.2% | 0.60 | -0.13 | -29.1% | 19.8% | 68.2% |
| position_limit_0.01 | {'position_limit': 0.01} | 14.2% | 0.55 | -0.25 | -13.5% | 15.2% | 52.1% |
| risk_penalty_1000.0 | {'risk_penalty': 1000.0} | 13.9% | 0.46 | -0.06 | -14.5% | 13.5% | 65.6% |
| position_limit_0.005 | {'position_limit': 0.005} | 9.7% | 0.41 | -0.16 | -7.1% | 11.4% | 25.9% |
| annual_vol_limit_0.05 | {'annual_vol_limit': 0.05} | 11.9% | 0.15 | -0.05 | -12.6% | 8.7% | 61.4% |
| risk_penalty_3000.0 | {'risk_penalty': 3000.0} | 10.5% | 0.01 | -0.05 | -9.5% | 7.1% | 56.3% |

Vol and return are annualized; returns are net of modeled trading costs. IR is against cash + 4%; beta is realized against the S&P 500. Turnover is monthly one-way trades / NAV. Same ranking and candidates for all rows.

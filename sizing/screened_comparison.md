# Screened portfolio comparison

> **Audit of the 75%-gross row:** the numbers reproduce, but sector net exposure reaches 31% of NAV, the top ten positions average 52% of gross, and missing returns include a 5% short marked at zero. This is not a validated neutral portfolio. See screened_075_audit.md.

2021-01 to 2026-08 · current_gbm_no8k · 68 months

Price >=$5, excluding nano/micro-cap stocks; short market cap >=$500m. Identical rankings and candidates for all configurations. 84 pre-existing optimizer settings plus the beta-matched reference; no new tuning.

83 completed; 2 failed. Failed histories are excluded from rankings.

## Read this comparison first

| Configuration | CAGR | Volatility | IR | Beta | Max drawdown | Monthly turnover |
| --- | --- | --- | --- | --- | --- | --- |
| Beta-matched reference (`beta_matched`) | 13.4% | 10.1% | 0.57 | -0.15 | -5.6% | 49.1% |
| Optimizer with the same 1.5% position cap (`position_limit_0.015`) | 16.8% | 15.0% | 0.63 | -0.22 | -15.5% | 59.4% |
| Optimizer at 75% gross (5% position cap) (`gross_limit_0.75`) | 19.7% | 9.7% | 1.15 | -0.06 | -12.2% | 24.2% |
| Screened default optimizer (`baseline`) | 36.8% | 21.9% | 1.22 | -0.12 | -23.2% | 70.2% |
| Previous unscreened winner, now screened (`refine_r30.0_sector`) | 35.6% | 21.9% | 1.17 | -0.18 | -21.1% | 61.8% |
| Highest screened IR (`risk_penalty_10.0`) | 49.6% | 26.4% | 1.39 | -0.42 | -23.9% | 69.0% |
| Highest IR with realized volatility <=15% (`gross_limit_1.25`) | 28.5% | 14.6% | 1.30 | -0.16 | -17.4% | 44.3% |

## Effect of applying the screen

| Configuration | CAGR before | CAGR screened | IR before | IR screened |
| --- | --- | --- | --- | --- |
| baseline | 44.8% | 36.8% | 1.11 | 1.22 |
| refine_r30.0_sector | 54.7% | 35.6% | 1.42 | 1.17 |

## All completed configurations

| Configuration | CAGR | Volatility | IR | Beta | Max drawdown | Monthly turnover |
| --- | --- | --- | --- | --- | --- | --- |
| risk_penalty_10.0 | 49.6% | 26.4% | 1.39 | -0.42 | -23.9% | 69.0% |
| gross_limit_1.5 | 32.9% | 16.9% | 1.35 | -0.16 | -19.2% | 53.3% |
| risk_penalty_30.0 | 45.5% | 25.1% | 1.34 | -0.29 | -25.5% | 68.7% |
| covariance_months_60 | 37.1% | 20.0% | 1.32 | -0.23 | -21.5% | 70.7% |
| turnover_limit_1.0 | 37.0% | 20.2% | 1.31 | -0.14 | -19.9% | 49.8% |
| gross_limit_1.25 | 28.5% | 14.6% | 1.30 | -0.16 | -17.4% | 44.3% |
| gross_limit_1.0 | 25.2% | 12.5% | 1.28 | -0.10 | -15.9% | 35.1% |
| gross_limit_1.75 | 35.3% | 19.6% | 1.28 | -0.14 | -21.4% | 61.7% |
| covariance_months_24 | 37.8% | 21.8% | 1.25 | -0.21 | -25.7% | 69.9% |
| beta_limit_None | 38.7% | 22.6% | 1.25 | -0.10 | -22.4% | 70.6% |
| cost_penalty_100.0 | 34.5% | 19.6% | 1.25 | -0.19 | -20.6% | 40.9% |
| cost_penalty_50.0 | 36.4% | 21.1% | 1.24 | -0.12 | -23.0% | 51.3% |
| beta_limit_0.2 | 38.3% | 22.6% | 1.24 | -0.10 | -22.3% | 70.5% |
| beta_limit_0.1 | 37.5% | 22.3% | 1.22 | -0.11 | -22.6% | 70.4% |
| turnover_limit_2.0 | 36.9% | 21.9% | 1.22 | -0.12 | -23.0% | 69.9% |
| beta_limit_0.05 | 37.1% | 22.1% | 1.22 | -0.11 | -22.7% | 70.3% |
| turnover_limit_1.5 | 37.0% | 22.1% | 1.22 | -0.10 | -21.6% | 66.8% |
| annual_vol_limit_0.2 | 36.8% | 21.9% | 1.22 | -0.12 | -23.2% | 70.2% |
| baseline | 36.8% | 21.9% | 1.22 | -0.12 | -23.2% | 70.2% |
| annual_vol_limit_0.15 | 36.6% | 21.9% | 1.21 | -0.12 | -23.2% | 70.1% |
| mix_g2.0_p0.025_c100.0 | 30.5% | 17.6% | 1.19 | -0.11 | -12.6% | 38.4% |
| cost_penalty_10.0 | 35.8% | 22.1% | 1.17 | -0.13 | -24.0% | 65.4% |
| refine_r30.0_sector | 35.6% | 21.9% | 1.17 | -0.18 | -21.1% | 61.8% |
| annual_vol_limit_0.125 | 34.4% | 21.1% | 1.17 | -0.09 | -22.4% | 70.3% |
| size_limit_0.1 | 34.7% | 21.7% | 1.15 | -0.12 | -23.9% | 71.4% |
| size_limit_0.0 | 34.8% | 21.9% | 1.15 | -0.13 | -24.5% | 71.7% |
| size_limit_0.05 | 34.7% | 21.8% | 1.15 | -0.13 | -24.2% | 71.5% |
| gross_limit_0.75 | 19.7% | 9.7% | 1.15 | -0.06 | -12.2% | 24.2% |
| refine_r10.0_sector | 35.8% | 22.7% | 1.14 | -0.22 | -21.5% | 62.4% |
| cost_stress_35.0bps | 33.4% | 22.0% | 1.10 | -0.12 | -24.4% | 69.8% |
| mix_g1.5_p0.025_c100.0 | 26.3% | 16.0% | 1.08 | -0.11 | -13.0% | 29.3% |
| sector_limit_0.1 | 32.3% | 22.0% | 1.05 | 0.05 | -23.6% | 76.6% |
| mix_g2.0_p0.025_c10.0 | 28.5% | 18.5% | 1.05 | -0.12 | -16.6% | 62.5% |
| mix_g1.5_p0.025_c10.0 | 25.7% | 16.3% | 1.04 | -0.10 | -14.5% | 48.7% |
| covariance_months_12 | 31.0% | 21.6% | 1.03 | -0.24 | -28.2% | 69.5% |
| mix_g1.0_p0.025_c10.0 | 20.9% | 12.1% | 1.02 | -0.02 | -13.4% | 32.8% |
| cost_penalty_300.0 | 27.7% | 18.7% | 1.02 | -0.38 | -19.7% | 26.0% |
| annual_vol_limit_0.1 | 27.8% | 19.2% | 1.00 | -0.03 | -21.2% | 70.7% |
| cost_stress_50.0bps | 30.1% | 22.0% | 0.98 | -0.12 | -25.5% | 69.4% |
| refine_r30.0_p0.025_g1.5 | 24.6% | 16.8% | 0.97 | -0.21 | -19.1% | 49.2% |
| sector_limit_0.05 | 29.1% | 22.1% | 0.94 | 0.04 | -24.1% | 76.5% |
| risk_penalty_300.0 | 25.0% | 18.2% | 0.92 | -0.03 | -18.8% | 70.7% |
| refine_r10.0_p0.025_g1.5 | 24.8% | 18.1% | 0.91 | -0.26 | -20.1% | 48.9% |
| mix_g1.5_p0.01_c100.0 | 18.3% | 11.5% | 0.89 | -0.12 | -8.1% | 27.7% |
| mix_g1.0_p0.01_c100.0 | 16.2% | 9.1% | 0.89 | -0.08 | -5.7% | 18.7% |
| sector_limit_0.025 | 26.4% | 21.7% | 0.85 | 0.03 | -26.5% | 76.3% |
| refine_r3.0_p0.025_g1.5 | 23.9% | 18.7% | 0.85 | -0.29 | -20.1% | 48.8% |
| mix_g1.0_p0.025_c100.0 | 18.7% | 12.7% | 0.84 | -0.05 | -12.5% | 19.9% |
| refine_r30.0_p0.025_g2.0 | 24.3% | 20.6% | 0.81 | -0.25 | -25.3% | 65.7% |
| mix_g1.5_p0.01_c10.0 | 17.5% | 11.8% | 0.80 | -0.17 | -9.8% | 40.4% |
| position_limit_0.025 | 22.4% | 18.5% | 0.79 | -0.19 | -22.4% | 65.0% |
| refine_r10.0_p0.025_g2.0 | 25.1% | 22.3% | 0.79 | -0.32 | -27.8% | 65.6% |
| mix_g2.0_p0.01_c100.0 | 19.1% | 14.5% | 0.77 | -0.16 | -9.7% | 36.9% |
| refine_r30.0_p0.025_v0.125 | 22.6% | 19.5% | 0.77 | -0.19 | -24.9% | 65.7% |
| refine_r30.0_p0.025_v0.15 | 23.1% | 20.4% | 0.76 | -0.23 | -25.3% | 65.7% |
| mix_g1.0_p0.01_c10.0 | 14.8% | 9.1% | 0.76 | -0.09 | -7.3% | 28.3% |
| refine_r30.0_p0.025_v0.1 | 21.1% | 17.9% | 0.76 | -0.16 | -23.1% | 65.6% |
| refine_r10.0_p0.025_v0.1 | 21.1% | 17.9% | 0.76 | -0.16 | -23.1% | 65.6% |
| refine_r3.0_p0.025_g2.0 | 24.4% | 23.3% | 0.74 | -0.36 | -27.7% | 66.2% |
| refine_r10.0_p0.025_v0.125 | 22.1% | 19.9% | 0.74 | -0.20 | -27.2% | 65.8% |
| refine_r10.0_p0.025_v0.15 | 22.4% | 21.1% | 0.72 | -0.24 | -27.3% | 66.0% |
| refine_r10.0_p0.015_g2.0 | 19.5% | 17.2% | 0.70 | -0.30 | -15.2% | 60.4% |
| annual_vol_limit_0.075 | 18.7% | 16.3% | 0.69 | -0.04 | -17.1% | 69.2% |
| refine_r10.0_p0.015_v0.15 | 19.3% | 17.2% | 0.69 | -0.29 | -15.2% | 60.4% |
| refine_r30.0_p0.015_g2.0 | 18.7% | 16.6% | 0.68 | -0.26 | -16.0% | 60.0% |
| refine_r30.0_p0.015_v0.15 | 18.7% | 16.6% | 0.68 | -0.26 | -16.0% | 60.0% |
| refine_r10.0_p0.015_v0.125 | 18.2% | 16.3% | 0.66 | -0.25 | -15.4% | 60.1% |
| refine_r3.0_p0.015_g1.5 | 17.6% | 15.5% | 0.66 | -0.26 | -15.9% | 46.1% |
| mix_g2.0_p0.01_c10.0 | 16.8% | 14.3% | 0.65 | -0.18 | -12.2% | 48.2% |
| refine_r30.0_p0.015_v0.125 | 17.9% | 16.3% | 0.64 | -0.26 | -16.0% | 60.0% |
| refine_r3.0_p0.015_g2.0 | 18.8% | 18.0% | 0.64 | -0.30 | -15.6% | 60.5% |
| refine_r30.0_p0.015_g1.5 | 16.6% | 14.3% | 0.64 | -0.20 | -16.0% | 46.3% |
| refine_r10.0_p0.015_v0.1 | 16.9% | 15.1% | 0.63 | -0.21 | -16.9% | 59.9% |
| refine_r30.0_p0.015_v0.1 | 16.9% | 15.1% | 0.63 | -0.21 | -16.9% | 59.9% |
| position_limit_0.015 | 16.8% | 15.0% | 0.63 | -0.22 | -15.5% | 59.4% |
| refine_r10.0_p0.015_g1.5 | 16.4% | 15.0% | 0.60 | -0.24 | -15.8% | 46.2% |
| cost_stress_100.0bps | 19.8% | 22.2% | 0.60 | -0.13 | -29.1% | 68.2% |
| beta_matched | 13.4% | 10.1% | 0.57 | -0.15 | -5.6% | 49.1% |
| position_limit_0.01 | 15.2% | 14.2% | 0.55 | -0.25 | -13.5% | 52.1% |
| risk_penalty_1000.0 | 13.5% | 13.9% | 0.46 | -0.06 | -14.5% | 65.6% |
| position_limit_0.005 | 11.4% | 9.7% | 0.41 | -0.16 | -7.1% | 25.9% |
| annual_vol_limit_0.05 | 8.7% | 11.9% | 0.15 | -0.05 | -12.6% | 61.4% |
| risk_penalty_3000.0 | 7.1% | 10.5% | 0.01 | -0.05 | -9.5% | 56.3% |

The beta-matched reference uses a 1.5% position cap; optimizer caps and other settings are recorded per trial in screened_summary.csv. Optimizer trials require 0.1% minimum positions; the reference retains its original inverse-volatility sizing without this floor.

Returns include modeled trading costs. The baseline uses 20 bps on buys plus sells; the three cost-stress trials use their declared higher charge. Borrow and market impact are omitted. The screen is an eligibility proxy, not a capacity guarantee. IR is versus cash +4%; beta is realized against S&P 500 price returns.

screened_vs_unscreened.csv pairs each optimizer setting before and after the screen. Both rankings and candidates change when screening is applied. These are retrospective comparisons on previously examined years.

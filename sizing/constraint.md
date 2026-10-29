# Model comparison

2021-01 to 2026-08 · `current_gbm_no8k`

| Experiment | What changed | Vol | IR | Beta | Max drawdown | Return (CAGR) | Monthly turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | Current optimizer | 31.0% | 1.11 | -0.54 | -27.5% | 44.8% | 70.0% |
| vol_15pct | Estimated annual vol capped at 15% | 29.7% | 1.15 | -0.52 | -25.7% | 44.8% | 70.5% |
| gross_150pct | Gross exposure capped at 150% | 26.0% | 1.15 | -0.45 | -26.1% | 39.9% | 53.1% |

Vol and return are annualized; returns are net of modeled trading costs. IR is against cash + 4%; beta is realized against the S&P 500. Turnover is monthly one-way trades / NAV. Same ranking and candidates for all rows.

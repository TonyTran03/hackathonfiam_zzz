# Audit of the 75%-gross screened optimizer

The monthly return series was independently rebuilt from the saved forecast file and current screened stages. It reproduces the saved series within 1e-8. Reported CAGR, volatility, IR, exposure limits, and modeled cost deductions recalculate correctly. This verifies implementation consistency, not investability or freedom from upstream data problems.

- Gross exposure is 75% of NAV, versus 200% for the beta-matched reference. The position cap is 5% of NAV, versus 1.5% for the reference.
- Despite holding 300 names, average effective position count is about 32, calculated as gross exposure squared divided by the sum of squared weights. The top ten positions average 51.8% of gross exposure, reaching 61.3%.
- There is no hard sector bound. Maximum absolute sector net exposure reaches 31.0% of NAV. Estimated market-beta matching does not establish sector neutrality.
- IR is 1.61 in 2021–2023 and 0.63 in 2024–August 2026. CAGR is 24.2% and 14.9%, respectively. Neither subperiod is an untouched allocation holdout.
- Missing realized returns are marked at zero. Largest missing holding: a 5.0% short in PAND (Pandion Therapeutics), April 2021. Another is a 3.8% short in FWDI, December 2025. Their actual returns must be recovered before relying on the portfolio accounting. Zero marking can overstate or understate P&L.
- Modeled trading costs average 1.16% of NAV per year, using the sum of monthly cost fractions divided by elapsed years. Borrow and market impact remain omitted.

The result is a research candidate, not a validated market-neutral or capacity-compliant portfolio. Resolve missing outcomes, apply the actual updated sector/volatility mandate, and assess liquidity and borrow costs before presenting it as implementable.

Files: screened_075_audit.csv contains monthly concentration diagnostics; screened_075_missing_returns.csv identifies every missing outcome; screened_075_audit_holdings.parquet preserves all reconstructed holdings.

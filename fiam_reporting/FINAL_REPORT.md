> Updated: use [LEDGER_HANDOFF.md](LEDGER_HANDOFF.md) for corrected turnover, contributors and actual executed holdings. The earlier export-only workflow below produces a draft when no audit ledger is supplied. The final code and exported inputs are also on main; ZIP extraction is unnecessary after merging main.

# Final report from the 06_final export

Use final_report.py for the final strategy; report.py remains the round-one regression baseline.

Unzip the team's 06_final.zip at the repository root so 06_final/output/test_M/daily_returns.csv exists. This adapter needs only the supplied CSV exports, not the raw data or engine intermediates. It does not modify the strategy or regenerate signals.

From the repository root:

```bash
python -m pip install -r fiam_reporting/requirements.txt
python fiam_reporting/final_report.py --inputs 06_final/output/test_M --output fiam_reporting/output_final --factor-cache fiam_reporting/factor_cache
python -m unittest discover -s fiam_reporting/tests -v
```

Open fiam_reporting/output_final/report.html. It contains English-only text, the exact 23-row/four-column Section 9.1 layout, separately labelled CAGR, all eight interactive Section 9.4 exhibits, official FF5 + momentum regressions, and supplied hit-rate/alpha-decay diagnostics. Hover, zoom, pan, toggle legends, and export PNGs using the chart toolbar. Plotly is embedded, so the generated report works offline.

The first factor run downloads official Kenneth French US monthly five-factor and momentum ZIPs; subsequent runs reuse the cache. Preserve cache files and sources.json to reproduce the factor vintage. No missing month is silently dropped. FF5+momentum uses French RF, not the team's TB3MS series. Alpha is estimated monthly and annualised by 12. Standard errors are conventional OLS; they are not HAC. Both net and gross models are exported.

## Outputs

- section9_table.csv: submission-shaped presentation table.
- report.html: offline interactive report.
- market_regressions.csv: monthly/daily, gross/net alpha and beta with standard errors.
- ff5_momentum_attribution.csv and factor_regression_sample.csv: complete factor results and the aligned sample.
- calendar_years.csv and rolling_beta.csv: recomputed exhibit data.
- exhibit_1.json through exhibit_8.json: Plotly figure specifications.
- validation.json: input hashes, factor URLs/hashes, checks and limitations.
- hit_rate.csv, alpha_decay.csv and sizing_vs_selection.csv: copied supplied diagnostics, when present.

## Reporting conventions and corrections

NAV must reconcile with compounded net returns and the gross/net return gap must reconcile with cost plus borrow dollars divided by beginning-of-day NAV. The provisional daily hurdle must equal supplied rf + 0.04/252. Failure stops generation.

The main table uses net performance except the first IR and tracking error, which use gross returns; the last IR is net. All bases are disclosed. Monthly/daily net regressions are recomputed, and gross counterparts are provided separately. Drawdown includes the initial endowment. An always-positive benchmark has zero maximum loss. All daily exposure observations, including initial formation, are included.

Cost percentages sum each day's dollar cost divided by that day's beginning NAV, then annualise by 252 / observed days. They differ slightly from the original total-cost / average-NAV method. Calendar returns compound daily observations and label partial calendar years. Monthly regressions use compounded daily cash and market returns to keep observations aligned.

Cumulative active performance is relative compounded wealth (strategy wealth / benchmark wealth - 1), with gross/net and S&P price context. This is explicitly disclosed because Section 9.4 does not prescribe an aggregation formula. The S&P input is price-only.

## Limits requiring the team's detailed ledger

The ZIP does not include daily per-stock positions, trades, or signals. Therefore:

- Turnover is aggregated from the supplied daily engine field, not independently rebuilt under Section 9.3. The average is over dates with nonzero turnover; annualisation uses their observed frequency, including carried orders and risk trades. The engine's dollar-trade approximation and NAV denominators must be reconciled with exact pre/post-trade weights before certification.
- Holding period and average position size come from the supplied standard_table.csv.
- Top/bottom average holdings and stock contributors are supplied exports, not recalculated. Names may use later reference dates. Stock contributor P&L is divided by initial NAV and excludes portfolio cash/cost allocations.
- Market cap and ADV plots describe formation targets, not all actual executed positions. A passing target short-floor check is not proof of execution-level compliance. With the audited ledger, Exhibit 7 and the short-book median instead use held short positions and prior-month-end panel `me`; see LEDGER_HANDOFF.md.
- Hit-rate and alpha-decay diagnostics are preserved and explicitly labelled as supplied. Recomputing them requires position episodes and dated signals.
- Gross return adds costs back to the realised net-funded path; it is not an independent zero-cost portfolio simulation.

The report is suitable for reviewing the supplied exports, but does not certify all strategy rules or Arcana compatibility. Arcana import has not been performed.

## Checks on the supplied package

The headline test_M export passes the accounting, complete-factor-coverage, and required chart-input checks. The comparison test_Q export has 228 missing me_form values among 8,205 formation rows; strict validation rejects it instead of omitting those observations silently. Repair those input characteristics before reporting test_Q with this adapter.


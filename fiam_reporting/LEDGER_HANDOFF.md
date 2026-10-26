# Corrected reporting and daily-position handoff

## What changed

The patched engine records pre-trade and post-trade stock weights and computes Section 9.3 turnover as half their absolute difference summed across names. Trading costs change the NAV denominator; the older half-dollar-trades/NAV field is retained only as turnover_dollar_proxy. Turnover is a daily-close measure, including zero-trade dates, with arithmetic annualisation by 252. Monthly target formation and carried-order execution are different schedules; the report now states the daily basis explicitly.

Delisting settlement P&L is added to the per-stock P&L ledger with pnl_kind=delisting. Portfolio returns and trading decisions are unchanged by these audit additions. The ledger validator requires per-stock market plus delisting P&L + cash income - trading costs - borrow costs to reconcile to every NAV change.

## Run on the machine with the engine's existing data

From the repository root, after obtaining the patched bohan branch:

```bash
python 06_final/f03_engine.py --window test --freq M --output-tag test_M_audited
python 06_final/f06_report.py test_M_audited
python fiam_reporting/final_report.py --inputs 06_final/output/test_M_audited --ledger-dir 06_final/data/runs/test_M_audited --output fiam_reporting/output_final_audited --require-verified
```

This reuses the existing calendar, daily returns, monthly signals and forecasts. It does not retrain the prediction model. Do not run MAIN.py or run_all.sh merely to rebuild this report. Preserve the original test_M directory. If the run configuration has changed from the headline monthly/no-layer strategy, use the corresponding engine arguments and a matching output tag.

An older output/test_M export can be used with the new ledger only if its dates, NAV, gross/net returns, and costs match. The adapter rejects stale or mismatched exports. --require-verified also rejects missing chart names/liquidity, observed short-floor breaches, or daily aggregate mandate breaches. It does not validate raw price/share data quality or grant permission to use external data.

FF5 + momentum remain optional; append --factor-cache fiam_reporting/factor_cache only if the team elects to use those data.

## Files your teammate should share

The engine saves these under 06_final/data/runs/test_M_audited/:

- daily.parquet: daily accounting, cash income and corrected turnover.
- position_audit.parquet: date, permno, pre/post dollar positions, pre/post NAV and weights, market cap estimate, ADV and its as-of date. Zero closing positions are retained when needed to verify exits.
- pnl.parquet: per-stock ordinary and delisting P&L, explicitly distinguished.
- executions.parquet: each actual fill, before/after dollar position, trade amount, market cap, ADV, and whether ADV was observed or a fallback.

Also share 06_final/output/test_M_audited/ (the exported report inputs). To name every newly ranked stock, share the matching 06_final/data/signal_test.parquet or ensure the exported top_holdings/contributors contain all names. These data files are intentionally ignored by Git. A Git pull obtains code, not these local intermediate files. Zip the run folder and share it directly if the reporting machine does not have it.

The final adapter writes daily_positions.csv, all_average_holdings.csv, all_stock_contributors.csv, holding_spells.csv, short_executions.csv, execution_participation.csv and daily_returns_verified.csv into its output directory.

## Exact definitions and limitations

- Top/bottom holdings are recomputed over every end-of-day observation. Absent names have zero weight. The full universe's average weights are exported before selecting the top/bottom ten.
- Holding periods are consecutive same-side end-of-day spells, weighted by mean absolute position dollars. Spells at the sample boundary are censored; only observed days count, and censored-spell counts are disclosed.
- Average position size is the mean absolute dollar position across held name/day observations. Changing the teammate's old summary table is unnecessary in verified mode: these values are recomputed from positions.
- Contributors include all per-stock P&L, including delisting settlements, as percent of starting NAV. Cash and portfolio costs are separate; all components reconcile to daily NAV.
- Exhibit 7 describes actual short openings/additions, not unfilled targets. The $500m floor is checked at each such fill; passive drift below the floor is not an opening violation. Market cap uses the engine's most recently stored shares and the execution-date price. This estimate still needs raw-data validation around splits/share changes.
- Exhibit 8 describes actual held name/day position dollars divided by the engine's available 126-day ADV. ADV can be older than the observation; its source month-end is exported. It is not advertised as a freshly recomputed daily ADV series.
- Execution participation (trade dollars / ADV) is exported separately, including daily totals per name. It is different from position dollars / ADV. Missing values, fallback ADV and participation above 10% are reported, not hidden.
- Imported hit-rate, alpha-decay and sizing diagnostics are not independently rebuilt by this adapter. Rerun f07_diagnostics.py on the audited tag if those diagnostics need refreshed inputs, and review their definitions separately.
- With no corrected ledger, the adapter produces only a draft: turnover is pending and the known-incomplete contributor chart is withheld. It does not certify the old exports.

## Validation performed

Focused tests cover cost-induced NAV changes in turnover, delisting inclusion, full cash/P&L reconciliation, zero-weight months/days in average holdings, measured holding spells, and rejection of omitted delisting P&L and proxy turnover. An end-to-end synthetic 260-day, 300-stock run verifies engine -> Parquet ledger -> report. A development comparison against the original engine confirmed identical NAV, return, cost, exposure and trade outputs in the targeted toy run. The actual 2021-2026 rerun must be performed with the team's local intermediate data; it has not been claimed as completed here.

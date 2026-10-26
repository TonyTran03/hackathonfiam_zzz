> Turnover/delisting fixes and actual-position reporting: see [LEDGER_HANDOFF.md](LEDGER_HANDOFF.md). A corrected ledger rerun is required to verify the final report.

> For the final 06_final exports, use [FINAL_REPORT.md](FINAL_REPORT.md) and final_report.py. The instructions below describe the older round-one baseline.

# FIAM reporting — stage 1

This standalone module implements the first reporting milestone on the actual first-round submission. No model retraining, trading or GitHub changes are required.

## Run

From your repository checkout, open a terminal in `fiam_reporting`:

```bash
python -m pip install -r requirements.txt
python report.py --inputs inputs --output output --verify-round1
python -m unittest discover -s tests -v
```

Open `output/report.html` in a browser. The report works offline: Plotly JavaScript is embedded once.


## Outputs

- `performance_summary.csv`: Section 9.1 presentation table: 23 rows in prescribed order, four columns, percentages and US$ billion/million as specified. Unavailable values say Pending; non-applicable benchmark cells say n/a. Annualised return is arithmetic; CAGR is separately reported in HTML.
- `metric_diagnostics.csv`: supplemental raw numeric statistics, statuses and limitations; returns are decimals.
- `yearly_returns.csv`: compounded gross strategy, benchmark and S&P price returns; net returns blank; 2026 is partial January–August.
- `exposures_monthly.csv`: recorded target-weight gross/net exposures, nonzero position counts and max absolute position size. Not daily compliance evidence.
- `average_holdings.csv` and `top_bottom_holdings.csv`: equal-month average signed weights across all 68 months, including zero for absent names; latest observed company labels for display only.
- `report.html`: eight numbered Section 9.4 panels: four data exhibits and four missing-data placeholders. Data exhibits support zoom, pan, hover and PNG export. The active chart includes date controls and S&P 500 context. Net annual returns remain pending. Placeholders do not satisfy exhibit requirements. Older PNG files are not used.
- `exhibit_status.csv`: all eight Section 9.4 requirements with availability and gaps.
- `validation.json`: input and script hashes, software versions, verification flag and computed values.

## Input contract

`holdings.csv` (or holdings.parquet): date, permno, weight; optional ticker and company_name. Uppercase column names accepted. Exactly one complete target snapshot per month. Missing stock from a snapshot means zero position. Dates here are legacy holding-month labels, not validated finals execution dates.

`portfolio_returns.csv`: target_month (YYYY-MM), total (gross monthly return), hurdle, cash_monthly, sp500_ret. Optional active, spread, long_leg and short_leg are checked for accounting reconciliation. Returns and weights are decimal fractions. The script requires complete, matching monthly coverage and rejects duplicates/non-finite values.

This initial interface is intentionally monthly. Do not feed daily records into it. For future candidate runs, omit `--verify-round1` so they are not checked against the old strategy's numbers. Use a new output directory per candidate.

Benchmark is cash_monthly + 0.04/12, where cash_monthly = TB3MS/1200. This version checks that convention rather than silently overriding it. Official benchmark support is a future interface change.

## Statistics

12 periods/year; sample standard deviation (ddof=1). CAGR uses the number of complete monthly observations / 12; arithmetic mean × 12 is reported separately. Sharpe uses excess over cash; IR uses strategy minus hurdle. Benchmark Sharpe is undefined because the monthly excess over cash is constant. Drawdown includes starting NAV. Starting endowment is assumed $1bn, compounded from gross monthly returns, not a capacity-tested simulation.

Active chart: compounded strategy wealth minus compounded benchmark wealth, expressed in percentage points. This is explicitly labelled and is not obtained by compounding period-by-period active returns.

## Not final-ready

No costs are fabricated and no missing value is filled with zero. Daily beta/drawdowns, exact section 9.3 turnover, borrowing/trading costs, holding duration, dollar position size, stock attribution, liquidity distributions and factor/alpha-decay diagnostics remain outside this milestone. Monthly alpha/beta calculations are deferred to the next reporting stage. Current results are gross and monthly, including gross endowment. `--require-final` exits with an error.

Final turnover requires 0.5 × sum(abs(post-trade weight - actual drifted pre-trade weight)); this module deliberately does not report target-to-target turnover as exact.

The supplied fixture CSVs are copied from repository 05_submission at commit b349d15ea5c5b48fc12df768ef185fb0844a4267 and reproduce the user's submitted numerical results. Expected gross cumulative return: 1.7641948856767624; CAGR: 0.19653079645744076; IR: 0.8834050267790214. These are reproduction checks, not optimisation targets.

## Section 9 audit against the final instructions

The original report did not match the prescribed table layout or include all required exhibits. The corrected presentation follows Section 9.1 and separates extra diagnostics. Section 9.2 CAGR is displayed separately from arithmetic annualised return. Alpha and beta with standard errors remain pending implementation (monthly returns are already available, but the S&P fixture is price-only).

Exhibits 1, 3, 4 and 5 have data: cumulative active performance with S&P context, gross calendar-year returns, monthly target exposures, and top/bottom average holdings. Exhibit 3 is incomplete without costs; exhibit 4 shows monthly targets, not daily drift. Exhibits 2, 6, 7 and 8 are explicit missing-data panels, not fabricated plots.

Section 9.4 does not specify how to aggregate cumulative active returns. The report explicitly uses the difference of compounded strategy and benchmark wealth and applies the same convention to S&P context; confirm that convention with the organisers. Price-only S&P data remain a disclosed limitation. This report is not final-ready.


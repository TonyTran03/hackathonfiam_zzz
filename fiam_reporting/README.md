# FIAM reporting — stage 1

This standalone module implements the first reporting milestone on the actual first-round submission. No model retraining, trading or GitHub changes are required.

## Run

Unzip this package and open a terminal in `fiam_reporting`:

```bash
python -m pip install -r requirements.txt
python report.py --inputs inputs --output output --verify-round1
python -m unittest discover -s tests -v
```

Open `output/report.html` in a browser. Keep the PNG files beside it.

将压缩包解压，在 fiam_reporting 文件夹打开终端，运行以上命令。然后用浏览器打开 output/report.html。修改输入后重新运行即可，无需训练模型。

## Outputs

- `performance_summary.csv`: Section 9.1 table scaffold with available monthly gross statistics and explicit pending rows. Values are numeric decimals, not formatted percentages.
- `yearly_returns.csv`: compounded gross strategy, benchmark and S&P price returns; net returns blank; 2026 is partial January–August.
- `exposures_monthly.csv`: recorded target-weight gross/net exposures, nonzero position counts and max absolute position size. Not daily compliance evidence.
- `average_holdings.csv` and `top_bottom_holdings.csv`: equal-month average signed weights across all 68 months, including zero for absent names; latest observed company labels for display only.
- `growth.png`, `active_wealth.png`, `yearly_returns.png`, `exposures.png`: available monthly plots.
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

# Monthly stock-selection project

Work through one box at a time: data → prediction → portfolio → scoring → submission.

## The five boxes

| Folder | Purpose and contents |
| --- | --- |
| `01_data/` | Load and check the stock-month panel; prepare features. Original Parquet files, the 147-characteristic list, and the original dataset guide stay together in `raw/`. `count_missing.py` checks missing values. |
| `02_prediction/` | Train models and produce one predicted next-month excess return per stock, then rank stocks. Contains the supplied penalized-linear starter script. |
| `03_portfolio_construction/` | Convert rankings into monthly signed portfolio weights. Save working holdings here. |
| `04_backtest_scoring/` | Evaluate monthly returns, constraints, and risk. Contains the supplied portfolio-analysis starter script. |
| `05_submission/` | Keep final deliverables here: 8-page deck plus appendix, holdings CSV, portfolio-return CSV, `MAIN.py`, and team CVs. |

The competition PDF remains in the project root. The detailed dataset guide is [here](01_data/raw/readme.md).

## Local datasets

Teammates should use their existing copies of the datasets. They are not included in this Git repository. Place these two files in `01_data/raw/`:

- `chars_final_with_names.parquet`
- `8k_20150101_20260831_identified.parquet`

Keep the filenames unchanged. The feature-list CSV and dataset guide are already included in Git. Local Parquet files are ignored by Git, so they will not be uploaded when you commit or push.

## Constraints to build around

This checklist summarizes the supplied project brief; the competition PDF is the authority for exact rules and conventions.

- **Data:** One stock × one month, with 147 characteristics and zero or more 8-K filings. Preserve stock-months with no filings unless deliberately excluded by the strategy.
- **Timing:** Information from month t predicts month t+1. December 2020 information predicts January 2021 returns. The supplied target is `ret_exc_lead1m`; do not shift it again or use it as a feature. Keep feature month and return month explicit.
- **No look-ahead:** Use only information available at the decision cutoff, including filings and preprocessing. Filing report dates are not public release dates, and the supplied timestamps do not establish exact release times. Avoid historical-event leakage from LLMs.
- **Training:** For the first forecast year, train on available target months in 2015–2018, validate on 2019–2020, and test on 2021. Then expand training and roll the two-year validation window forward. Split by target/return month.
- **Portfolio:** Long the highest-ranked stocks and short the lowest-ranked stocks. Hold **100–500 total stocks**, counting longs and shorts together. Gross exposure `sum(abs(weight))` must be **≤ 2.00**; net exposure `sum(weight)` must stay between **-0.50 and +0.50**. Weights are fractions of portfolio capital.
- **Market neutrality:** Aim for beta near zero. Dollar neutrality alone does not guarantee market neutrality; realized beta is assessed separately.
- **Test period:** Monthly portfolio returns from **January 2021 through August 2026** (68 months).
- **Benchmark:** **3-month U.S. T-bill + 4% per year**. The S&P 500 is context and a market-exposure check, not the primary hurdle. Confirm the required monthly benchmark and portfolio cash/financing conventions before implementing scoring.
- **Scoring:** Report information ratio against that hurdle, OOS R², Sharpe, alpha, beta, drawdown, turnover, long- and short-leg returns, exposures, concentration, hit rate, yearly returns, best/worst months, and short-book liquidity/size characteristics.
- **Optional:** Agents, LLMs, external data, and daily risk analysis. A classical monthly ML approach is acceptable.

The portfolio starter currently labels alpha divided by residual volatility as “Information Ratio.” It must be adapted to use portfolio returns minus the competition benchmark, with consistent monthly units and annualization. Both starter scripts also contain placeholder paths and assumptions that need updating.

## Working code and final outputs

As implementation proceeds, use these script names inside the relevant boxes:

```text
01_data/01_load_data.py
01_data/02_make_features.py
02_prediction/03_train_predict.py
03_portfolio_construction/04_build_portfolio.py
04_backtest_scoring/05_evaluate.py
MAIN.py
```

The root `MAIN.py` runs these five stages in order with the same Python interpreter, using the project root as the working directory. It stops if a stage fails. Run the chain with:

```powershell
python MAIN.py
```

The five stage scripts still need implementing. Until they exist, `MAIN.py` lists the missing files and exits without running anything. The existing starter scripts are references, not connected pipeline stages. Package the final submission version with its required dependencies as allowed by the rules; moving `MAIN.py` alone would break its relative stage paths.

The final holdings CSV must cover every test month and include **date, PERMNO, ticker, company name, and signed weight** (positive long, negative short). Submit portfolio returns in a separate CSV.

To run the existing missing-data check from the project root (requires PyArrow):

```powershell
python 01_data/count_missing.py
```

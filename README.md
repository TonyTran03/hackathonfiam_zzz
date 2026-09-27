# Monthly stock-selection project

Work through one box at a time: data → prediction → portfolio → scoring → submission.

## The five boxes

| Folder | Purpose and contents |
| --- | --- |
| `01_data/` | Load and check the stock-month panel; prepare features. Original Parquet files, the 147-characteristic list, and the original dataset guide stay together in `raw/`. `count_missing.py` checks missing values. |
| `02_prediction/` | Train models and produce one predicted next-month excess return per stock, then rank stocks. Contains the supplied penalized-linear starter script. |
| `03_portfolio_construction/` | Convert rankings into monthly signed portfolio weights. Save working holdings here. |
| `04_backtest_scoring/` | Evaluate monthly returns, constraints, and risk. Contains the supplied portfolio-analysis starter script. |
| `05_submission/` | Keep final deliverables here: 8-page deck plus appendix, holdings CSV, portfolio-return CSV, `MAIN.py`, and team CVs. `deck/` holds the deck outline and the appendix drafts (research log, 8-K write-up, missing-returns note, pre-registered variants). |
| `common/` | Shared across every box: `config.py` (paths, the trading limits, the train/validation/test schedule) and `checks.py` (rule-compliance checks). Folder names starting with a digit cannot be imported in Python, so anything used by more than one stage lives here. |
| `tests/` | `test_checks.py` feeds the checker 21 deliberately broken inputs and asserts each one is caught. |

The competition PDF remains in the project root. The detailed dataset guide is [here](01_data/raw/readme.md).

## Setup

```powershell
python -m pip install -r requirements.txt
python 01_data/01_load_data.py
```

Versions are pinned so that every teammate regenerates byte-identical files.
Generated output lands in `01_data/processed/`, which is gitignored — the work
table is ~440 MB and must never be committed. Rebuilding takes about a minute.

## Local datasets

Teammates should use their existing copies of the datasets. They are not included in this Git repository. Place these two files in `01_data/raw/`:

- `chars_final_with_names.parquet`
- `8k_20150101_20260831_identified.parquet`

Keep the filenames unchanged. The feature-list CSV and dataset guide are already included in Git. Local Parquet files are ignored by Git, so they will not be uploaded when you commit or push.

If you keep the datasets somewhere else, point `FIAM_DATA_DIR` at that folder
instead of moving them. The repo root is also searched.

The benchmark inputs in `01_data/raw/external/` (cash rate and two market
series, 80 KB total) **are** committed on purpose. Both sources revise their
history, so pinning the downloaded snapshot is what keeps everyone's scores
comparable.

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

Stage 1 is implemented; the other four still need writing. Until they exist, `MAIN.py` lists the missing files and exits without running anything. The existing starter scripts are references, not connected pipeline stages. Package the final submission version with its required dependencies as allowed by the rules; moving `MAIN.py` alone would break its relative stage paths.

After all five stages succeed, `MAIN.py` runs the compliance checks as a final
gate and fails the chain if any competition rule is broken. Use `--no-check`
to skip it. House standards from `config.TEAM` (the beta-neutrality
thresholds) are printed at the same severity but do not stop the chain: the
beta control deliberately carries an ex-ante beta tilt to offset the realised
gap between estimated and actual leg betas, so a book can sit past that
threshold by design. Whether that is acceptable is a team judgement for the
deck.

Two switches exist for work after the chain has run:

```powershell
python 02_prediction/03_train_predict.py --metrics-only      # rewrite prediction_metrics.csv from saved forecasts, no retraining
python 03_portfolio_construction/04_build_portfolio.py --variant S   # one pre-registered variant (S: sector cap, B: 12-month beta feedback)
```

The variant switches are OFF by default and MAIN.py never passes them. Their
rules, acceptance criteria and results are in
`05_submission/deck/protocol_variants.md`.

The delisting mark for held positions with no realised return is
`config.TEAM["delisting_return"]` (0.0). Stage 5 applies it and
`11_deck_pack.py` reports the sensitivity grid next to it.

### Stage 1 — `01_data/01_load_data.py`

Writes `model_table.parquet` (147 predictors + identifiers + the answer) and
`benchmark_monthly.csv` (the cash-plus-4% hurdle, plus two market series) into
`01_data/processed/`.

It attaches a `target_month` column: a row labelled `eom` = month *t* carries
predictors for month *t*, and `ret_exc_lead1m` is **already** the month *t+1*
answer. **Assign train/validation/test by `target_month`, never by `eom`.**
Splitting on `eom` leaks one month of answers into training every year — the
bug is invisible and flatters the score, so the checker tests for it.

Known gap: the dividend-inclusive market series stops at 2026-07. The index
level series covers all 68 evaluation months; use it for the beta regression
and the other as a cross-check.

### `01_data/filing_features.py` — 8-K signals without reading the text

```powershell
python 01_data/filing_features.py --explore
```

Writes `filing_features.parquet`: one row per stock-month that has at least one
filing, keyed by `target_month` = filing month + 1. Repeated filings are
aggregated first — joining them raw would duplicate the panel's returns.

**Join with a LEFT join and leave the gaps missing.** Only half the
evaluation-window stock-months have any filing; dropping the rest would let
filing coverage silently redefine the universe.

What the training-window exploration says so far (target months ≤ 2018-12,
5 comparisons, logged):

| Signal | n | vs other filers | t |
| --- | ---: | ---: | ---: |
| Distress items 4.01/4.02 | 499 | **−1.386%/mo** | −2.0 |
| Officer change 5.02 | 16,378 | −0.178% | −1.4 |
| Filed late (> 4 days) | 10,938 | +0.072% | +0.4 |
| Filing burst > 2× | 2,750 | +0.250% | +0.9 |

Only the distress flag looks usable, and it is far too rare to sort a book on —
it is meant as a veto overlay (bar from the long leg, prefer for the short),
not as a predictor. Late filing and filing burst do **not** survive the correct
control group; against *all* stock-months they look positive, but that is
entirely the "this company filed anything at all" effect, which is itself
largely size.

The 5.02 result is the argument for the next step: 70k officer-change filings
carry almost no signal in aggregate, which is what you would expect if a few
abrupt departures are buried in mostly routine appointments. Separating those
is a bounded classification task on the document in front of you — the one
place in this pipeline where a language model earns its keep without risking
look-ahead from what the model already knows about 2021–2026.

## Compliance checks

`common/checks.py` covers two things the rules are explicit about:

- **Look-ahead.** Predictors must come from `factor_char_list.csv`; the answer
  column must never be an input; splits must be keyed on the target month; and
  scalers, medians and imputers must be fitted on training months only.
- **Trading criteria.** Per month: 100–500 names, gross ≤ 2.00, net within
  ±0.50, both legs present, no duplicates, no untradable stocks, every
  evaluation month covered.

```powershell
python tests/test_checks.py          # prove the checker actually fires
python run_checks.py                 # look-ahead checks on the work table
python run_checks.py holdings.csv    # also check a book
```

`run_checks.py` exits non-zero on any failure. Run it before every submission —
the rules say the organizers will audit for look-ahead, so check first.

The final holdings CSV must cover every test month and include **date, PERMNO, ticker, company name, and signed weight** (positive long, negative short). Submit portfolio returns in a separate CSV.

To run the existing missing-data check from the project root (requires PyArrow):

```powershell
python 01_data/count_missing.py
```

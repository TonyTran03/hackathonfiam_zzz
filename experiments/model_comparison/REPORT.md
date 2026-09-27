# Fair model-comparison experiment

## What was completed

Seven fixed model variants and an annually selected blend were evaluated over all 68 holding months from January 2021 through August 2026. Every model used the same 147 characteristics, original next-month excess-return target, annual time splits, investable-stock screen, portfolio rules and cost accounting. The two uploaded raw datasets remain unchanged; only the numerical dataset was needed.

The annual selection bug is repaired in the experiment: each year’s blend is selected using only that year’s preceding two-year validation window. Later validation outcomes are never pooled to choose earlier forecasts.

## Main findings

The highest observed information ratio after the assumed 20-basis-point trading cost was **Ridge: 0.63**, with a net CAGR of **16.78%**. This is a descriptive historical result, not proof that it is the best future model.

LightGBM with missing values preserved had a net IR of **-0.12**, versus **-1.65** for separately tuned median-filled LightGBM and **-0.46** for median-filled LightGBM with the missing-preserved variant’s settings. Ridge had a net IR of **0.63**. Read the paired uncertainty intervals before attributing these differences to a reliable advantage. The Ridge-minus-LightGBM-missing gap is supported by the descriptive paired interval in this setup, but the missing-versus-median intervals include zero.

These headline returns are **provisional**: Ridge holds 54 stock-month positions without observed outcomes. The base case marks those stock returns at zero; under the stated adverse marking scenario, Ridge CAGR becomes approximately **−1.10%**. The unresolved positions are listed in missing_return_positions.csv. This sensitivity is material and should be addressed before presenting returns as submission-ready.

This experiment deliberately gives all algorithms the same unmodified return target. The existing team code gave LightGBM a month-demeaned, clipped target while the linear models used original returns. Consequently, this is a fair comparison under a common objective; it does not reproduce the team’s earlier saved performance or rule out better results from a separately specified ranking-oriented experiment.

## Portfolio comparison

Net means 20 bps charged per dollar traded, including opening trades. CAGR is compounded annual growth; IR measures excess over the cash-plus-4% hurdle. Beta is measured against the supplied S&P 500 price series.

| Model                              | Net CAGR   |   IR, gross |   IR, net |   Beta | Max drawdown   |   Mean rank IC |
|:-----------------------------------|:-----------|------------:|----------:|-------:|:---------------|---------------:|
| OLS reference                      | 6.14%      |        0.17 |     -0.07 | -0.121 | -16.17%        |         0.0269 |
| Ridge                              | 16.78%     |        0.79 |      0.63 | -0.075 | -16.36%        |         0.0477 |
| Lasso                              | 4.01%      |       -0.11 |     -0.44 |  0.013 | -9.84%         |         0.0039 |
| Elastic Net                        | 4.28%      |       -0.09 |     -0.41 |  0.04  | -9.60%         |         0.0065 |
| LightGBM: missing preserved        | 5.59%      |        0.17 |     -0.12 | -0.048 | -19.83%        |        -0.0043 |
| LightGBM: median filled            | -4.57%     |       -1.22 |     -1.65 | -0.033 | -27.86%        |         0.0067 |
| LightGBM: median, matched settings | 2.39%      |       -0.16 |     -0.46 |  0.029 | -15.96%        |         0.0025 |
| Annually selected blend            | 8.23%      |        0.33 |      0.11 | -0.046 | -19.19%        |         0.0383 |

All portfolios held 100 longs and 100 shorts in each of 68 months, stayed within 200% gross and the competition’s ±50% net band, and had both legs present with no duplicated stock-month positions. Satisfying those limits does not certify market neutrality: read beta and its standard error in portfolio_metrics.csv. The inherited nominal 2% position cap applies before scaling the legs and is not an enforced final cap.

## Prediction quality and tied forecasts

| Model                              | OOS R², eligible   |   Rank IC months |   Constant-forecast months |
|:-----------------------------------|:-------------------|-----------------:|---------------------------:|
| OLS reference                      | -0.431%            |               68 |                          0 |
| Ridge                              | 0.084%             |               68 |                          0 |
| Lasso                              | -0.012%            |               44 |                         24 |
| Elastic Net                        | -0.015%            |               44 |                         24 |
| LightGBM: missing preserved        | -0.114%            |               68 |                          0 |
| LightGBM: median filled            | -0.048%            |               68 |                          0 |
| LightGBM: median, matched settings | 0.008%             |               68 |                          0 |
| Annually selected blend            | not applicable     |               68 |                          0 |

R² compares squared forecast error with predicting zero; it is reported on the common eligible universe here. The full-universe version is also supplied. Rank IC is monthly Spearman correlation, averaged only over months where it is defined. The blend is a ranking score, so return-unit R² is inappropriate.

If regularization collapses a model to a constant, it has no within-month stock-selection signal. To keep the same portfolio construction for every model, tied scores follow deterministic input/PERMNO ordering, with the short selection traversing the reverse order. Portfolio returns in those months are mechanical fallback results, not evidence of prediction skill. The constant-month counts above make this limitation visible.

## Performance by year

| Model                              | 2021    | 2022   | 2023   | 2024    | 2025   | 2026   |
|:-----------------------------------|:--------|:-------|:-------|:--------|:-------|:-------|
| OLS reference                      | -4.06%  | 28.73% | 8.63%  | -10.09% | 8.29%  | 7.31%  |
| Ridge                              | 46.27%  | 48.13% | 7.58%  | -11.06% | 8.29%  | 7.31%  |
| Lasso                              | -0.82%  | 3.21%  | 1.16%  | -0.42%  | 9.46%  | 10.69% |
| Elastic Net                        | -0.82%  | 3.21%  | 9.57%  | -7.06%  | 10.40% | 10.17% |
| LightGBM: missing preserved        | 26.43%  | 30.54% | -3.41% | -8.25%  | -5.15% | -1.90% |
| LightGBM: median filled            | -13.41% | -5.32% | 13.18% | -7.74%  | -5.64% | -5.01% |
| LightGBM: median, matched settings | 8.16%   | 9.12%  | 12.88% | -13.76% | 2.51%  | -2.97% |
| Annually selected blend            | 1.86%   | 37.54% | 12.12% | -11.06% | 2.76%  | 9.05%  |

2026 covers January–August only; its number is an eight-month compounded return, not a full-year return. All entries use 20 bps per dollar traded. Benchmark and market yearly returns are in yearly_returns.csv.

## Annual choices

|   Test year | Training through   | Validation         | Selected blend   |   Trees, missing |   Trees, filled |
|------------:|:-------------------|:-------------------|:-----------------|-----------------:|----------------:|
|        2021 | 2018-12            | 2019-01 to 2020-12 | avg_linear       |                1 |               1 |
|        2022 | 2019-12            | 2020-01 to 2021-12 | ridge_gbm        |                9 |               9 |
|        2023 | 2020-12            | 2021-01 to 2022-12 | avg_linear       |              124 |              77 |
|        2024 | 2021-12            | 2022-01 to 2023-12 | gbm_median       |              214 |             317 |
|        2025 | 2022-12            | 2023-01 to 2024-12 | ridge_gbm        |              224 |               9 |
|        2026 | 2023-12            | 2024-01 to 2025-12 | avg_linear       |              299 |               5 |

Model hyperparameters minimize validation MSE. The annual blend maximizes mean validation-month rank IC across the five predeclared candidates. Hyperparameters, candidate scores, split dates and row counts are recorded in annual_choices.json. Some boosting fits stop after very few trees; this is the validation choice under the shared raw-return objective, not a failed training run. Ridge occasionally selects a grid boundary, so this finite grid does not establish an optimal Ridge setting.

## Uncertainty in model differences

| Paired comparison                                                    | Annual mean difference   | 95% interval       |
|:---------------------------------------------------------------------|:-------------------------|:-------------------|
| LightGBM: missing preserved minus Ridge                              | -10.62 pp                | [-19.59, -2.48] pp |
| LightGBM: missing preserved minus LightGBM: median filled            | +10.41 pp                | [-3.52, +26.60] pp |
| LightGBM: missing preserved minus LightGBM: median, matched settings | +3.19 pp                 | [-6.49, +13.46] pp |
| Annually selected blend minus Ridge                                  | -7.93 pp                 | [-16.41, +0.07] pp |

These are paired circular six-month block-bootstrap intervals based on 2,000 draws of the same 68 months, using identical sampled months for both models. The statistic is an annualized arithmetic mean return difference, not a CAGR or IR difference. Intervals containing zero do not support a clear directional conclusion at this descriptive confidence level. The exercise has no untouched new holdout, and these intervals are not adjusted for multiple comparisons or historical strategy development.

## Missing outcomes and implementation limits

| Model                              |   Missing-return positions | Mean unobserved gross exposure   | Net CAGR, adverse marking   |
|:-----------------------------------|---------------------------:|:---------------------------------|:----------------------------|
| OLS reference                      |                         61 | 1.626%                           | -12.93%                     |
| Ridge                              |                         54 | 1.375%                           | -1.10%                      |
| Lasso                              |                         56 | 1.431%                           | -12.56%                     |
| Elastic Net                        |                         51 | 1.307%                           | -10.98%                     |
| LightGBM: missing preserved        |                         55 | 1.359%                           | -10.52%                     |
| LightGBM: median filled            |                         40 | 0.984%                           | -15.44%                     |
| LightGBM: median, matched settings |                         36 | 0.932%                           | -8.58%                      |
| Annually selected blend            |                         60 | 1.551%                           | -10.38%                     |

Base returns explicitly mark positions with unavailable forward outcomes at zero raw stock return; such stocks are never removed using their future outcome. The adverse marking scenario assigns −100% to missing long-stock returns and +100% to missing short-stock returns, keeping the base holdings and 20-bps trading charge fixed. It is a sensitivity illustration, not a worst-case bound, and does not rerun historical beta feedback under the alternate marks. Missing delisting or other terminal outcomes still need resolution before a submission-quality performance claim.

Accounting reconstructs raw forward returns using the source risk-free rate, verified from ret minus ret_exc. Total portfolio return is cash + Σ w × (raw stock return − cash); financing at the same cash rate is assumed. This handles nonzero net exposure without pretending the panel RF and TB3MS cancel. Trade sizes compare target weights against drifted prior positions, including prior costs in NAV. Initial entry is charged; final liquidation is not. Stock-borrow fees, recalls, asymmetric financing and nonlinear liquidity costs are not modeled.

The model-selection repair removes a specific forward-looking choice, but cannot erase prior human inspection of 2021–2026 results. The inherited portfolio policy was developed using those historical results. Treat this as a controlled historical comparison. All labels remain original: some missing ticker/company labels require verification before competition submission.

## Verification and next action

The numerical file’s SHA-256 matches the distributed dataset documentation. The panel has 529,082 rows, 147 selected predictors, and no duplicate security-month keys. 522,431 available forward/current return pairs matched to within numerical precision. Observed feature values are identical across missingness variants. All annual split boundaries and every model’s 68 portfolios were checked. Five focused tests cover annual-selection independence from test outcomes, calendar smoothing, initial-loss drawdown, financing arithmetic and saved split dates.

Use these results to explain what changed and why, rather than announcing a winner from the historical test table. A useful next experiment would predeclare a common ranking-oriented or robust target for all models and rerun the same comparison, with no portfolio retuning. It is outside the present experiment and has not been run.

To rerun or integrate the work, follow README.md. The complete deliverable includes scripts, pinned dependencies, the frozen protocol, annual choices, predictions, holdings, metrics, plots and verification outputs. Raw datasets and regenerable caches are excluded.


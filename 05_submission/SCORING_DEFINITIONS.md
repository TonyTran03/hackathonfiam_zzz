# Scoring definitions and pre-freeze reconciliation

Status: review draft for the team's official scoring agreement. The requested
headline is **net of 20 bps per dollar traded**, against **cash + 4% per year**,
with a **0% missing-return base assumption**. The last item still needs its unit
(raw or excess return) confirmed. This document records both intended reporting
and the actual implementation; it does not declare the accounting reconciled.

Audited main commit: `46890aae6cf25bfa5e93032621dfdcbbede33edb`.
Audit date: 2026-09-27. Final strategy, final performance, and freeze tag: **pending**.
The sector-cap switch is `None` at this commit; variant S results are separate.
No strategy, holdings, scoring defaults, or official output files were changed
by this audit. Recheck this document if Oliver changes the implementation.

## 1. Common metric definitions

Use 68 ordered holding/target months, January 2021 through August 2026.
December 2020 features predict January 2021; `ret_exc_lead1m` is already forward
aligned. Returns and weights are decimal fractions, not percentage points.

For holding month t:

- Cash c_t = FRED TB3MS annual percentage / 1200. This is the code's simple
  monthly conversion, not an effective-rate transformation.
- Hurdle h_t = c_t + 0.04/12. Do not add 4% per month or use S&P 500 as the hurdle.
- Active return a_t = portfolio total return R_t - h_t, using net R_t for the
  intended headline. Subtract costs before computing the mean and deviation.
- Annualized IR = sqrt(12) * mean(a_t) / sample_std(a_t), with ddof=1.
  This is not regression alpha / residual volatility. Zero deviation makes IR
  undefined and should be reported as such.
- Sharpe = sqrt(12) * mean(R_t-c_t) / sample_std(R_t-c_t).
- CAGR = product(1+R_t)^(12/N) - 1; annual arithmetic return = 12*mean(R_t).
- Calendar-year return = product(1+R_t) - 1 over that year's available months.
  Label 2026 as January-August; do not present it as a full-year realized return.
- Wealth begins at 1. Drawdown = wealth / running_peak_including_initial_1 - 1.
- Alpha/beta: regress R_t-c_t on S&P 500 price return minus c_t, with intercept.
  Current code uses HAC standard errors, maxlags=3, use_t=True. Annual alpha is
  12 times the monthly intercept. Label the market series as price-only.
- Long/short contributions are signed sums relative to portfolio capital;
  they are not standalone leg returns normalized by each leg's notional.
- Prediction R2 is 1 - sum((y-pred)^2)/sum(y^2), a zero-return baseline.
  Rank-only blend scores do not have return-unit R2. Monthly rank IC is Spearman
  correlation; exclude undefined months explicitly and report their count.

Sources: `01_data/01_load_data.py`, `04_backtest_scoring/05_evaluate.py`,
`04_backtest_scoring/11_deck_pack.py`, and
`experiments/model_comparison/evaluate_comparison.py`.

## 2. Return accounting: unresolved difference

Let y_it be the supplied next-month excess return, f_t its source risk-free rate,
r_it = y_it + f_t the raw stock return, and w_it signed beginning-month weights.

Main stage 5 currently computes:

    R_main,t = c_t + sum_i(w_it * y_it)

The comparison computes cash financing explicitly:

    R_comparison,t = c_t + sum_i(w_it * (r_it - c_t))
                   = (1 - sum_i w_it) * c_t + sum_i(w_it * r_it)

For positions with observed returns, comparison minus main is
`sum_i(w_it) * (f_t - c_t)`. Thus the formulas agree if net exposure is zero or
source RF equals the cash series; neither should be silently assumed.
The comparison obtains source RF from same-month `ret - ret_exc` and maps it to
the holding month. Recovering it needs the raw dataset, not just holdings CSV.
The numerical effect on the official book was not recomputed in this audit.

Neither convention here models stock-specific borrow fees, locate failures,
margin calls, or asymmetric financing. A liquidity screen does not establish
actual borrow availability. State those limitations with performance results.

## 3. What exactly does 0% missing return mean?

| Item | Current main pipeline | Model-comparison experiment |
|---|---|---|
| Field filled | `ret_exc_lead1m` (excess return) | `raw_forward` (raw return) |
| Default mark | `TEAM["delisting_return"] = 0.0` | raw return 0.0 |
| Contribution of missing position | 0 in the excess spread | w * (0 - cash) in the cash-relative spread |
| Sensitivity | 0 / -30 / -50 / -100% applied to excess returns | adverse raw-return scenario for missing positions |

Consequently the existing main 0% mark is **not literally a flat raw stock price**.
If the agreement means raw return m, an excess-return implementation must use
m-f_t to reconstruct raw returns (and then handle cash financing consistently).
Alternatively, explicitly approve and label the existing excess-return convention.
Do not silently reinterpret a numeric config value.

Missing observations are not proof of bankruptcy or acquisition. The acquisition
interpretation in `deck/appendix_missing_returns.md` is based on panel exits and
pre-exit patterns; it does not establish every actual terminal cash flow. Record
confirmed causes separately. Do not remove stocks from selection using missing
future outcomes. Sensitivities are fixed-holdings scenarios, not newly simulated
strategies; +/-100% adverse marks are not a worst-case bound for short positions.
Stage 4's beta-feedback returns still use `.fillna(0.0)` independently of the
stage-5 config, so changing that config alone does not rerun portfolio feedback.

## 4. Trading costs and turnover

20 bps = 0.002 per dollar of stock notional traded, charged on buys and sells:

    cost_t / NAV = 0.002 * sum_i abs(target_weight_it - pretrade_weight_it)
    net_return_t = gross_return_t - cost_t / NAV

Current main deck-pack approximation uses the prior month's **target** weights
as pretrade weights. It skips the first month, does not drift holdings with
returns/NAV, and does not charge final liquidation. Its reported turnover is
`sum(abs(delta target weights)) / (2 * current gross exposure)`, averaged over
67 transitions. Do not multiply this normalized turnover directly by 20 bps:
the charge uses the full absolute traded notional.

The comparison instead drifts prior positions:

    pretrade_weight_it = prior_weight_i * (1 + prior_raw_stock_return_i)
                        / (1 + prior_net_portfolio_return)

It includes initial entry from cash, retains separate NAV paths for each cost
scenario, and excludes terminal liquidation. Thus equal "20bps" labels do not
mean identical cost accounting across the pipelines. Both are simplified models.

Current main `portfolio_returns.csv` is GROSS. Main deck-pack return/risk rows,
figures and variant headlines are gross unless explicitly in the cost section.
The deck-pack cost table contains net IR/CAGR, but there is no official net-20
monthly series exported by stage 5. Before headline adoption, agree on entry and
drift conventions, then export a clearly named net series and regenerate all
headline statistics/figures from it. Keep gross results separately labeled.

## 5. Independent check of committed outputs

Reproduce without training, raw data, or third-party dependencies:

    python tools/audit_scoring_definitions.py

The script reads committed CSVs only and prints JSON. It checks all 68 months,
stock-month uniqueness, labels, both legs, 100-500 names, gross <=2, net within
+/-0.5, cash against TB3MS, return identities, and rounded IR against deck_pack.
It does not establish leakage freedom, raw-return accuracy or market neutrality.

Results at the audited commit:

| Calculation on default book | IR | CAGR |
|---|---:|---:|
| Current gross accounting | 0.883405 | 19.6531% |
| Current deck-pack 20bps approximation | 0.706335 | 16.9349% |
| Same approximation, adding initial entry only | 0.699784 | 16.8499% |

The third row is an accounting sensitivity, not a new strategy or final result.
Initial gross is 2, so entry costs 0.004 of NAV (40bps). The audit does not compute
drift-adjusted costs for the official book; raw stock returns are required.
All 68 months have 200 names (13,600 rows), gross approximately 2, net exposure
from -24.0351% to +30%. These pass the core count/exposure checks with numerical
tolerance. Beta remains a separate assessment; a passing gate is not proof of
market neutrality. Main house-beta findings are nonblocking by current design.

Additional discrepancy: main stage 5 and deck-pack drawdown omit initial NAV
from the peak. A first-month loss can be missed by that implementation. The audit
uses initial NAV=1; for this committed gross series the minimum still matches
-6.5264%. Log/fix this edge case before treating the helper as general-purpose.

## 6. Freeze handoff

Before labeling this document final, record:

- [ ] Team choice of default book or sector variant, and implementation commit.
- [ ] Raw-versus-excess missing mark and cash/financing convention agreed.
- [ ] Cost convention agreed: 20bps, initial entry, drift and terminal liquidation.
- [ ] Any genuine accounting bugs logged and corrected; all affected outputs rerun.
- [ ] Official net-20 returns CSV identified; deck tables/charts use that series.
- [ ] Oliver's verification incorporated, including gross/net IR-jump comparison.
- [ ] Full pipeline and compliance checks rerun on the final implementation.
- [ ] Freeze tag/commit and output checksums recorded together.

Freeze tag: PENDING. Final results: PENDING. This document does not authorize a
strategy change or claim team approval of an unresolved accounting choice.

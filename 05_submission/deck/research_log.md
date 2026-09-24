# Research log: every look at the 2021-2026 test period

**Purpose.** The brief says multiple-testing discipline is the participant's
responsibility, and the judges' first question about any backtest is "how many
things did you try, and how did you choose?" This log answers it. Every entry
is traceable to a commit, a pull request, or a dated team message. It is meant
for the appendix; the count at the bottom belongs on the discussion page.

Conventions. "Test" means the 68 holding months 2021-01 to 2026-08. "Validation"
means the two-year block before each fold's test year (only the first fold's
block, 2019-2020, sits entirely outside the test period). "Decision changed"
means the traded book was different afterwards.

## 1. Chronological log

| # | Date | What was evaluated | Data used to decide | Test-period looks | Decision changed? | Where recorded |
|---|------|--------------------|---------------------|:-----------------:|-------------------|----------------|
| 1 | 2026-09-16 | Repo skeleton, five-stage layout | none | 0 | n/a | commits `9e51cd1`, `6786d4c` |
| 2 | 2026-09-17 | Missing-value audit of the 147 characteristics: 8.4M empty cells (10.8%); 48% structural (the line item does not exist for the firm), 31% insufficient history, 21% other | full panel, no returns | 0 | Yes: keep blanks for the trees rather than median-fill | team chat; `01_data/count_missing.py` |
| 3 | 2026-09-19 | Data layer, target-month alignment, compliance checks (21 deliberately broken inputs all caught) | none | 0 | n/a | `329422c`, PR #1 |
| 4 | 2026-09-19 | 8-K item-code signals: distress 4.01/4.02, officer change 5.02, late filing, filing burst. 5 comparisons against the correct control group (other filers) | training window only (target months to 2018-12) | 0 | Yes: only the distress flag kept, as a veto not a predictor | `fef0c10`; `01_data/filing_features.py --explore` |
| 5 | 2026-09-19 | Baseline: four linear models, equal-weight top/bottom 100 | validation for penalties; test for the score | 1 | Baseline set: IR 0.45, beta -0.54, short leg full of penny stocks | `7e2b986` |
| 6 | 2026-09-19 | Tradability screen (price >= $5, no nano/micro), signal neutralisation on sector/size/beta, inverse-vol weights, beta-matched legs, buffer | beta estimator ranked on training window; construction iterated with the test score visible | 4 | Yes: IR 0.36, beta -0.18, drawdown -30% to -8% | `6c265ee` (commit message records the four runs) |
| 7 | 2026-09-19 | Gradient-boosted trees on the missing-preserved table; blend candidates compared | blend chosen on validation blocks (pooled, see #14) | 1 | Yes: IR 0.76 | `5f53012` |
| 8 | 2026-09-19 | Forecast smoothing and holding buffer, 20 combinations | validation 2019-2020 (all 20 negative net IR); test score then inspected | 1 | Yes, then reverted to pre-specified values in #10 | `70ad057` |
| 9 | 2026-09-19 | Why 2019-2020 lost money: dead signal (rank IC +0.002) plus realised beta -0.35 | validation only | 0 | Yes: motivated the beta feedback in #10 | `34e26b5`; `04_backtest_scoring/07_why_2019_failed.py` |
| 10 | 2026-09-19 | Closed-loop beta control (legs sized on their own trailing realised beta, past months only); validation tuning switched OFF, smoothing 3 months and buffer 2.5x fixed as pre-specified | past months only inside the backtest; test score inspected | ~3 | Yes: IR 0.85, beta -0.17. Commit records "the test period has now been evaluated roughly ten times" | `8ae8139` |
| 11 | 2026-09-19 | 8-K features joined into the tree model | validation rank correlation: +0.1087 without, +0.1082 with | 1 (rerun, identical result) | No: traded model runs without them | `99a798b`; flag `INCLUDE_FILING_FEATURES` |
| 12 | 2026-09-19 | Officer-change triage (abrupt vs routine 5.02 filings, rule-based, no language model); daily marking of the book | training window only; daily path is descriptive | 0 | No (t = -1.9 does not clear the bar we set) | `fb63fdb`; `01_data/officer_triage.py`, `04_backtest_scoring/10_daily_risk.py` |
| 13 | 2026-09-20 | Fair model comparison: OLS, Ridge, Lasso, Elastic Net, LightGBM missing-preserved, LightGBM median-filled (two variants), annual blend. Protocol frozen before fitting | per-fold validation for all choices; 8 test-period series produced and read | 8 | No change to the traded book. Ridge 0.63 net was the best of eight and is reported as post hoc; the real-time choice (annual blend) is 0.11 | PR #4; `experiments/model_comparison/PROTOCOL.md`, `REPORT.md` |
| 14 | 2026-09-21 | Cross-fold leak found: blend had been chosen once on all six folds' pooled validation blocks (60 of 84 months inside the test period). Fixed to per-fold selection; new compliance check added | per-fold validation | 1 | Yes: 2022 and 2023 now trade ridge+gbm instead of gbm alone. IR 0.85 to 0.88 | `35e3e6f` on `feat/pipeline` (merged via this PR) |
| 15 | 2026-09-21 | Compliance gate wired to the holdings file; beta-neutrality check; scoring arithmetic tested against 42 hand-computed answers | none | 0 | No numbers moved | PR #5 |
| 16 | 2026-09-21 | Short-leg diagnosis: each leg measured against the eligible-universe average by sub-period; model shorts vs a diversified hedge basket held for all 68 months | test period, descriptive | 2 | No: model shorts kept as the pre-registered design; basket reported in appendix | team chat (2026-09-21), Oliver; scripts not yet committed |
| 17 | 2026-09-21 | Sector exposure of the traded book (tech 7.8 long vs 27.1 short on average; sum of absolute count differences 52 of 200). Same tilt found in the 2019-2020 validation window | test-period holdings inspected; validation window used as evidence | 1 | Not yet. Sector cap (option B, +/-5 names per sector) proposed, rule to be written down before the run | team chat (2026-09-21), Oliver; Alex +1 with weight cap |
| 18 | 2026-09-22 | Reconciliation of a reported number (short leg vs universe 2021-22: -29.35% vs -26.90%) | none | 0 | -26.90% confirmed as correct | team chat |
| 19 | 2026-09-23 | Merge of the per-fold blend fix into the working branch; full rebuild reproduces Oliver's holdings exactly (weights equal to 1e-16); deck pack, figures and tables regenerated from the per-fold book | none (reproduction) | 0 | No | this PR |
| 20 | 2026-09-23 | Delisting mark: the 50 positions with no realised return are all last-month-in-panel exits with acquisition-shaped pre-exit returns (longs +45% over the prior 6 months, shorts +28%); sensitivity 0% / -30% / -50% / -100% added to deck_pack | test-period holdings, descriptive | 1 (sensitivity table) | No: 0% kept as base case with the table in the appendix | `appendix_missing_returns.md`, `11_deck_pack.py` |
| 21 | 2026-09-23 | Variant S, sector count cap +/-5, rule and acceptance criterion written before the run | test period, one run | 1 | Recommended for adoption on neutrality grounds; IR 0.88 to 1.33 as a by-product, reported as such | `protocol_variants.md` |
| 22 | 2026-09-23 | Variant B, 12-month beta feedback window, rule written before the run | test period, one run | 1 | Rejected by its own criterion | `protocol_variants.md` |

## 2. The count

- **Test-period series produced and looked at:** about 25 (rows 5 to 8, 10, 11, 13, 14, 16, 17, 20 to 22). Roughly 10 of these were construction iterations on 2026-09-19 that Oliver logged in the commit messages at the time, 8 were Bohan's pre-registered comparison, and the rest are diagnostics.
- **Decisions that changed the traded book after seeing a test-period number:** four (rows 6, 7, 8/10, 14). Of these, #7 and #14 were decided on validation data and the test score was read afterwards; #6 and #8/10 were iterated with the test score visible, which is why the smoothing and buffer values were reset to pre-specified defaults rather than tuned.
- **Decisions made on training or validation data only:** rows 2, 4, 9, 11, 12.
- **Pre-registered before running:** rows 13, 21 and 22 (rule and acceptance criterion committed before the run).

## 3. What this means for the headline

The headline information ratio of 0.88 is the result of a sequence that saw the test period roughly twenty times. Two facts limit how much that inflates it:

1. The single clean out-of-sample window we have, 2019-2020, was used to diagnose and fix a construction bug (beta), not to pick a signal. The signal itself had no skill there (rank IC +0.002), which we state rather than hide.
2. The largest improvements came from things that are not fitted to returns: removing untradeable penny stocks, neutralising beta, and fixing a selection leak. The one return-fitted choice, the model blend, was decided on validation blocks and re-decided per fold when the leak was found, and the number moved up, not down.

What we cannot claim: that 0.88 is an unbiased estimate of forward performance. Removing the five best months of 68 takes the IR to about 0.30 (commit `8ae8139`), and the 2023-2026 stretch runs at roughly 0.66 against 1.22 for 2021-2022.

## 4. Rules we now hold ourselves to

- Any new variant (sector cap, borrowability screen) is written into a protocol note and committed before it is run, with the acceptance rule stated in advance.
- One run per variant, reported either way, and it goes in the appendix whether or not it is adopted.
- After the model freeze, nothing that changes holdings is run again; anything found later goes under "potential improvements".

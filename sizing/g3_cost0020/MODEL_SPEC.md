# Model spec — `g3_cost0020`

For cross-checking. Everything below is read from the run's own `run.json`,
`summary.csv`, `monthly_returns.csv`, `holdings.parquet` and
`constraint_checks.csv`, not retyped from memory.

    repo      TonyTran03/hackathonfiam_zzz, branch simple-pipeline-handoff
    arm       sizing/g3_cost0020/
    window    2021-01 .. 2026-08, 68 months, monthly rebalance
    forecast  current_gbm_no8k (prediction/saved_forecasts/predictions.parquet)
    sha       engine 706f45e5dd309bc8 | predictions 294917816da1363e

## Objective

    max   alpha' w  -  0.5 w' Sigma w  -  0.002 (||w - w_||_1 + F)
     w

    alpha  = 0.004339 * s, in MONTHLY RETURN units
    s      = ranking score: forecast unit-ranked per month, residualised on
             sector dummies + size rank + beta, then 3-month rolling mean
    Sigma  = Ledoit-Wolf shrunk covariance, trailing 36 months, min 12 obs
    w_     = last month's weights after price drift
    F      = absolute weight of holdings that left the candidate list and
             must be liquidated; their turnover is charged even though their
             new weight is zero

In code the cost coefficient is `cost_penalty * trading_cost_bps / 10000`
= 1.0 * 20 / 10000 = 0.002.

### Where 0.004339 comes from

Cross-sectional OLS slope of realised next-month return on score, over the
68 months, on the screened universe: **+0.4339% per unit of score, t = +2.41**,
mean rank IC 0.062. It is measured, not tuned. Without it the objective treats
one unit of score as a 100% monthly return and the cost term is ~230x too
small to bind.

## Constraints (all enforced, none relaxed)

    ||w||_1            <= 0.75          gross
    -0.50 <= 1'w       <= 0.50          net
    |w_i|              <= 0.02          position cap
    beta_hat' w         = 0             estimated market-beta neutrality
    d_i w_i            >= 0.001         direction + minimum allocation
                                        d_i = +1 long candidate, -1 short

Mandate ceilings (gross <= 2.0, |w_i| <= 0.05) are separate rules and never
bind here. Solver CLARABEL, tol 1e-9. **All 68 months solved `optimal`; max
constraint violation 2.06e-08.**

There is **no sector constraint** in this arm. `sector_limit = None`.

## Selection

Universe: |price| >= $5, size group not in {nano, micro}, finite beta /
rvol_21d / me. Short candidates additionally need market cap >= $500m.

Candidates: 150 long + 150 short, chosen **sector-balanced** — each sector's
slot count is proportional to its share of the eligible universe and is the
SAME for both legs, with a 2.5x retention buffer applied inside each sector.
This is `sizing/g3_cost0020/selection.py` and it differs from `optimizer/`.

## Results

                              IR
    gross (no cost)          0.7730
    net of 20bp (engine)     0.6994
    net of 65bp + borrow     0.4556

The engine always charges `trading_cost_bps` = 20bp on realised trades inside
`account()`. The 0.002 in the objective is the optimiser's BELIEF about cost
and deducts nothing, so raising it cannot flatter the reported P&L.

"65bp + borrow" re-costs the same monthly returns at 65bp per dollar traded
plus 152bp annual on short gross. Those two numbers are measured on the team's
daily engine, not on this one.

    CAGR                       12.96%        ending NAV      $1.99bn
    annual volatility           7.32%        max drawdown    -6.65%  (-7.36% at full cost)
    realised beta vs SPX       -0.1535
    annual one-way turnover   137.82%        cost @20bp       3.12% of NAV
                                             cost @full       2.38% of NAV
    gross                      75.0%         net   -1.80% (range -17.51% .. +11.85%)
    positions                  300           max weight at rebalance 2.00%
    max single-sector net      23.57%        missing-return gross 0.285%

## Known limitations — please read before quoting any level

1. **Monthly research engine.** No execution lag, no intramonth drift, no
   formation-day short eligibility. The team's registered daily engine
   (`06_final`, test_M) has all three. Levels from here are NOT comparable to
   the registered number; only comparisons WITHIN this engine are valid.

2. **Sector exposure is unconstrained.** Max single-sector net 23.57%. The
   score is sector-neutralised in `ranking.py` but the portfolio is not.

3. **59.8% of positions sit exactly at the 0.1% minimum**, median |w| = 0.100%.
   The book holds 300 names but effective breadth is far lower.

4. **The signal is concentrated in names we screen out.** Mean monthly rank IC
   is 0.171 in nano/micro/sub-$5 versus 0.040 in this screened universe, and
   on screened names it is ~0 from 2023 onward. Independently verified.

5. **No holdout.** This window is the whole OOS period. The kappa and gamma
   values here came from a sweep over this same window and are exploratory,
   not pre-registered. Treat 0.4556 as an upper bound, not an estimate.

6. Missing realised returns are marked at zero (0.285% of gross on average).
   Borrow, market impact and financing spreads are excluded from the engine's
   own accounting and only appear in the "65bp + borrow" line.

## Reproduce

    git fetch origin && git switch --track origin/simple-pipeline-handoff
    python -m pip install -r requirements.txt
    cp chars_final_with_names.parquet data/
    python sizing/g3_cost0020/main.py          # START=None END=None -> full window

Outputs land in `sizing/g3_cost0020/outputs/<n>/` with `run.json` recording the
exact source of every step file plus the engine hash. The arm appends to
`sizing/comparison.csv`.

## Context on the two coefficients

A sweep over kappa at gamma = 0.5, all arms reported, net of 65bp + borrow:

    kappa 0       IR 0.663   turnover 278%
    kappa 0.0005  IR 0.531   turnover 208%
    kappa 0.0010  IR 0.541   turnover 173%
    kappa 0.0020  IR 0.456   turnover 138%     <- this arm
    kappa 0.0065  IR 0.379   turnover 121%
    kappa 0.0240  IR -0.525  turnover  65%

A sweep over gamma at kappa = 0.002:

    gamma 0.1     IR 0.417
    gamma 0.5     IR 0.456                     <- this arm, and the peak
    gamma 2.0     IR 0.204
    gamma 10.0    IR -0.389

So gamma = 0.5 is optimal on this window; kappa = 0.002 is NOT. IR falls
monotonically as kappa rises, and kappa = 0 reproduces the original objective
(0.663 vs 0.641). Pricing turnover only wins once the per-dollar cost exceeds
roughly 125bp, about 2x what we measured — and by then every arm is near zero
anyway. This arm is the "turnover priced near its true cost" choice, and it
costs about 0.2 of IR against kappa = 0.

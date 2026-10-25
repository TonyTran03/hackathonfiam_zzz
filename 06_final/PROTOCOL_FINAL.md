# Final-round protocol (written before any 2021-2026 number from the daily engine)

Committed before the test window is run. Each open choice below names the data
that decides it and the rule, so the result cannot choose the rule.

## What is carried over unchanged from round 1

- The forecast: per-fold blend of gradient-boosted trees and linear models on
  the 147 characteristics, refit annually on an expanding window, blend chosen on
  each fold's own validation block (`02_prediction/03_train_predict.py`).
- Score: neutralised on sector, size and beta each month, averaged over 3 months.
- Long screen: price >= $5, no nano or micro caps. Turnover buffer 2.5x.
- Inverse-volatility weights inside each leg; legs sized on beta with feedback
  from each leg's own realised beta (weight 0.6).

## What the mandate forces (no data used to choose)

| Item | Round 1 | Final | Why this value |
|---|---|---|---|
| Names per leg | 100 | 150 | floor is now 200 combined; 100/leg leaves no margin for a delisting |
| Short universe | screen only | + market cap >= $500m at formation | mandate; checked on the formation-day close, drawn with a 10% cushion at month end |
| Single-name cap | 2% | 1.5% house, 5% mandate | more names, smaller positions |
| Capacity | none | position <= 3 days x 10% of ADV, against current NAV | $1bn compounding fund; caps tighten as NAV grows |
| Gross | 200% at formation | 195% target, scaled back above 199.5% at any close | daily marking: drift could breach 200% between rebalances |
| Execution | earn the whole month | form at close of first trading day, earn from day 2 | Section 7 convention |
| Beta feedback | 24 monthly points | 252 daily points, Dimson lag 0+1, min 126 | daily data measures it far more precisely |
| Delisting | 0% mark | remainder of the monthly CRSP return; else -30% long / 0% short | Section 7.6 |

## Cost model (fixed before any run; construction and accounting only)

Commission 1 bp + half the Corwin-Schultz spread (`bidaskhl_21d`, floored 2 bp,
capped 50 bp) + square-root impact 0.7 x daily vol x sqrt(trade / ADV). Borrow
by size group: mega 25 bp, large 30, small 75; +500 bp for top-decile
idiosyncratic volatility. Flat alternatives reported alongside: trading 0/10/
20/30/50 bp; borrow 50 bp large and mega, 500 bp everything else (Section 7).

## Open choices and how each is decided

**D1. How often to re-tighten exposures: monthly (M), weekly (W) or daily (D).**
Decided on the 2019-2020 design window only, on risk and cost, not return
(our own power test showed a 24-month window cannot resolve an IR difference
smaller than about 1.1). Rule: among M, W, D, keep those whose design-window
daily beta is inside +/-0.10 and whose 63-day rolling daily beta is inside
+/-0.30 on at least 90% of days; of those, choose the one with the lowest
annual trading cost. If none qualifies, choose the one with the smallest
absolute daily beta.

**D2. Event overlay E (exit longs within one day of a distress 8-K).**
Decided on an event study of filings dated 2015-2020 (`f05_event_study.py`).
Rule: adopt if the mean market-adjusted return from t+2 to t+21 is negative
with a monthly-clustered t below -2.

**D3. Risk layer.** Three versions share one trigger set (`f04_risk_layer.py`):
none, fixed rule, agent. The fixed rule and no-layer are run now. The agent
needs an API key and runs at the event; its result is reported next to the
other two whatever it is. Triggers and the fixed rule are frozen in this commit.

## The test run

One run per configuration on 2021-01 .. 2026-08. Every configuration run is
listed in `06_final/output/run_register.csv`, adopted or not. The headline is
the configuration selected by D1-D2, not the best of the register.

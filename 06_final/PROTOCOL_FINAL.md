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

## Amendment 1 -- design window only, before any test-window run (2026-10-25)

The first design-window run (`design_M`, 2019-2020) cost 10.3% of NAV a year.
Diagnosing it on the design window alone led to four changes to construction
and cost accounting. None reads a 2021-2026 number.

1. **Execution is capped at 10% of ADV per name per day.** The original
   capacity rule bounded the *position* at 3 days x 10% of ADV but let the
   *trade* that builds it go through in one day, i.e. up to 30% of ADV. Orders
   now carry over until filled (Section 3.3: desks keep participation below
   10-20%).
2. **Half-spread is capped by size group** (mega 3 bp, large 6, small 15,
   micro 40). Half the Corwin-Schultz estimate gave a 36 bp median for mega
   caps, an artefact of the estimator reading intraday volatility as spread.
3. **No-trade band of +/-50% on continuing positions.** Two thirds of formation
   turnover (20% of NAV a month against 7-9% for entries and exits) was
   re-weighting names already held toward exact inverse-vol targets.
4. **Gross 190% at formation, scaled back to 195% if a close exceeds 199.5%.**
   At 195% a 2.5% market move breached the band 45 times in 24 months.

The square-root impact coefficient stays at 0.7, the conservative end of the
published range; the report shows 0.25 / 0.5 / 1.0 beside it.

## Decisions taken (design window and pre-2021 event study)

**D1 -> monthly (M).** All three frequencies pass the beta screen (daily beta
-0.06 M, -0.09 W, -0.09 D; 63-day beta inside +/-0.30 on 100% of days for
all three). Monthly is cheapest: 4.67% of NAV a year against 4.93% (W) and
5.05% (D). Weekly and daily re-tightening bought no neutrality.

**D2 -> do not adopt E.** 391 distress 8-Ks on tradable names, 2015-2020:
mean market-adjusted return t+2..t+21 of -1.38%, monthly-clustered t = -1.49,
short of the -2 bar. Items 3.01 (t -2.72) and 4.02 (t -2.10) clear it alone;
picking them now would be choosing the rule after seeing the result, so E is
run on the test window and reported, not adopted.

**Register for the test window** (one run each, all reported):
M (headline) - W - D - M+E - M+rule layer - M at $250m / $4bn starting NAV
(capacity, descriptive) - M+agent layer (at the event, needs an API key).

## Amendment 2 -- cost-aware trade triage, POST-HOC (2026-10-25, evening)

Designed AFTER the test-window register showed that trading costs take the
book from IR 0.65 before costs to 0.06 after them. It is therefore labelled
post-hoc everywhere it appears, and is not a candidate for the headline.

- The no-triage baseline is the engine exactly as registered (`test_M`): it
  already carries a fixed-rule triage of its own, the +/-50% no-trade band on
  continuing names and the 10%-of-ADV daily execution cap. Mode `none`
  reproduces it to the dollar.
- `rule` adds a fixed cost rule on top: above 130 bp all-in, trade half;
  above 200 bp, skip (an exit or a side flip is halved, never skipped).
- `ai` sends the same review-eligible trades to a language model.
- Thresholds were read off the 2019-2020 design-window cost distribution
  (quartiles 53 / 88 / 133 bp, 90th percentile 203 bp) before any test-window
  triage run, and are not changed after it.
- The question the comparison answers: what does a fixed cost rule, and then
  an AI, add ON TOP OF the band and the participation cap?
- One run per mode on 2021-01 .. 2026-08, all reported. The position-risk
  agent (pre-registered as "M+agent layer") stays a separate
  optional mode.

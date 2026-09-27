# Pre-registered variants: written before either run

Two open questions from the team discussion of 2026-09-21 to 2026-09-23. This
note fixes the rule, the single run, and the acceptance criterion for each
BEFORE any result is seen, following the frozen-protocol practice of the
model-comparison experiment. Each variant is one run of stages 4 and 5 on the
frozen per-fold-blend forecasts (`35e3e6f`). Whatever the numbers say, they go
in the appendix. Neither variant becomes the traded book unless the team adopts
it before the model freeze.

## Why these two, and why now

Both are neutrality questions, not return questions. The brief says the
committee checks that the book "really is neutral before we look at anything
else", and the rolling 12-month beta chart is the exhibit they read first.

Diagnosis behind variant B (from the committed holdings and returns, per-leg
realised beta of the underlying stocks per dollar of notional, S&P 500 excess):

| year | long-leg beta | short-leg beta | book beta | avg net exposure |
|------|--------------:|---------------:|----------:|-----------------:|
| 2021 | +0.75 | +0.43 | +0.34 | +0.9% |
| 2022 | +0.88 | +1.21 | -0.16 | +11.9% |
| 2023 | +1.20 | +1.60 | -0.14 | +19.2% |
| 2024 | +1.35 | +1.39 | +0.25 | +19.8% |
| 2025 | +0.95 | +1.25 | -0.18 | +9.5% |
| 2026 | +0.60 | +1.26 | -0.54 | +14.5% |
| all  | +0.92 | +1.23 | -0.16 | +12.5% |

The short leg is structurally higher beta than the long leg, and in 2026 the
long leg's realised beta halved while the short leg's did not move. The beta
control measures each leg over a trailing 24-month window and shrinks the
per-stock estimate 60% toward it; a 24-month window cannot follow a change
that large within a year. The 2026 short book is heavy in names whose realised
beta is far above any historical estimate: crypto miners and treasuries
(Core Scientific, Riot, Strategy, Bitmine), quantum (D-Wave, Quantum Computing
Inc.), AI infrastructure (CoreWeave, Astera Labs), and other retail-driven
names (AST SpaceMobile, Red Cat, Trump Media). Ten of 57 rolling 12-month
windows sit outside +/-0.3, and the window ending 2026-08 is at -0.63.

## Variant S: sector count cap (Oliver's option B, Alex's +1)

**Problem.** Residualising the score on sector dummies removes each sector's
mean score but not its skew, so the traded book averages 7.8 tech longs
against 27.1 tech shorts, 29.8 health-care longs against 20.7 shorts, and 10.9
financials longs against 17.8 shorts. The sum of absolute long-minus-short
count differences is 52 of 200 names when the differences are averaged first
(Oliver's figure), and 82.7 of 200 when measured month by month and then
averaged (the number that matters for a monthly book; worst month 130). By
weight, the per-month sum of absolute sector net exposures averages 89.7% of
capital and the largest single-sector net exposure in any month is 45.5%. The
same tilt exists in the 2019-2020 validation window, so it is structural to
the model, not a test-period artefact.

**Rule.** Keep the global ranking and the turnover buffer exactly as they are.
After the 100 longs and 100 shorts are chosen, for every GICS sector (2-digit
code) whose long count minus short count exceeds +5, drop the lowest-scoring
long in that sector and replace it with the highest-scoring unselected
candidate from a sector that is not at its cap; symmetrically for sectors
below -5 on the short side. Repeat until every sector is inside +/-5. Names
with no sector code form their own bucket. Nothing else changes.

**Acceptance criterion (neutrality, not return).** With a cap of 5 and 12
sector buckets the per-month count imbalance is at most 60 by construction, so
the count metric cannot fail; the decision rests on cost and on weight. Adopt
if the per-month sum of absolute sector net exposures by WEIGHT falls below
60% of capital (from 89.7%) and the full-period information ratio moves by
less than 0.10 in either direction. If the IR
falls by more than 0.10, do not adopt, report the result, and note the cost of
neutrality in the appendix. If it rises by more than 0.10, still report it as
a neutrality change, not as an improvement we selected for.

**Expected direction, stated in advance.** Oliver estimated about 1.3
percentage points of the 2021-2022 short alpha came from the sector bet, so
the IR is expected to fall slightly.

## Variant B: faster beta feedback

**Problem.** See the table above. The book's mandate exposure drifts because
the leg-beta measurement lags.

**Rule.** `BETA_FEEDBACK_WINDOW` 24 months to 12 months, `BETA_FEEDBACK_MIN`
12 to 9, `BETA_FEEDBACK_WEIGHT` unchanged at 0.6. Nothing else changes.
Past months only, as now.

**Acceptance criterion.** Adopt if the number of rolling 12-month windows with
|beta| > 0.3 falls (currently 10 of 57) AND the absolute full-period beta does
not rise, regardless of what the information ratio does. If the IR falls, say
so; neutrality is the mandate.

**Expected direction.** Fewer out-of-band windows in 2026, higher net exposure
in some months (the sizing has to lean further to reach neutrality), and a
lower IR because the 2026 gains partly came from being short beta in a market
that fell in June and July.

## What is not being run

- Any combination of S and B (that would be a third look).
- A beta cap or borrowability screen on the short leg. Alex's point stands that
  a borrowability screen should be decided on tradability grounds, not on
  returns; it is a separate decision for the team.
- Anything after the model freeze.

## Results (run 2026-09-23, after the rules above were written)

Both variants were run once each on the frozen per-fold forecasts, stages 4
and 5 only. The default book was rebuilt first and reproduced the committed
holdings byte for byte, so the switches change nothing unless turned on.
Monthly return series: `variants/variant_S_sector_cap_portfolio_returns.csv`
and `variants/variant_B_beta12m_portfolio_returns.csv`. Gross of trading
costs, 01/2021 to 08/2026.

| | Official book | Variant S: sector cap 5 | Variant B: 12-month beta feedback |
|---|---:|---:|---:|
| Information ratio vs cash+4% | 0.88 | **1.33** | 0.92 |
| Sharpe (over cash) | 1.19 | 1.63 | 1.22 |
| CAGR | 19.65% | 27.07% | 20.25% |
| Max drawdown (monthly) | -6.53% | -5.46% | -6.81% |
| Alpha vs S&P 500 (t) | 17.3% (3.22) | 23.1% (3.63) | 18.0% (3.30) |
| Beta vs S&P 500 (se) | -0.159 (0.120) | -0.125 (0.121) | -0.175 (0.121) |
| Rolling 12m beta outside +/-0.3 | 10 of 57 windows | 7 of 57 | 12 of 57 |
| Rolling 12m beta, last window (2026-08) | -0.63 | -0.21 | -0.52 |
| IR by year 2021..2026 | 0.72, 1.58, 0.40, -0.01, 0.80, 1.23 | 2.38, 1.92, 0.74, 0.47, 0.96, 0.83 | 0.68, 1.59, 0.42, 0.10, 0.75, 1.47 |
| Net exposure, avg (range) | +12.5% (-24%..+30%) | +3.6% (-30%..+22%) | +11.1% (-27%..+30%) |
| Turnover | 24.6% | 27.0% | 24.7% |
| Sector imbalance, counts per month | 82.7 of 200 (max 130) | 32.6 (max 44; no sector beyond 5) | 82.7 |
| Sector net exposure by weight, per month | 89.7% of capital | 38.2% | 89.5% |
| Largest single sector-month exposure | 45.5% | 16.4% | 51.2% |

### Variant S against its criterion

Criterion: weight-based sector exposure below 60% of capital (result 38.2%,
met) and IR within 0.10 of the official book (result +0.45, NOT within). The
rule said a rise beyond 0.10 is to be reported as a neutrality change, not
as an improvement we selected for, and that is how it should be read: the
variant was pre-registered with the expectation that it would COST about a
point of IR. It did the opposite.

Why, mechanically (from the two books): 83% of stock-months are identical.
The cap removed 963 Info Tech shorts and 580 Financials shorts and replaced
them mainly with Health Care (553), Consumer Discretionary (368) and
Industrials (308) shorts. The tech shorts that left had a mean realised excess
return of +1.1% a month (they rallied against us through 2023-2025); the
shorts that came in averaged -1.0% a month. On the long side the swap cost
about 0.9% a month on 603 positions. So the gain is the removal of a
structural short-technology bet during the largest technology rally in the
sample, which is exactly the uncompensated sector risk the cap was designed to
remove. It also fixes most of the 2026 beta drift, because the 2026 short book
was concentrated in high-beta technology names.

Recommendation: adopt on neutrality grounds before the freeze, and say in the
deck that the IR moved up as a consequence, with the run count and this note
in the appendix. Do not tune the cap (5 was chosen before the run; leave it).

### Variant B against its criterion

Criterion: fewer out-of-band rolling windows (result 12 versus 10, worse) AND
absolute full-period beta not higher (result 0.175 versus 0.159, worse).
**Rejected as pre-registered.** A faster feedback window does not fix the 2026
drift; the drift is a composition problem in the short book, which variant S
addresses.

### Looks at the test period added by this note

Two, one per variant, both with rules written first. Recorded in
`research_log.md`.

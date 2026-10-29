# Constraint: time-series valuation cap
Date fixed: 2026-10-28, BEFORE any test-window run.

## Idea
A stock whose PE today sits above the 70th percentile of its own past
5 years is expensive relative to its own history. Do not take a large
long position in it.

## Why this is not already in the model
The 147 features include 8 cross-sectional valuation ratios (ni_me,
be_me, at_me, sale_me, ocf_me, fcf_me, ebitda_mev, mispricing_perf).
All of them compare a stock to OTHER stocks today. None compares a
stock to ITS OWN history. Measured mean monthly rank correlation
between the forecast and this signal: +0.040 -> near-orthogonal.

## Definition (fixed in advance)
PE proxy        = 1 / ni_me  (ni_me = net income / market equity)
pe_pct          = 1 - rolling(60m, min 36m).rank(pct) of ni_me
expensive       = pe_pct > 0.70
loss-making     = ni_me <= 0  -> pe_pct = NaN -> UNCONSTRAINED
insufficient hist (<36m) -> NaN -> UNCONSTRAINED

## Rule
Long weight in an "expensive" name is capped at 0.5% of NAV
(not banned: the engine already forces >=0.1% on every selected name,
so a ban would be mechanically infeasible).

## Measured in advance
coverage in screened universe   68.5%
longs blocked per month         22.2 / 150 avg (min 2, max 53)

## Success criterion
IR falls by less than 0.05 while max drawdown improves.
If infeasible, the ONLY permitted change is raising the cap to 1.0%,
and that change gets recorded here.
---

## Amendment 1 — 2026-10-28, after run 2, before run 3

**What changed and why.** Run 2 showed the constraint binding on only 0.8 of 150
longs per month, against the 22 / 150 estimated in advance. Cause: the estimate
was computed on a screened universe, while `optimizer/selection.py` ships with
`MIN_PRICE = 0.0` and `EXCLUDED_SIZE_GROUPS = ()`. The resulting book was 77.8%
nano/micro/small and held 40.3% of gross in sub-$5 stocks. Those names are
mostly loss-making or too young for 36 months of history, so they carry no
pe_pct and the constraint had almost no surface to act on.

Screens restored to match `beta_matched`: MIN_PRICE = 5.0,
EXCLUDED_SIZE_GROUPS = ('nano', 'micro').

**This is a confound fix, not a tuning step.** The constraint itself —
threshold 0.70, cap 0.5%, NaN unconstrained — is UNCHANGED from the original
registration. No parameter was moved after seeing a result.

**Control arm added.** `sizing/oliver_base/` is byte-identical to
`sizing/oliver_pe/` except `expensive_long_cap = None`. The constraint's effect
is oliver_pe minus oliver_base, with nothing else differing.

**Prior evidence is against the hypothesis.** Measured on the screened universe,
among the model's top-150 longs, names flagged expensive returned +1.958%/month
versus +1.378% for the rest (difference +0.580%/month, t = +1.28), and their
worst month was better (-9.71% vs -10.63%) at identical beta (0.94). Only
volatility supports the constraint (21.3% vs 19.0% annualised). Recorded here
BEFORE run 3. The expected result is a small IR reduction.

**Success criterion is unchanged:** IR falls by less than 0.05 while max
drawdown improves, measured oliver_pe vs oliver_base.

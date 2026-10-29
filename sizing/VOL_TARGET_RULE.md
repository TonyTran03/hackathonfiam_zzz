# Vol-target overlay on c3_sector_2 — rule fixed before computing

Written 2026-10-29, before the overlay was evaluated. Requested by Tony:
scale gross each month on trailing vol so NAV vol is ~10%, past data only,
gross <= 200%, SPX hedge on.

## Order of operations

1. SPX hedge first, then vol-target the HEDGED series. The hedge changes
   volatility, so targeting the unhedged series would miss the stated 10%.
2. Scaling every weight by a scalar k_t scales excess return, turnover, beta,
   sector exposure and position size by k_t. The hedge notional scales with it,
   so the hedged series simply scales by k_t and the overlay is self-consistent.

## Hedge

    h_t = trailing 24-month OLS beta of strategy excess return on SPX excess
          return, estimated through month t-1 ONLY, minimum 12 months.
    Before 12 months of history: h_t = 0.
    hedged_t = r_t - h_t * (spx_t - cash_t)

## Vol target

    sigma_t   = annualised stdev of the hedged, fully costed monthly series
                over the trailing 12 months, through t-1 ONLY, minimum 12 months.
    k_t       = clip(0.10 / sigma_t, 0.25, 1.00)
    Before 12 months of history: k_t = 1.

The upper clip is 1.00, not 2.00/2.00: c3_sector_2 already runs at gross 2.0,
which is the mandate ceiling, so the overlay can only ever scale DOWN. The
lower clip of 0.25 stops the rule from degearing to nothing after one bad
month. Both clips are stated here before any result is seen.

## Costs charged in the overlay (full, not the engine's flat 20bp)

    trading   65 bp per dollar traded, applied to the SCALED weights so the
              turnover saving from degearing is credited honestly.
    borrow    152 bp annual on the short leg's gross, the weighted average rate
              measured on the daily engine, of which 72% was the +500bp
              hard-to-borrow penalty on high-ivol shorts.
    These are the numbers used in last night's cost sensitivity, unchanged.

## What is NOT claimed

The overlay is applied to an already-computed weight path; the optimiser was
not re-run under the vol target. Scaling is exact for exposure, return and
beta, but a re-optimised book could differ. The rule above is fixed; no
parameter in it is chosen after seeing an outcome.

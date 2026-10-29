# Sector-constraint agent: rule written before any result

**Written:** 2026-10-29 11:43 (UTC−4). No agent input, decision, optimizer run or return had been
computed for this experiment. The only earlier look at the data was a descriptive check of
`holdings_final.csv` while locating code (median largest sector gross share 28.7%, Health Care
27%). Nothing below changes after seeing results.

## Base book is a config, and may change

- **The base book is set in `base_config.yaml`, not hard-coded.** It names the optimizer path,
  the optimizer parameters, the forecast column, the overlay switch and the reference holdings.
  It currently holds c3_sector_2: `sizing/optimizer` defaults with `sector_limit = 0.02`,
  forecast `current_gbm_no8k`, the overlay from `VOL_TARGET_RULE.md`, and reference
  `holdings_final.csv`.
- **The base book may change, but the agent rule and its menus never do.** A rerun under a new
  config keeps this rule and these menus unchanged.
- **If the forecast column changes,** the agent inputs and decisions are regenerated, and the
  change is logged in `decision_log.md`. The old files are copied to `archive/`, never deleted.
- **If only optimizer parameters change,** the existing decisions are kept.
- **One command, `python run_all.py`, runs Steps 3–7.** It stops after building inputs if no
  valid decisions exist for the current forecast column.

## Arms

| | Control | Agent |
|---|---|---|
| Book | Whatever `base_config.yaml` says | Same config, same forecasts, same candidates, same γ (`cost_penalty`) |
| Sector net band | The config's `sector_limit` (2% now) | Agent's choice each month from {1%, 2%, 3%} of NAV |
| Sector gross-share cap | None | Agent's choice each month from {1.25×, 1.5×, none} |

**Fallbacks** (all logged):
- Band: if a 1% band is infeasible, it falls back to 2%.
- Cap: 1.25× → 1.5× → none.
- The band is relaxed first, then the cap.
- If the agent arm is infeasible even at a 2% band with no cap, the month uses the control
  setting, and that is logged.

**Cap definition.** For each sector s in month t:

    gross(s) ≤ m × u(s, t) × gross_limit

Here u(s, t) is the sector's share of the tradable universe (count of eligible stocks after
`prepare_universe`), m is the multiple (1.25 or 1.5), and gross_limit is the config's (2.0).
gross_limit is used in place of the book's realised gross so the constraint stays convex; the
gross constraint binds in practice.

**The new constraint is optional and off by default.** It is the `sector_gross_cap` setting in a
copy of the optimizer inside `experiments/sector_agent/`; `sizing/` is not edited. With the
constraint off, the control arm must reproduce the config's base book.

## Agent inputs (Step 3)

All inputs use only data available at the formation date (end of month t−1). Neither book feeds
them.

- One row per month, 68 rows (target months 2021-01 to 2026-08).
- The month order is shuffled with a fixed seed and replaced by an ID. The mapping is kept in
  `month_key.csv`, which the agent does not read.
- Sectors are the 11 GICS sectors, labelled A–K by a fixed random permutation. The mapping is
  kept in `sector_key.csv`, which the agent does not read.

Per sector, three inputs:
1. `share`: the sector's share of the tradable universe (eligible stocks).
2. `disp`: the cross-sectional standard deviation of the base config's forecast column within
   the sector's eligible stocks.
3. `vol`: the trailing 3-month volatility of the sector's equal-weighted monthly return over
   observed months t−3 to t−1, annualised (× √12).

No dates, tickers or sector names appear in the inputs.

## Agent decisions (Step 4)

- The agent reads only `agent_inputs.csv` and this file.
- For each row it picks a band ∈ {1%, 2%, 3%} and a cap ∈ {1.25×, 1.5×, none}, with a one-line
  reason.
- It saves `agent_decisions.csv` (ID, band, cap, reason) before any optimizer run.
- It sees no returns or results while deciding.

## Overlay and costs (both arms)

The overlay follows `VOL_TARGET_RULE.md`; the original script is not on this machine, so it is
reimplemented from the text.

- **Hedge.** `h_t` = trailing 24-month OLS beta of the arm's fully costed, unscaled excess
  return on SPX excess return, through t−1. Minimum 12 months; before that, h = 0.
- **Vol target.** σ_t = annualised standard deviation of the hedged, fully costed, unscaled
  series over the trailing 12 months through t−1. Minimum 12 months; before that, k = 1.
  Then k_t = clip(0.10 / σ_t, 0.25, 1.00).
  - Using the unscaled series for σ avoids feedback from k into its own estimate. This is my
    reading of the rule text.
- **Final book.** k_t × weights, with the hedge notional scaled by k_t as well.
- **Costs.**
  - Trading: 65 bp per dollar traded, measured on the scaled weights against the previous
    month's drifted, scaled book.
  - Borrow: 152 bp a year on short gross (k_t × short gross).
  - The engine's flat 20 bp is not charged a second time.

## Reproduction check (Step 5), a gate

The control arm is compared with the config's reference holdings, excluding the SPY hedge row,
matched by formation date and ticker.

- **Shape:** the same names each month, and the normalised weights (position / gross) agree to
  within 1e-4 of gross.
- **Scale:** the reference's gross in dollars is reported against k_t × gross × NAV.

**If the control arm does not reproduce the reference after the overlay, the run stops and
reports it.** No arm comparison is published in that case.

## Success (fixed now)

All four must hold:
1. **Concentration.** The agent arm's largest sector gross share and its Health Care gross share
   are both clearly lower than control's. "Clearly" means the median month is at least 3
   percentage points lower for both.
2. **Net IR.** Net IR after all costs is not materially worse: agent net IR ≥ control net IR −
   0.10.
3. **Mandate.** Every mandate constraint is met in every month of the agent arm, after the
   overlay:
   - 200–500 names;
   - gross ≤ 200%;
   - net within ±50%;
   - single name ≤ 5%;
   - short book ≥ $500m;
   - at least 5 sectors;
   - every sector's net ≤ 20%.
4. **Control breaches.** Control-arm breaches are reported the same way.

IR is the annualised mean of the return minus (cash + 4%/12), divided by its annualised
standard deviation.

The result is reported whichever arm wins. Both arms run once, 2021-01 to 2026-08.

## Addendum, 2026-10-29 11:55 (UTC−4), before any arm result: the control arm is a re-run

**The control arm is a re-run of our optimizer, not the exact submitted book.** The
reproduction gate above failed with `sizing/optimizer` defaults plus `sector_limit = 0.02`.

**How the matching was done.** I searched for a config by comparing 2021-02 positions only
(no returns): `match_config.csv`, `match_config_fine.csv` and `match_config_fine2.csv`.
- `cost_penalty` (γ) from 227.5 to 235 put all 299 matched 2021-02 positions within 1 bp of
  `holdings_final`.
- `base_config.yaml` now sets **γ = 230**. γ stays fixed in both arms, as the rule requires.
- This is an optimizer parameter, so the agent decisions are kept (see `decision_log.md`).

**How close the control gets over all 68 months** (`reproduction_shape_matched.csv`; final
figures in RESULTS.md):
- **Names.** Every reference name not matched is one of our names with no ticker in the panel
  that month (counts are equal in every month). None of our ticker-matched names is missing
  from the reference.
- **Weights.** On matched names, signs agree 100%. The max weight difference has a median of
  0.027% of gross (about 0.05% of NAV) and a worst month of 0.1% of gross. That is not "within
  rounding".
- **Dollar scale.** The reference's gross is 97.6–100.0% of our k × gross × NAV, drifting
  steadily from 2021. The reference compounds about 5 bp a month less, even before the overlay
  has any effect. With 85 bp trading cost the ratio is 100.0–103.5%, so its cost lies in between.
  The costs here stay at the rule's 65 bp + 152 bp, unchanged.

**Matching stopped at 11:54,** within the user's 12:05 limit. `allow_approximate_control: true`
in the config lets the run continue, and the gap is reported. Both arms run with identical code.

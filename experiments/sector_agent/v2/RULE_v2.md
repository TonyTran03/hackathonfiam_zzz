# Sector-constraint agent v2 (Tony's constraint set): rule written before any result

**Written:** 2026-10-29 12:35 (UTC−4). No v2 optimizer run or result existed when this was
written. The v1 results (`../RESULTS.md`) are kept unchanged and were already known. Nothing
below changes after seeing v2 results.

## What stays the same as v1

- **Forecasts:** `current_gbm_no8k`, the same candidate selection (150 long, 150 short), and the
  same covariance (Ledoit–Wolf, 36 months).
- **Objective:** sᵀw − λ·wᵀΣw − γ·(c/10⁴)·(‖w − w̃‖₁ + f), with λ = 100, γ = 230 and c = 20 bp.
  γ is fixed in both arms, at the value matched in v1.
- **Agent decisions: `../agent_decisions.csv` from v1, reused unchanged.**
  - SHA-256 is `eaedf4b1c7580bfca8c8624ba62557d62fc80dcd8d9dbfaacbdf63c3f3fa1c19`.
  - Dates are mapped through `../month_key.csv`
    (`196f8dc757b58987c01aef57840811428b072068bcff94e6aa4dd41d5df1b96a`).
  - Both checksums are verified at run time.
  - The masked inputs (universe share, forecast dispersion and trailing sector vol) do not depend
    on the constraint set, so the agent does not re-decide.
- **Menus:** band ∈ {1%, 2%, 3%}; gross-share cap ∈ {1.25×, 1.5×, none} × u(k, t) × G, where
  u is the sector's share of the tradable universe and G = 2.
- **Overlay:** σ_t is the annualised standard deviation of the fully costed, unscaled series over
  the last 12 months (through t−1, minimum 12 months), and k_t = clip(0.10/σ_t, 0.25, 1.00).
- **Costs:** 65 bp per dollar traded, measured on the scaled book, plus 152 bp a year on short
  gross. These are identical in both arms.

## Base constraints, v2 (both arms)

| | Constraint |
|---|---|
| Long candidates | w_i ≥ 0.001 |
| Short candidates | w_i ≤ −0.001 |
| Gross | Σ\|w_i\| ≤ 2.00 |
| Net | Σ w_i = 0 (dollar neutral) |
| Position cap | \|w_i\| ≤ 0.035 |
| Beta neutral | β̂ᵀw = 0 |
| SPX futures hedge | **None.** The overlay's hedge ratio is set to h_t ≡ 0, so the vol target applies to the unhedged series. |

**β̂ is estimated from data up to t−1 only.** It is the engine's `beta_use`: the first available
of `betabab_1260d`, `betadown_252d` and `beta_60m`, read from the panel row at eom t−1 and
clipped to [−0.5, 3.5].

**Lower and upper bounds on each name.**
- Longs: 0.001 ≤ w_i ≤ 0.035.
- Shorts: −0.035 ≤ w_i ≤ −0.001.
- The 1 bp floors replace strict w_i > 0 and w_i < 0, which a solver cannot enforce.

## Arms

**Control.** The base constraints plus a sector band |Σ_{i∈S_k} w_i| ≤ 0.02 for every sector k.

**Agent.** The base constraints plus that month's decision:
- |Σ_{i∈S_k} w_i| ≤ b_t;
- Σ_{i∈S_k} |w_i| ≤ m_t · u(k, t) · G.

**Infeasible months.**
- **Agent:** only the agent's choices are relaxed. The band is relaxed first, upward from the
  chosen value to 3%. Then the cap moves one step (1.25× → 1.5× → none), and the band restarts
  at the chosen value. Every attempt is logged in `fallbacks_v2.csv`.
- **Never relaxed:** base and mandate constraints. If even a 3% band with no cap is infeasible,
  that month is reported as infeasible and the run stops.
- **Control:** if the control arm is infeasible in any month, the run stops and reports it.

## Mandate check (every month, both arms, after the overlay)

| Mandate | Check |
|---|---|
| Names | 200–500 names with \|k·w_i\| > 1e-6 |
| Gross | k·Σ\|w_i\| ≤ 2.00 |
| Net | \|k·Σw_i\| ≤ 0.50 |
| Single name | k·\|w_i\| ≤ 0.05 |
| Short market cap | Every short name has `me` ≥ $500m at formation (panel row at t−1) |
| Sectors | At least 5 sectors held |
| Sector net | max_k \|k·Σ_{i∈S_k} w_i\| ≤ 0.20 |

**Realised volatility.** The full-window annualised volatility of the net series is reported
against the 12–14% cap.

## Reporting (`RESULTS_v2.md`)

**Side-by-side table:**
- net IR, gross IR, vol and max drawdown;
- monthly beta with its standard error (OLS of net excess return on S&P 500 excess return over
  the full window);
- max sector net, largest sector gross share and Health Care gross share;
- turnover and cost (% of NAV);
- infeasible months, fallbacks and mandate breaches.

**Also in the file:**
- the decision log mapped to dates;
- one worked example month;
- a 3-sentence summary;
- one line comparing the v2 control with the v1 control.

**Success.** The same success rule as v1 is applied:
1. **Concentration:** the largest sector share and the Health Care share are both at least 3 pp
   lower in the median month.
2. **Net IR:** agent net IR ≥ control net IR − 0.10.
3. **Mandate:** zero mandate breaches in the agent arm.

The result is reported whichever arm wins. Both arms run once, 2021-01 to 2026-08.

## Same caveats as v1

- **The control is a re-run of our optimizer** under new constraints, not a submitted book.
  There is no reference holdings file for v2, so there is no reproduction check.
- **The overlay is reimplemented** from `VOL_TARGET_RULE.md`.

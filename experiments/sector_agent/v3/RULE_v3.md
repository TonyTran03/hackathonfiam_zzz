# Sector-constraint agent v3 (Tony's new objective): rule written before any result

**Written:** 2026-10-29 12:51 (UTC−4). No v3 solve or result existed when this was written. The
v1 and v2 results were already known and are kept unchanged. Nothing below changes after seeing
v3 results.

**This is our implementation of Tony's formula,** written from the user's specification. Tony's
code for it is not on this machine (searched 12:45). Every interpretation choice is listed at the
end so Tony can confirm or correct it.

## Objective (each month t)

$$
\min_{w}\;\; -\alpha^\top w \;+\; 0.024\,\lVert w - w_{\text{prev}} \rVert_1 \;+\; 0.5\, w^\top \Sigma\, w
$$

- **Universe U_t.** All eligible names at t, using the engine's `prepare_universe`: price ≥ $5,
  no nano or micro caps, and finite beta, `rvol_21d` and `me`.
- **Long candidates:** L = {forecast > 0}.
- **Short candidates:** S = {forecast < 0 and `me` ≥ $500m at formation}.
- **α.** The raw `current_gbm_no8k` forecast (expected next-month excess return), demeaned across
  U_t each month. It is not the ranked score.
- **w_prev.** Last month's book, drifted by its realised returns. Names that have left U_t are
  exited. Their turnover is a constant in the objective, so it doesn't affect the solve, but it
  is charged in costs.

## Σ: the engine's method over the full universe, never built as a dense N×N matrix

The method is the same as `sizing/_engine.py::covariance_for`:
- 36 monthly returns strictly before t, with at least 12 observations per stock;
- sample standard deviation sd (ddof 0), falling back to `rvol_21d`·√21 for unreliable stocks,
  with a floor of 1e-4;
- standardised returns Z = (x − x̄)/sd, missing values set to 0, and unreliable columns set to 0;
- a Ledoit–Wolf fit on Z, giving shrinkage δ and μ = trace(S)/N, where S = ZᵀZ/T.

The shrunk matrix is (1−δ)·S + δ·μ·I. As in the engine, it is converted to a correlation and
rescaled by sd, with unreliable stocks given zero correlation and variance sd². This is
algebraically identical to

$$
w^\top \Sigma w \;=\; \frac{1-\delta}{T}\,\lVert Z A w \rVert_2^2 \;+\; \delta\mu\,\lVert A w \rVert_2^2
\;+\; \sum_{j\,\text{unreliable}} sd_j^2 w_j^2 \;+\; 10^{-10}\lVert w\rVert_2^2
$$

**About A.** A = diag(a_j), with a_j = sd_j / √((1−δ)S_jj + δμ) for reliable stocks and 0 for
unreliable ones. This is the user's formula, with D = diag(sd) replaced by A so that it matches
the engine's step of converting to a correlation. For fully observed stocks S_jj = 1, so A is
close to D.

**Checked before the run.** The factor form is checked against the engine's dense `covariance_for`
on the 300 candidates of 2021-01, as a numerical check of the algebra.

**β̂.** The engine's `beta_use`, read from the panel row at t−1 (data up to t−1 only).

## Constraints (Tony's, as in v2)

| | Constraint |
|---|---|
| Gross | ‖w‖₁ ≤ 2.00 |
| Net | 1ᵀw = 0 |
| Position cap | \|w_i\| ≤ 0.035 |
| Beta neutral | β̂ᵀw = 0 |
| Signs | w_i ≥ 0 on L; w_i ≤ 0 on S; w_i = 0 elsewhere |

## Two stages each month

- **(a)** Solve with no minimum weights.
- **(b)** Keep the 150 largest longs and the 150 most negative shorts from (a). Fix every other
  name to 0, add d_i·w_i ≥ 0.001 on those 300, and re-solve. The result holds exactly 300 names.

The arm's sector constraints apply in both stages. The agent's fallbacks re-run both stages.

## Arms

**Control:** the above plus |Σ_{i∈k} w_i| ≤ 0.02 for every sector k.

**Agent:** the above plus v1's decision for that month.
- Sector band b_t, and gross-share cap Σ_{i∈k}|w_i| ≤ m_t·u(k, t)·2.
- u(k, t) is the sector's count share of U_t.
- The decisions file is `../agent_decisions.csv`, unchanged:
  - SHA-256 `eaedf4b1c7580bfca8c8624ba62557d62fc80dcd8d9dbfaacbdf63c3f3fa1c19`;
  - mapped to dates through `../month_key.csv`
    (`196f8dc757b58987c01aef57840811428b072068bcff94e6aa4dd41d5df1b96a`);
  - both checksums verified at run time.

**Fallbacks (as in v2).**
- If the agent's choice is infeasible, only the agent's choices are relaxed. The band goes up to
  3% first; then the cap moves 1.25× → 1.5× → none, with the band restarting at the chosen value.
  Every attempt is logged.
- Base and mandate constraints are never relaxed.
- If the control arm is infeasible in any month, the run stops and reports it.

## Overlay, costs, mandate checks and success (as in v2)

- **Overlay.** Oliver's vol target is applied to the unhedged series (h ≡ 0):
  k_t = clip(0.10/σ_t, 0.25, 1.00), with σ_t taken from the trailing 12 months of the fully
  costed, unscaled series.
- **Costs.** 65 bp per dollar traded, on the scaled book, plus 152 bp a year on short gross.
- **Mandate checks.** The same as v2:
  - 200–500 names;
  - gross ≤ 200%;
  - net within ±50%;
  - single name ≤ 5%;
  - every short ≥ $500m market cap at formation;
  - at least 5 sectors;
  - sector net ≤ 20%;
  - realised vol reported against the 12–14% cap.
- **Success** (the same as v1 and v2). All three must hold:
  1. The largest sector share and the Health Care share are both at least 3 pp lower in the
     median month.
  2. Agent net IR ≥ control net IR − 0.10.
  3. Zero agent mandate breaches.

## Procedure and time limits

1. **Test month.** Run 2021-01 first, for both arms. Report solve time, names, gross, net, beta
   and max sector net. If one solve takes over 60 seconds, stop.
2. **Full run.** Run all 68 months for both arms, in parallel, saving after every month.
3. **Hard stop at 13:20.** Whatever has finished by then goes into `RESULTS_v3.md`, which says
   exactly how far the run got. Arms are compared only over months both have completed.

## Interpretation choices for Tony to confirm

1. **Universe** = the engine's `prepare_universe`, which also requires finite beta, `rvol_21d`
   and `me`, beyond price ≥ $5 and the size groups.
2. **α** = the raw forecast minus its cross-sectional mean over U_t, not over L ∪ S.
3. **Σ** follows the engine's correlation-then-rescale step, so A replaces D (see above). δ and μ
   come from sklearn's Ledoit–Wolf on the full universe's Z.
4. **The 0.024 cost term** uses the drifted previous book. Drift uses the book's gross return; the
   20 bp engine cost is not applied. Turnover from names leaving U_t is excluded from the objective
   as a constant.
5. **Stage (b)** keeps the largest 150 by signed weight on each side, even if some weights in (a)
   are near zero. These get the 0.001 floor.
6. **The sector constraints and the agent's choices** apply in both stages. Sector shares u(k, t)
   are count shares of U_t, as in v1 and v2.
7. **Names with forecast exactly 0, and negative-forecast names under $500m,** are held at 0.
8. **There is no separate γ multiplier:** 0.024 is the full per-unit-turnover coefficient, in the
   same units as w and α (fractions of capital).

## Amendment, 2026-10-29 13:05 (UTC−4), before any full-run result

**α changed from the raw forecast to the ranked score.** The user clarified that the 0.024 lives
in the score function, so α is the engine's ranked score, not the raw forecast:
- α is the `score` column from `sizing/optimizer/ranking.py`: the forecast's cross-sectional
  rank, z-scored, then residualised on size, beta and sector;
- it is demeaned across U_t each month;
- the 0.024 and 0.5·wᵀΣw terms are applied to it as written.

This replaces interpretation choice 2 above. The L/S candidate split still uses the sign of the
raw forecast.

**Why.** The 2021-01 test with the raw forecast left stage (a) empty: the raw forecast has a
standard deviation of 0.4% a month, below the 0.024 cost per unit traded.

Nothing else changes.

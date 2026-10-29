# Mentor-review build: sector- and size-neutral sizing

Built 2026-10-29 after the mentor review. Tony's `optimizer/` is unchanged; this folder copies
its features/ranking/constraints and changes only what the mentor asked for.

## Final model (the one sent to Arcana)

Run from this folder (about 5 minutes; outputs go to `outputs/`, which is gitignored):

```
N_LONG=100 N_SHORT=1000 LONG_FLOOR=0.001 SHORT_FLOOR=0 K_SHORT=100 \
OBJECTIVE=mv_ann ANNUAL_COST=0.024 ALPHA=score NET_LIMIT=0 RISK_AVERSION=2 GROSS=1.75 \
python run_neutral.py final_g1.75 0.02 0.02 m
```

- Objective (mentor's): $\min_w -\alpha^\top w + 0.024\lVert w-w^-\rVert_1 + 1.0\, w^\top\Sigma_{ann} w$, where $\alpha = 12\cdot s/\mathrm{sd}(s)\cdot \mathrm{sd}(\text{forecast})$. `RISK_AVERSION=2` multiplies the 0.5, so the coefficient is 1.0.
- Constraints:
  - gross <= 175%
  - net = 0
  - |w| <= 2%
  - estimated beta = 0
  - every name held >= 0.1%
  - sector net within ±2% (GICS 2-digit)
  - size exposure within ±0.02
  - top 100 long; 100 shorts picked by the optimizer from the bottom 1,000 (market cap >= $500m), in two stages
  - 200 names
- Add `VOL_LIMIT=0.12` for the predicted-vol cap. It never binds here (predicted vol peaks at 9.4%), so the results are identical, but each solve is much slower.
- Results 2021-01 to 2026-08:
  - IR 0.98; 0.70 at 65bp + 1% borrow
  - CAGR 21.3%, vol 13.1%, max DD -7.1%
  - beta -0.02, max sector net 2.0%
  - stock-selection P&L 18.0%/yr, sector P&L 0.4%/yr
  - no losing year

**Agent hook.** `SECTOR_SCHEDULE=<csv>` sets the sector band month by month. The csv needs `target_month` plus `band_used` (or `sector_limit`), for example `../../experiments/sector_agent/decision_log_by_date.csv`. Months that are not in the file keep the band passed on the command line. Each month's band is written to `sector_limit_used` in the monthly output.

```
SECTOR_SCHEDULE=../../experiments/sector_agent/decision_log_by_date.csv <same env as above> \
python run_neutral.py final_agent 0.02 0.02 m
```

## What the mentor asked, and what this folder does

| Mentor point | Here |
| --- | --- |
| Signal strips sector, so sizing must not bet between sectors | Hard constraint: \|net weight\| per GICS sector <= 2% of NAV |
| Size neutrality (market cap, not dollar balance) | Hard constraint: \|w . size\| <= 0.02, size = standardized market-cap rank |
| Signal needs size adjustment | Already there: `ranking.neutralise` regresses the forecast on market-cap rank, beta and sector. Score vs size correlation is 0.004 |
| Top names long, wider bottom pool short so constraints can be met | 150 long candidates, 300 short candidates (shorts >= $500m) |
| Enforce neutrality in the weights, not the selection | Constraints sit in the optimizer; every candidate gets >= 5bp so all 450 names are held (mandate 200-500) |
| Daily data for the covariance | `d` mode: 36 months of daily returns (~750 obs) from `06_final/data/dsf.parquet`, Ledoit-Wolf, scaled x21 to monthly |
| Beta not mandatory, can be an overlay | Estimated-beta = 0 kept from Tony's model; realised beta is now -0.01 |
| Cost: model it or drop it and state the limitation | Objective keeps Tony's 0.002 term (it is a function of w through \|w - w_prev\|; F is a constant and does not move the weights). It is ~0.07% of the objective, so this is effectively plain mean-variance. P&L charges 20bp. Impact and borrow are NOT modelled: stated limitation |
| Test the signal on its own, apples with apples | `signal_check.py` |

## Results, 2021-01 to 2026-08 (68 months, saved walk-forward forecasts, 20bp costs)

| Run | Sector cap | Size cap | Cov | IR | CAGR | Vol | Max DD | Realised beta | Max sector net | Names |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tony `g075_cap0.020` (reference) | none | none | monthly | 1.11 | 17.0% | 7.9% | -7.4% | -0.11 | 24.9% | 300 |
| `nb_d` (pools only) | none | none | daily | 0.99 | 16.1% | 8.0% | -8.2% | -0.12 | 24.1% | 450 |
| `n2_m` | 2% | 0.02 | monthly | 0.78 | 15.6% | 9.7% | -10.0% | -0.01 | 2.0% | 450 |
| **`n2_d` (main)** | **2%** | **0.02** | **daily** | **0.75** | **14.7%** | **9.2%** | **-10.1%** | **-0.01** | **2.0%** | **450** |
| `n2_100_d` (top 100 long / bottom 100 short, `N_LONG=100 N_SHORT=100`) | 2% | 0.02 | daily | 0.68 | 14.4% | 9.8% | -10.7% | 0.01 | 2.0% | 200 |
| `wb2_d` whiteboard: top 100 long (w >= 0.1%), shorts picked from bottom 1,000 (w <= 0), 2-stage to 100 held | 2% | 0.02 | daily | 0.63 | 13.9% | 9.8% | -10.7% | -0.01 | 2.0% | 200 |
| `wb2_m` same, monthly covariance | 2% | 0.02 | monthly | 0.75 | 15.5% | 10.2% | -9.3% | -0.01 | 2.0% | 200 |
| `wbmv_l1_d` mentor's exact board (min -a'w + 0.024 dw + 0.5 w'Sw, ann.), whiteboard candidates | 2% | 0.02 | daily | 0.06 | 7.4% | 12.5% | -14.4% | -0.14 | 2.0% | 200 |
| `wbmv_l10_d` same, risk aversion 10 | 2% | 0.02 | daily | 0.44 | 11.7% | 9.6% | -10.6% | -0.06 | 2.0% | 200 |
| `n5_d` | 5% | 0.05 | daily | 0.83 | 15.5% | 9.1% | -12.4% | -0.03 | 5.0% | 450 |

Mentor's annualized objective (`OBJECTIVE=mv_ann`): max alpha'w - 0.018 |w - w_prev|_1 - 0.5 w'Sigma_ann w,
alpha = 12 x IC(0.035) x sigma x z, same constraints and daily covariance:

| Run | Sector/size cap | Cost term | IR | CAGR | Vol | Max DD | Beta | Selection P&L |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mv2_d` | 2% | 0.018 | -0.15 | 5.1% | 11.1% | -16.2% | -0.15 | 3.9%/yr |
| `mv05_d` | 0.5% | 0.018 | -0.12 | 5.7% | 10.2% | -12.6% | -0.11 | 4.0%/yr |
| `mvnc2_d` | 2% | 0 | -0.16 | 4.9% | 11.5% | -18.5% | -0.13 | 3.8%/yr |
| `mv2_l10_d` (risk aversion 10: 0.5 x 10 x w'Sigma w) | 2% | 0.018 | 0.35 | 10.5% | 8.8% | -11.5% | -0.08 | 8.3%/yr |

Risk aversion 10 was set ex ante (lambda = expected IR / target vol = 1 / 0.10) and run once.
Cost sensitivity for `mv2_l10_d`: 50bp 0.21, 65bp + 1% borrow 0.10. Turnover 1.99/yr vs 3.32 for `n2_d`.

The cost term is not the cause (removing it changes nothing). alpha = IC x sigma x z makes the
expected return proportional to each stock's volatility, and at risk aversion 0.5 in annual units the
variance term barely binds, so the largest positions go to the most volatile names. Exact zero
(sector and size = 0) is infeasible with a 5bp floor on 450 names; 0.5% is the tightest run.

P&L split for `n2_d`: sector bets +0.7%/yr, stock selection within sector +11.7%/yr.
Cost sensitivity for `n2_d`: 20bp 0.75, 50bp 0.53, 65bp + 1% borrow 0.38, 100bp + 2% borrow 0.09.
IR by year for `n2_d`: 2021 1.50, 2022 0.83, 2023 -1.13, 2024 0.69, 2025 1.35, 2026 1.13.

Exact sector/size = 0 with the whiteboard setup is infeasible (0.1% floor on 200 names).

## Signal check (`signal_check.py`, tradeable universe, ~1,870 stocks a month)

Alpha = realised return minus a cross-sectional fit on sector, size and beta.

- Rank IC vs alpha 0.035 (t = 3.9), positive in 75% of months.
- Top 100 minus bottom 100 alpha: +1.43%/month, t = 2.3, IR 0.97.
- Decile alpha is broadly increasing, with most of the spread in the worst decile (-0.83%/month).
- 2023 is the weak year (IC -0.007), which matches the portfolio's weak year.

## Honest caveats

- The sector and size limits (2%) were taken from the mentor, not tuned; 5% is shown for sensitivity.
- Monthly rebalancing; weights drift inside the month. Missing returns are marked at zero.
- 20bp flat cost. Impact and borrow are not modelled and matter (see cost sensitivity).
- Earlier allocation settings (75% gross, 2% cap) were chosen by the team on the same 2021-26 window.

## Run

    python run_neutral.py n2_d 0.02 0.02 d     # name, sector cap, size cap, m|d covariance
    python signal_check.py

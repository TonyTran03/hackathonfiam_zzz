> **Future feature specification — not currently active.** No CSV is required yet.
> In each experiment, add future inputs in `features.py` and blend their signal
> in `ranking.py`. Candidate choice belongs in `selection.py`; allocation rules
> belong in `constraints.py`. The hard-constraint suggestions below are research
> ideas from the original notes, not rules the active pipeline applies.

# Carbon Arc features (`carbonarc_features.csv`)

One row per **permno x eom**, the same keys as `signal_design/test.parquet`, so it is a plain
left join. 34,066 rows, 435 permnos, eom 2019-02 to 2026-09. Rebuild with
`python3 build_altdata_features.py <this folder> carbonarc_features.csv` (run from 06_final/carbonarc).

**No look-ahead in timing:** a data month is used at the first month-end on or after its
available date (month-end + Carbon Arc's lag: foot T+5, card T+3, web T+1). So January's data
appears at the February eom formation. `*_data_month` shows which month each row uses.
**Caveat:** the history is today's snapshot (card panel restated, foot traffic modelled), so
any backtest is on revised data.

## Columns

Prefixes: `ft_` foot traffic (PassBy store visits, 100 consumer names, from 2019),
`cs_` card spend (Facteus, 117 consumer names, from 2019), `wt_` website traffic
(Clickstream, 313 non-consumer names, from mid-2020). Log growth, clipped at +/-2.

| Column | Meaning | Why we'd care |
|---|---|---|
| `*_yoy` | log(this month / same month last year) | Demand growing or shrinking; removes seasonality and panel size |
| `*_yoy3` | log(last 3 months / same 3 months last year) | Same, less noisy; main input to the rank |
| `*_yoy2y` | log(this month / two years ago) | Use for 2021, when last year is the 2020 lockdown |
| `*_accel` | yoy3 now minus yoy3 three months ago | Growth speeding up or slowing down |
| `*_z` | yoy vs the name's own last 12 months (z-score) | Surprise relative to its usual growth |
| `*_rank` | sector-relative percentile of yoy3, centred (-0.5 .. +0.5) | Cross-sectional: better or worse than peers |
| `*_data_month` | the data month used | Audit / staleness |
| `ca_score` | mean of the available `*_rank` columns | One number per name per month |
| `ca_n_sources` | how many sources cover the name that month (0-2) | Coverage; 0 = no Carbon Arc data |

Coverage: about 5,000 name-months a year with a `ca_score` from 2022; 2020-21 thinner
(web traffic ranks start 2021-09). Names without coverage have NaN: leave them unconstrained.

## How it plugs into the optimizer (suggestions)

1. **Constraint, "don't short what customers are buying more of":**
   `w_i >= 0` for names with `ca_score_i > 0.3`. Linear, so still convex. Story: our 10
   worst shorts all had improving fundamentals while we were short (see
   `mcp_findings_worst_shorts.md`); this blocks shorting names whose real-economy data says
   demand is rising faster than peers'.
2. **Mirror for longs:** `w_i <= 0` (or `w_i <= small cap`) when `ca_score_i < -0.3`.
3. **Alpha tilt instead of a hard rule:** `mu_i <- mu_i + k * ca_score_i * sd(mu)` with a small k.

Pick one and fix the threshold before looking at test-window results.

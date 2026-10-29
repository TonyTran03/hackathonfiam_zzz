# Sector-constraint agent: results

**Run:** 2026-10-29 11:55, one run of each arm, 2021-01 to 2026-08, under `RULE.md` (written
11:43, addendum 11:55, both before any arm result).
**Reproduce:** `python run_all.py`. The base book is in `base_config.yaml`.

**Verdict: the agent did not meet the success rule.** It cut sector concentration clearly, but
net IR after all costs fell by 0.26, more than the 0.10 allowed. Neither arm breached the mandate
in any month.

## Summary for a mentor

We let a rule-based agent choose, each month, how tightly to cap any one sector's share of the
book, using only information known at the time. It cut the Health Care share of gross from about
27% to 21% in the median month without breaching any mandate limit.

The price was too high: risk-adjusted return after all costs fell from an IR of 1.01 to 0.74,
and the loss is in the gross-of-cost return too. So the cap is removing good positions, not just
saving trading costs.

We report this as a failed test, measured against a re-run of our own optimizer that matches
the submitted book closely but not exactly.

## Important caveat: the control is a re-run, not the submitted book

**The control arm is a re-run of our optimizer, not the exact submitted book
(`holdings_final.csv`).** With the `sizing/optimizer` defaults plus `sector_limit = 0.02`, it
matched the first month exactly but diverged from 2021-02 onwards.

**Matching the trade-off parameter.** A positions-only search on 2021-02 found that cost penalty
γ = 227.5–235 puts all 299 matched positions within 1 bp of the reference
(`match_config*.csv`). The config uses **γ = 230** in both arms. Agent decisions were made before
this and were not changed; γ is an optimizer parameter, so RULE.md keeps them.

**How close the control gets over all 68 months** (`reproduction_check.csv`):

| Check | Result |
|---|---|
| Names | Same in **68 / 68** months. Every reference name we cannot match is one of our names with no ticker in the panel that month (1 a month typically; up to 157 in 2026, when the panel leaves many tickers blank). |
| Long/short sign on matched names | **100%** agree |
| Max weight difference, matched names | Median **0.027% of gross** (about 0.05% of NAV); worst month **0.10% of gross**. Within the 1e-4 threshold in only 3 of 68 months, so **not "within rounding"**. |
| Dollar scale (reference gross ÷ our k × gross × NAV) | **97.6%–100.0%**, drifting down steadily from 2021 even while the overlay is inactive. The reference compounds about 5 bp a month less. With 85 bp trading cost instead of 65 bp the ratio is 100.0–103.5%, so the reference's cost lies in between. Costs here stay at the rule's 65 bp + 152 bp. |

**Two more caveats.**
- Oliver's overlay script is not on this machine, so the overlay is reimplemented from
  `VOL_TARGET_RULE.md`.
- The run used a temporary Python environment, because no existing environment had both cvxpy
  and pyarrow. Versions follow `requirements.txt`: pandas 2.3.1, numpy 2.2.6, pyarrow 25.0.1,
  cvxpy 1.9.3.

## Side by side (after the overlay and full costs)

| | Control (re-run of c3_sector_2, γ = 230) | Agent |
|---|---:|---:|
| **Net IR** (vs cash + 4%) | **1.01** | **0.74** |
| Gross IR (before costs) | 1.32 | 1.07 |
| Volatility (annualised) | 13.6% | 13.6% |
| Max drawdown | −6.7% | −8.6% |
| Max sector net (% NAV) | 2.0% | 3.0% |
| Largest sector gross share, median / max | 27.7% / 35.7% | **22.2% / 27.6%** |
| Health Care gross share, median / max | 26.9% / 35.7% | **20.6% / 27.6%** |
| Monthly one-way turnover | 21.5% | 22.1% |
| Cost (% NAV a year: 65 bp trading + 152 bp borrow) | 4.39% | 4.51% |
| Mean overlay scale k | 0.68 | 0.69 |
| Mandate breaches (month × rule) | **0** | **0** |
| Ending NAV from $1bn | $3.10bn | $2.54bn |

**Mandate margins, worst month.**

| Mandate | Control | Agent |
|---|---|---|
| Names | 300 | 300 |
| Gross | 200% | 200% |
| Net | 14.6% | 14.0% |
| Single name | 5.0% | 5.0% |
| Short book | $875m | $801m |
| Sectors held | 10 | 10 |
| Sector net | 2.0% | 3.0% |

## Success test (fixed in RULE.md)

| Criterion | Result |
|---|---|
| Largest sector and Health Care gross share ≥ 3 pp lower in the median month | **Met.** Largest sector −5.5 pp, Health Care −6.2 pp. |
| Net IR ≥ control − 0.10 | **Not met.** 0.74 vs 1.01, a drop of 0.26. |
| Every mandate constraint, every month | **Met.** 0 breaches in either arm. |
| **Overall** | **Fail** |

The lost IR is not a cost effect: cost rose only 0.12% of NAV a year, while gross IR fell by
about the same 0.25 as net IR.

## Decision log, mapped to dates

- **Source.** `agent_decisions.csv` was written by `agent_decide.py` from `agent_inputs.csv` only,
  before any optimizer run (`decision_log.md`).
- **Mapping.** Dates come from `month_key.csv`. Health Care is GICS 35, label **B** in
  `sector_key.csv`.
- **Fallbacks.** None were needed: every month ran at the agent's own choice.
- **Full table:** `decision_log_by_date.csv`.

| Months | Band | Cap | Mean Δ Health Care share | Mean Δ monthly net return (agent − control) |
|---|---|---|---:|---:|
| 5 | 1% | 1.25× | −8.8 pp | −0.69% |
| 10 | 1% | 1.5× | −6.3 pp | +0.94% |
| 26 | 2% | 1.25× | −5.4 pp | −0.38% |
| 13 | 2% | 1.5× | −6.3 pp | −0.92% |
| 10 | 3% | 1.25× | −3.8 pp | −0.23% |
| 4 | 3% | 1.5× | −5.7 pp | −0.51% |

By year:
- **2021:** mostly 2–3% bands, cap 1.5× early, then 1.25×.
- **2022 H2 to 2023 Q1:** a run of 1% bands, as trailing sector vol was high.
- **2024–26:** mostly 2% / 1.25×.

The biggest single-month cuts to Health Care came in 2024 (control 33–36%, agent 19–25%).

## Worked example: April 2024 (row R61)

**What the agent saw.** Row R61, with no date or sector names:
- the median sector's trailing volatility was 0.19 a year, which is normal;
- the most dispersed sector's forecasts were just under 2× the median's.

So its rule chose the **2% band and the tight 1.25× cap**: "median sector vol 0.19 (normal) →
band 2%; dispersion spread 2.0x, tight cap".

**What the cap means for sector B (Health Care).** Sector B was 16.1% of the tradable universe.
- The cap allowed it at most 1.25 × 16.1% × 200% = 40.4% of NAV in gross, which is 20.2% of a
  full 200% book.
- The control book, with no cap, held **35.6%** of its gross in Health Care.
- The agent book held **20.2%**, exactly at the cap. Industrials became its largest sector at
  21.7%.

**What happened that month.**
- The control lost 0.91% and the agent made 0.59% after costs.
- The agent traded slightly less (22% vs 25% one-way).
- Both stayed within every mandate limit: 300 names, gross ≤ 200% and short book above $1.3bn.

This was a good month for the agent. Across all 68 months the cap cost more than it saved.

## Files

- `RULE.md`: the rule and its addendum.
- `base_config.yaml`: the base book.
- `run_all.py`: one command for Steps 3–7.
- Agent: `agent_inputs.csv`, `agent_decide.py`, `agent_decisions.csv`, `decisions_meta.json`,
  `decision_log.md`.
- Results: `monthly_control.csv`, `monthly_agent.csv`, `summary.csv`, `agent_fallbacks.csv`
  (empty: no fallbacks), `decision_log_by_date.csv`.
- Reproduction: `reproduction_check.csv`, `reproduction_shape_matched.csv`,
  `match_config*.csv`, `diagnose_repro.py`, `match_config.py`, `match_scale.py`.
- Private keys, not read by the agent: `month_key.csv`, `sector_key.csv`.

# Sector-constraint agent v2 (Tony's constraint set): results

**Run:** 2026-10-29 12:36. One run of each arm, 2021-01 to 2026-08, under `RULE_v2.md` (written
12:35, before any v2 result). To reproduce, run `python run_v2.py`. The v1 results in
`../RESULTS.md` are unchanged.

**Verdict: the agent meets the success rule, but only just.** It cut sector concentration
clearly. Its net IR is 0.096 below control, inside the 0.10 tolerance. Neither arm breached the
mandate, was infeasible in any month or needed a fallback.

## Summary for a mentor

Under Tony's tighter constraints (dollar-neutral, beta-neutral, 3.5% position cap and no index
hedge), a rule-based agent that sets each month's sector limits from information available at
the time cut the Health Care share of gross from 25% to 21% in the median month.

It kept net IR within the tolerance we fixed beforehand: 0.69 against 0.79 for the control.

Both books stayed inside every mandate limit in every month, and both realised 12.1–12.4% vol,
inside the 12–14% cap. The IR margin is thin (0.096 against a 0.10 limit) and comes from a single
run, so we read it as "concentration control at a small, uncertain cost" rather than a free
improvement.

## Side by side (after the vol-target overlay and full costs)

| | Control (base + 2% sector band) | Agent |
|---|---:|---:|
| **Net IR** (vs cash + 4%) | **0.79** | **0.69** |
| Gross IR (before costs) | 1.15 | 1.07 |
| Volatility (annualised) | 12.1% | 12.4% |
| Realised vol vs the 12–14% cap | within | within |
| Max drawdown | −8.1% | −9.6% |
| Monthly beta to S&P 500 (s.e.) | −0.02 (0.10) | −0.07 (0.10) |
| Ex-ante beta β̂ᵀw, max \|·\| | 0.000 | 0.000 |
| Max sector net (% NAV) | 2.0% | 3.0% |
| Largest sector gross share, median / max | 27.0% / 37.1% | **22.1% / 26.9%** |
| Health Care gross share, median / max | 25.4% / 37.1% | **21.1% / 26.9%** |
| Monthly one-way turnover | 21.9% | 23.7% |
| Cost (% NAV a year: 65 bp traded + 152 bp borrow) | 4.48% | 4.81% |
| Mean overlay scale k | 0.70 | 0.74 |
| Infeasible months | 0 | 0 |
| Fallbacks used | 0 | 0 (`fallbacks_v2.csv` is empty) |
| Mandate breaches (month × rule) | **0** | **0** |

**Mandate margins in the worst month** (identical for both arms):

| Mandate | Worst month |
|---|---|
| Names held | 300 |
| Gross | ≤ 200% |
| Net | 0.0% (dollar neutral) |
| Single name | 3.5% |
| Smallest short-name market cap at formation | $503m |
| Sectors held | 10 |
| Sector net | 2.0% (control), 3.0% (agent) |

Neither arm's realised beta is distinguishable from zero.

## Success test (same rule as v1)

| Criterion | Result |
|---|---|
| Largest sector and Health Care share at least 3 pp lower in the median month | **Met.** Largest sector −4.9 pp, Health Care −4.3 pp. |
| Net IR ≥ control − 0.10 | **Met, narrowly.** 0.69 vs 0.79, a drop of 0.096. |
| Zero mandate breaches | **Met.** 0 in both arms. |
| **Overall** | **Pass** |

## v1 control vs v2 control: what Tony's constraints changed on their own

v1 control → v2 control:
- **Net IR:** 1.01 → 0.79.
- **Vol:** 13.6% → 12.1%.
- **Max drawdown:** −6.7% → −8.1%.
- **Health Care median share:** 26.9% → 25.4%.
- **Cost:** 4.39% → 4.48% of NAV a year.

The changes run together, so they cannot be separated: v2 is dollar-neutral, uses a 3.5% rather
than 5% position cap and drops the SPX hedge.

## Decision log mapped to dates

- **Source.** The v1 decisions were reused unchanged; their checksums were verified at run time.
- **Mapping.** Dates come from `../month_key.csv`.
- **Fallbacks.** Every month ran at the agent's own choice.
- **Full table:** `decision_log_by_date_v2.csv` (decision, reason and both arms' results by month).

| Months | Band | Cap | Mean Δ Health Care share (agent − control) | Mean Δ monthly net return |
|---|---|---|---:|---:|
| 5 | 1% | 1.25× | −8.2 pp | −0.34% |
| 10 | 1% | 1.5× | −5.0 pp | +1.03% |
| 26 | 2% | 1.25× | −5.4 pp | +0.11% |
| 13 | 2% | 1.5× | −6.3 pp | −1.32% |
| 10 | 3% | 1.25× | −3.2 pp | +0.07% |
| 4 | 3% | 1.5× | −7.4 pp | −0.08% |

| Year | Mean Δ Health Care share | Mean Δ monthly net return |
|---|---:|---:|
| 2021 | −1.0 pp | +0.20% |
| 2022 | −5.2 pp | +0.29% |
| 2023 | −5.6 pp | −0.15% |
| 2024 | −11.0 pp | −0.64% |
| 2025 | −6.7 pp | −0.14% |
| 2026 (Jan–Aug) | −2.5 pp | +0.01% |

The agent pays most in 2024, the year it cut Health Care hardest. The three largest cuts were:
- 2024-06: −18.0 pp, −1.19% return relative to control;
- 2025-01: −14.9 pp, −2.07%;
- 2024-07: −14.1 pp, +0.34%.

## Worked example: April 2024 (row R61)

**What the agent saw.** The agent saw only masked numbers. The median sector's trailing
volatility was 0.19 a year (normal), and no sector's forecasts were unusually spread out. So it
chose the **2% sector band and the tight 1.25× cap**.

**What the cap meant for Health Care.** Health Care was 16.1% of the tradable universe, so the cap
held it to at most 1.25 × 16.1% = **20.2% of the book's gross**.

**The control book**, under Tony's base rules with a fixed 2% band:
- Health Care was its largest sector, at **32.5%** of gross.
- It returned **+0.36%** after costs that month.

**The agent book:**
- Health Care held **20.2%** of gross, exactly at the cap, and Industrials became the largest
  sector at 21.7%.
- It returned **+1.58%**.
- It traded less (19.5% vs 22.4% one-way).

Both books were dollar-neutral and beta-neutral, held 300 names with no position above 3.5%,
and stayed inside every mandate limit. This was one of the agent's better months; 2024 as a whole
cost it 0.64% a month.

## Caveats

- **The control is a re-run of our optimizer** under Tony's constraints, not a submitted book.
  There is no reference holdings file for v2.
- **γ = 230 is reused from v1,** where it was matched to the original book's weights. It was not
  re-tuned for v2.
- **One run, no tuning.** The 0.096 IR gap sits close to the 0.10 limit, so a different γ,
  window or forecast could flip the verdict.
- **The overlay is reimplemented** from `VOL_TARGET_RULE.md`, with the hedge switched off
  (h = 0) as v2 requires.
- **Market-cap rule.** v2 checks each short name's market cap (≥ $500m at formation). v1
  checked the short book's dollar size, so the two short-side checks are not the same rule.

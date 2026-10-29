# Mandate check: screened optimizer at 75% gross

Verdict: retain as a research candidate, but do not certify the existing run as compliant. Fragility and concentration are not themselves numerical breaches. Rebalance-only enforcement leaves a demonstrable position-limit problem, and event-specific rules remain unavailable.

Source: McGill-FIAM Asset Management Hackathon 2026 — Final Challenge Instructions.pdf, Downloads copy, sections 3.1–3.3, 7–9. The revised presentation guide refers to additional sector-breadth, sector-cap and volatility constraints issued at the event; their numbers are not supplied in this instructions PDF.

| Requirement | Checked evidence | Status |
| --- | --- | --- |
| 200–500 positions | 300 at every monthly formation | Pass at checked formations |
| Gross <=200% of capital | 75% after rebalance; month-end maximum 88.81% | Pass at checked snapshots; daily path not checked |
| Net within +/-50% at all times | Rebalance -29.55% to +18.14%; month-end -32.17% to +18.40% | Pass at checked snapshots; daily path not checked |
| Single name <=5% of capital | Rebalance maximum 5%; month-end maximum 9.76%; 57 of 68 month-ends have at least one name over 5% | Breach under an ongoing holding limit; seek clarification if organizers intend formation-only |
| Shorts >=$500m at formation | Minimum $502.65m using prior month-end formation characteristics | Pass for this monthly formation convention; execution-date movements not checked |
| Monthly-to-daily rebalancing | Monthly | Allowed |
| $1bn initial capital, compounding | NAV model starts at $1bn and compounds | Implemented; capacity evidence still incomplete |
| January 2021–August 2026 reporting | 68 months | Pass for monthly coverage |
| Market neutrality | Estimated beta matched to zero at rebalance; realized monthly beta -0.059 | Monthly evidence only; daily beta and standard errors required; no numeric acceptance threshold stated |
| Additional sector and volatility constraints | Portfolio has up to 31.0% sector net exposure; event-specific limits not supplied | Cannot determine until supplementary rules are known |
| Cost and implementation reporting | Trading costs included; borrow, impact and capacity not fully modeled | Disclosure of omissions is permitted by section 8.3; cost/borrow sensitivity and required exhibits still need completion |
| Accurate returns and reporting | Missing returns, including a 5% short, marked at zero; daily statistics and Arcana exhibits incomplete | Resolve or substantiate assumptions before relying on final figures |
| Out-of-sample methodology | Forecasts walk-forward; allocation experiments inspected test-period results | Disclose allocation selection history; no untouched allocation test is claimed |

## Concrete breach example

August 2021: UPST entered the month at a -5.0% weight. The supplied monthly return is +89.73%; after the portfolio NAV move, its short notional is approximately -9.76% of NAV before the next rebalance. This uses the same holdings accounting as the engine. The evidence does not require daily data to demonstrate month-end drift, although daily data are needed to determine the first breach date and enforce a remedy.

## Minimum route to compliance

1. Obtain the exact supplementary sector-breadth, sector-cap and volatility rules and the intended timing of position-limit checks.
2. If the 5% cap is ongoing, enforce a deterministic intramonth risk overlay using point-in-time daily data, or use a smaller formation cap plus daily checks. A smaller cap alone is not a guarantee.
3. Recompute trades, costs, holdings, and performance with that overlay; do not keep the current return series after changing weights.
4. Complete daily neutrality evidence, recover missing outcomes, and supply the required cost sensitivity and reporting exhibits. Disclose unmodeled implementation risks rather than assuming they are automatically disqualifying.

Detailed snapshots: screened_075_mandate_drift.csv. This check covers available data and is not a claim of organizer approval.

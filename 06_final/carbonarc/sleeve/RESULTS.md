# News → foot-traffic sleeve: results of the one pre-registered run

Run on 2026-10-28 with `sleeve_run.py`, exactly as fixed in `PROTOCOL_SLEEVE.md`, which was
committed at 07cfc0f before this run. The rule was committed first but **not posted to the
group before the run**. The commit time is the only record that it came first. Nothing was
re-run or tuned. All figures are aggregates; the licensed foot-traffic panel stays outside
the repo.

## Step 3: confirmation

D(m) is mean 3-month year-over-year foot-traffic growth of the winners (AZO, ORLY, MNRO, GPC)
minus that of the losers (KMX, AN, LAD, SAH, PAG, CRMT). It uses live stock-months only, and
all 4 and 6 names are defined in every month shown.

| Data month | Winners' growth | Losers' growth | D(m) |
|---|---|---|---|
| 2021-09 | +6.6% | +28.9% | -22.3% |
| 2021-10 | +10.1% | +19.5% | -9.4% |
| 2021-11 | +14.7% | +16.2% | -1.5% |
| 2021-12 | +19.0% | +15.0% | **+4.0%** |
| 2022-01 | +19.7% | +15.6% | **+4.1%** |
| 2022-02 | +22.8% | +17.3% | +5.5% |
| 2022-03 | +17.4% | +21.5% | -4.1% |
| 2022-04 | +15.3% | +19.3% | -4.0% |
| 2022-05 | +9.4% | +1.6% | +7.8% |
| 2022-06 | +7.9% | -11.9% | +19.9% |
| 2022-07 | +6.8% | -20.4% | +27.1% |
| 2022-08 | +8.4% | -22.7% | +31.2% |
| 2022-09 | +7.3% | -17.0% | +24.3% |
| 2022-10 | +5.6% | -11.0% | +16.7% |
| 2022-11 | +1.4% | -10.8% | +12.1% |
| 2022-12 | +1.7% | -3.1% | +4.8% |

- **Confirmed at formation month 2022-03.** The two latest usable data months, 2021-12 and
  2022-01, both had D > 0. Under T+5 plus one month, those are the latest data usable on
  the first trading day of 2022-03.
- **The confirmation was thin.** It rested on two small spreads of about +4%. The next two
  data months turned negative, at about -4% each. The large, lasting spread, with dealer
  visits falling 10-23% year over year while parts visits kept growing, only appears from
  2022-05.
- **In hindsight the chain's foot-traffic prediction held from mid-2022.** The rule had no
  way to know that in 2022-03.

## Step 4: return test

The position opened at the close on 2022-03-01 and closed at the close on 2022-08-31. All
10 names have returns for the whole holding period.

| | Return over the hold |
|---|---|
| Winners, equal-dollar basket | +13.7% |
| Losers, equal-dollar basket | -2.7% |
| **Pair, equal dollars** | **+16.4%** |
| **Pair, beta-matched** (β winners 0.83, β losers 1.11) | **+15.7%** |
| S&P 500, for context | -8.2% |

**Placebo.** We drew 1,000 random 4-versus-6 splits of the 87 Consumer Discretionary
foot-traffic names live in 2022-03, with the same entry date and holding period.

| Placebo result | Equal-dollar pair | Beta-matched pair |
|---|---|---|
| Median random pair | -1.5% | -1.1% |
| Share of random pairs the real pair beat | 89.1% | 87.6% |

That is roughly a one-sided p of 0.11 to 0.12: **not significant at conventional levels.**

**Where the return came from, by name:**

| Side | Name | Return |
|---|---|---|
| Winner | GPC | +30% |
| Winner | AZO | +17% |
| Winner | ORLY | +6% |
| Winner | MNRO | +3% |
| Loser | LAD | -22% |
| Loser | KMX | -16% |
| Loser | CRMT | -15% |
| Loser | SAH | +3% |
| Loser | AN | +10% |
| Loser | PAG | +23% |

**Timing:** most of the pair's return came in the first month. The pair stood at +16.0% at
the end of 2022-03, fell to +5.0% at the end of 2022-05, and ended at +16.4%.

**Gross returns.** Trading and borrowing costs are not modelled.

## What it shows, and what it does not

- **The process worked end to end.** The news agent proposed a chain from masked pre-event
  releases. Foot traffic, lagged to what was publishable, confirmed it on the rule's own
  terms. The trade was held inside one sector and beta-matched. It made +16% while the
  S&P 500 fell 8%.
- **It is not evidence of an edge:**
  - It is one event whose outcome we already knew.
  - The agent is a model trained on 2022 news, and its picks match the chain the team had
    in mind beforehand.
  - The result sits at the 89th percentile of same-sector random pairs, not beyond the 95th.
  - The confirmation itself was marginal and reversed for two months.
  - The foot-traffic data is today's snapshot, not point-in-time.
- **Overlay (step 5):** not produced. Tony's score hook has not been confirmed ready.

# News → foot-traffic sleeve: protocol (written before any return is computed)

Owner: Bohan. Committed before the confirmation step and before any return for the chosen
names is looked at. The git commit time of this file is the evidence. Anything changed after
that commit is listed under "Amendments" at the end, with its reason, and is reported as
post-hoc.

The idea: an AI proposes a cause-and-effect chain from news that was public before the
event, foot-traffic data must confirm it, and we trade it only within one GICS sector, so it
cannot become a hidden sector bet.

## 1. The chain (done before this rule, recorded in this folder)

- **Agent input** is `chain_prompt.txt`. It contains two official US releases from
  December 2021, with every month, year and full date masked, plus the 99 foot-traffic names
  that were live stocks in our panel in 2021-12. Each name carries its ticker at the time,
  its company name and its GICS sector and industry. The input contains no foot-traffic
  values, no returns and no hint of an expected chain.
  - Document 1: BLS CPI release for November 2021, published 2021-12-10. Archived copy
    `web.archive.org/web/20220103203905id_/https://www.bls.gov/news.release/archives/cpi_12102021.htm`
    (sha256 a44e91b2…). BLS blocks scripted downloads, so we used the archive.
  - Document 2: FOMC statement of 2021-12-15, from
    `federalreserve.gov/newsevents/pressreleases/monetary20211215a.htm` (sha256 83b36c52…).
    The list of voters is dropped.
- **Agent:** a fresh Claude instance. It read only that file, was told to use no other tool,
  and was asked to reason as of the release day. Its answer is saved verbatim in
  `chain_answer.md`.
- **Its winners (W) and losers (L) are used exactly as given.** If a pick is not in the list,
  or not in the stated sector, it is dropped and the drop is recorded. Nobody edits the
  picks.
- **The picks, all in Consumer Discretionary and none dropped:**
  - W = AZO, ORLY, MNRO, GPC.
  - L = KMX, AN, LAD, SAH, PAG, CRMT.
  - Thin data does not change the picks; the rule handles it. Card 5 of `dd_cards.md`
    flags SAH, LAD and CRMT as thin in card spend, but this sleeve uses foot traffic. Any
    name-month without a live, complete 6-month window is simply undefined under section 3.

## 2. Data and mapping

- **Data:** PassBy foot traffic (Carbon Arc insight 45862, CA0060), monthly US visits, as
  pulled on 2026-10-28.
- **Mapping:** ticker to permno through `dd_coverage.py`'s date-bounded map. A (name, month)
  is used only if its `map_status` starts with `matched`, meaning a live stock in our panel
  that month.
- **Caveat:** the data is a current snapshot, not point-in-time. Values may have been
  restated since 2022; see `dd_cards.md`, card 6, rule 2.

## 3. Signal and timing (fixed)

- **Foot-traffic growth.** For name i and data month m:
  g_i(m) = (V(m-2) + V(m-1) + V(m)) / (V(m-14) + V(m-13) + V(m-12)) - 1.
  This is 3-month growth year over year, which removes seasonality. g_i(m) is defined only if
  all six months have values and the stock is live in month m.
- **Group spread.** D(m) = mean of g_i(m) over W minus mean of g_i(m) over L, as equal-weight
  means over the names defined that month. D(m) is undefined if either side has fewer than
  2 names that month.
- **Lag.** The documented publication lag is T+5, and we add one extra month on top of it.
  So data month m is first used at the formation on the first trading day of month m+2.
- **Confirmation.** Formation months F run from 2022-01 to 2022-12. The chain is confirmed at
  the first F where D(F-2) > 0 and D(F-3) > 0, that is, the two latest usable data months
  both show winners ahead of losers. If no F in 2022 qualifies, the chain is unconfirmed:
  there is no trade, and that result is reported.
- **Not used for confirmation:** no return data and no foot-traffic level. The spread
  threshold is zero and is not tuned.

## 4. Return test (one run, fixed horizon)

- **Entry** at the close of the first trading day of F, the confirmation month. **Holding
  period:** 6 calendar months, F to F+5, exiting at the close of the last trading day of F+5.
- **Data:** daily total returns from our daily file. A name that delists during the hold
  keeps its delisting return, and its proceeds earn zero until the exit.
- **Equal-dollar pair:** buy-and-hold, equal dollars in each W name long and each L name
  short. The pair return is R_W - R_L, where each leg is the return on its equal-dollar
  basket.
- **Beta-matched pair:** long 1 dollar of W, short β_W / β_L dollars of L. The β are the leg
  betas to the S&P 500 (`01_data/raw/external/SP500_fred.csv`), estimated from 252 trading
  days of daily returns ending the day before entry.
- **Placebo,** reported with the result and never used to pick anything:
  - Draw 1,000 random W' and L' sets of the same sizes from the agent's sector names that
    were live and had foot traffic at F, with a fixed seed of 2026.
  - Use the same entry and horizon for every draw.
  - Report where the real pair's return falls in that distribution, for both versions.
- **Also reported:** the monthly path of the pair, both legs separately, and D(m) through 2022.
- **Returns are gross.** Trading and borrowing costs are not modelled for this sleeve, and
  the result says so.
- **2019-2020 check:** none. The chain is specific to one event, and the design window has
  no comparable inflation-and-rates event. The placebo is the only control.

## 5. Overlay (only if Tony's score hook is ready)

- **File:** `score_overlay.csv` with columns permno, target_month, score_adj.
- **Values:** +1 for each W name and -1 for each L name, in target months F to F+5, but only
  for live stock-months. The file is produced only if the chain is confirmed.
- **Engine run:** the engine runs once with the overlay and once without, unchanged
  otherwise. Both results are reported.

## 6. Limits, stated up front

- **It is one event.** We already know how 2022 went, and the language model was trained on
  news from 2022. That makes this a demonstration of the process, not evidence of an edge.
- **The data is a current snapshot.** The vendor may have revised 2022 foot traffic since
  then.
- **Small sample.** The trade is about 3 to 8 names a side, inside one sector. It is a sleeve,
  not a strategy, and the headline book is unchanged.

## Amendments

None yet.

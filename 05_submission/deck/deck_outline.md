# Deck outline: 8 pages plus appendix

Page structure is fixed by the brief (pages 20-22 of the PDF). This maps each
page to the exhibits the pipeline already produces, so the deck is filled from
`05_submission/deck_pack.csv` and `05_submission/figures/` and never from a
number remembered from a terminal. Every table and chart is labelled
"01/2021 to 08/2026, gross of trading costs" unless it is the cost table.

Numbers quoted here are from the per-fold-blend run (`35e3e6f`); regenerate
`deck_pack.csv` and re-check each one before the slide is final.

**Open decision that changes every number below:** variant S (sector count
cap, `protocol_variants.md`) is recommended for adoption on neutrality grounds
and would take the IR from 0.88 to 1.33. If adopted before the freeze, set
`SECTOR_COUNT_CAP = 5` in stage 4, rerun `python MAIN.py` and the three
exhibit scripts, and refill every slide from the new `deck_pack.csv`.

## Page 1: Executive summary

One paragraph, one table, one chart.

- Strategy in one sentence: a monthly U.S. equity market-neutral book, 100
  long and 100 short, chosen by a gradient-boosted-tree forecast of next-month
  excess return built on the 147 supplied characteristics, neutralised on
  sector, size and beta, sized by inverse volatility, with the legs matched on
  realised beta.
- Headline table (deck_pack rows): information ratio vs cash+4% (`risk`),
  Sharpe, alpha vs S&P 500 with t, beta with se, CAGR, max drawdown, average
  gross and net, names held. Put the hurdle and the S&P 500 in adjacent
  columns where the statistic exists for them (cumulative return, calendar
  years).
- Chart: `figures/cumulative.png`.
- One honest line: the edge is concentrated in 2021-2022; 2023-2026 clears the
  hurdle at a lower information ratio. Say it here so page 8 is not a surprise.

## Page 2: Investment strategy

- Long and short legs: top and bottom 100 of a neutralised score; a held name
  survives while inside the top or bottom 250 (turnover buffer); forecast
  smoothed over three months.
- Neutrality enforced: dollar neutrality as the centre of the band, then
  beta neutrality by matching the legs on beta-weighted exposure, using each
  leg's own trailing realised beta (past months only). Net exposure is the
  price of that: state the range (deck_pack `exposure`).
- Signals: the 147 characteristics, ranked within month to [-1, 1], missing
  values kept as missing for the trees. Name the top characteristics by split
  gain from `05_submission/feature_importance.csv` (chart:
  `figures/feature_importance.png`), produced by
  `04_backtest_scoring/12_feature_importance.py`.
- Table: top 10 long and top 10 short by average weight,
  `05_submission/top_holdings.csv`, every row as "TICKER, Company Name".
- Chart: `figures/cumulative.png` again is allowed by the brief; use the
  rolling-beta chart here instead if page 1 already carried cumulative.

## Page 3: Data and methodology

- Data: 529,082 stock-months, 147 characteristics; 373,139 8-K filings used
  as described in the appendix; TB3MS and S&P 500 from FRED, snapshot
  committed so scores are comparable across machines.
- Alignment: month t characteristics predict month t+1; every split keyed on
  the target month; the checker fails a split keyed on `eom`.
- Preprocessing: within-month rank to [-1, 1]; median fill for the linear
  models, blanks preserved for the trees; scaler fitted on training months
  only.
- Training: expanding window, rolling two-year validation, one-year test,
  refit annually 2021 to 2026, exactly the brief's schedule. Blend of tree and
  linear forecasts chosen inside each fold on that fold's validation block
  (per-fold choices from `blend.json`: gbm in four years, ridge+gbm in 2022 and
  2023).
- Why trees: missingness is informative (structural for 48% of blanks), and a
  tree learns the direction of a blank instead of being handed a median.
- OOS R-squared table for every model (deck_pack `model` rows), with the
  brief's note that 1-2% is typical and any positive value is predictability.
- Agentic component: none in the traded pipeline. State plainly that coding
  assistants were used to write and review code, that no language model saw
  filing text to produce a traded signal, and how look-ahead on the model side
  was therefore ruled out.

## Pages 4 to 7: Performance pack

Headline statistics table on page 4, three or four charts across pages 5 to 7,
the rest to the appendix. Order the deck_pack sections as the brief lists them.

- Page 4: returns table (`returns` rows: average monthly, annualised
  arithmetic and geometric, cumulative, best and worst month with dates, hit
  rate, long and short leg separately) and the calendar-year table (`calendar`
  rows: strategy / hurdle / S&P 500).
- Page 5: risk-adjusted table (`risk` rows: IR, Sharpe, alpha with t, beta with
  se, correlation, drawdown monthly and daily) plus `figures/underwater.png`.
- Page 6: `figures/rolling_beta.png` and `figures/rolling_ir.png`. This is the
  page the judges said they read first. Write the caption before the chart:
  full-period beta about -0.16 with se 0.12; the 12-month window leaves the
  +/-0.3 band in mid-2022 and again in 2026, ending near -0.6. Explain what
  the book was doing in those months (short leg gaining in the 2022 unwind;
  2026 to be diagnosed before the deck is final) and what the beta control did
  and did not catch.
- Page 7: exposure and implementation table (`exposure` rows: holdings by
  leg, gross and net with ranges, average and max position, top-10 share,
  turnover with range), short-book table (`short_book` rows: median market
  cap, median dollar volume, median price, share in small caps), and the cost
  table (`costs` rows). Add `figures/histogram.png` if it fits.

Appendix candidates from this pack: `figures/contributors.png` with
`contributors.csv`, daily-marked statistics with their coverage caveat
(`daily_coverage.csv`), delisting-mark sensitivity (`delisting` rows).

## Page 8: Discussion

- Did it perform as trained? The signal had no skill in the 2019-2020
  validation window (rank IC +0.002) and clear skill in 2021-2026 (about
  +0.13). Say why we still trusted it: the construction changes were not
  fitted to returns and the largest gains came from removing untradeable
  names and fixing beta.
- The two legs take turns: shorts paid in the 2021-2022 unwind, longs pay in
  2023-2026. One signal, different legs in different regimes. Quote the
  leg-by-period numbers from the short-leg diagnosis.
- Fundamental signals behind the performance: the importance table.
- Most profitable and least profitable positions: `contributors.csv`, each as
  "TICKER, Company Name", with one line on why (the short book in 2021-2022
  was speculative growth names into a rate shock; name three).
- Macro events: the 2021 retail squeeze (the reason for the tradability
  screen), the 2022 drawdown, the 2023-2025 concentration rally.
- Potential improvements, in the order we would do them: sector cap on the
  count imbalance (the tilt exists in the validation window too, so it is
  structural), a borrowability screen decided on tradability grounds,
  post-earnings drift from item 2.02, tighter beta control in 2026,
  alternative data in the finals.
- Multiple testing: the count from `research_log.md`, stated as a number.

## Appendix (up to 10 pages)

1. Research log (`research_log.md`): every test-period look, what changed.
2. Model comparison (`experiments/model_comparison/REPORT.md`): eight variants
   under one protocol, Ridge best post hoc, annual blend the real-time choice.
3. Missing-value ablation: missing-preserved vs median-filled trees, from the
   same report; the missingness breakdown (48 / 31 / 21).
4. Short-leg diagnosis and hedge-basket comparison (Oliver's tables; scripts
   to be committed).
5. Sector exposure and the sector-cap protocol, whichever way the run goes.
6. 8-K work (`appendix_8k.md`).
7. Daily-marked risk with the coverage table.
8. Delisting-mark sensitivity and the list of positions with no realised
   return.
9. Compliance: the checker's report for all 68 months; label provenance for
   the 549 holdings named from an earlier month.
10. Reproduction: `python MAIN.py`, pinned versions, data placement.

## Submission package checklist (brief page 22)

1. Deck plus appendix as one PDF, from PowerPoint.
2. `holdings.csv` with Date, PERMNO, TICKER, COMPANY NAME, WEIGHT for every
   month 2021-01 to 2026-08; `portfolio_returns.csv` (monthly; daily series
   optional, with its caveat).
3. `MAIN.py`. Decide as a team whether to submit the repository with `MAIN.py`
   at its root or to bundle the stage scripts into one file; the brief says
   "one file called MAIN.py".
4. No licence needed.
5. One CV per team member.

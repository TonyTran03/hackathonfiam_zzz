# Carbon Arc MCP: what separated our worst shorts from our best ones (2023-2026)

Exploratory, after the fact. An agent (Claude, connected to the Carbon Arc MCP) asked the
same question about each of our 10 worst and 10 best short positions since 2023: what moved
the stock, which catalysts were scheduled, how analysts were leaning, whether the company
issued shares, and what was already known in the first months of the short. Carbon Arc is
used only to understand the book after the fact; nothing here feeds the model.

This file is our own summary. It contains no text copied from Carbon Arc or from the news
articles, filings and earnings calls its answers were built on.

## Method

- Book: `test_M` sector-neutral (Amendment 3), end-of-day weights. A short spell is a run of
  consecutive formations on the short side; its P&L is weight x next-day return, before any
  market hedge.
- Worst 10 spells lost 1,403 bp (39% of all short-side loss since 2023, -3,603 bp). Best 10
  made 1,111 bp.
- One `text_to_insight` question per name against Carbon Arc's document archive (news,
  10-K/10-Q filings, earnings-call transcripts), asking for dated bullet points.
- Cost: about 4,000 of the 20,000 daily MCP units (about 200 per question). The $3.80 dollar
  balance was not touched.
- Limits: only 5 of the 10 losers are in Carbon Arc's ticker list (RVMD, ASTS, SOFI, WBD, APO);
  the archive covered the others by company name. Carbon Arc's structured Benzinga event tables
  (analyst ratings, earnings) failed through the MCP with a server-side error, so we have no
  counts of upgrades vs downgrades, only what the documents describe. One best-short name
  (FLNA) returned no usable answer. Real-economy data (card spend) exists only for SoFi and its
  panel is too thin to use.

## Worst 10 shorts (stock went up)

| Ticker | Short window | Loss | Main driver (our summary) | At the start of the short |
|---|---|---|---|---|
| OKLO | 2025-01 to 2026-02 | -220 bp | Nuclear policy support, data-centre power deals, rising analyst targets | Deals and target raises already under way |
| RVMD | 2024-03 to 2026-05 | -218 bp | Positive trial data, FDA approval, takeover interest | Late-stage pipeline known, readouts scheduled |
| PRAX | 2024-11 to 2026-08 | -179 bp | Trial wins, FDA designations, steep target raises | Stock already up sharply, trials scheduled |
| ASTS | 2024-08 to 2026-08 | -147 bp | Carrier contracts, satellite launches, regulatory approvals, defence contract | Carrier prepayments and launch date public |
| APGE | 2024-06 to 2026-08 | -145 bp | Strong Phase 2 data, target raises, later acquired | Readout scheduled, well funded |
| CRNX | 2024-02 to 2026-08 | -117 bp | Two positive Phase 3 trials, FDA approval, upgrades, later acquired | Phase 3 wins just before; upgrades followed |
| SOFI | 2023-03 to 2025-07 | -114 bp | Earnings beats and guidance raises most quarters, member growth | Beat and guidance raise at the start |
| WBD | 2022-12 to 2023-02 | -93 bp | Upgrades on cash flow and debt paydown, an insider purchase | Upgrades and insider buying |
| MDGL | 2023-11 to 2025-06 | -85 bp | FDA approval, launch sales above expectations, upgrades | Approval decision scheduled, targets rising |
| APO | 2024-02 to 2025-01 | -85 bp | Earnings beats, fee growth, an upgrade, S&P 500 inclusion | Growth story known; inclusion came later |

## Best 10 shorts (stock went down), the control group

| Ticker | Short window | Gain | Main driver (our summary) | At the start of the short |
|---|---|---|---|---|
| SOC | 2025-02 to 2025-12 | +138 bp | Restart delayed by legal and regulatory fights, heavy dilution, targets cut | Restart catalyst scheduled; new Buy initiations |
| DISH | 2023-02 to 2023-11 | +138 bp | Subscriber losses, heavy debt, earnings miss, CEO exit | Mixed analysts; losses and debt known |
| APLS | 2024-03 to 2025-10 | +136 bp | Weak sales of its main drug; FDA approval of a second drug did not offset it | Stock already down; several upgrades in the window |
| AMC | 2023-09 to 2024-02 | +133 bp | Large share issuance to reduce debt | Dilution and debt known |
| EVH | 2024-09 to 2025-12 | +116 bp | Medical-cost spike, guidance cut, margin squeeze | Cost problem disclosed early |
| FISV | 2025-07 to 2025-11 | +109 bp | Large guidance cut, management changes, downgrades | Consensus positive, high targets |
| DJT | 2024-05 to 2026-08 | +105 bp | Tiny revenue, large losses, insider sales, dilution, political swings | No analyst coverage; lock-up expiry ahead |
| FLNA | 2024-08 to 2024-12 | +85 bp | No usable answer from Carbon Arc | - |
| RXRX | 2024-02 to 2025-06 | +76 bp | Trial disappointments, programmes cut, merger integration, targets cut | Many readouts scheduled; mixed analysts |
| LCID | 2023-05 to 2023-11 | +76 bp | Weak deliveries, production guidance cut, share issuance | Funding needs known; mixed analysts |

## What the control group shows

| Feature at the start of the short | Worst 10 | Best 10 | Separates them? |
|---|---|---|---|
| Scheduled catalyst (trial, FDA, contract, permit, election) | 7 | about 5 (SOC, APLS, RXRX, LCID, DJT) | Weakly |
| Analysts leaning positive (upgrades, target raises) | at least 8 | about 3-4 (SOC, FISV, APLS, partly DISH) | Yes, but not cleanly |
| Large share issuance | 4 (OKLO, CRNX, RVMD, ASTS) | 4 (AMC, LCID, SOC, DJT) | No |
| News flow on the business improving vs deteriorating | improving in most | deteriorating in most (DISH, EVH, AMC, LCID, FISV, RXRX) | Yes |
| Heavily covered by analysts | all 10 | 6 of 9 answered (no coverage found for AMC, EVH, DJT) | Somewhat |

1. **Catalysts alone don't explain the losers.** The best shorts had scheduled catalysts
   too; for them the catalyst failed or was delayed.
2. **Share issuance is not a short signal here.** Both groups issued heavily.
3. **The direction of fundamental news is the clearest difference.** Losers had beats,
   guidance raises, trial wins and approvals; winners had misses, guidance cuts, cost spikes
   and failed programmes. Analyst direction follows the same split, which is what the
   analyst-upgrade idea was trying to capture.
4. **This fits the Arcana finding.** Our short book is mainly short high-volatility,
   low-quality names. That bet works when those companies' news is bad (2021-22, and the best
   10 here) and fails when it turns good (the worst 10).

With 10 names per group this is anecdotal evidence, not a test.

## What we did and did not act on

- **Biotech exposure:** Amendment 5's 2% industry cap already cuts the sector-neutral book's
  net biotech short (GICS 352010) from about -10% of NAV on average (worst -21%) to -1.2%
  (worst -2.0%). The A5 industry-capped book is therefore a partial test of "don't short
  biotech"; its net IR fell from 0.27 to 0.00, so no separate biotech rule was added.
- **Next step, not done:** a rule against shorting names with net analyst upgrades or
  positive earnings revisions. It needs the Benzinga analyst-ratings data (a purchase, about
  $5 at Carbon Arc's minimum order) and point-in-time dating of each rating, and it would have
  to be pre-registered and checked on the 2019-2020 design window before any test-window run.

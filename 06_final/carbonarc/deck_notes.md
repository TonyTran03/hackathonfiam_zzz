# Speaker notes: Bohan's two slides

## Slide A: data due-diligence agent (`dd_slide.png`)

- Before trusting any new data, we ran an agent connected to Carbon Arc. It applies the
  same six checks to every dataset: publication lag, backward revisions, ticker-to-PERMNO
  mapping, a has-data flag, coverage, and real start date.
- **Our strongest finding is the 8-K check.** Our supplied 8-K file is missing almost
  every company that later left the market. All 27 exited firms we sampled did file 8-Ks
  on SEC EDGAR right up to their exit, but Carbon Arc's name search returned only 2 of
  them. So the survivorship gap is in the data we were given, not in the filings.
- **On spending data, the agent caught a false signal.** Big 5's card spend falls 96% in
  2024 while its foot traffic rises 11%. Etsy's card spend grows 3,500 times since 2019.
  Those are changes in the vendor's panel, not in the businesses. So card spend stays
  descriptive only, and foot traffic is cleared for the sleeve on rules 3 to 6.
- We also built our own date-bounded ticker map. Carbon Arc applies today's ticker to the
  whole history, and about 10% of rows belong to companies that were not listed that month.

## Slide B: news → foot-traffic agent (`sleeve/sleeve_slide.png`)

- **The idea:** the AI proposes a cause-and-effect chain, real spending data has to
  confirm it, and we trade it only within one sector.
- **The chain.** The agent saw only the December 2021 CPI release and Fed statement, with
  the dates masked. Its chain: car prices spike, people keep old cars, and repairs rise.
  It chose auto-parts chains over car dealers, all in Consumer Discretionary.
- **The rule came first.** We committed the rule before looking at any number: a lag of
  T+5 plus one month, and two consecutive months of parts beating dealers. Foot traffic
  confirmed it from March 2022.
- **The result.** The pair made 16% in six months while the S&P fell 8%. That beats 89%
  of random pairs drawn from the same sector.
- **Be explicit that this is a demonstration, not proof.** It is one event whose outcome
  we already know, the model was trained on 2022 news, and the result is not significant
  at 5%. What we are showing is the process.

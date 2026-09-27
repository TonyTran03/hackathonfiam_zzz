# Appendix: the 50 positions with no realised return, and the delisting mark

The panel has no `ret_exc_lead1m` for a stock-month when the security stops
trading inside the holding month. The scorer must put some number there. The
usual academic convention for delisted stocks is -30% (Shumway 1997), and the
team asked whether that should be the base case. We looked at the actual
positions before deciding.

## What the 50 positions are

Every one of the 50 held positions with no realised return is the stock's
LAST month in the panel; none reappears later, so these are exits, not data
gaps. They are 35 longs and 15 shorts, spread evenly across the six years
(8, 9, 7, 7, 12, 7). Together they carry 87% of capital summed over all 68
months, so about 1.3% of the book per month on average, at most 5.4% in any
single month.

The list (`missing_return_positions.csv`) reads as an M&A roster, not a
bankruptcy roster: Dunkin Brands, Fitbit, Varian Medical, Cerner, Abiomed,
Sanderson Farms, KnowBe4, Chase Corp, Rover, Inhibrx, Deciphera, Silk Road
Medical, SpringWorks, Masimo on the long side; Pandion, Santander Consumer,
Welbilt, Akouos, Prometheus Biosciences, Cerevel, Hawaiian Holdings, Aspen
Technology, Mr. Cooper, Metsera on the short side. Every exit happened at a
price above $5 and a market cap above $490 million.

## What the returns before exit say

| | last month before exit | 3 months before | 6 months before | share with 6-month return above +20% | share below -20% |
|---|---:|---:|---:|---:|---:|
| 35 longs, median | +0.5% | +2.3% | +45.4% | 74% | 0% |
| 15 shorts, median | +0.5% | +44.8% | +27.9% | 60% | 0% |
| all screened stocks in the period, median | | | about +2.7% | | |

The stocks jumped 28% to 45% in the half-year before they left the panel and
then went flat. That is the signature of an acquisition: the premium is paid
when the deal is announced, the stock then trades at the offer price until it
closes, and the closing month's return is close to zero. Where we were long,
the premium is already in our P&L in the earlier months; where we were short,
the loss is already there too. Not one of the 50 shows the drawdown that
would precede a distress delisting.

## Decision, and what is shown either way

A -30% mark is the convention for stocks that stop trading because they
failed. None of these did. Applying it to acquisition completions would
subtract 30% from 35 longs that were in fact bought out, and hand a 30% gain
to 15 shorts that were in fact squeezed. The honest base case for this book
is therefore the 0% mark the scorer already uses: the completion month of a
deal whose price is already fixed.

Because the choice moves the headline, the sensitivity is reported in
`deck_pack.csv` and belongs in the appendix table:

| missing-return mark | information ratio | CAGR |
|---|---:|---:|
| 0% (base case, completion month of a fixed-price deal) | 0.88 | 19.65% |
| -30% (Shumway convention for failed delistings) | 0.72 | 17.11% |
| -50% | 0.60 | 15.43% |
| -100% | 0.32 | 11.28% |
| adverse stress: longs -100%, shorts +100% | -0.25 | 2.52% |

Gross of trading costs, 01/2021 to 08/2026. The mark is one line in
`common/config.py` (`TEAM["delisting_return"]`) if the team decides otherwise.

Reproduce: `python 04_backtest_scoring/11_deck_pack.py` (delisting section);
the position list and pre-exit returns were computed from
`01_data/processed/holdings.parquet` and `model_table.parquet`.

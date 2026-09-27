# Appendix: what we did with the 8-K filings, and why they did not change the book

The brief says a candid account of something that did not work is worth more
than a polished account of something that supposedly did. This is that account.
Every number below comes from the supplied filing file and the team's committed
scripts; commands to reproduce each one are at the end.

## 1. What was tried, in three layers

**Layer 1: item-code signals, no text model.** `01_data/filing_features.py`
collapses the 373,139 filings to one row per stock-month, keyed so that only
filings dated inside month t can inform the month t+1 forecast. Four signal
families were derived from metadata alone: disclosure delay (filing date minus
the reported event date, against the four-business-day deadline), filing burst
(this month's count against the stock's own trailing twelve months), and item
flags for distress (4.01 auditor change, 4.02 non-reliance), officer change
(5.02) and earnings (2.02).

Association with next-month excess return, **training window only** (target
months to 2018-12), measured against the correct control group of *other
filers* rather than all stock-months:

| Signal | n (stock-months) | vs other filers, per month | t |
|---|---:|---:|---:|
| Distress item 4.01 or 4.02 | 499 | -1.39% | -2.0 |
| Officer change 5.02 | 16,378 | -0.18% | -1.4 |
| Filed late, more than 4 days | 10,938 | +0.07% | +0.4 |
| Filing burst above 2x trailing | 2,750 | +0.25% | +0.9 |

The control group decided the answer. "This company filed anything at all" is
worth about +0.37% a month on its own and is largely a size effect; against all
stock-months every filing-conditional signal inherits that premium and looks
alive. Against other filers only the distress flag survives, and at roughly 30
firms a month it can only be a veto, not something to sort a 200-name book on.
Five comparisons were made and are logged in the script's output.

**Layer 2: officer-change triage.** The flat 5.02 result is what a few abrupt
departures diluted by mostly routine appointments would look like, so
`01_data/officer_triage.py` splits them with rules read off the documents (no
language model). The boilerplate trap had to be handled first: the item's own
heading contains every useful keyword, so "appoint" appears in 99.2% of the
filings raw and 54.5% once the heading is stripped. Training window, monthly
regressions with the usual controls:

| 5.02 filings | n | per month | t |
|---|---:|---:|---:|
| all | 16,378 | +0.05% | +0.5 |
| classified abrupt | 1,632 | -0.64% | -1.9 |
| classified routine | 14,746 | +0.12% | +1.2 |

The direction was predicted before the test and the split has the shape a
diluted signal would have. A t of -1.9 does not clear the bar this project set
itself given how many tests it has run, so it is reported, not traded.

**Layer 3: inside the model.** The nine filing columns were joined onto the
tree model's table (LEFT join, non-filers left blank rather than zero, because
"filed nothing" and "filed and nothing was flagged" are different states). The
pre-declared decision rule was validation rank correlation:

| | Validation rank correlation |
|---|---:|
| 147 characteristics | +0.1087 |
| 147 characteristics + 9 filing columns | +0.1082 |

No gain. Feature importance says the same from another angle: of 156 inputs the
three event flags rank 152nd, 155th and 156th, and all nine filing columns
together take 1.75% of the model's split gain against the 5.77% an average
feature would get. The traded model therefore runs without them; the flag
`INCLUDE_FILING_FEATURES` in `01_data/02_make_features.py` reproduces the
comparison.

## 2. Why no method could have found a portfolio-level effect here

Coverage arithmetic, computed on the filing file for the 68 feature months that
feed the test period (2020-12 to 2026-07):

| | per month |
|---|---:|
| Companies filing at least one 8-K | 2,029 (range 1,390 to 2,991) |
| Screened, investable universe (price >= $5, not nano or micro cap) | 1,981 |
| Share of investable stock-months with any filing that month | 56% |
| Companies filing item 4.02 (non-reliance) | 8.1 |
| Companies filing item 4.01 (auditor change) | 21.4 |
| Companies filing item 5.02 (officer or director change) | 544 |
| Companies filing item 2.02 (results of operations) | 979 |

The two strongest distress items together touch about 30 companies a month
across the whole market. A 100-name short book drawn from a 2,000-name
universe would hold, in expectation, well under one of them in any given month.
The distress veto is real but it cannot move a monthly portfolio statistic;
this is a coverage limit, not a modelling failure, and it would be the same for
any team using these items.

## 3. What was deliberately not done, and why

- **Frontier-model sentiment on the filing text.** A model trained on data
  through 2026 already knows what happened to these companies in 2021-2026.
  Asking it for a view on a 2021 filing is recall, not forecasting, and the
  brief says teams that cannot rule that out will be treated as having used
  it. The rule-based triage in layer 2 has no such exposure.
- **Embedding the full text into the tree model.** Half the investable
  stock-months have no filing, so any dense text feature would have to invent
  a value for non-filers, and the item-level results above gave no reason to
  expect the text to carry what the item codes did not.

## 4. Where a second attempt would start

Item 2.02 is the only item with enough coverage to sort a book on (about 979
companies a month). Post-earnings-announcement drift, conditioned on the size
of the surprise, is the established use of it. It was not attempted before the
model freeze and is listed under potential improvements rather than claimed.

## 5. Reproduce

```
python 01_data/filing_features.py --explore     # layer 1 table and the five training-window comparisons
python 01_data/officer_triage.py                 # layer 2 split and the retest
python 01_data/officer_triage.py --sample        # print filings on each side for eye-checking
# layer 3: set INCLUDE_FILING_FEATURES = True in 01_data/02_make_features.py, rerun stages 2-3
```

Files: `01_data/filing_features.py`, `01_data/officer_triage.py`,
`01_data/02_make_features.py` (the flag and both validation numbers are
recorded next to it), commits `fef0c10`, `99a798b`, `fb63fdb`.

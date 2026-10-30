# Data due-diligence self-test: rule written before any result

**Written:** 2026-10-29 11:14 (UTC−4). Nothing in either dataset had been computed when this was
written. Only the organisers' `readme.md` (schema and documented counts) and file checksums had
been read. Nothing below changes after seeing results.

**Honesty note.** The same agent writes the expected answers and runs the checks, so this is not a
blind test. The guard is that every check, threshold and "caught" criterion is fixed here first.

## The six rules (as used for Carbon Arc, `dd_cards.md`, 2026-10-28 16:48 version)

| # | Rule | Source of the check |
|---|---|---|
| 1 | Lag declared and dated per record | dd_cards rule 1; Carbon Arc screen, merge rule 1 |
| 2 | No silent revisions (vintage) | dd_cards rule 2; merge rule 2 |
| 3 | CIK or date-bounded ticker to PERMNO | dd_cards rule 3; merge rule 3 |
| 4 | "Not covered" distinguishable from "nothing happened" (has-data flag) | dd_cards rule 4; merge rule 4 |
| 5 | Coverage within 50% of its 2024 level back to 2021 | dd_cards rule 5; merge rule 5 |
| 6 | Real history starting by 2019 | dd_cards rule 6; merge rule 6 |

**Verdicts (dd_cards definitions, unchanged).** PASS: checked on records across the asset.
FAIL: the evidence shows the rule cannot be met by any route. UNVERIFIED: only documentation speaks
to it, or record checks cover too few firms to generalise. NOT USED: rule 4 only, when no signal
reads the data. Both datasets feed our model, so NOT USED is not expected to apply.

## The two datasets

| File | Location read (read-only) | SHA-256 (matches readme) |
|---|---|---|
| `chars_final_with_names.parquet` | `C:\Users\b0079\Desktop\` | `797c01eb…615215ca` |
| `8k_20150101_20260831_identified.parquet` | Recycle Bin, `$RKLGOC1\MCGILL FIAM ASSET MANAGEMENT HACKATHON FINALS OCTOBER 2026\` | `f333cd02…58ab0cd07` |

## Groups used throughout

- **Listed:** the permno has a panel row at `eom` = 2026-08-31.
- **Left early:** the permno's last panel `eom` is before 2025-01-01.
- **Left 2025–26:** everything else. Reported, but not part of the known-answer comparison.

## How each rule is checked

**Rule 1, lag.**
- 8-K: is there a per-record availability timestamp? Count `sec_accepted_at_utc` non-null and
  the `filing_time_precision` values. Count filings with `filing_date` < `content_report_date`.
- Panel: is there a per-record publication date for the characteristics, beyond `eom`/`date`?
- Panel timing consistency (catches look-ahead): for each month, take the share of rows whose
  `ret_1_0` matches the same row's `ret`, and whose `market_equity` matches `me`. A match is
  |difference| < 1e-4, relative for `market_equity`. A month is flagged if either share is more
  than 50 percentage points below the median month's share.
- Verdict: PASS only if every record carries an availability timestamp. Otherwise UNVERIFIED,
  which is the dd_cards precedent for CA0032 (filing date but no acceptance time).

**Rule 2, vintage.**
- Look for any as-of/vintage column. Check uniqueness of the documented keys, and count
  amendments.
- One snapshot cannot show revisions, so without a vintage column the verdict is UNVERIFIED.

**Rule 3, ticker to PERMNO.**
- Panel: is `(permno, eom)` unique? Does each `(ticker, eom)` map to at most one permno? Count
  permnos whose `gvkey`/`iid` changes, and permnos that switch gvkey and then switch back.
- 8-K: for each filing, compare its `ticker` with the panel ticker for that permno and month.
  Count filings whose ticker belongs to a different permno in the panel that month.
- Verdict: PASS if the keys are unique, dated tickers map 1:1 each month, and filing/panel ticker
  conflicts are under 1% of matched filings. Otherwise UNVERIFIED, with the counts.

**Rule 4, has-data flag.**
- 8-K: per firm, does it have at least one 8-K in the 12 months ending at its last panel month
  (2026-08 for listed firms)? Compare by group and by `size_grp` at the last month.
- Panel: per row, the share of the 147 characteristics that are missing. Compare median `me` for
  rows missing more than half of them against all other rows, within the same month (median of
  monthly ratios).
- Flag if the left-early coverage is under half the listed coverage, or if the median `me` ratio
  is under 0.5.
- Verdict: PASS if not flagged. If flagged, UNVERIFIED with evidence against, because a route
  (EDGAR by CIK, explicit missing flags) is not closed. FAIL is reserved for "no route", as in
  dd_cards.

**Rule 5, coverage by year (2015–2026).**
- Panel: firms per year, split listed / left early / left 2025–26.
- 8-K: per year, the share of panel firms present that year with at least one 8-K, in the same
  split.
- Literal rule: every year 2021–2026 is at least 50% of its 2024 level. This is checked overall
  and per group.
- Survivorship check: the share of firms present in a window whose last panel month falls before
  the window's last month. Flag if it is under 1%.

**Rule 6, real start date.**
- Monthly row counts. The start month is the first month with at least 50% of the 2024 average
  monthly rows. PASS if it is on or before 2019-12.

Each verdict comes with evidence: counts, a short table and one example firm.

## Known answers, expected BEFORE running

**(a)** 8-K coverage is far lower for left-early firms than for listed firms. Round 1 found 1.6%
vs 93.2%; that figure comes from the user, and its exact definition is not in the repo. Primary
metric: the share of firms with at least one 8-K in their last 12 panel months. Also reported:
the share with at least one 8-K ever. "Far lower" means the left-early share is under half the
listed share. The result is also compared with 1.6% / 93.2% (within ±2 pp counts as reproduced),
but because the definition is unknown, that comparison does not decide pass/fail.

**(b)** In the panel, missingness is informative. Rows missing most characteristics (over 50% of
the 147) have a much smaller `me`: the median ratio is under 0.5.

**Pass criterion.** The agent passes if the rule checks above, as written, flag (a) and (b) on
their own (a non-PASS verdict whose evidence names the gap). For each, the result is reported as
caught / missed.

## Planted-error test (in memory only; nothing altered is written to disk)

- **Slice:** panel rows with `eom` 2019-01-31 to 2020-12-31 (two years, before the test window).
- **Error 1, look-ahead.** For month 2019-12, each permno's 147 characteristic values are replaced
  by its 2020-01 values. The December row then carries January information. Auxiliary columns
  (`ret`, `me`, …) are left alone.
- **Error 2, survivorship.** Drop every permno whose last month in the slice is before 2020-12.
- **Error 3, wrong ticker mapping.** Take the first ticker, alphabetically, carried by two or more
  permnos within the slice, each for at least 6 months. Relabel the later holder's rows to the
  earlier holder's permno.
- **Runs:** the clean slice (control, for false positives); each error alone; all three together.
- **Caught:** the expected rule flags the error on the altered slice and not on the clean slice.
  The expected rules are rule 1 for error 1, rule 5 (survivorship check) for error 2, and rule 3
  for error 3. Any other rule that fires is also reported.

## Outputs

- `RESULTS.md`: one card per dataset (six rules × verdict × evidence), the known-answer results,
  the planted-error results and a 3-sentence summary.
- `dd_selftest.py`: the script.
- Aggregates and single example rows only. No dataset is copied.

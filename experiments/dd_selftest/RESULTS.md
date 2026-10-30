# Data due-diligence self-test: results

**Run:** 2026-10-29, after `RULE.md` (written 11:14 UTC−4, before any computation).
**Script:** `dd_selftest.py`. **Full printed output:** `dd_selftest_output.txt`.
**Read-only.** Both parquets were opened for reading only. The 8-K file was read where it sits in
the Recycle Bin, at the user's request. The planted errors existed only in memory. Nothing was
moved, restored, committed or pushed. Checksums of both files match the organisers' readme.

## Summary for a mentor

We ran the same six data-quality rules we used to vet Carbon Arc's alternative data on our own
competition data, and the checks found, on their own, the two problems we already knew about:
- the 8-K filings almost completely miss companies that left the market before 2025 (1.9% have any
  filing, against 93.2% of companies still listed);
- in the characteristics panel, the rows with the most gaps belong to much smaller companies.

When we deliberately broke a two-year copy of the data in three ways (future data leaking into a
past month, dropping companies that delisted, and pinning a reused ticker on the wrong company),
the checks caught all three, each through the rule designed for it, and none of them fired on the
unbroken copy.

The main limit is that the look-ahead check only works when the leaked columns include price-based
ones: a leak of accounting data alone went unnoticed, and lag and revisions (rules 1 and 2) can
never be fully verified from a single snapshot of the data.

## Results at a glance

| Test | Result |
|---|---|
| Known answer (a): 8-K coverage, left early vs listed | **Caught** by rule 4 (and shown in rule 5's split) |
| Known answer (b): missing characteristics belong to small firms | **Caught** by rule 4 |
| Planted error 1: look-ahead | **Caught** by rule 1 |
| Planted error 2: survivorship | **Caught** by rule 5 |
| Planted error 3: wrong ticker-to-permno map | **Caught** by rule 3 |

## Card 1: characteristics panel (`chars_final_with_names.parquet`)

529,082 rows, 6,561 permnos, 2015-01 to 2026-08.

| Rule | Verdict | Evidence |
|---|---|---|
| 1. Lag | **UNVERIFIED** | No per-record publication or availability date. `eom` is a month label and `date` is the last return date. Timing consistency is clean: `ret_1_0` equals the same row's `ret` in 99.6% of rows in the median month (worst month 97.4%), and `market_equity` equals `me` in 100%. No month is flagged. Example: IBM (permno 12490), row `eom` 2015-01-31, `date` 2015-01-30. Nothing says when the accounting inputs behind that row were public. |
| 2. Vintage | **UNVERIFIED** | No vintage or as-of column. `(permno, eom)` and `(gvkey, iid, eom)` are both unique (0 duplicates). A single snapshot cannot show whether past values were restated, and the readme says original accounting vintages are not certified. |
| 3. Ticker to PERMNO | **PASS** | Tickers are dated per row. 0 ticker-months map to more than one permno. 219 tickers are reused across permnos over time, every one date-bounded. 299 permnos have dated gvkey-iid changes and 0 switch back. Example: ARNC is Arconic Inc. (permno 24643) to 2020-03, then Arconic Corp. (permno 19283) from 2020-04, each on its own permno. |
| 4. Has-data flag | **UNVERIFIED, evidence against** | Missingness is informative. Rows missing over half of the 147 characteristics (20,027 rows) have a median `me` 0.24× that of the other rows, as the median of 140 monthly ratios; it is 0.25× with 2026 excluded. 88% of them are micro or nano caps, against 39% of rows with ≤10% missing. These rows cluster in 2021–22 (about 10% of rows each year, against 1–3% in other years). Example: Ocuphire Pharma (OCUP, permno 92665), 2020-12, `me` $70.6m, 67% of characteristics missing. |
| 5. Coverage by year | **PASS** | Firms per year in 2021–2026 range from 88% to 111% of the 2024 count. The survivorship check is not flagged: 46.7% of firms leave before 2026-08, so dead firms are kept. Split table below. |
| 6. Real start date | **PASS** | Measured start is 2015-01 (3,729 rows, against a 2024 average of 3,884 a month). The panel is cut at 2015 by design. |

Firms in the panel each year:

| Year | Listed in 2026-08 | Left before 2025 | Left 2025–26 | All |
|---|---:|---:|---:|---:|
| 2015 | 1,952 | 1,788 | 198 | 3,938 |
| 2018 | 2,272 | 1,238 | 245 | 3,755 |
| 2021 | 2,968 | 1,172 | 357 | 4,497 |
| 2024 | 3,343 | 355 | 413 | 4,111 |
| 2026 (Jan–Aug) | 3,497 | 0 | 116 | 3,613 |

## Card 2: 8-K filings (`8k_20150101_20260831_identified.parquet`)

373,139 filings, 3,687 permnos, filed 2015-01-02 to 2026-08-31.

| Rule | Verdict | Evidence |
|---|---|---|
| 1. Lag | **UNVERIFIED** | Each record has a filing date but no acceptance time. `sec_accepted_at_utc` is null in all 373,139 rows, and `filing_time_precision` is `date_or_midnight_placeholder` in all of them. This matches the CA0032 precedent. Filing date minus report date: 212,899 filed the same day, 114,582 filed 1–4 days later, 44,646 filed more than 4 days later, 950 have no report date, and 62 are dated *before* their own event. Example: IBM, report date 2015-01-01, filed 2015-01-07, no time of day. |
| 2. Vintage | **UNVERIFIED** | No data-vintage column. The only as-of field is `cusip_asof_date`, which dates the identifier, not the content. 0 duplicate `document_id`s and 0 duplicates on `(permno, filing_date, text_sha256)`; 85 amendments (8-K/A). |
| 3. Ticker to PERMNO | **PASS** | CIK is on every row (0 missing). The filing ticker matches the panel's dated ticker for the same permno and month in 99.95% of filings (167 of 370,121 differ), and 0 filings carry a ticker that another permno held that month. Caveat: both labels come from the same CRSP-dated source, so this checks consistency, not independent truth. |
| 4. Has-data flag | **UNVERIFIED, evidence against** | No field tells "no filing" apart from "not covered". Coverage depends on survival: 1.8% of firms that left before 2025 have an 8-K in their last 12 months, against 92.5% of listed firms. Size does not explain it: among large caps it is 0.3% (left early) against 97.4% (listed). Example: Dr Pepper Snapple Group (DPS, permno 92618), last panel month 2018-07, `me` $171bn, **zero 8-Ks** in the file, though it was listed for 3½ years of the file's span. Not FAIL, because a route exists (EDGAR by CIK, 27 of 27 in the Carbon Arc pilot). |
| 5. Coverage by year | **UNVERIFIED, evidence against** | The literal rule passes overall: 2021 filings are 89% of 2024's, and the share of panel firms covered in 2021 is 81% of 2024's. Split by group, coverage of listed firms is flat at 91–94% every year, while firms that left early sit at 1.5–7.9% every year (table below). That gap is a survivorship hole, not a coverage trend. |
| 6. Real start date | **PASS** | Measured start is 2015-01: 1,715 filings, against a 2024 average of 3,284 a month (the threshold is 50%). |

Share of the year's panel firms with at least one 8-K that year:

| Year | Listed in 2026-08 | Left before 2025 | Left 2025–26 | All | Filings |
|---|---:|---:|---:|---:|---:|
| 2015 | 91.3% | 1.5% | 90.9% | 50.5% | 23,426 |
| 2018 | 92.5% | 1.5% | 91.0% | 62.4% | 26,944 |
| 2021 | 93.4% | 2.4% | 91.3% | 69.5% | 35,124 |
| 2024 | 93.1% | 7.9% | 90.3% | 85.5% | 39,411 |
| 2026 (Jan–Aug) | 86.3% | – | 6.9% | 83.8% | 23,958 |

Rule 4 is not NOT USED for either dataset, because both feed our model. The 8-K features come
from the supplied file (`dd_cards.md`).

## Known-answer test

| Expected before running | Measured | Result |
|---|---|---|
| (a) 8-K coverage far lower for firms that left before 2025 (round 1: 1.6% vs 93.2%) | **1.9% vs 93.2%** with any 8-K ever; 1.8% vs 92.5% in the last 12 months. The left-early share is 2% of the listed share, far below the 50% threshold. | **Caught** by rule 4, and visible in rule 5's split. Round 1 is reproduced within ±2 pp on the "ever" measure. |
| (b) Firms missing most characteristics are much smaller | The median `me` ratio is 0.24 (threshold 0.5). | **Caught** by rule 4. |

## Planted-error test

**Setup.**
- Slice: `eom` 2019-01 to 2020-12, 85,584 rows and 4,090 permnos, in memory only.
- Error 1: every firm's 147 characteristics for 2019-12 were replaced with its 2020-01 values.
- Error 2: the 400 firms that delist within the window were dropped.
- Error 3: ticker ARNC. Arconic Corp.'s rows (permno 19283) were relabelled to Arconic Inc.'s
  permno (24643).

| Error | Expected rule | Result | Evidence (clean slice → altered slice) |
|---|---|---|---|
| 1. Look-ahead | 1 | **Caught by rule 1** | Only month 2019-12 is flagged. Rows where `ret_1_0` matches `ret`: 99.5% → 0.9%. Rows where `market_equity` matches `me`: 100% → 1.1%. No other rule fired. |
| 2. Survivorship | 5 | **Caught by rule 5** | Share of firms exiting within the window: 9.8% → 0.0%, under the 1% flag. Rule 4's size ratio moved only slightly (0.325 → 0.303) and was not flagged. |
| 3. Wrong ticker map | 3 | **Caught by rule 3** | Duplicate `(permno, eom)` keys: 0 → 9, because both Arconics sit on one permno in 2020-04 to 2020-12. One permno switches gvkey and then back (0 → 1). Rule 2's key-uniqueness count also fired (0 → 9). |

All three errors together: each one was still flagged by its own rule. The clean slice raised no
flag under rules 1, 3 or 5.

**Extra run (not one of the three, reported for honesty).** The same look-ahead as error 1, but
leaving `ret_1_0` and `market_equity` untouched, was **missed**. Rule 1's consistency check can
only see a time shift through columns it can tie to the row's own price data. A leak in
accounting characteristics alone would pass.

## Deviations and caveats

- **Script fix after the first run.** The first version of the script also flagged rule 3
  whenever any permno changed gvkey-iid. That is broader than `RULE.md`, which bases PASS only on
  unique keys, 1:1 dated tickers and a conflict rate under 1%. With the broader test, rule 3 fired
  on the clean slice too (93 legitimate dated changes). The script was corrected to match
  `RULE.md` and rerun. The rule was not changed; the raw counts appear in both runs.
- **Rule 5, 8-K verdict.** `RULE.md` said rule 5 is checked overall and per group, but not how to
  combine them. The overall literal test passes, while the left-early group sits at 2–8% in every
  year. I applied the same reading as rule 4 (UNVERIFIED, evidence against).
- **Definition of round 1's 1.6% / 93.2%.** It is not in the repo. The "any 8-K ever" measure
  matches 93.2% exactly and gives 1.9% against 1.6%.
- **This is not a blind test.** The same agent wrote the expected answers and ran the checks. The
  safeguard is that `RULE.md` fixed every check and threshold before any data was computed.
- **Rule 6 is weak here.** Both files are cut at 2015-01 by construction, so rule 6 passes
  trivially, and it could not be evaluated on the 2019–20 slice (no 2024 reference year).

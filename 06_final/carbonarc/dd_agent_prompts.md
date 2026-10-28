# Data due-diligence agent: prompts

Paste these into a Claude session connected to the Carbon Arc MCP. Card 1 needs
`dd_exited_sample.csv` (27 large firms that left our panel 2015-2023, three per exit year,
built by `dd_sample_exited.py`). Answers go into `dd_cards.md` in our own words only.

Budget: about 200 units per `text_to_insight` question. Card 1 asks about three firms per
question (9 questions, about 1,800 units). Cards 2-4 should use catalogue metadata and row
counts, not document questions, so they should cost little. Stop and report if the total
passes 3,000 units.

## Card 1: CA0032 8-K coverage of exited firms

> For each company below, look it up by company name (and ticker as a cross-check) in
> Carbon Arc asset CA0032. The date is the last month the company traded. For each one,
> report only: (1) matched in CA0032: yes / no / ambiguous, with the entity name and CIK
> you matched; (2) number of 8-K filings dated in the 12 months up to and including the last
> month; (3) date of the last 8-K before the last month; (4) whether a merger or
> acquisition 8-K (items 1.01 or 2.01) appears. Answer as a table, one row per company,
> no quotes from filings.
>
> [three rows from dd_exited_sample.csv per question: company_name, ticker, last_panel_month]

**Pass for a firm:** matched, with at least one 8-K in the final 12 months.
**Coverage number:** passing firms / 27. Round one, for comparison: 13% of later-exiting
firms had any 8-K in the supplied file. The organisers' sheet: 326 of 330 large exits missing.

## Cards 2-4: the six-rule pass/fail card

Run once per asset (CA0032 first, then 2-3 from the recommended set, e.g. CA0035 Benzinga).

> Using only Carbon Arc's catalogue metadata and row counts for asset [ID], answer each rule
> with PASS, FAIL or UNKNOWN and one line of evidence (a field value, date or count):
> 1. Lag: the declared publication lag, and whether records carry both an event date and a
>    publication or availability date.
> 2. Vintage: are records point-in-time, or can a past value be revised later (is there a
>    version, as-of or restatement column)?
> 3. Ticker mapping: which entity keys it uses (ticker, CIK, CUSIP, other), and whether
>    ticker links are date-bounded.
> 4. Has-data flag: is there a field or method to tell "no event" apart from "not covered"?
> 5. Coverage: number of distinct entities and rows per year, 2015-2026.
> 6. Real start date: the earliest date with substantial rows, against the date the
>    catalogue advertises.

**Pass rules (ours):** lag declared and dated per record; no silent revisions; CIK or
date-bounded ticker; "not covered" distinguishable from "nothing happened"; coverage within
50% of its 2024 level back to 2021 (our test window start); real history starts by 2019
(design window).

## Cards 5-7: spending data for the news -> spending sleeve (quality gate)

Catalogue documentation only: free `data_library` / tearsheet / data-dictionary calls, no
billed query. Report the units used; it should be 0. Same verdict scale as `dd_cards.md`
(PASS / FAIL / UNVERIFIED / NOT USED), with one line of evidence each.

> Using only Carbon Arc's free catalogue calls (data library, tearsheets, data dictionaries),
> find the tearsheets for (a) card spend / consumer transactions, (b) foot traffic / store
> visits and (c) website traffic. For each, name the tearsheet and provider, then answer the
> six rules:
> 1. Publication lag: declared lag and delivery frequency; is there a publication or
>    availability date per record, or only the period date?
> 2. Backward revisions: does the documentation say past values are restated (panel
>    rebalancing, re-weighting, late-arriving transactions)? Is there a vintage or as-of column?
> 3. Ticker -> PERMNO mapping: entity keys (ticker, CIK, brand, merchant, domain, location);
>    how brands or domains map to a listed parent; are ticker links date-bounded?
> 4. Has-data flag: can "no activity" be told apart from "not covered" (zero vs missing)?
> 5. Coverage: number of companies or brands, and any coverage-by-year figures.
> 6. Real start date: advertised history start, and any note that early history is
>    backfilled or reconstructed.
> Do not quote documentation text; summarise in our own words.

Our extra rule for this sleeve: a dataset fails the gate if its lag is undocumented, or if
its history does not start before the first month the chain would need it (2022 inflation
case: data from 2021 at the latest). Website traffic (from 2020-06) is descriptive only.
Rules 3, 5 and 6 are then checked on the shared panel with `dd_coverage.py`.

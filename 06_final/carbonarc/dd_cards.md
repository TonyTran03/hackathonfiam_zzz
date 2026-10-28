# Carbon Arc data due diligence: 8-K search retrieval for exited firms and the six-rule cards

Pilot run on 2026-10-28 by an agent (Claude, connected to the Carbon Arc MCP), following
`dd_agent_prompts.md` and the 27 firms in `dd_exited_sample.csv`. Carbon Arc is used here
only to judge whether its data could help with the survivorship gap in our 8-K file.
Nothing here feeds the model.

This file is our own summary. It contains no text copied from Carbon Arc, its catalogue
or the filings behind it.

**Account context.** Every Carbon Arc result below came through Bohan's MCP connection
(context A), and which account it was signed in to is not confirmed. After reconnecting
to the team account (context B), a successful query, an unresolved query and three
catalogue checks gave identical results and permissions. See `dd_account_context.md`.
The SEC EDGAR checks do not depend on the account.

## Summary

**Headline: all 27 exited firms filed 8-Ks on SEC EDGAR in their final 12 months (8 to 34
filings each), but Carbon Arc's name search retrieved only 2 of them.** The filings exist
at the source; what is missing is a route to them keyed by CIK. EDGAR itself is that route.

| Step | Count |
|---|---|
| Exited firms with 8-K filings on SEC EDGAR in their final 12 months | **27 of 27** |
| Companies searched in CA0032 by name | 27 |
| 8-K event series retrieved | 2 (Nortek, Hostess Brands) |
| Retrieved series with legal entity confirmed on SEC EDGAR | 2 |
| Pre-exit 8-Ks verified as documents on EDGAR (accession and URL recorded) | 2 |
| Pre-exit 8-K dates in the final 12 months matched to the EDGAR filing index | 21 (10 Nortek, 11 Hostess) |
| Companies unresolved in Carbon Arc (all 25 have CIKs and pre-exit 8-Ks on EDGAR) | 25 |

This pilot does not establish that survivorship bias is resolved: it shows the gap is in
the supplied file and in Carbon Arc's lookup, not in the filings, for a sample of 27 of
the 672 large exits.

## Method

- **Which asset is CA0032.** The MCP catalogue does not index assets by CA code. A lookup
  of "CA0032" or "CA0035" returns unrelated tearsheets. Our source for the codes is the
  team's finals handoff note, which summarises the organisers' instructions: CA0032 is
  EDGAR keyed by CIK from 2012, and CA0035 is Benzinga event tags from 2011 with a T+1 lag
  and weekly delivery. We matched each code to a catalogue tearsheet on those attributes.
  - "Financial Filing Forms" matches CA0032: provider SEC Edgar, CIK key, aggregated
    history from 2012. The 8-K query results also name this tearsheet as their data asset.
  - "Financial News & Data" matches CA0035: provider Benzinga, history from 2011, T+1,
    weekly.
- **Card 1 route.** The prompt's document question (`text_to_insight`) cannot answer it.
  We sent the first three firms and got no answer. The document archive holds 10-K and
  10-Q text only, and for CareFusion it surfaced the acquirer's (Cardinal Health) filings.
  We switched to the structured route. Some companies have an "SEC Form 8-K Filing" event
  series under the "SEC Filing Events" insight, and a framework query returns every event
  date in it. We searched the event list for all 27 firms by name, cross-checked the
  company entity list, and pulled dates where a series came back.
- **Rate limits.** The event search allows about one call every two minutes. After eight
  single-name searches, we searched the last 16 firms four names per query. A control
  query with two known hits and two known misses returned both hits in its top ten. A
  batched miss is still weaker evidence than a single-name miss.
- **Verification on EDGAR.** For each retrieved series we downloaded the company's filing
  index from SEC EDGAR, a free public source. We then matched Carbon Arc's event dates to
  each candidate CIK's 8-K dates. We opened one pre-exit 8-K per company and recorded its
  accession number and URL in `dd_verified_filings.csv`. We made seven requests to EDGAR
  in all and bought nothing.
- **Cost.** About 35 Carbon Arc units of the 3,000-unit cap, all from two framework queries
  in the first round. This round used only free catalogue and search calls. The day
  started at 4,508 of 20,000 daily units used, from earlier work.
- **Cards 2-4.** Catalogue metadata only, plus the card 1 evidence for CA0032.

## Card 1: 8-K search retrieval for 27 exited firms

| Exit month | Ticker | Company | Search result in CA0032 | 8-K dates in final 12 months | Last 8-K before exit month | M&A 8-K (items 1.01/2.01) |
|---|---|---|---|---|---|---|
| 2015-02 | SAPE | Sapient | Not found | - | - | - |
| 2015-03 | CFN | CareFusion | Not found | - | - | - |
| 2015-12 | ZSPH | ZS Pharma | Not found | - | - | - |
| 2016-05 | BXLT | Baxalta | Not found | - | - | - |
| 2016-08 | NTK | Nortek | Series found; verified as Nortek, Inc., CIK 1216596 | 10, all on EDGAR | 2016-07-06, verified | Yes: 2016-07-06, item 1.01, merger agreement with Melrose Industries |
| 2016-11 | CVT | Cvent | Not found | - | - | - |
| 2017-07 | RAI | Reynolds American | Not found | - | - | - |
| 2017-08 | WBMD | WebMD Health | Not found | - | - | - |
| 2017-11 | CBF | Capital Bank Financial | Not found (batched search) | - | - | - |
| 2018-02 | STRP | Straight Path Communications | Not found (batched search) | - | - | - |
| 2018-07 | CPLA | Capella Education | Not found (batched search) | - | - | - |
| 2018-11 | LPNT | LifePoint Health | Not found (batched search) | - | - | - |
| 2019-01 | VVC | Vectren | Not found (batched search) | - | - | - |
| 2019-02 | DNB | Dun & Bradstreet (old) | Ambiguous: only the 2020 relisted holding company, with no 8-K series | - | - | - |
| 2019-03 | NTRI | Nutrisystem | Not found (batched search) | - | - | - |
| 2020-03 | ZAYO | Zayo Group | Company entity found (326174), no filing events | - | - | - |
| 2020-10 | ETFC | E*TRADE Financial | Not found (batched search) | - | - | - |
| 2020-10 | NBL | Noble Energy | Not found (batched search) | - | - | - |
| 2021-02 | BEAT | BioTelemetry | Not found (batched search) | - | - | - |
| 2021-06 | BPFH | Boston Private Financial | Not found (batched search) | - | - | - |
| 2021-11 | KDMN | Kadmon Holdings | Not found (batched search) | - | - | - |
| 2022-01 | MGLN | Magellan Health | Not found (batched search) | - | - | - |
| 2022-04 | FLOW | SPX Flow | Not found (batched search) | - | - | - |
| 2022-11 | CLR | Continental Resources | Not found (batched search) | - | - | - |
| 2023-02 | CINC | CinCor Pharma | Not found (batched search) | - | - | - |
| 2023-11 | TWNK | Hostess Brands | Series found; verified as Hostess Brands, Inc., CIK 1644406 | 11, all on EDGAR | 2023-09-12, verified | Yes: 2023-09-12, item 1.01, merger agreement with J. M. Smucker |
| 2023-11 | VMW | VMware | Not found | - | - | - |

### The two verified hits

| | Hostess Brands | Nortek |
|---|---|---|
| Legal entity on EDGAR | Hostess Brands, Inc., CIK 1644406, formerly Gores Holdings, Inc. | Nortek, Inc., CIK 1216596 |
| Pre-exit 8-K opened | Filed 2023-09-12, accession 0001193125-23-233053 | Filed 2016-07-06, accession 0001047469-16-014186 |
| What it reports | Item 1.01: merger agreement with J. M. Smucker | Item 1.01: merger agreement with Melrose Industries, plus items 5.02, 5.03, 7.01 and 9.01 |
| Carbon Arc provenance | Company 26594, event series 7622, SEC Filing Events insight, Financial Filing Forms tearsheet, last refresh 2026-07-15 | Company 66399, event series 10677, same insight and tearsheet, last refresh 2026-07-15 |
| Carbon Arc 8-K dates found on this CIK's EDGAR 8-K dates | 107 of 107 | 131 of 131 |
| EDGAR 8-K dates missing from Carbon Arc | None | 6, all amendment-only (8-K/A) dates |

What the verification shows:

1. **The identities hold.** Every Carbon Arc 8-K date for the two hits falls on an EDGAR
   8-K date of one CIK. Nortek has an older registrant, Nortek Holdings (CIK 72423), and
   11 Carbon Arc dates from 2003-2004 also appear in its index. But all 131 dates appear
   in CIK 1216596's index, so we assign the series to it.
2. **Events are dates, not filings.** Carbon Arc keeps one event per filing date. Hostess
   filed 110 8-Ks on 107 dates, and Nortek filed 152 8-Ks and 8-K/As on 137 dates. Counts
   in the table above are distinct dates.
3. **Item codes exist upstream but not in the MCP rows.** EDGAR's index carries item codes,
   which identify both merger 8-Ks. The Carbon Arc event rows do not.

### All 27 on SEC EDGAR

For the 25 firms Carbon Arc did not return, we looked up each legal entity and CIK by name
in EDGAR's company search and counted its 8-K filings from the EDGAR filing index. The
results are in `dd_unresolved_ciks.csv`; Hostess Brands and Nortek are in
`dd_verified_filings.csv`.

| | Result |
|---|---|
| Exited firms with a CIK found on EDGAR | 27 of 27 |
| Firms with at least one 8-K in the 12 months ending with the exit month | 27 of 27 |
| 8-K filings per firm in that window, the 25 unresolved | 8 to 34 (median 14) |
| 8-K dates in that window, Hostess Brands and Nortek | 11 and 10 |
| Last 8-K before the exit month began, the 25 unresolved | 2 to 65 days before; median 9 days |
| Same, Hostess Brands and Nortek | 50 and 26 days before |

- **Count definition.** Filings of form 8-K, not 8-K/A amendments, filed in the 12 calendar
  months ending with the exit month. The two Carbon Arc hits are counted as distinct dates,
  because that is what Carbon Arc returns.
- **Spot check.** We re-pulled four firms from EDGAR's submissions data (Reynolds American,
  Noble Energy, Magellan Health, Vectren). All four counts and last pre-exit dates match the
  CSV on the definition above.
- **Entity caveats.** LifePoint and VMware appear on EDGAR under their post-merger names
  (Legacy LifePoint Health; VMware LLC), on the same CIK. Dun & Bradstreet is the CIK of the
  company taken private in 2019 (1115222), not its 2020 relisted successor.
- **What this does not show.** It does not show that Carbon Arc holds these filings, and
  nothing was rebuilt: our 8-K features still come from the supplied file. A fix would key
  EDGAR by CIK and link CIK to permno with dates, which is the rebuild we deferred today.

### Unresolved cases and access limits

- **25 companies are unresolved in Carbon Arc, though all 25 are on EDGAR.** 23 returned no series in name search, Zayo has a company
  entity with no filing events, and Dun & Bradstreet resolves only to its 2020 successor.
  For these firms, a miss means our name searches found nothing. It does not show that
  Carbon Arc lacks their filings.
- **The MCP offers no CIK search.** Entities resolve by present-day name, and the event
  rows expose no CIK. So there is no MCP route from a CIK we hold to Carbon Arc's records.
- **Rate limits forced batched searches** for 16 of the 25 misses.
- **The raw EDGAR block** documents CIK, filing date and form type on every row. A bulk
  extract keyed by CIK might resolve the 25. The MCP cannot test that, and it would be a
  purchase.

**Background, not comparable with the pilot above.** In round one, 13% of later-exiting
firms had any 8-K in the supplied file. The organisers' sheet lists 326 of 330 large exits
as missing. Those figures measure the supplied file, over a different set of firms, with a
different method. Read together with the 27 of 27 above, they say the same thing: exiting
firms keep filing 8-Ks until they leave, and the supplied file drops them.

## Cards 2-4: the six-rule card

Our pass rules: lag declared and dated per record; no silent revisions; CIK or
date-bounded ticker; "not covered" distinguishable from "nothing happened"; coverage within
50% of its 2024 level back to 2021; real history starting by 2019.

How to read the verdicts:

- **PASS** would mean we checked the rule on records across the asset. None reached PASS.
- **FAIL** would mean the evidence shows the rule cannot be met by any route. None reached
  FAIL. A missing CIK, for example, closes the CIK route but leaves date-bounded ticker
  matching open, so that is UNVERIFIED.
- **UNVERIFIED** means only documentation speaks to the rule, or our record checks cover
  too few firms to generalise.
- **NOT USED** applies to rule 4 only. No Carbon Arc data feeds any signal, so telling "no
  event" from "not covered" does not yet matter. The check: `06_final/run_all.sh` never
  runs `f09_altdata.py`, and no module imports it. It is the only code that would read a
  Carbon Arc asset. The handoff note also says never to trade a "has data" flag.

**Assets checked.** Three distinct assets from the organisers' recommended set, as named
in the handoff note: CA0032, CA0035 and CA0092 (New Constructs ratings). CA0092 is the
asset added this round. It is not in the MCP catalogue under any of five searches, by
name, by content and by entity. So we could not confirm its ID or read its tearsheet, and
its column rests only on the handoff note. The "Company Reported Actuals" table from last
round is listed inside the CA0032 tearsheet, so it no longer counts as an asset here.

| Rule | CA0032 SEC EDGAR filings | CA0035 Benzinga news and events | CA0092 New Constructs ratings |
|---|---|---|---|
| 1. Lag | **UNVERIFIED.** Documented: T+1, with filing date and EDGAR acceptance time on each row. Observed: for two firms, every 8-K event date equals an EDGAR filing date. The rows carry no acceptance time and no event date. | **UNVERIFIED.** Documented: T+1, but one date per record, so per-record publication dating is unavailable. A fixed T+1 lag would have to be assumed and tested. | **UNVERIFIED.** Handoff note only: T+2. No tearsheet found. |
| 2. Vintage | **UNVERIFIED.** Documented: facts are tied to a filing's accession number and date, with a flag for repeated figures. We opened no fact rows. | **UNVERIFIED.** The dictionary has no version or as-of column. No rows opened. | **UNVERIFIED.** No documentation reachable. |
| 3. Ticker mapping | **UNVERIFIED.** Documented: CIK on every raw row. Observed: the MCP event rows expose no CIK. We confirmed CIKs for two firms ourselves through EDGAR. | **UNVERIFIED.** No CIK, so the CIK route is unavailable. The dictionary shows a current Bloomberg ticker with no date bounds. Matching would need our own date-bounded ticker map, which we have not tested. | **UNVERIFIED.** No documentation reachable. |
| 4. Has-data flag | **NOT USED.** No coverage field documented. Not a failure, because no signal reads this data. | **NOT USED.** Same reason. | **NOT USED.** Same reason. |
| 5. Coverage by year | **UNVERIFIED.** Catalogue totals only: about 17,000 filers, 7,500 tickers and 500,000 filings. Exited firms: 2 of 27 series retrieved by name. | **UNVERIFIED.** Catalogue totals only: about 3,000 stocks. | **UNVERIFIED.** No documentation reachable. |
| 6. Real start date | **UNVERIFIED.** Catalogue: 2009 for the filings block, 2012 aggregated. Observed: Nortek's events from 2003 all match EDGAR, but that is one firm, not a row count. | **UNVERIFIED.** Catalogue: 2011. | **UNVERIFIED.** Handoff note only: 2016. |

**Documented lag and observed freshness are different things.** The lags above are what
the documentation declares. What we observed: the two framework queries on the SEC Filing
Events insight, for Nortek and Hostess, each reported a last data refresh of 2026-07-15.
The Financial Filing Forms tearsheet shows the same date. That date applies to that
insight and tearsheet as served by the MCP. We did not check freshness for Benzinga, for
New Constructs, or for the raw filings block.

**Carbon Arc's own load dates are not point-in-time.** The dictionary's sample values show
the EDGAR block loaded in one full backfill on 2026-10-13, so Carbon Arc's receipt date
cannot date first availability. For the two verified firms the event date equals the
EDGAR filing date, which can serve that purpose.

## Cards 5-7: spending data for the news-to-spending sleeve

Run on 2026-10-28 under the team account (context B in `dd_account_context.md`), using
the free catalogue calls only: data-library searches and tearsheets with their data
dictionaries. **Units used: 0.** The session made no billed call in this step.

Each card uses the same verdict scale as cards 2-4, with one change for rule 4. These
datasets are candidates for a planned sleeve, so "NOT USED" no longer applies there: rule
4 is UNVERIFIED until `dd_coverage.py` measures zeros against missing values on the
shared panel. Rules 3, 5 and 6 are also checked on that panel. No panel is in the repo
yet, so every row stays catalogue-only for now.

**Tearsheets found.** We searched once for each kind of data and then read the closest
tearsheet:

- **Card spend:** "Credit Card – US Complete Panel" from Facteus. A second tearsheet, "US
  Detailed Panel", is a closed history from 2019-01 to 2025-08. We did not card it.
- **Foot traffic:** "Foot Traffic" from PassBy.
- **Website traffic:** "Clickstream". The tearsheet names no provider.

| Rule | Card 5: card spend (Facteus) | Card 6: foot traffic (PassBy) | Card 7: website traffic (Clickstream) |
|---|---|---|---|
| 1. Publication lag | **UNVERIFIED.** Documented: T+3, delivered daily. Each transaction row carries only the transaction date. The only load marker is a batch label, and the sample batch is a full backfill of 2026-05-01. | **UNVERIFIED.** Documented: T+5, delivered daily. Rows carry the visit date and the month it belongs to. Each row also has a load-batch label, and the sample is an incremental drop of 2025-12-10. If old batches are kept, that label could date first availability. | **UNVERIFIED.** Documented: T+1, delivered daily. Rows carry the visit date, a device timestamp and a numeric load-batch ID. |
| 2. Backward revisions | **UNVERIFIED, revisions documented.** The tearsheet says the panel is reweighted every month, when the vendor restates it and drops inactive cards. A card's in-scope flag reflects its current status. So past totals can change, and there is no vintage or as-of column to rebuild them. | **UNVERIFIED.** Visits are modelled, then adjusted for season, weather and holidays. Nothing says whether past values are re-modelled. No vintage column. | **UNVERIFIED.** No restatement is described. The panel is opt-in users, so its make-up can drift. No vintage column. |
| 3. Ticker to PERMNO | **UNVERIFIED.** Keys are Carbon Arc company, brand and ticker IDs plus a current Bloomberg ticker. There is no CIK, and links have no date bounds. Brands reach a listed parent through the company ID. | **UNVERIFIED.** Keys are store ID, Placekey, brand, company and a current Bloomberg ticker. No CIK, no date bounds. | **UNVERIFIED.** Domains map to brand, company and ticker through a mapping table. The table warns that one domain can map to several rows. No date bounds. |
| 4. Has-data flag | **UNVERIFIED.** No field separates "no spend" from "not covered". The two card flags describe the cards, not company coverage. To be measured by `dd_coverage.py`. | **UNVERIFIED.** No such field. Store-days with no row are ambiguous. To be measured by `dd_coverage.py`. | **UNVERIFIED.** No such field. |
| 5. Coverage | **UNVERIFIED.** Catalogue totals only: 5,200+ companies, 8.8 million cards in 2024. Spend is skewed toward Iowa, Ohio and Washington. | **UNVERIFIED.** Catalogue totals only: 600+ companies, 1,200+ brands, 740,000+ stores. Skewed toward California, Texas and Florida. | **UNVERIFIED.** Catalogue totals only: 670+ companies, 2,400+ domains. Worldwide, skewed to the US, China, India and Argentina. |
| 6. Real start date | **UNVERIFIED, conflicting.** The history field says 2019. The overview says each panel holds five and a half years, which from today would start around April 2021. The sample load is a full backfill. | **UNVERIFIED.** The history field says 2019, and a sample row is dated 2019-07. Nothing says early history is backfilled. | **UNVERIFIED.** The history field says 2020. |
| Sleeve gate | **Passes on documentation, with a caveat.** The lag is documented. The start date passes if the 2019 figure holds, but the five-and-a-half-year note must be checked on the panel. | **Passes on documentation.** The lag is documented, and the 2019 start comes before 2021. | **Descriptive only,** as the prompts set out. Its 2020 start would pass the date rule. |

What the three cards show:

1. **All three document a lag, so none fails the sleeve gate on lag.** Each carries only
   the period date per record, though, so a fixed lag would have to be applied and
   tested.
2. **Card spend is the clearest revision risk.** It is the only one whose documentation
   says past values change. It also has no vintage column, so the series used in a
   backtest would be today's restated version, not what was available at the time.
3. **Card spend's start date was the open question.** The catalogue gives two different
   answers. The panel check below settles it: the history starts in 2019-01.
4. **None of the three carries a CIK or date-bounded tickers.** Mapping to PERMNO has to
   go through tickers we bound by date ourselves. The panel check below measures how
   often the vendor's ticker lands on a company that was not listed that month.

### Panel check: cards 5 and 6 on the shared panels

Run on 2026-10-28 with `dd_coverage.py` on Faig's two panels (`PROVENANCE.md` on his
machine: MCP `framework_to_insight`, monthly US sums, 2019-01 to 2026-08, nothing bought).
The panels are licensed and stay out of the repo. Only our counts are recorded here, and
the two coverage charts (`dd_coverage_card_spend.png`, `dd_coverage_foot_traffic.png`)
show counts of names, not Carbon Arc values. Units used in this step: 0.

**Mapping method.** The panels are keyed by ticker. Each (ticker, month) is matched to the
permno that carried that ticker that month in our panel. A second pass recovers renames:
if the permno that carries the ticker today was live that month under an earlier ticker,
the row is matched to it. Every other row is labelled pre-listing, post-delisting or gap.

| Measured on the panel | Card spend (Facteus) | Foot traffic (PassBy) |
|---|---|---|
| Tickers, rows, months | 117 tickers, 10,351 rows, 92 months | 100 tickers, 9,198 rows, 92 months |
| Names with a value in every month | 105 of 117 (Faig's count confirmed) | 98 of 100 (ODP ends 2026-06; RAD has 2 missing months) |
| Names with a value in 2019-01 / 2021-01 / 2024 average | 110 / 112 / 114 | 100 / 100 / 100 |
| Of those, live stocks in our panel | 89 / 96 / 104 | 85 / 90 / 92 |
| Measured start month (first month at half the 2024 level) | 2019-01, for all names and for live names | 2019-01, for all names and for live names |
| Rows on a live stock-month | 9,234 (89.2%): 8,992 by dated ticker, 242 through an earlier ticker | 8,388 (91.2%): 8,248 and 140 |
| Rows before listing | 596 (pre-IPO brands, e.g. KLC, SG, FWRG, LTH, DNUT) | 365 |
| Rows after delisting | 468 (companies still operating after leaving the market, e.g. PRTY, TA, RAD, JWN, WBA) | 392 |
| Gap or ambiguous | 52 gap (WOOF, ACI, DXLG, WW); 1 ambiguous (CZR, 2020-07 merger month) | 52 and 1, the same names |
| Zero values / missing values | 0 / 0. Absent months are simply missing rows. | 9 / 2. The zeros are real closures (RAD after its stores closed, WYNN in 2020-04). |

**The 12 short card-spend histories** (Faig's list confirmed): SAH (1 month), SPTN (2),
POOL (10), LAD (31), CRMT (38), EVRI (81, starts 2019-11), WYNN (85), DXLG (86), RSI (87,
starts 2019-06), LRN (88), SYY (91), VVNT (91). Most are businesses that consumers rarely
pay by card: car dealers (SAH, LAD, CRMT), distributors (SPTN, POOL, SYY), or casino
operators whose spend is mostly outside the US (WYNN). Their monthly values are tiny, and
the missing months fall where a tiny series has no transactions. Four names with a full
92 months are just as thin (BYD, CHDN, GHC, LVS, each with a median under $10,000 a month),
so about 101 card-spend names are both complete and usable.

**Breaks that point to vendor-side changes in card spend.** In the same months, foot
traffic for the same company stays flat or rises:

- **BGFV:** card spend falls 96% from 2024-03 to 2024-07, while foot traffic rises 11%.
- **GES:** card spend falls 58% in 2024-03, while foot traffic rises 24%.
- **UDMY:** card spend rises about 6x between 2022-10 and 2023-01. **TNL:** it rises 2.4x
  in 2024-08. There is no foot-traffic series for either to compare with.
- **ETSY:** card spend grows from about $500 a month in 2019-01 to $1.7 million in 2026-08.
  That pattern is merchant coverage growing inside the panel, not the business.

Together with the documented monthly reweighting, these breaks are why card spend stays
descriptive.

| Rule | Card 5: card spend, after the panel check | Card 6: foot traffic, after the panel check |
|---|---|---|
| 1. Publication lag | UNVERIFIED (unchanged). A single snapshot cannot show when values arrived. | UNVERIFIED (unchanged) |
| 2. Backward revisions | **UNVERIFIED, evidence against.** Restatement is documented, there is no vintage column, and the panel shows breaks that the business did not have. | UNVERIFIED. One snapshot cannot show revisions. To test it, re-pull a few names later and compare. |
| 3. Ticker to PERMNO | **PASS with our own date-bounded map.** 89% of rows land on a live stock-month. The other 11% belong to companies that were not listed that month, and the map drops them. | **PASS with our own map.** 91% of rows land on a live stock-month. |
| 4. Has-data flag | **UNVERIFIED.** Card spend never reports a zero, so a missing month cannot be told apart from no coverage. | **PASS on our panel.** Zeros mark real closures, and only 2 values are missing. |
| 5. Coverage | **PASS on our panel.** 96 live names in 2021-01, against a 2024 average of 104. | **PASS on our panel.** 90 live names in 2021-01, against 92. |
| 6. Real start date | **PASS.** Measured start 2019-01, so the catalogue's five-and-a-half-year note does not apply to this pull. That 2019 history is today's restated version (rule 2). | **PASS.** Measured start 2019-01. |
| Sleeve gate | **Descriptive only.** It meets the start-date rule but fails on revisions risk. | **Passes on the panel** for rules 3-6. Lag and vintage still rest on documentation. |

## What we did and did not act on

- **No change to the model or the 8-K features.** This pilot does not establish that
  survivorship bias is resolved. The bias stays documented as a limitation.
- **No asset is cleared for new features.** Nothing reached PASS.
- **Spending sleeve:** foot traffic passes the gate on the shared panel (rules 3-6), and it is
  the dataset the sleeve will use. Join it to permno with the date-bounded map in
  `dd_coverage.py`, keeping only rows on a live stock-month. Card spend stays descriptive:
  its documented restatements and the panel's level breaks need their own point-in-time
  plan first. Lag and vintage remain documentation-only for both datasets.
- **Done: CIKs and pre-exit 8-Ks from EDGAR for all 25 unresolved firms** (27 of 27 with
  the two hits; see "All 27 on SEC EDGAR").
- **Next step, not done:** a Carbon Arc route keyed by CIK, so the same filings could come
  through the competition's data provider. `dd_carbonarc_request.md` drafts the support
  request; a bulk extract would be a purchase. A CA0092 card needs its tearsheet, which
  means asking Carbon Arc whether our account can see it.

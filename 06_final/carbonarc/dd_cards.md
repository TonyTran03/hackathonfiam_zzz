# Carbon Arc data due diligence: 8-K search retrieval for exited firms and the six-rule cards

Pilot run on 2026-10-28 by an agent (Claude, connected to the Carbon Arc MCP), following
`dd_agent_prompts.md` and the 27 firms in `dd_exited_sample.csv`. Carbon Arc is used here
only to judge whether its data could help with the survivorship gap in our 8-K file.
Nothing here feeds the model.

This file is our own summary. It contains no text copied from Carbon Arc, its catalogue
or the filings behind it.

## Method

- **Which asset is CA0032.** The MCP catalogue does not index assets by CA code. A lookup
  of "CA0032" and "CA0035" returns unrelated tearsheets. We take CA0035 to be Benzinga
  ("Financial News & Data"), as `f09_altdata.py` already does. We take CA0032 to be the SEC
  EDGAR tearsheet ("Financial Filing Forms"). The 8-K query results name that tearsheet
  as their data asset, which supports the mapping but does not prove it.
- **Card 1 route.** The prompt's document question (`text_to_insight`) cannot answer it.
  We sent the first three firms (Sapient, CareFusion, ZS Pharma) and got no answer. The
  document archive holds 10-K and 10-Q text only, and for CareFusion it surfaced the
  acquirer's (Cardinal Health) filings instead. We switched to the structured route. Some
  companies have an "SEC Form 8-K Filing" event series under the "SEC Filing Events"
  insight, and a framework query returns every event date in it. We searched the event
  list for all 27 firms by name, cross-checked the company entity list, and pulled dates
  where a series came back.
- **Rate limits.** The event search allows about one call every two minutes. After the
  first eight single-name searches, we searched the last 16 firms four names per query.
  A control query with two known hits and two known misses returned both hits in its top
  ten. That supports the batched searches, but a batched miss is weaker evidence than a
  single-name miss.
- **Cost.** About 35 units of the 3,000-unit cap: two framework queries at about 15 units
  each. The failed document question cost nothing. Discovery calls are free. The day
  started at 4,508 of 20,000 daily units used, from earlier work. The dollar balance was
  not touched.
- **Cards 2-4.** Catalogue metadata only: tearsheets and data dictionaries. We opened no
  data rows for these cards apart from the 8-K event dates from card 1.

## Card 1: 8-K search retrieval for 27 exited firms

**Search retrieval only: 2 of 27 firms returned an 8-K event series (Nortek, Hostess
Brands).** This is not a verified coverage rate. For the two hits we did not open any
filing. We also could not confirm the company identity, because the event rows carry no
CIK. For the other 25, the miss means our name searches found no series. It does not
show that Carbon Arc lacks their filings.

| Exit month | Ticker | Company | Search result in CA0032 | 8-K events in final 12 months | Last 8-K event before exit month | M&A 8-K (items 1.01/2.01) |
|---|---|---|---|---|---|---|
| 2015-02 | SAPE | Sapient | Not found | - | - | - |
| 2015-03 | CFN | CareFusion | Not found | - | - | - |
| 2015-12 | ZSPH | ZS Pharma | Not found | - | - | - |
| 2016-05 | BXLT | Baxalta | Not found | - | - | - |
| 2016-08 | NTK | Nortek | Series found (Carbon Arc company 66399); identity unverified | 10 | 2016-07-06 | Not available: no item codes |
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
| 2023-11 | TWNK | Hostess Brands | Series found (Carbon Arc company 26594); identity unverified | 11 | 2023-09-12 | Not available: no item codes |
| 2023-11 | VMW | VMware | Not found | - | - | - |

What the search shows:

1. **Most exits did not resolve by name.** The company entity search found only Nortek,
   Zayo and Hostess Brands. For Dun & Bradstreet it found only the 2020 relisted holding
   company. Large names such as Reynolds American and VMware returned nothing.
2. **The two hits return long event histories.** Nortek's event dates reach back to 2003.
   Hostess has 9 to 21 events in every full year from 2016 to 2022. We did not check
   these against EDGAR, so we cannot say the series are complete.
3. **Two things the prompt asked for are missing from the event rows.** There are no
   item codes, so a merger 8-K cannot be told apart from any other. There is no CIK, so
   matches rest on Carbon Arc's company ID and name.
4. **Some delisted firms do have series.** The event search also returned series for
   Pharmacyclics, XO Group and InterDent, all no longer listed.

The SEC EDGAR data dictionary documents CIK, filing date and form type on every row of
the raw filings block. A bulk extract keyed by CIK, joined through our CIK-permno bridge,
might recover filings that name search cannot. The MCP cannot test that, and it would be
a separate purchase.

**Background, not comparable with the pilot above.** In round one, 13% of later-exiting
firms had any 8-K in the supplied file. The organisers' sheet lists 326 of 330 large exits
as missing. Those figures measure the supplied file over a different set of firms with a
different method.

## Cards 2-4: the six-rule card

Our pass rules: lag declared and dated per record; no silent revisions; CIK or
date-bounded ticker; "not covered" distinguishable from "nothing happened"; coverage within
50% of its 2024 level back to 2021; real history starting by 2019.

How to read the verdicts:

- **PASS** would mean we checked the rule on actual records. No rule reached PASS in this
  pilot.
- **FAIL** means the data dictionary itself shows the rule cannot be met, for example a
  missing key or date column.
- **UNVERIFIED** means only the catalogue speaks to the rule, or we did not inspect it.
- **NOT USED** applies to rule 4 only. It means no Carbon Arc data feeds any signal, so
  telling "no event" from "not covered" does not yet matter.

The rule 4 check: `06_final/run_all.sh` never runs `f09_altdata.py`, and no module
imports it. It is the only code that would read a Carbon Arc asset. So data availability
is not used as a trading signal. Rule 4 must be re-checked before any of these assets
feeds a feature.

**Assets checked.** The third column is not an independent asset. The "Company Reported
Actuals" table (Carbon Arc topic 89) is listed inside the CA0032 SEC EDGAR tearsheet. It
is also published on its own as the "Financial Reporting" tearsheet, and neither shows a
CA asset ID. We treat it as another table of CA0032. So this pilot covers two assets:
CA0032, with two of its tables, and CA0035.

| Rule | CA0032 filings block and SEC Filing Events | CA0035 Benzinga news and events | CA0032 table: Company Reported Actuals |
|---|---|---|---|
| 1. Lag | **UNVERIFIED.** Documented: a T+1 lag, and filing date plus EDGAR acceptance time on each row. Observed: the 8-K event rows we pulled carry one date each and no acceptance time. | **FAIL.** Documented: a T+1 lag, but the dictionary shows one date per record, so event and publication dates cannot be told apart. | **FAIL.** Documented: a T+90 lag on the "Financial Reporting" tearsheet. Records carry only the period start and end, with no filing date. |
| 2. Vintage | **UNVERIFIED.** Documented: each fact is tied to a filing's accession number and date, with a flag for figures repeated in later filings. We opened no fact rows. | **UNVERIFIED.** The dictionary has no version or as-of column. We opened no rows. | **UNVERIFIED.** The dictionary has no version or as-of column. We opened no rows. |
| 3. Ticker mapping | **UNVERIFIED.** Documented: CIK on every row, plus a current-only ticker. Observed: the MCP event rows expose neither, so our matches used Carbon Arc company IDs. | **FAIL.** The dictionary shows Carbon Arc ticker and company IDs plus a Bloomberg ticker, with no CIK and no date bounds. | **FAIL.** The dictionary shows the same keys as Benzinga, with no CIK. |
| 4. Has-data flag | **NOT USED.** No coverage field is documented. Not a failure, because no signal reads this data. | **NOT USED.** Same as CA0032. | **NOT USED.** Same as CA0032. |
| 5. Coverage by year | **UNVERIFIED.** Catalogue totals only: about 17,000 filers, 7,500 tickers and 500,000 filings. | **UNVERIFIED.** Catalogue totals only: about 3,000 stocks. | **UNVERIFIED.** Catalogue totals only: 850 companies. |
| 6. Real start date | **UNVERIFIED.** Catalogue: 2009 for the filings block. Observed: event dates back to 2003, for two companies only. No row counts, and no filings opened. | **UNVERIFIED.** Catalogue: 2011. | **UNVERIFIED.** Catalogue: 2008. |

**Documented lag and observed freshness are different things.** The one-day lag above is
what the catalogue declares. What we observed: the two framework queries on the SEC Filing
Events insight, for Nortek and Hostess, each reported a last data refresh of 2026-07-15.
The SEC EDGAR tearsheet shows the same date. That date applies to that insight and
tearsheet as served by the MCP. We did not check freshness for Benzinga, for the Company
Reported Actuals table, or for the raw filings block.

**Carbon Arc's own load dates are not point-in-time.** The dictionary's sample values
show the EDGAR block loaded in one full backfill on 2026-10-13. Carbon Arc's receipt date
therefore cannot date first availability. The EDGAR filing date would have to serve that
purpose, and we have not verified it on rows.

## What we did and did not act on

- **No change to the model or the 8-K features.** This pilot does not establish that
  survivorship bias is resolved. The bias stays documented as a limitation.
- **No asset is cleared for new features.** Nothing reached PASS. Benzinga and the
  Company Reported Actuals table fail on lag dating and CIK mapping in their own data
  dictionaries.
- **Next step, not done:** price a bulk EDGAR extract keyed by CIK. Then check the 27
  firms on it filing by filing, with CIK-verified identities. That would turn this
  search pilot into a coverage measurement.

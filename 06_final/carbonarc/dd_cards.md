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

| Step | Count |
|---|---|
| Companies searched in CA0032 by name | 27 |
| 8-K event series retrieved | 2 (Nortek, Hostess Brands) |
| Retrieved series with legal entity confirmed on SEC EDGAR | 2 |
| Pre-exit 8-Ks verified as documents on EDGAR (accession and URL recorded) | 2 |
| Pre-exit 8-K dates in the final 12 months matched to the EDGAR filing index | 21 (10 Nortek, 11 Hostess) |
| Companies unresolved | 25 |

This pilot does not establish that survivorship bias is resolved.

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

### Unresolved cases and access limits

- **25 companies are unresolved.** 23 returned no series in name search, Zayo has a company
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
different method.

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

## What we did and did not act on

- **No change to the model or the 8-K features.** This pilot does not establish that
  survivorship bias is resolved. The bias stays documented as a limitation.
- **No asset is cleared for new features.** Nothing reached PASS.
- **Next step, not done:** for the 25 unresolved firms, take CIKs from EDGAR and look for a
  Carbon Arc route keyed by CIK. That could be a bulk EDGAR extract, priced but not bought,
  or a support request for CIK lookup through the MCP. Then verify filing by filing as
  for the two firms here. A CA0092 card needs its tearsheet, which means asking Carbon Arc
  whether our account can see it.

# Draft request to Carbon Arc: a CIK-keyed route into CA0032 for delisted firms

Draft for the team to send from the team account. Not sent. It attaches
`dd_unresolved_ciks.csv` and quotes nothing from Carbon Arc or its sources. Before
sending, fill in the bracketed parts and remove this header.

---

**Subject:** CA0032 (SEC EDGAR): looking up delisted companies by CIK

Hello Carbon Arc team,

We are team Mont Royal Carlo in the McGill-FIAM Asset Management Hackathon 2026 finals,
using the team account registered to [team leader's name]. We are testing whether
CA0032 can supply 8-K filings for companies that left the market, since the 8-K file
supplied for the competition is missing most of them.

**What worked.** We searched your MCP by company name for 27 large US companies that
were delisted between 2015 and 2023. Two came back with an "SEC Form 8-K Filing" event
series, Hostess Brands and Nortek. We checked both against SEC EDGAR, and every 8-K date
you hold matches an EDGAR filing of the right company:

- **Hostess Brands, Inc. (CIK 1644406):** all 107 dates match.
- **Nortek, Inc. (CIK 1216596):** all 131 dates match. The only EDGAR dates missing are
  six that carry 8-K/A amendments only.

**What did not work.** The other 25 companies did not come back from name or ticker
search, although each filed 8 to 34 8-Ks in its final year as a listed company. We
attach them with their CIKs, taken from EDGAR. Zayo Group has a company entity but no
filing events. Dun & Bradstreet resolves only to the holding company that relisted in
2020, not to the company that was taken private in 2019 (CIK 1115222). The event rows we
receive carry no CIK, so we cannot work back from a CIK to your records.

**Our questions:**

1. Can CA0032 filing events, or the underlying filings block, be looked up by CIK
   through the MCP? If so, how?
2. Are filings from companies that are no longer listed held in CA0032 even when the
   company is missing from the entity search? Could you check a few of the attached
   CIKs?
3. If the MCP route is not available, is there a bulk CA0032 extract keyed by CIK? We
   would like the price and lead time, and whether its 8-K rows carry item numbers,
   accession numbers and the EDGAR acceptance time. We are not ready to commit to a
   purchase; this is to plan.
4. The SEC Filing Events data shows a last refresh of 2026-07-15, while the catalogue
   lists a one-day lag. Is that refresh date expected?
5. Is CA0092 (New Constructs ratings) available to our account? It does not appear in
   our catalogue searches.

A smaller point: in our framework queries on SEC Filing Events, start and end date
filters had no effect, and the full history came back. Is there a supported way to
limit the date range?

Thank you,
[Name], for team Mont Royal Carlo

Attachment: `dd_unresolved_ciks.csv`. It lists the 25 companies with ticker, exit month,
EDGAR name, CIK, the number of 8-Ks each filed in its final 12 months, and the date of
its last 8-K before exit.

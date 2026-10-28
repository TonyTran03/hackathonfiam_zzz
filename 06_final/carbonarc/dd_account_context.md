# Carbon Arc account context for the due-diligence pilot

Faig's earlier work (`mcp_findings_worst_shorts.md` on main) used Alex's authorised team
account. The pilot in `dd_cards.md` ran through Bohan's MCP connection, which may be
signed in to a personal account. Results are labelled by account context so they can be
compared after reconnecting.

## Context A: Bohan's MCP connection, account not confirmed

- **When:** 2026-10-28, before 15:00 Eastern.
- **Connection:** the project's HTTP MCP server at mcp.carbonarc.ai, signed in through
  the browser.
- **Covers:** every Carbon Arc result in `dd_cards.md`, `dd_verified_filings.csv` and
  `dd_slide.png` at commit 7ecd274. The SEC EDGAR checks in those files do not depend
  on the Carbon Arc account.
- **Account meters returned by billed queries:**

| Meter | Value |
|---|---|
| Daily usage before the first billed query | 4,507.56 of 20,000 |
| Daily usage after the last billed query | 4,542.15 of 20,000 |
| Balance | 15,492.44, then 15,473.32 |
| Primary balance | 0 |

The account is not confirmed. One reading is that the daily usage already stood at about
4,500 units at the start. That would fit a shared team quota after Faig's run of about
4,000 units, but it does not prove it.

## Rerun queries, with exact parameters

### Q1: previously successful (Hostess Brands 8-K events)

Tool `framework_to_insight`:

```json
{
  "entities": [{"carc_id": 26594, "representation": "company"}],
  "insight": {"insight_id": 137181},
  "events": [{"event_type": "Corporate Events", "event_category_id": 46}],
  "filters": {"location_resolution": "ww",
              "filters": {"start_date": "2022-11-01", "end_date": "2023-11-30"}},
  "question": "Dates of SEC Form 8-K filings for Hostess Brands between 2022-11-01 and 2023-11-30."
}
```

Context A result:

| Field | Value |
|---|---|
| Rows | 126: 107 dated 8-K events (event series 7622) and 19 SC-13G events (event series 7623) |
| 8-K event dates | 2015-08-19 to 2023-11-07; all 107 match EDGAR 8-K dates for CIK 1644406 |
| Date filter | Ignored: the full history came back |
| Last data refresh | 2026-07-15 |
| Price | 14.13 units |

### Q2: previously unresolved (Reynolds American 8-K event search)

Tool `search_events`:

```json
{"query": "Reynolds American SEC Form 8-K Filing", "event_type": "Corporate Events", "limit": 3}
```

Context A result: no Reynolds American series. The three hits were Wings N' Things (event
16548), Jameson Inn (8325) and Regis Corporation (12561). Free call.

### Permission probe (free, catalogue only)

| Call | Context A result |
|---|---|
| `data_library` with query "New Constructs stock ratings" | No New Constructs tearsheet (CA0092 not visible) |
| `data_library` with dataset_id "financial-filing-forms" | Visible: SEC Edgar provider, T+1, last updated 2026-07-15 |
| `data_library` with dataset_id "financial-news-and-data" | Visible: Benzinga provider, T+1, weekly |

## Context B: team account, after reconnecting

- **When:** 2026-10-28, after you signed in to the team account through `/mcp`. Claude
  saw no credentials, and none are stored in the repo.
- **Method:** the same Q1, Q2 and permission-probe calls, with the parameters above
  unchanged.

| Check | Context A | Context B | Same? |
|---|---|---|---|
| Q1 rows | 126 | 126 | Yes |
| Q1 8-K event dates | 107, from 2015-08-19 to 2023-11-07 | The same 107 dates | Yes, compared as sets |
| Q1 SC-13G rows | 19 | The same 19 dates | Yes |
| Q1 date filter | Ignored | Ignored | Yes |
| Q1 last data refresh | 2026-07-15 | 2026-07-15 | Yes |
| Q1 price | 14.13 units | 14.13 units | Yes |
| Q2 top three hits | Wings N' Things, Jameson Inn, Regis Corporation | The same three, same event IDs | Yes; still no Reynolds American series |
| New Constructs search | Not visible | Not visible | Yes |
| Financial Filing Forms tearsheet | Visible, last updated 2026-07-15 | Same | Yes |
| Financial News & Data tearsheet | Visible | Same | Yes |

| Meter after Q1 | Value |
|---|---|
| Daily usage | 5,765.98 of 20,000 |
| Balance | 14,248.15 |
| Primary balance | 0 |

**Verdict: no difference in permissions or results.** Per the plan, the full 27-firm sample
was not rerun. The Carbon Arc results in `dd_cards.md` stand for both account contexts.

**The meters cannot tell the two accounts apart.** In both contexts, the balance plus the
daily usage comes to 20,000 plus the price of the last call. So the balance is just the
day's remaining quota. Daily usage rose from 4,542 to about 5,752 while this session made
no billed calls. That fits a quota shared by the team. A shared quota would also explain
the 4,508 units already used before context A's first query. If so, context A may already
have been drawing on team quota. We cannot prove which account context A used.

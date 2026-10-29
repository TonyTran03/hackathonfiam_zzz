# Carbon Arc alt-data test: rule written before any result

**Written:** 2026-10-28 21:20 (UTC−4). Step 0 (survivorship, descriptive) had been run before this. No IC,
long-short or correlation number had been computed. Nothing below changes after seeing results.

## Inputs

- Carbon Arc: `foot_traffic_permno.csv`, `card_spend_permno.csv`, `web_traffic_permno.csv`
  (`permno`, `date` = month-end the value describes, `value`). All pulled 2026-10-28.
- Panel: `chars_final_with_names.parquet` (SHA-256 starts `797C01EBD59F7A14`). Columns used:
  `permno`, `eom`, `gics`, `prc`, `size_grp`, `ret_exc_lead1m`, `ret_12_1`.

## Signal

For each dataset at month-end t (panel `eom` = t):

    growth(t) = value(month t−1) / value(month t−13) − 1

- **Year-over-year**, to remove seasonality.
- **Month t−1 is the latest data allowed.** That covers the publication lag (T+1 to T+5 days), plus a
  safety month.
- **Only rows on live stock-months.** The permno must have a panel row at t, at t−1 and at t−13 (the
  last two are the months the Carbon Arc values describe).
- **Drop the stock-month** if the denominator is zero or missing, or the numerator is missing.

## Universe each month t

- The name has a signal.
- `prc` ≥ $5 at t.
- `size_grp` at t is small, large or mega: micro and nano are dropped, and so are missing values.
- The name has a 2-digit GICS sector (`gics[:2]`).
- `ret_exc_lead1m` is not missing. Names without a next-month return can't be scored.

## Ranking

- Within each 2-digit GICS sector and month: rank the growth, then z-score the ranks (subtract
  the mean, divide by the standard deviation).
- Drop sectors with fewer than 5 names that month, and drop the whole month if any test below has
  fewer than 2 sectors left.

## Target

`ret_exc_lead1m` on the row dated t: the excess return earned in month t+1. It is already shifted
forward and is not shifted again.

## Tests (per dataset, per window)

a. **Monthly Spearman IC** between the sector z-score and `ret_exc_lead1m`, across all names left
   that month. Report:
   - the mean;
   - a Newey-West t-stat on the monthly IC series (3 lags, Bartlett weights);
   - the hit rate (share of months with IC > 0).
b. **Long-short within each sector:**
   - Take the equal-weighted mean return of the top third minus the bottom third. Each third is
     floor(n/3) names, ranked by the signal.
   - Average across sectors, weighting each sector by its name count that month.
   - Report the monthly mean, the annualised Sharpe (mean / sd × √12) and the t-stat
     (mean / (sd/√months)).

Also reported: months, average names per month, and sectors covered (distinct sectors used at
least once).

## Windows (by the month the return is earned)

- **Design:** first available month through returns of 2020-12 (signal months ≤ 2020-11).
- **Test:** returns 2021-01 to 2026-08 (signal months 2020-12 to 2026-07). Reported whatever it
  shows, with per-year results by return year.
- Expected:
  - foot traffic and card spend: first signal 2020-02, so about 10 design months
    (returns 2020-03 to 2020-12), all during COVID, which is too short to decide anything;
  - web traffic: starts 2020-06, so the first signal is 2021-07 and there is no design window.

## Status (set in advance)

| Dataset | Status | Why |
|---|---|---|
| Foot traffic | **Primary test** | |
| Card spend | Descriptive only | Vendor documents monthly restatement, and our checks found breaks |
| Web traffic | Descriptive only | No design window |

All three are reported. Nothing changes after seeing results: no tuning, one rule per dataset.

## New-information check (all three)

- Each month, compute the cross-sectional Spearman correlation between each pair of
  sector z-scored signals, on the names they share, and between each signal and momentum.
- **Momentum** = `ret_12_1` (the stock's own return from month t−12 to t−1), z-scored within
  sector on the same universe as the signal.
- Report the average over months with at least 20 shared names, and the number of months used.
- Computed over the test window, and over all months.

## Outputs

- `RESULTS.md`: Step 0 counts, tables, per-year results, correlations, caveats, and a 3-sentence
  summary.
- Charts: cumulative IC and cumulative long-short return (running sum of monthly values), one line
  per dataset.
- Aggregates and statistics only. No raw Carbon Arc value is written to any output file.

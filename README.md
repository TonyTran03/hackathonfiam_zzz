# FIAM pipeline — team handoff

## Get this branch

Already cloned the repo? Save/commit your own changes first, then:

```bash
git fetch origin
git switch --track origin/simple-pipeline-handoff
```

If the branch already exists locally, use `git switch simple-pipeline-handoff`.
For a new checkout:

```bash
git clone --branch simple-pipeline-handoff https://github.com/TonyTran03/hackathonfiam_zzz.git
```

In VS Code, the equivalent is **Source Control → Fetch**, then select
`origin/simple-pipeline-handoff` from the branch picker.

## One-time setup

Use Python 3.12 and install the root `requirements.txt` in your selected Python environment.
For example: `python -m pip install -r requirements.txt`.
Copy the organizers' **chars_final_with_names.parquet** into **data/**.
Alternatively, `FIAM_DATA_DIR` can point to the folder containing that file.
The 413MB dataset is intentionally not uploaded to Git.

**Saved forecasts are included** under `prediction/saved_forecasts/`; you do not
need to train models to start testing portfolio ideas. Outcomes are excluded from
that shared forecast file. Its manifest and training choices document the source.
The feature list and market benchmark snapshots are included too.

## Your normal workflow — editor Run button, no GUI or notebook

1. Open **sizing/optimizer/** (or **sizing/price_only/** for the deliberately naive reference).
2. Edit the relevant step in that same folder:

   | File | What you change |
   |---|---|
   | `features.py` | Add new input columns; currently a pass-through |
   | `ranking.py` | Blend signals, residualize and smooth scores |
   | `selection.py` | Eligibility and which stocks become long/short candidates |
   | `constraints.py` | Allocation objective and weight/exposure limits |

3. Open **main.py in that folder** and click your editor's **Run Python File** button.
4. For the optimizer, open **sizing/constraint.md** for the comparison table.
   Edit **sizing/constraint.csv** to change trials. Each row is a trial; columns named
   after `Settings` fields override the defaults in `optimizer/constraints.py`.
   Blank cells inherit those defaults. Keep `trial` names unique. Other columns are
   refreshed results. Initial trials compare baseline, a 15% estimated annual
   volatility ceiling, and a 150% gross ceiling, with identical ranking/candidates.

The optimizer refreshes only `constraint.csv` and `constraint.md` in place.
The table shows what changed, annual volatility, IR, realized beta, maximum
drawdown, net CAGR and average monthly one-way turnover.
It creates no trial or numbered run folders. Existing historical outputs are preserved.
The price-only runner still uses its existing numbered reports. `sizing/comparison.csv` lists
the latest successful run per experiment, forecast and time window. Compare
identical forecasts and dates. There is no root runner.
Set `MAX_MONTHS = 2` for an execution check; leave it `None` for the full 68 months.

## Try a new idea

The optimizer now defaults to the same eligibility screen as `beta_matched`:
price >=$5, excluding nano/micro-cap stocks, with market cap >=$500m for shorts.
Run `python sizing/optimizer/compare_screened.py` to compare the 84 previously
declared optimizer settings against beta-matched sizing on identical candidates.
Use `--resume` after interruption; it verifies input/source consistency and skips
completed or failed trials. Read `sizing/screened_comparison.md` for results and
`screened_vs_unscreened.csv` for each setting's before/after screen comparison.
`screened_monthly.csv`, `screened_summary.csv`, `screened_periods.csv`,
`screened_metadata.json`, and `screened_failures.json` retain diagnostics.
The earlier unscreened editable table is preserved in `constraint_unscreened.csv`
and `constraint_unscreened.md`; the earlier `sweep_*` results remain unscreened.
The screen is an eligibility proxy; liquidity/capacity at fund size is not certified.
For the 75%-gross portfolio, `python sizing/optimizer/position_caps.py` compares
2.5%, 2%, 1.5%, and 1% starting position caps and saves monthly weight-drift checks
in `sizing/position_caps.md`. The tested variants are also present in the editable
comparison CSV. The 2% variant is `g075_cap0.020`; its observed monthly closes stay
below 5%, but daily compliance still requires daily-return data and checks.

For a broad allocation comparison, run `python sizing/optimizer/sweep.py`.
It tests 58 configurations with identical ranking and candidates: gross and volatility
budgets, position caps, risk/cost penalties, beta/sector/size bounds, covariance
windows, turnover limits, combined settings, and higher trading-cost assumptions.
It refreshes `sizing/constraint.csv` and `sizing/constraint.md` after completion.
Four worker processes evaluate independent trials. `sweep_monthly.csv` is checkpointed
after each completed trial; `sweep_summary.csv` contains
full-period diagnostics and `sweep_periods.csv` compares 2021–2023 with 2024 onward.
`sweep_failures.json` records failed trials without relaxing their constraints;
failed trials are excluded from the final comparison. `sweep_metadata.json`
records settings and stage sources. These period comparisons are descriptive,
not an untouched test set. Restarting the broad command reruns it from the beginning.
After the broad pass completes, `python sizing/optimizer/sweep.py --refine`
appends 26 combinations of lower risk penalties with position caps, gross limits,
volatility budgets, and sector bounds. It preserves the broad-pass observations
in the same comparison files. Repeating refinement resumes unfinished trials;
it checks saved settings, forecast path, and stage sources before resuming.
In editable CSV settings, blank means inherit the default; `none` explicitly
disables an optional bound (including the estimated-beta bound).

Add a row to **sizing/constraint.csv** and edit its allocation settings. Run
**sizing/optimizer/main.py** again. To test a ranking change, edit the optimizer's
ranking step; all rows in the CSV deliberately share the same ranking and selection.
`annual_vol_limit` is a decimal annual volatility budget (0.15 = 15%), using
monthly covariance and variance <= annual_vol_limit squared / 12. Realized
volatility may exceed this forecast budget. Infeasible trials stop with their
name and month; constraints are never automatically relaxed.

## Change prediction models

Edit **prediction/predict.py** and run that file directly with the editor's Run button.
Then run your experiment's `main.py`. The experiment reuses the latest completed full training export,
or the included saved forecasts on a fresh checkout. `FORECAST` chooses the
output column. Each experiment in one run uses the same pinned forecast file.
`FEATURES.md` specifies future Carbon Arc inputs; they are not active or required.

## Verification

Constraint violations/infeasibility stop a backtest, rather than
silently relaxing rules. Each output records its exact step sources as metadata.

## Important limits

These are research backtests, not a final mandate certification. The price-only
reference keeps adjusted ranking, only the $5 price filter, and equal weights.
The optimizer enforces gross/net/position limits and holds 300 names with a
0.1% minimum allocation per selected name (a research choice). Estimated market
beta matching is enabled by default (`beta_limit = 0.0`). Sector, size and
turnover bounds remain optional. Estimated matching does not guarantee zero realized beta.
Formation-day short eligibility, delayed execution, daily reporting and capacity
analysis remain incomplete. The daily dsf_mini_from_2014.csv has not been located
and is not included. Missing realized returns are marked at zero and reported;
borrow/impact are omitted. The benchmark is TB3MS/1200 + 4%/12; reported one-way
turnover is half buys plus sells. See **Final challenge instructions.pdf**.

Old code and reports remain in Git history/on the original main branch. This
branch replaces the active layout; local retired backups are not part of the clone.

The reference runners retain numbered `outputs` folders. Optimizer constraint trials use the shared CSV and refresh their comparison files in place.

## Beta-matched inverse-volatility reference

Run **sizing/beta_matched/main.py** to keep the earlier capped inverse-volatility
portfolio as a third experiment. It uses 150 names per side, the >=$5/no-nano-or-micro
screen, the $500m month-end short floor, 3-observation score smoothing, a 2.5x
retention buffer, a 1.5% final cap, and long/short notionals matched on estimated
beta. It does not use realized-beta feedback. Caps can leave a small residual
estimated beta; realized beta is not guaranteed zero.

Matching forecasts and dates appear together on the charts: **blue = beta_matched**,
**orange = optimizer**, **purple = price_only**, green dashed = cash + 4%.
Outputs use the same numbered folders and constraints.md records.

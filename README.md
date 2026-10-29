# FIAM pipeline — team handoff

## Get this branch

Already cloned the repo? Save/commit your own changes first, then:

```bash
git fetch origin
git switch --track origin/codex/simple-pipeline-handoff
```

If the branch already exists locally, use `git switch codex/simple-pipeline-handoff`.
For a new checkout:

```bash
git clone --branch codex/simple-pipeline-handoff https://github.com/TonyTran03/hackathonfiam_zzz.git
```

In VS Code, the equivalent is **Source Control → Fetch**, then select
`origin/codex/simple-pipeline-handoff` from the branch picker.

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
4. Open **outputs → run timestamp → report.html** in that folder.

To run both experiments and compare them, use **root main.py** instead. Settings
are ordinary variables at its top. The final printed table compares exactly
those runs. `sizing/comparison.csv` also lists the latest successful run per
experiment, forecast and time window. Compare identical forecasts and dates.
Set `MAX_MONTHS = 2` for an execution check; leave it `None` for the full 68 months.

## Try a new idea

Copy only the five Python files from `sizing/optimizer/` into a new folder under
`sizing/` — **not outputs or __pycache__**. Edit its step files and run its main.py.
It detects its folder name automatically. To compare it from root main.py, add
that name to `EXPERIMENTS`.

## Change prediction models

Edit **prediction/predict.py**. Set `RETRAIN_PREDICTIONS = True` in root main.py
and run it. Otherwise the runner reuses the latest completed full training export,
or the included saved forecasts on a fresh checkout. `FORECAST` chooses the
output column. Each experiment in one run uses the same pinned forecast file.
`FEATURES.md` specifies future Carbon Arc inputs; they are not active or required.

## Verification

The checks live in **sizing/test_sizing.py**; run that file with the same editor
Run button. Constraint violations/infeasibility stop a backtest, rather than
silently relaxing rules. Each output records its exact step sources as metadata.

## Important limits

These are research backtests, not a final mandate certification. The price-only
reference keeps adjusted ranking, only the $5 price filter, and equal weights.
The optimizer enforces gross/net/position limits and holds 300 names with a
0.1% minimum allocation per selected name (a research choice). Optional beta,
sector, size and turnover bounds are editable.
Formation-day short eligibility, delayed execution, daily reporting and capacity
analysis remain incomplete. The daily dsf_mini_from_2014.csv has not been located
and is not included. Missing realized returns are marked at zero and reported;
borrow/impact are omitted. The benchmark is TB3MS/1200 + 4%/12; reported one-way
turnover is half buys plus sells. See **Final challenge instructions.pdf**.

Old code and reports remain in Git history/on the original main branch. This
branch replaces the active layout; local retired backups are not part of the clone.

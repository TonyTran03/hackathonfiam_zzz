"""Broad, reproducible allocation sweep; run directly, then compare constraint.md.

Completed-trial checkpoints survive interruption. Failed trials are never relaxed.
Ranking and candidates stay fixed so allocation comparisons remain comparable.
"""
from dataclasses import replace, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json
import os
import sys
import time

# Keep each worker from creating its own large BLAS thread pool.
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main as M


def save_csv(frame, path):
    """Replace checkpoints atomically; tolerate short Windows file locks."""
    temporary = path.with_suffix('.tmp.csv')
    frame.to_csv(temporary, index=False)
    for attempt in range(10):
        try:
            os.replace(temporary, path)
            return
        except OSError:
            if attempt == 9:
                raise
            time.sleep(0.25)


def initialize_worker(schedule, history, cash, market):
    global WORKER_INPUTS, WORKER_MODULE
    WORKER_INPUTS = schedule, history, cash, market
    WORKER_MODULE = M.E.load_stages('optimizer')['constraints']


def evaluate_trial(name, overrides):
    E = M.E
    schedule, history, cash, market = WORKER_INPUTS
    setting = replace(WORKER_MODULE.SETTINGS, **overrides)
    previous = pd.Series(dtype=float)
    rows = []
    for month, g in schedule:
        try:
            cov = E.covariance_for(history, month, g, setting)[0]
            inputs = E.sizing_inputs(g, previous, setting)
            weights, audit, status = E.solve_weights(g, cov, inputs, setting,
                WORKER_MODULE.build_constraints, WORKER_MODULE.build_objective)
            if month not in cash.index or not np.isfinite(cash.loc[month]):
                raise ValueError('Missing cash return')
            row, previous, _, _ = E.account(month, g, weights, previous,
                history.loc[month], float(cash.loc[month]), cov, setting)
            row.update(method=name, market_return=float(market.get(month, np.nan)),
                       max_constraint_violation=max(x['max_violation'] for x in audit))
            rows.append(row)
        except (ValueError, E.cp.error.SolverError) as exc:
            return name, rows, dict(month=month, error=str(exc))
    return name, rows, None


def configurations():
    trials = [('baseline', {})]
    axes = {
        'gross_limit': [0.75, 1.0, 1.25, 1.5, 1.75],
        'annual_vol_limit': [0.05, 0.075, 0.10, 0.125, 0.15, 0.20],
        'position_limit': [0.005, 0.01, 0.015, 0.025],
        'risk_penalty': [10., 30., 300., 1000., 3000.],
        'cost_penalty': [10., 50., 100., 300.],
        'beta_limit': [0.05, 0.10, 0.20, None],
        'sector_limit': [0., 0.025, 0.05, 0.10],
        'size_limit': [0., 0.05, 0.10],
        'covariance_months': [12, 24, 60],
        'turnover_limit': [0.75, 1.0, 1.5, 2.0],
    }
    for field, values in axes.items():
        for value in values:
            trials.append((f'{field}_{value}', {field: value}))
    for gross in [1.0, 1.5, 2.0]:
        for cap in [0.01, 0.025]:
            for cost in [10., 100.]:
                trials.append((f'mix_g{gross}_p{cap}_c{cost}', dict(
                    gross_limit=gross, position_limit=cap, cost_penalty=cost,
                    sector_limit=0.05, size_limit=0.10, annual_vol_limit=0.10)))
    for cost in [35., 50., 100.]:
        trials.append((f'cost_stress_{cost}bps', {'trading_cost_bps': cost}))
    return trials


def refinement_configurations():
    trials = []
    for risk in [3., 10., 30.]:
        for cap in [0.015, 0.025]:
            for gross in [1.5, 2.0]:
                trials.append((f'refine_r{risk}_p{cap}_g{gross}', dict(
                    risk_penalty=risk, position_limit=cap, gross_limit=gross)))
    for risk in [10., 30.]:
        for cap in [0.015, 0.025]:
            for vol in [0.10, 0.125, 0.15]:
                trials.append((f'refine_r{risk}_p{cap}_v{vol}', dict(
                    risk_penalty=risk, position_limit=cap, annual_vol_limit=vol)))
    for risk in [10., 30.]:
        trials.append((f'refine_r{risk}_sector', dict(risk_penalty=risk,
                       position_limit=0.025, sector_limit=0.05, cost_penalty=10.)))
    return trials


def run(refine=False):
    E = M.E
    stages = E.load_stages('optimizer')
    module = stages['constraints']
    new_trials = refinement_configurations() if refine else configurations()
    trials = new_trials
    failed, rows, descriptions = {}, [], {}
    if refine:
        metadata = json.loads((E.HERE / 'sweep_metadata.json').read_text())
        if metadata['forecast'] != M.FORECAST:
            raise ValueError('Refinement must use the same forecast.')
        old_trials = list(metadata['settings'].items())
        known = dict(old_trials)
        for name, overrides in new_trials:
            if name in known and known[name] != asdict(replace(module.SETTINGS, **overrides)):
                raise ValueError(f'{name}: saved settings differ; start a fresh sweep.')
        trials = old_trials + [(n, o) for n, o in new_trials if n not in known]
        rows = pd.read_csv(E.HERE / 'sweep_monthly.csv').to_dict('records')
        failed = json.loads((E.HERE / 'sweep_failures.json').read_text())
        old_summary = pd.read_csv(E.HERE / 'sweep_summary.csv')
        descriptions = old_summary.set_index('trial').what_changed.to_dict()
        descriptions.update({name: str(overrides)
                             for name, overrides in refinement_configurations()})
    settings = [replace(module.SETTINGS, **overrides) for _, overrides in trials]
    for setting in settings:
        module.validate(setting)
        stages['selection'].validate(setting)
    prediction_path = E.resolve_predictions(None)
    scores, history, cash = E.load_inputs(prediction_path, M.FORECAST, E.C.CHARS_PARQUET,
                                         module.SETTINGS, stages=stages)
    schedule = list(stages['selection'].candidate_schedule(scores, module.SETTINGS))
    if refine:
        for step, source in metadata['step_sources'].items():
            if source != (Path(__file__).parent / f'{step}.py').read_text():
                raise ValueError(f'{step}: source changed; start a fresh sweep.')
        saved = pd.DataFrame(rows)
        completed = set(saved.groupby('method').filter(
            lambda g: len(g) == len(schedule) and g.target_month.tolist() ==
            [month for month, _ in schedule]).method)
        new_trials = [(n, o) for n, o in new_trials if n not in completed and n not in failed]
        pending = set(dict(new_trials))
        rows = [r for r in rows if r['method'] not in pending]
        print(f'Resuming: {len(new_trials)} pending refinement trials', flush=True)
    market = E.benchmark_returns()
    if refine and str(prediction_path) != metadata['predictions']:
        raise ValueError('Refinement must use the same prediction file.')
    (E.HERE / 'sweep_metadata.json').write_text(json.dumps(dict(
        forecast=M.FORECAST, predictions=str(prediction_path),
        settings={name: asdict(s) for (name, _), s in zip(trials, settings)},
        step_sources={name: (Path(__file__).parent / f'{name}.py').read_text()
                      for name in stages}), indent=2), encoding='utf-8')
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=4, initializer=initialize_worker,
                             initargs=(schedule, history, cash, market)) as pool:
        futures = [pool.submit(evaluate_trial, name, overrides) for name, overrides in new_trials]
        for finished, future in enumerate(as_completed(futures), 1):
            name, trial_rows, error = future.result()
            rows.extend(trial_rows)
            if error:
                failed[name] = error
                print(f'FAILED {name}: {error}', flush=True)
            save_csv(pd.DataFrame(rows), E.HERE / 'sweep_monthly.csv')
            (E.HERE / 'sweep_failures.json').write_text(json.dumps(failed, indent=2))
            print(f'{finished}/{len(new_trials)} trials finished: {name}; '
                  f'{time.monotonic()-started:.0f}s elapsed', flush=True)
    monthly = pd.concat([E.attach_final_reporting(g) for _, g in
                         pd.DataFrame(rows).groupby('method', sort=False)], ignore_index=True)
    save_csv(monthly, E.HERE / 'sweep_monthly.csv')
    complete = monthly[~monthly.method.isin(failed)]
    summary = E.summarize(complete).rename(columns={'method': 'trial'})
    config = pd.DataFrame([dict(trial=name, what_changed=descriptions.get(name,
                               str(overrides) if overrides else 'Current optimizer'), **asdict(s))
                           for (name, overrides), s in zip(trials, settings) if name not in failed])
    result = config.merge(summary, on='trial', validate='one_to_one')
    result = result.sort_values('information_ratio', ascending=False)
    result.to_csv(E.HERE / 'sweep_summary.csv', index=False)
    split_rows = []
    for label, subset in [('2021_2023', complete[complete.target_month < '2024-01']),
                          ('2024_2026', complete[complete.target_month >= '2024-01'])]:
        part = E.summarize(subset).rename(columns={'method': 'trial'})
        part['period'] = label
        split_rows.append(part)
    pd.concat(split_rows).to_csv(E.HERE / 'sweep_periods.csv', index=False)
    # Blank CSV cells inherit defaults; explicit 'none' disables optional bounds.
    for field in ['beta_limit', 'sector_limit', 'size_limit', 'turnover_limit',
                  'annual_vol_limit']:
        result[field] = result[field].astype(object).where(result[field].notna(), 'none')
    M.write_table(result, schedule[0][0], schedule[-1][0], M.FORECAST)


if __name__ == '__main__':
    run(refine='--refine' in sys.argv)

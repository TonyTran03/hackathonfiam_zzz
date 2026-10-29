"""Compare smaller formation caps at 75% gross and audit month-end weight drift.

This uses monthly data. A month-end pass is not proof of daily compliance.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep as S
import numpy as np
import pandas as pd


def evaluate(name, overrides):
    E = S.M.E
    schedule, history, cash, market = S.WORKER_INPUTS
    module = S.WORKER_MODULE
    setting = replace(module.SETTINGS, **overrides)
    previous = pd.Series(dtype=float)
    rows, holdings = [], []
    for month, g in schedule:
        cov = E.covariance_for(history, month, g, setting)[0]
        inputs = E.sizing_inputs(g, previous, setting)
        w, audit, status = E.solve_weights(g, cov, inputs, setting,
                                         module.build_constraints, module.build_objective)
        row, previous, raw, _ = E.account(month, g, w, previous,
            history.loc[month], float(cash.loc[month]), cov, setting)
        row.update(method=name, market_return=float(market.loc[month]),
                   monthend_max_weight=float(previous.abs().max()),
                   monthend_gross=float(previous.abs().sum()),
                   monthend_net=float(previous.sum()),
                   monthend_names_over_5pct=int((previous.abs() > .05 + 1e-6).sum()),
                   max_constraint_violation=max(c['max_violation'] for c in audit))
        rows.append(row)
        h = g[['ticker', 'company_name', 'sector', 'side', 'prc', 'me', 'size_grp']].copy()
        h['weight'], h['monthend_weight'], h['raw_return'] = w, previous, raw
        h['target_month'], h['trial'] = month, name
        holdings.append(h.reset_index())
    return name, rows, pd.concat(holdings, ignore_index=True)


def run():
    E = S.M.E
    meta = json.loads((E.HERE / 'screened_metadata.json').read_text())
    stages = E.load_stages('optimizer')
    module = stages['constraints']
    scores, history, cash = E.load_inputs(Path(meta['predictions']), meta['forecast'],
        E.C.CHARS_PARQUET, module.SETTINGS, stages=stages)
    schedule = list(stages['selection'].candidate_schedule(scores, module.SETTINGS))
    market = E.benchmark_returns()
    trials = [(f'g075_cap{cap:.3f}', dict(gross_limit=.75, position_limit=cap))
              for cap in [.025, .020, .015, .010]]
    for _, overrides in trials:
        module.validate(replace(module.SETTINGS, **overrides))
    metadata = dict(forecast=meta['forecast'], predictions=meta['predictions'],
        settings={name: asdict(replace(module.SETTINGS, **overrides)) for name, overrides in trials},
        stages={step: (Path(__file__).parent / f'{step}.py').read_text() for step in stages},
        engine_source=(E.HERE / '_engine.py').read_text(), runner_source=Path(__file__).read_text(),
        limitation='Monthly observations only; intramonth compliance is not certified.')
    (E.HERE / 'position_caps_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    rows, held = [], []
    with ProcessPoolExecutor(max_workers=4, initializer=S.initialize_worker,
                             initargs=(schedule, history, cash, market)) as pool:
        futures = [pool.submit(evaluate, name, overrides) for name, overrides in trials]
        for future in as_completed(futures):
            name, data, holdings = future.result()
            rows.extend(data)
            held.append(holdings)
            S.save_csv(pd.DataFrame(rows), E.HERE / 'position_caps_monthly.csv')
            print(f'{name}: all {len(data)} months complete', flush=True)
    monthly = pd.concat([E.attach_final_reporting(g) for _, g in
                        pd.DataFrame(rows).groupby('method')], ignore_index=True)
    assert monthly.groupby('method').size().eq(68).all()
    assert monthly.max_constraint_violation.max() <= 1e-6
    S.save_csv(monthly, E.HERE / 'position_caps_monthly.csv')
    pd.concat(held, ignore_index=True).to_parquet(E.HERE / 'position_caps_holdings.parquet', index=False)
    summary = E.summarize(monthly).rename(columns={'method': 'trial'})
    diagnostics = monthly.groupby('method').agg(
        max_monthend_weight=('monthend_max_weight', 'max'),
        months_over_5pct=('monthend_names_over_5pct', lambda x: int((x > 0).sum())))
    summary = summary.merge(diagnostics, left_on='trial', right_index=True)
    configs = pd.DataFrame([dict(trial=name, **asdict(replace(module.SETTINGS, **overrides)))
                            for name, overrides in trials])
    summary = summary.merge(configs, on='trial', validate='one_to_one')
    S.save_csv(summary, E.HERE / 'position_caps_summary.csv')
    print(summary[['trial', 'cagr', 'annual_vol', 'information_ratio', 'realized_market_beta',
                   'max_drawdown', 'max_monthend_weight', 'months_over_5pct']].to_string(index=False))
    lines = ['# Smaller position caps at 75% gross', '',
             'Same screened candidates, forecasts, dates, and cost model. Only the formation '
             'position cap changes. No intramonth trading or future information enters sizing.', '',
             '| Starting cap | CAGR | Volatility | IR | Beta | Max drawdown | Largest month-end position | Month-ends over 5% |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    original = pd.read_csv(E.HERE / 'screened_summary.csv').set_index('trial').loc['gross_limit_0.75']
    drift = pd.read_csv(E.HERE / 'screened_075_mandate_drift.csv')
    lines.append(f'| 5.0% (original) | {original.cagr:.1%} | {original.annual_vol:.1%} | '
                 f'{original.information_ratio:.2f} | {original.realized_market_beta:.2f} | '
                 f'{original.max_drawdown:.1%} | {drift.monthend_max_weight.max():.2%} | '
                 f'{int((drift.monthend_names_over_5pct > 0).sum())} |')
    for _, r in summary.sort_values('position_limit', ascending=False).iterrows():
        lines.append(f'| {r.position_limit:.1%} | {r.cagr:.1%} | {r.annual_vol:.1%} | '
                     f'{r.information_ratio:.2f} | {r.realized_market_beta:.2f} | '
                     f'{r.max_drawdown:.1%} | {r.max_monthend_weight:.2%} | {r.months_over_5pct} |')
    lines += ['', 'A pass here means no observed monthly closing breach. Daily returns are '
              'needed to detect intramonth breaches and implement a causal risk overlay. '
              'Missing returns remain marked at zero; borrow and market impact remain omitted. '
              'Do not describe these rows as fully mandate-certified. These are retrospective tests.']
    (E.HERE / 'position_caps.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    run()

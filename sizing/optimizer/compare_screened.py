"""Apply the same screen to the 84 previously declared trials and beta-matched rule.

Run directly. Results go to sizing/screened_*; previous sweep files are preserved.
No settings are selected or adapted using the screened results.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep as S
import numpy as np
import pandas as pd


def beta_matched_reference(schedule, history, cash, market):
    E = S.M.E
    module = E.load_stages('beta_matched')['constraints']
    setting = module.SETTINGS
    previous = pd.Series(dtype=float)
    rows = []
    for month, g in schedule:
        cov = E.covariance_for(history, month, g, setting)[0]
        inputs = E.sizing_inputs(g, previous, setting)
        weights = module.size_positions(g, setting)
        variable = E.cp.Variable(len(g), value=weights.to_numpy())
        violation = max(float(np.max(rule.violation())) for rule in
                        module.build_constraints(variable, inputs, setting).values())
        if violation > setting.numerical_tolerance:
            raise ValueError(f'{month}: beta-matched constraint violation {violation}')
        row, previous, _, _ = E.account(month, g, weights, previous,
            history.loc[month], float(cash.loc[month]), cov, setting)
        row.update(method='beta_matched', market_return=float(market.loc[month]),
                   max_constraint_violation=violation)
        rows.append(row)
    return rows


def write_report(summary, paired, failed, months):
    E = S.M.E
    columns = ['trial', 'cagr', 'annual_vol', 'information_ratio',
               'realized_market_beta', 'max_drawdown', 'mean_one_way_turnover']
    table = summary[columns].copy()
    table.columns = ['Configuration', 'CAGR', 'Volatility', 'IR', 'Beta',
                     'Max drawdown', 'Monthly turnover']
    for col in ['CAGR', 'Volatility', 'Max drawdown', 'Monthly turnover']:
        table[col] = table[col].map(lambda x: f'{x:.1%}')
    for col in ['IR', 'Beta']:
        table[col] = table[col].map(lambda x: f'{x:.2f}')
    lines = ['# Screened portfolio comparison', '',
        f'{months[0]} to {months[-1]} · {S.M.FORECAST} · {len(months)} months', '',
        'Price >=$5, excluding nano/micro-cap stocks; short market cap >=$500m. '
        'Identical rankings and candidates for all configurations. '
        '84 pre-existing optimizer settings plus the beta-matched reference; no new tuning.', '',
        f'{len(summary)} completed; {len(failed)} failed. Failed histories are excluded from rankings.', '',
        '## Read this comparison first', '',
        '| ' + ' | '.join(table.columns) + ' |',
        '| ' + ' | '.join(['---'] * len(table.columns)) + ' |']
    shortlist = [('Beta-matched reference', 'beta_matched'),
                 ('Optimizer with the same 1.5% position cap', 'position_limit_0.015'),
                 ('Optimizer at 75% gross (5% position cap)', 'gross_limit_0.75'),
                 ('Screened default optimizer', 'baseline'),
                 ('Previous unscreened winner, now screened', 'refine_r30.0_sector'),
                 ('Highest screened IR', summary.iloc[0].trial)]
    lower_risk = summary[(summary.annual_vol <= 0.15) & (summary.trial != 'beta_matched')]
    if not lower_risk.empty:
        shortlist.append(('Highest IR with realized volatility <=15%', lower_risk.iloc[0].trial))
    indexed = table.set_index('Configuration')
    for label, name in shortlist:
        if name in indexed.index:
            lines.append('| ' + ' | '.join([f'{label} (`{name}`)'] +
                         indexed.loc[name].astype(str).tolist()) + ' |')
        else:
            lines.append(f'\n{name}: failed; see screened_failures.json.\n')
    lines += ['', '## Effect of applying the screen', '',
              '| Configuration | CAGR before | CAGR screened | IR before | IR screened |',
              '| --- | --- | --- | --- | --- |']
    for name in ['baseline', 'refine_r30.0_sector']:
        match = paired[paired.trial == name]
        if not match.empty:
            r = match.iloc[0]
            lines.append(f'| {name} | {r.cagr_unscreened:.1%} | {r.cagr_screened:.1%} | '
                         f'{r.information_ratio_unscreened:.2f} | {r.information_ratio_screened:.2f} |')
    lines += ['', '## All completed configurations', '',
              '| ' + ' | '.join(table.columns) + ' |',
              '| ' + ' | '.join(['---'] * len(table.columns)) + ' |']
    lines.extend('| ' + ' | '.join(row) + ' |' for row in table.astype(str).values.tolist())
    lines += ['', 'The beta-matched reference uses a 1.5% position cap; optimizer caps and '
              'other settings are recorded per trial in screened_summary.csv. Optimizer '
              'trials require 0.1% minimum positions; the reference retains its original '
              'inverse-volatility sizing without this floor.', '',
              'Returns include modeled trading costs. The baseline uses 20 bps on buys plus sells; '
              'the three cost-stress trials use their declared higher charge. Borrow and market '
              'impact are omitted. The screen is an eligibility proxy, not a capacity guarantee. '
              'IR is versus cash +4%; beta is realized against S&P 500 price returns.', '',
              'screened_vs_unscreened.csv pairs each optimizer setting before and after the '
              'screen. Both rankings and candidates change when screening is applied. '
              'These are retrospective comparisons on previously examined years.']
    (E.HERE / 'screened_comparison.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def run():
    E = S.M.E
    stages = E.load_stages('optimizer')
    reference_stages = E.load_stages('beta_matched')
    for step in ['features', 'ranking', 'selection']:
        assert (E.HERE / 'optimizer' / f'{step}.py').read_bytes() == (
            E.HERE / 'beta_matched' / f'{step}.py').read_bytes(), f'{step} must match reference'
    trials = S.configurations() + S.refinement_configurations()
    module = stages['constraints']
    settings = {name: replace(module.SETTINGS, **overrides) for name, overrides in trials}
    for setting in settings.values():
        module.validate(setting)
        stages['selection'].validate(setting)
    original = json.loads((E.HERE / 'sweep_metadata.json').read_text())
    prediction_path = Path(original['predictions'])
    assert original['forecast'] == S.M.FORECAST
    reference_run = json.loads((E.HERE / 'beta_matched/outputs/1/run.json').read_text())
    assert Path(reference_run['predictions']).resolve() == prediction_path.resolve()
    scores, history, cash = E.load_inputs(prediction_path, S.M.FORECAST,
                                         E.C.CHARS_PARQUET, module.SETTINGS, stages=stages)
    schedule = list(stages['selection'].candidate_schedule(scores, module.SETTINGS))
    months = [month for month, _ in schedule]
    assert months == pd.period_range('2021-01', '2026-08', freq='M').astype(str).tolist()
    for _, g in schedule:
        assert (g.prc.abs() >= 5).all()
        assert not g.size_grp.isin(['nano', 'micro']).any()
        assert (g.loc[g.side < 0, 'me'] >= 500).all()
    market = E.benchmark_returns()
    metadata = dict(forecast=S.M.FORECAST, predictions=str(prediction_path), months=months,
        screen=dict(min_price=5, excluded_sizes=['nano', 'micro'], short_min_market_cap_musd=500),
        settings={name: asdict(setting) for name, setting in settings.items()},
        reference_settings=asdict(reference_stages['constraints'].SETTINGS),
        step_sources={step: (Path(__file__).parent / f'{step}.py').read_text()
                      for step in stages}, engine_source=(E.HERE / '_engine.py').read_text(),
        runner_source=Path(__file__).read_text(),
        prediction_sha256=hashlib.sha256(prediction_path.read_bytes()).hexdigest())
    resume = '--resume' in sys.argv
    if resume:
        saved_metadata = json.loads((E.HERE / 'screened_metadata.json').read_text())
        for field in ['forecast', 'prediction_sha256', 'settings', 'reference_settings',
                      'step_sources', 'engine_source', 'months', 'screen']:
            if saved_metadata[field] != metadata[field]:
                raise ValueError(f'{field} changed; cannot resume this comparison')
    (E.HERE / 'screened_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    rows = beta_matched_reference(schedule, history, cash, market)
    reference = E.summarize(E.attach_final_reporting(pd.DataFrame(rows))).iloc[0]
    recorded = pd.read_csv(E.HERE / 'beta_matched/outputs/1/summary.csv').iloc[0]
    for field in ['cagr', 'annual_vol', 'information_ratio', 'realized_market_beta']:
        assert np.isclose(reference[field], recorded[field], atol=1e-7), field
    print('Beta-matched reference reproduced; starting 84 screened optimizer trials', flush=True)
    failed = {}
    pending = trials
    if resume:
        checkpoint = pd.read_csv(E.HERE / 'screened_monthly.csv')
        failed = json.loads((E.HERE / 'screened_failures.json').read_text())
        completed = set(checkpoint.groupby('method').filter(lambda g:
            g.target_month.tolist() == months).method)
        pending = [(n, o) for n, o in trials if n not in completed and n not in failed]
        pending_names = set(dict(pending))
        rows.extend(checkpoint[~checkpoint.method.isin(pending_names | {'beta_matched'})]
                    .to_dict('records'))
        print(f'Resuming {len(pending)} pending optimizer trials', flush=True)
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=4, initializer=S.initialize_worker,
                             initargs=(schedule, history, cash, market)) as pool:
        futures = [pool.submit(S.evaluate_trial, name, overrides) for name, overrides in pending]
        for i, future in enumerate(as_completed(futures), 1):
            name, trial_rows, error = future.result()
            rows.extend(trial_rows)
            if error:
                failed[name] = error
                print(f'FAILED {name}: {error}', flush=True)
            S.save_csv(pd.DataFrame(rows), E.HERE / 'screened_monthly.csv')
            (E.HERE / 'screened_failures.json').write_text(json.dumps(failed, indent=2))
            print(f'{i}/{len(pending)} finished: {name}; {time.monotonic()-started:.0f}s', flush=True)
    monthly = pd.concat([E.attach_final_reporting(g) for _, g in
                        pd.DataFrame(rows).groupby('method', sort=False)], ignore_index=True)
    S.save_csv(monthly, E.HERE / 'screened_monthly.csv')
    complete = monthly[~monthly.method.isin(failed)]
    assert complete.groupby('method').size().eq(len(months)).all()
    assert not complete.duplicated(['method', 'target_month']).any()
    assert complete.max_constraint_violation.max() <= module.SETTINGS.numerical_tolerance
    summary = E.summarize(complete).rename(columns={'method': 'trial'})
    configs = pd.DataFrame([dict(trial=name, **asdict(setting))
                            for name, setting in settings.items()] +
                          [dict(trial='beta_matched', **asdict(reference_stages['constraints'].SETTINGS))])
    summary = summary.merge(configs, on='trial', how='left', validate='one_to_one')
    summary = summary.sort_values('information_ratio', ascending=False)
    S.save_csv(summary, E.HERE / 'screened_summary.csv')
    old = pd.read_csv(E.HERE / 'sweep_summary.csv')
    paired = old.merge(summary, on='trial', suffixes=('_unscreened', '_screened'))
    S.save_csv(paired, E.HERE / 'screened_vs_unscreened.csv')
    periods = []
    for label, mask in [('2021_2023', complete.target_month < '2024-01'),
                        ('2024_2026', complete.target_month >= '2024-01')]:
        part = E.summarize(complete[mask]).rename(columns={'method': 'trial'})
        part['period'] = label
        periods.append(part)
    S.save_csv(pd.concat(periods), E.HERE / 'screened_periods.csv')
    write_report(summary, paired, failed, months)
    # Keep the normal editable comparison aligned with the now-screened defaults.
    editable = summary[summary.trial != 'beta_matched'].copy()
    descriptions = {name: str(overrides) if overrides else 'Current optimizer'
                    for name, overrides in trials}
    editable['what_changed'] = editable.trial.map(descriptions)
    for field in ['beta_limit', 'sector_limit', 'size_limit', 'turnover_limit', 'annual_vol_limit']:
        editable[field] = editable[field].astype(object).where(editable[field].notna(), 'none')
    S.M.write_table(editable, months[0], months[-1], S.M.FORECAST)
    note_path = E.HERE / 'constraint.md'
    note_path.write_text(note_path.read_text(encoding='utf-8').replace(
        '# Model comparison\n', '# Model comparison\n\nScreened universe: price >=$5; '
        'no nano/micro-caps; short market cap >=$500m. See screened_comparison.md '
        'for the beta-matched reference.\n', 1), encoding='utf-8')
    print(summary[['trial', 'cagr', 'annual_vol', 'information_ratio',
                   'realized_market_beta', 'max_drawdown']].head(12).to_string(index=False), flush=True)


if __name__ == '__main__':
    run()

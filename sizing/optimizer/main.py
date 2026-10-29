"""Edit sizing/constraint.csv, then run this file for the comparison table."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FORECAST = 'current_gbm_no8k'
START = None
END = None
MAX_MONTHS = None  # 2 for a quick execution check; None for the full window.
from dataclasses import fields, replace
import numpy as np
import pandas as pd

import _engine as E


def run(predictions=None, forecast='current_gbm_no8k', start=None, end=None, max_months=None):
    path = E.HERE / 'constraint.csv'
    table = pd.read_csv(path)
    if table.trial.isna().any() or table.trial.duplicated().any():
        raise ValueError('Each trial needs a unique name.')
    stages = E.load_stages('optimizer')
    module = stages['constraints']
    names = {f.name for f in fields(module.SETTINGS)}
    configs = table[['trial'] + (['what_changed'] if 'what_changed' in table else [])
                    + [c for c in table if c in names]].copy()
    settings = []
    for _, config in configs.iterrows():
        overrides = {}
        for k, v in config.items():
            if k not in names or pd.isna(v):
                continue
            if isinstance(v, str) and v.strip().lower() == 'none':
                v = None
            elif isinstance(getattr(module.SETTINGS, k), int):
                if float(v) != int(float(v)):
                    raise ValueError(f'{k} must be an integer.')
                v = int(float(v))
            else:
                v = float(v)
            overrides[k] = v
        setting = replace(module.SETTINGS, **overrides)
        module.validate(setting)
        stages['selection'].validate(setting)
        settings.append(setting)
    prediction_path = E.resolve_predictions(predictions)
    scores, history, cash = E.load_inputs(prediction_path, forecast, E.C.CHARS_PARQUET,
                                         module.SETTINGS, stages=stages)
    schedule = [(m, g) for m, g in stages['selection'].candidate_schedule(scores, module.SETTINGS)
                if (not start or m >= start) and (not end or m <= end)]
    if max_months is not None:
        if max_months < 1:
            raise ValueError('max_months must be positive.')
        schedule = schedule[:max_months]
    months = [m for m, _ in schedule]
    if not months or months != pd.period_range(months[0], months[-1], freq='M').astype(str).tolist():
        raise ValueError('Trials require a contiguous nonempty window.')
    previous = [pd.Series(dtype=float) for _ in settings]
    market = E.benchmark_returns()
    rows = []
    # Ranking and candidate selection are shared. Covariance uses only earlier months.
    for month, g in schedule:
        covariance_cache = {}
        for i, (trial, setting) in enumerate(zip(configs.trial, settings)):
            key = (setting.covariance_months, setting.covariance_min_observations)
            if key not in covariance_cache:
                covariance_cache[key] = E.covariance_for(history, month, g, setting)[0]
            covariance = covariance_cache[key]
            inputs = E.sizing_inputs(g, previous[i], setting)
            try:
                weights, audit, status = E.solve_weights(g, covariance, inputs, setting,
                                                        module.build_constraints, module.build_objective)
            except Exception as exc:
                raise RuntimeError(f'{trial}, {month}: {exc}') from exc
            if month not in cash.index or not np.isfinite(cash.loc[month]):
                raise ValueError(f'{month}: missing cash return.')
            row, previous[i], _, _ = E.account(month, g, weights, previous[i],
                history.loc[month], float(cash.loc[month]), covariance, setting)
            row.update(method=trial, market_return=float(market.get(month, np.nan)))
            rows.append(row)
            if setting.annual_vol_limit is not None:
                assert row['predicted_monthly_vol'] * np.sqrt(12) <= setting.annual_vol_limit + 1e-5
        print(f'{month}: {len(settings)} trials complete', flush=True)
    monthly = pd.concat([E.attach_final_reporting(g) for _, g in
                         pd.DataFrame(rows).groupby('method', sort=False)], ignore_index=True)
    summary = E.summarize(monthly).rename(columns={'method': 'trial'})
    result = configs.merge(summary, on='trial', validate='one_to_one')
    result = write_table(result, months[0], months[-1], forecast)
    return result


def write_table(result, start, end, forecast):
    """Only two outputs: editable CSV and its readable Markdown table."""
    columns = ['trial', 'what_changed', 'gross_limit', 'annual_vol_limit',
               'cagr', 'annual_vol', 'information_ratio', 'realized_market_beta',
               'max_drawdown', 'mean_one_way_turnover']
    if 'what_changed' not in result:
        result['what_changed'] = result.apply(lambda row: ', '.join(
            f'{k}={row[k]:g}' for k in ('gross_limit', 'annual_vol_limit')
            if k in row and pd.notna(row[k])) or 'Current optimizer', axis=1)
    # Preserve any editable Settings overrides, without exposing diagnostic metrics.
    names = {f.name for f in fields(E.load_stages('optimizer')['constraints'].SETTINGS)}
    columns += [c for c in result if c in names and c not in columns]
    result = result[[c for c in columns if c in result]].copy()
    result.to_csv(E.HERE / 'constraint.csv', index=False)
    display = result[['trial', 'what_changed', 'annual_vol', 'information_ratio',
                      'realized_market_beta', 'max_drawdown', 'cagr',
                      'mean_one_way_turnover']].copy()
    display.columns = ['Experiment', 'What changed', 'Vol', 'IR', 'Beta',
                       'Max drawdown', 'Return (CAGR)', 'Monthly turnover']
    for col in ['Vol', 'Max drawdown', 'Return (CAGR)', 'Monthly turnover']:
        display[col] = display[col].map(lambda v: f'{v:.1%}')
    for col in ['IR', 'Beta']:
        display[col] = display[col].map(lambda v: f'{v:.2f}')
    markdown = '| ' + ' | '.join(display.columns) + ' |\n'
    markdown += '| ' + ' | '.join(['---'] * len(display.columns)) + ' |\n'
    markdown += '\n'.join('| ' + ' | '.join(row) + ' |' for row in display.astype(str).values)
    note = (f'# Model comparison\n\n{start} to {end} · `{forecast}`\n\n'
            + markdown + '\n\nVol and return are annualized; returns are net of modeled trading costs. '
            'IR is against cash + 4%; beta is realized against the S&P 500. '
            'Turnover is monthly one-way trades / NAV. Same ranking and candidates for all rows.\n')
    (E.HERE / 'constraint.md').write_text(note, encoding='utf-8')
    print(display.to_string(index=False))
    return result


if __name__ == '__main__':
    run(forecast=FORECAST, start=START, end=END, max_months=MAX_MONTHS)

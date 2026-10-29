"""Run the current model: saved forecasts -> ranking -> CVXPY sizing -> results.

This is a MONTHLY research experiment, not the final daily submission engine.
No model training, production outputs, or notebook edits occur here.
"""
from dataclasses import asdict, replace
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import subprocess

import cvxpy as cp
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'prediction'))
sys.path.insert(0, str(HERE))
import prediction_helpers as C
from optimizer.constraints import build_constraints, build_objective

BETA_SOURCES = ['betabab_1260d', 'betadown_252d', 'beta_60m']


def run_number(path):
    """Numeric order: run 10 comes after run 9, not after run 1."""
    name = path.name if path.is_dir() else path.parent.name
    return int(name) if name.isdigit() else -1


def write_constraints_note(out, metadata):
    sources = metadata.get('step_sources', {})
    source = sources.get('constraints.py', metadata.get('constraints_source'))
    lines = [f'# Run {out.name}: constraints', '',
             f'Experiment: {metadata.get("experiment", out.parent.parent.name)}', '',
             f'Forecast: `{metadata.get("forecast", "not recorded")}`', '']
    if metadata.get('settings'):
        lines += ['## Settings used', '', '```json', json.dumps(metadata['settings'], indent=2), '```', '']
    if source:
        lines += ['## Exact sizing rules used', '', '```python', source.rstrip(), '```', '']
    else:
        lines += ['The original constraints source was not recorded for this historical run.', '']
    (out / 'constraints.md').write_text('\n'.join(lines), encoding='utf-8')


def renumber_legacy_outputs(parent):
    parent.mkdir(parents=True, exist_ok=True)
    maximum = max((int(p.name) for p in parent.iterdir() if p.is_dir() and p.name.isdigit()), default=0)
    for old in sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.isdigit()
                      and (p / 'run.json').is_file()):
        maximum += 1
        target = parent / str(maximum)
        old.rename(target)
    for out in parent.iterdir():
        if out.is_dir() and out.name.isdigit() and (out / 'run.json').is_file() and not (out / 'constraints.md').exists():
            write_constraints_note(out, json.loads((out / 'run.json').read_text(encoding='utf-8')))


def new_run_folder(parent):
    renumber_legacy_outputs(parent)
    number = max((int(p.name) for p in parent.iterdir() if p.is_dir() and p.name.isdigit()), default=0) + 1
    while True:
        out = parent / str(number)
        try:
            out.mkdir()
            return out
        except FileExistsError:
            number += 1


def load_stages(experiment):
    """Load the editable files from the chosen folder, without cached cross-run imports."""
    folder=(HERE/experiment).resolve()
    if folder.parent != HERE:
        raise ValueError('Experiment must be a folder directly inside sizing.')
    modules={}
    for step in ['features','ranking','selection','constraints']:
        path=folder/f'{step}.py'
        spec=importlib.util.spec_from_file_location(f'active_{experiment}_{step}',path)
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        modules[step]=module
    return modules


def resolve_predictions(path):
    if path:
        result = Path(path).resolve()
        if not result.is_file():
            raise FileNotFoundError(result)
        return result
    # Do not automatically use a sampled smoke run or mix forecast runs.
    candidates = sorted((ROOT / 'prediction/outputs/next_month_prediction/full').glob(
        '*/predictions.parquet'), reverse=True)
    for candidate in candidates:
        manifest = candidate.parent / 'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8')).get('run_mode') == 'full':
            return candidate.resolve()
    shared = ROOT / 'prediction/saved_forecasts/predictions.parquet'
    if shared.is_file():
        return shared
    raise FileNotFoundError('No saved forecasts found. Set RETRAIN_PREDICTIONS=True in root main.py.')


def load_inputs(prediction_path, forecast, panel_path, settings, stages=None):
    # Intentionally do not read notebook outcome columns into selection inputs.
    pred = pd.read_parquet(prediction_path, columns=['permno', 'target_month', forecast])
    pred['target_month'] = pd.PeriodIndex(pred.target_month, freq='M').astype(str)
    pred = pred.rename(columns={forecast: 'forecast'})
    if pred.duplicated(['permno', 'target_month']).any():
        raise ValueError('Duplicate stock/month predictions.')
    if not np.isfinite(pred.forecast).all():
        raise ValueError('Forecasts must be finite.')
    cols = ['permno', 'eom', 'prc', 'me', 'size_grp', 'gics', 'rvol_21d',
            'ret', 'ret_exc', 'ticker', 'company_name'] + BETA_SOURCES
    panel = pd.read_parquet(panel_path, columns=cols)
    panel['eom'] = pd.to_datetime(panel.eom)
    panel['observed_month'] = panel.eom.dt.to_period('M').astype(str)
    panel['target_month'] = (panel.eom.dt.to_period('M') + 1).astype(str)
    if panel.duplicated(['permno', 'observed_month']).any():
        raise ValueError('Duplicate stock/month source observations.')
    characteristics = panel.drop(columns=['ret', 'ret_exc', 'observed_month'])
    g = pred.merge(characteristics, on=['permno', 'target_month'], how='left', validate='one_to_one')
    if g.eom.isna().any():
        raise ValueError('Some forecasts have no prior-month characteristics.')
    assert ((pd.PeriodIndex(g.target_month, freq='M') - 1).astype(str)
            == g.eom.dt.to_period('M').astype(str)).all(), 'Feature/forecast date mismatch'
    g['beta_use'] = g[BETA_SOURCES].bfill(axis=1).iloc[:, 0].clip(-0.5, 3.5)
    if stages is None:
        stages = load_stages('optimizer')
    g = stages['selection'].prepare_universe(g, settings)
    if set(pred.target_month) != set(g.target_month):
        raise ValueError('Eligibility removed every stock from a forecast month.')
    g['sector'] = g.gics.astype(str).str[:2].where(g.gics.notna(), 'na')
    g = stages['features'].add_features(g)
    g = stages['ranking'].build_ranking(g, settings)
    # Returns are separate: only historical rows enter covariance, and future
    # rows are consulted AFTER weights have been solved, solely for accounting.
    history = panel.pivot(index='observed_month', columns='permno', values='ret')
    cash = (panel.ret - panel.ret_exc).groupby(panel.observed_month).agg(['median', 'min', 'max'])
    if ((cash['max'] - cash['min']).abs().dropna() > 1e-7).any():
        raise ValueError('Source implied cash return varies across stocks within a month.')
    return g, history.sort_index(), cash['median']


def covariance_for(history, month, g, settings):
    past = history.loc[history.index < month].tail(settings.covariance_months)
    x = past.reindex(columns=g.index).replace([np.inf, -np.inf], np.nan)
    if len(x) < settings.covariance_min_observations:
        raise ValueError(f'{month}: insufficient historical months for covariance.')
    counts = x.notna().sum().to_numpy()
    sample_sd = x.std(ddof=0).to_numpy()
    reliable = (counts >= settings.covariance_min_observations) & np.isfinite(sample_sd) & (sample_sd > 1e-8)
    # rvol_21d is daily realized volatility; convert to approximate monthly SD.
    sd = np.where(reliable, sample_sd, g.rvol_21d.to_numpy() * np.sqrt(21))
    sd = np.maximum(sd, 1e-4)
    z = ((x - x.mean()) / sd).fillna(0).to_numpy()
    z[:, ~reliable] = 0
    # Shrunk correlation from mean-imputed histories. Rescaling and resetting
    # the unreliable block preserve PSD and do not treat missing returns as low risk.
    shrunk = LedoitWolf().fit(z).covariance_
    diag = np.sqrt(np.maximum(np.diag(shrunk), 1e-12))
    correlation = shrunk / np.outer(diag, diag)
    correlation[~reliable, :] = 0
    correlation[:, ~reliable] = 0
    np.fill_diagonal(correlation, 1)
    cov = correlation * np.outer(sd, sd) + np.eye(len(g)) * 1e-10
    return cov, {'history_start': x.index.min(), 'history_end': x.index.max(),
                 'history_months': len(x), 'fallback_vol_stocks': int((~reliable).sum()),
                 'missing_history_fraction': float(x.isna().to_numpy().mean())}


def sizing_inputs(g, previous, settings):
    previous_aligned = previous.reindex(g.index, fill_value=0).to_numpy()
    sectors = pd.get_dummies(g.sector, dtype=float).T
    return {
        'beta': g.beta_use.to_numpy(), 'size': g['size'].to_numpy(),
        'sector_matrix': sectors.to_numpy(), 'sector_names': sectors.index.tolist(),
        'previous': previous_aligned,
        'forced_exit_turnover': float(previous.loc[~previous.index.isin(g.index)].abs().sum()),
        'long_limits': np.where(g.side > 0, settings.position_limit, 0),
        'short_limits': np.where(g.side < 0, settings.position_limit, 0),
        'side': g.side.to_numpy(),
    }


def solve_weights(g, covariance, inputs, settings, constraint_builder=build_constraints,
                  objective_builder=build_objective):
    w = cp.Variable(len(g))
    objective = objective_builder(w, g.score.to_numpy(), covariance, inputs['previous'],
                                  inputs['forced_exit_turnover'], settings)
    rules = constraint_builder(w, inputs, settings)
    problem = cp.Problem(objective, list(rules.values()))
    problem.solve(solver='CLARABEL', tol_gap_abs=1e-9, tol_feas=1e-9, tol_gap_rel=1e-9)
    if problem.status not in ('optimal', 'optimal_inaccurate') or w.value is None:
        raise ValueError(f'Optimizer status: {problem.status}. No constraints were automatically relaxed.')
    checks = []
    for name, rule in rules.items():
        violation = float(np.max(rule.violation()))
        checks.append({'constraint': name, 'max_violation': violation,
                       'max_abs_dual': float(np.max(np.abs(rule.dual_value)))
                       if rule.dual_value is not None else np.nan})
        if violation > settings.numerical_tolerance:
            raise ValueError(f'{name}: violation {violation:g} exceeds numerical tolerance.')
    # Keep solver values as returned: clipping/renormalizing could break constraints.
    return pd.Series(w.value, index=g.index), checks, problem.status



def account(month, g, weights, previous, realized, cash, covariance, settings):
    raw = realized.reindex(g.index)
    filled = raw.fillna(0.)
    traded = float(weights.subtract(previous, fill_value=0).abs().sum())
    cost = traded * settings.trading_cost_bps / 10000
    gross_return = float(cash + weights @ (filled - cash))
    total = gross_return - cost
    if total <= -1 or (filled < -1).any():
        raise ValueError(f'{month}: invalid returns or portfolio bankruptcy.')
    sector = weights.groupby(g.sector).sum()
    row = dict(target_month=month, total_gross=gross_return, total_net=total,
               cash=cash, hurdle=cash + C.COMPETITION['benchmark_premium_annual'] / 12,
               turnover=traded, cost=cost, gross=float(weights.abs().sum()), net=float(weights.sum()),
               one_way_turnover=traded / 2,
               max_weight=float(weights.abs().max()), market_beta=float(weights @ g.beta_use),
               size_exposure=float(weights @ g['size']), max_sector_net=float(sector.abs().max()),
               predicted_monthly_vol=float(np.sqrt(max(0, weights.to_numpy() @ covariance @ weights.to_numpy()))),
               positions=int((weights.abs() > 1e-6).sum()), missing_return_positions=int(raw.isna().sum()),
               missing_return_gross=float(weights[raw.isna()].abs().sum()))
    # Trades/cost booked after target weights, consistent with existing monthly
    # research accounting. All holdings (including forced exits) enter turnover.
    drifted = weights * (1 + filled) / (1 + total)
    return row, drifted, raw, sector


def benchmark_returns():
    d = pd.read_csv(C.SP500_CSV, parse_dates=['observation_date'])
    d['SP500'] = pd.to_numeric(d.SP500, errors='coerce')
    levels = d.set_index('observation_date').SP500.resample('ME').last().dropna()
    returns = levels.pct_change()
    returns.index = returns.index.to_period('M').astype(str)
    return returns


def official_hurdle():
    """Final instructions Section 9.2: annualized percent TB3MS / 1200 + 4%/12."""
    d = pd.read_csv(C.TB3MS_CSV, parse_dates=['observation_date'])
    values = pd.to_numeric(d.TB3MS, errors='coerce') / 1200 + .04 / 12
    return pd.Series(values.to_numpy(), index=d.observation_date.dt.to_period('M').astype(str))


def summarize(monthly):
    rows = []
    for method, m in monthly.groupby('method', sort=False):
        r = m.total_net.to_numpy()
        active = r - m.hurdle.to_numpy()
        wealth = np.r_[1., np.cumprod(1 + r)]
        market = m.market_return.to_numpy() - m.cash.to_numpy()
        beta = np.nan
        if len(m) >= 3 and np.isfinite(market).all() and market.std() > 0:
            beta = np.linalg.lstsq(np.column_stack([np.ones(len(m)), market]),
                                   r - m.cash.to_numpy(), rcond=None)[0][1]
        rows.append(dict(method=method, months=len(m), cagr=wealth[-1] ** (12 / len(m)) - 1,
                         annual_vol=np.std(r, ddof=1) * np.sqrt(12) if len(m) > 1 else np.nan,
                         information_ratio=np.sqrt(12) * np.mean(active) / np.std(active, ddof=1)
                         if len(m) > 1 and np.std(active, ddof=1) > 0 else np.nan,
                         max_drawdown=float(np.min(wealth / np.maximum.accumulate(wealth) - 1)),
                         realized_market_beta=beta, mean_traded_nav=m.turnover.mean(),
                         mean_one_way_turnover=m.one_way_turnover.mean(),
                         annual_one_way_turnover=m.one_way_turnover.mean() * 12,
                         ending_nav_billion=wealth[-1],
                         total_cost_nav_fractions=m.cost.sum(), mean_gross=m.gross.mean(),
                         max_abs_estimated_beta=m.market_beta.abs().max(),
                         max_sector_net=m.max_sector_net.max(), min_positions=m.positions.min(),
                         mean_missing_return_gross=m.missing_return_gross.mean()))
        if 'shorts_below_500m' in m and m.shorts_below_500m.notna().any():
            rows[-1]['max_shorts_below_500m'] = int(m.shorts_below_500m.max())
    return pd.DataFrame(rows)


def attach_final_reporting(monthly):
    monthly = monthly.copy()
    monthly['hurdle'] = monthly.target_month.map(official_hurdle())
    if monthly.hurdle.isna().any():
        raise ValueError('Missing TB3MS benchmark months; no forward fill or substitution allowed.')
    monthly['one_way_turnover'] = monthly.turnover / 2
    monthly['nav_usd'] = 1e9 * (1 + monthly.total_net).cumprod()
    return monthly



def run_price_only(predictions=None, forecast='current_gbm_no8k', start=None, end=None, max_months=None):
    """Adjusted ranking, price >= $5, equal long/short weights; no other screens."""
    from optimizer.constraints import SETTINGS
    stages = load_stages('price_only')
    reference = stages['constraints']
    selection = stages['selection']
    path = resolve_predictions(predictions)
    scores, history, cash = load_inputs(path, forecast, C.CHARS_PARQUET,
                                        SETTINGS, stages=stages)
    months = sorted(scores.target_month.unique())
    months = [m for m in months if (not start or m >= start) and (not end or m <= end)]
    if max_months:
        months = months[:max_months]
    if not months:
        raise ValueError('Empty reference window.')
    out = new_run_folder(HERE / 'price_only/outputs')
    write_constraints_note(out, dict(experiment='price_only', forecast=forecast,
                                    step_sources={'constraints.py': (HERE / 'price_only/constraints.py').read_text(encoding='utf-8')}))
    previous = pd.Series(dtype=float)
    selected = dict(selection.candidate_schedule(scores, SETTINGS))
    rows, held = [], []
    for month in months:
        g = selected[month]
        weights = reference.size_positions(g)
        covariance, _ = covariance_for(history, month, g, SETTINGS)
        realized = history.loc[month] if month in history.index else pd.Series(dtype=float)
        row, previous, raw, _ = account(month,g,weights,previous,realized,float(cash.loc[month]),covariance,SETTINGS)
        row.update(method='price_only',market_return=float(benchmark_returns().get(month,np.nan)),
                   position_count_in_200_500=True,
                   shorts_below_500m=int(((weights<0)&(g.me<500)).sum()))
        rows.append(row)
        h=g[['target_month','ticker','company_name','score','me','prc','size_grp']].copy()
        h['weight'],h['raw_return']=weights,raw
        held.append(h.reset_index())
    monthly=attach_final_reporting(pd.DataFrame(rows))
    monthly.to_csv(out/'monthly_returns.csv',index=False)
    pd.concat(held,ignore_index=True).to_parquet(out/'holdings.parquet',index=False)
    summary=summarize(monthly)
    summary.to_csv(out/'summary.csv',index=False)
    meta=dict(status='complete',experiment='price_only',forecast=forecast,months=months,
              prediction_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
              scope='Deliberately naive adjusted-ranking price-only reference; not final-mandate compliant',
              step_sources={p.name:p.read_text(encoding='utf-8') for p in (HERE/'price_only').glob('*.py')})
    (out/'run.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    save_report(out,monthly,summary,SETTINGS)
    update_comparison(out)
    return out


def comparison_monthly(current):
    """Overlay other experiments only when forecasts and evaluation dates match."""
    meta = json.loads((current / 'run.json').read_text(encoding='utf-8'))
    current_monthly = pd.read_csv(current / 'monthly_returns.csv')
    frames = [current_monthly]
    for folder in sorted(HERE.iterdir()):
        if not folder.is_dir() or folder.name == meta.get('experiment'):
            continue
        for old_path in sorted((folder / 'outputs').glob('*/run.json'), key=run_number, reverse=True):
            other = json.loads(old_path.read_text(encoding='utf-8'))
            if (other.get('status') == 'complete' and other['forecast'] == meta['forecast']
                    and other['prediction_sha256'] == meta['prediction_sha256']
                    and other['months'] == current_monthly.target_month.tolist()):
                frames.append(pd.read_csv(old_path.parent / 'monthly_returns.csv'))
                break
    return pd.concat(frames, ignore_index=True)


def update_comparison(out):
    frames = []
    for path in sorted(HERE.glob('*/outputs/*/summary.csv'), key=run_number):
        meta = json.loads((path.parent / 'run.json').read_text(encoding='utf-8'))
        if meta.get('status') != 'complete':
            continue
        frame = pd.read_csv(path)
        # Do not compare headline IRs computed under the superseded cash proxy.
        if 'mean_one_way_turnover' not in frame.columns:
            continue
        frame.insert(0, 'experiment', path.parents[2].name)
        frame.insert(1, 'run', path.parent.name)
        frame['forecast'] = meta['forecast']
        frame['prediction_sha256'] = meta['prediction_sha256']
        frame['start'], frame['end'] = meta['months'][0], meta['months'][-1]
        frames.append(frame)
    comparison = pd.concat(frames, ignore_index=True).drop_duplicates(
        ['experiment', 'forecast', 'prediction_sha256', 'start', 'end'], keep='last')
    comparison.to_csv(HERE / 'comparison.csv', index=False)


def save_report(out, monthly, summary, settings):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    colors = {'beta_matched': 'tab:blue', 'optimizer': 'tab:orange', 'price_only': 'tab:purple'}
    for method, m in monthly.groupby('method', sort=False):
        dates = pd.to_datetime(m.target_month)
        axes[0].plot(dates, (1 + m.total_net).cumprod(), label=method, color=colors.get(method))
        axes[1].plot(dates, m.market_beta, label=method, color=colors.get(method))
        axes[2].plot(dates, m.turnover, label=method, color=colors.get(method))
    m = monthly[monthly.method == monthly.method.iloc[0]]
    axes[0].plot(pd.to_datetime(m.target_month), (1 + m.hurdle).cumprod(), '--', color='tab:green', label='cash + 4% hurdle')
    for ax, label in zip(axes, ['Wealth after trading costs', 'Estimated market beta', 'Buys + sells / NAV']):
        ax.set_ylabel(label)
        ax.grid(alpha=.2)
    if settings.beta_limit is not None:
        for limit in [-settings.beta_limit, settings.beta_limit]:
            axes[1].axhline(limit, color='gray', linestyle=':')
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(out / 'results.png', dpi=150)
    plt.close(fig)
    lines = ['# Optimizer results', '', 'Current model: saved forecasts → ranking → CVXPY weights.', '',
             '![Returns, market exposure and turnover](results.png)', '',
             'Starting penalty settings are unvalidated. This is a retrospective research run, not a final mandate compliance certificate.', '',
             '```text', summary.round(5).to_string(index=False), '```', '',
             'Missing realized stock returns are marked at zero and their exposure is reported. '
             'Borrow fees, market impact, formation-day execution and intramonth drift constraints are not modeled. '
             'S&P 500 beta uses price returns. Position-count checks are diagnostics, not optimizer guarantees.', '',
             'See run.json and constraint_checks.csv for settings and checks.']
    (out / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    table = summary.set_index('method').T
    html = ('<!doctype html><html><head><meta charset="utf-8"><title>Sizing results</title>'
            '<style>body{font:17px system-ui;max-width:1100px;margin:40px auto;padding:20px;}'
            'img{width:100%;}td,th{padding:8px;text-align:left;}tr:nth-child(even){background:#f1f5f9;}</style>'
            '</head><body><h1>Sizing results</h1><p>Monthly research run. '
            'Not certified for the final mandate. Check position counts, formation-day short eligibility, '
            'daily exposure drift, borrow/capacity and required reporting.</p>'
            '<img src="results.png" alt="Returns, beta and turnover">' + table.round(5).to_html()
            + '<p>Missing returns are marked at zero. Borrow/impact and daily execution rules are not modeled.</p>'
            '<p><a href="monthly_returns.csv">Monthly returns and exposures</a> · '
            '<a href="constraint_checks.csv">Constraint checks</a></p></body></html>')
    (out / 'report.html').write_text(html, encoding='utf-8')


def run(experiment='optimizer', predictions=None, forecast='current_gbm_no8k',
        start=None, end=None, max_months=None):
    """Called by Run.ipynb. Each experiment folder owns its constraints and results."""
    folder = (HERE / experiment).resolve()
    if folder.parent != HERE or not (folder / 'constraints.py').is_file():
        raise ValueError('Choose an experiment folder directly inside sizing, containing constraints.py.')
    spec = importlib.util.spec_from_file_location('active_sizing_constraints', folder / 'constraints.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    settings = module.SETTINGS
    module.validate(settings)
    if max_months is not None and max_months < 1:
        raise ValueError('max_months must be positive.')
    for value in (start, end):
        if value is not None:
            pd.Period(value, freq='M')
    prediction_path = resolve_predictions(predictions)
    out = new_run_folder(folder / 'outputs')
    manifest = {'status': 'running', 'experiment': experiment,
                'predictions': str(prediction_path), 'forecast': forecast,
                'settings': asdict(settings),
                'step_sources': {p.name:p.read_text(encoding='utf-8') for p in folder.glob('*.py')},
                'engine_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'panel': str(C.CHARS_PARQUET),
                'prediction_sha256': hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
                'panel_bytes': C.CHARS_PARQUET.stat().st_size,
                'panel_mtime_ns': C.CHARS_PARQUET.stat().st_mtime_ns,
                'versions': {'python': sys.version, 'cvxpy': cp.__version__, 'numpy': np.__version__,
                             'pandas': pd.__version__},
                'final_mandate_compliant': False,
                'remaining_checks': ['formation-day eligibility and Section 7 execution lag',
                                     'intramonth exposure limits and daily beta reporting',
                                     'full standardized report and capacity analysis'],
                'scope': 'monthly research; position-count/daily-execution compliance incomplete'}
    def write_manifest():
        (out / 'run.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    write_manifest()
    write_constraints_note(out, manifest)
    print(f'Experiment: {experiment}\nForecasts: {prediction_path}\nResults: {out}', flush=True)
    rows, holdings, checks, cov_audit, sector_rows = [], [], [], [], []
    try:
        stages = load_stages(experiment)
        stages['selection'].validate(settings)
        scores, history, cash = load_inputs(prediction_path, forecast, C.CHARS_PARQUET, settings, stages=stages)
        schedule = list(stages['selection'].candidate_schedule(scores, settings))
        schedule = [(m, g) for m, g in schedule if (not start or m >= start)
                    and (not end or m <= end)]
        if max_months:
            schedule = schedule[:max_months]
        months = [m for m, _ in schedule]
        if not months or months != pd.period_range(months[0], months[-1], freq='M').astype(str).tolist():
            raise ValueError('Evaluation requires a nonempty, contiguous monthly forecast window.')
        previous = pd.Series(dtype=float)
        market = benchmark_returns()
        for month, g in schedule:
            if month not in cash.index or not np.isfinite(cash.loc[month]):
                raise ValueError(f'{month}: missing source cash return.')
            covariance, audit = covariance_for(history, month, g, settings)
            cov_audit.append({'target_month': month, **audit})
            inputs = sizing_inputs(g, previous, settings)
            if hasattr(module, 'size_positions'):
                optimized = module.size_positions(g, settings)
                if not optimized.index.equals(g.index) or not np.isfinite(optimized).all():
                    raise ValueError('Sizing rule returned invalid or misaligned weights.')
                variable = cp.Variable(len(g), value=optimized.to_numpy())
                month_checks = []
                for name, rule in module.build_constraints(variable, inputs, settings).items():
                    violation = float(np.max(rule.violation()))
                    if violation > settings.numerical_tolerance:
                        raise ValueError(f'{name}: rule-based weights violate constraint by {violation:g}.')
                    month_checks.append(dict(constraint=name, max_violation=violation, max_abs_dual=np.nan))
                status = 'rule_based'
            else:
                optimized, month_checks, status = solve_weights(
                    g, covariance, inputs, settings, module.build_constraints, module.build_objective)
            checks.extend({'target_month': month, 'solver_status': status, **c} for c in month_checks)
            realized = history.loc[month] if month in history.index else pd.Series(dtype=float)
            row, previous, raw, sectors = account(
                month, g, optimized, previous, realized, float(cash.loc[month]), covariance, settings)
            row.update(method=experiment, market_return=float(market.get(month, np.nan)),
                       position_count_in_200_500=bool(200 <= row['positions'] <= 500))
            rows.append(row)
            h = g[['target_month', 'ticker', 'company_name', 'score', 'side', 'beta_use', 'sector', 'size']].copy()
            h['weight'], h['raw_return'] = optimized, raw
            holdings.append(h.reset_index())
            sector_rows.extend({'target_month': month, 'sector': k, 'net_exposure': v}
                               for k, v in sectors.items())
            print(f'{month}: {status}; optimizer gross={rows[-1]["gross"]:.3f}, '
                  f'beta={rows[-1]["market_beta"]:+.3f}, positions={rows[-1]["positions"]}', flush=True)
        monthly = attach_final_reporting(pd.DataFrame(rows))
        monthly.to_csv(out / 'monthly_returns.csv', index=False)
        pd.concat(holdings, ignore_index=True).to_parquet(out / 'holdings.parquet', index=False)
        pd.DataFrame(checks).to_csv(out / 'constraint_checks.csv', index=False)
        pd.DataFrame(cov_audit).to_csv(out / 'covariance_audit.csv', index=False)
        pd.DataFrame(sector_rows).to_csv(out / 'sector_exposures.csv', index=False)
        summary = summarize(monthly)
        summary.to_csv(out / 'summary.csv', index=False)
        manifest.update(status='complete', months=months,
                        all_position_counts_in_200_500=bool(monthly.position_count_in_200_500.all()),
                        max_constraint_violation=max(c['max_violation'] for c in checks))
        write_manifest()
        plot_monthly = comparison_monthly(out)
        save_report(out, plot_monthly, summarize(plot_monthly), settings)
        update_comparison(out)
        print(summary.to_string(index=False), flush=True)
        print(f"Results ready: {out / 'report.html'}", flush=True)
        if not manifest['all_position_counts_in_200_500']:
            print('RESEARCH ONLY: at least one portfolio is outside the 200-500 position range. '
                  'Candidate count does not guarantee nonzero holdings; see monthly_returns.csv.', flush=True)
    except Exception as exc:
        manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if checks:
            pd.DataFrame(checks).to_csv(out / 'constraint_checks.csv', index=False)
        raise
    finally:
        write_manifest()
    return out


def execute(experiments, *, retrain=False, predictions=None,
            forecast='current_gbm_no8k', start=None, end=None, max_months=None):
    if not C.CHARS_PARQUET.is_file():
        raise FileNotFoundError(
            'Missing monthly stock data. Copy chars_final_with_names.parquet into '
            f'{ROOT / "data"}, or set FIAM_DATA_DIR to its folder. See README.md.')
    if retrain:
        if predictions is not None:
            raise ValueError('Choose retraining OR an existing prediction file.')
        try:
            before = resolve_predictions(None)
        except FileNotFoundError:
            before = None
        subprocess.run([sys.executable, str(ROOT / 'prediction/predict.py')], cwd=ROOT, check=True)
        if resolve_predictions(None) == before:
            raise RuntimeError('No new full forecast export produced; check RUN_MODE="full" in prediction/predict.py.')
    source = resolve_predictions(predictions)
    print(f'All experiments use: {source}\nForecast: {forecast}', flush=True)
    outputs = {}
    summaries = []
    for name in experiments:
        options = dict(predictions=str(source), forecast=forecast,
                       start=start, end=end, max_months=max_months)
        out = run_price_only(**options) if name == 'price_only' else run(name, **options)
        outputs[name] = out
        frame = pd.read_csv(out / 'summary.csv')
        frame.insert(0, 'experiment', name)
        summaries.append(frame)
        print(f'\n{name}: OPEN {out / "report.html"}', flush=True)
    if not summaries:
        raise ValueError('Choose at least one experiment.')
    comparison = pd.concat(summaries, ignore_index=True)
    print('\nRuns just executed:')
    print(comparison[['experiment', 'months', 'cagr', 'information_ratio',
                      'max_drawdown', 'realized_market_beta', 'min_positions']].to_string(index=False))
    print(f'\nLatest experiments: {ROOT / "sizing/comparison.csv"}')
    return outputs

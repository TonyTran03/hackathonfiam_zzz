"""STEP 4: edit allocation limits and the CVXPY constraints, then run main.py in this folder.

Weights and exposure limits are fractions of NAV (0.015 means 1.5%).
None disables an optional house constraint; 0.0 requests exact neutrality.
The fixed mandate ceilings below are kept separate from research choices.
"""
from dataclasses import dataclass

import cvxpy as cp
import numpy as np


@dataclass(frozen=True)
class Settings:
    # House limits. Mandatory gross/net/5% ceilings are enforced separately.
    gross_limit: float = 2.0
    net_min: float = -0.50
    net_max: float = 0.50
    position_limit: float = 0.05
    # Allocation choice to keep selected names economically nonzero ($1m at inception).
    # This is not a PDF-specified minimum position size. All 300 candidates are held.
    minimum_position_weight: float = 0.001
    beta_limit: float | None = None # Match estimated long and short market-beta exposure.
    sector_limit: float | None = None
    size_limit: float | None = None
    turnover_limit: float | None = None
    # Time-series valuation guard. See PRE_REGISTRATION.MD; fixed before any run.
    expensive_percentile: float = 0.70
    expensive_long_cap: float | None = None  # CONTROL ARM: constraint off.

    # Starting values, NOT validated parameters. Scores are not return forecasts.
    # Score reward and penalties are in score units; tune on a design period.
    # Measured: one unit of score = +0.4339%/month (t=+2.41). See ARMS.md.
    score_scale: float = 0.004339
    risk_penalty: float = 0.4339
    cost_penalty: float = 1.0
    trading_cost_bps: float = 20.0  # one-way charge on all buys + sells
    covariance_months: int = 36
    covariance_min_observations: int = 12
    numerical_tolerance: float = 1e-6


SETTINGS = Settings()


def build_objective(w, scores, covariance, previous, forced_exit_turnover, settings):
    """Edit the sizing trade-off here: signal reward minus risk and trading costs."""
    trades = cp.norm1(w - previous) + forced_exit_turnover
    return cp.Maximize(
        settings.score_scale * (scores @ w)
        - settings.risk_penalty * cp.quad_form(w, cp.psd_wrap(covariance))
        - settings.cost_penalty * settings.trading_cost_bps / 10000 * trades)


def build_constraints(w, inputs, settings=SETTINGS):
    """Add new CVXPY expressions here.

    inputs fields (all aligned with w): beta, size, sector_matrix, previous,
    long_limits, short_limits, forced_exit_turnover. Sector matrix has one
    row per sector. Previous holdings outside the current universe MUST be
    liquidated; their turnover counts even though their new weight is zero.

    Example of another exposure:
        rules['value'] = cp.abs(inputs['value_beta'] @ w) <= value_limit
    Supply that exposure in sizing/_engine.py before enabling the expression.
    """
    rules = {
        'mandate_gross': cp.norm1(w) <= 2.0,
        'mandate_net_min': cp.sum(w) >= -0.50,
        'mandate_net_max': cp.sum(w) <= 0.50,
        'mandate_position': cp.abs(w) <= 0.05,
        'long_limits': w <= inputs['long_limits'],
        'short_limits': w >= -inputs['short_limits'],
        'house_gross': cp.norm1(w) <= settings.gross_limit,
        'house_net_min': cp.sum(w) >= settings.net_min,
        'house_net_max': cp.sum(w) <= settings.net_max,
        'selected_name_minimum': cp.multiply(inputs['side'], w) >= settings.minimum_position_weight,
    }
    if settings.beta_limit is not None:
        rules['market_beta'] = cp.abs(inputs['beta'] @ w) <= settings.beta_limit
    if settings.sector_limit is not None:
        rules['sector'] = cp.abs(inputs['sector_matrix'] @ w) <= settings.sector_limit
    if settings.size_limit is not None:
        rules['size'] = cp.abs(inputs['size'] @ w) <= settings.size_limit
    if settings.turnover_limit is not None:
        rules['turnover'] = (
            cp.norm1(w - inputs['previous']) + inputs['forced_exit_turnover']
            <= settings.turnover_limit
        )
    if settings.expensive_long_cap is not None and inputs.get('pe_pct') is not None:
        # NaN (loss-making, or under 36 months of history) means unconstrained.
        pe = np.nan_to_num(inputs['pe_pct'], nan=0.0)
        expensive = np.flatnonzero(pe > settings.expensive_percentile)
        if len(expensive):
            rules['expensive_long_cap'] = w[expensive] <= settings.expensive_long_cap
    return rules


def validate(settings):
    if not 0 < settings.gross_limit <= 2:
        raise ValueError('gross_limit must be in (0, 2].')
    if not -0.5 <= settings.net_min <= settings.net_max <= 0.5:
        raise ValueError('Net limits must stay inside [-0.5, 0.5].')
    if not 0 < settings.position_limit <= 0.05:
        raise ValueError('position_limit must be in (0, 0.05].')
    if not 1e-6 < settings.minimum_position_weight <= settings.position_limit:
        raise ValueError('Selected names require a positive allocation above numerical dust.')
    if not 0 < settings.expensive_percentile < 1:
        raise ValueError('expensive_percentile must be a percentile in (0, 1).')
    if (settings.expensive_long_cap is not None
            and not settings.minimum_position_weight <= settings.expensive_long_cap
            <= settings.position_limit):
        raise ValueError('expensive_long_cap must sit between the minimum position '
                         'and the position limit, or the problem is infeasible.')
    if not 0 < settings.score_scale <= 1:
        raise ValueError('score_scale converts score units to monthly return; (0, 1].')
    for key in ('beta_limit', 'sector_limit', 'size_limit', 'turnover_limit',
                'risk_penalty', 'cost_penalty', 'trading_cost_bps'):
        val = getattr(settings, key)
        if val is not None and (not np.isfinite(val) or val < 0):
            raise ValueError(f'{key} must be finite and nonnegative, or None for optional bounds.')
    if not 2 <= settings.covariance_min_observations <= settings.covariance_months:
        raise ValueError('Covariance history requires 2 <= minimum observations <= window.')

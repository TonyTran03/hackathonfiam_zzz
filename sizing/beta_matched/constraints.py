# Fixed reference: the original capped inverse-volatility / beta-matched sizing.
# No realized-beta feedback. Position caps can leave a small estimated-beta residual.
"""STEP 4: edit allocation limits and the CVXPY constraints, then run main.py in this folder.

Weights and exposure limits are fractions of NAV (0.015 means 1.5%).
None disables an optional house constraint; 0.0 requests exact neutrality.
The fixed mandate ceilings below are kept separate from research choices.
"""
from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Settings:
    # House limits. Mandatory gross/net/5% ceilings are enforced separately.
    gross_limit: float = 2.0
    net_min: float = -0.50
    net_max: float = 0.50
    position_limit: float = 0.015
    # Allocation choice to keep selected names economically nonzero ($1m at inception).
    # This is not a PDF-specified minimum position size. All 300 candidates are held.
    minimum_position_weight: float = 0.001
    beta_limit: float | None = None
    sector_limit: float | None = None
    size_limit: float | None = None
    turnover_limit: float | None = None

    # Starting values, NOT validated parameters. Scores are not return forecasts.
    # Score reward and penalties are in score units; tune on a design period.
    risk_penalty: float = 100.0
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
        scores @ w
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
    for key in ('beta_limit', 'sector_limit', 'size_limit', 'turnover_limit',
                'risk_penalty', 'cost_penalty', 'trading_cost_bps'):
        val = getattr(settings, key)
        if val is not None and (not np.isfinite(val) or val < 0):
            raise ValueError(f'{key} must be finite and nonnegative, or None for optional bounds.')
    if not 2 <= settings.covariance_min_observations <= settings.covariance_months:
        raise ValueError('Covariance history requires 2 <= minimum observations <= window.')


def capped_inverse_vol(vol, budget, cap):
    v = np.clip(vol, np.quantile(vol, .05), np.quantile(vol, .95))
    budget = min(budget, len(v) * cap)
    weights = np.zeros(len(v))
    free = np.ones(len(v), dtype=bool)
    while free.any():
        allocation = (1 / v[free]) / (1 / v[free]).sum() * (budget - weights.sum())
        over = allocation > cap
        indexes = np.flatnonzero(free)
        if not over.any():
            weights[indexes] = allocation
            break
        weights[indexes[over]] = cap
        free[indexes[over]] = False
    return weights

def baseline_weights(g, settings):
    """Inverse-vol sizing with estimated-beta leg matching; no realized-beta feedback.

    Same candidate list, gross/net limits and true final position cap. Optional
    optimizer-only house constraints are measured, but not imposed on baseline.
    """
    is_long = g.side.to_numpy() > 0
    wl = capped_inverse_vol(g.loc[is_long, 'rvol_21d'].to_numpy(), 1, 1)
    ws = capped_inverse_vol(g.loc[~is_long, 'rvol_21d'].to_numpy(), 1, 1)
    bl = wl @ g.loc[is_long, 'beta_use'].to_numpy()
    bs = ws @ g.loc[~is_long, 'beta_use'].to_numpy()
    long_budget = settings.gross_limit * bs / (bl + bs) if min(bl, bs) > 0 else settings.gross_limit / 2
    net = np.clip(2 * long_budget - settings.gross_limit, settings.net_min, settings.net_max)
    long_budget = (settings.gross_limit + net) / 2
    budgets = (long_budget, settings.gross_limit - long_budget)
    # If one side cannot absorb its budget, scale BOTH down to retain the net band.
    scale = min(1, is_long.sum() * settings.position_limit / max(budgets[0], 1e-12),
                (~is_long).sum() * settings.position_limit / max(budgets[1], 1e-12))
    result = np.zeros(len(g))
    for mask, budget, sign in [(is_long, budgets[0], 1), (~is_long, budgets[1], -1)]:
        result[mask] = sign * capped_inverse_vol(g.loc[mask, 'rvol_21d'].to_numpy(), budget * scale,
                                                settings.position_limit)
    return pd.Series(result, index=g.index)


def size_positions(candidates, settings):
    return baseline_weights(candidates, settings)

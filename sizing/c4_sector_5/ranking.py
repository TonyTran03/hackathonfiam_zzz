"""STEP 2: turn forecasts and any extra feature columns into the ranking signal.

Edit SIGNAL_WEIGHTS to blend future signals; uncovered names contribute zero.
Carbon Arc is NOT active. FEATURES.md is its future input specification.
"""
import numpy as np
import pandas as pd

SMOOTH_MONTHS = 3
FORECAST_WEIGHT = 1.0
SIGNAL_WEIGHTS = {}  # Future example: {"ca_score": 0.1}, after adding that column in features.py.

def unit_rank(s):
    r = s.rank(method='average')
    sd = r.std(ddof=0)
    return (r - r.mean()) / (sd if sd else 1.0)

def neutralise(g):
    """Existing ranking recipe, independent of the retired sizing code."""
    y = g['signal'].to_numpy()
    sector = pd.get_dummies(g['sector'], drop_first=True, dtype=float).to_numpy()
    design = np.column_stack([np.ones(len(g)), unit_rank(g.me), g.beta_use, sector])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    return pd.Series(y - design @ coefficients, index=g.index)

def build_ranking(frame, settings):
    frame = frame.copy()
    frame['signal'] = FORECAST_WEIGHT * frame.groupby('target_month').forecast.transform(unit_rank)
    for column, weight in SIGNAL_WEIGHTS.items():
        if column not in frame:
            raise ValueError(f"Signal {column} is not provided by features.py")
        extra = frame.groupby('target_month')[column].transform(unit_rank).fillna(0)
        frame['signal'] += weight * extra
    frame['size'] = frame.groupby('target_month').me.transform(unit_rank)
    frame['score'] = np.nan
    for _, indexes in frame.groupby('target_month', sort=True).groups.items():
        frame.loc[indexes, 'score'] = neutralise(frame.loc[indexes]).to_numpy()
    frame = frame.sort_values(['permno','target_month'],kind='stable')
    frame['score'] = frame.groupby('permno').score.transform(
        lambda s:s.rolling(SMOOTH_MONTHS,min_periods=1).mean())
    return frame.sort_values(['target_month','permno'],kind='stable').reset_index(drop=True)

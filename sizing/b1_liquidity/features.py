"""STEP 1: add the time-series valuation column.

ni_me (net income / market equity) is earnings yield = 1/PE. The engine does
not load it, so we read it from the panel here and join on permno + eom.

The percentile is TRAILING ONLY: rolling(60) ends at the current eom, which is
the month BEFORE the position is formed, so no future information is used.
Caveat: the panel is a current-vintage snapshot, so earnings are as restated
today, not as first reported.
"""
import pandas as pd
import prediction_helpers as C

WINDOW_MONTHS = 60
MIN_MONTHS = 36


def add_features(frame):
    panel = pd.read_parquet(C.CHARS_PARQUET, columns=['permno', 'eom', 'ni_me'])
    panel['eom'] = pd.to_datetime(panel.eom)
    panel = panel.sort_values(['permno', 'eom'], kind='stable')

    # Percentile of today's earnings yield within this stock's own trailing
    # 5 years. High earnings yield = cheap, so PE percentile is 1 - that.
    yield_pct = panel.groupby('permno', sort=False).ni_me.transform(
        lambda s: s.rolling(WINDOW_MONTHS, min_periods=MIN_MONTHS).rank(pct=True))
    panel['pe_pct'] = 1.0 - yield_pct
    # Negative or zero earnings make PE meaningless: leave those unconstrained.
    panel.loc[panel.ni_me <= 0, 'pe_pct'] = float('nan')

    out = frame.merge(panel[['permno', 'eom', 'pe_pct']], on=['permno', 'eom'],
                      how='left', validate='many_to_one')
    if len(out) != len(frame):
        raise ValueError('Valuation join changed the row count.')
    return out

"""STEP 1: add input columns. Forecasts and stock characteristics arrive here.

FEATURES.md describes future Carbon Arc inputs. They are not loaded or used yet.
Add future joins here using permno + feature eom, never future returns.
Then give the new column a weight in ranking.py to make it a signal.
Do not put weight/exposure constraints in this file.
"""

def add_features(frame):
    # Future example: left-join point-in-time Carbon Arc observations here.
    # Keep uncovered stocks; adding a dataset must not silently drop them.
    return frame.copy()

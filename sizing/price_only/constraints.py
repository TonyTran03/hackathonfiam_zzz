"""STEP 4: deliberately naive equal-weight allocation, not risk repairs.
Price eligibility and candidate counts are in selection.py.
"""
GROSS = 2.0


def size_positions(candidates):
    """Equal long/short allocations. Edit the allocation math here if desired."""
    return candidates.side * GROSS / len(candidates)

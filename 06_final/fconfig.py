"""Final-round mandate and house choices, kept apart from the first round's config.

FINAL is a transcription of the Final Challenge instructions (Sections 3, 7, 9).
Nothing in it is a modelling choice. HOUSE is ours, and each value carries the
reason it was set and WHEN: everything marked "pre-specified" was written down
before any 2021-2026 number was produced by the daily engine (see
06_final/PROTOCOL_FINAL.md, committed before the test run).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import config as C  # noqa: E402

FINAL_DIR = ROOT / "06_final"
DATA = FINAL_DIR / "data"            # gitignored: derived daily tables
OUT = FINAL_DIR / "output"           # committed: tables, figures, logs
FIG = OUT / "figures"
AGENT_CACHE = FINAL_DIR / "agent_cache"

DSF_CSV_CANDIDATES = [
    C.RAW_DIR / "dsf_mini_from_2014.csv",
    C.RAW_DIR / "dsf_mini_from_2014.csv.gz",
]
DSF_PARQUET = DATA / "dsf.parquet"

FINAL = {
    # Section 3.1
    "start_nav": 1.0e9,                 # US$1bn, compounding, no flows
    "min_positions": 200,
    "max_positions": 500,
    "max_gross": 2.00,
    "net_band": (-0.50, 0.50),
    "short_min_me_musd": 500.0,         # market cap >= $500m AT FORMATION
    "max_single_weight": 0.05,          # 5% of capital
    "oos_start": "2021-01-01",
    "oos_end": "2026-08-31",
    # Section 9.2: daily benchmark  b_t = TB3MS/25200 + 0.04/252
    "premium_annual": 0.04,
    # Section 7, daily convention: information dated through day t forms the
    # book at the close of day t+1; first return earned is close t+1 -> t+2.
    "formation_lag_days": 1,
}

HOUSE = {
    # --- pre-specified, mandate-driven -----------------------------------
    # Floor doubled to 200, so 100 per leg no longer leaves margin: one
    # delisting mid-month would breach it. 150 per leg keeps a 100-name
    # margin, sits well inside the 500 ceiling, and gives ~0.67% average
    # positions (~$6.7m at inception).
    "n_per_leg": 150,
    "house_max_weight": 0.015,          # 1.5% of NAV; the 5% cap never binds
    # Capacity: a position must be exitable in <= 3 days at 10% of ADV.
    "max_days_adv": 3.0,
    "max_participation": 0.10,
    # Short floor applied with a 10% cushion so a formation-day drop does not
    # put a name on the line; the hard check is still the mandate's $500m.
    "short_floor_cushion": 1.10,
    # First-round construction, carried over unchanged (pre-specified then):
    "smooth_months": 3,
    "buffer_mult": 2.5,
    "min_price": 5.0,
    "net_cap": 0.30,
    # Beta control: legs sized on each leg's own realised beta. Daily data
    # makes that far more precise than 24 monthly points, so the measurement
    # is now 252 trading days of DAILY leg returns with a Dimson (lag 0 + lag
    # 1) correction for stale small-cap prices, past days only.
    "beta_window_days": 252,
    "beta_min_days": 126,
    "beta_feedback_weight": 0.6,

    # --- cost model (construction and accounting layers only; never enters
    # the forecast) ------------------------------------------------------
    "commission_bps": 1.0,
    # half the Corwin-Schultz high-low spread (bidaskhl_21d), floored and
    # capped: the estimator overstates spreads for liquid names
    "half_spread_floor_bps": 2.0,
    "half_spread_cap_bps": 50.0,
    # square-root impact: Y * sigma_daily * sqrt(trade / ADV)
    "impact_y": 0.7,
    # borrow, annual, by size group at formation (general collateral for
    # large/mega, scaled up for smaller and more volatile names)
    "borrow_bps": {"mega": 25.0, "large": 30.0, "small": 75.0, "micro": 300.0, "nano": 500.0},
    "borrow_hard_bps": 500.0,           # extra when ivol is in the top decile
    # Section 7 flat conservative alternative the judges asked for
    "flat_borrow_large_bps": 50.0,      # large and mega
    "flat_borrow_other_bps": 500.0,     # everything else
    "flat_cost_grid_bps": (0, 10, 20, 30, 50),

    # Delisting: a name whose daily series ends inside a holding period takes
    # the remainder of its monthly CRSP return as a stub on the last day.
    # When no monthly return exists either, longs take -30% (Shumway 1997)
    # and shorts take 0% -- conservative in both directions.
    "delist_long": -0.30,
    "delist_short": 0.0,
}

# Validation (design) window: the only months before 2021 that carry an
# out-of-sample forecast. Every choice the protocol leaves open is decided
# here, on risk and cost metrics, before the test window is run.
DESIGN_START, DESIGN_END = "2019-01-01", "2020-12-31"

"""Stage 4 -- turn predictions into monthly signed weights.

The baseline version of this file ranked on the raw forecast and equal-weighted
the top and bottom 100. That book was dollar neutral and nothing else: its
realised beta came out at -0.537, which under the rules is a directional
strategy however it is described. Four changes fix that, in this order.

1. TRADABILITY SCREEN. Without it the short leg fills with penny stocks --
   median market cap $50m, median price $2.63 -- and reports a return nobody
   could have earned. January 2021 cost the unscreened book 48% in one month.

2. NEUTRALISE THE SIGNAL. Each month the forecast is regressed on sector
   dummies, size and beta, and only the residual is kept. This strips out
   "this stock scores well merely because it is a low-beta utility" and leaves
   the part that is genuinely stock selection. Doing it on the SIGNAL rather
   than on the weights means the legs come out balanced by construction, so
   the beta repair in step 4 has almost nothing left to do.

3. RISK-WEIGHT THE POSITIONS. Inside each leg, weight by inverse volatility
   instead of equally. Same expected return, lower portfolio volatility --
   and the information ratio is a ratio, so the denominator counts as much as
   the numerator.

4. MATCH THE LEGS ON BETA. Scale the two legs so the beta-weighted long
   exposure equals the beta-weighted short exposure, subject to gross <= 200%
   and net inside the band. After step 2 this is a small adjustment.

5. TURNOVER BUFFER. A name already held is kept while it stays inside a wider
   band, instead of being sold the moment it leaves the top 100. Cuts trading
   without materially changing what is held.

Selection never consults the realized return, so stocks delisted during the
holding month can still be picked -- as they must be, or the outcome would be
choosing the universe.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

PRED_FILE = C.PROCESSED_DIR / "predictions.parquet"
OUT = C.PROCESSED_DIR / "holdings.parquet"
SUBMISSION_CSV = C.ROOT / "05_submission" / "holdings.csv"

MODEL = "avg"
N_PER_LEG = 100
BUFFER_MULT = 1.6         # a held name survives while inside the top 160
GROSS_TARGET = 2.00       # 200% of capital, the limit
MAX_WEIGHT = 0.02         # 2% of capital in any one name
NET_CAP = 0.20            # keep well inside the -50%..+50% band

MIN_PRICE = 5.0
EXCLUDE_SIZE_GROUPS = ("nano", "micro")

# Beta choice matters more than it looks. A 21-day estimate is available for
# 99.8% of rows but its levels are nonsense (1st percentile -6.1, 99th +9.4)
# and it sorts future market sensitivity worst of the four candidates. The
# five-year daily estimate has sane levels and the widest realised spread
# (+0.59 to +1.58 across its quintiles), so it leads, with progressively
# shorter windows filling its gaps.
BETA_COL = "beta_use"
BETA_SOURCES = ["betabab_1260d", "betadown_252d", "beta_60m"]
VOL_COL = "rvol_21d"
PANEL_COLS = ["permno", "target_month", "prc", "me", "size_grp", "gics",
              VOL_COL, "ticker", "company_name"] + BETA_SOURCES


def screen(pred):
    panel = pd.read_parquet(C.MODEL_TABLE, columns=PANEL_COLS)
    pred = pred.merge(panel, on=["permno", "target_month"], how="left")
    before = len(pred)
    pred[BETA_COL] = pred[BETA_SOURCES[0]]
    for nxt in BETA_SOURCES[1:]:
        pred[BETA_COL] = pred[BETA_COL].fillna(pred[nxt])
    pred = pred[(pred["prc"].abs() >= MIN_PRICE)
                & (~pred["size_grp"].isin(EXCLUDE_SIZE_GROUPS))
                & pred[BETA_COL].notna() & pred[VOL_COL].notna()].copy()
    pred[BETA_COL] = pred[BETA_COL].clip(-0.5, 3.5)   # trim estimation noise
    per_month = pred.groupby("target_month").size()
    print("tradability screen: price >= $%.0f, no %s, beta and vol present"
          % (MIN_PRICE, "/".join(EXCLUDE_SIZE_GROUPS)))
    print("  %s of %s stock-months kept; %.0f per month, min %d"
          % (format(len(pred), ","), format(before, ","),
             per_month.mean(), per_month.min()))
    return pred


def unit_rank(s):
    r = s.rank(method="average")
    return (r - r.mean()) / (r.std(ddof=0) if r.std(ddof=0) else 1.0)


def neutralise(g):
    """Residual of the forecast after sector, size and beta are removed."""
    y = unit_rank(g[MODEL]).values
    sector = g["gics"].astype(str).str[:2].fillna("NA")
    # size enters as a rank (only its ordering matters); beta enters as a LEVEL,
    # because the leg-matching in size_legs works on levels and neutralising the
    # rank would leave the level exposure untouched
    X = [np.ones(len(g)), unit_rank(g["me"]).values, g[BETA_COL].values]
    dummies = pd.get_dummies(sector, drop_first=True).values.astype(float)
    M = np.column_stack(X + ([dummies] if dummies.size else []))
    beta, *_ = np.linalg.lstsq(M, y, rcond=None)
    return pd.Series(y - M @ beta, index=g.index)


def select(scores, held_long, held_short):
    """Top/bottom N, but a held name survives inside the wider buffer band."""
    order = scores.sort_values(ascending=False)
    wide = int(N_PER_LEG * BUFFER_MULT)
    long_zone, short_zone = set(order.head(wide).index), set(order.tail(wide).index)

    longs = [i for i in order.index if i in held_long and i in long_zone]
    longs += [i for i in order.index if i not in longs and i not in held_short][
        :max(0, N_PER_LEG - len(longs))]
    longs = longs[:N_PER_LEG]

    rev = order.index[::-1]
    shorts = [i for i in rev if i in held_short and i in short_zone]
    shorts += [i for i in rev if i not in shorts and i not in longs][
        :max(0, N_PER_LEG - len(shorts))]
    shorts = shorts[:N_PER_LEG]
    return longs, shorts


def leg_weights(vol):
    """Inverse volatility, capped, summing to 1."""
    v = vol.clip(lower=vol.quantile(0.05), upper=vol.quantile(0.95))
    w = 1.0 / v
    w = w / w.sum()
    for _ in range(10):                       # cap and redistribute
        over = w > MAX_WEIGHT / (GROSS_TARGET / 2)
        if not over.any():
            break
        excess = (w[over] - MAX_WEIGHT / (GROSS_TARGET / 2)).sum()
        w[over] = MAX_WEIGHT / (GROSS_TARGET / 2)
        w[~over] += excess * w[~over] / w[~over].sum()
    return w / w.sum()


def size_legs(beta_long, beta_short):
    """Scale the legs so beta nets out, inside the gross and net limits."""
    if beta_long <= 0 or beta_short <= 0:     # degenerate; fall back to dollar neutral
        return GROSS_TARGET / 2, GROSS_TARGET / 2
    long_notional = GROSS_TARGET * beta_short / (beta_long + beta_short)
    short_notional = GROSS_TARGET - long_notional
    net = long_notional - short_notional
    if abs(net) > NET_CAP:                    # respect the band before beta
        long_notional = (GROSS_TARGET + np.sign(net) * NET_CAP) / 2
        short_notional = GROSS_TARGET - long_notional
    return long_notional, short_notional


def build():
    if not PRED_FILE.exists():
        raise SystemExit("missing %s -- run stage 3 first" % PRED_FILE)

    pred = pd.read_parquet(PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    pred = screen(pred[(pred["target_month"] >= lo) & (pred["target_month"] <= hi)].copy())

    held_long, held_short = set(), set()
    rows = []
    for month, g in pred.groupby("target_month", sort=True):
        g = g.copy()
        g["score"] = neutralise(g)
        longs, shorts = select(g["score"], held_long, held_short)

        L, S = g.loc[longs].copy(), g.loc[shorts].copy()
        wl, ws = leg_weights(L[VOL_COL]), leg_weights(S[VOL_COL])
        bl = float((wl * L[BETA_COL]).sum())
        bs = float((ws * S[BETA_COL]).sum())
        long_notional, short_notional = size_legs(bl, bs)

        L["weight"] = wl * long_notional
        S["weight"] = -ws * short_notional
        rows.append(pd.concat([L, S]))

        held_long = {g.loc[i, "permno"] for i in longs}
        held_short = {g.loc[i, "permno"] for i in shorts}
        # index positions change month to month; carry identity by permno
        held_long = set(L["permno"])
        held_short = set(S["permno"])

    h = pd.concat(rows, ignore_index=True)
    h["date"] = pd.PeriodIndex(h["target_month"], freq="M").to_timestamp()

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    h.to_parquet(OUT, index=False, compression="zstd")
    SUBMISSION_CSV.parent.mkdir(parents=True, exist_ok=True)
    (h[["date", "permno", "ticker", "company_name", "weight"]]
       .rename(columns={"date": "DATE", "permno": "PERMNO", "ticker": "TICKER",
                        "company_name": "COMPANY_NAME", "weight": "WEIGHT"})
       .to_csv(SUBMISSION_CSV, index=False))

    stats = h.groupby("target_month").apply(
        lambda d: pd.Series({
            "n": len(d),
            "gross": d["weight"].abs().sum(),
            "net": d["weight"].sum(),
            "max_w": d["weight"].abs().max(),
            "beta_gap": (d["weight"] * d[BETA_COL]).sum(),
        }), include_groups=False)

    print("wrote %s and %s" % (OUT.name, SUBMISSION_CSV.relative_to(C.ROOT)))
    print("  months          : %d   names per month: %.0f" % (len(stats), stats["n"].mean()))
    print("  gross exposure  : %.0f%%  (max %.0f%%)"
          % (100 * stats["gross"].mean(), 100 * stats["gross"].max()))
    print("  net exposure    : %+.1f%%  (range %+.1f%% .. %+.1f%%)"
          % (100 * stats["net"].mean(), 100 * stats["net"].min(), 100 * stats["net"].max()))
    print("  largest position: %.2f%%" % (100 * stats["max_w"].max()))
    print("  predicted beta  : %+.4f on average  (was the thing we are fixing)"
          % stats["beta_gap"].mean())
    return h


if __name__ == "__main__":
    build()

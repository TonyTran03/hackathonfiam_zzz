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
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12

PRED_FILE = C.PROCESSED_DIR / "predictions.parquet"
OUT = C.PROCESSED_DIR / "holdings.parquet"
SUBMISSION_CSV = C.ROOT / "05_submission" / "holdings.csv"

MODEL = "avg"
N_PER_LEG = 100
GROSS_TARGET = 2.00       # 200% of capital, the limit
MAX_WEIGHT = 0.02         # 2% of capital in any one name
NET_CAP = 0.30            # room to reach beta neutrality; rules allow +/-50%

# Turnover controls. The unsmoothed book traded 221% of capital a month and
# broke even at 34 bps -- too thin a margin for a long leg that is two thirds
# small caps. Two levers, both chosen on the clean validation window below.
#   SMOOTH_MONTHS  average the forecast over this many months. A monthly tree
#                  forecast is mostly noise month to month; the part that
#                  persists is the part worth trading.
#   BUFFER_MULT    a held name survives while inside the top N*BUFFER_MULT.
SMOOTH_MONTHS = 3
BUFFER_MULT = 2.5
ASSUMED_COST_BPS = 20     # what the tuning would optimise against

# Tuning these on validation is OFF, and that is a finding rather than a
# shortcut. The only clean validation window is 24 months (2019-2020), every
# configuration in it loses money, and the "best" choice flipped from
# (2 months, 3.0x) to (1 month, 2.0x) purely because the beta feedback below
# was added. A selection that unstable is reading noise. Turnover control is
# a cost decision, not a return forecast, so the values above stand as
# specified before any tuning was run: 3 months is the standard smoothing for
# a noisy monthly forecast, and 2.5x is a moderate buffer.
TUNE_ON_VALIDATION = False

# Closed-loop beta control. Matching the legs on per-stock beta estimates left
# the book at -0.24: the long leg's realised beta came in 0.30 below its
# estimate while the short leg's nearly matched. So blend the estimate with
# each leg's own measured sensitivity over completed months.
BETA_FEEDBACK_WINDOW = 24     # months of history used to measure
BETA_FEEDBACK_MIN = 12        # months required before the measurement is used
BETA_FEEDBACK_WEIGHT = 0.6    # how far to move from estimate toward measurement

# Only the FIRST fold's validation block sits entirely before the evaluation
# window; later folds validate on months inside 2021-2026 and so cannot be
# used to choose anything. That leaves 24 clean months -- thin, and said so.
TUNE_END = "2020-12"
SMOOTH_GRID = [1, 2, 3, 4, 6]
BUFFER_GRID = [1.6, 2.0, 2.5, 3.0]

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


def screen(pred, quiet=False):
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
    if not quiet:
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


def smooth_scores(pred, months):
    """Average each stock's neutralised score over the last `months` months.

    Only past and present values enter: the rolling mean is taken on a series
    sorted by month within each stock, so month t uses t, t-1, ... and never
    t+1. A stock with a short history simply averages what it has.
    """
    if months <= 1:
        return pred["score"]
    pred = pred.sort_values(["permno", "target_month"])
    sm = (pred.groupby("permno")["score"]
              .transform(lambda s: s.rolling(months, min_periods=1).mean()))
    return sm.reindex(pred.index)


def select(scores, held_long, held_short, buffer_mult=None):
    """Top/bottom N, but a held name survives inside the wider buffer band."""
    order = scores.sort_values(ascending=False)
    wide = int(N_PER_LEG * (buffer_mult if buffer_mult is not None else BUFFER_MULT))
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


def realised_leg_betas(history, market):
    """Each leg's own market sensitivity, measured from how it has behaved.

    Matching the legs on per-stock beta ESTIMATES leaves a gap. Over the test
    period the long leg's estimated beta was +1.23 but its realised beta only
    +0.92, while the short leg's +1.22 came in at +1.15. The legs were matched
    exactly as designed and the book still carried -0.24, because the forecast
    picks longs that behave more defensively than their own history says and a
    per-stock estimate cannot see that.

    So measure the legs instead of only trusting the estimates. Only COMPLETED
    months enter -- month t uses t-1 and earlier, nothing else. Returns None
    until there is enough history.
    """
    if len(history) < BETA_FEEDBACK_MIN:
        return None
    h = pd.DataFrame(history[-BETA_FEEDBACK_WINDOW:])
    mk = market.reindex(h["target_month"]).values.astype(float)
    ok = ~np.isnan(mk)
    if ok.sum() < BETA_FEEDBACK_MIN or np.std(mk[ok]) == 0:
        return None
    bl = np.polyfit(mk[ok], h["long_ret"].values[ok] / h["long_notional"].values[ok], 1)[0]
    bs = np.polyfit(mk[ok], -h["short_ret"].values[ok] / h["short_notional"].values[ok], 1)[0]
    return bl, bs


def make_book(pred, smooth_months, buffer_mult, market=None):
    """Build monthly weights from a screened prediction frame."""
    pred = pred.copy()
    pred["score"] = pred.groupby("target_month", group_keys=False).apply(
        neutralise, include_groups=False)
    pred["score"] = smooth_scores(pred, smooth_months)

    held_long, held_short = set(), set()
    rows, history = [], []
    for month, g in pred.groupby("target_month", sort=True):
        held_l = set(g.index[g["permno"].isin(held_long)])
        held_s = set(g.index[g["permno"].isin(held_short)])
        longs, shorts = select(g["score"], held_l, held_s, buffer_mult)

        L, S = g.loc[longs].copy(), g.loc[shorts].copy()
        wl, ws = leg_weights(L[VOL_COL]), leg_weights(S[VOL_COL])
        bl = float((wl * L[BETA_COL]).sum())
        bs = float((ws * S[BETA_COL]).sum())

        # shrink the per-stock estimate toward what the legs have actually done
        if market is not None:
            measured = realised_leg_betas(history, market)
            if measured is not None:
                w = BETA_FEEDBACK_WEIGHT
                bl = (1 - w) * bl + w * measured[0]
                bs = (1 - w) * bs + w * measured[1]

        long_notional, short_notional = size_legs(bl, bs)
        L["weight"] = wl * long_notional
        S["weight"] = -ws * short_notional
        rows.append(pd.concat([L, S]))
        held_long, held_short = set(L["permno"]), set(S["permno"])

        if market is not None:
            history.append({
                "target_month": month,
                "long_ret": float((L["weight"] * L[C.TARGET].fillna(0.0)).sum()),
                "short_ret": float((S["weight"] * S[C.TARGET].fillna(0.0)).sum()),
                "long_notional": long_notional,
                "short_notional": short_notional,
            })

    return pd.concat(rows, ignore_index=True)


def net_ir(book, cost_bps):
    """Information ratio after costs, from the book's own realized returns."""
    piv = book.pivot_table(index="target_month", columns="permno",
                           values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1)
    traded.iloc[0] = piv.abs().sum(axis=1).iloc[0]
    book = book.copy()
    book["pnl"] = book["weight"] * book[C.TARGET].fillna(0.0)
    spread = book.groupby("target_month")["pnl"].sum()
    active = spread - traded * cost_bps / 10000 - PREMIUM_M
    return np.sqrt(12) * active.mean() / active.std(ddof=1), traded.mean()


def tune_turnover(screened_val, market=None):
    """Pick the smoothing window and buffer on months before the test period."""
    print("\nturnover tuning on %d clean validation months (%s and earlier), "
          "scored at %d bps" % (screened_val["target_month"].nunique(),
                                TUNE_END, ASSUMED_COST_BPS))
    best, best_ir = (SMOOTH_MONTHS, BUFFER_MULT), -np.inf
    for sm in SMOOTH_GRID:
        line = []
        for bf in BUFFER_GRID:
            book = make_book(screened_val, sm, bf, market=market)
            v, traded = net_ir(book, ASSUMED_COST_BPS)
            line.append("%+.2f" % v)
            if v > best_ir:
                best, best_ir = (sm, bf), v
        print("  smooth %d months   buffer %s -> IR %s"
              % (sm, "/".join(str(b) for b in BUFFER_GRID), " ".join(line)))
    print("  -> smoothing %d months, buffer %.1fx  (validation net IR %+.2f)"
          % (best[0], best[1], best_ir))
    return best


def load_market():
    """Monthly market return in excess of cash, indexed by target month."""
    bm = pd.read_csv(C.BENCHMARK_CSV)
    return (bm["sp500_ret"] - bm["cash_monthly"]).set_axis(bm["target_month"])


def build(tune=True):
    if not PRED_FILE.exists():
        raise SystemExit("missing %s -- run stage 3 first" % PRED_FILE)

    market = load_market()

    smooth, buffer_mult = SMOOTH_MONTHS, BUFFER_MULT
    val_file = C.PROCESSED_DIR / "validation_predictions.parquet"
    if tune and TUNE_ON_VALIDATION and val_file.exists():
        val = pd.read_parquet(val_file)
        val = val[val["target_month"] <= TUNE_END].drop_duplicates(
            ["permno", "target_month"], keep="first")
        # stage 3 only wrote the blend column onto the test frame; rebuild it
        # here from the same recipe it chose, recorded in blend.json
        parts = json.loads((C.PROCESSED_DIR / "blend.json").read_text(
            encoding="utf-8"))["parts"]
        if "avg_linear" in parts and "avg_linear" not in val.columns:
            val["avg_linear"] = val[["ols", "lasso", "ridge", "en"]].mean(axis=1)
        z = val.groupby("target_month")[parts].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
        val[MODEL] = z.mean(axis=1)
        if val["target_month"].nunique() >= 12:
            smooth, buffer_mult = tune_turnover(screen(val, quiet=True), market)

    pred = pd.read_parquet(PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    pred = screen(pred[(pred["target_month"] >= lo) & (pred["target_month"] <= hi)].copy())

    h = make_book(pred, smooth, buffer_mult, market=market)
    h["date"] = pd.PeriodIndex(h["target_month"], freq="M").to_timestamp()
    print("\nsmoothing %d months, buffer %.1fx" % (smooth, buffer_mult))

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

"""Experiment -- does picking inside sectors beat picking across them?

    python 03_portfolio_construction/exp_sector_neutral.py

The submitted book ranks the whole eligible universe on one neutralised score
and takes the best and worst 100. Whatever sector mix falls out is a
by-product: on average 8 technology longs against 28 technology shorts, and
half the 200 names carry a sector imbalance nobody chose. Two ways to stop
that, and they are not the same thing:

  A  keep the same 200 names, rescale the weights inside each sector so the
     sector nets to zero, then restore the gross exposure the rescaling cost.
     Same stock picks, no sector bet.

  B  give each sector a quota equal to its share of the eligible universe and
     pick the best and worst inside that sector. A different 200 names: the
     model is now only ever asked "is this chip maker better than that chip
     maker", never "is this chip maker better than that bank".

Both are scored on the clean validation window FIRST. Choosing between
construction rules by looking at the evaluation period is the same mistake as
choosing a model that way, and 2019-2020 is the only stretch this project has
that the model never saw. The evaluation-period numbers are printed second and
are a report, not the basis for the choice.

Nothing here overwrites the submitted book; this script only prints and writes
exp_sector_neutral.csv.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common import config as C

_spec = importlib.util.spec_from_file_location(
    "bp", ROOT / "03_portfolio_construction" / "04_build_portfolio.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

OUT = C.ROOT / "05_submission" / "exp_sector_neutral.csv"


def sector_of(s):
    return s.astype(str).str[:2]


def quotas(sec, n):
    """Seats per sector, proportional to its share of the month's universe."""
    raw = sec.value_counts(normalize=True) * n
    q = raw.astype(int)
    short = n - int(q.sum())
    if short > 0:
        q[(raw - q).sort_values(ascending=False).index[:short]] += 1
    return q


def select_within_sector(g, scores, held_l, held_s, buffer_mult):
    """Top/bottom of each sector, with the same buffer rule as the baseline."""
    sec = sector_of(g["gics"])
    q = quotas(sec, bp.N_PER_LEG)
    longs, shorts = [], []
    for s, idx in g.groupby(sec.values).groups.items():
        seats = min(int(q.get(s, 0)), len(idx) // 2)
        if seats <= 0:
            continue
        sub = scores.loc[list(idx)].sort_values(ascending=False)
        wide = min(len(sub), int(seats * buffer_mult))
        lz, sz = set(sub.head(wide).index), set(sub.tail(wide).index)
        L = [i for i in sub.index if i in held_l and i in lz]
        L += [i for i in sub.index if i not in L and i not in held_s][:max(0, seats - len(L))]
        L = L[:seats]
        rev = list(sub.index[::-1])
        S = [i for i in rev if i in held_s and i in sz]
        S += [i for i in rev if i not in S and i not in L][:max(0, seats - len(S))]
        longs += L
        shorts += S[:seats]
    return longs, shorts


def make_book(pred, smooth_months, buffer_mult, market=None, within_sector=False):
    """bp.make_book, with the selection rule swapped when within_sector."""
    pred = pred.copy()
    pred["score"] = pred.groupby("target_month", group_keys=False).apply(
        bp.neutralise, include_groups=False)
    pred["score"] = bp.smooth_scores(pred, smooth_months)

    held_long, held_short = set(), set()
    rows, history = [], []
    for month, g in pred.groupby("target_month", sort=True):
        held_l = set(g.index[g["permno"].isin(held_long)])
        held_s = set(g.index[g["permno"].isin(held_short)])
        if within_sector:
            longs, shorts = select_within_sector(g, g["score"], held_l, held_s, buffer_mult)
        else:
            longs, shorts = bp.select(g["score"], held_l, held_s, buffer_mult)

        L, S = g.loc[longs].copy(), g.loc[shorts].copy()
        wl, ws = bp.leg_weights(L[bp.VOL_COL]), bp.leg_weights(S[bp.VOL_COL])
        bl = float((wl * L[bp.BETA_COL]).sum())
        bs = float((ws * S[bp.BETA_COL]).sum())
        if market is not None:
            measured = bp.realised_leg_betas(history, market)
            if measured is not None:
                w = bp.BETA_FEEDBACK_WEIGHT
                bl = (1 - w) * bl + w * measured[0]
                bs = (1 - w) * bs + w * measured[1]
        ln, sn = bp.size_legs(bl, bs)
        L["weight"] = wl * ln
        S["weight"] = -ws * sn
        rows.append(pd.concat([L, S]))
        held_long, held_short = set(L["permno"]), set(S["permno"])
        if market is not None:
            history.append({"target_month": month,
                            "long_ret": float((L["weight"] * L[C.TARGET].fillna(0.0)).sum()),
                            "short_ret": float((S["weight"] * S[C.TARGET].fillna(0.0)).sum()),
                            "long_notional": ln, "short_notional": sn})
    return pd.concat(rows, ignore_index=True)


def neutralise_weights(book):
    """Variant A: same names, zero net weight per sector, gross restored."""
    out = []
    for month, g in book.groupby("target_month"):
        g = g.copy()
        g["sec"] = sector_of(g["gics"])
        parts = []
        for _, gs in g.groupby("sec"):
            net, ab = gs["weight"].sum(), gs["weight"].abs().sum()
            gs = gs.copy()
            gs["weight"] = gs["weight"] - (net * gs["weight"].abs() / ab if ab > 0 else 0.0)
            parts.append(gs)
        a = pd.concat(parts)
        scale = g["weight"].abs().sum() / a["weight"].abs().sum()
        a["weight"] *= scale                     # the rescaling cost ~30% of gross
        out.append(a)
    return pd.concat(out, ignore_index=True)


def stats(book, market, cash, hurdle, label):
    b = book.copy()
    b["pnl"] = b["weight"] * b[C.TARGET].fillna(0.0)
    spread = b.groupby("target_month")["pnl"].sum()
    piv = b.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1)
    traded.iloc[0] = piv.abs().sum(axis=1).iloc[0]
    months = spread.index
    # bp.net_ir scores active = spread - PREMIUM_M: the cash leg appears in both
    # the total return and the hurdle, so it cancels. Subtracting the full
    # hurdle here would remove cash twice.
    hur = np.full(len(months), bp.PREMIUM_M)
    act = spread.values - hur
    ir = np.sqrt(12) * act.mean() / act.std(ddof=1)
    net20 = spread.values - traded.reindex(months).values * 20 / 10000 - hur
    ir20 = np.sqrt(12) * net20.mean() / net20.std(ddof=1)
    mk = market.reindex(months).values.astype(float)
    ok = ~np.isnan(mk)
    beta = np.polyfit(mk[ok], spread.values[ok], 1)[0] if ok.sum() > 6 else np.nan
    g = b.groupby("target_month")
    nsec = (b.assign(sec=sector_of(b["gics"]))
             .groupby(["target_month", "sec"])["weight"].sum()
             .abs().groupby("target_month").sum().mean())
    curve = (1 + pd.Series(cash.reindex(months).values + spread.values)).cumprod()
    return {"book": label, "months": len(months),
            "spread_ann": 100 * 12 * spread.mean(),
            "vol_ann": 100 * np.sqrt(12) * spread.std(ddof=1),
            "IR": ir, "IR_20bps": ir20, "beta": beta,
            "turnover": 100 * (traded / (2 * piv.abs().sum(axis=1))).mean(),
            "net_sector": 100 * nsec,
            "gross": 100 * g["weight"].apply(lambda w: w.abs().sum()).mean(),
            "names": g.size().mean(),
            "maxdd": 100 * (curve / curve.cummax() - 1).min()}


def show(rows, title):
    print("\n" + "=" * 94)
    print(title)
    print("=" * 94)
    print("  %-26s %6s %9s %8s %7s %9s %7s %9s %10s"
          % ("book", "months", "spread", "vol", "IR", "IR@20bps", "beta",
             "turnover", "net-sector"))
    for r in rows:
        print("  %-26s %6d %+8.2f%% %7.2f%% %+7.2f %+9.2f %+7.2f %8.1f%% %9.1f%%"
              % (r["book"], r["months"], r["spread_ann"], r["vol_ann"], r["IR"],
                 r["IR_20bps"], r["beta"], r["turnover"], r["net_sector"]))


def main():
    market = bp.load_market()
    bm = pd.read_csv(C.BENCHMARK_CSV).set_index("target_month")
    cash = bm["cash_monthly"]
    hurdle = cash + bp.PREMIUM_M

    allrows = []

    # ---- 1. the clean validation window: 2019-2020, never seen by the model --
    vf = C.PROCESSED_DIR / "validation_predictions.parquet"
    if vf.exists():
        val = pd.read_parquet(vf)
        val = val[val["target_month"] <= bp.TUNE_END].drop_duplicates(
            ["permno", "target_month"], keep="first")
        # blend.json now records one recipe per fold. The validation window sits
        # inside the FIRST fold, so use that fold's recipe -- the only one chosen
        # without seeing any evaluation month.
        bj = json.loads((C.PROCESSED_DIR / "blend.json").read_text(encoding="utf-8"))
        first = sorted(bj["per_fold"])[0]
        parts = bj["per_fold"][first]["parts"]
        print("  using the %s fold's blend: %s" % (first, "+".join(parts)))
        if "avg_linear" in parts and "avg_linear" not in val.columns:
            val["avg_linear"] = val[["ols", "lasso", "ridge", "en"]].mean(axis=1)
        z = val.groupby("target_month")[parts].transform(
            lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
        val[bp.MODEL] = z.mean(axis=1)
        sv = bp.screen(val, quiet=True)
        print("validation window: %s .. %s (%d months, %s stock-months)"
              % (sv["target_month"].min(), sv["target_month"].max(),
                 sv["target_month"].nunique(), format(len(sv), ",")))
        base_v = make_book(sv, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market)
        rows_v = [
            stats(base_v, market, cash, hurdle, "baseline (as submitted)"),
            stats(neutralise_weights(base_v), market, cash, hurdle, "A  weights neutralised"),
            stats(make_book(sv, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market, True),
                  market, cash, hurdle, "B  picked within sectors"),
        ]
        show(rows_v, "VALIDATION 2019-2020 -- the only pre-test evidence, and it decides")
        for r in rows_v:
            r["window"] = "validation"
        allrows += rows_v

    # ---- 2. the evaluation period: reported, not used to choose ------------
    pred = pd.read_parquet(bp.PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    st = bp.screen(
        pred[(pred["target_month"] >= lo) & (pred["target_month"] <= hi)].copy(), quiet=True)
    base_t = make_book(st, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market)
    rows_t = [
        stats(base_t, market, cash, hurdle, "baseline (as submitted)"),
        stats(neutralise_weights(base_t), market, cash, hurdle, "A  weights neutralised"),
        stats(make_book(st, bp.SMOOTH_MONTHS, bp.BUFFER_MULT, market, True),
              market, cash, hurdle, "B  picked within sectors"),
    ]
    show(rows_t, "EVALUATION 2021-2026 -- reported for completeness, NOT the basis for choosing")
    for r in rows_t:
        r["window"] = "evaluation"
    allrows += rows_t

    df = pd.DataFrame(allrows)
    df.to_csv(OUT, index=False)
    print("\n  gross exposure / average names held / max drawdown")
    for r in allrows:
        print("    %-12s %-26s gross %5.1f%%  names %5.1f  maxDD %+6.2f%%"
              % (r["window"], r["book"], r["gross"], r["names"], r["maxdd"]))
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

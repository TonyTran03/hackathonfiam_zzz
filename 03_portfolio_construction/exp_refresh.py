"""Is variant S's gain about sectors, or about evicting stale positions?

    python 03_portfolio_construction/exp_refresh.py

The dose curve in 14_sector_dose.py showed that only about a third of variant
S's extra return is explained by the sector exposure it removes. The other two
thirds come from the swap the rule performs to get there: drop the
lowest-scoring long in an over-capped sector, put back the highest-scoring
unselected candidate.

In a pure global ranking that swap cannot help. The highest-scoring unselected
name is number 101, and it scores below every one of the hundred already held,
so replacing the hundredth with the hundred-and-first makes the book worse.
The swap can only be an upgrade because the book is NOT the top hundred: the
turnover buffer keeps names that have drifted far down the ranking, and the
lowest-scoring long in a sector is usually one of them.

If that is right, then variant S is partly a turnover rule wearing a sector
rule's clothes, and the same gain should appear with no sector logic at all.
Two ways to check, both scored on the clean validation window first:

  buffer    tighten the buffer and let the ordinary rule evict stale names
  refresh   keep the buffer, but each month force out the N lowest-scoring
            longs and N highest-scoring shorts and replace them from the top
            of the unselected list -- variant S's swap without its sector test

A third arm reproduces the sector cap itself, so all three sit on one axis.
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
    "sn", ROOT / "03_portfolio_construction" / "exp_sector_neutral.py")
sn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sn)
bp = sn.bp

OUT = C.ROOT / "05_submission" / "exp_refresh.csv"
GICS = set("10 15 20 25 30 35 40 45 50 55 60".split())
CAP = 5


def sector_of(s):
    x = s.astype(str).str[:2]
    return x.where(x.isin(GICS), "??")


def refresh(longs, shorts, scores, n):
    """Evict the n weakest longs and n weakest shorts; refill from the top.

    No sector test anywhere in here. This is variant S's swap with its reason
    removed, which is the whole point of the arm.
    """
    if n <= 0:
        return longs, shorts
    order = scores.sort_values(ascending=False)
    held = set(longs) | set(shorts)
    free = [i for i in order.index if i not in held]
    ls = scores.loc[longs].sort_values()
    drop_l = list(ls.index[:n])
    add_l = free[:n]
    ss = scores.loc[shorts].sort_values(ascending=False)
    drop_s = list(ss.index[:n])
    add_s = [i for i in reversed(free) if i not in add_l][:n]
    longs = [i for i in longs if i not in drop_l] + add_l
    shorts = [i for i in shorts if i not in drop_s] + add_s
    return longs, shorts


def cap_sectors(longs, shorts, scores, sector, cap):
    """Variant S's published rule, reimplemented here for the comparison arm."""
    longs, shorts = list(longs), list(shorts)
    for _ in range(200):
        cl = pd.Series(sector.loc[longs]).value_counts()
        cs = pd.Series(sector.loc[shorts]).value_counts()
        diff = cl.subtract(cs, fill_value=0)
        over = diff[diff > cap]
        under = diff[diff < -cap]
        if over.empty and under.empty:
            break
        held = set(longs) | set(shorts)
        order = scores.sort_values(ascending=False)
        if not over.empty:
            s = over.idxmax()
            inside = [i for i in longs if sector.loc[i] == s]
            worst = scores.loc[inside].idxmin()
            cand = [i for i in order.index
                    if i not in held and diff.get(sector.loc[i], 0) < cap]
            if not cand:
                break
            longs = [i for i in longs if i != worst] + [cand[0]]
        else:
            s = under.idxmin()
            inside = [i for i in shorts if sector.loc[i] == s]
            worst = scores.loc[inside].idxmax()
            cand = [i for i in reversed(order.index)
                    if i not in held and diff.get(sector.loc[i], 0) > -cap]
            if not cand:
                break
            shorts = [i for i in shorts if i != worst] + [cand[0]]
    return longs, shorts


def make_book(pred, smooth, buf, market, arm=None, n=0):
    pred = pred.copy()
    pred["score"] = pred.groupby("target_month", group_keys=False).apply(
        bp.neutralise, include_groups=False)
    pred["score"] = bp.smooth_scores(pred, smooth)
    pred["sec"] = sector_of(pred["gics"])

    held_long, held_short = set(), set()
    rows, history = [], []
    for month, g in pred.groupby("target_month", sort=True):
        hl = set(g.index[g["permno"].isin(held_long)])
        hs = set(g.index[g["permno"].isin(held_short)])
        longs, shorts = bp.select(g["score"], hl, hs, buf)
        if arm == "refresh":
            longs, shorts = refresh(longs, shorts, g["score"], n)
        elif arm == "cap":
            longs, shorts = cap_sectors(longs, shorts, g["score"], g["sec"], CAP)

        L, S = g.loc[longs].copy(), g.loc[shorts].copy()
        wl, ws = bp.leg_weights(L[bp.VOL_COL]), bp.leg_weights(S[bp.VOL_COL])
        bl = float((wl * L[bp.BETA_COL]).sum())
        bs = float((ws * S[bp.BETA_COL]).sum())
        measured = bp.realised_leg_betas(history, market)
        if measured is not None:
            w = bp.BETA_FEEDBACK_WEIGHT
            bl, bs = (1 - w) * bl + w * measured[0], (1 - w) * bs + w * measured[1]
        ln, sn_ = bp.size_legs(bl, bs)
        L["weight"], S["weight"] = wl * ln, -ws * sn_
        rows.append(pd.concat([L, S]))
        held_long, held_short = set(L["permno"]), set(S["permno"])
        history.append({"target_month": month,
                        "long_ret": float((L["weight"] * L[C.TARGET].fillna(0.0)).sum()),
                        "short_ret": float((S["weight"] * S[C.TARGET].fillna(0.0)).sum()),
                        "long_notional": ln, "short_notional": sn_})
    return pd.concat(rows, ignore_index=True)


def score(book):
    b = book.copy()
    b["pnl"] = b["weight"] * b[C.TARGET].fillna(0.0)
    sp = b.groupby("target_month")["pnl"].sum()
    piv = b.pivot_table(index="target_month", columns="permno",
                        values="weight", fill_value=0.0)
    traded = piv.diff().abs().sum(axis=1)
    traded.iloc[0] = piv.abs().sum(axis=1).iloc[0]
    act = sp.values - bp.PREMIUM_M
    # Net of costs. The refresh arms trade half again as much as the baseline,
    # and an information ratio quoted gross rewards exactly that. Whatever
    # survives here is the only part worth reporting.
    net = {}
    for bps in (10, 20, 30):
        a = sp.values - traded.values * bps / 10000 - bp.PREMIUM_M
        net["IR_%dbps" % bps] = np.sqrt(12) * a.mean() / a.std(ddof=1)
    nsec = (b.assign(sec=sector_of(b["gics"]))
             .groupby(["target_month", "sec"])["weight"].sum()
             .abs().groupby("target_month").sum().mean())
    # how far down the ranking does the book reach?
    rank = b.groupby("target_month")["score"].rank(ascending=False, pct=True)
    return {"IR": np.sqrt(12) * act.mean() / act.std(ddof=1), **net,
            "spread": 100 * 12 * sp.mean(),
            "vol": 100 * np.sqrt(12) * sp.std(ddof=1),
            "turnover": 100 * (traded / (2 * piv.abs().sum(axis=1))).mean(),
            "net_sector": 100 * nsec}


def main():
    market = bp.load_market()
    bj = json.loads((C.PROCESSED_DIR / "blend.json").read_text(encoding="utf-8"))
    parts = bj["per_fold"][sorted(bj["per_fold"])[0]]["parts"]
    val = pd.read_parquet(C.PROCESSED_DIR / "validation_predictions.parquet")
    val = val[val["target_month"] <= bp.TUNE_END].drop_duplicates(
        ["permno", "target_month"], keep="first")
    if "avg_linear" in parts and "avg_linear" not in val.columns:
        val["avg_linear"] = val[["ols", "lasso", "ridge", "en"]].mean(axis=1)
    z = val.groupby("target_month")[parts].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) else 1.0))
    val[bp.MODEL] = z.mean(axis=1)
    pred = pd.read_parquet(bp.PRED_FILE)
    lo, hi = C.COMPETITION["oos_start"], C.COMPETITION["oos_end"]
    WIN = [("validation", bp.screen(val, quiet=True)),
           ("evaluation", bp.screen(
               pred[(pred["target_month"] >= lo)
                    & (pred["target_month"] <= hi)].copy(), quiet=True))]

    rows = []
    for wname, W in WIN:
        print("\n" + "=" * 86)
        print("%s  -- does the gain need the sector rule?" % wname.upper())
        print("=" * 86)
        print("  %-30s %8s %8s %8s %8s %9s %10s"
              % ("arm", "IR gross", "@10bps", "@20bps", "@30bps", "turnover",
                 "net-sector"))
        arms = [("baseline (buffer 2.5)", dict(buf=2.5)),
                ("buffer 2.0, nothing else", dict(buf=2.0)),
                ("buffer 1.6, nothing else", dict(buf=1.6)),
                ("refresh 5/month, no sectors", dict(buf=2.5, arm="refresh", n=5)),
                ("refresh 10/month, no sectors", dict(buf=2.5, arm="refresh", n=10)),
                ("refresh 20/month, no sectors", dict(buf=2.5, arm="refresh", n=20)),
                ("sector cap 5 (variant S rule)", dict(buf=2.5, arm="cap"))]
        for label, kw in arms:
            buf = kw.pop("buf")
            s = score(make_book(W, bp.SMOOTH_MONTHS, buf, market, **kw))
            print("  %-30s %+8.2f %+8.2f %+8.2f %+8.2f %8.1f%% %9.1f%%"
                  % (label, s["IR"], s["IR_10bps"], s["IR_20bps"], s["IR_30bps"],
                     s["turnover"], s["net_sector"]))
            rows.append({"window": wname, "arm": label, **s})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

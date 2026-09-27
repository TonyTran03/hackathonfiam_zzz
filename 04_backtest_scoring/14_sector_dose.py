"""Why does removing the sector tilt raise volatility in one test and not the other?

    python 04_backtest_scoring/14_sector_dose.py

Two sector-neutral results disagree on what happens to risk. Rescaling the
weights inside each sector until the sector nets to zero raised volatility by
about a fifth. Variant S -- capping each sector's long-minus-short COUNT at
five and swapping names to get there -- left volatility unchanged while raising
return by about the same amount.

The obvious explanation is that they are not the same dose. Full weight
neutralisation takes the per-month sum of absolute sector net exposures from
about 90% of capital to 0%. Variant S takes it to 38%. If volatility rises with
the dose, both results can be right and there is nothing to investigate.

So this traces the whole curve. Weights inside each sector are shrunk toward
sector-neutral by a factor lambda, gross exposure is restored, and the book is
scored at each step. lambda = 0 is the traded book; lambda = 1 is full
neutrality; variant S's measured 38% of capital lands somewhere in between, and
its own numbers are printed on the same axis for comparison.

Everything runs on the submitted book -- holdings.parquet as merged from main --
so the comparison with variant S is like for like.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

PREMIUM_M = C.COMPETITION["benchmark_premium_annual"] / 12
HOLDINGS = C.PROCESSED_DIR / "holdings.parquet"
RETURNS = C.ROOT / "05_submission" / "portfolio_returns.csv"
VARIANT_S = C.ROOT / "05_submission" / "deck" / "variants" / \
            "variant_S_sector_cap_portfolio_returns.csv"
OUT = C.ROOT / "05_submission" / "sector_dose.csv"

GICS = set("10 15 20 25 30 35 40 45 50 55 60".split())


def sector_of(s):
    x = s.astype(str).str[:2]
    return x.where(x.isin(GICS), "??")


def shrink(h, lam):
    """Shrink each sector's net weight toward zero by lam, then restore gross.

    Restoring gross matters more than it looks. Zeroing the sector nets costs
    about 30% of gross exposure, and the hurdle does not shrink with the book,
    so an unrestored comparison charges the smaller book the same 4% and
    understates its information ratio. That is exactly the trap that made an
    earlier version of this comparison read 0.87 when it should have read 1.07.
    """
    out = []
    for month, g in h.groupby("target_month"):
        g = g.copy()
        parts = []
        for _, gs in g.groupby("sec"):
            net, ab = gs["weight"].sum(), gs["weight"].abs().sum()
            gs = gs.copy()
            gs["w"] = gs["weight"] - lam * (net * gs["weight"].abs() / ab if ab else 0.0)
            parts.append(gs)
        a = pd.concat(parts)
        a["w"] *= g["weight"].abs().sum() / a["w"].abs().sum()
        out.append(a)
    return pd.concat(out)


def score(a, weight_col="w"):
    sp = (a[weight_col] * a[C.TARGET].fillna(0.0)).groupby(a["target_month"]).sum()
    net_sec = (a.groupby(["target_month", "sec"])[weight_col].sum()
                .abs().groupby("target_month").sum().mean())
    act = sp.values - PREMIUM_M
    return {"spread_ann": 100 * 12 * sp.mean(),
            "vol_ann": 100 * np.sqrt(12) * sp.std(ddof=1),
            "IR": np.sqrt(12) * act.mean() / act.std(ddof=1),
            "net_sector": 100 * net_sec,
            "series": sp}


def main():
    h = pd.read_parquet(HOLDINGS)
    h["sec"] = sector_of(h["gics"])
    m = pd.read_csv(RETURNS)
    base_ir = np.sqrt(12) * m["active"].mean() / m["active"].std(ddof=1)

    print("=" * 84)
    print("SECTOR NEUTRALISATION AS A DOSE, on the submitted book (IR %+.2f)" % base_ir)
    print("=" * 84)
    print("  %-8s %11s %10s %9s %11s %11s"
          % ("lambda", "net-sector", "spread", "vol", "IR", "vol change"))

    rows, base = [], None
    for lam in [0.0, 0.25, 0.50, 0.75, 1.0]:
        s = score(shrink(h, lam))
        if base is None:
            base = s
        print("  %-8.2f %10.1f%% %+9.2f%% %8.2f%% %+10.2f %+10.1f%%"
              % (lam, s["net_sector"], s["spread_ann"], s["vol_ann"], s["IR"],
                 100 * (s["vol_ann"] / base["vol_ann"] - 1)))
        rows.append({"book": "lambda %.2f" % lam, "net_sector": s["net_sector"],
                     "spread_ann": s["spread_ann"], "vol_ann": s["vol_ann"],
                     "IR": s["IR"],
                     "vol_change_pct": 100 * (s["vol_ann"] / base["vol_ann"] - 1)})

    # Where does variant S sit on this axis, and does the curve explain it?
    if VARIANT_S.exists():
        v = pd.read_csv(VARIANT_S)
        v_ir = np.sqrt(12) * v["active"].mean() / v["active"].std(ddof=1)
        v_vol = 100 * np.sqrt(12) * v["spread"].std(ddof=1)
        v_sp = 100 * 12 * v["spread"].mean()
        print("\n  %-8s %10.1f%% %+9.2f%% %8.2f%% %+10.2f %+10.1f%%"
              % ("variantS", 38.2, v_sp, v_vol, v_ir,
                 100 * (v_vol / base["vol_ann"] - 1)))
        print("           (38.2%% is the figure protocol_variants.md reports for it)")
        rows.append({"book": "variant S", "net_sector": 38.2, "spread_ann": v_sp,
                     "vol_ann": v_vol, "IR": v_ir,
                     "vol_change_pct": 100 * (v_vol / base["vol_ann"] - 1)})

        # interpolate the dose curve to variant S's sector exposure
        d = pd.DataFrame(rows[:5])
        pred_vol = np.interp(38.2, d["net_sector"][::-1], d["vol_ann"][::-1])
        pred_sp = np.interp(38.2, d["net_sector"][::-1], d["spread_ann"][::-1])
        print("\n  At 38.2%% of capital the dose curve predicts vol %.2f%% and spread "
              "%+.2f%%;" % (pred_vol, pred_sp))
        print("  variant S delivers vol %.2f%% and spread %+.2f%%." % (v_vol, v_sp))
        print("  -> volatility %s the curve; return %s it."
              % ("matches" if abs(v_vol - pred_vol) < 0.5 else "does NOT match",
                 "matches" if abs(v_sp - pred_sp) < 1.5 else "does NOT match"))

        # month-by-month agreement with the traded book
        sp0 = base["series"]
        j = pd.DataFrame({"base": sp0}).join(
            v.set_index("target_month")["spread"].rename("vs"))
        gap = (j["vs"] - j["base"]).dropna()
        print("\n  variant S vs the traded book, month by month:")
        print("    correlation %+.3f   months differing by >1%%: %d of %d"
              % (j["vs"].corr(j["base"]), int((gap.abs() > 0.01).sum()), len(gap)))
        print("    mean gap %+.3f%%/month   t %+.2f"
              % (100 * gap.mean(), gap.mean() / (gap.std(ddof=1) / np.sqrt(len(gap)))))
        big = gap.nlargest(4)
        print("    biggest gains: %s"
              % ", ".join("%s %+.1f%%" % (k, 100 * x) for k, x in big.items()))
        rest = gap.drop(big.index)
        print("    excluding those 4: mean gap %+.3f%%/month -> %s"
              % (100 * rest.mean(), "still ahead" if rest.mean() > 0 else "gone"))

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

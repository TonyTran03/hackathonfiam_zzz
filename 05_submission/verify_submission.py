"""Check the submission package against the rules, end to end.

    python 05_submission/verify_submission.py

One pass over everything a grader opens: the five items the rules list, the
format of the two CSVs they read most carefully, and whether the deck, the
returns series and the holdings all describe the same book. Prints a PASS/FAIL
line per check and exits non-zero on any failure.

This is deliberately separate from run_checks.py, which asks whether the
STRATEGY obeys the competition's trading and look-ahead rules. This asks
whether the PACKAGE is internally consistent and complete -- a different
question, and the one that catches a stale file rather than a bad book.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SUB = Path(__file__).resolve().parent
ROOT = SUB.parent
sys.path.insert(0, str(ROOT))
from common import config as C

FAILS = []


def check(name, ok, detail=""):
    print("  [%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAILS.append(name)
    return ok


def main():
    print("=" * 78)
    print("1. THE FIVE ITEMS THE RULES LIST")
    print("=" * 78)
    check("deck as one PDF", (SUB / "FIAM_deck.pdf").exists())
    check("monthly holdings CSV", (SUB / "holdings.csv").exists())
    check("portfolio returns CSV", (SUB / "portfolio_returns.csv").exists())
    check("daily returns CSV (optional extra)", (SUB / "daily_returns.csv").exists())
    check("MAIN.py", (ROOT / "MAIN.py").exists())
    check("licence", (ROOT / "LICENSE").exists())
    print("  [ -- ] team CVs                                  supplied separately")

    try:
        from pypdf import PdfReader
        pages = len(PdfReader(str(SUB / "FIAM_deck.pdf")).pages)
        check("deck length inside 8 main + 10 appendix", pages <= 18,
              "%d pages" % pages)
        text = " ".join((p.extract_text() or "")
                        for p in PdfReader(str(SUB / "FIAM_deck.pdf")).pages)
        check("no unfilled placeholders on the deck", "FILL IN" not in text,
              "" if "FILL IN" not in text else "TEAM NAME still a placeholder")
    except ImportError:
        print("  [ -- ] pdf checks                                pypdf not installed")

    print("\n" + "=" * 78)
    print("2. HOLDINGS FILE, AGAINST THE FORMAT THE RULES SPECIFY")
    print("=" * 78)
    h = pd.read_csv(SUB / "holdings.csv")
    want = ["DATE", "PERMNO", "TICKER", "COMPANY_NAME", "WEIGHT"]
    check("columns exactly as specified", list(h.columns) == want, str(list(h.columns)))
    d = pd.to_datetime(h["DATE"])
    check("every date is the first of a month", bool((d.dt.day == 1).all()))
    months = sorted(d.dt.to_period("M").astype(str).unique())
    check("covers 01/2021 to 08/2026 with no gaps",
          months[0] == "2021-01" and months[-1] == "2026-08" and len(months) == 68,
          "%s .. %s, %d months" % (months[0], months[-1], len(months)))
    check("no missing ticker or company name",
          not h["TICKER"].isna().any() and not h["COMPANY_NAME"].isna().any())
    check("both legs present every month",
          bool(h.assign(s=np.sign(h["WEIGHT"])).groupby(d.dt.to_period("M"))["s"]
                .nunique().eq(2).all()))
    g = h.groupby(d.dt.to_period("M"))["WEIGHT"]
    check("gross never above 200% of NAV", bool(g.apply(lambda w: w.abs().sum()).max() <= 2.0 + 1e-9),
          "max %.4f" % g.apply(lambda w: w.abs().sum()).max())
    check("net inside +/-50%", bool(g.sum().abs().max() <= 0.5),
          "range %+.3f to %+.3f" % (g.sum().min(), g.sum().max()))
    check("100 to 500 names a month",
          bool(h.groupby(d.dt.to_period("M")).size().between(100, 500).all()),
          "%d a month" % h.groupby(d.dt.to_period("M")).size().iloc[0])

    print("\n" + "=" * 78)
    print("3. DO THE FILES DESCRIBE THE SAME BOOK?")
    print("=" * 78)
    m = pd.read_csv(SUB / "portfolio_returns.csv")
    check("returns cover the same 68 months",
          sorted(m["target_month"]) == months, "%d rows" % len(m))
    check("active = total - hurdle, exactly",
          bool((m["total"] - m["hurdle"] - m["active"]).abs().max() < 1e-12))

    hp = C.PROCESSED_DIR / "holdings.parquet"
    if hp.exists():
        p = pd.read_parquet(hp)
        spread = (p["weight"] * p[C.TARGET].fillna(0.0)).groupby(p["target_month"]).sum()
        gap = (m.set_index("target_month")["spread"] - spread).abs().max()
        check("returns reconcile with the holdings", bool(gap < 1e-10), "max gap %.1e" % gap)
        k = ["target_month", "permno"]
        hh = h.copy()
        hh.columns = [c.lower() for c in hh.columns]
        hh["target_month"] = pd.PeriodIndex(pd.to_datetime(hh["date"]), freq="M").astype(str)
        mg = p[k + ["weight"]].merge(hh[k + ["weight"]], on=k, how="outer",
                                     suffixes=("_p", "_c"), indicator=True)
        check("submitted CSV matches the built book",
              bool((mg["_merge"] == "both").all())
              and bool((mg["weight_p"] - mg["weight_c"]).abs().max() < 1e-12))

    print("\n" + "=" * 78)
    print("4. THE DECK'S OWN NUMBERS")
    print("=" * 78)
    pack = pd.read_csv(SUB / "deck_pack.csv")
    ir_pack = pack.loc[pack["metric"].str.contains("INFORMATION RATIO"), "value"].iloc[0]
    ir_live = np.sqrt(12) * m["active"].mean() / m["active"].std(ddof=1)
    check("headline IR matches the returns series",
          abs(float(ir_pack) - ir_live) < 0.005, "%s vs %+.4f live" % (ir_pack, ir_live))
    cs = SUB / "compliance_summary.csv"
    if cs.exists():
        c = pd.read_csv(cs).set_index("metric")["value"]
        check("no competition-rule failures", str(c.get("rule failures")) == "0",
              "%s rule, %s house-standard" % (c.get("rule failures"),
                                              c.get("house-standard failures")))

    print("\n" + "=" * 78)
    print("%d checks failed" % len(FAILS) if FAILS else "Everything checked passes")
    print("=" * 78)
    for f in FAILS:
        print("  FAILED: %s" % f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Split officer-change filings into abrupt departures and routine turnover.

Why this exists. Item 5.02 filings carry almost no signal in aggregate --
16,378 of them over the training window move next-month returns by -0.18%
with a monthly t of -1.2. That is exactly what a few abrupt exits buried in
mostly routine appointments would look like, so the hypothesis is that the
aggregate is diluted rather than empty. This script tests it.

    python 01_data/officer_triage.py            # classify and retest
    python 01_data/officer_triage.py --sample   # print what each rule caught

THE BOILERPLATE TRAP, which has to be handled first. The item's own heading
is "Departure of Directors or Certain Officers; Election of Directors;
Appointment of Certain Officers; Compensatory Arrangements of Certain
Officers" -- every keyword worth searching for is already in the title of
every filing. Measured raw, "appoint" appears in 99.2% of these documents and
sub-item markers (a) through (d) in 88-100%. Strip the heading and the same
words fall to sensible rates: appoint 54.5%, resign 31.7%, retire 20.2%. Any
classifier trained on the unstripped text would be learning the title.

No language model is involved. The rules are read off the documents, and the
sample mode exists so they can be checked by eye.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

OUT = C.PROCESSED_DIR / "officer_triage.parquet"
TRAIN_END = "2018-12"

HEADING = re.compile(
    r"item\s*5\.02[.:\s]*"
    r"(departure of directors[^.]{0,220}?officers?[.;]?)?", re.I)
TAIL = re.compile(
    r"^[^.]{0,240}?(compensatory arrangements of certain officers|"
    r"appointment of certain officers|election of directors)[.;]?\s*", re.I)

# An exit that was not planned. Weighted by how unambiguous each phrase is.
ABRUPT = [
    (r"effective immediately", 2.0),
    (r"resigned?\b", 1.5),
    (r"mutual(ly)? agree", 2.0),
    (r"terminat(ed|ion) (of|his|her|the) employment", 2.0),
    (r"removed (from|as)", 2.0),
    (r"stepp?(ed|ing) down", 1.5),
    (r"pursue (other|professional|personal)", 1.0),
    (r"without (good )?cause", 1.0),
    (r"separation agreement", 1.5),
    (r"placed on (administrative )?leave", 2.5),
]
# Planned turnover, or not a departure at all.
ROUTINE = [
    (r"retire(ment|s|d)?\b", 1.5),
    (r"increas\w+ the size of the board", 2.0),
    (r"elected? (as )?(a )?(new )?director", 1.0),
    (r"appointed? .{0,40}(to (the )?board|as a director)", 1.0),
    (r"succeed|successor", 1.0),
    (r"annual meeting", 1.5),
    (r"compensat\w+ (arrangement|committee) approv", 1.5),
    (r"grant(ed)? .{0,30}(restricted stock|options)", 1.5),
    (r"amend\w* .{0,30}employment agreement", 1.5),
]


def strip_heading(text):
    b = re.sub(r"\s+", " ", text)
    m = HEADING.search(b)
    if m:
        b = TAIL.sub("", b[m.end():])
    return b


def score(body):
    lo = body.lower()
    a = sum(w for p, w in ABRUPT if re.search(p, lo))
    r = sum(w for p, w in ROUTINE if re.search(p, lo))
    return a, r


def classify():
    cols = ["items", "text", "permno", "filing_date", "ticker", "company_name"]
    f = pq.read_table(C.FILINGS_PARQUET, columns=cols).to_pandas()
    items = [list(x) if x is not None else [] for x in f["items"]]
    f = f[np.array(["5.02" in x for x in items])].copy()

    f["body"] = [strip_heading(t) for t in f["text"]]
    scored = [score(b) for b in f["body"]]
    f["abrupt_score"] = [a for a, _ in scored]
    f["routine_score"] = [r for _, r in scored]
    f["net"] = f["abrupt_score"] - f["routine_score"]
    f["is_abrupt"] = (f["net"] >= 2.0).astype(int)
    f["target_month"] = (pd.to_datetime(f["filing_date"]).dt.to_period("M") + 1).astype(str)

    print("%s officer-change filings" % format(len(f), ","))
    print("  classified abrupt : %s (%.1f%%)"
          % (format(int(f["is_abrupt"].sum()), ","), 100 * f["is_abrupt"].mean()))
    print("  classified routine: %s" % format(int((1 - f["is_abrupt"]).sum()), ","))

    monthly = (f.groupby(["permno", "target_month"])
                 .agg(abrupt=("is_abrupt", "max"),
                      n_officer_filings=("is_abrupt", "size"))
                 .reset_index())
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(OUT, index=False, compression="zstd")
    return f, monthly


def show_sample(f, n=4):
    print("\n--- classified ABRUPT ---")
    for _, r in f[f["is_abrupt"] == 1].sample(n, random_state=3).iterrows():
        print("  %s %s  (abrupt %.1f / routine %.1f)"
              % (r["ticker"], r["filing_date"], r["abrupt_score"], r["routine_score"]))
        print("    %s\n" % r["body"][:260])
    print("--- classified ROUTINE ---")
    for _, r in f[f["is_abrupt"] == 0].sample(n, random_state=3).iterrows():
        print("  %s %s  (abrupt %.1f / routine %.1f)"
              % (r["ticker"], r["filing_date"], r["abrupt_score"], r["routine_score"]))
        print("    %s\n" % r["body"][:260])


def fama_macbeth(d, flag_col, controls):
    coefs = []
    for _, g in d.groupby("target_month"):
        if len(g) < 50 or g[flag_col].sum() < 3:
            continue
        X = g[[flag_col] + controls].copy()
        for c in controls:
            v = X[c].fillna(X[c].median())
            rk = v.rank(method="dense") - 1
            X[c] = (rk / rk.max()) * 2 - 1 if rk.max() > 0 else 0.0
        M = np.column_stack([np.ones(len(g)), X.values.astype(float)])
        coefs.append(np.linalg.lstsq(M, g[C.TARGET].values, rcond=None)[0][1])
    coefs = np.array(coefs)
    if len(coefs) < 10:
        return np.nan, np.nan, len(coefs)
    return (100 * coefs.mean(),
            coefs.mean() / (coefs.std(ddof=1) / np.sqrt(len(coefs))), len(coefs))


def retest(monthly):
    """Does separating the two halves recover a signal the aggregate hid?"""
    CTRL = ["market_equity", "be_me", "ret_12_1", "ret_1_0", "rvol_21d",
            "ami_126d", "gp_at", "at_gr1", "beta_dimson_21d"]
    panel = pd.read_parquet(C.MODEL_TABLE,
                            columns=["permno", "target_month", C.TARGET] + CTRL)
    panel = panel[(panel["target_month"] <= TRAIN_END) & panel[C.TARGET].notna()]
    d = panel.merge(monthly, on=["permno", "target_month"], how="left")
    d["any_officer"] = d["n_officer_filings"].notna().astype(float)
    d["abrupt"] = d["abrupt"].fillna(0).astype(float)
    d["routine_only"] = ((d["any_officer"] == 1) & (d["abrupt"] == 0)).astype(float)

    print("\n--- training window only (%s and earlier), monthly regressions ---"
          % TRAIN_END)
    print("  %-34s %9s %8s %7s" % ("", "coef/mo", "t", "months"))
    for label, col in [("any officer-change filing", "any_officer"),
                       ("  of which ABRUPT", "abrupt"),
                       ("  of which routine", "routine_only")]:
        n_flag = int(d[col].sum())
        coef, t, months = fama_macbeth(d, col, CTRL)
        print("  %-34s %+8.3f%% %+8.1f %7d   (n=%s)"
              % (label, coef, t, months, format(n_flag, ",")))
    print("\n  The aggregate test that motivated this returned -0.216%% at t=-2.0.")
    print("  If the split is real, ABRUPT should be materially more negative than")
    print("  the aggregate and routine should be near zero.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", action="store_true",
                    help="print filings on each side so the rules can be checked by eye")
    args = ap.parse_args()
    f, monthly = classify()
    if args.sample:
        show_sample(f)
    retest(monthly)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

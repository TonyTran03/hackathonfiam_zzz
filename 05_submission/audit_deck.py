"""Audit the deck for numbers that are typed in rather than read from a CSV.

    python 05_submission/audit_deck.py

The leg attribution sat on two slides as four literals after the book that
produced them had been replaced. Nothing failed, because a literal cannot fail
-- it just quietly stops being true. Separately, a patch that claimed to add
two bullets to page 3 matched nothing, reported success, and was believed.
Both are the same class of error and this catches both.

  SOURCE   every RESULT-shaped number inside a string in build_deck.js:
           signed percentages, t-statistics, basis points, dollar figures.
           Layout coordinates and colours never take those shapes, so the
           report stays readable. Each hit must appear in JUSTIFIED with a
           reason, or it is flagged.

  RENDER   every value the CSVs hold, looked for in the text extracted back
           out of the built PDF. This is the direction that catches a patch
           which silently matched nothing: the source can claim anything, the
           PDF either contains the number or it does not.

Exit code is non-zero if the source pass finds an unexplained literal.
"""
import re
import sys
from pathlib import Path

import pandas as pd

SUB = Path(__file__).resolve().parent
JS = SUB / "build_deck.js"
PDF = SUB / "FIAM_deck.pdf"

RESULT = re.compile(
    r"(?<![\w.])[-+]\d+(?:\.\d+)?\s*%"            # +8.81%   -29.35%
    r"|(?<![\w.])t\s*[-+]\d+(?:\.\d+)?"           # t +2.4
    r"|(?<![\w.])\d+(?:\.\d+)?\s*bps"             # 97 bps
    r"|\$\d[\d,]*(?:\.\d+)?\s*(?:m|bn)?"          # $45m   $1.15bn
    r"|(?<![\w.%$])[-+]\d\.\d{2,3}(?![\d%])"      # +0.88  -0.159
)
def js_strings(src):
    """Yield (line, text) for every double-quoted string literal in src.

    Scanned character by character rather than by stripping comments first and
    pairing quotes afterwards. Stripping is the obvious approach and it is
    wrong: the comments in build_deck.js quote example values, so removing
    them leaves an odd number of quotes and every pairing after that point
    slides by one, matching the code BETWEEN strings instead of the strings.
    The symptom is an audit that cheerfully reports zero findings -- which is
    the same failure this file exists to catch, so it is worth the extra code.
    """
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
        elif c in "\"'":
            quote, start, i = c, line, i + 1
            buf = []
            while i < n:
                if src[i] == "\\":
                    buf.append(src[i:i + 2])
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                if src[i] == "\n":
                    line += 1
                buf.append(src[i])
                i += 1
            if quote == '"':
                yield start, "".join(buf)
        else:
            i += 1

# Literals that are deliberate: figures quoted as history from a prior
# configuration, or measured by a stage that does not write a deck CSV. Each
# one is a promise that the number does not move when the book is rebuilt.
JUSTIFIED = {
    "-0.537": "pre-neutralisation beta, quoted as history",
    "-30%": "pre-neutralisation drawdown, quoted as history",
    "$50m": "unscreened short book, screen diagnostic",
    "$2.63": "unscreened short book, screen diagnostic",
    "$282m": "missingness diagnostic, stage 2",
    "$1,687m": "missingness diagnostic, stage 2",
    "+0.27%": "undemeaned-target failure, stage 3",
    "+2.52%": "undemeaned-target failure, stage 3",
    "+25.03%": "2019-20 validation build",
    "+0.85%": "2019-20 validation build",
    "+5.42%": "2019-20 validation build",
    "t +0.1": "2019-20 validation build",
    "t +1.1": "2019-20 validation build",
    "+8.81%": "2023-26 long leg; also read from leg_attribution.csv",
    "+0.1087": "filing-feature with/without comparison, stage 2",
    "+0.1082": "filing-feature with/without comparison, stage 2",
    "+0.046%": "item 5.02 aggregate, 8-K appendix",
    "-0.640%": "item 5.02 abrupt, 8-K appendix",
    "+0.121%": "item 5.02 routine, 8-K appendix",
    "t +0.5": "item 5.02 aggregate",
    "t -1.9": "item 5.02 abrupt",
    "-0.24%": "8-K missingness, Fama-MacBeth",
    "t -2.22": "8-K missingness, Fama-MacBeth",
    "t +23.8": "8-K missingness, survival",
    "t +2.0": "value loading, factor regression",
    "-0.63": "last rolling window, neutrality_check.csv",
    "-0.21": "last rolling window, neutrality_check.csv",
    "-0.66": "validation IR at 20bps, exp_refresh.csv",
    "-1.05": "validation IR at 20bps, exp_refresh.csv",
    "-0.034": "full-period beta move, neutrality_check.csv",
    "+0.2": "stated range of the sector effects",
    "+0.4": "stated range of the sector effects",
    "-48%": "January 2021 unscreened, screen diagnostic",
    "+0.3956%": "OOS R2 table, stage 3",
    "+0.0278%": "OOS R2 table, stage 3",
    "-0.0068%": "OOS R2 table, stage 3",
    "+0.1354": "OOS R2 table, stage 3",
    "+0.1193": "OOS R2 table, stage 3",
    "+0.0806": "OOS R2 table, stage 3",
    "+1.71%": "filing columns' share of gain, stage 3",
    "+8.81": "2023-26 long leg",
    "-1.57%": "2021-22 universe, validation build",
    "+12.05%": "2023-26 universe, validation build",
    "+0.85": "2019-20 validation build",
    # Cost and screen assumptions we chose, and limits the rules set. Constants,
    # not results: they do not move when the book is rebuilt.
    "20bps": "the cost assumption the deck reports net at",
    "20 bps": "the cost assumption the deck reports net at",
    "25bps": "the borrow-cost illustration",
    "$5,": "the price screen",
    "$2.63 m": "unscreened short book median price (regex catches the next word)",
    "+0.08": "Lasso/Elastic Net monthly IC, stage 3",
    "-50%": "the rules' net exposure limit",
}


def source_pass():
    src = JS.read_text(encoding="utf8")
    hits, seen = [], set()
    for line, text in js_strings(src):
        for n in RESULT.finditer(text):
            v = n.group(0).strip()
            if (line, v) in seen:
                continue
            seen.add((line, v))
            hits.append((line, v, text[:66]))

    print("=" * 78)
    print("SOURCE PASS -- result-shaped numbers typed into build_deck.js")
    print("=" * 78)
    unexplained = [h for h in hits if h[1] not in JUSTIFIED]
    print("  %d result-shaped literal(s); %d accounted for, %d NOT"
          % (len(hits), len(hits) - len(unexplained), len(unexplained)))
    if unexplained:
        print("\n  Each of these can stop being true without anything failing:")
        for line, v, text in unexplained:
            print("    line %-5d %-12s %s" % (line, v, text))
    return unexplained


def render_pass():
    try:
        from pypdf import PdfReader
    except ImportError:
        print("\n  pypdf not available; render pass skipped")
        return []
    text = re.sub(r"\s+", " ",
                  " ".join((p.extract_text() or "") for p in PdfReader(str(PDF)).pages))

    want = []
    pack = pd.read_csv(SUB / "deck_pack.csv")
    for _, r in pack[pack["section"].isin(["risk", "exposure", "returns",
                                           "short_book"])].iterrows():
        want.append(("deck_pack", str(r["metric"]), str(r["value"]).strip()))
    rob = pd.read_csv(SUB / "robustness.csv")
    for _, r in rob[rob["section"].isin(["costs", "attribution", "rolling",
                                         "stress"])].iterrows():
        want.append(("robustness", str(r["metric"]), str(r["value"]).strip()))
    leg = pd.read_csv(SUB / "leg_attribution.csv")
    for _, r in leg.iterrows():
        want.append(("leg_attribution", "%s %s" % (r["period"], r["metric"]),
                     str(r["value"]).strip()))

    missing = []
    for src, metric, value in want:
        if not value or value in ("nan", "NOT COMPUTED", "NOT AVAILABLE"):
            continue
        if value not in text:
            missing.append((src, metric, value))

    print("\n" + "=" * 78)
    print("RENDER PASS -- do the CSV values actually reach the built PDF?")
    print("=" * 78)
    print("  %d of %d checked values appear in the PDF"
          % (len(want) - len(missing), len(want)))
    if missing:
        print("\n  In a CSV but on no slide. Deliberate for anything the deck")
        print("  never promised to show; a silently-failed patch otherwise:")
        for src, metric, value in missing:
            print("    %-16s %-46s %s" % (src, metric[:46], value))
    return missing


def main():
    if not PDF.exists():
        print("build the deck first: node 05_submission/build_deck.js")
        return 1
    unexplained = source_pass()
    render_pass()
    print("\nThe render pass is the one that matters: a patch matching nothing")
    print("still reports success, but a number missing from the PDF does not.")
    return 1 if unexplained else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stage 5l -- the 8-K corpus's coverage, measured across the whole panel.

    python 04_backtest_scoring/18_filing_coverage.py

The appendix first made this point from the 59 holdings that lose their forward
return, which tied the claim to whichever book happened to be current. The same
pattern is in the panel itself and does not move when the book is rebuilt, so
that is what the slide should say.

A company still listed at the end of the panel is almost certainly in the
corpus. A company that left before 2025 almost certainly is not -- not because
it stopped filing, but because the corpus's company list was built from
identifiers that still resolve today, and an acquired company's do not. Seven
well-known cases are checked by name as the concrete version of the same thing.

Writes filing_coverage.csv.
"""
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

OUT = C.ROOT / "05_submission" / "filing_coverage.csv"

# All acquired between 2020 and 2021, all filing 8-Ks throughout 2015-2020.
NAMED = ["dunkin", "fitbit", "varian", "alexion", "maxim integrated",
         "luminex", "raven indus"]

rows = []


def put(metric, value, note=""):
    rows.append({"metric": metric, "value": value, "note": note})
    print("  %-44s %-16s %s" % (metric, value, note))


def main():
    if not C.FILINGS_PARQUET.exists():
        print("8-K corpus not found; skipping")
        return 0

    f = pq.ParquetFile(C.FILINGS_PARQUET)
    covered, names = set(), []
    for batch in f.iter_batches(batch_size=100000,
                                columns=["permno", "company_name"]):
        b = batch.to_pandas()
        covered |= set(pd.to_numeric(b["permno"], errors="coerce")
                       .dropna().astype(int))
        names.append(b["company_name"].fillna("").str.lower())
    names = pd.concat(names, ignore_index=True)

    pan = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "target_month"])
    last = pan.groupby("permno")["target_month"].max()
    end = pan["target_month"].max()

    print("=" * 76)
    print("8-K COVERAGE, ACROSS THE WHOLE PANEL")
    print("=" * 76)
    put("panel", "%s stocks" % format(len(last), ","), "ends %s" % end)
    put("8-K corpus", "%s companies" % format(len(covered), ","),
        "%s filings" % format(f.metadata.num_rows, ","))

    print("")
    for label, sel in [("left the panel before 2025", last < "2025-01"),
                       ("still listed at the panel's end", last == end)]:
        idx = last[sel].index
        hit = sum(1 for p in idx if int(p) in covered)
        put(label, "%.1f%% covered" % (100 * hit / len(idx)),
            "%s of %s stocks" % (format(hit, ","), format(len(idx), ",")))

    print("\nSEVEN COMPANIES THAT FILED THROUGHOUT 2015-2020 AND WERE ACQUIRED")
    missing = [n for n in NAMED
               if not names.str.contains(n, regex=False).any()]
    put("named companies checked", "%d" % len(NAMED),
        "Dunkin', Fitbit, Varian, Alexion, Maxim, Luminex, Raven")
    put("of those, filings in the corpus", "%d" % (len(NAMED) - len(missing)),
        "in a corpus spanning 2015-2026")

    print("")
    print("  Absence is not 'they stopped filing'. The corpus's company list was")
    print("  built from identifiers that still resolve today, so a company acquired")
    print("  before roughly 2025 is simply not in it -- which makes 'no 8-K record'")
    print("  a variable that knows the future.")

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("\nwrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

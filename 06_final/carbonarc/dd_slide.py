"""One slide for the Carbon Arc due-diligence pilot (dd_cards.md), as a 1600 x 1000 PNG.

Left: the 27 exited firms searched in Carbon Arc's CA0032 by name, the two event series
retrieved, and the two pre-exit 8-Ks verified on SEC EDGAR. Right: the six-rule card for
three distinct recommended assets (CA0032, CA0035, CA0092). Values are typed in from
dd_cards.md and dd_verified_filings.csv; nothing is queried here.

    python 06_final/carbonarc/dd_slide.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).with_name("dd_slide.png")

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
HIT, UNK = "#2a78d6", "#b9b8b2"

EXITS = [  # (ticker, exit month, event series retrieved and verified on EDGAR)
    ("SAPE", "2015-02", 0), ("CFN", "2015-03", 0), ("ZSPH", "2015-12", 0), ("BXLT", "2016-05", 0),
    ("NTK", "2016-08", 1), ("CVT", "2016-11", 0), ("RAI", "2017-07", 0), ("WBMD", "2017-08", 0),
    ("CBF", "2017-11", 0), ("STRP", "2018-02", 0), ("CPLA", "2018-07", 0), ("LPNT", "2018-11", 0),
    ("VVC", "2019-01", 0), ("DNB", "2019-02", 0), ("NTRI", "2019-03", 0), ("ZAYO", "2020-03", 0),
    ("ETFC", "2020-10", 0), ("NBL", "2020-10", 0), ("BEAT", "2021-02", 0), ("BPFH", "2021-06", 0),
    ("KDMN", "2021-11", 0), ("MGLN", "2022-01", 0), ("FLOW", "2022-04", 0), ("CLR", "2022-11", 0),
    ("CINC", "2023-02", 0), ("TWNK", "2023-11", 1), ("VMW", "2023-11", 0),
]
FUNNEL = [("27", "companies\nsearched by name"), ("2", "8-K event\nseries retrieved"),
          ("2", "pre-exit 8-Ks\nverified on EDGAR"), ("25", "companies\nunresolved")]

RULES = ["Lag dated\nper record", "No silent\nrevisions", "CIK or dated\nticker", "Has-data\nflag",
         "Coverage\nby year", "History\nby 2019"]
U, N = "UNVERIFIED", "NOT USED"
ASSETS = [  # (name, verdict per rule); no rule reached PASS or FAIL
    ("CA0032  SEC EDGAR filings", [U, U, U, N, U, U]),
    ("CA0035  Benzinga news and events", [U, U, U, N, U, U]),
    ("CA0092  New Constructs ratings (not in MCP catalogue)", [U, U, U, N, U, U]),
]
FILL = {U: UNK, N: SURFACE}
EDGE = {U: UNK, N: MUTED}
TEXT = {U: INK, N: INK2}
LABEL = {U: "UNVERIFIED", N: "– NOT USED"}


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor=SURFACE)

    fig.text(0.04, 0.93, "Carbon Arc pilot: 8-K search retrieval for firms that left the panel",
             fontsize=26, weight="bold")
    fig.text(0.04, 0.885, "Data due diligence through the Carbon Arc MCP, checked against SEC EDGAR, 2026-10-28. "
             "27 large exits, 2015-2023.", fontsize=14, color=INK2)

    # Left: funnel of counts
    for k, (num, lab) in enumerate(FUNNEL):
        x = 0.04 + k * 0.105
        fig.text(x, 0.76, num, fontsize=44, weight="bold", color=HIT if k in (1, 2) else INK)
        fig.text(x, 0.745, lab, fontsize=11.5, color=INK2, va="top", linespacing=1.3)

    ax = fig.add_axes([0.04, 0.17, 0.40, 0.49], facecolor=SURFACE)
    n = len(EXITS)
    for i, (tic, month, hit) in enumerate(EXITS):
        col, row = i % 3, i // 3
        x, y = col * 1.0, -row * 1.0
        ax.add_patch(FancyBboxPatch((x + 0.04, y - 0.40), 0.92, 0.80, boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor=HIT if hit else SURFACE, edgecolor=HIT if hit else GRID, lw=2))
        ax.text(x + 0.12, y + 0.06, tic, fontsize=13, weight="bold", va="center", color="white" if hit else INK)
        ax.text(x + 0.12, y - 0.20, month, fontsize=10, va="center", color="white" if hit else MUTED)
        ax.text(x + 0.88, y - 0.07, "✓ verified" if hit else "not found", fontsize=11, ha="right",
                va="center", color="white" if hit else MUTED)
    ax.set_xlim(0, 3)
    ax.set_ylim(-(n // 3) + 0.5, 0.5)
    ax.axis("off")
    fig.text(0.04, 0.135, "Verified: Nortek, Inc. (CIK 1216596) 8-K of 2016-07-06 and Hostess Brands, Inc.\n"
             "(CIK 1644406) 8-K of 2023-09-12, both item 1.01 merger agreements.",
             fontsize=11, color=INK2, va="top", linespacing=1.4)

    # Right: six-rule card
    ax2 = fig.add_axes([0.50, 0.30, 0.47, 0.50], facecolor=SURFACE)
    for j, rule in enumerate(RULES):
        ax2.text(j + 0.5, 3.15, rule, ha="center", va="bottom", fontsize=12, color=INK2)
    for i, (name, verdicts) in enumerate(ASSETS):
        y = 2 - i
        ax2.text(0, y + 0.92, name, fontsize=13, weight="bold", va="bottom")
        for j, v in enumerate(verdicts):
            ax2.add_patch(FancyBboxPatch((j + 0.05, y + 0.08), 0.90, 0.70, boxstyle="round,pad=0,rounding_size=0.06",
                                         facecolor=FILL[v], edgecolor=EDGE[v], lw=2))
            ax2.text(j + 0.5, y + 0.43, LABEL[v], ha="center", va="center", fontsize=10, weight="bold",
                     color=TEXT[v])
    ax2.set_xlim(0, 6)
    ax2.set_ylim(0, 3.6)
    ax2.axis("off")

    notes = [
        "No rule reached PASS (checked across the asset) or FAIL (no route at all).",
        "A missing CIK closes the CIK route only. Date-bounded tickers are untested.",
        "NOT USED: no Carbon Arc data feeds any signal, so no has-data flag is needed yet.",
        "Lags are documented. Observed: SEC Filing Events last refreshed 2026-07-15.",
        "Access limits: name search only, no CIK lookup, rate limits, CA0092 not visible.",
        "This pilot does not establish that survivorship bias is resolved.",
    ]
    fig.text(0.50, 0.265, "\n".join(notes), fontsize=12, color=INK2, va="top", linespacing=1.5)
    fig.text(0.04, 0.04, "Source: Carbon Arc MCP (about 35 query units) and SEC EDGAR filing indexes. "
             "Our own summary; details in 06_final/carbonarc/dd_cards.md.", fontsize=11, color=MUTED)

    fig.savefig(OUT, dpi=100, facecolor=SURFACE)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

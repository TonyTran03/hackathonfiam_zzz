"""One slide for the Carbon Arc due-diligence pilot (dd_cards.md), as a 1600 x 1000 PNG.

Left: the 27 large exits by exit month, marked by whether a name search of Carbon Arc's
CA0032 returned an 8-K event series (search retrieval only). Right: the six-rule card for
CA0032 (two tables) and CA0035. Values are typed in from dd_cards.md; nothing is queried
here.

    python 06_final/carbonarc/dd_slide.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).with_name("dd_slide.png")

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
HIT, CRIT, UNK = "#2a78d6", "#d03b3b", "#b9b8b2"

EXITS = [  # (ticker, exit month, 8-K event series returned by name search)
    ("SAPE", "2015-02", 0), ("CFN", "2015-03", 0), ("ZSPH", "2015-12", 0), ("BXLT", "2016-05", 0),
    ("NTK", "2016-08", 1), ("CVT", "2016-11", 0), ("RAI", "2017-07", 0), ("WBMD", "2017-08", 0),
    ("CBF", "2017-11", 0), ("STRP", "2018-02", 0), ("CPLA", "2018-07", 0), ("LPNT", "2018-11", 0),
    ("VVC", "2019-01", 0), ("DNB", "2019-02", 0), ("NTRI", "2019-03", 0), ("ZAYO", "2020-03", 0),
    ("ETFC", "2020-10", 0), ("NBL", "2020-10", 0), ("BEAT", "2021-02", 0), ("BPFH", "2021-06", 0),
    ("KDMN", "2021-11", 0), ("MGLN", "2022-01", 0), ("FLOW", "2022-04", 0), ("CLR", "2022-11", 0),
    ("CINC", "2023-02", 0), ("TWNK", "2023-11", 1), ("VMW", "2023-11", 0),
]

RULES = ["Lag dated\nper record", "No silent\nrevisions", "CIK or dated\nticker", "Has-data\nflag",
         "Coverage\nby year", "History\nby 2019"]
U, F, N = "UNVERIFIED", "FAIL", "NOT USED"
ASSETS = [  # (name, verdict per rule); no rule reached PASS, which needs a check on records
    ("CA0032  SEC EDGAR filings block and SEC Filing Events", [U, U, U, N, U, U]),
    ("CA0035  Benzinga news and events", [F, U, F, N, U, U]),
    ("CA0032 table: Company Reported Actuals (not a separate asset)", [F, U, F, N, U, U]),
]
FILL = {F: CRIT, U: UNK, N: SURFACE}
EDGE = {F: CRIT, U: UNK, N: MUTED}
TEXT = {F: "white", U: INK, N: INK2}
LABEL = {F: "✕ FAIL", U: "UNVERIFIED", N: "– NOT USED"}


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor=SURFACE)

    fig.text(0.04, 0.93, "Carbon Arc pilot: 8-K search retrieval for firms that left the panel",
             fontsize=26, weight="bold")
    fig.text(0.04, 0.885, "Data due diligence through the Carbon Arc MCP, 2026-10-28. "
             "27 large exits, 2015-2023, three per year; six-rule card from catalogue metadata.",
             fontsize=14, color=INK2)

    # Left: hero number and the 27 exits
    fig.text(0.04, 0.76, "2 of 27", fontsize=56, weight="bold")
    fig.text(0.04, 0.715, "exits returned an 8-K event series in a CA0032 name search", fontsize=15, color=INK2)
    fig.text(0.04, 0.685, "Search retrieval only: no filings opened, no CIK to confirm identity",
             fontsize=12, color=MUTED)

    ax = fig.add_axes([0.04, 0.13, 0.40, 0.52], facecolor=SURFACE)
    n = len(EXITS)
    for i, (tic, month, hit) in enumerate(EXITS):
        col, row = i % 3, i // 3
        x, y = col * 1.0, -row * 1.0
        ax.add_patch(FancyBboxPatch((x + 0.04, y - 0.40), 0.92, 0.80, boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor=HIT if hit else SURFACE, edgecolor=HIT if hit else GRID, lw=2))
        ink = "white" if hit else INK
        ax.text(x + 0.12, y + 0.06, tic, fontsize=13, weight="bold", va="center", color=ink)
        ax.text(x + 0.12, y - 0.20, month, fontsize=10, va="center", color="white" if hit else MUTED)
        ax.text(x + 0.88, y - 0.07, "✓ found" if hit else "not found", fontsize=11, ha="right",
                va="center", color="white" if hit else MUTED)
    ax.set_xlim(0, 3)
    ax.set_ylim(-(n // 3) + 0.5, 0.5)
    ax.axis("off")

    # Right: six-rule card
    ax2 = fig.add_axes([0.50, 0.24, 0.47, 0.56], facecolor=SURFACE)
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
        "No rule reached PASS, which needs a check on records. UNVERIFIED = catalogue only.",
        "NOT USED: no Carbon Arc data feeds any signal, so a has-data flag is not yet needed.",
        "Lag is the documented figure. Observed: SEC Filing Events queries report a last",
        "refresh of 2026-07-15. This pilot does not establish that survivorship bias is resolved.",
    ]
    fig.text(0.50, 0.19, "\n".join(notes), fontsize=12, color=INK2, va="top", linespacing=1.5)
    fig.text(0.04, 0.04, "Source: Carbon Arc MCP catalogue and SEC Filing Events, about 35 query units. "
             "Our own summary; details in 06_final/carbonarc/dd_cards.md.", fontsize=11, color=MUTED)

    fig.savefig(OUT, dpi=100, facecolor=SURFACE)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

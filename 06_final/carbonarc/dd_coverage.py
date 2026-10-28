"""Coverage by month for a Carbon Arc spending panel (permno, month, value), for the six-rule card.

Reads the shared panel Faig pulls once (foot traffic first, card spend later) and measures,
from the data itself, the parts of the card that row counts can answer:

- Coverage (rule 5): names with a value each month, against the 2024 average, and against
  the Consumer Discretionary names alive in our panel that month.
- Real start date (rule 6): the first month at or above half the 2024 coverage.
- Mapping (rule 3): rows whose (permno, month) is not a live stock-month in our panel,
  e.g. after a delisting, which points to a ticker->permno link without date bounds.
- Has-data (rule 4): zero values reported separately from missing ones.

Nothing here reads returns. Outputs go next to the panel unless --output is given.

    python 06_final/carbonarc/dd_coverage.py --panel <foot_traffic_panel>.csv --label "Foot traffic"
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
HIT, UNK = "#2a78d6", "#b9b8b2"


def load_panel(path):
    p = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)
    p.columns = [c.lower() for c in p.columns]
    missing = {"permno", "month", "value"} - set(p)
    if missing:raise ValueError(f"{path} lacks columns {sorted(missing)}")
    p["month"] = pd.PeriodIndex(pd.to_datetime(p["month"].astype(str)), freq="M")
    dups = int(p.duplicated(["permno", "month"]).sum())
    if dups:raise ValueError(f"{dups} duplicate (permno, month) rows in {path}")
    return p


def coverage(p, chars):
    c = pd.read_parquet(chars, columns=["permno", "eom", "gics"])
    c["month"] = pd.PeriodIndex(pd.to_datetime(c.eom), freq="M")
    live = set(zip(c.permno, c.month))
    cd = c[c.gics.astype("string").str[:2] == "25"].groupby("month").permno.nunique()
    has = p[p.value.notna()]
    m = pd.DataFrame({"names_with_value": has.groupby("month").permno.nunique(),
                      "names_zero_value": p[p.value == 0].groupby("month").permno.nunique(),
                      "rows_missing_value": p[p.value.isna()].groupby("month").size()})
    m = m.reindex(pd.period_range(p.month.min(), p.month.max(), freq="M")).fillna(0).astype(int)
    m["consumer_discretionary_names_in_panel"] = cd.reindex(m.index).fillna(0).astype(int)
    covered = has.assign(cd=has.permno.isin(c[c.gics.astype("string").str[:2] == "25"].permno))
    m["names_with_value_consumer_discretionary"] = covered[covered.cd].groupby("month").permno.nunique().reindex(m.index).fillna(0).astype(int)
    p_live = pd.Series([(a, b) in live for a, b in zip(p.permno, p.month)], index=p.index)
    m["rows_not_live_in_our_panel"] = p[~p_live].groupby("month").size().reindex(m.index).fillna(0).astype(int)
    base = m.loc[m.index.year == 2024, "names_with_value"].mean()
    m["pct_of_2024_level"] = 100 * m.names_with_value / base if base else float("nan")
    m.index.name = "month"
    return m, base, p[~p_live]


def chart(m, base, label, out):
    fig, ax = plt.subplots(figsize=(16, 7), dpi=100, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    x = m.index.to_timestamp()
    ax.plot(x, m.names_with_value, color=HIT, lw=2.4, label="Names with a value")
    ax.plot(x, m.names_with_value_consumer_discretionary, color=INK2, lw=1.6, label="of which Consumer Discretionary")
    ax.plot(x, m.consumer_discretionary_names_in_panel, color=UNK, lw=1.4, ls="--", label="Consumer Discretionary names in our panel")
    if base:ax.axhline(base / 2, color=MUTED, lw=1, ls=":", label="Half the 2024 level (rule 6 threshold)")
    for d, t in [("2019-01-01", "Design window"), ("2021-01-01", "Test window")]:
        ax.axvline(pd.Timestamp(d), color=GRID, lw=1.5)
        ax.text(pd.Timestamp(d), ax.get_ylim()[1] * .97, " " + t, color=MUTED, fontsize=11, va="top")
    ax.set_title(f"{label}: names covered per month", loc="left", fontsize=20, color=INK, pad=14)
    ax.set_ylabel("Stocks (permno)", color=INK2, fontsize=12)
    for s in ["top", "right"]:ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=11)
    ax.grid(axis="y", color=GRID, lw=.8)
    ax.legend(frameon=False, fontsize=11, labelcolor=INK2, loc="upper left", bbox_to_anchor=(0, -.08), ncol=4)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--panel", type=Path, required=True)
    a.add_argument("--label", default="Foot traffic")
    a.add_argument("--chars", type=Path, default=ROOT / "01_data/raw/chars_final_with_names.parquet")
    a.add_argument("--output", type=Path)
    args = a.parse_args()
    out = args.output or args.panel.parent
    out.mkdir(parents=True, exist_ok=True)
    stem = "dd_coverage_" + args.label.lower().replace(" ", "_")
    p = load_panel(args.panel)
    m, base, dead = coverage(p, args.chars)
    m.to_csv(out / f"{stem}.csv")
    dead.to_csv(out / f"{stem}_not_live_rows.csv", index=False)
    chart(m, base, args.label, out / f"{stem}.png")
    start = m.index[m.names_with_value >= base / 2][0] if base else None
    print(f"{args.label}: {p.permno.nunique()} permnos, {m.index[0]} to {m.index[-1]}, 2024 average {base:.0f} names")
    print(f"first month at half the 2024 level: {start}; 2021-01 at {m.pct_of_2024_level.get(pd.Period('2021-01', 'M'), float('nan')):.0f}% of 2024")
    print(f"rows not live in our panel: {len(dead)} ({dead.permno.nunique()} permnos); zero values: {int((p.value == 0).sum())}; missing values: {int(p.value.isna().sum())}")
    print(f"-> {out / stem}.csv/.png")


if __name__ == "__main__":
    main()

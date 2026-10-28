"""Coverage by month for a Carbon Arc spending panel, for the six-rule card.

Reads the shared panel Faig pulls once (ticker or permno, month, one value column) and
measures, from the data itself, the parts of the card that row counts can answer:

- Mapping (rule 3): a ticker panel is joined to permno on (ticker, month), using the ticker
  each permno carried that month in our panel (labels filled within a permno across unlabelled
  months). A second pass recovers renames: rows the dated labels reject are matched to the
  permno that carries the ticker today if it was live that month (matched_earlier_ticker).
  Rows still without a live permno are labelled before_listing, after_delisting or gap, so
  values that belong to a brand rather than a listed stock are visible.
- Coverage (rule 5): names with a value each month, against the 2024 average, and how many
  of them are live stocks in our panel that month.
- Real start date (rule 6): the first month at or above half the 2024 coverage, both for all
  names and for names live in our panel.
- Has-data (rule 4): zero values reported separately from missing ones.

Nothing here reads returns. Outputs go next to the panel unless --output is given; the panel
is licensed Carbon Arc data, so keep both out of the repo.

    python 06_final/carbonarc/dd_coverage.py --panel ~/Downloads/card_spend_monthly.csv --label "Card spend"
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
    key = "permno" if "permno" in p else "ticker" if "ticker" in p else None
    values = [c for c in p if c not in ("permno", "ticker", "month")]
    if key is None or "month" not in p or len(values) != 1:
        raise ValueError(f"{path} needs permno or ticker, month and exactly one value column; has {list(p)}")
    p = p.rename(columns={values[0]: "value", key: "id"})
    p["month"] = pd.PeriodIndex(pd.to_datetime(p["month"].astype(str)), freq="M")
    dups = int(p.duplicated(["id", "month"]).sum())
    if dups:raise ValueError(f"{dups} duplicate ({key}, month) rows in {path}")
    return p, key


def load_chars(chars):
    c = pd.read_parquet(chars, columns=["permno", "eom", "ticker", "gics"])
    c["month"] = pd.PeriodIndex(pd.to_datetime(c.eom), freq="M")
    c = c.sort_values(["permno", "month"])
    c["ticker"] = c.groupby("permno").ticker.transform(lambda s: s.ffill().bfill())
    c["cd"] = c.gics.astype("string").str[:2] == "25"
    return c


def map_ids(p, key, c):
    """Attach a live permno to every row, with map_status matched/ambiguous/before_listing/after_delisting/gap."""
    if key == "permno":
        live = c[["permno", "month"]].assign(_live=True)
        p = p.assign(permno=p.id).merge(live, on=["permno", "month"], how="left")
        p["map_status"] = p._live.fillna(False).map({True: "matched", False: "not_live"})
        return p.drop(columns="_live")
    lab = c.dropna(subset=["ticker"]).groupby(["ticker", "month"]).permno.agg(["first", "nunique"]).reset_index()
    p = p.merge(lab.rename(columns={"ticker": "id", "first": "permno", "nunique": "_n"}), on=["id", "month"], how="left")
    span = c.dropna(subset=["ticker"]).groupby("ticker").month.agg(["min", "max"])
    first, last = p.id.map(span["min"]), p.id.map(span["max"])
    p["map_status"] = "gap"
    p.loc[p.month < first, "map_status"] = "before_listing"
    p.loc[p.month > last, "map_status"] = "after_delisting"
    p.loc[p._n == 1, "map_status"] = "matched"
    p.loc[p._n > 1, "map_status"] = "ambiguous"
    p.loc[p.map_status != "matched", "permno"] = pd.NA
    # Second pass: the vendor keys history by today's ticker. A row the dated labels reject is
    # the same listed company if the permno carrying the ticker at its last label was live that
    # month under an earlier ticker (e.g. GPS -> GAP). What is still unmatched is pre-IPO or post-exit.
    labelled = c.dropna(subset=["ticker"])
    now = labelled.loc[labelled.groupby("ticker").month.idxmax(), ["ticker", "permno"]].set_index("ticker").permno
    live = set(zip(c.permno, c.month))
    cand = p.id.map(now)
    renamed = (p.map_status.isin(["before_listing", "gap"]) & cand.notna()
               & pd.Series([(q, mo) in live for q, mo in zip(cand, p.month)], index=p.index))
    p.loc[renamed, "permno"] = cand[renamed]
    p.loc[renamed, "map_status"] = "matched_earlier_ticker"
    return p.drop(columns="_n")


def coverage(p, c):
    has = p[p.value.notna()]
    live = has[has.map_status.str.startswith("matched")]
    months = pd.period_range(p.month.min(), p.month.max(), freq="M")
    cd_ids = set(c.loc[c.cd, "permno"])
    m = pd.DataFrame({"names_with_value": has.groupby("month").id.nunique(),
                      "names_with_value_live_in_panel": live.groupby("month").permno.nunique(),
                      "names_with_value_live_consumer_discretionary": live[live.permno.isin(cd_ids)].groupby("month").permno.nunique(),
                      "names_zero_value": p[p.value == 0].groupby("month").id.nunique(),
                      "rows_missing_value": p[p.value.isna()].groupby("month").size(),
                      "rows_not_live_in_panel": p[~p.map_status.str.startswith("matched")].groupby("month").size()}).reindex(months).fillna(0).astype(int)
    m["consumer_discretionary_names_in_panel"] = c[c.cd].groupby("month").permno.nunique().reindex(months).fillna(0).astype(int)
    base = {}
    for col in ["names_with_value", "names_with_value_live_in_panel"]:
        b = m.loc[m.index.year == 2024, col].mean()
        base[col] = float(b) if pd.notna(b) and b > 0 else None   # no 2024 rows (or none with a value): no baseline
        m["pct_of_2024_" + col.replace("names_with_value", "all").replace("all_live_in_panel", "live")] = 100 * m[col] / base[col] if base[col] else float("nan")
    m.index.name = "month"
    return m, base


def per_name(p):
    g = p.groupby("id")
    s = pd.DataFrame({"months_with_value": g.value.count(), "first_month": g.month.min().astype(str),
                      "last_month": g.month.max().astype(str), "zero_values": g.value.apply(lambda v: int((v == 0).sum())),
                      "missing_values": g.value.apply(lambda v: int(v.isna().sum())),
                      "permnos": g.permno.apply(lambda v: ";".join(str(int(x)) for x in sorted(v.dropna().unique())))})
    st = p.groupby(["id", "map_status"]).size().unstack(fill_value=0)
    s = s.join(st.add_prefix("months_"))
    s.index.name = "id"
    return s.reset_index()


def chart(m, base, label, out):
    fig, ax = plt.subplots(figsize=(16, 7), dpi=100, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    x = m.index.to_timestamp()
    ax.plot(x, m.names_with_value, color=HIT, lw=2.4, label="Names with a value")
    ax.plot(x, m.names_with_value_live_in_panel, color=INK, lw=1.8, label="of which a live stock in our panel")
    ax.plot(x, m.names_with_value_live_consumer_discretionary, color=INK2, lw=1.2, ls="--", label="of which Consumer Discretionary")
    b = base["names_with_value"]
    if b:ax.axhline(b / 2, color=MUTED, lw=1, ls=":", label="Half the 2024 level (rule 6 threshold)")
    ax.set_ylim(0, max(m.names_with_value.max(), 1) * 1.12)
    for d, t in [("2019-01-01", "Design window"), ("2021-01-01", "Test window")]:
        ax.axvline(pd.Timestamp(d), color=GRID, lw=1.5)
        ax.text(pd.Timestamp(d), ax.get_ylim()[1] * .97, " " + t, color=MUTED, fontsize=11, va="top")
    ax.set_title(f"{label}: names covered per month", loc="left", fontsize=20, color=INK, pad=14)
    ax.set_ylabel("Names", color=INK2, fontsize=12)
    for s in ["top", "right"]:ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=11)
    ax.grid(axis="y", color=GRID, lw=.8)
    ax.legend(frameon=False, fontsize=11, labelcolor=INK2, loc="upper left", bbox_to_anchor=(0, -.08), ncol=4)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def first_at_half(m, col, base):
    if not base:return None
    reached = m.index[m[col] >= base / 2]
    return str(reached[0]) if len(reached) else "never"


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
    p, key = load_panel(args.panel)
    c = load_chars(args.chars)
    p = map_ids(p, key, c)
    m, base = coverage(p, c)
    names = per_name(p)
    m.to_csv(out / f"{stem}.csv")
    names.to_csv(out / f"{stem}_by_name.csv", index=False)
    p[~p.map_status.str.startswith("matched")].to_csv(out / f"{stem}_not_live_rows.csv", index=False)
    chart(m, base, args.label, out / f"{stem}.png")
    full = len(m)
    print(f"{args.label}: {p.id.nunique()} {key}s, {m.index[0]} to {m.index[-1]} ({full} months); "
          f"{int((names.months_with_value == full).sum())} names have a value in every month")
    for col, what in [("names_with_value", "all names"), ("names_with_value_live_in_panel", "names live in our panel")]:
        b = base[col]
        if not b:print(f"  {what}: no 2024 values, so no baseline: rules 5 and 6 cannot be scored");continue
        print(f"  {what}: 2024 average {b:.0f}; first month at half that: {first_at_half(m, col, b)}; "
              f"2019-01 {m.loc[pd.Period('2019-01', 'M'), col] if pd.Period('2019-01', 'M') in m.index else 'n/a'}, "
              f"2021-01 {m.loc[pd.Period('2021-01', 'M'), col] if pd.Period('2021-01', 'M') in m.index else 'n/a'}")
    print("  map status (rows):", p.map_status.value_counts().to_dict())
    print(f"  zero values: {int((p.value == 0).sum())}; missing values: {int(p.value.isna().sum())}")
    print(f"-> {out / stem}.csv, _by_name.csv, _not_live_rows.csv, .png")


if __name__ == "__main__":
    main()

"""Step 0: survivorship check of the Carbon Arc permno mapping (descriptive only).

For each dataset:
  - how many mapped permnos left the panel before 2025, by exit year;
  - Carbon Arc months that fall after a permno's last panel month (a sign the
    series belongs to today's company, not the one that delisted);
  - coverage of comparable panel stocks still listed in Aug 2026 vs stocks
    that exited earlier. Comparable = same 2-digit GICS sectors as the mapped
    names, present in the panel during the dataset's months, size group small
    or larger at least once in that period.

Writes step0_survivorship.csv (counts and shares only).
"""
import pandas as pd

from altdata_lib import DATASETS, LABEL, OUT, load_ca, load_panel

LAST = pd.Timestamp("2026-08-31")


def main():
    p = load_panel(("permno", "eom", "gics", "size_grp"))
    life = p.groupby("permno")["eom"].agg(first="min", last="max")
    rows = []
    for name in DATASETS:
        ca = load_ca(name)
        lo, hi = ca["eom"].min(), ca["eom"].max()
        mapped = pd.Index(ca["permno"].unique())
        lf = life.reindex(mapped)
        alive = lf["last"] == LAST
        left_pre2025 = lf["last"] < pd.Timestamp("2025-01-01")
        ca = ca.join(life, on="permno")
        after_exit = (ca["eom"] > ca["last"]).sum()
        before_entry = (ca["eom"] < ca["first"]).sum()
        not_live = (~ca.set_index(["permno", "eom"]).index.isin(
            p.set_index(["permno", "eom"]).index)).sum()

        # comparable universe
        w = p[(p["eom"] >= lo) & (p["eom"] <= hi)]
        sectors = w[w["permno"].isin(mapped)].groupby("permno")["gics"].last().str[:2]
        sec_set = set(sectors.value_counts()[lambda s: s >= 3].index)
        w = w[w["gics"].str[:2].isin(sec_set)]
        big = w[w["size_grp"].isin(["small", "large", "mega"])]["permno"].unique()
        big_lm = w[w["size_grp"].isin(["large", "mega"])]["permno"].unique()
        r = {"dataset": LABEL[name], "data months": f"{lo:%Y-%m} to {hi:%Y-%m}",
             "mapped permnos": len(mapped),
             "mapped: still in panel Aug 2026": int(alive.sum()),
             "mapped: left panel before 2025": int(left_pre2025.sum()),
             "mapped: left panel 2025 to Jul 2026": int((~alive & ~left_pre2025).sum()),
             "CA rows after permno's last panel month": int(after_exit),
             "CA rows before permno's first panel month": int(before_entry),
             "CA rows on months with no panel row": int(not_live),
             "CA rows total": len(ca),
             "comparison sectors (2-digit GICS, >=3 mapped names)": " ".join(sorted(sec_set))}
        for tag, uni in [("small+", big), ("large/mega", big_lm)]:
            u = pd.Index(uni)
            ua = life.reindex(u)["last"] == LAST
            cov = u.isin(mapped)
            r[f"{tag}: listed Aug 2026, n"] = int(ua.sum())
            r[f"{tag}: listed Aug 2026, % covered"] = round(100 * cov[ua.values].mean(), 1)
            r[f"{tag}: exited earlier, n"] = int((~ua).sum())
            r[f"{tag}: exited earlier, % covered"] = round(100 * cov[~ua.values].mean(), 1)
        ex = lf.loc[~alive, "last"].dt.year.value_counts().sort_index()
        r["mapped exits by year"] = ", ".join(f"{y}:{n}" for y, n in ex.items()) or "none"
        rows.append(r)
    out = pd.DataFrame(rows).set_index("dataset").T
    out.to_csv(OUT / "step0_survivorship.csv")
    pd.set_option("display.width", 200, "display.max_colwidth", 60)
    print(out.to_string())


if __name__ == "__main__":
    main()

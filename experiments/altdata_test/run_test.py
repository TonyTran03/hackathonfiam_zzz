"""Step 2: compute everything exactly as written in RULE.md.

Writes aggregates only: tables.md (pasted into RESULTS.md), monthly_stats.csv
(monthly IC / long-short / name counts), cum_ic.png, cum_long_short.png.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from altdata_lib import DATASETS, LABEL, OUT, STATUS, load_ca, load_panel

DESIGN_END = pd.Timestamp("2020-12-31")           # by return month
TEST = (pd.Timestamp("2021-01-31"), pd.Timestamp("2026-08-31"))
KEEP_SIZE = ["small", "large", "mega"]
MIN_SECTOR = 5
NW_LAGS = 3
COLORS = {"foot_traffic": "#2a78d6", "card_spend": "#eb6834", "web_traffic": "#1baf7a"}
STYLES = {"foot_traffic": "-", "card_spend": "--", "web_traffic": ":"}


# ---------------------------------------------------------------- signal
def build_signal(name, panel, live):
    ca = load_ca(name)
    ca = ca.merge(live, on=["permno", "eom"])                      # live stock-months only
    num = ca.assign(eom=ca["eom"] + pd.offsets.MonthEnd(1)).rename(columns={"value": "num"})
    den = ca.assign(eom=ca["eom"] + pd.offsets.MonthEnd(13)).rename(columns={"value": "den"})
    s = num.merge(den, on=["permno", "eom"])
    s = s[s["num"].notna() & s["den"].notna() & (s["den"] != 0)]
    s["growth"] = s["num"] / s["den"] - 1
    s = s[np.isfinite(s["growth"])][["permno", "eom", "growth"]]
    d = s.merge(panel, on=["permno", "eom"])                       # panel row at t
    d = d[(d["prc"] >= 5) & d["size_grp"].isin(KEEP_SIZE) & d["sector"].notna()
          & d["ret_exc_lead1m"].notna()]
    n = d.groupby(["eom", "sector"])["permno"].transform("size")
    d = d[n >= MIN_SECTOR].copy()
    nsec = d.groupby("eom")["sector"].transform("nunique")
    d = d[nsec >= 2].copy()
    g = d.groupby(["eom", "sector"])
    r = g["growth"].rank()
    d["z"] = (r - r.groupby([d["eom"], d["sector"]]).transform("mean")) / \
        r.groupby([d["eom"], d["sector"]]).transform("std", ddof=0)
    m = g["ret_12_1"].rank()
    d["z_mom"] = (m - m.groupby([d["eom"], d["sector"]]).transform("mean")) / \
        m.groupby([d["eom"], d["sector"]]).transform("std", ddof=0)
    d["ret_month"] = d["eom"] + pd.offsets.MonthEnd(1)
    return d


# ---------------------------------------------------------------- monthly stats
def long_short(x):
    out, w = 0.0, 0
    for _, s in x.groupby("sector"):
        k = len(s) // 3
        s = s.sort_values("growth")
        out += len(s) * (s["ret_exc_lead1m"].iloc[-k:].mean() - s["ret_exc_lead1m"].iloc[:k].mean())
        w += len(s)
    return out / w


def monthly(d):
    rows = []
    for t, x in d.groupby("ret_month"):
        rows.append({"ret_month": t, "ic": x["z"].corr(x["ret_exc_lead1m"], method="spearman"),
                     "ls": long_short(x), "names": len(x), "sectors": x["sector"].nunique()})
    return pd.DataFrame(rows)


def nw_t(x, lags=NW_LAGS):
    x = np.asarray(x, float)
    T = len(x)
    if T < 3:
        return np.nan
    e = x - x.mean()
    v = e @ e / T
    for l in range(1, min(lags, T - 1) + 1):
        v += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / T
    return x.mean() / np.sqrt(v / T)


def summarise(m, d):
    if m.empty:
        return {"months": 0}
    T = len(m)
    sd = m["ls"].std(ddof=1)
    return {"months": T,
            "first-last return month": f"{m.ret_month.min():%Y-%m} to {m.ret_month.max():%Y-%m}",
            "avg names/month": m["names"].mean(),
            "sectors covered": d["sector"].nunique(),
            "mean IC": m["ic"].mean(), "IC t (NW3)": nw_t(m["ic"]),
            "hit rate": (m["ic"] > 0).mean(),
            "L-S mean %/mo": 100 * m["ls"].mean(),
            "L-S Sharpe (ann.)": m["ls"].mean() / sd * np.sqrt(12) if T > 1 else np.nan,
            "L-S t": m["ls"].mean() / (sd / np.sqrt(T)) if T > 1 else np.nan}


def in_window(df, col, w):
    if w == "design":
        return df[df[col] <= DESIGN_END]
    return df[(df[col] >= TEST[0]) & (df[col] <= TEST[1])]


# ---------------------------------------------------------------- correlations
def avg_xs_corr(a, b, min_n=20):
    j = a.merge(b, on=["permno", "eom"])
    cs = [x["a"].corr(x["b"], method="spearman") for _, x in j.groupby("eom") if len(x) >= min_n]
    return (np.nanmean(cs) if cs else np.nan), len(cs), (j.groupby("eom").size().mean() if len(j) else 0)


def fmt(v, k):
    if isinstance(v, str):
        return v
    if k in ("months", "sectors covered"):
        return f"{int(v)}"
    if k == "hit rate":
        return f"{100 * v:.0f}%"
    if k == "avg names/month":
        return f"{v:.0f}"
    if k == "mean IC":
        return f"{v:+.3f}"
    if k == "L-S mean %/mo":
        return f"{v:+.2f}"
    return f"{v:+.2f}"


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def main():
    panel = load_panel()
    live = panel[["permno", "eom"]]
    sig, mon = {}, {}
    for name in DATASETS:
        sig[name] = build_signal(name, panel, live)
        mon[name] = monthly(sig[name])

    md = []
    # --- main tables
    keys = ["months", "first-last return month", "avg names/month", "sectors covered", "mean IC",
            "IC t (NW3)", "hit rate", "L-S mean %/mo", "L-S Sharpe (ann.)", "L-S t"]
    rows = []
    for name in DATASETS:
        for w in ["design", "test"]:
            s = summarise(in_window(mon[name], "ret_month", w), in_window(sig[name], "ret_month", w))
            r = {"dataset": LABEL[name], "status": STATUS[name], "window": w}
            for k in keys:
                r[k] = fmt(s[k], k) if k in s else "–"
            rows.append(r)
    main_tab = pd.DataFrame(rows)
    md.append("## Main table\n\n" + md_table(main_tab))

    # --- per year, test window
    yrows = []
    for name in DATASETS:
        m = in_window(mon[name], "ret_month", "test")
        for y, x in m.groupby(m["ret_month"].dt.year):
            sd = x["ls"].std(ddof=1)
            yrows.append({"dataset": LABEL[name], "year": y, "months": len(x),
                          "avg names": f"{x['names'].mean():.0f}",
                          "mean IC": f"{x['ic'].mean():+.3f}", "hit rate": f"{100 * (x['ic'] > 0).mean():.0f}%",
                          "L-S mean %/mo": f"{100 * x['ls'].mean():+.2f}",
                          "L-S t": f"{x['ls'].mean() / (sd / np.sqrt(len(x))):+.2f}" if len(x) > 1 else "–"})
    md.append("## Per year, test window (by return year)\n\n" + md_table(pd.DataFrame(yrows)))

    # --- correlations
    crow = []
    names = list(DATASETS)
    for w in ["test", "all"]:
        pick = (lambda d: in_window(d, "ret_month", "test")) if w == "test" else (lambda d: d)
        for i, a in enumerate(names):
            A = pick(sig[a])
            c, n, sh = avg_xs_corr(A[["permno", "eom", "z"]].rename(columns={"z": "a"}),
                                   A[["permno", "eom", "z_mom"]].rename(columns={"z_mom": "b"}))
            crow.append({"window": w, "pair": f"{LABEL[a]} vs momentum (ret_12_1)",
                         "avg monthly Spearman": f"{c:+.3f}" if n else "n/a", "months used": n,
                         "avg shared names": f"{sh:.0f}"})
            for b in names[i + 1:]:
                B = pick(sig[b])
                c, n, sh = avg_xs_corr(A[["permno", "eom", "z"]].rename(columns={"z": "a"}),
                                       B[["permno", "eom", "z"]].rename(columns={"z": "b"}))
                crow.append({"window": w, "pair": f"{LABEL[a]} vs {LABEL[b]}",
                             "avg monthly Spearman": f"{c:+.3f}" if n else "n/a (never >=20 shared names)",
                             "months used": n, "avg shared names": f"{sh:.0f}"})
    md.append("## Correlation with each other and with momentum\n\n" + md_table(pd.DataFrame(crow)))
    (OUT / "tables.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")

    allm = pd.concat([m.assign(dataset=LABEL[n]) for n, m in mon.items()])
    allm.to_csv(OUT / "monthly_stats.csv", index=False, float_format="%.6f")

    # --- charts
    for col, fname, ylab, scale in [("ic", "cum_ic.png", "Cumulative IC (sum of monthly IC)", 1),
                                    ("ls", "cum_long_short.png", "Cumulative long-short return (sum, %)", 100)]:
        fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
        fig.patch.set_facecolor("#fcfcfb")
        ax.set_facecolor("#fcfcfb")
        ends = []
        for n in DATASETS:
            m = mon[n].sort_values("ret_month")
            y = (m[col] * scale).cumsum()
            ax.plot(m["ret_month"], y, STYLES[n], color=COLORS[n], lw=2,
                    label=f"{LABEL[n]} ({STATUS[n]})")
            ends.append([y.iloc[-1], m["ret_month"].iloc[-1], LABEL[n]])
        lo, hi = ax.get_ylim()
        gap = 0.06 * (hi - lo)                     # keep end labels from overlapping
        ends.sort()
        pos = []
        for y0, _, _ in ends:
            pos.append(y0 if not pos else max(y0, pos[-1] + gap))
        for (y0, x0, lab), yp in zip(ends, pos):
            ax.annotate(lab, (x0, y0), xytext=(x0 + pd.Timedelta(days=12), yp),
                        va="center", fontsize=9, color="#3d3d3a")
        ax.axvline(TEST[0] - pd.offsets.MonthEnd(1) + pd.Timedelta(days=1), color="#8a8a85", lw=1)
        ax.text(TEST[0], lo, "  test window →", va="bottom", fontsize=9, color="#5c5c58")
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.set_ylabel(ylab, color="#3d3d3a")
        ax.grid(axis="y", color="#e6e5e0", lw=0.8)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        for s in ["left", "bottom"]:
            ax.spines[s].set_color("#c3c2b7")
        ax.tick_params(colors="#5c5c58")
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, fontsize=9)
        ax.set_title(ylab.split(" (")[0] + " by return month, one line per dataset",
                     loc="left", fontsize=11, color="#1f1f1d")
        fig.tight_layout()
        fig.savefig(OUT / fname)
        plt.close(fig)

    print("\n\n".join(md))


if __name__ == "__main__":
    main()

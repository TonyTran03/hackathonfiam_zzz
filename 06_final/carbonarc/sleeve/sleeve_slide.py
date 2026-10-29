"""One slide for the news -> foot-traffic sleeve (RESULTS.md), as a 1600 x 1000 PNG.

Top left: the agent's chain and picks. Top right: D(m), winners' minus losers' foot-traffic
growth, with the confirmation month and the holding window. Bottom left: the pair against the
S&P 500. Bottom right: the placebo distribution and the real pair's percentile. Reads only the
aggregate outputs of sleeve_run.py (no licensed values).

    python 06_final/carbonarc/sleeve/sleeve_slide.py --input <sleeve_run.py output dir>
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import pandas as pd

OUT = Path(__file__).with_name("sleeve_slide.png")
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
HIT, NEG, UNK = "#2a78d6", "#c2410c", "#b9b8b2"
CHAIN = ["Used cars +31%,\nnew cars +11%\n(CPI release)", "Squeezed budgets,\ndearer car loans\n(Fed taper)",
         "Households keep\nold cars longer", "More repairs:\nparts and service\nvisits rise"]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ["top", "right"]:ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=10.5)
    ax.grid(axis="y", color=GRID, lw=.8)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--input", type=Path, required=True)
    i = a.parse_args().input
    res = json.loads((i / "result.json").read_text())
    sp = pd.read_csv(i / "spread_by_data_month.csv", index_col=0)
    sp.index = pd.PeriodIndex(sp.index, freq="M").to_timestamp()
    path = pd.read_csv(i / "pair_path_daily.csv", index_col=0, parse_dates=True)
    plac = pd.read_csv(i / "placebo_draws.csv")

    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor=SURFACE)
    fig.text(0.04, 0.935, "AI proposes, foot traffic confirms: auto parts over car dealers, +16% in 6 months",
             fontsize=24, weight="bold")
    fig.text(0.04, 0.893, "News agent on masked Dec-2021 CPI and Fed releases; rule pre-registered (commit 07cfc0f); "
             "one run, within Consumer Discretionary, gross of costs.", fontsize=13.5, color=INK2)

    # Chain
    for k, t in enumerate(CHAIN):
        x = 0.04 + k * 0.112
        fig.patches.append(FancyBboxPatch((x, 0.705), 0.098, 0.12, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, facecolor=SURFACE, edgecolor=GRID, lw=1.6))
        fig.text(x + 0.049, 0.765, t, fontsize=10.5, ha="center", va="center", linespacing=1.35)
        if k < 3:fig.text(x + 0.1045, 0.765, "→", fontsize=16, ha="center", va="center", color=MUTED)
    fig.text(0.04, 0.665, "Long  AZO · ORLY · MNRO · GPC", fontsize=13, color=HIT, weight="bold")
    fig.text(0.04, 0.633, "Short KMX · AN · LAD · SAH · PAG · CRMT", fontsize=13, color=NEG, weight="bold")
    fig.text(0.04, 0.600, "All Consumer Discretionary, so the pair carries no sector bet. Picked by the agent, unedited.",
             fontsize=11, color=INK2)

    # D(m)
    ax = fig.add_axes([0.53, 0.58, 0.43, 0.27]);style(ax)
    d = sp.D.loc["2021-09-01":] * 100   # earlier months compare against the 2020 lockdown base
    ax.bar(d.index, d.values, width=24, color=[HIT if v > 0 else UNK for v in d.values])
    ax.axhline(0, color=INK2, lw=.8)
    conf = pd.Timestamp(res["data_months_used"][1] + "-01")
    ax.annotate("Confirmed: Dec + Jan data > 0,\nusable from Mar-2022 (T+5 + 1 month)", xy=(conf, d.loc[conf]),
                xytext=(pd.Timestamp("2021-09-01"), 26), fontsize=10, color=INK, arrowprops=dict(arrowstyle="->", color=INK2))
    ax.axvspan(pd.Timestamp("2022-03-01"), pd.Timestamp("2022-08-31"), color=HIT, alpha=.07)
    ax.text(pd.Timestamp("2022-03-08"), d.min() * .95, "holding period", fontsize=9.5, color=MUTED, va="bottom")
    ax.set_title("Parts minus dealers: 3-month YoY foot-traffic growth, by data month (pp)", loc="left", fontsize=12.5, color=INK)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))

    # Pair vs S&P
    ax = fig.add_axes([0.06, 0.14, 0.40, 0.36]);style(ax)
    ax.plot(path.index, path.pair_equal_dollar_cum * 100, color=HIT, lw=2.4, label=f"Pair, equal dollars  {res['pair_equal_dollar']*100:+.1f}%")
    ax.plot(path.index, path.sp500_cum * 100, color=INK2, lw=1.6, ls="--", label=f"S&P 500  {res['sp500_return']*100:+.1f}%")
    ax.axhline(0, color=INK2, lw=.8)
    ax.set_title(f"Pair vs S&P 500, {res['entry_close']} to {res['exit_close']} (%)", loc="left", fontsize=12.5, color=INK)
    ax.legend(frameon=False, fontsize=11, labelcolor=INK2, loc="lower left")
    ax.text(0.99, 0.04, f"Beta-matched pair {res['pair_beta_matched']*100:+.1f}%", transform=ax.transAxes, ha="right",
            fontsize=10.5, color=INK2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))

    # Placebo
    ax = fig.add_axes([0.55, 0.14, 0.41, 0.36]);style(ax)
    ax.hist(plac.pair_equal_dollar * 100, bins=40, color=UNK, edgecolor=SURFACE)
    ax.axvline(res["pair_equal_dollar"] * 100, color=HIT, lw=2.6)
    ax.text(res["pair_equal_dollar"] * 100 + 1.5, ax.get_ylim()[1] * .97,
            f"Real pair\nbeats {res['placebo_pct_below_equal_dollar']:.0f}% of\nrandom pairs\n(p ≈ 0.11)",
            fontsize=11.5, color=HIT, va="top", ha="left", weight="bold")
    ax.set_title(f"Placebo: {res['placebo_draws']:,} random 4-vs-6 pairs from the same {res['placebo_pool_size']} names (%)",
                 loc="left", fontsize=12.5, color=INK)

    fig.text(0.04, 0.035, "Demonstration, not proof: one event we already know; the model was trained on 2022 news; not significant at 5%;\n"
             "foot traffic is today's snapshot, not point-in-time. Details: 06_final/carbonarc/sleeve/RESULTS.md.",
             fontsize=10.5, color=MUTED)
    fig.savefig(OUT, facecolor=SURFACE)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

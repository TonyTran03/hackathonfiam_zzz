"""Stage 5m -- could this book actually be traded at the mandated fund size?

    python 04_backtest_scoring/19_capacity.py [holdings.parquet]

The finals mandate endows the fund with US$1bn. That single number decides
whether a backtest describes a portfolio or a fantasy, because every weight is
now a dollar order that has to go through a real order book.

The round-one submission fails this badly and it is worth being precise about
how: the median LONG position was 36% of its name's average daily volume, 63%
of long positions sat above 20%, and United States Lime & Minerals -- one of
the ten largest long holdings -- would have required 32 days of the stock's
entire traded volume to build. Professional desks stay under 10-20% of volume
precisely because above that the price moves against you while you are still
filling, so the returns the backtest recorded were never available.

This measures it rather than asserting it, and writes capacity.csv plus the
distribution exhibit the finals ask for by name.

Conventions: ADV is `dolvol_126d`, the 126-day average DAILY dollar volume.
The round-one deck reported `dolvol`, which is the month's total, as a daily
figure -- a factor of about twenty-one.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

FUND_USD = 1_000_000_000.0
PARTICIPATION = 0.10          # the share of a day's volume we are willing to be
ADV_COL = "dolvol_126d"
OUT = C.ROOT / "05_submission" / "capacity.csv"
FIG = C.ROOT / "05_submission" / "figures" / "capacity.png"

rows = []


def put(leg, metric, value, note=""):
    rows.append({"leg": leg, "metric": metric, "value": value, "note": note})


def load(path):
    h = pd.read_parquet(path)
    if ADV_COL not in h.columns:
        panel = pd.read_parquet(C.MODEL_TABLE,
                                columns=["permno", "target_month", ADV_COL, "me"])
        h = h.merge(panel, on=["permno", "target_month"], how="left")
    return h.dropna(subset=[ADV_COL])


def main(argv):
    path = Path(argv[0]) if argv else C.PROCESSED_DIR / "holdings.parquet"
    h = load(path)
    h["usd"] = FUND_USD * h["weight"].abs()
    h["pct_adv"] = h["usd"] / h[ADV_COL]
    h["days"] = h["pct_adv"] / PARTICIPATION      # days to build at the limit
    h["leg"] = np.where(h["weight"] > 0, "long", "short")

    print("=" * 76)
    print("CAPACITY AT US$%.0fbn  (%s, %d months)"
          % (FUND_USD / 1e9, path.name, h["target_month"].nunique()))
    print("  ADV is the 126-day average DAILY dollar volume")
    print("=" * 76)
    print("  %-7s %9s %11s %10s %10s %11s"
          % ("leg", "position", "% of ADV", "90th pct", "days to", "above 20%"))
    print("  %-7s %9s %11s %10s %10s %11s"
          % ("", "median", "median", "", "build", "of ADV"))
    for leg, g in h.groupby("leg"):
        print("  %-7s $%7.1fm %10.0f%% %9.0f%% %10.1f %10.0f%%"
              % (leg, g["usd"].median() / 1e6, 100 * g["pct_adv"].median(),
                 100 * g["pct_adv"].quantile(0.9), g["days"].median(),
                 100 * (g["pct_adv"] > 0.20).mean()))
        put(leg, "median position", "$%.1fm" % (g["usd"].median() / 1e6))
        put(leg, "median share of ADV", "%.0f%%" % (100 * g["pct_adv"].median()))
        put(leg, "90th percentile share of ADV",
            "%.0f%%" % (100 * g["pct_adv"].quantile(0.9)))
        put(leg, "positions above 20% of ADV",
            "%.0f%%" % (100 * (g["pct_adv"] > 0.20).mean()))
        put(leg, "median days to build",
            "%.1f" % g["days"].median(), "at %.0f%% of volume" % (100 * PARTICIPATION))
        put(leg, "worst days to build", "%.0f" % g["days"].max())
        tradable = g["pct_adv"] <= PARTICIPATION
        put(leg, "positions inside the participation limit",
            "%.0f%%" % (100 * tradable.mean()),
            "%.0f%% of the money" % (100 * g.loc[tradable, "usd"].sum()
                                     / g["usd"].sum()))

    print("\n  SHARE OF THE BOOK INSIDE THE %.0f%% PARTICIPATION LIMIT"
          % (100 * PARTICIPATION))
    for leg, g in h.groupby("leg"):
        t = g["pct_adv"] <= PARTICIPATION
        print("    %-7s %.0f%% of positions, %.0f%% of the money"
              % (leg, 100 * t.mean(),
                 100 * g.loc[t, "usd"].sum() / g["usd"].sum()))

    print("\n  THE NAMES THAT CANNOT ABSORB THEIR POSITION")
    worst = h.nlargest(5, "pct_adv")
    for _, r in worst.iterrows():
        name = str(r.get("company_name", ""))[:34]
        print("    %-6s %-34s $%5.1fm into $%6.2fm/day = %6.0f%% (%s)"
              % (r.get("ticker", ""), name, r["usd"] / 1e6,
                 r[ADV_COL] / 1e6, 100 * r["pct_adv"], r["leg"]))
        put(r["leg"], "worst name: %s" % r.get("ticker", ""),
            "%.0f%% of ADV" % (100 * r["pct_adv"]),
            "%s, $%.1fm into $%.2fm a day" % (name, r["usd"] / 1e6,
                                              r[ADV_COL] / 1e6))

    if "me" in h.columns:
        s = h[h["leg"] == "short"]
        below = s["me"] < 500
        print("\n  MANDATE: short leg market cap >= US$500m")
        print("    %s of %s short positions below the floor (%.2f%% by weight)"
              % (format(int(below.sum()), ","), format(len(s), ","),
                 100 * s.loc[below, "weight"].abs().sum()
                 / s["weight"].abs().sum()))
        put("short", "below the US$500m floor", "%d of %d" % (below.sum(), len(s)),
            "%.2f%% by weight" % (100 * s.loc[below, "weight"].abs().sum()
                                  / s["weight"].abs().sum()))

    # The exhibit the finals ask for by name: position size in days of volume,
    # the two legs shown separately.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 3.6))
        bins = np.logspace(-2, 2.6, 46)
        for leg, colour in [("long", "#1E2761"), ("short", "#A62B1F")]:
            g = h[h["leg"] == leg]
            ax.hist(g["days"].clip(0.01, 400), bins=bins, alpha=0.6,
                    label="%s leg" % leg, color=colour)
        ax.axvline(1.0, color="black", lw=1.0, ls="--",
                   label="one day at %.0f%% of volume" % (100 * PARTICIPATION))
        ax.set_xscale("log")
        ax.set_xlabel("trading days to build the position at %.0f%% of daily volume"
                      % (100 * PARTICIPATION))
        ax.set_ylabel("positions")
        ax.set_title("Position size in days of volume, US$%.0fbn fund"
                     % (FUND_USD / 1e9))
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        FIG.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG, dpi=150)
        print("\n  wrote %s" % FIG.relative_to(C.ROOT))
    except ImportError:
        print("\n  matplotlib unavailable; chart skipped")

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("  wrote %s" % OUT.relative_to(C.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""One run of the news -> foot-traffic sleeve, exactly as fixed in PROTOCOL_SLEEVE.md (commit 07cfc0f).

Step 3 (confirmation, sections 2-3) uses foot traffic only. Step 4 (return test and placebo,
section 4) uses our daily returns. Nothing here is tuned; run it once.

    python 06_final/carbonarc/sleeve/sleeve_run.py --panel ~/Downloads/foot_traffic_monthly.csv \
        --permno-map <dir>/dd_coverage_foot_traffic_permno_map.csv --output <dir outside the repo>

The panel and the map stay outside the repo (licensed data). The outputs are aggregates.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
W = ["AZO", "ORLY", "MNRO", "GPC"]
L = ["KMX", "AN", "LAD", "SAH", "PAG", "CRMT"]
SEED, DRAWS, HOLD, BETA_DAYS = 2026, 1000, 6, 252


def growth(panel, pmap):
    """g_i(m): 3-month sum over the same 3 months a year earlier, minus 1; live stock-months only."""
    p = panel.merge(pmap, on=["ticker", "month"], how="left")
    p["live"] = p.map_status.fillna("").str.startswith("matched")
    p["month"] = pd.PeriodIndex(p.month, freq="M")
    v = p.pivot(index="month", columns="ticker", values="foot_traffic").sort_index()
    v = v.reindex(pd.period_range(v.index.min(), v.index.max(), freq="M"))
    live = p.pivot(index="month", columns="ticker", values="live").reindex(v.index).fillna(False).astype(bool)
    s3 = v.rolling(3, min_periods=3).sum()          # NaN unless all 3 months have values
    g = s3 / s3.shift(12) - 1
    return g.where(live), p


def spread(g):
    gw, gl = g.reindex(columns=W), g.reindex(columns=L)
    nw, nl = gw.notna().sum(axis=1), gl.notna().sum(axis=1)
    d = gw.mean(axis=1) - gl.mean(axis=1)
    return pd.DataFrame({"mean_g_winners": gw.mean(axis=1), "mean_g_losers": gl.mean(axis=1), "n_winners": nw,
                         "n_losers": nl, "D": d.where((nw >= 2) & (nl >= 2))})


def confirm(sp):
    for f in pd.period_range("2022-01", "2022-12", freq="M"):
        a, b = sp.D.get(f - 2), sp.D.get(f - 3)
        if pd.notna(a) and pd.notna(b) and a > 0 and b > 0:
            return f
    return None


def basket(r, names, start, end):
    """Equal-dollar buy-and-hold over [start, end]: daily value path of 1 dollar split equally."""
    x = r.loc[start:end, names].copy()
    x = x.fillna(0.0)                                # after delisting, proceeds earn zero
    return (1 + x).cumprod().mean(axis=1)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--panel", type=Path, required=True)
    a.add_argument("--permno-map", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = a.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(args.panel)
    pmap = pd.read_csv(args.permno_map)
    g, p = growth(panel, pmap)
    sp = spread(g)
    sp.loc["2021-01":"2022-12"].to_csv(args.output / "spread_by_data_month.csv")
    f = confirm(sp)
    res = {"confirmation_formation_month": str(f) if f else None}
    print(sp.loc["2021-09":"2022-12"].round(4).to_string())
    if f is None:
        res["result"] = "unconfirmed in 2022: no trade"
        (args.output / "result.json").write_text(json.dumps(res, indent=2));print(res);return
    res["data_months_used"] = [str(f - 3), str(f - 2)]

    # Step 4. permno for each pick from the map in the entry month (live by construction)
    perm = pmap[pmap.month == str(f)].set_index("ticker").permno
    cal = pd.read_parquet(ROOT / "06_final/data/calendar.parquet")[["date", "sp_ret"]].set_index("date").sp_ret
    days = cal.index[(cal.index >= f.start_time) & (cal.index <= (f + HOLD - 1).end_time)]
    entry, exit_ = days[0], days[-1]
    pre = cal.index[cal.index < entry][-BETA_DAYS:]
    # Placebo pool: names live with foot traffic at F whose GICS sector at F is the agent's (25).
    live_f = perm[perm.notna() & pmap[pmap.month == str(f)].set_index("ticker").map_status.str.startswith("matched")]
    c = pd.read_parquet(ROOT / "01_data/raw/chars_final_with_names.parquet", columns=["permno", "eom", "gics"])
    c = c[pd.PeriodIndex(pd.to_datetime(c.eom), freq="M") == f].set_index("permno").gics
    sec = live_f.astype(int).map(c).astype("Int64").astype(str).str[:2]
    pool_tick = sorted(sec[sec == "25"].index)
    tick_perm = {t: int(perm[t]) for t in set(pool_tick) | set(W) | set(L) if t in perm and pd.notna(perm[t])}
    d = pd.read_parquet(ROOT / "06_final/data/dsf.parquet", columns=["permno", "date", "daily_return"],
                        filters=[("permno", "in", list(tick_perm.values()))])
    d = d[(d.date >= pre[0]) & (d.date <= exit_)]
    r = d.pivot(index="date", columns="permno", values="daily_return").reindex(cal.loc[pre[0]:exit_].index)
    r.columns = [ {v: k for k, v in tick_perm.items()}[c] for c in r.columns]
    missing = [t for t in W + L if t not in r.columns]
    # Entry at the close of the first trading day: returns accrue from the next day.
    start = days[1]

    def legs(win, lose):
        vw, vl = basket(r, win, start, exit_), basket(r, lose, start, exit_)
        rw, rl = vw.iloc[-1] - 1, vl.iloc[-1] - 1
        bw = np.polyfit(cal.loc[pre], r.loc[pre, win].mean(axis=1).fillna(0), 1)[0]
        bl = np.polyfit(cal.loc[pre], r.loc[pre, lose].mean(axis=1).fillna(0), 1)[0]
        return rw, rl, rw - rl, rw - (bw / bl) * rl, bw, bl, vw, vl

    rw, rl, eq, bm, bw, bl, vw, vl = legs(W, L)
    rng = np.random.default_rng(SEED)
    pool = [t for t in pool_tick if t in r.columns]
    plac = []
    for _ in range(DRAWS):
        pick = rng.choice(pool, size=len(W) + len(L), replace=False)
        o = legs(list(pick[:len(W)]), list(pick[len(W):]))
        plac.append((o[2], o[3]))
    plac = np.array(plac)
    res.update({"entry_close": str(entry.date()), "exit_close": str(exit_.date()), "missing_names": missing,
                "winners_return": rw, "losers_return": rl, "pair_equal_dollar": eq, "pair_beta_matched": bm,
                "beta_winners": bw, "beta_losers": bl, "sp500_return": float((1 + cal.loc[start:exit_]).prod() - 1),
                "placebo_pool_size": len(pool), "placebo_draws": DRAWS,
                "placebo_pct_below_equal_dollar": float((plac[:, 0] < eq).mean() * 100),
                "placebo_pct_below_beta_matched": float((plac[:, 1] < bm).mean() * 100),
                "placebo_median_equal_dollar": float(np.median(plac[:, 0])), "placebo_median_beta_matched": float(np.median(plac[:, 1]))})
    m = pd.DataFrame({"winners_value": vw, "losers_value": vl}).resample("ME").last()
    m["pair_equal_dollar_cum"] = m.winners_value - m.losers_value
    m.to_csv(args.output / "pair_path_month_end.csv")
    (args.output / "result.json").write_text(json.dumps(res, indent=2, default=float))
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()

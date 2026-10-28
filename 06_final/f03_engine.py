"""Final stage 3 -- the daily engine: a US$1bn fund, marked every trading day.

    python 06_final/f03_engine.py --window design --freq M
    python 06_final/f03_engine.py --window test   --freq M --overlay E --layer rule

What one simulated day does, in this order:

  1. EARN. Positions carried from yesterday's close earn today's close-to-close
     return. Cash (capital less net position value, i.e. collateral plus short
     proceeds) earns the daily bill rate; short positions pay borrow. A name
     whose daily series has ended is closed at its delisting stub (see below).
  2. DECIDE, at today's close, using information dated YESTERDAY or earlier.
     That is the Section 7 convention: data through day t forms the book at
     the close of t+1. Today's return is already spent.
       - first trading day of a month: build the month's book from the
         monthly forecast (characteristics dated at the previous month end)
       - W / D frequency: re-tighten beta, caps and drift weekly / daily
       - E overlay: exit longs hit by a distress 8-K filed before today
       - risk layer: proposes scalings on exceptions
  3. ENFORCE, in code, after everything above has had its say: 200-500 names,
     gross <= 200%, net within +/-50%, 5% single-name cap, US$500m short
     floor at formation. Nothing hard is left to a prompt or a convention.
  4. TRADE at the close; pay commission, half-spread and square-root impact.

NAV accounting: NAV_d = NAV_{d-1} * (1 + rf_d) + sum_i x_i * (r_i - rf_d)
- borrow - costs, which is the total return on capital the instructions ask
for. Weights are positions over current NAV, so every order scales with the
fund as it compounds.

Delisting: if a held name has no return after its last trading day, the
position closes at a stub equal to the part of its monthly CRSP return the
daily series did not deliver. With no monthly return either, longs take -30%
and shorts 0%.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fconfig as F  # noqa: E402
import f02_signal as S  # noqa: E402

H = F.HOUSE
FIN = F.FINAL

GROSS_TARGET = 1.90          # at formation: room for a 5% market move before 200%
GROSS_TRIGGER = 1.995        # above this at a close, scale the whole book back
GROSS_RESET = 1.95
NET_TRIGGER = 0.48
MIN_NAMES_TRIGGER = 210      # refill legs before the 200 floor is reached
DISTRESS_ITEMS = {"4.01", "4.02", "1.03", "3.01"}


# ---------------------------------------------------------------- inputs
def load_inputs(window):
    cal = pd.read_parquet(F.DATA / "calendar.parquet")
    sig = pd.read_parquet(F.DATA / ("signal_%s.parquet" % window))
    if window == "test":
        lo, hi = FIN["oos_start"], FIN["oos_end"]
    else:
        lo, hi = F.DESIGN_START, F.DESIGN_END
    days = cal[(cal["date"] >= lo) & (cal["date"] <= hi)].reset_index(drop=True)
    # one extra day of history in front, so day 0 has a "yesterday"
    prev_day = cal.loc[cal["date"] < lo, "date"].max()

    perms = np.sort(sig["permno"].unique())
    dsf = pd.read_parquet(F.DSF_PARQUET)
    dsf = dsf[dsf["permno"].isin(perms) & (dsf["date"] >= prev_day) & (dsf["date"] <= hi)]
    R = (dsf.pivot(index="date", columns="permno", values="daily_return")
            .reindex(index=[prev_day] + list(days["date"]), columns=perms))
    P = (dsf.pivot(index="date", columns="permno", values="prc")
            .reindex(index=[prev_day] + list(days["date"]), columns=perms).abs())
    # NOT forward-filled: a name with no price today cannot be traded today
    P = P.replace([np.inf, -np.inf], np.nan)
    last = pd.read_parquet(F.DATA / "last_day.parquet")["last_day"].reindex(perms)
    return days, sig, perms, R.values, P.values, last.values


def load_events(perms):
    """Distress 8-Ks per (permno, filing_date). Used ONLY by the E overlay and
    the risk layer, both of which may act no earlier than the next close."""
    import pyarrow.parquet as pq
    from common import config as C
    f = pq.read_table(C.FILINGS_PARQUET, columns=["permno", "filing_date", "items"]).to_pandas()
    f = f[f["permno"].isin(perms)]
    f["filing_date"] = pd.to_datetime(f["filing_date"]).dt.normalize()
    f["distress"] = [bool(set(i) & DISTRESS_ITEMS) if i is not None else False for i in f["items"]]
    f = f[f["distress"]].drop_duplicates(["permno", "filing_date"])
    return f[["permno", "filing_date"]]


# ---------------------------------------------------------------- helpers
def dimson_beta(y, m):
    """Sum of slopes on market lag 0 and lag 1; corrects stale small-cap prices."""
    if len(y) < 3:
        return np.nan
    X = np.column_stack([np.ones(len(y) - 1), m[1:], m[:-1]])
    coef, *_ = np.linalg.lstsq(X, y[1:], rcond=None)
    return coef[1] + coef[2]


def leg_weights(vol, caps, notional):
    """Inverse-vol weights for one leg scaled to `notional`, each capped at
    caps[i] (fraction of NAV), excess redistributed. Returns weights and the
    notional actually placed (less than asked if the caps cannot absorb it)."""
    v = np.clip(vol, np.nanquantile(vol, 0.05), np.nanquantile(vol, 0.95))
    w = (1.0 / v)
    w = w / w.sum() * notional
    for _ in range(50):
        over = w > caps + 1e-12
        if not over.any():
            break
        excess = (w[over] - caps[over]).sum()
        w[over] = caps[over]
        free = ~over & (w < caps - 1e-12)
        if not free.any():
            break
        w[free] += excess * w[free] / w[free].sum()
    return w, w.sum()


# ---------------------------------------------------------------- engine
class Engine:
    def __init__(self, window, freq="M", overlay=None, layer=None, seed_legs=None, triage=None,
                 label=None, cost_scale=1.0, start_nav=None, cost_mode="sqrt:0.7",
                 borrow_mode="model", sector_neutral=False):
        self.window, self.freq, self.overlay, self.layer = window, freq, overlay, layer
        self.triage = triage            # f04_risk_layer.TriageLayer, optional
        self.sector_neutral = sector_neutral
        self.label = label or "%s_%s%s%s%s%s" % (window, freq, "_" + overlay if overlay else "",
                                                 "_" + layer.name if layer else "",
                                                 "_" + triage.name if triage else "",
                                                 "_secneu" if sector_neutral else "")
        self.cost_scale = cost_scale
        self.start_nav = start_nav or FIN["start_nav"]
        self.cost_mode, self.borrow_mode = cost_mode, borrow_mode
        (self.days, sig, self.perms, self.R, self.P, self.last) = load_inputs(window)
        self.pidx = {p: i for i, p in enumerate(self.perms)}
        self.sig_sel = {m: g.set_index("permno") for m, g in
                        S.select_inputs(sig).groupby("target_month")}
        self.stub = sig.set_index(["permno", "target_month"])["stub_ret"]
        self.events = load_events(self.perms) if (overlay == "E" or layer) else None
        if self.events is not None:
            self.events["pi"] = self.events["permno"].map(self.pidx)
        self.leg_hist = list(seed_legs) if seed_legs else []   # (mkt_ex, long_r, short_r)

    # ---- formation ---------------------------------------------------
    def leg_betas(self, est_l, est_s):
        h = self.leg_hist[-H["beta_window_days"]:]
        if len(h) < H["beta_min_days"]:
            return est_l, est_s, None
        a = np.array(h)
        bl, bs = dimson_beta(a[:, 1], a[:, 0]), dimson_beta(a[:, 2], a[:, 0])
        w = H["beta_feedback_weight"]
        return (1 - w) * est_l + w * bl, (1 - w) * est_s + w * bs, (bl, bs)

    def caps(self, g, nav):
        adv_cap = H["max_days_adv"] * H["max_participation"] * g["dolvol_126d"].values / nav
        return np.minimum(np.minimum(H["house_max_weight"], FIN["max_single_weight"]), adv_cap)

    def form(self, di, month, x, nav):
        g = self.sig_sel.get(month)
        if g is None:
            return None, {}
        g = g.copy()
        g["pi"] = [self.pidx[p] for p in g.index]
        # trading on the formation day requires a price yesterday and today
        pr_prev, pr_now = self.P[di], self.P[di + 1]   # row 0 is the extra day
        g["px_prev"], g["px_now"] = pr_prev[g["pi"]], pr_now[g["pi"]]
        alive = np.isfinite(self.R[di + 1][g["pi"].values])     # traded today
        g = g[g["px_prev"].notna() & g["px_now"].notna() & alive]
        # the mandate measures the short floor AT FORMATION; check it on both
        # yesterday's close (decision) and today's (execution)
        me_prev = g["shares"] * g["px_prev"]
        me_now = g["shares"] * g["px_now"]
        g["short_ok"] = (g["short_ok_eom"]
                         & (me_prev >= FIN["short_min_me_musd"] * H["short_floor_cushion"])
                         & (me_now >= FIN["short_min_me_musd"]))
        g["cap"] = self.caps(g, nav)

        held_l = set(np.array(self.perms)[x > 0])
        held_s = set(np.array(self.perms)[x < 0])
        n = H["n_per_leg"]
        wide = int(n * H["buffer_mult"])
        order = g.sort_values("score", ascending=False)
        long_zone = set(order.index[:wide])
        short_pool = order[order["short_ok"]].iloc[::-1]
        short_zone = set(short_pool.index[:wide])

        def pick(pool, held, zone, exclude):
            keep = [p for p in pool.index if p in held and p in zone]
            rest = [p for p in pool.index if p not in keep and p not in exclude]
            return keep, rest

        lk, lrest = pick(order, held_l, long_zone, set())
        longs = (lk + lrest)[:n]
        sk, srest = pick(short_pool, held_s, short_zone, set(longs))
        shorts = (sk + srest)[:n]

        L, Sx = g.loc[longs], g.loc[shorts]
        est_l = float(np.average(L["beta_use"], weights=1 / L["rvol_21d"]))
        est_s = float(np.average(Sx["beta_use"], weights=1 / Sx["rvol_21d"]))
        bl, bs, measured = self.leg_betas(est_l, est_s)
        if bl <= 0 or bs <= 0:
            bl, bs = 1.0, 1.0
        ln = GROSS_TARGET * bs / (bl + bs)
        sn = GROSS_TARGET - ln
        if abs(ln - sn) > H["net_cap"]:
            ln = (GROSS_TARGET + np.sign(ln - sn) * H["net_cap"]) / 2
            sn = GROSS_TARGET - ln
        if self.sector_neutral:
            # POST-HOC (mentor review, Oct 28): equal long and short dollars in
            # every GICS sector; market beta is left to an index-futures
            # overlay applied afterwards (f11_beta_hedge.py), not to leg sizes
            ln = sn = GROSS_TARGET / 2

        # capacity: extend a leg with the next names until its caps absorb it
        def place(names, rest, notional, sign):
            names = list(names)
            while True:
                G = g.loc[names]
                w, placed = leg_weights(G["rvol_21d"].values, G["cap"].values, notional)
                if placed >= notional * 0.999 or not rest or len(names) >= 250:
                    return G.index.values, sign * w, placed
                names.append(rest.pop(0))

        lrest2 = [p for p in order.index if p not in longs and p not in shorts]
        srest2 = [p for p in short_pool.index if p not in shorts and p not in longs]
        lnames, lw, lplaced = place(longs, lrest2, ln, 1.0)
        snames, sw, splaced = place(shorts, srest2, sn, -1.0)

        target = np.zeros(len(self.perms))
        target[g.loc[lnames, "pi"].values] = lw * nav
        target[g.loc[snames, "pi"].values] = sw * nav
        # no-trade band: a name held on the same side and within the band of
        # its new target keeps its current size; the names that do trade are
        # rescaled so each leg still carries its beta-matched notional
        band = H["no_trade_band"]
        same = (np.sign(x) == np.sign(target)) & (target != 0)
        keep = same & (np.abs(x - target) <= band * np.abs(target))
        for sgn, want in ((1, lplaced * nav), (-1, -splaced * nav)):
            leg = np.sign(target) == sgn
            kept = (x * (leg & keep)).sum()
            free = leg & ~keep
            tf = target[free].sum()
            if tf != 0 and np.sign(want - kept) == np.sign(tf):
                capd = g.set_index("pi")["cap"].reindex(np.where(free)[0]).values * nav
                target[free] = np.clip(target[free] * (want - kept) / tf, -capd, capd)
        target = np.where(keep, x, target)
        sector_net = {}
        if self.sector_neutral:
            target, sector_net = self.sector_balance(target, g, nav)
        info = {"est_beta_long": est_l, "est_beta_short": est_s,
                "used_beta_long": bl, "used_beta_short": bs,
                "measured": measured, "long_notional": lplaced, "short_notional": splaced,
                "n_long": len(lnames), "n_short": len(snames),
                "long_extended": len(lnames) - len(longs),
                "short_extended": len(snames) - len(shorts),
                "max_abs_sector_net": max(map(abs, sector_net.values())) if sector_net else None}
        self.month_target_w = target / nav
        self.month_rows = g
        return target, info

    def sector_balance(self, target, g, nav):
        """Equal long and short dollars in every GICS sector, total gross kept
        where the caps allow it, no name above its cap. A sector with names on
        one side only is closed (nothing in that sector to offset it).

        Amendment 3 fix. Each side of a sector holds at most the sum of its
        names' caps, so a sector carries at most min(long capacity, short
        capacity) per side. Each sector starts at the midpoint of its two
        sides; one common factor scales every sector toward the original
        gross, each stopping at its capacity. A sector whose lighter side is
        capped is therefore balanced by scaling its heavier side DOWN, and the
        freed gross goes to sectors with room. Within a side, names keep their
        relative sizes; any excess over a cap moves to that side's uncapped
        names. (The first version clipped to the caps after balancing, which
        undid the balance wherever the lighter side was capped.)
        Returns the new target ($) and each sector's net weight (% of NAV)."""
        sec = np.full(len(self.perms), "zz", dtype=object)
        sec[g["pi"].values] = g["sector"].astype(str).values
        caps = np.zeros(len(target))
        caps[g["pi"].values] = g["cap"].values * nav
        t = target.astype(float).copy()
        gross0 = np.abs(t).sum()
        # a name kept by the no-trade band may sit above today's cap: never
        # force a sale just to balance, never let it grow either
        caps = np.maximum(caps, np.abs(t))
        secs, mid, room = [], [], []
        for s in np.unique(sec[t != 0]):
            m = sec == s
            lo, sh = m & (t > 0), m & (t < 0)
            if not lo.any() or not sh.any():
                t[m] = 0.0
                continue
            secs.append(s)
            mid.append((t[lo].sum() - t[sh].sum()) / 2)
            room.append(min(caps[lo].sum(), caps[sh].sum()))
        mid, room = np.array(mid), np.array(room)

        def side(k):                                      # dollars per side
            return np.minimum(k * mid, room)

        if len(secs) and 2 * room.sum() > gross0:
            lo_k, hi_k = 0.0, 1.0
            while 2 * side(hi_k).sum() < gross0:
                hi_k *= 2
            for _ in range(60):                           # bisection on k
                k = (lo_k + hi_k) / 2
                lo_k, hi_k = (k, hi_k) if 2 * side(k).sum() < gross0 else (lo_k, k)
            e = side(hi_k)
        else:
            e = room                                      # caps bind everywhere
        for s, es in zip(secs, e):
            m = sec == s
            for idx in (np.where(m & (t > 0))[0], np.where(m & (t < 0))[0]):
                sgn = np.sign(t[idx[0]])
                w = np.abs(t[idx])
                w = w / w.sum() * es
                c = caps[idx]
                for _ in range(200):                      # water-fill under caps
                    over = w > c + 1e-6
                    if not over.any():
                        break
                    excess = (w[over] - c[over]).sum()
                    w[over] = c[over]
                    free = w < c - 1e-6
                    if not free.any():
                        break
                    w[free] += excess * w[free] / w[free].sum()
                t[idx] = sgn * w
        net = {s: 100 * t[sec == s].sum() / nav for s in np.unique(sec[t != 0])}
        return t, net

    # ---- costs -------------------------------------------------------
    def trade_cost(self, delta, g_cost):
        """Cost of a day's trades in $. Modes (all construction-layer only):
          sqrt:Y    commission + half-spread + Y * sigma * sqrt(|trade| / ADV)
                    (Y = 0.7 is the pre-registered headline)
          almgren   commission + half-spread + Almgren et al. (2005) impact
                    calibrated on Citigroup institutional orders, one-day
                    execution: 0.142 sigma (q)^0.6 temporary + 0.5 x 0.314
                    sigma q permanent, q = |trade| / ADV
          flat:B    B bps on every dollar traded, nothing else
        """
        a = np.abs(delta)
        hs, sig, adv = g_cost
        q = np.divide(a, adv, out=np.zeros_like(a), where=adv > 0)
        mode = self.cost_mode
        if mode.startswith("flat:"):
            return float(a.sum()) * float(mode[5:]) / 1e4
        if mode == "almgren":
            imp = 0.142 * sig * q ** 0.6 + 0.5 * 0.314 * sig * q
        else:
            y = float(mode[5:]) if mode.startswith("sqrt:") else H["impact_y"]
            imp = y * sig * np.sqrt(q)
        bps = H["commission_bps"] / 1e4 + hs + imp
        return float((a * bps).sum()) * self.cost_scale

    # ---- run ---------------------------------------------------------
    def run(self, quiet=False):
        t0 = time.time()
        nP = len(self.perms)
        x = np.zeros(nP)
        nav = self.start_nav
        cash = nav
        hs = np.full(nP, H["half_spread_cap_bps"] / 1e4)
        sig = np.full(nP, 0.03)
        adv = np.full(nP, np.nan)
        borrow = np.zeros(nP)
        month_in_book = None
        tw = np.zeros(nP)
        pending = np.zeros(nP, dtype=bool)
        gone = np.zeros(nP, dtype=bool)
        shares_now = np.full(nP, np.nan)
        decision_epoch = 0
        targets_log = []
        rows, pos_rows, trades, anomalies, form_log = [], [], [], [], []
        self.form_log_live = form_log        # read by the triage layer during the run
        acted_events = set()
        cum_month = np.ones(nP)      # running product of daily returns this month
        days = self.days

        for di in range(len(days)):
            d = days.loc[di]
            day, month = d["date"], d["month"]
            m_str = str(month)
            if d["is_formation"]:
                cum_month[:] = 1.0
            r = self.R[di + 1]
            rf = d["rf_d"]

            # ---- 1. earn ------------------------------------------------
            held = x != 0
            r_use = np.where(np.isnan(r), 0.0, r)
            dead = held & np.isnan(r) & (np.array(self.last, dtype="datetime64[ns]") < np.datetime64(day))
            stub_pnl = 0.0
            for i in np.where(dead)[0]:
                key = (self.perms[i], m_str)
                R_m = self.stub.get(key, np.nan)
                if np.isfinite(R_m):
                    s = (1 + R_m + d["tb3ms"] / 1200) / cum_month[i] - 1
                else:
                    s = H["delist_long"] if x[i] > 0 else H["delist_short"]
                s = float(np.clip(s, -1.0, 2.0))
                stub_pnl += x[i] * s
                anomalies.append({"date": day, "permno": int(self.perms[i]), "kind": "delisting",
                                  "position": x[i], "stub": s,
                                  "basis": "monthly CRSP remainder" if np.isfinite(R_m) else "default"})
                cash += x[i] * (1 + s)        # close: long sells, short buys back
                x[i] = 0.0
                tw[i] = 0.0                   # and never trade it again
                pending[i] = False
                gone[i] = True
            big = held & (np.abs(r_use) > 0.5)
            for i in np.where(big)[0]:
                anomalies.append({"date": day, "permno": int(self.perms[i]), "kind": "move>50%",
                                  "position": x[i], "ret": float(r_use[i])})
            cum_month *= (1 + r_use)

            x_open = x.copy()                  # positions that earn today
            longs, shorts = x > 0, x < 0
            lval, sval = x[longs].sum(), -x[shorts].sum()
            pnl_i = x * r_use
            long_r = pnl_i[longs].sum() / lval if lval > 0 else 0.0
            short_r = -pnl_i[shorts].sum() / sval if sval > 0 else 0.0   # return of the shorted names
            x = x * (1 + r_use)
            cash = cash * (1 + rf)
            fee = float((-x[x < 0] * borrow[x < 0]).sum() / 252)
            cash -= fee
            nav_prev = nav
            nav = cash + x.sum()
            day_ret = nav / nav_prev - 1
            # today's leg returns join the history only AFTER today's decision:
            # data through day t may form the book at the close of t+1
            today_leg = (d["mkt_ex"], long_r - rf, short_r - rf) if (lval > 0 and sval > 0) else None
            hi_ = np.where(held & (x_open != 0))[0]
            pos_rows.append(np.column_stack([np.full(len(hi_), di), self.perms[hi_],
                                             x_open[hi_], r_use[hi_], pnl_i[hi_]]))

            # ---- 2. decide at the close ------------------------------
            # tw: target weights (fraction of NAV); pending: names still being
            # worked toward their target. A real desk does not fill a $6m order
            # in one day in a name trading $20m, so execution is capped at
            # MAX_PARTICIPATION of ADV per name per day and the rest carries.
            reason = None
            forced = gone.copy()              # names trade triage may not touch today
            skip = (self.freq in ("B", "Q") and month_in_book is not None
                    and (month.month - 1) % (2 if self.freq == "B" else 3) != 0)
            if d["is_formation"] and m_str in self.sig_sel and not skip:
                target, info = self.form(di, m_str, x, nav)
                info.update({"date": day, "month": m_str, "nav": nav})
                form_log.append(info)
                g = self.month_rows
                # names leaving the book keep last month's cost inputs
                hs[g["pi"].values] = g["half_spread"].values
                sig[g["pi"].values] = g["rvol_21d"].clip(0.005, 0.2).values
                adv[g["pi"].values] = g["dolvol_126d"].values
                if self.borrow_mode == "flat":      # Section 7 alternative
                    b = np.where(g["size_grp"].isin(["mega", "large"]).values,
                                 H["flat_borrow_large_bps"], H["flat_borrow_other_bps"])
                else:
                    b = g["size_grp"].map(H["borrow_bps"]).fillna(500.0).values
                    b = b + np.where(g["ivol_top_decile"].values, H["borrow_hard_bps"], 0.0)
                borrow[g["pi"].values] = b / 1e4
                tw = target / nav
                nz_ = np.where(tw != 0)[0]
                targets_log.append(pd.DataFrame({
                    "date": day, "month": m_str, "permno": self.perms[nz_], "target_weight": tw[nz_],
                    "me_formation": (g.set_index("pi")["shares"] * g.set_index("pi")["px_now"]).reindex(nz_).values,
                    "dolvol_126d": adv[nz_], "target_usd": target[nz_]}))
                pending = (tw != 0) | (x != 0)
                shares_now[g["pi"].values] = g["shares"].values
                month_in_book = m_str
                decision_epoch += 1
                reason = "formation"
            elif month_in_book is not None and (
                    (self.freq == "W" and d["is_week_start"]) or self.freq == "D"):
                t2 = self.retighten(di, x, nav)
                if t2 is not None:
                    chg = np.abs(t2 - x) > 1.0
                    forced |= (t2 == 0) & (x < 0)     # short closed for the $500m floor
                    tw = np.where(chg, t2 / nav, tw)
                    pending = pending | chg
                    decision_epoch += 1
                    reason = "retighten"

            if month_in_book is not None:
                want = np.where(pending, tw * nav, x)
                if self.overlay == "E":
                    want2, hits = self.event_exits(day, want, acted_events)
                    if hits:
                        chg = want2 != want
                        forced |= chg
                        tw = np.where(chg, want2 / nav, tw); pending = pending | chg
                        want = want2
                        reason = reason or "event"
                if self.layer is not None:
                    new = self.layer.review(self, di, day, want, nav)
                    if new is not None:
                        chg = np.abs(new - want) > 1.0
                        forced |= chg
                        tw = np.where(chg, new / nav, tw); pending = pending | chg
                        want = new
                        if chg.any():
                            reason = reason or "risk_layer"

            # ---- 2b. trade triage (optional): which proposed trades are worth
            # paying for. It scales TRADES, sees mandatory names as untouchable,
            # and decides each order once; tw stays the proposal, tw_exec is
            # what gets worked.
            tw_exec = tw
            if self.triage is not None and month_in_book is not None:
                tw_exec = self.triage.apply(self, di, day, x, tw, nav, (hs, sig, adv), forced,
                                            epoch=decision_epoch)

            # ---- 3. trade toward the targets, inside the participation cap
            cost, turnover = 0.0, 0.0
            if month_in_book is not None and pending.any():
                adv_use = np.where(np.isfinite(adv), adv, 1e7)
                want = np.where(pending, tw_exec * nav, x)
                lim = H["max_participation"] * adv_use
                # only names that printed a price today can be traded today
                lim = np.where(np.isfinite(r) & ~gone, lim, 0.0)
                delta = np.clip(want - x, -lim, lim)
                # every day a short is extended is treated as a formation date:
                # no extension in a name below $500m at today's close
                me_now = shares_now * self.P[di + 1]
                extend_short = (delta < 0) & (x + delta < 0) & ~(me_now >= FIN["short_min_me_musd"])
                delta = np.where(extend_short, np.maximum(delta, np.minimum(0.0, -x)), delta)
                # an exit of a name we no longer want, or a target of zero, is
                # still worked at the cap; nothing is forced except by step 4
                done = np.abs(want - (x + delta)) <= 1.0
                pending = pending & ~done
                if np.abs(delta).sum() > 1.0:
                    c = self.trade_cost(delta, (hs, sig, adv_use))
                    cash -= delta.sum() + c
                    cost += c
                    turnover += 0.5 * np.abs(delta).sum() / nav
                    if self.triage is not None:
                        self.triage.record_fills(day, delta, "trade")
                    x = x + delta
                    x[np.abs(x) < 1.0] = 0.0
                    for i in np.where(np.abs(delta) > 1.0)[0]:
                        trades.append((day, int(self.perms[i]), float(delta[i]),
                                       float(delta[i] / adv_use[i]), reason or "working"))
                    nav = cash + x.sum()

            # ---- 4. enforce the mandate on the ACTUAL book, in code -----
            fixed, why = self.enforce(x.copy(), nav, di, tw_exec)
            delta = np.where(np.isfinite(r), fixed - x, 0.0)
            fixed = x + delta
            if self.triage is not None and np.abs(delta).sum() > 1.0:
                self.triage.record_fills(day, delta, "compliance")
            if np.abs(delta).sum() > 1.0:
                adv_use = np.where(np.isfinite(adv), adv, 1e7)
                c = self.trade_cost(delta, (hs, sig, adv_use))
                cash -= delta.sum() + c
                cost += c
                turnover += 0.5 * np.abs(delta).sum() / nav
                for i in np.where(np.abs(delta) > 1.0)[0]:
                    trades.append((day, int(self.perms[i]), float(delta[i]),
                                   float(delta[i] / adv_use[i]), "compliance:" + why))
                x = fixed
                nav = cash + x.sum()
            if why:
                reason = (reason + "+" if reason else "") + why

            if today_leg is not None:
                self.leg_hist.append(today_leg)
            w = x / nav
            rows.append({
                "date": day, "month": m_str, "nav": nav, "ret": nav / nav_prev - 1,
                "ret_pre_cost": (nav + cost) / nav_prev - 1,
                "ret_gross": (nav + cost + fee) / nav_prev - 1,
                "rf": rf, "hurdle": d["hurdle_d"], "sp_ret": d["sp_ret"], "mkt_ex": d["mkt_ex"],
                "gross": np.abs(w).sum(), "net": w.sum(),
                "n_long": int((x > 0).sum()), "n_short": int((x < 0).sum()),
                "max_w": float(np.abs(w).max()) if nP else 0.0,
                "long_ret": long_r, "short_ret": short_r,
                "cost": cost, "borrow": fee, "stub_pnl": stub_pnl,
                "turnover": turnover, "rebalance": reason or "",
            })

        self.daily = pd.DataFrame(rows)
        pr = np.vstack(pos_rows) if pos_rows else np.zeros((0, 5))
        self.pnl = pd.DataFrame(pr, columns=["di", "permno", "x", "r", "pnl"])
        self.pnl["date"] = self.days["date"].values[self.pnl["di"].astype(int)]
        self.pnl["permno"] = self.pnl["permno"].astype(int)
        self.trades = pd.DataFrame(trades, columns=["date", "permno", "delta", "adv_frac", "reason"])
        self.anomalies = pd.DataFrame(anomalies)
        self.form_log = pd.DataFrame(form_log)
        self.targets = pd.concat(targets_log, ignore_index=True) if targets_log else pd.DataFrame()
        self.positions_last = x
        if not quiet:
            print("[%s] %d days, ending NAV $%.3fbn, %.0fs"
                  % (self.label, len(self.daily), nav / 1e9, time.time() - t0))
        return self

    # ---- weekly / daily re-tightening --------------------------------
    def retighten(self, di, x, nav):
        """Bring leg notionals back to beta-matched targets and weights back
        toward the month's target weights, inside a no-trade band. Uses leg
        history through yesterday (leg_hist already holds today; drop it)."""
        tw = self.month_target_w
        held = x != 0
        if not held.any():
            return None
        if True:                              # leg_hist holds yesterday and earlier
            G = self.month_rows
            longs_i = G["pi"].values[tw[G["pi"].values] > 0]
            shorts_i = G["pi"].values[tw[G["pi"].values] < 0]
            bmap = pd.Series(G["beta_use"].values, index=G["pi"].values)
            vol = pd.Series(G["rvol_21d"].values, index=G["pi"].values)
            est_l = np.average(bmap[longs_i], weights=1 / vol[longs_i]) if len(longs_i) else 1.0
            est_s = np.average(bmap[shorts_i], weights=1 / vol[shorts_i]) if len(shorts_i) else 1.0
            bl, bs, _ = self.leg_betas(est_l, est_s)
        if bl <= 0 or bs <= 0:
            bl, bs = 1.0, 1.0
        ln = GROSS_TARGET * bs / (bl + bs)
        sn = GROSS_TARGET - ln
        if abs(ln - sn) > H["net_cap"]:
            ln = (GROSS_TARGET + np.sign(ln - sn) * H["net_cap"]) / 2
            sn = GROSS_TARGET - ln
        # only names still held keep a target (exits stay exited)
        t = np.where(held, tw, 0.0)
        # a short re-sized on a re-tightening date is formed again, so it must
        # clear the $500m floor at yesterday's close or be closed
        G = self.month_rows
        me_prev = G["shares"].values * self.P[di][G["pi"].values]
        below = G["pi"].values[(me_prev < FIN["short_min_me_musd"]) & (t[G["pi"].values] < 0)]
        t[below] = 0.0
        lt, st = t[t > 0].sum(), -t[t < 0].sum()
        t = np.where(t > 0, t * ln / lt if lt else 0, t * sn / st if st else 0) * nav
        band = np.abs(x - t) <= 0.25 * np.abs(t)
        return np.where(band, x, t)

    # ---- E overlay ---------------------------------------------------
    def event_exits(self, day, base, acted):
        """Exit longs with a distress 8-K filed strictly before today."""
        ev = self.events
        recent = ev[(ev["filing_date"] < day) & (ev["filing_date"] >= day - pd.Timedelta(days=7))]
        hits = []
        base = base.copy()
        for _, e in recent.iterrows():
            k = (e["permno"], e["filing_date"])
            i = e["pi"]
            if k in acted or base[i] <= 0:
                continue
            acted.add(k)
            base[i] = 0.0
            hits.append(int(e["permno"]))
        return base, hits

    # ---- hard constraints, in code -----------------------------------
    def enforce(self, base, nav, di, tw=None):
        """The mandate, applied to the actual end-of-day book."""
        why = []
        w = base / nav
        over = np.abs(w) > FIN["max_single_weight"]
        if over.any():
            w[over] = np.sign(w[over]) * FIN["max_single_weight"]
            why.append("cap5")
        n = int((w != 0).sum())
        if n > FIN["max_positions"] and tw is not None:
            # finish the exits we were working, smallest first
            exits = np.where((w != 0) & (tw == 0))[0]
            exits = exits[np.argsort(np.abs(w[exits]))][:n - FIN["max_positions"]]
            w[exits] = 0.0
            why.append("names>500")
        gross = np.abs(w).sum()
        if gross > GROSS_TRIGGER:
            w *= GROSS_RESET / gross
            why.append("gross")
        net = w.sum()
        if abs(net) > NET_TRIGGER:
            L, Sx = w[w > 0].sum(), -w[w < 0].sum()
            tgt = np.sign(net) * (NET_TRIGGER - 0.03)
            if net > 0:
                w[w > 0] *= (Sx + tgt) / L
            else:
                w[w < 0] *= (L - tgt) / Sx
            why.append("net")
        if int((w != 0).sum()) < MIN_NAMES_TRIGGER:
            why.append("names<%d" % MIN_NAMES_TRIGGER)
        return w * nav, "+".join(why)


# ---------------------------------------------------------------- outputs
def save(e, tag=None):
    tag = tag or e.label
    d = F.DATA / "runs" / tag
    d.mkdir(parents=True, exist_ok=True)
    e.daily.to_parquet(d / "daily.parquet", index=False)
    e.pnl.to_parquet(d / "pnl.parquet", index=False)
    e.trades.to_parquet(d / "trades.parquet", index=False)
    e.anomalies.to_parquet(d / "anomalies.parquet", index=False)
    e.targets.to_parquet(d / "targets.parquet", index=False)
    fl = e.form_log.copy()
    fl["measured"] = fl["measured"].astype(str)
    fl.to_parquet(d / "formations.parquet", index=False)
    return d


def quick_stats(daily, label=""):
    a = daily["ret"] - daily["hurdle"]
    ir = np.sqrt(252) * a.mean() / a.std(ddof=1)
    X = np.column_stack([np.ones(len(daily)), daily["mkt_ex"]])
    y = daily["ret"] - daily["rf"]
    beta = np.linalg.lstsq(X, y, rcond=None)[0][1]
    yrs = len(daily) / 252
    cagr = (daily["nav"].iloc[-1] / daily["nav"].iloc[0] * (1 + daily["ret"].iloc[0])) ** (1 / yrs) - 1
    to = daily["turnover"].sum() / yrs
    cost = daily["cost"].sum() / daily["nav"].mean() / yrs
    print("  %-28s IR %+.2f  beta %+.3f  CAGR %+.2f%%  turnover %.0f%%/yr  cost %.2f%%/yr"
          % (label, ir, beta, 100 * cagr, 100 * to, 100 * cost))
    return ir, beta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="design", choices=["design", "test"])
    ap.add_argument("--freq", default="M", choices=["M", "W", "D", "B", "Q"],
                    help="B / Q: form every 2nd / 3rd month (post-hoc, see run register)")
    ap.add_argument("--overlay", default=None, choices=[None, "E"])
    ap.add_argument("--layer", default=None, choices=[None, "rule", "agent"])
    ap.add_argument("--triage", default=None, choices=[None, "none", "rule", "ai"],
                    help="cost-aware trade triage mode (f04_risk_layer.TriageLayer)")
    ap.add_argument("--nav", type=float, default=None, help="starting NAV, US$")
    ap.add_argument("--cost", default="sqrt:0.7", help="sqrt:Y | almgren | flat:BPS")
    ap.add_argument("--borrow", default="model", choices=["model", "flat"])
    ap.add_argument("--sector-neutral", action="store_true",
                    help="POST-HOC: equal long/short dollars per GICS sector")
    a = ap.parse_args()
    lay = None
    if a.layer:
        import f04_risk_layer as RL
        lay = RL.RuleLayer() if a.layer == "rule" else RL.AgentLayer()
    label = None
    if a.nav:
        label = "%s_%s_nav%.0fm" % (a.window, a.freq, a.nav / 1e6)
    if a.cost != "sqrt:0.7" or a.borrow != "model":
        # keep the NAV in the label, or a capacity run overwrites the cost run
        label = "%s_%s%s_cost-%s_borrow-%s" % (a.window, a.freq,
                                               "_nav%.0fm" % (a.nav / 1e6) if a.nav else "",
                                               a.cost.replace(":", ""), a.borrow)
    if label and a.sector_neutral:
        label += "_secneu"
    tri = None
    if a.triage:
        import f04_risk_layer as RL
        tri = RL.TriageLayer(a.triage)
    e = Engine(a.window, a.freq, a.overlay, layer=lay, label=label, start_nav=a.nav,
               cost_mode=a.cost, borrow_mode=a.borrow, triage=tri,
               sector_neutral=a.sector_neutral).run()
    save(e)
    if lay is not None:
        lay.write_log(e.label)
    if tri is not None:
        tri.write_log(e.label)
    quick_stats(e.daily, e.label)

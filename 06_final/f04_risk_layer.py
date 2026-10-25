"""Final stage 4 -- the position-level risk layer: a fixed rule and an agent,
behind the same triggers, so the two can be run side by side (Section 5.3.4).

Design, in the order Section 5.3 lists its requirements:

1. The agent proposes; code enforces. A layer returns a scale in [0, 1.5]
   per flagged name, nothing else. The engine applies it and THEN runs its
   own hard-constraint pass (gross, net, 5% cap, $500m short floor, count),
   so no answer from a model can breach the mandate.
2. Every decision is logged with its inputs: 06_final/output/decisions_<layer>.jsonl
3. Point in time: a trigger at the close of day t is computed from data
   through day t-1 only (returns, vol, filings filed before t). The agent is
   given a BLINDED, NUMERIC context -- no ticker, no name, no filing text,
   no dates beyond "days since formation" -- so it has nothing to recall a
   company's future from. Section 7's re-identification test is
   correspondingly trivial for this layer; it is reported anyway.
4. Counterfactual: RuleLayer and AgentLayer share TRIGGERS exactly. Run the
   engine with each and with no layer at all.
5. Exceptions, not routine: a model call happens only when a trigger fires
   (see count_triggers() for the budget on the 2021-2026 book).
6. Cache: every agent response is stored under the SHA-256 of its prompt in
   06_final/agent_cache/, so a rerun is identical and a judge can read what
   the model said on any date. With no API key the agent replays the cache
   and refuses to run on a miss, rather than silently falling back.

Triggers (all through day t-1):
  VOL   the name's 10-day realised volatility is >= 3x its volatility at
        formation (the Section 5.1 "realised volatility tripled" case)
  LOSS  yesterday's market-adjusted move against the position was worse than
        -5 sigma of its formation volatility (an unexplained loss)
  EVENT a distress 8-K (items 4.01, 4.02, 1.03, 3.01) was filed on a held name
Fixed rule (the counterfactual):
  VOL   scale the position by formation_vol / current_vol, floor 0.33
  LOSS  hold (no action) -- selling after an unexplained gap is a
        behavioural reflex, not a rule with evidence behind it
  EVENT exit if long, hold if short
"""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import fconfig as F

VOL_MULT = 3.0
LOSS_SIGMA = 5.0
VOL_WINDOW = 10
SCALE_MIN, SCALE_MAX = 0.0, 1.5

AGENT_MODEL = os.environ.get("FIAM_AGENT_MODEL", "claude-haiku-4-5")
SYSTEM_PROMPT = """You are the risk analyst for a market-neutral US equity fund.
You review ONE flagged position at a time. You see only numbers about the
position and the book, never the company's identity, and you must not guess it.
Decide how to resize this position for the next period.

Return JSON only: {"scale": <number 0 to 1.5>, "reason": "<one sentence>"}
  scale 1.0 = leave unchanged, 0 = close, 0.5 = halve, 1.5 = add half.
Hard limits are enforced in code after you answer; you do not need to check them.
Prefer small changes unless the evidence is strong. Explain the trade-off you made."""


def _vol(eng, di, i_idx):
    lo = max(1, di - VOL_WINDOW + 1)
    win = eng.R[lo:di + 1, i_idx]            # rows lo..di are days t-VOL..t-1
    with np.errstate(invalid="ignore"):
        return np.nanstd(win, axis=0, ddof=1)


def find_triggers(eng, di, day, base, nav):
    """Return a list of dicts, one per flagged held name. Through t-1 only."""
    held = np.where(base != 0)[0]
    if len(held) == 0 or di < 2:
        return []
    G = eng.month_rows.set_index("pi")
    in_g = [i for i in held if i in G.index]
    if not in_g:
        return []
    in_g = np.array(in_g)
    f_vol = G.loc[in_g, "rvol_21d"].values
    beta = G.loc[in_g, "beta_use"].values
    vol10 = _vol(eng, di, in_g)
    r_y = eng.R[di, in_g]                       # yesterday's return
    m_y = eng.days.loc[di - 1, "mkt_ex"] if di >= 1 else 0.0
    side = np.sign(base[in_g])
    adverse = side * (np.nan_to_num(r_y) - beta * m_y) / f_vol

    out = []
    for k, i in enumerate(in_g):
        kinds = []
        month = eng.days.loc[di, "month"]
        if (np.isfinite(vol10[k]) and vol10[k] >= VOL_MULT * f_vol[k]
                and (int(i), month) not in eng._vol_flagged):
            eng._vol_flagged.add((int(i), month))      # once per name per month
            kinds.append("VOL")
        if np.isfinite(adverse[k]) and adverse[k] <= -LOSS_SIGMA:
            kinds.append("LOSS")
        if kinds:
            out.append({"i": int(i), "kinds": kinds, "side": int(side[k]),
                        "weight": float(base[i] / nav), "formation_vol": float(f_vol[k]),
                        "vol10": float(vol10[k]), "adverse_sigma": float(adverse[k]),
                        "beta": float(beta[k])})
    if eng.events is not None:
        ev = eng.events[(eng.events["filing_date"] < day)
                        & (eng.events["filing_date"] >= day - pd.Timedelta(days=7))]
        held_set = set(held)
        for _, e in ev.iterrows():
            i, key = int(e["pi"]), (int(e["pi"]), e["filing_date"])
            if i not in held_set or key in eng._seen_event:
                continue
            eng._seen_event.add(key)
            row = next((o for o in out if o["i"] == i), None)
            if row is None:
                row = {"i": int(i), "kinds": [], "side": int(np.sign(base[i])),
                       "weight": float(base[i] / nav)}
                out.append(row)
            if "EVENT" not in row["kinds"]:
                row["kinds"].append("EVENT")
    return out


class _Base:
    name = "base"

    def __init__(self):
        self.log = []

    def review(self, eng, di, day, base, nav):
        if not hasattr(eng, "_seen_event"):
            eng._seen_event = set()
            eng._vol_flagged = set()
        eng._last_base = base
        trig = find_triggers(eng, di, day, base, nav)
        if not trig:
            return None
        new = base.copy()
        for t in trig:
            scale, reason = self.decide(eng, di, day, t, nav)
            scale = float(np.clip(scale, SCALE_MIN, SCALE_MAX))
            new[t["i"]] = base[t["i"]] * scale
            self.log.append({"date": str(day.date()), "permno": int(eng.perms[t["i"]]),
                             "layer": self.name, "inputs": t, "scale": scale,
                             "reason": reason})
        return new

    def write_log(self, tag):
        F.OUT.mkdir(parents=True, exist_ok=True)
        p = F.OUT / ("decisions_%s.jsonl" % tag)
        with open(p, "w") as fh:
            for r in self.log:
                fh.write(json.dumps(r, default=float) + "\n")
        return p


class RuleLayer(_Base):
    name = "rule"

    def decide(self, eng, di, day, t, nav):
        scale, why = 1.0, []
        if "VOL" in t["kinds"]:
            s = max(0.33, t["formation_vol"] / t["vol10"])
            scale = min(scale, s)
            why.append("vol x%.1f -> scale %.2f" % (t["vol10"] / t["formation_vol"], s))
        if "LOSS" in t["kinds"]:
            why.append("unexplained loss %.1f sigma -> hold" % t["adverse_sigma"])
        if "EVENT" in t["kinds"]:
            if t["side"] > 0:
                scale = 0.0
                why.append("distress 8-K on a long -> exit")
            else:
                why.append("distress 8-K on a short -> hold")
        return scale, "; ".join(why)


class AgentLayer(_Base):
    """Same triggers; the decision comes from a language model, cached."""
    name = "agent"

    def __init__(self, model=AGENT_MODEL):
        super().__init__()
        self.model = model
        F.AGENT_CACHE.mkdir(parents=True, exist_ok=True)
        self.client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
        self.calls = self.hits = 0

    def context(self, eng, di, t, nav):
        """Blinded, numeric, point-in-time. Nothing here names the company or
        the calendar date."""
        days_since_form = int(di - eng.days.index[
            (eng.days.index <= di) & eng.days["is_formation"]].max())
        recent = eng.R[max(1, di - 4):di + 1, t["i"]]
        return {
            "position": "long" if t["side"] > 0 else "short",
            "weight_pct_nav": round(100 * t["weight"], 3),
            "triggers": t["kinds"],
            "formation_daily_vol_pct": round(100 * t.get("formation_vol", np.nan), 2),
            "vol_last_10d_pct": round(100 * t.get("vol10", np.nan), 2),
            "adverse_move_sigma_yesterday": round(t.get("adverse_sigma", np.nan), 2),
            "beta_estimate": round(t.get("beta", np.nan), 2),
            "returns_last_5d_pct": [round(100 * float(v), 2) for v in np.nan_to_num(recent)],
            "trading_days_since_formation": days_since_form,
            "event_type": "distress 8-K (auditor change, non-reliance, bankruptcy "
                          "or delisting notice)" if "EVENT" in t["kinds"] else None,
            "book": {"gross_pct": round(100 * float(np.abs(eng._last_base).sum() / nav), 1),
                     "net_pct": round(100 * float(eng._last_base.sum() / nav), 1)},
        }

    def decide(self, eng, di, day, t, nav):
        ctx = self.context(eng, di, t, nav)
        prompt = json.dumps(ctx, sort_keys=True)
        key = hashlib.sha256((self.model + SYSTEM_PROMPT + prompt).encode()).hexdigest()
        path = F.AGENT_CACHE / (key + ".json")
        if path.exists():
            self.hits += 1
            rec = json.loads(path.read_text())
        else:
            if self.client is None:
                raise SystemExit("agent cache miss and no ANTHROPIC_API_KEY: set the key "
                                 "to run the agent, or replay a complete cache")
            msg = self.client.messages.create(
                model=self.model, max_tokens=200, temperature=0,
                system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}])
            text = msg.content[0].text
            rec = {"model": self.model, "prompt": ctx, "response": text}
            path.write_text(json.dumps(rec, indent=1))
            self.calls += 1
        try:
            ans = json.loads(rec["response"][rec["response"].find("{"):rec["response"].rfind("}") + 1])
            return float(ans["scale"]), str(ans.get("reason", ""))
        except Exception:
            return 1.0, "unparseable response -> no change"


def count_triggers(eng_cls, window="test"):
    """How many model calls would the agent make? Run the engine with a
    layer that only counts."""
    class Counter(RuleLayer):
        name = "count"

        def decide(self, eng, di, day, t, nav):
            return 1.0, "count only"
    lay = Counter()
    e = eng_cls(window, "M", None, layer=lay).run(quiet=True)
    df = pd.DataFrame(lay.log)
    return df

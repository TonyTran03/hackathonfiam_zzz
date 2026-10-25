"""Final stage 4 -- two optional, separate layers between construction and execution.

  RuleLayer / AgentLayer   position-risk resizing (below): resize a POSITION when
                           something unusual happens to it
  TriageLayer              cost-aware trade triage (end of file): decide which
                           proposed TRADES are worth paying for; modes none /
                           rule / ai; tests in tests_triage.py

Each is passed to the engine on its own (Engine(..., layer=...) or
Engine(..., triage=...)); neither changes the forecast or the cost model.

The position-level risk layer: a fixed rule and an agent,
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

# Which model answers. FIAM_AGENT_PROVIDER picks the backend; every backend
# gets the same system prompt, the same blinded context and the same cache.
#   anthropic  ANTHROPIC_API_KEY             default model claude-haiku-4-5
#   xai        XAI_API_KEY (Grok)            default model grok-3-mini
#   ollama     a local Ollama server, no key default model llama3.1:8b
# The key is read from the environment only: never written to a file, a log
# or the cache, so nothing secret can reach the repository.
AGENT_PROVIDER = os.environ.get("FIAM_AGENT_PROVIDER", "anthropic")
_DEFAULT_MODEL = {"anthropic": "claude-haiku-4-5", "xai": "grok-3-mini", "ollama": "llama3.1:8b"}
AGENT_MODEL = os.environ.get("FIAM_AGENT_MODEL", _DEFAULT_MODEL.get(AGENT_PROVIDER, "claude-haiku-4-5"))
_OPENAI_STYLE = {"xai": ("https://api.x.ai/v1/chat/completions", "XAI_API_KEY"),
                 "ollama": (os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/v1/chat/completions", None)}


def _chat_openai_style(provider, model, system, user):
    """xAI and Ollama both speak the OpenAI chat-completions format; plain
    HTTP, so no extra package is needed."""
    import urllib.request
    url, key_env = _OPENAI_STYLE[provider]
    headers = {"Content-Type": "application/json"}
    if key_env:
        headers["Authorization"] = "Bearer " + os.environ[key_env]
    body = json.dumps({"model": model, "temperature": 0, "max_tokens": 200,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    return out["choices"][0]["message"]["content"]
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

    def __init__(self, model=AGENT_MODEL, provider=AGENT_PROVIDER):
        super().__init__()
        self.model, self.provider = model, provider
        F.AGENT_CACHE.mkdir(parents=True, exist_ok=True)
        self.client = None
        if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
        elif provider == "ollama" or (provider == "xai" and os.environ.get("XAI_API_KEY")):
            self.client = provider
        self.calls = self.hits = 0

    def ask(self, prompt):
        if self.provider == "anthropic":
            msg = self.client.messages.create(
                model=self.model, max_tokens=200, temperature=0,
                system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}])
            return msg.content[0].text
        return _chat_openai_style(self.provider, self.model, SYSTEM_PROMPT, prompt)

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
                raise SystemExit("agent cache miss and no key for provider %r: set "
                                 "ANTHROPIC_API_KEY / XAI_API_KEY, use FIAM_AGENT_PROVIDER=ollama, "
                                 "or replay a complete cache" % self.provider)
            text = self.ask(prompt)
            rec = {"provider": self.provider, "model": self.model, "prompt": ctx, "response": text}
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


def reidentification_test(n=50, model=AGENT_MODEL, seed=0):
    """Section 7: how often can the model name the company from what it is
    shown? Samples cached agent prompts, asks for the ticker, and scores the
    answer against the permno's true ticker. Needs ANTHROPIC_API_KEY.

        python -c "import f04_risk_layer as R; print(R.reidentification_test())"
    """
    import random
    import anthropic
    from common import config as C
    files = sorted(F.AGENT_CACHE.glob("*.json"))
    if not files:
        raise SystemExit("no cached agent prompts yet -- run the agent layer first")
    random.Random(seed).shuffle(files)
    log = [json.loads(l) for l in open(F.OUT / "decisions_test_M_agent.jsonl")]
    by_prompt = {}
    for r in log:
        by_prompt.setdefault(json.dumps(r["inputs"], sort_keys=True, default=float), r["permno"])
    panel = pd.read_parquet(C.MODEL_TABLE, columns=["permno", "ticker"]).dropna()
    tick = panel.groupby("permno")["ticker"].agg(lambda s: set(s))
    client = anthropic.Anthropic()
    rows = []
    for f in files[:n]:
        rec = json.loads(f.read_text())
        q = ("Here is the numeric context a risk analyst saw for one US stock position:\n"
             + json.dumps(rec["prompt"]) + "\nWhich company is this? Answer with a ticker "
             "only, or UNKNOWN.")
        a = client.messages.create(model=model, max_tokens=10, temperature=0,
                                   messages=[{"role": "user", "content": q}]).content[0].text.strip()
        rows.append({"file": f.name, "answer": a})
    df = pd.DataFrame(rows)
    df["unknown"] = df["answer"].str.upper().str.contains("UNKNOWN")
    out = F.OUT / "reidentification_test.csv"
    df.to_csv(out, index=False)
    return {"n": len(df), "share_declined": float(df["unknown"].mean()),
            "note": "answers are matched to true tickers by hand from decisions log; see %s" % out.name}


def smoke_test():
    """One call with a made-up context, to check the key, the network and the
    reply format before a full run:
        FIAM_AGENT_PROVIDER=xai XAI_API_KEY=... python3 -c "import f04_risk_layer as R; R.smoke_test()"
    """
    ctx = {"position": "long", "weight_pct_nav": 0.8, "triggers": ["VOL"],
           "formation_daily_vol_pct": 2.1, "vol_last_10d_pct": 6.9,
           "adverse_move_sigma_yesterday": -1.2, "beta_estimate": 1.1,
           "returns_last_5d_pct": [-3.1, 4.0, -5.2, 2.2, -1.0],
           "trading_days_since_formation": 9, "event_type": None,
           "book": {"gross_pct": 189.0, "net_pct": 7.5}}
    lay = AgentLayer()
    if lay.client is None:
        raise SystemExit("no key for provider %r" % lay.provider)
    text = lay.ask(json.dumps(ctx, sort_keys=True))
    ans = json.loads(text[text.find("{"):text.rfind("}") + 1])
    print("provider %s, model %s -> scale %s: %s" % (lay.provider, lay.model, ans["scale"], ans.get("reason")))
    return ans


# =============================================================================
# Cost-aware trade triage (a second, separate optional mode)
# =============================================================================
#
# The position-risk layer above resizes POSITIONS when something unusual
# happens to them. Trade triage answers a different question, at every
# decision: of the trades the construction step proposes today, which are worth
# paying for? Code handles the routine ones; only ambiguous, potentially
# expensive trades go to review, where a decision is execute, half or skip.
#
# The decision scales the proposed TRADE, never the position:
#     revised_target = current_position + fraction * proposed_trade,  fraction in {1, 0.5, 0}
# so "half" on a +$4m buy into a $2m holding leaves $4m, not $3m or $1m.
#
# Three modes share the eligibility rules, the inputs, the forecast, the cost
# model and the execution path, so they are comparable:
#     none   every proposed trade is executed (identical to running without triage)
#     rule   a fixed rule decides each review-eligible trade
#     ai     a language model decides each review-eligible trade
#
# What triage never touches: compliance trades (the engine's step 4 runs after
# triage and enforces gross, net, the 5% cap, the name count and the $500m
# short floor on the ACTUAL book), delistings, and changes made that day by the
# event overlay or the position-risk layer. Those are "mandatory" and bypass it.
#
# Point in time: triage runs at the close of day t, the same moment the engine
# trades, using only month-end characteristics (forecast rank, beta, ADV,
# spread, volatility -- all dated end of the previous month), the holdings the
# fund actually has, and holding ages. It never reads a return. The calendar
# date is kept OUT of the model's input by default (it is in the log): a date
# plus a sector is a strong hint to a model that remembers the market.
# Blinding names, tickers and dates REDUCES model-memory risk; it does not
# remove it, and the re-identification test should still be reported.

TRIAGE_VERSION = "triage-v1"

TRIAGE_SYSTEM_PROMPT = """You are the execution analyst for a market-neutral US equity fund.
The portfolio-construction step has proposed ONE trade. You decide whether it is
worth its trading cost. You see only numbers -- never the company's identity --
and you must not guess it.

Choose one:
  execute  trade the full proposed amount
  half     trade half of the proposed amount (the position moves halfway to its target)
  skip     do not trade; the position stays where it is

The forecast is a cross-sectional RANK, not an expected return; do not convert
it into one. Weigh how far the name's rank has moved and how long it has been
held against the estimated cost and the time needed to trade it. Hard limits
(gross, net, position size, name count, short-sale floor) are enforced in code
after you answer.

Return JSON only: {"decision": "execute" | "half" | "skip", "reason": "<one sentence>"}"""

FRACTION = {"execute": 1.0, "half": 0.5, "skip": 0.0}


class TriageUnavailable(RuntimeError):
    """The model could not give a valid decision and on_failure='raise'."""


class TriageConfig:
    """Thresholds, set on the 2019-2020 design window and never tuned on 2021-2026.

    They are round numbers read off the DISTRIBUTION of estimated trade costs
    in the design window (non-mandatory orders of the monthly book under the
    pre-registered cost model: quartiles 53 / 88 / 133 bp, 90th percentile
    203 bp), not optimised on any return. Roughly: the cheaper half of trades
    is routine; the rest is reviewed; the fixed rule halves the costliest
    quarter and skips the costliest tenth. A first draft used 20 bp, which
    sent 96% of all orders to review -- no longer triage.

      min_trade_pct_nav     below this the trade is routine (executed)
      routine_cost_bps      at or below this all-in cost the trade is routine
      review_adv_frac       a trade larger than this share of ADV is reviewed
                            even when cheap on paper: 0.10 = more than one day
                            at the engine's participation cap (impact models
                            are least reliable for large orders)
      rule_half_bps         fixed rule: above this cost, trade half
      rule_skip_bps         fixed rule: above this cost, skip -- except a full
                            exit or a flip of side, which is halved instead
      include_date          put the calendar date in the model's input (off)
      on_failure            'raise' (default): stop the run on an unusable model
                            answer; 'execute': trade the full amount and log
                            status 'ai_failed_executed'. A fixed-rule decision
                            is NEVER substituted for a missing model answer.
    """

    def __init__(self, min_trade_pct_nav=0.0002, routine_cost_bps=90.0, review_adv_frac=0.10,
                 rule_half_bps=130.0, rule_skip_bps=200.0, include_date=False, on_failure="raise"):
        assert on_failure in ("raise", "execute")
        self.min_trade_pct_nav = min_trade_pct_nav
        self.routine_cost_bps = routine_cost_bps
        self.review_adv_frac = review_adv_frac
        self.rule_half_bps = rule_half_bps
        self.rule_skip_bps = rule_skip_bps
        self.include_date = include_date
        self.on_failure = on_failure

    def as_dict(self):
        return dict(self.__dict__)


def revised_target(current, proposed_target, fraction):
    """Scale the TRADE, not the position."""
    return current + fraction * (proposed_target - current)


def trade_kind(current, target):
    if current == 0 and target != 0:
        return "entry"
    if target == 0 and current != 0:
        return "exit"
    if np.sign(current) != np.sign(target):
        return "flip"
    return "increase" if abs(target) > abs(current) else "reduce"


def model_call(provider, model, system, user):
    """One chat call to any supported backend. Raises on any transport error."""
    if provider == "anthropic":
        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model=model, max_tokens=200, temperature=0, system=system,
            messages=[{"role": "user", "content": user}])
        return msg.content[0].text
    if provider in _OPENAI_STYLE:
        return _chat_openai_style(provider, model, system, user)
    raise ValueError("unknown provider %r" % provider)


def parse_triage(text):
    """Validate a model answer. Returns (decision, reason) or raises ValueError."""
    if not isinstance(text, str) or "{" not in text:
        raise ValueError("no JSON object in the answer")
    obj = json.loads(text[text.find("{"):text.rfind("}") + 1])
    dec = str(obj.get("decision", "")).strip().lower()
    if dec not in FRACTION:
        raise ValueError("decision %r is not execute / half / skip" % dec)
    reason = str(obj.get("reason", "")).strip()
    if not reason:
        raise ValueError("no reason given")
    return dec, reason[:400]


class TriageLayer:
    """Cost-aware trade triage. Plug into the engine with Engine(..., triage=TriageLayer('rule')).

    The engine calls, at each close:
        tw_exec = triage.apply(eng, di, day, x, tw_prop, nav, cost_inputs, mandatory)
    and after each execution step:
        triage.record_fills(day, delta, kind)    # kind 'trade' or 'compliance'

    Pending orders: a decision is taken ONCE per order, an order being one
    proposed target for one name. While the engine works it over several days
    (participation cap), later calls see the same proposal and reuse the
    approved target, so a half is never halved again and a skip is never
    reversed. A new proposal (next formation, a re-tightening) is a new order.
    """

    def __init__(self, mode="rule", config=None, provider=None, model=None, backend=None,
                 cache_dir=None):
        assert mode in ("none", "rule", "ai")
        self.mode = mode
        self.name = "triage-" + mode
        self.cfg = config or TriageConfig()
        self.provider = provider or AGENT_PROVIDER
        self.model = model or AGENT_MODEL
        self.backend = backend or model_call          # injectable for tests
        self.cache_dir = Path(cache_dir) if cache_dir else F.AGENT_CACHE / "triage"
        self.reviewed_prop = None      # proposal (weight) last decided, per name
        self.approved = None           # approved target (weight), per name
        self.order_id = None
        self.entry_di = None
        self.prev_rank = {}
        self.cur_rank = {}
        self.rank_month = None
        self.open_orders = {}          # name index -> log row of its live order
        self.log = []
        self.calls = self.cache_hits = 0

    # ---- state ---------------------------------------------------------
    def _init(self, n):
        self.reviewed_prop = np.full(n, np.nan)
        self.approved = np.zeros(n)
        self.order_id = np.full(n, -1, dtype=np.int64)
        self.entry_di = np.full(n, -1, dtype=np.int64)
        self._next_order = 0

    def _update_ranks(self, eng, month):
        if month == self.rank_month:
            return
        G = eng.month_rows
        pct = G["score"].rank(pct=True).values
        self.prev_rank = self.cur_rank
        self.cur_rank = dict(zip(G["pi"].values, pct))
        self.rank_month = month

    # ---- context -------------------------------------------------------
    def context(self, eng, di, day, i, x, target, nav, est_bps, adv_i):
        """Blinded, numeric, point in time. Exactly what a review sees."""
        G = eng.month_rows.set_index("pi")
        row = G.loc[i] if i in G.index else None
        trade = target - x[i]
        w = x / nav
        sector = row["sector"] if row is not None else None
        sec_net = None
        if sector is not None:
            in_sec = G.index[G["sector"] == sector]
            sec_net = float(w[np.asarray(in_sec, dtype=int)].sum())
        live = getattr(eng, "form_log_live", None)
        fl = live[-1] if live else {}
        beta_i = float(row["beta_use"]) if row is not None else None
        ctx = {
            "trade": {"kind": trade_kind(x[i], target), "direction": "buy" if trade > 0 else "sell",
                      "current_weight_pct": round(100 * x[i] / nav, 3),
                      "target_weight_pct": round(100 * target / nav, 3),
                      "trade_pct_nav": round(100 * trade / nav, 3),
                      "trade_usd_m": round(trade / 1e6, 2)},
            "forecast": {"rank_pct_now": _r(self.cur_rank.get(i)),
                         "rank_pct_last_formation": _r(self.prev_rank.get(i)),
                         "note": "cross-sectional rank of the neutralised forecast, 1 = best; not a return"},
            "holding_age_trading_days": int(di - self.entry_di[i]) if self.entry_di[i] >= 0 and x[i] != 0 else 0,
            "cost": {"estimated_all_in_bps": round(est_bps, 1),
                     "trade_over_adv_pct": round(100 * abs(trade) / adv_i, 2) if adv_i > 0 else None,
                     "days_to_execute_at_10pct_adv": round(abs(trade) / (0.10 * adv_i), 1) if adv_i > 0 else None},
            "book": {"gross_pct": round(100 * float(np.abs(w).sum()), 1),
                     "net_pct": round(100 * float(w.sum()), 1),
                     "net_after_trade_pct": round(100 * float(w.sum() + trade / nav), 1),
                     "name_beta": _r(beta_i, 2),
                     "beta_exposure_change_pct": _r(100 * beta_i * trade / nav, 3) if beta_i is not None else None,
                     "leg_betas_used": [_r(fl.get("used_beta_long"), 2), _r(fl.get("used_beta_short"), 2)],
                     "sector_net_weight_pct": _r(100 * sec_net, 2) if sec_net is not None else None},
        }
        if self.cfg.include_date:
            ctx["date"] = str(pd.Timestamp(day).date())
        return ctx

    # ---- decisions -----------------------------------------------------
    def classify(self, trade, nav, est_bps, adv_i):
        if abs(trade) < self.cfg.min_trade_pct_nav * nav:
            return "routine"
        big = adv_i > 0 and abs(trade) / adv_i > self.cfg.review_adv_frac
        if est_bps <= self.cfg.routine_cost_bps and not big:
            return "routine"
        return "review"

    def rule_decision(self, ctx):
        bps = ctx["cost"]["estimated_all_in_bps"]
        kind = ctx["trade"]["kind"]
        if bps > self.cfg.rule_skip_bps:
            if kind in ("exit", "flip"):
                return "half", "cost %.0f bp above %.0f; exit or flip halved, not skipped" % (bps, self.cfg.rule_skip_bps)
            return "skip", "cost %.0f bp above %.0f" % (bps, self.cfg.rule_skip_bps)
        if bps > self.cfg.rule_half_bps:
            return "half", "cost %.0f bp above %.0f" % (bps, self.cfg.rule_half_bps)
        return "execute", "cost %.0f bp at or below %.0f" % (bps, self.cfg.rule_half_bps)

    def ai_decision(self, ctx):
        """Returns (decision, reason, status, raw, cache_key). Never falls back to the rule."""
        user = json.dumps(ctx, sort_keys=True)
        key = hashlib.sha256(json.dumps(
            [TRIAGE_VERSION, self.provider, self.model, TRIAGE_SYSTEM_PROMPT, user]).encode()).hexdigest()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / (key + ".json")
        raw = None
        if path.exists():
            rec = json.loads(path.read_text())
            raw = rec["response"]
            self.cache_hits += 1
        else:
            try:
                raw = self.backend(self.provider, self.model, TRIAGE_SYSTEM_PROMPT, user)
                self.calls += 1
            except Exception as exc:              # transport, auth, quota
                return self._failed("model call failed: %s" % type(exc).__name__, None, key)
        try:
            dec, reason = parse_triage(raw)
        except Exception as exc:
            return self._failed("invalid answer: %s" % exc, raw, key)
        if not path.exists():                     # cache only answers that validated
            path.write_text(json.dumps({"version": TRIAGE_VERSION, "provider": self.provider,
                                        "model": self.model, "system": TRIAGE_SYSTEM_PROMPT,
                                        "prompt": ctx, "response": raw}, indent=1))
        return dec, reason, "ok", raw, key

    def _failed(self, why, raw, key):
        if self.cfg.on_failure == "raise":
            raise TriageUnavailable(why)
        return "execute", why, "ai_failed_executed", raw, key

    # ---- the engine hook -----------------------------------------------
    def apply(self, eng, di, day, x, tw_prop, nav, cost_inputs, mandatory, epoch=0):
        """Return tw_exec: the targets the engine should work toward today.

        epoch: a counter the engine raises at each formation / re-tightening.
        A new epoch makes every live proposal a new order (new information
        arrived), even if its value repeats, e.g. 'exit' proposed two months
        running. Within an epoch, a repeated proposal is the same order."""
        n = len(x)
        if self.reviewed_prop is None:
            self._init(n)
            self.epoch_of = np.full(n, -1, dtype=np.int64)
        # holding ages, from the actual book
        opened = (x != 0) & (self.entry_di < 0)
        self.entry_di[opened] = di
        self.entry_di[x == 0] = -1
        self._update_ranks(eng, str(eng.days.loc[di, "month"]))

        hs, sig, adv = cost_inputs
        changed = ~np.isclose(tw_prop, self.reviewed_prop, rtol=0, atol=1e-12)
        live = (tw_prop != 0) | (x != 0)
        changed |= live & (self.epoch_of != epoch)
        for i in np.where(changed)[0]:
            self.epoch_of[i] = epoch
            target = tw_prop[i] * nav
            trade = target - x[i]
            self._next_order += 1
            self.order_id[i] = self._next_order
            self.reviewed_prop[i] = tw_prop[i]
            self.open_orders.pop(i, None)         # fills from now on belong to the new order
            if abs(trade) <= 1.0:
                self.approved[i] = tw_prop[i]
                continue
            adv_i = float(adv[i]) if np.isfinite(adv[i]) else 1e7
            one = np.zeros(n)
            one[i] = trade
            est_bps = 1e4 * eng.trade_cost(one, (hs, sig, np.where(np.isfinite(adv), adv, 1e7))) / abs(trade)
            if mandatory[i]:
                cls = "mandatory"
            else:
                cls = self.classify(trade, nav, est_bps, adv_i)
            ctx = raw = key = None
            status = "ok"
            if cls != "review" or self.mode == "none":
                dec, reason = "execute", ("%s trade" % cls if cls != "review" else "mode none: no triage")
            else:
                ctx = self.context(eng, di, day, i, x, target, nav, est_bps, adv_i)
                if self.mode == "rule":
                    dec, reason = self.rule_decision(ctx)
                else:
                    dec, reason, status, raw, key = self.ai_decision(ctx)
            f = FRACTION[dec]
            self.approved[i] = revised_target(x[i], target, f) / nav
            row = {"date": str(pd.Timestamp(day).date()), "order_id": int(self.order_id[i]),
                   "permno": int(eng.perms[i]), "mode": self.mode, "class": cls,
                   "proposed_trade_usd": float(trade), "current_usd": float(x[i]),
                   "proposed_target_usd": float(target), "est_cost_bps": float(est_bps),
                   "decision": dec, "fraction": f, "approved_target_usd": float(self.approved[i] * nav),
                   "reason": reason, "status": status, "model_input": ctx, "model_response": raw,
                   "cache_key": key, "provider": self.provider if self.mode == "ai" else None,
                   "model": self.model if self.mode == "ai" else None,
                   "executed_usd": 0.0, "compliance_override_usd": 0.0}
            self.log.append(row)
            self.open_orders[i] = row
        return self.approved.copy()

    def record_fills(self, day, delta, kind):
        """Attach what actually traded to the open order of each name."""
        for i in np.where(np.abs(delta) > 1.0)[0]:
            row = self.open_orders.get(i)
            if row is None:
                continue
            key = "compliance_override_usd" if kind == "compliance" else "executed_usd"
            row[key] += float(delta[i])

    def write_log(self, tag):
        F.OUT.mkdir(parents=True, exist_ok=True)
        p = F.OUT / ("triage_%s.jsonl" % tag)
        with open(p, "w") as fh:
            fh.write(json.dumps({"_header": True, "version": TRIAGE_VERSION, "mode": self.mode,
                                 "config": self.cfg.as_dict(), "provider": self.provider,
                                 "model": self.model, "system_prompt": TRIAGE_SYSTEM_PROMPT}) + "\n")
            for r in self.log:
                fh.write(json.dumps(r, default=float) + "\n")
        return p


def _r(v, nd=3):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), nd)

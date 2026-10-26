"""Focused tests for the cost-aware trade triage (f04_risk_layer.TriageLayer).

    python3 06_final/tests_triage.py           # unit tests only, no data needed
    python3 06_final/tests_triage.py --engine  # + wiring checks on the design window

No test makes a paid model call: the AI mode is driven by a fake backend.
The --engine checks compare runs for EQUALITY and inspect logs; they print no
performance figure and are not strategy experiments.
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f04_risk_layer as R  # noqa: E402

PASSED = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    PASSED.append(msg)
    print("PASS  " + msg)


class StubEngine:
    """The few engine attributes the triage reads. Its R matrix is all NaN
    after the decision row, so any use of a future return would surface as a
    NaN in the context."""

    def __init__(self, n=4, cost_bps=120.0):
        self.perms = np.arange(10001, 10001 + n)
        self.days = pd.DataFrame({"date": pd.date_range("2021-01-04", periods=5, freq="B"),
                                  "month": ["2021-01"] * 5})
        self.month_rows = pd.DataFrame({"pi": np.arange(n), "score": np.linspace(1, -1, n),
                                        "sector": ["35", "35", "45", "45"][:n],
                                        "beta_use": np.ones(n)})
        self.form_log_live = [{"used_beta_long": 1.0, "used_beta_short": 1.1}]
        self.R = np.full((6, n), np.nan)
        self.cost_bps = cost_bps

    def trade_cost(self, delta, g_cost):
        return float(np.abs(delta).sum()) * self.cost_bps / 1e4


def cost_inputs(n):
    return (np.full(n, 0.001), np.full(n, 0.02), np.full(n, 1e8))


def fake_backend(answer, counter):
    def call(provider, model, system, user):
        counter.append(json.loads(user))
        if isinstance(answer, Exception):
            raise answer
        return answer
    return call


def test_trade_not_position():
    check(R.revised_target(100.0, 300.0, 0.5) == 200.0, "half scales the trade: 100 -> 300 at 0.5 gives 200")
    check(R.revised_target(100.0, -200.0, 0.5) == -50.0, "half of a flip stops halfway: 100 -> -200 gives -50")
    check(R.revised_target(100.0, 0.0, 0.0) == 100.0, "skip leaves the position where it is")
    eng, nav = StubEngine(), 1e9
    x = np.array([2e6, 0.0, -3e6, 0.0])
    tw = np.array([6e6, 0.0, -3e6, 0.0]) / nav
    t = R.TriageLayer("rule", config=R.TriageConfig(routine_cost_bps=20, rule_half_bps=100, rule_skip_bps=200),
                      cache_dir=tempfile.mkdtemp())
    out = t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(abs(out[0] * nav - 4e6) < 1, "rule 'half' on +$4m into $2m approves $4m, not $3m")


def test_pending_orders():
    eng, nav = StubEngine(), 1e9
    calls = []
    t = R.TriageLayer("ai", backend=fake_backend('{"decision":"half","reason":"costly"}', calls),
                      cache_dir=tempfile.mkdtemp())
    x = np.array([0.0, 0.0, 0.0, 0.0])
    tw = np.array([5e6, 0.0, 0.0, 0.0]) / nav
    a1 = t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 1 and abs(a1[0] * nav - 2.5e6) < 1, "first review halves a $5m entry to $2.5m")
    x2 = x.copy(); x2[0] = 1e6                         # partly filled at the participation cap
    a2 = t.apply(eng, 2, eng.days.loc[2, "date"], x2, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 1 and abs(a2[0] * nav - 2.5e6) < 1,
          "same proposal next day: no second review, approved target kept (not halved again)")
    t.apply(eng, 2, eng.days.loc[2, "date"], x2, tw, nav, cost_inputs(4), np.zeros(4, bool), epoch=1)
    check(len(calls) == 2, "a new formation epoch re-reviews the remaining trade once")
    tw3 = tw.copy(); tw3[0] = 4e6 / nav                # a new proposal = a new order
    t.apply(eng, 3, eng.days.loc[3, "date"], x2, tw3, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 3, "a changed proposal is a new order and is reviewed once")
    ids = [r["order_id"] for r in t.log]
    check(len(set(ids)) == len(ids), "each logged decision carries its own order id")
    t2 = R.TriageLayer("ai", backend=fake_backend('{"decision":"skip","reason":"no"}', []),
                       cache_dir=tempfile.mkdtemp())
    a = t2.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    b = t2.apply(eng, 2, eng.days.loc[2, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(a[0] == 0 and b[0] == 0, "a skip is not reversed on the following day")


def test_timing_and_blinding():
    eng, nav = StubEngine(), 1e9
    calls = []
    t = R.TriageLayer("ai", backend=fake_backend('{"decision":"execute","reason":"ok"}', calls),
                      cache_dir=tempfile.mkdtemp())
    x = np.zeros(4)
    tw = np.array([5e6, 0, 0, 0]) / nav
    t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    ctx = calls[0]
    flat = json.dumps(ctx)
    check("NaN" not in flat, "context reads no return (future rows are NaN and none appear)")
    check(str(eng.perms[0]) not in flat and "2021" not in flat,
          "context carries no permno and, by default, no calendar date")
    check(t.log[0]["date"] == "2021-01-05" and t.log[0]["permno"] == int(eng.perms[0]),
          "the LOG keeps the date and the permno for audit")
    t_d = R.TriageLayer("ai", config=R.TriageConfig(include_date=True),
                        backend=fake_backend('{"decision":"execute","reason":"ok"}', calls),
                        cache_dir=tempfile.mkdtemp())
    t_d.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(calls[-1].get("date") == "2021-01-05", "include_date=True puts the decision date (not a later one) in the input")
    check("expected_return" not in flat and "rank_pct_now" in flat,
          "the forecast is passed as a rank, never as an expected return")


def test_failure_handling():
    eng, nav = StubEngine(), 1e9
    x, tw = np.zeros(4), np.array([5e6, 0, 0, 0]) / nav
    for answer, label in [(RuntimeError("timeout"), "transport error"),
                          ("I think you should buy", "no JSON"),
                          ('{"decision":"0.3","reason":"x"}', "invalid decision"),
                          ('{"decision":"half"}', "missing reason")]:
        t = R.TriageLayer("ai", backend=fake_backend(answer, []), cache_dir=tempfile.mkdtemp())
        try:
            t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
            raised = False
        except R.TriageUnavailable:
            raised = True
        check(raised, "on_failure='raise' stops the run on %s" % label)
    cache = tempfile.mkdtemp()
    t = R.TriageLayer("ai", config=R.TriageConfig(on_failure="execute"),
                      backend=fake_backend("garbage", []), cache_dir=cache)
    out = t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    row = t.log[0]
    check(row["status"] == "ai_failed_executed" and abs(out[0] * nav - 5e6) < 1,
          "on_failure='execute' trades the full amount and logs the failure")
    check(row["decision"] == "execute" and "rule" not in row["reason"],
          "a failed AI answer is never replaced by the fixed rule")
    check(not list(Path(cache).glob("*.json")), "an invalid answer is not cached")


def test_reply_and_transport_robustness():
    dec, reason = R.parse_triage('{"decision":"half","reason":"costly"} Note: I considered the rank.')
    check(dec == "half" and reason == "costly", "text after the JSON answer is ignored, not fatal")
    dec, _ = R.parse_triage('Answer: {"decision":"skip","reason":"r"}\n{"decision":"execute","reason":"x"}')
    check(dec == "skip", "with two objects, the first complete one is the answer")
    import io
    import urllib.error
    import urllib.request
    calls, waits = [], []
    real = urllib.request.urlopen

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "at capacity", {}, None)
        return Resp(json.dumps({"choices": [{"message": {"content": '{"decision":"execute","reason":"ok"}'}}]}).encode())

    urllib.request.urlopen = fake
    try:
        import os
        os.environ.setdefault("XAI_API_KEY", "test-not-a-key")
        out = R._chat_openai_style("xai", "m", "s", "u", waits=(1, 2, 3), sleep=waits.append)
    finally:
        urllib.request.urlopen = real
    check(len(calls) == 3 and waits == [1, 2] and "execute" in out,
          "a 429 'at capacity' is retried with growing waits, then succeeds")

    def denied(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, None)

    urllib.request.urlopen = denied
    try:
        R._chat_openai_style("xai", "m", "s", "u", waits=(1, 2), sleep=lambda s: None)
        failed_fast = False
    except urllib.error.HTTPError as exc:
        failed_fast = exc.code == 401
    finally:
        urllib.request.urlopen = real
    check(failed_fast, "a 401 is not retried: a wrong key fails at once")


def test_cache():
    eng, nav = StubEngine(), 1e9
    calls, cache = [], tempfile.mkdtemp()
    x, tw = np.zeros(4), np.array([5e6, 0, 0, 0]) / nav
    for _ in range(2):
        t = R.TriageLayer("ai", backend=fake_backend('{"decision":"half","reason":"r"}', calls),
                          cache_dir=cache)
        t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 1, "identical input is answered from the cache the second time")
    rec = json.loads(next(Path(cache).glob("*.json")).read_text())
    check(rec["version"] == R.TRIAGE_VERSION and rec["model"] and "prompt" in rec,
          "cache record holds version, model, prompt and raw response")
    t3 = R.TriageLayer("ai", model="another-model",
                       backend=fake_backend('{"decision":"half","reason":"r"}', calls), cache_dir=cache)
    t3.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 2, "a different model is a different cache key")


def test_routine_and_mandatory():
    eng, nav = StubEngine(cost_bps=10.0), 1e9
    calls = []
    t = R.TriageLayer("ai", backend=fake_backend('{"decision":"skip","reason":"r"}', calls),
                      cache_dir=tempfile.mkdtemp())
    x, tw = np.zeros(4), np.array([1e6, 0, 0, 0]) / nav
    t.apply(eng, 1, eng.days.loc[1, "date"], x, tw, nav, cost_inputs(4), np.zeros(4, bool))
    check(len(calls) == 0 and t.log[0]["class"] == "routine", "a cheap, small trade is routine: no review")
    eng2 = StubEngine(cost_bps=90.0)
    t2 = R.TriageLayer("ai", backend=fake_backend('{"decision":"skip","reason":"r"}', calls),
                       cache_dir=tempfile.mkdtemp())
    mand = np.array([True, False, False, False])
    out = t2.apply(eng2, 1, eng2.days.loc[1, "date"], np.array([3e6, 0, 0, 0]),
                   np.zeros(4), nav, cost_inputs(4), mand)
    check(len(calls) == 0 and out[0] == 0 and t2.log[0]["class"] == "mandatory",
          "a mandatory trade bypasses review and executes in full")
    t2.record_fills(None, np.array([-1e6, 0, 0, 0]), "trade")
    t2.record_fills(None, np.array([-2e6, 0, 0, 0]), "compliance")
    check(t2.log[0]["executed_usd"] == -1e6 and t2.log[0]["compliance_override_usd"] == -2e6,
          "fills and compliance overrides are logged against the order")


def test_engine_wiring():
    """Needs 06_final/data/ built. Equality and log checks only."""
    import f03_engine as E
    base = E.Engine("design", "M").run(quiet=True)
    none = E.Engine("design", "M", triage=R.TriageLayer("none", cache_dir=tempfile.mkdtemp())).run(quiet=True)
    check(np.allclose(base.daily["nav"].values, none.daily["nav"].values, rtol=0, atol=1e-3),
          "mode 'none' reproduces the engine without triage exactly (design window NAV path)")
    calls = []
    ai = R.TriageLayer("ai", backend=fake_backend('{"decision":"half","reason":"r"}', calls),
                       cache_dir=tempfile.mkdtemp())
    e = E.Engine("design", "M", triage=ai).run(quiet=True)
    log = pd.DataFrame(ai.log)
    rev = log[log["class"] == "review"]
    check(len(calls) == len(rev) > 0, "every review made exactly one model call (%d)" % len(calls))
    check(rev.groupby("order_id").size().max() == 1, "no order was reviewed twice")
    # a target is a WEIGHT, so a multi-day order tracks NAV and price moves;
    # allow 25% drift, and require the typical order to land on its half
    ratio = rev["executed_usd"] / (0.5 * rev["proposed_trade_usd"])
    check((ratio <= 1.25).mean() >= 0.99 and abs(ratio.median() - 1) < 0.02,
          "reviewed 'half' orders execute half their trade (median %.3f, %.1f%% within drift)"
          % (ratio.median(), 100 * (ratio <= 1.25).mean()))
    d = e.daily
    check((d["gross"] <= 2.0 + 1e-9).all() and (d["net"].abs() <= 0.5 + 1e-9).all()
          and (d["max_w"] <= 0.05 + 1e-9).all(), "mandate holds at every close with AI triage")
    n = d["n_long"] + d["n_short"]
    check((n.iloc[1:] <= 500).all(), "name count never exceeds 500 with AI triage")


if __name__ == "__main__":
    for f in [test_trade_not_position, test_pending_orders, test_timing_and_blinding,
              test_failure_handling, test_reply_and_transport_robustness, test_cache,
              test_routine_and_mandatory]:
        f()
    if "--engine" in sys.argv:
        test_engine_wiring()
    print("\n%d checks passed" % len(PASSED))

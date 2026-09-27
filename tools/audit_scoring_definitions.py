"""Read-only audit of committed submission CSVs; Python standard library only.

Run from any directory. Prints JSON; never rewrites official results.
Net figures reproduce the CURRENT deck-pack target-weight cost approximation,
not the drift-adjusted experiment or an approved final accounting convention.
"""
import csv
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    with (ROOT / path).open(newline='') as f:
        return list(csv.DictReader(f))

def metrics(returns, hurdle):
    active = [r-b for r, b in zip(returns, hurdle)]
    wealth = peak = 1.0
    dd = 0.0
    for r in returns:
        wealth *= 1+r
        peak = max(peak, wealth)
        dd = min(dd, wealth/peak-1)
    return dict(ir=math.sqrt(12)*statistics.mean(active)/statistics.stdev(active),
                cagr=wealth**(12/len(returns))-1, max_drawdown_from_initial_nav=dd)

def audit():
    rp = '05_submission/portfolio_returns.csv'
    hp = '05_submission/holdings.csv'
    rows = read(rp)
    months = [r['target_month'] for r in rows]
    expected = [f'{y}-{m:02}' for y in range(2021, 2027)
                for m in range(1, 13) if (y, m) <= (2026, 8)]
    assert months == expected, 'Returns must cover exactly 68 ordered months'
    books = {}
    for r in read(hp):
        month, stock, weight = r['DATE'][:7], r['PERMNO'], float(r['WEIGHT'])
        assert math.isfinite(weight) and weight != 0
        book = books.setdefault(month, {})
        assert stock not in book, 'Duplicate stock-month'
        book[stock] = weight
        assert r['TICKER'].strip() and r['COMPANY_NAME'].strip(), 'Missing label'
    assert set(books) == set(months), 'Holdings/returns month mismatch'
    hurdle = [float(r['hurdle']) for r in rows]
    total = [float(r['total']) for r in rows]
    assert all(math.isfinite(float(r[k])) for r in rows for k in
               ['total', 'hurdle', 'active', 'spread', 'cash_monthly', 'long_leg', 'short_leg'])
    cash_source = {r['observation_date'][:7]: float(r['TB3MS'])/1200
                   for r in read('01_data/raw/external/TB3MS.csv') if r['TB3MS'] not in ('', '.')}
    for r in rows:
        cash = float(r['cash_monthly'])
        assert abs(cash-cash_source[r['target_month']]) < 1e-10
        assert abs(float(r['hurdle'])-cash-.04/12) < 1e-10
        assert abs(float(r['total'])-cash-float(r['spread'])) < 1e-10
        assert abs(float(r['active'])-float(r['total'])+float(r['hurdle'])) < 1e-10
        assert abs(float(r['spread'])-float(r['long_leg'])-float(r['short_leg'])) < 1e-10
    traded, counts, grosses, nets = [], [], [], []
    previous = None
    for month in months:
        book = books[month]
        counts.append(len(book)); grosses.append(sum(abs(w) for w in book.values()))
        nets.append(sum(book.values()))
        assert 100 <= len(book) <= 500
        assert grosses[-1] <= 2+1e-8 and abs(nets[-1]) <= .5+1e-8
        assert min(book.values()) < 0 < max(book.values())
        traded.append(0.0 if previous is None else sum(
            abs(book.get(p, 0)-previous.get(p, 0)) for p in book.keys() | previous.keys()))
        previous = book
    net20 = [r-.002*t for r, t in zip(total, traded)]
    entry20 = net20.copy(); entry20[0] -= .002*grosses[0]
    # Compare unrounded recomputation against the committed rounded deck figures.
    deck = {(r['section'], r['metric']): r for r in read('05_submission/deck_pack.csv')}
    gross_metrics = metrics(total, hurdle)
    net_metrics = metrics(net20, hurdle)
    assert abs(gross_metrics['ir']-float(deck['risk', 'INFORMATION RATIO vs cash+4%']['value'])) <= .0051
    assert abs(net_metrics['ir']-float(deck['costs', 'IR at 20 bps per trade']['value'])) <= .0051
    return dict(
        audited_checkout=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        input_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                      [rp, hp, '05_submission/deck_pack.csv']},
        checks='PASS: dates, uniqueness, finite returns, labels, core exposure limits, cash source, return identities, rounded deck IR',
        limits='Does not verify raw return truth, leakage, borrowability, beta neutrality, or final strategy adoption.',
        months=len(months), positions=sum(counts), positions_per_month=[min(counts), max(counts)],
        gross_range=[min(grosses), max(grosses)], net_range=[min(nets), max(nets)],
        gross_current_accounting=gross_metrics,
        net20_current_deck_approximation=net_metrics,
        net20_same_approximation_including_entry=metrics(entry20, hurdle),
        initial_entry_cost_at_20bps=.002*grosses[0],
        mean_target_weight_turnover_excluding_entry=statistics.mean(
            t/(2*g) for t,g in zip(traded[1:], grosses[1:])))

if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, allow_nan=False))

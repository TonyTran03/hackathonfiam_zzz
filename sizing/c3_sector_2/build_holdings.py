"""c3_sector_2 + SPX hedge + 10% vol target, full costs. Rule: sizing/VOL_TARGET_RULE.md"""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

TARGET_VOL, K_LO, K_HI = 0.10, 0.25, 1.00
BETA_WIN, VOL_WIN, MIN_OBS = 24, 12, 12
TRADE_BPS, BORROW_ANN = 0.0065, 0.0152      # 65bp per $ traded; 152bp on short gross

PANEL = 'data/chars_final_with_names.parquet'
runs = [(len(pd.read_csv(f)), Path(f).parent) for f in
        glob.glob('sizing/c3_sector_2/outputs/*/monthly_returns.csv')]
n_months, RUN = max(runs)
if n_months != 68:
    raise ValueError(f'expected a 68-month run, best available is {n_months}')
print(f'using {RUN} ({n_months} months)')
h = pd.read_parquet(RUN / 'holdings.parquet')
m = pd.read_csv(RUN / 'monthly_returns.csv')
m = m.sort_values('target_month').reset_index(drop=True)

sp = pd.read_csv('data/external/SP500_fred.csv', parse_dates=['observation_date'])
sp['SP500'] = pd.to_numeric(sp.SP500, errors='coerce')
lv = sp.set_index('observation_date').SP500.resample('ME').last().dropna()
mk = lv.pct_change(); mk.index = mk.index.to_period('M').astype(str)
m['spx'] = m.target_month.map(mk)

# short-leg gross per month, for the borrow charge
sl = h.assign(s=h.weight.clip(upper=0).abs()).groupby('target_month').s.sum()
m['short_gross'] = m.target_month.map(sl)

# ---- unscaled, FULLY costed -------------------------------------------------
m['cost_full'] = m.turnover * TRADE_BPS + m.short_gross * BORROW_ANN / 12
m['r_full'] = m.total_gross - m.cost_full                 # includes cash on unused capital
m['x'] = m.r_full - m.cash                                # excess over cash
m['mx'] = m.spx - m.cash

# ---- SPX hedge, past data only ---------------------------------------------
hedge = np.zeros(len(m))
for t in range(len(m)):
    p = m.iloc[:t].dropna(subset=['mx', 'x']).tail(BETA_WIN)
    hedge[t] = np.polyfit(p.mx, p.x, 1)[0] if len(p) >= MIN_OBS else 0.0
m['h'] = hedge
m['x_hedged'] = m.x - m.h * m.mx.fillna(0)

# ---- vol target on the unscaled hedged series, past data only ---------------
k = np.ones(len(m))
for t in range(len(m)):
    p = m.x_hedged.iloc[:t].tail(VOL_WIN)
    if len(p) >= MIN_OBS:
        s = p.std(ddof=1) * np.sqrt(12)
        k[t] = float(np.clip(TARGET_VOL / s, K_LO, K_HI)) if s > 0 else 1.0
m['k'] = k

# ---- rebuild turnover on the SCALED weights, then re-cost -------------------
W = h.pivot_table(index='target_month', columns='permno', values='weight', aggfunc='sum').fillna(0)
W = W.reindex(m.target_month).fillna(0)
Ws = W.mul(m.set_index('target_month').k.reindex(W.index), axis=0)
traded = Ws.diff().abs().sum(axis=1)
traded.iloc[0] = Ws.iloc[0].abs().sum()
m['traded_s'] = traded.to_numpy()
m['cost_s'] = m.traded_s * TRADE_BPS + m.short_gross * m.k * BORROW_ANN / 12
# scaled excess return, hedge included, then costs charged on the scaled book
m['x_s'] = m.k * (m.total_gross - m.cash - m.h * m.mx.fillna(0)) - m.cost_s
m['ret'] = m.cash + m.x_s
m['nav'] = 1e9 * (1 + m.ret).cumprod()
m['nav_open'] = m.nav.shift(1).fillna(1e9)

ir = lambda a: a.mean() / a.std(ddof=1) * np.sqrt(12)
dd = lambda r: ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()
act = m.ret - m.hurdle
print('=== c3_sector_2 + SPX hedge + 10% vol target, FULL COSTS, 2021-01..2026-08 ===')
print('  volatility on NAV      %6.2f%%' % (100 * m.ret.std(ddof=1) * np.sqrt(12)))
print('  max drawdown           %6.2f%%' % (100 * dd(m.ret)))
print('  net IR vs T-bill+4%%    %6.3f' % ir(act))
print('  max sector net         %6.2f%%' % (100 * (m.k * 0.02).max()))
print('  --')
print('  CAGR                   %6.2f%%' % (100 * ((m.nav.iloc[-1] / 1e9) ** (12 / len(m)) - 1)))
print('  ending NAV             $%.2fbn' % (m.nav.iloc[-1] / 1e9))
print('  realised beta vs SPX   %+.3f' % np.polyfit(m.dropna(subset=['mx']).mx, (m.ret - m.cash)[m.mx.notna()], 1)[0])
print('  gross: mean %.1f%%  max %.1f%%' % (100 * (2.0 * m.k).mean(), 100 * (2.0 * m.k).max()))
print('  scale k: mean %.3f  min %.3f  max %.3f' % (m.k.mean(), m.k.min(), m.k.max()))
print('  annual one-way turnover %.0f%%' % (100 * (m.traded_s / 2).mean() * 12))
print('  annual cost             %.2f%% of NAV' % (100 * m.cost_s.mean() * 12))
print('  hedge h: mean %+.3f  range %+.3f..%+.3f' % (m.h.mean(), m.h.min(), m.h.max()))

# ---- holdings export --------------------------------------------------------
x = h.merge(m[['target_month', 'k', 'nav_open', 'h']], on='target_month', how='left')
x['position_usd'] = x.weight * x.k * x.nav_open
x['date'] = (pd.PeriodIndex(x.target_month, freq='M') - 1).to_timestamp(how='end').normalize()
# The panel's ticker/company_name are 44.7% blank in 2026 against 0.3-0.5% in
# every other year -- a vintage artifact, not a missing company. Carry the last
# non-null label at or before the formation month forward per permno, then fall
# back to the earliest available label for names that only appear later.
lab = pd.read_parquet(PANEL, columns=['permno', 'eom', 'ticker', 'company_name'])
lab['eom'] = pd.to_datetime(lab.eom)
lab = lab.sort_values(['permno', 'eom'], kind='stable')
for col in ('ticker', 'company_name'):
    g = lab.groupby('permno', sort=False)[col]
    lab[col] = g.ffill()
    lab[col] = lab.groupby('permno', sort=False)[col].bfill()
lab = lab.rename(columns={'ticker': 'tick_f', 'company_name': 'name_f'})
x['eom_form'] = (pd.PeriodIndex(x.target_month, freq='M') - 1).to_timestamp(how='end').normalize()
lab['eom'] = lab.eom.dt.normalize()
x = x.merge(lab[['permno', 'eom', 'tick_f', 'name_f']],
            left_on=['permno', 'eom_form'], right_on=['permno', 'eom'], how='left')
x['ticker'] = x.ticker.fillna(x.tick_f)
x['name'] = x.company_name.fillna(x.name_f)
missing = x.ticker.isna().sum()
if missing:
    raise ValueError(f'{missing} rows still have no ticker after carry-forward')
out = x[['date', 'ticker', 'name', 'position_usd']].copy()
hedge_rows = m.assign(date=(pd.PeriodIndex(m.target_month, freq='M') - 1).to_timestamp(how='end').normalize(),
                      ticker='SPY', name='SPX futures hedge (SPY proxy)',
                      position_usd=-m.h * m.k * m.nav_open)[['date', 'ticker', 'name', 'position_usd']]
out = pd.concat([out, hedge_rows], ignore_index=True)
out = out.sort_values(['date', 'position_usd'], ascending=[True, False]).reset_index(drop=True)
out['position_usd'] = out.position_usd.round(2)
p = 'sizing/c3_sector_2/holdings_final.csv'
out.to_csv(p, index=False)
print('\n  rows %d  rebalances %d  -> %s' % (len(out), out.date.nunique(), p))
print('  gross USD check, first rebalance: $%.1fm on $%.0fm NAV = %.1f%%' % (
    out[out.date == out.date.min()].position_usd.abs().sum() / 1e6, m.nav_open.iloc[0] / 1e6,
    100 * out[out.date == out.date.min()].position_usd.abs().sum() / m.nav_open.iloc[0]))

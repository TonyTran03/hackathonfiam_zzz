"""Stage-one reporting: monthly gross returns and rebalance snapshots only."""
from pathlib import Path
import argparse
import hashlib
import json
import html
import platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def load_inputs(folder):
    hp = folder / 'holdings.csv'
    if not hp.exists(): hp = folder / 'holdings.parquet'
    h = pd.read_parquet(hp) if hp.suffix == '.parquet' else pd.read_csv(hp)
    h.columns = h.columns.str.lower()
    if 'date' not in h and 'target_month' in h: h['date'] = h['target_month']
    for c in ['date', 'permno', 'weight']:
        if c not in h: raise ValueError(f'Holdings missing {c}')
    h['date'] = pd.to_datetime(h.date, errors='raise')
    h['month'] = h.date.dt.to_period('M')
    if h.groupby('month').date.nunique().max() != 1:
        raise ValueError('Stage one accepts one portfolio snapshot per month, not daily holdings.')
    h['weight'] = pd.to_numeric(h.weight, errors='raise')
    if h.permno.isna().any() or not np.isfinite(h.weight).all():
        raise ValueError('Missing identifier or non-finite holding weight')
    if h.duplicated(['month', 'permno']).any(): raise ValueError('Duplicate stock-month holdings')
    h = h[h.weight != 0].copy()
    rp = folder / 'portfolio_returns.csv'
    r = pd.read_csv(rp)
    required = ['target_month', 'total', 'hurdle', 'cash_monthly', 'sp500_ret']
    if any(c not in r for c in required): raise ValueError(f'Returns require {required}')
    r['month'] = pd.PeriodIndex(r.target_month, freq='M')
    r = r.sort_values('month').reset_index(drop=True)
    if r.month.duplicated().any(): raise ValueError('Duplicate return months')
    if len(r) < 3: raise ValueError('At least three months required')
    expected = pd.period_range(r.month.min(), r.month.max(), freq='M')
    if list(r.month) != list(expected): raise ValueError('Missing return months')
    if set(h.month) != set(r.month): raise ValueError('Holdings and returns cover different months')
    for c in required[1:]:
        r[c] = pd.to_numeric(r[c], errors='raise')
        if not np.isfinite(r[c]).all(): raise ValueError(f'Missing/non-finite {c}')
    if (r[['total', 'hurdle', 'sp500_ret']] < -1).any().any(): raise ValueError('Return below -100%')
    if not np.allclose(r.hurdle, r.cash_monthly + .04/12, atol=1e-10, rtol=0):
        raise ValueError('Provisional benchmark must equal cash_monthly + 0.04/12')
    if 'active' in r and not np.allclose(r.active, r.total-r.hurdle, atol=1e-10, rtol=0):
        raise ValueError('Stored active returns do not reconcile')
    if 'spread' in r and not np.allclose(r.total, r.cash_monthly+r.spread, atol=1e-10, rtol=0):
        raise ValueError('Cash plus spread does not reconcile')
    if all(c in r for c in ['spread','long_leg','short_leg']):
        if not np.allclose(r.spread, r.long_leg+r.short_leg, atol=1e-10, rtol=0):
            raise ValueError('Leg returns do not reconcile')
    return h, r, [hp, rp]


def performance(returns, cash):
    a = np.asarray(returns, dtype=float)
    wealth = np.r_[1., np.cumprod(1+a)]
    excess = a-np.asarray(cash)
    sd = excess.std(ddof=1)
    return dict(ending_nav=1e9*wealth[-1], cumulative=wealth[-1]-1,
                cagr=wealth[-1]**(12/len(a))-1, arithmetic=a.mean()*12,
                volatility=a.std(ddof=1)*np.sqrt(12),
                sharpe=excess.mean()/sd*np.sqrt(12) if sd > 1e-14 else np.nan,
                drawdown=(wealth/np.maximum.accumulate(wealth)-1).min(),
                worst_month=a.min())


def calculate(h, r):
    p = performance(r.total, r.cash_monthly)
    b = performance(r.hurdle, r.cash_monthly)
    active = r.total-r.hurdle
    te = active.std(ddof=1)*np.sqrt(12)
    p['information_ratio'] = active.mean()*12/te if te>1e-14 else np.nan
    p['tracking_error'] = te
    stats = h.groupby('month').weight.agg(positions='size', net='sum', max_abs=lambda w:w.abs().max(), gross=lambda w:w.abs().sum()).reset_index()
    rows=[]
    def add(metric, unit, value=None, benchmark=None, status='available', note=''):
        rows.append(dict(metric=metric,unit=unit,strategy=value,benchmark=benchmark,status=status,note=note))
    for key,label,unit in [
        ('ending_nav','Ending endowment','USD'),('cumulative','Cumulative return','decimal'),
        ('cagr','CAGR','decimal/year'),('arithmetic','Annualised arithmetic return','decimal/year'),
        ('volatility','Annualised volatility','decimal/year'),('sharpe','Sharpe ratio','ratio'),
        ('drawdown','Maximum drawdown — monthly observations','decimal'),('worst_month','Maximum one-month loss / minimum monthly return','decimal')]:
        note='Gross; monthly observations.'
        if key=='sharpe':note+=' Benchmark excess return is constant; its Sharpe is undefined, not zero.'
        add(label,unit,p[key],b[key],note=note)
    add('Information ratio — gross','ratio',p['information_ratio'],note='Versus cash + 4%; monthly frequency.')
    add('Tracking error','decimal/year',te,note='Std(strategy minus benchmark) × sqrt(12).')
    add('Months beating benchmark','fraction',float((active>0).mean()),note='Monthly benchmark hit rate, not position win rate.')
    for c,label in [('positions','Positions held'),('gross','Gross exposure'),('net','Net exposure')]:
        for agg in ['mean','min','max']:
            add(f'{label}: {agg}','count' if c=='positions' else 'fraction NAV',float(getattr(stats[c],agg)()),status='snapshot only',note='Monthly recorded target weights; does not establish daily compliance.')
    add('Largest single-name weight','fraction NAV',float(stats.max_abs.max()),status='snapshot only')
    for label,note in [
        ('Annualised alpha + standard error','Regression calculation scheduled for daily-risk stage.'),
        ('Monthly beta + standard error','Regression calculation scheduled for next reporting stage.'),
        ('Daily beta + standard error','Requires agreed daily portfolio and market returns.'),
        ('Maximum one-day loss','Requires agreed daily portfolio returns.'),
        ('One-way turnover per rebalance','Requires actual pre-trade drifted and post-trade weights (section 9.3).'),
        ('Annualised one-way turnover','Requires exact turnover and declared rebalance schedule.'),
        ('Average holding period','Requires position histories and holding-period convention.'),
        ('Average position size, USD million','Requires agreed NAV and dollar positions; not inferred from target weights.'),
        ('Short-book median market cap, USD million','Requires historically aligned market cap.'),
        ('Trading cost, fraction NAV/year','Requires trade-cost ledger.'),
        ('Borrow cost, fraction NAV/year','Requires borrow-cost ledger.'),
        ('Information ratio — net of all costs','Requires agreed net return series.')]:
        add(label,'see note',status='pending',note=note)
    yearly=r.groupby(r.month.dt.year).agg(strategy_gross=('total',lambda s:(1+s).prod()-1),benchmark=('hurdle',lambda s:(1+s).prod()-1),sp500_price=('sp500_ret',lambda s:(1+s).prod()-1),months=('total','size')).reset_index(names='year')
    yearly['strategy_net']=np.nan
    yearly['period_note']=np.where(yearly.months==12,'full calendar year','partial year')
    weights=h.pivot(index='month',columns='permno',values='weight').reindex(r.month).fillna(0)
    avg=weights.mean().rename('average_weight').reset_index()
    labels=[c for c in ['ticker','company_name'] if c in h]
    if labels:avg=avg.merge(h.sort_values('date').drop_duplicates('permno',keep='last')[['permno']+labels],on='permno',validate='one_to_one')
    avg=avg.sort_values('average_weight',ascending=False)
    top=pd.concat([avg[avg.average_weight>0].head(10).assign(side='long'),avg[avg.average_weight<0].tail(10).sort_values('average_weight').assign(side='short')])
    return pd.DataFrame(rows),stats,yearly,avg,top,p


def generate(folder, out, verify=False):
    h,r,files=load_inputs(folder)
    table,stats,yearly,avg,top,p=calculate(h,r)
    if verify:
        for key,value in {'cumulative':1.7641948856767624,'cagr':.19653079645744076,'information_ratio':.8834050267790214}.items():
            if not np.isclose(p[key],value,atol=1e-10,rtol=0):raise ValueError(f'Round-one reference mismatch: {key}')
        if len(h)!=13600 or len(r)!=68:raise ValueError('Round-one row-count mismatch')
    out.mkdir(parents=True,exist_ok=True)
    for name,df in [('performance_summary',table),('exposures_monthly',stats),('yearly_returns',yearly),('average_holdings',avg),('top_bottom_holdings',top)]:df.to_csv(out/f'{name}.csv',index=False)
    plt.rcParams.update({'figure.dpi':140,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'font.size':10})
    dates=r.month.dt.to_timestamp('M');start=dates.iloc[0]-pd.offsets.MonthEnd(1);x=pd.DatetimeIndex([start,*dates])
    fig,ax=plt.subplots(figsize=(10,4))
    for c,label in [('total','Strategy — gross'),('hurdle','Cash + 4%'),('sp500_ret','S&P 500 — price only')]:ax.plot(x,np.r_[1,np.cumprod(1+r[c])],label=label)
    ax.set(ylabel='Growth of $1',title='Round-one monthly performance');ax.legend();fig.tight_layout();fig.savefig(out/'growth.png');plt.close(fig)
    curve=(1+r.total).cumprod()-(1+r.hurdle).cumprod()
    fig,ax=plt.subplots(figsize=(10,3));ax.plot(x,np.r_[0,curve]*100,color='#126e82');ax.set(title='Cumulative wealth advantage over benchmark',ylabel='Percentage-point difference');fig.tight_layout();fig.savefig(out/'active_wealth.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4));yearly.set_index('year')[['strategy_gross','benchmark','sp500_price']].mul(100).plot.bar(ax=ax);ax.set(title='Calendar-year returns — 2026 is January–August',ylabel='Return (%)',xlabel='');ax.tick_params(axis='x',rotation=0);fig.tight_layout();fig.savefig(out/'yearly_returns.png');plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(10,6),sharex=True)
    for ax,c in zip(axes,['gross','net','positions']):ax.plot(dates,stats[c]*(100 if c!='positions' else 1));ax.set_ylabel(c+(' (%)' if c!='positions' else ''))
    axes[0].set_title('Recorded monthly target exposures — not daily exposure paths');fig.tight_layout();fig.savefig(out/'exposures.png');plt.close(fig)
    status=pd.DataFrame([
        [1,'Cumulative active performance','partial','Gross monthly wealth comparison; daily/net version pending.'],
        [2,'252-day rolling beta','pending','Daily return series required.'],
        [3,'Calendar-year gross/net returns','partial','Gross and benchmark available; net costs pending.'],
        [4,'Exposure and position histories','partial','Monthly snapshots only.'],
        [5,'Top/bottom ten average holdings','available','Equal-month average, absent names counted as zero; latest observed labels.'],
        [6,'Largest positive/negative contributors','pending','Position P&L and agreed compounding attribution required.'],
        [7,'Short market-cap/dollar-volume distributions','pending','Historical stock characteristics required.'],
        [8,'Position size in days of ADV','pending','Dollar positions and ADV required.']],columns=['section_9_4_item','exhibit','status','note'])
    status.to_csv(out/'exhibit_status.csv',index=False)
    table_display=table.copy()
    for c in ['strategy','benchmark']:table_display[c]=table_display[c].map(lambda x:'—' if pd.isna(x) else f'{x:,.6f}')
    body='''<!doctype html><meta charset="utf-8"><title>FIAM Round-one Reporting</title><style>body{font:15px system-ui;max-width:1100px;margin:40px auto;color:#173047;padding:0 20px}h1,h2{color:#126e82}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:9px;border-bottom:1px solid #dbe3e8;text-align:left}th{background:#edf4f6}img{width:100%;margin:15px 0}.notice{padding:18px;background:#fff4dc;border-left:4px solid #c58b27}</style><h1>FIAM · Round-one reporting baseline</h1><p>阶段一：初赛月度报告基准</p><div class="notice">Gross monthly results only. This is a reporting test, not the final submission. Pending values are unavailable, never zero. Monthly target snapshots do not establish daily compliance.</div>'''
    body+=f'<p>{len(r)} months · {len(h):,} position records · starting capital assumption: US$1 billion.</p>'
    for f in ['growth.png','active_wealth.png','yearly_returns.png','exposures.png']:body+=f'<img src="{f}" alt="{f}">'
    body+='<h2>Performance table scaffold</h2><p>Decimal returns: 0.01 = 1%. NAV is in USD. Risk metrics use 12 monthly periods/year. Benchmark Sharpe is undefined because its excess over cash is constant.</p>'+table_display.to_html(index=False,escape=True)
    body+='<h2>Top and bottom holdings</h2><p>Average over all holding months; zero when absent. These are monthly averages, not daily time-weighted averages.</p>'+top.to_html(index=False,escape=True)
    body+='<h2>Required exhibit coverage</h2>'+status.to_html(index=False,escape=True)
    body+='<h2>Conventions and limitations</h2><p>Benchmark: cash_monthly + 0.04/12; cash_monthly is TB3MS/1200. S&P series excludes dividends. Cumulative active exhibit is strategy compounded wealth minus benchmark compounded wealth, not compounding the difference of returns. First-period drawdowns include initial NAV. Alpha/beta, exact turnover, daily metrics, costs and attribution remain pending.</p>'
    (out/'report.html').write_text(body,encoding='utf-8')
    manifest={'scope':'stage-one monthly gross reporting','reference_verified':verify,'months':len(r),'holdings_rows':len(h),'inputs':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'gross_results':p,'complete_final_report':False}
    (out/'validation.json').write_text(json.dumps(manifest,indent=2,allow_nan=False))
    print(json.dumps(p,indent=2));print('Report:',out/'report.html')

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--inputs',type=Path,default=Path('inputs'));a.add_argument('--output',type=Path,default=Path('output'));a.add_argument('--verify-round1',action='store_true');a.add_argument('--require-final',action='store_true',help='Fail: this stage-one module is intentionally incomplete for finals.')
    args=a.parse_args()
    if args.require_final:a.error('Final report unavailable: daily accounting, costs, exact turnover and remaining exhibits are pending.')
    generate(args.inputs,args.output,args.verify_round1)

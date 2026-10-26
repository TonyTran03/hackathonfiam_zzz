"""Section 9 report from exported 06_final results; does not rerun the strategy."""
import argparse
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ledger

DEFAULT_MARKET_CAPS=Path(__file__).resolve().parents[1]/'01_data'/'processed'/'model_table.parquet'  # common.config.MODEL_TABLE

FACTOR_NAMES=['Mkt-RF','SMB','HML','RMW','CMA','Mom']
FACTOR_URLS={
 'ff5':'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip',
 'momentum':'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_french(data, names):
    """Read monthly records only; source values are percentages, output decimals."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1: raise ValueError('Expected one French CSV in ZIP')
        lines=z.read(members[0]).decode('utf-8-sig').splitlines()
    rows=[]
    for line in lines:
        if re.match(r'^\s*\d{6},',line):
            fields=line.strip().split(',')
            if len(fields)!=len(names)+1: raise ValueError('Unexpected factor column count')
            vals=[float(v) for v in fields[1:]]
            if any(v<=-99.99 for v in vals): raise ValueError('Missing-value sentinel in factor source')
            rows.append([pd.Period(fields[0],freq='M'),*[v/100 for v in vals]])
    result=pd.DataFrame(rows,columns=['month',*names])
    if result.empty or result.month.duplicated().any():raise ValueError('Invalid factor month keys')
    return result


def fetch_factors(cache):
    cache.mkdir(parents=True,exist_ok=True)
    manifest={}
    frames=[]
    for key,url in FACTOR_URLS.items():
        path=cache/(key+'.zip')
        if not path.exists():
            data=urllib.request.urlopen(url,timeout=45).read()
            parse_french(data,['Mkt-RF','SMB','HML','RMW','CMA','RF'] if key=='ff5' else ['Mom'])
            path.write_bytes(data)
        frames.append(parse_french(path.read_bytes(),['Mkt-RF','SMB','HML','RMW','CMA','RF'] if key=='ff5' else ['Mom']))
        manifest[key]={'url':url,'sha256':sha(path)}
    factors=frames[0].merge(frames[1],on='month',validate='one_to_one')
    factors.to_csv(cache/'ff5_momentum_monthly.csv',index=False)
    (cache/'sources.json').write_text(json.dumps(manifest,indent=2))
    return factors,manifest


def regression(y, x, names):
    y=np.asarray(y,float);x=np.asarray(x,float)
    if x.ndim==1:x=x[:,None]
    a=np.column_stack([np.ones(len(y)),x])
    if len(y)<=a.shape[1] or not np.isfinite(a).all() or not np.isfinite(y).all():raise ValueError('Invalid regression sample')
    if np.linalg.matrix_rank(a)!=a.shape[1]:raise ValueError('Rank-deficient regression')
    coef=np.linalg.lstsq(a,y,rcond=None)[0];resid=y-a@coef
    se=np.sqrt(np.diag(np.linalg.inv(a.T@a)*(resid@resid)/(len(y)-a.shape[1])))
    result=pd.DataFrame({'term':['alpha',*names],'coefficient':coef,'standard_error':se})
    result['t_stat']=np.divide(coef,se,out=np.full_like(coef,np.nan),where=se>0)
    return result,1-(resid@resid)/np.sum((y-y.mean())**2)


def max_drawdown(returns):
    wealth=np.r_[1.,np.cumprod(1+np.asarray(returns))]
    return (wealth/np.maximum.accumulate(wealth)-1).min()


def ratio(x):
    x=pd.Series(x);sd=x.std(ddof=1)
    return np.sqrt(252)*x.mean()/sd if sd>1e-14 else np.nan


def validate_daily(d,nav0):
    d=d.copy();d['date']=pd.to_datetime(d.date,errors='raise')
    numeric=['nav','ret','ret_gross','rf','hurdle','sp_ret','gross','net','n_long','n_short','max_w','cost','borrow','turnover']
    if d.date.duplicated().any() or not d.date.is_monotonic_increasing:raise ValueError('Daily dates must be unique and sorted')
    if len(d)<252 or not np.isfinite(d[numeric].to_numpy(float)).all():raise ValueError('Daily sample too short or non-finite')
    if (d[['ret','ret_gross','sp_ret','hurdle']]<=-1).any().any():raise ValueError('Return at/below -100%')
    if (d[['cost','borrow','turnover']]<0).any().any():raise ValueError('Negative cost or turnover')
    if not np.allclose(d.nav,nav0*(1+d.ret).cumprod(),rtol=1e-9,atol=.01):raise ValueError('NAV does not reconcile with net returns/start NAV')
    prev=d.nav.shift().fillna(nav0)
    if not np.allclose(d.ret_gross-d.ret,(d.cost+d.borrow)/prev,atol=1e-10,rtol=0):raise ValueError('Gross/net returns do not reconcile with costs')
    if not np.allclose(d.hurdle,d.rf+.04/252,atol=1e-10,rtol=0):raise ValueError('Daily provisional benchmark is inconsistent')
    d['month']=d.date.dt.to_period('M')
    return d


def monthly(d):
    return d.groupby('month')[['ret','ret_gross','rf','hurdle','sp_ret']].agg(lambda x:(1+x).prod()-1)


def fmt(x):return f'{x:,.3f}' if np.isfinite(x) else 'Undefined'


def build_table(d,source,form,nav0):
    rows=[];m=monthly(d);years=len(d)/252;prev=d.nav.shift().fillna(nav0)
    regs={}
    for basis,col in [('net','ret'),('gross','ret_gross')]:
        regs[basis+'_daily']=regression(d[col]-d.rf,d.sp_ret-d.rf,['market'])[0]
        regs[basis+'_monthly']=regression(m[col]-m.rf,m.sp_ret-m.rf,['market'])[0]
    def add(label,units,s,b='n/a'):rows.append([label,units,s,b])
    def both(label,units,fn,scale=1):add(label,units,fmt(fn(d.ret)*scale),fmt(fn(d.hurdle)*scale))
    both('Ending value of the endowment','US$ billion',lambda r:nav0*(1+r).prod()/1e9)
    both('Cumulative return over the period','%',lambda r:(1+r).prod()-1,100)
    both('Annualised return','% per year',lambda r:r.mean()*252,100)
    both('Annualised volatility','% per year',lambda r:r.std(ddof=1)*np.sqrt(252),100)
    a=regs['net_monthly'].iloc[0];b=regs['net_monthly'].iloc[1];bd=regs['net_daily'].iloc[1]
    add('Annualised alpha vs S&P 500','% per year (+ s.e.)',f'{a.coefficient*1200:.3f} ({a.standard_error*1200:.3f})')
    add('Beta vs S&P 500 - monthly','coefficient (+ s.e.)',f'{b.coefficient:.4f} ({b.standard_error:.4f})')
    add('Beta vs S&P 500 - daily','coefficient (+ s.e.)',f'{bd.coefficient:.4f} ({bd.standard_error:.4f})')
    add('Sharpe ratio','annualised',fmt(ratio(d.ret-d.rf)),fmt(ratio(d.hurdle-d.rf)))
    add('Information ratio vs T-bill + 4%','annualised',fmt(ratio(d.ret_gross-d.hurdle)))
    add('Tracking error','% per year',fmt((d.ret_gross-d.hurdle).std(ddof=1)*np.sqrt(252)*100))
    both('Maximum drawdown','%',max_drawdown,100)
    add('Maximum one-month loss','%',fmt(min(0,m.ret.min())*100),fmt(min(0,m.hurdle.min())*100))
    both('Maximum one-day loss','%',lambda r:min(0,r.min()),100)
    n=d.n_long+d.n_short
    add('Positions held','average / min / max',' / '.join(fmt(x) for x in [n.mean(),n.min(),n.max()]))
    add('Gross exposure','average / maximum, % of capital',' / '.join(fmt(x*100) for x in [d.gross.mean(),d.gross.max()]))
    add('Net exposure','average / min / max, % of capital',' / '.join(fmt(x*100) for x in [d.net.mean(),d.net.min(),d.net.max()]))
    traded=d.loc[d.turnover>0,'turnover']
    add('One-way turnover','% per rebalance and annualised',f'{traded.mean()*100:.3f} / {d.turnover.sum()/years*100:.3f}')
    def supplied(label):
        found=source.loc[source.metric==label,'strategy']
        if len(found)!=1:raise ValueError('Missing/ambiguous supplied metric: '+label)
        return str(found.iloc[0])
    add('Average holding period','trading days',supplied('Average holding period'))
    add('Average position size','US$ million',supplied('Average position size'))
    add('Short book median market cap','US$ million',fmt(form.loc[form.leg=='short','me_form'].median()))
    add('Trading cost','% of NAV per year',fmt((d.cost/prev).sum()/years*100))
    add('Borrow cost','% of NAV per year',fmt((d.borrow/prev).sum()/years*100))
    add('Information ratio, net of all costs','annualised',fmt(ratio(d.ret-d.hurdle)))
    return pd.DataFrame(rows,columns=['Metric','Units / basis','Strategy','Benchmark']),regs


def make_charts(d,top,contrib,form):
    figs=[];dates=d.date.dt.strftime('%Y-%m-%d').tolist()
    f=make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=('Cumulative returns','Relative compounded wealth vs benchmark'))
    benchmark=(1+d.hurdle).cumprod()
    for col,label in [('ret','Strategy - net'),('ret_gross','Strategy - gross'),('hurdle','Cash + 4%'),('sp_ret','S&P 500 - price context')]:
        wealth=(1+d[col]).cumprod();f.add_trace(go.Scatter(x=dates,y=((wealth-1)*100).tolist(),name=label),row=1,col=1)
        if col!='hurdle':f.add_trace(go.Scatter(x=dates,y=((wealth/benchmark-1)*100).tolist(),name=label+' relative'),row=2,col=1)
    f.update_layout(title='1. Cumulative active performance',height=650);f.update_yaxes(title_text='%');figs.append(f)
    beta=pd.DataFrame({'date':d.date})
    for col,label in [('ret','net'),('ret_gross','gross')]:
        beta[label]=(d[col]-d.rf).rolling(252,min_periods=252).cov(d.sp_ret-d.rf)/(d.sp_ret-d.rf).rolling(252,min_periods=252).var()
    f=go.Figure()
    for c in ['net','gross']:f.add_trace(go.Scatter(x=dates,y=beta[c].tolist(),name=c.title()))
    f.add_hline(y=0,line_dash='dot');f.update_layout(title='2. Rolling S&P 500 beta - 252 trading days',yaxis_title='Beta');figs.append(f)
    annual=d.groupby(d.date.dt.year)[['ret','ret_gross','hurdle','sp_ret']].agg(lambda x:(1+x).prod()-1)
    counts=d.groupby(d.date.dt.year).month.nunique();labels=[str(y)+(' (partial)' if counts[y]<12 else '') for y in annual.index]
    f=go.Figure()
    for c,label in [('ret_gross','Gross'),('ret','Net'),('hurdle','Cash + 4%')]:f.add_trace(go.Bar(x=labels,y=(annual[c]*100).tolist(),name=label))
    f.update_layout(title='3. Calendar-year returns before and after costs',barmode='group',yaxis_title='Return (%)');figs.append(f)
    f=make_subplots(rows=3,cols=1,shared_xaxes=True,subplot_titles=('Gross exposure (% NAV)','Net exposure (% NAV)','Positions held'))
    for i,(y,label) in enumerate([(d.gross*100,'Gross'),(d.net*100,'Net'),(d.n_long+d.n_short,'Positions')],1):f.add_trace(go.Scatter(x=dates,y=y.tolist(),name=label),row=i,col=1)
    f.update_layout(title='4. Daily exposure and position count',height=650);figs.append(f)
    for data,col,title,xlabel in [(top,'avg_weight_pct','5. Top ten and bottom ten holdings','Average weight (% NAV; zero when absent)'),(contrib,'contribution_pct_of_start_nav','6. Largest positive and negative contributors','Stock P&L (% of starting NAV; before portfolio costs)')]:
        q=data.sort_values(col);labels=q.ticker.fillna('?').astype(str)+' | '+q.company_name.fillna('').astype(str)+' | '+q.permno.astype(str)
        f=go.Figure(go.Bar(x=q[col].tolist(),y=labels.tolist(),orientation='h',marker_color=['#147d92' if v>=0 else '#b94b50' for v in q[col]]));f.update_layout(title=title,xaxis_title=xlabel,height=720,margin=dict(l=330));figs.append(f)
    short=form[form.leg=='short']
    f=make_subplots(rows=1,cols=2,subplot_titles=('Market cap (US$ million)','126-day average daily dollar volume (US$ million)'))
    for i,c,scale in [(1,'me_form',1),(2,'dolvol_126d',1e6)]:f.add_trace(go.Histogram(x=(short[c]/scale).tolist(),nbinsx=60,name=c),row=1,col=i)
    f.add_vline(x=500,line_color='red',line_dash='dash',row=1,col=1);f.update_layout(title='7. Short-book characteristics at formation - $500m floor',showlegend=False);figs.append(f)
    f=make_subplots(rows=1,cols=2,subplot_titles=('Long positions','Short positions'))
    for i,leg in enumerate(['long','short'],1):f.add_trace(go.Histogram(x=form.loc[form.leg==leg,'days_adv'].tolist(),nbinsx=40,name=leg),row=1,col=i)
    f.update_xaxes(title_text='Absolute position dollars / average daily dollar volume');f.update_layout(title='8. Position size in days of ADV - formation targets',showlegend=False);figs.append(f)
    for f in figs:f.update_layout(template='plotly_white',font=dict(family='Arial',color='#173047'),dragmode='zoom')
    return figs,beta,annual


def log_histogram(values,name,color,step=.05):
    """Bars over log10-spaced bins; every positive value is binned, none clipped."""
    x=np.log10(np.asarray(values,float));lo=np.floor(x.min()/step)*step;hi=np.ceil(x.max()/step)*step+step
    counts,edges=np.histogram(x,bins=np.arange(lo,hi+step/2,step))
    text=[f'US${10**a:,.3g}m to US${10**b:,.3g}m: {c:,} observations' for a,b,c in zip(edges[:-1],edges[1:],counts)]
    return go.Bar(x=((edges[:-1]+edges[1:])/2).tolist(),y=counts.tolist(),width=step,name=name,hovertext=text,hoverinfo='text',marker_color=color)


def short_book_exhibit(held,openings,sm):
    """Exhibit 7: held short stock-days (market cap, ADV) plus the separate opening/addition eligibility diagnostic."""
    cap=held.market_cap_million.dropna();adv=held.loc[held.liquidity_known,'adv_dollars']/1e6;oc=openings.market_cap_million.dropna()
    age=(pd.to_datetime(held.date)-pd.to_datetime(held.liquidity_asof)).dt.days
    f=make_subplots(rows=1,cols=3,horizontal_spacing=.07,subplot_titles=('Held shorts: prior-month-end panel me','Held shorts: engine stored 126-day ADV','Short openings/additions: prior-month-end panel me'))
    for i,(v,name,color) in enumerate([(cap,'Held short market cap','#147d92'),(adv,'Held short ADV','#6b7f8e'),(oc,'Opening/addition market cap','#b94b50')],1):
        if len(v):f.add_trace(log_histogram(v,name,color),row=1,col=i)
    ticks=[.01,.1,1,10,100,1000,10000,100000,1000000]
    for i,title in [(1,'US$ million, log scale'),(2,'US$ million, log scale'),(3,'US$ million, log scale')]:
        f.update_xaxes(tickvals=np.log10(ticks).tolist(),ticktext=[f'{t:,.0f}' if t>=1 else f'{t:g}' for t in ticks],tickangle=0,title_text=title,row=1,col=i)
    for i in [1,3]:f.add_vline(x=float(np.log10(500)),line_color='red',line_dash='dash',row=1,col=i)
    f.update_yaxes(title_text='Stock-day observations',row=1,col=1);f.update_yaxes(title_text='Openings/additions',row=1,col=3)
    def rng(v):return f'{v.min():,.3g} to {v.max():,.0f}' if len(v) else 'none'
    note=(f"Held shorts: {sm['short_held_name_days']:,} stock-days; unmatched month-end me {sm['short_held_month_end_unmatched']:,}; held short stock-days below US$500m at prior month-end {sm['short_held_month_end_below_500m']:,}. Range {rng(cap)}; median {sm['short_book_median_market_cap_million'] if sm['short_book_median_market_cap_million'] is None else format(sm['short_book_median_market_cap_million'],',.0f')}.<br>"
          f"Openings/additions: {sm['short_openings']:,}; unmatched {sm['short_openings_month_end_unmatched']:,}; below US$500m at month-end {sm['short_openings_month_end_below_500m']:,}; range {rng(oc)}. ADV range {rng(adv)}; ADV age {age.median():.0f} days median, {age.max():.0f} max; missing ADV {sm['position_liquidity_unknown']:,}.<br>"
          "Red line: US$500m. Values are prior-month-end panel me, so this does not prove execution-day compliance. Log10 bins of 0.05; no observations dropped or clipped.")
    f.add_annotation(text=note,xref='paper',yref='paper',x=0,y=-.3,yanchor='top',showarrow=False,align='left',xanchor='left',font=dict(size=11))
    f.update_layout(title='7. Short book: market cap and liquidity of held short positions',template='plotly_white',showlegend=False,height=600,margin=dict(b=200),bargap=0)
    return f


def factor_attribution(d,factors):
    m=monthly(d).reset_index();factors=factors.copy();factors['month']=pd.PeriodIndex(factors.month,freq='M')
    if factors.month.duplicated().any():raise ValueError('Duplicate factor month')
    j=m.merge(factors,on='month',how='left',validate='one_to_one')
    if not np.isfinite(j[FACTOR_NAMES+['RF']].to_numpy(float)).all():raise ValueError('FF5+momentum must cover every test month without missing values')
    rows=[]
    for basis,col in [('net','ret'),('gross','ret_gross')]:
        reg,r2=regression(j[col]-j.RF,j[FACTOR_NAMES],FACTOR_NAMES)
        reg['basis']=basis;reg['n_months']=len(j);reg['r_squared']=r2
        reg['annual_mean_contribution_pct']=[reg.iloc[0].coefficient*1200]+[reg.loc[reg.term==c,'coefficient'].iloc[0]*j[c].mean()*1200 for c in FACTOR_NAMES]
        reg['annualised_coefficient']=reg.coefficient.where(reg.term!='alpha',reg.coefficient*12)
        reg['annualised_standard_error']=reg.standard_error.where(reg.term!='alpha',reg.standard_error*12)
        rows.append(reg)
    return pd.concat(rows,ignore_index=True),j


def generate(inputs,out,factor_cache=None,nav0=1e9,ledger_dir=None,require_verified=False,market_caps=None):
    out.mkdir(parents=True,exist_ok=True)
    files=['daily_returns.csv','standard_table.csv','formation_positions.csv','top_holdings.csv','contributors.csv']
    loaded={n:pd.read_csv(inputs/n) for n in files}
    d=validate_daily(loaded['daily_returns.csv'],nav0);form=loaded['formation_positions.csv']
    verified=None
    if ledger_dir is None:
        candidate=inputs.parent.parent/'data'/'runs'/inputs.name
        if (candidate/'position_audit.parquet').exists():ledger_dir=candidate
    if ledger_dir is not None:
        names=pd.concat([loaded['top_holdings.csv'],loaded['contributors.csv']],ignore_index=True)[['permno','ticker','company_name']].drop_duplicates('permno')
        signals=ledger_dir.parent.parent/'signal_test.parquet';caps=None
        # signal_test is screened, so it is a label source only; market caps come from the full monthly panel.
        if market_caps is not None and Path(market_caps).exists():caps=ledger.load_market_caps(market_caps)
        if signals.exists():
            signal=pd.read_parquet(signals)
            if all(c in signal for c in ['permno','ticker','company_name']):
                if 'target_month' in signal:signal=signal.sort_values('target_month')
                names=signal.dropna(subset=['ticker','company_name']).drop_duplicates('permno',keep='last')[['permno','ticker','company_name']]
        verified=ledger.load(ledger_dir,d,names,caps)
        d=validate_daily(verified['daily'],nav0)
        pos=verified['positions']
        form=pos.rename(columns={'market_cap_million':'me_form','adv_dollars':'dolvol_126d','position_usd':'target_usd'}).copy()
        form['leg']=np.where(form.target_usd>0,'long','short')
        for item in ['top','contributors']:
            q=verified[item]
            q['ticker']=q.ticker.fillna('PERMNO')
            q['company_name']=q.company_name.fillna('Name unavailable')
        loaded['top_holdings.csv']=verified['top'];loaded['contributors.csv']=verified['contributors']
        for name,key in [('daily_positions','positions'),('short_executions','shorts'),('short_book_market_caps','held_shorts'),('execution_participation','executions'),('all_average_holdings','all_average'),('all_stock_contributors','all_contributors'),('holding_spells','spells')]:
            verified[key].to_csv(out/(name+'.csv'),index=False)
        d.to_csv(out/'daily_returns_verified.csv',index=False)
    elif require_verified:
        raise ValueError('Detailed audit ledger required: rerun patched engine and pass --ledger-dir')

    for col in ['me_form','dolvol_126d','target_usd','days_adv']:
        if verified is None and not np.isfinite(form[col]).all():raise ValueError('Missing formation '+col)
    if (form[['me_form','dolvol_126d']]<=0).any().any():raise ValueError('Nonpositive formation characteristics')
    if not set(form.leg)<= {'long','short'} or set(form.leg)!={'long','short'}:raise ValueError('Both long/short legs required')
    if verified is None and not np.allclose(form.days_adv,form.target_usd.abs()/form.dolvol_126d,atol=1e-9):raise ValueError('Days ADV does not reconcile')
    for filename,col in [('top_holdings.csv','avg_weight_pct'),('contributors.csv','contribution_pct_of_start_nav')]:
        q=loaded[filename]
        if len(q)!=20 or q.permno.duplicated().any() or not np.isfinite(q[col]).all():raise ValueError('Expected 20 unique finite rows in '+filename)
        if (q[col]>0).sum()!=10 or (q[col]<0).sum()!=10:raise ValueError('Expected ten positive and ten negative entries in '+filename)
    table,regs=build_table(d,loaded['standard_table.csv'],form,nav0)
    if verified is not None:
        sm=verified['summary']
        replacements={'One-way turnover':f"{sm['turnover_per_daily_rebalance_pct']:.3f} / {sm['turnover_annual_pct']:.3f}",
            'Average holding period':fmt(sm['holding_period_days']),
            'Average position size':fmt(sm['average_position_size_million']),
            'Short book median market cap':fmt(sm['short_book_median_market_cap_million']) if sm['short_book_median_market_cap_million'] is not None else 'Incomplete'}
        for metric,value in replacements.items():table.loc[table.Metric==metric,'Strategy']=value
    else:
        table.loc[table.Metric=='One-way turnover','Strategy']='Pending corrected ledger'
    table.to_csv(out/'section9_table.csv',index=False)
    pd.concat([v.assign(regression=k) for k,v in regs.items()]).to_csv(out/'market_regressions.csv',index=False)
    figs,beta,annual=make_charts(d,loaded['top_holdings.csv'],loaded['contributors.csv'],form)
    if verified is not None:
        positions=verified['positions'];sm=verified['summary']
        figs[6]=short_book_exhibit(verified['held_shorts'],verified['shorts'],sm)
        f=make_subplots(rows=1,cols=2,subplot_titles=('Actual long holdings','Actual short holdings'))
        for i,sign in enumerate([1,-1],1):
            q=positions[(np.sign(positions.position_usd)==sign)&positions.liquidity_known]
            f.add_trace(go.Histogram(x=q.days_adv.tolist(),name='Long' if sign==1 else 'Short'),row=1,col=i)
        f.update_layout(title='8. Actual daily positions in days of ADV',template='plotly_white',showlegend=False)
        f.update_xaxes(title_text='Absolute closing position dollars / stored ADV')
        f.add_annotation(text=f"One observation per held name/day. Missing ADV: {sm['position_liquidity_unknown']}; ADV is the engine's last formation estimate.",xref='paper',yref='paper',x=0,y=-.25,showarrow=False)
        figs[7]=f
    else:
        figs[5]=go.Figure()
        figs[5].update_layout(title='6. Return contributors - pending corrected ledger',template='plotly_white',xaxis_visible=False,yaxis_visible=False)
        figs[5].add_annotation(text='Previous contributors omit delisting P&L. Rerun the patched engine.',xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
    beta.to_csv(out/'rolling_beta.csv',index=False);annual.to_csv(out/'calendar_years.csv',index_label='year')
    attribution=None;sources={}
    if factor_cache is not None:
        factors,sources=fetch_factors(factor_cache);attribution,joined=factor_attribution(d,factors)
        attribution.to_csv(out/'ff5_momentum_attribution.csv',index=False);joined.to_csv(out/'factor_regression_sample.csv',index=False)
    checks={'nav_reconciles':True,'costs_reconcile':True,'daily_benchmark_formula':True,
        'positions_min':int((d.n_long+d.n_short).min()),'gross_max':float(d.gross.max()),'net_min':float(d.net.min()),'net_max':float(d.net.max()),'single_name_max':float(d.max_w.max()),
        'short_sample_min_market_cap_million':float(form.loc[form.leg=='short','me_form'].min()),
        'short_sample_floor_pass':bool((form.loc[form.leg=='short','me_form']>=500).all()),
        'daily_position_count_pass':bool(((d.n_long+d.n_short)>=200).all() and ((d.n_long+d.n_short)<=500).all()),
        'daily_gross_limit_pass':bool((d.gross<=2+1e-10).all()),
        'daily_net_limit_pass':bool((d.net.abs()<=.5+1e-10).all()),
        'daily_single_name_limit_pass':bool((d.max_w<=.05+1e-10).all())}
    warnings=[
      'Turnover is aggregated from the supplied engine field, not independently reconstructed from pre/post-trade weights. Section 9.3 verification still requires the detailed trade ledger.',
      'Per-rebalance turnover uses all dates with nonzero turnover, including carried orders and risk trades; annualisation uses observed trading-date frequency, not simply 12.',
      'Holding period and average position size are imported from the supplied standard_table.csv. Detailed daily position histories are absent from this package.',
      'Holdings averages and contributors are supplied exports. Names can use later reference dates and are display labels only. Contributor dollars are divided by starting NAV; costs and cash are not allocated to stocks.',
      'Liquidity and short-floor checks describe formation targets, not all executed positions. Execution-level compliance is not certified.',
      'Gross returns add back each day\'s costs to the realised net-funded path; compounded gross wealth is not a separate cost-free strategy simulation.',
      'Most table metrics are net; the first IR and its tracking error are gross. Net IR is the last row. Alpha and beta use net returns; gross regressions are supplied separately.',
      'Daily benchmark is the provisional cash series plus 4%/252. Monthly regression cash and market series are compounded from these same daily observations. S&P context is price-only.',
      'Cost percentages use each day\'s beginning NAV, summed and annualised. This differs from the original ratio of total costs to average NAV.',
      'OLS standard errors are conventional, not heteroskedasticity/autocorrelation robust. FF regressions use the French RF; market regressions use the supplied cash series.',
      'Cumulative active exhibit uses the relative compounded wealth ratio minus one; this aggregation convention is explicitly disclosed.'
    ]
    if verified is not None:
        checks_panel_name=str(market_caps) if caps is not None else 'no panel (unavailable)'
        warnings=warnings[4:]
        warnings=[w for w in warnings if not w.startswith('Liquidity and short-floor')]
        warnings.insert(0,'Verified against the supplied detailed ledger: Section 9.3 turnover, daily positions, and stock P&L including delistings. This does not certify the raw market data or strategy.')
        warnings.insert(1,'Daily turnover uses all trading dates including zero-trade days, annualised by 252; carried orders are actual executions, not monthly target changes.')
        warnings.insert(2,'Holding periods are consecutive end-of-day holding spells, weighted by mean absolute dollars. Sample-boundary spells are censored and included only for observed days. Average position size is the mean absolute held name/day position.')
        warnings.insert(3,'Market caps are panel me (US$ million) at the calendar month-end immediately before each date, from '+checks_panel_name+'. No older month is carried forward; unmatched observations are counted and left blank. The engine estimate (monthly shares x split-adjusted daily price) is exported as engine_market_cap_million for reference only and is never used as a fallback. Month-end checks do not verify market cap on execution days; execution-day $500m compliance remains unverified.')
        warnings.insert(4,'Short book median market cap is the unweighted median of prior-month-end panel me across actual held short positions, one observation per stock per trading day (short_book_market_caps.csv). Short openings/additions are a separate eligibility diagnostic. Shares and 126-day ADV are last formation inputs; their as-of dates are exported. Position-size/ADV uses actual closing holdings. Missing values and fallback ADV are explicitly counted.')
        warnings.insert(5,'Average weights use every end-of-day snapshot, with zero for absent names. Contributors include delisting settlement P&L, but cash income and portfolio costs remain separate. Labels may use later reference dates.')
        checks.update(verified['summary'])
        checks.pop('short_sample_floor_pass',None)
        checks.pop('short_sample_min_market_cap_million',None)
        checks['market_cap_panel']=str(market_caps) if caps is not None else 'unavailable: '+str(market_caps)
        missing_names=int((verified['top'].company_name=='Name unavailable').sum()+(verified['contributors'].company_name=='Name unavailable').sum())
        checks['missing_exhibit_company_names']=missing_names
        if require_verified and checks['month_end_market_cap_verification']!='complete':
            raise ValueError('Month-end market-cap verification is incomplete (panel unavailable or unmatched short observations); inspect short_executions.csv and short_book_market_caps.csv')
        if require_verified and (missing_names or checks['short_execution_adv_fallbacks'] or checks['position_liquidity_unknown'] or checks['short_openings_month_end_below_500m'] or not all(checks[k] for k in ['daily_position_count_pass','daily_gross_limit_pass','daily_net_limit_pass','daily_single_name_limit_pass'])):
            raise ValueError('Ledger reconciles, but missing labels/liquidity or month-end short-floor failures prevent verified submission; inspect audit exports')
    if attribution is None:warnings.append('FF5+momentum not generated: provide --factor-cache to fetch and cache the official monthly series.')
    provenance={'run':inputs.name,'start':str(d.date.min().date()),'end':str(d.date.max().date()),'days':len(d),'months':len(monthly(d)),'start_nav':nav0,'inputs':{n:sha(inputs/n) for n in files},'script_sha256':sha(Path(__file__)),'factors':sources,'checks':checks,'limitations':warnings,'independent_full_ledger_validation':verified is not None}
    if verified is not None:
        provenance['ledger_inputs']={name:sha(ledger_dir/name) for name in ['daily.parquet','position_audit.parquet','pnl.parquet','executions.parquet']}
        if signals.exists():provenance['label_signal_sha256']=sha(signals)
        if caps is not None:provenance['market_cap_panel']={'path':str(market_caps),'sha256':sha(Path(market_caps)),'columns':['permno','eom','me']}
    (out/'validation.json').write_text(json.dumps(provenance,indent=2))
    import html
    body='<!doctype html><html lang="en"><meta charset="utf-8"><title>FIAM final reporting</title><style>body{font:15px Arial;color:#173047;max-width:1300px;margin:35px auto;padding:20px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:8px;border-bottom:1px solid #dbe3e8;text-align:left}th{background:#edf4f6}.notice{background:#fff4dc;padding:16px}h1,h2{color:#126e82}@media print{.plotly-graph-div{break-inside:avoid}}</style>'
    body+=f'<h1>FIAM final reporting: {html.escape(inputs.name)}</h1><p>{d.date.min():%Y-%m-%d} to {d.date.max():%Y-%m-%d} | {len(d)} trading observations</p>'
    status='' if verified is None else f" Month-end market-cap verification: {checks['month_end_market_cap_verification']}. Execution-day market-cap compliance: {checks['execution_day_market_cap_compliance']}."
    body+='<p class="notice">Accounting checks passed. This is not a certification of full mandate compliance.'+html.escape(status)+' Detailed-ledger verification status and outstanding limitations are listed below.</p><h2>Section 9.1</h2><p>Net performance except the first IR and tracking error, which are gross. Percentages are in percent units. Parentheses contain standard errors.</p>'+table.to_html(index=False,escape=True)
    years=len(d)/252
    body+=f'<p>Section 9.2 CAGR: net strategy {((1+d.ret).prod()**(1/years)-1)*100:.3f}%; benchmark {((1+d.hurdle).prod()**(1/years)-1)*100:.3f}%. Annualised table return is the arithmetic mean times 252.</p>'
    body+='<h2>Section 9.4: eight required exhibits</h2><p>Hover for values; drag or scroll to zoom; use the toolbar to pan, reset, or export PNG. The report works offline.</p>'
    for i,f in enumerate(figs,1):
        f.write_json(out/f'exhibit_{i}.json')
        fragment=f.to_html(full_html=False,include_plotlyjs=(i==1),div_id=f'exhibit-{i}',config={'scrollZoom':True,'responsive':True,'displaylogo':False,'toImageButtonOptions':{'format':'png','filename':f'exhibit_{i}','scale':2}})
        body+=re.sub(r'[\u3400-\u9fff]',lambda m:'\\u%04x'%ord(m.group()),fragment)
    if attribution is not None:body+='<h2>FF5 + momentum attribution</h2><p>Official monthly factors; all test months included. Coefficients and standard errors are in return-decimal units. Alpha is monthly in coefficient and annual in annualised_coefficient. Annual mean contributions are percentage points, not compounded attribution.</p>'+attribution.to_html(index=False,float_format=lambda v:f'{v:.5f}')
    for name in ['hit_rate.csv','alpha_decay.csv','sizing_vs_selection.csv']:
        if (inputs/name).exists():
            q=pd.read_csv(inputs/name).rename(columns={'Unnamed: 0':'Leg'});q.to_csv(out/name,index=False)
            body+='<h2>'+html.escape(name.replace('.csv','').replace('_',' ').title())+'</h2><p>Supplied diagnostic; not independently recomputed without position and signal histories.</p>'+q.to_html(index=False,escape=True,na_rep='n/a')
            provenance['inputs'][name]=sha(inputs/name)
    body+='<h2>Checks</h2>'+pd.DataFrame(checks.items(),columns=['Check','Result']).to_html(index=False)+'<h2>Provenance and limitations</h2><ul>'+''.join('<li>'+html.escape(w)+'</li>' for w in warnings)+'</ul></html>'
    if re.search(r'[\u3400-\u9fff]',body):raise ValueError('Report contains non-English CJK text')
    (out/'report.html').write_text(body,encoding='utf-8');(out/'validation.json').write_text(json.dumps(provenance,indent=2))
    print(json.dumps(checks,indent=2));print('Report:',out/'report.html')
    return table,provenance


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True,help='06_final/output/test_M or another exported run')
    p.add_argument('--output',type=Path,default=Path('output_final'))
    p.add_argument('--factor-cache',type=Path,help='Download/cache official FF5 + momentum ZIPs and run attribution')
    p.add_argument('--start-nav',type=float,default=1e9)
    p.add_argument('--ledger-dir',type=Path,help='06_final/data/runs/test_M from patched engine')
    p.add_argument('--require-verified',action='store_true',help='Require a reconciled ledger, complete labels/liquidity and complete month-end market-cap matches')
    p.add_argument('--market-caps',type=Path,default=DEFAULT_MARKET_CAPS,help='Monthly panel with permno, eom, me (default: configured model_table.parquet)')
    a=p.parse_args();generate(a.inputs,a.output,a.factor_cache,a.start_nav,a.ledger_dir,a.require_verified,a.market_caps)


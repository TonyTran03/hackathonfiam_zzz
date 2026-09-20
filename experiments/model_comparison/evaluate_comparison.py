"""Identical portfolio policy and explicit accounting for every forecast."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import config as C
import baseline_portfolio as P

ROOT=Path(__file__).resolve().parent;RES=ROOT/'results'
MODELS=['ols','ridge','lasso','en','gbm_missing','gbm_median','gbm_median_matched','annual_blend']
COSTS=[0,10,20,30,50]

def calendar_smooth(pred,months):
    result=pd.Series(index=pred.index,dtype=float)
    for _,g in pred.groupby('permno',sort=False):
        s=pd.Series(g.score.values,index=pd.PeriodIndex(g.target_month,freq='M'))
        full=s.reindex(pd.period_range(s.index.min(),s.index.max(),freq='M'))
        result.loc[g.index]=full.rolling(months,min_periods=1).mean().reindex(s.index).values
    return result

def cash_adjusted_forward(d,bm):
    rf=(d.ret-d.ret_exc).groupby(d.eom.dt.to_period('M').astype(str)).agg(['median','min','max'])
    assert ((rf['max']-rf['min']).abs()<1e-8).all(),'source RF varies within month'
    src=d.target_month.map(rf['median'])
    raw=d[C.TARGET]+src
    nxt=d[['permno','eom','ret','ret_exc']].copy();nxt['target_month']=nxt.eom.dt.to_period('M').astype(str)
    check=d[['permno','target_month',C.TARGET]].merge(nxt[['permno','target_month','ret_exc']],on=['permno','target_month'],how='left',validate='one_to_one')
    ok=check[C.TARGET].notna()&check.ret_exc.notna()
    diff=(check.loc[ok,C.TARGET]-check.loc[ok,'ret_exc']).abs()
    assert diff.max()<1e-8,'forward target mismatch'
    return pd.DataFrame({'permno':d.permno,'target_month':d.target_month,'raw_forward':raw}),{'source_rf_range_max':float((rf['max']-rf['min']).max()),'forward_pairs_checked':int(ok.sum()),'max_forward_difference':float(diff.max())}

def metrics(m,bps):
    total=m[f'total_{bps}'];active=total-m.hurdle;ex=total-m.cash
    reg=sm.OLS(ex,sm.add_constant(m.market-m.cash)).fit(cov_type='HAC',cov_kwds={'maxlags':3},use_t=True)
    wealth=(1+total).cumprod();peak=np.maximum.accumulate(np.r_[1.,wealth.values])[1:]
    return {'cost_bps':bps,'months':len(m),'cagr':float(wealth.iloc[-1]**(12/len(m))-1),'cumulative_return':float(wealth.iloc[-1]-1),'ir':float(np.sqrt(12)*active.mean()/active.std(ddof=1)),'sharpe':float(np.sqrt(12)*ex.mean()/ex.std(ddof=1)),'alpha_annual':float(reg.params.iloc[0]*12),'alpha_t':float(reg.tvalues.iloc[0]),'beta':float(reg.params.iloc[1]),'beta_se':float(reg.bse.iloc[1]),'max_drawdown':float((wealth/peak-1).min()),'hit_rate':float((active>0).mean()),'mean_traded_nav':float(m[f'traded_{bps}'].mean()),'mean_gross':float(m.gross.mean()),'min_net':float(m.net.min()),'max_net':float(m.net.max()),'max_weight':float(m.max_weight.max()),'missing_positions':int(m.missing_n.sum()),'mean_missing_gross':float(m.missing_gross.mean()),'max_missing_gross':float(m.missing_gross.max())}

def score_book(h,bm):
    rows=[]
    for month,g in h.groupby('target_month',sort=True):
        b=bm.loc[month];w=g.weight;raw=g.raw_forward.fillna(0.)
        spread=float((w*(raw-b.cash_monthly)).sum());gross=float(b.cash_monthly+spread)
        rows.append(dict(target_month=month,cash=b.cash_monthly,hurdle=b.hurdle_monthly,market=b.sp500_ret,total_gross=gross,long_contribution=float((w[w>0]*(raw[w>0]-b.cash_monthly)).sum()),short_contribution=float((w[w<0]*(raw[w<0]-b.cash_monthly)).sum()),gross=float(w.abs().sum()),net=float(w.sum()),n=len(g),max_weight=float(w.abs().max()),missing_n=int(g.raw_forward.isna().sum()),missing_gross=float(w[g.raw_forward.isna()].abs().sum())))
    m=pd.DataFrame(rows)
    assert len(m)==68 and m.n.between(100,500).all() and (m.gross<=2+1e-8).all() and m.net.between(-.5,.5).all()
    assert not h.duplicated(['permno','target_month']).any()
    assert h.groupby('target_month').weight.apply(lambda w:(w>0).any() and (w<0).any()).all()
    groups={t:g.set_index('permno') for t,g in h.groupby('target_month')}
    for bps in COSTS:
        prev=None;prev_ret=None;prev_total=0.;trades=[];totals=[]
        for r in m.itertuples():
            g=groups[r.target_month];w=g.weight
            if prev is None:change=float(w.abs().sum())
            else:
                drift=prev*(1+prev_ret)/(1+prev_total)
                change=float(w.subtract(drift,fill_value=0).abs().sum())
            net=r.total_gross-change*bps/10000
            assert net>-1,'bankrupt portfolio'
            trades.append(change);totals.append(net)
            prev=w;prev_ret=g.raw_forward.fillna(0);prev_total=net
        m[f'traded_{bps}']=trades;m[f'total_{bps}']=totals
    # Fixed-book marking scenario, NOT a bound or alternate selection backtest.
    # Missing long -> -100%, missing short -> +100%; 20bp baseline trading charge unchanged.
    m['adverse_missing_total_20']=m.total_20-m.missing_gross
    return m

def prediction_stats(p,cols,universe='all'):
    p=p[p[C.TARGET].notna()];y=p[C.TARGET].to_numpy();rows=[]
    for c in cols:
        monthly=p.groupby('target_month').apply(lambda g:g[c].corr(g[C.TARGET],method='spearman'),include_groups=False)
        rows.append({'model':c,'universe':universe,'rows':len(p),'oos_r2':np.nan if c=='annual_blend' else float(1-np.sum((y-p[c].values)**2)/np.sum(y*y)),'mean_monthly_ic':float(monthly.mean()),'positive_ic_share':float((monthly.dropna()>0).mean()),'months_with_defined_ic':int(monthly.notna().sum()),'constant_forecast_months':int((p.groupby('target_month')[c].nunique()<=1).sum())})
    return rows

def evaluate(d,p):
    print('Evaluating identical portfolios',flush=True)
    P.smooth_scores=calendar_smooth
    bm=pd.read_csv(C.BENCHMARK_CSV).set_index('target_month')
    forward,audit=cash_adjusted_forward(d,bm)
    # One shared eligibility screen; no realized outcome is used by screen().
    screened=P.screen(p.copy()).merge(forward,on=['permno','target_month'],how='left',validate='one_to_one')
    predrows=prediction_stats(p,MODELS)+prediction_stats(screened,MODELS,'eligible')
    pd.DataFrame(predrows).to_csv(RES/'prediction_metrics.csv',index=False)
    screened[C.TARGET]=screened.raw_forward.fillna(0.)-screened.target_month.map(bm.cash_monthly)
    market=bm.sp500_ret-bm.cash_monthly
    summaries=[];monthly=[];yearly=[];checks=[];missing_positions=[]
    for name in MODELS:
        P.MODEL=name
        h=P.make_book(screened.copy(),3,2.5,market=market)
        keep=['target_month','permno','ticker','company_name','weight','raw_forward']
        h[keep].to_parquet(RES/f'holdings_{name}.parquet',index=False)
        missing_positions.append(h.loc[h.raw_forward.isna(),keep].assign(model=name))
        m=score_book(h,bm);m['model']=name;monthly.append(m)
        for bps in COSTS:
            s=metrics(m,bps);s['model']=name;summaries.append(s)
        for year,g in m.groupby(m.target_month.str[:4]):
            yearly.append({'model':name,'year':year,'months':len(g),'gross_return':float((1+g.total_gross).prod()-1),'net_return_20bps':float((1+g.total_20).prod()-1),'benchmark_return':float((1+g.hurdle).prod()-1),'sp500_price_return':float((1+g.market).prod()-1)})
        base=metrics(m,20)
        checks.append({'model':name,'months':len(m),'min_positions':int(m.n.min()),'max_positions':int(m.n.max()),'max_gross':float(m.gross.max()),'min_net':float(m.net.min()),'max_net':float(m.net.max()),'no_duplicate_positions':True,'both_legs_every_month':True,'missing_return_positions':int(m.missing_n.sum()),'adverse_missing_cagr':float((1+m.adverse_missing_total_20).prod()**(12/len(m))-1)})
        print(name,'IR20',round(base['ir'],3),'CAGR',round(base['cagr'],3),'beta',round(base['beta'],3),'missing',base['missing_positions'],flush=True)
    pd.concat(missing_positions,ignore_index=True).to_csv(RES/'missing_return_positions.csv',index=False)
    s=pd.DataFrame(summaries);s.to_csv(RES/'portfolio_metrics.csv',index=False)
    mm=pd.concat(monthly,ignore_index=True);mm.to_csv(RES/'monthly_returns.csv',index=False)
    pd.DataFrame(yearly).to_csv(RES/'yearly_returns.csv',index=False)
    audit['portfolio_checks']=checks;audit['preprocessing_observed_values_identical']=True;audit['prediction_universe_independent_of_future_label']=True
    (RES/'verification.json').write_text(json.dumps(audit,indent=2))
    bootstrap(mm)
    plot_results(mm,s)

def bootstrap(mm):
    p=mm.pivot(index='target_month',columns='model',values='total_20');n=len(p);rng=np.random.default_rng(2026)
    starts=rng.integers(0,n,size=(2000,int(np.ceil(n/6))))
    ix=((starts[:,:,None]+np.arange(6))%n).reshape(2000,-1)[:,:n]
    rows=[]
    for a,b in [('gbm_missing','ridge'),('gbm_missing','gbm_median'),('gbm_missing','gbm_median_matched'),('annual_blend','ridge')]:
        diff=(p[a]-p[b]).to_numpy();draw=diff[ix].mean(axis=1)*12
        rows.append({'model_a':a,'model_b':b,'annualized_arithmetic_mean_difference':float(diff.mean()*12),'ci_low':float(np.quantile(draw,.025)),'ci_high':float(np.quantile(draw,.975)),'method':'paired circular 6-month block bootstrap; 2000 draws; 68 months'})
    pd.DataFrame(rows).to_csv(RES/'paired_uncertainty.csv',index=False)

def plot_results(mm,s):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(2,1,figsize=(11,8),sharex=True)
    shown=['ridge','lasso','en','gbm_missing','gbm_median','annual_blend']
    for name in shown:
        m=mm[mm.model==name];x=pd.to_datetime(m.target_month);wealth=(1+m.total_20).cumprod();peak=np.maximum.accumulate(np.r_[1,wealth.values])[1:]
        axs[0].plot(x,wealth,label=name);axs[1].plot(x,100*(wealth/peak-1),label=name)
    axs[0].plot(x,(1+m.hurdle).cumprod(),'k--',label='cash + 4% hurdle')
    axs[0].set(title='Controlled comparison | 20 bps per dollar traded',ylabel='Growth of $1');axs[0].legend(ncol=3,fontsize=8)
    axs[1].set(ylabel='Drawdown (%)',xlabel='Holding month')
    for ax in axs:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(RES/'comparison.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8))
    for name in shown:
        g=s[s.model==name];ax.plot(g.cost_bps,g.ir,marker='o',label=name)
    ax.axhline(0,color='black',linewidth=.7);ax.set(xlabel='Cost per dollar traded (basis points)',ylabel='Annualized information ratio',title='Trading-cost sensitivity | same portfolio rules');ax.legend(ncol=3,fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(RES/'cost_sensitivity.png',dpi=160);plt.close(fig)

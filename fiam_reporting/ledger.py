"""Validate audit exports and recompute position-based Section 9 outputs."""
import numpy as np
import pandas as pd


MIN_SHORT_ME=500.0
MARKET_CAP_BASIS='panel me (US$ million) at the immediately preceding calendar month-end'


def validate_market_caps(caps):
    """Return a clean permno/eom/me panel; reject anything that would make a month-end match ambiguous."""
    missing=[c for c in ['permno','eom','me'] if c not in caps]
    if missing:raise ValueError('Market-cap panel missing columns: '+', '.join(missing))
    caps=caps[['permno','eom','me']].copy()
    if caps[['permno','eom']].isna().any().any():raise ValueError('Market-cap panel has missing permno/eom')
    caps['eom']=pd.to_datetime(caps.eom).astype('datetime64[ns]')
    if (caps.eom!=caps.eom.dt.normalize()+pd.offsets.MonthEnd(0)).any():raise ValueError('Market-cap panel eom values must be calendar month-ends')
    if caps.duplicated(['permno','eom']).any():raise ValueError('Duplicate permno/eom keys in market-cap panel')
    if not np.isfinite(caps.me.to_numpy(float)).all():raise ValueError('Missing or non-finite me in market-cap panel')
    if (caps.me<=0).any():raise ValueError('Nonpositive me in market-cap panel')
    caps['permno']=caps.permno.astype('int64')
    return caps


def load_market_caps(path):
    return validate_market_caps(pd.read_parquet(path,columns=['permno','eom','me']))


def attach_month_end_caps(frame,caps):
    """Match each row to panel me at the calendar month-end immediately before its date.

    No older month is carried forward and no later month is used; unmatched rows stay NaN with a status.
    The engine's estimate is never a fallback; it is retained as engine_market_cap_million.
    """
    out=frame.copy().reset_index(drop=True)
    out['engine_market_cap_million']=out.pop('market_cap_million') if 'market_cap_million' in out else np.nan
    out['market_cap_month_end']=(pd.to_datetime(out.date).dt.normalize()-pd.offsets.MonthEnd(1)).astype('datetime64[ns]')
    if caps is None:
        out['market_cap_million']=np.nan;out['market_cap_match']='panel_unavailable';return out
    key=caps.rename(columns={'eom':'market_cap_month_end','me':'market_cap_million'})
    out=out.merge(key,on=['permno','market_cap_month_end'],how='left',validate='many_to_one')
    first=out.permno.map(caps.groupby('permno').eom.min())
    out['market_cap_match']=np.select([out.market_cap_million.notna(),first<out.market_cap_month_end],
                                      ['matched','missing_prior_month_end'],'no_earlier_panel_value')
    return out


def finite(x):return float(x) if np.isfinite(x) else None


def close(a,b,label,atol=.02):
    if not np.allclose(a,b,rtol=1e-9,atol=atol,equal_nan=False):
        raise ValueError(label+' does not reconcile')


def derive(d,a,pnl,executions,labels,market_caps=None):
    d=d.copy();a=a.copy();pnl=pnl.copy();ex=executions.copy()
    for frame in [d,a,pnl,ex]:frame['date']=pd.to_datetime(frame.date)
    dates=pd.DatetimeIndex(d.date);byday=d.set_index('date')
    if d.date.duplicated().any() or a.duplicated(['date','permno']).any() or pnl.duplicated(['date','permno']).any():raise ValueError('Duplicate daily/position/P&L keys')
    for frame in [a,pnl,ex]:
        if not frame.date.isin(dates).all():raise ValueError('Ledger dates outside return sample')
    for frame,cols in [(a,['pre_usd','pre_nav','position_usd','nav','pre_weight','weight']),
                       (pnl,['x','r','pnl']),(ex,['trade_usd','before_usd','after_usd','adv_dollars'])]:
        if not np.isfinite(frame[cols].to_numpy(float)).all():raise ValueError('Non-finite accounting fields')
    if (a[['pre_nav','nav']]<=0).any().any():raise ValueError('Nonpositive NAV')
    close(a.pre_weight,a.pre_usd/a.pre_nav,'Pre weights',1e-10)
    close(a.weight,a.position_usd/a.nav,'Post weights',1e-10)
    close(a.nav,a.date.map(byday.nav),'Position NAV')
    close(pnl.pnl,pnl.x*pnl.r,'Stock P&L')
    daily_pnl=pnl.groupby('date').pnl.sum().reindex(dates,fill_value=0).to_numpy()
    prev=np.r_[float(d.nav.iloc[0]/(1+d.ret.iloc[0])),d.nav.iloc[:-1]]
    close(daily_pnl+d.cash_income.to_numpy()-d.cost.to_numpy()-d.borrow.to_numpy(),d.nav.to_numpy()-prev,'Full P&L bridge')
    if 'pnl_kind' not in pnl:raise ValueError('Rerun patched engine: pnl_kind/delisting records required')
    stubs=pnl[pnl.pnl_kind=='delisting'].groupby('date').pnl.sum().reindex(dates,fill_value=0)
    close(stubs,d.stub_pnl,'Delisting P&L')
    calc=.5*(a.weight-a.pre_weight).abs().groupby(a.date).sum().reindex(dates,fill_value=0)
    close(calc,d.turnover,'Section 9.3 turnover',1e-10)
    pos=a[a.position_usd!=0].copy()
    g=pos.groupby('date')
    for observed,expected,label in [(g.weight.sum().reindex(dates,fill_value=0),d.net,'Net exposure'),
        (g.weight.apply(lambda x:x.abs().sum()).reindex(dates,fill_value=0),d.gross,'Gross exposure'),
        (g.size().reindex(dates,fill_value=0),d.n_long+d.n_short,'Position count')]:close(observed,expected,label,1e-9)
    close(ex.after_usd-ex.before_usd,ex.trade_usd,'Executed trade dollars')
    # Sequential fills may net against each other. Reconcile net fills to each daily snapshot.
    net=ex.groupby(['date','permno']).trade_usd.sum()
    expected=a.set_index(['date','permno']);joined=expected.join(net.rename('fills'),how='outer').fillna({'fills':0,'pre_usd':0,'position_usd':0})
    close(joined.position_usd-joined.pre_usd,joined.fills,'Executed trades to daily positions',atol=1.01)
    names=labels.drop_duplicates('permno').set_index('permno')
    avg=pos.groupby('permno').weight.sum()/len(d)
    average=avg.rename('avg_weight').to_frame().join(names).reset_index()
    average['avg_weight_pct']=average.avg_weight*100
    top=pd.concat([average[average.avg_weight>0].nlargest(10,'avg_weight'),average[average.avg_weight<0].nsmallest(10,'avg_weight')])
    contribution=(pnl.groupby('permno').pnl.sum()/prev[0]*100).rename('contribution_pct_of_start_nav').to_frame().join(names).reset_index()
    col='contribution_pct_of_start_nav'
    contributors=pd.concat([contribution[contribution[col]>0].nlargest(10,col),contribution[contribution[col]<0].nsmallest(10,col)])
    # Spell = consecutive end-of-day held dates on the same side. Boundary spells are censored.
    pos['day_index']=pos.date.map(pd.Series(np.arange(len(d)),index=dates));pos['side']=np.sign(pos.position_usd)
    q=pos.sort_values(['permno','day_index'])
    breaks=q.permno.ne(q.permno.shift()) | q.day_index.ne(q.day_index.shift()+1) | q.side.ne(q.side.shift())
    q['spell']=breaks.cumsum();q['abs_usd']=q.position_usd.abs()
    spells=q.groupby('spell').agg(permno=('permno','first'),days=('day_index','size'),mean_abs_usd=('abs_usd','mean'),first=('day_index','min'),last=('day_index','max'))
    spells['boundary_censored']=(spells['first']==0)|(spells['last']==len(d)-1)
    holding=float(np.average(spells.days,weights=spells.mean_abs_usd))
    # Floor applies on every opening/addition to a short, not passive drift below the floor.
    ex['short_added_usd']=np.maximum(-ex.after_usd,0)-np.maximum(-ex.before_usd,0)
    # Market caps come only from prior-month-end panel me; the engine estimate is kept for reference.
    shorts=attach_month_end_caps(ex[ex.short_added_usd>1e-8],market_caps)
    shorts['month_end_floor_pass']=shorts.market_cap_million>=MIN_SHORT_ME
    pos=attach_month_end_caps(pos,market_caps)
    ex['participation']=ex.trade_usd.abs()/ex.adv_dollars
    ex['daily_name_participation']=ex.groupby(['date','permno']).participation.transform('sum')
    # actual book observations for exhibit 8; preserve missing liquidity rather than filling it
    pos['days_adv']=pos.position_usd.abs()/pos.adv_dollars
    pos['liquidity_known']=np.isfinite(pos.adv_dollars)&(pos.adv_dollars>0)
    held=pos[pos.position_usd<0]
    caps_ok=market_caps is not None and (shorts.market_cap_match=='matched').all() and (held.market_cap_match=='matched').all()
    def counts(q):return {k:int(v) for k,v in q.market_cap_match.value_counts().items() if k!='matched'}
    summary={'holding_period_days':holding,'average_position_size_million':float(pos.position_usd.abs().mean()/1e6),
      'turnover_per_daily_rebalance_pct':float(calc.mean()*100),'turnover_annual_pct':float(calc.mean()*25200),
      'market_cap_basis':MARKET_CAP_BASIS if market_caps is not None else 'unavailable',
      'month_end_market_cap_verification':'complete' if caps_ok else 'incomplete',
      'execution_day_market_cap_compliance':'unverified',
      'short_openings':int(len(shorts)),
      'short_openings_month_end_unmatched':int((shorts.market_cap_match!='matched').sum()),
      'short_openings_month_end_unmatched_by_status':counts(shorts),
      'short_openings_month_end_below_500m':int((shorts.market_cap_match=='matched').sum()-shorts.month_end_floor_pass.sum()),
      'short_openings_month_end_min_market_cap_million':finite(shorts.market_cap_million.min()),
      'short_held_name_days':int(len(held)),
      'short_held_month_end_unmatched':int((held.market_cap_match!='matched').sum()),
      'short_held_month_end_unmatched_by_status':counts(held),
      'short_held_month_end_below_500m':int((held.market_cap_million<MIN_SHORT_ME).sum()),
      'short_book_median_market_cap_million':finite(held.market_cap_million.median()) if caps_ok else None,
      'position_liquidity_unknown':int((~pos.liquidity_known).sum()),'short_execution_adv_fallbacks':int((~shorts.adv_observed.astype(bool)).sum()),
      'execution_name_days_above_10pct_adv':int((ex.groupby(['date','permno']).participation.sum()>.1+1e-10).sum()),
      'boundary_censored_spells':int(spells.boundary_censored.sum()),'delisting_pnl_dollars':float(stubs.sum()),
      'turnover_verified':True,'stock_pnl_bridge_verified':True,'daily_position_aggregates_verified':True}
    return dict(daily=d,positions=pos,shorts=shorts,held_shorts=held,executions=ex,top=top,contributors=contributors,
                all_average=average,all_contributors=contribution,spells=spells,summary=summary)


def load(directory,d,labels,market_caps=None):
    required=['daily.parquet','position_audit.parquet','pnl.parquet','executions.parquet']
    for name in required:
        if not (directory/name).exists():raise ValueError('Missing '+str(directory/name)+'; rerun patched f03_engine.py')
    daily=pd.read_parquet(directory/'daily.parquet')
    if 'audit_version' not in daily or not daily.audit_version.eq(1).all():raise ValueError('Patched engine audit_version=1 required')
    if not pd.to_datetime(daily.date).reset_index(drop=True).equals(pd.to_datetime(d.date).reset_index(drop=True)):raise ValueError('Stale exports: daily date sets differ')
    for col in ['nav','ret','ret_gross','cost','borrow']:close(daily[col],d[col],'Ledger versus export '+col)
    return derive(daily,pd.read_parquet(directory/'position_audit.parquet'),pd.read_parquet(directory/'pnl.parquet'),pd.read_parquet(directory/'executions.parquet'),labels,market_caps)

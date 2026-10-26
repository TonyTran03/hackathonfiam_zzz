"""Compare two 06_final runs (for example the original test_M and test_M_audited); report only, never edits either run.

Identical exports do not prove identical portfolios. Daily holdings, executions and per-stock P&L
are compared only when both runs' ledger directories are supplied and contain those files;
otherwise each is listed as not performed. The status is never 'match' unless every comparison ran.
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Exports keyed by these columns; numeric columns are compared after aligning on the keys.
EXPORT_KEYS={'daily_returns.csv':['date'],'monthly_returns.csv':['month'],'calendar_years.csv':['year'],
             'rolling_beta.csv':['date'],'formation_positions.csv':['date','permno'],
             'top_holdings.csv':['permno'],'contributors.csv':['permno'],'standard_table.csv':['metric','units']}  # IR metrics repeat with daily/monthly units
# Engine ledger files and their natural keys (executions: at most one fill per stage per stock-day).
LEDGER_KEYS={'position_audit.parquet':['date','permno'],'executions.parquet':['date','permno','stage'],'pnl.parquet':['date','permno']}
LEDGER_LABELS={'position_audit.parquet':'daily pre/post holdings','executions.parquet':'executions (fills)','pnl.parquet':'per-stock P&L'}
# Columns whose definition changed in the audited engine, so a difference is expected rather than a mismatch.
TURNOVER='audited engine computes Section 9.3 turnover from pre/post weights; original field was a dollar-trade proxy'
REDEFINED={'daily_returns.csv':{'turnover':TURNOVER}}
# Summary rows recomputed from the redefined turnover. Exempt only in the listed column, and only when every differing row is listed.
REDEFINED_ROWS={'standard_table.csv':{'strategy':{'One-way turnover','Average holding period','Holding period, approximation'}}}


def compare_frame(name,a,b,keys,rtol):
    row={'file':name,'keys':keys,'rows_original':len(a),'rows_other':len(b),
         'columns_only_original':sorted(set(a)-set(b)),'columns_only_other':sorted(set(b)-set(a))}
    missing={side:[k for k in keys if k not in f] for side,f in [('original',a),('other',b)]}
    if any(missing.values()):return {**row,'status':'missing_key_columns','missing_key_columns':missing,'match':False}
    dups={side:int(f.duplicated(keys).sum()) for side,f in [('original',a),('other',b)]}
    if any(dups.values()):return {**row,'status':'duplicate_keys','duplicate_keys':dups,'match':False}
    # Two empty tables agree trivially; that is no evidence, so it is an issue rather than a comparison.
    if a.empty and b.empty:return {**row,'status':'empty_in_both','match':False}
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index()
    row.update({'status':'compared','keys_identical':bool(a.index.equals(b.index)),
         'only_original':int((~a.index.isin(b.index)).sum()),'only_other':int((~b.index.isin(a.index)).sum()),'columns':{}})
    common=a.index.intersection(b.index)
    for c in [c for c in a if c in b]:
        x,y=a.loc[common,c],b.loc[common,c];bad_keys=[]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            x,y=x.to_numpy(float),y.to_numpy(float);both_nan=np.isnan(x)&np.isnan(y);diff=np.abs(x-y)
            scale=np.maximum(np.abs(x),np.abs(y));rel=np.divide(diff,scale,out=np.zeros_like(diff),where=scale>0)
            bad=(np.isnan(x)!=np.isnan(y))|(~both_nan&~np.isclose(x,y,rtol=rtol,atol=0,equal_nan=True))
            entry={'max_abs_diff':float(np.nanmax(np.where(both_nan,0,diff))) if len(x) else 0.,'max_rel_diff':float(np.nanmax(np.where(both_nan,0,rel))) if len(x) else 0.,
                   'nan_mismatch':int((np.isnan(x)!=np.isnan(y)).sum())}
        else:
            bad=(~((x.isna()&y.isna())|(x.astype(str)==y.astype(str)))).to_numpy()
            entry={}
        bad_keys=list(common[bad])
        entry.update({'unequal_values':len(bad_keys),'match':not bad_keys,'unequal_keys':[' | '.join(map(str,k)) if isinstance(k,tuple) else str(k) for k in bad_keys][:20]})
        if c in REDEFINED.get(name,{}):entry['expected_difference']=REDEFINED[name][c]
        rows_ok=REDEFINED_ROWS.get(name,{}).get(c,set())
        if bad_keys and rows_ok and {k[0] if isinstance(k,tuple) else k for k in bad_keys}<=rows_ok:
            entry['expected_difference']='only turnover-derived rows differ: '+', '.join(entry['unequal_keys'])
        row['columns'][c]=entry
    row['match']=bool(row['columns']) and row['keys_identical'] and all(v['match'] or 'expected_difference' in v for v in row['columns'].values())
    return row


def compare_files(names,left,right,keys,read,rtol):
    rows,issues=[],[]
    for name in names:
        a,b=left/name,right/name
        if not a.exists() or not b.exists():
            where='original' if not a.exists() and b.exists() else 'other' if a.exists() else 'both'
            issues.append({'file':name,'status':'missing_in_'+where});continue
        if name not in keys:issues.append({'file':name,'status':'unsupported: no comparison key defined'});continue
        r=compare_frame(name,read(a),read(b),keys[name],rtol)
        (rows if r['status']=='compared' else issues).append(r)
    return rows,issues


def compare(original,other,original_ledger=None,other_ledger=None,rtol=1e-9):
    for d in [original,other]:
        if not Path(d).is_dir():raise ValueError('Run export directory not found: '+str(d))
    names=sorted({p.name for p in original.glob('*.csv')}|{p.name for p in other.glob('*.csv')})
    exports,issues=compare_files(names,original,other,EXPORT_KEYS,pd.read_csv,rtol)
    ledger_rows,not_performed=[],[]
    if original_ledger is None or other_ledger is None:
        missing=[s for s,d in [('--original-ledger',original_ledger),('--other-ledger',other_ledger)] if d is None]
        not_performed=[{'file':n,'status':'not performed: '+' and '.join(missing)+' not supplied'} for n in LEDGER_KEYS]
    else:
        ledger_rows,ledger_issues=compare_files(list(LEDGER_KEYS),Path(original_ledger),Path(other_ledger),LEDGER_KEYS,pd.read_parquet,rtol)
        not_performed=[{**i,'status':'not performed: '+i['status']} for i in ledger_issues]
    compared=exports+ledger_rows
    shared_match=bool(compared) and all(r['match'] for r in compared)
    column_gaps=[{'file':r['file'],'columns_only_original':r['columns_only_original'],'columns_only_other':r['columns_only_other']}
                 for r in compared if r['columns_only_original'] or r['columns_only_other']]
    holdings=next((r for r in ledger_rows if r['file']=='position_audit.parquet'),None)
    if holdings is not None:
        q=pd.read_parquet(Path(original_ledger)/'position_audit.parquet')
        held=int((q.position_usd!=0).sum()) if 'position_usd' in q else 0
        holdings['nonzero_positions_original']=held
        if not held:
            ledger_rows.remove(holdings);compared.remove(holdings)
            not_performed.append({'file':'position_audit.parquet','status':'not performed: no nonzero holdings, so there is no holdings coverage to verify'})
            shared_match=bool(compared) and all(r['match'] for r in compared)
    ledger_done=len(ledger_rows)==len(LEDGER_KEYS)
    if not compared:status='nothing_compared'
    elif not shared_match:status='mismatch'
    elif issues or not_performed or column_gaps:status='partial_match'
    else:status='match'
    unverified=[LEDGER_LABELS[i['file']]+' ('+i['file']+'): '+i['status'] for i in not_performed]
    if not ledger_done:unverified.append('Stock-by-stock daily holdings, executions and P&L equivalence is not established; only the exports listed under files were compared.')
    return {'original':str(original),'other':str(other),'original_ledger':str(original_ledger) if original_ledger else None,
            'other_ledger':str(other_ledger) if other_ledger else None,'relative_tolerance':rtol,'status':status,
            'comparisons_performed':[r['file'] for r in compared],'shared_comparisons_match':shared_match,
            'ledger_compared':ledger_done,'portfolio_equivalence_verified':status=='match' and ledger_done,
            'issues':issues,'ledger_not_performed':not_performed,'column_gaps':column_gaps,'unverified':unverified,'files':compared}


def summary_table(result):
    out=[]
    for r in result['files']:
        for c,v in r['columns'].items():
            out.append({'file':r['file'],'column':c,'keys_identical':r['keys_identical'],'match':v['match'],
                        'max_abs_diff':v.get('max_abs_diff'),'max_rel_diff':v.get('max_rel_diff'),'unequal_values':v.get('unequal_values'),'unequal_keys':'; '.join(v.get('unequal_keys',[])),
                        'expected_difference':v.get('expected_difference','')})
    for r in result['issues']+result['ledger_not_performed']:out.append({'file':r['file'],'column':'','match':False,'expected_difference':r['status']})
    return pd.DataFrame(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,required=True,help='e.g. 06_final/output/test_M')
    p.add_argument('--other',type=Path,required=True,help='e.g. 06_final/output/test_M_audited')
    p.add_argument('--original-ledger',type=Path,help='Original run ledger directory (position_audit/executions/pnl parquet), if one exists')
    p.add_argument('--other-ledger',type=Path,help='Other run ledger directory, e.g. 06_final/data/runs/test_M_audited')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rtol',type=float,default=1e-9)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    r=compare(a.original,a.other,a.original_ledger,a.other_ledger,rtol=a.rtol)
    (a.output/'run_comparison.json').write_text(json.dumps(r,indent=2));summary_table(r).to_csv(a.output/'run_comparison.csv',index=False)
    print(json.dumps({k:v for k,v in r.items() if k!='files'},indent=2))
    # Exit 0 only when at least one comparison ran and every compared value matched; partial coverage is in status.
    sys.exit(0 if r['shared_comparisons_match'] else 1)

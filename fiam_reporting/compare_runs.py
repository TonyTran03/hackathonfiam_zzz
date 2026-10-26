"""Compare two 06_final exports (for example the original test_M and test_M_audited); report only, never edits either run.

Identical NAV paths do not prove identical portfolios, so every shared export is compared and
anything the original run did not export (daily holdings, executions) is listed as unverified.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Exports keyed by these columns; numeric columns are compared after aligning on the keys.
KEYS={'daily_returns.csv':['date'],'monthly_returns.csv':['month'],'calendar_years.csv':['year'],
      'rolling_beta.csv':['date'],'formation_positions.csv':['date','permno'],
      'top_holdings.csv':['permno'],'contributors.csv':['permno'],'standard_table.csv':['metric']}
# Columns whose definition changed in the audited engine, so a difference is expected rather than a mismatch.
TURNOVER='audited engine computes Section 9.3 turnover from pre/post weights; original field was a dollar-trade proxy'
REDEFINED={'daily_returns.csv':{'turnover':TURNOVER}}
# Summary rows recomputed from the redefined turnover; the strategy column is checked row by row instead.
REDEFINED_ROWS={'standard_table.csv':{'One-way turnover','Average holding period','Holding period, approximation'}}
LEDGER_ONLY=['position_audit.parquet (daily pre/post holdings)','executions.parquet (fills)','pnl.parquet (per-stock P&L)']


def compare_frame(name,a,b,atol):
    keys=KEYS.get(name)
    if keys is None or not set(keys)<=set(a)&set(b):return {'file':name,'status':'not compared: no shared key'}
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index()
    row={'file':name,'rows_original':len(a),'rows_other':len(b),'keys_identical':bool(a.index.equals(b.index)),
         'only_original':int((~a.index.isin(b.index)).sum()),'only_other':int((~b.index.isin(a.index)).sum()),
         'columns_only_original':sorted(set(a)-set(b)),'columns_only_other':sorted(set(b)-set(a)),'columns':{}}
    common=a.index.intersection(b.index)
    for c in [c for c in a if c in b]:
        x,y=a.loc[common,c],b.loc[common,c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            x,y=x.to_numpy(float),y.to_numpy(float);both_nan=np.isnan(x)&np.isnan(y);diff=np.abs(x-y)
            scale=np.maximum(np.abs(x),np.abs(y));rel=np.divide(diff,scale,out=np.zeros_like(diff),where=scale>0)
            entry={'max_abs_diff':float(np.nanmax(np.where(both_nan,0,diff))) if len(x) else 0.,'max_rel_diff':float(np.nanmax(np.where(both_nan,0,rel))) if len(x) else 0.,
                   'nan_mismatch':int((np.isnan(x)!=np.isnan(y)).sum())}
            entry['match']=bool(entry['nan_mismatch']==0 and np.allclose(x[~both_nan],y[~both_nan],rtol=atol,atol=0))
        else:
            bad=~((x.isna()&y.isna())|(x.astype(str)==y.astype(str)))
            entry={'unequal_values':int(bad.sum()),'match':not bad.any(),'unequal_keys':[str(k) for k in x.index[bad.to_numpy()]][:20]}
        if c in REDEFINED.get(name,{}):entry['expected_difference']=REDEFINED[name][c]
        rows_ok=REDEFINED_ROWS.get(name,set())
        if not entry['match'] and entry.get('unequal_keys') and set(entry['unequal_keys'])<=rows_ok:
            entry['expected_difference']='only turnover-derived rows differ: '+', '.join(entry['unequal_keys'])
        row['columns'][c]=entry
    row['match']=row['keys_identical'] and all(v['match'] or 'expected_difference' in v for v in row['columns'].values())
    return row


def compare(original,other,original_ledger=None,other_ledger=None,rtol=1e-9):
    files=sorted({p.name for p in original.glob('*.csv')}|{p.name for p in other.glob('*.csv')})
    rows=[];missing={'only_original':[],'only_other':[]}
    for name in files:
        a,b=original/name,other/name
        if not a.exists():missing['only_other'].append(name);continue
        if not b.exists():missing['only_original'].append(name);continue
        rows.append(compare_frame(name,pd.read_csv(a),pd.read_csv(b),rtol))
    has_ledger=original_ledger is not None and (original_ledger/'position_audit.parquet').exists()
    return {'original':str(original),'other':str(other),'relative_tolerance':rtol,'files':rows,'exports_missing':missing,
            'original_ledger_available':has_ledger,
            'unverified':[] if has_ledger else ['Original run has no detailed ledger: '+', '.join(LEDGER_ONLY)+' cannot be compared. Daily holdings and executions are verified only through aggregates (gross, net, counts, max weight, leg returns, costs) and monthly formation targets.'],
            'all_compared_match':all(r.get('match',False) for r in rows)}


def summary_table(result):
    out=[]
    for r in result['files']:
        for c,v in r.get('columns',{}).items():
            out.append({'file':r['file'],'column':c,'keys_identical':r['keys_identical'],'match':v['match'],
                        'max_abs_diff':v.get('max_abs_diff'),'max_rel_diff':v.get('max_rel_diff'),'unequal_values':v.get('unequal_values'),'unequal_keys':'; '.join(v.get('unequal_keys',[])),
                        'expected_difference':v.get('expected_difference','')})
    return pd.DataFrame(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,required=True,help='e.g. 06_final/output/test_M')
    p.add_argument('--other',type=Path,required=True,help='e.g. 06_final/output/test_M_audited')
    p.add_argument('--original-ledger',type=Path,help='Original run ledger directory, if one exists')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rtol',type=float,default=1e-9)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    r=compare(a.original,a.other,a.original_ledger,rtol=a.rtol)
    (a.output/'run_comparison.json').write_text(json.dumps(r,indent=2));summary_table(r).to_csv(a.output/'run_comparison.csv',index=False)
    print(json.dumps({k:v for k,v in r.items() if k!='files'},indent=2))

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import compare_runs as c


def daily(n=3,ret=.01):return pd.DataFrame({'date':pd.bdate_range('2021-01-04',periods=n).strftime('%Y-%m-%d'),'nav':100.,'ret':ret})


def ledger(n=2):
    dates=pd.bdate_range('2021-01-04',periods=n)
    return {'position_audit.parquet':pd.DataFrame({'date':dates,'permno':1,'position_usd':10.}),
            'executions.parquet':pd.DataFrame({'date':dates,'permno':1,'stage':'target','trade_usd':10.}),
            'pnl.parquet':pd.DataFrame({'date':dates,'permno':1,'pnl':1.})}


class CompareRunsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def run_dirs(self,frames_a,frames_b,tag='run'):
        a,b=self.root/(tag+'_a'),self.root/(tag+'_b')
        for d,frames in [(a,frames_a),(b,frames_b)]:
            d.mkdir()
            for name,df in frames.items():
                df.to_csv(d/name,index=False) if name.endswith('.csv') else df.to_parquet(d/name,index=False)
        return a,b

    def test_empty_directories_are_not_success(self):
        a,b=self.run_dirs({},{})
        r=c.compare(a,b)
        self.assertEqual(r['status'],'nothing_compared');self.assertFalse(r['shared_comparisons_match'])
        self.assertFalse(r['portfolio_equivalence_verified'])

    def test_only_unsupported_files_are_not_success(self):
        a,b=self.run_dirs({'notes.csv':pd.DataFrame({'x':[1]})},{'notes.csv':pd.DataFrame({'x':[1]})})
        r=c.compare(a,b)
        self.assertEqual(r['status'],'nothing_compared')
        self.assertTrue(r['issues'][0]['status'].startswith('unsupported'))

    def test_ledger_path_alone_does_not_clear_warning(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()})
        empty=self.root/'empty_ledger';empty.mkdir()
        r=c.compare(a,b,original_ledger=empty)
        self.assertEqual(r['status'],'partial_match');self.assertFalse(r['ledger_compared'])
        self.assertTrue(all('not performed' in i['status'] for i in r['ledger_not_performed']))
        self.assertTrue(any('not established' in u for u in r['unverified']))
        r=c.compare(a,b,original_ledger=empty,other_ledger=empty)
        self.assertFalse(r['ledger_compared']);self.assertEqual(len(r['ledger_not_performed']),3)
        self.assertTrue(all('missing_in_both' in i['status'] for i in r['ledger_not_performed']))

    def test_full_ledger_comparison_and_mismatch(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()})
        la,lb=self.root/'la',self.root/'lb';la.mkdir();lb.mkdir()
        for d,frames in [(la,ledger()),(lb,ledger())]:
            for n,df in frames.items():df.to_parquet(d/n,index=False)
        r=c.compare(a,b,la,lb)
        self.assertEqual(r['status'],'match');self.assertTrue(r['portfolio_equivalence_verified'])
        self.assertEqual(set(r['comparisons_performed']),{'daily_returns.csv'}|set(c.LEDGER_KEYS))
        changed=ledger();changed['executions.parquet'].loc[1,'trade_usd']=11.;changed['executions.parquet'].to_parquet(lb/'executions.parquet',index=False)
        r=c.compare(a,b,la,lb)
        self.assertEqual(r['status'],'mismatch');self.assertFalse(r['portfolio_equivalence_verified'])

    def test_missing_files_columns_and_duplicate_keys_are_reported(self):
        dup=pd.concat([daily(),daily(1)])
        a,b=self.run_dirs({'daily_returns.csv':daily(),'monthly_returns.csv':pd.DataFrame({'month':['2021-01'],'ret':[.01]}),'top_holdings.csv':pd.DataFrame({'permno':[1],'w':[.1]})},
                          {'daily_returns.csv':daily().assign(extra=1.),'top_holdings.csv':pd.DataFrame({'ticker':['A'],'w':[.1]})})
        r=c.compare(a,b)
        status={i['file']:i['status'] for i in r['issues']}
        self.assertEqual(status['monthly_returns.csv'],'missing_in_other')
        self.assertEqual(status['top_holdings.csv'],'missing_key_columns')
        self.assertEqual(r['column_gaps'][0]['columns_only_other'],['extra'])
        self.assertEqual(r['status'],'partial_match')
        a,b=self.run_dirs({'daily_returns.csv':dup},{'daily_returns.csv':daily()},tag='dup')
        r=c.compare(a,b)
        self.assertEqual(r['issues'][0]['status'],'duplicate_keys');self.assertEqual(r['status'],'nothing_compared')

    def ledgers(self,frames_a,frames_b):
        la,lb=self.root/'la',self.root/'lb'
        for d,frames in [(la,frames_a),(lb,frames_b)]:
            d.mkdir()
            for n,df in frames.items():df.to_parquet(d/n,index=False)
        return la,lb

    def test_empty_ledger_files_are_not_equivalence(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()})
        empty={n:df.iloc[:0] for n,df in ledger().items()}
        r=c.compare(a,b,*self.ledgers(empty,empty))
        self.assertEqual(r['status'],'partial_match');self.assertFalse(r['ledger_compared'])
        self.assertFalse(r['portfolio_equivalence_verified'])
        self.assertEqual({i['file'] for i in r['ledger_not_performed']},set(c.LEDGER_KEYS))
        self.assertTrue(all('empty_in_both' in i['status'] for i in r['ledger_not_performed']))

    def test_empty_executions_and_pnl_are_reported_not_verified(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()})
        f=ledger();f['executions.parquet']=f['executions.parquet'].iloc[:0];f['pnl.parquet']=f['pnl.parquet'].iloc[:0]
        r=c.compare(a,b,*self.ledgers(f,f))
        self.assertEqual(r['comparisons_performed'],['daily_returns.csv','position_audit.parquet'])
        self.assertEqual({i['file'] for i in r['ledger_not_performed']},{'executions.parquet','pnl.parquet'})
        self.assertEqual(r['status'],'partial_match');self.assertFalse(r['portfolio_equivalence_verified'])

    def test_all_zero_holdings_are_not_coverage(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()})
        f=ledger();f['position_audit.parquet']['position_usd']=0.
        r=c.compare(a,b,*self.ledgers(f,f))
        self.assertNotIn('position_audit.parquet',r['comparisons_performed'])
        self.assertFalse(r['ledger_compared']);self.assertFalse(r['portfolio_equivalence_verified'])
        self.assertIn('no finite nonzero holdings in either run',r['ledger_not_performed'][0]['status'])

    def holdings_case(self,positions_a,positions_b):
        """Same exports and fills/P&L in both runs; only the holdings file differs. None means an empty holdings file."""
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily()},tag=self.id().split('.')[-1]+str(len(list(self.root.iterdir()))))
        frames=[]
        for pos in [positions_a,positions_b]:
            f=ledger();h=f['position_audit.parquet']
            f['position_audit.parquet']=h.iloc[:0] if pos is None else h.assign(position_usd=pos)
            frames.append(f)
        la,lb=self.root/(a.name+'_la'),self.root/(a.name+'_lb')
        for d,f in zip([la,lb],frames):
            d.mkdir()
            for n,df in f.items():df.to_parquet(d/n,index=False)
        return c.compare(a,b,la,lb)

    def test_empty_versus_populated_holdings_is_mismatch_in_both_orders(self):
        for pa,pb in [(None,10.),(10.,None)]:
            r=self.holdings_case(pa,pb)
            self.assertEqual(r['status'],'mismatch',(pa,pb));self.assertIn('position_audit.parquet',r['comparisons_performed'])
            self.assertFalse(r['portfolio_equivalence_verified'])

    def test_zero_versus_populated_holdings_is_mismatch_in_both_orders(self):
        for pa,pb in [(0.,10.),(10.,0.)]:
            r=self.holdings_case(pa,pb)
            self.assertEqual(r['status'],'mismatch',(pa,pb));self.assertIn('position_audit.parquet',r['comparisons_performed'])
            h=next(f for f in r['files'] if f['file']=='position_audit.parquet')
            self.assertEqual(sorted(v['finite_nonzero'] for v in h['holdings_coverage'].values()),[0,2])

    def test_all_nan_holdings_are_invalid(self):
        r=self.holdings_case(np.nan,np.nan)
        self.assertEqual(r['status'],'invalid');self.assertFalse(r['shared_comparisons_match'])
        self.assertFalse(r['portfolio_equivalence_verified'])
        h=next(f for f in r['files'] if f['file']=='position_audit.parquet')
        self.assertEqual(set(h['invalid_positions']),{'original','other'})
        r=self.holdings_case(10.,np.inf)
        self.assertEqual(r['status'],'invalid');self.assertEqual(set(next(f for f in r['files'] if f['file']=='position_audit.parquet')['invalid_positions']),{'other'})

    def test_matching_populated_holdings_verify(self):
        r=self.holdings_case(10.,10.)
        self.assertEqual(r['status'],'match');self.assertTrue(r['portfolio_equivalence_verified'])

    def standard_table(self,turnover=342.,nav=1.51,bench=1.51):
        return pd.DataFrame({'metric':['Ending value of the endowment','One-way turnover','Average holding period'],
                             'units':['US$ billion','% per year','days'],'strategy':[nav,turnover,164.7],'benchmark':[bench,0.,0.]})

    def test_allowed_numeric_turnover_difference(self):
        a,b=self.run_dirs({'standard_table.csv':self.standard_table()},{'standard_table.csv':self.standard_table(turnover=345.)})
        r=c.compare(a,b);col=r['files'][0]['columns']['strategy']
        self.assertFalse(col['match']);self.assertEqual(col['unequal_keys'],['One-way turnover | % per year'])
        self.assertIn('turnover-derived',col['expected_difference'])
        self.assertTrue(r['shared_comparisons_match']);self.assertEqual(r['status'],'partial_match')  # no ledgers supplied

    def test_disallowed_numeric_nav_difference(self):
        a,b=self.run_dirs({'standard_table.csv':self.standard_table()},{'standard_table.csv':self.standard_table(turnover=345.,nav=1.52)})
        r=c.compare(a,b);col=r['files'][0]['columns']['strategy']
        self.assertEqual(r['status'],'mismatch');self.assertNotIn('expected_difference',col)
        self.assertIn('Ending value of the endowment | US$ billion',col['unequal_keys'])
        # The exemption is limited to the strategy column.
        t=self.standard_table();t.loc[1,'benchmark']=1.
        a,b=self.run_dirs({'standard_table.csv':self.standard_table()},{'standard_table.csv':t},tag='bench')
        self.assertEqual(c.compare(a,b)['status'],'mismatch')

    def test_value_difference_is_mismatch(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily(ret=.02)})
        self.assertEqual(c.compare(a,b)['status'],'mismatch')


if __name__=='__main__':unittest.main()

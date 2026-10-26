import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def test_value_difference_is_mismatch(self):
        a,b=self.run_dirs({'daily_returns.csv':daily()},{'daily_returns.csv':daily(ret=.02)})
        self.assertEqual(c.compare(a,b)['status'],'mismatch')


if __name__=='__main__':unittest.main()

import unittest
import tempfile
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import report
ROOT=Path(__file__).resolve().parents[1]
class ReportingTests(unittest.TestCase):
    def test_interactive_english_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            report.generate(ROOT/'inputs',out,verify=True)
            page=(out/'report.html').read_text()
            self.assertNotRegex(page,r'[\u3400-\u9fff]')
            self.assertEqual(page.count('class="plotly-graph-div"'),4)
            self.assertEqual(page.count('"scrollZoom": true'),4)
            self.assertNotIn('<script src=',page)
            self.assertIn('plotly.js v',page)
            self.assertIn('Stage one: monthly reporting baseline',page)
    def test_initial_loss_is_drawdown(self):
        self.assertAlmostEqual(report.performance([-.1,0,0],[0,0,0])['drawdown'],-.1)
    def test_compounding(self):
        self.assertAlmostEqual(report.performance([.1,-.1,0],[0,0,0])['cumulative'],-.01)
    def test_reference_and_zero_absent_weights(self):
        h,r,_=report.load_inputs(ROOT/'inputs')
        table,stats,annual,avg,top,p=report.calculate(h,r)
        self.assertAlmostEqual(p['information_ratio'],.8834050267790214,places=10)
        self.assertAlmostEqual(p['cagr'],.19653079645744076,places=10)
        self.assertEqual(len(h),13600)
        self.assertTrue((stats.positions==200).all())
        ident=h.permno.iloc[0]
        self.assertAlmostEqual(avg.set_index('permno').loc[ident,'average_weight'],h.loc[h.permno==ident,'weight'].sum()/68)
        self.assertTrue(table.loc[table.status=='pending','strategy'].isna().all())
        self.assertEqual(annual.loc[annual.year==2026,'months'].iloc[0],8)
    def test_duplicate_and_missing_month_rejected(self):
        h=pd.read_csv(ROOT/'inputs/holdings.csv');r=pd.read_csv(ROOT/'inputs/portfolio_returns.csv')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);pd.concat([h,h.iloc[:1]]).to_csv(p/'holdings.csv',index=False);r.to_csv(p/'portfolio_returns.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Duplicate'):report.load_inputs(p)
            h.to_csv(p/'holdings.csv',index=False);r.drop(index=2).to_csv(p/'portfolio_returns.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Missing return months'):report.load_inputs(p)
    def test_wrong_benchmark_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'holdings.csv').write_bytes((ROOT/'inputs/holdings.csv').read_bytes())
            r=pd.read_csv(ROOT/'inputs/portfolio_returns.csv');r.loc[0,'hurdle']+=.1;r.to_csv(p/'portfolio_returns.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Provisional benchmark'):report.load_inputs(p)
if __name__=='__main__':unittest.main()

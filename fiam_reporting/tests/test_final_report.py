import io
import sys
import unittest
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import final_report as f

class FinalReportingTests(unittest.TestCase):
    def test_drawdown_includes_initial_endowment(self):
        self.assertAlmostEqual(f.max_drawdown([-.1,.02]),-.1)
        self.assertEqual(f.max_drawdown([.1,.02]),0)

    def test_regression_known_coefficients(self):
        x=np.arange(30,dtype=float)
        result,r2=f.regression(.02+.4*x,x,['market'])
        np.testing.assert_allclose(result.coefficient,[.02,.4],atol=1e-12)
        self.assertAlmostEqual(r2,1)
        with self.assertRaisesRegex(ValueError,'Rank-deficient'):
            f.regression(x,np.ones(30),['market'])

    def test_french_parser_excludes_annual_records_and_converts_percent(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('f.csv','Header\n202101, 1.2\n202102,-0.3\n2021,7.5\n')
        df=f.parse_french(buf.getvalue(),['Mom'])
        np.testing.assert_allclose(df.Mom,[.012,-.003]);self.assertEqual(len(df),2)

    def test_factor_alignment_and_contribution_reconciliation(self):
        rng=np.random.default_rng(7);dates=pd.bdate_range('2021-01-01',periods=650)
        d=pd.DataFrame({'date':dates,'month':dates.to_period('M'),'ret':rng.normal(.0003,.01,len(dates)),
            'ret_gross':rng.normal(.0004,.01,len(dates)),'rf':.0001,'hurdle':.00025,'sp_ret':rng.normal(.0004,.01,len(dates))})
        months=pd.PeriodIndex(d.month.unique())
        factors=pd.DataFrame(rng.normal(0,.03,(len(months),6)),columns=f.FACTOR_NAMES)
        factors['RF']=.001;factors['month']=months
        result,j=f.factor_attribution(d,factors)
        self.assertEqual(len(result),14)
        for basis,col in [('net','ret'),('gross','ret_gross')]:
            self.assertAlmostEqual(result.loc[result.basis==basis,'annual_mean_contribution_pct'].sum(),(j[col]-j.RF).mean()*1200)
        with self.assertRaisesRegex(ValueError,'every test month'):
            f.factor_attribution(d,factors.iloc[:-1])

    def test_accounting_validation_rejects_corruption(self):
        n=260
        d=pd.DataFrame({'date':pd.bdate_range('2021-01-01',periods=n),'ret':.001,'ret_gross':.001,
            'rf':.0001,'hurdle':.0001+.04/252,'sp_ret':.002,'gross':1.9,'net':0,'n_long':150,'n_short':150,
            'max_w':.01,'cost':0.,'borrow':0.,'turnover':0.,'nav':1e9*1.001**np.arange(1,n+1)})
        f.validate_daily(d,1e9)
        bad=d.copy();bad.loc[1,'nav']+=1e6
        with self.assertRaisesRegex(ValueError,'NAV'):f.validate_daily(bad,1e9)
        bad=d.copy();bad.loc[1,'cost']=1e6
        with self.assertRaisesRegex(ValueError,'costs'):f.validate_daily(bad,1e9)
        bad=d.copy();bad.loc[1,'date']=bad.loc[0,'date']
        with self.assertRaisesRegex(ValueError,'unique'):f.validate_daily(bad,1e9)

if __name__=='__main__':unittest.main()

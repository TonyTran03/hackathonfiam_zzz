import sys
import time
import types
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ledger
from test_ledger import engine_class

ROOT=Path(__file__).resolve().parents[2]


def caps(rows):return ledger.validate_market_caps(pd.DataFrame(rows,columns=['permno','eom','me']))


class MonthEndMatchTests(unittest.TestCase):
    def frame(self,dates,permnos,engine=1e9):
        return pd.DataFrame({'date':pd.to_datetime(dates),'permno':permnos,'market_cap_million':engine})

    def test_exact_prior_month_end(self):
        c=caps([(1,'2021-01-31',700.),(1,'2021-02-28',800.),(1,'2021-03-31',900.)])
        out=ledger.attach_month_end_caps(self.frame(['2021-02-01','2021-02-26','2021-02-28','2021-03-01'],[1]*4),c)
        # Feb 28 is itself a month-end: its information date is still Jan 31, never the same-day value.
        self.assertEqual(out.market_cap_month_end.dt.strftime('%Y-%m-%d').tolist(),['2021-01-31']*3+['2021-02-28'])
        self.assertEqual(out.market_cap_million.tolist(),[700.,700.,700.,800.])
        self.assertTrue((out.market_cap_match=='matched').all())

    def test_no_future_value_is_used(self):
        c=caps([(1,'2021-02-28',800.)])
        out=ledger.attach_month_end_caps(self.frame(['2021-02-15'],[1]),c)
        self.assertTrue(np.isnan(out.market_cap_million.iloc[0]))
        self.assertEqual(out.market_cap_match.iloc[0],'no_earlier_panel_value')

    def test_missing_prior_month_is_not_carried_forward(self):
        c=caps([(1,'2020-12-31',650.),(1,'2021-03-31',900.)])
        out=ledger.attach_month_end_caps(self.frame(['2021-02-03','2021-03-02'],[1,1]),c)
        self.assertTrue(np.isnan(out.market_cap_million.iloc[0]))
        self.assertEqual(out.market_cap_match.tolist(),['missing_prior_month_end','missing_prior_month_end'])

    def test_engine_estimate_retained_and_never_used(self):
        out=ledger.attach_month_end_caps(self.frame(['2021-02-03'],[1],engine=1.4e9),caps([(2,'2021-01-31',900.)]))
        self.assertEqual(out.engine_market_cap_million.iloc[0],1.4e9)
        self.assertTrue(np.isnan(out.market_cap_million.iloc[0]))
        none=ledger.attach_month_end_caps(self.frame(['2021-02-03'],[1],engine=1.4e9),None)
        self.assertEqual(none.market_cap_match.iloc[0],'panel_unavailable')
        self.assertTrue(np.isnan(none.market_cap_million.iloc[0]))
        self.assertEqual(none.engine_market_cap_million.iloc[0],1.4e9)

    def test_panel_validation(self):
        for rows,msg in [([(1,'2021-01-31',1.),(1,'2021-01-31',2.)],'Duplicate'),
                         ([(1,'2021-01-30',1.)],'month-ends'),
                         ([(1,'2021-01-31',np.nan)],'non-finite'),
                         ([(1,'2021-01-31',0.)],'Nonpositive'),
                         ([(1,None,1.)],'missing permno/eom')]:
            with self.assertRaisesRegex(ValueError,msg):caps(rows)
        with self.assertRaisesRegex(ValueError,'missing columns'):ledger.validate_market_caps(pd.DataFrame({'permno':[1]}))


def short_toy():
    """Three names: a long, a short filled in two tranches (low ADV), a short filled at once."""
    cls=engine_class(ROOT/'06_final/f03_engine.py');e=cls.__new__(cls);dates=pd.bdate_range('2021-02-01',periods=4)
    e.days=pd.DataFrame({'date':dates,'month':dates.to_period('M'),'is_formation':[True,False,False,False],
        'is_week_start':[True,False,False,False],'rf_d':0.,'tb3ms':0.,'hurdle_d':.04/252,'mkt_ex':0.,'sp_ret':0.})
    e.perms=np.array([1,2,3]);e.start_nav=100.;e.R=np.zeros((5,3));e.P=np.full((5,3),10.)
    e.last=pd.Series([dates[-1]+pd.Timedelta(days=30)]*3)
    e.stub=pd.Series(dtype=float);e.sig_sel={'2021-02':None};e.leg_hist=[];e.freq='M';e.overlay=None;e.layer=None;e.triage=None;e.borrow_mode='model';e.label='toy'
    def form(self,*args):
        self.month_rows=pd.DataFrame({'pi':[0,1,2],'half_spread':0.,'rvol_21d':.02,'dolvol_126d':[1000.,100.,1000.],
            'size_grp':'large','ivol_top_decile':False,'shares':100.,'px_now':10.})
        return np.array([40.,-20.,-20.]),{'measured':None}
    e.form=types.MethodType(form,e);e.trade_cost=lambda delta,args:0.
    e.enforce=lambda base,nav,di,tw:(base,'');e.run(quiet=True)
    return e


class ShortBookMedianTests(unittest.TestCase):
    def test_held_book_median_differs_from_trade_median(self):
        e=short_toy();labels=pd.DataFrame({'permno':[1,2,3],'ticker':list('ABC'),'company_name':list('ABC')})
        panel=caps([(1,'2021-01-31',5000.),(2,'2021-01-31',600.),(3,'2021-01-31',9000.)])
        r=ledger.derive(e.daily,e.position_audit,e.pnl,e.executions,labels,panel)
        o=r['shorts'];h=r['held_shorts'];sm=r['summary']
        self.assertGreater((o.permno==2).sum(),(o.permno==3).sum())     # permno 2 is filled in tranches
        self.assertEqual(sm['month_end_market_cap_verification'],'complete')
        self.assertEqual(sm['execution_day_market_cap_compliance'],'unverified')
        self.assertEqual(sm['short_book_median_market_cap_million'],float(h.market_cap_million.median()))
        self.assertEqual(len(h),h[['date','permno']].drop_duplicates().shape[0])
        self.assertNotEqual(sm['short_book_median_market_cap_million'],float(o.market_cap_million.median()))
        self.assertEqual(o.engine_market_cap_million.notna().sum(),len(o))

    def test_missing_panel_month_makes_verification_incomplete(self):
        e=short_toy();labels=pd.DataFrame({'permno':[1,2,3]})
        panel=caps([(1,'2021-01-31',5000.),(2,'2020-12-31',600.),(3,'2021-01-31',9000.)])
        sm=ledger.derive(e.daily,e.position_audit,e.pnl,e.executions,labels,panel)['summary']
        self.assertEqual(sm['month_end_market_cap_verification'],'incomplete')
        self.assertIsNone(sm['short_book_median_market_cap_million'])
        self.assertGreater(sm['short_openings_month_end_unmatched_by_status']['missing_prior_month_end'],0)
        sm=ledger.derive(e.daily,e.position_audit,e.pnl,e.executions,labels,None)['summary']
        self.assertEqual(sm['market_cap_basis'],'unavailable');self.assertEqual(sm['month_end_market_cap_verification'],'incomplete')


if __name__=='__main__':unittest.main()

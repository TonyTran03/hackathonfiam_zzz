import ast
import sys
import time
import types
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ledger

ROOT=Path(__file__).resolve().parents[2]

def engine_class(path):
    tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Engine')
    ns=dict(np=np,pd=pd,time=time,H={'half_spread_cap_bps':10,'max_participation':.1,'borrow_bps':{'large':0},'borrow_hard_bps':0,'delist_long':-.3,'delist_short':0},FIN={'short_min_me_musd':500})
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns['Engine']


def toy(cls):
    e=cls.__new__(cls);dates=pd.bdate_range('2021-01-04',periods=3)
    e.days=pd.DataFrame({'date':dates,'month':dates.to_period('M'),'is_formation':[True,False,False],
        'is_week_start':[True,False,False],'rf_d':0.,'tb3ms':0.,'hurdle_d':.04/252,'mkt_ex':0.,'sp_ret':0.})
    e.perms=np.array([1,2]);e.start_nav=100.;e.R=np.array([[0,0],[0,0],[.1,0],[np.nan,0]])
    e.P=np.full((4,2),10.);e.last=pd.Series([dates[1],dates[2]])
    e.stub=pd.Series(dtype=float);e.sig_sel={'2021-01':None};e.leg_hist=[];e.freq='M';e.overlay=None;e.layer=None;e.triage=None;e.borrow_mode='model';e.label='toy'
    def form(self,*args):
        self.month_rows=pd.DataFrame({'pi':[0,1],'half_spread':[0.,0.],'rvol_21d':[.02,.02],
         'dolvol_126d':[1000.,1000.],'size_grp':['large','large'],'ivol_top_decile':[False,False],
         'shares':[100.,100.],'px_now':[10.,10.]})
        return np.array([40.,-20.]),{'measured':None}
    e.form=types.MethodType(form,e);e.trade_cost=lambda delta,args:.01*np.abs(delta).sum()
    e.enforce=lambda base,nav,di,tw:(base,'')
    e.run(quiet=True)
    return e

class LedgerTests(unittest.TestCase):
    def setUp(self):self.e=toy(engine_class(ROOT/'06_final/f03_engine.py'))
    def test_turnover_includes_cost_nav_change(self):
        e=self.e
        self.assertAlmostEqual(e.daily.turnover.iloc[0],.5*60/99.4)
        self.assertAlmostEqual(e.daily.turnover_dollar_proxy.iloc[0],.3)
    def test_delisting_and_cash_bridge(self):
        e=self.e;labels=pd.DataFrame({'permno':[1,2],'ticker':['A','B'],'company_name':['A corp','B corp']})
        r=ledger.derive(e.daily,e.position_audit,e.pnl,e.executions,labels)
        self.assertAlmostEqual(r['summary']['delisting_pnl_dollars'],-13.2)
        self.assertAlmostEqual(r['all_contributors'].set_index('permno').loc[1,'contribution_pct_of_start_nav'],-9.2)
        self.assertEqual(r['summary']['holding_period_days'],(2*42+3*20)/62)
        self.assertAlmostEqual(r['all_average'].set_index('permno').loc[1,'avg_weight'],(40/99.4+44/103.4)/3)
    def test_omitted_stub_is_rejected(self):
        e=self.e
        with self.assertRaisesRegex(ValueError,'P&L bridge'):
            ledger.derive(e.daily,e.position_audit,e.pnl[e.pnl.pnl_kind!='delisting'],e.executions,pd.DataFrame({'permno':[1,2]}))
    def test_bad_turnover_is_rejected(self):
        e=self.e;d=e.daily.copy();d['turnover']=d.turnover_dollar_proxy
        with self.assertRaisesRegex(ValueError,'turnover'):
            ledger.derive(d,e.position_audit,e.pnl,e.executions,pd.DataFrame({'permno':[1,2]}))

if __name__=='__main__':unittest.main()

class EngineParityTests(unittest.TestCase):
    def test_audit_changes_do_not_change_nav_or_trades(self):
        original=ROOT.parent/'audit'/'06_final'/'f03_engine.py'
        if not original.exists():self.skipTest('Original engine snapshot only available in development workspace')
        old=toy(engine_class(original));new=toy(engine_class(ROOT/'06_final/f03_engine.py'))
        for c in ['nav','ret','ret_gross','cost','borrow','gross','net']:
            np.testing.assert_array_equal(old.daily[c],new.daily[c])
        pd.testing.assert_frame_equal(old.trades,new.trades)

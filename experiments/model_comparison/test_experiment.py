"""Focused checks for information timing and accounting, plus saved-output audit."""
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from run_comparison import select_annual
from evaluate_comparison import calendar_smooth, metrics
from common import config as C

ROOT=Path(__file__).resolve().parent

class ExperimentChecks(unittest.TestCase):
    def test_test_outcomes_cannot_choose_annual_blend(self):
        rng=np.random.default_rng(42);n=120
        v=pd.DataFrame({'target_month':np.repeat(['2019-01','2019-02'],60),C.TARGET:rng.normal(size=n)})
        for col in ['ols','ridge','lasso','en','gbm_missing','gbm_median']:
            v[col]=v[C.TARGET]+rng.normal(size=n)
        p=v.copy();p['target_month']='2021-01';q=p.copy();q[C.TARGET]=-1000*p[C.TARGET]
        a=select_annual(v.copy(),p);b=select_annual(v.copy(),q)
        self.assertEqual(a,b)
        np.testing.assert_array_equal(p.annual_blend,q.annual_blend)

    def test_smoothing_uses_calendar_not_observation_count(self):
        p=pd.DataFrame({'permno':[1,1,1],'target_month':['2021-01','2021-02','2021-06'],'score':[2.,4.,10.]})
        np.testing.assert_allclose(calendar_smooth(p,3),[2.,3.,10.])

    def test_first_month_loss_counts_as_drawdown(self):
        n=68;t=np.zeros(n);t[0]=-.1
        m=pd.DataFrame({'total_20':t,'hurdle':.004,'cash':.001,'market':np.linspace(-.05,.05,n),'traded_20':1.,'gross':2.,'net':0.,'max_weight':.02,'missing_n':0,'missing_gross':0.})
        self.assertAlmostEqual(metrics(m,20)['max_drawdown'],-.1)

    def test_cash_accounting_with_nonzero_net_exposure(self):
        w=np.array([1.1,-.9]);raw=np.array([.04,-.02]);cash=.003;source_rf=.001
        excess=raw-source_rf
        correct=cash+np.sum(w*(excess+source_rf-cash))
        self.assertAlmostEqual(correct,(1-w.sum())*cash+np.sum(w*raw))
        self.assertNotAlmostEqual(correct,cash+np.sum(w*excess))

    def test_saved_fold_dates_are_historical(self):
        for p in (ROOT/'results').glob('fold_*.json'):
            d=json.loads(p.read_text())
            self.assertLess(d['train_end'],d['validation_start'])
            self.assertLess(d['validation_end'],d['test_start'])
            self.assertLessEqual(d['test_start'],d['test_end'])

if __name__=='__main__':unittest.main(verbosity=2)

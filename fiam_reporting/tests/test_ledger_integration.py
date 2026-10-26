import hashlib
import unittest
import types
from tempfile import TemporaryDirectory
from pathlib import Path
import numpy as np
import pandas as pd
from test_ledger import toy,engine_class
import ledger
import final_report

class IntegrationTests(unittest.TestCase):
    def test_engine_to_report(self):
        cls=engine_class(Path(__file__).resolve().parents[2]/'06_final/f03_engine.py');e=toy(cls)
        rng=np.random.default_rng(8);dates=pd.bdate_range('2021-01-04',periods=260);n=300
        e.days=pd.DataFrame({'date':dates,'month':dates.to_period('M'),'is_formation':[True]+[False]*259,'is_week_start':False,'rf_d':.00005,'tb3ms':1.26,'hurdle_d':.00005+.04/252,'sp_ret':rng.normal(.0002,.01,260)});e.days['mkt_ex']=e.days.sp_ret-e.days.rf_d
        e.start_nav=1e9;e.perms=np.arange(n);e.R=np.vstack([np.zeros(n),rng.normal(0,.002,(260,n))]);e.P=np.full((261,n),10.);e.last=pd.Series([dates[-1]]*n);e.leg_hist=[]
        def form(self,*args):
         self.month_rows=pd.DataFrame({'pi':np.arange(n),'half_spread':0.,'rvol_21d':.02,'dolvol_126d':1e9,'size_grp':'large','ivol_top_decile':False,'shares':100.,'px_now':10.})
         return np.r_[np.full(150,3e6),np.full(150,-3e6)],{'measured':None}
        e.form=types.MethodType(form,e);e.run(quiet=True)
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);run=root/'data/runs/test_M';run.mkdir(parents=True,exist_ok=True);inputs=root/'output/test_M';inputs.mkdir(parents=True,exist_ok=True)
        for name,df in [('daily',e.daily),('pnl',e.pnl),('position_audit',e.position_audit),('executions',e.executions)]:df.to_parquet(run/(name+'.parquet'),index=False)
        labels=pd.DataFrame({'permno':np.arange(n),'ticker':['T'+str(i) for i in range(n)],'company_name':['Company '+str(i) for i in range(n)]});labels.to_parquet(root/'data/signal_test.parquet',index=False)
        r=ledger.derive(e.daily,e.position_audit,e.pnl,e.executions,labels)
        e.daily.to_csv(inputs/'daily_returns.csv',index=False)
        pd.DataFrame({'metric':['Average holding period','Average position size'],'strategy':[0.,0.]}).to_csv(inputs/'standard_table.csv',index=False)
        r['top'].to_csv(inputs/'top_holdings.csv',index=False);r['contributors'].to_csv(inputs/'contributors.csv',index=False)
        f=e.targets.copy();f['me_form']=f.me_formation;f['leg']=np.where(f.target_usd>0,'long','short');f['days_adv']=f.target_usd.abs()/f.dolvol_126d;f.to_csv(inputs/'formation_positions.csv',index=False)
        months=pd.period_range('2020-12',dates[-1].to_period('M'),freq='M').to_timestamp(how='end').normalize()
        panel=pd.DataFrame([(p,m,1000.+p) for p in range(n) for m in months],columns=['permno','eom','me']);panel.to_parquet(root/'model_table.parquet',index=False)
        before={f:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
        with self.assertRaisesRegex(ValueError,'Month-end market-cap verification is incomplete'):
            final_report.generate(inputs,root/'report_no_panel',ledger_dir=run,require_verified=True,market_caps=root/'missing.parquet')
        t,meta=final_report.generate(inputs,root/'report',ledger_dir=run,require_verified=True,market_caps=root/'model_table.parquet')
        self.assertEqual(before,{f:hashlib.sha256(f.read_bytes()).hexdigest() for f in before})
        assert meta['independent_full_ledger_validation']
        assert meta['checks']['stock_pnl_bridge_verified']
        self.assertEqual(meta['checks']['month_end_market_cap_verification'],'complete')
        self.assertEqual(meta['checks']['execution_day_market_cap_compliance'],'unverified')
        self.assertNotIn('short_execution_floor_breaches',meta['checks'])
        held=pd.read_csv(root/'report/short_book_market_caps.csv')
        self.assertEqual(meta['checks']['short_book_median_market_cap_million'],held.market_cap_million.median())
        html=(root/'report/report.html').read_text()
        assert 'Actual daily positions' in html and 'prior-month-end panel me' in html and 'execution-day' in html
        print('PASS full 260-day, 300-stock engine-to-ledger-to-report integration')

"""Run from this directory: FIAM_DATA_DIR=/path/to/data python run_comparison.py.
See PROTOCOL.md. Generated caches are excluded from the deliverable ZIP.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(k,'2')
import argparse, hashlib, json, time, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import Lasso, ElasticNet
from sklearn.preprocessing import StandardScaler
from scipy.linalg import eigh
from common import config as C
import data_loader

ROOT=Path(__file__).resolve().parent
RES=ROOT/'results'; CACHE=ROOT/'cache'
for p in (RES,CACHE): p.mkdir(exist_ok=True)
TARGET=C.TARGET
MODELS=['ols','ridge','lasso','en','gbm_missing','gbm_median','gbm_median_matched']
GRIDS={'ridge':np.logspace(0,6,13),'lasso':np.logspace(-5,-1,13),'en':np.logspace(-5,-1,13)}
GBM_GRID=[dict(num_leaves=15,min_child_samples=500,learning_rate=.02),dict(num_leaves=31,min_child_samples=200,learning_rate=.02),dict(num_leaves=63,min_child_samples=100,learning_rate=.01)]
FIXED=dict(objective='l2',n_estimators=3000,subsample=.7,subsample_freq=1,colsample_bytree=.7,reg_lambda=1.,verbosity=-1,n_jobs=2,random_state=2026,deterministic=True,force_col_wise=True)

def dump(path,obj): path.write_text(json.dumps(obj,indent=2,default=str))
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def prepare():
    identity={'dataset_sha256':sha(C.CHARS_PARQUET), 'protocol_sha256':sha(ROOT/'PROTOCOL.md')}
    old=RES/'input_manifest.json'
    if old.exists():
        previous=json.loads(old.read_text())
        for key,value in identity.items():
            if previous.get(key)!=value:
                raise RuntimeError('Data/protocol changed: use a fresh experiment directory; do not reuse caches or checkpoints.')
    if not C.MODEL_TABLE.exists():data_loader.build_model_table()
    if not C.BENCHMARK_CSV.exists():data_loader.build_benchmark()
    feats=pd.read_csv(C.FACTOR_LIST_CSV).variable.tolist()
    d=pd.read_parquet(C.MODEL_TABLE)
    assert len(feats)==147 and TARGET not in feats
    assert not d.duplicated(['permno','target_month']).any()
    assert ((pd.PeriodIndex(d.target_month,freq='M')-1).astype(str)==d.eom.dt.to_period('M').astype(str)).all()
    if not (CACHE/'filled.npy').exists():
        a=np.empty((len(d),len(feats)),np.float64)
        for month,ix in d.groupby('target_month',sort=True).groups.items():
            x=d.loc[ix,feats].replace([np.inf,-np.inf],np.nan)
            r=x.rank(method='dense')-1
            top=r.max();r=r.div(top.where(top>0))*2-1
            # Constant observed columns are neutral; original missing cells remain missing.
            for c in top.index[top.eq(0)]:r[c]=x[c].where(x[c].isna(),0.)
            a[np.asarray(ix)]=r.to_numpy()
        np.save(CACHE/'sparse.npy',a.astype(np.float32))
        for _,ix in d.groupby('target_month',sort=True).groups.items():
            x=a[np.asarray(ix)]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning);med=np.nanmedian(x,axis=0)
            med=np.nan_to_num(med,nan=0.)
            a[np.asarray(ix)]=np.where(np.isnan(x),med,x)
        np.save(CACHE/'filled.npy',a.astype(np.float32))
    sp=np.load(CACHE/'sparse.npy',mmap_mode='r');fi=np.load(CACHE/'filled.npy',mmap_mode='r')
    assert np.isfinite(fi).all()
    for i in range(0,len(d),10000):
        x=sp[i:i+10000];y=fi[i:i+10000];ok=np.isfinite(x);assert np.array_equal(x[ok],y[ok])
    dump(RES/'input_manifest.json',{'dataset_sha256':sha(C.CHARS_PARQUET),'rows':len(d),'features':len(feats),'protocol_sha256':sha(ROOT/'PROTOCOL.md'),'feature_nan_share':float(np.isnan(sp).mean()),'seed':2026})
    return d,feats,sp,fi

def ic(frame,col):
    return frame.groupby('target_month').apply(lambda g:g[col].corr(g[TARGET],method='spearman'),include_groups=False).mean()

def blend(frame,parts):
    z=frame.groupby('target_month')[parts].transform(lambda x:(x-x.mean())/(x.std(ddof=0) or 1.))
    return z.mean(axis=1)

def select_annual(v,p):
    for f in (v,p):f['avg_linear']=f[['ols','ridge','lasso','en']].mean(axis=1)
    candidates={'gbm_missing':['gbm_missing'],'gbm_median':['gbm_median'],'avg_linear':['avg_linear'],'linear_gbm':['avg_linear','gbm_missing'],'ridge_gbm':['ridge','gbm_missing']}
    scores={}
    for n,parts in candidates.items():scores[n]=float(ic(v.assign(candidate=blend(v,parts)),'candidate'))
    name=max(scores,key=lambda n:scores[n] if np.isfinite(scores[n]) else -np.inf)
    p['annual_blend']=blend(p,candidates[name])
    return name,scores

def train(d,features,sp,fi):
    allp=[]; logs=[]
    for te,vs,ve,ts,end in C.training_schedule():
        year=int(ts[:4]);out=RES/f'predictions_{year}.parquet';meta=RES/f'fold_{year}.json'
        if out.exists() and meta.exists():
            allp.append(pd.read_parquet(out));logs.append(json.loads(meta.read_text()));continue
        start=time.time();tm=d.target_month
        tr=np.flatnonzero((tm<=te)&d[TARGET].notna()); va=np.flatnonzero((tm>=vs)&(tm<=ve)&d[TARGET].notna());tt=np.flatnonzero((tm>=ts)&(tm<=end))
        assert tm.iloc[tr].max()<tm.iloc[va].min() and tm.iloc[va].max()<tm.iloc[tt].min()
        scaler=StandardScaler().fit(fi[tr]);X=np.asfortranarray(scaler.transform(fi[tr]).astype(float));V=scaler.transform(fi[va]).astype(float);T=scaler.transform(fi[tt]).astype(float)
        y=d[TARGET].to_numpy()[tr];yv=d[TARGET].to_numpy()[va];mu=y.mean();yc=y-mu
        p=d.iloc[tt][['permno','target_month',TARGET]].copy();v=d.iloc[va][['permno','target_month',TARGET]].copy()
        log={'year':year,'train_end':te,'validation_start':vs,'validation_end':ve,'test_start':ts,'test_end':end,'training_rows':len(tr),'validation_rows':len(va),'test_rows':len(tt),'hyperparameters':{}}
        gram=X.T@X;xy=X.T@yc
        ev,Q=eigh(gram);proj=Q.T@xy
        coef=Q@(proj/np.where(ev>ev.max()*1e-12,ev,np.inf))
        p['ols']=T@coef+mu;v['ols']=V@coef+mu
        for name in ('ridge','lasso','en'):
            best=np.inf;history=[]
            for a in GRIDS[name]:
                if name=='ridge':coef=Q@(proj/(ev+a));iterations=0
                else:
                    cls=Lasso if name=='lasso' else ElasticNet
                    m=cls(alpha=float(a),fit_intercept=False,max_iter=3000,tol=1e-4,precompute=gram.copy()).fit(X,yc)
                    coef=m.coef_;iterations=int(m.n_iter_)
                vp=V@coef+mu;mse=float(np.mean((yv-vp)**2));history.append({'alpha':float(a),'validation_mse':mse,'iterations':iterations})
                if mse<best:best=mse;bc=coef.copy();ba=float(a)
            p[name]=T@bc+mu;v[name]=V@bc+mu
            log['hyperparameters'][name]={'alpha':ba,'validation_mse':best,'grid':history}
        del X,V,T,gram
        for name,arr in [('gbm_missing',sp),('gbm_median',fi)]:
            best=np.inf;history=[];bm=None
            A=arr[tr];B=arr[va]
            for cfg in GBM_GRID:
                m=lgb.LGBMRegressor(**FIXED,**cfg)
                m.fit(A,y,eval_set=[(B,yv)],eval_metric='l2',callbacks=[lgb.early_stopping(50,verbose=False)])
                vp=m.predict(B);mse=float(np.mean((yv-vp)**2));rounds=int(m.best_iteration_)
                history.append(dict(config=cfg,rounds=rounds,validation_mse=mse))
                if mse<best:best=mse;bm=m;bcfg=cfg;bn=rounds
            p[name]=bm.predict(arr[tt]);v[name]=bm.predict(B)
            log['hyperparameters'][name]={'config':bcfg,'rounds':bn,'validation_mse':best,'grid':history}
            print(year,name,'rounds',bn,'validation MSE',round(best,6),flush=True)
        matched=log['hyperparameters']['gbm_missing'];fixed=dict(FIXED);fixed['n_estimators']=matched['rounds']
        m=lgb.LGBMRegressor(**fixed,**matched['config']).fit(fi[tr],y)
        p['gbm_median_matched']=m.predict(fi[tt]);v['gbm_median_matched']=m.predict(fi[va])
        log['hyperparameters']['gbm_median_matched']={'config':matched['config'],'rounds':matched['rounds'],'validation_mse':float(np.mean((yv-v.gbm_median_matched)**2))}
        winner,scores=select_annual(v,p);log['annual_blend']=winner;log['blend_validation_ic']=scores
        log['seconds']=time.time()-start
        assert np.isfinite(p[MODELS+['annual_blend']].to_numpy()).all()
        p.to_parquet(out,index=False);dump(meta,log)
        allp.append(p);logs.append(log)
        print('Completed',year,'blend',winner,'seconds',round(log['seconds']),flush=True)
    pred=pd.concat(allp,ignore_index=True)
    assert pred.target_month.nunique()==68 and not pred.duplicated(['permno','target_month']).any()
    pred.to_parquet(RES/'predictions.parquet',index=False);dump(RES/'annual_choices.json',logs)
    return pred

def main():
    a=argparse.ArgumentParser();a.add_argument('--evaluate-only',action='store_true');args=a.parse_args()
    d,feats,sp,fi=prepare()
    p=pd.read_parquet(RES/'predictions.parquet') if args.evaluate_only else train(d,feats,sp,fi)
    from evaluate_comparison import evaluate
    evaluate(d,p)

if __name__=='__main__':main()

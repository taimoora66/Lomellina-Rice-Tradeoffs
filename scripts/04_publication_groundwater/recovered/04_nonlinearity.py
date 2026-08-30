import pandas as pd, numpy as np
import statsmodels.formula.api as smf
from scipy import stats
p=pd.read_csv('/mnt/data/panel_monthly_weather_test.csv')
cols=['d_spr_8','ff10_anom','P_A8','T_A8','pre','station','year']
r=p.dropna(subset=cols).copy()
# baseline
base='d_spr_8 ~ ff10_anom + P_A8 + T_A8 + pre + C(station)+C(year)'
m=smf.ols(base,r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
print('BASE',len(r),r.station.nunique(),r.ff10_anom.mean(),r.ff10_anom.std(),r.ff10_anom.quantile([.01,.05,.1,.25,.5,.75,.9,.95,.99]).to_dict())
print('linear',m.params.ff10_anom,m.pvalues.ff10_anom,m.conf_int().loc['ff10_anom'].tolist())
# quadratic centered anomaly already ~ centered within station but sample nonzero; scale for numerical stability
r['ff100']=r.ff10_anom*100
mq=smf.ols('d_spr_8 ~ ff100 + I(ff100**2) + P_A8 + T_A8 + pre + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
print('QUAD linear_per1',mq.params.ff100,'quad',mq.params['I(ff100 ** 2)'],'quad_p',mq.pvalues['I(ff100 ** 2)'])
# joint FF terms robust Wald
print('QUAD_JOINT',mq.wald_test('ff100 = 0, I(ff100 ** 2) = 0',scalar=True))
# cubic spline df=4; compare nonlinear components via wald after explicit patsy bs generated in formula
ms=smf.ols('d_spr_8 ~ bs(ff100, df=4, degree=3, include_intercept=False) + P_A8 + T_A8 + pre + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
terms=[x for x in ms.params.index if x.startswith('bs(ff100')]
print('SPLINE terms',[(t,ms.params[t],ms.pvalues[t]) for t in terms])
# Cannot directly test nonlinearity vs linear with basis coefficients. Compare predictions of spline vs linear over observed support descriptively.
# Quantile bins. Four bins on anomaly. Use bin FE but station/year FE; Q2 reference to avoid extreme-v-extreme framing.
r['qbin']=pd.qcut(r.ff10_anom,4,labels=['Q1','Q2','Q3','Q4'])
mb=smf.ols('d_spr_8 ~ C(qbin, Treatment(reference="Q2")) + P_A8 + T_A8 + pre + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
print('BINS bounds')
print(r.groupby('qbin',observed=True).ff10_anom.agg(['count','min','median','max']))
for t in mb.params.index:
 if 'qbin' in t: print('BINCOEF',t,mb.params[t],mb.pvalues[t],mb.conf_int().loc[t].tolist())
# marginal adjusted means for bins using recycled predictions? estimate contrasts relative Q1/Q4 via coefficient calculations. Direct Q4-Q1 contrast.
coefnames={q:[t for t in mb.params.index if f'[T.{q}]' in t and 'qbin' in t] for q in ['Q1','Q3','Q4']}
# Q4-Q1
if coefnames['Q4'] and coefnames['Q1']:
 c=np.zeros(len(mb.params)); names=list(mb.params.index); c[names.index(coefnames['Q4'][0])]=1;c[names.index(coefnames['Q1'][0])]=-1
 wt=mb.t_test(c)
 print('Q4-Q1',float(wt.effect),float(wt.pvalue),wt.conf_int().tolist())
# trims symmetric by FF anomaly percentiles 5/95 and 10/90
for a in [.05,.10]:
 lo,hi=r.ff10_anom.quantile([a,1-a]); rr=r[(r.ff10_anom>=lo)&(r.ff10_anom<=hi)].copy()
 mm=smf.ols(base,rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station})
 print('TRIM',int(a*100),len(rr),rr.station.nunique(),lo,hi,mm.params.ff10_anom,mm.pvalues.ff10_anom,mm.conf_int().loc['ff10_anom'].tolist(), 'sd',rr.ff10_anom.std())
# winsor sensitivity 5/95, 10/90 while retaining N
for a in [.05,.10]:
 lo,hi=r.ff10_anom.quantile([a,1-a]); rr=r.copy(); rr['ff_w']=rr.ff10_anom.clip(lo,hi)
 mm=smf.ols('d_spr_8 ~ ff_w + P_A8 + T_A8 + pre + C(station)+C(year)',rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station})
 print('WINSOR',int(a*100),len(rr),lo,hi,mm.params.ff_w,mm.pvalues.ff_w,mm.conf_int().loc['ff_w'].tolist())
# tails individually: exclude low 5, high 5, low10, high10
for label, mask in [
 ('drop_low5', r.ff10_anom>=r.ff10_anom.quantile(.05)),
 ('drop_high5',r.ff10_anom<=r.ff10_anom.quantile(.95)),
 ('drop_low10',r.ff10_anom>=r.ff10_anom.quantile(.10)),
 ('drop_high10',r.ff10_anom<=r.ff10_anom.quantile(.90))]:
 rr=r[mask].copy(); mm=smf.ols(base,rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station})
 print('ONE_TAIL',label,len(rr),mm.params.ff10_anom,mm.pvalues.ff10_anom,mm.conf_int().loc['ff10_anom'].tolist())
# piecewise linear knot at 0; useful sign asymmetry. xneg=min(x,0), xpos=max(x,0)
r['ffneg']=np.minimum(r.ff10_anom,0); r['ffpos']=np.maximum(r.ff10_anom,0)
mp=smf.ols('d_spr_8 ~ ffneg + ffpos + P_A8 + T_A8 + pre + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
print('PIECE',[(v,mp.params[v],mp.pvalues[v],mp.conf_int().loc[v].tolist()) for v in ['ffneg','ffpos']])
print('PIECE_DIFF',mp.t_test('ffneg = ffpos'))

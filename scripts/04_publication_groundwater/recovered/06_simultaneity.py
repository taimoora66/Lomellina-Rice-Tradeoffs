import pandas as pd, numpy as np
from pathlib import Path
import statsmodels.formula.api as smf
base=Path('/mnt/data')
# panel FF and metadata
p=pd.read_csv(base/'panel_monthly_weather_test.csv')
p=p[['station','year','ff_10','ff10_anom','gw_x','gw_y','gwb']].drop_duplicates(['station','year']).copy()
# groundwater raw clean superficial
f=base/'8c52fa50-368e-4ca0-97d6-77d30b15e129.xlsx'
gw=pd.read_excel(f)
gw['Data']=pd.to_datetime(gw['Data']); gw['year']=gw.Data.dt.year; gw['month']=gw.Data.dt.month
v='Soggiacenza m da Qr'
gw=gw.drop_duplicates(['CODICE','Data',v])
ct=gw.groupby(['CODICE','Data'])[v].nunique(); bad=set(ct[ct>1].index)
idx=pd.MultiIndex.from_frame(gw[['CODICE','Data']]); gw=gw[~idx.isin(bad)].copy()
gw=gw[gw['GroundWater Body (GWB_2015)'].astype(str).str.startswith('GWB ISS',na=False)].copy()
# monthly mean depths
mon=gw.groupby(['CODICE','year','month'],as_index=False)[v].mean().rename(columns={v:'depth'})
wide=mon.pivot_table(index=['CODICE','year'],columns='month',values='depth').reset_index()
wide.columns=['CODICE','year']+[f'gw_m{int(c)}' for c in wide.columns[2:]]
# Jan-Feb average strict pre-March
jf=gw[gw.month.isin([1,2])].groupby(['CODICE','year'])[v].mean().rename('gw_janfeb').reset_index()
# prior autumn Oct-Nov linked to next year
on=gw[gw.month.isin([10,11])].groupby(['CODICE','year'])[v].mean().rename('gw_prevaut').reset_index(); on['year']=on.year+1
p=p.merge(wide,left_on=['station','year'],right_on=['CODICE','year'],how='left').drop(columns='CODICE')
p=p.merge(jf,left_on=['station','year'],right_on=['CODICE','year'],how='left').drop(columns='CODICE')
p=p.merge(on,left_on=['station','year'],right_on=['CODICE','year'],how='left').drop(columns='CODICE')
# Weather raw monthly already generated in panel only Apr-Aug. Recompute Jan-Mar station links using same methods but simpler by reusing source files.
prec_files=[base/'a010663a-150f-4560-820d-2f0a663a130a.csv',base/'198768f4-08cf-4616-b902-44291c84719b.csv',base/'2354a6c0-98b3-4b8d-b22f-642d2594f52c.csv']
temp_files=[base/'80842682-0069-4a60-80ff-7b297c4b3bfc.csv',base/'666b0217-fa56-42c1-baeb-f78ccb95ea33.csv',base/'881348f3-0246-4881-b67c-f5e3744323be.csv']
def daily(files,var):
 out=[]
 for f in files:
  for d in pd.read_csv(f,usecols=['idsensore','data','valore','stato'],chunksize=400000):
   d['data']=pd.to_datetime(d.data,errors='coerce'); d=d[(d.data.dt.year>=2008)&(d.data.dt.year<=2021)]
   d['idsensore']=pd.to_numeric(d.idsensore,errors='coerce').astype('Int64'); d['valore']=pd.to_numeric(d.valore,errors='coerce')
   if var=='temp': d.loc[d.valore.eq(-999),'valore']=np.nan
   d.loc[d.stato.ne('VA'),'valore']=np.nan; d['date']=d.data.dt.floor('D')
   z=d.groupby(['idsensore','date'],as_index=False).agg(n=('valore','count'),s=('valore','sum'),mean=('valore','mean')); out.append(z)
 z=pd.concat(out,ignore_index=True)
 if var=='precip': z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),s=('s','sum'))
 else:
  z['ws']=z['mean']*z['n']; z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),ws=('ws','sum')); z['mean']=z.ws/z.n.replace(0,np.nan)
 z['year']=z.date.dt.year; z['month']=z.date.dt.month
 ex=z.groupby(['idsensore','year'])['n'].quantile(.9).reset_index(name='q90'); common=np.array([8,12,24,48,72,96,144,288]); ex['expected']=ex.q90.apply(lambda q: common[np.argmin(abs(common-q))])
 z=z.merge(ex[['idsensore','year','expected']],on=['idsensore','year']); z['value']=z['s'] if var=='precip' else z['mean']; z.loc[z.n<.8*z.expected,'value']=np.nan
 return z
def monthly(z,var):
 fn='sum' if var=='precip' else 'mean'; m=z.groupby(['idsensore','year','month'],as_index=False).agg(value=('value',fn),valid_days=('value','count'))
 m['days']=m.apply(lambda r: pd.Period(f'{int(r.year)}-{int(r.month):02d}').days_in_month,axis=1); m.loc[m.valid_days/m.days<.8,'value']=np.nan; return m
pr=monthly(daily(prec_files,'precip'),'precip'); tr=monthly(daily(temp_files,'temp'),'temp')
wm=pd.read_csv(base/'f54a3909-e823-449d-b276-5465d1e75ff2.csv'); wm['IdSensore']=pd.to_numeric(wm.IdSensore,errors='coerce').astype('Int64')
def link(panel,m,typ,prefix):
 wc=wm[wm.Tipologia.eq(typ)][['IdSensore','UTM_Est','UTM_Nord']].dropna().drop_duplicates('IdSensore'); wc=wc[wc.IdSensore.isin(m.idsensore.dropna().unique())]
 lookup={(int(y),int(mm)):g.set_index('idsensore')['value'] for (y,mm),g in m.groupby(['year','month'])}; rows=[]
 for r in panel[['station','year','gw_x','gw_y']].itertuples(index=False):
  rec={'station':r.station,'year':r.year}
  for mo in range(1,7):
   a=lookup.get((int(r.year),mo),pd.Series(dtype=float)).dropna(); c=wc[wc.IdSensore.isin(a.index)].copy()
   if len(c): c['dist']=np.sqrt((c.UTM_Est-r.gw_x)**2+(c.UTM_Nord-r.gw_y)**2)/1000; c=c[c.dist<=50].sort_values('dist').head(3)
   if len(c)>=2:
    vals=a.reindex(c.IdSensore).astype(float).values; dd=c.dist.values.astype(float); ww=1/np.maximum(dd,.5)**2; ww/=ww.sum(); rec[f'{prefix}{mo}']=float((vals*ww).sum())
   else: rec[f'{prefix}{mo}']=np.nan
  rows.append(rec)
 return pd.DataFrame(rows)
p=p.merge(link(p,pr,'Precipitazione','P'),on=['station','year']).merge(link(p,tr,'Temperatura','T'),on=['station','year'])
# create cumulative weather Jan-target and JanFeb
for t in [2,3,4,5,6]:
 ms=list(range(1,t+1)); p[f'P_J{t}']=p[[f'P{x}' for x in ms]].sum(axis=1,min_count=len(ms))
 days=np.array([31,28,31,30,31,30][:t],float) # leap ignored tiny for weighting
 vals=p[[f'T{x}' for x in ms]].to_numpy(float); p[f'T_J{t}']=np.where(np.isfinite(vals).all(1),(vals*days[:len(ms)]).sum(1)/days[:len(ms)].sum(),np.nan)
# within-station groundwater anomalies, useful predictor scale
for c in ['gw_prevaut','gw_janfeb','gw_m3','gw_m4','gw_m5','gw_m6']:
 if c in p: p[c+'_anom']=p[c]-p.groupby('station')[c].transform('mean')
# Test A: antecedent groundwater predicting current FF anomaly. Dep var FF anomaly, station/year FE + weather through relevant time.
rows=[]
def fit_ff(pred,weather_end):
 cols=['ff10_anom',pred,f'P_J{weather_end}',f'T_J{weather_end}','station','year']; r=p.dropna(subset=cols).copy()
 f=f'ff10_anom ~ {pred} + P_J{weather_end} + T_J{weather_end} + C(station)+C(year)'; m=smf.ols(f,r).fit(cov_type='cluster',cov_kwds={'groups':r.station});
 return m,r
# prior autumn no current weather logically; use year FE only
r=p.dropna(subset=['ff10_anom','gw_prevaut_anom','station','year']).copy(); m=smf.ols('ff10_anom ~ gw_prevaut_anom + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station}); rows.append(('FF outcome','prev Oct-Nov GW',m.params['gw_prevaut_anom'],m.pvalues['gw_prevaut_anom'],len(r),r.station.nunique()))
for pred,end,label in [('gw_janfeb_anom',2,'Jan-Feb GW'),('gw_m3_anom',3,'March GW'),('gw_m4_anom',4,'April GW'),('gw_m5_anom',5,'May GW'),('gw_m6_anom',6,'June GW')]:
 m,r=fit_ff(pred,end); rows.append(('FF outcome',label,m.params[pred],m.pvalues[pred],len(r),r.station.nunique()))
# Test B: groundwater outcome at each timing predicted by FF anomaly (same regression orientation as main), weather aligned. For Jan-Feb this is impossible reverse-time placebo because GW predates FF window.
def fit_gw(out,end):
 cols=[out,'ff10_anom',f'P_J{end}',f'T_J{end}','station','year']; r=p.dropna(subset=cols).copy(); f=f'{out} ~ ff10_anom + P_J{end} + T_J{end} + C(station)+C(year)'; m=smf.ols(f,r).fit(cov_type='cluster',cov_kwds={'groups':r.station}); return m,r
for out,end,label in [('gw_janfeb',2,'Jan-Feb GW'),('gw_m3',3,'March GW'),('gw_m4',4,'April GW'),('gw_m5',5,'May GW'),('gw_m6',6,'June GW')]:
 m,r=fit_gw(out,end); rows.append(('GW outcome',label,m.params['ff10_anom'],m.pvalues['ff10_anom'],len(r),r.station.nunique()))
res=pd.DataFrame(rows,columns=['orientation','timing','beta','p','N','wells']); print(res.to_string(index=False))
# correlations and FF window statement support metrics: number of Aug observations after June 30
# exact Aug dates sample linked to FF
au=gw[(gw.month==8)&(gw.year.between(2008,2021))].merge(p[['station','year','ff10_anom']],left_on=['CODICE','year'],right_on=['station','year'])
print('August exact dates N',len(au),'range',au.Data.min(),au.Data.max(),'all after Jun30',bool((au.Data.dt.month==8).all()))
res.to_csv(base/'simultaneity_results.csv',index=False); p.to_csv(base/'panel_simultaneity_test.csv',index=False)

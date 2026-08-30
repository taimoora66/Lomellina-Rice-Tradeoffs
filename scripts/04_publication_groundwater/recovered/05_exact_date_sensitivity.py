import pandas as pd, numpy as np
from pathlib import Path
import statsmodels.formula.api as smf
base=Path('/mnt/data')
# ---- groundwater clean ----
gw=pd.read_excel(base/'8c52fa50-368e-4ca0-97d6-77d30b15e129.xlsx')
gw['Data']=pd.to_datetime(gw['Data'],errors='coerce')
gw['depth']=pd.to_numeric(gw['Soggiacenza m da Qr'],errors='coerce')
gw=gw[gw['GroundWater Body (GWB_2015)'].astype(str).str.startswith('GWB ISS',na=False)].copy()
gw=gw[(gw.Data.dt.year>=2008)&(gw.Data.dt.year<=2021)&gw.depth.notna()]
# collapse exact dupes, exclude conflicting station-date measurements
rows=[]; conflicts=[]
for (st,dt),g in gw.groupby(['CODICE','Data'],sort=False):
    vals=np.unique(g.depth.dropna().values)
    if len(vals)==1:
        r=g.iloc[0].copy(); r['depth']=vals[0]; rows.append(r)
    elif len(vals)>1:
        conflicts.append((st,dt,vals.tolist()))
gc=pd.DataFrame(rows)
print('ISS raw',len(gw),'clean',len(gc),'conflicts',len(conflicts),conflicts[:3])
# ---- annual panel base with FF and pre ----
p=pd.read_csv(base/'panel_monthly_weather_test.csv')
p=p[p['gwb'].astype(str).str.startswith('GWB ISS',na=False)].copy()
p=p[['station','year','commune','pre','ff_10','ffw_10','ffb_10','gw_x','gw_y','gwb']].drop_duplicates(['station','year'])
p['ff10_mean']=p.groupby('station')['ff_10'].transform('mean')
p['ff10_anom']=p.ff_10-p.ff10_mean
# ---- interpolate fixed dates ----
def interp_station_year(g, year, month, day, maxgap=45):
    target=pd.Timestamp(year=year,month=month,day=day)
    gg=g[['Data','depth']].dropna().sort_values('Data')
    # exact observation / same day
    ex=gg[gg.Data.eq(target)]
    if not ex.empty: return float(ex.depth.mean()),0.,0.
    before=gg[gg.Data<target].tail(1)
    after=gg[gg.Data>target].head(1)
    if before.empty or after.empty: return np.nan,np.nan,np.nan
    db=(target-before.Data.iloc[0]).days; da=(after.Data.iloc[0]-target).days
    if db>maxgap or da>maxgap: return np.nan,db,da
    total=(after.Data.iloc[0]-before.Data.iloc[0]).days
    if total<=0: return np.nan,db,da
    w=(target-before.Data.iloc[0]).days/total
    v=float(before.depth.iloc[0]+w*(after.depth.iloc[0]-before.depth.iloc[0]))
    return v,float(db),float(da)

def build_fixed(maxgap):
    rec=[]
    groups={st:g for st,g in gc.groupby('CODICE')}
    for r in p[['station','year']].itertuples(index=False):
        g=groups.get(r.station)
        d={'station':r.station,'year':int(r.year)}
        if g is None:
            for m in [5,6,7,8]: d[f'd{m}15']=np.nan
        else:
            for m in [5,6,7,8]:
                v,db,da=interp_station_year(g,int(r.year),m,15,maxgap)
                d[f'd{m}15']=v; d[f'd{m}15_before_gap']=db; d[f'd{m}15_after_gap']=da
        rec.append(d)
    return p.merge(pd.DataFrame(rec),on=['station','year'],how='left')
# ---- daily weather ----
prec_files=[base/'a010663a-150f-4560-820d-2f0a663a130a.csv',base/'198768f4-08cf-4616-b902-44291c84719b.csv',base/'2354a6c0-98b3-4b8d-b22f-642d2594f52c.csv']
temp_files=[base/'80842682-0069-4a60-80ff-7b297c4b3bfc.csv',base/'666b0217-fa56-42c1-baeb-f78ccb95ea33.csv',base/'881348f3-0246-4881-b67c-f5e3744323be.csv']

def daily_from_files(files,var):
    out=[]
    for f in files:
        print('reading',f.name,var)
        chunks=[]
        for d in pd.read_csv(f,usecols=['idsensore','data','valore','stato'],chunksize=500000):
            d['data']=pd.to_datetime(d['data'],errors='coerce')
            d=d[(d['data'].dt.year>=2008)&(d['data'].dt.year<=2021)]
            d['idsensore']=pd.to_numeric(d['idsensore'],errors='coerce').astype('Int64')
            d['valore']=pd.to_numeric(d['valore'],errors='coerce')
            if var=='temp': d.loc[d.valore.eq(-999),'valore']=np.nan
            d.loc[d.stato.ne('VA'),'valore']=np.nan
            d['date']=d.data.dt.floor('D')
            if var=='precip':
                g=d.groupby(['idsensore','date'],as_index=False).agg(n=('valore','count'),s=('valore','sum'))
            else:
                g=d.groupby(['idsensore','date'],as_index=False).agg(n=('valore','count'),s=('valore','sum'))
            chunks.append(g)
        z=pd.concat(chunks,ignore_index=True).groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),s=('s','sum'))
        z['year']=z.date.dt.year
        ex=z.groupby(['idsensore','year'])['n'].quantile(.90).reset_index(name='q90')
        common=np.array([8,12,24,48,72,96,144,288])
        ex['expected']=ex.q90.apply(lambda q: common[np.argmin(abs(common-q))] if pd.notna(q) else np.nan)
        z=z.merge(ex[['idsensore','year','expected']],on=['idsensore','year'],how='left')
        z['valid_day']=z.n>=.8*z.expected
        z['value']=np.where(z.valid_day,z.s if var=='precip' else z.s/z.n.replace(0,np.nan),np.nan)
        out.append(z[['idsensore','date','year','value']])
    # periods non-overlap, but guard duplicates
    z=pd.concat(out,ignore_index=True)
    if z.duplicated(['idsensore','date']).any():
        # Shouldn't happen across period files. For temp average, precip sum duplicates unlikely.
        z=z.groupby(['idsensore','date','year'],as_index=False).agg(value=('value','mean' if var=='temp' else 'sum'))
    return z
pr=daily_from_files(prec_files,'precip'); tr=daily_from_files(temp_files,'temp')
wm=pd.read_csv(base/'f54a3909-e823-449d-b276-5465d1e75ff2.csv')
wm['IdSensore']=pd.to_numeric(wm.IdSensore,errors='coerce').astype('Int64')

def window_sensor(d, var, end_month, end_day=15):
    # Apr1 through target inclusive, require >=80% valid calendar days
    dd=d.copy(); dd['month']=dd.date.dt.month; dd['day']=dd.date.dt.day
    dd=dd[(dd['month']>=4)&((dd['month']<end_month)|((dd['month']==end_month)&(dd['day']<=end_day)))]
    aggfun='sum' if var=='precip' else 'mean'
    a=dd.groupby(['idsensore','year'],as_index=False).agg(value=('value',aggfun),valid_days=('value','count'))
    def ndays(y): return (pd.Timestamp(int(y),end_month,end_day)-pd.Timestamp(int(y),4,1)).days+1
    a['expected_days']=a.year.map(ndays); a['coverage']=a.valid_days/a.expected_days
    a.loc[a.coverage<.8,'value']=np.nan
    return a

# metadata subsets by variable
wcP=wm[wm.Tipologia.eq('Precipitazione')][['IdSensore','UTM_Est','UTM_Nord','NomeStazione']].dropna().drop_duplicates('IdSensore')
wcT=wm[wm.Tipologia.eq('Temperatura')][['IdSensore','UTM_Est','UTM_Nord','NomeStazione']].dropna().drop_duplicates('IdSensore')

def link_window(panel,agg,wc,prefix):
    wc=wc[wc.IdSensore.isin(agg.idsensore.unique())].copy()
    look={int(y):g.set_index('idsensore')['value'] for y,g in agg.groupby('year')}
    out=[]
    for r in panel[['station','year','gw_x','gw_y']].itertuples(index=False):
        a=look.get(int(r.year),pd.Series(dtype=float)).dropna()
        cand=wc[wc.IdSensore.isin(a.index)].copy()
        if not cand.empty:
            cand['dist']=np.sqrt((cand.UTM_Est-r.gw_x)**2+(cand.UTM_Nord-r.gw_y)**2)/1000
            cand=cand[cand.dist<=50].sort_values('dist').head(3)
        rec={'station':r.station,'year':r.year,prefix:np.nan,prefix+'_n':len(cand)}
        if len(cand)>=2:
            vals=a.reindex(cand.IdSensore).astype(float).values; dd=cand.dist.astype(float).values
            ww=1/np.maximum(dd,.5)**2; ww/=ww.sum(); rec[prefix]=float(np.sum(vals*ww)); rec[prefix+'_dmax']=float(dd.max())
        out.append(rec)
    return pd.DataFrame(out)

weather=p[['station','year','gw_x','gw_y']].copy()
for m in [6,7,8]:
    pa=window_sensor(pr,'precip',m,15); ta=window_sensor(tr,'temp',m,15)
    weather=weather.merge(link_window(p,pa,wcP,f'P_A{m}15'),on=['station','year'],how='left')
    weather=weather.merge(link_window(p,ta,wcT,f'T_A{m}15'),on=['station','year'],how='left')

# ---- fit fixed date interpolation at several max gaps ----
def fit_panel(q,target, direct=False):
    out=f'd{target}15' if direct else f'chg_{target}15'
    if not direct: q[out]=q[f'd{target}15']-q['d515']
    x=['ff10_anom',f'P_A{target}15',f'T_A{target}15','pre'] + (['d515'] if direct else [])
    cols=[out,'station','year']+x
    r=q.dropna(subset=cols).copy()
    f=out+' ~ '+' + '.join(x)+' + C(station)+C(year)'
    mod=smf.ols(f,r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
    return mod,r

allres=[]
for maxgap in [30,45,60]:
    q=build_fixed(maxgap).merge(weather.drop(columns=['gw_x','gw_y']),on=['station','year'],how='left')
    print('\nMAXGAP',maxgap)
    for target in [6,7,8]:
        m,r=fit_panel(q,target,False); term='ff10_anom'; ci=m.conf_int().loc[term].tolist()
        print('chg',target,'beta',m.params[term],'p',m.pvalues[term],'CI',ci,'N',len(r),'wells',r.station.nunique())
        allres.append([maxgap,target,'change',m.params[term],m.pvalues[term],ci[0],ci[1],len(r),r.station.nunique()])
    m,r=fit_panel(q,8,True);ci=m.conf_int().loc['ff10_anom'].tolist()
    print('direct8',m.params['ff10_anom'],m.pvalues['ff10_anom'],ci,'N',len(r),'wells',r.station.nunique())
    allres.append([maxgap,8,'direct',m.params['ff10_anom'],m.pvalues['ff10_anom'],ci[0],ci[1],len(r),r.station.nunique()])
    # Lead-lag at Aug for 45 only
    if maxgap==45:
        q=q.sort_values(['station','year'])
        q['lag']=q.groupby('station').ff10_anom.shift(1); q['lead']=q.groupby('station').ff10_anom.shift(-1)
        yl=q.groupby('station').year.shift(1); yd=q.groupby('station').year.shift(-1)
        q.loc[q.year-yl!=1,'lag']=np.nan; q.loc[yd-q.year!=1,'lead']=np.nan
        q['chg_815']=q.d815-q.d515
        cols=['chg_815','lag','ff10_anom','lead','P_A815','T_A815','pre','station','year']
        rr=q.dropna(subset=cols).copy()
        mm=smf.ols('chg_815 ~ lag + ff10_anom + lead + P_A815 + T_A815 + pre + C(station)+C(year)',rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station})
        print('leadlag45 N',len(rr),'wells',rr.station.nunique(),[(v,mm.params[v],mm.pvalues[v]) for v in ['lag','ff10_anom','lead']])

pd.DataFrame(allres,columns=['maxgap','target','outcome','beta','p','ci_lo','ci_hi','N','wells']).to_csv(base/'exact_date_results.csv',index=False)
print('\nSaved',base/'exact_date_results.csv')

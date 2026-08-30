import pandas as pd, numpy as np, os
from pathlib import Path
import statsmodels.formula.api as smf
from scipy import stats
base=Path('/mnt/data')
prec_files=[base/'a010663a-150f-4560-820d-2f0a663a130a.csv',base/'198768f4-08cf-4616-b902-44291c84719b.csv',base/'2354a6c0-98b3-4b8d-b22f-642d2594f52c.csv']
temp_files=[base/'80842682-0069-4a60-80ff-7b297c4b3bfc.csv',base/'666b0217-fa56-42c1-baeb-f78ccb95ea33.csv',base/'881348f3-0246-4881-b67c-f5e3744323be.csv']

def daily_from_files(files,var):
    out=[]
    for f in files:
        print('reading',f.name)
        chunks=[]
        for d in pd.read_csv(f,usecols=['idsensore','data','valore','stato'],chunksize=400000):
            d['data']=pd.to_datetime(d['data'],errors='coerce')
            d=d[(d['data'].dt.year>=2008)&(d['data'].dt.year<=2021)]
            d['idsensore']=pd.to_numeric(d['idsensore'],errors='coerce').astype('Int64')
            d['valore']=pd.to_numeric(d['valore'],errors='coerce')
            if var=='temp': d.loc[d['valore'].eq(-999),'valore']=np.nan
            d.loc[d['stato'].ne('VA'),'valore']=np.nan
            d['date']=d['data'].dt.floor('D')
            g=d.groupby(['idsensore','date'],as_index=False).agg(n=('valore','count'), s=('valore','sum'), mean=('valore','mean'))
            chunks.append(g)
        z=pd.concat(chunks,ignore_index=True)
        # combine chunk-split days exactly
        if var=='precip':
            z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'), s=('s','sum'))
        else:
            # Need weighted mean using daily chunks: reconstruct weighted sum = mean*n
            z['ws']=z['mean']*z['n']
            z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),ws=('ws','sum'))
            z['mean']=z['ws']/z['n'].replace(0,np.nan)
        out.append(z)
    z=pd.concat(out,ignore_index=True)
    # combine possible overlapping files (none expected)
    if var=='precip':
        z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),s=('s','sum'))
    else:
        z['ws']=z['mean']*z['n']
        z=z.groupby(['idsensore','date'],as_index=False).agg(n=('n','sum'),ws=('ws','sum'))
        z['mean']=z['ws']/z['n'].replace(0,np.nan)
    z['year']=z.date.dt.year; z['month']=z.date.dt.month
    # expected daily count per sensor-year: 90th percentile, snap to common cadences
    ex=z.groupby(['idsensore','year'])['n'].quantile(.90).reset_index(name='q90')
    common=np.array([8,12,24,48,72,96,144,288])
    ex['expected']=ex.q90.apply(lambda q: common[np.argmin(np.abs(common-q))] if pd.notna(q) else np.nan)
    z=z.merge(ex[['idsensore','year','expected']],on=['idsensore','year'],how='left')
    z['valid_day']=z['n']>=0.8*z['expected']
    if var=='precip': z['value']=z['s']
    else: z['value']=z['mean']
    z.loc[~z.valid_day,'value']=np.nan
    return z

def monthly(d,var):
    aggfun='sum' if var=='precip' else 'mean'
    m=d.groupby(['idsensore','year','month'],as_index=False).agg(value=('value',aggfun),valid_days=('value','count'))
    m['days']=m.apply(lambda r: pd.Period(f"{int(r.year)}-{int(r.month):02d}").days_in_month,axis=1)
    m['coverage']=m.valid_days/m.days
    m.loc[m.coverage<0.8,'value']=np.nan
    return m

pr=monthly(daily_from_files(prec_files,'precip'),'precip')
tr=monthly(daily_from_files(temp_files,'temp'),'temp')
print('monthly valid counts P',pr.value.notna().sum(),'T',tr.value.notna().sum())
# metadata and panel
p=pd.read_csv(base/'empirical_panel_preweather.csv')
gw=pd.read_excel(base/'8c52fa50-368e-4ca0-97d6-77d30b15e129.xlsx')
meta=(gw.sort_values('Data').groupby('CODICE',as_index=False).agg(gw_x=('X_WGS84','median'),gw_y=('Y_WGS84','median'),gwb=('GroundWater Body (GWB_2015)','first')))
p=p.merge(meta,left_on='station',right_on='CODICE',how='left')
wm=pd.read_csv(base/'f54a3909-e823-449d-b276-5465d1e75ff2.csv')
wm['IdSensore']=pd.to_numeric(wm.IdSensore,errors='coerce').astype('Int64')

# construct IDW weather each month Apr-Aug for each groundwater station-year, same fixed rule nearest 3 valid sensors <=50km min2
def link_month(panel,m,typ,prefix):
    wc=wm[wm.Tipologia.eq(typ)][['IdSensore','UTM_Est','UTM_Nord','NomeStazione']].dropna().drop_duplicates('IdSensore')
    wc=wc[wc.IdSensore.isin(m.idsensore.dropna().unique())]
    lookup={(int(y),int(mon)):g.set_index('idsensore')['value'] for (y,mon),g in m.groupby(['year','month'])}
    rows=[]
    for r in panel[['station','year','gw_x','gw_y']].itertuples(index=False):
        rec={'station':r.station,'year':r.year}
        for mon in range(4,9):
            a=lookup.get((int(r.year),mon),pd.Series(dtype=float)).dropna()
            cand=wc[wc.IdSensore.isin(a.index)].copy()
            if not cand.empty:
                cand['dist']=np.sqrt((cand.UTM_Est-r.gw_x)**2+(cand.UTM_Nord-r.gw_y)**2)/1000
                cand=cand[cand.dist<=50].sort_values('dist').head(3)
            if len(cand)>=2:
                vals=a.reindex(cand.IdSensore).astype(float).values
                dd=cand.dist.values.astype(float); ww=1/np.maximum(dd,.5)**2; ww/=ww.sum()
                rec[f'{prefix}{mon}']=float(np.sum(vals*ww)); rec[f'{prefix}{mon}_n']=len(cand); rec[f'{prefix}{mon}_dmax']=float(dd.max())
            else:
                rec[f'{prefix}{mon}']=np.nan; rec[f'{prefix}{mon}_n']=len(cand); rec[f'{prefix}{mon}_dmax']=np.nan
        rows.append(rec)
    return pd.DataFrame(rows)

pc=link_month(p,pr,'Precipitazione','P'); tc=link_month(p,tr,'Temperatura','T')
p=p.merge(pc,on=['station','year'],how='left').merge(tc,on=['station','year'],how='left')
# cumulative P sum; cumulative T weighted days (approx exact calendar weights)
for target in [6,7,8]:
    months=list(range(4,target+1))
    p[f'P_A{target}']=p[[f'P{m}' for m in months]].sum(axis=1,min_count=len(months))
    # weighted monthly means by days
    weights=np.array([30,31,30,31,31][:len(months)],dtype=float) # Apr-Aug
    vals=p[[f'T{m}' for m in months]].to_numpy(float)
    p[f'T_A{target}']=np.where(np.isfinite(vals).all(1),(vals*weights).sum(1)/weights.sum(),np.nan)
# spring outcome = aprmay column. target deltas
for m in [6,7,8]: p[f'd_spr_{m}']=p[f'm{m}']-p['aprmay']
# within FF anomaly, full available period station mean
p['ff10_mean']=p.groupby('station')['ff_10'].transform('mean');p['ff10_anom']=p.ff_10-p.ff10_mean
# lag lead anomaly by consecutive year only
p=p.sort_values(['station','year'])
p['ff_anom_lag']=p.groupby('station').ff10_anom.shift(1); p['yr_lag']=p.groupby('station').year.shift(1)
p['ff_anom_lead']=p.groupby('station').ff10_anom.shift(-1); p['yr_lead']=p.groupby('station').year.shift(-1)
p.loc[p.year-p.yr_lag!=1,'ff_anom_lag']=np.nan;p.loc[p.yr_lead-p.year!=1,'ff_anom_lead']=np.nan

# models: primary cumulative aligned weather, station + year FE, cluster station. Include spring GW state aprmay? Outcome delta already contains spring baseline; could include pre-season GW depth to account initial hydrologic state (pre). We'll report both with/without pre, primary includes pre.
def fit(target, weather='cum', leadlag=False, include_pre=True):
    out=f'd_spr_{target}'
    if weather=='cum': wx=[f'P_A{target}',f'T_A{target}']
    else: wx=['P4','P5',f'P{target}','T4','T5',f'T{target}']
    x=['ff10_anom']+wx+(['pre'] if include_pre else [])
    if leadlag: x=['ff_anom_lag','ff10_anom','ff_anom_lead']+wx+(['pre'] if include_pre else [])
    cols=[out,'station','year']+x
    r=p.dropna(subset=cols).copy()
    f=out+' ~ '+' + '.join(x)+' + C(station)+C(year)'
    mod=smf.ols(f,r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
    return mod,r

print('\nPRIMARY CUMULATIVE WEATHER + PRE')
results=[]
for target in [6,7,8]:
    m,r=fit(target,'cum',False,True); term='ff10_anom'
    ci=m.conf_int().loc[term].tolist(); results.append((target,m.params[term],m.pvalues[term],ci[0],ci[1],len(r),r.station.nunique()))
    print(target,results[-1])
print('\nLEAD LAG')
for target in [6,7,8]:
    m,r=fit(target,'cum',True,True)
    print(target,'N',len(r),'wells',r.station.nunique(),[(v,m.params[v],m.pvalues[v],m.conf_int().loc[v].tolist()) for v in ['ff_anom_lag','ff10_anom','ff_anom_lead']])
print('\nALT WEATHER separate spring+target month + PRE')
for target in [6,7,8]:
    m,r=fit(target,'separate',False,True); print(target,m.params['ff10_anom'],m.pvalues['ff10_anom'],len(r))
print('\nNO PRE sensitivity cumulative')
for target in [6,7,8]:
    m,r=fit(target,'cum',False,False); print(target,m.params['ff10_anom'],m.pvalues['ff10_anom'],len(r))

# weather coverage for eligible outcome by target
print('\ncoverage')
for target in [6,7,8]:
    mask=p[f'd_spr_{target}'].notna() & p.ff10_anom.notna()
    print(target,'outN',mask.sum(),'cum complete',p.loc[mask,[f'P_A{target}',f'T_A{target}']].notna().all(1).sum(),'pre complete',p.loc[mask,'pre'].notna().sum())

# save compact results/panel
p.to_csv(base/'panel_monthly_weather_test.csv',index=False)
pd.DataFrame(results,columns=['target_month','beta','p','ci_lo','ci_hi','N','wells']).to_csv(base/'monthly_timing_results.csv',index=False)

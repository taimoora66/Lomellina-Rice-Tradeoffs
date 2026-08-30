import pandas as pd, numpy as np
from pathlib import Path
from scipy.spatial.distance import cdist
import statsmodels.formula.api as smf

base=Path('/mnt/data')
# panel
p=pd.read_csv(base/'empirical_panel_preweather.csv')
# groundwater metadata
x=pd.read_excel(base/'8c52fa50-368e-4ca0-97d6-77d30b15e129.xlsx')
meta=(x.sort_values('Data').groupby('CODICE',as_index=False).agg(
    gw_x=('X_WGS84','median'),gw_y=('Y_WGS84','median'),gwb=('GroundWater Body (GWB_2015)','first'),commune2=('COMUNE','first')))
p=p.merge(meta,left_on='station',right_on='CODICE',how='left')
# outcome seasonal change + = deepening
p['d_may_aug']=p['m8']-p['m5']
# regime thresholds from prior analysis / pooled tertiles verify
q=p['ff_10'].quantile([1/3,2/3]); print('ff quantiles',q.to_dict())
lo,hi=q.iloc[0],q.iloc[1]
p['regime']=pd.cut(p.ff_10,[-np.inf,lo,hi,np.inf],labels=['Low','Mid','High'])

# weather master
wm=pd.read_csv(base/'f54a3909-e823-449d-b276-5465d1e75ff2.csv')
# file sets
prec_files=[base/'a010663a-150f-4560-820d-2f0a663a130a.csv',base/'198768f4-08cf-4616-b902-44291c84719b.csv',base/'2354a6c0-98b3-4b8d-b22f-642d2594f52c.csv']
temp_files=[base/'80842682-0069-4a60-80ff-7b297c4b3bfc.csv',base/'666b0217-fa56-42c1-baeb-f78ccb95ea33.csv',base/'881348f3-0246-4881-b67c-f5e3744323be.csv']

def read_weather(files,var):
    parts=[]
    for f in files:
        d=pd.read_csv(f,usecols=['idsensore','data','valore','stato'])
        d['idsensore']=pd.to_numeric(d.idsensore,errors='coerce').astype('Int64')
        d['data']=pd.to_datetime(d.data,errors='coerce')
        d['valore']=pd.to_numeric(d.valore,errors='coerce')
        d=d[(d.data.dt.year>=2008)&(d.data.dt.year<=2021)]
        if var=='temp': d.loc[d.valore==-999,'valore']=np.nan
        # keep VA only for measurement values; -999 blanks already nan
        d.loc[d.stato.ne('VA'),'valore']=np.nan
        parts.append(d[['idsensore','data','valore']])
    d=pd.concat(parts,ignore_index=True).drop_duplicates(['idsensore','data'])
    return d

def aggregate_weather(d,var):
    # estimate expected observations/day per sensor-year-month via median positive timestamp gap global sensor segment
    d=d.sort_values(['idsensore','data'])
    # master typical interval per sensor based on mode rounded minutes
    exp={}
    for sid,g in d.dropna(subset=['valore']).groupby('idsensore'):
        dif=g.data.diff().dt.total_seconds().div(60)
        dif=dif[(dif>0)&(dif<=180)]
        if len(dif):
            med=float(dif.median()); exp[sid]=max(1,round(1440/med))
    d['date']=d.data.dt.floor('D')
    # observations and agg among valid
    if var=='precip':
        day=d.groupby(['idsensore','date']).agg(value=('valore','sum'),n=('valore','count')).reset_index()
    else:
        day=d.groupby(['idsensore','date']).agg(value=('valore','mean'),n=('valore','count')).reset_index()
    day['expected']=day.idsensore.map(exp)
    day['ok']=day.n>=0.8*day.expected
    day.loc[~day.ok,'value']=np.nan
    day['year']=day.date.dt.year
    day['month']=day.date.dt.month
    # target May-Aug controls; include Apr-Aug also outputs
    outs=[]
    for months,label in [([5,6,7,8],'mayaug'),([4,5,6,7,8],'apraug'),([6,7,8],'jja')]:
        z=day[day.month.isin(months)].copy()
        aggfun='sum' if var=='precip' else 'mean'
        a=z.groupby(['idsensore','year']).agg(val=('value',aggfun), valid_days=('value','count'), total_days=('date','nunique')).reset_index()
        # expected calendar days in window varies leap only Feb irrelevant => fixed
        ndays=sum(pd.Period(f'2021-{m:02d}').days_in_month for m in months)
        a['coverage']=a.valid_days/ndays
        a.loc[a.coverage<0.8,'val']=np.nan
        a['window']=label
        outs.append(a)
    return pd.concat(outs,ignore_index=True),exp

pr=read_weather(prec_files,'precip'); tr=read_weather(temp_files,'temp')
pa,pexp=aggregate_weather(pr,'precip'); ta,texp=aggregate_weather(tr,'temp')
print('weather rows',len(pr),len(tr),'sensor counts',pr.idsensore.nunique(),tr.idsensore.nunique())
# sensor coords
wcoords=wm[['IdSensore','Tipologia','UTM_Est','UTM_Nord','NomeStazione']].copy()
wcoords['IdSensore']=pd.to_numeric(wcoords.IdSensore,errors='coerce').astype('Int64')
# Link each groundwater station-year-window to nearest 3 active valid weather sensors within 50 km IDW^2

def link_controls(panel, agg, typ, prefix):
    wc=wcoords[wcoords.Tipologia.eq(typ)].dropna(subset=['UTM_Est','UTM_Nord']).drop_duplicates('IdSensore')
    out=panel[['station','year','gw_x','gw_y']].copy()
    # actually only sensors present in agg
    wc=wc[wc.IdSensore.isin(agg.idsensore.unique())].copy()
    for window in ['mayaug','apraug','jja']:
        A=agg[agg.window.eq(window)].pivot(index='year',columns='idsensore',values='val')
        vals=[]; nused=[]; dmax=[]
        for row in out.itertuples(index=False):
            if pd.isna(row.gw_x) or row.year not in A.index:
                vals.append(np.nan);nused.append(0);dmax.append(np.nan);continue
            a=A.loc[row.year]
            avail=a.dropna().index
            cand=wc[wc.IdSensore.isin(avail)].copy()
            if cand.empty:
                vals.append(np.nan);nused.append(0);dmax.append(np.nan);continue
            dist=np.sqrt((cand.UTM_Est-row.gw_x)**2+(cand.UTM_Nord-row.gw_y)**2)/1000
            cand=cand.assign(dist=dist.values).query('dist<=50').sort_values('dist').head(3)
            if len(cand)<2:
                vals.append(np.nan);nused.append(len(cand));dmax.append(cand.dist.max() if len(cand) else np.nan);continue
            vv=a.reindex(cand.IdSensore).astype(float).values
            dd=cand.dist.values.astype(float)
            ww=1/np.maximum(dd,0.5)**2; ww/=ww.sum()
            vals.append(float(np.sum(vv*ww)));nused.append(len(cand));dmax.append(float(dd.max()))
        out[f'{prefix}_{window}']=vals;out[f'{prefix}_{window}_n']=nused;out[f'{prefix}_{window}_dmax']=dmax
    return out

pc=link_controls(p,pa,'Precipitazione','P')
tc=link_controls(p,ta,'Temperatura','T')
keys=['station','year']
ctrl=pc.merge(tc,on=['station','year','gw_x','gw_y'])
p=p.merge(ctrl.drop(columns=['gw_x','gw_y']),on=keys,how='left')
p.to_csv(base/'panel_event_weather.csv',index=False)
print('weather coverage on d sample',p.loc[p.d_may_aug.notna(),['P_mayaug','T_mayaug']].notna().mean().to_dict())

# Identify durable downward transition: first year where regime is lower than prior persistent state and stays at/ below new state >=3 consecutive years.
# Focus first durable entry into Low from Mid/High, require >=2 pre years non-Low and >=3 low years including transition.
events=[]
for st,g in p.sort_values('year').groupby('station'):
    gg=g.set_index('year')
    years=sorted(gg.index)
    for y in years:
        if y<2010 or y>2019: continue # need two pre and two post for event windows
        if not all(k in gg.index for k in [y-2,y-1,y,y+1,y+2]): continue
        pre=gg.loc[[y-2,y-1],'regime'].astype(str)
        post=gg.loc[[y,y+1,y+2],'regime'].astype(str)
        if (pre!='Low').all() and (post=='Low').all():
            events.append((st,y,gg.loc[y-1,'regime']))
            break
print('durable low events',len(events),events)

# construct event sample +-4 where available, first event per station
emap=dict((st,y) for st,y,_ in events)
p['event_year']=p.station.map(emap)
p['event_time']=p.year-p.event_year
es=p[p.event_year.notna() & p.event_time.between(-4,4)].copy()
print('event obs outcome',es.d_may_aug.notna().sum(),'stations',es.loc[es.d_may_aug.notna(),'station'].nunique())
# event summaries raw and weather residualized
print(es.groupby('event_time').agg(n=('d_may_aug','count'),wells=('station','nunique'),mean_delta=('d_may_aug','mean'),mean_ff=('ff_10','mean')).to_string())

# Regression event study on treated-event stations only: station + calendar-year FE, P/T, omit -1.
# This is descriptive association around transition, not causal staggered DiD.
reg=es.dropna(subset=['d_may_aug','P_mayaug','T_mayaug']).copy()
# collapse tails? use -3..3 to improve coverage
reg=reg[reg.event_time.between(-3,3)].copy()
# create dummies manually avoiding formula minus names
for k in [-3,-2,0,1,2,3]: reg[f'et_{"m"+str(abs(k)) if k<0 else "p"+str(k)}']=(reg.event_time==k).astype(int)
terms=['et_m3','et_m2','et_p0','et_p1','et_p2','et_p3']
formula='d_may_aug ~ '+' + '.join(terms)+' + P_mayaug + T_mayaug + C(station) + C(year)'
mod=smf.ols(formula,reg).fit(cov_type='cluster',cov_kwds={'groups':reg.station})
print('\nEVENT REG')
for t in terms: print(t,mod.params.get(t),mod.pvalues.get(t),mod.conf_int().loc[t].tolist())
# joint pretrend m3/m2
print('pretrend F/Wald',mod.wald_test('et_m3=0, et_m2=0',scalar=True))
# post average using post indicator with pre window -3..-1 vs post 0..3, event station FE/year FE/weather
reg2=es[es.event_time.between(-3,3)].dropna(subset=['d_may_aug','P_mayaug','T_mayaug']).copy()
reg2['post']=(reg2.event_time>=0).astype(int)
mod2=smf.ols('d_may_aug ~ post + P_mayaug + T_mayaug + C(station) + C(year)',reg2).fit(cov_type='cluster',cov_kwds={'groups':reg2.station})
print('post coeff',mod2.params['post'],mod2.pvalues['post'],mod2.conf_int().loc['post'].tolist(), 'N',len(reg2),'wells',reg2.station.nunique())

# Placebo timing: shift event year -2,+2 and estimate post-like local window [-3,3] based on fake event; this is rough
for shift in [-2,2]:
    rr=p[p.station.isin(emap)].copy(); rr['fake_event']=rr.station.map(emap)+shift; rr['tau']=rr.year-rr.fake_event
    rr=rr[rr.tau.between(-3,3)].dropna(subset=['d_may_aug','P_mayaug','T_mayaug'])
    rr['post']=(rr.tau>=0).astype(int)
    mm=smf.ols('d_may_aug ~ post + P_mayaug + T_mayaug + C(station) + C(year)',rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station})
    print('fake shift',shift,'post',mm.params['post'],mm.pvalues['post'])

# Alternative continuous within-station FF anomaly model on delta with weather + station/year FE, and leads/lags
q=p.sort_values(['station','year']).copy(); q['ff_lag']=q.groupby('station').ff_10.shift(1);q['ff_lead']=q.groupby('station').ff_10.shift(-1)
r=q.dropna(subset=['d_may_aug','P_mayaug','T_mayaug','ff_10','ff_lag','ff_lead'])
m3=smf.ols('d_may_aug ~ ff_lag + ff_10 + ff_lead + P_mayaug + T_mayaug + C(station)+C(year)',r).fit(cov_type='cluster',cov_kwds={'groups':r.station})
print('continuous lag/current/lead',[(v,m3.params[v],m3.pvalues[v]) for v in ['ff_lag','ff_10','ff_lead']], 'N',len(r))

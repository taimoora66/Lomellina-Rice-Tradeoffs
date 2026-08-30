import pandas as pd, numpy as np
import statsmodels.formula.api as smf
p=pd.read_csv('/mnt/data/panel_monthly_weather_test.csv')
p=p.sort_values(['station','year'])
# create anomalies for variants and lags/leads
for v in ['ff_10','ffw_10','ffb_10']:
    an=v+'_anom'; p[an]=p[v]-p.groupby('station')[v].transform('mean')
    p[an+'_lag']=p.groupby('station')[an].shift(1); p[an+'_lead']=p.groupby('station')[an].shift(-1)
# valid consecutive years
yl=p.groupby('station').year.shift(1); yd=p.groupby('station').year.shift(-1)
for v in ['ff_10','ffw_10','ffb_10']:
    an=v+'_anom'; p.loc[p.year-yl!=1,an+'_lag']=np.nan;p.loc[yd-p.year!=1,an+'_lead']=np.nan
# centered coords scaled 100km
p['x100']=(p.gw_x-p.gw_x.mean())/100000;p['y100']=(p.gw_y-p.gw_y.mean())/100000
basecols=['d_spr_8','P_A8','T_A8','pre','station','year','gwb']

def est(form, cols):
 r=p.dropna(subset=cols).copy(); m=smf.ols(form,r).fit(cov_type='cluster',cov_kwds={'groups':r.station}); return m,r
specs={
'baseline':'d_spr_8 ~ ff_10_anom + P_A8 + T_A8 + pre + C(station)+C(year)',
'gwb_year':'d_spr_8 ~ ff_10_anom + P_A8 + T_A8 + pre + C(station)+C(gwb):C(year)',
'spatial_year_grad':'d_spr_8 ~ ff_10_anom + P_A8 + T_A8 + pre + C(station)+C(year) + C(year):x100 + C(year):y100',
}
for name,f in specs.items():
 cols=basecols+['ff_10_anom']+(['x100','y100'] if name=='spatial_year_grad' else [])
 m,r=est(f,cols)
 print(name,m.params['ff_10_anom'],m.pvalues['ff_10_anom'],m.conf_int().loc['ff_10_anom'].tolist(),len(r),r.station.nunique())
# exposure variants
for v in ['ffw_10','ffb_10']:
 an=v+'_anom'; cols=basecols+[an]
 f=f'd_spr_8 ~ {an} + P_A8 + T_A8 + pre + C(station)+C(year)'
 m,r=est(f,cols); print(v,m.params[an],m.pvalues[an],m.conf_int().loc[an].tolist(),len(r),r.station.nunique())
# LOO baseline
r=p.dropna(subset=basecols+['ff_10_anom']).copy()
vals=[]
for st in r.station.unique():
 rr=r[r.station!=st]; m=smf.ols('d_spr_8 ~ ff_10_anom + P_A8 + T_A8 + pre + C(station)+C(year)',rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station}); vals.append((st,m.params['ff_10_anom'],m.pvalues['ff_10_anom']))
print('LOO beta min med max',min(x[1] for x in vals),np.median([x[1] for x in vals]),max(x[1] for x in vals),'p sig<.05',sum(x[2]<.05 for x in vals),'/',len(vals))
# leave-year-out
vals_y=[]
for y in sorted(r.year.unique()):
 rr=r[r.year!=y]; m=smf.ols('d_spr_8 ~ ff_10_anom + P_A8 + T_A8 + pre + C(station)+C(year)',rr).fit(cov_type='cluster',cov_kwds={'groups':rr.station}); vals_y.append((y,m.params['ff_10_anom'],m.pvalues['ff_10_anom']))
print('LOY')
print(vals_y)
# lead-lag under richer specs
for name,extra in [('baseline','C(station)+C(year)'),('gwb_year','C(station)+C(gwb):C(year)'),('spatial','C(station)+C(year)+C(year):x100+C(year):y100')]:
 cols=basecols+['ff_10_anom_lag','ff_10_anom','ff_10_anom_lead']+(['x100','y100'] if name=='spatial' else [])
 r2=p.dropna(subset=cols).copy()
 f='d_spr_8 ~ ff_10_anom_lag+ff_10_anom+ff_10_anom_lead+P_A8+T_A8+pre+'+extra
 m=smf.ols(f,r2).fit(cov_type='cluster',cov_kwds={'groups':r2.station})
 print('LL',name,len(r2),[(v,float(m.params[v]),float(m.pvalues[v])) for v in ['ff_10_anom_lag','ff_10_anom','ff_10_anom_lead']])

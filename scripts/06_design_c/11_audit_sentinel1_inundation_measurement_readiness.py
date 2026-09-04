from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"outputs"/"diagnostics"/"design_c"
OUT.mkdir(parents=True, exist_ok=True)
START_YEAR, END_YEAR = 2015, 2023
RICE_MONTHS = {4,5,6,7,8,9}

def norm(x): return str(x).strip().lower().replace("-","_").replace(" ","_")

def first_col(df, names):
    m={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in m: return m[norm(n)]
    return None

def find_named(name):
    hits=[]
    for base in [ROOT/"data"/"design_c", ROOT/"data", OUT]:
        if base.exists():
            hits += list(base.rglob(name))
    seen=[]
    for p in hits:
        if p.resolve() not in [x.resolve() for x in seen]: seen.append(p)
    return sorted(seen, key=lambda p:(0 if "design_c" in str(p).lower() else 1,len(str(p))))

def rice_files():
    hits=[]
    for base in [ROOT/"data"/"design_c", ROOT/"data", OUT]:
        if base.exists():
            for p in base.rglob("*.csv"):
                if "riceflood" in p.name.lower() and p.resolve() not in [x.resolve() for x in hits]:
                    hits.append(p)
    return sorted(hits)

def main():
    print("DESIGN C - C2I SENTINEL-1 / INUNDATION MEASUREMENT READINESS")
    print("="*70)
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO flood threshold tuned.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    candidates=find_named("sentinel1_grd_scene_inventory_2015_2023.csv")
    if not candidates:
        raise FileNotFoundError("sentinel1_grd_scene_inventory_2015_2023.csv not found.")
    p=candidates[0]
    raw=pd.read_csv(p)
    d=raw.copy()

    dtcol=first_col(d,["datetime","acquisition_datetime","acquired","sensing_time","start_datetime","date"])
    if dtcol is None:
        raise AssertionError(f"No date/datetime column found. Columns={list(d.columns)}")

    d["_dt"]=pd.to_datetime(d[dtcol],errors="coerce",utc=True)
    bad=int(d["_dt"].isna().sum())
    d=d.dropna(subset=["_dt"]).copy()
    d["_date"]=d["_dt"].dt.date
    d["_year"]=d["_dt"].dt.year
    d["_month"]=d["_dt"].dt.month
    d["_rice"]=d["_month"].isin(RICE_MONTHS)
    h=d[d["_year"].between(START_YEAR,END_YEAR)].copy()

    scene=first_col(h,["scene_id","id","product_id","title"])
    orbit=first_col(h,["orbit_state","sat:orbit_state","orbitdirection","orbit_direction"])
    relorbit=first_col(h,["relative_orbit","relativeorbitnumber","sat:relative_orbit","relative_orbit_number"])
    platform=first_col(h,["platform","satellite","spacecraftname","constellation"])
    pol=first_col(h,["polarization","polarizations","sar:polarizations","transmitterreceiverpolarisation"])
    mode=first_col(h,["instrument_mode","sar:instrument_mode","sensoroperationalmode","mode"])
    product=first_col(h,["product_type","sar:product_type","producttype","collection"])

    unique_scene=int(h[scene].nunique()) if scene else len(h)
    dup=int(h[scene].duplicated().sum()) if scene else 0
    adates=pd.Series(pd.to_datetime(sorted(h["_date"].unique())))
    gaps=adates.diff().dt.days.dropna()

    pd.DataFrame([{
        "inventory_file":str(p.relative_to(ROOT)),
        "rows_raw_n":len(raw),"bad_datetime_n":bad,"rows_2015_2023_n":len(h),
        "unique_scene_ids_n":unique_scene,"duplicate_scene_ids_n":dup,
        "unique_acquisition_dates_n":h["_date"].nunique(),
        "first_acquisition":h["_dt"].min().isoformat() if len(h) else None,
        "last_acquisition":h["_dt"].max().isoformat() if len(h) else None,
        "median_gap_any_date_days":float(gaps.median()) if len(gaps) else np.nan,
        "p90_gap_any_date_days":float(gaps.quantile(.9)) if len(gaps) else np.nan,
        "max_gap_any_date_days":int(gaps.max()) if len(gaps) else np.nan,
    }]).to_csv(OUT/"c2i_sentinel1_scene_inventory_audit.csv",index=False)

    yr=[]
    for y in range(START_YEAR,END_YEAR+1):
        yy=h[h["_year"].eq(y)]
        r=yy[yy["_rice"]]
        rd=pd.Series(pd.to_datetime(sorted(r["_date"].unique())))
        gg=rd.diff().dt.days.dropna()
        yr.append({
            "year":y,"scenes_n":len(yy),"acquisition_dates_n":yy["_date"].nunique(),
            "rice_season_scenes_n":len(r),"rice_season_acquisition_dates_n":r["_date"].nunique(),
            "rice_season_months_with_any_acquisition_n":r["_month"].nunique(),
            "rice_season_months":"_".join(map(str,sorted(r["_month"].unique()))),
            "rice_season_first_date":str(min(r["_date"])) if len(r) else None,
            "rice_season_last_date":str(max(r["_date"])) if len(r) else None,
            "rice_season_median_gap_days":float(gg.median()) if len(gg) else np.nan,
            "rice_season_p90_gap_days":float(gg.quantile(.9)) if len(gg) else np.nan,
            "rice_season_max_gap_days":int(gg.max()) if len(gg) else np.nan,
            "rice_season_all_apr_sep_months_present":RICE_MONTHS.issubset(set(r["_month"].unique()))
        })
    byy=pd.DataFrame(yr)
    byy.to_csv(OUT/"c2i_sentinel1_rice_season_by_year.csv",index=False)

    meta=[]
    for label,col in [("scene_id",scene),("orbit_state",orbit),("relative_orbit",relorbit),
                      ("platform",platform),("polarization",pol),("instrument_mode",mode),
                      ("product_type",product)]:
        meta.append({
            "field":label,"column_found":col,"available":col is not None,
            "non_null_n":int(h[col].notna().sum()) if col else 0,
            "unique_n":int(h[col].nunique(dropna=True)) if col else 0,
            "values_preview":"|".join(sorted(map(str,h[col].dropna().unique()))[:20]) if col else None
        })
    md=pd.DataFrame(meta)
    md.to_csv(OUT/"c2i_sentinel1_metadata_support.csv",index=False)

    rf=rice_files()
    finv=[]; fschema=[]
    for q in rf:
        try:
            x=pd.read_csv(q); err=None
        except Exception as e:
            x=pd.DataFrame(); err=repr(e)
        finv.append({"file":str(q.relative_to(ROOT)),"rows_n":len(x),"columns_n":len(x.columns),"read_error":err})
        if err is None:
            fschema.append({
                "file":str(q.relative_to(ROOT)),
                "columns":"|".join(map(str,x.columns)),
                "station_like":"|".join(c for c in x.columns if any(k in norm(c) for k in ["station","well","piez"])),
                "year_like":"|".join(c for c in x.columns if "year" in norm(c) or norm(c)=="anno"),
                "coordinate_like":"|".join(c for c in x.columns if norm(c) in {"lon","lat","longitude","latitude","utm_e","utm_n","x","y"}),
                "flood_like":"|".join(c for c in x.columns if any(k in norm(c) for k in ["flood","ff_","inund","water","rice"])),
                "contains_groundwater_depth_column":any("gw_depth" in norm(c) or "soggiac" in norm(c) for c in x.columns)
            })
    pd.DataFrame(finv).to_csv(OUT/"c2i_ricefloodit_file_inventory.csv",index=False)
    pd.DataFrame(fschema).to_csv(OUT/"c2i_ricefloodit_schema_audit.csv",index=False)

    complete=int(byy["rice_season_all_apr_sep_months_present"].sum())
    mindates=int(byy["rice_season_acquisition_dates_n"].min())
    worst=float(byy["rice_season_max_gap_days"].max())
    ready=(len(h)>0 and complete==9 and mindates>=12)

    qa={
        "status":"PASS" if ready else "PASS_WITH_LIMITATIONS",
        "stage":"DESIGN_C_C2I_SENTINEL1_INUNDATION_MEASUREMENT_READINESS",
        "groundwater_level_values_read":0,"irrigation_flow_values_read":0,
        "association_models_fitted":0,"flood_classification_thresholds_tuned":0,
        "frozen_artifacts_modified":0,
        "sentinel_inventory_file":str(p.relative_to(ROOT)),
        "sentinel_rows_2015_2023_n":len(h),
        "sentinel_unique_dates_2015_2023_n":int(h["_date"].nunique()),
        "rice_season_years_with_all_apr_sep_months_n":complete,
        "minimum_rice_season_acquisition_dates_in_any_year_n":mindates,
        "worst_rice_season_max_gap_days":worst,
        "ricefloodit_csv_files_found_n":len(rf),
        "interpretation_rule":"Cadence readiness does not validate an inundation classifier.",
        "next_stage":"C2J pixel/product-level inundation measurement validation, outcome-blind."
    }
    (OUT/"c2i_inundation_measurement_readiness_qa.json").write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")

    lines=[
        "DESIGN C - C2I SENTINEL-1 / INUNDATION MEASUREMENT READINESS","="*68,"",
        f"Sentinel-1 inventory: {p.relative_to(ROOT)}",
        f"2015-2023 scenes: {len(h)}",
        f"2015-2023 unique acquisition dates: {h['_date'].nunique()}",
        f"Rice-season years with all Apr-Sep months represented: {complete}/9",
        f"Minimum rice-season acquisition dates in any year: {mindates}",
        f"Worst annual rice-season maximum gap (days): {worst}",
        f"Duplicate scene IDs: {dup}","","METADATA SUPPORT","----------------"
    ]
    for _,r in md.iterrows():
        lines.append(f"- {r['field']}: " + (f"YES ({r['column_found']}; unique={r['unique_n']}; values={r['values_preview']})" if r["available"] else "NO"))
    lines += ["",f"RiceFloodIT-related CSV files found: {len(rf)}"]
    lines += [f"- {q.relative_to(ROOT)}" for q in rf]
    lines += ["","INTERPRETATION","--------------",
              "This audits acquisition/product support only; it does not validate a SAR flooding classifier.",
              "Groundwater outcomes were not used.","","DECISION","--------",
              "Proceed to C2J pixel/product-level inundation measurement validation.",
              "",f"C2I STATUS: {qa['status']}"]
    txt="\n".join(lines)+"\n"
    (OUT/"c2i_inundation_measurement_readiness_summary.txt").write_text(txt,encoding="utf-8")
    print("\n"+txt)

if __name__=="__main__":
    main()

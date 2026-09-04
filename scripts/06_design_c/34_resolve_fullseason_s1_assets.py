"""Design C — canonical C2U full-season Sentinel-1 asset resolution.

Consolidated from the validated C2U -> C2U-R -> C2U-RR lineage.

Preserved behavior:
- frozen C2T temporal candidate universe is immutable;
- retry/backoff and HTTP 429 recovery from C2U-R;
- outcome-blind IW + VV/VH technical measurement eligibility from C2U-RR;
- technical exclusions are retained in the audit trail;
- canonicalization and asset planning operate only on measurement-eligible scenes;
- no SAR pixels, groundwater, RiceFloodIT flooding outcomes, threshold, or classifier.

This file replaces the three operational versions 34, 34R and 34RR.
"""
from __future__ import annotations
import json,re,time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"outputs"/"diagnostics"/"design_c"; OUT.mkdir(parents=True,exist_ok=True)
DESIGN=OUT/"c2t_frozen_s1_temporal_design.csv"
CACHE=OUT/"c2u_item_cache"; CACHE.mkdir(parents=True,exist_ok=True)
ITEM_OUT=OUT/"c2u_item_metadata.csv"
ASSET_OUT=OUT/"c2u_asset_inventory.csv"
DUP_OUT=OUT/"c2u_duplicate_groups.csv"
CANON_OUT=OUT/"c2u_scene_canonicalization.csv"
PLAN_OUT=OUT/"c2u_fullseason_canonical_asset_plan.csv"
QA_OUT=OUT/"c2u_fullseason_asset_plan_qa.json"
TXT_OUT=OUT/"c2u_fullseason_asset_plan_summary.txt"
STAC="https://stac.dataspace.copernicus.eu/v1"
COLL="sentinel-1-grd"
TRACKS={("ascending",15),("ascending",88),("descending",66),("descending",168)}
MAX_ATTEMPTS=12
BASE_DELAY_S=5.0
SUCCESS_PACING_S=0.35
MAX_BACKOFF_S=120.0

def item_url(s): return f"{STAC}/collections/{COLL}/items/"+quote(s,safe="")
def cpath(s): return CACHE/(re.sub(r"[^A-Za-z0-9_.-]+","_",s)+".json")
def fetch(s):
    cp=cpath(s)
    if cp.exists():
        try:
            x=json.loads(cp.read_text(encoding="utf-8"))
            if str(x.get("id"))==s:
                return x,"CACHE",0
        except Exception:
            pass

    last=None
    for a in range(1,MAX_ATTEMPTS+1):
        try:
            req=Request(
                item_url(s),
                headers={
                    "User-Agent":"DesignC-C2U-fullseason-rate-limit-recovery/1.0",
                    "Accept":"application/geo+json, application/json;q=0.9,*/*;q=0.1",
                },
            )
            with urlopen(req,timeout=120) as r:
                x=json.loads(r.read())

            if str(x.get("id"))!=s:
                raise RuntimeError("STAC item id mismatch")

            tmp=cp.with_suffix(".tmp")
            tmp.write_text(json.dumps(x),encoding="utf-8")
            tmp.replace(cp)

            # Gentle proactive pacing after every successful remote request.
            time.sleep(SUCCESS_PACING_S)
            return x,"REMOTE",a

        except HTTPError as e:
            last=repr(e)

            if e.code == 429:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    retry_after_s = float(retry_after) if retry_after is not None else None
                except Exception:
                    retry_after_s = None

                exponential = BASE_DELAY_S * (2 ** (a-1))
                delay = retry_after_s if retry_after_s is not None else exponential
                delay = min(max(delay, BASE_DELAY_S), MAX_BACKOFF_S)

                if a < MAX_ATTEMPTS:
                    print(
                        f"    attempt {a} rate-limited (HTTP 429); "
                        f"sleeping {delay:.1f}s before retry...",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
            else:
                if a < MAX_ATTEMPTS:
                    delay=min(BASE_DELAY_S*a,MAX_BACKOFF_S)
                    print(
                        f"    attempt {a} HTTP {e.code} failed: {last}; "
                        f"retrying in {delay:.1f}s...",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue

        except Exception as e:
            last=repr(e)
            if a < MAX_ATTEMPTS:
                delay=min(BASE_DELAY_S*a,MAX_BACKOFF_S)
                print(
                    f"    attempt {a} failed: {last}; retrying in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)
                continue

    raise RuntimeError(f"Failed STAC resolution for {s}: {last}")

def norm(x): return str(x).strip().lower()
def pol_asset(r):
    text=" ".join([norm(r.get("asset_key","")),norm(r.get("title","")),norm(r.get("href",""))])
    vv=bool(re.search(r"(^|[^a-z0-9])vv([^a-z0-9]|$)",text))
    vh=bool(re.search(r"(^|[^a-z0-9])vh([^a-z0-9]|$)",text))
    if vv and not vh:return "VV"
    if vh and not vv:return "VH"
    return None
def bbox_key(x):
    try:
        b=json.loads(x) if isinstance(x,str) else x
        return tuple(round(float(v),6) for v in b[:4]) if b and len(b)>=4 else None
    except Exception:return None
def platform_norm(s,p):
    q=str(p).strip().upper()
    m={"SENTINEL-1A":"S1A","SENTINEL-1B":"S1B","SENTINEL-1C":"S1C"}
    if q in m:return m[q]
    if q in {"S1A","S1B","S1C"}:return q
    return str(s)[:3].upper()

def main():
    print("DESIGN C - C2U-RR TECHNICAL ELIGIBILITY + FULL-SEASON ASSET PLAN")
    print("="*78)
    print("METADATA ONLY. No SAR pixels / groundwater / flood outcomes.\n")
    if not DESIGN.exists(): raise FileNotFoundError(DESIGN)
    d=pd.read_csv(DESIGN,low_memory=False)
    req={"scene_id","acquisition_datetime","orbit_state","relative_orbit","year","acquisition_date","temporal_design_included"}
    miss=req-set(d.columns)
    if miss: raise AssertionError(f"C2T missing columns: {sorted(miss)}")
    d=d[d.temporal_design_included.astype(str).str.lower().isin(["true","1","yes"])].copy()
    d["scene_id"]=d.scene_id.astype(str)
    d["orbit_state"]=d.orbit_state.astype(str).str.lower().str.strip()
    d["relative_orbit"]=pd.to_numeric(d.relative_orbit).astype(int)
    d["year"]=pd.to_numeric(d.year).astype(int)
    if d.scene_id.duplicated().any(): raise AssertionError("Duplicate scene_id in C2T.")
    if set(zip(d.orbit_state,d.relative_orbit))!=TRACKS: raise AssertionError("C2T track universe changed.")
    if (d.year.min(),d.year.max())!=(2015,2025): raise AssertionError("C2T year range changed.")
    scenes=sorted(d.scene_id.unique())
    print(f"Frozen C2T scenes: {len(scenes)}")
    print(f"Cached item JSON files: {len(list(CACHE.glob('*.json')))}\n")

    ir=[]; ar=[]
    for i,s in enumerate(scenes,1):
        x,source,attempts=fetch(s)
        p=x.get("properties",{}) or {}; assets=x.get("assets",{}) or {}; bbox=x.get("bbox")
        ir.append({
            "scene_id":s,"resolve_status":"OK","resolve_source":source,"remote_attempts":attempts,
            "platform":p.get("platform") or p.get("constellation") or s[:3],
            "datetime":p.get("datetime") or p.get("start_datetime"),
            "end_datetime":p.get("end_datetime"),"instrument_mode":p.get("sar:instrument_mode"),
            "polarizations":"|".join(map(str,p.get("sar:polarizations",[]) or [])),
            "orbit_state":p.get("sat:orbit_state"),"relative_orbit":p.get("sat:relative_orbit"),
            "absolute_orbit":p.get("sat:absolute_orbit"),"product_type":p.get("sar:product_type"),
            "processing_level":p.get("processing:level"),
            "bbox":json.dumps(bbox) if bbox is not None else None,
            "asset_count":len(assets),"stac_item_url":item_url(s)
        })
        for k,a in assets.items():
            href=a.get("href"); roles=a.get("roles",[]) or []
            ar.append({"scene_id":s,"asset_key":k,"title":a.get("title"),"media_type":a.get("type"),
                       "roles":"|".join(map(str,roles)),"href":href,"is_data_role":"data" in roles,
                       "looks_like_tiff":bool(href and str(href).lower().split("?")[0].endswith((".tif",".tiff")))})
        if i==1 or i%25==0 or i==len(scenes):
            print(f"[{i:04d}/{len(scenes):04d}] {s} source={source} assets={len(assets)}",flush=True)

    items=pd.DataFrame(ir); assets=pd.DataFrame(ar)
    items.to_csv(ITEM_OUT,index=False); assets.to_csv(ASSET_OUT,index=False)

    chk=d[["scene_id","acquisition_datetime","orbit_state","relative_orbit"]].merge(
        items[["scene_id","datetime","orbit_state","relative_orbit","instrument_mode","polarizations"]],
        on="scene_id",suffixes=("_c2t","_stac"),validate="one_to_one")
    chk["datetime_match"]=pd.to_datetime(chk.acquisition_datetime,utc=True,errors="coerce").eq(pd.to_datetime(chk.datetime,utc=True,errors="coerce"))
    chk["orbit_match"]=chk.orbit_state_c2t.astype(str).str.lower().eq(chk.orbit_state_stac.astype(str).str.lower())
    chk["rel_match"]=pd.to_numeric(chk.relative_orbit_c2t,errors="coerce").eq(pd.to_numeric(chk.relative_orbit_stac,errors="coerce"))
    metadata_mismatch=int((~(chk.datetime_match&chk.orbit_match&chk.rel_match)).sum())
    if metadata_mismatch: raise AssertionError(f"{metadata_mismatch} STAC/C2T metadata mismatches.")

    items["platform_norm"]=[platform_norm(s,p) for s,p in zip(items.scene_id,items.platform)]
    items["datetime"]=pd.to_datetime(items.datetime,utc=True,errors="coerce")
    items["end_datetime"]=pd.to_datetime(items.end_datetime,utc=True,errors="coerce")
    items["_bbox_key"]=items.bbox.map(bbox_key)
    non_iw=int((items.instrument_mode.astype(str).str.upper()!="IW").sum())
    poltxt=items.polarizations.astype(str).str.upper()
    non_dual=int((~(poltxt.str.contains(r"(^|\|)VV(\||$)",regex=True)&poltxt.str.contains(r"(^|\|)VH(\||$)",regex=True))).sum())
    # Outcome-blind technical measurement eligibility. C2T remains the immutable
    # temporal candidate universe; incompatible sensor modes/polarizations are
    # retained in the audit trail but excluded from the VV/VH measurement layer.
    items["measurement_eligible_iw_vvvh"] = (
        items.instrument_mode.astype(str).str.upper().eq("IW")
        & poltxt.str.contains(r"(?:^|\|)VV(?:\||$)", regex=True)
        & poltxt.str.contains(r"(?:^|\|)VH(?:\||$)", regex=True)
    )

    technical_exclusions = items.loc[~items["measurement_eligible_iw_vvvh"]].copy()
    technical_exclusions["technical_exclusion_reason"] = "non_VV_VH_polarization"
    non_iw_idx = technical_exclusions.instrument_mode.astype(str).str.upper().ne("IW")
    technical_exclusions.loc[non_iw_idx, "technical_exclusion_reason"] = "non_IW_mode_and_non_VV_VH_polarization"
    technical_exclusions.to_csv(OUT/"c2urr_technical_measurement_exclusions.csv", index=False)

    eligible_scene_ids = set(items.loc[items["measurement_eligible_iw_vvvh"], "scene_id"].astype(str))
    print(f"Outcome-blind measurement-eligible scenes (IW + VV/VH): {len(eligible_scene_ids)} / {len(items)}")
    print(f"Technical exclusions documented: {len(technical_exclusions)}")

    # Canonicalization/asset planning proceeds only on technically eligible scenes.
    items_all = items.copy()
    assets_all = assets.copy()
    items = items.loc[items["measurement_eligible_iw_vvvh"]].copy()
    assets = assets.loc[assets["scene_id"].astype(str).isin(eligible_scene_ids)].copy()

    assets["polarization_asset"]=assets.apply(pol_asset,axis=1)
    sa=assets.groupby("scene_id").agg(
        vv_assets_n=("polarization_asset",lambda x:int((x=="VV").sum())),
        vh_assets_n=("polarization_asset",lambda x:int((x=="VH").sum())),
        data_role_assets_n=("is_data_role","sum"),tiff_assets_n=("looks_like_tiff","sum"),
        asset_rows_n=("asset_key","count")).reset_index()
    ix=items.merge(sa,on="scene_id",how="left")
    for c in ["vv_assets_n","vh_assets_n","data_role_assets_n","tiff_assets_n","asset_rows_n"]: ix[c]=ix[c].fillna(0).astype(int)
    ix["has_both"]=(ix.vv_assets_n>0)&(ix.vh_assets_n>0)
    dupcols=["platform_norm","datetime","end_datetime","orbit_state","relative_orbit","_bbox_key"]
    ix["_dup_key"]=ix[dupcols].astype(str).agg("|".join,axis=1)

    cr=[]; dr=[]
    for key,g in ix.groupby("_dup_key",sort=True):
        z=g.sort_values(["has_both","data_role_assets_n","tiff_assets_n","asset_rows_n","scene_id"],
                        ascending=[False,False,False,False,True])
        chosen=str(z.iloc[0].scene_id)
        dr.append({"duplicate_group_key":key,"scene_ids_n":int(z.scene_id.nunique()),
                   "scene_ids":"|".join(sorted(z.scene_id.astype(str))),"is_duplicate_group":z.scene_id.nunique()>1,
                   "canonical_scene_id":chosen,"platform":z.iloc[0].platform_norm,"datetime":z.iloc[0].datetime,
                   "end_datetime":z.iloc[0].end_datetime,"orbit_state":z.iloc[0].orbit_state,
                   "relative_orbit":z.iloc[0].relative_orbit,"bbox":z.iloc[0].bbox})
        for rank,(_,r) in enumerate(z.iterrows(),1):
            cr.append({"duplicate_group_key":key,"scene_id":str(r.scene_id),"canonical_rank":rank,
                       "is_canonical_scene":rank==1,"canonical_scene_id":chosen,"duplicate_group_size":len(z),
                       "platform":r.platform_norm,"datetime":r.datetime,"end_datetime":r.end_datetime,
                       "orbit_state":r.orbit_state,"relative_orbit":r.relative_orbit,"bbox":r.bbox,
                       "vv_assets_n":r.vv_assets_n,"vh_assets_n":r.vh_assets_n,
                       "data_role_assets_n":r.data_role_assets_n,"tiff_assets_n":r.tiff_assets_n,
                       "asset_rows_n":r.asset_rows_n})
    dup=pd.DataFrame(dr); canon=pd.DataFrame(cr)
    dup.to_csv(DUP_OUT,index=False); canon.to_csv(CANON_OUT,index=False)
    cids=set(canon.loc[canon.is_canonical_scene,"canonical_scene_id"].astype(str))

    pa=assets[assets.scene_id.astype(str).isin(cids)&assets.polarization_asset.isin(["VV","VH"])].copy()
    pa=pa.sort_values(["scene_id","polarization_asset","is_data_role","looks_like_tiff","asset_key","href"],
                      ascending=[True,True,False,False,True,True])
    pa["asset_rank"]=pa.groupby(["scene_id","polarization_asset"]).cumcount()+1
    sel=pa[pa.asset_rank==1].copy()
    lookup={(str(r.scene_id),str(r.asset_key)):str(r.href) for r in assets_all.itertuples(index=False)}
    omap=dict(zip(canon.scene_id.astype(str),canon.canonical_scene_id.astype(str)))
    dm=d.loc[d.scene_id.astype(str).isin(eligible_scene_ids)].copy()
    dm["canonical_scene_id"]=dm.scene_id.map(omap)
    if dm.canonical_scene_id.isna().any(): raise AssertionError("Unmapped eligible C2T scene.")
    dm=dm.sort_values(["canonical_scene_id","scene_id"]).drop_duplicates(["canonical_scene_id"])

    rows=[]
    for r in dm.itertuples(index=False):
        sid=str(r.canonical_scene_id)
        rec={"year":int(r.year),"acquisition_date":str(r.acquisition_date),
             "acquisition_datetime":str(r.acquisition_datetime),"orbit_state":str(r.orbit_state),
             "relative_orbit":int(r.relative_orbit),"platform":str(getattr(r,"platform","")),
             "original_frozen_scene_id":str(r.scene_id),"canonical_scene_id":sid}
        sx=sel[sel.scene_id.astype(str).eq(sid)]
        for pol in ["VV","VH"]:
            q=sx[sx.polarization_asset.eq(pol)]
            rec[f"{pol.lower()}_asset_found"]=len(q)==1
            rec[f"{pol.lower()}_asset_key"]=q.iloc[0].asset_key if len(q) else None
            rec[f"{pol.lower()}_href"]=q.iloc[0].href if len(q) else None
            for schema in ["calibration","noise","product"]:
                k=f"schema-{schema}-{pol.lower()}"; h=lookup.get((sid,k))
                rec[f"{schema}_{pol.lower()}_asset_key"]=k
                rec[f"{schema}_{pol.lower()}_href"]=h
                rec[f"{schema}_{pol.lower()}_found"]=h is not None
        rows.append(rec)
    plan=pd.DataFrame(rows).sort_values(["year","orbit_state","relative_orbit","acquisition_datetime","canonical_scene_id"])
    plan.to_csv(PLAN_OUT,index=False)

    raster_missing=int((~plan.vv_asset_found).sum()+(~plan.vh_asset_found).sum())
    schema_missing=sum(int((~plan[f"{s}_{p}_found"]).sum()) for s in ["calibration","noise","product"] for p in ["vv","vh"])
    expected={(y,o,r) for y in range(2015,2026) for o,r in TRACKS}
    actual={(int(r.year),str(r.orbit_state),int(r.relative_orbit)) for r in plan[["year","orbit_state","relative_orbit"]].drop_duplicates().itertuples(index=False)}
    missing_yt=sorted(expected-actual)
    status="PASS" if not any([metadata_mismatch,raster_missing,schema_missing,len(missing_yt)]) else "FAIL"
    qa={"status":status,"stage":"DESIGN_C_C2URR_FULLSEASON_SENTINEL1_TECHNICAL_ELIGIBILITY_AND_ASSET_PLAN",
        "frozen_c2t_scene_ids_n":len(scenes),"resolved_scene_ids_n":len(items),
        "metadata_mismatch_n":metadata_mismatch,"non_iw_scene_ids_n":non_iw,
        "non_vvvh_scene_ids_n":non_dual,
        "technical_measurement_exclusions_n":int(len(technical_exclusions)),
        "measurement_eligible_iw_vvvh_scene_ids_n":int(len(eligible_scene_ids)),
        "technical_exclusions_are_outcome_blind":True,
        "c2t_candidate_universe_preserved":True,"duplicate_or_alternate_groups_n":int(dup.is_duplicate_group.sum()),
        "canonical_scene_ids_after_duplicate_collapse_n":int(plan.canonical_scene_id.nunique()),
        "selected_raster_assets_missing_n":raster_missing,"required_schema_assets_missing_n":schema_missing,
        "year_track_combinations_present_n":len(actual),"year_track_combinations_expected_n":len(expected),
        "missing_year_track_combinations":[{"year":y,"orbit_state":o,"relative_orbit":r} for y,o,r in missing_yt],
        "sar_raster_pixels_read":False,"vv_vh_statistics_calculated":False,
        "groundwater_values_read":False,"irrigation_flow_values_read":False,
        "ricefloodit_flood_outcomes_read":False,"sensor_response_values_used_for_selection":False,
        "inundation_threshold_selected":False,"classifier_fitted":False,"c2t_temporal_rule_modified":False}
    QA_OUT.write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")
    txt="\n".join([
        "DESIGN C - C2U FULL-SEASON SENTINEL-1 ASSET RESOLUTION","="*78,"",
        f"C2T frozen scene IDs: {len(scenes)}",f"Resolved STAC scene IDs: {len(items)}",
        f"Metadata mismatches against C2T: {metadata_mismatch}",
        f"Non-IW candidate scenes documented: {non_iw}",
        f"Candidate scenes without VV+VH documented: {non_dual}",
        f"Outcome-blind technical exclusions: {len(technical_exclusions)}",
        f"Measurement-eligible IW+VV/VH scenes: {len(eligible_scene_ids)} / {len(items_all)}",
        f"Duplicate/alternate item groups among eligible scenes: {int(dup.is_duplicate_group.sum())}",
        f"Canonical scenes after duplicate collapse: {plan.canonical_scene_id.nunique()}",
        f"Missing selected VV/VH raster assets: {raster_missing}",
        f"Missing required calibration/noise/product schema assets: {schema_missing}",
        f"Year-track combinations retained: {len(actual)}/{len(expected)}","",
        "SAR raster pixels read: False","Groundwater read: False","RiceFloodIT flooding outcome read: False",
        "Threshold/classifier: False","C2T temporal rule modified: False","",f"C2U-RR STATUS: {status}"])+"\n"
    TXT_OUT.write_text(txt,encoding="utf-8"); print("\n"+txt)
    print("CANONICAL PLAN BY YEAR/TRACK"); print("-"*28)
    print(plan.groupby(["year","orbit_state","relative_orbit"],as_index=False).agg(
        canonical_scenes_n=("canonical_scene_id","nunique"),acquisition_dates_n=("acquisition_date","nunique")).to_string(index=False))
    if status!="PASS": raise RuntimeError("C2U failed; inspect QA outputs.")

if __name__=="__main__": main()

"""Design C — C2J Freeze Primary Sentinel-1 Track/Date Universe
and Build Outcome-Blind SAR Validation Manifest.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)
C2IT = OUT / "c2it_track_date_rice_support_coverage.csv"
INV = ROOT / "data" / "design_c" / "raw" / "sentinel1" / "sentinel1_grd_scene_inventory_2014_latest2026.csv"
COMPLETE_YEARS = list(range(2015, 2026))
PRIMARY_TRACKS = {("ascending", 15), ("descending", 66)}
PRIMARY_MIN_RICE_SUPPORT = 0.99
ANCHOR_YEARS = [2015, 2020, 2025]
SEASON_ANCHORS = [("establishment",5,15),("mid_season",7,15),("late_season",9,1)]

def main():
    print("DESIGN C - C2J FREEZE PRIMARY SENTINEL-1 UNIVERSE")
    print("="*64)
    print("NO SAR pixel values inspected.")
    print("NO flooding/exposure values read.")
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO threshold tuned.")
    print("NO association model fitted.")
    print("NO frozen publication artifact modified.\n")

    if not C2IT.exists():
        raise FileNotFoundError(f"Missing {C2IT}. Run C2I-T first.")
    if not INV.exists():
        raise FileNotFoundError(f"Missing {INV}. Run C2I-R first.")

    cov = pd.read_csv(C2IT)
    inv = pd.read_csv(INV)
    cov["date"] = pd.to_datetime(cov["date"], errors="coerce")
    cov["year"] = cov["date"].dt.year
    cov["relative_orbit"] = pd.to_numeric(cov["relative_orbit"], errors="coerce").astype("Int64")
    cov["is_primary_track"] = [((str(a), int(o)) in PRIMARY_TRACKS) if pd.notna(o) else False for a,o in zip(cov["orbit_state"], cov["relative_orbit"])]

    primary = cov.loc[
        cov["year"].isin(COMPLETE_YEARS)
        & cov["is_primary_track"]
        & (cov["rice_support_coverage_fraction"] >= PRIMARY_MIN_RICE_SUPPORT)
    ].copy()
    primary["eligibility_rule"] = "primary track + complete year + Apr-Sep IW VV|VH + actual rice-support coverage >=0.99"
    primary = primary.sort_values(["orbit_state","relative_orbit","date"])
    primary.to_csv(OUT / "c2j_primary_sentinel_track_date_universe.csv", index=False)

    nonprimary = pd.DataFrame([
        {"orbit_state":"ascending","relative_orbit":88,"primary_status":"EXCLUDED_FROM_PRIMARY","future_status":"DIAGNOSTIC_SPATIAL_ROBUSTNESS_ONLY","reason":"Systematically incomplete actual RiceFloodIT-support coverage; includes severe low/zero-coverage dates."},
        {"orbit_state":"descending","relative_orbit":168,"primary_status":"EXCLUDED_FROM_PRIMARY","future_status":"DIAGNOSTIC_SPATIAL_ROBUSTNESS_ONLY","reason":"Persistent partial spatial support; approximately three-quarters of actual RiceFloodIT coordinates on typical dates."},
        {"orbit_state":"descending","relative_orbit":139,"primary_status":"EXCLUDED_FROM_PRIMARY","future_status":"TEMPORAL_DIAGNOSTIC_ONLY","reason":"Not temporally continuous across all complete candidate years 2015-2025."},
    ])
    nonprimary.to_csv(OUT / "c2j_nonprimary_sentinel_track_status.csv", index=False)

    rows=[]
    for year in ANCHOR_YEARS:
        for state,orbit in sorted(PRIMARY_TRACKS):
            x=primary.loc[primary["year"].eq(year) & primary["orbit_state"].eq(state) & primary["relative_orbit"].eq(orbit)].copy()
            for phase,month,day in SEASON_ANCHORS:
                anchor=pd.Timestamp(year=year,month=month,day=day)
                if x.empty:
                    rows.append({"anchor_year":year,"season_phase":phase,"anchor_date":anchor.date().isoformat(),"orbit_state":state,"relative_orbit":orbit,"selected_date":None,"distance_from_anchor_days":None,"rice_support_coverage_fraction":None,"scenes_on_date_n":None,"selection_status":"NO_ELIGIBLE_DATE"})
                    continue
                y=x.copy(); y["_delta"]=(y["date"]-anchor).abs().dt.days
                y=y.sort_values(["_delta","rice_support_coverage_fraction","date"], ascending=[True,False,True])
                r=y.iloc[0]
                rows.append({"anchor_year":year,"season_phase":phase,"anchor_date":anchor.date().isoformat(),"orbit_state":state,"relative_orbit":orbit,"selected_date":r["date"].date().isoformat(),"distance_from_anchor_days":int(r["_delta"]),"rice_support_coverage_fraction":float(r["rice_support_coverage_fraction"]),"scenes_on_date_n":int(r["scenes_on_date_n"]),"selection_status":"SELECTED"})
    manifest=pd.DataFrame(rows)

    inv["datetime"]=pd.to_datetime(inv["datetime"],errors="coerce",utc=True)
    inv["date_key"]=inv["datetime"].dt.date.astype(str)
    inv["relative_orbit"]=pd.to_numeric(inv["relative_orbit"],errors="coerce").astype("Int64")
    ids=[]
    for _,r in manifest.iterrows():
        if r["selection_status"]!="SELECTED": ids.append(""); continue
        z=inv.loc[
            inv["date_key"].eq(str(r["selected_date"]))
            & inv["orbit_state"].eq(r["orbit_state"])
            & inv["relative_orbit"].eq(r["relative_orbit"])
            & inv["instrument_mode"].eq("IW")
            & inv["polarizations"].eq("VV|VH")
        ]
        ids.append("|".join(sorted(z["scene_id"].astype(str).unique())))
    manifest["scene_ids"]=ids
    manifest.to_csv(OUT / "c2j_sar_validation_manifest.csv", index=False)

    by_track_year = primary.groupby(["orbit_state","relative_orbit","year"]).agg(
        eligible_dates_n=("date","nunique"),
        min_support_fraction=("rice_support_coverage_fraction","min"),
        median_support_fraction=("rice_support_coverage_fraction","median"),
    ).reset_index()

    qa={
        "status":"PASS",
        "stage":"DESIGN_C_C2J_PRIMARY_SENTINEL_UNIVERSE_FREEZE",
        "freeze_basis":"metadata only; before SAR signal inspection",
        "complete_candidate_years":COMPLETE_YEARS,
        "primary_tracks":[{"orbit_state":a,"relative_orbit":o} for a,o in sorted(PRIMARY_TRACKS)],
        "primary_min_actual_rice_support_fraction":PRIMARY_MIN_RICE_SUPPORT,
        "same_track_same_date_rule":"Adjacent scenes are one date-level mosaic.",
        "anchor_years_for_validation":ANCHOR_YEARS,
        "seasonal_validation_anchors":[{"phase":p,"month":m,"day":d} for p,m,d in SEASON_ANCHORS],
        "eligible_primary_track_dates_n":int(len(primary)),
        "validation_targets_n":int((manifest["selection_status"]=="SELECTED").sum()),
        "sar_pixels_inspected":0,
        "flooding_exposure_values_read":0,
        "groundwater_level_values_read":0,
        "irrigation_flow_values_read":0,
        "thresholds_tuned":0,
        "association_models_fitted":0,
        "frozen_publication_artifacts_modified":0,
        "future_rule":"Do not alter primary track/date eligibility after inspecting SAR signal or groundwater outcomes. Any later change must be explicitly labeled post-freeze diagnostic.",
        "next_stage":"Resolve STAC assets for the fixed validation manifest and perform SAR measurement validation independently of groundwater."
    }
    (OUT/"c2j_sentinel_measurement_freeze.json").write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")

    lines=[
        "DESIGN C - C2J PRIMARY SENTINEL-1 UNIVERSE FREEZE","="*62,"",
        "PRIMARY TRACKS","--------------","ascending relative orbit 15","descending relative orbit 66","",
        "PRIMARY DATE RULE","-----------------","2015-2025 complete candidate years","April-September","IW, VV|VH","actual RiceFloodIT support coverage >= 0.99","same-track same-date scenes = one mosaic","",
        "ELIGIBLE PRIMARY DATE SUPPORT","-----------------------------",by_track_year.to_string(index=False),"",
        "OUTCOME-BLIND SAR VALIDATION MANIFEST","-------------------------------------",manifest.to_string(index=False),"",
        "NON-PRIMARY TRACK STATUS","------------------------",nonprimary.to_string(index=False),"",
        "FIREWALL","--------","No SAR pixel values inspected.","No flooding/exposure values read.","No groundwater-level values read.","No irrigation-flow values read.","No thresholds tuned.","No association model fitted.","",
        "DECISION","--------","Primary Sentinel track/date universe is now frozen before measurement validation.","Any later departure from this rule must be labeled post-freeze diagnostic.","","C2J FREEZE STATUS: PASS"
    ]
    summary="\n".join(lines)+"\n"
    (OUT/"c2j_sentinel_measurement_freeze_summary.txt").write_text(summary,encoding="utf-8")
    print(summary)

if __name__=="__main__":
    main()

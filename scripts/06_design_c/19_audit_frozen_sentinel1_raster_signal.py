"""Design C — C2M Frozen Sentinel-1 Raster Signal QA (GCP revision).

Corrected C2M implementation using embedded Sentinel-1 GCP geolocation.
No flooding threshold or dB conversion is selected here.
"""

from __future__ import annotations

import json, os, time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import GCPTransformer
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

PLAN = OUT / "c2l_target_mosaic_asset_plan.csv"
RICE_GEO = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"

RASTER_ENV = {
    "AWS_S3_ENDPOINT": "eodata.dataspace.copernicus.eu",
    "AWS_VIRTUAL_HOSTING": "FALSE",
    "AWS_DEFAULT_REGION": "default",
}

MAX_OPEN_ATTEMPTS = 4
OPEN_DELAY_SECONDS = 2.0


def require_credentials():
    missing = [k for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"] if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing CDSE S3 environment credential(s): " + ", ".join(missing))


def retry_open(href):
    last = None
    for attempt in range(1, MAX_OPEN_ATTEMPTS + 1):
        try:
            return rasterio.open(href), attempt, None
        except Exception as e:
            last = repr(e)
            if attempt < MAX_OPEN_ATTEMPTS:
                time.sleep(OPEN_DELAY_SECONDS * attempt)
    return None, MAX_OPEN_ATTEMPTS, last


def finite_stats(values):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return dict(n=0, min=None, p01=None, p10=None, median=None, mean=None,
                    p90=None, p99=None, max=None, sd=None, zero_share=None)
    return {
        "n": int(len(x)),
        "min": float(np.min(x)),
        "p01": float(np.quantile(x, .01)),
        "p10": float(np.quantile(x, .10)),
        "median": float(np.median(x)),
        "mean": float(np.mean(x)),
        "p90": float(np.quantile(x, .90)),
        "p99": float(np.quantile(x, .99)),
        "max": float(np.max(x)),
        "sd": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
        "zero_share": float(np.mean(x == 0)),
    }


def choose_point_id_column(g):
    candidates = ["id","cell_id","pixel_id","grid_id","point_id","ricefloodit_id","fid","index"]
    cmap = {str(c).strip().lower(): c for c in g.columns}
    for c in candidates:
        if c in cmap:
            return cmap[c]
    return None


def transform_points_to_pixels(ds, lon, lat):
    gcps, gcp_crs = ds.gcps
    if not gcps:
        raise RuntimeError("Raster contains no embedded GCPs.")
    if gcp_crs is None:
        raise RuntimeError("Raster GCP CRS is missing.")

    tr = Transformer.from_crs("EPSG:4326", gcp_crs, always_xy=True)
    x, y = tr.transform(np.asarray(lon, float), np.asarray(lat, float))

    with GCPTransformer(gcps) as gt:
        rows, cols = gt.rowcol(x, y)

    rows = np.asarray(rows, dtype=np.int64)
    cols = np.asarray(cols, dtype=np.int64)
    inside = (rows >= 0) & (rows < ds.height) & (cols >= 0) & (cols < ds.width)
    return rows, cols, inside, gcps, gcp_crs


def sample_required_blocks(ds, rows, cols, inside):
    out = np.full(len(rows), np.nan, dtype=float)
    if ds.block_shapes:
        block_h, block_w = map(int, ds.block_shapes[0])
    else:
        block_h, block_w = 512, 512

    groups = {}
    for i in np.flatnonzero(inside):
        key = (int(rows[i] // block_h), int(cols[i] // block_w))
        groups.setdefault(key, []).append(int(i))

    for (br, bc), idxs in groups.items():
        row_off = br * block_h
        col_off = bc * block_w
        h = min(block_h, ds.height - row_off)
        w = min(block_w, ds.width - col_off)
        arr = ds.read(1, window=Window(col_off, row_off, w, h), masked=False)

        for i in idxs:
            v = float(arr[int(rows[i]-row_off), int(cols[i]-col_off)])
            if ds.nodata is not None and np.isclose(v, ds.nodata):
                continue
            out[i] = v

    return out, len(groups)


def sample_one_asset(href, lon, lat):
    ds, attempts, err = retry_open(href)
    if ds is None:
        return None, {"open_status":"ERROR","open_attempts":attempts,"open_error":err}

    with ds:
        try:
            rows, cols, inside, gcps, gcp_crs = transform_points_to_pixels(ds, lon, lat)
            values, blocks_n = sample_required_blocks(ds, rows, cols, inside)
            finite_n = int(np.isfinite(values).sum())
            inside_n = int(inside.sum())
            meta = {
                "open_status":"OK",
                "open_attempts":attempts,
                "open_error":None,
                "driver":ds.driver,
                "affine_crs":str(ds.crs) if ds.crs else None,
                "gcp_crs":str(gcp_crs),
                "gcp_count":len(gcps),
                "width":ds.width,
                "height":ds.height,
                "dtype":str(ds.dtypes[0]),
                "nodata":float(ds.nodata) if ds.nodata is not None else None,
                "scale":float(ds.scales[0]) if ds.scales else None,
                "offset":float(ds.offsets[0]) if ds.offsets else None,
                "units":str(ds.units[0]) if ds.units and ds.units[0] is not None else None,
                "block_shape":"x".join(map(str, ds.block_shapes[0])) if ds.block_shapes else None,
                "unique_blocks_read_n":blocks_n,
                "points_mapped_inside_raster_n":inside_n,
                "points_with_finite_raw_value_n":finite_n,
                "inside_points_finite_share":float(finite_n/inside_n) if inside_n else None,
            }
            return values, meta
        except Exception as e:
            return None, {"open_status":"ERROR","open_attempts":attempts,"open_error":repr(e)}


def main():
    print("DESIGN C - C2M FROZEN SENTINEL-1 RASTER SIGNAL QA (GCP REVISION)")
    print("="*74)
    print("THIS STAGE READS frozen SAR raster pixels.")
    print("Embedded GCPs are used for geolocation.")
    print("Only required raster blocks are read.")
    print("NO flooding threshold is selected.")
    print("NO existing flooding/exposure outcomes are read.")
    print("NO groundwater-level values are read.")
    print("NO irrigation-flow values are read.")
    print("NO association model is fitted.")
    print("C2J frozen acquisition universe is unchanged.\n")

    require_credentials()
    plan = pd.read_csv(PLAN)
    geo = pd.read_csv(RICE_GEO)
    geo["lon"] = pd.to_numeric(geo["lon"], errors="coerce")
    geo["lat"] = pd.to_numeric(geo["lat"], errors="coerce")
    geo = geo.dropna(subset=["lon","lat"]).copy()

    pid = choose_point_id_column(geo)
    geo["_point_id"] = geo[pid].astype(str) if pid else [f"ricept_{i}" for i in range(len(geo))]
    points = geo.drop_duplicates(["lon","lat"]).reset_index(drop=True).copy()
    lon = points["lon"].to_numpy(float)
    lat = points["lat"].to_numpy(float)

    print(f"Canonical target-scene rows: {len(plan)}")
    print(f"Unique RiceFloodIT support coordinates: {len(points)}")
    print("Credentials detected: YES (values not printed)\n")

    expected = []
    for _, r in plan.iterrows():
        for pol in ["VV","VH"]:
            expected.append((str(r.canonical_scene_id), pol, str(r[f"{pol.lower()}_href"])))
    expected = list(dict.fromkeys(expected))

    cache = {}
    asset_rows = []

    with rasterio.Env(**RASTER_ENV):
        for j,(scene,pol,href) in enumerate(expected,1):
            r = plan[plan.canonical_scene_id.astype(str).eq(scene)].iloc[0]
            print(f"[{j:02d}/{len(expected):02d}] {scene} {pol}")
            values, meta = sample_one_asset(href, lon, lat)
            row = {
                "canonical_scene_id":scene,
                "platform":r.platform,
                "polarization":pol,
                "asset_key":r[f"{pol.lower()}_asset_key"],
                "href":href,
                **meta,
            }
            if values is not None:
                row.update({f"raw_{k}":v for k,v in finite_stats(values).items()})
            asset_rows.append(row)
            cache[(scene,pol,href)] = values

    asset_qa = pd.DataFrame(asset_rows)
    asset_qa.to_csv(OUT/"c2m_raster_asset_technical_qa.csv", index=False)

    point_rows = []
    for _, r in plan.iterrows():
        for pol in ["VV","VH"]:
            href = str(r[f"{pol.lower()}_href"])
            scene = str(r.canonical_scene_id)
            vals = cache.get((scene,pol,href))
            if vals is None:
                continue
            for i in np.flatnonzero(np.isfinite(vals)):
                point_rows.append({
                    "anchor_year":int(r.anchor_year),
                    "season_phase":r.season_phase,
                    "selected_date":r.selected_date,
                    "orbit_state":r.orbit_state,
                    "relative_orbit":int(r.relative_orbit),
                    "platform":r.platform,
                    "canonical_scene_id":scene,
                    "polarization":pol,
                    "point_id":points.iloc[i]["_point_id"],
                    "lon":float(lon[i]),
                    "lat":float(lat[i]),
                    "raw_value":float(vals[i]),
                })

    samples = pd.DataFrame(point_rows)
    samples.to_csv(OUT/"c2m_target_point_signal_samples.csv", index=False)
    if samples.empty:
        raise AssertionError("No finite Sentinel-1 point samples were obtained after GCP geolocation.")

    point_keys = ["anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
                  "platform","polarization","point_id","lon","lat"]

    point_target = samples.groupby(point_keys,as_index=False).agg(
        raw_value=("raw_value","median"),
        contributing_scenes_n=("canonical_scene_id","nunique"),
    )

    group_cols = ["anchor_year","season_phase","selected_date","orbit_state",
                  "relative_orbit","platform","polarization"]

    summaries=[]
    for key,g in point_target.groupby(group_cols):
        rec=dict(zip(group_cols,key))
        n=int(g.point_id.nunique())
        rec.update({
            "rice_support_points_sampled_n":n,
            "rice_support_point_coverage_fraction":float(n/len(points)),
            "points_with_multi_scene_overlap_n":int((g.contributing_scenes_n>1).sum()),
        })
        rec.update({f"raw_{k}":v for k,v in finite_stats(g.raw_value).items()})
        summaries.append(rec)

    summary_df=pd.DataFrame(summaries)
    summary_df.to_csv(OUT/"c2m_target_polarization_signal_summary.csv", index=False)

    targets_n = plan[["anchor_year","season_phase","selected_date","orbit_state","relative_orbit"]].drop_duplicates().shape[0]
    expected_target_pol_n = targets_n*2
    failed_n = int((~asset_qa.open_status.eq("OK")).sum())
    status = "PASS" if failed_n==0 and len(summary_df)==expected_target_pol_n else "PASS_WITH_LIMITATIONS"

    qa = {
        "status":status,
        "stage":"DESIGN_C_C2M_FROZEN_SENTINEL_RASTER_SIGNAL_QA_GCP_REVISION",
        "supersedes_initial_failed_c2m_attempt":True,
        "frozen_targets_n":int(targets_n),
        "expected_target_polarization_combinations_n":int(expected_target_pol_n),
        "canonical_scene_polarization_assets_expected_n":int(len(expected)),
        "canonical_scene_polarization_assets_opened_n":int(asset_qa.open_status.eq("OK").sum()),
        "failed_asset_opens_n":failed_n,
        "target_polarization_summaries_n":int(len(summary_df)),
        "unique_rice_support_coordinates_n":int(len(points)),
        "minimum_target_pol_point_coverage_fraction":float(summary_df.rice_support_point_coverage_fraction.min()),
        "median_target_pol_point_coverage_fraction":float(summary_df.rice_support_point_coverage_fraction.median()),
        "sar_raster_pixels_read":True,
        "existing_flooding_exposure_values_read":False,
        "groundwater_level_values_read":False,
        "irrigation_flow_values_read":False,
        "thresholds_tuned":False,
        "association_models_fitted":0,
        "c2j_frozen_rule_modified":False,
        "raw_signal_interpretation":"Raw uint16 values are not yet interpreted as dB/calibrated backscatter.",
    }
    (OUT/"c2m_raster_signal_qa.json").write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")

    txt = "\n".join([
        "DESIGN C - C2M FROZEN SENTINEL-1 RASTER SIGNAL QA (GCP REVISION)",
        "="*72,
        "",
        f"Frozen targets: {targets_n}",
        f"Expected target-polarization combinations: {expected_target_pol_n}",
        f"Canonical scene/polarization assets expected: {len(expected)}",
        f"Canonical scene/polarization assets opened: {asset_qa.open_status.eq('OK').sum()}",
        f"Failed asset opens: {failed_n}",
        f"Target-polarization summaries produced: {len(summary_df)}",
        f"Unique rice-support coordinates: {len(points)}",
        f"Minimum target/pol point coverage: {summary_df.rice_support_point_coverage_fraction.min():.6f}",
        f"Median target/pol point coverage: {summary_df.rice_support_point_coverage_fraction.median():.6f}",
        "",
        "TARGET / POLARIZATION RAW-SIGNAL SUMMARY",
        "----------------------------------------",
        summary_df.to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "SAR raster pixels WERE read for technical measurement QA.",
        "Embedded GCPs were used for geolocation.",
        "No existing flooding/exposure values were read.",
        "No groundwater-level values were read.",
        "No irrigation-flow values were read.",
        "No threshold was tuned or selected.",
        "No association model was fitted.",
        "C2J frozen acquisition universe unchanged.",
        "",
        "RAW-SIGNAL CAUTION",
        "------------------",
        "Raw uint16 values are not yet interpreted as dB/calibrated backscatter.",
        "",
        f"C2M STATUS: {status}",
    ]) + "\n"

    (OUT/"c2m_raster_signal_qa_summary.txt").write_text(txt,encoding="utf-8")
    print("\n"+txt)


if __name__=="__main__":
    main()

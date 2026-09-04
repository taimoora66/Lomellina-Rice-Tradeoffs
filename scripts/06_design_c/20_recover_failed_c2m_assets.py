"""Design C — C2M-R targeted recovery of failed Sentinel-1 raster assets.

Retries ONLY assets that failed in the original C2M GCP-revision run.
Original C2M outputs are never overwritten.
"""

from __future__ import annotations

import json
import os
import time
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

ASSET_QA = OUT / "c2m_raster_asset_technical_qa.csv"
ORIGINAL_SAMPLES = OUT / "c2m_target_point_signal_samples.csv"
PLAN = OUT / "c2l_target_mosaic_asset_plan.csv"
RICE_GEO = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"

REC_ASSET_QA = OUT / "c2mr_recovered_asset_technical_qa.csv"
REC_SAMPLES = OUT / "c2mr_recovered_point_signal_samples.csv"
AUG_SUMMARY = OUT / "c2mr_augmented_target_polarization_signal_summary.csv"
QA_JSON = OUT / "c2mr_recovery_qa.json"
SUMMARY_TXT = OUT / "c2mr_recovery_summary.txt"

MAX_FULL_ATTEMPTS = 6
RETRY_BASE_SECONDS = 8

os.environ.setdefault("AWS_S3_ENDPOINT", "eodata.dataspace.copernicus.eu")
os.environ.setdefault("AWS_VIRTUAL_HOSTING", "FALSE")
os.environ.setdefault("AWS_HTTPS", "YES")


def finite_stats(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return {
            "raw_n": 0, "raw_min": np.nan, "raw_p01": np.nan, "raw_p10": np.nan,
            "raw_median": np.nan, "raw_mean": np.nan, "raw_p90": np.nan,
            "raw_p99": np.nan, "raw_max": np.nan, "raw_sd": np.nan,
            "raw_zero_share": np.nan,
        }
    return {
        "raw_n": int(len(a)),
        "raw_min": float(np.min(a)),
        "raw_p01": float(np.quantile(a, 0.01)),
        "raw_p10": float(np.quantile(a, 0.10)),
        "raw_median": float(np.median(a)),
        "raw_mean": float(np.mean(a)),
        "raw_p90": float(np.quantile(a, 0.90)),
        "raw_p99": float(np.quantile(a, 0.99)),
        "raw_max": float(np.max(a)),
        "raw_sd": float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
        "raw_zero_share": float(np.mean(a == 0)),
    }


def choose_point_id_column(g):
    cmap = {str(c).strip().lower(): c for c in g.columns}
    for c in ["point_id", "id", "cell_id", "pixel_id", "grid_id", "ricefloodit_id", "fid", "index"]:
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


def process_whole_asset_with_retry(href, lon, lat):
    last_error = None
    for attempt in range(1, MAX_FULL_ATTEMPTS + 1):
        try:
            with rasterio.open(href) as ds:
                rows, cols, inside, gcps, gcp_crs = transform_points_to_pixels(ds, lon, lat)
                values, blocks_n = sample_required_blocks(ds, rows, cols, inside)
                meta = {
                    "recovery_status": "RECOVERED",
                    "full_operation_attempts": attempt,
                    "recovery_error": None,
                    "driver": ds.driver,
                    "affine_crs": str(ds.crs) if ds.crs else None,
                    "gcp_crs": str(gcp_crs),
                    "gcp_count": len(gcps),
                    "width": ds.width,
                    "height": ds.height,
                    "dtype": str(ds.dtypes[0]),
                    "nodata": float(ds.nodata) if ds.nodata is not None else None,
                    "block_shape": "x".join(map(str, ds.block_shapes[0])) if ds.block_shapes else None,
                    "unique_blocks_read_n": int(blocks_n),
                    "points_mapped_inside_raster_n": int(inside.sum()),
                    "points_with_finite_raw_value_n": int(np.isfinite(values).sum()),
                    "inside_points_finite_share": float(np.isfinite(values[inside]).mean()) if inside.any() else np.nan,
                }
                meta.update(finite_stats(values))
                return values, inside, meta
        except Exception as e:
            last_error = repr(e)
            if attempt < MAX_FULL_ATTEMPTS:
                delay = RETRY_BASE_SECONDS * attempt
                print(f"    attempt {attempt} failed: {last_error}", flush=True)
                print(f"    retrying whole asset operation in {delay}s...", flush=True)
                time.sleep(delay)
    return None, None, {
        "recovery_status": "FAILED",
        "full_operation_attempts": MAX_FULL_ATTEMPTS,
        "recovery_error": last_error,
    }


def find_col(df, candidates, label):
    for c in candidates:
        if c in df.columns:
            return c
    raise AssertionError(f"Could not locate {label} column. Columns: {list(df.columns)}")


def main():
    print("DESIGN C - C2M-R TARGETED FAILED-ASSET RECOVERY")
    print("=" * 64)
    print("Retries ONLY failed original C2M assets.")
    print("Retries the WHOLE open -> GCP -> block-read operation.")
    print("Original C2M outputs are NOT overwritten.")
    print("NO flooding/exposure values read.")
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO threshold tuned.")
    print("NO association model fitted.")
    print("Raw uint16 remains UNCALIBRATED.\n")

    for p in [ASSET_QA, ORIGINAL_SAMPLES, PLAN, RICE_GEO]:
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    qa0 = pd.read_csv(ASSET_QA)
    failed = qa0.loc[qa0["open_status"].eq("ERROR")].copy()
    if failed.empty:
        print("No failed original C2M assets found. Nothing to recover.")
        return

    geo = pd.read_csv(RICE_GEO)
    geo["lon"] = pd.to_numeric(geo["lon"], errors="coerce")
    geo["lat"] = pd.to_numeric(geo["lat"], errors="coerce")
    geo = geo.dropna(subset=["lon", "lat"]).copy()
    pid_col = choose_point_id_column(geo)
    geo["_point_id"] = geo[pid_col].astype(str) if pid_col else [f"ricept_{i}" for i in range(len(geo))]
    points = geo.drop_duplicates(["lon", "lat"]).reset_index(drop=True).copy()
    lon = points["lon"].to_numpy(float)
    lat = points["lat"].to_numpy(float)

    plan = pd.read_csv(PLAN)
    scene_col = find_col(plan, ["canonical_scene_id", "scene_id", "canonical_id"], "scene id")
    context_cols = ["anchor_year", "season_phase", "selected_date", "orbit_state", "relative_orbit", "platform"]
    missing = [c for c in context_cols if c not in plan.columns]
    if missing:
        raise AssertionError(f"C2L plan lacks required columns: {missing}")

    print(f"Original failed assets found: {len(failed)}")
    print(f"Unique RiceFloodIT support coordinates: {len(points)}\n")

    rec_qa_rows = []
    rec_sample_rows = []

    for seq, (_, f) in enumerate(failed.iterrows(), start=1):
        scene_id = str(f["canonical_scene_id"])
        pol = str(f["polarization"])
        href = str(f["href"])
        print(f"[{seq:02d}/{len(failed):02d}] {scene_id} {pol}", flush=True)

        values, inside, meta = process_whole_asset_with_retry(href, lon, lat)
        row = {
            "canonical_scene_id": scene_id,
            "platform": f.get("platform"),
            "polarization": pol,
            "asset_key": f.get("asset_key"),
            "href": href,
            "original_open_attempts": f.get("open_attempts"),
            "original_open_error": f.get("open_error"),
        }
        row.update(meta)
        rec_qa_rows.append(row)

        if meta["recovery_status"] != "RECOVERED":
            print("    FINAL STATUS: FAILED\n", flush=True)
            continue

        finite = np.isfinite(values)
        print(
            f"    FINAL STATUS: RECOVERED | inside={int(inside.sum())}/{len(points)} "
            f"| finite={int(finite.sum())}/{len(points)} "
            f"| blocks={meta['unique_blocks_read_n']}\n",
            flush=True,
        )

        # C2L plan is one row per canonical scene and stores VV/VH in
        # separate asset columns (vv_href, vh_href), so target context is
        # linked by canonical_scene_id only. Polarization comes from the
        # failed C2M asset row being recovered.
        links = plan.loc[
            plan[scene_col].astype(str).eq(scene_id)
        ].copy()
        if links.empty:
            raise AssertionError(f"Scene absent from C2L plan: {scene_id}")

        for _, link in links.iterrows():
            for i in np.flatnonzero(finite):
                rec_sample_rows.append({
                    "anchor_year": link["anchor_year"],
                    "season_phase": link["season_phase"],
                    "selected_date": link["selected_date"],
                    "orbit_state": link["orbit_state"],
                    "relative_orbit": link["relative_orbit"],
                    "platform": link["platform"],
                    "polarization": pol,
                    "point_id": points.iloc[i]["_point_id"],
                    "lon": float(lon[i]),
                    "lat": float(lat[i]),
                    "canonical_scene_id": scene_id,
                    "raw_value": float(values[i]),
                })

    rec_qa = pd.DataFrame(rec_qa_rows)
    rec_qa.to_csv(REC_ASSET_QA, index=False)
    rec_samples = pd.DataFrame(rec_sample_rows)
    rec_samples.to_csv(REC_SAMPLES, index=False)

    original = pd.read_csv(ORIGINAL_SAMPLES)
    required = {
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","point_id","lon","lat","canonical_scene_id","raw_value"
    }
    missing = required - set(original.columns)
    if missing:
        raise AssertionError(f"Original C2M sample schema missing columns: {sorted(missing)}")

    if len(rec_samples):
        aligned = rec_samples.reindex(columns=original.columns)
        aug = pd.concat([original, aligned], ignore_index=True, sort=False)
    else:
        aug = original.copy()

    dedup_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","point_id","canonical_scene_id"
    ]
    aug = aug.drop_duplicates(dedup_keys, keep="last")

    point_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","point_id","lon","lat"
    ]
    point_target = aug.groupby(point_keys, as_index=False).agg(
        raw_value=("raw_value","median"),
        contributing_scenes_n=("canonical_scene_id","nunique"),
    )

    target_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization"
    ]
    rows = []
    for key, g in point_target.groupby(target_keys, dropna=False):
        r = dict(zip(target_keys, key))
        r.update({
            "rice_support_points_sampled_n": int(g["point_id"].nunique()),
            "rice_support_point_coverage_fraction": float(g["point_id"].nunique()/len(points)),
            "points_with_multi_scene_overlap_n": int((g["contributing_scenes_n"] > 1).sum()),
        })
        r.update(finite_stats(g["raw_value"].to_numpy(float)))
        rows.append(r)

    summary = pd.DataFrame(rows).sort_values(target_keys)
    summary.to_csv(AUG_SUMMARY, index=False)

    recovered_n = int(rec_qa["recovery_status"].eq("RECOVERED").sum())
    still_failed_n = int(rec_qa["recovery_status"].eq("FAILED").sum())
    min_cov = float(summary["rice_support_point_coverage_fraction"].min())
    med_cov = float(summary["rice_support_point_coverage_fraction"].median())
    status = (
        "RECOVERY_PASS"
        if still_failed_n == 0 and min_cov >= 0.99
        else "RECOVERY_PARTIAL"
        if recovered_n > 0
        else "RECOVERY_FAILED"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2MR_TARGETED_FAILED_ASSET_RECOVERY",
        "original_c2m_status_preserved": "PASS_WITH_LIMITATIONS",
        "original_failed_assets_n": int(len(failed)),
        "assets_recovered_n": recovered_n,
        "assets_still_failed_n": still_failed_n,
        "augmented_target_polarization_summaries_n": int(len(summary)),
        "unique_rice_support_coordinates_n": int(len(points)),
        "augmented_minimum_target_pol_point_coverage_fraction": min_cov,
        "augmented_median_target_pol_point_coverage_fraction": med_cov,
        "original_outputs_overwritten": False,
        "retry_scope": "whole_open_gcp_block_read_operation",
        "max_full_operation_attempts": MAX_FULL_ATTEMPTS,
        "sar_raster_pixels_read": True,
        "existing_flooding_exposure_values_read": False,
        "groundwater_level_values_read": False,
        "irrigation_flow_values_read": False,
        "thresholds_tuned": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "raw_signal_interpretation": "Raw uint16 values remain uncalibrated and are not interpreted as dB.",
    }
    QA_JSON.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    cols = [
        "canonical_scene_id","polarization","recovery_status",
        "full_operation_attempts","points_mapped_inside_raster_n",
        "points_with_finite_raw_value_n","recovery_error"
    ]
    lines = [
        "DESIGN C - C2M-R TARGETED FAILED-ASSET RECOVERY",
        "=" * 64,
        "",
        f"Original failed assets: {len(failed)}",
        f"Recovered assets: {recovered_n}",
        f"Still failed assets: {still_failed_n}",
        f"Augmented target/polarization summaries: {len(summary)}",
        f"Minimum augmented target/pol coverage: {min_cov:.6f}",
        f"Median augmented target/pol coverage: {med_cov:.6f}",
        "",
        "RECOVERY ASSET QA",
        "-----------------",
        rec_qa[cols].to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "Original C2M PASS_WITH_LIMITATIONS record preserved.",
        "No existing flooding/exposure values were read.",
        "No groundwater-level values were read.",
        "No irrigation-flow values were read.",
        "No threshold was tuned or selected.",
        "No association model was fitted.",
        "C2J frozen acquisition universe unchanged.",
        "Raw uint16 signal remains uncalibrated.",
        "",
        f"C2M-R STATUS: {status}",
    ]
    txt = "\n".join(lines) + "\n"
    SUMMARY_TXT.write_text(txt, encoding="utf-8")
    print("\n" + txt)


if __name__ == "__main__":
    main()

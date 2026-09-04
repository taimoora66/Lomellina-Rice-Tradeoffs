"""Design C — C2N-R post-C2M-R radiometric calibration rebuild.

Purpose
-------
Rebuild the Sentinel-1 radiometric calibration layer from the COMPLETE
post-recovery raw-sample universe:

    original C2M samples
    + successful C2M-R recovered samples

This script DOES NOT overwrite historical C2N outputs.

Key audit improvements over historical C2N
------------------------------------------
1. Explicitly expects all 68 canonical scene/polarization assets.
2. Deduplicates at scene/polarization/target/coordinate level.
3. Retries remote XML and raster metadata access.
4. Uses embedded Sentinel-1 GCPs for pixel geolocation.
5. Strictly checks every sampled row/column lies INSIDE calibration LUT
   line/range support before interpolation. No silent np.interp edge-clamping
   is permitted outside LUT support.
6. Calibrates scene-level samples as DN^2 / LUT^2.
7. Mosaics overlapping scenes at target x polarization x support-point level
   using the median in LINEAR power, then converts to dB.
8. Preserves the scientific firewall.

No thermal-noise subtraction is applied here.
No inundation threshold is selected.
No groundwater, irrigation-flow, or pre-existing flood/exposure values are read.
No association model is fitted.
C2J frozen acquisition universe is unchanged.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import GCPTransformer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

C2M = OUT / "c2m_target_point_signal_samples.csv"
C2MR = OUT / "c2mr_recovered_point_signal_samples.csv"
PLAN = OUT / "c2l_target_mosaic_asset_plan.csv"
ASSETS = OUT / "c2kr_validation_asset_inventory_complete.csv"
C2M_TECH_QA = OUT / "c2m_raster_asset_technical_qa.csv"
C2MR_TECH_QA = OUT / "c2mr_recovered_asset_technical_qa.csv"

SCENE_OUT = OUT / "c2nr_scene_point_calibrated_samples.csv"
XML_QA_OUT = OUT / "c2nr_calibration_xml_qa.csv"
TARGET_OUT = OUT / "c2nr_target_polarization_calibrated_summary.csv"
QA_JSON = OUT / "c2nr_radiometric_calibration_qa.json"
SUMMARY_TXT = OUT / "c2nr_radiometric_calibration_summary.txt"

S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"
RASTER_ENV = {
    "AWS_S3_ENDPOINT": "eodata.dataspace.copernicus.eu",
    "AWS_VIRTUAL_HOSTING": "FALSE",
    "AWS_DEFAULT_REGION": "default",
}
MAX_REMOTE_ATTEMPTS = 5
BASE_DELAY_S = 5


def require_credentials():
    missing = [
        k for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
        if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(
            "Missing CDSE S3 credential environment variable(s): "
            + ", ".join(missing)
        )


def lname(tag):
    return tag.rsplit("}", 1)[-1]


def child(el, name):
    for c in list(el):
        if lname(c.tag) == name:
            return c
    return None


def first(root, name):
    for e in root.iter():
        if lname(e.tag) == name:
            return e
    return None


def text_of(el, name):
    c = child(el, name)
    if c is None or c.text is None:
        raise ValueError(f"Missing XML child: {name}")
    return c.text.strip()


def arr_float(text):
    return np.asarray([float(x) for x in text.split()], dtype=float)


def arr_int(text):
    return np.asarray([int(x) for x in text.split()], dtype=int)


def parse_s3_href(href):
    m = re.match(r"^s3://([^/]+)/(.+)$", str(href))
    if not m:
        raise ValueError(f"Not an s3:// href: {href}")
    return m.group(1), m.group(2)


def make_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="default",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def fetch_bytes_retry(s3, href):
    last = None
    for attempt in range(1, MAX_REMOTE_ATTEMPTS + 1):
        try:
            bucket, key = parse_s3_href(href)
            return s3.get_object(Bucket=bucket, Key=key)["Body"].read(), attempt
        except Exception as e:
            last = repr(e)
            if attempt < MAX_REMOTE_ATTEMPTS:
                delay = BASE_DELAY_S * attempt
                print(f"    XML fetch attempt {attempt} failed: {last}", flush=True)
                print(f"    retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Failed XML fetch after {MAX_REMOTE_ATTEMPTS} attempts: {href}\n{last}")


def parse_calibration_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)

    info = first(root, "calibrationInformation")
    abs_cal = None
    if info is not None:
        x = child(info, "absoluteCalibrationConstant")
        if x is not None and x.text:
            abs_cal = float(x.text.strip())

    vector_list = first(root, "calibrationVectorList")
    if vector_list is None:
        raise ValueError("No calibrationVectorList found")

    vecs = []
    for v in list(vector_list):
        if lname(v.tag) != "calibrationVector":
            continue
        line = int(text_of(v, "line"))
        pixel = arr_int(text_of(v, "pixel"))
        sigma = arr_float(text_of(v, "sigmaNought"))
        beta = arr_float(text_of(v, "betaNought"))
        gamma = arr_float(text_of(v, "gamma"))
        dn = arr_float(text_of(v, "dn"))
        n = len(pixel)
        if not all(len(a) == n for a in [sigma, beta, gamma, dn]):
            raise ValueError(f"LUT length mismatch at line {line}")
        if n < 2:
            raise ValueError(f"Calibration vector at line {line} has <2 range samples")
        if np.any(np.diff(pixel) <= 0):
            raise ValueError(f"Non-increasing pixel LUT at line {line}")
        vecs.append({
            "line": line,
            "pixel": pixel,
            "sigma": sigma,
            "beta": beta,
            "gamma": gamma,
            "dn": dn,
        })

    if not vecs:
        raise ValueError("No calibrationVector entries parsed")

    vecs = sorted(vecs, key=lambda z: z["line"])
    lines = np.asarray([v["line"] for v in vecs], dtype=float)
    if np.any(np.diff(lines) <= 0):
        raise ValueError("Calibration vector lines are not strictly increasing")
    return vecs, abs_cal


def interp_range_strict(vec, col, field):
    px = vec["pixel"].astype(float)
    c = float(col)
    if c < px[0] or c > px[-1]:
        raise ValueError(
            f"Column {c} outside LUT pixel support [{px[0]}, {px[-1]}] "
            f"at line {vec['line']}"
        )
    return float(np.interp(c, px, vec[field].astype(float)))


def interp_2d_strict(vecs, row, col, field):
    lines = np.asarray([v["line"] for v in vecs], dtype=float)
    r = float(row)

    if r < lines[0] or r > lines[-1]:
        raise ValueError(
            f"Row {r} outside calibration line support [{lines[0]}, {lines[-1]}]"
        )

    if r == lines[0]:
        return interp_range_strict(vecs[0], col, field)
    if r == lines[-1]:
        return interp_range_strict(vecs[-1], col, field)

    hi = int(np.searchsorted(lines, r, side="right"))
    lo = hi - 1
    v0, v1 = vecs[lo], vecs[hi]

    a0 = interp_range_strict(v0, col, field)
    a1 = interp_range_strict(v1, col, field)
    l0, l1 = float(v0["line"]), float(v1["line"])
    w = (r - l0) / (l1 - l0)
    return float(a0 + w * (a1 - a0))


def raster_href(plan, scene, pol):
    x = plan.loc[plan["canonical_scene_id"].astype(str).eq(str(scene))]
    if x.empty:
        raise KeyError(f"Scene absent from C2L plan: {scene}")
    col = f"{pol.lower()}_href"
    if col not in x.columns or pd.isna(x.iloc[0][col]):
        raise KeyError(f"Missing {col} in C2L plan for {scene}")
    return str(x.iloc[0][col])


def geolocate_retry(href, lon, lat):
    last = None
    for attempt in range(1, MAX_REMOTE_ATTEMPTS + 1):
        try:
            with rasterio.Env(**RASTER_ENV):
                with rasterio.open(href) as ds:
                    gcps, gcp_crs = ds.gcps
                    if not gcps or gcp_crs is None:
                        raise RuntimeError("Missing embedded GCP geolocation")
                    tr = Transformer.from_crs("EPSG:4326", gcp_crs, always_xy=True)
                    x, y = tr.transform(
                        np.asarray(lon, dtype=float),
                        np.asarray(lat, dtype=float),
                    )
                    with GCPTransformer(gcps) as gt:
                        rows, cols = gt.rowcol(x, y)
                    rows = np.asarray(rows, dtype=int)
                    cols = np.asarray(cols, dtype=int)
                    inside = (
                        (rows >= 0) & (rows < ds.height)
                        & (cols >= 0) & (cols < ds.width)
                    )
                    if not inside.all():
                        bad = int((~inside).sum())
                        raise RuntimeError(
                            f"{bad}/{len(rows)} supplied sample coordinates map outside raster"
                        )
                    return rows, cols, len(gcps), str(gcp_crs), attempt
        except Exception as e:
            last = repr(e)
            if attempt < MAX_REMOTE_ATTEMPTS:
                delay = BASE_DELAY_S * attempt
                print(f"    raster metadata attempt {attempt} failed: {last}", flush=True)
                print(f"    retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Raster metadata/GCP access failed: {href}\n{last}")


def finite_summary(x, prefix):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return {f"{prefix}_{k}": np.nan for k in
                ["n","min","p01","p10","median","mean","p90","p99","max","sd"]}
    q = {
        "n": int(len(a)),
        "min": float(np.min(a)),
        "p01": float(np.quantile(a, .01)),
        "p10": float(np.quantile(a, .10)),
        "median": float(np.median(a)),
        "mean": float(np.mean(a)),
        "p90": float(np.quantile(a, .90)),
        "p99": float(np.quantile(a, .99)),
        "max": float(np.max(a)),
        "sd": float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
    }
    return {f"{prefix}_{k}": v for k, v in q.items()}


def main():
    print("DESIGN C - C2N-R POST-RECOVERY RADIOMETRIC CALIBRATION")
    print("=" * 72)
    print("Combines current C2M + successful C2M-R recovered samples.")
    print("Historical C2N outputs are NOT overwritten.")
    print("Requires complete accounting of 68 canonical scene/polarization assets.")
    print("Calibrates only assets with >=1 finite RiceFloodIT support sample.")
    print("Strict LUT support checks: NO silent edge clamping.")
    print("Calibration: DN^2 / LUT^2.")
    print("NO thermal-noise subtraction.")
    print("NO inundation threshold.")
    print("NO groundwater / irrigation-flow / pre-existing flood outcomes.")
    print("NO association model.\n")

    require_credentials()
    for p in [C2M, C2MR, PLAN, ASSETS, C2M_TECH_QA, C2MR_TECH_QA]:
        if not p.exists():
            raise FileNotFoundError(p)

    base = pd.read_csv(C2M)
    rec = pd.read_csv(C2MR)
    plan = pd.read_csv(PLAN)
    assets = pd.read_csv(ASSETS)
    tech0 = pd.read_csv(C2M_TECH_QA)
    techr = pd.read_csv(C2MR_TECH_QA)

    required = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","canonical_scene_id","polarization","point_id","lon","lat","raw_value"
    ]
    for label, df in [("C2M", base), ("C2M-R", rec)]:
        miss = [c for c in required if c not in df.columns]
        if miss:
            raise AssertionError(f"{label} missing columns: {miss}")

    raw = pd.concat(
        [base[required], rec[required]],
        ignore_index=True,
    )

    # Coordinate-level identity is safer than relying on generated point IDs
    # across two independently written files.
    dedup_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","canonical_scene_id","polarization","lon","lat"
    ]
    before = len(raw)
    raw = raw.drop_duplicates(dedup_keys, keep="last").copy()
    duplicates_removed = before - len(raw)

    pairs = (
        raw[["canonical_scene_id","polarization","platform"]]
        .drop_duplicates()
        .sort_values(["canonical_scene_id","polarization"])
        .reset_index(drop=True)
    )

    # Frozen canonical ASSET universe from C2L: 68 scene/polarization assets.
    canonical = []
    for r in plan.itertuples(index=False):
        scene = str(r.canonical_scene_id)
        platform = str(r.platform)
        if bool(getattr(r, "vv_assets_complete")):
            canonical.append((scene, "VV", platform))
        if bool(getattr(r, "vh_assets_complete")):
            canonical.append((scene, "VH", platform))
    canonical = sorted(set(canonical))
    if len(canonical) != 68:
        raise AssertionError(
            f"Frozen C2L plan does not yield 68 canonical scene/pol assets; got {len(canonical)}"
        )

    # Analytical CONTRIBUTING universe is narrower: a canonical asset contributes
    # only if at least one RiceFloodIT support coordinate has a finite raw value.
    # Original C2M technical QA establishes this for successfully read assets;
    # C2M-R technical QA supersedes original ERROR rows that were recovered.
    contrib = set()
    zero_support = set()

    platform_lookup = {
        str(r.canonical_scene_id): str(r.platform)
        for r in plan.itertuples(index=False)
    }

    recovered_keys = set()
    for r in techr.itertuples(index=False):
        if str(getattr(r, "recovery_status", "")) == "RECOVERED":
            key2 = (str(r.canonical_scene_id), str(r.polarization).upper())
            recovered_keys.add(key2)
            nfin = int(float(getattr(r, "points_with_finite_raw_value_n", 0) or 0))
            tup = (key2[0], key2[1], platform_lookup[key2[0]])
            if nfin > 0:
                contrib.add(tup)
            else:
                zero_support.add(tup)

    for r in tech0.itertuples(index=False):
        key2 = (str(r.canonical_scene_id), str(r.polarization).upper())
        if key2 in recovered_keys:
            continue
        status0 = str(getattr(r, "open_status", ""))
        nfin_raw = getattr(r, "points_with_finite_raw_value_n", 0)
        nfin = 0 if pd.isna(nfin_raw) else int(float(nfin_raw))
        tup = (key2[0], key2[1], platform_lookup[key2[0]])
        if status0 == "OK" and nfin > 0:
            contrib.add(tup)
        elif status0 == "OK" and nfin == 0:
            zero_support.add(tup)
        elif status0 == "ERROR":
            raise AssertionError(
                f"Unrecovered failed canonical asset remains after C2M-R: {key2}"
            )

    canonical_set = set(canonical)
    if (contrib | zero_support) != canonical_set:
        unresolved = sorted(canonical_set - (contrib | zero_support))
        extra_classified = sorted((contrib | zero_support) - canonical_set)
        raise AssertionError(
            f"Canonical asset accounting incomplete. "
            f"Unresolved={unresolved}; extra_classified={extra_classified}"
        )
    if contrib & zero_support:
        raise AssertionError(
            f"Assets classified as both contributing and zero-support: "
            f"{sorted(contrib & zero_support)}"
        )

    expected = sorted(contrib)
    observed = sorted(
        (str(r.canonical_scene_id), str(r.polarization).upper(), str(r.platform))
        for r in pairs.itertuples(index=False)
    )

    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise AssertionError(
            f"Post-recovery raw analytical universe != expected contributing universe. "
            f"Missing={missing}; Extra={extra}"
        )

    print(f"C2M rows + C2M-R rows before dedup: {before}")
    print(f"Duplicate scene-target-coordinate rows removed: {duplicates_removed}")
    print(f"Post-recovery raw rows: {len(raw)}")
    print(f"Canonical scene/polarization assets: {len(canonical)} / 68")
    print(f"Spatially contributing scene/polarization pairs: {len(expected)}")
    print(f"Zero-support canonical scene/polarization assets: {len(zero_support)}")
    for z in sorted(zero_support):
        print(f"    ZERO SUPPORT: {z[0]} {z[1]} ({z[2]})")
    print()

    asset_lookup = {
        (str(r["scene_id"]), str(r["asset_key"])): str(r["href"])
        for _, r in assets.iterrows()
    }
    s3 = make_s3()

    xml_qa = []
    out_parts = []

    for j, r in enumerate(pairs.itertuples(index=False), 1):
        scene = str(r.canonical_scene_id)
        pol = str(r.polarization).upper()
        platform = str(r.platform)
        print(f"[{j:02d}/{len(pairs):02d}] {scene} {pol}", flush=True)

        cal_key = f"schema-calibration-{pol.lower()}"
        cal_href = asset_lookup.get((scene, cal_key))
        if not cal_href:
            raise RuntimeError(f"Missing {cal_key} asset for {scene}")

        xml_bytes, xml_attempts = fetch_bytes_retry(s3, cal_href)
        vecs, abs_cal = parse_calibration_xml(xml_bytes)

        sx = raw.loc[
            raw["canonical_scene_id"].astype(str).eq(scene)
            & raw["polarization"].astype(str).str.upper().eq(pol)
        ].copy()

        rhref = raster_href(plan, scene, pol)
        rows, cols, gcp_n, gcp_crs, raster_attempts = geolocate_retry(
            rhref,
            sx["lon"].to_numpy(float),
            sx["lat"].to_numpy(float),
        )

        line_min = float(vecs[0]["line"])
        line_max = float(vecs[-1]["line"])
        row_out_n = int(((rows < line_min) | (rows > line_max)).sum())

        # For each point, require range support in BOTH bracketing line vectors.
        range_out_n = 0
        sigma_lut = np.empty(len(sx), dtype=float)
        beta_lut = np.empty(len(sx), dtype=float)
        gamma_lut = np.empty(len(sx), dtype=float)
        dn_lut = np.empty(len(sx), dtype=float)

        for i, (rr, cc) in enumerate(zip(rows, cols)):
            try:
                sigma_lut[i] = interp_2d_strict(vecs, rr, cc, "sigma")
                beta_lut[i] = interp_2d_strict(vecs, rr, cc, "beta")
                gamma_lut[i] = interp_2d_strict(vecs, rr, cc, "gamma")
                dn_lut[i] = interp_2d_strict(vecs, rr, cc, "dn")
            except ValueError as e:
                range_out_n += 1
                raise RuntimeError(
                    f"{scene} {pol}: calibration LUT support violation at sample index {i}, "
                    f"row={rr}, col={cc}: {e}"
                ) from e

        if row_out_n or range_out_n:
            raise RuntimeError(
                f"{scene} {pol}: LUT support violations row={row_out_n}, range={range_out_n}"
            )

        dn_raw = sx["raw_value"].to_numpy(float)
        sigma0 = (dn_raw ** 2) / (sigma_lut ** 2)
        beta0 = (dn_raw ** 2) / (beta_lut ** 2)
        gamma0 = (dn_raw ** 2) / (gamma_lut ** 2)

        sx["image_row"] = rows
        sx["image_col"] = cols
        sx["sigma_lut"] = sigma_lut
        sx["beta_lut"] = beta_lut
        sx["gamma_lut"] = gamma_lut
        sx["dn_lut"] = dn_lut
        sx["sigma0_linear"] = sigma0
        sx["sigma0_db"] = np.where(sigma0 > 0, 10*np.log10(sigma0), np.nan)
        sx["beta0_linear"] = beta0
        sx["beta0_db"] = np.where(beta0 > 0, 10*np.log10(beta0), np.nan)
        sx["gamma0_linear"] = gamma0
        sx["gamma0_db"] = np.where(gamma0 > 0, 10*np.log10(gamma0), np.nan)
        sx["thermal_noise_subtracted"] = False
        sx["calibration_xml_href"] = cal_href
        out_parts.append(sx)

        xml_qa.append({
            "canonical_scene_id": scene,
            "platform": platform,
            "polarization": pol,
            "calibration_xml_href": cal_href,
            "xml_fetch_attempts": xml_attempts,
            "raster_metadata_attempts": raster_attempts,
            "xml_bytes_n": len(xml_bytes),
            "calibration_vectors_n": len(vecs),
            "first_vector_line": int(vecs[0]["line"]),
            "last_vector_line": int(vecs[-1]["line"]),
            "min_pixel_lut_points_n": int(min(len(v["pixel"]) for v in vecs)),
            "max_pixel_lut_points_n": int(max(len(v["pixel"]) for v in vecs)),
            "absolute_calibration_constant": abs_cal,
            "gcp_count": int(gcp_n),
            "gcp_crs": gcp_crs,
            "sample_rows_n": int(len(sx)),
            "sample_image_row_min": int(rows.min()),
            "sample_image_row_max": int(rows.max()),
            "sample_image_col_min": int(cols.min()),
            "sample_image_col_max": int(cols.max()),
            "row_outside_lut_support_n": row_out_n,
            "range_outside_lut_support_n": range_out_n,
            "sigma_lut_min": float(np.min(sigma_lut)),
            "sigma_lut_max": float(np.max(sigma_lut)),
            "sigma0_finite_n": int(np.isfinite(sigma0).sum()),
            "status": "PASS",
        })

    calibrated = pd.concat(out_parts, ignore_index=True)
    xml_qa_df = pd.DataFrame(xml_qa)

    calibrated.to_csv(SCENE_OUT, index=False)
    xml_qa_df.to_csv(XML_QA_OUT, index=False)

    point_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","point_id","lon","lat"
    ]
    # Recovery may use a different generated point_id convention. Normalize
    # identity by coordinates within a target before mosaicking.
    coord_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","lon","lat"
    ]
    mosaic = (
        calibrated.groupby(coord_keys, as_index=False)
        .agg(
            point_id=("point_id", "first"),
            sigma0_linear=("sigma0_linear", "median"),
            beta0_linear=("beta0_linear", "median"),
            gamma0_linear=("gamma0_linear", "median"),
            contributing_scenes_n=("canonical_scene_id", "nunique"),
        )
    )
    mosaic["sigma0_db"] = np.where(
        mosaic["sigma0_linear"] > 0, 10*np.log10(mosaic["sigma0_linear"]), np.nan
    )
    mosaic["beta0_db"] = np.where(
        mosaic["beta0_linear"] > 0, 10*np.log10(mosaic["beta0_linear"]), np.nan
    )
    mosaic["gamma0_db"] = np.where(
        mosaic["gamma0_linear"] > 0, 10*np.log10(mosaic["gamma0_linear"]), np.nan
    )

    target_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization"
    ]
    summary_rows = []
    for key, g in mosaic.groupby(target_keys, dropna=False):
        row = dict(zip(target_keys, key))
        row["points_n"] = int(len(g))
        row["points_with_multi_scene_overlap_n"] = int((g["contributing_scenes_n"] > 1).sum())
        row.update(finite_summary(g["sigma0_db"], "sigma0_db"))
        row.update(finite_summary(g["beta0_db"], "beta0_db"))
        row.update(finite_summary(g["gamma0_db"], "gamma0_db"))
        summary_rows.append(row)

    target = pd.DataFrame(summary_rows).sort_values(target_keys)
    target.to_csv(TARGET_OUT, index=False)

    row_viol = int(xml_qa_df["row_outside_lut_support_n"].sum())
    range_viol = int(xml_qa_df["range_outside_lut_support_n"].sum())
    finite_all = bool(
        np.isfinite(calibrated["sigma0_linear"]).all()
        and np.isfinite(calibrated["beta0_linear"]).all()
        and np.isfinite(calibrated["gamma0_linear"]).all()
    )

    status = (
        "PASS"
        if len(pairs) == len(expected)
        and len(xml_qa_df) == len(expected)
        and row_viol == 0
        and range_viol == 0
        and finite_all
        and len(target) == 36
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2NR_POST_RECOVERY_RADIOMETRIC_CALIBRATION",
        "historical_c2n_preserved": True,
        "base_c2m_rows_n": int(len(base)),
        "recovered_c2mr_rows_n": int(len(rec)),
        "combined_before_dedup_n": int(before),
        "duplicates_removed_n": int(duplicates_removed),
        "post_recovery_raw_rows_n": int(len(raw)),
        "canonical_scene_polarization_assets_n": int(len(canonical)),
        "expected_spatially_contributing_scene_polarization_pairs_n": int(len(expected)),
        "zero_support_canonical_scene_polarization_assets_n": int(len(zero_support)),
        "zero_support_canonical_scene_polarization_assets": [
            {"canonical_scene_id": s, "polarization": p, "platform": pl}
            for s, p, pl in sorted(zero_support)
        ],
        "observed_spatially_contributing_scene_polarization_pairs_n": int(len(pairs)),
        "calibration_xmls_parsed_n": int(len(xml_qa_df)),
        "calibrated_scene_point_rows_n": int(len(calibrated)),
        "target_polarization_summaries_n": int(len(target)),
        "calibration_equation": "value = DN^2 / LUT^2",
        "lut_interpolation": "bilinear line/range with strict no-outside-support rule",
        "row_outside_lut_support_n": row_viol,
        "range_outside_lut_support_n": range_viol,
        "all_calibrated_linear_values_finite": finite_all,
        "thermal_noise_subtraction_applied": False,
        "inundation_threshold_selected": False,
        "groundwater_level_values_read": False,
        "irrigation_flow_values_read": False,
        "existing_flooding_exposure_values_read": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "next_stage": "Post-recovery thermal-noise audit/correction using C2N-R outputs.",
    }
    QA_JSON.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2N-R POST-RECOVERY RADIOMETRIC CALIBRATION",
        "=" * 72,
        "",
        f"Base C2M rows: {len(base)}",
        f"Recovered C2M-R rows: {len(rec)}",
        f"Combined rows before dedup: {before}",
        f"Duplicate rows removed: {duplicates_removed}",
        f"Post-recovery raw rows: {len(raw)}",
        f"Canonical scene/polarization assets: {len(canonical)} / 68",
        f"Spatially contributing scene/polarization pairs: {len(pairs)} / {len(expected)}",
        f"Zero-support canonical scene/polarization assets: {len(zero_support)}",
        *[
            f"  ZERO SUPPORT: {s} {p} ({pl})"
            for s, p, pl in sorted(zero_support)
        ],
        f"Calibration XMLs parsed for contributing pairs: {len(xml_qa_df)} / {len(expected)}",
        f"Calibrated scene-point rows: {len(calibrated)}",
        f"Target/polarization summaries: {len(target)} / 36",
        f"Rows outside LUT line support: {row_viol}",
        f"Samples outside LUT range support: {range_viol}",
        f"All calibrated linear values finite: {finite_all}",
        "",
        "CALIBRATION",
        "-----------",
        "value = DN^2 / LUT^2",
        "Bilinear line/range interpolation.",
        "Strict support checking: no silent np.interp edge clamping outside LUT support.",
        "Scene overlap is aggregated using median LINEAR power before dB conversion.",
        "",
        "FIREWALL",
        "--------",
        "Historical C2N outputs preserved.",
        "All 68 canonical scene/polarization assets are accounted for.",
        "Zero-support canonical assets are documented but not artificially sampled/calibrated.",
        "No thermal-noise subtraction applied at this stage.",
        "No inundation threshold selected.",
        "No groundwater values read.",
        "No irrigation-flow values read.",
        "No pre-existing flood/exposure labels read.",
        "No association model fitted.",
        "C2J frozen acquisition universe unchanged.",
        "",
        f"C2N-R STATUS: {status}",
    ]
    txt = "\n".join(lines) + "\n"
    SUMMARY_TXT.write_text(txt, encoding="utf-8")
    print("\n" + txt)

    if status != "PASS":
        raise RuntimeError("C2N-R did not satisfy freeze criteria; inspect outputs.")


if __name__ == "__main__":
    main()

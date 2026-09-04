"""Design C — C2N Sentinel-1 Radiometric Calibration Audit.

Convert C2M raw Sentinel-1 GRD amplitude samples into calibrated
sigma0, beta0 and gamma0 using each scene/polarization calibration XML.

Calibration rule:
    value = DN^2 / LUT^2

LUT interpolation is bilinear in image line and range pixel.

No thermal-noise subtraction is applied here.
No inundation threshold is selected.
No groundwater, irrigation, or pre-existing flooding/exposure outcomes are read.
"""

from __future__ import annotations

import json
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import GCPTransformer

try:
    import boto3
except ImportError as e:
    raise RuntimeError(
        "C2N requires boto3. Install once with: python -m pip install boto3"
    ) from e


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

SAMPLES = OUT / "c2m_target_point_signal_samples.csv"
PLAN = OUT / "c2l_target_mosaic_asset_plan.csv"
ASSETS = OUT / "c2kr_validation_asset_inventory_complete.csv"

S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"
RASTER_ENV = {
    "AWS_S3_ENDPOINT": "eodata.dataspace.copernicus.eu",
    "AWS_VIRTUAL_HOSTING": "FALSE",
    "AWS_DEFAULT_REGION": "default",
}


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


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_child(el, name):
    for c in list(el):
        if localname(c.tag) == name:
            return c
    return None


def find_first(root, name):
    for el in root.iter():
        if localname(el.tag) == name:
            return el
    return None


def text_of(el, child_name, required=True):
    c = find_child(el, child_name)
    if c is None or c.text is None:
        if required:
            raise ValueError(f"Missing XML element {child_name}")
        return None
    return c.text.strip()


def parse_s3_href(href: str):
    m = re.match(r"^s3://([^/]+)/(.+)$", str(href))
    if not m:
        raise ValueError(f"Not an s3:// href: {href}")
    return m.group(1), m.group(2)


def make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="default",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def fetch_s3_bytes(client, href: str) -> bytes:
    bucket, key = parse_s3_href(href)
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def parse_float_array(text):
    return np.asarray([float(x) for x in text.split()], dtype=float)


def parse_int_array(text):
    return np.asarray([int(x) for x in text.split()], dtype=int)


def parse_calibration_xml(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)

    cal_info = find_first(root, "calibrationInformation")
    absolute_cal = None
    if cal_info is not None:
        x = find_child(cal_info, "absoluteCalibrationConstant")
        if x is not None and x.text:
            absolute_cal = float(x.text.strip())

    vector_list = find_first(root, "calibrationVectorList")
    if vector_list is None:
        raise ValueError("No calibrationVectorList found")

    rows = []
    for v in list(vector_list):
        if localname(v.tag) != "calibrationVector":
            continue

        line = int(text_of(v, "line"))
        pixel = parse_int_array(text_of(v, "pixel"))
        sigma = parse_float_array(text_of(v, "sigmaNought"))
        beta = parse_float_array(text_of(v, "betaNought"))
        gamma = parse_float_array(text_of(v, "gamma"))
        dn = parse_float_array(text_of(v, "dn"))

        n = len(pixel)
        if not all(len(a) == n for a in [sigma, beta, gamma, dn]):
            raise ValueError(
                f"LUT length mismatch at line {line}: "
                f"pixel={n}, sigma={len(sigma)}, beta={len(beta)}, "
                f"gamma={len(gamma)}, dn={len(dn)}"
            )

        rows.append({
            "line": line,
            "pixel": pixel,
            "sigma": sigma,
            "beta": beta,
            "gamma": gamma,
            "dn": dn,
        })

    if not rows:
        raise ValueError("No calibrationVector entries parsed")

    return sorted(rows, key=lambda x: x["line"]), absolute_cal


def interp_range(vec, col, field):
    return float(
        np.interp(
            float(col),
            vec["pixel"].astype(float),
            vec[field].astype(float),
        )
    )


def interp_2d(vectors, row, col, field):
    lines = np.asarray([v["line"] for v in vectors], dtype=float)
    r = float(row)

    if r <= lines[0]:
        return interp_range(vectors[0], col, field)
    if r >= lines[-1]:
        return interp_range(vectors[-1], col, field)

    hi = int(np.searchsorted(lines, r, side="right"))
    lo = hi - 1

    v0 = vectors[lo]
    v1 = vectors[hi]
    l0 = float(v0["line"])
    l1 = float(v1["line"])

    a0 = interp_range(v0, col, field)
    a1 = interp_range(v1, col, field)

    if l1 == l0:
        return a0

    w = (r - l0) / (l1 - l0)
    return float(a0 + w * (a1 - a0))


def get_scene_raster_href(plan, scene, pol):
    x = plan[plan["canonical_scene_id"].astype(str).eq(str(scene))]
    if x.empty:
        raise KeyError(f"Scene absent from C2L plan: {scene}")
    return str(x.iloc[0][f"{pol.lower()}_href"])


def geolocate_points(raster_href, lon, lat):
    with rasterio.Env(**RASTER_ENV):
        with rasterio.open(raster_href) as ds:
            gcps, gcp_crs = ds.gcps
            if not gcps or gcp_crs is None:
                raise RuntimeError(
                    f"Missing GCP geolocation for {raster_href}"
                )

            tr = Transformer.from_crs(
                "EPSG:4326", gcp_crs, always_xy=True
            )
            x, y = tr.transform(
                np.asarray(lon, dtype=float),
                np.asarray(lat, dtype=float),
            )

            with GCPTransformer(gcps) as gt:
                rows, cols = gt.rowcol(x, y)

            return (
                np.asarray(rows, dtype=int),
                np.asarray(cols, dtype=int),
                len(gcps),
                str(gcp_crs),
            )


def finite_summary(x):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return {
            "n": 0, "min": None, "p01": None, "p10": None,
            "median": None, "mean": None, "p90": None,
            "p99": None, "max": None, "sd": None,
        }
    return {
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


def main():
    print("DESIGN C - C2N SENTINEL-1 RADIOMETRIC CALIBRATION AUDIT")
    print("=" * 68)
    print("Reads scene-specific calibration XMLs and raster GCP metadata.")
    print("Uses frozen C2M raw samples.")
    print("NO thermal-noise subtraction is applied.")
    print("NO inundation threshold is selected.")
    print("NO groundwater or irrigation outcomes are read.")
    print("NO association model is fitted.")
    print("C2J frozen acquisition universe unchanged.\n")

    require_credentials()

    for p in [SAMPLES, PLAN, ASSETS]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required input: {p}")

    samples = pd.read_csv(SAMPLES)
    plan = pd.read_csv(PLAN)
    assets = pd.read_csv(ASSETS)

    client = make_s3_client()

    asset_lookup = {
        (str(r["scene_id"]), str(r["asset_key"])): str(r["href"])
        for _, r in assets.iterrows()
    }

    pairs = (
        samples[["canonical_scene_id", "polarization", "platform"]]
        .drop_duplicates()
        .sort_values(["canonical_scene_id", "polarization"])
    )

    xml_qa = []
    out_parts = []

    for j, r in enumerate(pairs.itertuples(index=False), 1):
        scene = str(r.canonical_scene_id)
        pol = str(r.polarization).upper()
        platform = str(r.platform)

        print(f"[{j:02d}/{len(pairs):02d}] {scene} {pol}")

        cal_key = f"schema-calibration-{pol.lower()}"
        cal_href = asset_lookup.get((scene, cal_key))
        if not cal_href:
            raise RuntimeError(
                f"Missing {cal_key} asset for scene {scene}"
            )

        xml_bytes = fetch_s3_bytes(client, cal_href)
        vectors, abs_cal = parse_calibration_xml(xml_bytes)

        sx = samples[
            samples["canonical_scene_id"].astype(str).eq(scene)
            & samples["polarization"].astype(str).str.upper().eq(pol)
        ].copy()

        raster_href = get_scene_raster_href(plan, scene, pol)
        rows, cols, gcp_n, gcp_crs = geolocate_points(
            raster_href,
            sx["lon"].to_numpy(float),
            sx["lat"].to_numpy(float),
        )

        sigma_lut = np.empty(len(sx), dtype=float)
        beta_lut = np.empty(len(sx), dtype=float)
        gamma_lut = np.empty(len(sx), dtype=float)
        dn_lut = np.empty(len(sx), dtype=float)

        for i, (rr, cc) in enumerate(zip(rows, cols)):
            sigma_lut[i] = interp_2d(vectors, rr, cc, "sigma")
            beta_lut[i] = interp_2d(vectors, rr, cc, "beta")
            gamma_lut[i] = interp_2d(vectors, rr, cc, "gamma")
            dn_lut[i] = interp_2d(vectors, rr, cc, "dn")

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
        sx["sigma0_db"] = np.where(
            sigma0 > 0, 10.0 * np.log10(sigma0), np.nan
        )
        sx["beta0_linear"] = beta0
        sx["beta0_db"] = np.where(
            beta0 > 0, 10.0 * np.log10(beta0), np.nan
        )
        sx["gamma0_linear"] = gamma0
        sx["gamma0_db"] = np.where(
            gamma0 > 0, 10.0 * np.log10(gamma0), np.nan
        )
        sx["thermal_noise_subtracted"] = False
        sx["calibration_xml_href"] = cal_href

        out_parts.append(sx)

        xml_qa.append({
            "canonical_scene_id": scene,
            "platform": platform,
            "polarization": pol,
            "calibration_xml_href": cal_href,
            "xml_bytes_n": len(xml_bytes),
            "calibration_vectors_n": len(vectors),
            "first_vector_line": int(vectors[0]["line"]),
            "last_vector_line": int(vectors[-1]["line"]),
            "min_pixel_lut_points_n": int(
                min(len(v["pixel"]) for v in vectors)
            ),
            "max_pixel_lut_points_n": int(
                max(len(v["pixel"]) for v in vectors)
            ),
            "absolute_calibration_constant": abs_cal,
            "gcp_count": int(gcp_n),
            "gcp_crs": gcp_crs,
            "sample_rows_n": int(len(sx)),
            "sigma_lut_min": float(np.min(sigma_lut)),
            "sigma_lut_max": float(np.max(sigma_lut)),
            "sigma0_finite_n": int(np.isfinite(sigma0).sum()),
            "status": "PASS",
        })

    calibrated = pd.concat(out_parts, ignore_index=True)
    xml_qa_df = pd.DataFrame(xml_qa)

    calibrated.to_csv(
        OUT / "c2n_scene_point_calibrated_samples.csv",
        index=False,
    )
    xml_qa_df.to_csv(
        OUT / "c2n_calibration_xml_qa.csv",
        index=False,
    )

    point_keys = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform",
        "polarization", "point_id", "lon", "lat"
    ]

    mosaic = (
        calibrated.groupby(point_keys, as_index=False)
        .agg(
            sigma0_linear=("sigma0_linear", "median"),
            beta0_linear=("beta0_linear", "median"),
            gamma0_linear=("gamma0_linear", "median"),
            contributing_scenes_n=("canonical_scene_id", "nunique"),
        )
    )

    mosaic["sigma0_db"] = np.where(
        mosaic["sigma0_linear"] > 0,
        10.0 * np.log10(mosaic["sigma0_linear"]),
        np.nan,
    )
    mosaic["beta0_db"] = np.where(
        mosaic["beta0_linear"] > 0,
        10.0 * np.log10(mosaic["beta0_linear"]),
        np.nan,
    )
    mosaic["gamma0_db"] = np.where(
        mosaic["gamma0_linear"] > 0,
        10.0 * np.log10(mosaic["gamma0_linear"]),
        np.nan,
    )

    group_cols = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform", "polarization"
    ]

    summary_rows = []
    for key, g in mosaic.groupby(group_cols):
        rec = dict(zip(group_cols, key))
        rec["points_n"] = int(g["point_id"].nunique())
        rec["multi_scene_points_n"] = int(
            (g["contributing_scenes_n"] > 1).sum()
        )

        for field in ["sigma0_db", "beta0_db", "gamma0_db"]:
            stats = finite_summary(g[field])
            for stat, value in stats.items():
                rec[f"{field}_{stat}"] = value

        summary_rows.append(rec)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(
        OUT / "c2n_target_polarization_calibrated_summary.csv",
        index=False,
    )

    expected_pairs_n = int(len(pairs))
    all_xml_pass = bool(
        len(xml_qa_df) == expected_pairs_n
        and xml_qa_df["status"].eq("PASS").all()
    )

    qa = {
        "status": "PASS" if all_xml_pass else "PASS_WITH_LIMITATIONS",
        "stage": "DESIGN_C_C2N_SENTINEL1_RADIOMETRIC_CALIBRATION",
        "scene_polarization_pairs_n": expected_pairs_n,
        "calibration_xmls_parsed_n": int(len(xml_qa_df)),
        "calibrated_scene_point_rows_n": int(len(calibrated)),
        "target_polarization_summaries_n": int(len(summary)),
        "platforms": sorted(
            calibrated["platform"].dropna().astype(str).unique()
        ),
        "polarizations": sorted(
            calibrated["polarization"].dropna().astype(str).unique()
        ),
        "calibration_equation": "value = DN^2 / LUT^2",
        "lut_interpolation": "bilinear in image line and range pixel",
        "thermal_noise_subtraction_applied": False,
        "inundation_threshold_selected": False,
        "groundwater_level_values_read": False,
        "irrigation_flow_values_read": False,
        "existing_flooding_exposure_values_read": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "next_stage": (
            "Audit scene-specific noise XMLs and processing metadata before "
            "deciding whether/how thermal-noise correction is required."
        ),
    }

    (OUT / "c2n_radiometric_calibration_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    cols = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform",
        "polarization", "points_n",
        "sigma0_db_median", "sigma0_db_mean",
        "sigma0_db_p10", "sigma0_db_p90",
    ]

    lines = [
        "DESIGN C - C2N SENTINEL-1 RADIOMETRIC CALIBRATION AUDIT",
        "=" * 66,
        "",
        f"Scene/polarization pairs: {expected_pairs_n}",
        f"Calibration XMLs parsed: {len(xml_qa_df)}",
        f"Calibrated scene-point rows: {len(calibrated)}",
        f"Target/polarization summaries: {len(summary)}",
        f"Platforms: {'|'.join(qa['platforms'])}",
        f"Polarizations: {'|'.join(qa['polarizations'])}",
        "",
        "CALIBRATION",
        "-----------",
        "value = DN^2 / LUT^2",
        "LUT interpolation: bilinear in image line and range pixel",
        "sigma0, beta0 and gamma0 computed in linear and dB forms",
        "",
        "THERMAL NOISE",
        "-------------",
        "NOT subtracted at C2N.",
        "Noise XMLs will be audited prospectively in the next stage.",
        "",
        "TARGET / POLARIZATION SIGMA0 SUMMARY",
        "------------------------------------",
        summary[cols].to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "No inundation threshold selected.",
        "No groundwater values read.",
        "No irrigation-flow values read.",
        "No pre-existing flooding exposure values read.",
        "No association model fitted.",
        "C2J frozen acquisition universe unchanged.",
        "",
        f"C2N STATUS: {qa['status']}",
    ]

    txt = "\n".join(lines) + "\n"
    (OUT / "c2n_radiometric_calibration_summary.txt").write_text(
        txt, encoding="utf-8"
    )

    print("\n" + txt)


if __name__ == "__main__":
    main()

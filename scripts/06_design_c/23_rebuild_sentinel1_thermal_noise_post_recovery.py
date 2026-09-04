"""Design C — C2O-R post-recovery Sentinel-1 thermal-noise rebuild.

Consumes the completed C2N-R calibrated scene-point table and rebuilds the
thermal-noise-corrected layer without overwriting historical C2O outputs.

Scientific rules
----------------
- 68 canonical scene/polarization assets must remain fully accounted for.
- 66 spatially contributing scene/polarization pairs are expected.
- Legacy and modern Sentinel-1 noise XML schemas are supported.
- thermalNoiseCorrectionPerformed must be false for every contributing asset.
- Noise LUT interpolation is strict: no silent edge clamping/extrapolation.
- Modern azimuth blocks must match uniquely for every sampled point.
- corrected_power = DN^2 - eta
- Non-positive corrected power is flagged and retained as NaN after calibration;
  it is NEVER clipped.
- Scene overlap is mosaicked using median LINEAR corrected power before dB.
- No inundation threshold, groundwater, irrigation-flow, prior flood labels,
  or association model are used.
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

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

C2NR = OUT / "c2nr_scene_point_calibrated_samples.csv"
ASSETS = OUT / "c2kr_validation_asset_inventory_complete.csv"
PLAN = OUT / "c2l_target_mosaic_asset_plan.csv"
C2M_TECH = OUT / "c2m_raster_asset_technical_qa.csv"
C2MR_TECH = OUT / "c2mr_recovered_asset_technical_qa.csv"

SCENE_OUT = OUT / "c2or_scene_point_noise_corrected_samples.csv"
NOISE_QA_OUT = OUT / "c2or_noise_xml_qa.csv"
TARGET_OUT = OUT / "c2or_target_polarization_noise_effect_summary.csv"
QA_JSON = OUT / "c2or_thermal_noise_qa.json"
SUMMARY_TXT = OUT / "c2or_thermal_noise_summary.txt"

S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"
MAX_REMOTE_ATTEMPTS = 5
BASE_DELAY_S = 5


def require_credentials():
    missing = [k for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
               if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing CDSE S3 credential environment variable(s): "
                           + ", ".join(missing))


def make_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="default",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def parse_s3_href(href):
    m = re.match(r"^s3://([^/]+)/(.+)$", str(href))
    if not m:
        raise ValueError(f"Not an s3:// href: {href}")
    return m.group(1), m.group(2)


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
                print(f"    fetch attempt {attempt} failed: {last}", flush=True)
                print(f"    retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Remote XML fetch failed after {MAX_REMOTE_ATTEMPTS} attempts: {href}\n{last}")


def lname(tag):
    return tag.rsplit("}", 1)[-1]


def first(root, name):
    for e in root.iter():
        if lname(e.tag) == name:
            return e
    return None


def child_text(el, name, required=True):
    for c in list(el):
        if lname(c.tag) == name and c.text is not None:
            return c.text.strip()
    if required:
        raise ValueError(f"Missing XML child: {name}")
    return None


def arr_float(text):
    return np.asarray([float(x) for x in text.split()], dtype=float)


def arr_int(text):
    return np.asarray([int(x) for x in text.split()], dtype=int)


def parse_product_noise_flag(xml_bytes):
    root = ET.fromstring(xml_bytes)
    e = first(root, "thermalNoiseCorrectionPerformed")
    if e is None or e.text is None:
        return None
    return e.text.strip().lower()


def parse_noise_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    legacy = first(root, "noiseVectorList")
    modern_range = first(root, "noiseRangeVectorList")
    modern_az = first(root, "noiseAzimuthVectorList")

    if legacy is not None:
        vecs = []
        for v in list(legacy):
            if lname(v.tag) != "noiseVector":
                continue
            line = int(child_text(v, "line"))
            pixel = arr_int(child_text(v, "pixel"))
            lut = arr_float(child_text(v, "noiseLut"))
            if len(pixel) != len(lut):
                raise ValueError(f"Legacy LUT length mismatch at line {line}")
            if len(pixel) < 2 or np.any(np.diff(pixel) <= 0):
                raise ValueError(f"Invalid legacy pixel support at line {line}")
            vecs.append({"line": line, "pixel": pixel, "noise": lut})
        if not vecs:
            raise ValueError("Legacy schema found but no vectors parsed")
        vecs = sorted(vecs, key=lambda z: z["line"])
        lines = np.asarray([v["line"] for v in vecs], dtype=float)
        if np.any(np.diff(lines) <= 0):
            raise ValueError("Legacy noise vector lines not strictly increasing")
        return {
            "schema": "legacy_noiseVectorList",
            "legacy_vectors": vecs,
            "range_vectors": [],
            "azimuth_vectors": [],
        }

    if modern_range is not None:
        rvecs = []
        for v in list(modern_range):
            if lname(v.tag) != "noiseRangeVector":
                continue
            line = int(child_text(v, "line"))
            pixel = arr_int(child_text(v, "pixel"))
            lut = arr_float(child_text(v, "noiseRangeLut"))
            if len(pixel) != len(lut):
                raise ValueError(f"Modern range LUT mismatch at line {line}")
            if len(pixel) < 2 or np.any(np.diff(pixel) <= 0):
                raise ValueError(f"Invalid modern range support at line {line}")
            rvecs.append({"line": line, "pixel": pixel, "noise": lut})
        if not rvecs:
            raise ValueError("Modern schema found but no range vectors parsed")
        rvecs = sorted(rvecs, key=lambda z: z["line"])
        rlines = np.asarray([v["line"] for v in rvecs], dtype=float)
        if np.any(np.diff(rlines) <= 0):
            raise ValueError("Modern range vector lines not strictly increasing")

        avecs = []
        if modern_az is not None:
            for v in list(modern_az):
                if lname(v.tag) != "noiseAzimuthVector":
                    continue
                fal = child_text(v, "firstAzimuthLine", required=False)
                lal = child_text(v, "lastAzimuthLine", required=False)
                frs = child_text(v, "firstRangeSample", required=False)
                lrs = child_text(v, "lastRangeSample", required=False)
                line_text = child_text(v, "line", required=False)
                lut_text = child_text(v, "noiseAzimuthLut", required=False)
                swath = child_text(v, "swath", required=False)
                if line_text is None or lut_text is None:
                    continue
                lines = arr_int(line_text)
                lut = arr_float(lut_text)
                if len(lines) != len(lut):
                    raise ValueError("Azimuth LUT length mismatch")
                if len(lines) < 2 or np.any(np.diff(lines) <= 0):
                    raise ValueError("Invalid azimuth line support")
                avecs.append({
                    "swath": swath,
                    "firstAzimuthLine": int(fal) if fal is not None else None,
                    "lastAzimuthLine": int(lal) if lal is not None else None,
                    "firstRangeSample": int(frs) if frs is not None else None,
                    "lastRangeSample": int(lrs) if lrs is not None else None,
                    "line": lines,
                    "noise": lut,
                })
        return {
            "schema": "modern_range_x_azimuth",
            "legacy_vectors": [],
            "range_vectors": rvecs,
            "azimuth_vectors": avecs,
        }

    raise ValueError("Unrecognized Sentinel-1 noise XML schema")


def interp1_strict(px, vals, x, label):
    px = np.asarray(px, dtype=float)
    vals = np.asarray(vals, dtype=float)
    xx = float(x)
    if xx < px[0] or xx > px[-1]:
        raise ValueError(f"{label}: coordinate {xx} outside [{px[0]}, {px[-1]}]")
    return float(np.interp(xx, px, vals))


def interp_2d_line_pixel_strict(vectors, row, col, label):
    lines = np.asarray([v["line"] for v in vectors], dtype=float)
    r = float(row)
    if r < lines[0] or r > lines[-1]:
        raise ValueError(f"{label}: row {r} outside [{lines[0]}, {lines[-1]}]")

    if r == lines[0]:
        return interp1_strict(vectors[0]["pixel"], vectors[0]["noise"], col, label+" range")
    if r == lines[-1]:
        return interp1_strict(vectors[-1]["pixel"], vectors[-1]["noise"], col, label+" range")

    hi = int(np.searchsorted(lines, r, side="right"))
    lo = hi - 1
    v0, v1 = vectors[lo], vectors[hi]
    n0 = interp1_strict(v0["pixel"], v0["noise"], col, label+" range")
    n1 = interp1_strict(v1["pixel"], v1["noise"], col, label+" range")
    l0, l1 = float(v0["line"]), float(v1["line"])
    w = (r - l0) / (l1 - l0)
    return float(n0 + w * (n1 - n0))


def applicable_azimuth_vectors(azvecs, row, col):
    out = []
    for v in azvecs:
        fal, lal = v["firstAzimuthLine"], v["lastAzimuthLine"]
        frs, lrs = v["firstRangeSample"], v["lastRangeSample"]
        row_ok = (fal is None or row >= fal) and (lal is None or row <= lal)
        col_ok = (frs is None or col >= frs) and (lrs is None or col <= lrs)
        if row_ok and col_ok:
            out.append(v)
    return out


def modern_azimuth_factor_strict(azvecs, row, col):
    if not azvecs:
        return 1.0, 0
    candidates = applicable_azimuth_vectors(azvecs, row, col)
    if len(candidates) == 0:
        raise ValueError(f"No applicable azimuth noise block for row={row}, col={col}")
    if len(candidates) > 1:
        raise ValueError(f"Multiple azimuth noise blocks ({len(candidates)}) for row={row}, col={col}")
    v = candidates[0]
    val = interp1_strict(v["line"], v["noise"], row, "azimuth")
    return val, 1


def noise_power_at_strict(parsed, row, col):
    if parsed["schema"] == "legacy_noiseVectorList":
        eta = interp_2d_line_pixel_strict(
            parsed["legacy_vectors"], row, col, "legacy noise"
        )
        return eta, np.nan, np.nan, 1

    nr = interp_2d_line_pixel_strict(
        parsed["range_vectors"], row, col, "modern range noise"
    )
    na, nc = modern_azimuth_factor_strict(
        parsed["azimuth_vectors"], row, col
    )
    return nr * na, nr, na, nc


def finite_summary(x, prefix):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    keys = ["n","min","p01","p10","median","mean","p90","p99","max"]
    if len(a) == 0:
        return {f"{prefix}_{k}": np.nan for k in keys}
    vals = {
        "n": int(len(a)),
        "min": float(np.min(a)),
        "p01": float(np.quantile(a,.01)),
        "p10": float(np.quantile(a,.10)),
        "median": float(np.median(a)),
        "mean": float(np.mean(a)),
        "p90": float(np.quantile(a,.90)),
        "p99": float(np.quantile(a,.99)),
        "max": float(np.max(a)),
    }
    return {f"{prefix}_{k}": v for k,v in vals.items()}


def main():
    print("DESIGN C - C2O-R POST-RECOVERY THERMAL-NOISE REBUILD")
    print("=" * 72)
    print("Consumes completed C2N-R calibrated samples.")
    print("Historical C2O outputs are NOT overwritten.")
    print("Strict range/azimuth noise support checks.")
    print("Non-positive corrected power is FLAGGED, never clipped.")
    print("NO inundation threshold.")
    print("NO groundwater / irrigation-flow / pre-existing flood outcomes.")
    print("NO association model.\n")

    require_credentials()
    for p in [C2NR, ASSETS, PLAN, C2M_TECH, C2MR_TECH]:
        if not p.exists():
            raise FileNotFoundError(p)

    s = pd.read_csv(C2NR)
    a = pd.read_csv(ASSETS)
    plan = pd.read_csv(PLAN)

    pairs = (
        s[["canonical_scene_id","polarization","platform"]]
        .drop_duplicates()
        .sort_values(["canonical_scene_id","polarization"])
        .reset_index(drop=True)
    )
    if len(pairs) != 66:
        raise AssertionError(f"Expected 66 spatially contributing scene/pol pairs, got {len(pairs)}")

    # Confirm frozen 68 canonical assets still exist in C2L.
    canonical = []
    for r in plan.itertuples(index=False):
        scene = str(r.canonical_scene_id)
        platform = str(r.platform)
        if bool(getattr(r, "vv_assets_complete")):
            canonical.append((scene,"VV",platform))
        if bool(getattr(r, "vh_assets_complete")):
            canonical.append((scene,"VH",platform))
    canonical = sorted(set(canonical))
    if len(canonical) != 68:
        raise AssertionError(f"Expected 68 canonical scene/pol assets in C2L, got {len(canonical)}")

    observed = set(
        (str(r.canonical_scene_id), str(r.polarization).upper(), str(r.platform))
        for r in pairs.itertuples(index=False)
    )
    zero_support = sorted(set(canonical) - observed)
    if len(zero_support) != 2:
        raise AssertionError(f"Expected exactly 2 zero-support canonical assets, got {zero_support}")

    asset_lookup = {
        (str(r["scene_id"]), str(r["asset_key"])): str(r["href"])
        for _, r in a.iterrows()
    }

    s3 = make_s3()
    corrected_parts = []
    qa_rows = []

    for j, r in enumerate(pairs.itertuples(index=False), 1):
        scene = str(r.canonical_scene_id)
        pol = str(r.polarization).upper()
        platform = str(r.platform)
        print(f"[{j:02d}/66] {scene} {pol}", flush=True)

        noise_key = f"schema-noise-{pol.lower()}"
        prod_key = f"schema-product-{pol.lower()}"
        noise_href = asset_lookup.get((scene, noise_key))
        prod_href = asset_lookup.get((scene, prod_key))
        if not noise_href:
            raise RuntimeError(f"Missing {noise_key} for {scene}")
        if not prod_href:
            raise RuntimeError(f"Missing {prod_key} for {scene}")

        noise_bytes, noise_attempts = fetch_bytes_retry(s3, noise_href)
        prod_bytes, prod_attempts = fetch_bytes_retry(s3, prod_href)

        flag = parse_product_noise_flag(prod_bytes)
        if flag != "false":
            raise RuntimeError(
                f"{scene} {pol}: expected thermalNoiseCorrectionPerformed=false, got {flag!r}"
            )

        parsed = parse_noise_xml(noise_bytes)
        x = s.loc[
            s["canonical_scene_id"].astype(str).eq(scene)
            & s["polarization"].astype(str).str.upper().eq(pol)
        ].copy()

        eta = np.empty(len(x), dtype=float)
        nr = np.empty(len(x), dtype=float)
        na = np.empty(len(x), dtype=float)
        cand_n = np.empty(len(x), dtype=int)

        rows = x["image_row"].to_numpy(int)
        cols = x["image_col"].to_numpy(int)

        for i, (rr, cc) in enumerate(zip(rows, cols)):
            try:
                e, rn, an, nc = noise_power_at_strict(parsed, int(rr), int(cc))
            except ValueError as e:
                raise RuntimeError(
                    f"{scene} {pol}: noise LUT support violation at sample {i}, "
                    f"row={rr}, col={cc}: {e}"
                ) from e
            eta[i] = e
            nr[i] = rn
            na[i] = an
            cand_n[i] = int(nc)

        if not np.isfinite(eta).all():
            raise RuntimeError(f"{scene} {pol}: missing/non-finite noise power after strict interpolation")
        if (cand_n > 1).any():
            raise RuntimeError(f"{scene} {pol}: multiple azimuth blocks remain after strict matching")

        raw_dn = x["raw_value"].to_numpy(float)
        raw_power = raw_dn ** 2
        corrected_power = raw_power - eta
        valid = np.isfinite(corrected_power) & (corrected_power > 0)

        sigma_lut = x["sigma_lut"].to_numpy(float)
        beta_lut = x["beta_lut"].to_numpy(float)
        gamma_lut = x["gamma_lut"].to_numpy(float)

        sig_corr = np.full(len(x), np.nan)
        bet_corr = np.full(len(x), np.nan)
        gam_corr = np.full(len(x), np.nan)

        sig_corr[valid] = corrected_power[valid] / sigma_lut[valid]**2
        bet_corr[valid] = corrected_power[valid] / beta_lut[valid]**2
        gam_corr[valid] = corrected_power[valid] / gamma_lut[valid]**2

        sig_db = np.full(len(x), np.nan)
        bet_db = np.full(len(x), np.nan)
        gam_db = np.full(len(x), np.nan)
        sig_db[valid] = 10*np.log10(sig_corr[valid])
        bet_db[valid] = 10*np.log10(bet_corr[valid])
        gam_db[valid] = 10*np.log10(gam_corr[valid])

        x["noise_schema"] = parsed["schema"]
        x["thermalNoiseCorrectionPerformed_input"] = flag
        x["noise_power_eta"] = eta
        x["noise_range_component"] = nr
        x["noise_azimuth_component"] = na
        x["noise_azimuth_candidate_blocks_n"] = cand_n
        x["raw_detected_power"] = raw_power
        x["noise_to_raw_power_ratio"] = np.divide(
            eta, raw_power,
            out=np.full(len(x), np.nan),
            where=(raw_power > 0) & np.isfinite(eta),
        )
        x["corrected_detected_power"] = corrected_power
        x["corrected_power_positive"] = valid
        x["sigma0_noise_corrected_linear"] = sig_corr
        x["sigma0_noise_corrected_db"] = sig_db
        x["beta0_noise_corrected_linear"] = bet_corr
        x["beta0_noise_corrected_db"] = bet_db
        x["gamma0_noise_corrected_linear"] = gam_corr
        x["gamma0_noise_corrected_db"] = gam_db
        x["sigma0_noise_effect_db"] = x["sigma0_noise_corrected_db"] - x["sigma0_db"]
        corrected_parts.append(x)

        qa_rows.append({
            "canonical_scene_id": scene,
            "platform": platform,
            "polarization": pol,
            "noise_schema": parsed["schema"],
            "thermalNoiseCorrectionPerformed_input": flag,
            "noise_xml_href": noise_href,
            "product_xml_href": prod_href,
            "noise_fetch_attempts": noise_attempts,
            "product_fetch_attempts": prod_attempts,
            "noise_xml_bytes_n": len(noise_bytes),
            "legacy_vectors_n": len(parsed["legacy_vectors"]),
            "range_vectors_n": len(parsed["range_vectors"]),
            "azimuth_vectors_n": len(parsed["azimuth_vectors"]),
            "sample_rows_n": int(len(x)),
            "finite_noise_power_n": int(np.isfinite(eta).sum()),
            "missing_noise_power_n": int((~np.isfinite(eta)).sum()),
            "nonpositive_corrected_power_n": int((~valid).sum()),
            "nonpositive_corrected_power_share": float((~valid).mean()),
            "multiple_azimuth_block_matches_n": int((cand_n > 1).sum()),
            "noise_to_raw_power_ratio_median": float(np.nanmedian(x["noise_to_raw_power_ratio"])),
            "noise_to_raw_power_ratio_p99": float(np.nanquantile(x["noise_to_raw_power_ratio"], .99)),
            "sigma0_noise_effect_db_median": float(np.nanmedian(x["sigma0_noise_effect_db"])),
            "status": "PASS",
        })

    corrected = pd.concat(corrected_parts, ignore_index=True)
    qa_df = pd.DataFrame(qa_rows)
    corrected.to_csv(SCENE_OUT, index=False)
    qa_df.to_csv(NOISE_QA_OUT, index=False)

    # Mosaicking is done in corrected LINEAR power.
    coord_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization","lon","lat"
    ]
    mosaic = (
        corrected.groupby(coord_keys, as_index=False)
        .agg(
            point_id=("point_id","first"),
            sigma0_uncorrected_linear=("sigma0_linear","median"),
            sigma0_corrected_linear=("sigma0_noise_corrected_linear","median"),
            contributing_scenes_n=("canonical_scene_id","nunique"),
        )
    )

    mosaic["sigma0_uncorrected_db"] = np.where(
        mosaic["sigma0_uncorrected_linear"] > 0,
        10*np.log10(mosaic["sigma0_uncorrected_linear"]),
        np.nan,
    )
    mosaic["sigma0_corrected_db"] = np.where(
        mosaic["sigma0_corrected_linear"] > 0,
        10*np.log10(mosaic["sigma0_corrected_linear"]),
        np.nan,
    )
    mosaic["noise_effect_db"] = (
        mosaic["sigma0_corrected_db"] - mosaic["sigma0_uncorrected_db"]
    )

    target_keys = [
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "platform","polarization"
    ]
    rows_out = []
    for key, g in mosaic.groupby(target_keys, dropna=False):
        r = dict(zip(target_keys,key))
        r["points_n"] = int(len(g))
        r["corrected_finite_points_n"] = int(np.isfinite(g["sigma0_corrected_db"]).sum())
        r["corrected_finite_share"] = float(np.isfinite(g["sigma0_corrected_db"]).mean())
        r["points_with_multi_scene_overlap_n"] = int((g["contributing_scenes_n"] > 1).sum())
        r.update(finite_summary(g["sigma0_uncorrected_db"], "sigma0_uncorrected_db"))
        r.update(finite_summary(g["sigma0_corrected_db"], "sigma0_corrected_db"))
        r.update(finite_summary(g["noise_effect_db"], "noise_effect_db"))
        rows_out.append(r)

    target = pd.DataFrame(rows_out).sort_values(target_keys)
    target.to_csv(TARGET_OUT, index=False)

    missing_noise = int(qa_df["missing_noise_power_n"].sum())
    multi_az = int(qa_df["multiple_azimuth_block_matches_n"].sum())
    nonpos = int(qa_df["nonpositive_corrected_power_n"].sum())
    nonpos_share = float(nonpos / len(corrected))
    flags = sorted(set(qa_df["thermalNoiseCorrectionPerformed_input"].astype(str)))
    schemas = sorted(set(qa_df["noise_schema"].astype(str)))

    status = (
        "PASS"
        if len(pairs) == 66
        and len(qa_df) == 66
        and len(target) == 36
        and missing_noise == 0
        and multi_az == 0
        and flags == ["false"]
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2OR_POST_RECOVERY_THERMAL_NOISE_REBUILD",
        "historical_c2o_preserved": True,
        "canonical_scene_polarization_assets_n": 68,
        "spatially_contributing_scene_polarization_pairs_n": int(len(pairs)),
        "zero_support_canonical_scene_polarization_assets_n": int(len(zero_support)),
        "zero_support_canonical_scene_polarization_assets": [
            {"canonical_scene_id": s, "polarization": p, "platform": pl}
            for s,p,pl in zero_support
        ],
        "noise_xmls_parsed_n": int(len(qa_df)),
        "schemas_observed": schemas,
        "thermalNoiseCorrectionPerformed_values": flags,
        "scene_point_rows_n": int(len(corrected)),
        "missing_noise_power_n": missing_noise,
        "multiple_azimuth_block_matches_n": multi_az,
        "nonpositive_corrected_power_n": nonpos,
        "nonpositive_corrected_power_share": nonpos_share,
        "target_polarization_summaries_n": int(len(target)),
        "silent_clipping_applied": False,
        "strict_noise_support_checking": True,
        "inundation_threshold_selected": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "preexisting_flood_exposure_values_read": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "next_stage": "Freeze radiometric/noise measurement layer, then proceed to prospective inundation-measurement validation.",
    }
    QA_JSON.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2O-R POST-RECOVERY THERMAL-NOISE REBUILD",
        "=" * 72,
        "",
        "Canonical scene/polarization assets: 68 / 68 accounted",
        f"Spatially contributing scene/pol pairs: {len(pairs)} / 66",
        f"Zero-support canonical assets: {len(zero_support)}",
        f"Noise XMLs parsed: {len(qa_df)} / 66",
        f"Schemas observed: {'|'.join(schemas)}",
        f"Input thermal-noise flags: {'|'.join(flags)}",
        f"Scene-point rows: {len(corrected)}",
        f"Missing noise-power rows: {missing_noise}",
        f"Multiple azimuth-block matches: {multi_az}",
        f"Non-positive corrected-power rows: {nonpos}",
        f"Non-positive corrected-power share: {nonpos_share:.8f}",
        f"Target/polarization summaries: {len(target)} / 36",
        "",
        "METHOD",
        "------",
        "corrected_power = DN^2 - eta",
        "sigma0_corrected = corrected_power / sigmaLUT^2",
        "No silent clipping of non-positive corrected power.",
        "Strict LUT support checking; no silent edge extrapolation.",
        "Overlapping scenes mosaicked using median corrected LINEAR power before dB.",
        "",
        "FIREWALL",
        "--------",
        "Historical C2O outputs preserved.",
        "No inundation threshold selected.",
        "No groundwater values read.",
        "No irrigation-flow values read.",
        "No pre-existing flood/exposure labels read.",
        "No association model fitted.",
        "C2J frozen acquisition universe unchanged.",
        "",
        f"C2O-R STATUS: {status}",
    ]
    txt = "\n".join(lines) + "\n"
    SUMMARY_TXT.write_text(txt, encoding="utf-8")
    print("\n" + txt)

    if status != "PASS":
        raise RuntimeError("C2O-R did not satisfy freeze criteria; inspect outputs.")


if __name__ == "__main__":
    main()

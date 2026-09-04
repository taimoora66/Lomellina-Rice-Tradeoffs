"""Design C — C2O Sentinel-1 Thermal Noise Audit and Correction.

PURPOSE
-------
Apply scene-specific Sentinel-1 GRD thermal-noise correction to the frozen
C2N scene-point samples, while preserving the scientific firewall.

Historical schemas supported
----------------------------
Legacy (e.g. 2015):
    noiseVectorList / noiseVector / noiseLut

Modern (e.g. 2020, 2025):
    noiseRangeVectorList / noiseRangeLut
    noiseAzimuthVectorList / noiseAzimuthLut

For modern products:
    eta(row, col) = interpolated_noiseRangeLut(row, col)
                    * applicable_interpolated_noiseAzimuthLut(row)

For legacy products:
    eta(row, col) = interpolated_noiseLut(row, col)

Because thermalNoiseCorrectionPerformed=false in the frozen products,
noise is removed in detected power before calibration:

    corrected_power = DN^2 - eta

    sigma0_corrected = corrected_power / sigmaLUT^2

Analogous beta0 and gamma0 values are also computed.

IMPORTANT
---------
This stage DOES NOT silently clip non-positive corrected power. Such samples
are retained with an explicit flag and calibrated corrected values are NaN.
Their frequency is part of the audit.

NO inundation threshold is selected.
NO groundwater values are read.
NO irrigation-flow values are read.
NO pre-existing flood/exposure labels are read.
NO association model is fitted.
C2J frozen acquisition universe is unchanged.

INPUTS
------
outputs/diagnostics/design_c/c2n_scene_point_calibrated_samples.csv
outputs/diagnostics/design_c/c2kr_validation_asset_inventory_complete.csv

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2o_noise_xml_qa.csv
    c2o_scene_point_noise_corrected_samples.csv
    c2o_target_polarization_noise_effect_summary.csv
    c2o_thermal_noise_qa.json
    c2o_thermal_noise_summary.txt

RUN
---
python -u scripts/06_design_c/21_audit_sentinel1_thermal_noise.py
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import boto3
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

C2N = OUT / "c2n_scene_point_calibrated_samples.csv"
ASSETS = OUT / "c2kr_validation_asset_inventory_complete.csv"

S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"


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


def fetch_bytes(s3, href):
    bucket, key = parse_s3_href(href)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def lname(tag):
    return tag.rsplit("}", 1)[-1]


def children(el, name):
    return [c for c in list(el) if lname(c.tag) == name]


def first(root, name):
    for e in root.iter():
        if lname(e.tag) == name:
            return e
    return None


def child_text(el, name, required=True):
    for c in list(el):
        if lname(c.tag) == name:
            if c.text is not None:
                return c.text.strip()
    if required:
        raise ValueError(f"Missing XML child: {name}")
    return None


def arr_float(text):
    return np.asarray([float(x) for x in text.split()], dtype=float)


def arr_int(text):
    return np.asarray([int(x) for x in text.split()], dtype=int)


def interp1(px, vals, x):
    px = np.asarray(px, dtype=float)
    vals = np.asarray(vals, dtype=float)
    return float(np.interp(float(x), px, vals))


def parse_product_noise_flag(xml_bytes):
    root = ET.fromstring(xml_bytes)
    e = first(root, "thermalNoiseCorrectionPerformed")
    if e is None or e.text is None:
        return None
    return e.text.strip().lower()


def parse_noise_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)

    legacy_list = first(root, "noiseVectorList")
    modern_range_list = first(root, "noiseRangeVectorList")
    modern_az_list = first(root, "noiseAzimuthVectorList")

    if legacy_list is not None:
        vecs = []
        for v in list(legacy_list):
            if lname(v.tag) != "noiseVector":
                continue
            line = int(child_text(v, "line"))
            pixel = arr_int(child_text(v, "pixel"))
            noise = arr_float(child_text(v, "noiseLut"))
            if len(pixel) != len(noise):
                raise ValueError(
                    f"Legacy noise LUT length mismatch at line {line}"
                )
            vecs.append({
                "line": line,
                "pixel": pixel,
                "noise": noise,
            })
        if not vecs:
            raise ValueError("Legacy schema found but no noiseVector parsed")
        return {
            "schema": "legacy_noiseVectorList",
            "legacy_vectors": sorted(vecs, key=lambda z: z["line"]),
            "range_vectors": [],
            "azimuth_vectors": [],
        }

    if modern_range_list is not None:
        rvecs = []
        for v in list(modern_range_list):
            if lname(v.tag) != "noiseRangeVector":
                continue
            line = int(child_text(v, "line"))
            pixel = arr_int(child_text(v, "pixel"))
            lut = arr_float(child_text(v, "noiseRangeLut"))
            if len(pixel) != len(lut):
                raise ValueError(
                    f"Modern range LUT length mismatch at line {line}"
                )
            rvecs.append({
                "line": line,
                "pixel": pixel,
                "noise": lut,
            })

        avecs = []
        if modern_az_list is not None:
            for v in list(modern_az_list):
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

                avecs.append({
                    "swath": swath,
                    "firstAzimuthLine": int(fal) if fal is not None else None,
                    "lastAzimuthLine": int(lal) if lal is not None else None,
                    "firstRangeSample": int(frs) if frs is not None else None,
                    "lastRangeSample": int(lrs) if lrs is not None else None,
                    "line": lines,
                    "noise": lut,
                })

        if not rvecs:
            raise ValueError(
                "Modern schema found but no noiseRangeVector parsed"
            )

        return {
            "schema": "modern_range_x_azimuth",
            "legacy_vectors": [],
            "range_vectors": sorted(rvecs, key=lambda z: z["line"]),
            "azimuth_vectors": avecs,
        }

    raise ValueError("Unrecognized Sentinel-1 noise XML schema")


def interp_2d_line_pixel(vectors, row, col):
    lines = np.asarray([v["line"] for v in vectors], dtype=float)
    r = float(row)

    if r <= lines[0]:
        return interp1(vectors[0]["pixel"], vectors[0]["noise"], col)

    if r >= lines[-1]:
        return interp1(vectors[-1]["pixel"], vectors[-1]["noise"], col)

    hi = int(np.searchsorted(lines, r, side="right"))
    lo = hi - 1

    v0 = vectors[lo]
    v1 = vectors[hi]
    n0 = interp1(v0["pixel"], v0["noise"], col)
    n1 = interp1(v1["pixel"], v1["noise"], col)

    l0 = float(v0["line"])
    l1 = float(v1["line"])
    if l1 == l0:
        return n0

    w = (r - l0) / (l1 - l0)
    return float(n0 + w * (n1 - n0))


def applicable_azimuth_vectors(azvecs, row, col):
    out = []
    for v in azvecs:
        fal = v["firstAzimuthLine"]
        lal = v["lastAzimuthLine"]
        frs = v["firstRangeSample"]
        lrs = v["lastRangeSample"]

        row_ok = (
            (fal is None or row >= fal)
            and (lal is None or row <= lal)
        )
        col_ok = (
            (frs is None or col >= frs)
            and (lrs is None or col <= lrs)
        )

        if row_ok and col_ok:
            out.append(v)
    return out


def modern_azimuth_factor(azvecs, row, col):
    if not azvecs:
        # Some modern XMLs may omit azimuth correction.
        return 1.0, 0

    candidates = applicable_azimuth_vectors(azvecs, row, col)

    if not candidates:
        return np.nan, 0

    vals = []
    for v in candidates:
        vals.append(interp1(v["line"], v["noise"], row))

    # If boundaries overlap, median avoids arbitrary selection and is recorded.
    return float(np.median(vals)), len(candidates)


def noise_power_at(parsed, row, col):
    if parsed["schema"] == "legacy_noiseVectorList":
        eta = interp_2d_line_pixel(
            parsed["legacy_vectors"], row, col
        )
        return eta, np.nan, np.nan, 1

    nr = interp_2d_line_pixel(
        parsed["range_vectors"], row, col
    )
    na, n_candidates = modern_azimuth_factor(
        parsed["azimuth_vectors"], row, col
    )

    if not np.isfinite(na):
        return np.nan, nr, na, n_candidates

    return nr * na, nr, na, n_candidates


def summarize(x):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return {
            "n": 0, "min": None, "p01": None, "p10": None,
            "median": None, "mean": None, "p90": None,
            "p99": None, "max": None,
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
    }


def main():
    print("DESIGN C - C2O SENTINEL-1 THERMAL NOISE AUDIT/CORRECTION")
    print("=" * 72)
    print("Uses frozen C2N scene-point samples.")
    print("Supports legacy and modern Sentinel-1 noise XML schemas.")
    print("Non-positive corrected power is FLAGGED, not silently clipped.")
    print("NO inundation threshold is selected.")
    print("NO groundwater or irrigation outcomes are read.")
    print("NO association model is fitted.")
    print("C2J frozen acquisition universe unchanged.\n")

    require_credentials()

    if not C2N.exists():
        raise FileNotFoundError(C2N)
    if not ASSETS.exists():
        raise FileNotFoundError(ASSETS)

    s = pd.read_csv(C2N)
    a = pd.read_csv(ASSETS)

    asset_lookup = {
        (str(r["scene_id"]), str(r["asset_key"])): str(r["href"])
        for _, r in a.iterrows()
    }

    pairs = (
        s[["canonical_scene_id", "polarization", "platform"]]
        .drop_duplicates()
        .sort_values(["canonical_scene_id", "polarization"])
    )

    s3 = make_s3()
    corrected_parts = []
    qa_rows = []

    for j, r in enumerate(pairs.itertuples(index=False), 1):
        scene = str(r.canonical_scene_id)
        pol = str(r.polarization).upper()
        platform = str(r.platform)

        print(f"[{j:02d}/{len(pairs):02d}] {scene} {pol}")

        noise_key = f"schema-noise-{pol.lower()}"
        prod_key = f"schema-product-{pol.lower()}"

        noise_href = asset_lookup.get((scene, noise_key))
        prod_href = asset_lookup.get((scene, prod_key))

        if not noise_href:
            raise RuntimeError(
                f"Missing {noise_key} for {scene}"
            )
        if not prod_href:
            raise RuntimeError(
                f"Missing {prod_key} for {scene}"
            )

        noise_bytes = fetch_bytes(s3, noise_href)
        prod_bytes = fetch_bytes(s3, prod_href)

        flag = parse_product_noise_flag(prod_bytes)
        if flag != "false":
            raise RuntimeError(
                f"{scene} {pol}: expected thermalNoiseCorrectionPerformed=false, "
                f"got {flag!r}"
            )

        parsed = parse_noise_xml(noise_bytes)

        x = s[
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
            e, rnoise, anoise, nc = noise_power_at(
                parsed, int(rr), int(cc)
            )
            eta[i] = e
            nr[i] = rnoise
            na[i] = anoise
            cand_n[i] = int(nc)

        raw_dn = x["raw_value"].to_numpy(float)
        raw_power = raw_dn ** 2
        corrected_power = raw_power - eta

        valid = (
            np.isfinite(corrected_power)
            & (corrected_power > 0)
        )

        sigma_lut = x["sigma_lut"].to_numpy(float)
        beta_lut = x["beta_lut"].to_numpy(float)
        gamma_lut = x["gamma_lut"].to_numpy(float)

        sig_corr = np.full(len(x), np.nan, dtype=float)
        bet_corr = np.full(len(x), np.nan, dtype=float)
        gam_corr = np.full(len(x), np.nan, dtype=float)

        sig_corr[valid] = (
            corrected_power[valid] / sigma_lut[valid] ** 2
        )
        bet_corr[valid] = (
            corrected_power[valid] / beta_lut[valid] ** 2
        )
        gam_corr[valid] = (
            corrected_power[valid] / gamma_lut[valid] ** 2
        )

        sig_db = np.full(len(x), np.nan, dtype=float)
        bet_db = np.full(len(x), np.nan, dtype=float)
        gam_db = np.full(len(x), np.nan, dtype=float)

        sig_db[valid] = 10.0 * np.log10(sig_corr[valid])
        bet_db[valid] = 10.0 * np.log10(bet_corr[valid])
        gam_db[valid] = 10.0 * np.log10(gam_corr[valid])

        x["noise_schema"] = parsed["schema"]
        x["thermalNoiseCorrectionPerformed_input"] = flag
        x["noise_power_eta"] = eta
        x["noise_range_component"] = nr
        x["noise_azimuth_component"] = na
        x["noise_azimuth_candidate_blocks_n"] = cand_n
        x["raw_detected_power"] = raw_power
        x["noise_to_raw_power_ratio"] = np.divide(
            eta,
            raw_power,
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
        x["sigma0_noise_effect_db"] = (
            x["sigma0_noise_corrected_db"]
            - x["sigma0_db"]
        )

        corrected_parts.append(x)

        qa_rows.append({
            "canonical_scene_id": scene,
            "platform": platform,
            "polarization": pol,
            "noise_schema": parsed["schema"],
            "thermalNoiseCorrectionPerformed_input": flag,
            "noise_xml_bytes_n": len(noise_bytes),
            "legacy_vectors_n": len(parsed["legacy_vectors"]),
            "range_vectors_n": len(parsed["range_vectors"]),
            "azimuth_vectors_n": len(parsed["azimuth_vectors"]),
            "sample_rows_n": int(len(x)),
            "finite_noise_power_n": int(np.isfinite(eta).sum()),
            "missing_noise_power_n": int((~np.isfinite(eta)).sum()),
            "nonpositive_corrected_power_n": int((~valid).sum()),
            "nonpositive_corrected_power_share": float(
                (~valid).mean()
            ),
            "multiple_azimuth_block_matches_n": int(
                (cand_n > 1).sum()
            ),
            "noise_to_raw_power_ratio_median": float(
                np.nanmedian(x["noise_to_raw_power_ratio"])
            ),
            "noise_to_raw_power_ratio_p99": float(
                np.nanquantile(
                    x["noise_to_raw_power_ratio"], .99
                )
            ),
            "sigma0_noise_effect_db_median": float(
                np.nanmedian(x["sigma0_noise_effect_db"])
            ),
            "status": (
                "PASS"
                if np.isfinite(eta).all()
                else "PASS_WITH_LIMITATIONS"
            ),
        })

    c = pd.concat(corrected_parts, ignore_index=True)
    qa_df = pd.DataFrame(qa_rows)

    c.to_csv(
        OUT / "c2o_scene_point_noise_corrected_samples.csv",
        index=False,
    )
    qa_df.to_csv(
        OUT / "c2o_noise_xml_qa.csv",
        index=False,
    )

    # Target/polarization/point mosaic AFTER scene-specific correction.
    point_keys = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform",
        "polarization", "point_id", "lon", "lat"
    ]

    mosaic = (
        c.groupby(point_keys, as_index=False)
        .agg(
            sigma0_uncorrected_linear=("sigma0_linear", "median"),
            sigma0_corrected_linear=(
                "sigma0_noise_corrected_linear", "median"
            ),
            contributing_scenes_n=("canonical_scene_id", "nunique"),
            contributing_valid_corrected_scenes_n=(
                "sigma0_noise_corrected_linear",
                lambda z: int(np.isfinite(z).sum())
            ),
        )
    )

    mosaic["sigma0_uncorrected_db"] = np.where(
        mosaic["sigma0_uncorrected_linear"] > 0,
        10.0 * np.log10(mosaic["sigma0_uncorrected_linear"]),
        np.nan,
    )
    mosaic["sigma0_corrected_db"] = np.where(
        mosaic["sigma0_corrected_linear"] > 0,
        10.0 * np.log10(mosaic["sigma0_corrected_linear"]),
        np.nan,
    )
    mosaic["noise_effect_db"] = (
        mosaic["sigma0_corrected_db"]
        - mosaic["sigma0_uncorrected_db"]
    )

    gcols = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform", "polarization"
    ]

    sum_rows = []
    for key, g in mosaic.groupby(gcols):
        rec = dict(zip(gcols, key))
        rec["points_n"] = int(g["point_id"].nunique())
        rec["corrected_finite_points_n"] = int(
            np.isfinite(g["sigma0_corrected_db"]).sum()
        )
        rec["corrected_finite_share"] = float(
            np.isfinite(g["sigma0_corrected_db"]).mean()
        )

        for field in [
            "sigma0_uncorrected_db",
            "sigma0_corrected_db",
            "noise_effect_db",
        ]:
            stats = summarize(g[field])
            for k, v in stats.items():
                rec[f"{field}_{k}"] = v

        sum_rows.append(rec)

    summary = pd.DataFrame(sum_rows)
    summary.to_csv(
        OUT / "c2o_target_polarization_noise_effect_summary.csv",
        index=False,
    )

    schemas = sorted(qa_df["noise_schema"].unique())
    flags = sorted(
        qa_df["thermalNoiseCorrectionPerformed_input"].unique()
    )

    total_nonpositive = int(
        (~c["corrected_power_positive"]).sum()
    )
    total_rows = int(len(c))
    overall_nonpositive_share = float(
        total_nonpositive / total_rows
    )

    status = (
        "PASS"
        if qa_df["status"].eq("PASS").all()
        and flags == ["false"]
        else "PASS_WITH_LIMITATIONS"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2O_SENTINEL1_THERMAL_NOISE_AUDIT_CORRECTION",
        "scene_polarization_pairs_n": int(len(pairs)),
        "noise_xmls_parsed_n": int(len(qa_df)),
        "schemas_observed": schemas,
        "thermalNoiseCorrectionPerformed_values": flags,
        "scene_point_rows_n": total_rows,
        "nonpositive_corrected_power_n": total_nonpositive,
        "nonpositive_corrected_power_share": overall_nonpositive_share,
        "target_polarization_summaries_n": int(len(summary)),
        "silent_clipping_applied": False,
        "inundation_threshold_selected": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "preexisting_flood_exposure_values_read": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "decision_rule": (
            "C2O is measurement QA only. Magnitude of noise correction "
            "and non-positive power frequency are reported before any "
            "inundation metric is frozen."
        ),
    }

    (OUT / "c2o_thermal_noise_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    display_cols = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit", "platform",
        "polarization", "points_n", "corrected_finite_share",
        "sigma0_uncorrected_db_median",
        "sigma0_corrected_db_median",
        "noise_effect_db_median",
        "noise_effect_db_p10",
        "noise_effect_db_p90",
    ]

    lines = [
        "DESIGN C - C2O SENTINEL-1 THERMAL NOISE AUDIT/CORRECTION",
        "=" * 70,
        "",
        f"Scene/polarization pairs: {len(pairs)}",
        f"Noise XMLs parsed: {len(qa_df)}",
        f"Schemas observed: {'|'.join(schemas)}",
        f"Input thermal-noise flags: {'|'.join(flags)}",
        f"Scene-point rows: {total_rows}",
        f"Non-positive corrected-power rows: {total_nonpositive}",
        (
            "Non-positive corrected-power share: "
            f"{overall_nonpositive_share:.8f}"
        ),
        f"Target/polarization summaries: {len(summary)}",
        "",
        "TARGET / POLARIZATION NOISE EFFECT",
        "----------------------------------",
        summary[display_cols].to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "No silent clipping of non-positive corrected power.",
        "No inundation threshold selected.",
        "No groundwater values read.",
        "No irrigation-flow values read.",
        "No pre-existing flood/exposure labels read.",
        "No association model fitted.",
        "C2J frozen acquisition universe unchanged.",
        "",
        f"C2O STATUS: {status}",
    ]

    txt = "\n".join(lines) + "\n"
    (OUT / "c2o_thermal_noise_summary.txt").write_text(
        txt, encoding="utf-8"
    )

    print("\n" + txt)


if __name__ == "__main__":
    main()

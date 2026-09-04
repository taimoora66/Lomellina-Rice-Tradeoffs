"""Design C — C2U-S Sentinel-1 technical-exception rescue coverage audit.

Purpose
-------
Before finalizing C2U technical exclusions, test whether:
1) the same-date 2025-04-21 IW VV/VH scene on descending track 66 covers the
   RiceFloodIT support and can objectively rescue that primary acquisition date;
2) the 2016 IW HH/HV exception acquisitions cover the RiceFloodIT support well
   enough to retain as a separate auxiliary polarization stream.

This is an outcome-blind TECHNICAL COVERAGE audit.

No SAR pixel values are read.
No groundwater, irrigation-flow, RiceFloodIT flooding values, thresholds,
classifiers, or sensor-response optimization are used.

Coverage is determined only by mapping the 4,331 fixed RiceFloodIT support
coordinates through each Sentinel-1 raster's embedded GCP geolocation and
checking whether the mapped row/column lies inside the raster dimensions.

Outputs
-------
outputs/diagnostics/design_c/
  c2us_exception_rescue_scene_coverage.csv
  c2us_exception_rescue_date_coverage.csv
  c2us_exception_rescue_decision.csv
  c2us_exception_rescue_qa.json
  c2us_exception_rescue_summary.txt
  c2us_item_cache/*.json

Run
---
python -u scripts/06_design_c/35_audit_s1_exception_rescue_coverage.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import GCPTransformer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

RICE_GEO = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "ricefloodit_georef.csv"
)
C2URR_EXCLUSIONS = OUT / "c2urr_technical_measurement_exclusions.csv"

ITEM_CACHE = OUT / "c2us_item_cache"
ITEM_CACHE.mkdir(parents=True, exist_ok=True)

SCENE_OUT = OUT / "c2us_exception_rescue_scene_coverage.csv"
DATE_OUT = OUT / "c2us_exception_rescue_date_coverage.csv"
DECISION_OUT = OUT / "c2us_exception_rescue_decision.csv"
QA_OUT = OUT / "c2us_exception_rescue_qa.json"
TXT_OUT = OUT / "c2us_exception_rescue_summary.txt"

STAC_ROOT = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-1-grd"

RASTER_ENV = {
    "AWS_S3_ENDPOINT": "eodata.dataspace.copernicus.eu",
    "AWS_VIRTUAL_HOSTING": "FALSE",
    "AWS_DEFAULT_REGION": "default",
}

MAX_ATTEMPTS = 8
BASE_DELAY_S = 5.0
MAX_BACKOFF_S = 120.0

# Objective rescue candidate found by the metadata-only ±3 day audit:
RESCUE_2025 = (
    "S1C_IW_GRDH_1SDV_20250421T053447_"
    "20250421T053516_001987_003FE6_9043_COG"
)


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


def item_url(scene_id: str) -> str:
    return (
        f"{STAC_ROOT}/collections/{COLLECTION}/items/"
        + quote(scene_id, safe="")
    )


def cache_path(scene_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", scene_id)
    return ITEM_CACHE / f"{safe}.json"


def fetch_item(scene_id: str):
    cp = cache_path(scene_id)
    if cp.exists():
        try:
            item = json.loads(cp.read_text(encoding="utf-8"))
            if str(item.get("id")) == scene_id:
                return item, "CACHE", 0
        except Exception:
            pass

    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = Request(
                item_url(scene_id),
                headers={
                    "User-Agent":
                    "DesignC-C2US-s1-exception-rescue-coverage/1.0"
                },
            )
            with urlopen(req, timeout=120) as r:
                item = json.loads(r.read())

            if str(item.get("id")) != scene_id:
                raise RuntimeError("STAC item id mismatch")

            tmp = cp.with_suffix(".tmp")
            tmp.write_text(json.dumps(item), encoding="utf-8")
            tmp.replace(cp)
            return item, "REMOTE", attempt

        except HTTPError as e:
            last = repr(e)
            if attempt < MAX_ATTEMPTS:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    delay = float(retry_after)
                except Exception:
                    delay = min(
                        BASE_DELAY_S * (2 ** (attempt - 1)),
                        MAX_BACKOFF_S,
                    )
                delay = max(BASE_DELAY_S, min(delay, MAX_BACKOFF_S))
                print(
                    f"    STAC attempt {attempt} failed ({e.code}); "
                    f"retrying in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)
        except Exception as e:
            last = repr(e)
            if attempt < MAX_ATTEMPTS:
                delay = min(BASE_DELAY_S * attempt, MAX_BACKOFF_S)
                print(
                    f"    STAC attempt {attempt} failed: {last}; "
                    f"retrying in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Failed STAC item resolution for {scene_id}: {last}"
    )


def choose_pol_asset(item, preferred_pols):
    assets = item.get("assets", {}) or []
    if not isinstance(assets, dict):
        raise RuntimeError("STAC assets are not a dictionary")

    rows = []
    for key, a in assets.items():
        href = a.get("href")
        roles = a.get("roles", []) or []
        title = a.get("title") or ""
        text = f"{key} {title} {href or ''}".lower()

        pol = None
        for candidate in ["VV", "VH", "HH", "HV"]:
            c = candidate.lower()
            if re.search(
                rf"(^|[^a-z0-9]){c}([^a-z0-9]|$)", text
            ):
                if pol is not None and pol != candidate:
                    pol = None
                    break
                pol = candidate

        if pol is None:
            continue

        rows.append({
            "asset_key": key,
            "href": href,
            "roles": roles,
            "pol": pol,
            "is_data": "data" in roles,
            "is_tiff": bool(
                href and str(href).lower().split("?")[0].endswith(
                    (".tif", ".tiff")
                )
            ),
        })

    df = pd.DataFrame(rows)
    for pol in preferred_pols:
        q = df[df["pol"].eq(pol)].copy()
        if q.empty:
            continue
        q = q.sort_values(
            ["is_data", "is_tiff", "asset_key", "href"],
            ascending=[False, False, True, True],
        )
        r = q.iloc[0]
        return str(r["asset_key"]), str(r["href"]), pol

    raise RuntimeError(
        f"No usable raster asset found for preferred polarizations "
        f"{preferred_pols}"
    )


def map_support_to_raster(href, lon, lat):
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with rasterio.Env(**RASTER_ENV):
                with rasterio.open(href) as ds:
                    gcps, gcp_crs = ds.gcps
                    if not gcps or gcp_crs is None:
                        raise RuntimeError("Missing embedded GCP geolocation")

                    tr = Transformer.from_crs(
                        "EPSG:4326", gcp_crs, always_xy=True
                    )
                    x, y = tr.transform(lon, lat)

                    with GCPTransformer(gcps) as gt:
                        rows, cols = gt.rowcol(x, y)

                    rows = np.asarray(rows, dtype=np.int64)
                    cols = np.asarray(cols, dtype=np.int64)
                    inside = (
                        (rows >= 0) & (rows < ds.height)
                        & (cols >= 0) & (cols < ds.width)
                    )

                    return {
                        "inside": inside,
                        "width": int(ds.width),
                        "height": int(ds.height),
                        "gcp_count": int(len(gcps)),
                        "gcp_crs": str(gcp_crs),
                        "driver": str(ds.driver),
                        "dtype": str(ds.dtypes[0]),
                        "attempts": attempt,
                    }

        except Exception as e:
            last = repr(e)
            if attempt < MAX_ATTEMPTS:
                delay = min(BASE_DELAY_S * attempt, MAX_BACKOFF_S)
                print(
                    f"    raster metadata attempt {attempt} failed: {last}; "
                    f"retrying in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Raster metadata/GCP access failed after {MAX_ATTEMPTS} attempts: "
        f"{href}\n{last}"
    )


def main():
    print("DESIGN C - C2U-S SENTINEL-1 EXCEPTION RESCUE COVERAGE AUDIT")
    print("=" * 78)
    print("No SAR pixel values read.")
    print("No groundwater / irrigation flow / flood outcomes read.")
    print("Coverage only from raster dimensions + embedded GCPs.\n")

    require_credentials()

    if not C2URR_EXCLUSIONS.exists():
        raise FileNotFoundError(C2URR_EXCLUSIONS)
    if not RICE_GEO.exists():
        raise FileNotFoundError(RICE_GEO)

    bad = pd.read_csv(C2URR_EXCLUSIONS)
    geo = pd.read_csv(RICE_GEO, low_memory=False)

    geo["lon"] = pd.to_numeric(geo["lon"], errors="coerce")
    geo["lat"] = pd.to_numeric(geo["lat"], errors="coerce")
    points = (
        geo.dropna(subset=["lon", "lat"])[["lon", "lat"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    if len(points) != 4331:
        raise AssertionError(
            f"Expected 4331 RiceFloodIT support coordinates, got {len(points)}"
        )

    lon = points["lon"].to_numpy(float)
    lat = points["lat"].to_numpy(float)

    bad_ids = bad["scene_id"].astype(str).tolist()
    target_ids = bad_ids + [RESCUE_2025]

    # Group labels are acquisition-level, not row-level.
    labels = {}
    for sid in bad_ids:
        if "20160703" in sid:
            labels[sid] = "2016-07-03_ASC15_HHHV"
        elif "20160820" in sid:
            labels[sid] = "2016-08-20_ASC15_HHHV"
        elif "20250421" in sid:
            labels[sid] = "2025-04-21_DESC66_EW_HHHV"
        else:
            labels[sid] = "OTHER_EXCEPTION"

    labels[RESCUE_2025] = "2025-04-21_DESC66_IW_VVVH_RESCUE"

    scene_rows = []
    masks = {}

    for i, sid in enumerate(target_ids, 1):
        print(f"[{i}/{len(target_ids)}] {sid}", flush=True)
        item, source, stac_attempts = fetch_item(sid)
        p = item.get("properties", {}) or {}

        pols = [
            str(x).upper()
            for x in (p.get("sar:polarizations", []) or [])
        ]
        mode = str(p.get("sar:instrument_mode") or "")

        if sid == RESCUE_2025:
            preferred = ["VV", "VH"]
        else:
            preferred = ["HH", "HV"]

        asset_key, href, selected_pol = choose_pol_asset(
            item, preferred
        )

        print(
            f"    mode={mode}; pols={'|'.join(pols)}; "
            f"coverage asset={asset_key}",
            flush=True,
        )

        m = map_support_to_raster(href, lon, lat)
        inside = m.pop("inside")
        masks[sid] = inside

        n = int(inside.sum())
        scene_rows.append({
            "scene_id": sid,
            "acquisition_group": labels[sid],
            "datetime": p.get("datetime") or p.get("start_datetime"),
            "platform": p.get("platform") or p.get("constellation"),
            "instrument_mode": mode,
            "polarizations": "|".join(pols),
            "orbit_state": p.get("sat:orbit_state"),
            "relative_orbit": p.get("sat:relative_orbit"),
            "selected_coverage_polarization": selected_pol,
            "selected_asset_key": asset_key,
            "selected_href": href,
            "stac_source": source,
            "stac_attempts": stac_attempts,
            **m,
            "support_points_total_n": int(len(points)),
            "support_points_inside_n": n,
            "support_coverage_fraction": float(n / len(points)),
            "sar_pixel_values_read": False,
        })

    scene_df = pd.DataFrame(scene_rows)
    scene_df.to_csv(SCENE_OUT, index=False)

    # Acquisition/date-level union coverage.
    groups = {
        "2016-07-03_ASC15_HHHV": [
            x for x in bad_ids if "20160703" in x
        ],
        "2016-08-20_ASC15_HHHV": [
            x for x in bad_ids if "20160820" in x
        ],
        "2025-04-21_DESC66_EW_HHHV": [
            x for x in bad_ids if "20250421" in x
        ],
        "2025-04-21_DESC66_IW_VVVH_RESCUE": [RESCUE_2025],
    }

    date_rows = []
    group_masks = {}

    for name, ids in groups.items():
        if not ids:
            continue
        union = np.zeros(len(points), dtype=bool)
        for sid in ids:
            union |= masks[sid]
        group_masks[name] = union
        date_rows.append({
            "acquisition_group": name,
            "scene_rows_n": len(ids),
            "support_points_total_n": len(points),
            "support_points_inside_union_n": int(union.sum()),
            "support_coverage_union_fraction":
                float(union.mean()),
        })

    date_df = pd.DataFrame(date_rows)
    date_df.to_csv(DATE_OUT, index=False)

    # Direct same-date 2025 rescue comparison.
    ew = group_masks["2025-04-21_DESC66_EW_HHHV"]
    iw = group_masks["2025-04-21_DESC66_IW_VVVH_RESCUE"]

    ew_n = int(ew.sum())
    iw_n = int(iw.sum())
    overlap_n = int((ew & iw).sum())
    ew_covered_by_iw_share = (
        float(overlap_n / ew_n) if ew_n else np.nan
    )
    iw_covered_by_ew_share = (
        float(overlap_n / iw_n) if iw_n else np.nan
    )

    # Decision rules are purely technical, fixed before response/outcome data:
    # Primary rescue: same date + same track + IW VV/VH and >=99% support coverage.
    # Auxiliary retain: IW HH/HV acquisition with >=99% union support coverage.
    iw_frac = float(iw.mean())
    h1 = float(group_masks["2016-07-03_ASC15_HHHV"].mean())
    h2 = float(group_masks["2016-08-20_ASC15_HHHV"].mean())

    decisions = [
        {
            "acquisition_group": "2025-04-21_DESC66_EW_HHHV",
            "decision": (
                "RESCUED_PRIMARY_VVVH"
                if iw_frac >= 0.99
                else "PRIMARY_RESCUE_COVERAGE_INSUFFICIENT"
            ),
            "basis": (
                "Same-date, same-track IW VV/VH candidate; "
                "technical GCP support coverage only."
            ),
            "replacement_scene_id": RESCUE_2025,
            "support_coverage_fraction_used": iw_frac,
        },
        {
            "acquisition_group": "2016-07-03_ASC15_HHHV",
            "decision": (
                "AUXILIARY_HHHV"
                if h1 >= 0.99
                else "AUXILIARY_HHHV_PARTIAL_COVERAGE"
            ),
            "basis": (
                "No ±3-day same-track VV/VH replacement found; "
                "retain separately from VV/VH if technical coverage supports it."
            ),
            "replacement_scene_id": None,
            "support_coverage_fraction_used": h1,
        },
        {
            "acquisition_group": "2016-08-20_ASC15_HHHV",
            "decision": (
                "AUXILIARY_HHHV"
                if h2 >= 0.99
                else "AUXILIARY_HHHV_PARTIAL_COVERAGE"
            ),
            "basis": (
                "No ±3-day same-track VV/VH replacement found; adjacent HH/HV "
                "frames treated as one acquisition mosaic."
            ),
            "replacement_scene_id": None,
            "support_coverage_fraction_used": h2,
        },
    ]
    decision_df = pd.DataFrame(decisions)
    decision_df.to_csv(DECISION_OUT, index=False)

    status = (
        "PASS"
        if len(scene_df) == 6
        and len(points) == 4331
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2US_SENTINEL1_EXCEPTION_RESCUE_COVERAGE_AUDIT",
        "rice_support_coordinates_n": int(len(points)),
        "exception_scene_rows_n": int(len(bad_ids)),
        "rescue_candidate_scene_rows_n": 1,
        "scene_coverage_rows_n": int(len(scene_df)),
        "date_acquisition_groups_n": int(len(date_df)),
        "same_date_2025_iw_vvvh_support_coverage_fraction": iw_frac,
        "same_date_2025_ew_hhhv_support_coverage_fraction":
            float(ew.mean()),
        "same_date_2025_support_overlap_n": overlap_n,
        "ew_support_covered_by_iw_share": ew_covered_by_iw_share,
        "iw_support_covered_by_ew_share": iw_covered_by_ew_share,
        "2016_07_03_hhhv_union_support_coverage_fraction": h1,
        "2016_08_20_hhhv_union_support_coverage_fraction": h2,
        "primary_rescue_threshold": 0.99,
        "auxiliary_retain_threshold": 0.99,
        "threshold_type":
            "technical spatial-support coverage, not sensor-response threshold",
        "sar_pixel_values_read": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "ricefloodit_flood_values_read": False,
        "inundation_threshold_selected": False,
        "classifier_fitted": False,
        "sensor_response_values_used_for_decision": False,
        "c2t_temporal_rule_modified": False,
    }
    QA_OUT.write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )

    txt = "\n".join([
        "DESIGN C - C2U-S SENTINEL-1 EXCEPTION RESCUE COVERAGE AUDIT",
        "=" * 78,
        "",
        f"Rice support coordinates: {len(points)}",
        f"Exception scene rows audited: {len(bad_ids)}",
        f"Additional same-date 2025 IW VV/VH rescue candidate: {RESCUE_2025}",
        "",
        "ACQUISITION-LEVEL COVERAGE",
        "--------------------------",
        date_df.to_string(index=False),
        "",
        "2025 SAME-DATE RESCUE COMPARISON",
        "--------------------------------",
        f"EW HH/HV support coverage: {float(ew.mean()):.6f}",
        f"IW VV/VH support coverage: {iw_frac:.6f}",
        f"Support points covered by both: {overlap_n}",
        f"EW-covered support also covered by IW: {ew_covered_by_iw_share:.6f}",
        f"IW-covered support also covered by EW: {iw_covered_by_ew_share:.6f}",
        "",
        "PRE-OUTCOME TECHNICAL DECISIONS",
        "-------------------------------",
        decision_df.to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "SAR pixel values read: False",
        "Groundwater read: False",
        "Irrigation flow read: False",
        "RiceFloodIT flood values read: False",
        "Sensor response used for decision: False",
        "C2T temporal rule modified: False",
        "",
        f"C2U-S STATUS: {status}",
    ]) + "\n"

    TXT_OUT.write_text(txt, encoding="utf-8")
    print("\n" + txt)

    if status != "PASS":
        raise RuntimeError("C2U-S failed; inspect outputs.")


if __name__ == "__main__":
    main()

"""Design C — C2P-B Sentinel-2 SCL rice-support usability audit.

Purpose
-------
Measure ACTUAL optical usability over the 4,331 RiceFloodIT support locations
for the 14 Sentinel-1 anchor targets that are genuinely matchable to
Sentinel-2 L2A within +/-1 day.

This stage samples the native 20 m Sentinel-2 Scene Classification Layer (SCL)
from every relevant Sentinel-2 tile on the selected optical date, mosaics
overlapping tile observations by support coordinate, and reports actual
cloud/shadow/cirrus/snow/no-data coverage.

It does NOT:
- use catalogue eo:cloud_cover as the final usability measure;
- read groundwater values;
- read irrigation-flow values;
- read historical/post-2021 flooding/exposure outcomes;
- select or train an inundation classifier;
- derive optical water indices;
- fit any groundwater association model;
- modify the frozen Sentinel-1 target universe.

Final optical-usability interpretation:
CONFIRMED_USABLE_SCL = {4 vegetation, 5 not-vegetated, 6 water}
OBSCURED_SCL = {2 cast/topographic shadow, 3 cloud shadow,
                8/9 cloud, 10 cirrus, 11 snow/ice}
UNCLASSIFIED_SCL = {7}
INVALID_SCL = {0 no data, 1 saturated/defective}

Class 2 is NOT treated as clear, and class 7 is retained separately rather
than promoted to usable. These are QA definitions only, not flooding labels.

Inputs
------
data/processed/publication_groundwater/ricefloodit_georef.csv
data/design_c/raw/sentinel2/sentinel2_l2a_scene_inventory_2015_latest.csv
outputs/diagnostics/design_c/c2pa_sentinel2_s1_target_matchability.csv

Outputs
-------
outputs/diagnostics/design_c/
    c2pb_scl_asset_technical_qa.csv
    c2pb_scl_point_samples.csv
    c2pb_target_scl_usability_summary.csv
    c2pb_scl_class_distribution.csv
    c2pb_scl_usability_qa.json
    c2pb_scl_usability_summary.txt

Run from repository root
------------------------
python -u scripts/06_design_c/25_audit_sentinel2_scl_rice_support.py
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]

GEOREF = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"
S2_INV = ROOT / "data" / "design_c" / "raw" / "sentinel2" / "sentinel2_l2a_scene_inventory_2015_latest.csv"
MATCH = ROOT / "outputs" / "diagnostics" / "design_c" / "c2pa_sentinel2_s1_target_matchability.csv"

DIAG = ROOT / "outputs" / "diagnostics" / "design_c"
DIAG.mkdir(parents=True, exist_ok=True)

ASSET_QA_OUT = DIAG / "c2pb_scl_asset_technical_qa.csv"
POINT_OUT = DIAG / "c2pb_scl_point_samples.csv"
TARGET_OUT = DIAG / "c2pb_target_scl_usability_summary.csv"
CLASS_OUT = DIAG / "c2pb_scl_class_distribution.csv"
QA_OUT = DIAG / "c2pb_scl_usability_qa.json"
SUMMARY_OUT = DIAG / "c2pb_scl_usability_summary.txt"

STAC_ITEM = (
    "https://stac.dataspace.copernicus.eu/v1/"
    "collections/sentinel-2-l2a/items/{item_id}"
)
TIMEOUT = 120
MAX_RETRIES = 6
USER_AGENT = "Lomellina-Design-C-C2PB-SCL/1.0"

EXPECTED_SUPPORT = 4331

SCL_LABELS = {
    0: "no_data",
    1: "saturated_or_defective",
    2: "cast_shadow",
    3: "cloud_shadows",
    4: "vegetation",
    5: "not_vegetated",
    6: "water",
    7: "unclassified",
    8: "cloud_medium_probability",
    9: "cloud_high_probability",
    10: "thin_cirrus",
    11: "snow_or_ice",
}

CONFIRMED_USABLE = {4, 5, 6}
OBSCURED = {2, 3, 8, 9, 10, 11}
UNCLASSIFIED = {7}
INVALID = {0, 1}


def get_json(url: str) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = repr(exc)
            if attempt < MAX_RETRIES:
                delay = min(30, attempt * 3)
                print(f"  metadata attempt {attempt} failed: {last}", flush=True)
                print(f"  retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Could not retrieve STAC item after retries: {last}")


def open_raster_retry(href: str):
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return rasterio.open(href), attempt
        except Exception as exc:
            last = repr(exc)
            if attempt < MAX_RETRIES:
                delay = min(30, attempt * 3)
                print(f"  raster open attempt {attempt} failed: {last}", flush=True)
                print(f"  retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Could not open raster after retries: {last}")



def infer_s2_crs(item_json: dict, item_id: str):
    """Resolve Sentinel-2 tile CRS without silently assuming raster metadata is complete.

    Priority:
      1. STAC proj:code (e.g. EPSG:32632)
      2. STAC proj:epsg
      3. Sentinel-2 MGRS tile code (UTM zone + latitude band)

    Returns (crs_string, source).
    """
    props = item_json.get("properties", {}) or {}

    proj_code = props.get("proj:code")
    if proj_code:
        s = str(proj_code)
        if s.upper().startswith("EPSG:"):
            return s.upper(), "stac_proj_code"
        if s.isdigit():
            return f"EPSG:{s}", "stac_proj_code_numeric"

    proj_epsg = props.get("proj:epsg")
    if proj_epsg is not None:
        try:
            return f"EPSG:{int(proj_epsg)}", "stac_proj_epsg"
        except Exception:
            pass

    candidates = [
        props.get("s2:mgrs_tile"),
        props.get("mgrs:tile"),
        props.get("grid:code"),
        item_id,
    ]

    mgrs = None
    for value in candidates:
        if not value:
            continue
        m = re.search(r"(?:T|MGRS-)?([0-9]{2})([A-Z])([A-Z]{2})", str(value).upper())
        if m:
            mgrs = m.groups()
            break

    if mgrs is None:
        raise AssertionError(
            f"{item_id}: raster CRS missing and CRS could not be recovered "
            "from STAC projection metadata or MGRS tile code."
        )

    zone = int(mgrs[0])
    lat_band = mgrs[1]

    # MGRS latitude bands C-M are south of the equator; N-X are north.
    north = lat_band >= "N"
    epsg = (32600 if north else 32700) + zone
    return f"EPSG:{epsg}", "mgrs_utm_fallback"

def sample_scl_for_item(item_id: str, support: pd.DataFrame):
    js = get_json(STAC_ITEM.format(item_id=item_id))
    assets = js.get("assets", {})
    if "SCL_20m" not in assets:
        raise AssertionError(f"{item_id}: SCL_20m asset missing.")

    href = assets["SCL_20m"]["href"]
    src, attempts = open_raster_retry(href)

    try:
        if src.crs is not None:
            effective_crs = str(src.crs)
            crs_source = "raster_metadata"
        else:
            effective_crs, crs_source = infer_s2_crs(js, item_id)
            print(
                f"      NOTE: raster CRS missing; recovered {effective_crs} "
                f"from {crs_source}",
                flush=True,
            )

        # Guard against unreferenced/identity-like raster transforms.
        transform_ok = (
            src.transform is not None
            and not (
                abs(src.transform.a - 1.0) < 1e-12
                and abs(src.transform.e - 1.0) < 1e-12
                and abs(src.transform.c) < 1e-12
                and abs(src.transform.f) < 1e-12
            )
        )
        if not transform_ok:
            raise AssertionError(
                f"{item_id}: raster transform/georeferencing is missing or identity-like. "
                "CRS recovery alone is insufficient; inspect granule metadata."
            )

        tf = Transformer.from_crs("EPSG:4326", effective_crs, always_xy=True)
        xs, ys = tf.transform(
            support["lon"].to_numpy(float),
            support["lat"].to_numpy(float),
        )

        inside = (
            (xs >= src.bounds.left)
            & (xs <= src.bounds.right)
            & (ys >= src.bounds.bottom)
            & (ys <= src.bounds.top)
        )

        idx = np.where(inside)[0]
        values = np.full(len(support), np.nan, dtype=float)

        if len(idx):
            coords = [(float(xs[i]), float(ys[i])) for i in idx]
            vals = np.fromiter(
                (int(v[0]) for v in src.sample(coords, indexes=1)),
                dtype=np.int16,
                count=len(coords),
            )
            values[idx] = vals

        qa = {
            "item_id": item_id,
            "scl_href": href,
            "open_attempts": attempts,
            "driver": src.driver,
            "crs": effective_crs,
            "crs_source": crs_source,
            "raster_crs_original": None if src.crs is None else str(src.crs),
            "transform": tuple(src.transform),
            "width": int(src.width),
            "height": int(src.height),
            "dtype": str(src.dtypes[0]),
            "nodata": src.nodata,
            "support_points_inside_raster_n": int(inside.sum()),
            "support_points_sampled_n": int(np.isfinite(values).sum()),
            "unknown_scl_values_n": int(
                np.sum([
                    np.isfinite(v) and int(v) not in SCL_LABELS
                    for v in values
                ])
            ),
            "status": "PASS",
        }
        return values, qa
    finally:
        src.close()


def target_key(row) -> str:
    return (
        f"{int(row.anchor_year)}|{row.season_phase}|"
        f"{row.s1_selected_date}|{row.s1_orbit_state}|"
        f"{int(row.s1_relative_orbit)}"
    )


def resolve_mosaic(values):
    """Resolve overlapping S2 tile observations for one support point/date.

    No spectral or flooding decision is made.

    If one tile is invalid (0/1) and another has a defined SCL class, keep the
    defined class. If multiple defined classes disagree, preserve the ambiguity
    explicitly instead of silently selecting one.
    """
    vals = [int(v) for v in values if np.isfinite(v)]
    if not vals:
        return np.nan, 0, False

    defined = [v for v in vals if v not in INVALID]
    use = defined if defined else vals

    counts = Counter(use)
    top_n = max(counts.values())
    top = sorted([k for k, n in counts.items() if n == top_n])

    ambiguous = len(top) > 1
    if ambiguous:
        return np.nan, len(vals), True

    return float(top[0]), len(vals), False


def main():
    print("DESIGN C - C2P-B SENTINEL-2 SCL RICE-SUPPORT USABILITY AUDIT")
    print("=" * 78)
    print("Actual 20 m SCL sampling over 4,331 RiceFloodIT support coordinates.")
    print("Uses only +/-1-day S1 targets with genuine S2 availability.")
    print("CONFIRMED usable SCL: 4,5,6")
    print("OBSCURED SCL: 2,3,8,9,10,11; class 7 retained as UNCLASSIFIED")
    print("No flooding classifier. No groundwater. No association model.\n")

    for path in (GEOREF, S2_INV, MATCH):
        if not path.exists():
            raise FileNotFoundError(path)

    geo = pd.read_csv(GEOREF)
    support = (
        geo[["lon", "lat"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["lat", "lon"])
        .reset_index(drop=True)
    )
    if len(support) != EXPECTED_SUPPORT:
        raise AssertionError(
            f"Expected {EXPECTED_SUPPORT} unique support points; found {len(support)}"
        )
    support["support_id"] = np.arange(len(support), dtype=int)

    inv = pd.read_csv(S2_INV)
    inv["date"] = pd.to_datetime(inv["date"], errors="coerce").dt.date.astype(str)

    mt = pd.read_csv(MATCH)
    mt = mt[
        (pd.to_numeric(mt["window_days"], errors="coerce") == 1)
        & (pd.to_numeric(mt["s2_items_n"], errors="coerce") > 0)
    ].copy()

    mt = mt.drop_duplicates(
        [
            "anchor_year",
            "season_phase",
            "s1_selected_date",
            "s1_orbit_state",
            "s1_relative_orbit",
        ]
    ).reset_index(drop=True)

    if len(mt) != 14:
        raise AssertionError(
            f"Expected 14 genuinely matchable frozen S1 targets; found {len(mt)}."
        )

    # The optical date is frozen here as the nearest catalogue date selected by C2P-A.
    mt["optical_date"] = mt["nearest_s2_date"].astype(str)
    mt["target_id"] = mt.apply(target_key, axis=1)

    asset_qa_rows = []
    sample_rows = []

    for n, tr in enumerate(mt.itertuples(index=False), start=1):
        print(
            f"[{n:02d}/{len(mt)}] target={tr.target_id} "
            f"optical_date={tr.optical_date}",
            flush=True,
        )

        scene_rows = inv[
            (inv["date"] == str(tr.optical_date))
            & (pd.to_numeric(
                inv["support_points_inside_footprint_n"], errors="coerce"
            ).fillna(0) > 0)
        ].copy()

        if scene_rows.empty:
            raise AssertionError(
                f"{tr.target_id}: no inventory items cover support on {tr.optical_date}."
            )

        print(f"  candidate tile items: {len(scene_rows)}", flush=True)

        per_item = []
        for sr in scene_rows.itertuples(index=False):
            print(f"    sampling {sr.item_id}", flush=True)
            values, qa = sample_scl_for_item(str(sr.item_id), support)
            qa.update(
                {
                    "target_id": tr.target_id,
                    "anchor_year": int(tr.anchor_year),
                    "season_phase": tr.season_phase,
                    "s1_selected_date": tr.s1_selected_date,
                    "optical_date": tr.optical_date,
                    "mgrs_tile": getattr(sr, "mgrs_tile", None),
                    "platform": getattr(sr, "platform", None),
                }
            )
            asset_qa_rows.append(qa)
            per_item.append((str(sr.item_id), values))

        # Mosaic by support coordinate without forcing disagreement.
        for i in range(len(support)):
            vals = [arr[i] for _, arr in per_item]
            scl, contributing_n, ambiguous = resolve_mosaic(vals)

            if np.isfinite(scl):
                code = int(scl)
                label = SCL_LABELS.get(code, "UNKNOWN")
                confirmed_usable = code in CONFIRMED_USABLE
                obscured = code in OBSCURED
                unclassified = code in UNCLASSIFIED
                invalid = code in INVALID
            else:
                code = np.nan
                label = "AMBIGUOUS_OVERLAP" if ambiguous else "NO_OBSERVATION"
                confirmed_usable = False
                obscured = False
                unclassified = False
                invalid = False

            sample_rows.append(
                {
                    "target_id": tr.target_id,
                    "anchor_year": int(tr.anchor_year),
                    "season_phase": tr.season_phase,
                    "s1_selected_date": tr.s1_selected_date,
                    "optical_date": tr.optical_date,
                    "nearest_abs_day_offset": int(tr.nearest_abs_day_offset),
                    "support_id": int(support.loc[i, "support_id"]),
                    "lon": float(support.loc[i, "lon"]),
                    "lat": float(support.loc[i, "lat"]),
                    "scl_code": code,
                    "scl_label": label,
                    "confirmed_usable": bool(confirmed_usable),
                    "obscured": bool(obscured),
                    "unclassified": bool(unclassified),
                    "invalid_or_nodata": bool(invalid),
                    "contributing_tile_items_n": int(contributing_n),
                    "tile_overlap_ambiguous": bool(ambiguous),
                }
            )

    asset_qa = pd.DataFrame(asset_qa_rows)
    samples = pd.DataFrame(sample_rows)

    asset_qa.to_csv(ASSET_QA_OUT, index=False)
    samples.to_csv(POINT_OUT, index=False)

    target_rows = []
    for target_id, g in samples.groupby("target_id", sort=True):
        meta = g.iloc[0]
        target_rows.append(
            {
                "target_id": target_id,
                "anchor_year": int(meta["anchor_year"]),
                "season_phase": meta["season_phase"],
                "s1_selected_date": meta["s1_selected_date"],
                "optical_date": meta["optical_date"],
                "nearest_abs_day_offset": int(meta["nearest_abs_day_offset"]),
                "support_points_n": int(len(g)),
                "observed_unambiguous_n": int(g["scl_code"].notna().sum()),
                "observed_unambiguous_share": float(g["scl_code"].notna().mean()),
                "confirmed_usable_n": int(g["confirmed_usable"].sum()),
                "confirmed_usable_share_domain": float(g["confirmed_usable"].mean()),
                "confirmed_usable_share_among_observed": (
                    float(g["confirmed_usable"].sum() / g["scl_code"].notna().sum())
                    if g["scl_code"].notna().sum() else np.nan
                ),
                "obscured_n": int(g["obscured"].sum()),
                "obscured_share_domain": float(g["obscured"].mean()),
                "unclassified_n": int(g["unclassified"].sum()),
                "unclassified_share_domain": float(g["unclassified"].mean()),
                "invalid_or_nodata_n": int(g["invalid_or_nodata"].sum()),
                "invalid_or_nodata_share": float(g["invalid_or_nodata"].mean()),
                "tile_overlap_ambiguous_n": int(g["tile_overlap_ambiguous"].sum()),
                "tile_overlap_ambiguous_share": float(
                    g["tile_overlap_ambiguous"].mean()
                ),
                "max_contributing_tile_items": int(
                    g["contributing_tile_items_n"].max()
                ),
            }
        )

    target_summary = pd.DataFrame(target_rows).sort_values(
        ["anchor_year", "s1_selected_date", "target_id"]
    )
    target_summary.to_csv(TARGET_OUT, index=False)

    class_dist = (
        samples.groupby(
            [
                "target_id",
                "anchor_year",
                "season_phase",
                "optical_date",
                "scl_code",
                "scl_label",
            ],
            dropna=False,
        )
        .size()
        .rename("n")
        .reset_index()
    )
    class_dist["share_within_target"] = (
        class_dist["n"]
        / class_dist.groupby("target_id")["n"].transform("sum")
    )
    class_dist.to_csv(CLASS_OUT, index=False)

    min_usable = float(target_summary["confirmed_usable_share_domain"].min())
    med_usable = float(target_summary["confirmed_usable_share_domain"].median())
    med_usable_obs = float(target_summary["confirmed_usable_share_among_observed"].median())
    max_ambig = float(target_summary["tile_overlap_ambiguous_share"].max())

    all_assets_pass = bool((asset_qa["status"] == "PASS").all())
    all_targets_complete = bool(
        (target_summary["support_points_n"] == EXPECTED_SUPPORT).all()
    )
    unknown_scl_total = int(asset_qa["unknown_scl_values_n"].sum())

    status = (
        "PASS"
        if all_assets_pass
        and all_targets_complete
        and unknown_scl_total == 0
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2PB_SENTINEL2_SCL_RICE_SUPPORT_USABILITY_AUDIT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ricefloodit_support_points_n": EXPECTED_SUPPORT,
        "matchability_window_days": 1,
        "matchable_s1_targets_n": int(len(mt)),
        "s2_scl_assets_opened_n": int(len(asset_qa)),
        "all_scl_assets_pass": all_assets_pass,
        "all_targets_have_expected_support_rows": all_targets_complete,
        "unknown_scl_values_n": unknown_scl_total,
        "confirmed_usable_scl_codes": sorted(CONFIRMED_USABLE),
        "obscured_scl_codes": sorted(OBSCURED),
        "unclassified_scl_codes": sorted(UNCLASSIFIED),
        "invalid_scl_codes": sorted(INVALID),
        "confirmed_usable_share_domain_min": min_usable,
        "confirmed_usable_share_domain_median": med_usable,
        "confirmed_usable_share_among_observed_median": med_usable_obs,
        "tile_overlap_ambiguity_share_max": max_ambig,
        "scl_semantics_final_correction_applied": True,
        "scl_class_2_treated_as_clear": False,
        "scl_class_7_treated_as_confirmed_usable": False,
        "catalogue_cloud_percentage_used_as_final_optical_usability": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "preexisting_flood_exposure_values_read": False,
        "optical_water_indices_derived": False,
        "inundation_classifier_fitted": False,
        "association_models_fitted": 0,
        "frozen_sentinel1_target_universe_modified": False,
        "next_stage": (
            "If PASS, audit L2A reflectance scaling/offset metadata and extract "
            "radiometrically comparable optical bands for the same outcome-blind "
            "target set before any water-index or inundation-rule calibration."
        ),
    }
    QA_OUT.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2P-B SENTINEL-2 SCL RICE-SUPPORT USABILITY AUDIT",
        "=" * 78,
        "",
        f"Matchable frozen S1 targets: {len(mt)}",
        f"RiceFloodIT support coordinates per target: {EXPECTED_SUPPORT}",
        f"SCL assets opened: {len(asset_qa)}",
        f"Unknown SCL values: {unknown_scl_total}",
        "",
        "ACTUAL RICE-SUPPORT OPTICAL USABILITY",
        "------------------------------------",
        f"Confirmed-usable domain share: min={min_usable:.6f}, median={med_usable:.6f}",
        f"Confirmed-usable share among observed: median={med_usable_obs:.6f}",
        f"Maximum ambiguous-overlap share: {max_ambig:.6f}",
        "",
        "Definitions:",
        "  confirmed usable = SCL {4 vegetation, 5 not vegetated, 6 water}",
        "  obscured         = SCL {2 cast shadow, 3 cloud shadow, 8/9 cloud, 10 cirrus, 11 snow/ice}",
        "  unclassified     = SCL {7}; retained separately",
        "  invalid          = SCL {0 no data, 1 saturated/defective}",
        "",
        "Catalogue eo:cloud_cover was NOT used as final rice-support usability.",
        "No optical water index or flooding classifier was fitted.",
        "No groundwater or irrigation-flow outcome was read.",
        "",
        f"C2P-B STATUS: {status}",
    ]

    summary = "\n".join(lines) + "\n"
    SUMMARY_OUT.write_text(summary, encoding="utf-8")
    print("\n" + summary)

    print("TARGET SUMMARY")
    print("--------------")
    pd.set_option("display.width", 260)
    print(target_summary.to_string(index=False))

    if status != "PASS":
        raise RuntimeError("C2P-B failed technical QA gates; inspect outputs.")


if __name__ == "__main__":
    main()

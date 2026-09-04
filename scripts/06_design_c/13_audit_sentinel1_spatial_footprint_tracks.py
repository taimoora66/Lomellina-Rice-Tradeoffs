"""Design C — C2I-S Sentinel-1 Stable-Track Spatial Footprint Audit.

PURPOSE
-------
Using the maximum Sentinel-1 metadata archive from C2I-R, determine whether
the four pre-measurement stable IW VV/VH tracks consistently cover the
RiceFloodIT/Lomellina study footprint during complete candidate years
2015-2025.

This stage DOES NOT:
- inspect SAR pixel values;
- classify inundation;
- read groundwater levels;
- read irrigation discharge;
- fit any association model;
- modify frozen publication artifacts.

PRE-FROZEN TECHNICAL FAMILY
---------------------------
Rice season: April-September
Instrument mode: IW
Polarization: VV|VH
Stable candidate tracks from C2I-R:
    ascending 15
    ascending 88
    descending 66
    descending 168
Orbit 139 is excluded from the primary stable-track universe because it is
not present across all complete candidate years.

SPATIAL METHOD
--------------
Each STAC item contains a bbox. For every track x acquisition date:
1. build rectangles from all scene bboxes on that date;
2. union them;
3. intersect with the study bounding rectangle derived from
   ricefloodit_georef.csv plus the same 0.10-degree C1/C2I-R margin;
4. compute study-bbox coverage fraction.

This is a metadata-level geometric coverage audit, not a SAR measurement.

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2is_track_date_spatial_coverage.csv
    c2is_track_year_spatial_coverage.csv
    c2is_stable_track_spatial_support.csv
    c2is_spatial_footprint_qa.json
    c2is_spatial_footprint_summary.txt

RUN
---
python scripts/06_design_c/13_audit_sentinel1_spatial_footprint_tracks.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[2]

INV = (
    ROOT / "data" / "design_c" / "raw" / "sentinel1"
    / "sentinel1_grd_scene_inventory_2014_latest2026.csv"
)
RICE_GEO = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "ricefloodit_georef.csv"
)
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

BBOX_MARGIN_DEG = 0.10
RICE_MONTHS = {4, 5, 6, 7, 8, 9}
COMPLETE_YEARS = list(range(2015, 2026))

STABLE_TRACKS = {
    ("ascending", 15),
    ("ascending", 88),
    ("descending", 66),
    ("descending", 168),
}

# Descriptive thresholds only. They do NOT select a scientific outcome sample.
FULL_COVERAGE_TOL = 0.995
HIGH_COVERAGE_TOL = 0.95


def study_bbox():
    g = pd.read_csv(RICE_GEO)
    if not {"lon", "lat"}.issubset(g.columns):
        raise AssertionError("ricefloodit_georef.csv must contain lon and lat.")

    minx = float(g["lon"].min()) - BBOX_MARGIN_DEG
    miny = float(g["lat"].min()) - BBOX_MARGIN_DEG
    maxx = float(g["lon"].max()) + BBOX_MARGIN_DEG
    maxy = float(g["lat"].max()) + BBOX_MARGIN_DEG

    return minx, miny, maxx, maxy


def valid_rect(row):
    vals = [
        row["bbox_min_lon"],
        row["bbox_min_lat"],
        row["bbox_max_lon"],
        row["bbox_max_lat"],
    ]

    if any(pd.isna(v) for v in vals):
        return None

    minx, miny, maxx, maxy = map(float, vals)

    if maxx <= minx or maxy <= miny:
        return None

    return box(minx, miny, maxx, maxy)


def main():
    print("DESIGN C - C2I-S SENTINEL-1 STABLE-TRACK SPATIAL FOOTPRINT AUDIT")
    print("=" * 74)
    print("NO SAR pixel values inspected.")
    print("NO inundation threshold tuned.")
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    if not INV.exists():
        raise FileNotFoundError(
            f"Missing C2I-R inventory: {INV}. Run C2I-R first."
        )

    d = pd.read_csv(INV)

    required = {
        "scene_id", "datetime", "instrument_mode", "polarizations",
        "orbit_state", "relative_orbit",
        "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
    }
    missing = required - set(d.columns)

    if missing:
        raise AssertionError(
            f"C2I-R inventory missing required fields: {sorted(missing)}"
        )

    d["datetime"] = pd.to_datetime(d["datetime"], errors="coerce", utc=True)
    d["date"] = d["datetime"].dt.date.astype(str)
    d["year"] = d["datetime"].dt.year
    d["month"] = d["datetime"].dt.month
    d["relative_orbit"] = pd.to_numeric(
        d["relative_orbit"], errors="coerce"
    ).astype("Int64")

    d = d.loc[
        d["year"].isin(COMPLETE_YEARS)
        & d["month"].isin(RICE_MONTHS)
        & d["instrument_mode"].eq("IW")
        & d["polarizations"].eq("VV|VH")
    ].copy()

    d["stable_track"] = [
        (str(a), int(o)) in STABLE_TRACKS if pd.notna(o) else False
        for a, o in zip(d["orbit_state"], d["relative_orbit"])
    ]
    d = d[d["stable_track"]].copy()

    sb = study_bbox()
    study_geom = box(*sb)
    study_area = float(study_geom.area)

    if study_area <= 0:
        raise AssertionError("Study bbox area is non-positive.")

    print(
        "Study bbox: "
        + ", ".join(f"{x:.8f}" for x in sb)
    )
    print(f"Stable-track rice-season scenes: {len(d)}")
    print(f"Years: {min(COMPLETE_YEARS)}-{max(COMPLETE_YEARS)}\n")

    rows = []

    for (state, orbit, date), g in d.groupby(
        ["orbit_state", "relative_orbit", "date"],
        dropna=False,
    ):
        geoms = []
        invalid_bbox_n = 0

        for _, r in g.iterrows():
            geom = valid_rect(r)
            if geom is None:
                invalid_bbox_n += 1
            else:
                geoms.append(geom)

        if geoms:
            union = unary_union(geoms)
            inter = union.intersection(study_geom)
            coverage = float(inter.area / study_area)
            coverage = min(max(coverage, 0.0), 1.0)
        else:
            coverage = np.nan

        rows.append(
            {
                "orbit_state": state,
                "relative_orbit": int(orbit),
                "date": date,
                "year": int(pd.Timestamp(date).year),
                "scenes_on_date_n": int(len(g)),
                "valid_scene_bboxes_n": int(len(geoms)),
                "invalid_scene_bboxes_n": int(invalid_bbox_n),
                "study_bbox_coverage_fraction": coverage,
                "study_bbox_coverage_pct": (
                    100.0 * coverage if pd.notna(coverage) else np.nan
                ),
                "full_coverage_ge_99_5pct": (
                    bool(coverage >= FULL_COVERAGE_TOL)
                    if pd.notna(coverage) else False
                ),
                "high_coverage_ge_95pct": (
                    bool(coverage >= HIGH_COVERAGE_TOL)
                    if pd.notna(coverage) else False
                ),
            }
        )

    td = pd.DataFrame(rows).sort_values(
        ["orbit_state", "relative_orbit", "date"]
    )
    td.to_csv(
        OUT / "c2is_track_date_spatial_coverage.csv",
        index=False,
    )

    ty = (
        td.groupby(["orbit_state", "relative_orbit", "year"])
        .agg(
            acquisition_dates_n=("date", "nunique"),
            median_scenes_per_date=("scenes_on_date_n", "median"),
            max_scenes_per_date=("scenes_on_date_n", "max"),
            median_coverage_fraction=("study_bbox_coverage_fraction", "median"),
            min_coverage_fraction=("study_bbox_coverage_fraction", "min"),
            p10_coverage_fraction=(
                "study_bbox_coverage_fraction",
                lambda x: float(x.quantile(0.10)),
            ),
            full_coverage_dates_n=("full_coverage_ge_99_5pct", "sum"),
            high_coverage_dates_n=("high_coverage_ge_95pct", "sum"),
        )
        .reset_index()
    )

    ty["full_coverage_share"] = (
        ty["full_coverage_dates_n"] / ty["acquisition_dates_n"]
    )
    ty["high_coverage_share"] = (
        ty["high_coverage_dates_n"] / ty["acquisition_dates_n"]
    )

    ty.to_csv(
        OUT / "c2is_track_year_spatial_coverage.csv",
        index=False,
    )

    support_rows = []

    for (state, orbit), g in td.groupby(
        ["orbit_state", "relative_orbit"]
    ):
        gy = ty.loc[
            ty["orbit_state"].eq(state)
            & ty["relative_orbit"].eq(orbit)
        ].copy()

        support_rows.append(
            {
                "orbit_state": state,
                "relative_orbit": int(orbit),
                "years_present_n": int(g["year"].nunique()),
                "acquisition_dates_n": int(g["date"].nunique()),
                "median_coverage_fraction_all_dates": float(
                    g["study_bbox_coverage_fraction"].median()
                ),
                "min_coverage_fraction_all_dates": float(
                    g["study_bbox_coverage_fraction"].min()
                ),
                "full_coverage_dates_share_all": float(
                    g["full_coverage_ge_99_5pct"].mean()
                ),
                "high_coverage_dates_share_all": float(
                    g["high_coverage_ge_95pct"].mean()
                ),
                "years_with_100pct_high_coverage_dates_n": int(
                    (gy["high_coverage_share"] >= 0.999999).sum()
                ),
                "worst_year_high_coverage_share": float(
                    gy["high_coverage_share"].min()
                ),
                "minimum_dates_in_any_year": int(
                    gy["acquisition_dates_n"].min()
                ),
                "max_scenes_needed_on_single_date": int(
                    g["scenes_on_date_n"].max()
                ),
            }
        )

    support = pd.DataFrame(support_rows).sort_values(
        ["orbit_state", "relative_orbit"]
    )
    support.to_csv(
        OUT / "c2is_stable_track_spatial_support.csv",
        index=False,
    )

    all_tracks_11_years = bool(
        (support["years_present_n"] == len(COMPLETE_YEARS)).all()
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2IS_SENTINEL1_STABLE_TRACK_SPATIAL_FOOTPRINT",
        "complete_candidate_years": COMPLETE_YEARS,
        "study_bbox": list(map(float, sb)),
        "study_bbox_margin_deg": BBOX_MARGIN_DEG,
        "stable_tracks": [
            {"orbit_state": a, "relative_orbit": o}
            for a, o in sorted(STABLE_TRACKS)
        ],
        "stable_tracks_n": int(len(support)),
        "all_stable_tracks_present_all_2015_2025_years": all_tracks_11_years,
        "track_date_rows_n": int(len(td)),
        "scene_bbox_invalid_rows_n": int(td["invalid_scene_bboxes_n"].sum()),
        "full_coverage_definition": "study bbox coverage >= 0.995",
        "high_coverage_definition": "study bbox coverage >= 0.95",
        "sar_pixels_inspected": 0,
        "inundation_thresholds_tuned": 0,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "interpretation_rule": (
            "Spatial footprint support is assessed independently of SAR signal "
            "and independently of groundwater outcomes."
        ),
        "next_stage": (
            "Select a prespecified small validation set of dates/areas from "
            "spatially adequate stable tracks, then inspect SAR measurement behavior."
        ),
    }

    (OUT / "c2is_spatial_footprint_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C - C2I-S SENTINEL-1 STABLE-TRACK SPATIAL FOOTPRINT AUDIT",
        "=" * 72,
        "",
        (
            "Study bbox: "
            + ", ".join(f"{x:.8f}" for x in sb)
        ),
        "Complete candidate years: 2015-2025",
        "Technical family: IW VV|VH, Apr-Sep",
        "",
        "STABLE TRACK SPATIAL SUPPORT",
        "----------------------------",
        support.to_string(index=False),
        "",
        "TRACK-YEAR SUPPORT",
        "------------------",
        ty.to_string(index=False),
        "",
        "INTERPRETATION",
        "--------------",
        "Coverage is based only on STAC scene bounding boxes.",
        "Multiple same-track scenes on the same date are unioned before coverage is computed.",
        "No SAR pixel values or groundwater outcomes were inspected.",
        "",
        "DECISION",
        "--------",
        (
            "Use these results to prespecify the spatially adequate track/date "
            "universe for C2J inundation measurement validation."
        ),
        "",
        "C2I-S STATUS: PASS",
    ]

    summary = "\n".join(lines) + "\n"
    (OUT / "c2is_spatial_footprint_summary.txt").write_text(
        summary,
        encoding="utf-8",
    )

    print("\n" + summary)


if __name__ == "__main__":
    main()

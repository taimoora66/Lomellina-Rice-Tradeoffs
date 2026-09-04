"""Design C — C2I-T Sentinel-1 coverage of actual RiceFloodIT support.

PURPOSE
-------
Refine the C2I-S rectangular-bbox footprint audit by evaluating coverage of
the ACTUAL georeferenced RiceFloodIT support points/cells.

Why this is necessary:
C2I-S used the full study bounding rectangle plus a 0.10-degree margin.
A Sentinel track can cover less than 100% of that rectangle while still
covering essentially all actual rice-study support.

This stage remains metadata-only.

IT DOES NOT
-----------
- inspect Sentinel-1 SAR pixel values;
- read flooding classifications or exposure values;
- read groundwater-level values;
- read irrigation discharge;
- tune thresholds;
- fit association models;
- alter frozen publication artifacts.

PRE-FROZEN TECHNICAL FAMILY
---------------------------
Complete candidate years: 2015-2025
Rice season: April-September
Instrument mode: IW
Polarization: VV|VH
Stable temporal tracks:
    ascending 15
    ascending 88
    descending 66
    descending 168

METHOD
------
For each stable track x acquisition date:
1. collect all STAC scene bounding boxes;
2. test every RiceFloodIT georeference point against those scene boxes;
3. calculate actual-support coverage fraction;
4. summarize by track and year.

No SAR pixels are downloaded or read.

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2it_track_date_rice_support_coverage.csv
    c2it_track_year_rice_support_coverage.csv
    c2it_stable_track_rice_support.csv
    c2it_rice_point_track_support.csv
    c2it_rice_support_footprint_qa.json
    c2it_rice_support_footprint_summary.txt

RUN
---
python scripts/06_design_c/14_audit_sentinel1_rice_support_coverage.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


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

COMPLETE_YEARS = list(range(2015, 2026))
RICE_MONTHS = {4, 5, 6, 7, 8, 9}

STABLE_TRACKS = {
    ("ascending", 15),
    ("ascending", 88),
    ("descending", 66),
    ("descending", 168),
}

FULL_SUPPORT_TOL = 0.999999
HIGH_SUPPORT_TOL = 0.99


def choose_point_id_column(g: pd.DataFrame) -> str | None:
    candidates = [
        "id", "cell_id", "pixel_id", "grid_id", "point_id",
        "ricefloodit_id", "fid", "index"
    ]
    cmap = {str(c).strip().lower(): c for c in g.columns}
    for c in candidates:
        if c in cmap:
            return cmap[c]
    return None


def valid_box_array(g: pd.DataFrame) -> np.ndarray:
    cols = [
        "bbox_min_lon", "bbox_min_lat",
        "bbox_max_lon", "bbox_max_lat",
    ]
    x = g[cols].apply(pd.to_numeric, errors="coerce").dropna().to_numpy(float)
    if len(x) == 0:
        return np.empty((0, 4), dtype=float)
    ok = (x[:, 2] > x[:, 0]) & (x[:, 3] > x[:, 1])
    return x[ok]


def covered_by_any_bbox(lon: np.ndarray, lat: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    covered = np.zeros(len(lon), dtype=bool)
    for minx, miny, maxx, maxy in boxes:
        covered |= (
            (lon >= minx) & (lon <= maxx)
            & (lat >= miny) & (lat <= maxy)
        )
    return covered


def main():
    print("DESIGN C - C2I-T SENTINEL-1 ACTUAL RICE-SUPPORT FOOTPRINT AUDIT")
    print("=" * 74)
    print("NO SAR pixel values inspected.")
    print("NO flooding/exposure values read.")
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO threshold tuned.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    if not INV.exists():
        raise FileNotFoundError(f"Missing C2I-R inventory: {INV}")
    if not RICE_GEO.exists():
        raise FileNotFoundError(f"Missing RiceFloodIT georef: {RICE_GEO}")

    d = pd.read_csv(INV)
    g = pd.read_csv(RICE_GEO)

    if not {"lon", "lat"}.issubset(g.columns):
        raise AssertionError("ricefloodit_georef.csv must contain lon and lat.")

    g["lon"] = pd.to_numeric(g["lon"], errors="coerce")
    g["lat"] = pd.to_numeric(g["lat"], errors="coerce")
    g = g.dropna(subset=["lon", "lat"]).copy()

    if g.empty:
        raise AssertionError("RiceFloodIT georef has zero valid lon/lat rows.")

    pid_col = choose_point_id_column(g)
    if pid_col:
        g["_point_id"] = g[pid_col].astype(str)
    else:
        g["_point_id"] = ["ricept_" + str(i) for i in range(len(g))]

    duplicate_coord_n = int(g.duplicated(["lon", "lat"]).sum())
    g_unique = (
        g.drop_duplicates(["lon", "lat"])
        .reset_index(drop=True)
        .copy()
    )

    lon = g_unique["lon"].to_numpy(float)
    lat = g_unique["lat"].to_numpy(float)
    point_ids = g_unique["_point_id"].astype(str).to_numpy()

    required = {
        "scene_id", "datetime", "instrument_mode", "polarizations",
        "orbit_state", "relative_orbit",
        "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
    }
    missing = required - set(d.columns)
    if missing:
        raise AssertionError(f"Inventory missing required fields: {sorted(missing)}")

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

    print(f"RiceFloodIT georef rows: {len(g)}")
    print(f"Unique rice-support coordinates: {len(g_unique)}")
    print(f"Duplicate-coordinate rows removed for coverage audit: {duplicate_coord_n}")
    print(f"Stable-track rice-season scenes: {len(d)}")
    print("Complete candidate years: 2015-2025\n")

    date_rows = []
    point_track_counts = {
        (state, orbit): np.zeros(len(g_unique), dtype=int)
        for state, orbit in STABLE_TRACKS
    }
    point_track_dates = {
        (state, orbit): 0
        for state, orbit in STABLE_TRACKS
    }

    for (state, orbit, date), s in d.groupby(
        ["orbit_state", "relative_orbit", "date"],
        dropna=False,
    ):
        boxes = valid_box_array(s)
        covered = covered_by_any_bbox(lon, lat, boxes)

        key = (str(state), int(orbit))
        point_track_counts[key] += covered.astype(int)
        point_track_dates[key] += 1

        frac = float(covered.mean()) if len(covered) else np.nan

        date_rows.append({
            "orbit_state": str(state),
            "relative_orbit": int(orbit),
            "date": date,
            "year": int(pd.Timestamp(date).year),
            "scenes_on_date_n": int(len(s)),
            "valid_scene_bboxes_n": int(len(boxes)),
            "rice_support_points_n": int(len(covered)),
            "rice_support_points_covered_n": int(covered.sum()),
            "rice_support_coverage_fraction": frac,
            "rice_support_coverage_pct": 100.0 * frac,
            "all_rice_support_covered": bool(frac >= FULL_SUPPORT_TOL),
            "rice_support_ge_99pct_covered": bool(frac >= HIGH_SUPPORT_TOL),
        })

    td = pd.DataFrame(date_rows).sort_values(
        ["orbit_state", "relative_orbit", "date"]
    )
    td.to_csv(
        OUT / "c2it_track_date_rice_support_coverage.csv",
        index=False,
    )

    ty = (
        td.groupby(["orbit_state", "relative_orbit", "year"])
        .agg(
            acquisition_dates_n=("date", "nunique"),
            median_scenes_per_date=("scenes_on_date_n", "median"),
            max_scenes_per_date=("scenes_on_date_n", "max"),
            median_rice_support_coverage_fraction=(
                "rice_support_coverage_fraction", "median"
            ),
            min_rice_support_coverage_fraction=(
                "rice_support_coverage_fraction", "min"
            ),
            p10_rice_support_coverage_fraction=(
                "rice_support_coverage_fraction",
                lambda x: float(x.quantile(0.10)),
            ),
            full_rice_support_dates_n=("all_rice_support_covered", "sum"),
            rice_support_ge_99pct_dates_n=(
                "rice_support_ge_99pct_covered", "sum"
            ),
        )
        .reset_index()
    )

    ty["full_rice_support_share"] = (
        ty["full_rice_support_dates_n"] / ty["acquisition_dates_n"]
    )
    ty["rice_support_ge_99pct_share"] = (
        ty["rice_support_ge_99pct_dates_n"] / ty["acquisition_dates_n"]
    )

    ty.to_csv(
        OUT / "c2it_track_year_rice_support_coverage.csv",
        index=False,
    )

    support_rows = []

    for (state, orbit), x in td.groupby(
        ["orbit_state", "relative_orbit"]
    ):
        xy = ty.loc[
            ty["orbit_state"].eq(state)
            & ty["relative_orbit"].eq(orbit)
        ]

        support_rows.append({
            "orbit_state": state,
            "relative_orbit": int(orbit),
            "years_present_n": int(x["year"].nunique()),
            "acquisition_dates_n": int(x["date"].nunique()),
            "median_rice_support_coverage_fraction_all_dates": float(
                x["rice_support_coverage_fraction"].median()
            ),
            "min_rice_support_coverage_fraction_all_dates": float(
                x["rice_support_coverage_fraction"].min()
            ),
            "full_rice_support_dates_share_all": float(
                x["all_rice_support_covered"].mean()
            ),
            "rice_support_ge_99pct_dates_share_all": float(
                x["rice_support_ge_99pct_covered"].mean()
            ),
            "years_with_100pct_dates_ge99pct_support_n": int(
                (xy["rice_support_ge_99pct_share"] >= 0.999999).sum()
            ),
            "worst_year_ge99pct_support_share": float(
                xy["rice_support_ge_99pct_share"].min()
            ),
            "minimum_dates_in_any_year": int(
                xy["acquisition_dates_n"].min()
            ),
        })

    support = pd.DataFrame(support_rows).sort_values(
        ["orbit_state", "relative_orbit"]
    )
    support.to_csv(
        OUT / "c2it_stable_track_rice_support.csv",
        index=False,
    )

    point_rows = []
    for key in sorted(STABLE_TRACKS):
        state, orbit = key
        total_dates = point_track_dates[key]
        counts = point_track_counts[key]

        for pid, xlon, xlat, count in zip(
            point_ids, lon, lat, counts
        ):
            point_rows.append({
                "orbit_state": state,
                "relative_orbit": orbit,
                "point_id": pid,
                "lon": xlon,
                "lat": xlat,
                "track_dates_n": total_dates,
                "dates_point_covered_n": int(count),
                "point_date_coverage_share": (
                    float(count / total_dates) if total_dates else np.nan
                ),
            })

    point_df = pd.DataFrame(point_rows)
    point_df.to_csv(
        OUT / "c2it_rice_point_track_support.csv",
        index=False,
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2IT_SENTINEL1_ACTUAL_RICE_SUPPORT_FOOTPRINT",
        "complete_candidate_years": COMPLETE_YEARS,
        "stable_tracks": [
            {"orbit_state": a, "relative_orbit": o}
            for a, o in sorted(STABLE_TRACKS)
        ],
        "rice_georef_rows_n": int(len(g)),
        "unique_rice_support_coordinates_n": int(len(g_unique)),
        "duplicate_rice_support_coordinates_n": duplicate_coord_n,
        "track_date_rows_n": int(len(td)),
        "sar_pixels_inspected": 0,
        "flooding_exposure_values_read": 0,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "thresholds_tuned": 0,
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "interpretation_rule": (
            "Final metadata footprint adequacy must be judged on actual "
            "RiceFloodIT support, not on unused corners of a rectangular bbox."
        ),
        "next_stage": (
            "Freeze the spatially adequate track/date universe and select a "
            "small prespecified SAR validation set without groundwater outcomes."
        ),
    }

    (OUT / "c2it_rice_support_footprint_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C - C2I-T SENTINEL-1 ACTUAL RICE-SUPPORT FOOTPRINT AUDIT",
        "=" * 72,
        "",
        f"RiceFloodIT georef rows: {len(g)}",
        f"Unique rice-support coordinates: {len(g_unique)}",
        f"Duplicate-coordinate rows: {duplicate_coord_n}",
        "Complete candidate years: 2015-2025",
        "Technical family: IW VV|VH, Apr-Sep",
        "",
        "ACTUAL RICE-SUPPORT TRACK COVERAGE",
        "----------------------------------",
        support.to_string(index=False),
        "",
        "TRACK-YEAR ACTUAL RICE-SUPPORT COVERAGE",
        "---------------------------------------",
        ty.to_string(index=False),
        "",
        "INTERPRETATION",
        "--------------",
        "This supersedes rectangular-bbox coverage for track eligibility.",
        "The C2I-S bbox audit remains useful as geographic context.",
        "No SAR signal values, flooding values, or groundwater outcomes were inspected.",
        "",
        "DECISION",
        "--------",
        "Use this table to freeze the track/date universe before SAR measurement validation.",
        "",
        "C2I-T STATUS: PASS",
    ]

    summary = "\n".join(lines) + "\n"
    (OUT / "c2it_rice_support_footprint_summary.txt").write_text(
        summary,
        encoding="utf-8",
    )

    print("\n" + summary)


if __name__ == "__main__":
    main()

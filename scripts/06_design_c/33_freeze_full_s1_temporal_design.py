"""Design C — C2T discover and freeze full Sentinel-1 temporal sampling design.

Purpose
-------
Identify the actual scene-level Sentinel-1 inventory used by the C2I-R maximum
archive and freeze the temporal sampling design for multi-temporal phenology.

This stage is outcome-blind:
- no groundwater
- no irrigation-flow outcome
- no RiceFloodIT flooding outcome
- no sensor-response optimization
- no classifier
- no threshold selection

Frozen temporal scope
---------------------
- years: 2015 through 2025 inclusive
- rice season: April 1 through September 30 inclusive
- stable tracks:
    ascending 15
    ascending 88
    descending 66
    descending 168

The script searches the repository for candidate scene-level CSV/Parquet files
with acquisition date/time, orbit state, relative orbit, and scene/item ID
columns. It scores candidates structurally, never by sensor values.

Outputs
-------
outputs/diagnostics/design_c/
    c2t_scene_inventory_candidates.csv
    c2t_frozen_s1_temporal_design.csv
    c2t_frozen_s1_temporal_design_by_year_track.csv
    c2t_frozen_s1_temporal_design_qa.json
    c2t_frozen_s1_temporal_design_summary.txt

Run
---
python -u scripts/06_design_c/33_freeze_full_s1_temporal_design.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "outputs" / "diagnostics" / "design_c"

OUT_CAND = D / "c2t_scene_inventory_candidates.csv"
OUT_DESIGN = D / "c2t_frozen_s1_temporal_design.csv"
OUT_YEAR_TRACK = D / "c2t_frozen_s1_temporal_design_by_year_track.csv"
OUT_QA = D / "c2t_frozen_s1_temporal_design_qa.json"
OUT_TXT = D / "c2t_frozen_s1_temporal_design_summary.txt"

START_YEAR = 2015
END_YEAR = 2025
START_MMDD = (4, 1)
END_MMDD = (9, 30)

TRACKS = {
    ("ascending", 15),
    ("ascending", 88),
    ("descending", 66),
    ("descending", 168),
}

SEARCH_ROOTS = [
    ROOT / "outputs" / "diagnostics" / "design_c",
    ROOT / "data" / "design_c",
    ROOT / "data" / "processed",
]

DATE_NAMES = [
    "datetime", "acquisition_datetime", "acquisition_date", "date",
    "selected_date", "sensing_datetime", "start_datetime", "start_time",
]
ORBIT_STATE_NAMES = ["orbit_state", "orbitstate"]
REL_ORBIT_NAMES = ["relative_orbit", "relativeorbit", "relative_orbit_number"]
ID_NAMES = [
    "scene_id", "canonical_scene_id", "item_id", "id",
    "product_id", "scene", "name",
]
PLATFORM_NAMES = ["platform", "satellite", "mission"]


def first_present(cols_lower, names):
    for n in names:
        if n in cols_lower:
            return cols_lower[n]
    return None


def inspect_file(path: Path):
    rec = {
        "path": str(path.relative_to(ROOT)),
        "suffix": path.suffix.lower(),
        "rows_n": np.nan,
        "columns_n": np.nan,
        "date_col": None,
        "orbit_state_col": None,
        "relative_orbit_col": None,
        "id_col": None,
        "platform_col": None,
        "structural_score": 0,
        "read_status": "UNREAD",
        "notes": "",
    }
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, nrows=200, low_memory=False)
            try:
                rows_n = sum(1 for _ in open(path, "rb")) - 1
            except Exception:
                rows_n = np.nan
        elif path.suffix.lower() in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
            rows_n = len(df)
            if len(df) > 200:
                df = df.head(200)
        else:
            rec["read_status"] = "SKIP_SUFFIX"
            return rec

        cols = list(df.columns)
        lower = {str(c).lower(): c for c in cols}
        rec["rows_n"] = int(rows_n) if np.isfinite(rows_n) else np.nan
        rec["columns_n"] = len(cols)
        rec["date_col"] = first_present(lower, DATE_NAMES)
        rec["orbit_state_col"] = first_present(lower, ORBIT_STATE_NAMES)
        rec["relative_orbit_col"] = first_present(lower, REL_ORBIT_NAMES)
        rec["id_col"] = first_present(lower, ID_NAMES)
        rec["platform_col"] = first_present(lower, PLATFORM_NAMES)

        required = [
            rec["date_col"], rec["orbit_state_col"],
            rec["relative_orbit_col"], rec["id_col"]
        ]
        rec["structural_score"] = sum(v is not None for v in required)
        rec["read_status"] = "PASS"
        return rec
    except Exception as e:
        rec["read_status"] = "ERROR"
        rec["notes"] = str(e)
        return rec


def parse_candidate(path: Path, meta: dict):
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, low_memory=False)
    else:
        df = pd.read_parquet(path)

    dcol = meta["date_col"]
    ocol = meta["orbit_state_col"]
    rcol = meta["relative_orbit_col"]
    icol = meta["id_col"]
    pcol = meta["platform_col"]

    out = pd.DataFrame({
        "acquisition_datetime": pd.to_datetime(df[dcol], errors="coerce", utc=True),
        "orbit_state": df[ocol].astype(str).str.lower().str.strip(),
        "relative_orbit": pd.to_numeric(df[rcol], errors="coerce"),
        "scene_id": df[icol].astype(str),
    })
    if pcol:
        out["platform"] = df[pcol].astype(str)
    else:
        out["platform"] = pd.NA

    out = out[
        out["acquisition_datetime"].notna()
        & out["relative_orbit"].notna()
        & out["scene_id"].notna()
    ].copy()
    out["relative_orbit"] = out["relative_orbit"].astype(int)
    out["year"] = out["acquisition_datetime"].dt.year.astype(int)
    out["month"] = out["acquisition_datetime"].dt.month.astype(int)
    out["day"] = out["acquisition_datetime"].dt.day.astype(int)
    out["acquisition_date"] = out["acquisition_datetime"].dt.date.astype(str)
    return out


def in_season(df):
    after_start = (df["month"] > START_MMDD[0]) | (
        (df["month"] == START_MMDD[0]) & (df["day"] >= START_MMDD[1])
    )
    before_end = (df["month"] < END_MMDD[0]) | (
        (df["month"] == END_MMDD[0]) & (df["day"] <= END_MMDD[1])
    )
    return after_start & before_end


def main():
    print("DESIGN C - C2T FREEZE FULL SENTINEL-1 TEMPORAL SAMPLING DESIGN")
    print("=" * 82)
    print("Years: 2015-2025")
    print("Rice season: Apr 1-Sep 30")
    print("Tracks: asc15, asc88, desc66, desc168")
    print("No groundwater. No outcomes. No threshold. No classifier.\n")

    files = []
    for root in SEARCH_ROOTS:
        if root.exists():
            for pat in ["*.csv", "*.parquet", "*.pq"]:
                files.extend(root.rglob(pat))

    # Avoid our own downstream outputs if script is rerun.
    files = sorted({
        p for p in files
        if "c2t_" not in p.name.lower()
        and p.stat().st_size > 0
    })

    cand_rows = [inspect_file(p) for p in files]
    cand = pd.DataFrame(cand_rows)

    if len(cand) == 0:
        raise RuntimeError("No candidate tabular files found.")

    # Prefer fully structural scene inventories, then larger row count.
    cand["rows_sort"] = pd.to_numeric(cand["rows_n"], errors="coerce").fillna(-1)
    cand = cand.sort_values(
        ["structural_score", "rows_sort", "path"],
        ascending=[False, False, True]
    ).reset_index(drop=True)

    cand.to_csv(OUT_CAND, index=False)

    eligible = cand[
        (cand["read_status"] == "PASS")
        & (cand["structural_score"] == 4)
    ].copy()

    chosen = None
    chosen_df = None
    chosen_metrics = None

    for _, row in eligible.iterrows():
        path = ROOT / row["path"]
        try:
            z = parse_candidate(path, row.to_dict())
        except Exception:
            continue

        z = z[
            (z["year"] >= START_YEAR)
            & (z["year"] <= END_YEAR)
            & in_season(z)
            & z.apply(
                lambda r: (str(r["orbit_state"]), int(r["relative_orbit"])) in TRACKS,
                axis=1,
            )
        ].copy()

        if len(z) == 0:
            continue

        # Structural quality for selection:
        # maximize stable-track-year coverage, then unique dates, then scenes.
        combo = (
            z[["year","orbit_state","relative_orbit"]]
            .drop_duplicates()
            .shape[0]
        )
        dates = z[
            ["year","orbit_state","relative_orbit","acquisition_date"]
        ].drop_duplicates().shape[0]
        scenes = z["scene_id"].nunique()

        metrics = (combo, dates, scenes)

        if chosen_metrics is None or metrics > chosen_metrics:
            chosen = row.to_dict()
            chosen_df = z
            chosen_metrics = metrics

    if chosen is None:
        print("\nTop structural candidates:")
        print(
            cand[
                ["path","rows_n","structural_score","date_col",
                 "orbit_state_col","relative_orbit_col","id_col"]
            ].head(20).to_string(index=False)
        )
        raise RuntimeError(
            "No scene-level candidate produced stable-track rice-season scenes."
        )

    z = chosen_df.copy()

    # Canonical deduplication is scene_id first. Repeated rows for the same scene
    # are metadata duplicates, not distinct acquisitions.
    z = z.sort_values(
        ["acquisition_datetime","orbit_state","relative_orbit","scene_id"]
    )
    z = z.drop_duplicates(["scene_id"]).copy()

    # Final strict filter.
    z = z[
        (z["year"] >= START_YEAR)
        & (z["year"] <= END_YEAR)
        & in_season(z)
        & z.apply(
            lambda r: (str(r["orbit_state"]), int(r["relative_orbit"])) in TRACKS,
            axis=1,
        )
    ].copy()

    z = z.sort_values(
        ["year","orbit_state","relative_orbit","acquisition_datetime","scene_id"]
    ).reset_index(drop=True)

    z["temporal_design_included"] = True
    z["temporal_design_reason"] = (
        "stable_track_and_apr_sep_and_year_2015_2025"
    )

    z.to_csv(OUT_DESIGN, index=False)

    yt = (
        z.groupby(["year","orbit_state","relative_orbit"], as_index=False)
        .agg(
            scenes_n=("scene_id","nunique"),
            acquisition_dates_n=("acquisition_date","nunique"),
            first_date=("acquisition_date","min"),
            last_date=("acquisition_date","max"),
        )
        .sort_values(["year","orbit_state","relative_orbit"])
    )

    # Gap diagnostics by year-track.
    gap_rows = []
    for key, g in z.groupby(["year","orbit_state","relative_orbit"], sort=True):
        dates = pd.to_datetime(sorted(g["acquisition_date"].unique()))
        gaps = pd.Series(dates).diff().dt.days.dropna()
        gap_rows.append({
            "year": key[0],
            "orbit_state": key[1],
            "relative_orbit": key[2],
            "median_gap_days": float(gaps.median()) if len(gaps) else np.nan,
            "max_gap_days": int(gaps.max()) if len(gaps) else np.nan,
        })
    gaps = pd.DataFrame(gap_rows)
    yt = yt.merge(
        gaps, on=["year","orbit_state","relative_orbit"],
        how="left", validate="one_to_one"
    )
    yt.to_csv(OUT_YEAR_TRACK, index=False)

    expected_combos = {
        (y, o, r)
        for y in range(START_YEAR, END_YEAR+1)
        for (o, r) in TRACKS
    }
    actual_combos = {
        (int(r.year), str(r.orbit_state), int(r.relative_orbit))
        for r in yt.itertuples(index=False)
    }
    missing = sorted(expected_combos - actual_combos)

    status = "PASS" if len(missing) == 0 else "PARTIAL"

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2T_FREEZE_FULL_S1_TEMPORAL_DESIGN",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "chosen_scene_inventory": chosen["path"],
        "chosen_date_col": chosen["date_col"],
        "chosen_orbit_state_col": chosen["orbit_state_col"],
        "chosen_relative_orbit_col": chosen["relative_orbit_col"],
        "chosen_scene_id_col": chosen["id_col"],
        "chosen_platform_col": chosen["platform_col"],
        "years": [START_YEAR, END_YEAR],
        "rice_season": "04-01 to 09-30 inclusive",
        "stable_tracks": [
            {"orbit_state":"ascending","relative_orbit":15},
            {"orbit_state":"ascending","relative_orbit":88},
            {"orbit_state":"descending","relative_orbit":66},
            {"orbit_state":"descending","relative_orbit":168},
        ],
        "scenes_n": int(z["scene_id"].nunique()),
        "acquisition_dates_n": int(z["acquisition_date"].nunique()),
        "year_track_combinations_expected_n": len(expected_combos),
        "year_track_combinations_present_n": len(actual_combos),
        "missing_year_track_combinations": [
            {"year": y, "orbit_state": o, "relative_orbit": r}
            for y,o,r in missing
        ],
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "ricefloodit_flood_outcomes_read": False,
        "sensor_response_values_used_for_selection": False,
        "inundation_threshold_selected": False,
        "classifier_fitted": False,
        "feature_optimization_performed": False,
    }
    OUT_QA.write_text(json.dumps(qa, indent=2)+"\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2T FREEZE FULL SENTINEL-1 TEMPORAL SAMPLING DESIGN",
        "="*82,
        "",
        f"Chosen scene inventory: {chosen['path']}",
        f"Scene-ID column: {chosen['id_col']}",
        f"Datetime column: {chosen['date_col']}",
        f"Orbit-state column: {chosen['orbit_state_col']}",
        f"Relative-orbit column: {chosen['relative_orbit_col']}",
        "",
        f"Frozen years: {START_YEAR}-{END_YEAR}",
        "Frozen rice season: April 1-September 30",
        "Frozen stable tracks: asc15, asc88, desc66, desc168",
        "",
        f"Included unique scenes: {qa['scenes_n']}",
        f"Included unique acquisition dates: {qa['acquisition_dates_n']}",
        f"Year-track combinations present: "
        f"{qa['year_track_combinations_present_n']}/"
        f"{qa['year_track_combinations_expected_n']}",
        f"Missing year-track combinations: {len(missing)}",
        "",
        "No groundwater / flow / RiceFloodIT flood outcome read.",
        "No sensor-response optimization.",
        "No threshold or classifier.",
        "",
        f"C2T STATUS: {status}",
    ]
    txt = "\n".join(lines)+"\n"
    OUT_TXT.write_text(txt, encoding="utf-8")

    print(txt)
    print("YEAR-TRACK TEMPORAL DESIGN")
    print("--------------------------")
    pd.set_option("display.width", 260)
    print(yt.to_string(index=False))

    if status == "PARTIAL":
        print("\nMissing year-track combinations:")
        for m in missing:
            print("  ", m)


if __name__ == "__main__":
    main()

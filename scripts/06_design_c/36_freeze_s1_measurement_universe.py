"""Design C — C2U-F final Sentinel-1 measurement-universe freeze.

Purpose
-------
Freeze the final outcome-blind Sentinel-1 measurement architecture after C2T,
C2U-RR and C2U-S.

This stage DOES NOT modify C2T. It classifies every C2T candidate scene into:
1) PRIMARY_VVVH
   - IW mode
   - VV + VH
   - contributes wherever its raster actually covers the fixed support
2) AUXILIARY_HHHV
   - IW mode
   - HH + HV
   - retained as a separate polarization-specific stream
   - never substituted numerically for VV/VH
3) OUTSIDE_STUDY_SUPPORT
   - non-primary technical exception demonstrated by C2U-S to have zero
     RiceFloodIT-support coverage
4) TECHNICAL_EXCEPTION_UNRESOLVED
   - fail-safe category; causes stage failure

The C2U-S >=99% threshold is NOT used as a scene-inclusion threshold here.
Partial primary spatial coverage is valid: observed support points are retained,
uncovered support points remain missing.

No SAR pixel values, groundwater, irrigation flow, RiceFloodIT flooding values,
thresholds, classifiers, or association models are read/fitted.

Inputs
------
outputs/diagnostics/design_c/c2t_frozen_s1_temporal_design.csv
outputs/diagnostics/design_c/c2u_item_metadata.csv
outputs/diagnostics/design_c/c2u_asset_inventory.csv
outputs/diagnostics/design_c/c2u_fullseason_canonical_asset_plan.csv
outputs/diagnostics/design_c/c2urr_technical_measurement_exclusions.csv
outputs/diagnostics/design_c/c2us_exception_rescue_scene_coverage.csv
outputs/diagnostics/design_c/c2us_exception_rescue_date_coverage.csv
outputs/diagnostics/design_c/c2us_exception_rescue_decision.csv

Outputs
-------
outputs/diagnostics/design_c/
  c2uf_scene_measurement_universe.csv
  c2uf_primary_vvvh_canonical_asset_plan.csv
  c2uf_auxiliary_hhhv_asset_plan.csv
  c2uf_audit_only_scene_manifest.csv
  c2uf_measurement_universe_by_year_track.csv
  c2uf_measurement_universe_qa.json
  c2uf_measurement_universe_summary.txt

Run
---
python -u scripts/06_design_c/36_freeze_s1_measurement_universe.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

C2T = OUT / "c2t_frozen_s1_temporal_design.csv"
ITEMS = OUT / "c2u_item_metadata.csv"
ASSETS = OUT / "c2u_asset_inventory.csv"
PRIMARY_PLAN = OUT / "c2u_fullseason_canonical_asset_plan.csv"
EXCLUSIONS = OUT / "c2urr_technical_measurement_exclusions.csv"
C2US_SCENE = OUT / "c2us_exception_rescue_scene_coverage.csv"
C2US_DATE = OUT / "c2us_exception_rescue_date_coverage.csv"
C2US_DECISION = OUT / "c2us_exception_rescue_decision.csv"

SCENE_OUT = OUT / "c2uf_scene_measurement_universe.csv"
PRIMARY_OUT = OUT / "c2uf_primary_vvvh_canonical_asset_plan.csv"
AUX_OUT = OUT / "c2uf_auxiliary_hhhv_asset_plan.csv"
AUDIT_OUT = OUT / "c2uf_audit_only_scene_manifest.csv"
YT_OUT = OUT / "c2uf_measurement_universe_by_year_track.csv"
QA_OUT = OUT / "c2uf_measurement_universe_qa.json"
TXT_OUT = OUT / "c2uf_measurement_universe_summary.txt"

EXPECTED_C2T_SCENES = 2170
EXPECTED_TECH_EXCEPTIONS = 5
EXPECTED_PRIMARY_ELIGIBLE_SCENE_ROWS = 2165
EXPECTED_AUX_SCENE_ROWS = 3
EXPECTED_OUTSIDE_SCENE_ROWS = 2
EXPECTED_PRIMARY_CANONICAL_SCENES = 2134
EXPECTED_YEAR_TRACK_COMBOS = 44


def has_pol(text, pol):
    s = str(text).upper()
    return bool(re.search(rf"(?:^|\|){pol}(?:\||$)", s))


def asset_lookup_table(assets):
    return {
        (str(r.scene_id), str(r.asset_key)): str(r.href)
        for r in assets.itertuples(index=False)
    }


def select_raster_asset(assets, scene, pol):
    q = assets[assets["scene_id"].astype(str).eq(str(scene))].copy()
    if q.empty:
        raise RuntimeError(f"No assets found for scene {scene}")

    rows = []
    for r in q.itertuples(index=False):
        key = str(r.asset_key)
        title = str(getattr(r, "title", "") or "")
        href = str(getattr(r, "href", "") or "")
        text = f"{key} {title} {href}".lower()

        match = bool(
            re.search(
                rf"(^|[^a-z0-9]){pol.lower()}([^a-z0-9]|$)",
                text,
            )
        )
        if not match:
            continue

        is_data = str(getattr(r, "is_data_role", "")).lower() == "true"
        is_tiff = str(getattr(r, "looks_like_tiff", "")).lower() == "true"

        rows.append({
            "asset_key": key,
            "href": href,
            "is_data": is_data,
            "is_tiff": is_tiff,
        })

    if not rows:
        raise RuntimeError(f"No {pol} raster asset found for {scene}")

    z = pd.DataFrame(rows).sort_values(
        ["is_data", "is_tiff", "asset_key", "href"],
        ascending=[False, False, True, True],
    )
    return z.iloc[0]["asset_key"], z.iloc[0]["href"]


def main():
    print("DESIGN C - C2U-F FINAL SENTINEL-1 MEASUREMENT-UNIVERSE FREEZE")
    print("=" * 82)
    print("C2T is preserved unchanged.")
    print("No SAR pixel values / groundwater / flow / flood outcomes.")
    print("Primary partial spatial coverage is allowed; uncovered support remains missing.\n")

    for p in [
        C2T, ITEMS, ASSETS, PRIMARY_PLAN, EXCLUSIONS,
        C2US_SCENE, C2US_DATE, C2US_DECISION,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    c2t = pd.read_csv(C2T, low_memory=False)
    items = pd.read_csv(ITEMS, low_memory=False)
    assets = pd.read_csv(ASSETS, low_memory=False)
    primary = pd.read_csv(PRIMARY_PLAN, low_memory=False)
    exc = pd.read_csv(EXCLUSIONS, low_memory=False)
    cov_scene = pd.read_csv(C2US_SCENE, low_memory=False)
    cov_date = pd.read_csv(C2US_DATE, low_memory=False)
    decisions = pd.read_csv(C2US_DECISION, low_memory=False)

    c2t = c2t[c2t["temporal_design_included"].astype(str).str.lower().isin(
        ["true", "1", "yes"]
    )].copy()

    if c2t["scene_id"].nunique() != EXPECTED_C2T_SCENES:
        raise AssertionError(
            f"Expected {EXPECTED_C2T_SCENES} C2T scenes, "
            f"got {c2t['scene_id'].nunique()}"
        )

    if items["scene_id"].nunique() != EXPECTED_C2T_SCENES:
        raise AssertionError(
            "C2U metadata table must retain all 2170 resolved STAC items; "
            f"got {items['scene_id'].nunique()}"
        )

    # Every C2T scene must have one resolved item metadata row.
    m = c2t.merge(
        items,
        on="scene_id",
        how="left",
        suffixes=("_c2t", "_stac"),
        validate="one_to_one",
    )
    if m["resolve_status"].isna().any():
        missing = m.loc[m["resolve_status"].isna(), "scene_id"].tolist()
        raise AssertionError(f"Unresolved/missing STAC item rows: {missing}")

    m["instrument_mode_norm"] = (
        m["instrument_mode"].astype(str).str.upper().str.strip()
    )
    m["polarizations_norm"] = (
        m["polarizations"].astype(str).str.upper().str.strip()
    )
    m["is_iw"] = m["instrument_mode_norm"].eq("IW")
    m["has_vv"] = m["polarizations_norm"].map(lambda x: has_pol(x, "VV"))
    m["has_vh"] = m["polarizations_norm"].map(lambda x: has_pol(x, "VH"))
    m["has_hh"] = m["polarizations_norm"].map(lambda x: has_pol(x, "HH"))
    m["has_hv"] = m["polarizations_norm"].map(lambda x: has_pol(x, "HV"))

    m["measurement_disposition"] = "TECHNICAL_EXCEPTION_UNRESOLVED"
    m["measurement_reason"] = ""

    primary_mask = m["is_iw"] & m["has_vv"] & m["has_vh"]
    aux_candidate = m["is_iw"] & m["has_hh"] & m["has_hv"]

    m.loc[primary_mask, "measurement_disposition"] = "PRIMARY_VVVH"
    m.loc[primary_mask, "measurement_reason"] = (
        "IW mode with VV+VH; primary homogeneous SAR backbone. "
        "Use only support points actually covered by each raster."
    )

    # C2U-S scene coverage is used only for the 5 technical exceptions.
    c2us_cov = cov_scene[
        cov_scene["scene_id"].astype(str).isin(
            exc["scene_id"].astype(str)
        )
    ][
        ["scene_id", "support_points_inside_n", "support_coverage_fraction"]
    ].copy()

    m = m.merge(
        c2us_cov,
        on="scene_id",
        how="left",
        validate="one_to_one",
    )

    aux_mask = (
        aux_candidate
        & m["support_coverage_fraction"].notna()
        & (m["support_coverage_fraction"] > 0)
    )
    m.loc[aux_mask, "measurement_disposition"] = "AUXILIARY_HHHV"
    m.loc[aux_mask, "measurement_reason"] = (
        "IW HH+HV technical exception with demonstrated study-support coverage; "
        "retain as separate auxiliary polarization stream; never substitute "
        "numerically for VV/VH."
    )

    outside_mask = (
        ~primary_mask
        & ~aux_mask
        & m["support_coverage_fraction"].notna()
        & np.isclose(
            pd.to_numeric(
                m["support_coverage_fraction"], errors="coerce"
            ).fillna(-1),
            0.0,
        )
    )
    m.loc[outside_mask, "measurement_disposition"] = "OUTSIDE_STUDY_SUPPORT"
    m.loc[outside_mask, "measurement_reason"] = (
        "Technical exception with zero fixed RiceFloodIT-support coverage in "
        "C2U-S; retain metadata/audit only."
    )

    unresolved = m[
        m["measurement_disposition"].eq("TECHNICAL_EXCEPTION_UNRESOLVED")
    ].copy()
    if len(unresolved):
        raise AssertionError(
            "Unresolved technical exceptions remain:\n"
            + unresolved[
                ["scene_id", "instrument_mode_norm", "polarizations_norm"]
            ].to_string(index=False)
        )

    disposition_counts = (
        m["measurement_disposition"].value_counts().to_dict()
    )

    if disposition_counts.get("PRIMARY_VVVH", 0) != EXPECTED_PRIMARY_ELIGIBLE_SCENE_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_PRIMARY_ELIGIBLE_SCENE_ROWS} PRIMARY_VVVH "
            f"scene rows, got {disposition_counts.get('PRIMARY_VVVH', 0)}"
        )
    if disposition_counts.get("AUXILIARY_HHHV", 0) != EXPECTED_AUX_SCENE_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_AUX_SCENE_ROWS} AUXILIARY_HHHV scene rows, "
            f"got {disposition_counts.get('AUXILIARY_HHHV', 0)}"
        )
    if disposition_counts.get("OUTSIDE_STUDY_SUPPORT", 0) != EXPECTED_OUTSIDE_SCENE_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_OUTSIDE_SCENE_ROWS} OUTSIDE_STUDY_SUPPORT "
            f"scene rows, got {disposition_counts.get('OUTSIDE_STUDY_SUPPORT', 0)}"
        )

    # Save concise, authoritative scene manifest.
    scene_cols = [
        "acquisition_datetime", "orbit_state_c2t", "relative_orbit_c2t",
        "scene_id", "platform_c2t", "year", "month", "day",
        "acquisition_date", "temporal_design_included",
        "temporal_design_reason", "instrument_mode",
        "polarizations", "product_type", "measurement_disposition",
        "measurement_reason", "support_points_inside_n",
        "support_coverage_fraction",
    ]
    scene_manifest = m[scene_cols].copy()
    scene_manifest = scene_manifest.rename(columns={
        "orbit_state_c2t": "orbit_state",
        "relative_orbit_c2t": "relative_orbit",
        "platform_c2t": "platform",
    })
    scene_manifest.to_csv(SCENE_OUT, index=False)

    # Validate existing primary canonical plan.
    if primary["canonical_scene_id"].nunique() != EXPECTED_PRIMARY_CANONICAL_SCENES:
        raise AssertionError(
            f"Expected {EXPECTED_PRIMARY_CANONICAL_SCENES} primary canonical "
            f"scenes, got {primary['canonical_scene_id'].nunique()}"
        )

    primary_ids = set(
        m.loc[
            m["measurement_disposition"].eq("PRIMARY_VVVH"),
            "scene_id",
        ].astype(str)
    )
    if not set(primary["original_frozen_scene_id"].astype(str)).issubset(primary_ids):
        bad_primary = sorted(
            set(primary["original_frozen_scene_id"].astype(str)) - primary_ids
        )
        raise AssertionError(
            f"Primary canonical plan contains non-primary original scenes: "
            f"{bad_primary[:20]}"
        )

    # Explicitly state partial coverage policy in primary plan.
    primary_out = primary.copy()
    primary_out["measurement_disposition"] = "PRIMARY_VVVH"
    primary_out["spatial_coverage_policy"] = (
        "retain all actually observed support points; uncovered support = missing; "
        "no whole-scene >=99% inclusion threshold"
    )
    primary_out["hh_hv_substitution_allowed"] = False
    primary_out.to_csv(PRIMARY_OUT, index=False)

    # Build auxiliary HH/HV exact asset plan for the 3 retained scenes.
    lookup = asset_lookup_table(assets)
    aux_rows = []

    aux_scenes = m[
        m["measurement_disposition"].eq("AUXILIARY_HHHV")
    ].copy()

    for r in aux_scenes.itertuples(index=False):
        sid = str(r.scene_id)
        hh_key, hh_href = select_raster_asset(assets, sid, "HH")
        hv_key, hv_href = select_raster_asset(assets, sid, "HV")

        rec = {
            "scene_id": sid,
            "acquisition_datetime": r.acquisition_datetime,
            "acquisition_date": r.acquisition_date,
            "year": int(r.year),
            "orbit_state": r.orbit_state_c2t,
            "relative_orbit": int(r.relative_orbit_c2t),
            "platform": r.platform_c2t,
            "instrument_mode": r.instrument_mode,
            "polarizations": r.polarizations,
            "measurement_disposition": "AUXILIARY_HHHV",
            "support_points_inside_n": int(r.support_points_inside_n),
            "support_coverage_fraction": float(r.support_coverage_fraction),
            "hh_asset_key": hh_key,
            "hh_href": hh_href,
            "hv_asset_key": hv_key,
            "hv_href": hv_href,
        }

        for pol in ["hh", "hv"]:
            for schema in ["calibration", "noise", "product"]:
                k = f"schema-{schema}-{pol}"
                h = lookup.get((sid, k))
                if not h:
                    raise RuntimeError(
                        f"Missing {k} for auxiliary scene {sid}"
                    )
                rec[f"{schema}_{pol}_asset_key"] = k
                rec[f"{schema}_{pol}_href"] = h

        aux_rows.append(rec)

    aux_plan = pd.DataFrame(aux_rows).sort_values(
        ["year", "acquisition_datetime", "scene_id"]
    )
    aux_plan.to_csv(AUX_OUT, index=False)

    audit_only = m[
        m["measurement_disposition"].eq("OUTSIDE_STUDY_SUPPORT")
    ][scene_cols].copy()
    audit_only = audit_only.rename(columns={
        "orbit_state_c2t": "orbit_state",
        "relative_orbit_c2t": "relative_orbit",
        "platform_c2t": "platform",
    })
    audit_only.to_csv(AUDIT_OUT, index=False)

    # Year-track architecture summary.
    yt = (
        scene_manifest.groupby(
            ["year", "orbit_state", "relative_orbit",
             "measurement_disposition"],
            as_index=False,
        )
        .agg(
            scene_rows_n=("scene_id", "nunique"),
            acquisition_dates_n=("acquisition_date", "nunique"),
        )
    )

    yt_pivot = (
        yt.pivot_table(
            index=["year", "orbit_state", "relative_orbit"],
            columns="measurement_disposition",
            values=["scene_rows_n", "acquisition_dates_n"],
            fill_value=0,
            aggfunc="sum",
        )
        .reset_index()
    )
    yt_pivot.columns = [
        "_".join([str(x) for x in c if str(x)])
        if isinstance(c, tuple) else str(c)
        for c in yt_pivot.columns
    ]
    yt_pivot.to_csv(YT_OUT, index=False)

    combos = scene_manifest[
        ["year", "orbit_state", "relative_orbit"]
    ].drop_duplicates()
    combo_n = len(combos)

    primary_combo_n = len(
        scene_manifest[
            scene_manifest["measurement_disposition"].eq("PRIMARY_VVVH")
        ][["year", "orbit_state", "relative_orbit"]].drop_duplicates()
    )

    # Confirm C2U-S evidence for the two 2016 acquisition groups and 2025 EW group.
    date_cov = dict(
        zip(
            cov_date["acquisition_group"].astype(str),
            pd.to_numeric(
                cov_date["support_coverage_union_fraction"],
                errors="coerce",
            ),
        )
    )

    if not np.isclose(
        date_cov.get("2016-07-03_ASC15_HHHV", np.nan), 1.0
    ):
        raise AssertionError("2016-07-03 HH/HV union coverage is not 1.0")
    if not np.isclose(
        date_cov.get("2016-08-20_ASC15_HHHV", np.nan), 1.0
    ):
        raise AssertionError("2016-08-20 HH/HV union coverage is not 1.0")
    if not np.isclose(
        date_cov.get("2025-04-21_DESC66_EW_HHHV", np.nan), 0.0
    ):
        raise AssertionError("2025-04-21 EW HH/HV union coverage is not 0.0")

    status = (
        "PASS"
        if combo_n == EXPECTED_YEAR_TRACK_COMBOS
        and primary_combo_n == EXPECTED_YEAR_TRACK_COMBOS
        and len(aux_plan) == EXPECTED_AUX_SCENE_ROWS
        and len(audit_only) == EXPECTED_OUTSIDE_SCENE_ROWS
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2UF_FINAL_SENTINEL1_MEASUREMENT_UNIVERSE_FREEZE",
        "c2t_candidate_scene_rows_n": int(len(scene_manifest)),
        "stac_items_resolved_n": int(items["scene_id"].nunique()),
        "primary_vvvh_scene_rows_n":
            int(disposition_counts.get("PRIMARY_VVVH", 0)),
        "auxiliary_hhhv_scene_rows_n":
            int(disposition_counts.get("AUXILIARY_HHHV", 0)),
        "outside_study_support_scene_rows_n":
            int(disposition_counts.get("OUTSIDE_STUDY_SUPPORT", 0)),
        "technical_exception_unresolved_scene_rows_n":
            int(disposition_counts.get("TECHNICAL_EXCEPTION_UNRESOLVED", 0)),
        "primary_vvvh_canonical_scene_rows_n":
            int(primary["canonical_scene_id"].nunique()),
        "year_track_combinations_candidate_n": int(combo_n),
        "year_track_combinations_primary_vvvh_n": int(primary_combo_n),
        "2016_07_03_hhhv_union_coverage_fraction":
            float(date_cov["2016-07-03_ASC15_HHHV"]),
        "2016_08_20_hhhv_union_coverage_fraction":
            float(date_cov["2016-08-20_ASC15_HHHV"]),
        "2025_04_21_ew_hhhv_union_coverage_fraction":
            float(date_cov["2025-04-21_DESC66_EW_HHHV"]),
        "partial_primary_scene_coverage_allowed": True,
        "uncovered_support_points_policy": "missing_not_imputed",
        "c2us_099_threshold_used_as_scene_inclusion_rule": False,
        "hh_hv_substituted_for_vv_vh": False,
        "c2t_modified": False,
        "sar_pixel_values_read": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "ricefloodit_flood_values_read": False,
        "sensor_response_values_used_for_selection": False,
        "inundation_threshold_selected": False,
        "classifier_fitted": False,
        "association_models_fitted": 0,
        "next_stage": (
            "C2V full-season raster extraction using frozen PRIMARY_VVVH "
            "canonical plan plus separately partitioned AUXILIARY_HHHV plan."
        ),
    }
    QA_OUT.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2U-F FINAL SENTINEL-1 MEASUREMENT-UNIVERSE FREEZE",
        "=" * 82,
        "",
        f"C2T candidate scene records: {len(scene_manifest)} / 2170",
        f"Resolved STAC items: {items['scene_id'].nunique()} / 2170",
        f"PRIMARY_VVVH scene records: {disposition_counts.get('PRIMARY_VVVH', 0)}",
        f"AUXILIARY_HHHV scene records: {disposition_counts.get('AUXILIARY_HHHV', 0)}",
        f"OUTSIDE_STUDY_SUPPORT scene records: {disposition_counts.get('OUTSIDE_STUDY_SUPPORT', 0)}",
        f"Primary canonical VV/VH scenes: {primary['canonical_scene_id'].nunique()}",
        f"Candidate year-track combinations: {combo_n}/44",
        f"Primary VV/VH year-track combinations: {primary_combo_n}/44",
        "",
        "2016 AUXILIARY HH/HV",
        "--------------------",
        "2016-07-03 ASC15 union support coverage: "
        f"{date_cov['2016-07-03_ASC15_HHHV']:.6f}",
        "2016-08-20 ASC15 union support coverage: "
        f"{date_cov['2016-08-20_ASC15_HHHV']:.6f}",
        "",
        "2025 EW AUDIT-ONLY",
        "------------------",
        "2025-04-21 DESC66 EW HH/HV union support coverage: "
        f"{date_cov['2025-04-21_DESC66_EW_HHHV']:.6f}",
        "",
        "PRIMARY SPATIAL-COVERAGE POLICY",
        "-------------------------------",
        "Partial primary scene coverage is valid.",
        "Observed support points are retained.",
        "Uncovered support points remain missing and are not imputed.",
        "The C2U-S >=99% rescue threshold is NOT a scene inclusion threshold.",
        "",
        "POLARIZATION POLICY",
        "-------------------",
        "HH/HV is retained only as a separate auxiliary stream.",
        "HH is never substituted for VV.",
        "HV is never substituted for VH.",
        "",
        "FIREWALL",
        "--------",
        "C2T modified: False",
        "SAR pixel values read: False",
        "Groundwater read: False",
        "Irrigation flow read: False",
        "RiceFloodIT flood values read: False",
        "Sensor-response optimization: False",
        "Threshold/classifier: False",
        "",
        f"C2U-F STATUS: {status}",
    ]

    txt = "\n".join(lines) + "\n"
    TXT_OUT.write_text(txt, encoding="utf-8")
    print(txt)

    print("AUXILIARY HH/HV ASSET PLAN")
    print("---------------------------")
    print(
        aux_plan[
            [
                "acquisition_date", "scene_id", "orbit_state",
                "relative_orbit", "support_coverage_fraction",
                "hh_asset_key", "hv_asset_key",
            ]
        ].to_string(index=False)
    )

    if status != "PASS":
        raise RuntimeError(
            "C2U-F did not satisfy freeze criteria; inspect outputs."
        )


if __name__ == "__main__":
    main()

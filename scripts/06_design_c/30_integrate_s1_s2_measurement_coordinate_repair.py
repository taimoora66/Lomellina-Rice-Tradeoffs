"""Design C — C2Q-R coordinate-key repair for S1/S2 integration.

Why this revision exists
------------------------
C2Q initially joined Sentinel-1 ricept_<n> IDs to Sentinel-2 support_id values.
Those integer IDs were created under different row-order conventions, so equal
integers did not necessarily identify the same geographic support coordinate.

This revision joins on the actual RiceFloodIT support coordinates instead.
The coordinate mapping is validated before any cross-sensor summaries are made.

No groundwater, irrigation-flow outcome, RiceFloodIT flood outcome, threshold,
classifier, or association model is read/fitted.

Run:
python -u scripts/06_design_c/30_integrate_s1_s2_measurement_coordinate_repair.py
"""

from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "outputs" / "diagnostics" / "design_c"

S1 = D / "c2or_scene_point_noise_corrected_samples.csv"
S2 = D / "c2pc2_sentinel2_boa_point_samples.csv"

OUT_MAP = D / "c2qr_support_coordinate_crosswalk.csv"
OUT_COLLAPSED = D / "c2qr_s1_point_polarization_collapsed.csv"
OUT_MATCHED = D / "c2qr_s1_s2_point_matched.csv"
OUT_TARGET = D / "c2qr_target_cross_sensor_summary.csv"
OUT_CORR = D / "c2qr_target_cross_sensor_correlations.csv"
OUT_PHASE = D / "c2qr_phase_cross_sensor_summary.csv"
OUT_QA = D / "c2qr_cross_sensor_qa.json"
OUT_TXT = D / "c2qr_cross_sensor_summary.txt"

EXPECTED_TARGETS = 14
EXPECTED_SUPPORT = 4331
COORD_DECIMALS = 9

SAR = ["VV_db", "VH_db", "VV_minus_VH_db"]
OPT = ["NDVI", "NDWI", "MNDWI", "LSWI"]

def make_target_id(df):
    return (
        pd.to_numeric(df["anchor_year"], errors="raise").astype(int).astype(str)
        + "|" + df["season_phase"].astype(str)
        + "|" + df["selected_date"].astype(str)
        + "|" + df["orbit_state"].astype(str)
        + "|" + pd.to_numeric(df["relative_orbit"], errors="raise").astype(int).astype(str)
    )

def parse_ricept(x):
    m = re.fullmatch(r"ricept_(\d+)", str(x))
    if not m:
        raise ValueError(f"Unexpected S1 point_id: {x!r}")
    return int(m.group(1))

def coord_key(lon, lat):
    return (
        pd.to_numeric(lon, errors="coerce").round(COORD_DECIMALS).astype(str)
        + "|"
        + pd.to_numeric(lat, errors="coerce").round(COORD_DECIMALS).astype(str)
    )

def med(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(x.median()) if len(x) else np.nan

def quant(x, p):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(x.quantile(p)) if len(x) else np.nan

def corr_safe(x, y, method):
    z = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(z) < 10 or z["x"].nunique() < 2 or z["y"].nunique() < 2:
        return np.nan, len(z)
    return float(z["x"].corr(z["y"], method=method)), len(z)

def main():
    print("DESIGN C - C2Q-R S1/S2 COORDINATE-KEY REPAIR")
    print("=" * 78)
    print("Join key: actual RiceFloodIT support lon/lat, not integer row IDs.")
    print(f"Coordinate key rounding: {COORD_DECIMALS} decimal degrees.")
    print("No groundwater. No flood outcome. No threshold. No classifier.\n")

    for f in [S1, S2]:
        if not f.exists():
            raise FileNotFoundError(f)

    s1 = pd.read_csv(S1)
    s2 = pd.read_csv(S2)

    req1 = {
        "anchor_year","season_phase","selected_date","orbit_state","relative_orbit",
        "canonical_scene_id","polarization","point_id","lon","lat",
        "sigma0_noise_corrected_linear"
    }
    req2 = {
        "target_id","support_id","lon","lat","anchor_year","season_phase",
        "s1_selected_date","optical_date","optical_usable_base",
        "NDVI","NDWI","MNDWI","LSWI",
        "NDVI_valid","NDWI_valid","MNDWI_valid","LSWI_valid"
    }
    if req1 - set(s1.columns):
        raise AssertionError(f"S1 missing: {sorted(req1-set(s1.columns))}")
    if req2 - set(s2.columns):
        raise AssertionError(f"S2 missing: {sorted(req2-set(s2.columns))}")

    s2["support_id"] = pd.to_numeric(s2["support_id"], errors="raise").astype(int)
    s2["coord_key"] = coord_key(s2["lon"], s2["lat"])

    tids = sorted(s2["target_id"].astype(str).unique())
    if len(tids) != EXPECTED_TARGETS:
        raise AssertionError(f"Expected {EXPECTED_TARGETS} S2 targets; found {len(tids)}")

    # Coordinate universe must be identical across all S2 targets.
    s2_universe = (
        s2[["coord_key","support_id","lon","lat"]]
        .drop_duplicates()
        .sort_values("coord_key")
    )
    if s2_universe["coord_key"].nunique() != EXPECTED_SUPPORT:
        raise AssertionError(
            f"Expected {EXPECTED_SUPPORT} unique S2 coordinate keys; "
            f"found {s2_universe['coord_key'].nunique()}"
        )

    # One S2 support_id must map to exactly one coordinate, and vice versa.
    if s2_universe.groupby("support_id")["coord_key"].nunique().max() != 1:
        raise AssertionError("S2 support_id maps to multiple coordinates.")
    if s2_universe.groupby("coord_key")["support_id"].nunique().max() != 1:
        raise AssertionError("S2 coordinate maps to multiple support_ids.")

    s1["target_id"] = make_target_id(s1)
    s1["s1_point_index"] = s1["point_id"].map(parse_ricept)
    s1["coord_key"] = coord_key(s1["lon"], s1["lat"])
    s1["polarization"] = s1["polarization"].astype(str).str.upper()
    s1["sigma0_noise_corrected_linear"] = pd.to_numeric(
        s1["sigma0_noise_corrected_linear"], errors="coerce"
    )
    s1 = s1[s1["target_id"].isin(tids)].copy()

    missing_targets = sorted(set(tids) - set(s1["target_id"].unique()))
    if missing_targets:
        raise AssertionError(f"S1 missing matched targets: {missing_targets}")

    s1_universe = (
        s1[["coord_key","s1_point_index","point_id","lon","lat"]]
        .drop_duplicates()
        .sort_values("coord_key")
    )

    if s1_universe["coord_key"].nunique() != EXPECTED_SUPPORT:
        raise AssertionError(
            f"Expected {EXPECTED_SUPPORT} unique S1 coordinate keys; "
            f"found {s1_universe['coord_key'].nunique()}"
        )

    s1_keys = set(s1_universe["coord_key"])
    s2_keys = set(s2_universe["coord_key"])
    missing_in_s1 = sorted(s2_keys - s1_keys)
    missing_in_s2 = sorted(s1_keys - s2_keys)

    if missing_in_s1 or missing_in_s2:
        raise AssertionError(
            f"Coordinate universes differ: missing_in_s1={len(missing_in_s1)}, "
            f"missing_in_s2={len(missing_in_s2)}"
        )

    # Explicit crosswalk documents that the numeric IDs are different conventions.
    crosswalk = (
        s1_universe[["coord_key","s1_point_index","point_id","lon","lat"]]
        .drop_duplicates("coord_key")
        .merge(
            s2_universe[["coord_key","support_id"]].drop_duplicates("coord_key"),
            on="coord_key",
            how="inner",
            validate="one_to_one",
        )
        .sort_values("support_id")
    )
    crosswalk["numeric_id_equal"] = (
        crosswalk["s1_point_index"].astype(int) == crosswalk["support_id"].astype(int)
    )
    crosswalk.to_csv(OUT_MAP, index=False)

    id_equal_n = int(crosswalk["numeric_id_equal"].sum())
    id_equal_share = float(crosswalk["numeric_id_equal"].mean())

    # Collapse S1 scene overlaps in linear power.
    keys = [
        "target_id","anchor_year","season_phase","selected_date",
        "orbit_state","relative_orbit","polarization","coord_key"
    ]
    rows = []
    for key, g in s1.groupby(keys, sort=True):
        r = dict(zip(keys, key))
        x = pd.to_numeric(g["sigma0_noise_corrected_linear"], errors="coerce")
        x = x[np.isfinite(x) & (x > 0)]
        lin = float(x.median()) if len(x) else np.nan

        r["scene_rows_n"] = int(len(g))
        r["unique_scene_ids_n"] = int(g["canonical_scene_id"].nunique())
        r["positive_finite_scene_values_n"] = int(len(x))
        r["sigma0_noise_corrected_linear_median"] = lin
        r["sigma0_noise_corrected_db"] = (
            float(10*np.log10(lin)) if np.isfinite(lin) and lin > 0 else np.nan
        )
        r["lon_s1"] = med(g["lon"])
        r["lat_s1"] = med(g["lat"])
        rows.append(r)

    c = pd.DataFrame(rows)
    c.to_csv(OUT_COLLAPSED, index=False)

    if c.duplicated(["target_id","coord_key","polarization"]).any():
        raise AssertionError("Duplicate S1 target/coordinate/polarization after collapse.")

    val = c.pivot(
        index=["target_id","coord_key"],
        columns="polarization",
        values="sigma0_noise_corrected_db",
    ).reset_index().rename(columns={"VV":"VV_db","VH":"VH_db"})

    scenes = c.pivot(
        index=["target_id","coord_key"],
        columns="polarization",
        values="unique_scene_ids_n",
    ).reset_index().rename(columns={"VV":"VV_scene_ids_n","VH":"VH_scene_ids_n"})

    coords = (
        c.groupby(["target_id","coord_key"], as_index=False)
        .agg(lon_s1=("lon_s1","median"), lat_s1=("lat_s1","median"))
    )

    w = val.merge(
        scenes, on=["target_id","coord_key"], how="outer", validate="one_to_one"
    ).merge(
        coords, on=["target_id","coord_key"], how="outer", validate="one_to_one"
    )

    for col in ["VV_db","VH_db"]:
        if col not in w.columns:
            w[col] = np.nan

    w["VV_minus_VH_db"] = w["VV_db"] - w["VH_db"]
    w["s1_dualpol_valid"] = np.isfinite(w["VV_db"]) & np.isfinite(w["VH_db"])

    # Join by target + actual coordinate.
    s2j = s2.rename(columns={"lon":"lon_s2","lat":"lat_s2"})
    m = s2j.merge(
        w,
        on=["target_id","coord_key"],
        how="left",
        validate="one_to_one",
    )

    expected_rows = EXPECTED_TARGETS * EXPECTED_SUPPORT
    if len(m) != expected_rows:
        raise AssertionError(f"Expected {expected_rows} matched rows; found {len(m)}")

    have_both_coords = (
        np.isfinite(m["lon_s1"]) & np.isfinite(m["lat_s1"]) &
        np.isfinite(m["lon_s2"]) & np.isfinite(m["lat_s2"])
    )
    m["coord_abs_diff_lon"] = np.where(
        have_both_coords, abs(m["lon_s1"] - m["lon_s2"]), np.nan
    )
    m["coord_abs_diff_lat"] = np.where(
        have_both_coords, abs(m["lat_s1"] - m["lat_s2"]), np.nan
    )
    maxdiff = float(np.nanmax(np.r_[
        m["coord_abs_diff_lon"].to_numpy(float),
        m["coord_abs_diff_lat"].to_numpy(float)
    ]))

    # Rounding key is only a join aid; exact stored coordinates should still agree.
    if maxdiff > 5e-9:
        raise AssertionError(f"Coordinate-key join has excessive exact-coordinate difference {maxdiff}")

    m["joint_base_valid"] = (
        m["s1_dualpol_valid"].fillna(False).astype(bool)
        & m["optical_usable_base"].fillna(False).astype(bool)
    )
    m.to_csv(OUT_MATCHED, index=False)

    # Target summaries.
    target_rows = []
    for tid, g in m.groupby("target_id", sort=True):
        r = {
            "target_id": tid,
            "anchor_year": int(g["anchor_year"].iloc[0]),
            "season_phase": g["season_phase"].iloc[0],
            "s1_selected_date": g["s1_selected_date"].iloc[0],
            "optical_date": g["optical_date"].iloc[0],
            "support_n": int(len(g)),
            "s1_dualpol_valid_n": int(g["s1_dualpol_valid"].fillna(False).sum()),
            "s1_dualpol_valid_share": float(g["s1_dualpol_valid"].fillna(False).mean()),
            "optical_usable_base_n": int(g["optical_usable_base"].sum()),
            "optical_usable_base_share": float(g["optical_usable_base"].mean()),
            "joint_base_valid_n": int(g["joint_base_valid"].sum()),
            "joint_base_valid_share": float(g["joint_base_valid"].mean()),
        }
        gj = g[g["joint_base_valid"]]
        for v in SAR + OPT:
            r[f"{v}_median_joint"] = med(gj[v])
            r[f"{v}_p10_joint"] = quant(gj[v], .10)
            r[f"{v}_p90_joint"] = quant(gj[v], .90)
        target_rows.append(r)

    ts = pd.DataFrame(target_rows).sort_values(
        ["anchor_year","s1_selected_date","target_id"]
    )
    ts.to_csv(OUT_TARGET, index=False)

    # Descriptive cross-sensor correlations; never a QA gate.
    corr_rows = []
    for tid, g in m.groupby("target_id", sort=True):
        gj = g[g["joint_base_valid"]]
        for sv in SAR:
            for ov in OPT:
                gg = gj[gj[f"{ov}_valid"].fillna(False).astype(bool)]
                pr, n1 = corr_safe(gg[sv], gg[ov], "pearson")
                sr, n2 = corr_safe(gg[sv], gg[ov], "spearman")
                corr_rows.append({
                    "target_id": tid,
                    "anchor_year": int(g["anchor_year"].iloc[0]),
                    "season_phase": g["season_phase"].iloc[0],
                    "s1_selected_date": g["s1_selected_date"].iloc[0],
                    "optical_date": g["optical_date"].iloc[0],
                    "sar_variable": sv,
                    "optical_variable": ov,
                    "paired_n": int(min(n1,n2)),
                    "pearson_r": pr,
                    "spearman_rho": sr,
                })
    pd.DataFrame(corr_rows).to_csv(OUT_CORR, index=False)

    # Phase summaries use target medians as the unit, not thousands of points.
    phase_rows = []
    for phase, g in ts.groupby("season_phase", sort=True):
        r = {
            "season_phase": phase,
            "targets_n": int(len(g)),
            "years_n": int(g["anchor_year"].nunique()),
            "joint_base_valid_share_median_across_targets": med(g["joint_base_valid_share"]),
        }
        for v in SAR + OPT:
            x = pd.to_numeric(g[f"{v}_median_joint"], errors="coerce").dropna()
            r[f"{v}_target_median_of_medians"] = float(x.median()) if len(x) else np.nan
            r[f"{v}_target_median_min"] = float(x.min()) if len(x) else np.nan
            r[f"{v}_target_median_max"] = float(x.max()) if len(x) else np.nan
        phase_rows.append(r)

    phase = pd.DataFrame(phase_rows)
    phase.to_csv(OUT_PHASE, index=False)

    structural = {
        "targets_ok": int(m["target_id"].nunique()) == EXPECTED_TARGETS,
        "rows_ok": len(m) == expected_rows,
        "support_ok": bool(
            (m.groupby("target_id")["coord_key"].nunique() == EXPECTED_SUPPORT).all()
        ),
        "coordinate_universes_identical": not missing_in_s1 and not missing_in_s2,
        "exact_coordinate_difference_ok": maxdiff <= 5e-9,
        "duplicates_ok": not m.duplicated(["target_id","coord_key"]).any(),
        "both_polarizations_present": bool(
            m["VV_db"].notna().any() and m["VH_db"].notna().any()
        ),
    }

    status = "PASS" if all(structural.values()) else "FAIL"

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2QR_CROSS_SENSOR_COORDINATE_KEY_REPAIR",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        **structural,
        "coordinate_key_decimal_places": COORD_DECIMALS,
        "crosswalk_rows_n": int(len(crosswalk)),
        "numeric_ids_equal_n": id_equal_n,
        "numeric_ids_equal_share": id_equal_share,
        "max_abs_exact_coordinate_difference_degrees": maxdiff,
        "targets_n": int(m["target_id"].nunique()),
        "rows_n": int(len(m)),
        "s1_scene_rows_input_n": int(len(s1)),
        "s1_collapsed_target_point_pol_rows_n": int(len(c)),
        "s1_multi_scene_target_point_pol_rows_n": int((c["unique_scene_ids_n"] > 1).sum()),
        "s1_missing_positive_finite_target_point_pol_n": int(
            c["sigma0_noise_corrected_linear_median"].isna().sum()
        ),
        "joint_base_valid_rows_n": int(m["joint_base_valid"].sum()),
        "joint_base_valid_share": float(m["joint_base_valid"].mean()),
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "ricefloodit_flood_outcomes_read": False,
        "inundation_threshold_selected": False,
        "classifier_fitted": False,
        "association_models_fitted": 0,
        "scientific_correlation_results_used_as_pass_fail_gate": False,
    }
    OUT_QA.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    text = "\n".join([
        "DESIGN C - C2Q-R S1/S2 COORDINATE-KEY REPAIR",
        "="*78,
        "",
        f"Targets: {qa['targets_n']}",
        f"Matched support rows: {qa['rows_n']}",
        f"Coordinate crosswalk rows: {qa['crosswalk_rows_n']}",
        f"Numeric S1/S2 IDs equal for only: {id_equal_n}/{len(crosswalk)} "
        f"({id_equal_share:.6f})",
        f"Max exact coordinate difference after coordinate-key join: {maxdiff:.12g} degrees",
        f"S1 scene-point rows (14 targets): {qa['s1_scene_rows_input_n']}",
        f"S1 collapsed target-point-pol rows: {qa['s1_collapsed_target_point_pol_rows_n']}",
        f"S1 target-point-pol rows with >1 scene: {qa['s1_multi_scene_target_point_pol_rows_n']}",
        f"S1 target-point-pol rows missing positive finite corrected sigma0: "
        f"{qa['s1_missing_positive_finite_target_point_pol_n']}",
        f"Joint S1-dualpol + S2-base-valid rows: {qa['joint_base_valid_rows_n']}",
        f"Joint valid share: {qa['joint_base_valid_share']:.6f}",
        "",
        "The failed C2Q integer-ID join is retained as an audit finding:",
        "ricept_<n> and C2P-C2 support_id encode different row-order conventions.",
        "C2Q-R uses actual coordinates and explicitly verifies a one-to-one universe.",
        "",
        "No groundwater / flow / RiceFloodIT flood outcome read.",
        "No threshold or classifier fitted.",
        "Correlation results are descriptive and do not determine PASS.",
        "",
        f"C2Q-R STATUS: {status}",
    ]) + "\n"
    OUT_TXT.write_text(text, encoding="utf-8")

    print(text)
    print("TARGET CROSS-SENSOR SUMMARY")
    print("---------------------------")
    pd.set_option("display.width", 320)
    print(ts.to_string(index=False))
    print()
    print("PHASE CROSS-SENSOR SUMMARY")
    print("--------------------------")
    print(phase.to_string(index=False))

    if status != "PASS":
        raise RuntimeError("C2Q-R failed structural QA; inspect outputs.")

if __name__ == "__main__":
    main()

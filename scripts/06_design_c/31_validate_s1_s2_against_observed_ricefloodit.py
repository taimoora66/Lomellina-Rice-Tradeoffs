"""Design C — C2R observed RiceFloodIT construct-validation bridge.

Purpose
-------
Use observed RiceFloodIT annual flooding frequency (FF) as an EXTERNAL
measurement benchmark for the already-built S1/S2 cross-sensor table.

This stage does NOT:
- read groundwater;
- read irrigation-flow outcomes;
- use post-2021 reconstructed FF as a validation label;
- fit a flood/no-flood classifier;
- select an inundation threshold;
- optimize feature combinations;
- use p-values;
- alter the 14 outcome-blind S1/S2 target dates.

The benchmark is descriptive/construct-validity only:
1. join observed RiceFloodIT FF to cross-sensor points for years where observed
   FF exists;
2. calculate Spearman rank associations between FF and each prespecified
   single sensor variable;
3. summarize sensor variables across within-year FF quartiles;
4. report direction consistency across target dates without using the result
   as a technical PASS/FAIL gate.

Primary prespecified sensor variables
-------------------------------------
S1:
    VV_db
    VH_db
    VV_minus_VH_db
S2:
    NDVI
    NDWI
    MNDWI
    LSWI

No composite score is fitted here.

Run from repository root
------------------------
python -u scripts/06_design_c/31_validate_s1_s2_against_observed_ricefloodit.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "outputs" / "diagnostics" / "design_c"

CROSS_IN = DIAG / "c2qr_s1_s2_point_matched.csv"

OUT_JOINED = DIAG / "c2r_observed_ff_cross_sensor_joined.csv"
OUT_ASSOC = DIAG / "c2r_observed_ff_sensor_rank_associations.csv"
OUT_QUARTILES = DIAG / "c2r_observed_ff_quartile_sensor_summary.csv"
OUT_TARGET = DIAG / "c2r_observed_ff_target_summary.csv"
OUT_QA = DIAG / "c2r_observed_ff_construct_validation_qa.json"
OUT_TXT = DIAG / "c2r_observed_ff_construct_validation_summary.txt"

COORD_DECIMALS = 9
SENSOR_VARS = [
    "VV_db",
    "VH_db",
    "VV_minus_VH_db",
    "NDVI",
    "NDWI",
    "MNDWI",
    "LSWI",
]


def coord_key(lon, lat):
    return (
        pd.to_numeric(lon, errors="coerce").round(COORD_DECIMALS).astype(str)
        + "|"
        + pd.to_numeric(lat, errors="coerce").round(COORD_DECIMALS).astype(str)
    )


def med(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(x.median()) if len(x) else np.nan


def q(x, p):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(x.quantile(p)) if len(x) else np.nan


def spearman(x, y):
    z = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(z) < 20 or z["x"].nunique() < 2 or z["y"].nunique() < 2:
        return np.nan, int(len(z))
    return float(z["x"].corr(z["y"], method="spearman")), int(len(z))


def find_ricefloodit_georef():
    """Find a unique plausible observed RiceFloodIT georeferenced FF table."""
    preferred = [
        ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv",
        ROOT / "data" / "processed" / "ricefloodit_georef.csv",
        ROOT / "data" / "raw" / "RiceFloodIT" / "ricefloodit_georef.csv",
        ROOT / "data" / "raw" / "ricefloodit_georef.csv",
    ]
    existing = [p for p in preferred if p.exists()]
    if existing:
        return existing[0]

    hits = sorted(ROOT.rglob("ricefloodit_georef.csv"))
    if not hits:
        raise FileNotFoundError(
            "Could not find ricefloodit_georef.csv anywhere under repository root."
        )
    if len(hits) > 1:
        print("Multiple ricefloodit_georef.csv files found:")
        for p in hits:
            print(f"  {p}")
        print(f"Using first lexicographically: {hits[0]}")
    return hits[0]


def ff_quartile_within_year(g):
    """Outcome-blind descriptive FF quartiles; ties may reduce category count."""
    x = pd.to_numeric(g["ff"], errors="coerce")
    valid = x.notna()
    out = pd.Series(pd.NA, index=g.index, dtype="Int64")
    if valid.sum() < 4 or x[valid].nunique() < 2:
        return out

    # Rank first so qcut is deterministic despite many tied FF values.
    ranks = x[valid].rank(method="average", pct=True)
    vals = np.ceil(ranks * 4).clip(1, 4).astype(int)
    out.loc[valid] = vals.astype("Int64")
    return out


def main():
    print("DESIGN C - C2R OBSERVED RICEFLOODIT CONSTRUCT-VALIDATION BRIDGE")
    print("=" * 78)
    print("Benchmark: observed RiceFloodIT annual FF only.")
    print("No groundwater. No flow outcome. No classifier. No threshold. No p-values.\n")

    if not CROSS_IN.exists():
        raise FileNotFoundError(CROSS_IN)

    ff_path = find_ricefloodit_georef()
    print(f"Observed RiceFloodIT source: {ff_path}")

    x = pd.read_csv(CROSS_IN)
    ff = pd.read_csv(ff_path)

    req_x = {
        "target_id", "anchor_year", "season_phase", "s1_selected_date",
        "optical_date", "support_id", "lon_s2", "lat_s2",
        "joint_base_valid", *SENSOR_VARS,
        "NDVI_valid", "NDWI_valid", "MNDWI_valid", "LSWI_valid",
    }
    missing_x = sorted(req_x - set(x.columns))
    if missing_x:
        raise AssertionError(f"Cross-sensor input missing columns: {missing_x}")

    # Accept a few common capitalization variants but do not guess semantics.
    lower = {c.lower(): c for c in ff.columns}
    required_ff_names = ["year", "ff", "lon", "lat"]
    absent = [c for c in required_ff_names if c not in lower]
    if absent:
        raise AssertionError(
            f"RiceFloodIT table must contain year, ff, lon, lat. "
            f"Missing: {absent}. Columns are: {list(ff.columns)}"
        )
    ff = ff.rename(columns={lower[k]: k for k in required_ff_names})

    ff["year"] = pd.to_numeric(ff["year"], errors="coerce").astype("Int64")
    ff["ff"] = pd.to_numeric(ff["ff"], errors="coerce")
    ff["coord_key"] = coord_key(ff["lon"], ff["lat"])

    x["anchor_year"] = pd.to_numeric(x["anchor_year"], errors="raise").astype(int)
    x["coord_key"] = coord_key(x["lon_s2"], x["lat_s2"])

    # This table is supposed to be observed RiceFloodIT support; preserve only
    # finite annual FF rows and collapse exact duplicate coordinate/year rows
    # only when they agree.
    f = ff[ff["year"].notna() & ff["ff"].notna()].copy()
    f["year"] = f["year"].astype(int)

    disagreement = (
        f.groupby(["year", "coord_key"])["ff"].nunique(dropna=True)
        .reset_index(name="ff_unique_n")
    )
    bad = disagreement[disagreement["ff_unique_n"] > 1]
    if len(bad):
        raise AssertionError(
            f"Observed RiceFloodIT has conflicting FF values for "
            f"{len(bad)} year/coordinate keys."
        )

    f = (
        f.groupby(["year", "coord_key"], as_index=False)
        .agg(
            ff=("ff", "first"),
            ff_lon=("lon", "first"),
            ff_lat=("lat", "first"),
        )
    )

    observed_years = sorted(f["year"].unique().tolist())
    candidate_target_years = sorted(set(x["anchor_year"]) & set(observed_years))

    if not candidate_target_years:
        raise AssertionError(
            f"No overlap between cross-sensor years {sorted(x.anchor_year.unique())} "
            f"and observed RiceFloodIT years {observed_years}"
        )

    print(f"Observed FF years available: {observed_years}")
    print(f"Cross-sensor target years with observed FF: {candidate_target_years}")

    # Only observed-overlap years become labelled construct-validation targets.
    xl = x[x["anchor_year"].isin(candidate_target_years)].copy()

    joined = xl.merge(
        f,
        left_on=["anchor_year", "coord_key"],
        right_on=["year", "coord_key"],
        how="left",
        validate="many_to_one",
    )

    joined["ff_available"] = joined["ff"].notna()
    joined["ff_quartile_within_year"] = (
        joined.groupby("anchor_year", group_keys=False)
        .apply(ff_quartile_within_year)
        .sort_index()
    )

    # Exact coordinate QA.
    have = joined["ff_available"]
    joined["ff_coord_abs_diff_lon"] = np.where(
        have,
        np.abs(
            pd.to_numeric(joined["lon_s2"], errors="coerce")
            - pd.to_numeric(joined["ff_lon"], errors="coerce")
        ),
        np.nan,
    )
    joined["ff_coord_abs_diff_lat"] = np.where(
        have,
        np.abs(
            pd.to_numeric(joined["lat_s2"], errors="coerce")
            - pd.to_numeric(joined["ff_lat"], errors="coerce")
        ),
        np.nan,
    )
    max_coord_diff = float(
        np.nanmax(
            np.r_[
                joined["ff_coord_abs_diff_lon"].to_numpy(float),
                joined["ff_coord_abs_diff_lat"].to_numpy(float),
            ]
        )
    )

    joined.to_csv(OUT_JOINED, index=False)

    # Target-level benchmark coverage.
    target_rows = []
    for tid, g in joined.groupby("target_id", sort=True):
        ffvals = pd.to_numeric(g["ff"], errors="coerce")
        gj = g[g["joint_base_valid"].fillna(False).astype(bool) & g["ff_available"]]
        r = {
            "target_id": tid,
            "anchor_year": int(g["anchor_year"].iloc[0]),
            "season_phase": g["season_phase"].iloc[0],
            "s1_selected_date": g["s1_selected_date"].iloc[0],
            "optical_date": g["optical_date"].iloc[0],
            "support_n": int(len(g)),
            "ff_available_n": int(g["ff_available"].sum()),
            "ff_available_share": float(g["ff_available"].mean()),
            "ff_unique_n": int(ffvals.nunique(dropna=True)),
            "ff_min": float(ffvals.min()) if ffvals.notna().any() else np.nan,
            "ff_median": med(ffvals),
            "ff_max": float(ffvals.max()) if ffvals.notna().any() else np.nan,
            "joint_ff_sensor_valid_n": int(len(gj)),
            "joint_ff_sensor_valid_share": float(len(gj) / len(g)),
        }
        target_rows.append(r)

    target_summary = pd.DataFrame(target_rows).sort_values(
        ["anchor_year", "s1_selected_date", "target_id"]
    )
    target_summary.to_csv(OUT_TARGET, index=False)

    # Prespecified single-variable rank associations.
    assoc_rows = []
    for tid, g in joined.groupby("target_id", sort=True):
        base = g[
            g["joint_base_valid"].fillna(False).astype(bool)
            & g["ff_available"]
        ].copy()

        for v in SENSOR_VARS:
            gv = base.copy()
            if v in ["NDVI", "NDWI", "MNDWI", "LSWI"]:
                gv = gv[gv[f"{v}_valid"].fillna(False).astype(bool)]

            rho, n = spearman(gv["ff"], gv[v])
            assoc_rows.append(
                {
                    "target_id": tid,
                    "anchor_year": int(g["anchor_year"].iloc[0]),
                    "season_phase": g["season_phase"].iloc[0],
                    "s1_selected_date": g["s1_selected_date"].iloc[0],
                    "optical_date": g["optical_date"].iloc[0],
                    "sensor_variable": v,
                    "paired_n": int(n),
                    "spearman_rho_ff_sensor": rho,
                    "absolute_rho": abs(rho) if np.isfinite(rho) else np.nan,
                }
            )

    assoc = pd.DataFrame(assoc_rows)
    assoc.to_csv(OUT_ASSOC, index=False)

    # Quartile summaries for visual/monotonic interpretation. Quartiles are
    # defined solely from observed FF within year, not from sensor variables.
    quartile_rows = []
    jq = joined[
        joined["joint_base_valid"].fillna(False).astype(bool)
        & joined["ff_available"]
        & joined["ff_quartile_within_year"].notna()
    ].copy()

    for (tid, fq), g in jq.groupby(
        ["target_id", "ff_quartile_within_year"], sort=True
    ):
        r = {
            "target_id": tid,
            "anchor_year": int(g["anchor_year"].iloc[0]),
            "season_phase": g["season_phase"].iloc[0],
            "s1_selected_date": g["s1_selected_date"].iloc[0],
            "optical_date": g["optical_date"].iloc[0],
            "ff_quartile_within_year": int(fq),
            "n": int(len(g)),
            "ff_median": med(g["ff"]),
            "ff_p10": q(g["ff"], .10),
            "ff_p90": q(g["ff"], .90),
        }
        for v in SENSOR_VARS:
            gg = g
            if v in ["NDVI", "NDWI", "MNDWI", "LSWI"]:
                gg = g[g[f"{v}_valid"].fillna(False).astype(bool)]
            r[f"{v}_n"] = int(pd.to_numeric(gg[v], errors="coerce").notna().sum())
            r[f"{v}_median"] = med(gg[v])
        quartile_rows.append(r)

    quart = pd.DataFrame(quartile_rows)
    quart.to_csv(OUT_QUARTILES, index=False)

    # Structural QA only. Association magnitude/sign is never a PASS gate.
    expected_labelled_targets = int(
        x[x["anchor_year"].isin(candidate_target_years)]["target_id"].nunique()
    )
    labelled_targets_n = int(joined["target_id"].nunique())
    ff_coverage_min = float(target_summary["ff_available_share"].min())
    ff_coordinate_ok = max_coord_diff <= 5e-9

    structural = {
        "cross_sensor_input_exists": True,
        "observed_ff_source_exists": True,
        "observed_overlap_years_n": len(candidate_target_years) > 0,
        "labelled_targets_expected_n": expected_labelled_targets,
        "labelled_targets_actual_n": labelled_targets_n,
        "all_labelled_targets_retained": labelled_targets_n == expected_labelled_targets,
        "ff_coordinate_alignment_ok": ff_coordinate_ok,
        "ff_available_for_at_least_one_point_each_target": bool(
            (target_summary["ff_available_n"] > 0).all()
        ),
    }

    status = "PASS" if (
        structural["all_labelled_targets_retained"]
        and structural["ff_coordinate_alignment_ok"]
        and structural["ff_available_for_at_least_one_point_each_target"]
    ) else "FAIL"

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2R_OBSERVED_RICEFLOODIT_CONSTRUCT_VALIDATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "observed_ff_source": str(ff_path.relative_to(ROOT)),
        "observed_ff_years_available": observed_years,
        "cross_sensor_years_with_observed_ff": candidate_target_years,
        "max_abs_coordinate_difference_degrees": max_coord_diff,
        "minimum_target_observed_ff_coverage_share": ff_coverage_min,
        **structural,
        "sensor_variables_prespecified": SENSOR_VARS,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "post2021_reconstructed_ff_used_as_label": False,
        "flood_classifier_fitted": False,
        "inundation_threshold_selected": False,
        "composite_sensor_score_optimized": False,
        "p_values_computed": False,
        "association_magnitude_or_sign_used_as_pass_fail_gate": False,
    }
    OUT_QA.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    # Concise terminal report.
    lines = [
        "DESIGN C - C2R OBSERVED RICEFLOODIT CONSTRUCT-VALIDATION BRIDGE",
        "=" * 78,
        "",
        f"Observed FF source: {qa['observed_ff_source']}",
        f"Observed FF years: {observed_years}",
        f"Cross-sensor labelled years: {candidate_target_years}",
        f"Labelled targets: {labelled_targets_n}",
        f"Minimum target observed-FF coverage: {ff_coverage_min:.6f}",
        f"Max FF/S2 coordinate difference: {max_coord_diff:.12g} degrees",
        "",
        "FIREWALL",
        "--------",
        "Groundwater read: False",
        "Irrigation-flow outcome read: False",
        "Post-2021 reconstructed FF used as label: False",
        "Flood classifier fitted: False",
        "Inundation threshold selected: False",
        "Composite score optimized: False",
        "p-values computed: False",
        "",
        "Association signs/magnitudes are construct-validation diagnostics only.",
        f"C2R STATUS: {status}",
    ]
    txt = "\n".join(lines) + "\n"
    OUT_TXT.write_text(txt, encoding="utf-8")
    print("\n" + txt)

    print("TARGET OBSERVED-FF COVERAGE")
    print("---------------------------")
    pd.set_option("display.width", 320)
    print(target_summary.to_string(index=False))

    print()
    print("PRESPECIFIED FF-SENSOR SPEARMAN ASSOCIATIONS")
    print("--------------------------------------------")
    print(
        assoc[
            [
                "target_id",
                "sensor_variable",
                "paired_n",
                "spearman_rho_ff_sensor",
            ]
        ].to_string(index=False)
    )

    if status != "PASS":
        raise RuntimeError("C2R failed structural QA; inspect outputs.")


if __name__ == "__main__":
    main()

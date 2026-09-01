"""Stage 6R — Independent replication of identification/information audit.

This is an independent audit of Stage 6, not a model-search stage.

It performs:
1. Manual Frisch-Waugh-Lovell (FWL) replication of the frozen Stage-5 beta
   without statsmodels formula regression.
2. Independent partial-leverage / information-concentration replication.
3. Squared-CV partial-leverage heterogeneity diagnostic Vs(L), appropriate
   for interpreting effective-cluster heterogeneity with cluster fixed effects.
4. Independent leave-one-well coefficient reconstruction.
5. Matched-scale historical validation:
   observed RiceFloodIT FF and bridge-predicted FF are aggregated to the exact
   same 10-km well geometry for the same 12 wells, then residualized by well
   and year fixed effects before comparing errors to the post-2021 identifying
   FF10 scale.

No Stage-5 model, sample, exposure radius, baseline, or inference rule is changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]

PANEL_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "post2021_primary_balanced_panel_2022_2025.csv"
)
STAGE5_RESULT_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage5_primary_groundwater_result_2022_2025.csv"
)
STAGE6_CLUSTER_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage6_cluster_information_diagnostics.csv"
)
STAGE6_QA_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage6_identification_information_qa.json"
)

GW_META_IN = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "groundwater_station_metadata.csv"
)
RICE_GEO_IN = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "ricefloodit_georef.csv"
)
BRIDGE_PREDICTIONS_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "bounded_bridge_predictions_2014_2021.csv"
)

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

FWL_OUT = OUT_DIR / "stage6r_independent_fwl_replication.csv"
LEVERAGE_OUT = OUT_DIR / "stage6r_independent_partial_leverage.csv"
LOO_OUT = OUT_DIR / "stage6r_independent_leave_one_well_out.csv"
MATCHED_PANEL_OUT = OUT_DIR / "stage6r_matched_scale_validation_panel_2014_2016.csv"
MATCHED_SUMMARY_OUT = OUT_DIR / "stage6r_matched_scale_validation_summary.csv"
CROSSCHECK_OUT = OUT_DIR / "stage6r_stage6_crosscheck.csv"
QA_OUT = OUT_DIR / "stage6r_replication_qa.json"
REPORT_OUT = OUT_DIR / "stage6r_replication_summary.txt"

YEARS = (2022, 2023, 2024, 2025)
VALIDATION_YEARS = (2014, 2015, 2016)
EXPECTED_WELLS = 12
EXPECTED_ROWS = 48
RADIUS_M = 10_000.0

OUTCOME = "gw_aug_nearest_aug23_m"
EXPOSURE = "ff10_anomaly_2010_2021"
ANTECEDENT = "gw_pre_last_janfeb_m"

TOL_BETA = 1e-10
TOL_SHARE = 1e-10
TOL_STAGE6 = 1e-10


def require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def design_matrix(
    d: pd.DataFrame,
    include_antecedent: bool,
) -> np.ndarray:
    """Explicit nuisance design: intercept + A(optional) + well FE + year FE.

    Reference categories are dropped solely to make the nuisance matrix full rank.
    The residual projection is invariant to reference-category choice.
    """
    n = len(d)
    cols = [np.ones(n, dtype=float)]

    if include_antecedent:
        cols.append(d[ANTECEDENT].to_numpy(dtype=float))

    stations = sorted(d["station"].astype(str).unique())
    years = sorted(pd.to_numeric(d["year"]).astype(int).unique())

    for s in stations[1:]:
        cols.append((d["station"].astype(str).to_numpy() == s).astype(float))

    for y in years[1:]:
        cols.append((pd.to_numeric(d["year"]).to_numpy() == y).astype(float))

    z = np.column_stack(cols)

    if np.linalg.matrix_rank(z) != z.shape[1]:
        raise AssertionError("Manual nuisance design is rank deficient.")

    return z


def residualize_manual(v: np.ndarray, z: np.ndarray) -> np.ndarray:
    coef, *_ = np.linalg.lstsq(z, np.asarray(v, dtype=float), rcond=None)
    return np.asarray(v, dtype=float) - z @ coef


def manual_fwl_beta(d: pd.DataFrame) -> tuple[float, np.ndarray, np.ndarray]:
    z = design_matrix(d, include_antecedent=True)

    f = d[EXPOSURE].to_numpy(dtype=float)
    y = d[OUTCOME].to_numpy(dtype=float)

    f_resid = residualize_manual(f, z)
    y_resid = residualize_manual(y, z)

    denom = float(f_resid @ f_resid)
    if denom <= 0:
        raise AssertionError("Manual FWL exposure denominator is non-positive.")

    beta = float((f_resid @ y_resid) / denom)
    return beta, f_resid, y_resid


def manual_fe_residual(
    values: np.ndarray,
    stations: np.ndarray,
    years: np.ndarray,
) -> np.ndarray:
    """Residualize arbitrary values on intercept + station FE + year FE."""
    temp = pd.DataFrame(
        {
            "station": stations.astype(str),
            "year": years.astype(int),
        }
    )
    n = len(temp)
    cols = [np.ones(n, dtype=float)]

    station_levels = sorted(temp["station"].unique())
    year_levels = sorted(temp["year"].unique())

    for s in station_levels[1:]:
        cols.append((temp["station"].to_numpy() == s).astype(float))
    for y in year_levels[1:]:
        cols.append((temp["year"].to_numpy() == y).astype(float))

    z = np.column_stack(cols)
    if np.linalg.matrix_rank(z) != z.shape[1]:
        raise AssertionError("Matched-scale FE design is rank deficient.")

    return residualize_manual(np.asarray(values, dtype=float), z)


def safe_corr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan
    return (
        float(stats.pearsonr(x, y).statistic),
        float(stats.spearmanr(x, y).statistic),
    )


def build_matched_validation(
    primary_stations: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build historical 10-km well-year observed/predicted FF validation.

    Because a cell-specific anomaly baseline is constant across years for a
    fixed well geometry, removing well fixed effects from FF levels removes
    that time-invariant well-specific level. Thus the well+year-FE comparison
    targets the same kind of within-well/interannual information that matters
    for the post-2021 anomaly model, without inventing a new historical baseline.
    """
    require(GW_META_IN, "Groundwater station metadata")
    require(RICE_GEO_IN, "RiceFloodIT georeference")
    require(BRIDGE_PREDICTIONS_IN, "Frozen bridge prediction table")

    wells = pd.read_csv(GW_META_IN)
    wells["station"] = wells["station"].astype(str)
    wells = (
        wells.loc[
            wells["station"].isin(primary_stations),
            ["station", "utm_e", "utm_n"],
        ]
        .drop_duplicates("station")
        .sort_values("station")
        .reset_index(drop=True)
    )

    if len(wells) != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} historical validation well coordinates; "
            f"found {len(wells)}."
        )

    geo = pd.read_csv(RICE_GEO_IN)
    required_geo = {"x", "y", "utm_e", "utm_n"}
    if not required_geo.issubset(geo.columns):
        raise AssertionError(
            f"Georef missing columns: {sorted(required_geo - set(geo.columns))}"
        )

    pred = pd.read_csv(BRIDGE_PREDICTIONS_IN)
    required_pred = {
        "rice_x",
        "rice_y",
        "year",
        "ff",
        "prediction",
        "split",
    }
    if not required_pred.issubset(pred.columns):
        raise AssertionError(
            "Bridge prediction table missing required columns: "
            f"{sorted(required_pred - set(pred.columns))}"
        )

    pred = pred.loc[
        pred["year"].isin(VALIDATION_YEARS)
        & (pred["split"] == "confirmation")
    ].copy()

    if pred.empty:
        raise AssertionError("No 2014-2016 confirmation predictions found.")

    if pred.duplicated(["rice_x", "rice_y", "year"]).any():
        raise AssertionError("Duplicate prediction rice-cell/year rows.")

    # IMPORTANT:
    # Historical RiceFloodIT confirmation support is not complete on all
    # 4,331 grid cells in every confirmation year. To avoid changing spatial
    # support across 2014, 2015, and 2016, freeze the validation geometry to
    # the exact intersection of rice cells observed in ALL three years.
    yearly_support = []
    for year in VALIDATION_YEARS:
        y = pred.loc[
            pred["year"] == year,
            ["rice_x", "rice_y"],
        ].drop_duplicates()

        yearly_support.append(
            set(map(tuple, y.to_numpy()))
        )

    balanced_support = set.intersection(*yearly_support)

    if len(balanced_support) <= 0:
        raise AssertionError(
            "No common RiceFloodIT confirmation support across 2014-2016."
        )

    balanced_lookup = pd.DataFrame(
        sorted(balanced_support),
        columns=["rice_x", "rice_y"],
    )

    pred = pred.merge(
        balanced_lookup.assign(balanced_support=True),
        on=["rice_x", "rice_y"],
        how="inner",
        validate="many_to_one",
    )

    expected_balanced_rows = (
        len(balanced_lookup) * len(VALIDATION_YEARS)
    )

    if len(pred) != expected_balanced_rows:
        raise AssertionError(
            "Balanced confirmation support is not complete across years: "
            f"expected {expected_balanced_rows}, found {len(pred)}."
        )

    geo_key = (
        geo[["x", "y", "utm_e", "utm_n"]]
        .drop_duplicates(["x", "y"])
        .rename(columns={"x": "rice_x", "y": "rice_y"})
    )

    cell = pred.merge(
        geo_key,
        on=["rice_x", "rice_y"],
        how="inner",
        validate="many_to_one",
    )

    if len(cell) != len(pred):
        raise AssertionError(
            f"Georeference merge lost prediction rows: {len(pred)} -> {len(cell)}."
        )

    # Geometry is now fixed on the balanced 2014-2016 confirmation support.
    cell_coords = (
        cell[["rice_x", "rice_y", "utm_e", "utm_n"]]
        .drop_duplicates(["rice_x", "rice_y"])
        .sort_values(["rice_x", "rice_y"])
        .reset_index(drop=True)
    )

    if len(cell_coords) != len(balanced_lookup):
        raise AssertionError(
            "Balanced support/georeference cell-count mismatch."
        )

    if cell_coords.duplicated(["utm_e", "utm_n"]).any():
        raise AssertionError(
            "Duplicate UTM cell-center coordinates in balanced georeference."
        )

    tree = cKDTree(
        cell_coords[["utm_e", "utm_n"]].to_numpy(dtype=float)
    )

    rows = []
    for _, w in wells.iterrows():
        idx = tree.query_ball_point(
            [float(w["utm_e"]), float(w["utm_n"])],
            r=RADIUS_M,
        )

        if len(idx) <= 0:
            raise AssertionError(f"{w['station']}: no RiceFloodIT cells within 10 km.")

        selected = cell_coords.iloc[idx][["rice_x", "rice_y"]]

        for year in VALIDATION_YEARS:
            y = cell.loc[cell["year"] == year].merge(
                selected,
                on=["rice_x", "rice_y"],
                how="inner",
                validate="one_to_one",
            )

            if len(y) != len(selected):
                raise AssertionError(
                    f"{w['station']} {year}: expected {len(selected)} cells, "
                    f"found {len(y)}."
                )

            rows.append(
                {
                    "station": str(w["station"]),
                    "year": int(year),
                    "n_cells_10km": int(len(y)),
                    "observed_ff10": float(y["ff"].mean()),
                    "predicted_ff10": float(y["prediction"].mean()),
                    "ff10_prediction_error": float(
                        y["prediction"].mean() - y["ff"].mean()
                    ),
                }
            )

    matched = pd.DataFrame(rows).sort_values(
        ["station", "year"]
    ).reset_index(drop=True)

    expected = EXPECTED_WELLS * len(VALIDATION_YEARS)
    if len(matched) != expected:
        raise AssertionError(
            f"Expected {expected} matched well-years; found {len(matched)}."
        )

    if matched.duplicated(["station", "year"]).any():
        raise AssertionError("Duplicate matched validation station-year rows.")

    stations = matched["station"].to_numpy(dtype=str)
    years = matched["year"].to_numpy(dtype=int)

    obs = matched["observed_ff10"].to_numpy(dtype=float)
    predv = matched["predicted_ff10"].to_numpy(dtype=float)
    err = predv - obs

    obs_fe = manual_fe_residual(obs, stations, years)
    pred_fe = manual_fe_residual(predv, stations, years)
    err_fe = pred_fe - obs_fe

    matched["observed_ff10_well_year_fe_resid"] = obs_fe
    matched["predicted_ff10_well_year_fe_resid"] = pred_fe
    matched["error_well_year_fe_resid"] = err_fe

    raw_pearson, raw_spearman = safe_corr(obs, predv)
    fe_pearson, fe_spearman = safe_corr(obs_fe, pred_fe)

    summary = pd.DataFrame(
        [
            {
                "validation_years": "2014-2016",
                "n_wells": EXPECTED_WELLS,
                "n_well_years": len(matched),
                "radius_m": RADIUS_M,
                "balanced_confirmation_cells": int(len(balanced_lookup)),
                "support_rule": (
                    "intersection of RiceFloodIT cells observed in all "
                    "2014-2016 confirmation years"
                ),
                "raw_well_year_observed_sd": float(np.std(obs, ddof=1)),
                "raw_well_year_predicted_sd": float(np.std(predv, ddof=1)),
                "raw_well_year_error_sd": float(np.std(err, ddof=1)),
                "raw_well_year_rmse": float(np.sqrt(np.mean(err ** 2))),
                "raw_pearson": raw_pearson,
                "raw_spearman": raw_spearman,
                "fe_observed_signal_sd": float(np.std(obs_fe, ddof=1)),
                "fe_predicted_signal_sd": float(np.std(pred_fe, ddof=1)),
                "fe_error_sd": float(np.std(err_fe, ddof=1)),
                "fe_error_rmse": float(np.sqrt(np.mean(err_fe ** 2))),
                "fe_pearson": fe_pearson,
                "fe_spearman": fe_spearman,
                "fe_error_to_observed_signal_sd_ratio": float(
                    np.std(err_fe, ddof=1) / np.std(obs_fe, ddof=1)
                ),
                "fe_error_to_predicted_signal_sd_ratio": float(
                    np.std(err_fe, ddof=1) / np.std(pred_fe, ddof=1)
                ),
                "interpretation": (
                    "Matched 10-km well-year validation after well and year FE. "
                    "No attenuation correction is performed."
                ),
            }
        ]
    )

    return matched, summary


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    require(PANEL_IN, "Stage-5 primary panel")
    require(STAGE5_RESULT_IN, "Stage-5 primary result")
    require(STAGE6_QA_IN, "Stage-6 QA")

    panel = pd.read_csv(PANEL_IN)
    panel["station"] = panel["station"].astype(str)
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)

    if len(panel) != EXPECTED_ROWS:
        raise AssertionError(f"Expected {EXPECTED_ROWS} rows.")
    if panel["station"].nunique() != EXPECTED_WELLS:
        raise AssertionError(f"Expected {EXPECTED_WELLS} wells.")
    if tuple(sorted(panel["year"].unique())) != YEARS:
        raise AssertionError("Unexpected primary years.")
    if panel.duplicated(["station", "year"]).any():
        raise AssertionError("Duplicate station-year rows.")
    if panel[[OUTCOME, EXPOSURE, ANTECEDENT]].isna().any().any():
        raise AssertionError("Missing primary Y/F/A.")

    saved = pd.read_csv(STAGE5_RESULT_IN)
    if len(saved) != 1:
        raise AssertionError("Stage-5 result must contain exactly one primary row.")
    stage5_beta = float(saved.iloc[0]["beta_hat_per_1_ff10"])

    # ------------------------------------------------------------------
    # 1. Independent manual FWL replication.
    # ------------------------------------------------------------------
    beta_manual, f_resid, y_resid = manual_fwl_beta(panel)

    beta_abs_diff = abs(beta_manual - stage5_beta)
    if beta_abs_diff > TOL_BETA:
        raise AssertionError(
            f"Manual FWL beta mismatch: saved={stage5_beta}, "
            f"manual={beta_manual}, abs_diff={beta_abs_diff}"
        )

    identifying_sd = float(np.std(f_resid, ddof=1))
    identifying_var = float(np.var(f_resid, ddof=1))

    pd.DataFrame(
        [
            {
                "stage5_saved_beta": stage5_beta,
                "manual_fwl_beta": beta_manual,
                "absolute_difference": beta_abs_diff,
                "manual_identifying_ff10_sd": identifying_sd,
                "manual_identifying_ff10_variance": identifying_var,
                "fwl_identity_pass": True,
            }
        ]
    ).to_csv(FWL_OUT, index=False)

    # ------------------------------------------------------------------
    # 2. Independent partial leverage and heterogeneity.
    # ------------------------------------------------------------------
    total_ss = float(f_resid @ f_resid)
    rows = []

    for station in sorted(panel["station"].unique()):
        mask = panel["station"].to_numpy() == station
        ss = float(f_resid[mask] @ f_resid[mask])
        rows.append(
            {
                "station": station,
                "partial_ss_manual": ss,
                "partial_leverage_manual": ss / total_ss,
            }
        )

    lev = pd.DataFrame(rows)
    shares = lev["partial_leverage_manual"].to_numpy(dtype=float)

    if not np.isclose(shares.sum(), 1.0, atol=TOL_SHARE):
        raise AssertionError("Manual partial leverages do not sum to one.")

    G = EXPECTED_WELLS
    mean_l = float(shares.mean())

    # MacKinnon-Nielsen-Webb guide's squared coefficient of variation:
    # Vs = [1 / (G * mean(L)^2)] sum_g (L_g - mean(L))^2.
    vs_partial = float(
        np.sum((shares - mean_l) ** 2)
        / (G * mean_l ** 2)
    )

    inverse_herf = float(1.0 / np.sum(shares ** 2))

    lev["partial_leverage_rank"] = (
        lev["partial_leverage_manual"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    lev = lev.sort_values("partial_leverage_rank").reset_index(drop=True)

    # Cross-check against Stage 6 if available.
    if STAGE6_CLUSTER_IN.exists():
        old = pd.read_csv(STAGE6_CLUSTER_IN)
        old["station"] = old["station"].astype(str)

        if "ff10_partial_leverage_share" in old.columns:
            lev = lev.merge(
                old[["station", "ff10_partial_leverage_share"]],
                on="station",
                how="left",
                validate="one_to_one",
            )
            lev["stage6_minus_stage6r_share"] = (
                lev["ff10_partial_leverage_share"]
                - lev["partial_leverage_manual"]
            )

            max_share_diff = float(
                lev["stage6_minus_stage6r_share"].abs().max()
            )
            if max_share_diff > TOL_STAGE6:
                raise AssertionError(
                    f"Stage6 vs Stage6R partial leverage mismatch: "
                    f"{max_share_diff}"
                )
        else:
            max_share_diff = np.nan
    else:
        max_share_diff = np.nan

    lev.to_csv(LEVERAGE_OUT, index=False)

    # ------------------------------------------------------------------
    # 3. Independent leave-one-well beta reconstruction.
    # ------------------------------------------------------------------
    loo_rows = []

    for station in sorted(panel["station"].unique()):
        d = panel.loc[panel["station"] != station].copy()
        beta_g, _, _ = manual_fwl_beta(d)

        loo_rows.append(
            {
                "omitted_station": station,
                "beta_minus_g_manual": beta_g,
                "change_from_full_beta": beta_g - beta_manual,
                "absolute_change_from_full_beta": abs(beta_g - beta_manual),
                "sign": (
                    "positive" if beta_g > 0
                    else "negative" if beta_g < 0
                    else "zero"
                ),
            }
        )

    loo = pd.DataFrame(loo_rows).sort_values(
        "absolute_change_from_full_beta",
        ascending=False,
    ).reset_index(drop=True)
    loo.to_csv(LOO_OUT, index=False)

    # ------------------------------------------------------------------
    # 4. Matched-scale historical bridge validation.
    # ------------------------------------------------------------------
    primary_stations = sorted(panel["station"].unique())
    matched, matched_summary = build_matched_validation(primary_stations)

    matched["post2021_identifying_ff10_sd_reference"] = identifying_sd
    matched.to_csv(MATCHED_PANEL_OUT, index=False)

    matched_summary["post2021_identifying_ff10_sd"] = identifying_sd
    matched_summary["matched_fe_error_sd_to_post2021_identifying_sd_ratio"] = (
        matched_summary["fe_error_sd"] / identifying_sd
    )
    matched_summary["matched_fe_rmse_to_post2021_identifying_sd_ratio"] = (
        matched_summary["fe_error_rmse"] / identifying_sd
    )
    matched_summary.to_csv(MATCHED_SUMMARY_OUT, index=False)

    # ------------------------------------------------------------------
    # 5. Stage 6 headline cross-check.
    # ------------------------------------------------------------------
    stage6_qa = json.loads(STAGE6_QA_IN.read_text(encoding="utf-8"))

    cross = {
        "metric": [],
        "stage6": [],
        "stage6r": [],
        "absolute_difference": [],
        "pass": [],
    }

    comparisons = [
        (
            "identifying_ff10_residual_sd",
            float(stage6_qa["identifying_ff10_residual_sd"]),
            identifying_sd,
        ),
        (
            "effective_ff10_clusters_inverse_herfindahl",
            float(stage6_qa["effective_ff10_clusters_inverse_herfindahl"]),
            inverse_herf,
        ),
        (
            "max_ff10_partial_leverage_share",
            float(stage6_qa["max_ff10_partial_leverage_share"]),
            float(shares.max()),
        ),
    ]

    for name, a, b in comparisons:
        diff = abs(a - b)
        cross["metric"].append(name)
        cross["stage6"].append(a)
        cross["stage6r"].append(b)
        cross["absolute_difference"].append(diff)
        cross["pass"].append(diff <= TOL_STAGE6)

    cross_df = pd.DataFrame(cross)
    cross_df.to_csv(CROSSCHECK_OUT, index=False)

    if not cross_df["pass"].all():
        raise AssertionError(
            "Stage 6R failed to independently reproduce one or more "
            "Stage-6 headline diagnostics."
        )

    # ------------------------------------------------------------------
    # 6. QA and concise terminal report.
    # ------------------------------------------------------------------
    top = lev.iloc[0]
    most_influential = loo.iloc[0]
    ms = matched_summary.iloc[0]

    qa = {
        "status": "PASS",
        "stage": "STAGE_6R_INDEPENDENT_REPLICATION",
        "model_changed": False,
        "sample_changed": False,
        "manual_fwl_beta": beta_manual,
        "stage5_saved_beta": stage5_beta,
        "beta_absolute_difference": beta_abs_diff,
        "identifying_ff10_sd_manual": identifying_sd,
        "partial_leverage_vs_stage6_max_difference": (
            None if np.isnan(max_share_diff) else max_share_diff
        ),
        "partial_leverage_squared_cv_Vs": vs_partial,
        "information_equivalent_clusters_inverse_herfindahl": inverse_herf,
        "max_partial_leverage": float(shares.max()),
        "top_partial_leverage_station": str(top["station"]),
        "most_influential_loo_station": str(
            most_influential["omitted_station"]
        ),
        "most_influential_loo_abs_beta_change": float(
            most_influential["absolute_change_from_full_beta"]
        ),
        "matched_scale_validation": {
            "years": list(VALIDATION_YEARS),
            "wells": EXPECTED_WELLS,
            "well_years": int(ms["n_well_years"]),
            "fe_observed_signal_sd": float(ms["fe_observed_signal_sd"]),
            "fe_predicted_signal_sd": float(ms["fe_predicted_signal_sd"]),
            "fe_error_sd": float(ms["fe_error_sd"]),
            "fe_error_rmse": float(ms["fe_error_rmse"]),
            "fe_pearson": float(ms["fe_pearson"]),
            "fe_spearman": float(ms["fe_spearman"]),
            "fe_error_sd_to_post2021_identifying_sd_ratio": float(
                ms["matched_fe_error_sd_to_post2021_identifying_sd_ratio"]
            ),
            "fe_rmse_to_post2021_identifying_sd_ratio": float(
                ms["matched_fe_rmse_to_post2021_identifying_sd_ratio"]
            ),
        },
        "warning": (
            "Matched-scale validation is a diagnostic of exposure reconstruction "
            "quality on the relevant 10-km within-well/interannual scale. It is "
            "not an errors-in-variables correction and does not alter Stage 5."
        ),
    }

    QA_OUT.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = f"""STAGE 6R — INDEPENDENT REPLICATION AUDIT
=========================================

1. FWL IDENTITY
Stage-5 saved beta: {stage5_beta:.12g}
Manual FWL beta:    {beta_manual:.12g}
Absolute difference: {beta_abs_diff:.3g}
PASS: {beta_abs_diff <= TOL_BETA}

Manual identifying FF10 SD: {identifying_sd:.12g}

2. PARTIAL LEVERAGE
Maximum well share: {float(shares.max()):.12g}
Top well: {top['station']}
Squared-CV heterogeneity Vs(L): {vs_partial:.12g}
Inverse-Herfindahl information-equivalent clusters: {inverse_herf:.12g}

3. LEAVE-ONE-WELL INFLUENCE
Largest absolute beta change:
station = {most_influential['omitted_station']}
beta_minus_g = {float(most_influential['beta_minus_g_manual']):.12g}
absolute change = {float(most_influential['absolute_change_from_full_beta']):.12g}

4. MATCHED-SCALE HISTORICAL VALIDATION
Same 12 wells, exact 10-km geometry, 2014-2016 confirmation years.

Well+year-FE observed signal SD: {float(ms['fe_observed_signal_sd']):.12g}
Well+year-FE predicted signal SD: {float(ms['fe_predicted_signal_sd']):.12g}
Well+year-FE reconstruction-error SD: {float(ms['fe_error_sd']):.12g}
Well+year-FE reconstruction-error RMSE: {float(ms['fe_error_rmse']):.12g}
Residual Pearson correlation: {float(ms['fe_pearson']):.12g}
Residual Spearman correlation: {float(ms['fe_spearman']):.12g}

Matched FE error SD / post-2021 identifying FF10 SD:
{float(ms['matched_fe_error_sd_to_post2021_identifying_sd_ratio']):.12g}

Matched FE RMSE / post-2021 identifying FF10 SD:
{float(ms['matched_fe_rmse_to_post2021_identifying_sd_ratio']):.12g}

5. STAGE-6 CROSS-CHECK
All independent headline replications pass: {bool(cross_df['pass'].all())}

No primary model or sample was changed.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")

    print("=== STAGE 6R INDEPENDENT REPLICATION AUDIT ===")
    print("")
    print("1. FWL IDENTITY")
    print(f"Stage-5 beta: {stage5_beta:.12g}")
    print(f"manual FWL beta: {beta_manual:.12g}")
    print(f"absolute difference: {beta_abs_diff:.3g}")
    print(f"identifying FF10 SD: {identifying_sd:.12g}")
    print("")
    print("2. PARTIAL LEVERAGE")
    print(f"max well information share: {float(shares.max()):.12g}")
    print(f"top well: {top['station']}")
    print(f"squared-CV Vs(L): {vs_partial:.12g}")
    print(f"inverse-Herfindahl effective clusters: {inverse_herf:.12g}")
    print("")
    print("3. LEAVE-ONE-WELL INFLUENCE")
    print(f"most influential well: {most_influential['omitted_station']}")
    print(
        "beta without that well: "
        f"{float(most_influential['beta_minus_g_manual']):.12g}"
    )
    print(
        "absolute beta change: "
        f"{float(most_influential['absolute_change_from_full_beta']):.12g}"
    )
    print("")
    print("4. MATCHED-SCALE 10-KM VALIDATION")
    print(f"validation well-years: {int(ms['n_well_years'])}")
    print(
        "balanced confirmation cells: "
        f"{int(ms['balanced_confirmation_cells'])}"
    )
    print(
        "FE observed signal SD: "
        f"{float(ms['fe_observed_signal_sd']):.12g}"
    )
    print(
        "FE predicted signal SD: "
        f"{float(ms['fe_predicted_signal_sd']):.12g}"
    )
    print(
        "FE reconstruction-error SD: "
        f"{float(ms['fe_error_sd']):.12g}"
    )
    print(
        "FE reconstruction-error RMSE: "
        f"{float(ms['fe_error_rmse']):.12g}"
    )
    print(f"FE Pearson r: {float(ms['fe_pearson']):.12g}")
    print(f"FE Spearman rho: {float(ms['fe_spearman']):.12g}")
    print(
        "FE error SD / post-2021 identifying SD: "
        f"{float(ms['matched_fe_error_sd_to_post2021_identifying_sd_ratio']):.12g}"
    )
    print("")
    print("5. CROSS-CHECK")
    print(f"Stage-6 headline replication pass: {bool(cross_df['pass'].all())}")
    print("")
    print(f"summary: {REPORT_OUT}")
    print(f"QA: {QA_OUT}")
    print("STAGE 6R INDEPENDENT REPLICATION: PASS")
    print("PRIMARY STAGE-5 MODEL / SAMPLE: UNCHANGED")


if __name__ == "__main__":
    main()

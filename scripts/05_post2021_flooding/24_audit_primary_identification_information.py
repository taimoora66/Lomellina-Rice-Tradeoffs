"""Stage 6 — Complete hostile identification / information-content audit.

Purpose
-------
Audit how much information actually identifies the already-frozen Stage-5
2022-2025 groundwater coefficient, and identify threats that can make
few-cluster inference fragile.

This script is deliberately post-reveal but NON-SELECTIVE:
- it does not change the Stage-5 primary model;
- it does not change the 12-well primary sample;
- it does not remove any year or well;
- it does not change the FF10 radius, anomaly baseline, outcome, or antecedent;
- it does not choose an inference method by significance;
- it does not refit a "better" substantive model.

The script reads the permanently saved 48-row Stage-5 primary panel and
evaluates five hostile-review domains:

A. Exposure information
   - raw FF10 variance;
   - after well FE;
   - after year FE;
   - after well + year FE;
   - after well + year FE + antecedent;
   - variance-retention ratios;
   - identifying-exposure distribution overall and by year.

B. Cluster information and influence
   - ordinary cluster leverage from the primary design;
   - FWL partial leverage for FF10 by well;
   - identifying-information share by well;
   - inverse-Herfindahl effective number of FF10 clusters;
   - concentration / coefficient of variation of partial leverage;
   - Stage-5 leave-one-well coefficient influence, if the frozen output exists.

C. Numerical identification
   - exact design rank;
   - singular values and condition number;
   - FF10 / antecedent dependence after well/year FE;
   - VIF-like continuous-pair diagnostic;
   - antecedent information cost.

D. Cross-well dependence threat
   - exact UTM well distances from frozen station metadata;
   - within-year spatial autocorrelation of PRIMARY MODEL residuals using
     inverse-distance weights;
   - fixed-seed permutation p-values for Moran-type I;
   - residual-product summaries by distance band.
   These are diagnostics only and do not replace frozen one-way clustering.

E. Exposure-measurement scale comparison
   - identifying FF10 residual SD;
   - frozen bridge confirmation pooled cell-year RMSE/MAE;
   - frozen bridge confirmation annual-mean RMSE/max absolute error;
   - ratios reported only as SCALE COMPARISONS.
   They are NOT measurement-error corrections because the validation metrics
   and the well-level identifying residual live at different aggregation levels.

No automated "significance rescue" or model alteration is permitted.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import cdist
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[2]

PANEL_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "post2021_primary_balanced_panel_2022_2025.csv"
)
STAGE5_RESULT_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage5_primary_groundwater_result_2022_2025.csv"
)
STAGE5_LOO_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage5_primary_leave_one_well_out_2022_2025.csv"
)
GW_META_IN = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "groundwater_station_metadata.csv"
)
BRIDGE_METRICS_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "bounded_bridge_confirmation_metrics_2014_2021.csv"
)
BRIDGE_INTERANNUAL_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "bounded_bridge_confirmation_interannual_2014_2016.csv"
)

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

SUMMARY_OUT = OUT_DIR / "stage6_exposure_information_summary.csv"
BY_YEAR_OUT = OUT_DIR / "stage6_exposure_information_by_year.csv"
PARTIAL_DIST_OUT = OUT_DIR / "stage6_partial_exposure_distribution.csv"
CLUSTER_OUT = OUT_DIR / "stage6_cluster_information_diagnostics.csv"
CLUSTER_SUMMARY_OUT = OUT_DIR / "stage6_cluster_information_summary.csv"
LOO_SUMMARY_OUT = OUT_DIR / "stage6_leave_one_well_influence_summary.csv"
DESIGN_OUT = OUT_DIR / "stage6_design_matrix_diagnostics.csv"
ANTECEDENT_OUT = OUT_DIR / "stage6_antecedent_overlap_diagnostics.csv"
SPATIAL_YEAR_OUT = OUT_DIR / "stage6_spatial_residual_moran_by_year.csv"
SPATIAL_DISTANCE_OUT = OUT_DIR / "stage6_spatial_residual_distance_bands.csv"
SPATIAL_PAIR_OUT = OUT_DIR / "stage6_spatial_residual_pairs.csv"
MEASUREMENT_OUT = OUT_DIR / "stage6_measurement_information_comparison.csv"
QA_OUT = OUT_DIR / "stage6_identification_information_qa.json"
REPORT_OUT = OUT_DIR / "stage6_hostile_audit_summary.txt"

YEARS = (2022, 2023, 2024, 2025)
EXPECTED_WELLS = 12
EXPECTED_ROWS = 48

OUTCOME = "gw_aug_nearest_aug23_m"
EXPOSURE = "ff10_anomaly_2010_2021"
ANTECEDENT = "gw_pre_last_janfeb_m"

PRIMARY_FORMULA = (
    f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} "
    "+ C(station) + C(year)"
)

SPATIAL_PERMUTATIONS = 9999
SPATIAL_SEED = 20260901

DISTANCE_BANDS_KM = (
    (0.0, 5.0),
    (5.0, 10.0),
    (10.0, 20.0),
    (20.0, 40.0),
    (40.0, np.inf),
)


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def require_exact_primary_panel(d: pd.DataFrame) -> None:
    required = {"station", "year", OUTCOME, EXPOSURE, ANTECEDENT}
    missing = required - set(d.columns)
    if missing:
        raise AssertionError(
            f"Stage-6 input missing required columns: {sorted(missing)}"
        )

    if len(d) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} primary rows; found {len(d)}."
        )

    if d["station"].nunique() != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} primary wells; "
            f"found {d['station'].nunique()}."
        )

    actual_years = tuple(sorted(pd.to_numeric(d["year"]).unique()))
    if actual_years != YEARS:
        raise AssertionError(
            f"Primary years are {actual_years}, expected {YEARS}."
        )

    if d.duplicated(["station", "year"]).any():
        raise AssertionError("Duplicate station-year rows in primary panel.")

    counts = d.groupby("station")["year"].nunique()
    if not (counts == len(YEARS)).all():
        raise AssertionError("Primary panel is not 12 x 4 balanced.")

    if d[[OUTCOME, EXPOSURE, ANTECEDENT]].isna().any().any():
        raise AssertionError("Primary panel contains missing Y/F/A values.")


def residualize(d: pd.DataFrame, response: str, rhs: str) -> np.ndarray:
    fit = smf.ols(f"{response} ~ {rhs}", data=d).fit()
    r = np.asarray(fit.resid, dtype=float)
    if not np.isfinite(r).all():
        raise AssertionError(f"Non-finite residuals from {response} ~ {rhs}.")
    return r


def sample_variance(x: np.ndarray) -> float:
    return float(np.var(np.asarray(x, dtype=float), ddof=1))


def sample_sd(x: np.ndarray) -> float:
    return float(np.std(np.asarray(x, dtype=float), ddof=1))


def distribution_row(
    x: np.ndarray,
    scope: str,
    year: int | None = None,
) -> dict[str, object]:
    v = np.asarray(x, dtype=float)
    return {
        "scope": scope,
        "year": year,
        "n": int(v.size),
        "mean": float(v.mean()),
        "sd": sample_sd(v),
        "variance": sample_variance(v),
        "min": float(v.min()),
        "p05": float(np.quantile(v, 0.05)),
        "p25": float(np.quantile(v, 0.25)),
        "median": float(np.quantile(v, 0.50)),
        "p75": float(np.quantile(v, 0.75)),
        "p95": float(np.quantile(v, 0.95)),
        "max": float(v.max()),
        "iqr": float(np.quantile(v, 0.75) - np.quantile(v, 0.25)),
    }


def coefficient_of_variation(x: np.ndarray) -> float:
    v = np.asarray(x, dtype=float)
    m = float(v.mean())
    if m == 0:
        return float("nan")
    return float(np.std(v, ddof=1) / m)


def inverse_herfindahl(shares: np.ndarray) -> float:
    s = np.asarray(shares, dtype=float)
    if np.any(s < 0):
        raise AssertionError("Information shares must be non-negative.")
    total = float(s.sum())
    if not np.isclose(total, 1.0, atol=1e-10):
        raise AssertionError(f"Information shares sum to {total}, not 1.")
    return float(1.0 / np.sum(s ** 2))


def moran_i(values: np.ndarray, weights: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)

    if w.shape != (x.size, x.size):
        raise ValueError("Weight matrix shape mismatch.")

    z = x - x.mean()
    denom = float(np.sum(z ** 2))
    s0 = float(w.sum())

    if denom <= 0 or s0 <= 0:
        return float("nan")

    numer = float(np.sum(w * np.outer(z, z)))
    return float((x.size / s0) * (numer / denom))


def permutation_moran(
    values: np.ndarray,
    weights: np.ndarray,
    rng: np.random.Generator,
    b: int,
) -> tuple[float, float, float, float]:
    observed = moran_i(values, weights)

    if not np.isfinite(observed):
        return observed, float("nan"), float("nan"), float("nan")

    perm = np.empty(b, dtype=float)
    x = np.asarray(values, dtype=float)

    for i in range(b):
        perm[i] = moran_i(rng.permutation(x), weights)

    center = float(np.nanmean(perm))
    distance_obs = abs(observed - center)
    distance_perm = np.abs(perm - center)

    p_two = float(
        (1 + np.sum(distance_perm >= distance_obs))
        / (b + 1)
    )

    return observed, center, float(np.nanstd(perm, ddof=1)), p_two


def build_inverse_distance_weights(
    coords_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    dist_m = cdist(coords_m, coords_m, metric="euclidean")
    np.fill_diagonal(dist_m, np.inf)

    w = np.zeros_like(dist_m, dtype=float)
    finite = np.isfinite(dist_m) & (dist_m > 0)
    w[finite] = 1.0 / dist_m[finite]

    if w.sum() <= 0:
        raise AssertionError("Spatial weight matrix has zero total weight.")

    return dist_m, w


def distance_band_label(distance_km: float) -> str:
    for low, high in DISTANCE_BANDS_KM:
        if low <= distance_km < high:
            if np.isinf(high):
                return f"{int(low)}+ km"
            return f"{int(low)}-{int(high)} km"
    raise AssertionError(f"Unclassified distance: {distance_km}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    require_file(PANEL_IN, "Frozen Stage-5 primary panel")
    require_file(GW_META_IN, "Frozen groundwater station metadata")

    panel = pd.read_csv(PANEL_IN)
    panel["station"] = panel["station"].astype(str)
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)

    require_exact_primary_panel(panel)

    # A. EXPOSURE INFORMATION
    f_raw = panel[EXPOSURE].astype(float).to_numpy()
    f_after_well = residualize(panel, EXPOSURE, "C(station)")
    f_after_year = residualize(panel, EXPOSURE, "C(year)")
    f_two_way = residualize(panel, EXPOSURE, "C(station) + C(year)")
    f_full_partial = residualize(
        panel,
        EXPOSURE,
        f"{ANTECEDENT} + C(station) + C(year)",
    )

    raw_var = sample_variance(f_raw)
    well_var = sample_variance(f_after_well)
    year_var = sample_variance(f_after_year)
    two_way_var = sample_variance(f_two_way)
    full_var = sample_variance(f_full_partial)

    for label, value in {
        "raw": raw_var,
        "two_way": two_way_var,
        "full_partial": full_var,
    }.items():
        if not np.isfinite(value) or value <= 0:
            raise AssertionError(
                f"{label} FF10 variance is non-positive/non-finite: {value}"
            )

    pd.DataFrame(
        [
            {"metric": "raw_ff10_variance", "value": raw_var},
            {"metric": "after_well_fe_variance", "value": well_var},
            {"metric": "after_year_fe_variance", "value": year_var},
            {"metric": "after_well_year_fe_variance", "value": two_way_var},
            {
                "metric": "after_well_year_fe_antecedent_variance",
                "value": full_var,
            },
            {
                "metric": "after_well_fe_to_raw_variance_ratio",
                "value": well_var / raw_var,
            },
            {
                "metric": "after_year_fe_to_raw_variance_ratio",
                "value": year_var / raw_var,
            },
            {
                "metric": "two_way_to_raw_variance_ratio",
                "value": two_way_var / raw_var,
            },
            {
                "metric": "full_to_raw_variance_ratio",
                "value": full_var / raw_var,
            },
            {
                "metric": "full_to_two_way_variance_ratio",
                "value": full_var / two_way_var,
            },
            {
                "metric": "full_partial_residual_sd",
                "value": sample_sd(f_full_partial),
            },
            {
                "metric": "full_partial_residual_min",
                "value": float(f_full_partial.min()),
            },
            {
                "metric": "full_partial_residual_max",
                "value": float(f_full_partial.max()),
            },
        ]
    ).to_csv(SUMMARY_OUT, index=False)

    exposure_diag = panel[["station", "year", EXPOSURE]].copy()
    exposure_diag["ff_after_well_fe"] = f_after_well
    exposure_diag["ff_after_year_fe"] = f_after_year
    exposure_diag["ff_after_well_year_fe"] = f_two_way
    exposure_diag["ff_identifying_residual"] = f_full_partial

    by_year_rows = []
    for year in YEARS:
        y = exposure_diag.loc[exposure_diag["year"] == year]
        by_year_rows.append(
            {
                "year": year,
                "n": int(len(y)),
                "raw_mean": float(y[EXPOSURE].mean()),
                "raw_sd": float(y[EXPOSURE].std(ddof=1)),
                "raw_min": float(y[EXPOSURE].min()),
                "raw_max": float(y[EXPOSURE].max()),
                "two_way_mean": float(y["ff_after_well_year_fe"].mean()),
                "two_way_sd": float(y["ff_after_well_year_fe"].std(ddof=1)),
                "two_way_min": float(y["ff_after_well_year_fe"].min()),
                "two_way_max": float(y["ff_after_well_year_fe"].max()),
                "identifying_mean": float(y["ff_identifying_residual"].mean()),
                "identifying_sd": float(y["ff_identifying_residual"].std(ddof=1)),
                "identifying_min": float(y["ff_identifying_residual"].min()),
                "identifying_max": float(y["ff_identifying_residual"].max()),
            }
        )
    pd.DataFrame(by_year_rows).to_csv(BY_YEAR_OUT, index=False)

    dist_rows = [
        distribution_row(
            f_full_partial,
            scope="overall",
        )
    ]
    for year in YEARS:
        mask = panel["year"].to_numpy() == year
        dist_rows.append(
            distribution_row(
                f_full_partial[mask],
                scope="year",
                year=year,
            )
        )
    pd.DataFrame(dist_rows).to_csv(PARTIAL_DIST_OUT, index=False)

    # B. PRIMARY DESIGN + CLUSTER / PARTIAL LEVERAGE
    primary_fit = smf.ols(PRIMARY_FORMULA, data=panel).fit()

    if EXPOSURE not in primary_fit.params.index:
        raise AssertionError("Exposure coefficient not estimable in primary model.")

    x = np.asarray(primary_fit.model.exog, dtype=float)
    rank = int(np.linalg.matrix_rank(x))
    n_columns = int(x.shape[1])

    if rank != n_columns:
        raise AssertionError(
            f"Primary design is rank deficient: rank={rank}, columns={n_columns}."
        )

    singular_values = np.linalg.svd(x, compute_uv=False)
    smallest_sv = float(singular_values.min())
    largest_sv = float(singular_values.max())
    condition_number = float(largest_sv / smallest_sv)

    xtx_inv = np.linalg.inv(x.T @ x)
    hat_diag = np.einsum("ij,jk,ik->i", x, xtx_inv, x)

    fwl = np.asarray(f_full_partial, dtype=float)
    total_fwl_ss = float(np.sum(fwl ** 2))
    if total_fwl_ss <= 0:
        raise AssertionError("Residualized FF10 sum of squares is zero.")

    stations = sorted(panel["station"].unique())
    cluster_rows = []

    for station in stations:
        mask = panel["station"].to_numpy() == station
        cluster_hat_trace = float(hat_diag[mask].sum())
        partial_ss = float(np.sum(fwl[mask] ** 2))
        partial_share = float(partial_ss / total_fwl_ss)

        cluster_rows.append(
            {
                "station": station,
                "n_rows": int(mask.sum()),
                "cluster_hat_trace": cluster_hat_trace,
                "cluster_hat_share_of_design_rank": (
                    cluster_hat_trace / n_columns
                ),
                "ff10_partial_ss": partial_ss,
                "ff10_partial_leverage_share": partial_share,
                "ff10_partial_resid_min": float(fwl[mask].min()),
                "ff10_partial_resid_max": float(fwl[mask].max()),
                "ff10_partial_resid_sd": sample_sd(fwl[mask]),
            }
        )

    cluster_df = pd.DataFrame(cluster_rows)

    if not np.isclose(
        cluster_df["ff10_partial_leverage_share"].sum(),
        1.0,
        atol=1e-10,
    ):
        raise AssertionError("FF10 partial leverage shares do not sum to one.")

    loo_available = False
    if STAGE5_LOO_IN.exists():
        loo = pd.read_csv(STAGE5_LOO_IN)
        if "omitted_station" in loo.columns:
            loo["omitted_station"] = loo["omitted_station"].astype(str)
            keep = [
                c
                for c in [
                    "omitted_station",
                    "beta_minus_g",
                    "change_from_full_beta",
                    "coefficient_sign",
                    "remaining_wells",
                    "remaining_rows",
                ]
                if c in loo.columns
            ]
            cluster_df = cluster_df.merge(
                loo[keep],
                left_on="station",
                right_on="omitted_station",
                how="left",
                validate="one_to_one",
            )
            loo_available = True

    cluster_df = cluster_df.sort_values(
        "ff10_partial_leverage_share",
        ascending=False,
    ).reset_index(drop=True)
    cluster_df["ff10_partial_leverage_rank"] = (
        np.arange(1, len(cluster_df) + 1)
    )
    cluster_df.to_csv(CLUSTER_OUT, index=False)

    shares = cluster_df["ff10_partial_leverage_share"].to_numpy(dtype=float)
    eff_clusters = inverse_herfindahl(shares)
    leverage_cv = coefficient_of_variation(shares)

    cluster_summary = {
        "n_clusters": EXPECTED_WELLS,
        "effective_ff10_clusters_inverse_herfindahl": eff_clusters,
        "max_ff10_partial_leverage_share": float(shares.max()),
        "min_ff10_partial_leverage_share": float(shares.min()),
        "partial_leverage_share_cv": leverage_cv,
        "top_1_information_share": float(shares[0]),
        "top_2_information_share": float(shares[:2].sum()),
        "top_3_information_share": float(shares[:3].sum()),
        "max_cluster_hat_trace": float(cluster_df["cluster_hat_trace"].max()),
        "min_cluster_hat_trace": float(cluster_df["cluster_hat_trace"].min()),
        "cluster_hat_trace_cv": coefficient_of_variation(
            cluster_df["cluster_hat_trace"].to_numpy(dtype=float)
        ),
        "stage5_loo_available": loo_available,
    }
    pd.DataFrame([cluster_summary]).to_csv(
        CLUSTER_SUMMARY_OUT,
        index=False,
    )

    loo_summary_rows = []
    if loo_available and "beta_minus_g" in cluster_df.columns:
        loo_beta = pd.to_numeric(
            cluster_df["beta_minus_g"],
            errors="coerce",
        )
        if loo_beta.notna().all():
            full_beta = float(primary_fit.params[EXPOSURE])
            abs_change = np.abs(loo_beta.to_numpy() - full_beta)
            idx = int(np.argmax(abs_change))
            loo_summary_rows.append(
                {
                    "full_beta": full_beta,
                    "loo_beta_min": float(loo_beta.min()),
                    "loo_beta_max": float(loo_beta.max()),
                    "loo_beta_sd": float(loo_beta.std(ddof=1)),
                    "loo_sign_changes_across_wells": bool(
                        (loo_beta > 0).any() and (loo_beta < 0).any()
                    ),
                    "max_abs_change_from_full_beta": float(abs_change[idx]),
                    "station_with_max_abs_change": str(
                        cluster_df.iloc[idx]["station"]
                    ),
                }
            )
    pd.DataFrame(loo_summary_rows).to_csv(
        LOO_SUMMARY_OUT,
        index=False,
    )

    # C. NUMERICAL IDENTIFICATION / ANTECEDENT OVERLAP
    a_two_way = residualize(
        panel,
        ANTECEDENT,
        "C(station) + C(year)",
    )

    pearson = stats.pearsonr(f_two_way, a_two_way)
    spearman = stats.spearmanr(f_two_way, a_two_way)

    pearson_r = float(pearson.statistic)
    spearman_rho = float(spearman.statistic)

    pair_r2 = pearson_r ** 2
    vif_like = float(1.0 / (1.0 - pair_r2))

    pd.DataFrame(
        [
            {
                "n_rows": EXPECTED_ROWS,
                "n_wells": EXPECTED_WELLS,
                "n_years": len(YEARS),
                "design_columns": n_columns,
                "design_rank": rank,
                "smallest_singular_value": smallest_sv,
                "largest_singular_value": largest_sv,
                "condition_number": condition_number,
                "pearson_ff10_antecedent_after_well_year_fe": pearson_r,
                "pearson_p_value_descriptive_only": float(pearson.pvalue),
                "spearman_ff10_antecedent_after_well_year_fe": spearman_rho,
                "spearman_p_value_descriptive_only": float(spearman.pvalue),
                "continuous_pair_r_squared": pair_r2,
                "continuous_pair_vif_like": vif_like,
                "note": (
                    "VIF-like statistic concerns only the two continuous "
                    "residualized variables; it is not a dummy-variable VIF."
                ),
            }
        ]
    ).to_csv(DESIGN_OUT, index=False)

    pd.DataFrame(
        [
            {
                "ff10_variance_after_well_year_fe": two_way_var,
                "ff10_variance_after_well_year_fe_plus_antecedent": full_var,
                "remaining_fraction_after_antecedent": full_var / two_way_var,
                "fraction_removed_by_antecedent": 1.0 - (full_var / two_way_var),
                "rule": (
                    "Diagnostic only. Antecedent groundwater remains in the "
                    "frozen primary model regardless of information loss."
                ),
            }
        ]
    ).to_csv(ANTECEDENT_OUT, index=False)

    # D. SPATIAL DEPENDENCE THREAT
    meta = pd.read_csv(GW_META_IN)
    required_meta = {"station", "utm_e", "utm_n"}
    missing_meta = required_meta - set(meta.columns)
    if missing_meta:
        raise AssertionError(
            f"Groundwater metadata missing spatial columns: {sorted(missing_meta)}"
        )

    meta["station"] = meta["station"].astype(str)
    meta = (
        meta.loc[meta["station"].isin(stations), ["station", "utm_e", "utm_n"]]
        .drop_duplicates("station")
        .sort_values("station")
        .reset_index(drop=True)
    )

    if len(meta) != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected coordinates for {EXPECTED_WELLS} wells; found {len(meta)}."
        )

    if meta[["utm_e", "utm_n"]].isna().any().any():
        raise AssertionError("Missing UTM coordinates in primary wells.")

    station_order = meta["station"].tolist()
    coords = meta[["utm_e", "utm_n"]].to_numpy(dtype=float)
    dist_m, spatial_w = build_inverse_distance_weights(coords)

    primary_resid = np.asarray(primary_fit.resid, dtype=float)
    panel_resid = panel[["station", "year"]].copy()
    panel_resid["primary_model_residual"] = primary_resid

    rng = np.random.default_rng(SPATIAL_SEED)
    spatial_year_rows = []
    pair_rows = []

    for year in YEARS:
        y = (
            panel_resid.loc[panel_resid["year"] == year]
            .set_index("station")
            .loc[station_order]
            .reset_index()
        )
        r = y["primary_model_residual"].to_numpy(dtype=float)

        obs_i, perm_mean, perm_sd, p_two = permutation_moran(
            r,
            spatial_w,
            rng,
            SPATIAL_PERMUTATIONS,
        )

        spatial_year_rows.append(
            {
                "year": year,
                "n_wells": EXPECTED_WELLS,
                "moran_i_inverse_distance": obs_i,
                "permutation_mean": perm_mean,
                "permutation_sd": perm_sd,
                "two_sided_permutation_p_value": p_two,
                "permutations": SPATIAL_PERMUTATIONS,
                "seed": SPATIAL_SEED,
                "interpretation": (
                    "Dependence diagnostic only; does not change frozen inference."
                ),
            }
        )

        for i in range(EXPECTED_WELLS):
            for j in range(i + 1, EXPECTED_WELLS):
                distance_km = float(dist_m[i, j] / 1000.0)
                pair_rows.append(
                    {
                        "year": year,
                        "station_i": station_order[i],
                        "station_j": station_order[j],
                        "distance_km": distance_km,
                        "distance_band": distance_band_label(distance_km),
                        "residual_i": float(r[i]),
                        "residual_j": float(r[j]),
                        "residual_product": float(r[i] * r[j]),
                        "absolute_residual_difference": float(abs(r[i] - r[j])),
                    }
                )

    spatial_year_df = pd.DataFrame(spatial_year_rows)
    spatial_year_df.to_csv(SPATIAL_YEAR_OUT, index=False)

    pair_df = pd.DataFrame(pair_rows)
    pair_df.to_csv(SPATIAL_PAIR_OUT, index=False)

    (
        pair_df.groupby("distance_band", sort=False)
        .agg(
            n_pairs=("residual_product", "size"),
            mean_distance_km=("distance_km", "mean"),
            mean_residual_product=("residual_product", "mean"),
            median_residual_product=("residual_product", "median"),
            mean_abs_residual_difference=("absolute_residual_difference", "mean"),
        )
        .reset_index()
        .to_csv(SPATIAL_DISTANCE_OUT, index=False)
    )

    # E. MEASUREMENT / INFORMATION SCALE COMPARISON
    identifying_sd = sample_sd(f_full_partial)

    measurement_rows = [
        {
            "quantity": "stage6_identifying_ff10_residual_sd",
            "value": identifying_sd,
            "aggregation_level": (
                "well-year residual after well FE + year FE + antecedent"
            ),
            "comparison_ratio_to_identifying_sd": 1.0,
            "valid_as_measurement_error_correction": False,
            "note": "Identifying exposure scale, not validation error.",
        }
    ]

    if BRIDGE_METRICS_IN.exists():
        bm = pd.read_csv(BRIDGE_METRICS_IN)
        pooled = bm.loc[
            (bm["subset"] == "confirmation")
            & (bm["year"].astype(str) == "pooled_2014_2016")
        ]
        if len(pooled) == 1:
            for col, label in [
                ("rmse", "bridge_confirmation_pooled_cell_year_rmse"),
                ("mae", "bridge_confirmation_pooled_cell_year_mae"),
            ]:
                value = float(pooled.iloc[0][col])
                measurement_rows.append(
                    {
                        "quantity": label,
                        "value": value,
                        "aggregation_level": "validation cell-year",
                        "comparison_ratio_to_identifying_sd": (
                            value / identifying_sd
                        ),
                        "valid_as_measurement_error_correction": False,
                        "note": (
                            "Scale comparison only. Cell-year validation error "
                            "is not the same object as 10-km well-year residual error."
                        ),
                    }
                )

    if BRIDGE_INTERANNUAL_IN.exists():
        bi = pd.read_csv(BRIDGE_INTERANNUAL_IN)
        if len(bi) >= 1:
            row = bi.iloc[0]
            for col, label in [
                ("annual_mean_rmse", "bridge_confirmation_annual_mean_rmse"),
                (
                    "annual_mean_max_abs_error",
                    "bridge_confirmation_annual_mean_max_abs_error",
                ),
            ]:
                if col in bi.columns:
                    value = float(row[col])
                    measurement_rows.append(
                        {
                            "quantity": label,
                            "value": value,
                            "aggregation_level": (
                                "regional annual mean validation"
                            ),
                            "comparison_ratio_to_identifying_sd": (
                                value / identifying_sd
                            ),
                            "valid_as_measurement_error_correction": False,
                            "note": (
                                "Scale comparison only. Regional annual-mean "
                                "error is not a well-year measurement-error SD."
                            ),
                        }
                    )

    measurement_df = pd.DataFrame(measurement_rows)
    measurement_df.to_csv(MEASUREMENT_OUT, index=False)

    # Stage-5 identity check
    stage5_identity = {}
    if STAGE5_RESULT_IN.exists():
        sr = pd.read_csv(STAGE5_RESULT_IN)
        if len(sr) == 1:
            saved_beta = (
                float(sr.iloc[0]["beta_hat_per_1_ff10"])
                if "beta_hat_per_1_ff10" in sr.columns
                else None
            )
            refit_beta = float(primary_fit.params[EXPOSURE])

            stage5_identity = {
                "stage5_beta": saved_beta,
                "stage6_refit_beta_for_identity_only": refit_beta,
            }

            if saved_beta is not None and not np.isclose(
                saved_beta,
                refit_beta,
                rtol=0,
                atol=1e-10,
            ):
                raise AssertionError(
                    "Stage-6 identity refit does not reproduce saved Stage-5 beta."
                )

    qa = {
        "status": "PASS",
        "stage": "STAGE_6_COMPLETE_HOSTILE_IDENTIFICATION_AUDIT",
        "scientific_model_modified": False,
        "primary_sample_modified": False,
        "outcome_used_for_specification_selection": False,
        "n_rows": EXPECTED_ROWS,
        "n_wells": EXPECTED_WELLS,
        "years": list(YEARS),
        "raw_ff10_variance": raw_var,
        "after_well_fe_variance": well_var,
        "after_year_fe_variance": year_var,
        "after_well_year_fe_variance": two_way_var,
        "after_well_year_fe_antecedent_variance": full_var,
        "two_way_to_raw_variance_ratio": two_way_var / raw_var,
        "full_to_raw_variance_ratio": full_var / raw_var,
        "full_to_two_way_variance_ratio": full_var / two_way_var,
        "identifying_ff10_residual_sd": identifying_sd,
        "effective_ff10_clusters_inverse_herfindahl": eff_clusters,
        "max_ff10_partial_leverage_share": float(shares.max()),
        "top_3_ff10_information_share": float(shares[:3].sum()),
        "design_rank": rank,
        "design_columns": n_columns,
        "smallest_singular_value": smallest_sv,
        "condition_number": condition_number,
        "ff10_antecedent_partial_pearson_r": pearson_r,
        "continuous_pair_vif_like": vif_like,
        "spatial_permutations": SPATIAL_PERMUTATIONS,
        "spatial_seed": SPATIAL_SEED,
        "stage5_identity": stage5_identity,
        "measurement_comparison_rule": (
            "Validation-error ratios are descriptive scale comparisons only; "
            "they are not attenuation corrections."
        ),
        "qualitative_classification_rule": (
            "No automated identification label is assigned. Classification "
            "must be written after reviewing all numeric diagnostics without "
            "changing the frozen model."
        ),
    }

    QA_OUT.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    top = cluster_df.iloc[0]

    spatial_lines = [
        (
            f"{int(row['year'])}: "
            f"I={row['moran_i_inverse_distance']:.6g}, "
            f"perm-p={row['two_sided_permutation_p_value']:.6g}"
        )
        for _, row in spatial_year_df.iterrows()
    ]

    measurement_lines = [
        (
            f"{row['quantity']}: {row['value']:.6g}; "
            f"ratio-to-identifying-SD="
            f"{row['comparison_ratio_to_identifying_sd']:.6g}; "
            f"level={row['aggregation_level']}"
        )
        for _, row in measurement_df.iterrows()
    ]

    report = f"""STAGE 6 — COMPLETE HOSTILE IDENTIFICATION / INFORMATION AUDIT
================================================================

Frozen model changed: NO
Frozen sample changed: NO
Rows / wells / years: {EXPECTED_ROWS} / {EXPECTED_WELLS} / {len(YEARS)}

A. EXPOSURE INFORMATION
-----------------------
Raw FF10 variance: {raw_var:.12g}
After well FE variance: {well_var:.12g}
After year FE variance: {year_var:.12g}
After well + year FE variance: {two_way_var:.12g}
After well + year FE + antecedent variance: {full_var:.12g}

Two-way / raw retained fraction: {two_way_var / raw_var:.12g}
Full partial / raw retained fraction: {full_var / raw_var:.12g}
Full partial / two-way retained fraction: {full_var / two_way_var:.12g}

Identifying FF10 residual SD: {identifying_sd:.12g}
Identifying FF10 residual range:
[{float(f_full_partial.min()):.12g}, {float(f_full_partial.max()):.12g}]

B. CLUSTER INFORMATION
----------------------
Nominal well clusters: {EXPECTED_WELLS}
Effective FF10 clusters (inverse-Herfindahl): {eff_clusters:.12g}
Maximum single-well FF10 information share: {float(shares.max()):.12g}
Top-3 wells FF10 information share: {float(shares[:3].sum()):.12g}
Partial-leverage share CV: {leverage_cv:.12g}

Highest-information well:
{top['station']}
share={float(top['ff10_partial_leverage_share']):.12g}

Stage-5 leave-one-well output available: {loo_available}

C. NUMERICAL IDENTIFICATION
---------------------------
Design rank: {rank}/{n_columns}
Smallest singular value: {smallest_sv:.12g}
Largest singular value: {largest_sv:.12g}
Condition number: {condition_number:.12g}

FF10 vs antecedent after well/year FE:
Pearson r = {pearson_r:.12g}
Spearman rho = {spearman_rho:.12g}
Continuous-pair VIF-like diagnostic = {vif_like:.12g}

Antecedent remaining-information fraction:
{full_var / two_way_var:.12g}

D. CROSS-WELL SPATIAL DEPENDENCE THREAT
---------------------------------------
Inverse-distance Moran-type residual diagnostic by year:
{chr(10).join(spatial_lines)}

These p-values are diagnostics only. They do not authorize replacing the
frozen one-way well-cluster inference.

E. MEASUREMENT / INFORMATION SCALE
----------------------------------
{chr(10).join(measurement_lines)}

IMPORTANT:
Bridge validation errors and the identifying well-year FF10 residual are at
different aggregation levels. Their ratios are scale comparisons only and must
not be described as measurement-error SD ratios or used for attenuation
correction.

HOSTILE-AUDIT DECISION RULE
---------------------------
Do not automatically assign an identification category from any single cutoff.
Interpret jointly:
1. fraction of FF10 variance surviving well/year FE;
2. fraction surviving antecedent adjustment;
3. concentration of FF10 partial leverage across wells;
4. effective FF10 cluster count;
5. leave-one-well coefficient stability;
6. numerical rank/conditioning;
7. spatial residual dependence threat;
8. measurement-information scale comparison.

No result in this audit permits changing the frozen Stage-5 primary result.
"""

    REPORT_OUT.write_text(report, encoding="utf-8")

    print("=== STAGE 6 COMPLETE HOSTILE IDENTIFICATION AUDIT ===")
    print(
        f"rows / wells / years: "
        f"{EXPECTED_ROWS} / {EXPECTED_WELLS} / {len(YEARS)}"
    )
    print("")
    print("A. EXPOSURE INFORMATION")
    print(f"raw FF10 variance: {raw_var:.12g}")
    print(f"after well FE variance: {well_var:.12g}")
    print(f"after year FE variance: {year_var:.12g}")
    print(f"after well + year FE variance: {two_way_var:.12g}")
    print(f"after well + year FE + antecedent variance: {full_var:.12g}")
    print(f"two-way/raw retained fraction: {two_way_var / raw_var:.12g}")
    print(f"full/raw retained fraction: {full_var / raw_var:.12g}")
    print(f"full/two-way retained fraction: {full_var / two_way_var:.12g}")
    print(f"identifying FF10 residual SD: {identifying_sd:.12g}")
    print("")
    print("B. CLUSTER INFORMATION")
    print(f"nominal clusters: {EXPECTED_WELLS}")
    print(f"effective FF10 clusters: {eff_clusters:.12g}")
    print(f"max single-well information share: {float(shares.max()):.12g}")
    print(f"top-3 information share: {float(shares[:3].sum()):.12g}")
    print(f"partial-leverage share CV: {leverage_cv:.12g}")
    print(f"highest-information well: {top['station']}")
    print("")
    print("C. NUMERICAL IDENTIFICATION")
    print(f"design rank: {rank}/{n_columns}")
    print(f"smallest singular value: {smallest_sv:.12g}")
    print(f"condition number: {condition_number:.12g}")
    print(f"F/A partial Pearson r: {pearson_r:.12g}")
    print(f"F/A partial Spearman rho: {spearman_rho:.12g}")
    print(f"continuous-pair VIF-like: {vif_like:.12g}")
    print("")
    print("D. SPATIAL DEPENDENCE DIAGNOSTIC")
    for line in spatial_lines:
        print(line)
    print("")
    print("E. MEASUREMENT / INFORMATION SCALE")
    for line in measurement_lines:
        print(line)
    print("")
    print(f"human summary: {REPORT_OUT}")
    print(f"QA: {QA_OUT}")
    print("STAGE 6 COMPLETE HOSTILE AUDIT: PASS")
    print("PRIMARY STAGE-5 MODEL / SAMPLE: UNCHANGED")


if __name__ == "__main__":
    main()

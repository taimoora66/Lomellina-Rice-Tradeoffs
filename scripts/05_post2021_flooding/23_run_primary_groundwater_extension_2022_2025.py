"""Stage 5 controlled primary groundwater reveal, 2022-2025.

Scientific role
---------------
This script performs the first real-data fit of the frozen Stage-4 primary
2022-2025 groundwater model.

It MUST NOT execute unless the synthetic Stage-5 inference smoke test has
already passed and produced:

    outputs/diagnostics/post2021/stage5_inference_smoke_test.json

with status == "PASS".

Frozen primary model
--------------------
gw_aug_nearest_aug23_m
    ~ ff10_anomaly_2010_2021
    + gw_pre_last_janfeb_m
    + C(station)
    + C(year)

Primary population:
    12 balanced wells x 4 years = 48 station-year observations.

Primary inference:
    - OLS beta_hat on ff10_anomaly_2010_2021
    - leave-one-well-out CV3J cluster-jackknife SE
    - 95% t interval with df = 11
    - restricted WCR31 wild cluster bootstrap
      with Webb six-point weights, null imposed,
      B = 9,999, seed = 20260831, clustered by station

Benchmark / continuity reporting:
    - CRV1 cluster-robust SE, p-value and t interval with df = 11
    - HC3 SE, p-value and 95% interval

This script does not search alternate models, radii, outcomes, baselines,
samples, controls, wells, years, or inferential procedures.

The result is observational and non-causal.
"""

from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats
import statsmodels
import statsmodels.formula.api as smf
from wildboottest.wildboottest import wildboottest


ROOT = Path(__file__).resolve().parents[2]

GW_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "groundwater_annual_measures_2008_2025.csv"
)

FF_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2025.csv"
)

FROZEN_IDS_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_integrated_balanced4_sample_ids.csv"
)

SMOKE_TEST_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "stage5_inference_smoke_test.json"
)

OUT_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

ANALYSIS_PANEL_OUT = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "post2021_primary_balanced_panel_2022_2025.csv"
)

PRIMARY_RESULT_OUT = (
    OUT_DIR
    / "stage5_primary_groundwater_result_2022_2025.csv"
)

LOO_OUT = (
    OUT_DIR
    / "stage5_primary_leave_one_well_out_2022_2025.csv"
)

QA_OUT = (
    OUT_DIR
    / "stage5_primary_reveal_qa_2022_2025.json"
)

SOFTWARE_OUT = (
    OUT_DIR
    / "stage5_primary_reveal_software.json"
)

YEARS = (2022, 2023, 2024, 2025)
EXPECTED_WELLS = 12
EXPECTED_ROWS = 48

OUTCOME = "gw_aug_nearest_aug23_m"
EXPOSURE = "ff10_anomaly_2010_2021"
ANTECEDENT = "gw_pre_last_janfeb_m"

FORMULA = (
    f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} "
    "+ C(station) + C(year)"
)

SEED = 20260831
B = 9999
BOOTSTRAP_TYPE = "31"
WEIGHTS_TYPE = "webb"
IMPOSE_NULL = True


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Required package {name!r} is not installed. "
            "Stage-5 reveal remains blocked."
        ) from exc


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found: {path}\n"
            "Stage-5 reveal is blocked."
        )


def require_unique(
    d: pd.DataFrame,
    key: list[str],
    label: str,
) -> None:
    if d.duplicated(key).any():
        bad = d.loc[
            d.duplicated(key, keep=False),
            key,
        ].sort_values(key)

        raise AssertionError(
            f"{label}: duplicate keys:\n"
            + bad.to_string(index=False)
        )


def require_smoke_test_pass() -> dict:
    """Gate all real-data access behind the synthetic smoke-test PASS."""
    require_file(
        SMOKE_TEST_IN,
        "Stage-5 synthetic inference smoke-test artifact",
    )

    payload = json.loads(
        SMOKE_TEST_IN.read_text(encoding="utf-8")
    )

    if payload.get("status") != "PASS":
        raise AssertionError(
            "Stage-5 synthetic inference smoke test did not PASS."
        )

    if payload.get("firewall") != "NO_REAL_POST2021_DATA_READ":
        raise AssertionError(
            "Smoke-test firewall marker is missing or unexpected."
        )

    boot = payload.get("bootstrap", {})

    expected = {
        "bootstrap_type": BOOTSTRAP_TYPE,
        "weights_type": WEIGHTS_TYPE,
        "impose_null": IMPOSE_NULL,
        "B": B,
        "seed": SEED,
    }

    for key, expected_value in expected.items():
        if boot.get(key) != expected_value:
            raise AssertionError(
                f"Smoke-test configuration mismatch for {key}: "
                f"expected {expected_value!r}, found {boot.get(key)!r}."
            )

    if boot.get("fixed_seed_exactly_reproducible") is not True:
        raise AssertionError(
            "Smoke test did not establish fixed-seed reproducibility."
        )

    if int(payload.get("n_clusters", -1)) != EXPECTED_WELLS:
        raise AssertionError(
            "Smoke test did not use the expected 12 synthetic clusters."
        )

    if int(payload.get("n_rows", -1)) != EXPECTED_ROWS:
        raise AssertionError(
            "Smoke test did not use the expected 48 synthetic rows."
        )

    return payload


def extract_wild_bootstrap_pvalue(
    result: pd.DataFrame,
    param: str,
) -> float:
    if param in result.index and "p-value" in result.columns:
        p = float(result.loc[param, "p-value"])
    elif "param" in result.columns and "p-value" in result.columns:
        row = result.loc[
            result["param"].astype(str) == param
        ]
        if len(row) != 1:
            raise RuntimeError(
                f"Could not uniquely identify wild-bootstrap result "
                f"for {param!r}."
            )
        p = float(row["p-value"].iloc[0])
    else:
        raise RuntimeError(
            "Unsupported wildboottest result layout."
        )

    if not np.isfinite(p) or not 0.0 <= p <= 1.0:
        raise RuntimeError(
            f"Invalid wild-bootstrap p-value: {p!r}"
        )

    return p


def residual_variation_gate(
    d: pd.DataFrame,
) -> dict[str, float]:
    """Verify FF10 remains estimable after FE and antecedent adjustment."""
    aux_formula = (
        f"{EXPOSURE} ~ {ANTECEDENT} "
        "+ C(station) + C(year)"
    )
    aux = smf.ols(
        aux_formula,
        data=d,
    ).fit()

    resid = np.asarray(
        aux.resid,
        dtype=float,
    )

    resid_var = float(
        np.var(
            resid,
            ddof=1,
        )
    )
    resid_sd = float(
        np.std(
            resid,
            ddof=1,
        )
    )

    if not np.isfinite(resid_var) or resid_var <= 0.0:
        raise AssertionError(
            "FF10 has zero/non-finite residual variation after "
            "well FE, year FE, and antecedent groundwater adjustment."
        )

    return {
        "ff10_partial_residual_variance": resid_var,
        "ff10_partial_residual_sd": resid_sd,
        "ff10_partial_residual_min": float(resid.min()),
        "ff10_partial_residual_max": float(resid.max()),
    }


def build_primary_panel() -> pd.DataFrame:
    """Read exactly the frozen 12-well, 2022-2025 primary panel."""
    require_file(
        FROZEN_IDS_IN,
        "Frozen balanced-four-year sample IDs",
    )
    require_file(
        GW_IN,
        "Groundwater annual measures through 2025",
    )
    require_file(
        FF_IN,
        "Frozen FF10 exposure panel through 2025",
    )

    ids = pd.read_csv(
        FROZEN_IDS_IN
    )

    if list(ids.columns) != ["station"]:
        raise AssertionError(
            "Frozen balanced-four-year ID file must contain only 'station'."
        )

    if len(ids) != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} frozen primary wells; "
            f"found {len(ids)}."
        )

    if ids["station"].duplicated().any():
        raise AssertionError(
            "Duplicate station in frozen primary IDs."
        )

    frozen_stations = set(
        ids["station"].astype(str)
    )

    gw = pd.read_csv(
        GW_IN,
        usecols=[
            "station",
            "year",
            "aquifer_group",
            OUTCOME,
            ANTECEDENT,
        ],
    )

    gw["station"] = gw["station"].astype(str)

    gw = gw.loc[
        gw["station"].isin(frozen_stations)
        & gw["year"].isin(YEARS)
    ].copy()

    require_unique(
        gw,
        ["station", "year"],
        "groundwater",
    )

    if len(gw) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} groundwater rows; "
            f"found {len(gw)}."
        )

    if set(gw["station"]) != frozen_stations:
        raise AssertionError(
            "Groundwater primary stations differ from frozen IDs."
        )

    if not (
        gw["aquifer_group"] == "ISS"
    ).all():
        raise AssertionError(
            "Frozen primary groundwater sample contains a non-ISS well."
        )

    if gw[
        [
            OUTCOME,
            ANTECEDENT,
        ]
    ].isna().any().any():
        raise AssertionError(
            "Frozen primary groundwater panel contains missing "
            "outcome or antecedent values."
        )

    ff = pd.read_csv(
        FF_IN,
        usecols=[
            "station",
            "year",
            EXPOSURE,
            "n_cells_10km",
        ],
    )

    ff["station"] = ff["station"].astype(str)

    ff = ff.loc[
        ff["station"].isin(frozen_stations)
        & ff["year"].isin(YEARS)
    ].copy()

    require_unique(
        ff,
        ["station", "year"],
        "FF10 exposure",
    )

    if len(ff) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} FF10 rows; "
            f"found {len(ff)}."
        )

    if set(ff["station"]) != frozen_stations:
        raise AssertionError(
            "FF10 primary stations differ from frozen IDs."
        )

    if ff[EXPOSURE].isna().any():
        raise AssertionError(
            "Frozen primary FF10 exposure contains missing values."
        )

    if (
        ff["n_cells_10km"] <= 0
    ).any():
        raise AssertionError(
            "Frozen primary sample contains non-positive 10-km "
            "exposure support."
        )

    panel = (
        gw.merge(
            ff,
            on=[
                "station",
                "year",
            ],
            how="inner",
            validate="one_to_one",
        )
        .sort_values(
            [
                "station",
                "year",
            ]
        )
        .reset_index(drop=True)
    )

    if len(panel) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} merged primary rows; "
            f"found {len(panel)}."
        )

    if panel["station"].nunique() != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} merged primary wells."
        )

    if tuple(
        sorted(
            panel["year"].unique()
        )
    ) != YEARS:
        raise AssertionError(
            "Primary panel years are not exactly 2022-2025."
        )

    counts = panel.groupby(
        "station"
    )["year"].nunique()

    if not (
        counts == len(YEARS)
    ).all():
        raise AssertionError(
            "Every primary well must contribute exactly four years."
        )

    if panel[
        [
            OUTCOME,
            EXPOSURE,
            ANTECEDENT,
        ]
    ].isna().any().any():
        raise AssertionError(
            "Primary panel contains missing Y/F/A values."
        )

    require_unique(
        panel,
        ["station", "year"],
        "merged primary panel",
    )

    return panel


def cv3j(
    d: pd.DataFrame,
    beta_hat: float,
) -> tuple[pd.DataFrame, float, float, float]:
    """Frozen leave-one-well-out CV3J variance and CI ingredients."""
    stations = sorted(
        d["station"].unique()
    )

    rows = []
    beta_minus = []

    for omitted in stations:
        reduced = d.loc[
            d["station"] != omitted
        ].copy()

        fit = smf.ols(
            FORMULA,
            data=reduced,
        ).fit()

        if EXPOSURE not in fit.params.index:
            raise AssertionError(
                f"LOO model omitting {omitted} lost {EXPOSURE}."
            )

        beta = float(
            fit.params[EXPOSURE]
        )

        if not np.isfinite(beta):
            raise AssertionError(
                f"LOO model omitting {omitted} produced "
                "a non-finite FF10 coefficient."
            )

        beta_minus.append(beta)

        rows.append(
            {
                "omitted_station": omitted,
                "remaining_wells": int(
                    reduced["station"].nunique()
                ),
                "remaining_rows": int(
                    len(reduced)
                ),
                "beta_minus_g": beta,
                "change_from_full_beta": beta - beta_hat,
                "coefficient_sign": (
                    "positive"
                    if beta > 0
                    else "negative"
                    if beta < 0
                    else "zero"
                ),
            }
        )

    g = len(stations)

    if g != EXPECTED_WELLS:
        raise AssertionError(
            f"CV3J expected {EXPECTED_WELLS} wells; found {g}."
        )

    b = np.asarray(
        beta_minus,
        dtype=float,
    )

    beta_bar = float(
        b.mean()
    )

    variance = float(
        ((g - 1) / g)
        * np.sum(
            (b - beta_bar) ** 2
        )
    )

    se = float(
        np.sqrt(
            variance
        )
    )

    if not np.isfinite(se) or se <= 0:
        raise AssertionError(
            f"Invalid CV3J standard error: {se!r}"
        )

    return (
        pd.DataFrame(rows),
        beta_bar,
        variance,
        se,
    )


def main() -> None:
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ANALYSIS_PANEL_OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # 0. PRE-REVEAL FIREWALL.
    # No real project data is read before this gate passes.
    # ---------------------------------------------------------

    smoke = require_smoke_test_pass()

    # ---------------------------------------------------------
    # 1. Record exact software environment.
    # ---------------------------------------------------------

    wildboottest_version = package_version(
        "wildboottest"
    )

    software = {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "statsmodels_version": statsmodels.__version__,
        "wildboottest_version": wildboottest_version,
        "bootstrap_seed": SEED,
        "bootstrap_replications": B,
        "bootstrap_type": BOOTSTRAP_TYPE,
        "bootstrap_label": "WCR31",
        "bootstrap_weight_distribution": WEIGHTS_TYPE,
        "bootstrap_impose_null": IMPOSE_NULL,
        "cluster_variable": "station",
    }

    SOFTWARE_OUT.write_text(
        json.dumps(
            software,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # ---------------------------------------------------------
    # 2. Build exact frozen primary panel.
    # ---------------------------------------------------------

    panel = build_primary_panel()

    # ---------------------------------------------------------
    # 3. Rank / estimability / identifying-variation gates.
    # ---------------------------------------------------------

    model = smf.ols(
        FORMULA,
        data=panel,
    )

    fit = model.fit()

    x = np.asarray(
        fit.model.exog,
        dtype=float,
    )

    rank = int(
        np.linalg.matrix_rank(
            x
        )
    )

    n_columns = int(
        x.shape[1]
    )

    if rank != n_columns:
        raise AssertionError(
            f"Primary design matrix rank failure: "
            f"rank={rank}, columns={n_columns}."
        )

    if EXPOSURE not in fit.params.index:
        raise AssertionError(
            f"Primary model does not contain coefficient {EXPOSURE!r}."
        )

    residual_gate = residual_variation_gate(
        panel
    )

    # ---------------------------------------------------------
    # 4. PRIMARY REVEAL: central OLS beta_hat.
    # ---------------------------------------------------------

    beta_hat = float(
        fit.params[EXPOSURE]
    )

    if not np.isfinite(beta_hat):
        raise AssertionError(
            "Primary FF10 coefficient is non-finite."
        )

    # ---------------------------------------------------------
    # 5. PRIMARY uncertainty: frozen CV3J.
    # ---------------------------------------------------------

    (
        loo,
        beta_bar_jack,
        cv3j_variance,
        cv3j_se,
    ) = cv3j(
        panel,
        beta_hat,
    )

    g = EXPECTED_WELLS
    df_cluster = g - 1
    tcrit = float(
        stats.t.ppf(
            0.975,
            df_cluster,
        )
    )

    cv3j_ci_low = float(
        beta_hat
        - tcrit * cv3j_se
    )

    cv3j_ci_high = float(
        beta_hat
        + tcrit * cv3j_se
    )

    # ---------------------------------------------------------
    # 6. PRIMARY small-cluster bootstrap test: WCR31 Webb.
    # ---------------------------------------------------------

    # wildboottest 0.3.2 + Numba requires a numeric cluster array.
    # Scientific clustering is unchanged: one deterministic integer code
    # corresponds one-to-one with each groundwater-well station.
    cluster_codes, cluster_levels = pd.factorize(
        panel["station"],
        sort=True,
    )
    cluster = np.asarray(cluster_codes, dtype=np.int64)

    if len(cluster_levels) != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} bootstrap cluster levels; "
            f"found {len(cluster_levels)}."
        )

    wb = wildboottest(
        model,
        param=EXPOSURE,
        cluster=cluster,
        B=B,
        bootstrap_type=BOOTSTRAP_TYPE,
        impose_null=IMPOSE_NULL,
        weights_type=WEIGHTS_TYPE,
        seed=SEED,
        parallel=False,
        show=False,
    )

    wb_p = extract_wild_bootstrap_pvalue(
        wb,
        EXPOSURE,
    )

    # ---------------------------------------------------------
    # 7. BENCHMARK: CRV1 clustered by station.
    # ---------------------------------------------------------

    crv1 = fit.get_robustcov_results(
        cov_type="cluster",
        groups=panel["station"],
        use_correction=True,
        df_correction=True,
    )

    names = list(
        fit.model.exog_names
    )

    exposure_idx = names.index(
        EXPOSURE
    )

    crv1_se = float(
        np.asarray(
            crv1.bse
        )[exposure_idx]
    )

    crv1_t = float(
        beta_hat
        / crv1_se
    )

    crv1_p = float(
        2.0
        * stats.t.sf(
            abs(crv1_t),
            df_cluster,
        )
    )

    crv1_ci_low = float(
        beta_hat
        - tcrit * crv1_se
    )

    crv1_ci_high = float(
        beta_hat
        + tcrit * crv1_se
    )

    # ---------------------------------------------------------
    # 8. CONTINUITY diagnostic: HC3.
    # ---------------------------------------------------------

    hc3 = fit.get_robustcov_results(
        cov_type="HC3"
    )

    hc3_se = float(
        np.asarray(
            hc3.bse
        )[exposure_idx]
    )

    hc3_t = float(
        beta_hat
        / hc3_se
    )

    hc3_p = float(
        2.0
        * stats.t.sf(
            abs(hc3_t),
            fit.df_resid,
        )
    )

    hc3_tcrit = float(
        stats.t.ppf(
            0.975,
            fit.df_resid,
        )
    )

    hc3_ci_low = float(
        beta_hat
        - hc3_tcrit * hc3_se
    )

    hc3_ci_high = float(
        beta_hat
        + hc3_tcrit * hc3_se
    )

    # ---------------------------------------------------------
    # 9. Persist complete primary result symmetrically.
    # ---------------------------------------------------------

    result = pd.DataFrame(
        [
            {
                "stage": "STAGE_5_PRIMARY_REVEAL",
                "sample": "balanced_12_well_2022_2025",
                "outcome": OUTCOME,
                "exposure": EXPOSURE,
                "antecedent": ANTECEDENT,
                "formula": FORMULA,
                "n": int(
                    fit.nobs
                ),
                "n_wells": int(
                    panel["station"].nunique()
                ),
                "n_years": int(
                    panel["year"].nunique()
                ),
                "beta_hat_per_1_ff10": beta_hat,
                "beta_hat_per_0_01_ff10": float(
                    0.01 * beta_hat
                ),
                "cv3j_beta_bar_jack": beta_bar_jack,
                "cv3j_variance": cv3j_variance,
                "cv3j_se": cv3j_se,
                "cv3j_df": df_cluster,
                "cv3j_ci95_low": cv3j_ci_low,
                "cv3j_ci95_high": cv3j_ci_high,
                "wcr31_webb_p_value": wb_p,
                "wcr31_B": B,
                "wcr31_seed": SEED,
                "crv1_se": crv1_se,
                "crv1_t": crv1_t,
                "crv1_df": df_cluster,
                "crv1_p_value": crv1_p,
                "crv1_ci95_low": crv1_ci_low,
                "crv1_ci95_high": crv1_ci_high,
                "hc3_se": hc3_se,
                "hc3_t": hc3_t,
                "hc3_df_resid": float(
                    fit.df_resid
                ),
                "hc3_p_value": hc3_p,
                "hc3_ci95_low": hc3_ci_low,
                "hc3_ci95_high": hc3_ci_high,
                "r_squared": float(
                    fit.rsquared
                ),
                "adj_r_squared": float(
                    fit.rsquared_adj
                ),
                "design_matrix_rank": rank,
                "design_matrix_columns": n_columns,
                "interpretation_scope": (
                    "non-causal adjusted within-well association"
                ),
            }
        ]
    )

    result.to_csv(
        PRIMARY_RESULT_OUT,
        index=False,
    )

    loo.to_csv(
        LOO_OUT,
        index=False,
    )

    panel.to_csv(
        ANALYSIS_PANEL_OUT,
        index=False,
    )

    qa = {
        "status": "PASS_PRIMARY_REVEAL_COMPLETED",
        "stage4_status_required": "STAGE 4 FROZEN",
        "smoke_test_status": smoke.get("status"),
        "smoke_test_firewall": smoke.get("firewall"),
        "n_rows": int(
            len(panel)
        ),
        "n_wells": int(
            panel["station"].nunique()
        ),
        "years": [
            int(y)
            for y in sorted(
                panel["year"].unique()
            )
        ],
        "rows_per_well": {
            str(k): int(v)
            for k, v in panel.groupby(
                "station"
            )["year"].nunique().to_dict().items()
        },
        "missing_primary_values": int(
            panel[
                [
                    OUTCOME,
                    EXPOSURE,
                    ANTECEDENT,
                ]
            ].isna().sum().sum()
        ),
        "duplicate_station_year_rows": int(
            panel.duplicated(
                [
                    "station",
                    "year",
                ]
            ).sum()
        ),
        "design_matrix_rank": rank,
        "design_matrix_columns": n_columns,
        **residual_gate,
        "primary_result_file": str(
            PRIMARY_RESULT_OUT.relative_to(ROOT)
        ),
        "leave_one_well_file": str(
            LOO_OUT.relative_to(ROOT)
        ),
        "analysis_panel_file": str(
            ANALYSIS_PANEL_OUT.relative_to(ROOT)
        ),
        "software_file": str(
            SOFTWARE_OUT.relative_to(ROOT)
        ),
    }

    QA_OUT.write_text(
        json.dumps(
            qa,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # ---------------------------------------------------------
    # 10. Terminal record.
    # ---------------------------------------------------------

    print("=== STAGE 5 CONTROLLED PRIMARY REVEAL ===")
    print(f"formula: {FORMULA}")
    print(f"rows: {len(panel)}")
    print(
        "wells: "
        f"{panel['station'].nunique()}"
    )
    print(
        "years: "
        + ", ".join(
            str(y)
            for y in sorted(
                panel["year"].unique()
            )
        )
    )
    print(
        f"design rank: {rank}/{n_columns}"
    )
    print(
        "FF10 partial residual SD: "
        f"{residual_gate['ff10_partial_residual_sd']:.12g}"
    )
    print("")
    print(
        "PRIMARY beta per 1.0 FF10: "
        f"{beta_hat:.12g}"
    )
    print(
        "PRIMARY beta per 0.01 FF10: "
        f"{0.01 * beta_hat:.12g} m"
    )
    print(
        "CV3J SE: "
        f"{cv3j_se:.12g}"
    )
    print(
        "CV3J 95% CI: "
        f"[{cv3j_ci_low:.12g}, {cv3j_ci_high:.12g}]"
    )
    print(
        "WCR31 Webb two-sided p-value: "
        f"{wb_p:.12g}"
    )
    print("")
    print(
        "CRV1 SE / p: "
        f"{crv1_se:.12g} / {crv1_p:.12g}"
    )
    print(
        "HC3 SE / p: "
        f"{hc3_se:.12g} / {hc3_p:.12g}"
    )
    print("")
    print(
        f"primary result: {PRIMARY_RESULT_OUT}"
    )
    print(
        f"LOO CV3J file: {LOO_OUT}"
    )
    print(
        f"QA file: {QA_OUT}"
    )
    print(
        "STAGE 5 PRIMARY REVEAL: COMPLETED"
    )
    print(
        "INTERPRETATION: NOT YET WRITTEN; "
        "proceed next to Stage 6 information-content audit."
    )


if __name__ == "__main__":
    main()

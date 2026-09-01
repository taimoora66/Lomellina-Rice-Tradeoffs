"""Stage 7 — Prespecified robustness and stability analysis.

Scientific role
---------------
Execute the robustness/stability hierarchy frozen in Stage 4 after the
Stage-5 primary reveal and Stage-6/6R information audits.

THIS SCRIPT DOES NOT ALTER OR REPLACE THE PRIMARY RESULT.

Frozen primary result:
    12 balanced wells, 48 rows, 2022-2025
    Y ~ F + A + C(station) + C(year)

Stage-7 analyses:
1. Primary leave-one-year-out temporal stability diagnostic.
2. Primary 12-well weather robustness:
       W1: Y ~ F + A + P_A8 + well FE + year FE
       W2: Y ~ F + A + T_A8 + well FE + year FE
       W3: Y ~ F + A + P_A8 + T_A8 + well FE + year FE
3. Secondary 18-well >=2-year unbalanced robustness population.
4. Diagnostic 14-well >=3-year sample-stability population.
5. Weather W1-W3 on the secondary population as an additional
   prespecified robustness layer, because weather availability was previously
   audited as complete for all eligible station-years.

For Stage-7 association models (except leave-one-year coefficient-only
diagnostics), the frozen Stage-4 inferential hierarchy is retained:
    - OLS beta on FF10
    - leave-one-well-out CV3J jackknife SE
    - 95% t CI with G-1 df
    - WCR31 restricted wild-cluster-bootstrap p-value
      Webb weights, null imposed, B=9999, seed=20260831
    - CRV1 benchmark
    - HC3 continuity diagnostic

No result can promote a robustness model to primary status.
No well/year is deleted because of its result.
No radius, anomaly baseline, outcome, FE structure, or antecedent definition
is changed.

CR2/Satterthwaite is NOT silently approximated here. It was not part of the
frozen Stage-4 hierarchy; an exact implementation, if later added, must be
clearly labelled supplementary/post-result.
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf
from wildboottest.wildboottest import wildboottest


ROOT = Path(__file__).resolve().parents[2]

GW_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "groundwater_annual_measures_2008_2025.csv"
)
FF_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "well_frozen_ff10_exposures_2022_2025.csv"
)
WEATHER_IN = (
    ROOT / "data" / "processed" / "post2021"
    / "well_weather_A8_2022_2025.csv"
)

PRIMARY_IDS_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "post2021_integrated_balanced4_sample_ids.csv"
)
DIAGNOSTIC_IDS_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "post2021_integrated_at_least3_sample_ids.csv"
)
SECONDARY_IDS_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "post2021_integrated_at_least2_sample_ids.csv"
)

STAGE5_RESULT_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage5_primary_groundwater_result_2022_2025.csv"
)
STAGE6R_QA_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage6r_replication_qa.json"
)

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

RESULTS_OUT = OUT_DIR / "stage7_robustness_results_2022_2025.csv"
LOO_YEAR_OUT = OUT_DIR / "stage7_primary_leave_one_year_out.csv"
LOO_WELL_OUT = OUT_DIR / "stage7_model_leave_one_well_ranges.csv"
PANELS_OUT = OUT_DIR / "stage7_sample_panel_audit.csv"
SOFTWARE_OUT = OUT_DIR / "stage7_software.json"
QA_OUT = OUT_DIR / "stage7_robustness_qa.json"
REPORT_OUT = OUT_DIR / "stage7_robustness_summary.txt"

YEARS = (2022, 2023, 2024, 2025)

OUTCOME = "gw_aug_nearest_aug23_m"
EXPOSURE = "ff10_anomaly_2010_2021"
ANTECEDENT = "gw_pre_last_janfeb_m"
PRECIP = "P_A8"
TEMP = "T_A8"

B = 9999
SEED = 20260831
BOOTSTRAP_TYPE = "31"
WEIGHTS_TYPE = "webb"
IMPOSE_NULL = True

EXPECTED = {
    "primary": {"wells": 12, "rows": 48, "min_years": 4},
    "diagnostic14": {"wells": 14, "rows": 54, "min_years": 3},
    "secondary18": {"wells": 18, "rows": 62, "min_years": 2},
}

FORMULAS = {
    "base": (
        f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} "
        "+ C(station) + C(year)"
    ),
    "W1_precip": (
        f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} + {PRECIP} "
        "+ C(station) + C(year)"
    ),
    "W2_temp": (
        f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} + {TEMP} "
        "+ C(station) + C(year)"
    ),
    "W3_precip_temp": (
        f"{OUTCOME} ~ {EXPOSURE} + {ANTECEDENT} "
        f"+ {PRECIP} + {TEMP} "
        "+ C(station) + C(year)"
    ),
}


def require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def extract_wild_pvalue(result: pd.DataFrame) -> float:
    if EXPOSURE in result.index and "p-value" in result.columns:
        p = float(result.loc[EXPOSURE, "p-value"])
    elif "param" in result.columns and "p-value" in result.columns:
        row = result.loc[result["param"].astype(str) == EXPOSURE]
        if len(row) != 1:
            raise RuntimeError(
                f"Could not uniquely identify wild-bootstrap row for {EXPOSURE}."
            )
        p = float(row["p-value"].iloc[0])
    else:
        raise RuntimeError("Unsupported wildboottest result layout.")

    if not np.isfinite(p) or not 0 <= p <= 1:
        raise RuntimeError(f"Invalid wild-bootstrap p-value: {p}")
    return p


def read_ids(
    path: Path,
    expected_n: int,
    label: str,
    expected_min_years: int,
) -> list[str]:
    """Read frozen sample-ID artifacts without assuming identical schemas.

    The balanced-four-year artifact contains only ``station``.
    The >=3-year and >=2-year artifacts additionally preserve the pre-result
    eligibility audit columns ``eligible_years_n`` and
    ``eligible_year_pattern``. Those columns are validated when present.
    """
    require(path, label)
    ids = pd.read_csv(path)

    if "station" not in ids.columns:
        raise AssertionError(f"{label}: missing station column.")

    allowed = {
        "station",
        "eligible_years_n",
        "eligible_year_pattern",
    }
    unexpected = set(ids.columns) - allowed
    if unexpected:
        raise AssertionError(
            f"{label}: unexpected columns {sorted(unexpected)}."
        )

    ids["station"] = ids["station"].astype(str)

    if ids["station"].duplicated().any():
        raise AssertionError(f"{label}: duplicate stations.")

    if len(ids) != expected_n:
        raise AssertionError(
            f"{label}: expected {expected_n} wells, found {len(ids)}."
        )

    if "eligible_years_n" in ids.columns:
        ids["eligible_years_n"] = pd.to_numeric(
            ids["eligible_years_n"],
            errors="raise",
        ).astype(int)

        if (ids["eligible_years_n"] < expected_min_years).any():
            bad = ids.loc[
                ids["eligible_years_n"] < expected_min_years,
                ["station", "eligible_years_n"],
            ]
            raise AssertionError(
                f"{label}: frozen eligibility-year count below "
                f"{expected_min_years}:\n{bad.to_string(index=False)}"
            )

    if "eligible_year_pattern" in ids.columns:
        if ids["eligible_year_pattern"].isna().any():
            raise AssertionError(
                f"{label}: missing eligible_year_pattern."
            )

        # Independently verify the pattern contains the same number of years
        # as eligible_years_n whenever both audit columns are present.
        if "eligible_years_n" in ids.columns:
            pattern_n = (
                ids["eligible_year_pattern"]
                .astype(str)
                .str.split("_")
                .map(len)
                .astype(int)
            )

            if not np.array_equal(
                pattern_n.to_numpy(),
                ids["eligible_years_n"].to_numpy(),
            ):
                raise AssertionError(
                    f"{label}: eligible_year_pattern does not agree with "
                    "eligible_years_n."
                )

    return sorted(ids["station"].tolist())


def build_integrated_source() -> pd.DataFrame:
    """Merge frozen groundwater, exposure, and weather source products."""
    for path, label in [
        (GW_IN, "Groundwater annual measures"),
        (FF_IN, "Frozen FF10 exposures"),
        (WEATHER_IN, "Weather A8 panel"),
    ]:
        require(path, label)

    gw = pd.read_csv(
        GW_IN,
        usecols=[
            "station", "year", "aquifer_group",
            OUTCOME, ANTECEDENT,
        ],
    )
    ff = pd.read_csv(
        FF_IN,
        usecols=[
            "station", "year", EXPOSURE, "n_cells_10km",
        ],
    )
    wx = pd.read_csv(
        WEATHER_IN,
        usecols=[
            "station", "year", PRECIP, TEMP,
        ],
    )

    for d in (gw, ff, wx):
        d["station"] = d["station"].astype(str)
        d["year"] = pd.to_numeric(d["year"], errors="raise").astype(int)

    gw = gw.loc[
        gw["year"].isin(YEARS)
        & gw["aquifer_group"].eq("ISS")
    ].copy()
    ff = ff.loc[ff["year"].isin(YEARS)].copy()
    wx = wx.loc[wx["year"].isin(YEARS)].copy()

    for d, label in [(gw, "GW"), (ff, "FF"), (wx, "weather")]:
        if d.duplicated(["station", "year"]).any():
            raise AssertionError(f"{label}: duplicate station-year rows.")

    merged = (
        gw.merge(
            ff,
            on=["station", "year"],
            how="left",
            validate="one_to_one",
        )
        .merge(
            wx,
            on=["station", "year"],
            how="left",
            validate="one_to_one",
        )
    )

    return merged


def build_sample(
    source: pd.DataFrame,
    stations: list[str],
    sample_name: str,
) -> pd.DataFrame:
    exp = EXPECTED[sample_name]

    d = source.loc[
        source["station"].isin(stations)
        & source["year"].isin(YEARS)
        & source[OUTCOME].notna()
        & source[ANTECEDENT].notna()
        & source[EXPOSURE].notna()
        & (source["n_cells_10km"] > 0)
    ].copy()

    d = d.sort_values(["station", "year"]).reset_index(drop=True)

    if len(d) != exp["rows"]:
        raise AssertionError(
            f"{sample_name}: expected {exp['rows']} rows, found {len(d)}."
        )
    if d["station"].nunique() != exp["wells"]:
        raise AssertionError(
            f"{sample_name}: expected {exp['wells']} wells, "
            f"found {d['station'].nunique()}."
        )
    if set(d["station"]) != set(stations):
        raise AssertionError(f"{sample_name}: station membership mismatch.")
    if d.duplicated(["station", "year"]).any():
        raise AssertionError(f"{sample_name}: duplicate station-year rows.")

    n_years = d.groupby("station")["year"].nunique()
    if (n_years < exp["min_years"]).any():
        raise AssertionError(
            f"{sample_name}: a well has fewer than {exp['min_years']} years."
        )

    # Weather had already been audited as complete; enforce that fact here.
    if d[[PRECIP, TEMP]].isna().any().any():
        raise AssertionError(
            f"{sample_name}: weather missing despite frozen availability audit."
        )

    return d


def residual_exposure_sd(d: pd.DataFrame, extra_controls: list[str]) -> float:
    rhs = [ANTECEDENT] + extra_controls + ["C(station)", "C(year)"]
    aux = smf.ols(
        f"{EXPOSURE} ~ " + " + ".join(rhs),
        data=d,
    ).fit()

    r = np.asarray(aux.resid, dtype=float)
    sd = float(np.std(r, ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        raise AssertionError("Exposure has zero/non-finite partial residual SD.")
    return sd


def cv3j(
    d: pd.DataFrame,
    formula: str,
    beta_full: float,
) -> tuple[float, float, float, pd.DataFrame]:
    stations = sorted(d["station"].unique())
    G = len(stations)
    rows = []

    for station in stations:
        sub = d.loc[d["station"] != station].copy()
        fit = smf.ols(formula, data=sub).fit()

        if EXPOSURE not in fit.params.index:
            raise AssertionError(
                f"LOO {station}: exposure became non-estimable."
            )

        b = float(fit.params[EXPOSURE])
        rows.append(
            {
                "omitted_station": station,
                "beta_minus_g": b,
                "change_from_full_beta": b - beta_full,
                "absolute_change_from_full_beta": abs(b - beta_full),
                "coefficient_sign": (
                    "positive" if b > 0
                    else "negative" if b < 0
                    else "zero"
                ),
            }
        )

    loo = pd.DataFrame(rows)
    vals = loo["beta_minus_g"].to_numpy(dtype=float)
    bar = float(vals.mean())

    variance = float(
        ((G - 1) / G) * np.sum((vals - bar) ** 2)
    )
    se = float(np.sqrt(variance))
    tcrit = float(stats.t.ppf(0.975, df=G - 1))
    lo = float(beta_full - tcrit * se)
    hi = float(beta_full + tcrit * se)

    return se, lo, hi, loo


def run_wild_bootstrap(
    model,
    d: pd.DataFrame,
) -> float:
    """Run the exact Stage-5 wildboottest 0.3.2 API.

    wildboottest expects the unfitted statsmodels model object, not the fitted
    OLSResults object. Numeric station codes are used one-to-one exactly as in
    the verified Stage-5 implementation.
    """
    codes, levels = pd.factorize(d["station"], sort=True)

    if len(levels) != d["station"].nunique():
        raise AssertionError("Cluster-code construction failed.")

    cluster = np.asarray(codes, dtype=np.int64)

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

    return extract_wild_pvalue(wb)


def infer_model(
    d: pd.DataFrame,
    sample_name: str,
    model_name: str,
    formula: str,
    extra_controls: list[str],
) -> tuple[dict, pd.DataFrame]:
    model = smf.ols(formula, data=d)
    fit = model.fit()

    x = np.asarray(fit.model.exog, dtype=float)
    rank = int(np.linalg.matrix_rank(x))
    cols = int(x.shape[1])

    if rank != cols:
        raise AssertionError(
            f"{sample_name}/{model_name}: rank {rank}/{cols}."
        )

    if EXPOSURE not in fit.params.index:
        raise AssertionError(
            f"{sample_name}/{model_name}: FF10 coefficient not estimable."
        )

    beta = float(fit.params[EXPOSURE])
    G = int(d["station"].nunique())
    N = int(len(d))
    df_cluster = G - 1

    partial_sd = residual_exposure_sd(d, extra_controls)

    cv3_se, cv3_lo, cv3_hi, loo = cv3j(
        d,
        formula,
        beta,
    )

    wb_p = run_wild_bootstrap(model, d)

    crv = fit.get_robustcov_results(
        cov_type="cluster",
        groups=d["station"],
        use_correction=True,
    )
    param_names = list(fit.params.index)
    j = param_names.index(EXPOSURE)

    crv_se = float(crv.bse[j])
    crv_t = float(beta / crv_se)
    crv_p = float(2 * stats.t.sf(abs(crv_t), df=df_cluster))
    crv_tcrit = float(stats.t.ppf(0.975, df=df_cluster))
    crv_lo = float(beta - crv_tcrit * crv_se)
    crv_hi = float(beta + crv_tcrit * crv_se)

    hc3 = fit.get_robustcov_results(cov_type="HC3")
    hc3_se = float(hc3.bse[j])
    hc3_t = float(beta / hc3_se)
    hc3_p = float(2 * stats.t.sf(abs(hc3_t), df=fit.df_resid))
    hc3_tcrit = float(stats.t.ppf(0.975, df=fit.df_resid))
    hc3_lo = float(beta - hc3_tcrit * hc3_se)
    hc3_hi = float(beta + hc3_tcrit * hc3_se)

    row = {
        "sample": sample_name,
        "model": model_name,
        "formula": formula,
        "n_rows": N,
        "n_wells": G,
        "design_rank": rank,
        "design_columns": cols,
        "ff10_partial_residual_sd": partial_sd,
        "beta_per_1_ff10": beta,
        "beta_per_0_01_ff10_m": 0.01 * beta,
        "cv3j_se": cv3_se,
        "cv3j_ci_low": cv3_lo,
        "cv3j_ci_high": cv3_hi,
        "cv3j_df": df_cluster,
        "wcr31_webb_p": wb_p,
        "bootstrap_B": B,
        "bootstrap_seed": SEED,
        "crv1_se": crv_se,
        "crv1_p": crv_p,
        "crv1_ci_low": crv_lo,
        "crv1_ci_high": crv_hi,
        "hc3_se": hc3_se,
        "hc3_p": hc3_p,
        "hc3_ci_low": hc3_lo,
        "hc3_ci_high": hc3_hi,
        "loo_beta_min": float(loo["beta_minus_g"].min()),
        "loo_beta_max": float(loo["beta_minus_g"].max()),
        "loo_sign_change_across_omissions": bool(
            (loo["beta_minus_g"] > 0).any()
            and (loo["beta_minus_g"] < 0).any()
        ),
        "loo_max_abs_beta_change": float(
            loo["absolute_change_from_full_beta"].max()
        ),
        "loo_most_influential_station": str(
            loo.loc[
                loo["absolute_change_from_full_beta"].idxmax(),
                "omitted_station",
            ]
        ),
        "status": "COMPLETED",
        "primary_status": (
            "PRIMARY_FROZEN" if sample_name == "primary"
            and model_name == "base_identity"
            else "ROBUSTNESS_OR_DIAGNOSTIC"
        ),
    }

    loo["sample"] = sample_name
    loo["model"] = model_name
    loo["full_beta"] = beta

    return row, loo


def primary_leave_one_year(
    primary: pd.DataFrame,
    full_beta: float,
) -> pd.DataFrame:
    rows = []

    for omitted_year in YEARS:
        d = primary.loc[primary["year"] != omitted_year].copy()
        formula = FORMULAS["base"]
        fit = smf.ols(formula, data=d).fit()

        x = np.asarray(fit.model.exog, dtype=float)
        rank = int(np.linalg.matrix_rank(x))
        cols = int(x.shape[1])

        if rank != cols:
            raise AssertionError(
                f"LOO-year {omitted_year}: rank {rank}/{cols}."
            )

        beta = float(fit.params[EXPOSURE])

        rows.append(
            {
                "omitted_year": omitted_year,
                "remaining_years": ";".join(
                    str(y) for y in YEARS if y != omitted_year
                ),
                "n_rows": int(len(d)),
                "n_wells": int(d["station"].nunique()),
                "design_rank": rank,
                "design_columns": cols,
                "beta_per_1_ff10": beta,
                "beta_per_0_01_ff10_m": 0.01 * beta,
                "change_from_full_primary_beta": beta - full_beta,
                "absolute_change_from_full_primary_beta": abs(
                    beta - full_beta
                ),
                "coefficient_sign": (
                    "positive" if beta > 0
                    else "negative" if beta < 0
                    else "zero"
                ),
                "role": "TEMPORAL_STABILITY_DIAGNOSTIC_ONLY",
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    require(STAGE5_RESULT_IN, "Stage-5 primary result")
    require(STAGE6R_QA_IN, "Stage-6R replication QA")

    stage6r = json.loads(STAGE6R_QA_IN.read_text(encoding="utf-8"))
    if stage6r.get("status") != "PASS":
        raise AssertionError("Stage 6R must PASS before Stage 7.")

    source = build_integrated_source()

    primary_ids = read_ids(
        PRIMARY_IDS_IN,
        EXPECTED["primary"]["wells"],
        "Primary IDs",
        expected_min_years=4,
    )
    diagnostic_ids = read_ids(
        DIAGNOSTIC_IDS_IN,
        EXPECTED["diagnostic14"]["wells"],
        "At-least-3-year IDs",
        expected_min_years=3,
    )
    secondary_ids = read_ids(
        SECONDARY_IDS_IN,
        EXPECTED["secondary18"]["wells"],
        "At-least-2-year IDs",
        expected_min_years=2,
    )

    primary = build_sample(source, primary_ids, "primary")
    diagnostic = build_sample(source, diagnostic_ids, "diagnostic14")
    secondary = build_sample(source, secondary_ids, "secondary18")

    panel_rows = []
    for name, d in [
        ("primary", primary),
        ("diagnostic14", diagnostic),
        ("secondary18", secondary),
    ]:
        year_counts = d.groupby("year")["station"].nunique().to_dict()
        panel_rows.append(
            {
                "sample": name,
                "n_rows": len(d),
                "n_wells": d["station"].nunique(),
                "min_years_per_well": int(
                    d.groupby("station")["year"].nunique().min()
                ),
                "max_years_per_well": int(
                    d.groupby("station")["year"].nunique().max()
                ),
                **{
                    f"wells_{year}": int(year_counts.get(year, 0))
                    for year in YEARS
                },
            }
        )
    pd.DataFrame(panel_rows).to_csv(PANELS_OUT, index=False)

    saved = pd.read_csv(STAGE5_RESULT_IN)
    if len(saved) != 1:
        raise AssertionError("Stage-5 result must contain one row.")
    saved_beta = float(saved.iloc[0]["beta_hat_per_1_ff10"])

    # Identity fit only: ensures Stage 7's rebuilt primary panel reproduces Stage 5.
    identity_fit = smf.ols(FORMULAS["base"], data=primary).fit()
    identity_beta = float(identity_fit.params[EXPOSURE])
    if not np.isclose(saved_beta, identity_beta, atol=1e-10, rtol=0):
        raise AssertionError(
            f"Stage-7 rebuilt primary beta {identity_beta} "
            f"does not reproduce Stage-5 beta {saved_beta}."
        )

    # Leave-one-year temporal stability, coefficient only per frozen Stage 4.
    loo_year = primary_leave_one_year(primary, saved_beta)
    loo_year.to_csv(LOO_YEAR_OUT, index=False)

    results = []
    all_loo = []

    # Primary base identity is NOT reclassified as a new result. We calculate
    # it through the full inferential engine only to ensure the implementation
    # continues to reproduce the frozen primary hierarchy exactly.
    row, loo = infer_model(
        primary,
        "primary",
        "base_identity",
        FORMULAS["base"],
        [],
    )
    results.append(row)
    all_loo.append(loo)

    # Prespecified primary weather robustness W1-W3.
    for model_name, extras in [
        ("W1_precip", [PRECIP]),
        ("W2_temp", [TEMP]),
        ("W3_precip_temp", [PRECIP, TEMP]),
    ]:
        row, loo = infer_model(
            primary,
            "primary",
            model_name,
            FORMULAS[model_name],
            extras,
        )
        results.append(row)
        all_loo.append(loo)

    # Prespecified secondary 18-well base robustness.
    row, loo = infer_model(
        secondary,
        "secondary18",
        "base",
        FORMULAS["base"],
        [],
    )
    results.append(row)
    all_loo.append(loo)

    # Weather robustness on the secondary population. This is a transparent
    # extension of the already-frozen weather robustness hierarchy; it cannot
    # supersede the primary balanced result.
    for model_name, extras in [
        ("W1_precip", [PRECIP]),
        ("W2_temp", [TEMP]),
        ("W3_precip_temp", [PRECIP, TEMP]),
    ]:
        row, loo = infer_model(
            secondary,
            "secondary18",
            model_name,
            FORMULAS[model_name],
            extras,
        )
        results.append(row)
        all_loo.append(loo)

    # Prespecified 14-well sample-stability diagnostic, base model only.
    row, loo = infer_model(
        diagnostic,
        "diagnostic14",
        "base",
        FORMULAS["base"],
        [],
    )
    results.append(row)
    all_loo.append(loo)

    results_df = pd.DataFrame(results)
    results_df.to_csv(RESULTS_OUT, index=False)

    loo_all = pd.concat(all_loo, ignore_index=True)
    loo_all.to_csv(LOO_WELL_OUT, index=False)

    software = {
        "wildboottest": package_version("wildboottest"),
        "statsmodels": package_version("statsmodels"),
        "numpy": package_version("numpy"),
        "pandas": package_version("pandas"),
        "scipy": package_version("scipy"),
        "bootstrap": {
            "type": BOOTSTRAP_TYPE,
            "weights": WEIGHTS_TYPE,
            "impose_null": IMPOSE_NULL,
            "B": B,
            "seed": SEED,
        },
    }
    SOFTWARE_OUT.write_text(
        json.dumps(software, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Summary QA.
    identity = results_df.loc[
        (results_df["sample"] == "primary")
        & (results_df["model"] == "base_identity")
    ].iloc[0]

    stage5_wcr = (
        float(saved.iloc[0]["wcr31_webb_p"])
        if "wcr31_webb_p" in saved.columns
        else None
    )
    stage5_cv3 = (
        float(saved.iloc[0]["cv3j_se"])
        if "cv3j_se" in saved.columns
        else None
    )

    qa = {
        "status": "PASS",
        "stage": "STAGE_7_PRESPECIFIED_ROBUSTNESS_AND_STABILITY",
        "primary_model_changed": False,
        "primary_sample_changed": False,
        "primary_beta_stage5": saved_beta,
        "primary_beta_stage7_identity": float(
            identity["beta_per_1_ff10"]
        ),
        "primary_beta_identity_abs_diff": abs(
            saved_beta - float(identity["beta_per_1_ff10"])
        ),
        "stage5_cv3j_se_if_available": stage5_cv3,
        "stage7_identity_cv3j_se": float(identity["cv3j_se"]),
        "stage5_wcr31_p_if_available": stage5_wcr,
        "stage7_identity_wcr31_p": float(identity["wcr31_webb_p"]),
        "models_completed": int(len(results_df)),
        "primary_weather_models": 3,
        "secondary_base_models": 1,
        "secondary_weather_models": 3,
        "diagnostic14_models": 1,
        "loo_year_fits": int(len(loo_year)),
        "selection_rule": (
            "No robustness or diagnostic result may replace the frozen "
            "Stage-5 primary result according to sign, magnitude, precision, "
            "confidence interval, or p-value."
        ),
        "cr2_rule": (
            "CR2/Satterthwaite not computed because it was not frozen in "
            "Stage 4 and no approximate implementation is silently substituted."
        ),
    }
    QA_OUT.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Human-readable summary without interpretation based on significance.
    lines = [
        "STAGE 7 — PRESPECIFIED ROBUSTNESS AND STABILITY",
        "================================================",
        "",
        f"Primary Stage-5 beta identity: {saved_beta:.12g}",
        f"Models completed: {len(results_df)}",
        "",
        "MODEL RESULTS",
        "-------------",
    ]

    for _, r in results_df.iterrows():
        lines.extend(
            [
                f"{r['sample']} / {r['model']}",
                (
                    f"  N={int(r['n_rows'])}, G={int(r['n_wells'])}, "
                    f"beta={r['beta_per_1_ff10']:.12g}"
                ),
                (
                    f"  CV3J SE={r['cv3j_se']:.12g}, "
                    f"95% CI=[{r['cv3j_ci_low']:.12g}, "
                    f"{r['cv3j_ci_high']:.12g}]"
                ),
                f"  WCR31-Webb p={r['wcr31_webb_p']:.12g}",
                (
                    f"  CRV1 SE/p={r['crv1_se']:.12g}/"
                    f"{r['crv1_p']:.12g}"
                ),
                (
                    f"  HC3 SE/p={r['hc3_se']:.12g}/"
                    f"{r['hc3_p']:.12g}"
                ),
                (
                    f"  LOO beta range=[{r['loo_beta_min']:.12g}, "
                    f"{r['loo_beta_max']:.12g}], "
                    f"max abs change={r['loo_max_abs_beta_change']:.12g}"
                ),
                "",
            ]
        )

    lines.extend(
        [
            "PRIMARY LEAVE-ONE-YEAR TEMPORAL DIAGNOSTIC",
            "------------------------------------------",
        ]
    )
    for _, r in loo_year.iterrows():
        lines.append(
            f"omit {int(r['omitted_year'])}: "
            f"beta={r['beta_per_1_ff10']:.12g}, "
            f"change={r['change_from_full_primary_beta']:.12g}"
        )

    lines.extend(
        [
            "",
            "REPORTING FIREWALL",
            "------------------",
            (
                "The frozen Stage-5 balanced result remains primary regardless "
                "of all Stage-7 results."
            ),
            (
                "Weather, secondary-population, diagnostic-population, and "
                "leave-one-out results assess robustness/stability only."
            ),
            (
                "CR2/Satterthwaite is not approximated or silently substituted."
            ),
        ]
    )

    REPORT_OUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("=== STAGE 7 PRESPECIFIED ROBUSTNESS AND STABILITY ===")
    print(f"Stage-5 primary beta reproduced: {saved_beta:.12g}")
    print("")
    for _, r in results_df.iterrows():
        print(
            f"{r['sample']} / {r['model']}: "
            f"N={int(r['n_rows'])}, G={int(r['n_wells'])}, "
            f"beta={r['beta_per_1_ff10']:.12g}, "
            f"CV3J SE={r['cv3j_se']:.12g}, "
            f"WCR31 p={r['wcr31_webb_p']:.12g}, "
            f"LOO max change={r['loo_max_abs_beta_change']:.12g}"
        )

    print("")
    print("PRIMARY LEAVE-ONE-YEAR")
    for _, r in loo_year.iterrows():
        print(
            f"omit {int(r['omitted_year'])}: "
            f"beta={r['beta_per_1_ff10']:.12g}, "
            f"change={r['change_from_full_primary_beta']:.12g}"
        )

    print("")
    print(f"results: {RESULTS_OUT}")
    print(f"QA: {QA_OUT}")
    print("STAGE 7 ROBUSTNESS/STABILITY: PASS")
    print("FROZEN STAGE-5 PRIMARY RESULT: UNCHANGED")


if __name__ == "__main__":
    main()

"""Run the frozen 2022-2023 held-out groundwater confirmation.

IMPORTANT
---------
The model architecture, sample rule, exposure definition, outcome,
antecedent, weather robustness specifications, and influence diagnostics
were frozen in docs/post2021/BRIDGE_PROTOCOL.md before groundwater-depth
values were inspected in relation to flooding exposure.

Frozen primary model
--------------------
First differences across 13 repeated ISS wells:

    delta_aug_gw ~ delta_ff10 + delta_pre_gw

Inference:
    OLS coefficients with HC3 heteroskedasticity-robust covariance.

Prespecified robustness:
    W1: + delta_P_A8
    W2: + delta_T_A8
    W3: + delta_P_A8 + delta_T_A8

Prespecified influence diagnostics:
    - leave-one-well-out primary beta
    - leverage
    - Cook's distance

No observation is deleted.
No alternative radius, outcome, exposure definition, or model is searched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path(__file__).resolve().parents[2]

GW_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "groundwater_annual_measures_2008_2023.csv"
)

FF_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2023.csv"
)

WEATHER_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_weather_A8_2022_2023.csv"
)

FROZEN_IDS_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_primary_repeated_sample_ids.csv"
)

OUT_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

MODEL_OUT = (
    OUT_DIR
    / "heldout_groundwater_model_results.csv"
)

PRIMARY_OUT = (
    OUT_DIR
    / "heldout_groundwater_primary_result.csv"
)

INFLUENCE_OUT = (
    OUT_DIR
    / "heldout_groundwater_primary_influence.csv"
)

LOO_OUT = (
    OUT_DIR
    / "heldout_groundwater_primary_leave_one_out.csv"
)

SAMPLE_QA_OUT = (
    OUT_DIR
    / "heldout_groundwater_sample_qa.csv"
)

ANALYSIS_PANEL_OUT = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "heldout_groundwater_first_difference_panel.csv"
)

YEARS = (2022, 2023)
EXPECTED_WELLS = 13

OUTCOME = "gw_aug_nearest_aug23_m"
ANTECEDENT = "gw_pre_last_janfeb_m"
EXPOSURE = "ff10_anomaly_2010_2021"

MODEL_SPECS = {
    "PRIMARY": [
        "delta_ff10",
        "delta_pre_gw",
    ],
    "W1_PRECIP": [
        "delta_ff10",
        "delta_pre_gw",
        "delta_P_A8",
    ],
    "W2_TEMP": [
        "delta_ff10",
        "delta_pre_gw",
        "delta_T_A8",
    ],
    "W3_PRECIP_TEMP": [
        "delta_ff10",
        "delta_pre_gw",
        "delta_P_A8",
        "delta_T_A8",
    ],
}


def require_unique(
    d: pd.DataFrame,
    key: list[str],
    label: str,
) -> None:
    if d.duplicated(key).any():
        bad = d.loc[
            d.duplicated(key, keep=False),
            key,
        ]

        raise AssertionError(
            f"{label}: duplicate keys:\n"
            + bad.to_string(index=False)
        )


def fit_model(
    d: pd.DataFrame,
    model_name: str,
    predictors: list[str],
) -> tuple[pd.DataFrame, object, object]:
    y = d["delta_aug_gw"].astype(float)

    X = sm.add_constant(
        d[predictors].astype(float),
        has_constant="add",
    )

    # Conventional OLS fit retained for influence diagnostics.
    base = sm.OLS(
        y,
        X,
    ).fit()

    # Frozen primary inference rule.
    robust = base.get_robustcov_results(
        cov_type="HC3"
    )

    names = list(
        base.model.exog_names
    )

    params = pd.Series(
        np.asarray(robust.params),
        index=names,
    )

    bse = pd.Series(
        np.asarray(robust.bse),
        index=names,
    )

    pvalues = pd.Series(
        np.asarray(robust.pvalues),
        index=names,
    )

    ci = np.asarray(
        robust.conf_int(
            alpha=0.05
        )
    )

    rows = []

    for i, term in enumerate(names):
        rows.append(
            {
                "model": model_name,
                "term": term,
                "estimate": float(
                    params[term]
                ),
                "hc3_se": float(
                    bse[term]
                ),
                "p_value": float(
                    pvalues[term]
                ),
                "ci95_low": float(
                    ci[i, 0]
                ),
                "ci95_high": float(
                    ci[i, 1]
                ),
                "n": int(
                    base.nobs
                ),
                "df_resid": float(
                    base.df_resid
                ),
                "r_squared": float(
                    base.rsquared
                ),
                "adj_r_squared": float(
                    base.rsquared_adj
                ),
                "condition_number": float(
                    base.condition_number
                ),
            }
        )

    return (
        pd.DataFrame(rows),
        base,
        robust,
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
    # 1. Read the already frozen sample IDs.
    # ---------------------------------------------------------

    ids = pd.read_csv(
        FROZEN_IDS_IN
    )

    if list(ids.columns) != ["station"]:
        raise AssertionError(
            "Frozen sample-ID file must contain only station."
        )

    if len(ids) != EXPECTED_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_WELLS} frozen wells; "
            f"found {len(ids)}."
        )

    if ids["station"].duplicated().any():
        raise AssertionError(
            "Duplicate station in frozen sample."
        )

    frozen_stations = set(
        ids["station"]
    )

    # ---------------------------------------------------------
    # 2. Read exactly the frozen groundwater fields.
    # ---------------------------------------------------------

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

    gw = gw.loc[
        gw["station"].isin(
            frozen_stations
        )
        & gw["year"].isin(
            YEARS
        )
    ].copy()

    if not (
        gw["aquifer_group"] == "ISS"
    ).all():
        raise AssertionError(
            "Frozen groundwater sample contains non-ISS wells."
        )

    require_unique(
        gw,
        [
            "station",
            "year",
        ],
        "groundwater",
    )

    if len(gw) != (
        EXPECTED_WELLS
        * len(YEARS)
    ):
        raise AssertionError(
            "Frozen groundwater panel is not complete 13 x 2."
        )

    if gw[
        [
            OUTCOME,
            ANTECEDENT,
        ]
    ].isna().any().any():
        raise AssertionError(
            "Frozen repeated groundwater sample unexpectedly "
            "contains missing outcome/antecedent."
        )

    # ---------------------------------------------------------
    # 3. Read frozen exposure.
    # ---------------------------------------------------------

    ff = pd.read_csv(
        FF_IN,
        usecols=[
            "station",
            "year",
            EXPOSURE,
            "n_cells_10km",
        ],
    )

    ff = ff.loc[
        ff["station"].isin(
            frozen_stations
        )
        & ff["year"].isin(
            YEARS
        )
    ].copy()

    require_unique(
        ff,
        [
            "station",
            "year",
        ],
        "FF10 exposure",
    )

    if len(ff) != (
        EXPECTED_WELLS
        * len(YEARS)
    ):
        raise AssertionError(
            "Frozen FF10 panel is not complete 13 x 2."
        )

    if ff[EXPOSURE].isna().any():
        raise AssertionError(
            "Missing FF10 exposure in frozen sample."
        )

    if (
        ff["n_cells_10km"] <= 0
    ).any():
        raise AssertionError(
            "Frozen sample unexpectedly contains zero-cell "
            "FF10 exposure."
        )

    # ---------------------------------------------------------
    # 4. Read prespecified weather robustness controls.
    # ---------------------------------------------------------

    weather = pd.read_csv(
        WEATHER_IN,
        usecols=[
            "station",
            "year",
            "P_A8",
            "T_A8",
        ],
    )

    weather = weather.loc[
        weather["station"].isin(
            frozen_stations
        )
        & weather["year"].isin(
            YEARS
        )
    ].copy()

    require_unique(
        weather,
        [
            "station",
            "year",
        ],
        "weather",
    )

    if len(weather) != (
        EXPECTED_WELLS
        * len(YEARS)
    ):
        raise AssertionError(
            "Frozen weather panel is not complete 13 x 2."
        )

    if weather[
        [
            "P_A8",
            "T_A8",
        ]
    ].isna().any().any():
        raise AssertionError(
            "Weather controls are missing in frozen sample."
        )

    # ---------------------------------------------------------
    # 5. Build one 26-row level panel.
    # ---------------------------------------------------------

    level = (
        gw.merge(
            ff,
            on=[
                "station",
                "year",
            ],
            how="inner",
            validate="one_to_one",
        )
        .merge(
            weather,
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
        .reset_index(
            drop=True
        )
    )

    if len(level) != 26:
        raise AssertionError(
            f"Expected 26 level rows; found {len(level)}."
        )

    # ---------------------------------------------------------
    # 6. First differences: 2023 minus 2022.
    # ---------------------------------------------------------

    def delta(
        column: str,
    ) -> pd.Series:
        wide = level.pivot(
            index="station",
            columns="year",
            values=column,
        )

        if list(
            sorted(wide.columns)
        ) != [2022, 2023]:
            raise AssertionError(
                f"{column}: unexpected year columns."
            )

        return (
            wide[2023]
            - wide[2022]
        )

    analysis = pd.DataFrame(
        {
            "station":
                sorted(
                    frozen_stations
                )
        }
    ).set_index(
        "station"
    )

    analysis[
        "delta_aug_gw"
    ] = delta(
        OUTCOME
    )

    analysis[
        "delta_pre_gw"
    ] = delta(
        ANTECEDENT
    )

    analysis[
        "delta_ff10"
    ] = delta(
        EXPOSURE
    )

    analysis[
        "delta_P_A8"
    ] = delta(
        "P_A8"
    )

    analysis[
        "delta_T_A8"
    ] = delta(
        "T_A8"
    )

    analysis = (
        analysis.reset_index()
        .sort_values(
            "station"
        )
        .reset_index(
            drop=True
        )
    )

    if len(analysis) != EXPECTED_WELLS:
        raise AssertionError(
            "First-difference panel is not 13 wells."
        )

    if analysis[
        [
            "delta_aug_gw",
            "delta_pre_gw",
            "delta_ff10",
            "delta_P_A8",
            "delta_T_A8",
        ]
    ].isna().any().any():
        raise AssertionError(
            "First-difference panel contains missing values."
        )

    if set(
        analysis["station"]
    ) != frozen_stations:
        raise AssertionError(
            "First-difference sample differs from frozen IDs."
        )

    analysis.to_csv(
        ANALYSIS_PANEL_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 7. Run all four frozen models.
    # ---------------------------------------------------------

    all_results = []
    fitted = {}

    for model_name, predictors in MODEL_SPECS.items():
        result, base, robust = fit_model(
            analysis,
            model_name,
            predictors,
        )

        all_results.append(
            result
        )

        fitted[
            model_name
        ] = {
            "base":
                base,
            "robust":
                robust,
        }

    results = pd.concat(
        all_results,
        ignore_index=True,
    )

    results.to_csv(
        MODEL_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 8. Compact primary result.
    # ---------------------------------------------------------

    primary_beta = results.loc[
        (
            results["model"] == "PRIMARY"
        )
        & (
            results["term"] == "delta_ff10"
        )
    ].copy()

    if len(primary_beta) != 1:
        raise AssertionError(
            "Could not isolate one primary FF10 coefficient."
        )

    primary_beta[
        "effect_per_0p01_ff10"
    ] = (
        primary_beta[
            "estimate"
        ]
        * 0.01
    )

    primary_beta[
        "ci95_low_per_0p01_ff10"
    ] = (
        primary_beta[
            "ci95_low"
        ]
        * 0.01
    )

    primary_beta[
        "ci95_high_per_0p01_ff10"
    ] = (
        primary_beta[
            "ci95_high"
        ]
        * 0.01
    )

    primary_beta.to_csv(
        PRIMARY_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 9. Frozen influence diagnostics for primary model.
    # ---------------------------------------------------------

    primary_base = fitted[
        "PRIMARY"
    ]["base"]

    influence = (
        primary_base
        .get_influence()
    )

    leverage = np.asarray(
        influence.hat_matrix_diag
    )

    cooks_d = np.asarray(
        influence.cooks_distance[0]
    )

    influence_df = pd.DataFrame(
        {
            "station":
                analysis[
                    "station"
                ].to_numpy(),
            "leverage":
                leverage,
            "cooks_distance":
                cooks_d,
        }
    )

    influence_df.to_csv(
        INFLUENCE_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 10. Leave-one-well-out PRIMARY coefficient.
    #
    # Same frozen primary equation every time.
    # No observation is selected for deletion.
    # ---------------------------------------------------------

    loo_rows = []

    primary_predictors = MODEL_SPECS[
        "PRIMARY"
    ]

    for station in analysis[
        "station"
    ]:
        q = analysis.loc[
            analysis[
                "station"
            ].ne(station)
        ].copy()

        loo_result, _, _ = fit_model(
            q,
            "PRIMARY_LOO",
            primary_predictors,
        )

        beta = loo_result.loc[
            loo_result[
                "term"
            ].eq(
                "delta_ff10"
            )
        ].iloc[0]

        loo_rows.append(
            {
                "omitted_station":
                    station,
                "n":
                    len(q),
                "delta_ff10_estimate":
                    float(
                        beta[
                            "estimate"
                        ]
                    ),
                "hc3_se":
                    float(
                        beta[
                            "hc3_se"
                        ]
                    ),
                "p_value":
                    float(
                        beta[
                            "p_value"
                        ]
                    ),
                "ci95_low":
                    float(
                        beta[
                            "ci95_low"
                        ]
                    ),
                "ci95_high":
                    float(
                        beta[
                            "ci95_high"
                        ]
                    ),
            }
        )

    loo = pd.DataFrame(
        loo_rows
    )

    loo.to_csv(
        LOO_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 11. Sample/influence QA.
    # ---------------------------------------------------------

    primary_estimate = float(
        primary_beta[
            "estimate"
        ].iloc[0]
    )

    sign = (
        "positive"
        if primary_estimate > 0
        else "negative"
        if primary_estimate < 0
        else "zero"
    )

    sample_qa = pd.DataFrame(
        [
            {
                "frozen_wells_n":
                    len(analysis),
                "level_rows_n":
                    len(level),
                "difference_rows_n":
                    len(analysis),
                "primary_predictors_n":
                    len(
                        MODEL_SPECS[
                            "PRIMARY"
                        ]
                    ),
                "primary_df_resid":
                    float(
                        primary_base.df_resid
                    ),
                "primary_delta_ff10_sign":
                    sign,
                "max_leverage":
                    float(
                        leverage.max()
                    ),
                "max_cooks_distance":
                    float(
                        cooks_d.max()
                    ),
                "loo_beta_min":
                    float(
                        loo[
                            "delta_ff10_estimate"
                        ].min()
                    ),
                "loo_beta_max":
                    float(
                        loo[
                            "delta_ff10_estimate"
                        ].max()
                    ),
                "loo_beta_all_same_sign_as_primary":
                    bool(
                        (
                            np.sign(
                                loo[
                                    "delta_ff10_estimate"
                                ]
                            )
                            ==
                            np.sign(
                                primary_estimate
                            )
                        ).all()
                    ),
            }
        ]
    )

    sample_qa.to_csv(
        SAMPLE_QA_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 12. First held-out reveal.
    # ---------------------------------------------------------

    print(
        "HELD-OUT GROUNDWATER CONFIRMATION COMPLETE"
    )
    print("")
    print(
        "Frozen sample:"
    )
    print(
        f"  wells: {len(analysis)}"
    )
    print(
        "  contrast: 2023 minus 2022"
    )
    print("")

    print(
        "PRIMARY MODEL — HC3"
    )

    cols = [
        "term",
        "estimate",
        "hc3_se",
        "p_value",
        "ci95_low",
        "ci95_high",
    ]

    print(
        results.loc[
            results[
                "model"
            ].eq(
                "PRIMARY"
            ),
            cols,
        ].to_string(
            index=False
        )
    )

    print("")

    pb = primary_beta.iloc[0]

    print(
        "Primary FF10 coefficient:"
    )
    print(
        f"  beta = {pb['estimate']:.10g}"
    )
    print(
        f"  HC3 SE = {pb['hc3_se']:.10g}"
    )
    print(
        f"  p = {pb['p_value']:.10g}"
    )
    print(
        "  95% CI = "
        f"[{pb['ci95_low']:.10g}, "
        f"{pb['ci95_high']:.10g}]"
    )
    print(
        "  effect per +0.01 FF10 = "
        f"{pb['effect_per_0p01_ff10']:.10g} m"
    )
    print("")

    print(
        "PRESPECIFIED WEATHER ROBUSTNESS — "
        "delta_ff10 coefficient"
    )

    robustness = results.loc[
        results[
            "term"
        ].eq(
            "delta_ff10"
        ),
        [
            "model",
            "estimate",
            "hc3_se",
            "p_value",
            "ci95_low",
            "ci95_high",
            "n",
            "df_resid",
        ],
    ]

    print(
        robustness.to_string(
            index=False
        )
    )

    print("")

    print(
        "PRESPECIFIED INFLUENCE DIAGNOSTICS"
    )
    print(
        f"  max leverage = "
        f"{leverage.max():.10g}"
    )
    print(
        f"  max Cook's distance = "
        f"{cooks_d.max():.10g}"
    )
    print(
        "  leave-one-out beta range = "
        f"[{loo['delta_ff10_estimate'].min():.10g}, "
        f"{loo['delta_ff10_estimate'].max():.10g}]"
    )
    print(
        "  all LOO betas same sign as primary = "
        f"{sample_qa['loo_beta_all_same_sign_as_primary'].iloc[0]}"
    )

    print("")
    print(
        "No radius/outcome/exposure/model selection was performed."
    )
    print(
        "No observation was deleted."
    )
    print("")
    print(
        f"Wrote: {MODEL_OUT}"
    )
    print(
        f"Wrote: {PRIMARY_OUT}"
    )
    print(
        f"Wrote: {INFLUENCE_OUT}"
    )
    print(
        f"Wrote: {LOO_OUT}"
    )
    print(
        f"Wrote: {SAMPLE_QA_OUT}"
    )
    print(
        f"Wrote: {ANALYSIS_PANEL_OUT}"
    )


if __name__ == "__main__":
    main()
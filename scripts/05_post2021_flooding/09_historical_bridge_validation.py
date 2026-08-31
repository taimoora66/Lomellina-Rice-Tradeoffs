from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
import statsmodels.api as sm


ROOT = Path(__file__).resolve().parents[2]

RICE_FILE = (
    ROOT
    / "data"
    / "raw"
    / "RiceFloodIT"
    / "ffavg_2021.csv"
)

PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
)

DIAG_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

DEV_YEARS = (2017, 2018, 2019)
VALIDATION_YEARS = (2020, 2021)
ALL_YEARS = DEV_YEARS + VALIDATION_YEARS

EXPECTED_RICE_GRID_CELLS = 4331
EXPECTED_COMPOSITES = 15
EXPECTED_NATIVE_PER_CELL = 4
EXPECTED_BALANCED_REFERENCE_CELLS = 3062


# ---------------------------------------------------------------------
# Prespecified candidate definitions
#
# These are deliberately limited to unresolved methodological choices.
# No groundwater information is used.
# ---------------------------------------------------------------------

QA_RULES = (
    "valid",
    "basic_clear",
    "strict",
)

AGGREGATION_ORDERS = (
    "index_then_aggregate",
    "aggregate_then_index",
)


def candidate_name(
    qa_rule: str,
    aggregation_order: str,
) -> str:
    return f"{qa_rule}__{aggregation_order}"


def safe_pearson(
    x: pd.Series,
    y: pd.Series,
) -> float:
    ok = x.notna() & y.notna()

    if ok.sum() < 3:
        return np.nan

    if x[ok].nunique() < 2 or y[ok].nunique() < 2:
        return np.nan

    return float(
        pearsonr(
            x[ok].to_numpy(),
            y[ok].to_numpy(),
        ).statistic
    )


def safe_spearman(
    x: pd.Series,
    y: pd.Series,
) -> float:
    ok = x.notna() & y.notna()

    if ok.sum() < 3:
        return np.nan

    if x[ok].nunique() < 2 or y[ok].nunique() < 2:
        return np.nan

    return float(
        spearmanr(
            x[ok].to_numpy(),
            y[ok].to_numpy(),
        ).statistic
    )


def qa_mask(
    df: pd.DataFrame,
    rule: str,
) -> pd.Series:
    """
    Prespecified diagnostic QA candidates.

    These masks are candidate bridge rules only.
    They are not yet frozen as the RiceFloodIT QA algorithm.
    """

    base = (
        df["valid_b01"].astype(bool)
        & df["valid_b07"].astype(bool)
        & df["state_valid"].astype(bool)
        & df["qc_valid"].astype(bool)
        & df["ndfi"].notna()
    )

    if rule == "valid":
        return base

    basic = (
        base
        & (df["cloud_state"] == 0)
        & (df["cloud_shadow"] == 0)
        & (df["snow_ice"] == 0)
    )

    if rule == "basic_clear":
        return basic

    strict = (
        basic
        & (df["internal_cloud"] == 0)
        & (df["adjacent_cloud"] == 0)
        & (df["cirrus"] == 0)
        & (df["modland"] == 0)
        & (df["band1_quality"] == 0)
        & (df["band2_quality"] == 0)
        & (df["band7_quality"] == 0)
    )

    if rule == "strict":
        return strict

    raise ValueError(
        f"Unknown QA rule: {rule}"
    )


def read_native_year(
    year: int,
) -> pd.DataFrame:
    path = (
        PROCESSED_DIR
        / f"mod09a1_ricefloodit_native_pixels_{year}.csv"
    )

    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)

    expected_rows = (
        EXPECTED_RICE_GRID_CELLS
        * EXPECTED_NATIVE_PER_CELL
        * EXPECTED_COMPOSITES
    )

    if len(df) != expected_rows:
        raise AssertionError(
            f"{year}: expected {expected_rows:,} native rows; "
            f"found {len(df):,}"
        )

    if df["rice_cell_id"].nunique() != EXPECTED_RICE_GRID_CELLS:
        raise AssertionError(
            f"{year}: unexpected RiceFloodIT grid-cell count."
        )

    if df["composite_start_doy"].nunique() != EXPECTED_COMPOSITES:
        raise AssertionError(
            f"{year}: unexpected composite count."
        )

    if df["year"].nunique() != 1:
        raise AssertionError(
            f"{year}: native table contains multiple years."
        )

    if int(df["year"].iloc[0]) != year:
        raise AssertionError(
            f"{year}: year field does not match filename."
        )

    return df


def read_reference() -> pd.DataFrame:
    ff = pd.read_csv(RICE_FILE)

    required = {
        "x",
        "y",
        "year",
        "ff",
    }

    missing = required - set(ff.columns)

    if missing:
        raise AssertionError(
            f"RiceFloodIT missing columns: {sorted(missing)}"
        )

    ff = ff[
        ff["year"].isin(ALL_YEARS)
    ].copy()

    if ff["ff"].isna().any():
        raise AssertionError(
            "Historical RiceFloodIT reference contains missing FF."
        )

    if ff.duplicated(
        ["year", "x", "y"]
    ).any():
        raise AssertionError(
            "Duplicate RiceFloodIT year/x/y rows found."
        )

    return ff


def build_reference_sets(
    ff: pd.DataFrame,
) -> tuple[dict[int, set[tuple[float, float]]], set]:
    yearly: dict[int, set[tuple[float, float]]] = {}

    for year in ALL_YEARS:
        g = ff.loc[
            ff["year"] == year,
            ["x", "y"],
        ]

        yearly[year] = set(
            map(
                tuple,
                g.to_numpy(),
            )
        )

    balanced = set.intersection(
        *yearly.values()
    )

    if len(balanced) != EXPECTED_BALANCED_REFERENCE_CELLS:
        raise AssertionError(
            "Balanced historical reference support changed: "
            f"expected {EXPECTED_BALANCED_REFERENCE_CELLS}, "
            f"found {len(balanced)}"
        )

    return yearly, balanced


def aggregate_index_then_aggregate(
    df: pd.DataFrame,
    mask: pd.Series,
) -> pd.DataFrame:
    """
    Native 500-m NDFI is calculated upstream.

    Here:
      1. apply candidate QA at 500 m;
      2. mean NDFI across available native pixels within each 2x2 block;
      3. mean the resulting 1-km composite NDFI across the season.
    """

    x = df.loc[
        mask,
        [
            "rice_cell_id",
            "rice_x",
            "rice_y",
            "composite_start_doy",
            "ndfi",
        ],
    ].copy()

    composite = (
        x.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
                "composite_start_doy",
            ],
            as_index=False,
        )
        .agg(
            composite_signal=("ndfi", "mean"),
            native_valid=("ndfi", "count"),
        )
    )

    annual = (
        composite.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
            ],
            as_index=False,
        )
        .agg(
            seasonal_signal=(
                "composite_signal",
                "mean",
            ),
            composites_valid=(
                "composite_signal",
                "count",
            ),
            mean_native_per_composite=(
                "native_valid",
                "mean",
            ),
        )
    )

    return annual


def aggregate_then_index(
    df: pd.DataFrame,
    mask: pd.Series,
) -> pd.DataFrame:
    """
    Alternative unresolved processing order:

      1. apply candidate QA at 500 m;
      2. average red and SWIR2 reflectance across available native cells;
      3. calculate NDFI from the 1-km mean reflectances;
      4. average composite NDFI across the season.
    """

    x = df.loc[
        mask,
        [
            "rice_cell_id",
            "rice_x",
            "rice_y",
            "composite_start_doy",
            "red",
            "swir2",
        ],
    ].copy()

    composite = (
        x.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
                "composite_start_doy",
            ],
            as_index=False,
        )
        .agg(
            red_mean=("red", "mean"),
            swir2_mean=("swir2", "mean"),
            native_valid=("red", "count"),
        )
    )

    denom = (
        composite["red_mean"]
        + composite["swir2_mean"]
    )

    composite["composite_signal"] = np.where(
        denom != 0,
        (
            composite["red_mean"]
            - composite["swir2_mean"]
        )
        / denom,
        np.nan,
    )

    annual = (
        composite.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
            ],
            as_index=False,
        )
        .agg(
            seasonal_signal=(
                "composite_signal",
                "mean",
            ),
            composites_valid=(
                "composite_signal",
                "count",
            ),
            mean_native_per_composite=(
                "native_valid",
                "mean",
            ),
        )
    )

    return annual


def build_features_for_candidate(
    df: pd.DataFrame,
    qa_rule: str,
    aggregation_order: str,
) -> pd.DataFrame:
    mask = qa_mask(
        df,
        qa_rule,
    )

    if aggregation_order == "index_then_aggregate":
        result = aggregate_index_then_aggregate(
            df,
            mask,
        )

    elif aggregation_order == "aggregate_then_index":
        result = aggregate_then_index(
            df,
            mask,
        )

    else:
        raise ValueError(
            f"Unknown aggregation order: {aggregation_order}"
        )

    result["qa_rule"] = qa_rule
    result["aggregation_order"] = aggregation_order
    result["candidate"] = candidate_name(
        qa_rule,
        aggregation_order,
    )

    result["native_rows_retained"] = int(
        mask.sum()
    )

    result["native_rows_total"] = len(df)

    return result


def fit_linear_bridge(
    dev: pd.DataFrame,
) -> tuple[float, float]:
    fit = dev[
        ["seasonal_signal", "ff"]
    ].dropna()

    if len(fit) < 100:
        raise AssertionError(
            "Insufficient development observations."
        )

    X = sm.add_constant(
        fit["seasonal_signal"],
        has_constant="add",
    )

    model = sm.OLS(
        fit["ff"],
        X,
    ).fit()

    intercept = float(
        model.params["const"]
    )

    slope = float(
        model.params["seasonal_signal"]
    )

    return intercept, slope


def prediction_metrics(
    df: pd.DataFrame,
    subset_name: str,
    candidate: str,
    year_label: str,
) -> dict:
    x = df[
        [
            "ff",
            "prediction",
            "seasonal_signal",
            "composites_valid",
        ]
    ].dropna(
        subset=[
            "ff",
            "prediction",
        ]
    )

    if len(x) == 0:
        return {
            "candidate": candidate,
            "subset": subset_name,
            "year": year_label,
            "n": 0,
        }

    error = (
        x["prediction"]
        - x["ff"]
    )

    return {
        "candidate": candidate,
        "subset": subset_name,
        "year": year_label,
        "n": int(len(x)),
        "pearson_r": safe_pearson(
            x["prediction"],
            x["ff"],
        ),
        "spearman_rho": safe_spearman(
            x["prediction"],
            x["ff"],
        ),
        "rmse": float(
            np.sqrt(
                np.mean(
                    error**2
                )
            )
        ),
        "mae": float(
            np.mean(
                np.abs(error)
            )
        ),
        "bias": float(
            np.mean(error)
        ),
        "observed_mean_ff": float(
            x["ff"].mean()
        ),
        "predicted_mean_ff": float(
            x["prediction"].mean()
        ),
        "observed_sd_ff": float(
            x["ff"].std()
        ),
        "predicted_sd_ff": float(
            x["prediction"].std()
        ),
        "mean_composites_valid": float(
            x["composites_valid"].mean()
        ),
        "min_composites_valid": int(
            x["composites_valid"].min()
        ),
        "prediction_below_zero_n": int(
            (x["prediction"] < 0).sum()
        ),
        "prediction_above_one_n": int(
            (x["prediction"] > 1).sum()
        ),
    }


def main() -> None:
    DIAG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ff = read_reference()

    _, balanced_cells = build_reference_sets(
        ff
    )

    balanced_lookup = pd.DataFrame(
        list(balanced_cells),
        columns=[
            "x",
            "y",
        ],
    )

    feature_frames = []
    coverage_rows = []

    print(
        "Building prespecified historical bridge candidates..."
    )
    print("")

    for year in ALL_YEARS:
        native = read_native_year(
            year
        )

        reference_year = ff.loc[
            ff["year"] == year,
            [
                "x",
                "y",
                "ff",
            ],
        ].copy()

        for qa_rule in QA_RULES:
            for aggregation_order in AGGREGATION_ORDERS:
                features = build_features_for_candidate(
                    native,
                    qa_rule,
                    aggregation_order,
                )

                features["year"] = year

                merged = features.merge(
                    reference_year,
                    left_on=[
                        "rice_x",
                        "rice_y",
                    ],
                    right_on=[
                        "x",
                        "y",
                    ],
                    how="inner",
                    validate="one_to_one",
                )

                expected_n = len(
                    reference_year
                )

                if len(merged) != expected_n:
                    raise AssertionError(
                        f"{year} "
                        f"{qa_rule} "
                        f"{aggregation_order}: "
                        "reference support merge mismatch. "
                        f"Expected {expected_n}, "
                        f"found {len(merged)}."
                    )

                merged["split"] = np.where(
                    merged["year"].isin(
                        DEV_YEARS
                    ),
                    "development",
                    "validation",
                )

                merged["balanced_panel"] = (
                    merged[
                        [
                            "rice_x",
                            "rice_y",
                        ]
                    ]
                    .merge(
                        balanced_lookup.assign(
                            balanced_panel=True
                        ),
                        left_on=[
                            "rice_x",
                            "rice_y",
                        ],
                        right_on=[
                            "x",
                            "y",
                        ],
                        how="left",
                    )["balanced_panel"]
                    .fillna(False)
                    .astype(bool)
                    .to_numpy()
                )

                feature_frames.append(
                    merged
                )

                coverage_rows.append(
                    {
                        "year": year,
                        "candidate": candidate_name(
                            qa_rule,
                            aggregation_order,
                        ),
                        "qa_rule": qa_rule,
                        "aggregation_order":
                            aggregation_order,
                        "reference_cells":
                            expected_n,
                        "feature_cells":
                            len(features),
                        "matched_reference_cells":
                            len(merged),
                        "seasonal_signal_nonmissing":
                            int(
                                merged[
                                    "seasonal_signal"
                                ]
                                .notna()
                                .sum()
                            ),
                        "mean_composites_valid":
                            float(
                                merged[
                                    "composites_valid"
                                ].mean()
                            ),
                        "min_composites_valid":
                            int(
                                merged[
                                    "composites_valid"
                                ].min()
                            ),
                        "native_rows_retained":
                            int(
                                features[
                                    "native_rows_retained"
                                ].iloc[0]
                            ),
                        "native_rows_total":
                            int(
                                features[
                                    "native_rows_total"
                                ].iloc[0]
                            ),
                    }
                )

    panel = pd.concat(
        feature_frames,
        ignore_index=True,
    )

    coverage = pd.DataFrame(
        coverage_rows
    )

    predictions = []
    metrics_rows = []
    coefficient_rows = []

    candidates = sorted(
        panel["candidate"].unique()
    )

    print(
        f"Candidates fixed in source: {len(candidates)}"
    )

    for candidate in candidates:
        c = panel.loc[
            panel["candidate"] == candidate
        ].copy()

        dev = c.loc[
            c["year"].isin(
                DEV_YEARS
            )
        ].copy()

        intercept, slope = fit_linear_bridge(
            dev
        )

        c["prediction"] = (
            intercept
            + slope
            * c["seasonal_signal"]
        )

        coefficient_rows.append(
            {
                "candidate": candidate,
                "development_years":
                    "2017-2019",
                "validation_years":
                    "2020-2021",
                "intercept": intercept,
                "slope": slope,
            }
        )

        predictions.append(
            c
        )

        # -------------------------------------------------------------
        # Primary year-specific reference support
        # -------------------------------------------------------------

        for year in ALL_YEARS:
            yr = c.loc[
                c["year"] == year
            ]

            split_name = (
                "development"
                if year in DEV_YEARS
                else "validation"
            )

            metrics_rows.append(
                prediction_metrics(
                    yr,
                    subset_name=split_name,
                    candidate=candidate,
                    year_label=str(year),
                )
            )

        # pooled development
        metrics_rows.append(
            prediction_metrics(
                c.loc[
                    c["year"].isin(
                        DEV_YEARS
                    )
                ],
                subset_name="development",
                candidate=candidate,
                year_label="pooled_2017_2019",
            )
        )

        # pooled held-out validation
        metrics_rows.append(
            prediction_metrics(
                c.loc[
                    c["year"].isin(
                        VALIDATION_YEARS
                    )
                ],
                subset_name="validation",
                candidate=candidate,
                year_label="pooled_2020_2021",
            )
        )

        # -------------------------------------------------------------
        # Secondary balanced-panel robustness
        # -------------------------------------------------------------

        balanced = c.loc[
            c["balanced_panel"]
        ]

        metrics_rows.append(
            prediction_metrics(
                balanced.loc[
                    balanced[
                        "year"
                    ].isin(
                        DEV_YEARS
                    )
                ],
                subset_name=(
                    "development_balanced"
                ),
                candidate=candidate,
                year_label=(
                    "pooled_2017_2019"
                ),
            )
        )

        metrics_rows.append(
            prediction_metrics(
                balanced.loc[
                    balanced[
                        "year"
                    ].isin(
                        VALIDATION_YEARS
                    )
                ],
                subset_name=(
                    "validation_balanced"
                ),
                candidate=candidate,
                year_label=(
                    "pooled_2020_2021"
                ),
            )
        )

    prediction_df = pd.concat(
        predictions,
        ignore_index=True,
    )

    metrics = pd.DataFrame(
        metrics_rows
    )

    coefficients = pd.DataFrame(
        coefficient_rows
    )

    # -------------------------------------------------------------
    # Interannual mean preservation
    #
    # This is deliberately reported separately because spatial
    # correlation alone cannot establish that annual anomalies are
    # preserved.
    # -------------------------------------------------------------

    year_means = (
        prediction_df.groupby(
            [
                "candidate",
                "year",
                "split",
            ],
            as_index=False,
        )
        .agg(
            observed_mean_ff=(
                "ff",
                "mean",
            ),
            predicted_mean_ff=(
                "prediction",
                "mean",
            ),
            n=(
                "ff",
                "size",
            ),
        )
    )

    interannual_rows = []

    for candidate, g in year_means.groupby(
        "candidate"
    ):
        g = g.sort_values(
            "year"
        )

        interannual_rows.append(
            {
                "candidate": candidate,
                "years": "2017-2021",
                "pearson_annual_means":
                    safe_pearson(
                        g[
                            "predicted_mean_ff"
                        ],
                        g[
                            "observed_mean_ff"
                        ],
                    ),
                "spearman_annual_means":
                    safe_spearman(
                        g[
                            "predicted_mean_ff"
                        ],
                        g[
                            "observed_mean_ff"
                        ],
                    ),
                "annual_mean_rmse":
                    float(
                        np.sqrt(
                            np.mean(
                                (
                                    g[
                                        "predicted_mean_ff"
                                    ]
                                    - g[
                                        "observed_mean_ff"
                                    ]
                                )
                                ** 2
                            )
                        )
                    ),
            }
        )

    interannual = pd.DataFrame(
        interannual_rows
    )

    # -------------------------------------------------------------
    # Write outputs
    # -------------------------------------------------------------

    coverage_path = (
        DIAG_DIR
        / "bridge_candidate_coverage_2017_2021.csv"
    )

    coefficient_path = (
        DIAG_DIR
        / "bridge_candidate_coefficients_2017_2019.csv"
    )

    metrics_path = (
        DIAG_DIR
        / "bridge_candidate_metrics_2017_2021.csv"
    )

    year_means_path = (
        DIAG_DIR
        / "bridge_candidate_year_means_2017_2021.csv"
    )

    interannual_path = (
        DIAG_DIR
        / "bridge_candidate_interannual_2017_2021.csv"
    )

    prediction_path = (
        PROCESSED_DIR
        / "historical_bridge_predictions_2017_2021.csv"
    )

    coverage.to_csv(
        coverage_path,
        index=False,
    )

    coefficients.to_csv(
        coefficient_path,
        index=False,
    )

    metrics.to_csv(
        metrics_path,
        index=False,
    )

    year_means.to_csv(
        year_means_path,
        index=False,
    )

    interannual.to_csv(
        interannual_path,
        index=False,
    )

    prediction_df.to_csv(
        prediction_path,
        index=False,
    )

    print("")
    print(
        "Historical bridge validation analysis complete"
    )
    print("")
    print(
        "Development years: 2017-2019"
    )
    print(
        "Held-out validation years: 2020-2021"
    )
    print(
        f"Candidates evaluated: {len(candidates)}"
    )
    print(
        f"Balanced reference cells: "
        f"{len(balanced_cells):,}"
    )
    print("")
    print("Candidate coefficients:")
    print(
        coefficients.to_string(
            index=False
        )
    )

    print("")
    print(
        "Held-out pooled validation metrics:"
    )

    heldout = metrics.loc[
        (
            metrics["subset"]
            == "validation"
        )
        & (
            metrics["year"]
            == "pooled_2020_2021"
        )
    ].copy()

    print(
        heldout[
            [
                "candidate",
                "n",
                "pearson_r",
                "spearman_rho",
                "rmse",
                "mae",
                "bias",
                "observed_mean_ff",
                "predicted_mean_ff",
                "mean_composites_valid",
                "min_composites_valid",
            ]
        ].to_string(
            index=False
        )
    )

    print("")
    print(
        "Interannual mean diagnostics:"
    )
    print(
        interannual.to_string(
            index=False
        )
    )

    print("")
    print(f"Wrote: {coverage_path}")
    print(f"Wrote: {coefficient_path}")
    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {year_means_path}")
    print(f"Wrote: {interannual_path}")
    print(f"Wrote: {prediction_path}")
    print("")
    print(
        "No candidate has been automatically selected or frozen."
    )
    print(
        "No post-2021 groundwater data were used."
    )


if __name__ == "__main__":
    main()
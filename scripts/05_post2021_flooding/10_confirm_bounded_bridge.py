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

DEVELOPMENT_YEARS = (2017, 2018, 2019, 2020, 2021)
CONFIRMATION_YEARS = (2014, 2015, 2016)

EXPECTED_RICE_GRID_CELLS = 4331
EXPECTED_COMPOSITES = 15
EXPECTED_NATIVE_PER_CELL = 4

BRIDGE_NAME = "valid__index_then_aggregate__fractional_logit"


def safe_pearson(
    x: pd.Series,
    y: pd.Series,
) -> float:
    ok = x.notna() & y.notna()

    if ok.sum() < 3:
        return np.nan

    if x.loc[ok].nunique() < 2:
        return np.nan

    if y.loc[ok].nunique() < 2:
        return np.nan

    return float(
        pearsonr(
            x.loc[ok].to_numpy(),
            y.loc[ok].to_numpy(),
        ).statistic
    )


def safe_spearman(
    x: pd.Series,
    y: pd.Series,
) -> float:
    ok = x.notna() & y.notna()

    if ok.sum() < 3:
        return np.nan

    if x.loc[ok].nunique() < 2:
        return np.nan

    if y.loc[ok].nunique() < 2:
        return np.nan

    return float(
        spearmanr(
            x.loc[ok].to_numpy(),
            y.loc[ok].to_numpy(),
        ).statistic
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
            f"{year}: expected {expected_rows:,} rows; "
            f"found {len(df):,}"
        )

    if df["rice_cell_id"].nunique() != EXPECTED_RICE_GRID_CELLS:
        raise AssertionError(
            f"{year}: unexpected RiceFloodIT cell count."
        )

    if df["composite_start_doy"].nunique() != EXPECTED_COMPOSITES:
        raise AssertionError(
            f"{year}: unexpected MODIS composite count."
        )

    if df["year"].nunique() != 1:
        raise AssertionError(
            f"{year}: native table contains multiple years."
        )

    if int(df["year"].iloc[0]) != year:
        raise AssertionError(
            f"{year}: year field does not match requested year."
        )

    return df


def valid_mask(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Frozen processing rule carried forward from Experiment 1.

    This is the 'valid' candidate, not a claim that the exact
    original RiceFloodIT QA algorithm has been recovered.
    """

    return (
        df["valid_b01"].astype(bool)
        & df["valid_b07"].astype(bool)
        & df["state_valid"].astype(bool)
        & df["qc_valid"].astype(bool)
        & df["ndfi"].notna()
    )


def build_seasonal_signal(
    df: pd.DataFrame,
    year: int,
) -> pd.DataFrame:
    """
    Frozen index-then-aggregate processing:

    1. calculate NDFI at native 500-m resolution upstream;
    2. retain observations satisfying the frozen validity rule;
    3. mean valid native NDFI within the exact 2x2 RiceFloodIT block;
    4. mean composite-level NDFI across the fixed 15-composite season.
    """

    mask = valid_mask(df)

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
            composite_ndfi=("ndfi", "mean"),
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
            seasonal_signal=("composite_ndfi", "mean"),
            composites_valid=("composite_ndfi", "count"),
            mean_native_per_composite=("native_valid", "mean"),
        )
    )

    annual["year"] = year
    annual["native_rows_retained"] = int(mask.sum())
    annual["native_rows_total"] = int(len(df))

    if len(annual) != EXPECTED_RICE_GRID_CELLS:
        raise AssertionError(
            f"{year}: seasonal feature table lost grid cells."
        )

    if annual["seasonal_signal"].isna().any():
        raise AssertionError(
            f"{year}: missing seasonal signal after frozen processing."
        )

    return annual


def read_reference_years(
    years: tuple[int, ...],
) -> pd.DataFrame:
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

    ff = ff.loc[
        ff["year"].isin(years),
        [
            "x",
            "y",
            "year",
            "ff",
        ],
    ].copy()

    if ff["ff"].isna().any():
        raise AssertionError(
            "RiceFloodIT reference contains missing FF."
        )

    if ff.duplicated(
        [
            "year",
            "x",
            "y",
        ]
    ).any():
        raise AssertionError(
            "Duplicate RiceFloodIT year/x/y records found."
        )

    if (
        (ff["ff"] < 0)
        | (ff["ff"] > 1)
    ).any():
        raise AssertionError(
            "Published RiceFloodIT FF is outside [0,1]."
        )

    return ff


def merge_features_reference(
    features: pd.DataFrame,
    reference: pd.DataFrame,
    year: int,
) -> pd.DataFrame:
    ref = reference.loc[
        reference["year"] == year,
        [
            "x",
            "y",
            "ff",
        ],
    ].copy()

    merged = features.merge(
        ref,
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

    if len(merged) != len(ref):
        raise AssertionError(
            f"{year}: failed to recover complete "
            "published RiceFloodIT support. "
            f"Reference={len(ref)}, merged={len(merged)}."
        )

    return merged


def fit_fractional_logit(
    development: pd.DataFrame,
):
    fit = development[
        [
            "seasonal_signal",
            "ff",
        ]
    ].dropna()

    if len(fit) < 1000:
        raise AssertionError(
            "Unexpectedly small development sample."
        )

    X = sm.add_constant(
        fit["seasonal_signal"],
        has_constant="add",
    )

    model = sm.GLM(
        fit["ff"],
        X,
        family=sm.families.Binomial(),
    ).fit()

    return model


def predict_fractional_logit(
    model,
    df: pd.DataFrame,
) -> pd.Series:
    X = sm.add_constant(
        df["seasonal_signal"],
        has_constant="add",
    )

    prediction = pd.Series(
        model.predict(X),
        index=df.index,
        dtype=float,
    )

    if (
        (prediction < 0)
        | (prediction > 1)
    ).any():
        raise AssertionError(
            "Fractional-logit prediction outside [0,1]."
        )

    return prediction


def metrics(
    df: pd.DataFrame,
    subset: str,
    year_label: str,
) -> dict:
    x = df[
        [
            "ff",
            "prediction",
            "composites_valid",
        ]
    ].dropna()

    error = (
        x["prediction"]
        - x["ff"]
    )

    return {
        "bridge": BRIDGE_NAME,
        "subset": subset,
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
            error.mean()
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

    # -------------------------------------------------------------
    # STEP 1
    # Build MODIS predictors without reading confirmation FF.
    # -------------------------------------------------------------

    print(
        "Building frozen MODIS seasonal signal for "
        "2014-2021..."
    )

    features_by_year: dict[int, pd.DataFrame] = {}

    for year in (
        CONFIRMATION_YEARS
        + DEVELOPMENT_YEARS
    ):
        native = read_native_year(year)

        features_by_year[year] = (
            build_seasonal_signal(
                native,
                year,
            )
        )

    # -------------------------------------------------------------
    # STEP 2
    # Read development FF only and fit the bounded bridge.
    # Confirmation-period FF has not yet been read by this script.
    # -------------------------------------------------------------

    print(
        "Reading development RiceFloodIT FF: 2017-2021..."
    )

    development_reference = read_reference_years(
        DEVELOPMENT_YEARS
    )

    development_frames = []

    for year in DEVELOPMENT_YEARS:
        merged = merge_features_reference(
            features_by_year[year],
            development_reference,
            year,
        )

        merged["split"] = "development"

        development_frames.append(
            merged
        )

    development = pd.concat(
        development_frames,
        ignore_index=True,
    )

    print(
        f"Fitting frozen fractional-logit bridge "
        f"using {len(development):,} development observations..."
    )

    model = fit_fractional_logit(
        development
    )

    intercept = float(
        model.params["const"]
    )

    slope = float(
        model.params["seasonal_signal"]
    )

    coefficient_table = pd.DataFrame(
        [
            {
                "bridge": BRIDGE_NAME,
                "development_years": "2017-2021",
                "confirmation_years": "2014-2016",
                "model_family": "Binomial",
                "link": "logit",
                "intercept": intercept,
                "slope": slope,
                "development_n": len(development),
            }
        ]
    )

    development["prediction"] = (
        predict_fractional_logit(
            model,
            development,
        )
    )

    print("")
    print("MODEL FIT COMPLETE.")
    print(
        "Confirmation-period RiceFloodIT FF has not "
        "yet been read by this script."
    )
    print("")
    print(
        f"Intercept: {intercept:.12f}"
    )
    print(
        f"Slope:     {slope:.12f}"
    )
    print("")

    # -------------------------------------------------------------
    # STEP 3
    # Only now reveal the untouched 2014-2016 RiceFloodIT values.
    # No model refitting occurs after this point.
    # -------------------------------------------------------------

    print(
        "Opening untouched historical confirmation "
        "RiceFloodIT FF: 2014-2016..."
    )

    confirmation_reference = read_reference_years(
        CONFIRMATION_YEARS
    )

    confirmation_frames = []

    for year in CONFIRMATION_YEARS:
        merged = merge_features_reference(
            features_by_year[year],
            confirmation_reference,
            year,
        )

        merged["split"] = "confirmation"

        merged["prediction"] = (
            predict_fractional_logit(
                model,
                merged,
            )
        )

        confirmation_frames.append(
            merged
        )

    confirmation = pd.concat(
        confirmation_frames,
        ignore_index=True,
    )

    # -------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------

    metric_rows = []

    for year in DEVELOPMENT_YEARS:
        metric_rows.append(
            metrics(
                development.loc[
                    development["year"] == year
                ],
                subset="development",
                year_label=str(year),
            )
        )

    metric_rows.append(
        metrics(
            development,
            subset="development",
            year_label="pooled_2017_2021",
        )
    )

    for year in CONFIRMATION_YEARS:
        metric_rows.append(
            metrics(
                confirmation.loc[
                    confirmation["year"] == year
                ],
                subset="confirmation",
                year_label=str(year),
            )
        )

    metric_rows.append(
        metrics(
            confirmation,
            subset="confirmation",
            year_label="pooled_2014_2016",
        )
    )

    metrics_df = pd.DataFrame(
        metric_rows
    )

    all_predictions = pd.concat(
        [
            development,
            confirmation,
        ],
        ignore_index=True,
    )

    # -------------------------------------------------------------
    # Annual means
    # -------------------------------------------------------------

    year_means = (
        all_predictions.groupby(
            [
                "year",
                "split",
            ],
            as_index=False,
        )
        .agg(
            observed_mean_ff=("ff", "mean"),
            predicted_mean_ff=("prediction", "mean"),
            n=("ff", "size"),
        )
        .sort_values("year")
    )

    confirmation_means = year_means.loc[
        year_means["split"] == "confirmation"
    ].copy()

    annual_error = (
        confirmation_means["predicted_mean_ff"]
        - confirmation_means["observed_mean_ff"]
    )

    confirmation_interannual = pd.DataFrame(
        [
            {
                "bridge": BRIDGE_NAME,
                "years": "2014-2016",
                "n_years": len(confirmation_means),
                "pearson_annual_means": safe_pearson(
                    confirmation_means[
                        "predicted_mean_ff"
                    ],
                    confirmation_means[
                        "observed_mean_ff"
                    ],
                ),
                "spearman_annual_means": safe_spearman(
                    confirmation_means[
                        "predicted_mean_ff"
                    ],
                    confirmation_means[
                        "observed_mean_ff"
                    ],
                ),
                "annual_mean_rmse": float(
                    np.sqrt(
                        np.mean(
                            annual_error**2
                        )
                    )
                ),
                "annual_mean_max_abs_error": float(
                    np.max(
                        np.abs(
                            annual_error
                        )
                    )
                ),
            }
        ]
    )

    # -------------------------------------------------------------
    # Balanced-support robustness across confirmation years only.
    # -------------------------------------------------------------

    confirmation_sets = []

    for year in CONFIRMATION_YEARS:
        g = confirmation.loc[
            confirmation["year"] == year,
            [
                "rice_x",
                "rice_y",
            ],
        ]

        confirmation_sets.append(
            set(
                map(
                    tuple,
                    g.to_numpy(),
                )
            )
        )

    balanced_confirmation = set.intersection(
        *confirmation_sets
    )

    balanced_lookup = pd.DataFrame(
        list(balanced_confirmation),
        columns=[
            "rice_x",
            "rice_y",
        ],
    )

    balanced = confirmation.merge(
        balanced_lookup.assign(
            balanced_confirmation=True
        ),
        on=[
            "rice_x",
            "rice_y",
        ],
        how="inner",
        validate="many_to_one",
    )

    balanced_metric = pd.DataFrame(
        [
            metrics(
                balanced,
                subset="confirmation_balanced",
                year_label="pooled_2014_2016",
            )
        ]
    )

    metrics_df = pd.concat(
        [
            metrics_df,
            balanced_metric,
        ],
        ignore_index=True,
    )

    # -------------------------------------------------------------
    # Coverage audit
    # -------------------------------------------------------------

    coverage_rows = []

    for year in (
        CONFIRMATION_YEARS
        + DEVELOPMENT_YEARS
    ):
        features = features_by_year[year]

        coverage_rows.append(
            {
                "year": year,
                "grid_cells": len(features),
                "seasonal_signal_nonmissing": int(
                    features[
                        "seasonal_signal"
                    ].notna().sum()
                ),
                "mean_composites_valid": float(
                    features[
                        "composites_valid"
                    ].mean()
                ),
                "min_composites_valid": int(
                    features[
                        "composites_valid"
                    ].min()
                ),
                "native_rows_retained": int(
                    features[
                        "native_rows_retained"
                    ].iloc[0]
                ),
                "native_rows_total": int(
                    features[
                        "native_rows_total"
                    ].iloc[0]
                ),
            }
        )

    coverage = pd.DataFrame(
        coverage_rows
    ).sort_values(
        "year"
    )

    # -------------------------------------------------------------
    # Write compact diagnostics.
    # Large prediction table remains processed/regenerable.
    # -------------------------------------------------------------

    coefficient_path = (
        DIAG_DIR
        / "bounded_bridge_coefficients_2017_2021.csv"
    )

    metrics_path = (
        DIAG_DIR
        / "bounded_bridge_confirmation_metrics_2014_2021.csv"
    )

    year_means_path = (
        DIAG_DIR
        / "bounded_bridge_year_means_2014_2021.csv"
    )

    interannual_path = (
        DIAG_DIR
        / "bounded_bridge_confirmation_interannual_2014_2016.csv"
    )

    coverage_path = (
        DIAG_DIR
        / "bounded_bridge_coverage_2014_2021.csv"
    )

    prediction_path = (
        PROCESSED_DIR
        / "bounded_bridge_predictions_2014_2021.csv"
    )

    coefficient_table.to_csv(
        coefficient_path,
        index=False,
    )

    metrics_df.to_csv(
        metrics_path,
        index=False,
    )

    year_means.to_csv(
        year_means_path,
        index=False,
    )

    confirmation_interannual.to_csv(
        interannual_path,
        index=False,
    )

    coverage.to_csv(
        coverage_path,
        index=False,
    )

    all_predictions.to_csv(
        prediction_path,
        index=False,
    )

    # -------------------------------------------------------------
    # Console report
    # -------------------------------------------------------------

    print("")
    print(
        "BOUNDED BRIDGE CONFIRMATION COMPLETE"
    )
    print("")

    print(
        "Frozen bridge:"
    )
    print(
        "  QA: valid"
    )
    print(
        "  spatial order: index then aggregate"
    )
    print(
        "  temporal summary: mean across fixed 15 composites"
    )
    print(
        "  model: fractional logit"
    )
    print(
        "  predictor: seasonal NDFI only"
    )
    print("")

    print(
        "Confirmation years were not used for model fitting:"
    )
    print(
        "  2014, 2015, 2016"
    )
    print("")

    print(
        "Confirmation metrics by year:"
    )

    confirmation_metrics = metrics_df.loc[
        (
            metrics_df["subset"]
            == "confirmation"
        )
        & (
            metrics_df["year"]
            != "pooled_2014_2016"
        )
    ]

    print(
        confirmation_metrics[
            [
                "year",
                "n",
                "pearson_r",
                "spearman_rho",
                "rmse",
                "mae",
                "bias",
                "observed_mean_ff",
                "predicted_mean_ff",
                "prediction_below_zero_n",
                "prediction_above_one_n",
            ]
        ].to_string(
            index=False
        )
    )

    print("")
    print(
        "Pooled confirmation:"
    )

    pooled = metrics_df.loc[
        (
            metrics_df["subset"]
            == "confirmation"
        )
        & (
            metrics_df["year"]
            == "pooled_2014_2016"
        )
    ]

    print(
        pooled.to_string(
            index=False
        )
    )

    print("")
    print(
        "Confirmation annual means:"
    )
    print(
        confirmation_means.to_string(
            index=False
        )
    )

    print("")
    print(
        "Confirmation interannual diagnostics:"
    )
    print(
        confirmation_interannual.to_string(
            index=False
        )
    )

    print("")
    print(
        f"Balanced confirmation cells: "
        f"{len(balanced_confirmation):,}"
    )

    print("")
    print(
        "No refitting or candidate selection was performed "
        "after confirmation FF was opened."
    )
    print(
        "No groundwater data were used."
    )

    print("")
    print(f"Wrote: {coefficient_path}")
    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {year_means_path}")
    print(f"Wrote: {interannual_path}")
    print(f"Wrote: {coverage_path}")
    print(f"Wrote: {prediction_path}")


if __name__ == "__main__":
    main()
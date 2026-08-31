from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import pearsonr, spearmanr


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

COEFFICIENT_FILE = (
    DIAG_DIR
    / "bounded_bridge_coefficients_2017_2021.csv"
)

PREVIOUS_YEAR_MEANS_FILE = (
    DIAG_DIR
    / "bounded_bridge_year_means_2014_2021.csv"
)

NEW_CONFIRMATION_YEARS = (2010, 2011, 2012, 2013)
PREVIOUS_CONFIRMATION_YEARS = (2014, 2015, 2016)
FULL_CONFIRMATION_YEARS = (
    NEW_CONFIRMATION_YEARS
    + PREVIOUS_CONFIRMATION_YEARS
)

EXPECTED_RICE_GRID_CELLS = 4331
EXPECTED_NATIVE_PER_CELL = 4
EXPECTED_COMPOSITES = 15

EXPECTED_INTERCEPT = -0.589681615540
EXPECTED_SLOPE = 15.145272547528

COEFFICIENT_TOLERANCE = 1e-9

BRIDGE_NAME = (
    "valid__index_then_aggregate__fractional_logit"
)


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


def read_frozen_coefficients() -> tuple[float, float]:
    if not COEFFICIENT_FILE.exists():
        raise FileNotFoundError(COEFFICIENT_FILE)

    d = pd.read_csv(COEFFICIENT_FILE)

    if len(d) != 1:
        raise AssertionError(
            "Expected exactly one frozen coefficient row."
        )

    row = d.iloc[0]

    intercept = float(row["intercept"])
    slope = float(row["slope"])

    if not np.isclose(
        intercept,
        EXPECTED_INTERCEPT,
        atol=COEFFICIENT_TOLERANCE,
        rtol=0,
    ):
        raise AssertionError(
            "Stored intercept differs from frozen value: "
            f"{intercept}"
        )

    if not np.isclose(
        slope,
        EXPECTED_SLOPE,
        atol=COEFFICIENT_TOLERANCE,
        rtol=0,
    ):
        raise AssertionError(
            "Stored slope differs from frozen value: "
            f"{slope}"
        )

    return intercept, slope


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

    if (
        df["rice_cell_id"].nunique()
        != EXPECTED_RICE_GRID_CELLS
    ):
        raise AssertionError(
            f"{year}: unexpected RiceFloodIT cell count."
        )

    if (
        df["composite_start_doy"].nunique()
        != EXPECTED_COMPOSITES
    ):
        raise AssertionError(
            f"{year}: unexpected composite count."
        )

    if df["year"].nunique() != 1:
        raise AssertionError(
            f"{year}: multiple years in native table."
        )

    if int(df["year"].iloc[0]) != year:
        raise AssertionError(
            f"{year}: year field mismatch."
        )

    return df


def valid_mask(
    df: pd.DataFrame,
) -> pd.Series:
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
            seasonal_signal=(
                "composite_ndfi",
                "mean",
            ),
            composites_valid=(
                "composite_ndfi",
                "count",
            ),
            mean_native_per_composite=(
                "native_valid",
                "mean",
            ),
        )
    )

    annual["year"] = year

    if len(annual) != EXPECTED_RICE_GRID_CELLS:
        raise AssertionError(
            f"{year}: seasonal table lost grid cells."
        )

    if annual["seasonal_signal"].isna().any():
        raise AssertionError(
            f"{year}: missing seasonal signal."
        )

    return annual


def frozen_prediction(
    seasonal_signal: pd.Series,
    intercept: float,
    slope: float,
) -> pd.Series:
    linear_predictor = (
        intercept
        + slope * seasonal_signal
    )

    prediction = pd.Series(
        expit(linear_predictor.to_numpy()),
        index=seasonal_signal.index,
        dtype=float,
    )

    if (
        (prediction < 0)
        | (prediction > 1)
    ).any():
        raise AssertionError(
            "Bounded prediction outside [0,1]."
        )

    return prediction


def read_confirmation_reference() -> pd.DataFrame:
    """
    This is deliberately called only after:
      1. predictors have been generated;
      2. frozen coefficients have been verified;
      3. predictions have been generated.
    """

    ff = pd.read_csv(RICE_FILE)

    ff = ff.loc[
        ff["year"].isin(
            NEW_CONFIRMATION_YEARS
        ),
        [
            "x",
            "y",
            "year",
            "ff",
        ],
    ].copy()

    if ff["ff"].isna().any():
        raise AssertionError(
            "Missing FF in new confirmation years."
        )

    if ff.duplicated(
        [
            "year",
            "x",
            "y",
        ]
    ).any():
        raise AssertionError(
            "Duplicate year/x/y records."
        )

    if (
        (ff["ff"] < 0)
        | (ff["ff"] > 1)
    ).any():
        raise AssertionError(
            "Published FF outside [0,1]."
        )

    return ff


def evaluate(
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

    print(
        "EXTENDED CONFIRMATION: predictor construction"
    )
    print(
        "RiceFloodIT FF for 2010-2013 has not yet "
        "been read by this script."
    )
    print("")

    intercept, slope = read_frozen_coefficients()

    print("Frozen coefficients verified:")
    print(f"  intercept: {intercept:.12f}")
    print(f"  slope:     {slope:.12f}")
    print("")

    prediction_frames = []

    for year in NEW_CONFIRMATION_YEARS:
        native = read_native_year(year)

        features = build_seasonal_signal(
            native,
            year,
        )

        features["prediction"] = (
            frozen_prediction(
                features["seasonal_signal"],
                intercept,
                slope,
            )
        )

        prediction_frames.append(
            features
        )

    predictions = pd.concat(
        prediction_frames,
        ignore_index=True,
    )

    print(
        "Predictions generated for 2010-2013 "
        "using frozen coefficients."
    )
    print(
        "No RiceFloodIT FF for those years has "
        "been read yet."
    )
    print("")

    # -------------------------------------------------------------
    # Confirmation reveal begins here.
    # No fitting or model modification occurs after this point.
    # -------------------------------------------------------------

    print(
        "Opening RiceFloodIT FF for new confirmation "
        "years 2010-2013..."
    )

    reference = read_confirmation_reference()

    merged_frames = []

    for year in NEW_CONFIRMATION_YEARS:
        p = predictions.loc[
            predictions["year"] == year
        ].copy()

        r = reference.loc[
            reference["year"] == year,
            [
                "x",
                "y",
                "ff",
            ],
        ].copy()

        m = p.merge(
            r,
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

        if len(m) != len(r):
            raise AssertionError(
                f"{year}: incomplete reference support merge. "
                f"reference={len(r)}, merged={len(m)}"
            )

        m["split"] = "extended_confirmation"

        merged_frames.append(
            m
        )

    confirmation = pd.concat(
        merged_frames,
        ignore_index=True,
    )

    metric_rows = []

    for year in NEW_CONFIRMATION_YEARS:
        metric_rows.append(
            evaluate(
                confirmation.loc[
                    confirmation["year"] == year
                ],
                subset="extended_confirmation",
                year_label=str(year),
            )
        )

    metric_rows.append(
        evaluate(
            confirmation,
            subset="extended_confirmation",
            year_label="pooled_2010_2013",
        )
    )

    metrics = pd.DataFrame(
        metric_rows
    )

    new_year_means = (
        confirmation.groupby(
            "year",
            as_index=False,
        )
        .agg(
            observed_mean_ff=("ff", "mean"),
            predicted_mean_ff=("prediction", "mean"),
            n=("ff", "size"),
        )
    )

    new_year_means["split"] = (
        "extended_confirmation"
    )

    # -------------------------------------------------------------
    # Combine only annual means with the already completed
    # 2014-2016 independent confirmation.
    # -------------------------------------------------------------

    previous = pd.read_csv(
        PREVIOUS_YEAR_MEANS_FILE
    )

    previous = previous.loc[
        previous["year"].isin(
            PREVIOUS_CONFIRMATION_YEARS
        ),
        [
            "year",
            "split",
            "observed_mean_ff",
            "predicted_mean_ff",
            "n",
        ],
    ].copy()

    full_year_means = pd.concat(
        [
            new_year_means[
                [
                    "year",
                    "split",
                    "observed_mean_ff",
                    "predicted_mean_ff",
                    "n",
                ]
            ],
            previous,
        ],
        ignore_index=True,
    ).sort_values(
        "year"
    )

    if tuple(
        full_year_means["year"]
        .astype(int)
        .tolist()
    ) != FULL_CONFIRMATION_YEARS:
        raise AssertionError(
            "Unexpected 2010-2016 annual-mean year set."
        )

    annual_error = (
        full_year_means["predicted_mean_ff"]
        - full_year_means["observed_mean_ff"]
    )

    interannual = pd.DataFrame(
        [
            {
                "bridge": BRIDGE_NAME,
                "years": "2010-2016",
                "n_years": 7,
                "pearson_annual_means":
                    safe_pearson(
                        full_year_means[
                            "predicted_mean_ff"
                        ],
                        full_year_means[
                            "observed_mean_ff"
                        ],
                    ),
                "spearman_annual_means":
                    safe_spearman(
                        full_year_means[
                            "predicted_mean_ff"
                        ],
                        full_year_means[
                            "observed_mean_ff"
                        ],
                    ),
                "annual_mean_rmse":
                    float(
                        np.sqrt(
                            np.mean(
                                annual_error**2
                            )
                        )
                    ),
                "annual_mean_mae":
                    float(
                        np.mean(
                            np.abs(
                                annual_error
                            )
                        )
                    ),
                "annual_mean_bias":
                    float(
                        annual_error.mean()
                    ),
                "annual_mean_max_abs_error":
                    float(
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
    # Balanced support for newly revealed years.
    # -------------------------------------------------------------

    year_sets = []

    for year in NEW_CONFIRMATION_YEARS:
        g = confirmation.loc[
            confirmation["year"] == year,
            [
                "rice_x",
                "rice_y",
            ],
        ]

        year_sets.append(
            set(
                map(
                    tuple,
                    g.to_numpy(),
                )
            )
        )

    balanced_cells = set.intersection(
        *year_sets
    )

    balanced_lookup = pd.DataFrame(
        list(balanced_cells),
        columns=[
            "rice_x",
            "rice_y",
        ],
    )

    balanced = confirmation.merge(
        balanced_lookup,
        on=[
            "rice_x",
            "rice_y",
        ],
        how="inner",
        validate="many_to_one",
    )

    balanced_metric = pd.DataFrame(
        [
            evaluate(
                balanced,
                subset="extended_confirmation_balanced",
                year_label="pooled_2010_2013",
            )
        ]
    )

    metrics = pd.concat(
        [
            metrics,
            balanced_metric,
        ],
        ignore_index=True,
    )

    metrics_path = (
        DIAG_DIR
        / "extended_bridge_confirmation_metrics_2010_2013.csv"
    )

    year_means_path = (
        DIAG_DIR
        / "extended_bridge_year_means_2010_2016.csv"
    )

    interannual_path = (
        DIAG_DIR
        / "extended_bridge_interannual_2010_2016.csv"
    )

    prediction_path = (
        PROCESSED_DIR
        / "extended_bridge_predictions_2010_2013.csv"
    )

    metrics.to_csv(
        metrics_path,
        index=False,
    )

    full_year_means.to_csv(
        year_means_path,
        index=False,
    )

    interannual.to_csv(
        interannual_path,
        index=False,
    )

    confirmation.to_csv(
        prediction_path,
        index=False,
    )

    print("")
    print(
        "EXTENDED HISTORICAL CONFIRMATION COMPLETE"
    )
    print("")

    print(
        "No coefficients were re-estimated."
    )
    print(
        "No QA, spatial, temporal, or model rule changed."
    )
    print("")

    print(
        "New confirmation metrics:"
    )

    print(
        metrics.to_string(
            index=False
        )
    )

    print("")
    print(
        "Full independent annual-mean confirmation:"
    )

    print(
        full_year_means.to_string(
            index=False
        )
    )

    print("")
    print(
        "2010-2016 interannual diagnostics:"
    )

    print(
        interannual.to_string(
            index=False
        )
    )

    print("")
    print(
        f"Balanced 2010-2013 cells: "
        f"{len(balanced_cells):,}"
    )

    print("")
    print(
        "No groundwater data were used."
    )

    print("")
    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {year_means_path}")
    print(f"Wrote: {interannual_path}")
    print(f"Wrote: {prediction_path}")


if __name__ == "__main__":
    main()
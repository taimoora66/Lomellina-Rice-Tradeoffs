from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit


ROOT = Path(__file__).resolve().parents[2]

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

YEARS = (2022, 2023, 2024, 2025)

EXPECTED_RICE_GRID_CELLS = 4331
EXPECTED_NATIVE_PER_CELL = 4
EXPECTED_COMPOSITES = 15

EXPECTED_INTERCEPT = -0.589681615540
EXPECTED_SLOPE = 15.145272547528
COEFFICIENT_TOLERANCE = 1e-9

PRODUCT_NAME = "ricefloodit_compatible_frozen_bridge_v1"


def read_frozen_coefficients() -> tuple[float, float]:
    if not COEFFICIENT_FILE.exists():
        raise FileNotFoundError(COEFFICIENT_FILE)

    d = pd.read_csv(COEFFICIENT_FILE)

    if len(d) != 1:
        raise AssertionError(
            "Expected exactly one frozen coefficient row."
        )

    intercept = float(d.loc[0, "intercept"])
    slope = float(d.loc[0, "slope"])

    if not np.isclose(
        intercept,
        EXPECTED_INTERCEPT,
        atol=COEFFICIENT_TOLERANCE,
        rtol=0,
    ):
        raise AssertionError(
            f"Frozen intercept mismatch: {intercept}"
        )

    if not np.isclose(
        slope,
        EXPECTED_SLOPE,
        atol=COEFFICIENT_TOLERANCE,
        rtol=0,
    ):
        raise AssertionError(
            f"Frozen slope mismatch: {slope}"
        )

    return intercept, slope


def read_native_year(year: int) -> pd.DataFrame:
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
            f"{year}: expected {expected_rows:,} rows, "
            f"found {len(df):,}"
        )

    if df["rice_cell_id"].nunique() != EXPECTED_RICE_GRID_CELLS:
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

    return df


def valid_mask(df: pd.DataFrame) -> pd.Series:
    return (
        df["valid_b01"].astype(bool)
        & df["valid_b07"].astype(bool)
        & df["state_valid"].astype(bool)
        & df["qc_valid"].astype(bool)
        & df["ndfi"].notna()
    )


def build_annual_signal(
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
            seasonal_ndfi=("composite_ndfi", "mean"),
            composites_valid=("composite_ndfi", "count"),
            min_native_valid=("native_valid", "min"),
            mean_native_valid=("native_valid", "mean"),
        )
    )

    annual["year"] = year

    if len(annual) != EXPECTED_RICE_GRID_CELLS:
        raise AssertionError(
            f"{year}: annual product lost grid cells."
        )

    if annual["seasonal_ndfi"].isna().any():
        raise AssertionError(
            f"{year}: missing seasonal NDFI."
        )

    return annual


def main() -> None:
    DIAG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    intercept, slope = read_frozen_coefficients()

    print("Frozen coefficients verified")
    print(f"  intercept: {intercept:.12f}")
    print(f"  slope:     {slope:.12f}")
    print("")

    frames = []
    qa_rows = []

    for year in YEARS:
        native = read_native_year(year)

        annual = build_annual_signal(
            native,
            year,
        )

        linear_predictor = (
            intercept
            + slope * annual["seasonal_ndfi"]
        )

        annual["ff_reconstructed"] = expit(
            linear_predictor.to_numpy()
        )

        annual["product"] = PRODUCT_NAME
        annual["bridge_intercept"] = intercept
        annual["bridge_slope"] = slope

        if (
            (annual["ff_reconstructed"] < 0)
            | (annual["ff_reconstructed"] > 1)
        ).any():
            raise AssertionError(
                f"{year}: reconstructed FF outside [0,1]."
            )

        qa_rows.append(
            {
                "year": year,
                "rows": len(annual),
                "rice_cells": annual["rice_cell_id"].nunique(),
                "seasonal_ndfi_nonmissing": int(
                    annual["seasonal_ndfi"].notna().sum()
                ),
                "ff_nonmissing": int(
                    annual["ff_reconstructed"].notna().sum()
                ),
                "ff_mean": float(
                    annual["ff_reconstructed"].mean()
                ),
                "ff_sd": float(
                    annual["ff_reconstructed"].std()
                ),
                "ff_min": float(
                    annual["ff_reconstructed"].min()
                ),
                "ff_max": float(
                    annual["ff_reconstructed"].max()
                ),
                "mean_composites_valid": float(
                    annual["composites_valid"].mean()
                ),
                "min_composites_valid": int(
                    annual["composites_valid"].min()
                ),
                "mean_native_valid": float(
                    annual["mean_native_valid"].mean()
                ),
                "min_native_valid": int(
                    annual["min_native_valid"].min()
                ),
            }
        )

        frames.append(annual)

    product = pd.concat(
        frames,
        ignore_index=True,
    )

    qa = pd.DataFrame(qa_rows)

    annual_summary = (
        product.groupby(
            "year",
            as_index=False,
        )
        .agg(
            ff_mean=("ff_reconstructed", "mean"),
            ff_sd=("ff_reconstructed", "std"),
            ff_min=("ff_reconstructed", "min"),
            ff_max=("ff_reconstructed", "max"),
            n_cells=("ff_reconstructed", "size"),
        )
    )

    overall_mean = float(
        annual_summary["ff_mean"].mean()
    )

    annual_summary["ff_mean_anomaly"] = (
        annual_summary["ff_mean"]
        - overall_mean
    )

    cell_mean = (
        product.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
            ],
            as_index=False,
        )
        .agg(
            cell_mean_ff=(
                "ff_reconstructed",
                "mean",
            )
        )
    )

    product = product.merge(
        cell_mean,
        on=[
            "rice_cell_id",
            "rice_x",
            "rice_y",
        ],
        how="left",
        validate="many_to_one",
    )

    product["ff_cell_anomaly"] = (
        product["ff_reconstructed"]
        - product["cell_mean_ff"]
    )

    product_path = (
        PROCESSED_DIR
        / "ricefloodit_compatible_ff_2022_2025.csv"
    )

    qa_path = (
        DIAG_DIR
        / "post2021_frozen_ff_qa_2022_2025.csv"
    )

    summary_path = (
        DIAG_DIR
        / "post2021_frozen_ff_annual_summary_2022_2025.csv"
    )

    product.to_csv(
        product_path,
        index=False,
    )

    qa.to_csv(
        qa_path,
        index=False,
    )

    annual_summary.to_csv(
        summary_path,
        index=False,
    )

    print("POST-2021 FROZEN FF GENERATION COMPLETE")
    print("")
    print(qa.to_string(index=False))
    print("")
    print("Annual summary:")
    print(
        annual_summary.to_string(
            index=False
        )
    )
    print("")
    print(
        "No model fitting was performed."
    )
    print(
        "No RiceFloodIT post-2021 observations exist or were used."
    )
    print(
        "No groundwater data were read."
    )
    print("")
    print(f"Wrote: {product_path}")
    print(f"Wrote: {qa_path}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
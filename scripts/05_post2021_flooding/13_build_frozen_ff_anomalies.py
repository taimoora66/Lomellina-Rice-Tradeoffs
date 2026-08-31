from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit


ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = ROOT / "data" / "processed" / "post2021"
DIAG_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

COEFFICIENT_FILE = (
    DIAG_DIR / "bounded_bridge_coefficients_2017_2021.csv"
)

YEARS = tuple(range(2010, 2026))
BASELINE_YEARS = tuple(range(2010, 2022))
POST2021_YEARS = (2022, 2023, 2024, 2025)

EXPECTED_RICE_CELLS = 4331
EXPECTED_COMPOSITES = 15
EXPECTED_NATIVE_PER_CELL = 4

EXPECTED_INTERCEPT = -0.589681615540
EXPECTED_SLOPE = 15.145272547528
TOL = 1e-9

PRODUCT = "ricefloodit_compatible_frozen_bridge_v1"
BASELINE_NAME = "cell_mean_reconstructed_ff_2010_2021"


def read_coefficients() -> tuple[float, float]:
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
        atol=TOL,
        rtol=0,
    ):
        raise AssertionError(
            f"Frozen intercept mismatch: {intercept}"
        )

    if not np.isclose(
        slope,
        EXPECTED_SLOPE,
        atol=TOL,
        rtol=0,
    ):
        raise AssertionError(
            f"Frozen slope mismatch: {slope}"
        )

    return intercept, slope


def read_native(year: int) -> pd.DataFrame:
    path = (
        PROCESSED_DIR
        / f"mod09a1_ricefloodit_native_pixels_{year}.csv"
    )

    if not path.exists():
        raise FileNotFoundError(path)

    d = pd.read_csv(path)

    expected_rows = (
        EXPECTED_RICE_CELLS
        * EXPECTED_NATIVE_PER_CELL
        * EXPECTED_COMPOSITES
    )

    if len(d) != expected_rows:
        raise AssertionError(
            f"{year}: expected {expected_rows:,} native rows, "
            f"found {len(d):,}"
        )

    if d["rice_cell_id"].nunique() != EXPECTED_RICE_CELLS:
        raise AssertionError(
            f"{year}: unexpected RiceFloodIT cell count."
        )

    if (
        d["composite_start_doy"].nunique()
        != EXPECTED_COMPOSITES
    ):
        raise AssertionError(
            f"{year}: unexpected composite count."
        )

    return d


def build_year(
    d: pd.DataFrame,
    year: int,
    intercept: float,
    slope: float,
) -> pd.DataFrame:
    valid = (
        d["valid_b01"].astype(bool)
        & d["valid_b07"].astype(bool)
        & d["state_valid"].astype(bool)
        & d["qc_valid"].astype(bool)
        & d["ndfi"].notna()
    )

    x = d.loc[
        valid,
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
        )
    )

    annual["year"] = year

    if len(annual) != EXPECTED_RICE_CELLS:
        raise AssertionError(
            f"{year}: annual grid is incomplete."
        )

    if annual["seasonal_ndfi"].isna().any():
        raise AssertionError(
            f"{year}: missing seasonal NDFI."
        )

    annual["ff_reconstructed"] = expit(
        intercept
        + slope * annual["seasonal_ndfi"].to_numpy()
    )

    annual["product"] = PRODUCT

    return annual


def main() -> None:
    DIAG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    intercept, slope = read_coefficients()

    print("Frozen bridge coefficients verified.")
    print(f"  intercept = {intercept:.12f}")
    print(f"  slope     = {slope:.12f}")
    print("")

    frames = []

    for year in YEARS:
        d = read_native(year)

        annual = build_year(
            d,
            year,
            intercept,
            slope,
        )

        frames.append(annual)

        print(
            f"{year}: "
            f"{len(annual):,} cells; "
            f"mean FF={annual['ff_reconstructed'].mean():.6f}; "
            f"min composites={annual['composites_valid'].min()}"
        )

    panel = pd.concat(
        frames,
        ignore_index=True,
    )

    expected_panel_rows = (
        len(YEARS)
        * EXPECTED_RICE_CELLS
    )

    if len(panel) != expected_panel_rows:
        raise AssertionError(
            "Unexpected full reconstructed panel size."
        )

    # ---------------------------------------------------------
    # Fixed historical baseline: reconstructed 2010-2021 only.
    # ---------------------------------------------------------

    baseline_source = panel.loc[
        panel["year"].isin(BASELINE_YEARS)
    ].copy()

    baseline_counts = (
        baseline_source.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
            ]
        )["year"]
        .nunique()
    )

    if not (
        baseline_counts == len(BASELINE_YEARS)
    ).all():
        raise AssertionError(
            "Not every cell has all 12 baseline years."
        )

    baseline = (
        baseline_source.groupby(
            [
                "rice_cell_id",
                "rice_x",
                "rice_y",
            ],
            as_index=False,
        )
        .agg(
            ff_baseline_2010_2021=(
                "ff_reconstructed",
                "mean",
            )
        )
    )

    if len(baseline) != EXPECTED_RICE_CELLS:
        raise AssertionError(
            "Unexpected historical baseline cell count."
        )

    panel = panel.merge(
        baseline,
        on=[
            "rice_cell_id",
            "rice_x",
            "rice_y",
        ],
        how="left",
        validate="many_to_one",
    )

    panel["ff_anomaly_2010_2021"] = (
        panel["ff_reconstructed"]
        - panel["ff_baseline_2010_2021"]
    )

    panel["baseline_definition"] = BASELINE_NAME

    post = panel.loc[
        panel["year"].isin(POST2021_YEARS)
    ].copy()

    # ---------------------------------------------------------
    # Compact annual QA.
    # ---------------------------------------------------------

    annual = (
        panel.groupby(
            "year",
            as_index=False,
        )
        .agg(
            n_cells=("rice_cell_id", "size"),
            ff_mean=("ff_reconstructed", "mean"),
            ff_sd=("ff_reconstructed", "std"),
            anomaly_mean=("ff_anomaly_2010_2021", "mean"),
            anomaly_sd=("ff_anomaly_2010_2021", "std"),
            anomaly_min=("ff_anomaly_2010_2021", "min"),
            anomaly_max=("ff_anomaly_2010_2021", "max"),
            min_composites=("composites_valid", "min"),
            min_native_valid=("min_native_valid", "min"),
        )
    )

    baseline_check = (
        panel.loc[
            panel["year"].isin(BASELINE_YEARS)
        ]
        .groupby(
            "rice_cell_id"
        )["ff_anomaly_2010_2021"]
        .mean()
    )

    max_abs_cell_baseline_residual = float(
        baseline_check.abs().max()
    )

    if max_abs_cell_baseline_residual > 1e-12:
        raise AssertionError(
            "Cell anomalies do not center exactly over "
            "the 2010-2021 baseline."
        )

    qa = pd.DataFrame(
        [
            {
                "years_generated": "2010-2025",
                "baseline_years": "2010-2021",
                "baseline_n_years": 12,
                "rice_cells": EXPECTED_RICE_CELLS,
                "panel_rows": len(panel),
                "post2021_rows": len(post),
                "max_abs_cell_baseline_residual":
                    max_abs_cell_baseline_residual,
                "bridge_intercept": intercept,
                "bridge_slope": slope,
            }
        ]
    )

    panel_path = (
        PROCESSED_DIR
        / "frozen_ff_anomaly_panel_2010_2025.csv"
    )

    post_path = (
        PROCESSED_DIR
        / "frozen_ff_anomalies_2022_2025.csv"
    )

    baseline_path = (
        PROCESSED_DIR
        / "frozen_ff_baseline_2010_2021.csv"
    )

    annual_path = (
        DIAG_DIR
        / "frozen_ff_anomaly_annual_qa_2010_2025.csv"
    )

    qa_path = (
        DIAG_DIR
        / "frozen_ff_anomaly_definition_qa.csv"
    )

    panel.to_csv(
        panel_path,
        index=False,
    )

    post.to_csv(
        post_path,
        index=False,
    )

    baseline.to_csv(
        baseline_path,
        index=False,
    )

    annual.to_csv(
        annual_path,
        index=False,
    )

    qa.to_csv(
        qa_path,
        index=False,
    )

    print("")
    print("FROZEN FF ANOMALY PANEL COMPLETE")
    print("")
    print(
        "Baseline: cell-specific reconstructed FF mean, "
        "2010-2021."
    )
    print(
        "No groundwater data were read."
    )
    print(
        "No bridge parameters were fitted or changed."
    )
    print("")
    print("Post-2021 annual diagnostics:")
    print(
        annual.loc[
            annual["year"].isin(POST2021_YEARS)
        ].to_string(
            index=False
        )
    )
    print("")
    print(
        "Maximum absolute cell baseline-centering residual: "
        f"{max_abs_cell_baseline_residual:.3e}"
    )
    print("")
    print(f"Wrote: {panel_path}")
    print(f"Wrote: {post_path}")
    print(f"Wrote: {baseline_path}")
    print(f"Wrote: {annual_path}")
    print(f"Wrote: {qa_path}")


if __name__ == "__main__":
    main()
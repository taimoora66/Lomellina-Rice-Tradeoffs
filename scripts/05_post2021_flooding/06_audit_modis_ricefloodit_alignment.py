from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

RICE = (
    ROOT
    / "data"
    / "raw"
    / "RiceFloodIT"
    / "ffavg_2021.csv"
)

OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "modis_ricefloodit_alignment_qa.json"
)


# Standard MODIS sinusoidal tiling constants.
RADIUS = 6371007.181
TILE_SIZE = 1111950.5196666666
NPIX = 2400
PIXEL_SIZE = TILE_SIZE / NPIX

GLOBAL_X_MIN = -20015109.354
GLOBAL_Y_MAX = 10007554.677

H = 18
V = 4


def main() -> None:
    ff = pd.read_csv(RICE)

    required = {"x", "y"}

    if not required.issubset(ff.columns):
        raise AssertionError(
            f"RiceFloodIT file must contain {required}"
        )

    rice_xy = (
        ff[["x", "y"]]
        .drop_duplicates()
        .sort_values(["y", "x"])
        .reset_index(drop=True)
    )

    tile_xmin = GLOBAL_X_MIN + H * TILE_SIZE
    tile_ymax = GLOBAL_Y_MAX - V * TILE_SIZE

    # Pixel-center coordinates.
    cols = np.arange(NPIX)
    rows = np.arange(NPIX)

    x_centers = (
        tile_xmin
        + (cols + 0.5) * PIXEL_SIZE
    )

    y_centers = (
        tile_ymax
        - (rows + 0.5) * PIXEL_SIZE
    )

    # For each RiceFloodIT coordinate, find closest 500-m
    # MODIS pixel center independently in x and y.
    rice_x = rice_xy["x"].to_numpy(float)
    rice_y = rice_xy["y"].to_numpy(float)

    col_float = (
        (rice_x - tile_xmin) / PIXEL_SIZE
        - 0.5
    )

    row_float = (
        (tile_ymax - rice_y) / PIXEL_SIZE
        - 0.5
    )

    col_nearest = np.rint(col_float).astype(int)
    row_nearest = np.rint(row_float).astype(int)

    inside = (
        (col_nearest >= 0)
        & (col_nearest < NPIX)
        & (row_nearest >= 0)
        & (row_nearest < NPIX)
    )

    x_nearest = np.full(len(rice_xy), np.nan)
    y_nearest = np.full(len(rice_xy), np.nan)

    x_nearest[inside] = x_centers[
        col_nearest[inside]
    ]

    y_nearest[inside] = y_centers[
        row_nearest[inside]
    ]

    dx = rice_x - x_nearest
    dy = rice_y - y_nearest

    distance = np.sqrt(dx**2 + dy**2)

    # Determine RiceFloodIT native grid spacings.
    unique_x = np.sort(
        rice_xy["x"].unique()
    )
    unique_y = np.sort(
        rice_xy["y"].unique()
    )

    dx_unique = np.diff(unique_x)
    dy_unique = np.diff(unique_y)

    positive_dx = dx_unique[dx_unique > 0]
    positive_dy = np.abs(
        dy_unique[dy_unique != 0]
    )

    result = {
        "modis_tile": "h18v04",
        "modis_tile_size_m": TILE_SIZE,
        "modis_pixels_per_side": NPIX,
        "modis_pixel_size_m": PIXEL_SIZE,

        "tile_xmin": tile_xmin,
        "tile_xmax": tile_xmin + TILE_SIZE,
        "tile_ymin": tile_ymax - TILE_SIZE,
        "tile_ymax": tile_ymax,

        "rice_unique_xy_rows": int(len(rice_xy)),
        "rice_x_min": float(rice_x.min()),
        "rice_x_max": float(rice_x.max()),
        "rice_y_min": float(rice_y.min()),
        "rice_y_max": float(rice_y.max()),

        "rice_median_positive_x_spacing_m":
            float(np.median(positive_dx)),

        "rice_median_positive_y_spacing_m":
            float(np.median(positive_dy)),

        "rice_to_modis_spacing_ratio_x":
            float(
                np.median(positive_dx)
                / PIXEL_SIZE
            ),

        "rice_to_modis_spacing_ratio_y":
            float(
                np.median(positive_dy)
                / PIXEL_SIZE
            ),

        "rice_points_inside_h18v04":
            int(inside.sum()),

        "rice_points_outside_h18v04":
            int((~inside).sum()),

        "nearest_500m_center_dx_abs_median":
            float(
                np.nanmedian(np.abs(dx))
            ),

        "nearest_500m_center_dy_abs_median":
            float(
                np.nanmedian(np.abs(dy))
            ),

        "nearest_500m_center_distance_median":
            float(
                np.nanmedian(distance)
            ),

        "nearest_500m_center_distance_max":
            float(
                np.nanmax(distance)
            ),

        "nearest_col_fractional_residual_median":
            float(
                np.median(
                    np.abs(
                        col_float
                        - np.rint(col_float)
                    )
                )
            ),

        "nearest_row_fractional_residual_median":
            float(
                np.median(
                    np.abs(
                        row_float
                        - np.rint(row_float)
                    )
                )
            ),
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUT.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
        )

    print("MODIS-RiceFloodIT grid alignment audit")
    print("")
    print(f"  MODIS tile: h{H:02d}v{V:02d}")
    print(
        f"  MODIS 500-m pixel size: "
        f"{PIXEL_SIZE:.6f} m"
    )
    print(
        f"  Rice median x spacing: "
        f"{result['rice_median_positive_x_spacing_m']:.6f} m"
    )
    print(
        f"  Rice median y spacing: "
        f"{result['rice_median_positive_y_spacing_m']:.6f} m"
    )
    print(
        f"  spacing ratio x: "
        f"{result['rice_to_modis_spacing_ratio_x']:.8f}"
    )
    print(
        f"  spacing ratio y: "
        f"{result['rice_to_modis_spacing_ratio_y']:.8f}"
    )
    print("")
    print(
        f"  Rice coordinates inside tile: "
        f"{result['rice_points_inside_h18v04']}"
    )
    print(
        f"  outside tile: "
        f"{result['rice_points_outside_h18v04']}"
    )
    print("")
    print(
        "  nearest 500-m center distance:"
    )
    print(
        f"    median = "
        f"{result['nearest_500m_center_distance_median']:.3f} m"
    )
    print(
        f"    max    = "
        f"{result['nearest_500m_center_distance_max']:.3f} m"
    )
    print("")
    print(f"  wrote: {OUT}")
    print("")
    print(
        "No QA rule, spectral index, or FF model "
        "was applied."
    )


if __name__ == "__main__":
    main()

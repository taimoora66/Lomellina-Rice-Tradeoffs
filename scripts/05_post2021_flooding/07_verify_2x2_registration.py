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
    / "ricefloodit_modis_2x2_registration.json"
)


TILE_SIZE = 1111950.5196666666
NPIX = 2400
PIXEL_SIZE = TILE_SIZE / NPIX

GLOBAL_X_MIN = -20015109.354
GLOBAL_Y_MAX = 10007554.677

H = 18
V = 4


def main() -> None:
    ff = pd.read_csv(RICE)

    xy = (
        ff[["x", "y"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    tile_xmin = GLOBAL_X_MIN + H * TILE_SIZE
    tile_ymax = GLOBAL_Y_MAX - V * TILE_SIZE

    x = xy["x"].to_numpy(float)
    y = xy["y"].to_numpy(float)

    # Position relative to pixel edges, not centers.
    col_edge = (x - tile_xmin) / PIXEL_SIZE
    row_edge = (tile_ymax - y) / PIXEL_SIZE

    # A perfect 2x2 block center should lie at integer pixel-edge
    # coordinates with the same parity structure across the grid.
    nearest_col_edge = np.rint(col_edge)
    nearest_row_edge = np.rint(row_edge)

    col_resid = col_edge - nearest_col_edge
    row_resid = row_edge - nearest_row_edge

    col_edge_int = nearest_col_edge.astype(int)
    row_edge_int = nearest_row_edge.astype(int)

    inside_for_2x2 = (
        (col_edge_int >= 1)
        & (col_edge_int <= NPIX - 1)
        & (row_edge_int >= 1)
        & (row_edge_int <= NPIX - 1)
    )

    # Four 500-m cells surrounding each RiceFloodIT center.
    left_col = col_edge_int - 1
    right_col = col_edge_int

    top_row = row_edge_int - 1
    bottom_row = row_edge_int

    # Check parity of the 2x2 block anchors.
    left_col_parity = left_col % 2
    top_row_parity = top_row % 2

    unique_col_parity = sorted(
        np.unique(left_col_parity[inside_for_2x2]).tolist()
    )

    unique_row_parity = sorted(
        np.unique(top_row_parity[inside_for_2x2]).tolist()
    )

    # Compute centers of the implied 2x2 blocks.
    block_x = (
        tile_xmin
        + col_edge_int * PIXEL_SIZE
    )

    block_y = (
        tile_ymax
        - row_edge_int * PIXEL_SIZE
    )

    dx = x - block_x
    dy = y - block_y
    dist = np.sqrt(dx**2 + dy**2)

    # Count unique 2x2 blocks.
    blocks = pd.DataFrame(
        {
            "left_col": left_col,
            "top_row": top_row,
        }
    )

    unique_blocks = len(
        blocks.drop_duplicates()
    )

    result = {
        "rice_points": int(len(xy)),
        "inside_for_2x2": int(inside_for_2x2.sum()),
        "outside_for_2x2": int((~inside_for_2x2).sum()),

        "pixel_size_m": PIXEL_SIZE,

        "max_abs_col_edge_residual_pixels":
            float(np.max(np.abs(col_resid))),

        "max_abs_row_edge_residual_pixels":
            float(np.max(np.abs(row_resid))),

        "median_abs_col_edge_residual_pixels":
            float(np.median(np.abs(col_resid))),

        "median_abs_row_edge_residual_pixels":
            float(np.median(np.abs(row_resid))),

        "block_center_distance_median":
            float(np.median(dist)),

        "block_center_distance_max":
            float(np.max(dist)),

        "unique_left_col_parities":
            unique_col_parity,

        "unique_top_row_parities":
            unique_row_parity,

        "unique_2x2_blocks":
            int(unique_blocks),

        "rice_unique_coordinates":
            int(len(xy)),
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

    print("RiceFloodIT / MOD09A1 2x2 registration audit")
    print("")
    print(f"  RiceFloodIT coordinates: {len(xy)}")
    print(
        f"  valid 2x2 registrations: "
        f"{result['inside_for_2x2']}"
    )
    print("")
    print("  residual to implied 2x2 block center:")
    print(
        f"    median = "
        f"{result['block_center_distance_median']:.6f} m"
    )
    print(
        f"    max    = "
        f"{result['block_center_distance_max']:.6f} m"
    )
    print("")
    print(
        "  max column-edge residual: "
        f"{result['max_abs_col_edge_residual_pixels']:.10f} pixels"
    )
    print(
        "  max row-edge residual: "
        f"{result['max_abs_row_edge_residual_pixels']:.10f} pixels"
    )
    print("")
    print(
        "  left-column parity values: "
        f"{result['unique_left_col_parities']}"
    )
    print(
        "  top-row parity values: "
        f"{result['unique_top_row_parities']}"
    )
    print("")
    print(
        f"  unique implied 2x2 blocks: "
        f"{result['unique_2x2_blocks']}"
    )
    print("")
    print(f"  wrote: {OUT}")


if __name__ == "__main__":
    main()
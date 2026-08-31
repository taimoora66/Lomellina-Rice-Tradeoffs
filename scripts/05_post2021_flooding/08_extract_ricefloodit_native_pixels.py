from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyhdf.SD import SD, SDC


ROOT = Path(__file__).resolve().parents[2]

RICE_FILE = (
    ROOT
    / "data"
    / "raw"
    / "RiceFloodIT"
    / "ffavg_2021.csv"
)

MODIS_DIR = (
    ROOT
    / "data"
    / "raw"
    / "modis"
    / "MOD09A1.061"
    / "2021"
)

OUT_FILE = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "mod09a1_ricefloodit_native_pixels_2021.csv"
)

QA_FILE = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "native_pixel_extraction_qa_2021.csv"
)


TILE_SIZE = 1111950.5196666666
NPIX = 2400
PIXEL_SIZE = TILE_SIZE / NPIX

GLOBAL_X_MIN = -20015109.354
GLOBAL_Y_MAX = 10007554.677

H = 18
V = 4


REFLECTANCE_FILL = -28672
REFLECTANCE_MIN = -100
REFLECTANCE_MAX = 16000
REFLECTANCE_SCALE = 0.0001

STATE_FILL = 65535
DOY_FILL = 65535
QC_FILL = 4294967295


def bitfield(
    arr: np.ndarray,
    start: int,
    width: int,
) -> np.ndarray:
    return (arr >> start) & ((1 << width) - 1)


def parse_composite_start_doy(filename: str) -> int:
    m = re.search(r"\.A2021(\d{3})\.", filename)

    if not m:
        raise ValueError(
            f"Could not parse 2021 DOY from {filename}"
        )

    return int(m.group(1))


def read_sds(
    hdf: SD,
    name: str,
    dtype,
) -> np.ndarray:
    sds = hdf.select(name)

    try:
        return np.asarray(sds[:], dtype=dtype)
    finally:
        sds.endaccess()


def build_registration(
    rice_xy: pd.DataFrame,
) -> pd.DataFrame:
    tile_xmin = GLOBAL_X_MIN + H * TILE_SIZE
    tile_ymax = GLOBAL_Y_MAX - V * TILE_SIZE

    x = rice_xy["x"].to_numpy(float)
    y = rice_xy["y"].to_numpy(float)

    col_edge = np.rint(
        (x - tile_xmin) / PIXEL_SIZE
    ).astype(int)

    row_edge = np.rint(
        (tile_ymax - y) / PIXEL_SIZE
    ).astype(int)

    records = []

    for i in range(len(rice_xy)):
        left_col = col_edge[i] - 1
        right_col = col_edge[i]

        top_row = row_edge[i] - 1
        bottom_row = row_edge[i]

        native = [
            ("NW", top_row, left_col),
            ("NE", top_row, right_col),
            ("SW", bottom_row, left_col),
            ("SE", bottom_row, right_col),
        ]

        for position, row, col in native:
            if not (
                0 <= row < NPIX
                and 0 <= col < NPIX
            ):
                raise AssertionError(
                    "Native pixel falls outside tile."
                )

            records.append(
                {
                    "rice_cell_id": i,
                    "rice_x": x[i],
                    "rice_y": y[i],
                    "native_position": position,
                    "modis_row": row,
                    "modis_col": col,
                }
            )

    registration = pd.DataFrame(records)

    expected = len(rice_xy) * 4

    if len(registration) != expected:
        raise AssertionError(
            f"Expected {expected} registrations, "
            f"found {len(registration)}"
        )

    return registration


def main() -> None:
    rice = pd.read_csv(RICE_FILE)

    rice_xy = (
        rice[["x", "y"]]
        .drop_duplicates()
        .sort_values(["y", "x"])
        .reset_index(drop=True)
    )

    if len(rice_xy) != 4331:
        raise AssertionError(
            f"Expected 4331 RiceFloodIT cells, "
            f"found {len(rice_xy)}"
        )

    registration = build_registration(rice_xy)

    files = sorted(MODIS_DIR.glob("*.hdf"))

    if len(files) != 15:
        raise AssertionError(
            f"Expected 15 MOD09A1 HDF files, "
            f"found {len(files)}"
        )

    expected_doys = list(range(65, 178, 8))

    observed_doys = [
        parse_composite_start_doy(path.name)
        for path in files
    ]

    if observed_doys != expected_doys:
        raise AssertionError(
            "Unexpected MOD09A1 composite sequence: "
            f"{observed_doys}"
        )

    OUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    QA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_frames = []
    qa_rows = []

    rows_idx = registration["modis_row"].to_numpy()
    cols_idx = registration["modis_col"].to_numpy()

    for path in files:
        composite_start_doy = parse_composite_start_doy(
            path.name
        )

        print(path.name)

        hdf = SD(str(path), SDC.READ)

        try:
            b01_raw = read_sds(
                hdf,
                "sur_refl_b01",
                np.int16,
            )

            b02_raw = read_sds(
                hdf,
                "sur_refl_b02",
                np.int16,
            )

            b07_raw = read_sds(
                hdf,
                "sur_refl_b07",
                np.int16,
            )

            state = read_sds(
                hdf,
                "sur_refl_state_500m",
                np.uint16,
            )

            qc = read_sds(
                hdf,
                "sur_refl_qc_500m",
                np.uint32,
            )

            doy = read_sds(
                hdf,
                "sur_refl_day_of_year",
                np.uint16,
            )

        finally:
            hdf.end()

        b01 = b01_raw[rows_idx, cols_idx]
        b02 = b02_raw[rows_idx, cols_idx]
        b07 = b07_raw[rows_idx, cols_idx]

        state_v = state[rows_idx, cols_idx]
        qc_v = qc[rows_idx, cols_idx]
        doy_v = doy[rows_idx, cols_idx]

        valid_b01 = (
            (b01 != REFLECTANCE_FILL)
            & (b01 >= REFLECTANCE_MIN)
            & (b01 <= REFLECTANCE_MAX)
        )

        valid_b02 = (
            (b02 != REFLECTANCE_FILL)
            & (b02 >= REFLECTANCE_MIN)
            & (b02 <= REFLECTANCE_MAX)
        )

        valid_b07 = (
            (b07 != REFLECTANCE_FILL)
            & (b07 >= REFLECTANCE_MIN)
            & (b07 <= REFLECTANCE_MAX)
        )

        valid_reflectance = (
            valid_b01
            & valid_b02
            & valid_b07
        )

        red = np.where(
            valid_b01,
            b01.astype(float) * REFLECTANCE_SCALE,
            np.nan,
        )

        nir = np.where(
            valid_b02,
            b02.astype(float) * REFLECTANCE_SCALE,
            np.nan,
        )

        swir2 = np.where(
            valid_b07,
            b07.astype(float) * REFLECTANCE_SCALE,
            np.nan,
        )

        state_valid = state_v != STATE_FILL
        qc_valid = qc_v != QC_FILL
        doy_valid = doy_v != DOY_FILL

        cloud_state = bitfield(
            state_v,
            0,
            2,
        )

        cloud_shadow = bitfield(
            state_v,
            2,
            1,
        )

        land_water = bitfield(
            state_v,
            3,
            3,
        )

        aerosol = bitfield(
            state_v,
            6,
            2,
        )

        cirrus = bitfield(
            state_v,
            8,
            2,
        )

        internal_cloud = bitfield(
            state_v,
            10,
            1,
        )

        snow_ice = bitfield(
            state_v,
            12,
            1,
        )

        adjacent_cloud = bitfield(
            state_v,
            13,
            1,
        )

        modland = bitfield(
            qc_v,
            0,
            2,
        )

        band1_quality = bitfield(
            qc_v,
            2,
            4,
        )

        band2_quality = bitfield(
            qc_v,
            6,
            4,
        )

        band7_quality = bitfield(
            qc_v,
            26,
            4,
        )

        denom_ndvi = nir + red
        denom_ndfi = red + swir2

        ndvi = np.full(
            len(registration),
            np.nan,
        )

        ndfi = np.full(
            len(registration),
            np.nan,
        )

        ndvi_ok = (
            valid_b01
            & valid_b02
            & np.isfinite(denom_ndvi)
            & (denom_ndvi != 0)
        )

        ndfi_ok = (
            valid_b01
            & valid_b07
            & np.isfinite(denom_ndfi)
            & (denom_ndfi != 0)
        )

        ndvi[ndvi_ok] = (
            nir[ndvi_ok] - red[ndvi_ok]
        ) / denom_ndvi[ndvi_ok]

        ndfi[ndfi_ok] = (
            red[ndfi_ok] - swir2[ndfi_ok]
        ) / denom_ndfi[ndfi_ok]

        frame = registration.copy()

        frame["source_file"] = path.name
        frame["year"] = 2021
        frame["composite_start_doy"] = (
            composite_start_doy
        )

        frame["red_raw"] = b01
        frame["nir_raw"] = b02
        frame["swir2_raw"] = b07

        frame["red"] = red
        frame["nir"] = nir
        frame["swir2"] = swir2

        frame["valid_b01"] = valid_b01
        frame["valid_b02"] = valid_b02
        frame["valid_b07"] = valid_b07
        frame["valid_reflectance"] = (
            valid_reflectance
        )

        frame["pixel_doy"] = np.where(
            doy_valid,
            doy_v.astype(float),
            np.nan,
        )

        frame["state_valid"] = state_valid
        frame["qc_valid"] = qc_valid

        frame["cloud_state"] = cloud_state
        frame["cloud_shadow"] = cloud_shadow
        frame["land_water"] = land_water
        frame["aerosol"] = aerosol
        frame["cirrus"] = cirrus
        frame["internal_cloud"] = (
            internal_cloud
        )
        frame["snow_ice"] = snow_ice
        frame["adjacent_cloud"] = (
            adjacent_cloud
        )

        frame["modland"] = modland
        frame["band1_quality"] = band1_quality
        frame["band2_quality"] = band2_quality
        frame["band7_quality"] = band7_quality

        frame["ndvi"] = ndvi
        frame["ndfi"] = ndfi

        all_frames.append(frame)

        qa_rows.append(
            {
                "source_file": path.name,
                "composite_start_doy":
                    composite_start_doy,
                "rows": len(frame),
                "unique_rice_cells":
                    frame["rice_cell_id"].nunique(),
                "valid_reflectance_rows":
                    int(valid_reflectance.sum()),
                "valid_doy_rows":
                    int(doy_valid.sum()),
                "ndvi_nonmissing":
                    int(np.isfinite(ndvi).sum()),
                "ndfi_nonmissing":
                    int(np.isfinite(ndfi).sum()),
                "pixel_doy_min":
                    int(doy_v[doy_valid].min()),
                "pixel_doy_max":
                    int(doy_v[doy_valid].max()),
            }
        )

    out = pd.concat(
        all_frames,
        ignore_index=True,
    )

    expected_rows = 4331 * 4 * 15

    if len(out) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} rows, "
            f"found {len(out)}"
        )

    if out["rice_cell_id"].nunique() != 4331:
        raise AssertionError(
            "Unexpected RiceFloodIT cell count."
        )

    if out["source_file"].nunique() != 15:
        raise AssertionError(
            "Unexpected MODIS file count."
        )

    out.to_csv(
        OUT_FILE,
        index=False,
    )

    qa = pd.DataFrame(qa_rows)

    qa.to_csv(
        QA_FILE,
        index=False,
    )

    print("")
    print("Native MODIS extraction complete")
    print(f"  rows: {len(out):,}")
    print(
        f"  RiceFloodIT cells: "
        f"{out['rice_cell_id'].nunique():,}"
    )
    print(
        f"  native cells per RiceFloodIT cell: 4"
    )
    print(
        f"  composites: "
        f"{out['source_file'].nunique()}"
    )
    print(
        f"  valid reflectance rows: "
        f"{int(out['valid_reflectance'].sum()):,}"
    )
    print(
        f"  NDVI nonmissing: "
        f"{out['ndvi'].notna().sum():,}"
    )
    print(
        f"  NDFI nonmissing: "
        f"{out['ndfi'].notna().sum():,}"
    )
    print("")
    print(f"  wrote data: {OUT_FILE}")
    print(f"  wrote QA:   {QA_FILE}")
    print("")
    print(
        "No final QA exclusion rule or FF model "
        "was applied."
    )


if __name__ == "__main__":
    main()

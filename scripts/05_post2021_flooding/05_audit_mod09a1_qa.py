from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from pyhdf.SD import SD, SDC


ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = (
    ROOT
    / "data"
    / "raw"
    / "modis"
    / "MOD09A1.061"
    / "2021"
)

OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "mod09a1_qa_audit_2021.csv"
)


def bitfield(arr: np.ndarray, start: int, width: int) -> np.ndarray:
    mask = (1 << width) - 1
    return (arr >> start) & mask


def main() -> None:
    files = sorted(RAW_DIR.glob("*.hdf"))

    if len(files) != 15:
        raise AssertionError(
            f"Expected 15 MOD09A1 HDF files, found {len(files)}"
        )

    rows = []

    for path in files:
        hdf = SD(str(path), SDC.READ)

        try:
            state_sds = hdf.select("sur_refl_state_500m")
            qc_sds = hdf.select("sur_refl_qc_500m")
            doy_sds = hdf.select("sur_refl_day_of_year")

            try:
                state = np.asarray(state_sds[:], dtype=np.uint16)
                qc = np.asarray(qc_sds[:], dtype=np.uint32)
                doy = np.asarray(doy_sds[:], dtype=np.uint16)
            finally:
                state_sds.endaccess()
                qc_sds.endaccess()
                doy_sds.endaccess()

        finally:
            hdf.end()

        if state.shape != (2400, 2400):
            raise AssertionError(
                f"Unexpected state QA shape in {path.name}: {state.shape}"
            )

        cloud_state = bitfield(state, 0, 2)
        cloud_shadow = bitfield(state, 2, 1)
        land_water = bitfield(state, 3, 3)
        aerosol = bitfield(state, 6, 2)
        cirrus = bitfield(state, 8, 2)
        internal_cloud = bitfield(state, 10, 1)
        snow_ice = bitfield(state, 12, 1)
        adjacent_cloud = bitfield(state, 13, 1)

        modland = bitfield(qc, 0, 2)

        band1_quality = bitfield(qc, 2, 4)
        band2_quality = bitfield(qc, 6, 4)
        band7_quality = bitfield(qc, 26, 4)

        state_fill = state == np.uint16(65535)
        qc_fill = qc == np.uint32(4294967295)
        doy_fill = doy == np.uint16(65535)

        usable = ~(state_fill | qc_fill | doy_fill)

        n_usable = int(usable.sum())

        if n_usable == 0:
            raise AssertionError(
                f"No usable QA pixels in {path.name}"
            )

        def count(mask: np.ndarray) -> int:
            return int((mask & usable).sum())

        valid_doy = doy[~doy_fill]

        candidate_clear = (
            usable
            & (cloud_state == 0)
            & (cloud_shadow == 0)
            & (cirrus == 0)
            & (internal_cloud == 0)
            & (adjacent_cloud == 0)
            & (snow_ice == 0)
        )

        candidate_strict = (
            candidate_clear
            & (modland == 0)
            & (band1_quality == 0)
            & (band2_quality == 0)
            & (band7_quality == 0)
        )

        row = {
            "filename": path.name,
            "usable_pixels": n_usable,

            "cloud_clear": count(cloud_state == 0),
            "cloud_cloudy": count(cloud_state == 1),
            "cloud_mixed": count(cloud_state == 2),
            "cloud_not_set": count(cloud_state == 3),

            "cloud_shadow_yes": count(cloud_shadow == 1),

            "cirrus_none": count(cirrus == 0),
            "cirrus_small": count(cirrus == 1),
            "cirrus_average": count(cirrus == 2),
            "cirrus_high": count(cirrus == 3),

            "internal_cloud_yes": count(internal_cloud == 1),
            "adjacent_cloud_yes": count(adjacent_cloud == 1),
            "snow_ice_yes": count(snow_ice == 1),

            "modland_ideal": count(modland == 0),
            "modland_less_than_ideal": count(modland == 1),
            "modland_cloud": count(modland == 2),
            "modland_other": count(modland == 3),

            "band1_highest_quality": count(band1_quality == 0),
            "band2_highest_quality": count(band2_quality == 0),
            "band7_highest_quality": count(band7_quality == 0),

            "doy_min": int(valid_doy.min()),
            "doy_median": float(np.median(valid_doy)),
            "doy_max": int(valid_doy.max()),

            "candidate_clear_pixels": int(candidate_clear.sum()),
            "candidate_strict_pixels": int(candidate_strict.sum()),
        }

        rows.append(row)

        print(path.name)
        print(f"  usable: {n_usable:,}")
        print(
            f"  candidate clear: "
            f"{row['candidate_clear_pixels']:,}"
        )
        print(
            f"  candidate strict: "
            f"{row['candidate_strict_pixels']:,}"
        )
        print(
            f"  DOY range: "
            f"{row['doy_min']}-{row['doy_max']}"
        )

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    print("")
    print("MOD09A1 QA audit complete")
    print(f"  files: {len(rows)}")
    print(f"  wrote: {OUT}")
    print("")
    print(
        "Candidate masks are diagnostic only; "
        "no RiceFloodIT QA rule has been frozen."
    )


if __name__ == "__main__":
    main()

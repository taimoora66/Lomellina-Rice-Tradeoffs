from __future__ import annotations

import json
from pathlib import Path

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
    / "mod09a1_hdf_structure_2021.json"
)


def json_safe(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, (list, tuple)):
        return [json_safe(x) for x in value]

    if isinstance(value, dict):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    try:
        return value.tolist()
    except AttributeError:
        return str(value)


def main() -> None:
    files = sorted(RAW_DIR.glob("*.hdf"))

    print("MOD09A1 HDF4 inspection")
    print(f"  HDF files found: {len(files)}")

    if len(files) != 15:
        raise AssertionError(
            f"Expected 15 HDF files, found {len(files)}"
        )

    sample = files[0]

    print(f"  sample: {sample.name}")
    print("")

    hdf = SD(str(sample), SDC.READ)

    try:
        datasets = hdf.datasets()

        print(f"Scientific datasets found: {len(datasets)}")
        print("")

        output_datasets = []

        for index, name in enumerate(datasets.keys(), start=1):
            sds = hdf.select(name)

            try:
                info = sds.info()

                attributes = {
                    key: json_safe(value)
                    for key, value in sds.attributes().items()
                }

                entry = {
                    "index": index,
                    "name": name,
                    "info": json_safe(info),
                    "attributes": attributes,
                }

                output_datasets.append(entry)

                print(f"[{index}] {name}")
                print(f"    info: {info}")

                for attr in (
                    "_FillValue",
                    "scale_factor",
                    "add_offset",
                    "valid_range",
                    "long_name",
                    "units",
                ):
                    if attr in attributes:
                        print(
                            f"    {attr}: "
                            f"{attributes[attr]}"
                        )

                print("")

            finally:
                sds.endaccess()

        global_attributes = {
            key: json_safe(value)
            for key, value in hdf.attributes().items()
        }

        result = {
            "sample_file": sample.name,
            "file_count": len(files),
            "dataset_count": len(datasets),
            "global_attributes": global_attributes,
            "datasets": output_datasets,
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

        print("Required-layer audit")
        print("")

        required = [
            "sur_refl_b01",
            "sur_refl_b02",
            "sur_refl_b07",
            "sur_refl_qc_500m",
            "sur_refl_state_500m",
            "sur_refl_day_of_year",
        ]

        missing = []

        for name in required:
            if name in datasets:
                print(f"  PASS: {name}")
            else:
                print(f"  MISSING: {name}")
                missing.append(name)

        print("")

        if missing:
            print(
                "Required layers missing: "
                + ", ".join(missing)
            )
        else:
            print(
                "All required MOD09A1 science layers found."
            )

        print("")
        print(f"Wrote: {OUT}")

    finally:
        hdf.end()


if __name__ == "__main__":
    main()


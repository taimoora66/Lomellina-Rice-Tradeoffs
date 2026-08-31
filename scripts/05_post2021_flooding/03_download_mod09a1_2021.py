from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import earthaccess


ROOT = Path(__file__).resolve().parents[2]

SHORT_NAME = "MOD09A1"
VERSION = "061"

BBOX = (
    8.045516319819253,
    45.02499838977754,
    9.541490386571809,
    45.59166503617859,
)

TARGET_TILE = "h18v04"

EXPECTED_DOYS = list(range(65, 178, 8))


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Download the 15 March-June MOD09A1.061 "
            "h18v04 composites for one year."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="MODIS year to download; default: 2021",
    )

    args = parser.parse_args()

    if not 2000 <= args.year <= 2025:
        parser.error("--year must be between 2000 and 2025.")

    return args


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def main() -> None:
    args = parse_args()
    year = args.year

    raw_dir = (
        ROOT
        / "data"
        / "raw"
        / "modis"
        / "MOD09A1.061"
        / str(year)
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = (
        ROOT
        / "outputs"
        / "diagnostics"
        / "post2021"
        / f"mod09a1_{year}_download_manifest.csv"
    )

    temporal = (
        f"{year}-03-01",
        f"{year}-06-30",
    )

    print(
        f"Authenticating with NASA Earthdata "
        f"for MOD09A1 year {year}..."
    )

    # On first run this may prompt for Earthdata Login.
    earthaccess.login(strategy="interactive", persist=True)

    print("Searching MOD09A1.061...")

    results = earthaccess.search_data(
        short_name=SHORT_NAME,
        version=VERSION,
        temporal=temporal,
        bounding_box=BBOX,
        cloud_hosted=True,
        count=-1,
    )

    # Select only h18v04 and only granules whose
    # MODIS composite start date is within March-June.
    selected = []

    for result in results:
        text = str(result)

        if TARGET_TILE not in text:
            continue

        # earthaccess result metadata contain the native
        # granule identifier, e.g. A2021065.
        # DOY 065-177 are the 15 candidate 2021 composites.
        keep = any(
            f"A{year}{doy:03d}" in text
            for doy in EXPECTED_DOYS
        )

        if keep:
            selected.append(result)

    if len(selected) != 15:
        raise AssertionError(
            "Expected 15 h18v04 March-June "
            f"start-date granules; found {len(selected)}."
        )

    print(f"Selected {len(selected)} granules.")

    print("Downloading...")

    downloaded = earthaccess.download(
        selected,
        str(raw_dir),
    )

    paths = [
        Path(p)
        for p in downloaded
        if p is not None
    ]

    if len(paths) != 15:
        raise AssertionError(
            f"Expected 15 downloaded files; found {len(paths)}."
        )

    rows = []

    for path in sorted(paths):
        if not path.exists():
            raise FileNotFoundError(path)

        rows.append(
            {
                "filename": path.name,
                "year": year,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "product": SHORT_NAME,
                "version": VERSION,
                "tile": TARGET_TILE,
            }
        )

    manifest.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with manifest.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "year",
                "size_bytes",
                "sha256",
                "product",
                "version",
                "tile",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    total_bytes = sum(
        row["size_bytes"]
        for row in rows
    )

    print("")
    print(f"MOD09A1 {year} download complete")
    print(f"  files: {len(rows)}")
    print(f"  total bytes: {total_bytes}")
    print(f"  directory: {raw_dir}")
    print(f"  manifest: {manifest}")


if __name__ == "__main__":
    main()


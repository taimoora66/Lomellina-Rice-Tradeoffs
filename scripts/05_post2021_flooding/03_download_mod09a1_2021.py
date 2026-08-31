from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import earthaccess


ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = (
    ROOT
    / "data"
    / "raw"
    / "modis"
    / "MOD09A1.061"
    / "2021"
)

RAW_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "mod09a1_2021_download_manifest.csv"
)

SHORT_NAME = "MOD09A1"
VERSION = "061"

TEMPORAL = (
    "2021-03-01",
    "2021-06-30",
)

BBOX = (
    8.045516319819253,
    45.02499838977754,
    9.541490386571809,
    45.59166503617859,
)

TARGET_TILE = "h18v04"


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
    print("Authenticating with NASA Earthdata...")

    # On first run this may prompt for Earthdata Login.
    earthaccess.login(strategy="interactive", persist=True)

    print("Searching MOD09A1.061...")

    results = earthaccess.search_data(
        short_name=SHORT_NAME,
        version=VERSION,
        temporal=TEMPORAL,
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
            f"A2021{doy:03d}" in text
            for doy in range(65, 178, 8)
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
        str(RAW_DIR),
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
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "product": SHORT_NAME,
                "version": VERSION,
                "tile": TARGET_TILE,
            }
        )

    MANIFEST.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
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
    print("MOD09A1 2021 download complete")
    print(f"  files: {len(rows)}")
    print(f"  total bytes: {total_bytes}")
    print(f"  directory: {RAW_DIR}")
    print(f"  manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
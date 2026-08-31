from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CMR_COLLECTIONS = (
    "https://cmr.earthdata.nasa.gov/search/collections.json"
)
CMR_GRANULES = (
    "https://cmr.earthdata.nasa.gov/search/granules.json"
)

SHORT_NAME = "MOD09A1"
VERSION = "061"

START = "2021-03-01T00:00:00Z"
END = "2021-06-30T23:59:59Z"

# RiceFloodIT geographic envelope.
BBOX = (
    8.045516319819253,
    45.02499838977754,
    9.541490386571809,
    45.59166503617859,
)

TARGET_TILE = "h18v04"

HEADERS = {
    "Client-Id": "lomellina-ricefloodit-bridge",
    "User-Agent": "lomellina-ricefloodit-bridge/0.1",
}


def get_json(url: str, params: dict) -> requests.Response:
    r = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r


def get_collection_concept_id() -> tuple[str, dict]:
    r = get_json(
        CMR_COLLECTIONS,
        {
            "short_name": SHORT_NAME,
            "version": VERSION,
            "page_size": 50,
        },
    )

    payload = r.json()
    entries = payload.get("feed", {}).get("entry", [])

    if not entries:
        raise RuntimeError(
            f"No CMR collection found for "
            f"{SHORT_NAME}.{VERSION}"
        )

    # Prefer LP DAAC / cloud collection when multiple records exist,
    # but retain all candidates in diagnostics.
    candidates = []

    for entry in entries:
        candidates.append(
            {
                "id": entry.get("id"),
                "short_name": entry.get("short_name"),
                "version_id": entry.get("version_id"),
                "dataset_id": entry.get("dataset_id"),
                "data_center": entry.get("data_center"),
                "title": entry.get("title"),
            }
        )

    preferred = None

    for entry in entries:
        text = " ".join(
            str(entry.get(k, ""))
            for k in (
                "data_center",
                "dataset_id",
                "title",
            )
        ).lower()

        if (
            "lpdaac" in text
            or "lp daac" in text
            or "cloud" in text
        ):
            preferred = entry
            break

    if preferred is None:
        preferred = entries[0]

    concept_id = preferred.get("id")

    if not concept_id:
        raise RuntimeError(
            "Selected MOD09A1 collection has no concept ID."
        )

    return concept_id, {
        "selected": {
            "id": preferred.get("id"),
            "short_name": preferred.get("short_name"),
            "version_id": preferred.get("version_id"),
            "dataset_id": preferred.get("dataset_id"),
            "data_center": preferred.get("data_center"),
            "title": preferred.get("title"),
        },
        "all_candidates": candidates,
    }


def extract_download_links(entry: dict) -> list[str]:
    out = []

    for link in entry.get("links", []):
        href = link.get("href")

        if not href:
            continue

        inherited = link.get("inherited", False)

        if inherited:
            continue

        rel = str(link.get("rel", "")).lower()
        title = str(link.get("title", "")).lower()

        # Keep likely data-access links.
        if (
            "data#" in rel
            or "download" in title
            or href.lower().endswith(
                (".hdf", ".h5", ".nc", ".nc4")
            )
        ):
            out.append(href)

    return sorted(set(out))


def tile_from_text(text: str) -> str | None:
    m = re.search(r"h\d{2}v\d{2}", text, re.I)

    if m:
        return m.group(0).lower()

    return None


def main() -> None:
    concept_id, collection_info = (
        get_collection_concept_id()
    )

    bbox_string = ",".join(str(x) for x in BBOX)

    r = get_json(
        CMR_GRANULES,
        {
            "collection_concept_id": concept_id,
            "temporal": f"{START},{END}",
            "bounding_box": bbox_string,
            "page_size": 2000,
            "sort_key[]": "start_date",
        },
    )

    payload = r.json()
    entries = payload.get("feed", {}).get("entry", [])

    rows = []

    for e in entries:
        title = str(e.get("title", ""))
        producer_id = str(
            e.get("producer_granule_id", "")
        )

        tile = (
            tile_from_text(producer_id)
            or tile_from_text(title)
        )

        links = extract_download_links(e)

        rows.append(
            {
                "concept_id": e.get("id"),
                "title": title,
                "producer_granule_id": producer_id,
                "tile": tile,
                "start_time": e.get("time_start"),
                "end_time": e.get("time_end"),
                "updated": e.get("updated"),
                "day_night_flag": e.get(
                    "day_night_flag"
                ),
                "download_link_count": len(links),
                "download_links": " | ".join(links),
            }
        )

    # Bounding-box search can potentially return
    # adjacent tiles. Preserve them in raw diagnostics
    # but define the target-tile subset explicitly.
    target_rows = [
        row
        for row in rows
        if row["tile"] == TARGET_TILE
    ]

    raw_json = (
        OUT_DIR / "cmr_mod09a1_2021_raw.json"
    )
    collection_json = (
        OUT_DIR / "cmr_mod09a1_collection.json"
    )
    csv_all = (
        OUT_DIR / "cmr_mod09a1_2021_granules.csv"
    )
    csv_target = (
        OUT_DIR
        / "cmr_mod09a1_2021_h18v04_granules.csv"
    )

    with raw_json.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
        )

    with collection_json.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            collection_info,
            f,
            indent=2,
        )

    fieldnames = [
        "concept_id",
        "title",
        "producer_granule_id",
        "tile",
        "start_time",
        "end_time",
        "updated",
        "day_night_flag",
        "download_link_count",
        "download_links",
    ]

    for path, data in (
        (csv_all, rows),
        (csv_target, target_rows),
    ):
        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(data)

    print("MOD09A1 CMR discovery complete")
    print(
        f"  collection concept ID: "
        f"{concept_id}"
    )
    print(
        f"  temporal search: "
        f"{START} through {END}"
    )
    print(
        f"  bounding-box granules: "
        f"{len(rows)}"
    )
    print(
        f"  {TARGET_TILE} granules: "
        f"{len(target_rows)}"
    )

    tiles = sorted(
        {
            row["tile"]
            for row in rows
            if row["tile"]
        }
    )

    print(
        "  tiles returned: "
        + ", ".join(tiles)
    )

    print("")
    print(
        f"{TARGET_TILE} acquisition starts:"
    )

    for row in target_rows:
        print(
            "  "
            + str(row["start_time"])
            + "  "
            + str(
                row["producer_granule_id"]
                or row["title"]
            )
        )

    print("")
    print(
        f"wrote {csv_target}"
    )
    print(
        "NO SATELLITE DATA WERE DOWNLOADED."
    )


if __name__ == "__main__":
    main()
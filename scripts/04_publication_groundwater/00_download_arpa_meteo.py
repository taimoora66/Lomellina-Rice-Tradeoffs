"""Reproducible ARPA Lombardia meteorological download for the publication track.

This script deliberately stores only open-source query logic in Git. Raw CSV files belong
under data/raw/arpa_meteo/ and are ignored by Git. It uses Socrata SODA2 CSV endpoints and
paginates, avoiding the 1,000-row default and silent truncation problems encountered during
exploratory acquisition.

Run from repository root:
    python scripts/04_publication_groundwater/00_download_arpa_meteo.py
"""
from __future__ import annotations
import csv
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

OUT = Path("data/raw/arpa_meteo")
OUT.mkdir(parents=True, exist_ok=True)

JOBS = [
    ("precip_2008_2010", "e7r2-7m84", 2008, 2010, [2195, 6694, 6723, 8155, 8176, 8195, 9863, 2368]),
    ("precip_2011_2020", "2kar-pnuk", 2011, 2020, [2195, 2368, 6723, 8155, 8176, 9863, 17437, 17572]),
    ("precip_2021", "pstb-pga6", 2021, 2021, [2195, 2368, 8155, 9863, 12724, 17437, 17572]),
    ("temp_2008_2010", "6eu4-4tja", 2008, 2010, [2187, 2361, 6698, 6727, 8157, 8178, 8196, 9868]),
    ("temp_2011_2020", "d4kj-kbpj", 2011, 2020, [2187, 6698, 6727, 8157, 8178, 8196, 9868, 17432, 17573]),
    ("temp_2021", "w9wd-u6jh", 2021, 2021, [2187, 6698, 8157, 8196, 9868, 12716, 17432, 17573]),
]

PAGE = 50000

def download(name: str, dataset: str, y0: int, y1: int, sensors: list[int]) -> None:
    path = OUT / f"{name}.csv"
    ids = ",".join(f"'{x}'" for x in sensors)
    where = (
        f"idsensore in ({ids}) AND "
        f"data >= '{y0}-01-01T00:00:00' AND data <= '{y1}-12-31T23:59:59'"
    )
    offset = 0
    wrote_header = False
    rows_total = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = None
        while True:
            query = urlencode({"$limit": PAGE, "$offset": offset, "$order": "idsensore,data", "$where": where})
            url = f"https://www.dati.lombardia.it/resource/{dataset}.csv?{query}"
            with urlopen(url, timeout=120) as response:  # nosec - fixed public HTTPS endpoint
                text = response.read().decode("utf-8-sig")
            chunk = list(csv.DictReader(text.splitlines()))
            if not chunk:
                break
            if writer is None:
                writer = csv.DictWriter(fh, fieldnames=chunk[0].keys())
            if not wrote_header:
                writer.writeheader(); wrote_header = True
            writer.writerows(chunk)
            rows_total += len(chunk)
            offset += len(chunk)
            print(f"{name}: {rows_total:,} rows")
            if len(chunk) < PAGE:
                break
            time.sleep(0.15)
    print(f"saved {path} ({rows_total:,} rows)")

if __name__ == "__main__":
    for job in JOBS:
        download(*job)

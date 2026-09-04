"""Design C — C2I-R Maximum Sentinel-1 Metadata Archive.

PURPOSE
-------
Extend the already-validated C1 Sentinel-1 metadata acquisition from
2015-2023 to the maximum defensible public mission record:

    2014-01-01 -> current date

The original C1 file is NOT overwritten.

SOURCE/QUERY LOGIC PRESERVED FROM C1
------------------------------------
STAC endpoint:
    https://stac.dataspace.copernicus.eu/v1/search
Collection:
    sentinel-1-grd
Study bbox:
    bounds of publication_groundwater/ricefloodit_georef.csv
    plus the same 0.10 degree margin used in C1
Pagination:
    GET-only "next" links, refusing possible non-GET truncation

THIS STAGE DOES NOT
-------------------
- read groundwater-level values;
- read irrigation-flow values;
- inspect Sentinel-1 pixels;
- tune flooding thresholds;
- fit association models;
- alter frozen publication artifacts;
- overwrite C1 Sentinel metadata.

OUTPUTS
-------
data/design_c/raw/sentinel1/
    sentinel1_grd_scene_inventory_2014_latest2026.csv

outputs/diagnostics/design_c/
    c2ir_sentinel1_maximum_archive_by_year.csv
    c2ir_sentinel1_rice_season_by_year.csv
    c2ir_sentinel1_track_support.csv
    c2ir_sentinel1_track_by_year.csv
    c2ir_sentinel1_maximum_archive_qa.json
    c2ir_sentinel1_maximum_archive_summary.txt

RUN
---
python scripts/06_design_c/12_extend_sentinel1_maximum_archive.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

RICE_GEO = (
    ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"
)
SENTINEL_DIR = ROOT / "data" / "design_c" / "raw" / "sentinel1"
OUT_DIR = ROOT / "outputs" / "diagnostics" / "design_c"

SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
COLLECTION = "sentinel-1-grd"
BBOX_MARGIN_DEG = 0.10

START_DATE = "2014-01-01T00:00:00Z"
NOW_UTC = datetime.now(timezone.utc)
END_DATE = NOW_UTC.strftime("%Y-%m-%dT%H:%M:%SZ")
CURRENT_YEAR = NOW_UTC.year

RICE_MONTHS = {4, 5, 6, 7, 8, 9}

OUT_INVENTORY = (
    SENTINEL_DIR / "sentinel1_grd_scene_inventory_2014_latest2026.csv"
)


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    req = Request(
        url,
        headers={"User-Agent": "DesignC-C2IR-maximum-sentinel-audit/1.0"},
    )
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def study_bbox() -> tuple[float, float, float, float]:
    d = pd.read_csv(RICE_GEO)

    if not {"lon", "lat"}.issubset(d.columns):
        raise AssertionError(
            "ricefloodit_georef.csv must contain lon and lat."
        )

    return (
        float(d["lon"].min()) - BBOX_MARGIN_DEG,
        float(d["lat"].min()) - BBOX_MARGIN_DEG,
        float(d["lon"].max()) + BBOX_MARGIN_DEG,
        float(d["lat"].max()) + BBOX_MARGIN_DEG,
    )


def query_stac(bbox):
    params = {
        "collections": COLLECTION,
        "bbox": ",".join(f"{x:.8f}" for x in bbox),
        "datetime": f"{START_DATE}/{END_DATE}",
        "limit": 1000,
    }

    url = STAC_SEARCH_URL + "?" + urlencode(params)

    features = []
    pages = 0

    while url:
        pages += 1
        payload = json.loads(fetch_bytes(url))
        features.extend(payload.get("features", []))

        next_url = None
        for link in payload.get("links", []):
            if link.get("rel") == "next":
                if str(link.get("method", "GET")).upper() != "GET":
                    raise RuntimeError(
                        "Non-GET STAC pagination; refusing possible truncation."
                    )
                next_url = link.get("href")
                break

        url = next_url

    rows = []

    for f in features:
        p = f.get("properties", {})
        rows.append(
            {
                "scene_id": f.get("id"),
                "datetime": p.get("datetime") or p.get("start_datetime"),
                "instrument_mode": p.get("sar:instrument_mode"),
                "polarizations": "|".join(
                    map(str, p.get("sar:polarizations", []) or [])
                ),
                "orbit_state": p.get("sat:orbit_state"),
                "relative_orbit": p.get("sat:relative_orbit"),
                "platform": p.get("platform"),
                "constellation": p.get("constellation"),
                "product_type": p.get("sar:product_type"),
                "bbox_min_lon": (
                    f.get("bbox", [None, None, None, None])[0]
                    if f.get("bbox") else None
                ),
                "bbox_min_lat": (
                    f.get("bbox", [None, None, None, None])[1]
                    if f.get("bbox") else None
                ),
                "bbox_max_lon": (
                    f.get("bbox", [None, None, None, None])[2]
                    if f.get("bbox") else None
                ),
                "bbox_max_lat": (
                    f.get("bbox", [None, None, None, None])[3]
                    if f.get("bbox") else None
                ),
            }
        )

    d = pd.DataFrame(rows)

    if len(d):
        d["datetime"] = pd.to_datetime(
            d["datetime"], errors="coerce", utc=True
        )
        d["date"] = d["datetime"].dt.date.astype(str)
        d["year"] = d["datetime"].dt.year
        d["month"] = d["datetime"].dt.month
        d["platform_derived"] = (
            d["scene_id"].astype(str).str.extract(r"^(S1[ABC])", expand=False)
        )
        d = (
            d.drop_duplicates("scene_id")
            .sort_values(["datetime", "scene_id"])
            .reset_index(drop=True)
        )

    return d, pages, len(features)


def year_status(year: int) -> str:
    if year == 2014:
        return "PARTIAL_START_YEAR"
    if year == CURRENT_YEAR:
        return "PARTIAL_CURRENT_YEAR"
    return "COMPLETE_CANDIDATE_YEAR"


def main():
    print("DESIGN C - C2I-R MAXIMUM SENTINEL-1 METADATA ARCHIVE")
    print("=" * 66)
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO Sentinel-1 pixels inspected.")
    print("NO flood threshold tuned.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.")
    print("NO C1 Sentinel file overwritten.\n")

    bbox = study_bbox()

    print(
        "Study bbox: "
        + ", ".join(f"{x:.8f}" for x in bbox)
    )
    print(f"STAC collection: {COLLECTION}")
    print(f"Query horizon: {START_DATE} -> {END_DATE}")
    print("Querying Copernicus Data Space STAC...\n")

    d, pages_n, raw_features_n = query_stac(bbox)

    if d.empty:
        raise AssertionError("STAC query returned zero Sentinel-1 scenes.")

    d.to_csv(OUT_INVENTORY, index=False)

    annual = (
        d.groupby("year")
        .agg(
            scenes_n=("scene_id", "nunique"),
            acquisition_dates_n=("date", "nunique"),
            platforms_n=("platform_derived", "nunique"),
            relative_orbits_n=("relative_orbit", "nunique"),
        )
        .reset_index()
    )
    annual["year_status"] = annual["year"].apply(year_status)
    annual.to_csv(
        OUT_DIR / "c2ir_sentinel1_maximum_archive_by_year.csv",
        index=False,
    )

    rice = d[d["month"].isin(RICE_MONTHS)].copy()

    rice_rows = []
    for year, y in rice.groupby("year"):
        dates = pd.Series(pd.to_datetime(sorted(y["date"].unique())))
        gaps = dates.diff().dt.days.dropna()

        rice_rows.append(
            {
                "year": int(year),
                "year_status": year_status(int(year)),
                "rice_season_scenes_n": int(y["scene_id"].nunique()),
                "rice_season_acquisition_dates_n": int(y["date"].nunique()),
                "rice_season_months_present_n": int(y["month"].nunique()),
                "rice_season_months": "_".join(
                    map(str, sorted(y["month"].unique()))
                ),
                "rice_season_first_date": min(y["date"]),
                "rice_season_last_date": max(y["date"]),
                "rice_season_median_gap_days": (
                    float(gaps.median()) if len(gaps) else None
                ),
                "rice_season_max_gap_days": (
                    int(gaps.max()) if len(gaps) else None
                ),
                "all_apr_sep_months_present": bool(
                    RICE_MONTHS.issubset(set(y["month"].unique()))
                ),
            }
        )

    rice_year = pd.DataFrame(rice_rows).sort_values("year")
    rice_year.to_csv(
        OUT_DIR / "c2ir_sentinel1_rice_season_by_year.csv",
        index=False,
    )

    technical = rice.loc[
        rice["instrument_mode"].eq("IW")
        & rice["polarizations"].eq("VV|VH")
    ].copy()

    track = (
        technical.groupby(["orbit_state", "relative_orbit"])
        .agg(
            scenes_n=("scene_id", "nunique"),
            dates_n=("date", "nunique"),
            years_present_n=("year", "nunique"),
            first_date=("date", "min"),
            last_date=("date", "max"),
        )
        .reset_index()
    )

    complete_candidate_years = sorted(
        annual.loc[
            annual["year_status"].eq("COMPLETE_CANDIDATE_YEAR"),
            "year"
        ].astype(int).tolist()
    )

    tb = (
        technical.groupby(["orbit_state", "relative_orbit", "year"])
        .agg(
            scenes_n=("scene_id", "nunique"),
            dates_n=("date", "nunique"),
        )
        .reset_index()
    )

    present_map = (
        tb.groupby(["orbit_state", "relative_orbit"])["year"]
        .apply(lambda s: set(map(int, s)))
        .to_dict()
    )

    track["complete_candidate_years_present_n"] = track.apply(
        lambda r: len(
            present_map.get(
                (r["orbit_state"], r["relative_orbit"]), set()
            ).intersection(complete_candidate_years)
        ),
        axis=1,
    )

    track["complete_candidate_years_total_n"] = len(
        complete_candidate_years
    )

    track["present_all_complete_candidate_years"] = (
        track["complete_candidate_years_present_n"]
        == track["complete_candidate_years_total_n"]
    )

    track.to_csv(
        OUT_DIR / "c2ir_sentinel1_track_support.csv",
        index=False,
    )

    tb.to_csv(
        OUT_DIR / "c2ir_sentinel1_track_by_year.csv",
        index=False,
    )

    full_candidate = annual[
        annual["year_status"].eq("COMPLETE_CANDIDATE_YEAR")
    ].copy()

    years_with_full_rice_months = int(
        rice_year.loc[
            rice_year["year_status"].eq("COMPLETE_CANDIDATE_YEAR"),
            "all_apr_sep_months_present",
        ].sum()
    )

    stable_tracks_n = int(
        track["present_all_complete_candidate_years"].sum()
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2IR_MAXIMUM_SENTINEL1_METADATA_ARCHIVE",
        "stac_url": STAC_SEARCH_URL,
        "collection": COLLECTION,
        "query_start": START_DATE,
        "query_end": END_DATE,
        "study_bbox": list(map(float, bbox)),
        "bbox_margin_deg": BBOX_MARGIN_DEG,
        "stac_pages_n": int(pages_n),
        "raw_features_n": int(raw_features_n),
        "unique_scenes_n": int(d["scene_id"].nunique()),
        "duplicate_scene_ids_removed_n": int(
            raw_features_n - d["scene_id"].nunique()
        ),
        "first_scene_datetime": d["datetime"].min().isoformat(),
        "last_scene_datetime": d["datetime"].max().isoformat(),
        "years_present": sorted(map(int, d["year"].dropna().unique())),
        "complete_candidate_years": complete_candidate_years,
        "complete_candidate_years_n": len(complete_candidate_years),
        "complete_candidate_years_with_all_apr_sep_months_n":
            years_with_full_rice_months,
        "iw_vvvh_rice_season_scenes_n": int(
            technical["scene_id"].nunique()
        ),
        "stable_tracks_across_all_complete_candidate_years_n":
            stable_tracks_n,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "sentinel_pixels_inspected": 0,
        "flood_thresholds_tuned": 0,
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "c1_inventory_overwritten": False,
        "interpretation_rule": (
            "2014 is retained as partial mission-start context; the current "
            "calendar year is retained as partial-current context; neither is "
            "automatically treated as a complete annual comparison year."
        ),
    }

    (OUT_DIR / "c2ir_sentinel1_maximum_archive_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C - C2I-R MAXIMUM SENTINEL-1 METADATA ARCHIVE",
        "=" * 64,
        "",
        f"STAC: {STAC_SEARCH_URL}",
        f"Collection: {COLLECTION}",
        f"Query: {START_DATE} -> {END_DATE}",
        (
            "Study bbox: "
            + ", ".join(f"{x:.8f}" for x in bbox)
        ),
        "",
        f"STAC pages retrieved: {pages_n}",
        f"Raw features returned: {raw_features_n}",
        f"Unique scenes retained: {d['scene_id'].nunique()}",
        f"First scene: {d['datetime'].min().isoformat()}",
        f"Last scene: {d['datetime'].max().isoformat()}",
        "",
        "ANNUAL SUPPORT",
        "--------------",
        annual.to_string(index=False),
        "",
        "RICE-SEASON SUPPORT",
        "-------------------",
        rice_year.to_string(index=False),
        "",
        "IW VV/VH TRACK SUPPORT",
        "----------------------",
        track.to_string(index=False),
        "",
        "INTERPRETATION",
        "--------------",
        "2014 = PARTIAL_START_YEAR.",
        f"{CURRENT_YEAR} = PARTIAL_CURRENT_YEAR.",
        (
            "All intervening observed calendar years are "
            "COMPLETE_CANDIDATE_YEAR."
        ),
        "No pixel values or groundwater outcomes were inspected.",
        "",
        "DECISION",
        "--------",
        (
            "Use this maximum archive for the next stable-track and "
            "spatial-footprint audit."
        ),
        "Do not overwrite or reinterpret the original C1 2015-2023 inventory.",
        "",
        "C2I-R STATUS: PASS",
    ]

    summary = "\n".join(lines) + "\n"

    (
        OUT_DIR / "c2ir_sentinel1_maximum_archive_summary.txt"
    ).write_text(summary, encoding="utf-8")

    print("\n" + summary)


if __name__ == "__main__":
    main()

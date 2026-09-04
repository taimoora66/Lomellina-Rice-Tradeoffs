"""Design C â€” C2P-A Sentinel-2 L2A maximum-archive and matchability audit.

Purpose
-------
Inventory the public Copernicus Data Space Ecosystem Sentinel-2 L2A catalogue
over the RiceFloodIT/Lomellina study support from 2015-01-01 through today,
then quantify spatial and temporal matchability to the frozen Sentinel-1 targets.

This is a data-opportunity audit only.

It does NOT:
- read groundwater values;
- read irrigation-flow values;
- read pre-existing flood/exposure outcomes;
- select an inundation threshold or classifier;
- fit an association model;
- alter the frozen C2J Sentinel-1 acquisition universe;
- treat scene-level cloud percentage as rice-support clear-sky coverage.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[2]
GEOREF = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"
S1_PLAN = ROOT / "outputs" / "diagnostics" / "design_c" / "c2l_target_mosaic_asset_plan.csv"

RAW_OUT = ROOT / "data" / "design_c" / "raw" / "sentinel2"
DIAG = ROOT / "outputs" / "diagnostics" / "design_c"
RAW_OUT.mkdir(parents=True, exist_ok=True)
DIAG.mkdir(parents=True, exist_ok=True)

STAC_SEARCH = "https://stac.dataspace.copernicus.eu/v1/search"
COLLECTION = "sentinel-2-l2a"
START = "2015-01-01T00:00:00Z"
END = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LIMIT = 200
TIMEOUT = 120
MAX_RETRIES = 6
USER_AGENT = "Lomellina-Design-C-Sentinel2-Audit/1.0"

INVENTORY_OUT = RAW_OUT / "sentinel2_l2a_scene_inventory_2015_latest.csv"
ANNUAL_OUT = DIAG / "c2pa_sentinel2_annual_inventory.csv"
TILE_OUT = DIAG / "c2pa_sentinel2_tile_inventory.csv"
MATCH_OUT = DIAG / "c2pa_sentinel2_s1_target_matchability.csv"
ASSET_OUT = DIAG / "c2pa_sentinel2_asset_key_inventory.csv"
QA_OUT = DIAG / "c2pa_sentinel2_archive_qa.json"
SUMMARY_OUT = DIAG / "c2pa_sentinel2_archive_summary.txt"


def request_json(method, url, *, params=None, body=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json,application/json"}
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method.upper() == "POST":
                r = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
            else:
                r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = repr(e)
            if attempt < MAX_RETRIES:
                delay = min(60, 3 * attempt)
                print(f"request attempt {attempt} failed: {last}", flush=True)
                print(f"retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"STAC request failed after {MAX_RETRIES} attempts: {last}")


def iter_stac_items(bbox):
    params = {
        "collections": COLLECTION,
        "bbox": ",".join(f"{x:.8f}" for x in bbox),
        "datetime": f"{START}/{END}",
        "limit": LIMIT,
    }
    url = STAC_SEARCH
    method = "GET"
    body = None
    page = 0

    while True:
        page += 1
        js = request_json(method, url, params=params if method == "GET" else None, body=body)
        features = js.get("features", [])
        print(f"STAC page {page}: {len(features)} items", flush=True)

        for f in features:
            yield f, page

        next_link = next((x for x in js.get("links", []) if x.get("rel") == "next"), None)
        if not next_link:
            break

        url = urljoin(url, next_link["href"])
        method = str(next_link.get("method", "GET")).upper()
        body = next_link.get("body")
        params = None

        if page > 100:
            raise RuntimeError("Aborting after >100 STAC pages; possible pagination loop.")


def first_prop(props, *names):
    for name in names:
        if name in props and props[name] is not None:
            return props[name]
    return None


def parse_tile(item_id, props):
    for key in ["grid:code", "s2:mgrs_tile", "mgrs:tile"]:
        v = props.get(key)
        if v:
            s = str(v)
            m = re.search(r"([0-9]{2}[A-Z]{3})$", s)
            return m.group(1) if m else s
    m = re.search(r"_T([0-9]{2}[A-Z]{3})_", str(item_id))
    return m.group(1) if m else None


def platform_short(props, item_id):
    p = str(props.get("platform", "")).lower()
    if "2a" in p:
        return "S2A"
    if "2b" in p:
        return "S2B"
    if "2c" in p:
        return "S2C"
    m = re.match(r"(S2[A-Z])_", str(item_id))
    return m.group(1) if m else str(props.get("platform", ""))


def has_band(keys, band):
    b = band.upper()
    ku = [k.upper() for k in keys]
    pats = [rf"^{b}$", rf"^{b}_[0-9]+M$", rf"^{b}-[0-9]+M$"]
    return any(any(re.match(p, k) for p in pats) for k in ku)


def has_scl(keys):
    return any(k.upper() == "SCL" or k.upper().startswith("SCL_") for k in keys)


def support_inside_geometry(geom, support_points):
    g = shape(geom)
    pg = prep(g)
    return int(sum(1 for p in support_points if pg.intersects(p)))


def main():
    print("DESIGN C - C2P-A SENTINEL-2 L2A MAXIMUM ARCHIVE AUDIT")
    print("=" * 76)
    print(f"Collection: {COLLECTION}")
    print(f"Period: {START} -> {END}")
    print("Catalogue inventory + footprint/date matchability only.")
    print("Scene cloud metadata is NOT treated as rice-support clear-sky coverage.")
    print("NO groundwater / irrigation-flow / prior flood outcomes.")
    print("NO inundation classifier or threshold.")
    print("NO association model.\n")

    for p in [GEOREF, S1_PLAN]:
        if not p.exists():
            raise FileNotFoundError(p)

    geo = pd.read_csv(GEOREF)
    support = (
        geo[["lon", "lat"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["lat", "lon"])
        .reset_index(drop=True)
    )
    if len(support) != 4331:
        raise AssertionError(f"Expected 4331 unique RiceFloodIT support coordinates, got {len(support)}")

    lon = support["lon"].to_numpy(float)
    lat = support["lat"].to_numpy(float)
    margin = 0.001
    bbox = [float(lon.min()-margin), float(lat.min()-margin),
            float(lon.max()+margin), float(lat.max()+margin)]
    support_points = [Point(x, y) for x, y in zip(lon, lat)]

    print(f"RiceFloodIT support points: {len(support)}")
    print("Study bbox:", ",".join(f"{x:.6f}" for x in bbox))
    print()

    records, asset_rows, seen = [], [], set()

    for item, page in iter_stac_items(bbox):
        item_id = str(item.get("id"))
        if item_id in seen:
            continue
        seen.add(item_id)

        props = item.get("properties", {}) or {}
        assets = item.get("assets", {}) or {}
        keys = sorted(str(k) for k in assets)
        ts = pd.to_datetime(first_prop(props, "datetime", "start_datetime"),
                            utc=True, errors="coerce")
        geom = item.get("geometry")
        inside_n = support_inside_geometry(geom, support_points) if geom else None
        bb = item.get("bbox") or [np.nan]*4
        if len(bb) < 4:
            bb = [np.nan]*4

        rec = {
            "item_id": item_id,
            "datetime_utc": None if pd.isna(ts) else ts.isoformat(),
            "date": None if pd.isna(ts) else ts.date().isoformat(),
            "year": None if pd.isna(ts) else int(ts.year),
            "month": None if pd.isna(ts) else int(ts.month),
            "platform": platform_short(props, item_id),
            "mgrs_tile": parse_tile(item_id, props),
            "relative_orbit": first_prop(props, "sat:relative_orbit"),
            "eo_cloud_cover_pct": first_prop(props, "eo:cloud_cover"),
            "support_points_inside_footprint_n": inside_n,
            "support_points_inside_footprint_share": None if inside_n is None else inside_n/len(support),
            "bbox_west": bb[0], "bbox_south": bb[1],
            "bbox_east": bb[2], "bbox_north": bb[3],
            "asset_keys_n": len(keys),
            "has_B02": has_band(keys, "B02"),
            "has_B03": has_band(keys, "B03"),
            "has_B04": has_band(keys, "B04"),
            "has_B08": has_band(keys, "B08"),
            "has_B11": has_band(keys, "B11"),
            "has_B12": has_band(keys, "B12"),
            "has_SCL": has_scl(keys),
            "all_core_optical_assets_present":
                all(has_band(keys, b) for b in ["B02","B03","B04","B08","B11","B12"])
                and has_scl(keys),
            "stac_page": page,
        }
        records.append(rec)

        for k, a in assets.items():
            asset_rows.append({
                "item_id": item_id,
                "year": rec["year"],
                "platform": rec["platform"],
                "mgrs_tile": rec["mgrs_tile"],
                "asset_key": str(k),
                "media_type": a.get("type"),
                "title": a.get("title"),
                "href_scheme": str(a.get("href","")).split(":",1)[0] if a.get("href") else None,
            })

    inv = pd.DataFrame(records)
    if inv.empty:
        raise RuntimeError("STAC returned zero Sentinel-2 L2A items.")

    inv["date"] = pd.to_datetime(inv["date"], errors="coerce")
    inv = inv.sort_values(["date","item_id"]).reset_index(drop=True)
    inv.to_csv(INVENTORY_OUT, index=False)
    pd.DataFrame(asset_rows).drop_duplicates().to_csv(ASSET_OUT, index=False)

    annual_rows = []
    current_year = datetime.now(timezone.utc).year
    for year, g in inv.groupby("year"):
        y = int(year)
        rice = g[g["date"].dt.month.between(3,9)]
        est = g[g["date"].dt.month.between(4,6)]
        dates = sorted(pd.to_datetime(rice["date"].dropna().unique()))
        if len(dates) >= 2:
            gaps = np.diff(np.asarray(dates, dtype="datetime64[D]")).astype(int)
            max_gap = int(np.max(gaps))
            med_gap = float(np.median(gaps))
        else:
            max_gap = np.nan
            med_gap = np.nan
        cc = pd.to_numeric(g["eo_cloud_cover_pct"], errors="coerce")
        annual_rows.append({
            "year": y,
            "year_status": "current_partial" if y == current_year else "candidate_complete",
            "items_n": int(len(g)),
            "unique_dates_n": int(g["date"].dt.date.nunique()),
            "rice_season_mar_sep_items_n": int(len(rice)),
            "rice_season_mar_sep_unique_dates_n": int(rice["date"].dt.date.nunique()),
            "establishment_apr_jun_items_n": int(len(est)),
            "establishment_apr_jun_unique_dates_n": int(est["date"].dt.date.nunique()),
            "rice_season_max_gap_days": max_gap,
            "rice_season_median_gap_days": med_gap,
            "median_catalog_cloud_pct": float(cc.median()),
            "items_cloud_le_20pct_n": int((cc <= 20).sum()),
            "items_cloud_le_50pct_n": int((cc <= 50).sum()),
            "items_full_rice_support_coverage_n":
                int((g["support_points_inside_footprint_share"] >= .999).sum()),
            "items_ge_95pct_rice_support_coverage_n":
                int((g["support_points_inside_footprint_share"] >= .95).sum()),
            "items_all_core_assets_n":
                int(g["all_core_optical_assets_present"].fillna(False).sum()),
            "platforms": "|".join(sorted(g["platform"].dropna().astype(str).unique())),
            "mgrs_tiles": "|".join(sorted(g["mgrs_tile"].dropna().astype(str).unique())),
        })

    annual = pd.DataFrame(annual_rows).sort_values("year")
    annual.to_csv(ANNUAL_OUT, index=False)

    tile = (
        inv.groupby("mgrs_tile", dropna=False)
        .agg(
            items_n=("item_id","count"),
            first_date=("date","min"),
            last_date=("date","max"),
            years_n=("year","nunique"),
            support_coverage_median=("support_points_inside_footprint_share","median"),
            support_coverage_max=("support_points_inside_footprint_share","max"),
            catalog_cloud_median_pct=("eo_cloud_cover_pct","median"),
        )
        .reset_index()
    )
    tile.to_csv(TILE_OUT, index=False)

    p1 = pd.read_csv(S1_PLAN)
    target_keys = ["anchor_year","season_phase","selected_date","orbit_state","relative_orbit"]
    targets = p1[target_keys].drop_duplicates().copy()
    targets["selected_date"] = pd.to_datetime(targets["selected_date"])

    match_rows = []
    for r in targets.itertuples(index=False):
        t = pd.Timestamp(r.selected_date)
        z = inv[inv["support_points_inside_footprint_n"].fillna(0) > 0].copy()
        z["signed_day_offset"] = (z["date"] - t).dt.days
        z["abs_day_offset"] = z["signed_day_offset"].abs()

        nearest = None
        if not z.empty:
            nearest = z.sort_values(
                ["abs_day_offset","eo_cloud_cover_pct","support_points_inside_footprint_share"],
                ascending=[True,True,False], na_position="last"
            ).iloc[0]

        for window in [1,3,5,7,10]:
            zw = z[z["abs_day_offset"] <= window]
            cc = pd.to_numeric(zw["eo_cloud_cover_pct"], errors="coerce")
            match_rows.append({
                "anchor_year": int(r.anchor_year),
                "season_phase": str(r.season_phase),
                "s1_selected_date": t.date().isoformat(),
                "s1_orbit_state": str(r.orbit_state),
                "s1_relative_orbit": int(r.relative_orbit),
                "window_days": window,
                "s2_items_n": int(len(zw)),
                "s2_unique_dates_n": int(zw["date"].dt.date.nunique()),
                "s2_items_cloud_le_20pct_n": int((cc <= 20).sum()),
                "s2_items_ge_95pct_support_coverage_n":
                    int((zw["support_points_inside_footprint_share"] >= .95).sum()),
                "s2_items_all_core_assets_n":
                    int(zw["all_core_optical_assets_present"].fillna(False).sum()),
                "nearest_s2_item_id": None if nearest is None else nearest["item_id"],
                "nearest_s2_date": None if nearest is None else nearest["date"].date().isoformat(),
                "nearest_abs_day_offset": None if nearest is None else int(nearest["abs_day_offset"]),
                "nearest_signed_day_offset": None if nearest is None else int(nearest["signed_day_offset"]),
                "nearest_catalog_cloud_pct": None if nearest is None else nearest["eo_cloud_cover_pct"],
                "nearest_support_coverage_share": None if nearest is None else nearest["support_points_inside_footprint_share"],
                "nearest_mgrs_tile": None if nearest is None else nearest["mgrs_tile"],
                "nearest_platform": None if nearest is None else nearest["platform"],
            })

    match = pd.DataFrame(match_rows)
    match.to_csv(MATCH_OUT, index=False)

    years_found = sorted(int(y) for y in inv["year"].dropna().unique())
    expected_years = list(range(2015, current_year+1))
    missing_years = sorted(set(expected_years)-set(years_found))
    support_known_share = float(inv["support_points_inside_footprint_n"].notna().mean())
    core_share = float(inv["all_core_optical_assets_present"].fillna(False).mean())

    target_avail = (
        match.assign(any_item=match["s2_items_n"] > 0)
        .groupby("window_days")["any_item"].sum().astype(int).to_dict()
    )

    status = "PASS" if len(inv) > 0 and not missing_years and support_known_share == 1.0 else "FAIL"

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2PA_SENTINEL2_L2A_MAXIMUM_ARCHIVE_AUDIT",
        "stac_collection": COLLECTION,
        "stac_search_endpoint": STAC_SEARCH,
        "period_start": START,
        "period_end": END,
        "ricefloodit_support_points_n": int(len(support)),
        "study_bbox_wgs84": bbox,
        "unique_stac_items_n": int(len(inv)),
        "first_item_date": inv["date"].min().date().isoformat(),
        "last_item_date": inv["date"].max().date().isoformat(),
        "years_found": years_found,
        "missing_years": missing_years,
        "mgrs_tiles_n": int(inv["mgrs_tile"].nunique(dropna=True)),
        "platforms": sorted(inv["platform"].dropna().astype(str).unique().tolist()),
        "scene_footprint_support_evaluable_share": support_known_share,
        "all_core_optical_assets_present_share": core_share,
        "s1_frozen_target_dates_n": int(len(targets)),
        "s1_targets_with_any_s2_item_by_window_days":
            {str(k): int(v) for k,v in target_avail.items()},
        "scene_cloud_percentage_used_as_rice_support_clear_sky_truth": False,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "preexisting_flood_exposure_values_read": False,
        "inundation_threshold_selected": False,
        "inundation_classifier_fitted": False,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "next_stage": "Audit actual rice-support clear-sky usability from Sentinel-2 SCL and bands."
    }
    QA_OUT.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2P-A SENTINEL-2 L2A MAXIMUM ARCHIVE AUDIT",
        "="*76,
        "",
        f"STAC collection: {COLLECTION}",
        f"Period: {START} -> {END}",
        f"RiceFloodIT support coordinates: {len(support)}",
        f"Unique Sentinel-2 L2A items: {len(inv)}",
        f"First item: {inv['date'].min().date().isoformat()}",
        f"Last item: {inv['date'].max().date().isoformat()}",
        f"Years found: {','.join(map(str,years_found))}",
        f"Missing years: {','.join(map(str,missing_years)) if missing_years else 'NONE'}",
        f"MGRS tiles: {inv['mgrs_tile'].nunique(dropna=True)}",
        f"Platforms: {'|'.join(sorted(inv['platform'].dropna().astype(str).unique()))}",
        f"All-core-optical-asset item share: {core_share:.6f}",
        "",
        "SENTINEL-1 TARGET MATCHABILITY",
        "------------------------------",
    ]
    for w in sorted(target_avail):
        lines.append(
            f"Frozen S1 targets with >=1 S2 catalogue item within +/-{w} d: "
            f"{target_avail[w]}/{len(targets)}"
        )
    lines += [
        "",
        "IMPORTANT LIMIT",
        "---------------",
        "eo:cloud_cover is catalogue metadata only.",
        "It is NOT clear-sky coverage over rice-support pixels.",
        "Actual optical usability requires SCL/band sampling in the next stage.",
        "",
        "FIREWALL",
        "--------",
        "No groundwater values read.",
        "No irrigation-flow values read.",
        "No pre-existing flooding/exposure outcomes read.",
        "No inundation threshold selected.",
        "No inundation classifier fitted.",
        "No association model fitted.",
        "C2J frozen Sentinel-1 acquisition universe unchanged.",
        "",
        f"C2P-A STATUS: {status}",
    ]
    summary = "\n".join(lines) + "\n"
    SUMMARY_OUT.write_text(summary, encoding="utf-8")
    print("\n"+summary)
    print("\nANNUAL INVENTORY")
    print("----------------")
    pd.set_option("display.width", 240)
    print(annual.to_string(index=False))

    if status != "PASS":
        raise RuntimeError("C2P-A failed archive audit gates; inspect QA outputs.")


if __name__ == "__main__":
    main()


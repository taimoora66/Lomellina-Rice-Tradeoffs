"""Design C — C2K Sentinel-1 Frozen Validation Asset Resolution.

PURPOSE
-------
Resolve exact STAC item metadata and assets for the C2J-frozen SAR
validation manifest, without reading SAR pixel values.

This stage answers:
- Which platform (S1A/S1B/S1C) produced each frozen target?
- Which STAC assets are available for each scene?
- Are multiple same-date scene IDs true adjacent frames, duplicate/alternate
  representations, or overlapping frames?
- What exact assets should the next measurement-validation stage read?

FIREWALL
--------
This stage DOES NOT:
- open/read raster pixel values;
- calculate VV/VH statistics;
- classify flooding;
- read groundwater levels;
- read irrigation discharge;
- fit any association model;
- alter the C2J frozen universe.

INPUT
-----
outputs/diagnostics/design_c/c2j_sar_validation_manifest.csv

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2k_validation_item_metadata.csv
    c2k_validation_asset_inventory.csv
    c2k_validation_mosaic_qa.csv
    c2k_validation_asset_resolution_qa.json
    c2k_validation_asset_resolution_summary.txt

RUN
---
python scripts/06_design_c/16_resolve_frozen_sentinel1_assets.py
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

MANIFEST = OUT / "c2j_sar_validation_manifest.csv"

STAC_ROOT = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-1-grd"


def fetch_json(url: str, timeout: int = 120) -> dict:
    req = Request(
        url,
        headers={"User-Agent": "DesignC-C2K-frozen-sentinel-assets/1.0"},
    )
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def item_url(scene_id: str) -> str:
    return (
        f"{STAC_ROOT}/collections/{COLLECTION}/items/"
        + quote(scene_id, safe="")
    )


def bbox_overlap_fraction(a, b):
    """Intersection area / smaller bbox area in lon-lat planar degrees.
    Metadata QA only; not a physical area calculation.
    """
    if not a or not b or len(a) < 4 or len(b) < 4:
        return None

    ax1, ay1, ax2, ay2 = map(float, a[:4])
    bx1, by1, bx2, by2 = map(float, b[:4])

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih

    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ba = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    denom = min(aa, ba)
    return inter / denom if denom > 0 else None


def main():
    print("DESIGN C - C2K FROZEN SENTINEL-1 ASSET RESOLUTION")
    print("=" * 64)
    print("NO SAR raster pixels read.")
    print("NO VV/VH statistics calculated.")
    print("NO flooding values read.")
    print("NO groundwater-level values read.")
    print("NO irrigation-flow values read.")
    print("NO association model fitted.")
    print("NO C2J frozen rule modified.\n")

    if not MANIFEST.exists():
        raise FileNotFoundError(
            f"Missing C2J manifest: {MANIFEST}"
        )

    m = pd.read_csv(MANIFEST)

    required = {
        "anchor_year", "season_phase", "orbit_state", "relative_orbit",
        "selected_date", "selection_status", "scene_ids"
    }
    missing = required - set(m.columns)
    if missing:
        raise AssertionError(
            f"C2J manifest missing required columns: {sorted(missing)}"
        )

    m = m[m["selection_status"].eq("SELECTED")].copy()

    item_rows = []
    asset_rows = []

    unique_scene_ids = sorted({
        sid
        for x in m["scene_ids"].dropna().astype(str)
        for sid in x.split("|")
        if sid.strip()
    })

    print(f"Frozen validation targets: {len(m)}")
    print(f"Unique STAC scene IDs to resolve: {len(unique_scene_ids)}\n")

    item_cache = {}

    for i, sid in enumerate(unique_scene_ids, 1):
        url = item_url(sid)
        try:
            item = fetch_json(url)
            err = None
        except Exception as e:
            item = {}
            err = repr(e)

        item_cache[sid] = item

        p = item.get("properties", {}) if item else {}
        bbox = item.get("bbox") if item else None
        assets = item.get("assets", {}) if item else {}

        scene_platform = (
            p.get("platform")
            or p.get("constellation")
            or sid[:3]
        )

        item_rows.append({
            "scene_id": sid,
            "resolve_status": "OK" if err is None else "ERROR",
            "resolve_error": err,
            "platform": scene_platform,
            "datetime": p.get("datetime") or p.get("start_datetime"),
            "end_datetime": p.get("end_datetime"),
            "instrument_mode": p.get("sar:instrument_mode"),
            "polarizations": "|".join(
                map(str, p.get("sar:polarizations", []) or [])
            ),
            "orbit_state": p.get("sat:orbit_state"),
            "relative_orbit": p.get("sat:relative_orbit"),
            "absolute_orbit": p.get("sat:absolute_orbit"),
            "product_type": p.get("sar:product_type"),
            "processing_level": p.get("processing:level"),
            "bbox": json.dumps(bbox) if bbox is not None else None,
            "asset_count": len(assets),
            "stac_item_url": url,
        })

        for key, a in assets.items():
            href = a.get("href")
            roles = a.get("roles", []) or []
            asset_rows.append({
                "scene_id": sid,
                "asset_key": key,
                "title": a.get("title"),
                "media_type": a.get("type"),
                "roles": "|".join(map(str, roles)),
                "href": href,
                "is_data_role": "data" in roles,
                "looks_like_tiff": bool(
                    href and str(href).lower().split("?")[0].endswith(
                        (".tif", ".tiff")
                    )
                ),
            })

        print(f"[{i:02d}/{len(unique_scene_ids):02d}] {sid}: "
              f"{'OK' if err is None else 'ERROR'}; assets={len(assets)}")

    items = pd.DataFrame(item_rows)
    assets = pd.DataFrame(asset_rows)

    items.to_csv(
        OUT / "c2k_validation_item_metadata.csv",
        index=False,
    )
    assets.to_csv(
        OUT / "c2k_validation_asset_inventory.csv",
        index=False,
    )

    # Build target-level mosaic QA from exact frozen manifest.
    mosaic_rows = []

    for _, r in m.iterrows():
        ids = [x for x in str(r["scene_ids"]).split("|") if x]
        subset = items[items["scene_id"].isin(ids)].copy()

        bboxes = {}
        for sid in ids:
            it = item_cache.get(sid, {})
            bboxes[sid] = it.get("bbox") if it else None

        pair_overlaps = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                ov = bbox_overlap_fraction(
                    bboxes.get(ids[i]),
                    bboxes.get(ids[j]),
                )
                pair_overlaps.append({
                    "a": ids[i],
                    "b": ids[j],
                    "overlap_fraction_of_smaller_bbox": ov,
                })

        overlap_vals = [
            x["overlap_fraction_of_smaller_bbox"]
            for x in pair_overlaps
            if x["overlap_fraction_of_smaller_bbox"] is not None
        ]

        platforms = sorted(
            subset["platform"].dropna().astype(str).unique()
        )
        datetimes = sorted(
            subset["datetime"].dropna().astype(str).unique()
        )

        duplicate_exact_bbox_pairs = 0
        near_duplicate_bbox_pairs = 0

        for x in pair_overlaps:
            ov = x["overlap_fraction_of_smaller_bbox"]
            if ov is not None and ov >= 0.999999:
                duplicate_exact_bbox_pairs += 1
            elif ov is not None and ov >= 0.95:
                near_duplicate_bbox_pairs += 1

        mosaic_rows.append({
            "anchor_year": int(r["anchor_year"]),
            "season_phase": r["season_phase"],
            "selected_date": r["selected_date"],
            "orbit_state": r["orbit_state"],
            "relative_orbit": int(r["relative_orbit"]),
            "scene_ids_n": len(ids),
            "resolved_scene_ids_n": int(
                subset["resolve_status"].eq("OK").sum()
            ),
            "platforms": "|".join(platforms),
            "platforms_n": len(platforms),
            "unique_item_datetimes_n": len(datetimes),
            "item_datetimes": "|".join(datetimes),
            "pairwise_bbox_comparisons_n": len(pair_overlaps),
            "exact_or_effectively_exact_bbox_overlap_pairs_n":
                duplicate_exact_bbox_pairs,
            "near_duplicate_bbox_overlap_pairs_n":
                near_duplicate_bbox_pairs,
            "max_pairwise_overlap_fraction_of_smaller_bbox": (
                max(overlap_vals) if overlap_vals else None
            ),
            "min_pairwise_overlap_fraction_of_smaller_bbox": (
                min(overlap_vals) if overlap_vals else None
            ),
            "requires_multiple_scene_mosaic": len(ids) > 1,
        })

    mosaic = pd.DataFrame(mosaic_rows)
    mosaic.to_csv(
        OUT / "c2k_validation_mosaic_qa.csv",
        index=False,
    )

    unresolved_n = int(
        (items["resolve_status"] != "OK").sum()
    )

    data_assets_n = (
        int(assets["is_data_role"].sum())
        if len(assets) and "is_data_role" in assets.columns
        else 0
    )

    tiff_assets_n = (
        int(assets["looks_like_tiff"].sum())
        if len(assets) and "looks_like_tiff" in assets.columns
        else 0
    )

    platforms = sorted(
        items["platform"].dropna().astype(str).unique()
    )

    qa = {
        "status": "PASS" if unresolved_n == 0 else "PASS_WITH_LIMITATIONS",
        "stage": "DESIGN_C_C2K_FROZEN_SENTINEL_ASSET_RESOLUTION",
        "frozen_validation_targets_n": int(len(m)),
        "unique_scene_ids_n": int(len(unique_scene_ids)),
        "resolved_scene_ids_n": int(
            items["resolve_status"].eq("OK").sum()
        ),
        "unresolved_scene_ids_n": unresolved_n,
        "platforms_present": platforms,
        "asset_rows_n": int(len(assets)),
        "data_role_assets_n": data_assets_n,
        "tiff_like_assets_n": tiff_assets_n,
        "targets_requiring_multi_scene_mosaic_n": int(
            mosaic["requires_multiple_scene_mosaic"].sum()
        ),
        "targets_with_effectively_duplicate_bbox_pairs_n": int(
            (
                mosaic[
                    "exact_or_effectively_exact_bbox_overlap_pairs_n"
                ] > 0
            ).sum()
        ),
        "sar_raster_pixels_read": 0,
        "vv_vh_statistics_calculated": 0,
        "flooding_values_read": 0,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "next_stage": (
            "Canonicalize exact data assets for each frozen target, then "
            "read only the required spatial windows for independent SAR "
            "measurement validation."
        ),
    }

    (OUT / "c2k_validation_asset_resolution_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C - C2K FROZEN SENTINEL-1 ASSET RESOLUTION",
        "=" * 62,
        "",
        f"Frozen validation targets: {len(m)}",
        f"Unique scene IDs: {len(unique_scene_ids)}",
        f"Resolved scene IDs: {len(unique_scene_ids) - unresolved_n}",
        f"Unresolved scene IDs: {unresolved_n}",
        f"Platforms present: {'|'.join(platforms)}",
        f"Total STAC asset rows: {len(assets)}",
        f"Data-role assets: {data_assets_n}",
        f"TIFF-like assets: {tiff_assets_n}",
        "",
        "MOSAIC QA",
        "---------",
        mosaic.to_string(index=False),
        "",
        "ITEM METADATA",
        "-------------",
        items.to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "No raster pixels were opened/read.",
        "No VV/VH values were calculated.",
        "No flooding, groundwater, or irrigation outcomes were read.",
        "C2J primary universe was not modified.",
        "",
        f"C2K STATUS: {qa['status']}",
    ]

    txt = "\n".join(lines) + "\n"
    (OUT / "c2k_validation_asset_resolution_summary.txt").write_text(
        txt, encoding="utf-8"
    )

    print("\n" + txt)


if __name__ == "__main__":
    main()

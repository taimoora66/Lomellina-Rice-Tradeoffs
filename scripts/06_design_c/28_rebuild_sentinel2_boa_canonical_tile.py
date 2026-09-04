"""Design C — C2P-C2 Sentinel-2 BOA canonical-tile rebuild.

Purpose
-------
Extract radiometrically comparable Sentinel-2 L2A BOA reflectance at the
4,331 RiceFloodIT support coordinates for the same 14 outcome-blind
Sentinel-1-matched optical target dates used in C2P-B.

This stage:
- reads B02_20m, B03_20m, B04_20m, B8A_20m, B11_20m, B12_20m;
- uses STAC-provided projection metadata for exact 20 m georeferencing;
- applies the frozen PB05.xx Collection-1 radiometric rule:
      DN == 0 -> nodata
      BOA reflectance = (DN - 1000) / 10000
- carries forward SCL and the conservative confirmed-usable rule SCL in {4,5,6};
- preserves partial-swath non-observation separately from raster nodata;
- preserves overlapping-tile disagreement/ambiguity rather than silently
  selecting a value;
- computes diagnostic optical indices only for confirmed-usable pixels:
      NDVI  = (B8A - B04) / (B8A + B04)
      NDWI  = (B03 - B8A) / (B03 + B8A)
      MNDWI = (B03 - B11) / (B03 + B11)
      LSWI  = (B8A - B11) / (B8A + B11)

This stage does NOT:
- read groundwater;
- read irrigation-flow observations;
- read pre-existing flooding/exposure outcomes;
- select an inundation threshold;
- fit an inundation classifier;
- use the optical indices to optimize against groundwater;
- fit any association model;
- modify the frozen Sentinel-1 acquisition universe.

Inputs
------
data/processed/publication_groundwater/ricefloodit_georef.csv
data/design_c/raw/sentinel2/sentinel2_l2a_scene_inventory_2015_latest.csv
outputs/diagnostics/design_c/c2pa_sentinel2_s1_target_matchability.csv
outputs/diagnostics/design_c/c2pb_scl_point_samples.csv

Outputs
-------
outputs/diagnostics/design_c/
    c2pc_sentinel2_asset_technical_qa.csv
    c2pc_sentinel2_boa_point_samples.csv
    c2pc_sentinel2_target_reflectance_summary.csv
    c2pc_sentinel2_index_summary.csv
    c2pc_sentinel2_boa_qa.json
    c2pc_sentinel2_boa_summary.txt

Run from repository root
------------------------
python -u scripts/06_design_c/28_rebuild_sentinel2_boa_canonical_tile.py
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import rasterio
from affine import Affine
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]

GEOREF = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"
S2_INV = ROOT / "data" / "design_c" / "raw" / "sentinel2" / "sentinel2_l2a_scene_inventory_2015_latest.csv"
MATCH = ROOT / "outputs" / "diagnostics" / "design_c" / "c2pa_sentinel2_s1_target_matchability.csv"
SCL_POINTS = ROOT / "outputs" / "diagnostics" / "design_c" / "c2pb_scl_point_samples.csv"

DIAG = ROOT / "outputs" / "diagnostics" / "design_c"
DIAG.mkdir(parents=True, exist_ok=True)

ASSET_QA_OUT = DIAG / "c2pc2_sentinel2_asset_technical_qa.csv"
POINT_OUT = DIAG / "c2pc2_sentinel2_boa_point_samples.csv"
TARGET_OUT = DIAG / "c2pc2_sentinel2_target_reflectance_summary.csv"
INDEX_OUT = DIAG / "c2pc2_sentinel2_index_summary.csv"
QA_OUT = DIAG / "c2pc2_sentinel2_boa_qa.json"
SUMMARY_OUT = DIAG / "c2pc2_sentinel2_boa_summary.txt"

STAC_ITEM = (
    "https://stac.dataspace.copernicus.eu/v1/"
    "collections/sentinel-2-l2a/items/{item_id}"
)

EXPECTED_SUPPORT = 4331
TIMEOUT = 120
MAX_RETRIES = 6
USER_AGENT = "Lomellina-Design-C-C2PC-BOA/1.0"

BANDS = ["B02_20m", "B03_20m", "B04_20m", "B8A_20m", "B11_20m", "B12_20m"]
SHORT = {
    "B02_20m": "B02",
    "B03_20m": "B03",
    "B04_20m": "B04",
    "B8A_20m": "B8A",
    "B11_20m": "B11",
    "B12_20m": "B12",
}

# Frozen radiometric rule for PB05.xx / Collection-1 L2A products.
QUANTIFICATION = 10000.0
BOA_ADD_OFFSET = -1000.0
NODATA_DN = 0

# Conservative SCL interpretation frozen after C2P-B semantic correction.
CONFIRMED_USABLE_SCL = {4, 5, 6}
OBSCURED_SCL = {2, 3, 8, 9, 10, 11}
INVALID_SCL = {0, 1}
UNCLASSIFIED_SCL = {7}

# Overlap reconciliation tolerance. Same physical pixel observed in overlapping
# tiles should normally agree after quantization. We preserve disagreement.
REFLECTANCE_ABS_TOL = 1e-6


def get_json(url: str) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = repr(exc)
            if attempt < MAX_RETRIES:
                delay = min(30, attempt * 3)
                print(f"  metadata attempt {attempt} failed: {last}", flush=True)
                print(f"  retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Could not retrieve STAC item after retries: {last}")


def open_raster_retry(href: str):
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return rasterio.open(href), attempt
        except Exception as exc:
            last = repr(exc)
            if attempt < MAX_RETRIES:
                delay = min(30, attempt * 3)
                print(f"      raster open attempt {attempt} failed: {last}", flush=True)
                print(f"      retrying in {delay}s...", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Could not open raster after retries: {last}")


def parse_stac_transform(asset: dict) -> Affine:
    tr = asset.get("proj:transform")
    if tr is None or len(tr) < 6:
        raise AssertionError("STAC asset missing proj:transform.")
    return Affine(float(tr[0]), float(tr[1]), float(tr[2]),
                  float(tr[3]), float(tr[4]), float(tr[5]))


def get_asset_crs(asset: dict) -> str:
    code = asset.get("proj:code")
    if code:
        s = str(code)
        if s.upper().startswith("EPSG:"):
            return s.upper()
        if s.isdigit():
            return f"EPSG:{s}"
    epsg = asset.get("proj:epsg")
    if epsg is not None:
        return f"EPSG:{int(epsg)}"
    raise AssertionError("STAC asset missing projection code.")


def validate_asset_geometry(src, asset: dict, item_id: str, asset_key: str):
    expected_crs = get_asset_crs(asset)
    expected_transform = parse_stac_transform(asset)
    expected_shape = asset.get("proj:shape")

    if expected_shape is None or len(expected_shape) != 2:
        raise AssertionError(f"{item_id}/{asset_key}: missing proj:shape")

    expected_h = int(expected_shape[0])
    expected_w = int(expected_shape[1])

    if src.width != expected_w or src.height != expected_h:
        raise AssertionError(
            f"{item_id}/{asset_key}: raster shape {src.width}x{src.height} "
            f"!= STAC {expected_w}x{expected_h}"
        )

    # Some CDSE JP2 reads expose no CRS; STAC projection extension is used as
    # authoritative geometry. If raster metadata is present, require agreement.
    if src.crs is not None and str(src.crs).upper() != expected_crs.upper():
        raise AssertionError(
            f"{item_id}/{asset_key}: raster CRS {src.crs} != STAC {expected_crs}"
        )

    # If raster transform is meaningful, require close agreement with STAC.
    if src.transform is not None:
        vals_src = np.array(tuple(src.transform)[:6], dtype=float)
        vals_exp = np.array(tuple(expected_transform)[:6], dtype=float)

        identity_like = np.allclose(
            vals_src,
            np.array([1, 0, 0, 0, 1, 0], dtype=float),
            atol=1e-12,
            rtol=0,
        )
        if identity_like:
            raise AssertionError(
                f"{item_id}/{asset_key}: raster transform is identity-like; "
                "refuse sampling because georeferencing is not usable."
            )
        if not np.allclose(vals_src, vals_exp, atol=1e-8, rtol=0):
            raise AssertionError(
                f"{item_id}/{asset_key}: raster transform differs from STAC."
            )

    return expected_crs, expected_transform, expected_w, expected_h


def sample_band(item_json: dict, asset_key: str, support: pd.DataFrame):
    item_id = item_json["id"]
    assets = item_json.get("assets", {})
    if asset_key not in assets:
        raise AssertionError(f"{item_id}: required asset {asset_key} missing.")

    asset = assets[asset_key]
    href = asset["href"]

    src, attempts = open_raster_retry(href)
    try:
        crs, transform, width, height = validate_asset_geometry(
            src, asset, item_id, asset_key
        )

        tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        xs, ys = tf.transform(
            support["lon"].to_numpy(float),
            support["lat"].to_numpy(float),
        )

        # Use STAC affine to define spatial support, independent of missing JP2 CRS.
        inv = ~transform
        cols, rows = inv * (np.asarray(xs), np.asarray(ys))

        inside = (
            (cols >= 0)
            & (cols < width)
            & (rows >= 0)
            & (rows < height)
        )

        idx = np.where(inside)[0]
        dn = np.full(len(support), np.nan, dtype=float)
        edge_margin_px = np.full(len(support), np.nan, dtype=float)
        if len(idx):
            edge_margin_px[idx] = np.minimum.reduce([
                cols[idx],
                rows[idx],
                (width - 1) - cols[idx],
                (height - 1) - rows[idx],
            ])

        if len(idx):
            coords = [(float(xs[i]), float(ys[i])) for i in idx]
            vals = np.fromiter(
                (float(v[0]) for v in src.sample(coords, indexes=1)),
                dtype=float,
                count=len(coords),
            )
            dn[idx] = vals

        reflectance = np.full(len(support), np.nan, dtype=float)
        valid_dn = np.isfinite(dn) & (dn != NODATA_DN)
        reflectance[valid_dn] = (
            dn[valid_dn] + BOA_ADD_OFFSET
        ) / QUANTIFICATION

        qa = {
            "item_id": item_id,
            "asset_key": asset_key,
            "href": href,
            "open_attempts": attempts,
            "stac_crs": crs,
            "stac_width": width,
            "stac_height": height,
            "raster_driver": src.driver,
            "raster_dtype": str(src.dtypes[0]),
            "raster_crs_original": None if src.crs is None else str(src.crs),
            "stac_nodata": asset.get("nodata"),
            "support_inside_n": int(inside.sum()),
            "sampled_dn_n": int(np.isfinite(dn).sum()),
            "nodata_dn0_n": int(np.sum(np.isfinite(dn) & (dn == NODATA_DN))),
            "valid_reflectance_n": int(np.isfinite(reflectance).sum()),
            "reflectance_min": (
                float(np.nanmin(reflectance)) if np.isfinite(reflectance).any() else np.nan
            ),
            "reflectance_max": (
                float(np.nanmax(reflectance)) if np.isfinite(reflectance).any() else np.nan
            ),
            "status": "PASS",
        }
        return dn, reflectance, edge_margin_px, qa
    finally:
        src.close()


def target_key(row) -> str:
    return (
        f"{int(row.anchor_year)}|{row.season_phase}|"
        f"{row.s1_selected_date}|{row.s1_orbit_state}|"
        f"{int(row.s1_relative_orbit)}"
    )



def sample_scl(item_json: dict, support: pd.DataFrame):
    item_id = item_json["id"]
    asset_key = "SCL_20m"
    asset = item_json.get("assets", {}).get(asset_key)
    if asset is None:
        raise AssertionError(f"{item_id}: required asset {asset_key} missing.")

    src, attempts = open_raster_retry(asset["href"])
    try:
        crs, transform, width, height = validate_asset_geometry(
            src, asset, item_id, asset_key
        )
        tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        xs, ys = tf.transform(
            support["lon"].to_numpy(float),
            support["lat"].to_numpy(float),
        )
        inv = ~transform
        cols, rows = inv * (np.asarray(xs), np.asarray(ys))
        inside = (
            (cols >= 0) & (cols < width) &
            (rows >= 0) & (rows < height)
        )

        idx = np.where(inside)[0]
        scl = np.full(len(support), np.nan, dtype=float)
        margin = np.full(len(support), np.nan, dtype=float)

        if len(idx):
            margin[idx] = np.minimum.reduce([
                cols[idx],
                rows[idx],
                (width - 1) - cols[idx],
                (height - 1) - rows[idx],
            ])
            coords = [(float(xs[i]), float(ys[i])) for i in idx]
            vals = np.fromiter(
                (float(v[0]) for v in src.sample(coords, indexes=1)),
                dtype=float,
                count=len(coords),
            )
            scl[idx] = vals

        qa = {
            "item_id": item_id,
            "asset_key": asset_key,
            "href": asset["href"],
            "open_attempts": attempts,
            "stac_crs": crs,
            "stac_width": width,
            "stac_height": height,
            "raster_driver": src.driver,
            "raster_dtype": str(src.dtypes[0]),
            "raster_crs_original": None if src.crs is None else str(src.crs),
            "stac_nodata": asset.get("nodata"),
            "support_inside_n": int(inside.sum()),
            "sampled_dn_n": int(np.isfinite(scl).sum()),
            "nodata_dn0_n": int(np.sum(np.isfinite(scl) & (scl == 0))),
            "valid_reflectance_n": np.nan,
            "reflectance_min": np.nan,
            "reflectance_max": np.nan,
            "status": "PASS",
        }
        return scl, margin, qa
    finally:
        src.close()


def descriptive_spread(values):
    vals = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(vals) < 2:
        return 0 if len(vals) == 1 else 0, 0.0
    return int(len(vals)), float(np.nanmax(vals) - np.nanmin(vals))


def safe_index_nonnegative(a, b):
    """Normalized difference valid only with finite, nonnegative inputs."""
    if not (np.isfinite(a) and np.isfinite(b)):
        return np.nan, False
    if a < 0 or b < 0:
        return np.nan, False
    den = a + b
    if not np.isfinite(den) or den <= 1e-6:
        return np.nan, False
    return float((a - b) / den), True


def choose_owner(items, i):
    """Geometry-only canonical tile assignment.

    Among all tiles covering the support coordinate, choose the item for which
    the coordinate lies deepest inside the tile (maximum pixel distance from
    the nearest tile edge). Ties are resolved lexicographically by item_id.
    No reflectance, SCL class, flooding data, or groundwater data enters this
    choice.
    """
    candidates = []
    for item in items:
        m = item["margin"][i]
        if np.isfinite(m):
            candidates.append((float(m), str(item["item_id"]), item))
    if not candidates:
        return None, 0
    candidates.sort(key=lambda z: (-z[0], z[1]))
    return candidates[0][2], len(candidates)

def main():
    print("DESIGN C - C2P-C2 SENTINEL-2 BOA CANONICAL-TILE REBUILD")
    print("=" * 78)
    print("14 outcome-blind S1-matched optical targets.")
    print("4,331 RiceFloodIT support coordinates.")
    print("PB05.xx rule: DN==0 nodata; BOA=(DN-1000)/10000.")
    print("Bands: B02 B03 B04 B8A B11 B12 at 20 m.")
    print("Canonical tile owner = maximum distance from tile edge (geometry only).")
    print("Indices require nonnegative reflectance inputs.")
    print("No inundation threshold. No groundwater. No association model.\n")

    for p in (GEOREF, S2_INV, MATCH, SCL_POINTS):
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
    if len(support) != EXPECTED_SUPPORT:
        raise AssertionError(
            f"Expected {EXPECTED_SUPPORT} unique support points; found {len(support)}"
        )
    support["support_id"] = np.arange(len(support), dtype=int)

    inv = pd.read_csv(S2_INV)
    inv["date"] = pd.to_datetime(inv["date"], errors="coerce").dt.date.astype(str)

    mt = pd.read_csv(MATCH)
    mt = mt[
        (pd.to_numeric(mt["window_days"], errors="coerce") == 1)
        & (pd.to_numeric(mt["s2_items_n"], errors="coerce") > 0)
    ].copy()
    mt = mt.drop_duplicates(
        [
            "anchor_year",
            "season_phase",
            "s1_selected_date",
            "s1_orbit_state",
            "s1_relative_orbit",
        ]
    ).reset_index(drop=True)
    if len(mt) != 14:
        raise AssertionError(f"Expected 14 matchable targets; found {len(mt)}")

    mt["optical_date"] = mt["nearest_s2_date"].astype(str)
    mt["target_id"] = mt.apply(target_key, axis=1)

    scl = pd.read_csv(SCL_POINTS)
    scl["support_id"] = pd.to_numeric(scl["support_id"], errors="raise").astype(int)
    scl["scl_code"] = pd.to_numeric(scl["scl_code"], errors="coerce")

    expected_scl_rows = len(mt) * EXPECTED_SUPPORT
    scl_use = scl[scl["target_id"].isin(set(mt["target_id"]))].copy()
    if len(scl_use) != expected_scl_rows:
        raise AssertionError(
            f"Expected {expected_scl_rows} C2P-B point rows; found {len(scl_use)}"
        )

    # C2P-B already froze SCL mosaic interpretation. Reuse its final per-point
    # SCL code rather than re-derive SCL here.
    scl_lookup = scl_use.set_index(["target_id", "support_id"])

    asset_qa_rows = []
    point_rows = []

    for ti, tr in enumerate(mt.itertuples(index=False), start=1):
        print(
            f"[{ti:02d}/{len(mt)}] target={tr.target_id} "
            f"optical_date={tr.optical_date}",
            flush=True,
        )

        scene_rows = inv[
            (inv["date"] == str(tr.optical_date))
            & (
                pd.to_numeric(
                    inv["support_points_inside_footprint_n"], errors="coerce"
                ).fillna(0)
                > 0
            )
        ].copy()

        if scene_rows.empty:
            raise AssertionError(
                f"{tr.target_id}: no S2 items cover support on {tr.optical_date}"
            )

        print(f"  candidate tile items: {len(scene_rows)}", flush=True)

        item_band_values = []

        for sr in scene_rows.itertuples(index=False):
            item_id = str(sr.item_id)
            js = get_json(STAC_ITEM.format(item_id=item_id))

            proc_ver = str(js.get("properties", {}).get("processing:version", ""))
            if not proc_ver.startswith("05."):
                raise AssertionError(
                    f"{item_id}: processing:version={proc_ver!r}; "
                    "frozen C2P-C radiometric rule applies only to PB05.xx."
                )

            item_rec = {
                "item_id": item_id,
                "processing_version": proc_ver,
                "mgrs_tile": getattr(sr, "mgrs_tile", None),
                "platform": getattr(sr, "platform", None),
                "values": {},
                "margin": None,
                "scl": None,
            }

            print(f"    item {item_id} PB {proc_ver}", flush=True)

            for asset_key in BANDS:
                print(f"      {asset_key}", flush=True)
                dn, refl, margin, qa = sample_band(js, asset_key, support)
                qa.update(
                    {
                        "target_id": tr.target_id,
                        "anchor_year": int(tr.anchor_year),
                        "season_phase": tr.season_phase,
                        "s1_selected_date": tr.s1_selected_date,
                        "optical_date": tr.optical_date,
                        "processing_version": proc_ver,
                        "mgrs_tile": getattr(sr, "mgrs_tile", None),
                        "platform": getattr(sr, "platform", None),
                        "quantification_value": QUANTIFICATION,
                        "boa_add_offset": BOA_ADD_OFFSET,
                    }
                )
                asset_qa_rows.append(qa)
                item_rec["values"][SHORT[asset_key]] = refl

                if item_rec["margin"] is None:
                    item_rec["margin"] = margin
                else:
                    same = (
                        np.array_equal(
                            np.isnan(item_rec["margin"]), np.isnan(margin)
                        )
                        and np.allclose(
                            np.nan_to_num(item_rec["margin"], nan=-9999.0),
                            np.nan_to_num(margin, nan=-9999.0),
                            atol=1e-8, rtol=0,
                        )
                    )
                    if not same:
                        raise AssertionError(
                            f"{item_id}: 20 m band geometries disagree."
                        )

            print("      SCL_20m", flush=True)
            item_scl, scl_margin, scl_qa = sample_scl(js, support)
            scl_qa.update(
                {
                    "target_id": tr.target_id,
                    "anchor_year": int(tr.anchor_year),
                    "season_phase": tr.season_phase,
                    "s1_selected_date": tr.s1_selected_date,
                    "optical_date": tr.optical_date,
                    "processing_version": proc_ver,
                    "mgrs_tile": getattr(sr, "mgrs_tile", None),
                    "platform": getattr(sr, "platform", None),
                    "quantification_value": np.nan,
                    "boa_add_offset": np.nan,
                }
            )
            asset_qa_rows.append(scl_qa)

            if not (
                np.array_equal(np.isnan(item_rec["margin"]), np.isnan(scl_margin))
                and np.allclose(
                    np.nan_to_num(item_rec["margin"], nan=-9999.0),
                    np.nan_to_num(scl_margin, nan=-9999.0),
                    atol=1e-8, rtol=0,
                )
            ):
                raise AssertionError(f"{item_id}: SCL geometry differs from bands.")

            item_rec["scl"] = item_scl
            item_band_values.append(item_rec)

        for i in range(EXPECTED_SUPPORT):
            sid = int(support.loc[i, "support_id"])

            c2pb_row = scl_lookup.loc[(tr.target_id, sid)]
            c2pb_scl = (
                int(c2pb_row["scl_code"])
                if pd.notna(c2pb_row["scl_code"])
                else np.nan
            )

            owner, candidate_items_n = choose_owner(item_band_values, i)

            rec = {
                "target_id": tr.target_id,
                "anchor_year": int(tr.anchor_year),
                "season_phase": tr.season_phase,
                "s1_selected_date": tr.s1_selected_date,
                "optical_date": tr.optical_date,
                "nearest_abs_day_offset": int(tr.nearest_abs_day_offset),
                "support_id": sid,
                "lon": float(support.loc[i, "lon"]),
                "lat": float(support.loc[i, "lat"]),
                "candidate_tile_items_n": int(candidate_items_n),
                "c2pb_mosaic_scl_code": c2pb_scl,
                "c2pb_mosaic_scl_label": c2pb_row["scl_label"],
            }

            if owner is None:
                rec.update({
                    "owner_item_id": None,
                    "owner_mgrs_tile": None,
                    "owner_edge_margin_px": np.nan,
                    "owner_scl_code": np.nan,
                    "owner_scl_confirmed_usable": False,
                    "owner_vs_c2pb_scl_disagree": False,
                })
                for short in SHORT.values():
                    rec[f"{short}_boa"] = np.nan
                    rec[f"{short}_overlap_contributors_n"] = 0
                    rec[f"{short}_overlap_spread"] = np.nan
                rec["all_six_bands_present"] = False
                rec["optical_usable_base"] = False
            else:
                owner_scl = owner["scl"][i]
                owner_scl_code = int(owner_scl) if np.isfinite(owner_scl) else np.nan
                owner_clear = (
                    np.isfinite(owner_scl_code)
                    and int(owner_scl_code) in CONFIRMED_USABLE_SCL
                )

                rec.update({
                    "owner_item_id": owner["item_id"],
                    "owner_mgrs_tile": owner["mgrs_tile"],
                    "owner_edge_margin_px": float(owner["margin"][i]),
                    "owner_scl_code": owner_scl_code,
                    "owner_scl_confirmed_usable": bool(owner_clear),
                    "owner_vs_c2pb_scl_disagree": bool(
                        np.isfinite(owner_scl_code)
                        and np.isfinite(c2pb_scl)
                        and int(owner_scl_code) != int(c2pb_scl)
                    ),
                })

                all_six = True
                for short in SHORT.values():
                    value = owner["values"][short][i]
                    rec[f"{short}_boa"] = value

                    vals = [
                        item["values"][short][i]
                        for item in item_band_values
                        if np.isfinite(item["margin"][i])
                    ]
                    contrib_n, spread = descriptive_spread(vals)
                    rec[f"{short}_overlap_contributors_n"] = contrib_n
                    rec[f"{short}_overlap_spread"] = spread

                    if not np.isfinite(value):
                        all_six = False

                rec["all_six_bands_present"] = bool(all_six)
                rec["optical_usable_base"] = bool(owner_clear and all_six)

            if rec["optical_usable_base"]:
                rec["NDVI"], rec["NDVI_valid"] = safe_index_nonnegative(
                    rec["B8A_boa"], rec["B04_boa"]
                )
                rec["NDWI"], rec["NDWI_valid"] = safe_index_nonnegative(
                    rec["B03_boa"], rec["B8A_boa"]
                )
                rec["MNDWI"], rec["MNDWI_valid"] = safe_index_nonnegative(
                    rec["B03_boa"], rec["B11_boa"]
                )
                rec["LSWI"], rec["LSWI_valid"] = safe_index_nonnegative(
                    rec["B8A_boa"], rec["B11_boa"]
                )
            else:
                for name in ["NDVI", "NDWI", "MNDWI", "LSWI"]:
                    rec[name] = np.nan
                    rec[f"{name}_valid"] = False

            rec["all_four_indices_valid"] = bool(
                rec["NDVI_valid"]
                and rec["NDWI_valid"]
                and rec["MNDWI_valid"]
                and rec["LSWI_valid"]
            )

            point_rows.append(rec)

    asset_qa = pd.DataFrame(asset_qa_rows)
    pts = pd.DataFrame(point_rows)

    asset_qa.to_csv(ASSET_QA_OUT, index=False)
    pts.to_csv(POINT_OUT, index=False)

    # Technical target summaries.
    target_rows = []
    for target_id, g in pts.groupby("target_id", sort=True):
        m = g.iloc[0]
        row = {
            "target_id": target_id,
            "anchor_year": int(m["anchor_year"]),
            "season_phase": m["season_phase"],
            "s1_selected_date": m["s1_selected_date"],
            "optical_date": m["optical_date"],
            "support_n": int(len(g)),
            "owner_scl_confirmed_usable_n": int(g["owner_scl_confirmed_usable"].sum()),
            "owner_scl_confirmed_usable_share": float(g["owner_scl_confirmed_usable"].mean()),
            "all_six_bands_present_n": int(g["all_six_bands_present"].sum()),
            "all_six_bands_present_share": float(g["all_six_bands_present"].mean()),
            "owner_vs_c2pb_scl_disagree_n": int(g["owner_vs_c2pb_scl_disagree"].sum()),
            "owner_vs_c2pb_scl_disagree_share": float(g["owner_vs_c2pb_scl_disagree"].mean()),
            "optical_usable_base_n": int(g["optical_usable_base"].sum()),
            "optical_usable_base_share": float(g["optical_usable_base"].mean()),
            "all_four_indices_valid_n": int(g["all_four_indices_valid"].sum()),
            "all_four_indices_valid_share": float(g["all_four_indices_valid"].mean()),
        }

        for band in SHORT.values():
            x = pd.to_numeric(g[f"{band}_boa"], errors="coerce")
            row[f"{band}_median_all_available"] = (
                float(x.median()) if x.notna().any() else np.nan
            )
            xu = x[g["optical_usable_base"]]
            row[f"{band}_median_usable"] = (
                float(xu.median()) if xu.notna().any() else np.nan
            )

        target_rows.append(row)

    target_summary = pd.DataFrame(target_rows).sort_values(
        ["anchor_year", "s1_selected_date", "target_id"]
    )
    target_summary.to_csv(TARGET_OUT, index=False)

    index_rows = []
    for target_id, g in pts.groupby("target_id", sort=True):
        m = g.iloc[0]
        gu = g[g["optical_usable_base"]].copy()
        row = {
            "target_id": target_id,
            "anchor_year": int(m["anchor_year"]),
            "season_phase": m["season_phase"],
            "s1_selected_date": m["s1_selected_date"],
            "optical_date": m["optical_date"],
            "usable_n": int(len(gu)),
        }

        for idx_name in ["NDVI", "NDWI", "MNDWI", "LSWI"]:
            x = pd.to_numeric(
                gu.loc[gu[f"{idx_name}_valid"], idx_name], errors="coerce"
            ).dropna()
            row[f"{idx_name}_n"] = int(len(x))
            row[f"{idx_name}_median"] = float(x.median()) if len(x) else np.nan
            row[f"{idx_name}_p10"] = float(x.quantile(0.10)) if len(x) else np.nan
            row[f"{idx_name}_p90"] = float(x.quantile(0.90)) if len(x) else np.nan
            row[f"{idx_name}_min"] = float(x.min()) if len(x) else np.nan
            row[f"{idx_name}_max"] = float(x.max()) if len(x) else np.nan

        index_rows.append(row)

    index_summary = pd.DataFrame(index_rows).sort_values(
        ["anchor_year", "s1_selected_date", "target_id"]
    )
    index_summary.to_csv(INDEX_OUT, index=False)

    all_assets_pass = bool((asset_qa["status"] == "PASS").all())
    all_pb05 = bool(
        asset_qa["processing_version"].astype(str).str.startswith("05.").all()
    )
    all_support_rows = bool(
        (target_summary["support_n"] == EXPECTED_SUPPORT).all()
    )

    invalid_index_range = {}
    for name in ["NDVI", "NDWI", "MNDWI", "LSWI"]:
        x = pd.to_numeric(pts[name], errors="coerce").dropna()
        invalid_index_range[name] = int(((x < -1.000001) | (x > 1.000001)).sum())

    index_range_pass = all(v == 0 for v in invalid_index_range.values())

    # Negative BOA reflectance can legitimately occur after the PB04+ offset;
    # therefore it is reported, not failed.
    negative_refl = {}
    extreme_refl = {}
    for band in SHORT.values():
        x = pd.to_numeric(pts[f"{band}_boa"], errors="coerce").dropna()
        negative_refl[band] = int((x < 0).sum())
        extreme_refl[band] = int((x > 1.5).sum())

    status = (
        "PASS"
        if all_assets_pass and all_pb05 and all_support_rows and index_range_pass
        else "FAIL"
    )

    qa = {
        "status": status,
        "stage": "DESIGN_C_C2PC2_SENTINEL2_BOA_CANONICAL_TILE_REBUILD",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ricefloodit_support_points_n": EXPECTED_SUPPORT,
        "targets_n": int(len(mt)),
        "required_bands": BANDS,
        "quantification_value": QUANTIFICATION,
        "boa_add_offset": BOA_ADD_OFFSET,
        "nodata_dn": NODATA_DN,
        "processing_baseline_required": "05.xx",
        "all_assets_pass": all_assets_pass,
        "all_assets_pb05xx": all_pb05,
        "all_targets_expected_support_rows": all_support_rows,
        "confirmed_usable_scl_codes": sorted(CONFIRMED_USABLE_SCL),
        "obscured_scl_codes": sorted(OBSCURED_SCL),
        "unclassified_scl_codes": sorted(UNCLASSIFIED_SCL),
        "invalid_scl_codes": sorted(INVALID_SCL),
        "index_out_of_range_counts": invalid_index_range,
        "index_range_pass": index_range_pass,
        "negative_reflectance_counts_report_only": negative_refl,
        "reflectance_gt_1p5_counts_report_only": extreme_refl,
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "preexisting_flood_exposure_values_read": False,
        "inundation_threshold_selected": False,
        "inundation_classifier_fitted": False,
        "association_models_fitted": 0,
        "frozen_sentinel1_target_universe_modified": False,
        "canonical_tile_rule": (
            "maximum distance in pixels from nearest tile edge; "
            "lexicographic item_id tie-break; geometry only"
        ),
        "normalized_difference_rule": (
            "index emitted only when both inputs are finite and nonnegative "
            "and denominator > 1e-6"
        ),
        "next_stage": (
            "If PASS, inspect cross-sensor S1-S2 measurement trajectories without "
            "groundwater and audit exact annual rice-parcel geography in parallel."
        ),
    }
    QA_OUT.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    usable_shares = target_summary["optical_usable_base_share"]

    lines = [
        "DESIGN C - C2P-C2 SENTINEL-2 BOA CANONICAL-TILE REBUILD",
        "=" * 78,
        "",
        f"Targets: {len(mt)}",
        f"Support coordinates per target: {EXPECTED_SUPPORT}",
        f"Asset-band reads: {len(asset_qa)}",
        f"PB05.xx assets only: {all_pb05}",
        "",
        "FROZEN RADIOMETRIC RULE",
        "-----------------------",
        "DN == 0 -> nodata",
        "BOA reflectance = (DN - 1000) / 10000",
        "",
        "CANONICAL TILE RULE",
        "-------------------",
        "Choose the covering tile where the support point is deepest inside the tile.",
        "Tie-break by item_id. Reflectance/SCL values do not enter tile ownership.",
        "",
        "SCL CONFIRMED-USABLE RULE",
        "-------------------------",
        "Owner-tile SCL in {4 vegetation, 5 not-vegetated, 6 water}",
        "Class 2 treated as cast shadow; class 7 retained as unclassified.",
        "",
        "OPTICAL INDEX USABILITY",
        "-----------------------",
        f"Minimum target usable share: {usable_shares.min():.6f}",
        f"Median target usable share: {usable_shares.median():.6f}",
        f"Maximum target usable share: {usable_shares.max():.6f}",
        "",
        "INDEX RANGE QA",
        "--------------",
    ]
    for name, count in invalid_index_range.items():
        lines.append(f"{name}: out-of-range count = {count}")

    lines += [
        "",
        "Negative BOA reflectance values are reported, not automatically rejected.",
        "No inundation threshold or classifier was selected.",
        "No groundwater or irrigation-flow outcome was read.",
        "",
        f"C2P-C2 STATUS: {status}",
    ]

    summary = "\n".join(lines) + "\n"
    SUMMARY_OUT.write_text(summary, encoding="utf-8")
    print("\n" + summary)

    print("TARGET REFLECTANCE SUMMARY")
    print("--------------------------")
    pd.set_option("display.width", 280)
    print(target_summary.to_string(index=False))

    print()
    print("INDEX SUMMARY")
    print("-------------")
    print(index_summary.to_string(index=False))

    if status != "PASS":
        raise RuntimeError("C2P-C2 failed technical QA gates; inspect outputs.")


if __name__ == "__main__":
    main()

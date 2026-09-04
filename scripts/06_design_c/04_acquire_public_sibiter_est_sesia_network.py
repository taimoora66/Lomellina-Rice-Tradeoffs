"""Design C — C2B Public SIBITER / Est Sesia Network Acquisition.

PURPOSE
-------
Acquire authoritative PUBLIC irrigation-network features for the Design C
study footprint directly from Regione Lombardia ArcGIS REST.

No association models.
No groundwater outcome inspection.
No frozen Stage-5–8 modification.

Core actions:
1. Determine the Lomellina/RiceFloodIT study footprint from existing georef.
2. Convert footprint to EPSG:32632.
3. Query SIBITER service metadata and verify the Est Sesia manager code
   from the server's own coded-value domain.
4. Download study-area features for:
   - Rete SIBITER (canal network)
   - Comprensori di bonifica e irrigazione
   - Impianti di sollevamento
   - Manufatti idraulici
   - Fontanili
5. Save exact raw GeoJSON responses and SHA-256 hashes.
6. Produce an Est Sesia-only canal inventory with IDs/names/functions.
7. Produce QA summaries only; no hydrological linkage/model yet.

Run from repository root:
    python scripts/06_design_c/04_acquire_public_sibiter_est_sesia_network.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[2]

RICE_GEO = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "ricefloodit_georef.csv"
)

BASE = ROOT / "data" / "design_c"
RAW = BASE / "raw" / "sibiter_public"
META = BASE / "metadata"
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

for p in [RAW, META, OUT]:
    p.mkdir(parents=True, exist_ok=True)

SERVICE = (
    "https://www.cartografia.servizirl.it/arcgis1/rest/services/"
    "territorio/SIBITER/MapServer"
)

# Relevant scientific layers from the public service.
LAYERS = {
    0: "fontanili",
    1: "impianti_sollevamento",
    2: "manufatti_idraulici",
    4: "rete_sibiter",
    13: "comprensori",
}

WGS84_TO_UTM32 = Transformer.from_crs(
    "EPSG:4326", "EPSG:32632", always_xy=True
)


def fetch_json(url: str, timeout: int = 180) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "UNIMI-DesignC-public-SIBITER-acquisition/1.3"
            )
        },
    )
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_bytes(url: str, timeout: int = 180) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "UNIMI-DesignC-public-SIBITER-acquisition/1.3"
            )
        },
    )
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def post_form_bytes(
    url: str,
    params: dict,
    timeout: int = 180,
) -> bytes:
    """POST application/x-www-form-urlencoded to ArcGIS REST.

    Used for object-ID batches so the request does not exceed URL-length
    limits imposed by web servers/proxies.
    """
    body = urlencode(params).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": (
                "UNIMI-DesignC-public-SIBITER-acquisition/1.3"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def study_bbox_wgs84() -> tuple[float, float, float, float]:
    d = pd.read_csv(RICE_GEO)
    if not {"lon", "lat"}.issubset(d.columns):
        raise AssertionError("RiceFloodIT georef must contain lon, lat.")
    return (
        float(d["lon"].min()),
        float(d["lat"].min()),
        float(d["lon"].max()),
        float(d["lat"].max()),
    )


def bbox_to_utm32(bbox):
    minlon, minlat, maxlon, maxlat = bbox
    corners = [
        WGS84_TO_UTM32.transform(minlon, minlat),
        WGS84_TO_UTM32.transform(minlon, maxlat),
        WGS84_TO_UTM32.transform(maxlon, minlat),
        WGS84_TO_UTM32.transform(maxlon, maxlat),
    ]
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    return min(xs), min(ys), max(xs), max(ys)


def layer_metadata(layer_id: int) -> dict:
    return fetch_json(f"{SERVICE}/{layer_id}?f=pjson")


def coded_value_map(meta: dict, field_name: str) -> dict:
    for field in meta.get("fields", []):
        if field.get("name") != field_name:
            continue
        domain = field.get("domain") or {}
        coded = domain.get("codedValues") or []
        return {
            item.get("code"): item.get("name")
            for item in coded
        }
    return {}



def esri_geometry_to_geojson(geom: dict | None) -> dict | None:
    """Convert ArcGIS REST geometry JSON to GeoJSON geometry."""
    if not geom:
        return None

    if "x" in geom and "y" in geom:
        return {
            "type": "Point",
            "coordinates": [geom["x"], geom["y"]],
        }

    if "points" in geom:
        return {
            "type": "MultiPoint",
            "coordinates": geom["points"] or [],
        }

    if "paths" in geom:
        paths = geom["paths"] or []
        if not paths:
            return None
        if len(paths) == 1:
            return {
                "type": "LineString",
                "coordinates": paths[0],
            }
        return {
            "type": "MultiLineString",
            "coordinates": paths,
        }

    if "rings" in geom:
        rings = geom["rings"] or []
        if not rings:
            return None

        # Preserve ArcGIS ring coordinates exactly at acquisition time.
        # Topology/orientation QA belongs in C2C.
        return {
            "type": "Polygon",
            "coordinates": rings,
        }

    raise ValueError(
        "Unsupported ArcGIS geometry structure with keys: "
        + ", ".join(sorted(geom.keys()))
    )


def esri_features_to_geojson(obj: dict) -> dict:
    """Convert an ArcGIS REST feature response to a GeoJSON FeatureCollection."""
    features = []

    for feat in obj.get("features", []):
        attrs = dict(feat.get("attributes") or {})
        geom = esri_geometry_to_geojson(feat.get("geometry"))

        features.append({
            "type": "Feature",
            "properties": attrs,
            "geometry": geom,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def query_count(
    layer_id: int,
    bbox_utm32,
    where: str = "1=1",
) -> int:
    """Authoritative feature count for the same spatial/SQL query."""
    xmin, ymin, xmax, ymax = bbox_utm32
    params = {
        "where": where,
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "32632",
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true",
        "f": "json",
    }
    url = f"{SERVICE}/{layer_id}/query"
    raw = post_form_bytes(url, params)
    obj = json.loads(raw.decode("utf-8"))
    if "error" in obj:
        raise RuntimeError(
            f"ArcGIS count query error for layer {layer_id}: {obj['error']}"
        )
    if "count" not in obj:
        raise RuntimeError(
            f"ArcGIS count query returned no count for layer {layer_id}: "
            f"{obj.keys()}"
        )
    return int(obj["count"])


def query_geojson_complete(
    layer_id: int,
    bbox_utm32,
    where: str = "1=1",
    page_size: int = 500,
) -> tuple[bytes, dict]:
    """Complete spatial download using ArcGIS server-supported pagination.

    The layer metadata declares supportsPagination=true. Each page repeats
    the SAME spatial envelope and SQL condition and explicitly requests
    geometry. A separate returnCountOnly query is the authoritative expected
    count. Pages are ordered by the layer OID for deterministic completeness.
    """
    meta = layer_metadata(layer_id)

    oid_field = (
        meta.get("objectIdField")
        or meta.get("objectIdFieldName")
    )
    if not oid_field:
        for field in meta.get("fields", []):
            if field.get("type") == "esriFieldTypeOID":
                oid_field = field.get("name")
                break
    if not oid_field:
        raise AssertionError(
            f"Could not identify OID field for layer {layer_id}."
        )

    expected_n = query_count(layer_id, bbox_utm32, where=where)
    xmin, ymin, xmax, ymax = bbox_utm32

    all_features = []
    batches = []
    offset = 0

    while offset < expected_n:
        params = {
            "where": where,
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "32632",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "returnZ": "false",
            "returnM": "false",
            "outSR": "32632",
            "orderByFields": f"{oid_field} ASC",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
            "f": "json",
        }
        url = f"{SERVICE}/{layer_id}/query"
        raw = post_form_bytes(url, params)
        obj = json.loads(raw.decode("utf-8"))

        if "error" in obj:
            raise RuntimeError(
                f"ArcGIS paged query error for layer {layer_id}, "
                f"offset={offset}: {obj['error']}"
            )

        raw_feats = obj.get("features", [])
        if not raw_feats and offset < expected_n:
            raise AssertionError(
                f"Layer {layer_id} pagination stopped early at "
                f"offset={offset}; expected {expected_n}."
            )

        converted = esri_features_to_geojson(obj)
        feats = converted.get("features", [])

        null_geom = sum(
            1 for feat in feats if feat.get("geometry") is None
        )
        if null_geom:
            # Store diagnostic shape of server response in the error.
            first = raw_feats[0] if raw_feats else {}
            raise AssertionError(
                f"Layer {layer_id} page offset={offset} returned "
                f"{null_geom}/{len(feats)} null geometries. "
                f"Server feature keys={list(first.keys())}; "
                f"response keys={list(obj.keys())}"
            )

        all_features.extend(feats)
        batches.append({
            "batch_index": len(batches) + 1,
            "result_offset": offset,
            "requested_page_size": page_size,
            "returned_features_n": len(feats),
            "exceeded_transfer_limit": bool(
                obj.get("exceededTransferLimit", False)
            ),
            "null_geometry_n": null_geom,
        })

        offset += len(feats)

    if len(all_features) != expected_n:
        raise AssertionError(
            f"Layer {layer_id} count mismatch: expected={expected_n}, "
            f"downloaded={len(all_features)}"
        )

    # Verify OID uniqueness and expected record count.
    ids = []
    for feat in all_features:
        props = feat.get("properties") or {}
        if oid_field not in props:
            raise AssertionError(
                f"OID field {oid_field} missing from layer {layer_id} feature."
            )
        ids.append(int(props[oid_field]))

    dupes = sorted(
        oid for oid in set(ids) if ids.count(oid) > 1
    )
    if dupes:
        raise AssertionError(
            f"Layer {layer_id} returned duplicate OIDs: {dupes[:10]}"
        )

    fc = {
        "type": "FeatureCollection",
        "features": all_features,
    }
    data = json.dumps(fc, ensure_ascii=False).encode("utf-8")

    qa = {
        "authoritative_count_n": expected_n,
        "features_n": len(all_features),
        "batches_n": len(batches),
        "oid_field": oid_field,
        "unique_oids_n": len(set(ids)),
        "complete": len(all_features) == expected_n == len(set(ids)),
        "duplicate_object_ids": dupes,
        "batch_details": batches,
    }
    return data, qa



def geojson_coordinate_bounds(obj: dict) -> tuple[float, float, float, float]:
    xs = []
    ys = []

    def walk(coords):
        if coords is None:
            return
        if (
            isinstance(coords, (list, tuple))
            and len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
            return
        if isinstance(coords, (list, tuple)):
            for item in coords:
                walk(item)

    for feat in obj.get("features", []):
        geom = feat.get("geometry") or {}
        walk(geom.get("coordinates"))

    if not xs:
        return (float("nan"),) * 4

    return min(xs), min(ys), max(xs), max(ys)



def feature_properties(geojson_obj: dict) -> pd.DataFrame:
    rows = []
    for feat in geojson_obj.get("features", []):
        props = dict(feat.get("properties") or {})
        rows.append(props)
    return pd.DataFrame(rows)


def find_est_sesia_code(meta: dict) -> tuple[object, str]:
    managers = coded_value_map(meta, "ID_ENTE_GESTORE")
    candidates = [
        (code, name)
        for code, name in managers.items()
        if name and "EST SESIA" in str(name).upper()
    ]
    if len(candidates) != 1:
        raise AssertionError(
            "Could not uniquely verify Est Sesia manager code "
            f"from public SIBITER metadata. Candidates={candidates}"
        )
    return candidates[0]


def main():
    print("DESIGN C — C2B PUBLIC SIBITER / EST SESIA NETWORK")
    print("=" * 57)
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    bbox_wgs = study_bbox_wgs84()
    bbox_utm = bbox_to_utm32(bbox_wgs)

    print(
        "Study bbox WGS84: "
        f"{bbox_wgs[0]:.5f}, {bbox_wgs[1]:.5f}, "
        f"{bbox_wgs[2]:.5f}, {bbox_wgs[3]:.5f}"
    )
    print(
        "Study bbox EPSG:32632: "
        f"{bbox_utm[0]:.1f}, {bbox_utm[1]:.1f}, "
        f"{bbox_utm[2]:.1f}, {bbox_utm[3]:.1f}\n"
    )

    # Server metadata snapshot.
    service_meta_bytes = fetch_bytes(f"{SERVICE}?f=pjson")
    (RAW / "SIBITER_MapServer_metadata.json").write_bytes(
        service_meta_bytes
    )

    manifest_rows = []
    summary_rows = []

    rete_meta = layer_metadata(4)
    est_code, est_label = find_est_sesia_code(rete_meta)

    print(
        f"Verified public coded value: "
        f"ID_ENTE_GESTORE={est_code} -> {est_label}"
    )

    # Preserve layer metadata snapshots.
    for layer_id, slug in LAYERS.items():
        meta_bytes = fetch_bytes(f"{SERVICE}/{layer_id}?f=pjson")
        meta_path = RAW / f"layer_{layer_id:02d}_{slug}_metadata.json"
        meta_path.write_bytes(meta_bytes)

        manifest_rows.append({
            "artifact": meta_path.name,
            "kind": "layer_metadata",
            "layer_id": layer_id,
            "sha256": sha256_bytes(meta_bytes),
            "bytes": len(meta_bytes),
            "source_url": f"{SERVICE}/{layer_id}?f=pjson",
        })

        data, query_qa = query_geojson_complete(layer_id, bbox_utm, where="1=1")
        path = RAW / f"layer_{layer_id:02d}_{slug}_study_bbox.geojson"
        path.write_bytes(data)

        obj = json.loads(data.decode("utf-8"))
        n = len(obj.get("features", []))
        geometry_n = sum(
            1 for f in obj.get("features", [])
            if f.get("geometry") is not None
        )
        if geometry_n != n:
            raise AssertionError(
                f"Layer {layer_id} geometry completeness failed: "
                f"{geometry_n}/{n}"
            )
        geom_bounds = geojson_coordinate_bounds(obj)

        # EPSG:32632 plausibility gate for study-area layers.
        if n and not (
            200000 <= geom_bounds[0] <= 900000
            and 200000 <= geom_bounds[2] <= 900000
            and 4_700_000 <= geom_bounds[1] <= 5_400_000
            and 4_700_000 <= geom_bounds[3] <= 5_400_000
        ):
            raise AssertionError(
                f"Layer {layer_id} has implausible EPSG:32632 bounds: "
                f"{geom_bounds}"
            )

        manifest_rows.append({
            "artifact": path.name,
            "kind": "study_bbox_geojson",
            "layer_id": layer_id,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
            "source_url": f"{SERVICE}/{layer_id}/query",
        })

        props = feature_properties(obj)
        props.to_csv(
            OUT / f"c2b_{slug}_attributes.csv",
            index=False,
        )

        summary_rows.append({
            "layer_id": layer_id,
            "layer": slug,
            "features_in_study_bbox": n,
            "authoritative_object_ids_n": query_qa["authoritative_count_n"],
            "query_batches_n": query_qa["batches_n"],
            "download_complete": query_qa["complete"],
            "geometry_features_n": geometry_n,
            "geometry_complete": geometry_n == n,
            "min_x": geom_bounds[0],
            "min_y": geom_bounds[1],
            "max_x": geom_bounds[2],
            "max_y": geom_bounds[3],
            "attribute_columns_n": len(props.columns),
        })
        print(
            f"Layer {layer_id:02d} {slug}: {n} features "
            f"(IDs={query_qa['object_ids_n']}, "
            f"batches={query_qa['batches_n']}, complete=YES)"
        )

    # Est Sesia-specific network query from server itself.
    where_est = f"ID_ENTE_GESTORE={est_code}"
    est_data, est_query_qa = query_geojson_complete(
        4, bbox_utm, where=where_est
    )
    est_path = RAW / "layer_04_rete_sibiter_est_sesia_study_bbox.geojson"
    est_path.write_bytes(est_data)
    est_obj = json.loads(est_data.decode("utf-8"))
    est_props = feature_properties(est_obj)
    est_geometry_n = sum(
        1 for f in est_obj.get("features", [])
        if f.get("geometry") is not None
    )
    est_bounds = geojson_coordinate_bounds(est_obj)

    if est_geometry_n != len(est_obj.get("features", [])):
        raise AssertionError(
            f"Est Sesia geometry completeness failed: "
            f"{est_geometry_n}/{len(est_obj.get('features', []))}"
        )

    if len(est_obj.get("features", [])) and not (
        200000 <= est_bounds[0] <= 900000
        and 200000 <= est_bounds[2] <= 900000
        and 4_700_000 <= est_bounds[1] <= 5_400_000
        and 4_700_000 <= est_bounds[3] <= 5_400_000
    ):
        raise AssertionError(
            f"Est Sesia layer has implausible EPSG:32632 bounds: "
            f"{est_bounds}"
        )

    manifest_rows.append({
        "artifact": est_path.name,
        "kind": "est_sesia_network_geojson",
        "layer_id": 4,
        "sha256": sha256_bytes(est_data),
        "bytes": len(est_data),
        "source_url": f"{SERVICE}/4/query",
    })

    # Human-readable Est Sesia canal inventory.
    desired = [
        "OBJECTID",
        "ID_ENTE_GESTORE",
        "ID_ENTE_PROPRIETARIO",
        "CODICE_CANALE",
        "NOME_CANALE",
        "TIPO",
        "FUNZIONE",
        "TIPO_CANALE",
    ]
    keep = [c for c in desired if c in est_props.columns]
    inv = est_props[keep].copy() if len(est_props) else est_props.copy()

    if "NOME_CANALE" in inv.columns:
        inv = inv.sort_values(
            ["NOME_CANALE", "CODICE_CANALE"]
            if "CODICE_CANALE" in inv.columns
            else ["NOME_CANALE"],
            na_position="last",
        )

    inv.to_csv(
        OUT / "c2b_est_sesia_canal_inventory.csv",
        index=False,
    )

    # Summaries of named/unnamed canals.
    named_n = (
        int(est_props["NOME_CANALE"].notna().sum())
        if "NOME_CANALE" in est_props.columns else 0
    )
    unique_names_n = (
        int(est_props["NOME_CANALE"].dropna().nunique())
        if "NOME_CANALE" in est_props.columns else 0
    )
    unique_codes_n = (
        int(est_props["CODICE_CANALE"].dropna().nunique())
        if "CODICE_CANALE" in est_props.columns else 0
    )

    pd.DataFrame(manifest_rows).to_csv(
        META / "c2b_sibiter_public_acquisition_manifest.csv",
        index=False,
    )
    pd.DataFrame(summary_rows).to_csv(
        OUT / "c2b_sibiter_layer_summary.csv",
        index=False,
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2B_PUBLIC_SIBITER_EST_SESIA_NETWORK",
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "study_bbox_wgs84": bbox_wgs,
        "study_bbox_epsg32632": bbox_utm,
        "est_sesia_manager_code_verified_from_server": est_code,
        "est_sesia_manager_label": est_label,
        "est_sesia_features_n": int(len(est_props)),
        "est_sesia_authoritative_feature_count_n": int(est_query_qa["authoritative_count_n"]),
        "est_sesia_query_batches_n": int(est_query_qa["batches_n"]),
        "est_sesia_download_complete": bool(est_query_qa["complete"]),
        "est_sesia_geometry_features_n": int(est_geometry_n),
        "est_sesia_geometry_complete": bool(est_geometry_n == len(est_props)),
        "est_sesia_geometry_bounds_epsg32632": est_bounds,
        "est_sesia_named_features_n": named_n,
        "est_sesia_unique_canal_names_n": unique_names_n,
        "est_sesia_unique_canal_codes_n": unique_codes_n,
    }
    (OUT / "c2b_sibiter_est_sesia_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = f"""DESIGN C — C2B PUBLIC SIBITER / EST SESIA NETWORK
===================================================

Association models fitted: 0
Frozen artifacts modified: 0

Public server verification:
  Est Sesia manager code: {est_code}
  Est Sesia manager label: {est_label}

Est Sesia network inside study footprint:
  feature segments: {len(est_props)}
  authoritative feature count: {est_query_qa["authoritative_count_n"]}
  query batches: {est_query_qa["batches_n"]}
  completeness verified: YES
  geometry features: {est_geometry_n}
  geometry bounds EPSG:32632: {tuple(round(x, 1) for x in est_bounds)}
  geometry completeness verified: YES
  named segments: {named_n}
  unique canal names: {unique_names_n}
  unique canal codes: {unique_codes_n}

Outputs:
  c2b_est_sesia_canal_inventory.csv
  c2b_sibiter_layer_summary.csv
  c2b_sibiter_est_sesia_qa.json
  c2b_sibiter_public_acquisition_manifest.csv

NEXT
----
Inspect canal names/codes and comprensorio attributes.
Then spatially link groundwater wells to the public Est Sesia network
WITHOUT using groundwater values or association results.

C2B STATUS: PASS
"""
    (OUT / "c2b_sibiter_est_sesia_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print("\n" + summary)


if __name__ == "__main__":
    main()

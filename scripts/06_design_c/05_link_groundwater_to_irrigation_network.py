"""Design C — C2C Official Est Sesia / Groundwater Spatial Linkage.

AUTHORITATIVE INPUT
-------------------
data/design_c/processed/official_riru_est_sesia_network.gpkg

Layers:
- est_sesia_watercourses
    ALL 271 Est Sesia watercourses selected from official
    Corsi_acqua_RIB.GESTIONE.
- matched_detailed_tratti
    Detailed RIRU/SIBITER-linked segments for provenance/enrichment only.

GROUNDWATER INPUT
-----------------
Station metadata/coordinates only.
NO groundwater measurements are read.

PURPOSE
-------
For every groundwater station:
1. compute nearest official Est Sesia watercourse and distance;
2. retain nearest watercourse name/function/network type;
3. indicate whether that watercourse exact-name-links to Tratti_idrici;
4. compute Est Sesia network support within 1, 2, 5 and 10 km;
5. compute nearest matched detailed RIRU/SIBITER segment and distance;
6. retain ID_SIBITER / TRATTI_SIB provenance where available.

This is descriptive spatial feasibility QA only.
NO association model is fitted.
NO exposure/outcome values are used.
NO frozen Stage-5–8 artifacts are modified.

Run:
    python scripts/06_design_c/05_link_groundwater_to_irrigation_network.py
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

NETWORK_GPKG = (
    ROOT / "data" / "design_c" / "processed"
    / "official_riru_est_sesia_network.gpkg"
)

GW_META = (
    ROOT / "data" / "processed" / "publication_groundwater"
    / "groundwater_station_metadata.csv"
)

OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:32632"
RADII_M = [1000, 2000, 5000, 10000]


def load_station_points() -> gpd.GeoDataFrame:
    if not GW_META.exists():
        raise FileNotFoundError(GW_META)

    d = pd.read_csv(GW_META)

    candidates = [
        ("utm_e", "utm_n"),
        ("UTM_Est", "UTM_Nord"),
        ("x_utm", "y_utm"),
    ]
    pair = next(
        ((x, y) for x, y in candidates if x in d.columns and y in d.columns),
        None,
    )
    if pair is None:
        raise AssertionError(
            "Groundwater metadata must contain EPSG:32632 coordinates."
        )

    if "station" not in d.columns:
        raise AssertionError(
            "Groundwater metadata must contain 'station'."
        )

    xcol, ycol = pair
    d[xcol] = pd.to_numeric(d[xcol], errors="coerce")
    d[ycol] = pd.to_numeric(d[ycol], errors="coerce")
    d = d.loc[d[xcol].notna() & d[ycol].notna()].copy()

    if d["station"].duplicated().any():
        dup = d.loc[d["station"].duplicated(), "station"].tolist()
        raise AssertionError(
            f"Duplicate station metadata rows: {dup[:10]}"
        )

    g = gpd.GeoDataFrame(
        d,
        geometry=gpd.points_from_xy(d[xcol], d[ycol]),
        crs=CRS,
    )

    minx, miny, maxx, maxy = map(float, g.total_bounds)
    if not (
        200000 <= minx <= 900000
        and 200000 <= maxx <= 900000
        and 4_700_000 <= miny <= 5_400_000
        and 4_700_000 <= maxy <= 5_400_000
    ):
        raise AssertionError(
            "Station coordinates are implausible for EPSG:32632: "
            f"{(minx, miny, maxx, maxy)}"
        )

    return g


def load_network_layer(layer: str) -> gpd.GeoDataFrame:
    if not NETWORK_GPKG.exists():
        raise FileNotFoundError(NETWORK_GPKG)

    g = gpd.read_file(NETWORK_GPKG, layer=layer)

    if g.crs is None:
        raise AssertionError(
            f"{layer} has no CRS."
        )

    g = g.to_crs(CRS)

    if g.geometry.isna().any() or g.geometry.is_empty.any():
        raise AssertionError(
            f"{layer} contains null/empty geometry."
        )

    minx, miny, maxx, maxy = map(float, g.total_bounds)
    if not (
        200000 <= minx <= 900000
        and 200000 <= maxx <= 900000
        and 4_700_000 <= miny <= 5_400_000
        and 4_700_000 <= maxy <= 5_400_000
    ):
        raise AssertionError(
            f"{layer} has implausible EPSG:32632 bounds: "
            f"{(minx, miny, maxx, maxy)}"
        )

    return g


def nearest_join(
    stations: gpd.GeoDataFrame,
    layer: gpd.GeoDataFrame,
    prefix: str,
    fields: list[str],
) -> pd.DataFrame:
    right = layer.copy().reset_index(drop=True)
    right["_feature_index"] = right.index

    keep = [c for c in fields if c in right.columns]

    joined = gpd.sjoin_nearest(
        stations[["station", "geometry"]],
        right[keep + ["_feature_index", "geometry"]],
        how="left",
        distance_col=f"{prefix}_distance_m",
    )

    # Deterministic resolution of equal-distance ties.
    joined = (
        joined
        .sort_values(
            ["station", f"{prefix}_distance_m", "_feature_index"],
            na_position="last",
        )
        .drop_duplicates("station", keep="first")
    )

    out = joined[
        ["station", f"{prefix}_distance_m"]
    ].copy()

    for c in fields:
        output_name = f"{prefix}_{c.lower()}"
        out[output_name] = (
            joined[c].values if c in joined.columns else None
        )

    return out


def network_context(
    stations: gpd.GeoDataFrame,
    network: gpd.GeoDataFrame,
) -> pd.DataFrame:
    rows = []

    for _, s in stations[["station", "geometry"]].iterrows():
        row = {"station": s["station"]}

        for radius in RADII_M:
            buf = s.geometry.buffer(radius)
            cand = network.loc[network.intersects(buf)].copy()

            if len(cand):
                clipped = cand.geometry.intersection(buf)
                total_len = float(clipped.length.sum())
                feature_n = int(len(cand))
                unique_names_n = int(
                    cand["NOME_C_ACQ"].dropna().nunique()
                )
            else:
                total_len = 0.0
                feature_n = 0
                unique_names_n = 0

            km = radius // 1000

            row[f"est_sesia_watercourses_{km}km_n"] = feature_n
            row[f"est_sesia_unique_names_{km}km_n"] = unique_names_n
            row[f"est_sesia_network_length_{km}km_m"] = total_len

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    print("DESIGN C — C2C OFFICIAL EST SESIA / GROUNDWATER SPATIAL LINKAGE")
    print("=" * 70)
    print("NO groundwater measurements read.")
    print("NO flooding measurements read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    stations = load_station_points()
    est = load_network_layer("est_sesia_watercourses")
    detailed = load_network_layer("matched_detailed_tratti")

    print(f"Groundwater stations with coordinates: {len(stations)}")
    print(f"Official Est Sesia watercourses: {len(est)}")
    print(f"Matched detailed RIRU/SIBITER segments: {len(detailed)}")
    print(
        "Station bounds EPSG:32632: "
        f"{tuple(round(x, 1) for x in stations.total_bounds)}"
    )
    print(
        "Est Sesia bounds EPSG:32632: "
        f"{tuple(round(x, 1) for x in est.total_bounds)}"
    )
    print()

    nearest_est = nearest_join(
        stations,
        est,
        "nearest_est_sesia",
        [
            "OBJECTID",
            "NOME_C_ACQ",
            "FUNZIONE",
            "TIPO_RETIC",
            "GESTIONE",
            "exact_name_in_tratti",
        ],
    )

    nearest_detailed = nearest_join(
        stations,
        detailed,
        "nearest_detailed",
        [
            "OBJECTID",
            "ID_EL_IDR",
            "ID_TR_IDR",
            "NOME",
            "ID_SIBITER",
            "TRATTI_SIB",
        ],
    )

    context = network_context(stations, est)

    # Metadata only; never measurement/outcome values.
    base_cols = [c for c in stations.columns if c != "geometry"]
    linkage = stations[base_cols].copy()

    for part in [nearest_est, nearest_detailed, context]:
        linkage = linkage.merge(
            part,
            on="station",
            how="left",
            validate="one_to_one",
        )

    dist = pd.to_numeric(
        linkage["nearest_est_sesia_distance_m"],
        errors="coerce",
    )

    if dist.isna().any():
        bad = linkage.loc[
            dist.isna(), "station"
        ].tolist()
        raise AssertionError(
            "Missing nearest Est Sesia distance for station(s): "
            f"{bad}"
        )

    if not np.isfinite(dist.to_numpy()).all():
        raise AssertionError(
            "Non-finite nearest Est Sesia distance detected."
        )

    within = {}
    for threshold in [250, 500, 1000, 2000, 5000, 10000]:
        within[str(threshold)] = int((dist <= threshold).sum())

    linkage.to_csv(
        OUT / "c2c_groundwater_official_est_sesia_linkage.csv",
        index=False,
    )

    review_cols = [
        "station",
        "nearest_est_sesia_distance_m",
        "nearest_est_sesia_nome_c_acq",
        "nearest_est_sesia_funzione",
        "nearest_est_sesia_tipo_retic",
        "nearest_est_sesia_exact_name_in_tratti",
        "nearest_detailed_distance_m",
        "nearest_detailed_nome",
        "nearest_detailed_id_sibiter",
        "nearest_detailed_tratti_sib",
        "est_sesia_watercourses_1km_n",
        "est_sesia_unique_names_1km_n",
        "est_sesia_network_length_1km_m",
        "est_sesia_watercourses_2km_n",
        "est_sesia_unique_names_2km_n",
        "est_sesia_watercourses_5km_n",
        "est_sesia_unique_names_5km_n",
        "est_sesia_watercourses_10km_n",
        "est_sesia_unique_names_10km_n",
    ]
    review_cols = [c for c in review_cols if c in linkage.columns]

    linkage[review_cols].to_csv(
        OUT / "c2c_station_est_sesia_review.csv",
        index=False,
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2C_OFFICIAL_EST_SESIA_SPATIAL_LINKAGE",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "groundwater_stations_n": int(len(stations)),
        "official_est_sesia_watercourses_n": int(len(est)),
        "matched_detailed_segments_n": int(len(detailed)),
        "nearest_est_sesia_distance_m": {
            "min": float(dist.min()),
            "median": float(dist.median()),
            "p75": float(dist.quantile(0.75)),
            "max": float(dist.max()),
        },
        "stations_within_distance_m": within,
        "stations_with_est_sesia_watercourse_with_exact_tratti_name_link_n": int(
            pd.Series(
                linkage[
                    "nearest_est_sesia_exact_name_in_tratti"
                ]
            ).fillna(False).astype(bool).sum()
        ),
    }

    (OUT / "c2c_official_est_sesia_spatial_linkage_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = f"""DESIGN C — C2C OFFICIAL EST SESIA / GROUNDWATER SPATIAL LINKAGE
=================================================================

Groundwater measurements read: 0
Flooding measurements read: 0
Association models fitted: 0
Frozen artifacts modified: 0

Groundwater stations: {len(stations)}
Official Est Sesia watercourses: {len(est)}
Matched detailed RIRU/SIBITER segments: {len(detailed)}

Nearest official Est Sesia watercourse distance:
  minimum: {dist.min():.1f} m
  median: {dist.median():.1f} m
  75th percentile: {dist.quantile(0.75):.1f} m
  maximum: {dist.max():.1f} m

Stations within:
  250 m: {within["250"]}
  500 m: {within["500"]}
  1 km: {within["1000"]}
  2 km: {within["2000"]}
  5 km: {within["5000"]}
  10 km: {within["10000"]}

Outputs:
  c2c_groundwater_official_est_sesia_linkage.csv
  c2c_station_est_sesia_review.csv
  c2c_official_est_sesia_spatial_linkage_qa.json
  c2c_official_est_sesia_spatial_linkage_summary.txt

INTERPRETATION RULE
-------------------
Nearest watercourse is spatial proximity only.
It is NOT automatically the canal that hydraulically serves the well.
Network density/proximity is feasibility evidence for the next topology/
gauge-identification stage, not an irrigation treatment assignment.

C2C STATUS: PASS
"""

    (OUT / "c2c_official_est_sesia_spatial_linkage_summary.txt").write_text(
        summary,
        encoding="utf-8",
    )

    print(summary)


if __name__ == "__main__":
    main()

"""Design C — C1 Public Availability Auditor (revision 2).

QUALITY-FIRST FEASIBILITY AUDIT ONLY.

NO groundwater–flooding association model is fitted.
NO frozen historical/post-2021 artifact is modified.
NO well is selected using an exposure/outcome association.

This revision:
1. Audits native ARPA ISS groundwater cadence for 2015-2023.
2. Adds April-September (rice-season) support by well and well-year.
3. Adds station coordinates and metadata support.
4. Queries Sentinel-1 GRD metadata only.
5. Parses SIDRO public registry using either WGS84 lon/lat OR EPSG:32632 UTM.
6. Registers RIRU/SIBITER public GIS availability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]

GW_RAW = ROOT / "data" / "raw" / "arpa" / "groundwater_pavia.xlsx"
GW_META = ROOT / "data" / "processed" / "publication_groundwater" / "groundwater_station_metadata.csv"
RICE_GEO = ROOT / "data" / "processed" / "publication_groundwater" / "ricefloodit_georef.csv"

BASE = ROOT / "data" / "design_c"
RAW_DIR = BASE / "raw"
OUT_DIR = ROOT / "outputs" / "diagnostics" / "design_c"
SIDRO_RAW_DIR = RAW_DIR / "sidro"
SENTINEL_DIR = RAW_DIR / "sentinel1"
RIRU_DIR = RAW_DIR / "riru_sibiter"

for p in [RAW_DIR, OUT_DIR, SIDRO_RAW_DIR, SENTINEL_DIR, RIRU_DIR]:
    p.mkdir(parents=True, exist_ok=True)

SIDRO_REGISTRY_URL = "https://idro.arpalombardia.it/manual/AnagraficaSensoriWEB.csv"
STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"

START_YEAR = 2015
END_YEAR = 2023
RICE_MONTHS = (4, 5, 6, 7, 8, 9)
BBOX_MARGIN_DEG = 0.10

UTM32_TO_WGS84 = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    req = Request(url, headers={"User-Agent": "DesignC-C1-public-audit/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def classify_aquifer(gwb: pd.Series) -> pd.Series:
    s = gwb.astype("string")
    return np.select(
        [
            s.str.startswith("GWB ISS", na=False),
            s.str.startswith("GWB ISI", na=False),
            s.str.startswith("GWB ISP", na=False),
        ],
        ["ISS", "ISI", "ISP"],
        default="OTHER",
    )


def study_bbox() -> tuple[float, float, float, float]:
    d = pd.read_csv(RICE_GEO)
    if not {"lon", "lat"}.issubset(d.columns):
        raise AssertionError("ricefloodit_georef.csv must contain lon and lat.")
    return (
        float(d["lon"].min()) - BBOX_MARGIN_DEG,
        float(d["lat"].min()) - BBOX_MARGIN_DEG,
        float(d["lon"].max()) + BBOX_MARGIN_DEG,
        float(d["lat"].max()) + BBOX_MARGIN_DEG,
    )


def prepare_groundwater() -> pd.DataFrame:
    raw = pd.read_excel(GW_RAW)
    req = {"CODICE", "Data", "Soggiacenza m da Qr", "GroundWater Body (GWB_2015)"}
    missing = req - set(raw.columns)
    if missing:
        raise AssertionError(f"Missing groundwater fields: {sorted(missing)}")

    d = raw.rename(
        columns={
            "CODICE": "station",
            "Data": "date",
            "Soggiacenza m da Qr": "gw_depth_m",
            "GroundWater Body (GWB_2015)": "gwb",
        }
    ).copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["gw_depth_m"] = pd.to_numeric(d["gw_depth_m"], errors="coerce")
    d["aquifer_group"] = classify_aquifer(d["gwb"])

    d = d.loc[
        d["aquifer_group"].eq("ISS")
        & d["date"].dt.year.between(START_YEAR, END_YEAR)
    ].copy()

    # Same conservative duplicate logic as the frozen groundwater pipeline.
    g = d.groupby(["station", "date"], dropna=False)
    dup = pd.concat(
        [
            g.size().rename("rows"),
            g["gw_depth_m"].nunique(dropna=False).rename("n_unique_depth"),
        ],
        axis=1,
    ).reset_index()
    conflicts = dup.loc[
        (dup["rows"] > 1) & (dup["n_unique_depth"] > 1),
        ["station", "date"],
    ]
    keys = pd.MultiIndex.from_frame(d[["station", "date"]])
    conflict_keys = pd.MultiIndex.from_frame(conflicts)
    d = d.loc[~keys.isin(conflict_keys)].copy()
    d = d.sort_values(["station", "date"]).drop_duplicates(["station", "date"])

    d["year"] = d["date"].dt.year.astype(int)
    d["month"] = d["date"].dt.month.astype(int)
    d["rice_season"] = d["month"].isin(RICE_MONTHS)
    return d


def audit_groundwater():
    d = prepare_groundwater()

    meta = pd.read_csv(GW_META)
    meta_keep = [
        c for c in [
            "station", "utm_e", "utm_n", "measuring_point_elev_masl",
            "well_depth_m", "screen_top_m", "screen_bottom_m", "gwb"
        ] if c in meta.columns
    ]
    meta = meta[meta_keep].drop_duplicates("station")

    sy = []
    for (station, year), s in d.groupby(["station", "year"]):
        rs = s.loc[s["rice_season"]].sort_values("date")
        dates = rs["date"]
        gaps = dates.diff().dt.days.dropna()
        months = sorted(rs["month"].unique())

        sy.append({
            "station": station,
            "year": int(year),
            "annual_obs_n": int(len(s)),
            "rice_season_obs_n": int(len(rs)),
            "rice_season_months_n": int(len(months)),
            "rice_season_months": "_".join(map(str, months)),
            "rice_season_first_date": (
                dates.min().date().isoformat() if len(dates) else None
            ),
            "rice_season_last_date": (
                dates.max().date().isoformat() if len(dates) else None
            ),
            "rice_season_median_gap_days": (
                float(gaps.median()) if len(gaps) else np.nan
            ),
            "has_apr_sep_all_6_months": set(RICE_MONTHS).issubset(set(months)),
            "has_at_least_4_rice_months": len(months) >= 4,
        })

    sy = pd.DataFrame(sy).sort_values(["station", "year"])
    sy.to_csv(
        OUT_DIR / "c1_public_groundwater_rice_season_by_station_year.csv",
        index=False,
    )

    rows = []
    for station, s in d.groupby("station"):
        dates = s["date"].sort_values()
        gaps = dates.diff().dt.days.dropna()
        years = sorted(s["year"].unique())
        yearly_n = s.groupby("year").size()

        rice = sy.loc[sy["station"].eq(station)]
        full6 = int(rice["has_apr_sep_all_6_months"].sum())
        ge4 = int(rice["has_at_least_4_rice_months"].sum())

        rows.append({
            "station": station,
            "start_date": dates.min().date().isoformat(),
            "end_date": dates.max().date().isoformat(),
            "observations_n": int(len(s)),
            "years_observed_n": int(len(years)),
            "years_observed": "_".join(map(str, years)),
            "median_obs_per_year": float(yearly_n.median()),
            "median_gap_days": float(gaps.median()) if len(gaps) else np.nan,
            "rice_season_obs_n": int(s["rice_season"].sum()),
            "median_rice_season_obs_per_year": float(
                rice["rice_season_obs_n"].median()
            ),
            "median_rice_season_months_per_year": float(
                rice["rice_season_months_n"].median()
            ),
            "years_with_all_apr_sep_months": full6,
            "years_with_at_least_4_rice_months": ge4,
            "has_all_2015_2023_years": set(range(START_YEAR, END_YEAR + 1)).issubset(years),
        })

    station = pd.DataFrame(rows).merge(meta, on="station", how="left", validate="one_to_one")
    station = station.sort_values(
        ["years_observed_n", "median_rice_season_months_per_year", "observations_n"],
        ascending=[False, False, False],
    )
    station.to_csv(
        OUT_DIR / "c1_public_groundwater_native_cadence_by_station.csv",
        index=False,
    )

    year = (
        d.groupby("year")
        .agg(
            observations_n=("station", "size"),
            stations_n=("station", "nunique"),
            months_with_any_obs=("month", "nunique"),
            rice_season_observations_n=("rice_season", "sum"),
            rice_season_stations_n=("station", lambda x: x[d.loc[x.index, "rice_season"]].nunique()),
        )
        .reset_index()
    )

    # Add well-year quality counts.
    q = (
        sy.groupby("year")
        .agg(
            station_years_with_all_6_rice_months=("has_apr_sep_all_6_months", "sum"),
            station_years_with_at_least_4_rice_months=("has_at_least_4_rice_months", "sum"),
        )
        .reset_index()
    )
    year = year.merge(q, on="year", how="left")
    year.to_csv(
        OUT_DIR / "c1_public_groundwater_native_cadence_by_year.csv",
        index=False,
    )

    return d, station, sy, year


def parse_sidro_registry(bbox):
    raw_path = SIDRO_RAW_DIR / "AnagraficaSensoriWEB.csv"
    raw_path.write_bytes(fetch_bytes(SIDRO_REGISTRY_URL))

    choices = []
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        for sep in [";", ",", "\t"]:
            try:
                x = pd.read_csv(raw_path, encoding=enc, sep=sep)
                if x.shape[1] >= 4:
                    choices.append((x.shape[1], enc, sep, x))
            except Exception:
                pass
    if not choices:
        raise AssertionError("Unable to parse SIDRO registry.")
    _, enc, sep, d = max(choices, key=lambda z: z[0])
    d.columns = [str(c).strip().replace("\n", " ") for c in d.columns]

    lower = {c: c.lower() for c in d.columns}

    # 1. Try explicit decimal longitude/latitude.
    lon_cols = [c for c in d.columns if "long" in lower[c] or lower[c] in {"lon", "longitude"}]
    lat_cols = [c for c in d.columns if "lat" in lower[c] or lower[c] == "latitude"]

    best = None
    for xc in lon_cols:
        for yc in lat_cols:
            x = pd.to_numeric(d[xc].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            y = pd.to_numeric(d[yc].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            ok = x.between(7, 12) & y.between(44, 47)
            if best is None or int(ok.sum()) > best[0]:
                best = (int(ok.sum()), "WGS84", xc, yc, x, y)

    # 2. Try UTM32 fields, including common Italian labels.
    east_terms = ["utm_est", "utm est", "est", "easting", "x_utm", "utm_e"]
    north_terms = ["utm_nrd", "utm nrd", "nord", "northing", "y_utm", "utm_n"]

    e_cols = [
        c for c in d.columns
        if any(t == lower[c] or t in lower[c] for t in east_terms)
    ]
    n_cols = [
        c for c in d.columns
        if any(t == lower[c] or t in lower[c] for t in north_terms)
    ]

    for ec in e_cols:
        for nc in n_cols:
            e = pd.to_numeric(d[ec].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            n = pd.to_numeric(d[nc].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            plausible = e.between(200000, 900000) & n.between(4_800_000, 5_300_000)
            score = int(plausible.sum())
            if score == 0:
                continue
            lon = pd.Series(np.nan, index=d.index, dtype=float)
            lat = pd.Series(np.nan, index=d.index, dtype=float)
            ii = plausible.to_numpy()
            lo, la = UTM32_TO_WGS84.transform(e.loc[plausible].to_numpy(), n.loc[plausible].to_numpy())
            lon.loc[plausible] = lo
            lat.loc[plausible] = la

            if best is None or score > best[0]:
                best = (score, "EPSG:32632", ec, nc, lon, lat)

    if best is None or best[0] == 0:
        raise AssertionError(
            "SIDRO registry parsed, but no plausible WGS84 or EPSG:32632 coordinate pair was found. "
            f"Columns were: {list(d.columns)}"
        )

    score, crs_mode, xcol, ycol, lon, lat = best
    d["_lon_wgs84"] = lon
    d["_lat_wgs84"] = lat

    minx, miny, maxx, maxy = bbox
    nearby = d.loc[
        d["_lon_wgs84"].between(minx, maxx)
        & d["_lat_wgs84"].between(miny, maxy)
    ].copy()

    d.to_csv(OUT_DIR / "c1_public_sidro_registry_normalized.csv", index=False)
    nearby.to_csv(OUT_DIR / "c1_public_sidro_sensors_near_study_area.csv", index=False)

    pd.DataFrame([{
        "encoding": enc,
        "separator_repr": repr(sep),
        "coordinate_mode": crs_mode,
        "source_x_column": xcol,
        "source_y_column": ycol,
        "plausible_coordinate_rows": score,
        "registry_rows": len(d),
        "nearby_rows": len(nearby),
        "raw_sha256": sha256(raw_path),
    }]).to_csv(
        OUT_DIR / "c1_public_sidro_registry_parse_qa.csv",
        index=False,
    )

    return d, nearby, crs_mode, xcol, ycol


def query_stac(bbox):
    params = {
        "collections": "sentinel-1-grd",
        "bbox": ",".join(f"{x:.8f}" for x in bbox),
        "datetime": f"{START_YEAR}-01-01T00:00:00Z/{END_YEAR}-12-31T23:59:59Z",
        "limit": 1000,
    }
    url = STAC_SEARCH_URL + "?" + urlencode(params)
    features = []

    while url:
        payload = json.loads(fetch_bytes(url))
        features.extend(payload.get("features", []))
        next_url = None
        for link in payload.get("links", []):
            if link.get("rel") == "next":
                if str(link.get("method", "GET")).upper() != "GET":
                    raise RuntimeError("Non-GET STAC pagination; refusing possible truncation.")
                next_url = link.get("href")
                break
        url = next_url

    rows = []
    for f in features:
        p = f.get("properties", {})
        rows.append({
            "scene_id": f.get("id"),
            "datetime": p.get("datetime") or p.get("start_datetime"),
            "instrument_mode": p.get("sar:instrument_mode"),
            "polarizations": "|".join(map(str, p.get("sar:polarizations", []) or [])),
            "orbit_state": p.get("sat:orbit_state"),
            "relative_orbit": p.get("sat:relative_orbit"),
        })

    d = pd.DataFrame(rows)
    if len(d):
        d["datetime"] = pd.to_datetime(d["datetime"], errors="coerce", utc=True)
        d["date"] = d["datetime"].dt.date.astype(str)
        d["year"] = d["datetime"].dt.year
        d = d.drop_duplicates("scene_id").sort_values(["datetime", "scene_id"])

    d.to_csv(SENTINEL_DIR / "sentinel1_grd_scene_inventory_2015_2023.csv", index=False)

    annual = (
        d.groupby("year")
        .agg(scenes_n=("scene_id", "nunique"), acquisition_dates_n=("date", "nunique"))
        .reset_index()
        if len(d)
        else pd.DataFrame(columns=["year", "scenes_n", "acquisition_dates_n"])
    )
    annual.to_csv(OUT_DIR / "c1_public_sentinel1_inventory_by_year.csv", index=False)
    return d


def main():
    bbox = study_bbox()
    gw, station, sy, year = audit_groundwater()
    sidro, sidro_near, sidro_crs, sidro_x, sidro_y = parse_sidro_registry(bbox)
    s1 = query_stac(bbox)

    # Descriptive support counts only; not a frozen scientific sample definition.
    all9 = int(station["has_all_2015_2023_years"].sum())
    rice4_median = int((station["median_rice_season_months_per_year"] >= 4).sum())
    rice5_median = int((station["median_rice_season_months_per_year"] >= 5).sum())
    all9_rice4 = int(
        (
            station["has_all_2015_2023_years"]
            & (station["median_rice_season_months_per_year"] >= 4)
        ).sum()
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C1_PUBLIC_AVAILABILITY_AUDIT_REV2",
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "window": [START_YEAR, END_YEAR],
        "groundwater": {
            "native_observations_n": int(len(gw)),
            "iss_stations_n": int(station["station"].nunique()),
            "stations_all_9_years": all9,
            "stations_median_ge4_rice_months_per_year": rice4_median,
            "stations_median_ge5_rice_months_per_year": rice5_median,
            "all9year_stations_median_ge4_rice_months": all9_rice4,
        },
        "sentinel1": {
            "scenes_n": int(len(s1)),
            "unique_dates_n": int(s1["date"].nunique()) if len(s1) else 0,
        },
        "sidro": {
            "registry_rows": int(len(sidro)),
            "nearby_rows": int(len(sidro_near)),
            "coordinate_mode": sidro_crs,
            "source_x_column": sidro_x,
            "source_y_column": sidro_y,
        },
        "rirusibiter": {
            "public_availability": True,
            "topology_validation_pending": True,
        },
    }
    (OUT_DIR / "c1_public_availability_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )

    summary = f"""DESIGN C — C1 PUBLIC AVAILABILITY AUDIT REVISION 2
====================================================

NO association model fitted.
NO frozen artifact modified.

GROUNDWATER 2015-2023
---------------------
Native ISS observations: {len(gw)}
ISS wells: {station['station'].nunique()}
Wells present all 9 years: {all9}
Wells with median >=4 Apr-Sep months/year: {rice4_median}
Wells with median >=5 Apr-Sep months/year: {rice5_median}
All-9-year wells with median >=4 Apr-Sep months/year: {all9_rice4}

SENTINEL-1
----------
Scenes: {len(s1)}
Unique acquisition dates: {s1['date'].nunique() if len(s1) else 0}

SIDRO
-----
Registry rows: {len(sidro)}
Coordinate interpretation: {sidro_crs}
Coordinate source columns: {sidro_x} / {sidro_y}
Sensors inside study bbox: {len(sidro_near)}

RIRU / SIBITER
--------------
Public availability: CONFIRMED
Topology validation: PENDING

NEXT
----
1. Inspect rice-season well support.
2. Inspect nearby SIDRO sensor types and dates.
3. Acquire RIRU/SIBITER raw GIS with provenance.
4. Search public Est Sesia historical discharge before sending a request.
5. Still NO Design-C groundwater-association model.

C1 PUBLIC AVAILABILITY AUDIT REV2: PASS
"""
    (OUT_DIR / "c1_public_availability_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()

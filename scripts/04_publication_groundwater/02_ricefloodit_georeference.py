"""Georeference RiceFloodIT FFavg using the MODIS sinusoidal grid and audit alignment.

Run from repository root:
    python scripts/04_publication_groundwater/02_ricefloodit_georeference.py

This implements the numerically supported MODIS sinusoidal interpretation of the ffavg x/y
coordinates. Publication use still requires an authoritative-source CRS verification gate.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
FF_IN = ROOT / "data/raw/RiceFloodIT/ffavg_2021.csv"
GW_META = ROOT / "data/processed/publication_groundwater/groundwater_station_metadata.csv"
OUT = ROOT / "data/processed/publication_groundwater/ricefloodit_georef.csv"
QA_OUT = ROOT / "outputs/diagnostics/publication_groundwater/ricefloodit_georef_qa.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
QA_OUT.parent.mkdir(parents=True, exist_ok=True)

MODIS_SINU = CRS.from_proj4("+proj=sinu +R=6371007.181 +nadgrids=@null +wktext")
UTM32 = CRS.from_epsg(32632)
WGS84 = CRS.from_epsg(4326)


def main() -> None:
    ff = pd.read_csv(FF_IN)
    req = {"x", "y", "subdistrict", "year", "ff", "count"}
    if missing := req.difference(ff.columns):
        raise ValueError(f"RiceFloodIT missing required columns: {sorted(missing)}")

    unique = ff[["x", "y"]].drop_duplicates().copy()
    to_utm = Transformer.from_crs(MODIS_SINU, UTM32, always_xy=True)
    to_ll = Transformer.from_crs(MODIS_SINU, WGS84, always_xy=True)
    unique["utm_e"], unique["utm_n"] = to_utm.transform(unique["x"].to_numpy(), unique["y"].to_numpy())
    unique["lon"], unique["lat"] = to_ll.transform(unique["x"].to_numpy(), unique["y"].to_numpy())
    ff = ff.merge(unique, on=["x", "y"], how="left", validate="many_to_one")

    nyears = ff.groupby(["x", "y"])["year"].nunique()
    balanced = nyears[nyears == ff["year"].nunique()].rename("balanced_pixel").reset_index()
    balanced["balanced_pixel"] = True
    ff = ff.merge(balanced, on=["x", "y"], how="left")
    ff["balanced_pixel"] = ff["balanced_pixel"].fillna(False).astype(bool)
    ff.to_csv(OUT, index=False)

    qa = [
        ("rows", len(ff)),
        ("years", ff["year"].nunique()),
        ("min_year", ff["year"].min()),
        ("max_year", ff["year"].max()),
        ("unique_pixels", len(unique)),
        ("balanced_pixels", int(ff.loc[ff["balanced_pixel"], ["x", "y"]].drop_duplicates().shape[0])),
        ("lon_min", unique["lon"].min()),
        ("lon_max", unique["lon"].max()),
        ("lat_min", unique["lat"].min()),
        ("lat_max", unique["lat"].max()),
        ("utm_e_min", unique["utm_e"].min()),
        ("utm_e_max", unique["utm_e"].max()),
        ("utm_n_min", unique["utm_n"].min()),
        ("utm_n_max", unique["utm_n"].max()),
    ]

    # Original x/y spacing is a strong numerical fingerprint of the MODIS 1-km sinusoidal grid.
    ux = np.sort(ff["x"].unique())
    dx = np.diff(ux)
    dx = dx[dx > 0]
    qa.append(("median_positive_x_spacing_m", float(np.median(dx))))

    if GW_META.exists():
        gw = pd.read_csv(GW_META)
        gw = gw[gw["aquifer_group"] == "ISS"]
        tree = cKDTree(unique[["utm_e", "utm_n"]].to_numpy())
        d, _ = tree.query(gw[["utm_e", "utm_n"]].to_numpy(), k=1)
        qa.extend([
            ("iss_wells_checked", len(gw)),
            ("nearest_pixel_distance_median_km", float(np.median(d) / 1000)),
            ("nearest_pixel_distance_max_km", float(np.max(d) / 1000)),
        ])

    pd.DataFrame(qa, columns=["metric", "value"]).to_csv(QA_OUT, index=False)
    print("RiceFloodIT georeferencing complete")
    for k, v in qa:
        print(f"  {k}: {v}")
    print("NOTE: authoritative original-product CRS verification remains a publication gate.")


if __name__ == "__main__":
    main()

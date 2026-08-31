from __future__ import annotations

import json
from pathlib import Path

from pyproj import CRS, Transformer


ROOT = Path(__file__).resolve().parents[2]

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT = "MOD09A1.061"
PRODUCT_DOI = "10.5067/MODIS/MOD09A1.061"

# Published/reconstructed RiceFloodIT geographic envelope.
LON_MIN = 8.045516319819253
LON_MAX = 9.541490386571809
LAT_MIN = 45.02499838977754
LAT_MAX = 45.59166503617859

MODIS_RADIUS_M = 6371007.181
TILE_SIZE_M = 1111950.5196666666
GLOBAL_X_MIN_M = -20015109.354
GLOBAL_Y_MAX_M = 10007554.677


def modis_tile(lon: float, lat: float) -> tuple[int, int]:
    sinu = CRS.from_proj4(
        f"+proj=sinu +R={MODIS_RADIUS_M} +nadgrids=@null +wktext"
    )

    transformer = Transformer.from_crs(
        "EPSG:4326",
        sinu,
        always_xy=True,
    )

    x, y = transformer.transform(lon, lat)

    h = int((x - GLOBAL_X_MIN_M) // TILE_SIZE_M)
    v = int((GLOBAL_Y_MAX_M - y) // TILE_SIZE_M)

    return h, v


def main() -> None:
    corners = {
        "southwest": (LON_MIN, LAT_MIN),
        "northwest": (LON_MIN, LAT_MAX),
        "southeast": (LON_MAX, LAT_MIN),
        "northeast": (LON_MAX, LAT_MAX),
    }

    tile_results = {
        name: {
            "lon": lon,
            "lat": lat,
            "h": modis_tile(lon, lat)[0],
            "v": modis_tile(lon, lat)[1],
        }
        for name, (lon, lat) in corners.items()
    }

    unique_tiles = sorted(
        {
            (value["h"], value["v"])
            for value in tile_results.values()
        }
    )

    result = {
        "product": PRODUCT,
        "doi": PRODUCT_DOI,
        "initial_development_year": 2021,
        "initial_date_window": [
            "2021-03-01",
            "2021-06-30",
        ],
        "ricefloodit_bbox_wgs84": {
            "lon_min": LON_MIN,
            "lon_max": LON_MAX,
            "lat_min": LAT_MIN,
            "lat_max": LAT_MAX,
        },
        "corner_tiles": tile_results,
        "unique_tiles": [
            {"h": h, "v": v, "name": f"h{h:02d}v{v:02d}"}
            for h, v in unique_tiles
        ],
        "required_reflectance_bands": {
            "red": "sur_refl_b01",
            "nir": "sur_refl_b02",
            "swir2": "sur_refl_b07",
        },
        "indices": {
            "ndvi": "(nir - red) / (nir + red)",
            "ndfi": "(red - swir2) / (red + swir2)",
        },
        "status": (
            "inventory_only_no_satellite_files_downloaded"
        ),
    }

    out_json = OUT_DIR / "modis_inventory_2021.json"

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("MODIS post-2021 inventory")
    print(f"  product: {PRODUCT}")
    print(
        "  period: 2021-03-01 through 2021-06-30"
    )

    print("  unique tiles:")

    for h, v in unique_tiles:
        print(f"    h{h:02d}v{v:02d}")

    print("  required bands:")
    print("    red   = sur_refl_b01")
    print("    nir   = sur_refl_b02")
    print("    swir2 = sur_refl_b07")

    print(f"  wrote: {out_json}")


if __name__ == "__main__":
    main()
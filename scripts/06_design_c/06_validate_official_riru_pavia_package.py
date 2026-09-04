"""Design C — C2B Final Official RIRU / Est Sesia Reconciliation.

This is the corrected, deterministic C2B geometry test based on the actual
official Regione Lombardia PAVIA.zip schema.

AUTHORITATIVE ROLES
-------------------
Corsi_acqua_RIB.shp
    Authoritative watercourse management layer.
    Est Sesia is selected ONLY by:
        GESTIONE == "ASSOCIAZIONE IRRIGAZIONE EST SESIA"

Tratti_idrici.shp
    Detailed unified hydrographic segmentation.
    Used to verify/enrich Est Sesia watercourse provenance through exact
    normalized name matching and SIBITER identifiers.

IMPORTANT
---------
- ALL Est Sesia geometries from Corsi_acqua_RIB are retained, including
  watercourses that do not exact-name-match Tratti_idrici.
- Fuzzy/approximate name matching is NOT used here.
- Unmatched names are explicitly audited rather than silently discarded.
- GeoPackage is used for the validated spatial output to preserve CRS.
- M dimensions may be dropped by GeoPandas/pyogrio; XY coordinates remain
  the basis of the planned 2D spatial linkage.

NO groundwater measurements read.
NO flooding measurements read.
NO association model fitted.
NO frozen Stage-5–8 artifact modified.

Expected input:
    data/design_c/raw/riru_official/PAVIA.zip

Run:
    python scripts/06_design_c/06_validate_official_riru_pavia_package.py
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
import warnings
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ZIP_PATH = (
    ROOT / "data" / "design_c" / "raw" / "riru_official" / "PAVIA.zip"
)
EXTRACT_DIR = (
    ROOT / "data" / "design_c" / "derived_public_archive"
    / "riru_pavia_official"
)
PROCESSED = ROOT / "data" / "design_c" / "processed"
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

PROCESSED.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

EST_SESIA_LABEL = "ASSOCIAZIONE IRRIGAZIONE EST SESIA"
TARGET_CRS = "EPSG:32632"

RIB_REQUIRED = {
    "OBJECTID",
    "NOME_C_ACQ",
    "COD_RIB",
    "FUNZIONE",
    "TIPO_RETIC",
    "GESTIONE",
    "geometry",
}

TRATTI_REQUIRED = {
    "OBJECTID",
    "ID_EL_IDR",
    "ID_TR_IDR",
    "NOME",
    "ID_SIBITER",
    "TRATTI_SIB",
    "COD_RIB",
    "geometry",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_name(value) -> str:
    """Conservative exact-match normalization only.

    Removes accents, case and punctuation differences.
    Does NOT remove semantic words such as CAVO/ROGGIA/COLATORE.
    """
    if pd.isna(value):
        return ""

    s = str(value).strip()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def safe_extract_zip() -> None:
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"Official RIRU Pavia ZIP not found: {ZIP_PATH}"
        )

    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH) as z:
        for info in z.infolist():
            member = Path(info.filename)

            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(
                    f"Unsafe ZIP member rejected: {info.filename}"
                )

            if info.is_dir():
                continue

            dest = (EXTRACT_DIR / member).resolve()
            if EXTRACT_DIR.resolve() not in dest.parents:
                raise RuntimeError(
                    f"ZIP path traversal rejected: {info.filename}"
                )

            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info, "r") as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def read_official_layer(filename: str):
    path = EXTRACT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Required official layer missing: {path}"
        )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        g = gpd.read_file(path)

    warning_text = [str(w.message) for w in caught]
    return g, warning_text


def validate_schema(g: gpd.GeoDataFrame, required: set[str], label: str):
    missing = sorted(required - set(g.columns))
    if missing:
        raise AssertionError(
            f"{label} missing required fields: {missing}"
        )

    if g.crs is None:
        raise AssertionError(f"{label} has no CRS.")

    if g.geometry.isna().any():
        raise AssertionError(
            f"{label} contains null geometries."
        )

    if g.geometry.is_empty.any():
        raise AssertionError(
            f"{label} contains empty geometries."
        )


def clean_xy(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project to EPSG:32632 and force 2D XY geometry.

    This deliberately drops Z/M for distance calculations.
    """
    g = g.to_crs(TARGET_CRS).copy()

    # GeoPandas/Shapely 2: force_2d available through GeoSeries method
    # on recent stacks; fall back through shapely if needed.
    try:
        g["geometry"] = g.geometry.force_2d()
    except AttributeError:
        from shapely import force_2d
        g["geometry"] = g.geometry.map(force_2d)

    return g


def main():
    print("DESIGN C — C2B FINAL OFFICIAL RIRU / EST SESIA RECONCILIATION")
    print("=" * 68)
    print("NO groundwater measurements read.")
    print("NO flooding measurements read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    safe_extract_zip()

    zip_sha = sha256_file(ZIP_PATH)
    zip_bytes = ZIP_PATH.stat().st_size

    rib, rib_warnings = read_official_layer("Corsi_acqua_RIB.shp")
    tratti, tratti_warnings = read_official_layer("Tratti_idrici.shp")

    validate_schema(rib, RIB_REQUIRED, "Corsi_acqua_RIB")
    validate_schema(tratti, TRATTI_REQUIRED, "Tratti_idrici")

    rib_original_crs = rib.crs.to_string()
    tratti_original_crs = tratti.crs.to_string()

    # Authoritative management selection.
    gestione_norm = (
        rib["GESTIONE"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    est = rib.loc[
        gestione_norm.eq(EST_SESIA_LABEL)
    ].copy()

    if len(est) == 0:
        raise AssertionError(
            "No Est Sesia watercourses found using authoritative "
            "GESTIONE field."
        )

    # The management layer should identify each watercourse by name.
    est["name_norm"] = est["NOME_C_ACQ"].map(normalize_name)
    tratti["name_norm"] = tratti["NOME"].map(normalize_name)

    if est["name_norm"].eq("").any():
        raise AssertionError(
            "One or more Est Sesia RIB watercourses lack a usable name."
        )

    tratti_names = set(
        tratti.loc[tratti["name_norm"].ne(""), "name_norm"]
    )

    est["exact_name_in_tratti"] = est["name_norm"].isin(tratti_names)

    matched_names = set(
        est.loc[est["exact_name_in_tratti"], "name_norm"]
    )

    matched_tratti = tratti.loc[
        tratti["name_norm"].isin(matched_names)
    ].copy()

    unmatched_est = est.loc[
        ~est["exact_name_in_tratti"]
    ].copy()

    # Detailed provenance diagnostics.
    matched_tratti["has_id_sibiter"] = (
        pd.to_numeric(
            matched_tratti["ID_SIBITER"],
            errors="coerce",
        ).notna()
    )

    matched_tratti["has_tratti_sib"] = (
        pd.to_numeric(
            matched_tratti["TRATTI_SIB"],
            errors="coerce",
        ).notna()
    )

    # Build a watercourse-level reconciliation table.
    tratti_group = (
        matched_tratti
        .groupby("name_norm", dropna=False)
        .agg(
            detailed_segments_n=("OBJECTID", "size"),
            detailed_segments_with_id_sibiter_n=("has_id_sibiter", "sum"),
            detailed_segments_with_tratti_sib_n=("has_tratti_sib", "sum"),
            unique_id_sibiter_n=("ID_SIBITER", "nunique"),
            unique_id_tr_idr_n=("ID_TR_IDR", "nunique"),
        )
        .reset_index()
    )

    recon = est[
        [
            "OBJECTID",
            "NOME_C_ACQ",
            "FUNZIONE",
            "TIPO_RETIC",
            "GESTIONE",
            "COD_RIB",
            "name_norm",
            "exact_name_in_tratti",
        ]
    ].merge(
        tratti_group,
        on="name_norm",
        how="left",
        validate="one_to_one",
    )

    numeric_fill = [
        "detailed_segments_n",
        "detailed_segments_with_id_sibiter_n",
        "detailed_segments_with_tratti_sib_n",
        "unique_id_sibiter_n",
        "unique_id_tr_idr_n",
    ]
    for c in numeric_fill:
        recon[c] = recon[c].fillna(0).astype(int)

    # Reproject to explicit 2D UTM32 for downstream spatial linkage.
    est_utm = clean_xy(est)
    matched_tratti_utm = clean_xy(matched_tratti)

    # Hard coordinate plausibility gates.
    for label, g in [
        ("Est Sesia RIB", est_utm),
        ("matched Tratti_idrici", matched_tratti_utm),
    ]:
        if len(g) == 0:
            continue

        minx, miny, maxx, maxy = map(float, g.total_bounds)

        if not (
            200000 <= minx <= 900000
            and 200000 <= maxx <= 900000
            and 4_700_000 <= miny <= 5_400_000
            and 4_700_000 <= maxy <= 5_400_000
        ):
            raise AssertionError(
                f"{label} has implausible EPSG:32632 bounds: "
                f"{(minx, miny, maxx, maxy)}"
            )

    # Preserve ALL authoritative Est Sesia management geometries.
    gpkg = PROCESSED / "official_riru_est_sesia_network.gpkg"
    if gpkg.exists():
        gpkg.unlink()

    est_out_cols = [
        "OBJECTID",
        "NOME_C_ACQ",
        "FUNZIONE",
        "TIPO_RETIC",
        "GESTIONE",
        "COD_RIB",
        "name_norm",
        "exact_name_in_tratti",
        "geometry",
    ]
    est_utm[est_out_cols].to_file(
        gpkg,
        layer="est_sesia_watercourses",
        driver="GPKG",
    )

    if len(matched_tratti_utm):
        matched_cols = [
            "OBJECTID",
            "ID_EL_IDR",
            "ID_TR_IDR",
            "NOME",
            "ID_SIBITER",
            "TRATTI_SIB",
            "COD_RIB",
            "name_norm",
            "has_id_sibiter",
            "has_tratti_sib",
            "geometry",
        ]
        matched_tratti_utm[matched_cols].to_file(
            gpkg,
            layer="matched_detailed_tratti",
            driver="GPKG",
        )

    # Tabular outputs.
    recon.to_csv(
        OUT / "c2b_est_sesia_official_reconciliation.csv",
        index=False,
    )

    unmatched_est[
        [
            "OBJECTID",
            "NOME_C_ACQ",
            "FUNZIONE",
            "TIPO_RETIC",
            "GESTIONE",
            "COD_RIB",
            "name_norm",
        ]
    ].to_csv(
        OUT / "c2b_est_sesia_unmatched_names.csv",
        index=False,
    )

    matched_tratti[
        [
            "OBJECTID",
            "ID_EL_IDR",
            "ID_TR_IDR",
            "NOME",
            "ID_SIBITER",
            "TRATTI_SIB",
            "COD_RIB",
            "name_norm",
            "has_id_sibiter",
            "has_tratti_sib",
        ]
    ].to_csv(
        OUT / "c2b_est_sesia_matched_detailed_tratti.csv",
        index=False,
    )

    matched_watercourses_n = int(est["exact_name_in_tratti"].sum())
    unmatched_watercourses_n = int((~est["exact_name_in_tratti"]).sum())

    matched_segments_n = int(len(matched_tratti))
    sibiter_segments_n = int(matched_tratti["has_id_sibiter"].sum())
    tratti_sib_segments_n = int(
        matched_tratti["has_tratti_sib"].sum()
    )
    unique_sibiter_ids_n = int(
        matched_tratti["ID_SIBITER"].nunique(dropna=True)
    )

    exact_coverage = (
        matched_watercourses_n / len(est)
        if len(est) else np.nan
    )

    est_bounds = tuple(
        round(float(x), 3) for x in est_utm.total_bounds
    )

    # PASS refers to acquisition/reconciliation integrity, NOT to 100%
    # exact-name linkage. Unmatched names are deliberately retained.
    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2B_FINAL_OFFICIAL_RIRU_EST_SESIA_RECONCILIATION",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "zip_sha256": zip_sha,
        "zip_bytes": zip_bytes,
        "rib_original_crs": rib_original_crs,
        "tratti_original_crs": tratti_original_crs,
        "processed_crs": TARGET_CRS,
        "rib_features_n": int(len(rib)),
        "tratti_features_n": int(len(tratti)),
        "est_sesia_management_watercourses_n": int(len(est)),
        "est_sesia_unique_names_n": int(
            est["NOME_C_ACQ"].nunique(dropna=True)
        ),
        "est_sesia_cod_rib_nonnull_n": int(
            est["COD_RIB"].notna().sum()
        ),
        "exact_name_matched_watercourses_n": matched_watercourses_n,
        "exact_name_unmatched_watercourses_n": unmatched_watercourses_n,
        "exact_name_match_fraction": float(exact_coverage),
        "matched_detailed_segments_n": matched_segments_n,
        "matched_segments_with_id_sibiter_n": sibiter_segments_n,
        "matched_segments_with_tratti_sib_n": tratti_sib_segments_n,
        "unique_id_sibiter_n": unique_sibiter_ids_n,
        "authoritative_est_sesia_geometry_features_n": int(len(est_utm)),
        "authoritative_est_sesia_geometry_bounds_epsg32632": est_bounds,
        "authoritative_geometry_includes_unmatched_names": True,
        "fuzzy_matching_used": False,
        "rib_read_warnings": rib_warnings,
        "tratti_read_warnings": tratti_warnings,
        "M_dimension_policy": (
            "M/Z dimensions are not used downstream; processed output "
            "is explicitly forced to 2D XY in EPSG:32632."
        ),
        "authoritative_geometry_output": str(
            gpkg.relative_to(ROOT)
        ),
    }

    (OUT / "c2b_final_est_sesia_reconciliation_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = f"""DESIGN C — C2B FINAL OFFICIAL RIRU / EST SESIA RECONCILIATION
================================================================

Official ZIP
------------
SHA256: {zip_sha}
bytes: {zip_bytes:,}

Official schemas
----------------
Corsi_acqua_RIB features: {len(rib)}
Corsi_acqua_RIB CRS: {rib_original_crs}
Tratti_idrici features: {len(tratti)}
Tratti_idrici CRS: {tratti_original_crs}

Authoritative Est Sesia management selection
--------------------------------------------
GESTIONE = {EST_SESIA_LABEL}
Est Sesia watercourses: {len(est)}
Unique Est Sesia names: {est['NOME_C_ACQ'].nunique(dropna=True)}
Non-null COD_RIB among Est Sesia watercourses: {est['COD_RIB'].notna().sum()}

Exact normalized-name reconciliation
------------------------------------
Matched Est Sesia watercourses: {matched_watercourses_n}
Unmatched Est Sesia watercourses: {unmatched_watercourses_n}
Exact-name coverage: {exact_coverage:.3%}

Detailed Tratti_idrici support
------------------------------
Matched detailed segments: {matched_segments_n}
Segments with ID_SIBITER: {sibiter_segments_n}
Segments with TRATTI_SIB: {tratti_sib_segments_n}
Unique ID_SIBITER values: {unique_sibiter_ids_n}

Authoritative downstream geometry
---------------------------------
ALL {len(est_utm)} Est Sesia Corsi_acqua_RIB geometries retained.
Fuzzy matching used: NO
Processed CRS: {TARGET_CRS}
Bounds: {est_bounds}

Output:
  data/design_c/processed/official_riru_est_sesia_network.gpkg
    layer: est_sesia_watercourses
    layer: matched_detailed_tratti

Audit tables:
  c2b_est_sesia_official_reconciliation.csv
  c2b_est_sesia_unmatched_names.csv
  c2b_est_sesia_matched_detailed_tratti.csv
  c2b_final_est_sesia_reconciliation_qa.json

Interpretation
--------------
The RIB management layer is the authoritative Est Sesia geometry source.
Exact-name linkage to Tratti_idrici is provenance/enrichment evidence only;
the unmatched watercourses are NOT dropped from the spatial network.

Groundwater measurements read: 0
Flooding measurements read: 0
Association models fitted: 0
Frozen artifacts modified: 0

C2B FINAL STATUS: PASS
C2C SPATIAL LINKAGE INPUT: READY
"""

    (OUT / "c2b_final_est_sesia_reconciliation_summary.txt").write_text(
        summary,
        encoding="utf-8",
    )

    print(summary)


if __name__ == "__main__":
    main()

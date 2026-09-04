"""Design C — C1B Maximum Public Irrigation Archive Acquisition.

PURPOSE
-------
Acquire and provenance-lock the maximum useful PUBLIC irrigation/hydrology
research archive we can identify before institutional data requests.

This is NOT a modelling script.
It does NOT alter frozen Stage-5–8 data/results.
It does NOT select years based on groundwater associations.

Acquires:
- CeDATeR irrigation-season reports 2020-2025.
- Regione Lombardia public irrigation-methodology/ISIL bundle.
- Regione Lombardia planning/VAS document containing ANBI 2016-2023
  irrigation-withdrawal historical series.
- SIBITER technical specification.
- RIRU WMS capabilities and ArcGIS service metadata.
- CeDATeR / ISIL / monitoring / SIGRIAN public reference pages.
- A machine-readable provenance manifest with SHA-256 checksums.

It intentionally does NOT download:
- bulk Sentinel-1 rasters;
- authenticated CeDATeR/SIGRIAN data;
- anything requiring credentials;
- current Est Sesia unvalidated instrument feeds as scientific observations.

Run from repository root:
    python scripts/06_design_c/02_acquire_maximum_public_irrigation_archive.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[2]

BASE = ROOT / "data" / "design_c"
RAW = BASE / "raw"
META = BASE / "metadata"
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

DOCS = RAW / "public_irrigation_archive"
CEDATER = DOCS / "cedater_reports"
REGIONE = DOCS / "regione_lombardia"
NETWORK = DOCS / "network_metadata"
REFERENCE = DOCS / "reference_pages"

for p in [RAW, META, OUT, DOCS, CEDATER, REGIONE, NETWORK, REFERENCE]:
    p.mkdir(parents=True, exist_ok=True)


SOURCES = [
    # ---------------------------------------------------------------
    # CeDATeR formal irrigation-season report series.
    # Earliest report series explicitly published = 2020.
    # ---------------------------------------------------------------
    {
        "source_id": "cedater_report_2020",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2020,
        "year_end": 2020,
        "kind": "annual_irrigation_report",
        "url": "https://cedater.anbilombardia.it/wp-content/uploads/2023/03/Report_stagione_irrigua_2020.pdf",
        "relative_path": "cedater_reports/Report_stagione_irrigua_2020.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },
    {
        "source_id": "cedater_report_2021",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2021,
        "year_end": 2021,
        "kind": "annual_irrigation_report",
        "url": "https://cedater.anbilombardia.it/wp-content/uploads/2023/03/Report_stagione_irrigua_2021.pdf",
        "relative_path": "cedater_reports/Report_stagione_irrigua_2021.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },
    {
        "source_id": "cedater_report_2022",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2022,
        "year_end": 2022,
        "kind": "annual_irrigation_report",
        "url": "https://cedater.anbilombardia.it/wp-content/uploads/2023/04/Report_2022_def.pdf",
        "relative_path": "cedater_reports/Report_2022_def.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },
    {
        "source_id": "cedater_report_2023",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2023,
        "year_end": 2023,
        "kind": "annual_irrigation_report",
        "url": "https://cedater.anbilombardia.it/wp-content/uploads/2024/02/Report_2023.pdf",
        "relative_path": "cedater_reports/Report_2023.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },
    {
        "source_id": "cedater_report_2024",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2024,
        "year_end": 2024,
        "kind": "annual_irrigation_report",
        "url": "https://cedater.anbilombardia.it/wp-content/uploads/2025/05/Report_2024.pdf",
        "relative_path": "cedater_reports/Report_2024.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },
    {
        "source_id": "cedater_report_2025",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2025,
        "year_end": 2025,
        "kind": "annual_irrigation_report",
        "url": "https://anbilombardia.it/wp-content/uploads/2026/06/Report_2025.pdf",
        "relative_path": "cedater_reports/Report_2025.pdf",
        "role": "validation_and_historical_context",
        "expected_public": True,
    },

    # ---------------------------------------------------------------
    # Regione Lombardia public methodological / historical materials.
    # The ZIP includes DGR/measurement criteria, estimation methods,
    # national guidelines and the ISIL final report.
    # ---------------------------------------------------------------
    {
        "source_id": "regione_irrigation_isil_bundle",
        "organisation": "Regione Lombardia",
        "year_start": 2015,
        "year_end": 2018,
        "kind": "methodology_and_ISIL_archive",
        "url": "https://www.regione.lombardia.it/content/dam/rl/canali-tematici-servizi/06-ambiente-e-territorio/12-governo-delle-acque/06-irrigazione-e-bonifica/ser-uso-restituzione-rilascio-acqua-uso-irriguo-agr/allegati/Allegati%20%28uso%20irriguo%29.zip",
        "relative_path": "regione_lombardia/Allegati_uso_irriguo.zip",
        "role": "measurement_rules_ISIL_structure_and_methods",
        "expected_public": True,
    },
    {
        "source_id": "regione_pgbi_vas_historical_2016_2023",
        "organisation": "Regione Lombardia",
        "year_start": 2016,
        "year_end": 2023,
        "kind": "planning_report_historical_irrigation_volumes",
        "url": "https://www.regione.lombardia.it/wps/wcm/connect/16e4bdd5-754e-4a85-a744-4de2744db421/22V077_PGBI_Rapporto%2BAmbientale_01.pdf?CACHEID=ROOTWORKSPACE-16e4bdd5-754e-4a85-a744-4de2744db421-pvbDbs6&MOD=AJPERES",
        "relative_path": "regione_lombardia/PGBI_Rapporto_Ambientale_historical_2016_2023.pdf",
        "role": "historical_ANBI_validation_series",
        "expected_public": True,
    },

    # ---------------------------------------------------------------
    # SIBITER / RIRU technical metadata.
    # SIBITER began being assembled from consortium data in 1997.
    # Do not interpret 1997 as a time series start; this is source provenance.
    # ---------------------------------------------------------------
    {
        "source_id": "sibiter_technical_specification",
        "organisation": "Regione Lombardia",
        "year_start": 1997,
        "year_end": 2018,
        "kind": "irrigation_network_technical_specification",
        "url": "https://www.cartografia.servizirl.it/metadata/sibiter/doc/SIBITER.pdf",
        "relative_path": "network_metadata/SIBITER_technical_specification.pdf",
        "role": "network_schema_and_provenance",
        "expected_public": True,
    },
    {
        "source_id": "riru_wms_capabilities",
        "organisation": "Regione Lombardia",
        "year_start": None,
        "year_end": 2026,
        "kind": "RIRU_WMS_capabilities",
        "url": "https://www.cartografia.servizirl.it/arcgis1/services/territorio/ReticoloIdrografico_RIRU/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities",
        "relative_path": "network_metadata/RIRU_WMS_GetCapabilities.xml",
        "role": "network_layer_inventory",
        "expected_public": True,
    },
    {
        "source_id": "riru_arcgis_rest_metadata",
        "organisation": "Regione Lombardia",
        "year_start": None,
        "year_end": 2026,
        "kind": "RIRU_ArcGIS_service_metadata",
        "url": "https://www.cartografia.servizirl.it/arcgis1/rest/services/territorio/ReticoloIdrografico_RIRU/MapServer?f=pjson",
        "relative_path": "network_metadata/RIRU_MapServer.json",
        "role": "network_layer_inventory",
        "expected_public": True,
    },

    # ---------------------------------------------------------------
    # Public reference pages: preserved HTML snapshots for provenance.
    # ---------------------------------------------------------------
    {
        "source_id": "cedater_reports_index",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2020,
        "year_end": 2025,
        "kind": "reference_page",
        "url": "https://cedater.anbilombardia.it/report/",
        "relative_path": "reference_pages/cedater_reports_index.html",
        "role": "source_provenance",
        "expected_public": True,
    },
    {
        "source_id": "cedater_monitoring_system",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2017,
        "year_end": None,
        "kind": "reference_page",
        "url": "https://cedater.anbilombardia.it/sistema-di-monitoraggio/",
        "relative_path": "reference_pages/cedater_monitoring_system.html",
        "role": "monitoring_system_provenance",
        "expected_public": True,
    },
    {
        "source_id": "cedater_ISIL_project",
        "organisation": "ANBI Lombardia / CeDATeR",
        "year_start": 2015,
        "year_end": 2018,
        "kind": "reference_page",
        "url": "https://cedater.anbilombardia.it/indagine-sui-sistemi-irrigui/",
        "relative_path": "reference_pages/cedater_ISIL_project.html",
        "role": "ISIL_provenance",
        "expected_public": True,
    },
    {
        "source_id": "anbi_ISIL_2017_validation",
        "organisation": "ANBI Lombardia",
        "year_start": 2015,
        "year_end": 2018,
        "kind": "reference_page",
        "url": "https://anbilombardia.it/attivita/progetti/isil/",
        "relative_path": "reference_pages/anbi_ISIL.html",
        "role": "2017_validated_flow_volume_provenance",
        "expected_public": True,
    },
    {
        "source_id": "regione_irrigation_measurement_rules",
        "organisation": "Regione Lombardia",
        "year_start": 2016,
        "year_end": None,
        "kind": "reference_page",
        "url": "https://www.regione.lombardia.it/ambiente-e-territorio/governo-delle-acque/uso,-restituzione-e-rilascio-acqua-a-uso-irriguo",
        "relative_path": "reference_pages/regione_irrigation_measurement_rules.html",
        "role": "legal_and_measurement_provenance",
        "expected_public": True,
    },
    {
        "source_id": "sigrian_data_description",
        "organisation": "CREA-PB / SIGRIAN",
        "year_start": 2015,
        "year_end": None,
        "kind": "reference_page",
        "url": "https://sigrian.crea.gov.it/index.php/dati/",
        "relative_path": "reference_pages/SIGRIAN_data_description.html",
        "role": "national_irrigation_data_provenance",
        "expected_public": True,
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, timeout: int = 180) -> tuple[bytes, dict]:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "UNIMI-DesignC-public-research-archive/1.0 "
                "(academic reproducibility acquisition)"
            )
        },
    )
    with urlopen(req, timeout=timeout) as r:
        data = r.read()
        headers = {
            "final_url": r.geturl(),
            "content_type": r.headers.get("Content-Type"),
            "content_length_header": r.headers.get("Content-Length"),
            "last_modified": r.headers.get("Last-Modified"),
            "etag": r.headers.get("ETag"),
        }
    return data, headers


def main() -> None:
    manifest_rows = []
    failures = []

    print("DESIGN C — C1B MAXIMUM PUBLIC IRRIGATION ARCHIVE")
    print("=" * 58)
    print("No scientific association model will be fitted.")
    print("Acquiring authoritative PUBLIC source material only.\n")

    for i, src in enumerate(SOURCES, 1):
        dest = DOCS / src["relative_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{i:02d}/{len(SOURCES):02d}] {src['source_id']}")

        row = dict(src)
        row.update({
            "acquisition_utc": now_utc(),
            "status": None,
            "local_path": str(dest.relative_to(ROOT)),
            "bytes": None,
            "sha256": None,
            "content_type": None,
            "final_url": None,
            "last_modified": None,
            "etag": None,
            "error": None,
        })

        try:
            data, hdr = fetch(src["url"])
            dest.write_bytes(data)
            row.update({
                "status": "ACQUIRED",
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "content_type": hdr["content_type"],
                "final_url": hdr["final_url"],
                "last_modified": hdr["last_modified"],
                "etag": hdr["etag"],
            })
            print(f"  ACQUIRED {len(data):,} bytes")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            row["status"] = "FAILED_PUBLIC_FETCH"
            row["error"] = repr(exc)
            failures.append(src["source_id"])
            print(f"  FAILED: {exc}")

        manifest_rows.append(row)

    manifest_csv = META / "c1b_maximum_public_irrigation_archive_manifest.csv"
    fields = list(manifest_rows[0].keys())
    with manifest_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(manifest_rows)

    acquired = [r for r in manifest_rows if r["status"] == "ACQUIRED"]

    # Temporal horizon table: critical distinction between actual series
    # availability and provenance-vintage information.
    horizon = [
        {
            "stream": "SIBITER source construction/provenance",
            "earliest_publicly_documented_year": 1997,
            "latest_publicly_documented_year": 2018,
            "is_time_series": False,
            "interpretation": "Network database assembled from consortium data since 1997; not annual observations.",
        },
        {
            "stream": "ISIL irrigation-system survey",
            "earliest_publicly_documented_year": 2015,
            "latest_publicly_documented_year": 2018,
            "is_time_series": False,
            "interpretation": "Local/regional irrigation-system survey; ~3000 irrigation units, inflow/source/method attributes.",
        },
        {
            "stream": "Sentinel-1 GRD",
            "earliest_publicly_documented_year": 2014,
            "latest_publicly_documented_year": None,
            "is_time_series": True,
            "interpretation": "Archive begins Oct 2014; exact usable Lomellina inventory handled by C1 auditor.",
        },
        {
            "stream": "Validated irrigation flow/volume collection under ISIL",
            "earliest_publicly_documented_year": 2017,
            "latest_publicly_documented_year": 2017,
            "is_time_series": True,
            "interpretation": "ANBI states 2017 irrigation-season data were acquired, validated and transmitted to SIGRIAN.",
        },
        {
            "stream": "Regional/ANBI seasonal withdrawal historical series",
            "earliest_publicly_documented_year": 2016,
            "latest_publicly_documented_year": 2023,
            "is_time_series": True,
            "interpretation": "PGBI/VAS preserves regional totals; 2016-2019 from ANBI and 2020-2023 from annual reports.",
        },
        {
            "stream": "CeDATeR formal annual irrigation reports",
            "earliest_publicly_documented_year": 2020,
            "latest_publicly_documented_year": 2025,
            "is_time_series": True,
            "interpretation": "Annual Apr-Sep reports; validation/context rather than gauge-level primary exposure.",
        },
        {
            "stream": "CeDATeR regional monitoring system",
            "earliest_publicly_documented_year": 2017,
            "latest_publicly_documented_year": None,
            "is_time_series": True,
            "interpretation": "Monitoring infrastructure operational from 2017; public bulk gauge history not assumed.",
        },
    ]
    horizon_csv = META / "c1b_public_temporal_horizon_register.csv"
    with horizon_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(horizon[0].keys()))
        w.writeheader()
        w.writerows(horizon)

    qa = {
        "status": "PASS_WITH_FETCH_FAILURES" if failures else "PASS",
        "stage": "DESIGN_C_C1B_MAXIMUM_PUBLIC_IRRIGATION_ARCHIVE",
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "sources_attempted_n": len(SOURCES),
        "sources_acquired_n": len(acquired),
        "sources_failed_n": len(failures),
        "failed_source_ids": failures,
        "rules": {
            "maximum_public_horizon": True,
            "no_latest_year_restriction": True,
            "no_authenticated_data": True,
            "no_bulk_sentinel_rasters": True,
            "no_unvalidated_est_sesia_feed_as_primary_data": True,
        },
    }
    (OUT / "c1b_maximum_public_archive_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )

    summary = f"""DESIGN C — C1B MAXIMUM PUBLIC IRRIGATION ARCHIVE
==================================================

Sources attempted: {len(SOURCES)}
Sources acquired: {len(acquired)}
Sources failed: {len(failures)}

Earliest useful public horizons found:
- Sentinel-1: October 2014 onward.
- ISIL irrigation-system survey: 2015-2018.
- Regional irrigation-volume rules/data framework: 2016 onward.
- ANBI validated flow/volume collection explicitly documented for 2017.
- Regional historical seasonal withdrawals preserved for 2016-2023.
- CeDATeR monitoring infrastructure: 2017 onward.
- CeDATeR annual reports: 2020-2025.
- SIBITER database provenance reaches back to consortium inputs from 1997
  (NOT a 1997-present time series).

Important:
Older years are retained whenever an authoritative public source supports them.
No year is excluded because it is 'too old'.
Later C2 validation will decide comparability and usable overlap.

Association models fitted: 0
Frozen artifacts modified: 0

Failed source IDs:
{chr(10).join("- " + x for x in failures) if failures else "- none"}

Next:
1. Inspect downloaded archive and manifest.
2. Unpack the Regione ISIL/methodology bundle read-only.
3. Inventory RIRU layers from service metadata.
4. Determine whether public sources expose gauge/irrigation-unit-level time series.
5. Only request institutional data for gaps that remain.

C1B STATUS: {qa['status']}
"""
    (OUT / "c1b_maximum_public_archive_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print("\n" + summary)


if __name__ == "__main__":
    main()

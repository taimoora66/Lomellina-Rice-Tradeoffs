"""Design C — C2G Public Time-Series Acquisition Feasibility Audit.

PURPOSE
-------
Determine, outcome-blind, which manually verified irrigation-flow series
can actually be accessed through public authoritative web endpoints today.

This stage DOES NOT:
- read groundwater measurements;
- read flooding measurements;
- fit any association model;
- alter any frozen publication artifact;
- assume that a publicly visible current reading implies a downloadable
  historical archive.

Manually verified ISIL historical-series evidence
--------------------------------------------------
Roggione di Sartirana:
    AIES historical series, 01/01/2005–31/12/2014.

Roggia Vecchia:
    AIES historical series, 01/01/2005–31/12/2014.

Naviglio Langosco:
    Consorzio del Ticino historical series, 01/06/1957–30/11/2015.

Roggia Magna e Castellana:
    Consorzio del Ticino total historical coverage,
    01/04/1999–31/05/2015; AIES component 2005–2014.

Outputs
-------
outputs/diagnostics/design_c/c2g_public_endpoint_audit.csv
outputs/diagnostics/design_c/c2g_target_series_feasibility.csv
outputs/diagnostics/design_c/c2g_est_sesia_current_snapshot.csv
outputs/diagnostics/design_c/c2g_public_timeseries_feasibility_qa.json
outputs/diagnostics/design_c/c2g_public_timeseries_feasibility_summary.txt
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30

ENDPOINTS = {
    "est_sesia_current_idrometry":
        "https://arc.estsesia.it/idrometria-del-giorno/index.php",
    "cedater_monitoring_system":
        "https://cedater.anbilombardia.it/sistema-di-monitoraggio/",
    "cedater_reports":
        "https://cedater.anbilombardia.it/report/",
    "consorzio_ticino_home":
        "https://ticinoconsorzio.it/",
    "consorzio_ticino_langosco_background":
        "https://ticinoconsorzio.it/dati-idrologici/le-antiche-utenze/",
}

TARGETS = [
    {
        "target": "ROGGIONE DI SARTIRANA",
        "historical_provider": "Associazione Irrigazione Est Sesia",
        "historical_start": "2005-01-01",
        "historical_end": "2014-12-31",
        "historical_document_status": "VISUALLY_VERIFIED_ISIL",
        "public_live_label_terms": ["roggione di sartirana"],
    },
    {
        "target": "NAVIGLIO LANGOSCO",
        "historical_provider": "Consorzio del Ticino",
        "historical_start": "1957-06-01",
        "historical_end": "2015-11-30",
        "historical_document_status": "VISUALLY_VERIFIED_ISIL",
        "public_live_label_terms": [
            "naviglio langosco",
            "naviglio langosco e roggia molinara di galliate",
        ],
    },
    {
        "target": "ROGGIA MAGNA E CASTELLANA",
        "historical_provider": "Consorzio del Ticino / AIES",
        "historical_start": "1999-04-01",
        "historical_end": "2015-05-31",
        "historical_document_status": "VISUALLY_VERIFIED_ISIL",
        "public_live_label_terms": [
            "rogge magna e castellana",
            "roggia magna e castellana",
        ],
    },
    {
        "target": "ROGGIA VECCHIA",
        "historical_provider": "Associazione Irrigazione Est Sesia",
        "historical_start": "2005-01-01",
        "historical_end": "2014-12-31",
        "historical_document_status": "VISUALLY_VERIFIED_ISIL",
        "public_live_label_terms": ["roggia vecchia"],
    },
]


def clean_text(x: str) -> str:
    return re.sub(r"\s+", " ", x or "").strip()


def fetch(name: str, url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 Design-C-public-data-feasibility-audit/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        return {
            "endpoint_name": name,
            "url": url,
            "http_status": int(r.status_code),
            "reachable": bool(r.ok),
            "content_type": r.headers.get("content-type", ""),
            "bytes": int(len(r.content)),
            "text": r.text if r.content else "",
            "error": None,
        }
    except Exception as e:
        return {
            "endpoint_name": name,
            "url": url,
            "http_status": None,
            "reachable": False,
            "content_type": None,
            "bytes": 0,
            "text": "",
            "error": repr(e),
        }


def page_visible_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text(" ", strip=True))


def find_target_context(text: str, terms: list[str], radius: int = 180):
    low = text.lower()
    positions = [low.find(t.lower()) for t in terms if low.find(t.lower()) >= 0]
    if not positions:
        return None
    pos = min(positions)
    return clean_text(text[max(0, pos-radius): min(len(text), pos+500)])


def likely_restricted(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in [
        "accesso alla piattaforma è riservato",
        "accesso alla piattaforma e riservato",
        "area riservata",
        "login",
    ])


def main():
    print("DESIGN C — C2G PUBLIC TIME-SERIES ACQUISITION FEASIBILITY")
    print("=" * 68)
    print("NO groundwater measurements read.")
    print("NO flooding measurements read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    fetched = {}
    endpoint_rows = []

    for name, url in ENDPOINTS.items():
        result = fetch(name, url)
        visible = page_visible_text(result["text"])
        result["visible_text"] = visible
        fetched[name] = result

        endpoint_rows.append({
            "endpoint_name": name,
            "url": url,
            "http_status": result["http_status"],
            "reachable": result["reachable"],
            "content_type": result["content_type"],
            "bytes": result["bytes"],
            "restricted_language_detected": likely_restricted(visible),
            "error": result["error"],
        })

        print(
            f"{name}: "
            + (f"HTTP {result['http_status']}" if result["http_status"] is not None else "REQUEST FAILED")
        )

    endpoint_df = pd.DataFrame(endpoint_rows)
    endpoint_df.to_csv(OUT / "c2g_public_endpoint_audit.csv", index=False)

    est_text = fetched["est_sesia_current_idrometry"]["visible_text"]

    snapshot_rows = []
    feasibility_rows = []

    for t in TARGETS:
        context = find_target_context(est_text, t["public_live_label_terms"])
        live_visible = context is not None

        if live_visible:
            snapshot_rows.append({
                "target": t["target"],
                "source_endpoint": "est_sesia_current_idrometry",
                "source_url": ENDPOINTS["est_sesia_current_idrometry"],
                "target_label_visible": True,
                "context": context,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "validation_status": "PUBLIC_CURRENT_UNVALIDATED_OPERATIONAL_READING",
            })

        if t["target"] == "NAVIGLIO LANGOSCO":
            next_action = (
                "Request/search historical daily diversion series from Consorzio del Ticino, "
                "citing ISIL coverage 1957-06-01 to 2015-11-30."
            )
        elif t["target"] == "ROGGIA MAGNA E CASTELLANA":
            next_action = (
                "Request/search Consorzio del Ticino 1999-04-01 to 2015-05-31 series "
                "and AIES 2005-2014 component; preserve source components separately."
            )
        elif t["target"] == "ROGGIONE DI SARTIRANA":
            next_action = (
                "Request/search AIES daily series 2005-01-01 to 2014-12-31 and ask "
                "whether the current Est Sesia feed has an archive/API."
            )
        else:
            next_action = (
                "Request/search AIES daily Roggia Vecchia series 2005-01-01 to 2014-12-31."
            )

        feasibility_rows.append({
            **{k: v for k, v in t.items() if k != "public_live_label_terms"},
            "current_public_observation_visible": live_visible,
            "current_public_status": (
                "PUBLIC_CURRENT_HTML_VISIBLE"
                if live_visible
                else "NO_TARGET_CURRENT_HTML_FOUND"
            ),
            "current_public_source": (
                ENDPOINTS["est_sesia_current_idrometry"] if live_visible else None
            ),
            "current_public_context": context,
            "public_historical_download_status": "NOT_ESTABLISHED_PUBLICLY",
            "usable_historical_series_downloaded_n": 0,
            "next_action": next_action,
        })

    pd.DataFrame(snapshot_rows).to_csv(
        OUT / "c2g_est_sesia_current_snapshot.csv", index=False
    )

    feas = pd.DataFrame(feasibility_rows)
    feas.to_csv(OUT / "c2g_target_series_feasibility.csv", index=False)

    cedater_monitor = fetched["cedater_monitoring_system"]["visible_text"].lower()
    cedater_reports = fetched["cedater_reports"]["visible_text"]
    ticino_home = fetched["consorzio_ticino_home"]["visible_text"].lower()

    qa = {
        "status": "PASS" if endpoint_df["reachable"].all() else "PASS_WITH_ENDPOINT_FAILURES",
        "stage": "DESIGN_C_C2G_PUBLIC_TIMESERIES_ACQUISITION_FEASIBILITY",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "authoritative_endpoints_tested_n": int(len(endpoint_df)),
        "authoritative_endpoints_reachable_n": int(endpoint_df["reachable"].sum()),
        "manually_verified_historical_target_series_n": int(len(TARGETS)),
        "targets_with_public_current_observation_visible_n": int(
            feas["current_public_observation_visible"].sum()
        ),
        "public_historical_downloads_established_n": 0,
        "historical_series_files_downloaded_n": 0,
        "cedater_monitoring_system_description_found": bool(
            "monitoraggio" in cedater_monitor and "portat" in cedater_monitor
        ),
        "cedater_restricted_platform_language_found": bool(
            likely_restricted(cedater_reports)
        ),
        "consorzio_ticino_current_hydrology_page_found": bool(
            "dati automatici" in ticino_home or "dati idrologici" in ticino_home
        ),
        "rule": (
            "Public current HTML visibility is not treated as proof of a "
            "public downloadable historical archive."
        ),
    }

    (OUT / "c2g_public_timeseries_feasibility_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "DESIGN C — C2G PUBLIC TIME-SERIES ACQUISITION FEASIBILITY",
        "=" * 66,
        "",
        f"Authoritative endpoints tested: {len(endpoint_df)}",
        f"Authoritative endpoints reachable: {int(endpoint_df['reachable'].sum())}/{len(endpoint_df)}",
        f"Historically verified target series: {len(TARGETS)}",
        f"Targets visible in current Est Sesia public idrometry: {int(feas['current_public_observation_visible'].sum())}/{len(TARGETS)}",
        "Public historical downloadable target series established: 0",
        "Historical series files downloaded: 0",
        "",
        "TARGET STATUS",
        "-------------",
    ]

    for _, r in feas.iterrows():
        lines.append(
            f"- {r['target']}: historical {r['historical_start']} to {r['historical_end']} "
            f"({r['historical_provider']}); "
            f"current_public={'YES' if r['current_public_observation_visible'] else 'NO'}; "
            "historical_public_download=NOT ESTABLISHED"
        )

    lines += [
        "",
        "INTERPRETATION",
        "--------------",
        "The historical series are documentary-confirmed by ISIL.",
        "Current Est Sesia operational readings are publicly visible for some targets.",
        "No public historical-download route is accepted unless actually demonstrated.",
        "CeDATeR documents the active regional monitoring system, but public reports",
        "do not by themselves establish open access to raw historical target series.",
        "",
        "DECISION",
        "--------",
        "Do not model.",
        "Next pursue authoritative historical acquisition using the exact series names,",
        "providers and date ranges documented by ISIL.",
        "",
        f"C2G STATUS: {qa['status']}",
    ]

    summary = "\n".join(lines) + "\n"
    (OUT / "c2g_public_timeseries_feasibility_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print("\n" + summary)


if __name__ == "__main__":
    main()

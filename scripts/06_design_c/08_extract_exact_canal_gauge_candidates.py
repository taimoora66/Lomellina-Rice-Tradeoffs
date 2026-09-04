"""Design C — C2E Exact Canal / Gauge / Time-Series Candidate Extraction.

PURPOSE
-------
Refine C2D archive hits into auditable candidate gauge/time-series evidence.

Key rule:
- Exact normalized canal-name evidence is primary.
- Token-only matches are retained as secondary leads but NEVER promoted to
  direct evidence without a stronger source match.
- No groundwater measurements, flooding values, association models, or
  frozen artifacts are touched.

Inputs
------
outputs/diagnostics/design_c/c2d_canal_archive_evidence_matches.csv
outputs/diagnostics/design_c/c2d_canal_family_priority.csv

Outputs
-------
outputs/diagnostics/design_c/c2e_exact_canal_evidence.csv
outputs/diagnostics/design_c/c2e_secondary_token_leads.csv
outputs/diagnostics/design_c/c2e_gauge_station_candidates.csv
outputs/diagnostics/design_c/c2e_canal_evidence_summary.csv
outputs/diagnostics/design_c/c2e_exact_gauge_evidence_qa.json
outputs/diagnostics/design_c/c2e_exact_gauge_evidence_summary.txt

Run:
    python scripts/06_design_c/08_extract_exact_canal_gauge_candidates.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

MATCHES = OUT / "c2d_canal_archive_evidence_matches.csv"
PRIORITY = OUT / "c2d_canal_family_priority.csv"

OUT.mkdir(parents=True, exist_ok=True)

HYDRO_TERMS = [
    "portata", "portate", "discharge", "flow",
    "volume", "volumi", "monitoraggio", "monitoring",
    "idrometr", "misuratore", "misuratori",
    "sensore", "sensori", "stazione", "stazioni",
    "cedater", "sigrian", "derivazione", "derivazioni",
]

GAUGE_PATTERNS = [
    # Italian station/gauge wording followed by a short name/code phrase.
    r"\b(?:STAZIONE|STAZIONI|MISURATORE|MISURATORI|SENSORE|SENSORI|IDROMETRO|IDROMETRI)\b"
    r"[\s:;\-]+([A-Z0-9][A-Z0-9 _./\-]{2,50})",
    # Common code-like identifiers near hydrometric text.
    r"\b(?:CODICE|COD\.?|ID)\b[\s:;\-]+([A-Z0-9][A-Z0-9._/\-]{2,30})",
]


def norm(x) -> str:
    if pd.isna(x):
        return ""
    s = unicodedata.normalize("NFKD", str(x))
    s = s.encode("ascii", "ignore").decode("ascii").upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def hydrometric_hits(text: str) -> list[str]:
    low = str(text).lower()
    return sorted({t for t in HYDRO_TERMS if t in low})


def extract_gauge_candidates(text: str) -> list[str]:
    upper = unicodedata.normalize("NFKD", str(text))
    upper = upper.encode("ascii", "ignore").decode("ascii").upper()

    found = []
    for pat in GAUGE_PATTERNS:
        for m in re.finditer(pat, upper):
            val = re.sub(r"\s+", " ", m.group(1)).strip(" -.;,:")
            # Trim long sentence spillovers.
            val = re.split(
                r"\b(?:PORTATA|VOLUME|MONITORAGGIO|DATI|ANNO|DAL|NEL|PER)\b",
                val,
                maxsplit=1,
            )[0].strip(" -.;,:")
            if 3 <= len(val) <= 50:
                found.append(val)

    # Stable unique order.
    return list(dict.fromkeys(found))


def main():
    print("DESIGN C — C2E EXACT CANAL / GAUGE / TIME-SERIES CANDIDATES")
    print("=" * 66)
    print("NO groundwater values read.")
    print("NO flooding values read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    if not MATCHES.exists():
        raise FileNotFoundError(MATCHES)
    if not PRIORITY.exists():
        raise FileNotFoundError(PRIORITY)

    m = pd.read_csv(MATCHES)
    p = pd.read_csv(PRIORITY)

    if "match_mode" not in m.columns or "canal_name" not in m.columns:
        raise AssertionError("Unexpected C2D match schema.")

    m["source_text"] = m["source_text"].fillna("").astype(str)
    m["hydrometric_hits_recomputed"] = m["source_text"].map(
        lambda x: "|".join(hydrometric_hits(x))
    )
    m["gauge_candidates"] = m["source_text"].map(
        lambda x: "|".join(extract_gauge_candidates(x))
    )

    exact = m.loc[
        m["match_mode"].eq("exact_normalized_name")
    ].copy()

    secondary = m.loc[
        ~m["match_mode"].eq("exact_normalized_name")
    ].copy()

    # Direct hydrometric evidence requires BOTH exact canal-name match
    # and hydrometric language in the same retained source row.
    exact["direct_hydrometric_evidence"] = (
        exact["hydrometric_hits_recomputed"].ne("")
    )

    exact.to_csv(
        OUT / "c2e_exact_canal_evidence.csv",
        index=False,
    )
    secondary.to_csv(
        OUT / "c2e_secondary_token_leads.csv",
        index=False,
    )

    # Extract one row per candidate gauge/station mention.
    gauge_rows = []
    for _, r in exact.iterrows():
        if not r["direct_hydrometric_evidence"]:
            continue

        candidates = [
            x.strip()
            for x in str(r["gauge_candidates"]).split("|")
            if x.strip()
        ]

        # Keep hydrometric exact-name rows even if no explicit gauge identifier
        # could be parsed; manual source review may still reveal one.
        if not candidates:
            gauge_rows.append({
                "canal_name": r["canal_name"],
                "candidate_gauge_or_station": None,
                "hydrometric_terms": r["hydrometric_hits_recomputed"],
                "source_table": r.get("source_table"),
                "source_text": r.get("source_text"),
                "source_row_index": r.get("source_row_index"),
                "parser_status": "NO_EXPLICIT_IDENTIFIER_PARSED",
            })
        else:
            for cand in candidates:
                gauge_rows.append({
                    "canal_name": r["canal_name"],
                    "candidate_gauge_or_station": cand,
                    "hydrometric_terms": r["hydrometric_hits_recomputed"],
                    "source_table": r.get("source_table"),
                    "source_text": r.get("source_text"),
                    "source_row_index": r.get("source_row_index"),
                    "parser_status": "CANDIDATE_IDENTIFIER_PARSED",
                })

    gauges = pd.DataFrame(gauge_rows)
    gauges.to_csv(
        OUT / "c2e_gauge_station_candidates.csv",
        index=False,
    )

    # Canal-level evidence summary.
    if len(exact):
        canal_summary = (
            exact.groupby("canal_name", dropna=False)
            .agg(
                exact_source_rows_n=("source_row_index", "size"),
                direct_hydrometric_rows_n=(
                    "direct_hydrometric_evidence", "sum"
                ),
                exact_source_tables_n=("source_table", "nunique"),
                parsed_gauge_rows_n=(
                    "gauge_candidates",
                    lambda x: int(x.fillna("").ne("").sum()),
                ),
            )
            .reset_index()
        )
    else:
        canal_summary = pd.DataFrame(columns=[
            "canal_name",
            "exact_source_rows_n",
            "direct_hydrometric_rows_n",
            "exact_source_tables_n",
            "parsed_gauge_rows_n",
        ])

    # Merge C2D station/proximity context for review only.
    keep = [
        "canal_name",
        "stations_n",
        "stations_within_500m_n",
        "stations_within_1km_n",
        "stations_within_2km_n",
        "minimum_distance_m",
        "nearest_est_sesia_funzione",
        "nearest_est_sesia_tipo_retic",
    ]
    keep = [c for c in keep if c in p.columns]

    canal_summary = p[keep].merge(
        canal_summary,
        on="canal_name",
        how="left",
    )

    for c in [
        "exact_source_rows_n",
        "direct_hydrometric_rows_n",
        "exact_source_tables_n",
        "parsed_gauge_rows_n",
    ]:
        if c in canal_summary.columns:
            canal_summary[c] = canal_summary[c].fillna(0).astype(int)

    # Evidence classes are descriptive, not sample-selection rules.
    def evidence_class(r):
        if r.get("direct_hydrometric_rows_n", 0) > 0 and r.get(
            "parsed_gauge_rows_n", 0
        ) > 0:
            return "A_exact_name_plus_hydrometric_plus_candidate_identifier"
        if r.get("direct_hydrometric_rows_n", 0) > 0:
            return "B_exact_name_plus_hydrometric_text"
        if r.get("exact_source_rows_n", 0) > 0:
            return "C_exact_name_only"
        return "D_no_exact_archive_match"

    canal_summary["evidence_class"] = canal_summary.apply(
        evidence_class, axis=1
    )

    rank = {
        "A_exact_name_plus_hydrometric_plus_candidate_identifier": 1,
        "B_exact_name_plus_hydrometric_text": 2,
        "C_exact_name_only": 3,
        "D_no_exact_archive_match": 4,
    }
    canal_summary["_rank"] = canal_summary["evidence_class"].map(rank)

    sort_cols = ["_rank"]
    ascending = [True]
    if "stations_within_2km_n" in canal_summary.columns:
        sort_cols.append("stations_within_2km_n")
        ascending.append(False)
    if "minimum_distance_m" in canal_summary.columns:
        sort_cols.append("minimum_distance_m")
        ascending.append(True)

    canal_summary = canal_summary.sort_values(
        sort_cols, ascending=ascending
    ).drop(columns="_rank")

    canal_summary.to_csv(
        OUT / "c2e_canal_evidence_summary.csv",
        index=False,
    )

    n_exact_canals = int(exact["canal_name"].nunique()) if len(exact) else 0
    direct = exact.loc[
        exact["direct_hydrometric_evidence"]
    ] if len(exact) else exact
    n_direct_canals = int(direct["canal_name"].nunique()) if len(direct) else 0
    parsed_gauge_n = int(
        gauges["candidate_gauge_or_station"].notna().sum()
    ) if len(gauges) else 0

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2E_EXACT_CANAL_GAUGE_TIME_SERIES_CANDIDATES",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "c2d_match_rows_n": int(len(m)),
        "exact_normalized_name_rows_n": int(len(exact)),
        "secondary_token_lead_rows_n": int(len(secondary)),
        "canals_with_exact_name_evidence_n": n_exact_canals,
        "canals_with_exact_name_plus_hydrometric_evidence_n": n_direct_canals,
        "parsed_candidate_gauge_identifier_rows_n": parsed_gauge_n,
        "evidence_rule": (
            "Direct hydrometric evidence requires exact normalized canal-name "
            "match and hydrometric terminology in the same archive row."
        ),
        "candidate_identifier_rule": (
            "Regex-extracted identifiers are candidates for manual/source "
            "validation only; they are not accepted gauges automatically."
        ),
    }

    (OUT / "c2e_exact_gauge_evidence_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C — C2E EXACT CANAL / GAUGE / TIME-SERIES CANDIDATES",
        "=" * 64,
        "",
        f"C2D retained match rows: {len(m)}",
        f"Exact normalized-name rows: {len(exact)}",
        f"Secondary token-only lead rows: {len(secondary)}",
        f"Canals with exact-name evidence: {n_exact_canals}",
        (
            "Canals with exact-name + hydrometric evidence: "
            f"{n_direct_canals}"
        ),
        f"Parsed candidate gauge/station identifiers: {parsed_gauge_n}",
        "",
        "EVIDENCE RULE",
        "-------------",
        (
            "A direct hydrometric lead requires the canal name and a "
            "hydrometric term in the SAME archive row."
        ),
        (
            "Regex-parsed station/gauge identifiers remain candidates until "
            "verified against the underlying source."
        ),
        "",
        "NEXT",
        "----",
        "Review evidence classes A and B first.",
        "Trace their source documents/endpoints to actual gauge metadata and",
        "obtainable time-series coverage before any hydrological assignment.",
        "",
        "C2E STATUS: PASS",
    ]

    summary = "\n".join(lines) + "\n"
    (OUT / "c2e_exact_gauge_evidence_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print(summary)


if __name__ == "__main__":
    main()

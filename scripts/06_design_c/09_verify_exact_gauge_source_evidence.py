"""Design C — C2F Source-Level Verification of Exact Canal/Gauge Evidence.

PURPOSE
-------
Take C2E exact canal evidence and candidate gauge/station identifiers and
convert them into a source-level verification table.

This stage:
- keeps ONLY exact normalized canal-name evidence;
- identifies source file / URL / page / snippet fields where present;
- deduplicates repeated evidence rows;
- distinguishes explicit candidate identifiers from hydrometric text with
  no parsed identifier;
- ranks evidence for manual/source follow-up;
- DOES NOT accept any candidate as a valid gauge automatically.

NO groundwater values read.
NO flooding values read.
NO association model fitted.
NO frozen artifacts modified.

Inputs
------
outputs/diagnostics/design_c/c2e_exact_canal_evidence.csv
outputs/diagnostics/design_c/c2e_gauge_station_candidates.csv
outputs/diagnostics/design_c/c2e_canal_evidence_summary.csv

Outputs
-------
outputs/diagnostics/design_c/c2f_verified_source_evidence.csv
outputs/diagnostics/design_c/c2f_candidate_identifier_review.csv
outputs/diagnostics/design_c/c2f_canal_source_coverage.csv
outputs/diagnostics/design_c/c2f_source_verification_qa.json
outputs/diagnostics/design_c/c2f_source_verification_summary.txt

Run:
    python scripts/06_design_c/09_verify_exact_gauge_source_evidence.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

EXACT = OUT / "c2e_exact_canal_evidence.csv"
GAUGES = OUT / "c2e_gauge_station_candidates.csv"
SUMMARY = OUT / "c2e_canal_evidence_summary.csv"

OUT.mkdir(parents=True, exist_ok=True)

SOURCE_HINTS = [
    "source", "file", "filename", "path", "url", "endpoint",
    "document", "pdf", "page", "pagina", "sheet", "title",
    "report", "snippet", "text",
]


def choose_source_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        low = c.lower()
        if any(h in low for h in SOURCE_HINTS):
            cols.append(c)
    return cols


def compact(v):
    if pd.isna(v):
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s if s else None


def first_present(row, candidates):
    for c in candidates:
        if c in row.index:
            v = compact(row[c])
            if v:
                return v
    return None


def main():
    print("DESIGN C — C2F SOURCE-LEVEL EXACT GAUGE EVIDENCE VERIFICATION")
    print("=" * 69)
    print("NO groundwater values read.")
    print("NO flooding values read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    for p in [EXACT, GAUGES, SUMMARY]:
        if not p.exists():
            raise FileNotFoundError(p)

    exact = pd.read_csv(EXACT)
    gauges = pd.read_csv(GAUGES)
    canal_summary = pd.read_csv(SUMMARY)

    if len(exact) == 0:
        raise AssertionError("C2E exact evidence table is empty.")

    # Identify source/provenance columns retained from C2D.
    src_cols = choose_source_columns(exact)

    # Build a canonical source locator from whichever fields are actually present.
    source_file_candidates = [
        c for c in exact.columns
        if any(k in c.lower() for k in ["file", "filename", "path", "document", "pdf"])
    ]
    url_candidates = [
        c for c in exact.columns
        if any(k in c.lower() for k in ["url", "endpoint"])
    ]
    page_candidates = [
        c for c in exact.columns
        if any(k in c.lower() for k in ["page", "pagina"])
    ]
    title_candidates = [
        c for c in exact.columns
        if any(k in c.lower() for k in ["title", "report", "source_name"])
    ]

    records = []

    for idx, r in exact.iterrows():
        source_file = first_present(r, source_file_candidates)
        source_url = first_present(r, url_candidates)
        source_page = first_present(r, page_candidates)
        source_title = first_present(r, title_candidates)
        source_text = compact(r.get("source_text"))

        direct_hydro = bool(r.get("direct_hydrometric_evidence", False))
        parsed = compact(r.get("gauge_candidates"))

        # Source-level evidence strength only.
        if parsed and direct_hydro:
            evidence_level = "A_candidate_identifier_in_exact_hydrometric_row"
        elif direct_hydro:
            evidence_level = "B_exact_hydrometric_row_no_identifier"
        else:
            evidence_level = "C_exact_name_only"

        locator_parts = [
            x for x in [source_file, source_title, source_url, source_page]
            if x
        ]
        locator = " | ".join(locator_parts) if locator_parts else None

        records.append({
            "canal_name": r["canal_name"],
            "source_table": r.get("source_table"),
            "source_row_index": r.get("source_row_index"),
            "evidence_level": evidence_level,
            "candidate_identifiers_raw": parsed,
            "hydrometric_terms": compact(
                r.get("hydrometric_hits_recomputed")
            ),
            "source_locator": locator,
            "source_file": source_file,
            "source_title": source_title,
            "source_url_or_endpoint": source_url,
            "source_page": source_page,
            "source_text": source_text,
        })

    ver = pd.DataFrame(records)

    # Deterministic deduplication: same canal + same locator + same source text.
    before = len(ver)
    ver = ver.drop_duplicates(
        subset=["canal_name", "source_locator", "source_text"],
        keep="first",
    ).copy()
    after = len(ver)

    rank = {
        "A_candidate_identifier_in_exact_hydrometric_row": 1,
        "B_exact_hydrometric_row_no_identifier": 2,
        "C_exact_name_only": 3,
    }
    ver["_rank"] = ver["evidence_level"].map(rank)

    ver = ver.sort_values(
        ["_rank", "canal_name", "source_locator"],
        na_position="last",
    ).drop(columns="_rank")

    ver.to_csv(
        OUT / "c2f_verified_source_evidence.csv",
        index=False,
    )

    # Candidate identifier review: preserve every parsed identifier candidate,
    # but explicitly require source verification.
    if len(gauges):
        g = gauges.copy()
        g["candidate_gauge_or_station"] = (
            g["candidate_gauge_or_station"]
            .where(g["candidate_gauge_or_station"].notna(), None)
        )
        g["verification_status"] = "PENDING_SOURCE_VERIFICATION"
        g["accepted_as_gauge"] = False

        g = g.drop_duplicates(
            subset=[
                "canal_name",
                "candidate_gauge_or_station",
                "source_text",
            ],
            keep="first",
        )

        g.to_csv(
            OUT / "c2f_candidate_identifier_review.csv",
            index=False,
        )
    else:
        g = pd.DataFrame()
        g.to_csv(
            OUT / "c2f_candidate_identifier_review.csv",
            index=False,
        )

    # Canal-level source coverage.
    grouped = (
        ver.groupby("canal_name", dropna=False)
        .agg(
            verified_source_rows_n=("source_row_index", "size"),
            distinct_source_locators_n=(
                "source_locator",
                lambda x: x.dropna().nunique(),
            ),
            class_A_rows_n=(
                "evidence_level",
                lambda x: int(
                    (x == "A_candidate_identifier_in_exact_hydrometric_row").sum()
                ),
            ),
            class_B_rows_n=(
                "evidence_level",
                lambda x: int(
                    (x == "B_exact_hydrometric_row_no_identifier").sum()
                ),
            ),
        )
        .reset_index()
    )

    # Add proximity context from C2E summary.
    keep = [
        c for c in [
            "canal_name",
            "stations_within_500m_n",
            "stations_within_1km_n",
            "stations_within_2km_n",
            "minimum_distance_m",
            "evidence_class",
        ]
        if c in canal_summary.columns
    ]

    coverage = canal_summary[keep].merge(
        grouped,
        on="canal_name",
        how="left",
    )

    for c in [
        "verified_source_rows_n",
        "distinct_source_locators_n",
        "class_A_rows_n",
        "class_B_rows_n",
    ]:
        coverage[c] = coverage[c].fillna(0).astype(int)

    coverage["source_verification_priority"] = (
        5 * (coverage["class_A_rows_n"] > 0).astype(int)
        + 3 * (coverage["class_B_rows_n"] > 0).astype(int)
        + 2 * coverage.get(
            "stations_within_500m_n",
            pd.Series(0, index=coverage.index),
        ).fillna(0)
        + coverage.get(
            "stations_within_2km_n",
            pd.Series(0, index=coverage.index),
        ).fillna(0)
    )

    coverage = coverage.sort_values(
        [
            "source_verification_priority",
            "class_A_rows_n",
            "class_B_rows_n",
        ],
        ascending=[False, False, False],
    )

    coverage.to_csv(
        OUT / "c2f_canal_source_coverage.csv",
        index=False,
    )

    n_canals = int(ver["canal_name"].nunique())
    n_A_canals = int(
        ver.loc[
            ver["evidence_level"].eq(
                "A_candidate_identifier_in_exact_hydrometric_row"
            ),
            "canal_name",
        ].nunique()
    )
    n_B_canals = int(
        ver.loc[
            ver["evidence_level"].eq(
                "B_exact_hydrometric_row_no_identifier"
            ),
            "canal_name",
        ].nunique()
    )

    candidate_ids = 0
    if len(g):
        candidate_ids = int(
            g["candidate_gauge_or_station"].notna().sum()
        )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2F_SOURCE_LEVEL_EXACT_GAUGE_EVIDENCE",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "exact_input_rows_n": int(len(exact)),
        "deduplicated_source_evidence_rows_n": int(len(ver)),
        "duplicate_rows_removed_n": int(before - after),
        "canals_with_source_level_exact_evidence_n": n_canals,
        "canals_with_class_A_candidate_identifier_evidence_n": n_A_canals,
        "canals_with_class_B_exact_hydrometric_evidence_n": n_B_canals,
        "candidate_identifier_rows_n": candidate_ids,
        "candidate_identifiers_accepted_as_gauges_n": 0,
        "rule": (
            "No parsed identifier is accepted as a gauge until verified "
            "against its underlying source document or endpoint."
        ),
    }

    (OUT / "c2f_source_verification_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    top = coverage.head(20)

    lines = [
        "DESIGN C — C2F SOURCE-LEVEL EXACT GAUGE EVIDENCE VERIFICATION",
        "=" * 67,
        "",
        f"Exact input rows: {len(exact)}",
        f"Deduplicated source-evidence rows: {len(ver)}",
        f"Duplicate rows removed: {before - after}",
        f"Canals with source-level exact evidence: {n_canals}",
        f"Canals with Class A evidence: {n_A_canals}",
        f"Canals with Class B evidence: {n_B_canals}",
        f"Candidate identifier rows: {candidate_ids}",
        "Accepted gauges: 0",
        "",
        "TOP SOURCE-VERIFICATION TARGETS",
        "-------------------------------",
    ]

    for _, r in top.iterrows():
        lines.append(
            f"- {r['canal_name']} | "
            f"A={int(r['class_A_rows_n'])} | "
            f"B={int(r['class_B_rows_n'])} | "
            f"sources={int(r['distinct_source_locators_n'])} | "
            f"score={int(r['source_verification_priority'])}"
        )

    lines.extend([
        "",
        "INTERPRETATION",
        "--------------",
        "Class A = exact canal name + hydrometric text + parsed candidate identifier.",
        "Class B = exact canal name + hydrometric text, no parsed identifier.",
        "Neither class establishes a valid gauge until the source is checked.",
        "",
        "NEXT",
        "----",
        "Inspect Class A rows first, then Class B rows.",
        "Verify gauge/station identity, location, variable, temporal coverage,",
        "and whether data are publicly downloadable before any station-to-canal",
        "hydrological assignment.",
        "",
        "C2F STATUS: PASS",
    ])

    summary = "\n".join(lines) + "\n"
    (OUT / "c2f_source_verification_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print(summary)


if __name__ == "__main__":
    main()

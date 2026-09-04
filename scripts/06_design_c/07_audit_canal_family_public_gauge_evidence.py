"""Design C — C2D Canal-Family / Public Gauge Evidence Audit.

PURPOSE
-------
Use the completed C2C spatial linkage to identify named Est Sesia canal
families relevant to groundwater stations, then search the already-acquired
public irrigation archive for exact/normalized name evidence, gauge,
monitoring, discharge, flow, and volume references.

This is NOT a hydrological service assignment and NOT a model stage.

Inputs
------
outputs/diagnostics/design_c/c2c_station_est_sesia_review.csv
outputs/diagnostics/design_c/c2a_public_irrigation_evidence_hits.csv
outputs/diagnostics/design_c/c2a_candidate_public_endpoints.csv
data/design_c/metadata/c1b_maximum_public_irrigation_archive_manifest.csv

Outputs
-------
outputs/diagnostics/design_c/c2d_canal_family_station_context.csv
outputs/diagnostics/design_c/c2d_canal_archive_evidence_matches.csv
outputs/diagnostics/design_c/c2d_canal_family_priority.csv
outputs/diagnostics/design_c/c2d_public_gauge_evidence_qa.json
outputs/diagnostics/design_c/c2d_public_gauge_evidence_summary.txt

NO groundwater values read.
NO flooding values read.
NO association model fitted.
NO frozen artifact modified.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
META = ROOT / "data" / "design_c" / "metadata"

C2C = OUT / "c2c_station_est_sesia_review.csv"
EVIDENCE = OUT / "c2a_public_irrigation_evidence_hits.csv"
ENDPOINTS = OUT / "c2a_candidate_public_endpoints.csv"
MANIFEST = META / "c1b_maximum_public_irrigation_archive_manifest.csv"

OUT.mkdir(parents=True, exist_ok=True)

HYDRO_TERMS = [
    "portata", "portate", "discharge", "flow",
    "volume", "volumi", "misura", "misure",
    "monitoraggio", "monitoring", "idrometr",
    "misuratore", "misuratori", "sensore", "sensori",
    "stazione", "stazioni", "cedater", "sigrian",
    "derivazione", "derivazioni",
]

# Words describing feature type rather than family identity.
GENERIC_WORDS = {
    "ROGGIA", "CAVO", "CANALE", "CANAL", "NAVIGLIO",
    "DIRAMATORE", "SUBDIRAMATORE", "COLATORE", "FONTANA",
    "FOSSA", "COMUNALE", "DI", "DEL", "DELLA", "DELLE",
    "DEI", "ALLA", "ALLE", "AL", "O", "VECCHIO", "VECCHIA",
}


def norm(x) -> str:
    if pd.isna(x):
        return ""
    s = unicodedata.normalize("NFKD", str(x))
    s = s.encode("ascii", "ignore").decode("ascii").upper()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def family_tokens(name: str) -> list[str]:
    toks = [t for t in norm(name).split() if len(t) >= 4]
    informative = [t for t in toks if t not in GENERIC_WORDS]
    return informative if informative else toks


def choose_text_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        if (
            pd.api.types.is_object_dtype(df[c])
            or pd.api.types.is_string_dtype(df[c])
        ):
            cols.append(c)
    return cols


def combined_text(df: pd.DataFrame) -> pd.Series:
    cols = choose_text_columns(df)
    if not cols:
        return pd.Series([""] * len(df), index=df.index)
    return (
        df[cols]
        .fillna("")
        .astype(str)
        .agg(" | ".join, axis=1)
    )


def main():
    print("DESIGN C — C2D CANAL-FAMILY / PUBLIC GAUGE EVIDENCE AUDIT")
    print("=" * 64)
    print("NO groundwater values read.")
    print("NO flooding values read.")
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    if not C2C.exists():
        raise FileNotFoundError(C2C)

    c2c = pd.read_csv(C2C)

    required = {
        "station",
        "nearest_est_sesia_distance_m",
        "nearest_est_sesia_nome_c_acq",
        "nearest_est_sesia_funzione",
        "nearest_est_sesia_tipo_retic",
    }
    missing = sorted(required - set(c2c.columns))
    if missing:
        raise AssertionError(f"C2C missing required columns: {missing}")

    c2c["nearest_est_sesia_distance_m"] = pd.to_numeric(
        c2c["nearest_est_sesia_distance_m"], errors="coerce"
    )
    if c2c["nearest_est_sesia_distance_m"].isna().any():
        raise AssertionError("C2C contains missing canal distances.")

    c2c["canal_name"] = (
        c2c["nearest_est_sesia_nome_c_acq"].fillna("").astype(str).str.strip()
    )
    c2c["canal_norm"] = c2c["canal_name"].map(norm)

    # Descriptive distance strata only. These are NOT inclusion/exclusion rules.
    c2c["distance_stratum"] = pd.cut(
        c2c["nearest_est_sesia_distance_m"],
        bins=[-np.inf, 500, 1000, 2000, 5000, 10000, np.inf],
        labels=["<=500m", "0.5-1km", "1-2km", "2-5km", "5-10km", ">10km"],
        right=True,
    )

    c2c.to_csv(
        OUT / "c2d_canal_family_station_context.csv",
        index=False,
    )

    # Canal-family summary across ALL stations. Distance affects priority only;
    # nothing is dropped.
    fam = (
        c2c.groupby(
            [
                "canal_name",
                "nearest_est_sesia_funzione",
                "nearest_est_sesia_tipo_retic",
            ],
            dropna=False,
        )
        .agg(
            stations_n=("station", "size"),
            minimum_distance_m=("nearest_est_sesia_distance_m", "min"),
            median_distance_m=("nearest_est_sesia_distance_m", "median"),
            stations_within_500m_n=(
                "nearest_est_sesia_distance_m",
                lambda x: int((x <= 500).sum()),
            ),
            stations_within_1km_n=(
                "nearest_est_sesia_distance_m",
                lambda x: int((x <= 1000).sum()),
            ),
            stations_within_2km_n=(
                "nearest_est_sesia_distance_m",
                lambda x: int((x <= 2000).sum()),
            ),
            stations_within_5km_n=(
                "nearest_est_sesia_distance_m",
                lambda x: int((x <= 5000).sum()),
            ),
        )
        .reset_index()
    )
    fam["canal_norm"] = fam["canal_name"].map(norm)

    # Archive sources already downloaded in C1B/C2A.
    sources = []
    for label, path in [
        ("evidence_hits", EVIDENCE),
        ("candidate_endpoints", ENDPOINTS),
        ("archive_manifest", MANIFEST),
    ]:
        if path.exists():
            d = pd.read_csv(path)
            d["_source_table"] = label
            d["_row_text"] = combined_text(d)
            d["_row_norm"] = d["_row_text"].map(norm)
            sources.append(d)

    if not sources:
        raise FileNotFoundError(
            "No C2A/C1B public archive metadata tables found."
        )

    matches = []

    for _, f in fam.iterrows():
        name = f["canal_name"]
        nname = f["canal_norm"]
        toks = family_tokens(name)

        for src in sources:
            # Conservative evidence rule:
            # exact normalized name OR at least one strong informative token
            # plus hydrometric terminology. Keep match mode explicit.
            for idx, row in src.iterrows():
                txt_raw = row["_row_text"]
                txt_norm = row["_row_norm"]

                exact = bool(nname and nname in txt_norm)
                tok_hits = sorted({t for t in toks if t in txt_norm})

                hydro_hits = sorted({
                    t for t in HYDRO_TERMS
                    if norm(t) in txt_norm
                })

                # Avoid flooding output with weak single-token matches:
                # retain if exact name occurs, OR >=1 informative family token
                # occurs together with hydrometric language.
                retain = exact or (len(tok_hits) >= 1 and len(hydro_hits) >= 1)
                if not retain:
                    continue

                record = {
                    "canal_name": name,
                    "canal_norm": nname,
                    "source_table": row["_source_table"],
                    "source_row_index": idx,
                    "match_mode": (
                        "exact_normalized_name"
                        if exact else "family_token_plus_hydrometric_term"
                    ),
                    "family_token_hits": "|".join(tok_hits),
                    "hydrometric_term_hits": "|".join(hydro_hits),
                    "source_text": txt_raw,
                }

                # Preserve useful source columns without assuming exact schema.
                for c in src.columns:
                    if c.startswith("_"):
                        continue
                    if c not in record:
                        record[f"src_{c}"] = row[c]

                matches.append(record)

    match_df = pd.DataFrame(matches)
    match_df.to_csv(
        OUT / "c2d_canal_archive_evidence_matches.csv",
        index=False,
    )

    if len(match_df):
        ev = (
            match_df.groupby("canal_name")
            .agg(
                archive_evidence_rows_n=("source_row_index", "size"),
                exact_name_evidence_rows_n=(
                    "match_mode",
                    lambda x: int((x == "exact_normalized_name").sum()),
                ),
                hydrometric_evidence_rows_n=(
                    "hydrometric_term_hits",
                    lambda x: int(x.fillna("").ne("").sum()),
                ),
                source_tables_n=("source_table", "nunique"),
            )
            .reset_index()
        )
    else:
        ev = pd.DataFrame(columns=[
            "canal_name",
            "archive_evidence_rows_n",
            "exact_name_evidence_rows_n",
            "hydrometric_evidence_rows_n",
            "source_tables_n",
        ])

    priority = fam.merge(ev, on="canal_name", how="left")
    for c in [
        "archive_evidence_rows_n",
        "exact_name_evidence_rows_n",
        "hydrometric_evidence_rows_n",
        "source_tables_n",
    ]:
        priority[c] = priority[c].fillna(0).astype(int)

    # Priority is for PUBLIC-DATA FOLLOW-UP only, not scientific sample choice.
    # Closer multi-station canal families with direct archive evidence rise.
    priority["public_followup_score"] = (
        4 * priority["stations_within_500m_n"]
        + 3 * (
            priority["stations_within_1km_n"]
            - priority["stations_within_500m_n"]
        )
        + 2 * (
            priority["stations_within_2km_n"]
            - priority["stations_within_1km_n"]
        )
        + priority["stations_within_5km_n"]
        + 3 * (priority["exact_name_evidence_rows_n"] > 0).astype(int)
        + 2 * (priority["hydrometric_evidence_rows_n"] > 0).astype(int)
    )

    priority = priority.sort_values(
        [
            "public_followup_score",
            "stations_within_2km_n",
            "minimum_distance_m",
        ],
        ascending=[False, False, True],
    )

    priority.to_csv(
        OUT / "c2d_canal_family_priority.csv",
        index=False,
    )

    close_families = int((priority["stations_within_2km_n"] > 0).sum())
    evidence_families = int(
        (priority["archive_evidence_rows_n"] > 0).sum()
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2D_CANAL_FAMILY_PUBLIC_GAUGE_EVIDENCE_AUDIT",
        "association_models_fitted": 0,
        "groundwater_measurements_read": 0,
        "flooding_measurements_read": 0,
        "frozen_artifacts_modified": 0,
        "stations_n": int(len(c2c)),
        "unique_nearest_canal_families_n": int(c2c["canal_name"].nunique()),
        "canal_families_with_station_within_2km_n": close_families,
        "canal_families_with_public_archive_evidence_n": evidence_families,
        "archive_match_rows_n": int(len(match_df)),
        "priority_score_interpretation": (
            "Search-follow-up convenience only; not an exposure, treatment, "
            "inclusion criterion, or model weight."
        ),
    }
    (OUT / "c2d_public_gauge_evidence_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    top = priority.head(20)

    lines = [
        "DESIGN C — C2D CANAL-FAMILY / PUBLIC GAUGE EVIDENCE AUDIT",
        "=" * 62,
        "",
        f"Stations: {len(c2c)}",
        f"Unique nearest canal families: {c2c['canal_name'].nunique()}",
        f"Families with >=1 station within 2 km: {close_families}",
        f"Families with public archive evidence: {evidence_families}",
        f"Retained archive evidence rows: {len(match_df)}",
        "",
        "TOP PUBLIC-DATA FOLLOW-UP FAMILIES",
        "----------------------------------",
    ]

    for _, r in top.iterrows():
        lines.append(
            f"- {r['canal_name']} | score={int(r['public_followup_score'])} | "
            f"<=2km wells={int(r['stations_within_2km_n'])} | "
            f"min distance={r['minimum_distance_m']:.1f} m | "
            f"archive rows={int(r['archive_evidence_rows_n'])}"
        )

    lines.extend([
        "",
        "INTERPRETATION",
        "--------------",
        "Priority ranks where to search public gauge/discharge records first.",
        "It is NOT a hydrological service assignment and NOT a sample filter.",
        "",
        "NEXT",
        "----",
        "Inspect exact archive matches for the highest-priority canal families.",
        "Then identify named gauges/stations and obtainable time series.",
        "Only after topology/monitoring validation should irrigation delivery",
        "be linked to groundwater stations.",
        "",
        "C2D STATUS: PASS",
    ])

    summary = "\n".join(lines) + "\n"
    (OUT / "c2d_public_gauge_evidence_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print(summary)


if __name__ == "__main__":
    main()

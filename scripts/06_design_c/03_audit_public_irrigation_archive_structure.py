"""Design C — C2A Public Irrigation Archive Structure & Evidence Audit.

PURPOSE
-------
Turn the C1B public archive into a structured evidence inventory before any
institutional request or scientific association analysis.

This script:
- verifies every C1B acquired file against its SHA-256 manifest;
- validates basic file signatures (PDF/ZIP/XML/JSON/HTML);
- unpacks the Regione Lombardia ISIL/methodology ZIP into a derived audit folder;
- inventories every extracted file;
- extracts text from machine-readable PDFs and HTML WITHOUT OCR;
- inventories RIRU ArcGIS/WMS layers from downloaded service metadata;
- searches public materials for Lomellina / Est Sesia / irrigation-flow evidence;
- discovers candidate public URLs/endpoints embedded in acquired HTML/JSON/XML;
- writes one compact C2A QA/evidence package.

This script DOES NOT:
- fit any groundwater/irrigation/flooding model;
- inspect association coefficients;
- alter frozen Stage-5–8 artifacts;
- choose years/wells/districts based on results;
- use OCR;
- download new bulk datasets.

Run from repository root:
    python scripts/06_design_c/03_audit_public_irrigation_archive_structure.py
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = ROOT / "data" / "design_c"
RAW = BASE / "raw" / "public_irrigation_archive"
META = BASE / "metadata"
DERIVED = BASE / "derived_public_archive"
OUT = ROOT / "outputs" / "diagnostics" / "design_c"

MANIFEST = META / "c1b_maximum_public_irrigation_archive_manifest.csv"

for p in [DERIVED, OUT]:
    p.mkdir(parents=True, exist_ok=True)

EXTRACTED_ZIP = DERIVED / "regione_isil_bundle_extracted"
TEXT_CACHE = DERIVED / "text_cache"
TEXT_CACHE.mkdir(parents=True, exist_ok=True)

SEARCH_TERMS = {
    "est_sesia": [
        "est sesia",
        "associazione irrigazione est sesia",
        "aies",
    ],
    "lomellina": [
        "lomellina",
        "mortara",
        "mede",
        "robbio",
        "vigevano",
        "san giorgio di lomellina",
        "sartirana",
        "cavo isimbardi",
        "cavo canalino",
        "roggia comunale di san giorgio",
    ],
    "flow_volume": [
        "portata",
        "portate",
        "volume",
        "volumi",
        "m3/s",
        "m³/s",
        "mc/s",
        "milioni di m3",
        "milioni di m³",
    ],
    "gauge_monitoring": [
        "misuratore",
        "misuratori",
        "stazione",
        "stazioni",
        "sensore",
        "sensori",
        "monitoraggio",
        "idrometr",
        "telecontroll",
    ],
    "irrigation_unit": [
        "unità irrigua",
        "unita irrigua",
        "distretto irriguo",
        "comizio",
        "comprensorio",
        "canale",
        "roggia",
        "derivazione",
    ],
    "time_series": [
        "serie storica",
        "serie temporale",
        "giornal",
        "settiman",
        "mensil",
        "stagione irrigua",
        "2015",
        "2016",
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
    ],
}

URL_RE = re.compile(r'https?://[^\s<>"\']+', flags=re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def signature(path: Path) -> str:
    with path.open("rb") as f:
        head = f.read(32)
    if head.startswith(b"%PDF"):
        return "PDF"
    if head.startswith(b"PK\x03\x04"):
        return "ZIP"
    stripped = head.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return "JSON_OR_TEXT"
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        return "XML_OR_HTML"
    return "OTHER"


def verify_manifest() -> pd.DataFrame:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Missing C1B manifest: {MANIFEST}")

    m = pd.read_csv(MANIFEST)
    rows = []

    for _, r in m.iterrows():
        local = ROOT / str(r["local_path"])
        exists = local.exists()
        actual_sha = sha256_file(local) if exists else None
        expected_sha = str(r.get("sha256", "")) if pd.notna(r.get("sha256")) else None
        ok = exists and expected_sha == actual_sha

        rows.append({
            "source_id": r["source_id"],
            "local_path": str(local.relative_to(ROOT)) if exists else str(local),
            "exists": bool(exists),
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "sha256_match": bool(ok),
            "signature": signature(local) if exists else None,
            "bytes": local.stat().st_size if exists else None,
            "kind": r.get("kind"),
            "organisation": r.get("organisation"),
            "year_start": r.get("year_start"),
            "year_end": r.get("year_end"),
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT / "c2a_manifest_verification.csv", index=False)

    bad = out.loc[~out["sha256_match"]]
    if len(bad):
        raise AssertionError(
            "C1B manifest verification failed for: "
            + ", ".join(bad["source_id"].astype(str))
        )
    return out


def unpack_isil_bundle() -> pd.DataFrame:
    """Extract ISIL bundle using short deterministic filenames.

    Windows commonly fails on the original long Italian filenames when the
    repository path is already long. We therefore preserve the ORIGINAL ZIP
    member name in the inventory, but extract each file as isil_###.<suffix>.
    This changes no file contents and preserves byte-level provenance.
    """
    zip_path = RAW / "regione_lombardia" / "Allegati_uso_irriguo.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    if EXTRACTED_ZIP.exists():
        shutil.rmtree(EXTRACTED_ZIP)
    EXTRACTED_ZIP.mkdir(parents=True, exist_ok=True)

    rows = []
    file_counter = 0

    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            # Preserve directories only as metadata; do not reproduce long
            # nested paths on disk.
            if info.is_dir():
                continue

            # ZIP-slip protection on the archive member itself.
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"Unsafe ZIP member: {info.filename}")

            file_counter += 1
            suffix = Path(info.filename).suffix.lower()
            if not suffix:
                suffix = ".bin"

            short_name = f"isil_{file_counter:03d}{suffix}"
            path = EXTRACTED_ZIP / short_name

            # Stream exact uncompressed bytes into the short local path.
            with z.open(info, "r") as src_f, path.open("wb") as dst_f:
                shutil.copyfileobj(src_f, dst_f)

            rows.append({
                "archive_member": info.filename,
                "short_filename": short_name,
                "local_path": str(path.relative_to(ROOT)),
                "compressed_bytes": int(info.compress_size),
                "uncompressed_bytes_zip": int(info.file_size),
                "bytes": path.stat().st_size,
                "zip_crc32": f"{info.CRC:08x}",
                "suffix": path.suffix.lower(),
                "signature": signature(path),
                "sha256": sha256_file(path),
                "size_matches_zip_metadata": bool(path.stat().st_size == info.file_size),
            })

    inv = pd.DataFrame(rows).sort_values("archive_member")
    inv.to_csv(OUT / "c2a_isil_bundle_inventory.csv", index=False)

    if len(inv) and not inv["size_matches_zip_metadata"].all():
        bad = inv.loc[~inv["size_matches_zip_metadata"], "archive_member"].tolist()
        raise AssertionError(
            "Extracted ISIL file size mismatch for: " + "; ".join(bad)
        )

    return inv


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError(
            "pypdf is required for machine-readable PDF extraction. "
            "Install with: python -m pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            parts.append(f"\n--- PAGE {i+1} ---\n{txt}")
    return "".join(parts)


def strip_html_text(raw: str) -> str:
    # Remove script/style blocks first.
    x = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    x = re.sub(r"(?is)<style.*?>.*?</style>", " ", x)
    x = re.sub(r"(?s)<[^>]+>", " ", x)
    x = html.unescape(x)
    x = re.sub(r"\s+", " ", x)
    return x.strip()


def decode_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return ""


def all_candidate_files(manifest_df: pd.DataFrame, zip_inv: pd.DataFrame) -> list[Path]:
    files = []
    for pstr in manifest_df["local_path"]:
        p = ROOT / pstr
        if p.is_file():
            files.append(p)
    for pstr in zip_inv["local_path"]:
        p = ROOT / pstr
        if p.is_file():
            files.append(p)
    # stable unique list
    return sorted(set(files))


def extract_searchable_text(files: list[Path]) -> pd.DataFrame:
    rows = []
    for p in files:
        suf = p.suffix.lower()
        txt = ""
        method = None

        sig = signature(p)

        # Trust file bytes, not filename extensions. Some public portals return
        # HTML wrappers/errors from URLs ending in ".pdf".
        if sig == "PDF":
            try:
                txt = extract_pdf_text(p)
                method = "pypdf_text"
            except Exception as exc:
                rows.append({
                    "local_path": str(p.relative_to(ROOT)),
                    "extract_method": "FAILED_PDF_TEXT",
                    "characters": 0,
                    "error": repr(exc),
                })
                continue
        elif suf in {".html", ".htm"} or (
            sig == "XML_OR_HTML" and suf not in {".xml"}
        ):
            raw = decode_text(p)
            txt = strip_html_text(raw)
            method = "html_strip"
        elif suf in {".xml", ".json", ".txt", ".csv", ".md"} or sig in {
            "JSON_OR_TEXT", "XML_OR_HTML"
        }:
            txt = decode_text(p)
            method = "plain_text"
        else:
            # Do not attempt OCR/binary extraction.
            continue

        cache_name = hashlib.sha1(str(p).encode("utf-8")).hexdigest() + ".txt"
        cache = TEXT_CACHE / cache_name
        cache.write_text(txt, encoding="utf-8")

        rows.append({
            "local_path": str(p.relative_to(ROOT)),
            "extract_method": method,
            "characters": len(txt),
            "text_cache": str(cache.relative_to(ROOT)),
            "error": None,
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT / "c2a_text_extraction_inventory.csv", index=False)
    return out


def evidence_hits(text_inv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in text_inv.iterrows():
        if not r.get("text_cache") or pd.isna(r.get("text_cache")):
            continue
        path = ROOT / str(r["text_cache"])
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        low = text.lower()

        for category, terms in SEARCH_TERMS.items():
            for term in terms:
                start = 0
                term_low = term.lower()
                hit_count = 0
                while True:
                    idx = low.find(term_low, start)
                    if idx < 0:
                        break
                    hit_count += 1
                    if hit_count <= 10:  # bounded evidence snippets per term/file
                        left = max(0, idx - 220)
                        right = min(len(text), idx + len(term) + 360)
                        snippet = re.sub(r"\s+", " ", text[left:right]).strip()
                        rows.append({
                            "local_path": r["local_path"],
                            "category": category,
                            "term": term,
                            "snippet": snippet,
                        })
                    start = idx + len(term_low)

    out = pd.DataFrame(rows)
    if len(out):
        out = out.drop_duplicates().sort_values(
            ["category", "term", "local_path"]
        )
    out.to_csv(OUT / "c2a_public_irrigation_evidence_hits.csv", index=False)
    return out


def inventory_riru_layers() -> pd.DataFrame:
    rows = []

    json_path = RAW / "network_metadata" / "RIRU_MapServer.json"
    if json_path.exists():
        obj = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
        for layer in obj.get("layers", []):
            rows.append({
                "source": "ArcGIS_REST",
                "layer_id": layer.get("id"),
                "name": layer.get("name"),
                "parentLayerId": layer.get("parentLayerId"),
                "subLayerIds": json.dumps(layer.get("subLayerIds")),
            })

    xml_path = RAW / "network_metadata" / "RIRU_WMS_GetCapabilities.xml"
    if xml_path.exists():
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Namespace-agnostic layer walk.
        for elem in root.iter():
            if elem.tag.split("}")[-1] != "Layer":
                continue
            name = None
            title = None
            for child in elem:
                local = child.tag.split("}")[-1]
                if local == "Name":
                    name = child.text
                elif local == "Title":
                    title = child.text
            if name or title:
                rows.append({
                    "source": "WMS",
                    "layer_id": name,
                    "name": title,
                    "parentLayerId": None,
                    "subLayerIds": None,
                })

    out = pd.DataFrame(rows).drop_duplicates()
    out.to_csv(OUT / "c2a_riru_layer_inventory.csv", index=False)
    return out


def discover_urls(files: list[Path]) -> pd.DataFrame:
    rows = []
    for p in files:
        if p.suffix.lower() not in {".html", ".htm", ".xml", ".json", ".txt"}:
            continue
        raw = decode_text(p)
        urls = sorted(set(URL_RE.findall(raw)))
        for u in urls:
            clean = html.unescape(u).rstrip(").,;'\"")
            low = clean.lower()

            keywords = [
                "csv", "xls", "xlsx", "zip", "geojson", "shp",
                "feature", "mapserver", "wms", "wfs", "download",
                "monitor", "idrom", "portat", "cedater", "sigrian",
                "estsesia", "anbi",
            ]
            if not any(k in low for k in keywords):
                continue

            rows.append({
                "source_file": str(p.relative_to(ROOT)),
                "url": clean,
                "host": urlparse(clean).netloc.lower(),
                "candidate_reason": "|".join(k for k in keywords if k in low),
            })

    out = pd.DataFrame(rows)
    if len(out):
        out = out.drop_duplicates().sort_values(["host", "url"])
    out.to_csv(OUT / "c2a_candidate_public_endpoints.csv", index=False)
    return out


def summarize_evidence(hits: pd.DataFrame) -> pd.DataFrame:
    if not len(hits):
        return pd.DataFrame(columns=["category", "files_n", "hits_n"])

    out = (
        hits.groupby("category")
        .agg(
            files_n=("local_path", "nunique"),
            hits_n=("term", "size"),
        )
        .reset_index()
    )
    out.to_csv(OUT / "c2a_evidence_category_summary.csv", index=False)
    return out


def main():
    print("DESIGN C — C2A PUBLIC IRRIGATION ARCHIVE STRUCTURE AUDIT")
    print("=" * 62)
    print("NO association model fitted.")
    print("NO frozen artifact modified.\n")

    verified = verify_manifest()
    print(f"Manifest verified: {len(verified)}/{len(verified)} files")

    zip_inv = unpack_isil_bundle()
    print(f"ISIL bundle extracted files: {len(zip_inv)}")

    files = all_candidate_files(verified, zip_inv)
    print(f"Archive files considered: {len(files)}")

    text_inv = extract_searchable_text(files)
    print(f"Machine-readable text sources extracted: {len(text_inv)}")

    hits = evidence_hits(text_inv)
    print(f"Evidence snippets retained: {len(hits)}")

    layers = inventory_riru_layers()
    print(f"RIRU layer records inventoried: {len(layers)}")

    endpoints = discover_urls(files)
    print(f"Candidate public endpoints discovered: {len(endpoints)}")

    categories = summarize_evidence(hits)

    est_files = (
        hits.loc[hits["category"].eq("est_sesia"), "local_path"].nunique()
        if len(hits) else 0
    )
    lom_files = (
        hits.loc[hits["category"].eq("lomellina"), "local_path"].nunique()
        if len(hits) else 0
    )
    flow_files = (
        hits.loc[hits["category"].eq("flow_volume"), "local_path"].nunique()
        if len(hits) else 0
    )
    monitor_files = (
        hits.loc[hits["category"].eq("gauge_monitoring"), "local_path"].nunique()
        if len(hits) else 0
    )

    qa = {
        "status": "PASS",
        "stage": "DESIGN_C_C2A_PUBLIC_IRRIGATION_ARCHIVE_STRUCTURE",
        "association_models_fitted": 0,
        "frozen_artifacts_modified": 0,
        "manifest_files_verified_n": int(len(verified)),
        "manifest_sha256_failures_n": int((~verified["sha256_match"]).sum()),
        "isil_extracted_files_n": int(len(zip_inv)),
        "text_sources_extracted_n": int(len(text_inv)),
        "evidence_snippets_n": int(len(hits)),
        "riru_layer_records_n": int(len(layers)),
        "candidate_public_endpoints_n": int(len(endpoints)),
        "evidence_files": {
            "est_sesia": int(est_files),
            "lomellina": int(lom_files),
            "flow_volume": int(flow_files),
            "gauge_monitoring": int(monitor_files),
        },
        "ocr_used": False,
    }
    (OUT / "c2a_public_archive_structure_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = f"""DESIGN C — C2A PUBLIC IRRIGATION ARCHIVE STRUCTURE AUDIT
==========================================================

Manifest files verified: {len(verified)}
SHA-256 failures: {(~verified['sha256_match']).sum()}
ISIL bundle extracted files: {len(zip_inv)}
Machine-readable text sources: {len(text_inv)}
Evidence snippets retained: {len(hits)}
RIRU layer records inventoried: {len(layers)}
Candidate public endpoints: {len(endpoints)}

Evidence appears in:
- Est Sesia references: {est_files} source files
- Lomellina/place references: {lom_files} source files
- flow/volume references: {flow_files} source files
- gauge/monitoring references: {monitor_files} source files

OCR used: NO
Association models fitted: 0
Frozen artifacts modified: 0

NEXT DECISION
-------------
Inspect:
1. c2a_public_irrigation_evidence_hits.csv
2. c2a_candidate_public_endpoints.csv
3. c2a_riru_layer_inventory.csv
4. c2a_isil_bundle_inventory.csv

The objective is to determine whether gauge-, canal-, district-, or
irrigation-unit-level historical data are already publicly reachable.
Only unresolved high-value gaps justify an institutional request.

C2A STATUS: PASS
"""
    (OUT / "c2a_public_archive_structure_summary.txt").write_text(
        summary, encoding="utf-8"
    )
    print("\n" + summary)


if __name__ == "__main__":
    main()

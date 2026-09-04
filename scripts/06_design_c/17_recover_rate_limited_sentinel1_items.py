"""Design C — C2K-R Recover Rate-Limited Sentinel-1 STAC Items.

PURPOSE
-------
Recover only the C2K Sentinel-1 scene IDs that failed because of HTTP 429
rate limiting, using conservative retries and delays. Merge recovered
metadata/assets with the original C2K outputs.

This is NOT a new scientific selection stage. C2J remains frozen.

FIREWALL
--------
- no SAR raster pixels read
- no VV/VH statistics calculated
- no flooding values read
- no groundwater values read
- no irrigation flows read
- no model fitted
- no C2J rule modified

INPUTS
------
outputs/diagnostics/design_c/c2k_validation_item_metadata.csv
outputs/diagnostics/design_c/c2k_validation_asset_inventory.csv

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2kr_validation_item_metadata_complete.csv
    c2kr_validation_asset_inventory_complete.csv
    c2kr_rate_limit_recovery_qa.json
    c2kr_rate_limit_recovery_summary.txt

RUN
---
python scripts/06_design_c/17_recover_rate_limited_sentinel1_items.py
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

ITEMS_IN = OUT / "c2k_validation_item_metadata.csv"
ASSETS_IN = OUT / "c2k_validation_asset_inventory.csv"

STAC_ROOT = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-1-grd"

BASE_DELAY_SECONDS = 2.0
MAX_ATTEMPTS = 7


def item_url(scene_id: str) -> str:
    return (
        f"{STAC_ROOT}/collections/{COLLECTION}/items/"
        + quote(scene_id, safe="")
    )


def fetch_json_retry(url: str):
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = Request(
            url,
            headers={
                "User-Agent": "DesignC-C2KR-rate-limit-recovery/1.0",
                "Accept": "application/geo+json,application/json",
            },
        )

        try:
            with urlopen(req, timeout=120) as r:
                payload = json.loads(r.read())
            return payload, attempt, None

        except HTTPError as e:
            last_error = repr(e)

            if e.code != 429:
                return None, attempt, last_error

            # Conservative exponential backoff with small jitter.
            wait = min(60.0, BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            wait += random.uniform(0.0, 1.0)

            retry_after = e.headers.get("Retry-After")
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    pass

            print(
                f"    HTTP 429 on attempt {attempt}/{MAX_ATTEMPTS}; "
                f"waiting {wait:.1f}s"
            )
            time.sleep(wait)

        except Exception as e:
            last_error = repr(e)
            wait = min(30.0, BASE_DELAY_SECONDS * attempt)
            print(
                f"    transient error on attempt {attempt}/{MAX_ATTEMPTS}; "
                f"waiting {wait:.1f}s: {last_error}"
            )
            time.sleep(wait)

    return None, MAX_ATTEMPTS, last_error


def normalize_platform(scene_id: str, p: dict) -> str | None:
    raw = p.get("platform") or p.get("constellation")

    if raw:
        s = str(raw).strip().lower()
        mapping = {
            "sentinel-1a": "S1A",
            "sentinel-1b": "S1B",
            "sentinel-1c": "S1C",
            "s1a": "S1A",
            "s1b": "S1B",
            "s1c": "S1C",
        }
        if s in mapping:
            return mapping[s]

    prefix = str(scene_id)[:3].upper()
    return prefix if prefix in {"S1A", "S1B", "S1C"} else raw


def item_row(scene_id: str, item: dict, attempts: int):
    p = item.get("properties", {})
    bbox = item.get("bbox")
    assets = item.get("assets", {}) or {}

    return {
        "scene_id": scene_id,
        "resolve_status": "OK",
        "resolve_error": None,
        "platform": normalize_platform(scene_id, p),
        "datetime": p.get("datetime") or p.get("start_datetime"),
        "end_datetime": p.get("end_datetime"),
        "instrument_mode": p.get("sar:instrument_mode"),
        "polarizations": "|".join(
            map(str, p.get("sar:polarizations", []) or [])
        ),
        "orbit_state": p.get("sat:orbit_state"),
        "relative_orbit": p.get("sat:relative_orbit"),
        "absolute_orbit": p.get("sat:absolute_orbit"),
        "product_type": p.get("sar:product_type"),
        "processing_level": p.get("processing:level"),
        "bbox": json.dumps(bbox) if bbox is not None else None,
        "asset_count": len(assets),
        "stac_item_url": item_url(scene_id),
        "recovery_attempts": attempts,
    }


def asset_rows(scene_id: str, item: dict):
    rows = []
    for key, a in (item.get("assets", {}) or {}).items():
        href = a.get("href")
        roles = a.get("roles", []) or []

        rows.append({
            "scene_id": scene_id,
            "asset_key": key,
            "title": a.get("title"),
            "media_type": a.get("type"),
            "roles": "|".join(map(str, roles)),
            "href": href,
            "is_data_role": "data" in roles,
            "looks_like_tiff": bool(
                href
                and str(href).lower().split("?")[0].endswith(
                    (".tif", ".tiff")
                )
            ),
        })

    return rows


def main():
    print("DESIGN C - C2K-R RATE-LIMITED SENTINEL-1 RECOVERY")
    print("=" * 64)
    print("Metadata recovery only.")
    print("NO SAR raster pixels read.")
    print("NO VV/VH statistics calculated.")
    print("NO scientific selection rule modified.\n")

    if not ITEMS_IN.exists():
        raise FileNotFoundError(f"Missing {ITEMS_IN}")
    if not ASSETS_IN.exists():
        raise FileNotFoundError(f"Missing {ASSETS_IN}")

    items = pd.read_csv(ITEMS_IN)
    assets = pd.read_csv(ASSETS_IN)

    failed = items.loc[
        ~items["resolve_status"].eq("OK")
    ].copy()

    print(f"C2K items: {len(items)}")
    print(f"Already resolved: {(items.resolve_status == 'OK').sum()}")
    print(f"To recover: {len(failed)}\n")

    recovered_item_rows = []
    recovered_asset_rows = []
    remaining_failures = []

    for i, scene_id in enumerate(failed["scene_id"].astype(str), 1):
        print(f"[{i:02d}/{len(failed):02d}] {scene_id}")

        # Space successful requests too, not only failed requests.
        if i > 1:
            time.sleep(BASE_DELAY_SECONDS)

        item, attempts, err = fetch_json_retry(item_url(scene_id))

        if item is None:
            print(f"    FAILED after {attempts} attempts: {err}")
            remaining_failures.append({
                "scene_id": scene_id,
                "attempts": attempts,
                "error": err,
            })
            continue

        ir = item_row(scene_id, item, attempts)
        ars = asset_rows(scene_id, item)

        recovered_item_rows.append(ir)
        recovered_asset_rows.extend(ars)

        print(
            f"    OK after {attempts} attempt(s); "
            f"assets={len(ars)}; platform={ir['platform']}"
        )

    rec_items = pd.DataFrame(recovered_item_rows)
    rec_assets = pd.DataFrame(recovered_asset_rows)

    # Keep successful original C2K rows, replace failures with recovered rows.
    good_original = items.loc[
        items["resolve_status"].eq("OK")
    ].copy()

    if "recovery_attempts" not in good_original.columns:
        good_original["recovery_attempts"] = 0

    # Normalize platform labels in successful originals.
    good_original["platform"] = [
        (
            str(sid)[:3].upper()
            if str(sid)[:3].upper() in {"S1A", "S1B", "S1C"}
            else plat
        )
        for sid, plat in zip(
            good_original["scene_id"],
            good_original["platform"]
        )
    ]

    complete_items = pd.concat(
        [good_original, rec_items],
        ignore_index=True,
        sort=False,
    ).sort_values("scene_id")

    recovered_ids = set(rec_items["scene_id"]) if len(rec_items) else set()

    # Original assets exist only for successfully resolved originals.
    complete_assets = pd.concat(
        [assets, rec_assets],
        ignore_index=True,
        sort=False,
    )

    complete_items.to_csv(
        OUT / "c2kr_validation_item_metadata_complete.csv",
        index=False,
    )
    complete_assets.to_csv(
        OUT / "c2kr_validation_asset_inventory_complete.csv",
        index=False,
    )

    expected_n = int(len(items))
    resolved_n = int(
        complete_items["scene_id"].nunique()
    )
    remaining_n = expected_n - resolved_n

    platform_counts = (
        complete_items["platform"]
        .value_counts(dropna=False)
        .to_dict()
    )

    technical_mismatch = complete_items.loc[
        ~(
            complete_items["instrument_mode"].eq("IW")
            & complete_items["polarizations"].eq("VV|VH")
            & complete_items["orbit_state"].isin(
                ["ascending", "descending"]
            )
        )
    ].copy()

    qa = {
        "status": "PASS" if remaining_n == 0 else "PASS_WITH_LIMITATIONS",
        "stage": "DESIGN_C_C2KR_RATE_LIMIT_RECOVERY",
        "expected_scene_ids_n": expected_n,
        "already_resolved_before_recovery_n": int(len(good_original)),
        "attempted_recovery_n": int(len(failed)),
        "recovered_scene_ids_n": int(len(recovered_ids)),
        "remaining_unresolved_scene_ids_n": int(remaining_n),
        "platform_counts": {
            str(k): int(v) for k, v in platform_counts.items()
        },
        "technical_mismatch_scene_ids_n": int(len(technical_mismatch)),
        "asset_rows_complete_n": int(len(complete_assets)),
        "sar_raster_pixels_read": 0,
        "vv_vh_statistics_calculated": 0,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "interpretation": (
            "HTTP 429 recovery is an infrastructure/catalogue-access step "
            "and does not alter the frozen scientific design."
        ),
    }

    (OUT / "c2kr_rate_limit_recovery_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    failures_df = pd.DataFrame(remaining_failures)

    lines = [
        "DESIGN C - C2K-R RATE-LIMITED SENTINEL-1 RECOVERY",
        "=" * 62,
        "",
        f"Expected frozen scene IDs: {expected_n}",
        f"Already resolved before recovery: {len(good_original)}",
        f"Recovery attempted: {len(failed)}",
        f"Recovered now: {len(recovered_ids)}",
        f"Total resolved after recovery: {resolved_n}",
        f"Remaining unresolved: {remaining_n}",
        "",
        "PLATFORMS",
        "---------",
        pd.Series(platform_counts).to_string(),
        "",
        f"Complete asset rows: {len(complete_assets)}",
        f"Technical metadata mismatches: {len(technical_mismatch)}",
        "",
    ]

    if len(failures_df):
        lines += [
            "REMAINING FAILURES",
            "------------------",
            failures_df.to_string(index=False),
            "",
        ]

    lines += [
        "FIREWALL",
        "--------",
        "No SAR raster pixels read.",
        "No VV/VH values calculated.",
        "No groundwater or irrigation outcomes read.",
        "C2J frozen universe unchanged.",
        "",
        f"C2K-R STATUS: {qa['status']}",
    ]

    txt = "\n".join(lines) + "\n"
    (OUT / "c2kr_rate_limit_recovery_summary.txt").write_text(
        txt,
        encoding="utf-8",
    )

    print("\n" + txt)


if __name__ == "__main__":
    main()

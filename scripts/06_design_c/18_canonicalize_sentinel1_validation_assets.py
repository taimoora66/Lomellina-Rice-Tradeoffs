"""Design C — C2L Canonical Sentinel-1 Asset Plan.

PURPOSE
-------
Using the complete C2K-R metadata/assets, build a canonical raster-asset plan
for the 18 C2J-frozen validation targets BEFORE opening any SAR raster.

This stage resolves:
1. duplicate/alternate STAC item representations with identical acquisition
   geometry/time;
2. exact VV and VH data assets;
3. same-track same-date mosaic membership;
4. platform identity (S1A/S1B/S1C);
5. a deterministic canonical scene/asset plan for the next raster-reading stage.

FIREWALL
--------
- no raster pixels opened/read
- no VV/VH statistics calculated
- no flooding values read
- no groundwater values read
- no irrigation-flow values read
- no thresholds tuned
- no association model fitted
- no C2J scientific rule modified

INPUTS
------
outputs/diagnostics/design_c/c2j_sar_validation_manifest.csv
outputs/diagnostics/design_c/c2kr_validation_item_metadata_complete.csv
outputs/diagnostics/design_c/c2kr_validation_asset_inventory_complete.csv

OUTPUTS
-------
outputs/diagnostics/design_c/
    c2l_scene_duplicate_groups.csv
    c2l_canonical_scene_inventory.csv
    c2l_canonical_vvvh_asset_plan.csv
    c2l_target_mosaic_asset_plan.csv
    c2l_canonical_asset_plan_qa.json
    c2l_canonical_asset_plan_summary.txt

RUN
---
python scripts/06_design_c/18_canonicalize_sentinel1_validation_assets.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "diagnostics" / "design_c"
OUT.mkdir(parents=True, exist_ok=True)

MANIFEST = OUT / "c2j_sar_validation_manifest.csv"
ITEMS = OUT / "c2kr_validation_item_metadata_complete.csv"
ASSETS = OUT / "c2kr_validation_asset_inventory_complete.csv"


def norm(x):
    return str(x).strip().lower()


def classify_pol_asset(row):
    """Return VV, VH, or None from metadata only."""
    text = " ".join(
        [
            norm(row.get("asset_key", "")),
            norm(row.get("title", "")),
            norm(row.get("href", "")),
        ]
    )

    # Prefer token-style matches; avoid accidental substring matches.
    vv = bool(re.search(r"(^|[^a-z0-9])vv([^a-z0-9]|$)", text))
    vh = bool(re.search(r"(^|[^a-z0-9])vh([^a-z0-9]|$)", text))

    if vv and not vh:
        return "VV"
    if vh and not vv:
        return "VH"
    return None


def parse_bbox(x):
    if pd.isna(x):
        return None
    try:
        b = json.loads(x) if isinstance(x, str) else x
        if b and len(b) >= 4:
            return tuple(round(float(v), 6) for v in b[:4])
    except Exception:
        return None
    return None


def platform_norm(scene_id, platform):
    p = str(platform).strip().upper()
    if p in {"S1A", "S1B", "S1C"}:
        return p
    s = str(scene_id)[:3].upper()
    return s if s in {"S1A", "S1B", "S1C"} else p


def main():
    print("DESIGN C - C2L CANONICAL SENTINEL-1 ASSET PLAN")
    print("=" * 62)
    print("NO SAR raster pixels read.")
    print("NO VV/VH statistics calculated.")
    print("NO flooding, groundwater, or irrigation outcomes read.")
    print("NO C2J rule modified.\n")

    for p in [MANIFEST, ITEMS, ASSETS]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required input: {p}")

    manifest = pd.read_csv(MANIFEST)
    items = pd.read_csv(ITEMS)
    assets = pd.read_csv(ASSETS)

    items["datetime"] = pd.to_datetime(
        items["datetime"], errors="coerce", utc=True
    )
    items["end_datetime"] = pd.to_datetime(
        items["end_datetime"], errors="coerce", utc=True
    )
    items["platform_norm"] = [
        platform_norm(s, p)
        for s, p in zip(items["scene_id"], items["platform"])
    ]
    items["_bbox_key"] = items["bbox"].apply(parse_bbox)

    # Duplicate/alternate representation key:
    # same platform, acquisition start/end, orbit, and bbox.
    dup_cols = [
        "platform_norm", "datetime", "end_datetime",
        "orbit_state", "relative_orbit", "_bbox_key"
    ]

    items["_dup_key"] = (
        items[dup_cols]
        .astype(str)
        .agg("|".join, axis=1)
    )

    dup_summary = (
        items.groupby("_dup_key")
        .agg(
            scene_ids_n=("scene_id", "nunique"),
            scene_ids=("scene_id", lambda x: "|".join(sorted(set(map(str, x))))),
            platform=("platform_norm", "first"),
            datetime=("datetime", "first"),
            end_datetime=("end_datetime", "first"),
            orbit_state=("orbit_state", "first"),
            relative_orbit=("relative_orbit", "first"),
            bbox=("bbox", "first"),
        )
        .reset_index()
    )
    dup_summary["is_duplicate_group"] = dup_summary["scene_ids_n"] > 1
    dup_summary.to_csv(
        OUT / "c2l_scene_duplicate_groups.csv", index=False
    )

    # Asset classification.
    assets["polarization_asset"] = assets.apply(
        classify_pol_asset, axis=1
    )

    # Score each scene for canonicalization:
    # prefer both VV/VH identified, data-role assets, TIFF-like assets,
    # then deterministic lexical scene_id.
    asset_scene = (
        assets.groupby("scene_id")
        .agg(
            vv_assets_n=("polarization_asset", lambda x: int((x == "VV").sum())),
            vh_assets_n=("polarization_asset", lambda x: int((x == "VH").sum())),
            data_role_assets_n=("is_data_role", "sum"),
            tiff_assets_n=("looks_like_tiff", "sum"),
            asset_rows_n=("asset_key", "count"),
        )
        .reset_index()
    )

    ix = items.merge(asset_scene, on="scene_id", how="left")
    for c in [
        "vv_assets_n", "vh_assets_n", "data_role_assets_n",
        "tiff_assets_n", "asset_rows_n"
    ]:
        ix[c] = ix[c].fillna(0).astype(int)

    ix["has_both_vv_vh"] = (
        (ix["vv_assets_n"] > 0) & (ix["vh_assets_n"] > 0)
    )

    canonical_rows = []
    for key, g in ix.groupby("_dup_key"):
        z = g.sort_values(
            [
                "has_both_vv_vh",
                "data_role_assets_n",
                "tiff_assets_n",
                "asset_rows_n",
                "scene_id",
            ],
            ascending=[False, False, False, False, True],
        ).copy()

        chosen = z.iloc[0]

        for rank, (_, r) in enumerate(z.iterrows(), 1):
            canonical_rows.append({
                "duplicate_group_key": key,
                "scene_id": r["scene_id"],
                "canonical_rank": rank,
                "is_canonical_scene": rank == 1,
                "canonical_scene_id": chosen["scene_id"],
                "duplicate_group_size": len(z),
                "platform": r["platform_norm"],
                "datetime": r["datetime"],
                "end_datetime": r["end_datetime"],
                "orbit_state": r["orbit_state"],
                "relative_orbit": r["relative_orbit"],
                "bbox": r["bbox"],
                "vv_assets_n": r["vv_assets_n"],
                "vh_assets_n": r["vh_assets_n"],
                "data_role_assets_n": r["data_role_assets_n"],
                "tiff_assets_n": r["tiff_assets_n"],
                "asset_rows_n": r["asset_rows_n"],
            })

    canon = pd.DataFrame(canonical_rows)
    canon.to_csv(
        OUT / "c2l_canonical_scene_inventory.csv",
        index=False,
    )

    canonical_ids = set(
        canon.loc[canon["is_canonical_scene"], "scene_id"].astype(str)
    )

    # Candidate exact polarization assets for canonical scenes only.
    a = assets.loc[
        assets["scene_id"].astype(str).isin(canonical_ids)
        & assets["polarization_asset"].isin(["VV", "VH"])
    ].copy()

    # Rank asset choices within scene x polarization.
    # Prefer data role, then TIFF-like, then key/href lexical.
    a = a.sort_values(
        [
            "scene_id", "polarization_asset",
            "is_data_role", "looks_like_tiff",
            "asset_key", "href"
        ],
        ascending=[True, True, False, False, True, True],
    )
    a["asset_rank"] = (
        a.groupby(["scene_id", "polarization_asset"])
        .cumcount() + 1
    )
    a["is_selected_asset"] = a["asset_rank"].eq(1)

    a.to_csv(
        OUT / "c2l_canonical_vvvh_asset_plan.csv",
        index=False,
    )

    selected = a[a["is_selected_asset"]].copy()

    # Map original frozen scene IDs to canonical scene IDs.
    map_original_to_canon = dict(
        zip(
            canon["scene_id"].astype(str),
            canon["canonical_scene_id"].astype(str),
        )
    )

    manifest = manifest[
        manifest["selection_status"].eq("SELECTED")
    ].copy()

    target_rows = []

    for _, r in manifest.iterrows():
        original_ids = [
            x for x in str(r["scene_ids"]).split("|") if x
        ]

        canonical_target_ids = sorted(set(
            map_original_to_canon.get(x, x) for x in original_ids
        ))

        for sid in canonical_target_ids:
            im = items[items["scene_id"].astype(str).eq(sid)]
            sel = selected[selected["scene_id"].astype(str).eq(sid)]

            vv = sel[sel["polarization_asset"].eq("VV")]
            vh = sel[sel["polarization_asset"].eq("VH")]

            target_rows.append({
                "anchor_year": int(r["anchor_year"]),
                "season_phase": r["season_phase"],
                "selected_date": r["selected_date"],
                "orbit_state": r["orbit_state"],
                "relative_orbit": int(r["relative_orbit"]),
                "canonical_scene_id": sid,
                "platform": (
                    platform_norm(
                        sid,
                        im.iloc[0]["platform"]
                    )
                    if len(im) else sid[:3]
                ),
                "vv_asset_found": len(vv) == 1,
                "vv_asset_key": vv.iloc[0]["asset_key"] if len(vv) else None,
                "vv_href": vv.iloc[0]["href"] if len(vv) else None,
                "vh_asset_found": len(vh) == 1,
                "vh_asset_key": vh.iloc[0]["asset_key"] if len(vh) else None,
                "vh_href": vh.iloc[0]["href"] if len(vh) else None,
            })

    plan = pd.DataFrame(target_rows)

    target_id_cols = [
        "anchor_year", "season_phase", "selected_date",
        "orbit_state", "relative_orbit"
    ]

    target_summary = (
        plan.groupby(target_id_cols)
        .agg(
            canonical_scenes_n=("canonical_scene_id", "nunique"),
            platforms=("platform", lambda x: "|".join(sorted(set(map(str, x))))),
            vv_assets_complete=("vv_asset_found", "all"),
            vh_assets_complete=("vh_asset_found", "all"),
        )
        .reset_index()
    )

    plan = plan.merge(
        target_summary,
        on=target_id_cols,
        how="left",
    )

    plan.to_csv(
        OUT / "c2l_target_mosaic_asset_plan.csv",
        index=False,
    )

    duplicate_groups_n = int(
        dup_summary["is_duplicate_group"].sum()
    )
    duplicate_scene_rows_n = int(
        canon.loc[
            canon["duplicate_group_size"] > 1,
            "scene_id"
        ].nunique()
    )

    vv_missing = int((~plan["vv_asset_found"]).sum())
    vh_missing = int((~plan["vh_asset_found"]).sum())

    targets_complete = int(
        target_summary[
            target_summary["vv_assets_complete"]
            & target_summary["vh_assets_complete"]
        ].shape[0]
    )

    qa = {
        "status": (
            "PASS"
            if vv_missing == 0 and vh_missing == 0
            else "PASS_WITH_LIMITATIONS"
        ),
        "stage": "DESIGN_C_C2L_CANONICAL_SENTINEL_ASSET_PLAN",
        "frozen_targets_n": int(len(target_summary)),
        "input_scene_ids_n": int(items["scene_id"].nunique()),
        "duplicate_or_alternate_groups_n": duplicate_groups_n,
        "scene_ids_in_duplicate_groups_n": duplicate_scene_rows_n,
        "canonical_scene_ids_n": int(
            canon["canonical_scene_id"].nunique()
        ),
        "selected_vv_assets_n": int(
            (
                selected["polarization_asset"] == "VV"
            ).sum()
        ),
        "selected_vh_assets_n": int(
            (
                selected["polarization_asset"] == "VH"
            ).sum()
        ),
        "target_scene_rows_missing_vv_asset_n": vv_missing,
        "target_scene_rows_missing_vh_asset_n": vh_missing,
        "targets_with_complete_vv_vh_assets_n": targets_complete,
        "sar_raster_pixels_read": 0,
        "vv_vh_statistics_calculated": 0,
        "flooding_values_read": 0,
        "groundwater_level_values_read": 0,
        "irrigation_flow_values_read": 0,
        "thresholds_tuned": 0,
        "association_models_fitted": 0,
        "c2j_frozen_rule_modified": False,
        "canonicalization_rule": (
            "Within identical platform/time/orbit/bbox groups, prefer scene "
            "with both identifiable VV and VH assets, then more data-role "
            "assets, then more TIFF assets, then lexical scene_id."
        ),
        "next_stage": (
            "Open only the frozen canonical VV/VH assets and read only the "
            "required study-area windows for SAR measurement validation."
        ),
    }

    (OUT / "c2l_canonical_asset_plan_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "DESIGN C - C2L CANONICAL SENTINEL-1 ASSET PLAN",
        "=" * 60,
        "",
        f"Frozen targets: {len(target_summary)}",
        f"Input scene IDs: {items['scene_id'].nunique()}",
        f"Duplicate/alternate groups: {duplicate_groups_n}",
        f"Canonical scene IDs: {canon['canonical_scene_id'].nunique()}",
        f"Selected VV assets: {(selected['polarization_asset'] == 'VV').sum()}",
        f"Selected VH assets: {(selected['polarization_asset'] == 'VH').sum()}",
        f"Target-scene rows missing VV: {vv_missing}",
        f"Target-scene rows missing VH: {vh_missing}",
        f"Targets complete for VV+VH: {targets_complete}/{len(target_summary)}",
        "",
        "TARGET MOSAIC PLAN",
        "------------------",
        target_summary.to_string(index=False),
        "",
        "DUPLICATE / ALTERNATE ITEM GROUPS",
        "---------------------------------",
        dup_summary[
            dup_summary["is_duplicate_group"]
        ].to_string(index=False),
        "",
        "FIREWALL",
        "--------",
        "No raster pixels opened/read.",
        "No VV/VH statistics calculated.",
        "No flooding, groundwater, or irrigation outcomes read.",
        "C2J frozen universe unchanged.",
        "",
        f"C2L STATUS: {qa['status']}",
    ]

    txt = "\n".join(lines) + "\n"
    (OUT / "c2l_canonical_asset_plan_summary.txt").write_text(
        txt,
        encoding="utf-8",
    )

    print(txt)


if __name__ == "__main__":
    main()

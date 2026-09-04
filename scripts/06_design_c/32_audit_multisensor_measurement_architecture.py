"""Design C — C2S pre-freeze multi-sensor measurement architecture audit.

Purpose
-------
Summarize the already-completed C2Q-R + C2R evidence at the TARGET level to
decide what can and cannot be frozen for the next measurement-development
stage WITHOUT reading groundwater.

This script deliberately does NOT choose an inundation threshold or fit a
classifier. It documents construct-validity consistency of the seven
prespecified single-sensor variables and determines whether a single-snapshot
architecture is defensible.

Inputs
------
outputs/diagnostics/design_c/c2qr_target_cross_sensor_summary.csv
outputs/diagnostics/design_c/c2r_observed_ff_sensor_rank_associations.csv
outputs/diagnostics/design_c/c2r_observed_ff_target_summary.csv

Outputs
-------
outputs/diagnostics/design_c/c2s_sensor_construct_consistency.csv
outputs/diagnostics/design_c/c2s_phase_construct_consistency.csv
outputs/diagnostics/design_c/c2s_measurement_architecture_decision.json
outputs/diagnostics/design_c/c2s_measurement_architecture_decision.txt

Decision logic
--------------
This is NOT performance optimization.

A single-snapshot variable is considered sufficiently directionally stable
only if, among target dates with >=100 paired observations:
- at least 3 target dates are available;
- >=75% of non-zero Spearman signs agree;
- median absolute rho >=0.20.

These thresholds are methodological screening rules, not tuned to groundwater
or to maximize any sensor's score.

Regardless of screening result, no flood/no-flood threshold is selected here.

Run
---
python -u scripts/06_design_c/32_audit_multisensor_measurement_architecture.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "outputs" / "diagnostics" / "design_c"

ASSOC_IN = D / "c2r_observed_ff_sensor_rank_associations.csv"
TARGET_IN = D / "c2r_observed_ff_target_summary.csv"
CROSS_IN = D / "c2qr_target_cross_sensor_summary.csv"

OUT_SENSOR = D / "c2s_sensor_construct_consistency.csv"
OUT_PHASE = D / "c2s_phase_construct_consistency.csv"
OUT_JSON = D / "c2s_measurement_architecture_decision.json"
OUT_TXT = D / "c2s_measurement_architecture_decision.txt"

MIN_PAIRED_N = 100
MIN_TARGETS = 3
MIN_SIGN_AGREEMENT = 0.75
MIN_MEDIAN_ABS_RHO = 0.20

SENSORS = [
    "VV_db", "VH_db", "VV_minus_VH_db",
    "NDVI", "NDWI", "MNDWI", "LSWI",
]


def med(x):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(x.median()) if len(x) else np.nan


def sign_label(x):
    if not np.isfinite(x) or x == 0:
        return "zero_or_missing"
    return "positive" if x > 0 else "negative"


def main():
    print("DESIGN C - C2S PRE-FREEZE MULTI-SENSOR MEASUREMENT ARCHITECTURE AUDIT")
    print("=" * 82)
    print("No groundwater. No classifier. No inundation threshold.\n")

    for f in [ASSOC_IN, TARGET_IN, CROSS_IN]:
        if not f.exists():
            raise FileNotFoundError(f)

    a = pd.read_csv(ASSOC_IN)
    t = pd.read_csv(TARGET_IN)
    c = pd.read_csv(CROSS_IN)

    req_a = {
        "target_id","anchor_year","season_phase","sensor_variable",
        "paired_n","spearman_rho_ff_sensor"
    }
    if req_a-set(a.columns):
        raise AssertionError(f"Association input missing {sorted(req_a-set(a.columns))}")

    a = a[a["sensor_variable"].isin(SENSORS)].copy()
    a["paired_n"] = pd.to_numeric(a["paired_n"], errors="coerce")
    a["rho"] = pd.to_numeric(a["spearman_rho_ff_sensor"], errors="coerce")
    a["eligible"] = (a["paired_n"] >= MIN_PAIRED_N) & np.isfinite(a["rho"])
    a["rho_sign"] = a["rho"].map(sign_label)

    sensor_rows = []
    for s, g in a.groupby("sensor_variable", sort=False):
        e = g[g["eligible"]].copy()
        pos = int((e["rho"] > 0).sum())
        neg = int((e["rho"] < 0).sum())
        nonzero = pos + neg
        majority = max(pos, neg)
        sign_agreement = majority / nonzero if nonzero else np.nan
        majority_sign = (
            "positive" if pos > neg else
            "negative" if neg > pos else
            "tie"
        )
        median_abs = med(e["rho"].abs())
        stable = bool(
            len(e) >= MIN_TARGETS
            and np.isfinite(sign_agreement)
            and sign_agreement >= MIN_SIGN_AGREEMENT
            and np.isfinite(median_abs)
            and median_abs >= MIN_MEDIAN_ABS_RHO
        )
        sensor_rows.append({
            "sensor_variable": s,
            "eligible_targets_n": int(len(e)),
            "positive_targets_n": pos,
            "negative_targets_n": neg,
            "majority_sign": majority_sign,
            "sign_agreement_share": sign_agreement,
            "median_rho": med(e["rho"]),
            "median_absolute_rho": median_abs,
            "min_rho": float(e["rho"].min()) if len(e) else np.nan,
            "max_rho": float(e["rho"].max()) if len(e) else np.nan,
            "single_snapshot_stability_screen_pass": stable,
        })

    ss = pd.DataFrame(sensor_rows)
    ss.to_csv(OUT_SENSOR, index=False)

    phase_rows = []
    for (phase, s), g in a[a["eligible"]].groupby(
        ["season_phase","sensor_variable"], sort=True
    ):
        pos = int((g["rho"] > 0).sum())
        neg = int((g["rho"] < 0).sum())
        n = pos + neg
        phase_rows.append({
            "season_phase": phase,
            "sensor_variable": s,
            "eligible_targets_n": int(len(g)),
            "positive_targets_n": pos,
            "negative_targets_n": neg,
            "majority_sign": (
                "positive" if pos > neg else
                "negative" if neg > pos else
                "tie"
            ),
            "sign_agreement_share": max(pos,neg)/n if n else np.nan,
            "median_rho": med(g["rho"]),
            "median_absolute_rho": med(g["rho"].abs()),
        })
    ps = pd.DataFrame(phase_rows)
    ps.to_csv(OUT_PHASE, index=False)

    passing = ss.loc[
        ss["single_snapshot_stability_screen_pass"], "sensor_variable"
    ].tolist()

    # Architecture decision is deliberately conservative:
    # even if one snapshot variable passes, annual FF is a seasonal construct,
    # while target observations are snapshots. Therefore the next frozen
    # development architecture is temporal/phenological, not a snapshot label.
    decision = {
        "stage": "DESIGN_C_C2S_PRE_FREEZE_MEASUREMENT_ARCHITECTURE_AUDIT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "technical_status": "PASS",
        "screening_rules": {
            "minimum_paired_n_per_target": MIN_PAIRED_N,
            "minimum_eligible_targets": MIN_TARGETS,
            "minimum_sign_agreement_share": MIN_SIGN_AGREEMENT,
            "minimum_median_absolute_spearman_rho": MIN_MEDIAN_ABS_RHO,
        },
        "single_snapshot_variables_passing_screen": passing,
        "single_snapshot_architecture_frozen": False,
        "reason": (
            "Observed RiceFloodIT FF is an annual/seasonal flooding-frequency "
            "construct whereas S1/S2 anchors are date-specific snapshots. "
            "Associations vary materially by phenological phase and sensor. "
            "A single-date threshold/classifier would therefore conflate "
            "seasonal state with annual inundation behavior."
        ),
        "next_measurement_architecture": {
            "primary": (
                "multi-temporal Sentinel-1 phenology using the stable outcome-blind "
                "track families and all suitable rice-season acquisitions"
            ),
            "secondary_support": (
                "Sentinel-2 clear-pixel optical phenology/water-state descriptors"
            ),
            "historical_bridge": (
                "observed RiceFloodIT FF through 2021 and the separately frozen "
                "MODIS RiceFloodIT-compatible reconstruction through 2025"
            ),
        },
        "groundwater_values_read": False,
        "irrigation_flow_values_read": False,
        "inundation_threshold_selected": False,
        "classifier_fitted": False,
        "composite_score_optimized": False,
        "p_values_used": False,
    }
    OUT_JSON.write_text(json.dumps(decision, indent=2)+"\n", encoding="utf-8")

    lines = [
        "DESIGN C - C2S PRE-FREEZE MULTI-SENSOR MEASUREMENT ARCHITECTURE AUDIT",
        "="*82,
        "",
        f"Eligible target rule: paired_n >= {MIN_PAIRED_N}",
        f"Single-snapshot stability screen: >= {MIN_TARGETS} targets, "
        f">= {MIN_SIGN_AGREEMENT:.0%} sign agreement, "
        f"median |rho| >= {MIN_MEDIAN_ABS_RHO:.2f}",
        "",
        "SINGLE-SNAPSHOT SENSOR SCREEN",
        "-----------------------------",
    ]
    for _, r in ss.iterrows():
        lines.append(
            f"{r.sensor_variable:16s} targets={int(r.eligible_targets_n):2d} "
            f"majority={r.majority_sign:8s} "
            f"sign_agree={r.sign_agreement_share:.3f} "
            f"median_rho={r.median_rho:.3f} "
            f"median_|rho|={r.median_absolute_rho:.3f} "
            f"PASS={bool(r.single_snapshot_stability_screen_pass)}"
        )

    lines += [
        "",
        f"Variables passing screen: {passing if passing else 'NONE'}",
        "",
        "ARCHITECTURE DECISION",
        "---------------------",
        "Do NOT freeze a single-snapshot inundation classifier.",
        "Proceed to multi-temporal Sentinel-1 phenology as the primary measurement backbone.",
        "Use Sentinel-2 as clear-pixel optical support, not as the sole backbone.",
        "Retain observed RiceFloodIT/MODIS-compatible FF as the seasonal historical bridge.",
        "",
        "Groundwater read: False",
        "Threshold selected: False",
        "Classifier fitted: False",
        "Composite score optimized: False",
        "",
        "C2S STATUS: PASS",
    ]

    txt = "\n".join(lines)+"\n"
    OUT_TXT.write_text(txt, encoding="utf-8")
    print(txt)

    print("PHASE-SPECIFIC CONSTRUCT CONSISTENCY")
    print("------------------------------------")
    pd.set_option("display.width", 260)
    print(ps.to_string(index=False))


if __name__ == "__main__":
    main()

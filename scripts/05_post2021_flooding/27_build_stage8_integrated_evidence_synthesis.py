"""Stage 8 — Integrated evidence synthesis for publication.

Scientific role
---------------
Assemble already-completed, already-frozen analyses into publication-ready
evidence tables and figure-data files. NO model is fitted in this script.

Evidence chronology is preserved:
1. Historical 2008-2021 publication reanalysis — historically informed,
   not an untouched confirmation.
2. Genuine held-out 2022-2023 first-difference confirmation.
3. Prespecified subsequent 2022-2025 extension conditional on prior knowledge.
4. Stage-6 / Stage-6R identification-information audit.
5. Stage-7 prespecified robustness/stability hierarchy.

This script never promotes a robustness result to primary status and never
selects estimates according to sign, magnitude, precision, CI, or p-value.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

HIST_IN = (
    ROOT / "outputs" / "diagnostics" / "publication_groundwater"
    / "historical_publication_inference_summary.csv"
)
HELDOUT_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "heldout_groundwater_primary_result.csv"
)
STAGE5_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage5_primary_groundwater_result_2022_2025.csv"
)
STAGE6_QA_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage6_identification_information_qa.json"
)
STAGE6R_QA_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage6r_replication_qa.json"
)
STAGE7_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage7_robustness_results_2022_2025.csv"
)
STAGE7_LOOY_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage7_primary_leave_one_year_out.csv"
)
STAGE7_QA_IN = (
    ROOT / "outputs" / "diagnostics" / "post2021"
    / "stage7_robustness_qa.json"
)

OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

MAIN_TABLE_OUT = OUT_DIR / "stage8_publication_main_evidence_table.csv"
ROBUSTNESS_TABLE_OUT = OUT_DIR / "stage8_publication_robustness_table.csv"
IDENTIFICATION_TABLE_OUT = OUT_DIR / "stage8_publication_identification_table.csv"
FIGURE_ESTIMATES_OUT = OUT_DIR / "stage8_figure_estimate_sequence_data.csv"
FIGURE_STABILITY_OUT = OUT_DIR / "stage8_figure_stability_data.csv"
CLAIMS_OUT = OUT_DIR / "stage8_claims_and_limits_matrix.csv"
QA_OUT = OUT_DIR / "stage8_synthesis_qa.json"
SUMMARY_OUT = OUT_DIR / "stage8_integrated_evidence_summary.txt"


def require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def first_existing(row: pd.Series, names: list[str], required=True):
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return row[name]
    if required:
        raise KeyError(f"None of candidate columns found/nonmissing: {names}")
    return np.nan


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for p, label in [
        (HIST_IN, "Historical inference summary"),
        (HELDOUT_IN, "Held-out 2022-2023 primary result"),
        (STAGE5_IN, "Stage-5 primary result"),
        (STAGE6_QA_IN, "Stage-6 QA"),
        (STAGE6R_QA_IN, "Stage-6R QA"),
        (STAGE7_IN, "Stage-7 robustness results"),
        (STAGE7_LOOY_IN, "Stage-7 leave-one-year results"),
        (STAGE7_QA_IN, "Stage-7 QA"),
    ]:
        require(p, label)

    # ------------------------------------------------------------------
    # 1. Historical primary publication inference.
    # ------------------------------------------------------------------
    hist = pd.read_csv(HIST_IN)

    if "primary" not in hist.columns:
        raise AssertionError("Historical summary lacks primary flag.")

    primary_mask = (
        hist["primary"].astype(str).str.lower().isin(["true", "1"])
        if hist["primary"].dtype == object
        else hist["primary"].astype(bool)
    )
    h = hist.loc[primary_mask].copy()

    if len(h) != 1:
        raise AssertionError(
            f"Expected exactly one historical primary inference; found {len(h)}."
        )
    h = h.iloc[0]

    hist_beta = float(h["beta"])
    hist_se = float(h["se"])
    hist_lo = float(h["ci95_low_reported"])
    hist_hi = float(h["ci95_high_reported"])
    hist_p = float(h["p_reported"])

    # ------------------------------------------------------------------
    # 2. Genuine held-out 2022-2023 first-difference primary.
    # ------------------------------------------------------------------
    held = pd.read_csv(HELDOUT_IN)
    if len(held) != 1:
        raise AssertionError(
            f"Held-out primary result must contain one row; found {len(held)}."
        )
    ho = held.iloc[0]

    held_beta = float(first_existing(ho, ["estimate", "beta", "beta_hat"]))
    held_se = float(first_existing(ho, ["hc3_se", "se"]))
    held_p = float(first_existing(ho, ["p_value", "p", "p_value_hc3"]))
    held_lo = float(first_existing(ho, ["ci95_low", "ci_low", "ci95_low_hc3"]))
    held_hi = float(first_existing(ho, ["ci95_high", "ci_high", "ci95_high_hc3"]))
    held_n = int(float(first_existing(ho, ["n", "N"])))

    # ------------------------------------------------------------------
    # 3. 2022-2025 frozen Stage-5 primary.
    # ------------------------------------------------------------------
    s5 = pd.read_csv(STAGE5_IN)
    if len(s5) != 1:
        raise AssertionError("Stage-5 primary result must contain exactly one row.")
    p = s5.iloc[0]

    s5_beta = float(first_existing(
        p, ["beta_hat_per_1_ff10", "beta_per_1_ff10", "beta_hat"]
    ))
    s5_se = float(first_existing(p, ["cv3j_se"]))
    s5_lo = float(first_existing(p, ["cv3j_ci_low", "cv3j_ci95_low"]))
    s5_hi = float(first_existing(p, ["cv3j_ci_high", "cv3j_ci95_high"]))
    s5_p = float(first_existing(
        p, ["wcr31_webb_p_value", "wcr31_webb_p", "wcr31_webb_two_sided_p", "wcr31_p"]
    ))

    # ------------------------------------------------------------------
    # 4. Main evidence sequence table.
    # ------------------------------------------------------------------
    main = pd.DataFrame([
        {
            "sequence": 1,
            "evidence_block": "Historical publication reanalysis",
            "period": "2008-2021",
            "epistemic_status": (
                "historically informed frozen reanalysis; not untouched confirmation"
            ),
            "design": "historical publication groundwater model",
            "beta_per_1_ff10": hist_beta,
            "se_primary": hist_se,
            "ci95_low": hist_lo,
            "ci95_high": hist_hi,
            "p_primary": hist_p,
            "primary_inference": str(h["inference"]),
            "N": int(h["N"]),
            "wells": int(h["wells"]),
            "years": int(h["years"]),
            "direction": "positive" if hist_beta > 0 else "negative",
            "publication_role": "historical evidence",
        },
        {
            "sequence": 2,
            "evidence_block": "Genuine held-out confirmation",
            "period": "2022-2023",
            "epistemic_status": (
                "genuine held-out test under frozen bridge/sample/model protocol"
            ),
            "design": "13-well first difference; HC3",
            "beta_per_1_ff10": held_beta,
            "se_primary": held_se,
            "ci95_low": held_lo,
            "ci95_high": held_hi,
            "p_primary": held_p,
            "primary_inference": "HC3",
            "N": held_n,
            "wells": held_n,
            "years": 2,
            "direction": "positive" if held_beta > 0 else "negative",
            "publication_role": "held-out non-corroboration",
        },
        {
            "sequence": 3,
            "evidence_block": "Prespecified subsequent extension",
            "period": "2022-2025",
            "epistemic_status": (
                "prespecified subsequent extension conditional on prior knowledge"
            ),
            "design": (
                "12 balanced wells; well FE + year FE + antecedent groundwater"
            ),
            "beta_per_1_ff10": s5_beta,
            "se_primary": s5_se,
            "ci95_low": s5_lo,
            "ci95_high": s5_hi,
            "p_primary": s5_p,
            "primary_inference": "CV3J CI; WCR31-Webb p",
            "N": int(first_existing(p, ["n", "N"])),
            "wells": int(first_existing(p, ["n_wells", "wells"])),
            "years": int(first_existing(p, ["n_years", "years"])),
            "direction": "positive" if s5_beta > 0 else "negative",
            "publication_role": "post-2021 primary extension",
        },
    ])

    main.to_csv(MAIN_TABLE_OUT, index=False)
    main.to_csv(FIGURE_ESTIMATES_OUT, index=False)

    # ------------------------------------------------------------------
    # 5. Identification / information audit table.
    # ------------------------------------------------------------------
    s6 = json.loads(STAGE6_QA_IN.read_text(encoding="utf-8"))
    s6r = json.loads(STAGE6R_QA_IN.read_text(encoding="utf-8"))

    if s6r.get("status") != "PASS":
        raise AssertionError("Stage 6R did not PASS.")

    matched = s6r["matched_scale_validation"]

    identification = pd.DataFrame([
        {
            "diagnostic": "Raw FF10 variance retained after full adjustment",
            "value": float(s6["full_to_raw_variance_ratio"]),
            "unit": "fraction",
            "interpretive_role": (
                "quantifies how little raw exposure variance identifies beta"
            ),
        },
        {
            "diagnostic": "Identifying FF10 residual SD",
            "value": float(s6["identifying_ff10_residual_sd"]),
            "unit": "FF10",
            "interpretive_role": "scale of coefficient-identifying exposure variation",
        },
        {
            "diagnostic": "Maximum single-well information share",
            "value": float(s6["max_ff10_partial_leverage_share"]),
            "unit": "fraction",
            "interpretive_role": "cluster information concentration",
        },
        {
            "diagnostic": "Information-equivalent clusters",
            "value": float(
                s6["effective_ff10_clusters_inverse_herfindahl"]
            ),
            "unit": "inverse-Herfindahl count",
            "interpretive_role": (
                "descriptive information concentration; not inferential df"
            ),
        },
        {
            "diagnostic": "Stage6R manual FWL beta discrepancy",
            "value": float(s6r["beta_absolute_difference"]),
            "unit": "beta units",
            "interpretive_role": "independent algebraic replication",
        },
        {
            "diagnostic": "Matched-scale FE reconstruction error SD ratio",
            "value": float(
                matched["fe_error_sd_to_post2021_identifying_sd_ratio"]
            ),
            "unit": "ratio",
            "interpretive_role": (
                "historical 10-km reconstruction error relative to "
                "post-2021 identifying FF10 SD"
            ),
        },
        {
            "diagnostic": "Matched-scale FE observed/predicted Pearson r",
            "value": float(matched["fe_pearson"]),
            "unit": "correlation",
            "interpretive_role": "matched-scale bridge validation",
        },
    ])
    identification.to_csv(IDENTIFICATION_TABLE_OUT, index=False)

    # ------------------------------------------------------------------
    # 6. Stage-7 robustness hierarchy.
    # ------------------------------------------------------------------
    s7 = pd.read_csv(STAGE7_IN)

    expected_models = {
        ("primary", "base_identity"),
        ("primary", "W1_precip"),
        ("primary", "W2_temp"),
        ("primary", "W3_precip_temp"),
        ("secondary18", "base"),
        ("secondary18", "W1_precip"),
        ("secondary18", "W2_temp"),
        ("secondary18", "W3_precip_temp"),
        ("diagnostic14", "base"),
    }
    observed_models = set(zip(s7["sample"], s7["model"]))
    if observed_models != expected_models:
        raise AssertionError(
            "Stage-7 model set differs from frozen synthesis expectation."
        )

    robustness = s7[[
        "sample", "model", "n_rows", "n_wells",
        "beta_per_1_ff10", "beta_per_0_01_ff10_m",
        "cv3j_se", "cv3j_ci_low", "cv3j_ci_high",
        "wcr31_webb_p", "ff10_partial_residual_sd",
        "loo_beta_min", "loo_beta_max",
        "loo_sign_change_across_omissions",
        "loo_max_abs_beta_change",
        "loo_most_influential_station",
    ]].copy()

    robustness["reporting_role"] = np.where(
        (robustness["sample"] == "primary")
        & (robustness["model"] == "base_identity"),
        "identity reproduction of frozen primary",
        np.where(
            robustness["sample"] == "diagnostic14",
            "diagnostic population only",
            "prespecified robustness only",
        ),
    )
    robustness.to_csv(ROBUSTNESS_TABLE_OUT, index=False)

    looy = pd.read_csv(STAGE7_LOOY_IN)
    stability = looy.copy()
    stability["diagnostic_family"] = "leave-one-year primary"
    stability.to_csv(FIGURE_STABILITY_OUT, index=False)

    # ------------------------------------------------------------------
    # 7. Claims/limits matrix — guards publication wording.
    # ------------------------------------------------------------------
    claims = pd.DataFrame([
        {
            "statement": (
                "Historical analyses showed a positive flooding-groundwater "
                "association."
            ),
            "status": "SUPPORTED WITH QUALIFICATION",
            "qualification": (
                "historically informed/reanalyzed and affected by historical "
                "model exploration/multiplicity; not independent confirmation"
            ),
        },
        {
            "statement": (
                "The genuine 2022-2023 held-out test corroborated the "
                "historical positive association."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "held-out coefficient was negative and extremely imprecise"
            ),
        },
        {
            "statement": (
                "The 2022-2025 extension demonstrates a negative causal effect."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "observational non-causal estimand; WCR31/CV3J inference is "
                "weakly informative and cluster-concentrated"
            ),
        },
        {
            "statement": (
                "The 2022-2025 evidence precisely demonstrates no association."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "primary confidence interval is extremely wide; absence of "
                "statistical evidence is not precise evidence of absence"
            ),
        },
        {
            "statement": (
                "Weather adjustment explains the post-2021 primary estimate."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "primary W1-W3 estimates retain the same negative direction "
                "and broadly similar magnitude"
            ),
        },
        {
            "statement": (
                "The magnitude of the post-2021 association is stable across "
                "eligible-well populations."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "14- and 18-well estimates attenuate substantially toward zero"
            ),
        },
        {
            "statement": (
                "The main practical limitation of the post-2021 primary "
                "analysis is concentrated identifying information."
            ),
            "status": "SUPPORTED",
            "qualification": (
                "Stage 6 and independent Stage 6R reproduce the concentration "
                "and influential-cluster diagnosis"
            ),
        },
        {
            "statement": (
                "Matched-scale validation rules out all exposure measurement "
                "error concerns."
            ),
            "status": "NOT SUPPORTED",
            "qualification": (
                "matched-scale error is smaller than post-2021 identifying SD "
                "but residual agreement is only moderate; no EIV correction"
            ),
        },
    ])
    claims.to_csv(CLAIMS_OUT, index=False)

    # ------------------------------------------------------------------
    # 8. Cross-stage identity and QA.
    # ------------------------------------------------------------------
    s7qa = json.loads(STAGE7_QA_IN.read_text(encoding="utf-8"))
    s7primary = s7.loc[
        (s7["sample"] == "primary")
        & (s7["model"] == "base_identity")
    ].iloc[0]

    identities = {
        "stage5_vs_stage7_primary_beta_abs_diff": abs(
            s5_beta - float(s7primary["beta_per_1_ff10"])
        ),
        "stage5_vs_stage6r_beta_abs_diff": abs(
            s5_beta - float(s6r["manual_fwl_beta"])
        ),
    }

    if identities["stage5_vs_stage7_primary_beta_abs_diff"] > 1e-10:
        raise AssertionError("Stage 5/7 primary beta identity failed.")
    if identities["stage5_vs_stage6r_beta_abs_diff"] > 1e-10:
        raise AssertionError("Stage 5/6R primary beta identity failed.")
    if s7qa.get("status") != "PASS":
        raise AssertionError("Stage 7 QA is not PASS.")

    qa = {
        "status": "PASS",
        "stage": "STAGE_8_INTEGRATED_EVIDENCE_SYNTHESIS",
        "new_models_fitted": 0,
        "primary_result_changed": False,
        "robustness_promoted": False,
        "main_evidence_rows": int(len(main)),
        "stage7_models_synthesized": int(len(robustness)),
        "leave_one_year_rows": int(len(stability)),
        "identification_diagnostics_synthesized": int(len(identification)),
        **identities,
        "reporting_firewall": (
            "Chronology and frozen inferential hierarchy preserved. "
            "No estimate selected according to sign, precision or p-value."
        ),
    }
    QA_OUT.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # 9. Integrated publication narrative, factual and non-causal.
    # ------------------------------------------------------------------
    primary_weather = s7.loc[
        (s7["sample"] == "primary")
        & s7["model"].isin(["W1_precip", "W2_temp", "W3_precip_temp"])
    ]
    secondary_base = s7.loc[
        (s7["sample"] == "secondary18")
        & (s7["model"] == "base")
    ].iloc[0]
    diagnostic_base = s7.loc[
        (s7["sample"] == "diagnostic14")
        & (s7["model"] == "base")
    ].iloc[0]

    text = f"""STAGE 8 — INTEGRATED EVIDENCE SYNTHESIS
=======================================

NO NEW MODEL WAS FITTED IN STAGE 8.

EVIDENCE CHRONOLOGY
-------------------
Historical 2008-2021 publication reanalysis:
  beta = {hist_beta:.12g}
  primary reported 95% CI = [{hist_lo:.12g}, {hist_hi:.12g}]
  p = {hist_p:.12g}
  Status: historically informed frozen reanalysis, not untouched confirmation.

Genuine held-out 2022-2023 confirmation:
  beta = {held_beta:.12g}
  HC3 SE = {held_se:.12g}
  95% CI = [{held_lo:.12g}, {held_hi:.12g}]
  p = {held_p:.12g}
  Status: did not corroborate the historical positive association and was
  extremely imprecise.

Prespecified subsequent 2022-2025 extension:
  beta = {s5_beta:.12g}
  CV3J SE = {s5_se:.12g}
  CV3J 95% CI = [{s5_lo:.12g}, {s5_hi:.12g}]
  WCR31-Webb p = {s5_p:.12g}
  Status: no clear directional evidence under frozen small-cluster inference.

INFORMATION AUDIT
-----------------
Identifying FF10 residual SD = {float(s6["identifying_ff10_residual_sd"]):.12g}
Raw variance retained after full adjustment =
  {float(s6["full_to_raw_variance_ratio"]):.12g}
Maximum one-well information share =
  {float(s6["max_ff10_partial_leverage_share"]):.12g}
Information-equivalent clusters =
  {float(s6["effective_ff10_clusters_inverse_herfindahl"]):.12g}
Matched-scale FE error SD / post-2021 identifying SD =
  {float(matched["fe_error_sd_to_post2021_identifying_sd_ratio"]):.12g}

Stage 6R independently reproduced the Stage-5 coefficient and information
concentration. Therefore the primary practical limitation is concentrated
identifying information, not an algebraic/rank failure.

ROBUSTNESS / STABILITY
----------------------
Primary weather robustness beta range:
  [{primary_weather["beta_per_1_ff10"].min():.12g},
   {primary_weather["beta_per_1_ff10"].max():.12g}]

Secondary 18-well base beta =
  {float(secondary_base["beta_per_1_ff10"]):.12g}

Diagnostic 14-well base beta =
  {float(diagnostic_base["beta_per_1_ff10"]):.12g}

The primary weather specifications retain a negative direction, but broader
eligible-well populations attenuate markedly toward zero. Leave-one-year
diagnostics remain negative in all four omissions but show magnitude
instability.

PUBLICATION-SAFE SYNTHESIS
--------------------------
Historical analyses suggested a positive flooding-groundwater association.
A genuine held-out 2022-2023 test did not corroborate that association.
The prespecified 2022-2025 extension also yielded no clear directional
evidence under the frozen small-cluster inference procedure. Diagnostic
analysis shows that the later estimate is weakly informed because calendar-
year adjustment removes most raw exposure variation and the remaining
identifying information is highly concentrated among wells. Weather
adjustment does not materially explain the primary estimate, while broader
eligible-well samples attenuate substantially toward zero.

Accordingly, the post-2021 evidence neither supports a robust negative causal
effect nor provides precise evidence of no association.

REPORTING FIREWALL
------------------
The historical block, genuine held-out test, frozen 2022-2025 primary result,
Stage-6/6R diagnostics, and Stage-7 robustness retain their original
epistemic roles. No Stage-8 synthesis operation changes model status.
"""
    SUMMARY_OUT.write_text(text, encoding="utf-8")

    print("=== STAGE 8 INTEGRATED EVIDENCE SYNTHESIS ===")
    print("new models fitted: 0")
    print("")
    print(
        f"historical: beta={hist_beta:.12g}, "
        f"CI=[{hist_lo:.12g}, {hist_hi:.12g}], p={hist_p:.12g}"
    )
    print(
        f"held-out 2022-2023: beta={held_beta:.12g}, "
        f"HC3 SE={held_se:.12g}, p={held_p:.12g}"
    )
    print(
        f"primary 2022-2025: beta={s5_beta:.12g}, "
        f"CV3J SE={s5_se:.12g}, WCR31 p={s5_p:.12g}"
    )
    print("")
    print(
        "primary weather beta range: "
        f"[{primary_weather['beta_per_1_ff10'].min():.12g}, "
        f"{primary_weather['beta_per_1_ff10'].max():.12g}]"
    )
    print(
        "secondary18 base beta: "
        f"{float(secondary_base['beta_per_1_ff10']):.12g}"
    )
    print(
        "diagnostic14 base beta: "
        f"{float(diagnostic_base['beta_per_1_ff10']):.12g}"
    )
    print("")
    print(
        "max one-well information share: "
        f"{float(s6['max_ff10_partial_leverage_share']):.12g}"
    )
    print(
        "information-equivalent clusters: "
        f"{float(s6['effective_ff10_clusters_inverse_herfindahl']):.12g}"
    )
    print(
        "matched FE error / identifying SD: "
        f"{float(matched['fe_error_sd_to_post2021_identifying_sd_ratio']):.12g}"
    )
    print("")
    print(f"main table: {MAIN_TABLE_OUT}")
    print(f"robustness table: {ROBUSTNESS_TABLE_OUT}")
    print(f"identification table: {IDENTIFICATION_TABLE_OUT}")
    print(f"claims matrix: {CLAIMS_OUT}")
    print(f"summary: {SUMMARY_OUT}")
    print(f"QA: {QA_OUT}")
    print("STAGE 8 SYNTHESIS: PASS")
    print("FROZEN PRIMARY RESULT / EVIDENCE HIERARCHY: UNCHANGED")


if __name__ == "__main__":
    main()

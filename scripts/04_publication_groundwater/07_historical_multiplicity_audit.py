from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RECOVERY_PANEL = (
    ROOT
    / "outputs"
    / "publication_exploratory"
    / "empirical_panel_preweather_recovery_snapshot.csv"
)

PUBLICATION_PANEL = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "discovery_panel_2008_2021.csv"
)

OUTDIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "publication_groundwater"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

RESULT_OUT = (
    OUTDIR
    / "historical_minimum_multiplicity_family.csv"
)

QA_OUT = (
    OUTDIR
    / "historical_minimum_multiplicity_qa.csv"
)


# ---------------------------------------------------------------------
# Historical target used as computational QA
# ---------------------------------------------------------------------

EXPECTED_AUG_BETA = 6.440268535973067
EXPECTED_AUG_P = 0.026743407265692277

BETA_TOL = 1e-6
P_TOL = 1e-6


# ---------------------------------------------------------------------
# Load recovered historical fields
# ---------------------------------------------------------------------

old = pd.read_csv(RECOVERY_PANEL)

required_old = [
    "station",
    "year",
    "pre",
    "aprmay",
    "m6",
    "m7",
    "m8",
    "ff_10",
]

missing_old = [
    c for c in required_old
    if c not in old.columns
]

if missing_old:
    raise RuntimeError(
        f"Recovery panel missing columns: {missing_old}"
    )

if old.duplicated(["station", "year"]).any():
    raise RuntimeError(
        "Recovery panel contains duplicate station-year rows."
    )


# ---------------------------------------------------------------------
# Load reproducible publication weather controls
# ---------------------------------------------------------------------

weather_cols = [
    "station",
    "year",
    "P4",
    "P5",
    "P6",
    "P7",
    "P8",
    "T4",
    "T5",
    "T6",
    "T7",
    "T8",
    "P_A6",
    "T_A6",
    "P_A7",
    "T_A7",
    "P_A8",
    "T_A8",
]

pub = pd.read_csv(
    PUBLICATION_PANEL,
    usecols=weather_cols,
)

if pub.duplicated(["station", "year"]).any():
    raise RuntimeError(
        "Publication panel contains duplicate station-year rows."
    )


# ---------------------------------------------------------------------
# Reconstruct recovered monthly-timing analysis panel
# ---------------------------------------------------------------------

p = old.merge(
    pub,
    on=["station", "year"],
    how="left",
    validate="one_to_one",
)

for target in [6, 7, 8]:
    p[f"d_spr_{target}"] = (
        p[f"m{target}"] - p["aprmay"]
    )

# Exact recovered architecture:
# ff10 anomaly is centered using the station-specific mean available
# in the recovered historical panel.
p["ff10_mean"] = (
    p.groupby("station")["ff_10"]
    .transform("mean")
)

p["ff10_anom"] = (
    p["ff_10"] - p["ff10_mean"]
)


# ---------------------------------------------------------------------
# Model helper: reproduce recovered script
# ---------------------------------------------------------------------

def fit_model(
    target,
    weather,
    include_pre,
):
    outcome = f"d_spr_{target}"

    if weather == "cumulative":
        wx = [
            f"P_A{target}",
            f"T_A{target}",
        ]

    elif weather == "separate":
        wx = [
            "P4",
            "P5",
            f"P{target}",
            "T4",
            "T5",
            f"T{target}",
        ]

    else:
        raise ValueError(
            f"Unknown weather specification: {weather}"
        )

    x = ["ff10_anom"] + wx

    if include_pre:
        x.append("pre")

    cols = [
        outcome,
        "station",
        "year",
    ] + x

    r = (
        p.dropna(subset=cols)
        .copy()
    )

    formula = (
        outcome
        + " ~ "
        + " + ".join(x)
        + " + C(station) + C(year)"
    )

    model = smf.ols(
        formula,
        data=r,
    ).fit(
        cov_type="cluster",
        cov_kwds={
            "groups": r["station"],
        },
    )

    term = "ff10_anom"

    ci = (
        model.conf_int()
        .loc[term]
        .tolist()
    )

    return {
        "model": model,
        "sample": r,
        "formula": formula,
        "beta": float(
            model.params[term]
        ),
        "se": float(
            model.bse[term]
        ),
        "p_nominal": float(
            model.pvalues[term]
        ),
        "ci95_low": float(ci[0]),
        "ci95_high": float(ci[1]),
        "N": int(len(r)),
        "wells": int(
            r["station"].nunique()
        ),
    }


# ---------------------------------------------------------------------
# Minimum directly comparable historical family
# ---------------------------------------------------------------------

family_specs = []

# Family 1:
# cumulative weather + pre
for target in [6, 7, 8]:
    family_specs.append(
        {
            "family_group": (
                "cumulative_weather_plus_pre"
            ),
            "target_month": target,
            "weather": "cumulative",
            "include_pre": True,
        }
    )

# Family 2:
# separate April/May/target weather + pre
for target in [6, 7, 8]:
    family_specs.append(
        {
            "family_group": (
                "separate_weather_plus_pre"
            ),
            "target_month": target,
            "weather": "separate",
            "include_pre": True,
        }
    )

# Family 3:
# cumulative weather without pre
for target in [6, 7, 8]:
    family_specs.append(
        {
            "family_group": (
                "cumulative_weather_no_pre"
            ),
            "target_month": target,
            "weather": "cumulative",
            "include_pre": False,
        }
    )

if len(family_specs) != 9:
    raise RuntimeError(
        "Minimum multiplicity family must contain exactly 9 tests."
    )


# ---------------------------------------------------------------------
# Run all nine historical models
# ---------------------------------------------------------------------

rows = []

for family_index, spec in enumerate(
    family_specs,
    start=1,
):
    result = fit_model(
        target=spec["target_month"],
        weather=spec["weather"],
        include_pre=spec["include_pre"],
    )

    rows.append(
        {
            "family_index": family_index,
            "family_group": spec[
                "family_group"
            ],
            "target_month": spec[
                "target_month"
            ],
            "weather_spec": spec[
                "weather"
            ],
            "include_pre": spec[
                "include_pre"
            ],
            "formula": result["formula"],
            "beta_ff10_anom": result[
                "beta"
            ],
            "clustered_se": result[
                "se"
            ],
            "p_nominal": result[
                "p_nominal"
            ],
            "ci95_low": result[
                "ci95_low"
            ],
            "ci95_high": result[
                "ci95_high"
            ],
            "N": result["N"],
            "wells": result["wells"],
        }
    )

results = pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Multiple-testing adjustments across minimum family of nine
# ---------------------------------------------------------------------

pvals = (
    results["p_nominal"]
    .to_numpy(dtype=float)
)

if not np.isfinite(pvals).all():
    raise RuntimeError(
        "At least one nominal p-value is non-finite."
    )

if len(pvals) != 9:
    raise RuntimeError(
        "Multiplicity adjustment expected exactly 9 p-values."
    )

# Bonferroni
_, p_bonf, _, _ = multipletests(
    pvals,
    alpha=0.05,
    method="bonferroni",
)

# Holm familywise-error control
_, p_holm, _, _ = multipletests(
    pvals,
    alpha=0.05,
    method="holm",
)

# Benjamini-Hochberg FDR
_, p_bh, _, _ = multipletests(
    pvals,
    alpha=0.05,
    method="fdr_bh",
)

results["p_bonferroni_9"] = p_bonf
results["p_holm_9"] = p_holm
results["p_bh_9"] = p_bh

results["nominal_lt_0_05"] = (
    results["p_nominal"] < 0.05
)

results["bonferroni_lt_0_05"] = (
    results["p_bonferroni_9"] < 0.05
)

results["holm_lt_0_05"] = (
    results["p_holm_9"] < 0.05
)

results["bh_lt_0_05"] = (
    results["p_bh_9"] < 0.05
)


# ---------------------------------------------------------------------
# QA: recovered selected August model
# ---------------------------------------------------------------------

aug = results[
    (
        results["family_group"]
        == "cumulative_weather_plus_pre"
    )
    & (
        results["target_month"] == 8
    )
].copy()

if len(aug) != 1:
    raise RuntimeError(
        "Could not uniquely identify recovered August model."
    )

aug = aug.iloc[0]

beta_diff = (
    float(aug["beta_ff10_anom"])
    - EXPECTED_AUG_BETA
)

p_diff = (
    float(aug["p_nominal"])
    - EXPECTED_AUG_P
)

aug_beta_qa = (
    "PASS"
    if abs(beta_diff) <= BETA_TOL
    else "FAIL"
)

aug_p_qa = (
    "PASS"
    if abs(p_diff) <= P_TOL
    else "FAIL"
)

family_qa = (
    "PASS"
    if (
        len(results) == 9
        and results[
            "family_index"
        ].nunique() == 9
    )
    else "FAIL"
)

overall_qa = (
    "PASS"
    if (
        aug_beta_qa == "PASS"
        and aug_p_qa == "PASS"
        and family_qa == "PASS"
    )
    else "FAIL"
)


# ---------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------

results.to_csv(
    RESULT_OUT,
    index=False,
)

qa = pd.DataFrame(
    [
        {
            "check": "minimum_family_size",
            "value": len(results),
            "status": family_qa,
        },
        {
            "check": (
                "recovered_august_beta"
            ),
            "value": float(
                aug["beta_ff10_anom"]
            ),
            "target": EXPECTED_AUG_BETA,
            "difference": beta_diff,
            "status": aug_beta_qa,
        },
        {
            "check": (
                "recovered_august_p"
            ),
            "value": float(
                aug["p_nominal"]
            ),
            "target": EXPECTED_AUG_P,
            "difference": p_diff,
            "status": aug_p_qa,
        },
        {
            "check": "overall",
            "value": overall_qa,
            "status": overall_qa,
        },
    ]
)

qa.to_csv(
    QA_OUT,
    index=False,
)


# ---------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------

print()
print(
    "============================================================"
)
print(
    "HISTORICAL MINIMUM MULTIPLICITY AUDIT"
)
print(
    "============================================================"
)

print()
print(
    "Family definition: 9 directly comparable "
    "FF10 tests recovered from 02_monthly_timing.py"
)

print()
print(
    results[
        [
            "family_index",
            "family_group",
            "target_month",
            "beta_ff10_anom",
            "clustered_se",
            "p_nominal",
            "p_bonferroni_9",
            "p_holm_9",
            "p_bh_9",
            "N",
            "wells",
        ]
    ].to_string(index=False)
)

print()
print(
    "=== RECOVERED AUGUST MODEL QA ==="
)
print(
    "beta =",
    float(aug["beta_ff10_anom"]),
)
print(
    "target beta =",
    EXPECTED_AUG_BETA,
)
print(
    "beta difference =",
    beta_diff,
)
print(
    "beta QA =",
    aug_beta_qa,
)

print()
print(
    "p =",
    float(aug["p_nominal"]),
)
print(
    "target p =",
    EXPECTED_AUG_P,
)
print(
    "p difference =",
    p_diff,
)
print(
    "p QA =",
    aug_p_qa,
)

print()
print(
    "=== FAMILY SUMMARY ==="
)
print(
    "tests =",
    len(results),
)
print(
    "nominal p < .05 =",
    int(
        results[
            "nominal_lt_0_05"
        ].sum()
    ),
)
print(
    "Bonferroni p < .05 =",
    int(
        results[
            "bonferroni_lt_0_05"
        ].sum()
    ),
)
print(
    "Holm p < .05 =",
    int(
        results[
            "holm_lt_0_05"
        ].sum()
    ),
)
print(
    "BH p < .05 =",
    int(
        results[
            "bh_lt_0_05"
        ].sum()
    ),
)

print()
print(
    "overall QA =",
    overall_qa,
)

print()
print("Outputs:")
print(RESULT_OUT)
print(QA_OUT)

print()
print(
    "IMPORTANT: this is a documented LOWER BOUND "
    "on the historical exploratory universe."
)
print(
    "The broader recovered search included lead-lag, "
    "nonlinearity, alternative exposure variants, "
    "exact-date sensitivity, and other specifications."
)

print()
print("DONE")
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"

TABLES.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD
# ============================================================

d = pd.read_csv(
    DATA / "MEDWATERICE_CS1_yield_hierarchy.csv"
)

d["yield_t_ha_14pct"] = pd.to_numeric(
    d["yield_t_ha_14pct"],
    errors="raise"
)


COMMON_GROUPS = [
    "0 N",
    "100 N",
    "160 N + FUNG",
    "160 N + NO FUNG",
]


# ============================================================
# 1. PLOT x AGRONOMIC-TREATMENT MEANS
#
# Each value averages the two nested subplot observations.
# ============================================================

plot_group = (
    d.groupby(
        [
            "year",
            "irrigation",
            "plot",
            "agronomic_treatment"
        ]
    )
    .agg(
        n_subplots=(
            "yield_t_ha_14pct",
            "size"
        ),
        plot_group_mean_yield_t_ha=(
            "yield_t_ha_14pct",
            "mean"
        ),
        plot_group_min_yield_t_ha=(
            "yield_t_ha_14pct",
            "min"
        ),
        plot_group_max_yield_t_ha=(
            "yield_t_ha_14pct",
            "max"
        ),
    )
    .reset_index()
)

plot_group.to_csv(
    TABLES /
    "MEDWATERICE_yield_plot_by_agronomic_group.csv",
    index=False
)


# ============================================================
# 2. IRRIGATION SUMMARY BY AGRONOMIC GROUP
#
# n_plots must equal 2.
# SD is between the two physical plots.
# No subplot-level SE or significance testing.
# ============================================================

irrig_group = (
    plot_group
    .groupby(
        [
            "year",
            "irrigation",
            "agronomic_treatment"
        ]
    )
    .agg(
        n_plots=(
            "plot_group_mean_yield_t_ha",
            "size"
        ),
        mean_yield_t_ha=(
            "plot_group_mean_yield_t_ha",
            "mean"
        ),
        sd_between_plots_t_ha=(
            "plot_group_mean_yield_t_ha",
            "std"
        ),
        min_plot_mean_t_ha=(
            "plot_group_mean_yield_t_ha",
            "min"
        ),
        max_plot_mean_t_ha=(
            "plot_group_mean_yield_t_ha",
            "max"
        ),
    )
    .reset_index()
)

irrig_group.to_csv(
    TABLES /
    "MEDWATERICE_yield_irrigation_by_agronomic_group.csv",
    index=False
)


# ============================================================
# 3. COMMON-MANAGEMENT PLOT INDEX
#
# Equal-weight mean of the four agronomic groups shared by
# both years.
#
# This is NOT a farm-scale yield estimate.
# It is a balanced experimental production summary.
# ============================================================

common = plot_group[
    plot_group["agronomic_treatment"].isin(
        COMMON_GROUPS
    )
].copy()

plot_common = (
    common
    .groupby(
        [
            "year",
            "irrigation",
            "plot"
        ]
    )
    .agg(
        n_common_groups=(
            "agronomic_treatment",
            "nunique"
        ),
        common_management_mean_yield_t_ha=(
            "plot_group_mean_yield_t_ha",
            "mean"
        ),
    )
    .reset_index()
)

plot_common.to_csv(
    TABLES /
    "MEDWATERICE_yield_common_management_plot_summary.csv",
    index=False
)


common_irrig = (
    plot_common
    .groupby(
        [
            "year",
            "irrigation"
        ]
    )
    .agg(
        n_plots=(
            "common_management_mean_yield_t_ha",
            "size"
        ),
        mean_yield_t_ha=(
            "common_management_mean_yield_t_ha",
            "mean"
        ),
        sd_between_plots_t_ha=(
            "common_management_mean_yield_t_ha",
            "std"
        ),
        min_plot_mean_t_ha=(
            "common_management_mean_yield_t_ha",
            "min"
        ),
        max_plot_mean_t_ha=(
            "common_management_mean_yield_t_ha",
            "max"
        ),
    )
    .reset_index()
)

common_irrig.to_csv(
    TABLES /
    "MEDWATERICE_yield_common_management_irrigation_summary.csv",
    index=False
)


# ============================================================
# 4. LIKE-FOR-LIKE CONTRASTS AGAINST WFL
#
# Descriptive differences only.
# ============================================================

contrast_rows = []

for year, gy in irrig_group.groupby("year"):

    for agronomic_group, gg in gy.groupby(
        "agronomic_treatment"
    ):

        ref = gg[
            gg["irrigation"] == "WFL"
        ]

        if len(ref) != 1:
            continue

        ref_mean = float(
            ref.iloc[0]["mean_yield_t_ha"]
        )

        for _, row in gg.iterrows():

            mean = float(
                row["mean_yield_t_ha"]
            )

            contrast_rows.append(
                {
                    "year": year,
                    "agronomic_treatment":
                        agronomic_group,
                    "irrigation":
                        row["irrigation"],
                    "mean_yield_t_ha":
                        mean,
                    "WFL_mean_yield_t_ha":
                        ref_mean,
                    "difference_vs_WFL_t_ha":
                        mean - ref_mean,
                    "percent_difference_vs_WFL":
                        (
                            (mean - ref_mean)
                            / ref_mean
                            * 100
                        ),
                }
            )


contrasts = pd.DataFrame(
    contrast_rows
)

contrasts.to_csv(
    TABLES /
    "MEDWATERICE_yield_descriptive_contrasts_vs_WFL.csv",
    index=False
)


# ============================================================
# 5. CROSS-YEAR DIRECTIONAL CONSISTENCY
#
# Compare AWD-WFL and DFL-WFL direction in 2019 vs 2020.
# ============================================================

consistency_rows = []

for group in COMMON_GROUPS:

    x = contrasts[
        contrasts[
            "agronomic_treatment"
        ] == group
    ]

    for irrigation in [
        "AWD",
        "DFL"
    ]:

        xx = x[
            x["irrigation"] == irrigation
        ]

        vals = {
            int(row["year"]):
            float(
                row[
                    "difference_vs_WFL_t_ha"
                ]
            )
            for _, row in xx.iterrows()
        }

        if 2019 not in vals or 2020 not in vals:
            continue

        d19 = vals[2019]
        d20 = vals[2020]

        same_direction = (
            np.sign(d19) == np.sign(d20)
        )

        consistency_rows.append(
            {
                "agronomic_treatment":
                    group,
                "irrigation_vs_WFL":
                    irrigation,
                "difference_2019_t_ha":
                    d19,
                "difference_2020_t_ha":
                    d20,
                "same_direction":
                    same_direction,
            }
        )


consistency = pd.DataFrame(
    consistency_rows
)

consistency.to_csv(
    TABLES /
    "MEDWATERICE_yield_crossyear_directional_consistency.csv",
    index=False
)


# ============================================================
# 6. 160 N + FUNG PRIMARY LIKE-FOR-LIKE TABLE
# ============================================================

primary = irrig_group[
    irrig_group[
        "agronomic_treatment"
    ] == "160 N + FUNG"
].copy()

primary.to_csv(
    TABLES /
    "MEDWATERICE_yield_primary_160N_fungicide.csv",
    index=False
)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

pd.set_option(
    "display.width",
    180
)

pd.set_option(
    "display.max_columns",
    20
)


print()
print("=" * 105)
print("PRIMARY LIKE-FOR-LIKE YIELD: 160 N + FUNG")
print("=" * 105)

print(
    primary
    .round(3)
    .to_string(index=False)
)


print()
print("=" * 105)
print("COMMON-MANAGEMENT BALANCED PRODUCTION SUMMARY")
print("=" * 105)

print(
    common_irrig
    .round(3)
    .to_string(index=False)
)


print()
print("=" * 105)
print("DESCRIPTIVE CONTRASTS VS WFL — COMMON AGRONOMIC GROUPS")
print("=" * 105)

print(
    contrasts[
        contrasts[
            "agronomic_treatment"
        ].isin(COMMON_GROUPS)
    ]
    .round(3)
    .to_string(index=False)
)


print()
print("=" * 105)
print("CROSS-YEAR DIRECTIONAL CONSISTENCY")
print("=" * 105)

print(
    consistency
    .round(3)
    .to_string(index=False)
)


print()
print(
    "IMPORTANT:"
)

print(
    "The irrigation-level experimental unit is the physical plot "
    "(n=2 plots per irrigation strategy per year)."
)

print(
    "Nested subplot observations are used to construct plot means "
    "and are not treated as independent irrigation replicates."
)

print(
    "No significance test is interpreted as a definitive irrigation "
    "treatment effect given the very small plot-level replication."
)

print(
    "The common-management summary is a balanced experimental "
    "indicator, not a farm-scale yield estimate."
)

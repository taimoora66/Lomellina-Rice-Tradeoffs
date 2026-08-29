from pathlib import Path

import pandas as pd


ROOT = Path(".")
TABLES = ROOT / "outputs" / "tables"

src = TABLES / "MEDWATERICE_common_window_summary.csv"
df = pd.read_csv(src)

# ------------------------------------------------------------
# Rename columns for publication-oriented clarity
# ------------------------------------------------------------

keep = df[
    [
        "year",
        "treatment",
        "common_start",
        "common_end",
        "n_days",
        "gross_inflow_mm",
        "gross_outflow_mm",
        "net_irrigation_mm",
        "rainfall_mm",
        "etc_adjusted_mm",
        "percolation_balance_sum_mm",
        "mean_ponding_level_mm",
        "fraction_positive_ponding",
    ]
].copy()

keep = keep.rename(
    columns={
        "gross_inflow_mm":
            "measured_irrigation_inflow_mm",

        "gross_outflow_mm":
            "measured_irrigation_outflow_mm",

        "net_irrigation_mm":
            "derived_net_irrigation_mm",

        "percolation_balance_sum_mm":
            "derived_water_balance_percolation_mm",

        "fraction_positive_ponding":
            "positive_ponding_fraction",
    }
)


# ------------------------------------------------------------
# Within-year descriptive contrasts relative to WFL
#
# WFL is a reference management system only.
# These ARE NOT causal treatment-effect estimates.
# ------------------------------------------------------------

metrics = [
    "measured_irrigation_inflow_mm",
    "measured_irrigation_outflow_mm",
    "derived_net_irrigation_mm",
    "derived_water_balance_percolation_mm",
    "mean_ponding_level_mm",
    "positive_ponding_fraction",
]

rows = []

for year, gy in keep.groupby("year"):

    ref = (
        gy.loc[gy["treatment"] == "WFL"]
        .iloc[0]
    )

    for _, r in gy.iterrows():

        out = {
            "year": year,
            "treatment": r["treatment"],
            "common_start": r["common_start"],
            "common_end": r["common_end"],
            "n_days": r["n_days"],
        }

        for metric in metrics:

            value = r[metric]
            ref_value = ref[metric]

            out[metric] = value

            out[f"{metric}_absolute_difference_vs_WFL"] = (
                value - ref_value
            )

            if ref_value != 0:
                out[f"{metric}_percent_difference_vs_WFL"] = (
                    100 * (value - ref_value) / ref_value
                )
            else:
                out[f"{metric}_percent_difference_vs_WFL"] = None

        rows.append(out)


contrast = pd.DataFrame(rows)

contrast.to_csv(
    TABLES /
    "MEDWATERICE_common_window_hydrology_contrasts.csv",
    index=False
)


# ------------------------------------------------------------
# Compact manuscript-facing table
# ------------------------------------------------------------

compact = keep.copy()

compact["positive_ponding_percent"] = (
    100 * compact["positive_ponding_fraction"]
)

compact = compact[
    [
        "year",
        "treatment",
        "common_start",
        "common_end",
        "n_days",
        "measured_irrigation_inflow_mm",
        "measured_irrigation_outflow_mm",
        "derived_net_irrigation_mm",
        "derived_water_balance_percolation_mm",
        "mean_ponding_level_mm",
        "positive_ponding_percent",
    ]
]

compact.to_csv(
    TABLES /
    "MEDWATERICE_hydrology_results_primary.csv",
    index=False
)


pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 20)

print()
print("=" * 100)
print("PRIMARY COMMON-WINDOW HYDROLOGY RESULTS")
print("=" * 100)

print(
    compact.round(2).to_string(index=False)
)

print()
print("=" * 100)
print("DESCRIPTIVE CONTRASTS RELATIVE TO WFL")
print("=" * 100)

show = [
    "year",
    "treatment",

    "derived_net_irrigation_mm",
    "derived_net_irrigation_mm_percent_difference_vs_WFL",

    "derived_water_balance_percolation_mm",
    "derived_water_balance_percolation_mm_percent_difference_vs_WFL",

    "mean_ponding_level_mm",
    "mean_ponding_level_mm_percent_difference_vs_WFL",

    "positive_ponding_fraction",
    "positive_ponding_fraction_percent_difference_vs_WFL",
]

print(
    contrast[show]
    .round(2)
    .to_string(index=False)
)

print()
print(
    "IMPORTANT: contrasts are descriptive and are not "
    "replicated causal treatment-effect estimates."
)

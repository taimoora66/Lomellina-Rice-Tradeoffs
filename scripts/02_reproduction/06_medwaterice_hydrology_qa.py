from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# MEDWATERICE CS1 hydrology QA
#
# NO treatment-effect inference.
# Purpose:
# - validate extracted daily data
# - quantify missingness
# - reproduce net irrigation
# - inspect water-balance components
# - identify negative / implausible values
# - assess common temporal support
# ============================================================


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
OUT = ROOT / "outputs" / "diagnostics"
TABLES = ROOT / "outputs" / "tables"

OUT.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)

FILE = DATA / "MEDWATERICE_CS1_hydrology_daily.csv"

df = pd.read_csv(FILE)

df["date"] = pd.to_datetime(df["date"], errors="raise")


numeric_cols = [
    "days_after_sowing",
    "irrigation_inflow_mm",
    "irrigation_outflow_mm",
    "net_irrigation_calculated_mm",
    "net_irrigation_reported_mm",
    "ponding_level_mm",
    "rainfall_mm",
    "etc_adjusted_mm",
    "delta_ponding_storage_mm",
    "delta_soil_storage_mm",
    "percolation_balance_mm",
    "percolation_model_mm",
    "percolation_model_heavy_soil_zone_mm",
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# ------------------------------------------------------------
# 1. BASIC STRUCTURE
# ------------------------------------------------------------

if df.duplicated(["year", "treatment", "date"]).any():
    duplicates = df.loc[
        df.duplicated(
            ["year", "treatment", "date"],
            keep=False
        )
    ]

    duplicates.to_csv(
        OUT / "MEDWATERICE_duplicate_dates.csv",
        index=False
    )

    raise ValueError(
        "Duplicate year-treatment-date records detected."
    )


groups = (
    df.groupby(["year", "treatment"])
    .agg(
        n_rows=("date", "size"),
        first_date=("date", "min"),
        last_date=("date", "max"),
        n_unique_dates=("date", "nunique"),
    )
    .reset_index()
)

groups["expected_calendar_days"] = (
    groups["last_date"] -
    groups["first_date"]
).dt.days + 1

groups["missing_calendar_days"] = (
    groups["expected_calendar_days"]
    - groups["n_unique_dates"]
)

groups.to_csv(
    TABLES / "MEDWATERICE_date_coverage.csv",
    index=False
)


# ------------------------------------------------------------
# 2. MISSINGNESS
# ------------------------------------------------------------

missing_rows = []

for (year, treatment), g in df.groupby(
    ["year", "treatment"]
):

    for col in numeric_cols:

        missing_rows.append(
            {
                "year": year,
                "treatment": treatment,
                "variable": col,
                "n_rows": len(g),
                "n_missing": int(g[col].isna().sum()),
                "percent_missing":
                    100 * g[col].isna().mean(),
            }
        )

missing = pd.DataFrame(missing_rows)

missing.to_csv(
    TABLES / "MEDWATERICE_missingness.csv",
    index=False
)


# ------------------------------------------------------------
# 3. REPRODUCE NET IRRIGATION
#
# 2020 workbooks report Qnet_meas.
# Compare it against independently calculated Qin-Qout.
# ------------------------------------------------------------

qnet = df.loc[
    df["net_irrigation_reported_mm"].notna(),
    [
        "year",
        "treatment",
        "date",
        "irrigation_inflow_mm",
        "irrigation_outflow_mm",
        "net_irrigation_calculated_mm",
        "net_irrigation_reported_mm",
    ]
].copy()

qnet["difference_mm"] = (
    qnet["net_irrigation_calculated_mm"]
    - qnet["net_irrigation_reported_mm"]
)

qnet["absolute_difference_mm"] = (
    qnet["difference_mm"].abs()
)

qnet.to_csv(
    OUT / "MEDWATERICE_qnet_reproduction_daily.csv",
    index=False
)


qnet_summary = (
    qnet.groupby(["year", "treatment"])
    .agg(
        n_compared=("difference_mm", "size"),
        mean_difference_mm=("difference_mm", "mean"),
        max_absolute_difference_mm=(
            "absolute_difference_mm",
            "max"
        ),
        rmse_mm=(
            "difference_mm",
            lambda x: np.sqrt(np.mean(np.square(x)))
        ),
    )
    .reset_index()
)

qnet_summary.to_csv(
    TABLES / "MEDWATERICE_qnet_reproduction_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 4. WATER-BALANCE REPRODUCTION
#
# Perc_Bal =
# Qin - Qout + Rain - ETc - DeltaL - DeltaS
#
# Recalculate independently.
# ------------------------------------------------------------

wb = df.copy()

wb["percolation_balance_recalculated_mm"] = (
    wb["net_irrigation_calculated_mm"]
    + wb["rainfall_mm"]
    - wb["etc_adjusted_mm"]
    - wb["delta_ponding_storage_mm"]
    - wb["delta_soil_storage_mm"]
)

wb["percolation_balance_difference_mm"] = (
    wb["percolation_balance_recalculated_mm"]
    - wb["percolation_balance_mm"]
)

wb["percolation_balance_abs_difference_mm"] = (
    wb["percolation_balance_difference_mm"].abs()
)

wb_check = (
    wb.groupby(["year", "treatment"])
    .agg(
        n_balance_comparable=(
            "percolation_balance_difference_mm",
            "count"
        ),
        mean_balance_difference_mm=(
            "percolation_balance_difference_mm",
            "mean"
        ),
        max_balance_abs_difference_mm=(
            "percolation_balance_abs_difference_mm",
            "max"
        ),
        rmse_balance_mm=(
            "percolation_balance_difference_mm",
            lambda x:
                np.sqrt(np.nanmean(np.square(x)))
        ),
    )
    .reset_index()
)

wb_check.to_csv(
    TABLES /
    "MEDWATERICE_water_balance_reproduction.csv",
    index=False
)


# ------------------------------------------------------------
# 5. NEGATIVE-VALUE DIAGNOSTICS
# ------------------------------------------------------------

negative_variables = [
    "net_irrigation_calculated_mm",
    "delta_ponding_storage_mm",
    "delta_soil_storage_mm",
    "percolation_balance_mm",
    "percolation_model_mm",
    "percolation_model_heavy_soil_zone_mm",
]

negative_rows = []

for (year, treatment), g in df.groupby(
    ["year", "treatment"]
):

    for col in negative_variables:

        valid = g[col].dropna()

        if len(valid) == 0:
            continue

        negative_rows.append(
            {
                "year": year,
                "treatment": treatment,
                "variable": col,
                "n_valid": len(valid),
                "n_negative": int((valid < 0).sum()),
                "percent_negative":
                    100 * (valid < 0).mean(),
                "minimum": valid.min(),
                "maximum": valid.max(),
            }
        )

negative = pd.DataFrame(negative_rows)

negative.to_csv(
    TABLES /
    "MEDWATERICE_negative_value_diagnostics.csv",
    index=False
)


# ------------------------------------------------------------
# 6. DESCRIPTIVE SEASON TOTALS
#
# NOT treatment-effect estimates.
# These retain each management system's own recorded period.
# ------------------------------------------------------------

season = (
    df.groupby(["year", "treatment"])
    .agg(
        start_date=("date", "min"),
        end_date=("date", "max"),
        n_days=("date", "size"),

        gross_inflow_mm=("irrigation_inflow_mm", "sum"),
        gross_outflow_mm=("irrigation_outflow_mm", "sum"),
        net_irrigation_mm=(
            "net_irrigation_calculated_mm",
            "sum"
        ),

        rainfall_mm=("rainfall_mm", "sum"),
        etc_adjusted_mm=("etc_adjusted_mm", "sum"),

        percolation_balance_sum_mm=(
            "percolation_balance_mm",
            "sum"
        ),

        percolation_model_sum_mm=(
            "percolation_model_mm",
            lambda x: x.sum(min_count=1)
        ),

        percolation_model_heavy_soil_zone_sum_mm=(
            "percolation_model_heavy_soil_zone_mm",
            lambda x: x.sum(min_count=1)
        ),

        mean_ponding_level_mm=(
            "ponding_level_mm",
            "mean"
        ),

        max_ponding_level_mm=(
            "ponding_level_mm",
            "max"
        ),

        flooded_observation_days=(
            "ponding_level_mm",
            lambda x: int((x > 0).sum())
        ),

        ponding_valid_days=(
            "ponding_level_mm",
            "count"
        ),
    )
    .reset_index()
)

season["fraction_positive_ponding"] = (
    season["flooded_observation_days"]
    / season["ponding_valid_days"]
)

season.to_csv(
    TABLES /
    "MEDWATERICE_season_descriptive_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 7. COMMON CALENDAR WINDOW WITHIN EACH YEAR
#
# Prevents DFL's longer observation period from automatically
# generating larger/smaller totals simply because coverage differs.
# ------------------------------------------------------------

common_rows = []

for year, gy in df.groupby("year"):

    ranges = (
        gy.groupby("treatment")
        .agg(
            start=("date", "min"),
            end=("date", "max")
        )
    )

    common_start = ranges["start"].max()
    common_end = ranges["end"].min()

    for treatment, g in gy.groupby("treatment"):

        gc = g.loc[
            g["date"].between(
                common_start,
                common_end
            )
        ]

        common_rows.append(
            {
                "year": year,
                "treatment": treatment,
                "common_start": common_start,
                "common_end": common_end,
                "n_days": len(gc),

                "gross_inflow_mm":
                    gc["irrigation_inflow_mm"].sum(),

                "gross_outflow_mm":
                    gc["irrigation_outflow_mm"].sum(),

                "net_irrigation_mm":
                    gc[
                        "net_irrigation_calculated_mm"
                    ].sum(),

                "rainfall_mm":
                    gc["rainfall_mm"].sum(),

                "etc_adjusted_mm":
                    gc["etc_adjusted_mm"].sum(),

                "percolation_balance_sum_mm":
                    gc["percolation_balance_mm"].sum(),

                "percolation_model_sum_mm":
                    gc["percolation_model_mm"].sum(min_count=1),

                "percolation_model_heavy_soil_zone_sum_mm":
                    gc["percolation_model_heavy_soil_zone_mm"].sum(min_count=1),

                "mean_ponding_level_mm":
                    gc["ponding_level_mm"].mean(),

                "fraction_positive_ponding":
                    (
                        gc["ponding_level_mm"].gt(0).sum()
                        /
                        gc["ponding_level_mm"].notna().sum()
                    ),
            }
        )

common = pd.DataFrame(common_rows)

common.to_csv(
    TABLES /
    "MEDWATERICE_common_window_summary.csv",
    index=False
)


# ------------------------------------------------------------
# TERMINAL REPORT
# ------------------------------------------------------------

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 30)

print()
print("=" * 80)
print("DATE COVERAGE")
print("=" * 80)
print(groups.to_string(index=False))

print()
print("=" * 80)
print("QNET REPRODUCTION")
print("=" * 80)

if len(qnet_summary):
    print(qnet_summary.to_string(index=False))
else:
    print("No reported Qnet values available for comparison.")

print()
print("=" * 80)
print("WATER-BALANCE REPRODUCTION")
print("=" * 80)
print(wb_check.to_string(index=False))

print()
print("=" * 80)
print("SEASON DESCRIPTIVE SUMMARY")
print("=" * 80)
print(season.to_string(index=False))

print()
print("=" * 80)
print("COMMON-WINDOW SUMMARY")
print("=" * 80)
print(common.to_string(index=False))

print()
print("=" * 80)
print("NEGATIVE-VALUE DIAGNOSTICS")
print("=" * 80)
print(negative.to_string(index=False))

print()
print("MEDWATERICE hydrology QA completed successfully.")




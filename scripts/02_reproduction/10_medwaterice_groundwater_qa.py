from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"

TABLES.mkdir(parents=True, exist_ok=True)

gw = pd.read_csv(
    DATA / "MEDWATERICE_CS1_groundwater_depth_long.csv"
)

gw["date"] = pd.to_datetime(
    gw["date"],
    errors="raise"
)

gw["groundwater_depth_cm"] = pd.to_numeric(
    gw["groundwater_depth_cm"],
    errors="coerce"
)


# ============================================================
# 1. Piezometer-level summaries
# ============================================================

summary = (
    gw.groupby(
        ["year", "treatment", "piezometer"]
    )
    .agg(
        n=("groundwater_depth_cm", "count"),
        first_date=("date", "min"),
        last_date=("date", "max"),
        mean_depth_cm=("groundwater_depth_cm", "mean"),
        median_depth_cm=("groundwater_depth_cm", "median"),
        sd_depth_cm=("groundwater_depth_cm", "std"),
        min_depth_cm=("groundwater_depth_cm", "min"),
        max_depth_cm=("groundwater_depth_cm", "max"),
    )
    .reset_index()
)

summary["range_cm"] = (
    summary["max_depth_cm"]
    - summary["min_depth_cm"]
)

summary.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_piezometer_summary.csv",
    index=False
)


# ============================================================
# 2. Correlation among wells within each year
#
# Each column uses unique treatment+piezometer identity because
# piezometer labels are not treatment-invariant across years.
# ============================================================

corr_outputs = []

for year, gy in gw.groupby("year"):

    x = gy.copy()

    x["well_id"] = (
        x["treatment"]
        + "_"
        + x["piezometer"]
    )

    wide = x.pivot_table(
        index="date",
        columns="well_id",
        values="groundwater_depth_cm",
        aggfunc="mean"
    )

    corr = wide.corr()

    corr.to_csv(
        TABLES /
        f"MEDWATERICE_groundwater_correlations_{year}.csv"
    )

    values = corr.values[
        np.triu_indices_from(
            corr.values,
            k=1
        )
    ]

    values = values[
        np.isfinite(values)
    ]

    corr_outputs.append(
        {
            "year": year,
            "n_wells": wide.shape[1],
            "mean_pairwise_correlation":
                np.mean(values)
                if len(values)
                else np.nan,
            "median_pairwise_correlation":
                np.median(values)
                if len(values)
                else np.nan,
            "minimum_pairwise_correlation":
                np.min(values)
                if len(values)
                else np.nan,
            "maximum_pairwise_correlation":
                np.max(values)
                if len(values)
                else np.nan,
        }
    )


corr_summary = pd.DataFrame(
    corr_outputs
)

corr_summary.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_correlation_summary.csv",
    index=False
)


# ============================================================
# 3. Platform-wide daily groundwater signal
#
# Descriptive spatial mean and spread only.
# Wells are NOT independent replicates.
# ============================================================

platform = (
    gw.groupby(["year", "date"])
    .agg(
        n_wells=("groundwater_depth_cm", "count"),

        mean_depth_cm=(
            "groundwater_depth_cm",
            "mean"
        ),

        median_depth_cm=(
            "groundwater_depth_cm",
            "median"
        ),

        min_depth_cm=(
            "groundwater_depth_cm",
            "min"
        ),

        max_depth_cm=(
            "groundwater_depth_cm",
            "max"
        ),

        sd_across_wells_cm=(
            "groundwater_depth_cm",
            "std"
        ),
    )
    .reset_index()
)

platform["spatial_range_cm"] = (
    platform["max_depth_cm"]
    - platform["min_depth_cm"]
)

platform.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_platform_daily.csv",
    index=False
)


# ============================================================
# 4. Monthly platform summary
# ============================================================

monthly = (
    platform
    .set_index("date")
    .groupby("year")
    .resample("MS")
    .agg(
        mean_depth_cm=("mean_depth_cm", "mean"),
        min_platform_mean_cm=("mean_depth_cm", "min"),
        max_platform_mean_cm=("mean_depth_cm", "max"),
        mean_spatial_range_cm=("spatial_range_cm", "mean"),
    )
    .reset_index()
)

monthly.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_monthly_summary.csv",
    index=False
)


# ============================================================
# Terminal report
# ============================================================

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 20)

print()
print("=" * 95)
print("GROUNDWATER PIEZOMETER SUMMARY")
print("=" * 95)

print(
    summary.round(
        {
            "mean_depth_cm": 2,
            "median_depth_cm": 2,
            "sd_depth_cm": 2,
            "min_depth_cm": 2,
            "max_depth_cm": 2,
            "range_cm": 2,
        }
    ).to_string(index=False)
)

print()
print("=" * 95)
print("GROUNDWATER COHERENCE")
print("=" * 95)

print(
    corr_summary
    .round(3)
    .to_string(index=False)
)

print()
print("=" * 95)
print("MONTHLY PLATFORM SIGNAL")
print("=" * 95)

print(
    monthly
    .round(3)
    .to_string(index=False)
)

print()
print(
    "IMPORTANT: piezometers are spatial monitoring locations, "
    "not independent treatment replicates."
)

print(
    "Correlations describe shared temporal behaviour and do "
    "not establish causal treatment effects."
)

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"

TABLES.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD DATA
# ============================================================

gw = pd.read_csv(
    DATA / "MEDWATERICE_CS1_groundwater_depth_long.csv"
)

hyd = pd.read_csv(
    DATA / "MEDWATERICE_CS1_hydrology_daily.csv"
)

gw["date"] = pd.to_datetime(gw["date"], errors="raise")
hyd["date"] = pd.to_datetime(hyd["date"], errors="raise")

for col in [
    "groundwater_depth_cm",
]:
    gw[col] = pd.to_numeric(gw[col], errors="coerce")

for col in [
    "ponding_level_mm",
    "rainfall_mm",
    "irrigation_inflow_mm",
    "irrigation_outflow_mm",
    "net_irrigation_calculated_mm",
    "percolation_balance_mm",
]:
    hyd[col] = pd.to_numeric(hyd[col], errors="coerce")


# ============================================================
# 1. PLATFORM-WIDE DAILY GROUNDWATER SIGNAL
#
# Descriptive mean across wells.
# Wells are spatial monitoring locations, not replicates.
# ============================================================

gw_platform = (
    gw.groupby(["year", "date"])
    .agg(
        groundwater_mean_depth_cm=(
            "groundwater_depth_cm",
            "mean"
        ),
        groundwater_median_depth_cm=(
            "groundwater_depth_cm",
            "median"
        ),
        groundwater_n_wells=(
            "groundwater_depth_cm",
            "count"
        ),
        groundwater_sd_across_wells_cm=(
            "groundwater_depth_cm",
            "std"
        ),
    )
    .reset_index()
)


# ============================================================
# 2. PLATFORM SURFACE-HYDROLOGY CONTEXT
#
# Rainfall is identical across treatments on common dates.
# Other variables are summarized descriptively across the
# instrumented management plots.
# ============================================================

surface = (
    hyd.groupby(["year", "date"])
    .agg(
        rainfall_mm=(
            "rainfall_mm",
            "mean"
        ),

        mean_ponding_level_mm=(
            "ponding_level_mm",
            "mean"
        ),

        total_irrigation_inflow_mm=(
            "irrigation_inflow_mm",
            "sum"
        ),

        total_irrigation_outflow_mm=(
            "irrigation_outflow_mm",
            "sum"
        ),

        total_net_irrigation_mm=(
            "net_irrigation_calculated_mm",
            "sum"
        ),

        total_percolation_balance_mm=(
            "percolation_balance_mm",
            "sum"
        ),
    )
    .reset_index()
)


merged = gw_platform.merge(
    surface,
    on=["year", "date"],
    how="inner"
)


merged.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_surface_daily_merged.csv",
    index=False
)


# ============================================================
# 3. CONTEMPORANEOUS CORRELATIONS
#
# Pearson + Spearman.
# Descriptive association only.
# ============================================================

surface_vars = [
    "rainfall_mm",
    "mean_ponding_level_mm",
    "total_irrigation_inflow_mm",
    "total_irrigation_outflow_mm",
    "total_net_irrigation_mm",
    "total_percolation_balance_mm",
]

corr_rows = []

for year, g in merged.groupby("year"):

    for var in surface_vars:

        pair = g[
            [
                "groundwater_mean_depth_cm",
                var
            ]
        ].dropna()

        pearson = (
            pair["groundwater_mean_depth_cm"]
            .corr(pair[var], method="pearson")
        )

        spearman = (
            pair["groundwater_mean_depth_cm"]
            .corr(pair[var], method="spearman")
        )

        corr_rows.append(
            {
                "year": year,
                "surface_variable": var,
                "n_days": len(pair),
                "pearson_r": pearson,
                "spearman_rho": spearman,
            }
        )


corr = pd.DataFrame(corr_rows)

corr.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_contemporaneous_correlations.csv",
    index=False
)


# ============================================================
# 4. SHORT-LAG ASSOCIATIONS
#
# Interpretation:
# lag_days = 0  -> same-day surface variable
# lag_days = 1  -> surface variable one day earlier
# lag_days = 3  -> surface variable three days earlier
# lag_days = 7  -> surface variable seven days earlier
#
# These are exploratory temporal associations only.
# ============================================================

lags = [0, 1, 3, 7]

lag_rows = []

for year, g in merged.groupby("year"):

    g = g.sort_values("date").copy()

    for var in surface_vars:

        for lag in lags:

            x = g[var].shift(lag)
            y = g["groundwater_mean_depth_cm"]

            pair = pd.DataFrame(
                {
                    "x": x,
                    "y": y
                }
            ).dropna()

            lag_rows.append(
                {
                    "year": year,
                    "surface_variable": var,
                    "lag_days": lag,
                    "n_days": len(pair),

                    "pearson_r":
                        pair["y"].corr(
                            pair["x"],
                            method="pearson"
                        ),

                    "spearman_rho":
                        pair["y"].corr(
                            pair["x"],
                            method="spearman"
                        ),
                }
            )


lagged = pd.DataFrame(lag_rows)

lagged.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_lagged_correlations.csv",
    index=False
)


# ============================================================
# 5. DETRENDED / CHANGE-BASED SENSITIVITY
#
# This matters because raw correlations can be inflated by
# shared seasonal trends.
#
# Use first daily differences.
# ============================================================

diff_rows = []

for year, g in merged.groupby("year"):

    g = g.sort_values("date").copy()

    g["d_groundwater_depth_cm"] = (
        g["groundwater_mean_depth_cm"].diff()
    )

    for var in surface_vars:

        g[f"d_{var}"] = g[var].diff()

        pair = g[
            [
                "d_groundwater_depth_cm",
                f"d_{var}"
            ]
        ].dropna()

        diff_rows.append(
            {
                "year": year,
                "surface_variable": var,
                "n_days": len(pair),

                "pearson_r_first_difference":
                    pair[
                        "d_groundwater_depth_cm"
                    ].corr(
                        pair[f"d_{var}"],
                        method="pearson"
                    ),

                "spearman_rho_first_difference":
                    pair[
                        "d_groundwater_depth_cm"
                    ].corr(
                        pair[f"d_{var}"],
                        method="spearman"
                    ),
            }
        )


diffcorr = pd.DataFrame(diff_rows)

diffcorr.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_first_difference_correlations.csv",
    index=False
)


# ============================================================
# 6. BEST ABSOLUTE LAG PER VARIABLE
#
# Exploratory summary only.
# ============================================================

best_rows = []

for (year, var), g in lagged.groupby(
    ["year", "surface_variable"]
):

    valid = g.dropna(
        subset=["spearman_rho"]
    ).copy()

    if len(valid) == 0:
        continue

    valid["abs_rho"] = (
        valid["spearman_rho"].abs()
    )

    best = valid.loc[
        valid["abs_rho"].idxmax()
    ]

    best_rows.append(
        {
            "year": year,
            "surface_variable": var,
            "best_lag_days":
                int(best["lag_days"]),
            "spearman_rho":
                best["spearman_rho"],
            "pearson_r":
                best["pearson_r"],
            "n_days":
                int(best["n_days"]),
        }
    )


best = pd.DataFrame(best_rows)

best.to_csv(
    TABLES /
    "MEDWATERICE_groundwater_best_short_lag_summary.csv",
    index=False
)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 20)

print()
print("=" * 100)
print("CONTEMPORANEOUS GROUNDWATER ASSOCIATIONS")
print("=" * 100)

print(
    corr
    .round(3)
    .to_string(index=False)
)

print()
print("=" * 100)
print("BEST SHORT-LAG ASSOCIATIONS")
print("=" * 100)

print(
    best
    .round(3)
    .to_string(index=False)
)

print()
print("=" * 100)
print("FIRST-DIFFERENCE SENSITIVITY")
print("=" * 100)

print(
    diffcorr
    .round(3)
    .to_string(index=False)
)

print()
print(
    "IMPORTANT: these are descriptive temporal associations."
)

print(
    "Raw correlations may reflect shared seasonality; "
    "first-difference correlations are included as a "
    "sensitivity check."
)

print(
    "No correlation here establishes a causal groundwater "
    "response to a management treatment."
)

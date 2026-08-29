from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"
DIAG = ROOT / "outputs" / "diagnostics"

TABLES.mkdir(parents=True, exist_ok=True)
DIAG.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    DATA / "MEDWATERICE_CS1_hydrology_daily.csv"
)

df["date"] = pd.to_datetime(df["date"])


# ============================================================
# 1. COMMON-WINDOW DEFINITIONS
# ============================================================

common_ranges = {}

for year, gy in df.groupby("year"):

    coverage = (
        gy.groupby("treatment")
        .agg(
            first=("date", "min"),
            last=("date", "max")
        )
    )

    common_ranges[year] = (
        coverage["first"].max(),
        coverage["last"].min()
    )


frames = []

for year, gy in df.groupby("year"):

    start, end = common_ranges[year]

    g = gy.loc[
        gy["date"].between(start, end)
    ].copy()

    g["common_start"] = start
    g["common_end"] = end

    frames.append(g)

common = pd.concat(frames, ignore_index=True)


# ============================================================
# 2. DAILY DISTRIBUTION DIAGNOSTICS
# ============================================================

variables = [
    "irrigation_inflow_mm",
    "irrigation_outflow_mm",
    "net_irrigation_calculated_mm",
    "rainfall_mm",
    "etc_adjusted_mm",
    "ponding_level_mm",
    "percolation_balance_mm",
]

rows = []

for (year, treatment), g in common.groupby(
    ["year", "treatment"]
):

    for var in variables:

        x = g[var].dropna()

        rows.append(
            {
                "year": year,
                "treatment": treatment,
                "variable": var,
                "n": len(x),
                "sum": x.sum(),
                "mean": x.mean(),
                "median": x.median(),
                "sd": x.std(),
                "min": x.min(),
                "p05": x.quantile(0.05),
                "p25": x.quantile(0.25),
                "p75": x.quantile(0.75),
                "p95": x.quantile(0.95),
                "max": x.max(),
                "n_zero": int((x == 0).sum()),
                "pct_zero": 100 * (x == 0).mean(),
                "n_negative": int((x < 0).sum()),
                "pct_negative": 100 * (x < 0).mean(),
            }
        )

dist = pd.DataFrame(rows)

dist.to_csv(
    TABLES /
    "MEDWATERICE_crossyear_distribution_diagnostics.csv",
    index=False
)


# ============================================================
# 3. IRRIGATION EVENT STRUCTURE
#
# Do not assume every positive Qin is a distinct irrigation event.
# This is an operational daily-event diagnostic only.
# ============================================================

event_rows = []

for (year, treatment), g in common.groupby(
    ["year", "treatment"]
):

    g = g.sort_values("date").copy()

    inflow = g["irrigation_inflow_mm"]

    positive = inflow > 0

    event_rows.append(
        {
            "year": year,
            "treatment": treatment,

            "n_days": len(g),

            "days_with_positive_inflow":
                int(positive.sum()),

            "fraction_days_positive_inflow":
                positive.mean(),

            "total_inflow_mm":
                inflow.sum(),

            "mean_inflow_all_days_mm":
                inflow.mean(),

            "mean_inflow_positive_days_mm":
                inflow.loc[positive].mean(),

            "median_inflow_positive_days_mm":
                inflow.loc[positive].median(),

            "max_daily_inflow_mm":
                inflow.max(),

            "days_with_positive_outflow":
                int(
                    (
                        g["irrigation_outflow_mm"] > 0
                    ).sum()
                ),

            "fraction_days_positive_outflow":
                (
                    g["irrigation_outflow_mm"] > 0
                ).mean(),

            "days_net_irrigation_negative":
                int(
                    (
                        g["net_irrigation_calculated_mm"] < 0
                    ).sum()
                ),

            "fraction_days_net_irrigation_negative":
                (
                    g["net_irrigation_calculated_mm"] < 0
                ).mean(),
        }
    )

events = pd.DataFrame(event_rows)

events.to_csv(
    TABLES /
    "MEDWATERICE_irrigation_event_structure.csv",
    index=False
)


# ============================================================
# 4. RAINFALL / ET CONSISTENCY WITHIN YEAR
# ============================================================

weather_rows = []

for year, gy in common.groupby("year"):

    treatments = sorted(
        gy["treatment"].unique()
    )

    base = (
        gy.loc[
            gy["treatment"] == treatments[0],
            ["date", "rainfall_mm"]
        ]
        .rename(
            columns={
                "rainfall_mm":
                f"rain_{treatments[0]}"
            }
        )
    )

    comparison = base.copy()

    for treatment in treatments[1:]:

        z = (
            gy.loc[
                gy["treatment"] == treatment,
                ["date", "rainfall_mm"]
            ]
            .rename(
                columns={
                    "rainfall_mm":
                    f"rain_{treatment}"
                }
            )
        )

        comparison = comparison.merge(
            z,
            on="date",
            how="inner"
        )

    rain_cols = [
        c for c in comparison.columns
        if c.startswith("rain_")
    ]

    comparison["rain_range"] = (
        comparison[rain_cols].max(axis=1)
        - comparison[rain_cols].min(axis=1)
    )

    weather_rows.append(
        {
            "year": year,

            "n_common_dates":
                len(comparison),

            "max_daily_rainfall_difference_mm":
                comparison["rain_range"].max(),

            "days_rainfall_differs":
                int(
                    (
                        comparison["rain_range"] > 1e-9
                    ).sum()
                ),
        }
    )

weather = pd.DataFrame(weather_rows)

weather.to_csv(
    TABLES /
    "MEDWATERICE_weather_consistency.csv",
    index=False
)


# ============================================================
# 5. YEAR-TO-YEAR RATIOS WITHIN EACH MANAGEMENT SYSTEM
#
# Diagnostic only.
# ============================================================

season = pd.read_csv(
    TABLES /
    "MEDWATERICE_common_window_summary.csv"
)

metrics = [
    "gross_inflow_mm",
    "gross_outflow_mm",
    "net_irrigation_mm",
    "rainfall_mm",
    "etc_adjusted_mm",
    "percolation_balance_sum_mm",
    "mean_ponding_level_mm",
    "fraction_positive_ponding",
]

ratio_rows = []

for treatment, gt in season.groupby(
    "treatment"
):

    y19 = gt.loc[
        gt["year"] == 2019
    ].iloc[0]

    y20 = gt.loc[
        gt["year"] == 2020
    ].iloc[0]

    for metric in metrics:

        a = y19[metric]
        b = y20[metric]

        ratio_rows.append(
            {
                "treatment": treatment,
                "metric": metric,
                "value_2019": a,
                "value_2020": b,
                "absolute_change_2020_minus_2019":
                    b - a,

                "percent_change_2020_vs_2019":
                    (
                        100 * (b - a) / a
                        if a != 0
                        else np.nan
                    ),

                "ratio_2020_to_2019":
                    (
                        b / a
                        if a != 0
                        else np.nan
                    ),
            }
        )

ratios = pd.DataFrame(ratio_rows)

ratios.to_csv(
    TABLES /
    "MEDWATERICE_crossyear_ratios.csv",
    index=False
)


# ============================================================
# 6. DAILY INFLOW / OUTFLOW QUANTILES
# ============================================================

print()
print("=" * 95)
print("IRRIGATION EVENT STRUCTURE")
print("=" * 95)

print(
    events.round(3).to_string(index=False)
)


print()
print("=" * 95)
print("WEATHER CONSISTENCY")
print("=" * 95)

print(
    weather.round(6).to_string(index=False)
)


print()
print("=" * 95)
print("YEAR-TO-YEAR CHANGE")
print("=" * 95)

display_metrics = [
    "gross_inflow_mm",
    "gross_outflow_mm",
    "net_irrigation_mm",
    "percolation_balance_sum_mm",
    "mean_ponding_level_mm",
    "fraction_positive_ponding",
]

print(
    ratios.loc[
        ratios["metric"].isin(
            display_metrics
        )
    ]
    .round(3)
    .to_string(index=False)
)


print()
print("=" * 95)
print("DAILY INFLOW DISTRIBUTIONS")
print("=" * 95)

print(
    dist.loc[
        dist["variable"] ==
        "irrigation_inflow_mm"
    ]
    .round(3)
    .to_string(index=False)
)


print()
print(
    "Cross-year measurement comparability "
    "diagnostic completed."
)

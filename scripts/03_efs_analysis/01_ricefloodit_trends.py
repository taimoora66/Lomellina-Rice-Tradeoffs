from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# RiceFloodIT 2000-2021 quantitative trend analysis
#
# PRIMARY:
#   fixed 22-year balanced pixel panel
#
# SENSITIVITY:
#   all available pixels
#   balanced panel with count >= 3
#   count-weighted balanced-panel mean
#
# INFERENCE:
#   annual series, not 80,926 independent observations
# ============================================================


ROOT = Path(".")
DATA = ROOT / "data" / "raw" / "RiceFloodIT"
OUT = ROOT / "outputs" / "tables"
DIAG = ROOT / "outputs" / "diagnostics"

OUT.mkdir(parents=True, exist_ok=True)
DIAG.mkdir(parents=True, exist_ok=True)

FF_FILE = DATA / "ffavg_2021.csv"
WS_FILE = DATA / "ws_2021.csv"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def trend_stats(year, values):
    """
    Descriptive temporal trend statistics for an annual series.

    OLS is descriptive.
    Kendall tau provides a non-parametric monotonic-trend check.
    Theil-Sen provides a robust slope estimate.
    """

    x = np.asarray(year, dtype=float)
    y = np.asarray(values, dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]

    if len(y) < 3:
        return {
            "n_years": len(y),
            "ols_slope_per_year": np.nan,
            "ols_intercept": np.nan,
            "ols_r2": np.nan,
            "ols_p": np.nan,
            "kendall_tau": np.nan,
            "kendall_p": np.nan,
            "theil_sen_slope": np.nan,
            "theil_sen_low95": np.nan,
            "theil_sen_high95": np.nan,
        }

    lr = stats.linregress(x, y)

    kt = stats.kendalltau(x, y)

    ts = stats.theilslopes(y, x, alpha=0.95)

    return {
        "n_years": len(y),
        "ols_slope_per_year": lr.slope,
        "ols_intercept": lr.intercept,
        "ols_r2": lr.rvalue ** 2,
        "ols_p": lr.pvalue,
        "kendall_tau": kt.statistic,
        "kendall_p": kt.pvalue,
        "theil_sen_slope": ts.slope,
        "theil_sen_low95": ts.low_slope,
        "theil_sen_high95": ts.high_slope,
    }


def weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)

    mask = (
        np.isfinite(values)
        & np.isfinite(weights)
        & (weights > 0)
    )

    if not np.any(mask):
        return np.nan

    return np.average(values[mask], weights=weights[mask])


# ------------------------------------------------------------
# Load
# ------------------------------------------------------------

print("Loading RiceFloodIT...")

ff = pd.read_csv(FF_FILE)
ws = pd.read_csv(WS_FILE)

required_ff = {
    "x", "y", "subdistrict", "year", "ff", "count"
}

required_ws = {
    "subdistrict", "year", "ws", "count"
}

if not required_ff.issubset(ff.columns):
    raise ValueError(
        f"ffavg columns differ from expected: {list(ff.columns)}"
    )

if not required_ws.issubset(ws.columns):
    raise ValueError(
        f"ws columns differ from expected: {list(ws.columns)}"
    )

ff["year"] = pd.to_numeric(ff["year"], errors="raise").astype(int)
ff["ff"] = pd.to_numeric(ff["ff"], errors="raise")
ff["count"] = pd.to_numeric(ff["count"], errors="raise").astype(int)
ff["x"] = pd.to_numeric(ff["x"], errors="raise")
ff["y"] = pd.to_numeric(ff["y"], errors="raise")

ws["year"] = pd.to_numeric(ws["year"], errors="raise").astype(int)
ws["ws"] = pd.to_numeric(ws["ws"], errors="raise")
ws["count"] = pd.to_numeric(ws["count"], errors="raise").astype(int)


# ------------------------------------------------------------
# Basic assertions
# ------------------------------------------------------------

assert ff["year"].min() == 2000
assert ff["year"].max() == 2021
assert ff["year"].nunique() == 22

assert ff["ff"].between(0, 1).all()
assert ws["ws"].between(0, 1).all()

assert not ff.duplicated(["x", "y", "year"]).any()
assert not ws.duplicated(["subdistrict", "year"]).any()

print("Basic integrity assertions passed.")


# ------------------------------------------------------------
# Identify fixed 22-year balanced panel
# ------------------------------------------------------------

pixel_years = (
    ff.groupby(["x", "y"], sort=False)["year"]
    .nunique()
)

balanced_index = pixel_years[pixel_years == 22].index

balanced_keys = pd.DataFrame(
    balanced_index.tolist(),
    columns=["x", "y"]
)

balanced = ff.merge(
    balanced_keys,
    on=["x", "y"],
    how="inner",
    validate="many_to_one"
)

n_balanced_pixels = balanced[["x", "y"]].drop_duplicates().shape[0]

if n_balanced_pixels != 2419:
    raise ValueError(
        f"Expected 2419 balanced pixels, found {n_balanced_pixels}"
    )

year_counts = balanced.groupby("year").size()

if not (year_counts == 2419).all():
    raise ValueError(
        "Balanced panel is not exactly 2419 observations per year."
    )

print(f"Balanced panel confirmed: {n_balanced_pixels} pixels.")


# ------------------------------------------------------------
# Annual district summaries
# ------------------------------------------------------------

full_annual = (
    ff.groupby("year")
    .agg(
        n_full=("ff", "size"),
        mean_ff_full=("ff", "mean"),
        median_ff_full=("ff", "median"),
        sd_ff_full=("ff", "std"),
    )
    .reset_index()
)

balanced_annual = (
    balanced.groupby("year")
    .agg(
        n_balanced=("ff", "size"),
        mean_ff_balanced=("ff", "mean"),
        median_ff_balanced=("ff", "median"),
        sd_ff_balanced=("ff", "std"),
        mean_image_count=("count", "mean"),
    )
    .reset_index()
)

# Standard error is descriptive spatial dispersion / sqrt(n).
# It must NOT be treated as independent experimental replication.
balanced_annual["spatial_se_balanced"] = (
    balanced_annual["sd_ff_balanced"]
    / np.sqrt(balanced_annual["n_balanced"])
)


# ------------------------------------------------------------
# Observation-support sensitivity: count >= 3
# ------------------------------------------------------------

balanced_c3 = balanced.loc[balanced["count"] >= 3].copy()

c3_annual = (
    balanced_c3.groupby("year")
    .agg(
        n_balanced_count_ge3=("ff", "size"),
        mean_ff_balanced_count_ge3=("ff", "mean"),
        median_ff_balanced_count_ge3=("ff", "median"),
    )
    .reset_index()
)


# ------------------------------------------------------------
# Count-weighted balanced-panel annual mean
# ------------------------------------------------------------

weighted_rows = []

for year, g in balanced.groupby("year"):

    weighted_rows.append(
        {
            "year": int(year),
            "mean_ff_balanced_count_weighted":
                weighted_mean(g["ff"], g["count"]),
        }
    )

weighted_annual = pd.DataFrame(weighted_rows)


# ------------------------------------------------------------
# Merge annual FF results
# ------------------------------------------------------------

annual = (
    balanced_annual
    .merge(full_annual, on="year", validate="one_to_one")
    .merge(c3_annual, on="year", how="left", validate="one_to_one")
    .merge(weighted_annual, on="year", validate="one_to_one")
)

annual["full_minus_balanced"] = (
    annual["mean_ff_full"]
    - annual["mean_ff_balanced"]
)

annual.to_csv(
    OUT / "RiceFloodIT_annual_FF_summary.csv",
    index=False
)


# ------------------------------------------------------------
# District-level WS
# ------------------------------------------------------------

ws_district = (
    ws.loc[ws["subdistrict"].str.lower() == "all"]
    .sort_values("year")
    .copy()
)

if len(ws_district) != 22:
    raise ValueError(
        f"Expected 22 district WS records, found {len(ws_district)}"
    )

ws_district.to_csv(
    OUT / "RiceFloodIT_district_WS_2000_2021.csv",
    index=False
)


# ------------------------------------------------------------
# Balanced-panel subdistrict annual FF
# ------------------------------------------------------------

sub_ff = (
    balanced.groupby(["subdistrict", "year"])
    .agg(
        n_pixels=("ff", "size"),
        mean_ff=("ff", "mean"),
        median_ff=("ff", "median"),
        sd_ff=("ff", "std"),
        mean_image_count=("count", "mean"),
    )
    .reset_index()
)

sub_ff.to_csv(
    OUT / "RiceFloodIT_subdistrict_FF_annual.csv",
    index=False
)


# ------------------------------------------------------------
# Subdistrict WS
# ------------------------------------------------------------

sub_ws = (
    ws.loc[ws["subdistrict"].str.lower() != "all"]
    .sort_values(["subdistrict", "year"])
    .copy()
)

sub_ws.to_csv(
    OUT / "RiceFloodIT_subdistrict_WS_annual.csv",
    index=False
)


# ------------------------------------------------------------
# District FF trend statistics
# ------------------------------------------------------------

district_trends = []

series_to_test = {
    "balanced_primary":
        annual["mean_ff_balanced"],

    "full_sample_sensitivity":
        annual["mean_ff_full"],

    "balanced_count_ge3_sensitivity":
        annual["mean_ff_balanced_count_ge3"],

    "balanced_count_weighted_sensitivity":
        annual["mean_ff_balanced_count_weighted"],
}

for name, values in series_to_test.items():

    row = {
        "series": name,
        **trend_stats(annual["year"], values)
    }

    district_trends.append(row)

district_trends = pd.DataFrame(district_trends)

district_trends.to_csv(
    OUT / "RiceFloodIT_district_FF_trends.csv",
    index=False
)


# ------------------------------------------------------------
# District WS trend
# ------------------------------------------------------------

ws_trend = pd.DataFrame(
    [{
        "series": "district_water_seeded_proportion",
        **trend_stats(
            ws_district["year"],
            ws_district["ws"]
        )
    }]
)

ws_trend.to_csv(
    OUT / "RiceFloodIT_district_WS_trend.csv",
    index=False
)


# ------------------------------------------------------------
# Subdistrict FF trends
# ------------------------------------------------------------

sub_ff_trends = []

for subdistrict, g in sub_ff.groupby("subdistrict"):

    g = g.sort_values("year")

    sub_ff_trends.append(
        {
            "subdistrict": subdistrict,
            **trend_stats(g["year"], g["mean_ff"])
        }
    )

sub_ff_trends = pd.DataFrame(sub_ff_trends)

sub_ff_trends.to_csv(
    OUT / "RiceFloodIT_subdistrict_FF_trends.csv",
    index=False
)


# ------------------------------------------------------------
# Subdistrict WS trends
# ------------------------------------------------------------

sub_ws_trends = []

for subdistrict, g in sub_ws.groupby("subdistrict"):

    g = g.sort_values("year")

    sub_ws_trends.append(
        {
            "subdistrict": subdistrict,
            **trend_stats(g["year"], g["ws"])
        }
    )

sub_ws_trends = pd.DataFrame(sub_ws_trends)

sub_ws_trends.to_csv(
    OUT / "RiceFloodIT_subdistrict_WS_trends.csv",
    index=False
)


# ------------------------------------------------------------
# Early-vs-late period comparison
#
# Equal six-year windows:
# 2000-2005 versus 2016-2021
# ------------------------------------------------------------

early = annual.loc[
    annual["year"].between(2000, 2005),
    "mean_ff_balanced"
]

late = annual.loc[
    annual["year"].between(2016, 2021),
    "mean_ff_balanced"
]

early_mean = early.mean()
late_mean = late.mean()

period_change = pd.DataFrame(
    [{
        "early_period": "2000-2005",
        "late_period": "2016-2021",
        "early_mean_ff": early_mean,
        "late_mean_ff": late_mean,
        "absolute_change_ff": late_mean - early_mean,
        "relative_change_percent":
            100 * (late_mean - early_mean) / early_mean,
    }]
)

period_change.to_csv(
    OUT / "RiceFloodIT_early_late_change.csv",
    index=False
)


# ------------------------------------------------------------
# Endpoint values
# ------------------------------------------------------------

row_2000 = annual.loc[annual["year"] == 2000].iloc[0]
row_2021 = annual.loc[annual["year"] == 2021].iloc[0]

endpoint = pd.DataFrame(
    [{
        "metric": "balanced_mean_ff",
        "value_2000": row_2000["mean_ff_balanced"],
        "value_2021": row_2021["mean_ff_balanced"],
        "absolute_change":
            row_2021["mean_ff_balanced"]
            - row_2000["mean_ff_balanced"],
        "relative_change_percent":
            100 * (
                row_2021["mean_ff_balanced"]
                - row_2000["mean_ff_balanced"]
            )
            / row_2000["mean_ff_balanced"]
    }]
)

endpoint.to_csv(
    OUT / "RiceFloodIT_endpoint_change.csv",
    index=False
)


# ------------------------------------------------------------
# Reproducibility diagnostics
# ------------------------------------------------------------

diagnostics = pd.DataFrame(
    [{
        "ff_rows": len(ff),
        "unique_pixels": ff[["x", "y"]].drop_duplicates().shape[0],
        "balanced_pixels": n_balanced_pixels,
        "balanced_rows": len(balanced),
        "year_min": ff["year"].min(),
        "year_max": ff["year"].max(),
        "years": ff["year"].nunique(),
        "ff_missing": ff["ff"].isna().sum(),
        "duplicate_pixel_years":
            ff.duplicated(["x", "y", "year"]).sum(),
        "balanced_subdistricts":
            ",".join(sorted(balanced["subdistrict"].unique())),
    }]
)

diagnostics.to_csv(
    DIAG / "RiceFloodIT_analysis_diagnostics.csv",
    index=False
)


# ------------------------------------------------------------
# Terminal output
# ------------------------------------------------------------

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 30)

print()
print("============================================================")
print("PRIMARY ANNUAL BALANCED-PANEL FF")
print("============================================================")
print(
    annual[
        [
            "year",
            "n_balanced",
            "mean_ff_balanced",
            "mean_ff_full",
            "n_balanced_count_ge3",
            "mean_ff_balanced_count_ge3",
            "mean_ff_balanced_count_weighted",
        ]
    ].to_string(index=False)
)

print()
print("============================================================")
print("DISTRICT FF TREND CHECKS")
print("============================================================")
print(district_trends.to_string(index=False))

print()
print("============================================================")
print("DISTRICT WS TREND")
print("============================================================")
print(ws_trend.to_string(index=False))

print()
print("============================================================")
print("EARLY vs LATE")
print("============================================================")
print(period_change.to_string(index=False))

print()
print("============================================================")
print("SUBDISTRICT FF TRENDS")
print("============================================================")
print(sub_ff_trends.to_string(index=False))

print()
print("RiceFloodIT quantitative analysis completed successfully.")

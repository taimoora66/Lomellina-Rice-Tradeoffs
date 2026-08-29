from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# RiceFloodIT temporal robustness — CORRECTED
#
# Method:
# 1. fit linear annual trend
# 2. obtain residuals
# 3. centre residuals
# 4. resample residuals in moving/circular blocks
# 5. add resampled residuals back to fitted trend
# 6. refit slope
#
# This preserves temporal trend structure instead of destroying it.
# ============================================================


ROOT = Path(".")
TABLES = ROOT / "outputs" / "tables"

FF_FILE = TABLES / "RiceFloodIT_annual_FF_summary.csv"
WS_FILE = TABLES / "RiceFloodIT_district_WS_2000_2021.csv"

ff = pd.read_csv(FF_FILE)
ws = pd.read_csv(WS_FILE).sort_values("year")

rng = np.random.default_rng(20260829)


def lag1(x):
    x = np.asarray(x, dtype=float)

    if len(x) < 3:
        return np.nan

    return np.corrcoef(x[:-1], x[1:])[0, 1]


def durbin_watson(resid):
    resid = np.asarray(resid, dtype=float)

    return (
        np.sum(np.diff(resid) ** 2)
        / np.sum(resid ** 2)
    )


def circular_block_sample(residuals, block_length, rng):
    """
    Circular block resampling of residuals.
    """

    residuals = np.asarray(residuals, dtype=float)
    n = len(residuals)

    sampled = []

    while len(sampled) < n:

        start = rng.integers(0, n)

        for j in range(block_length):

            sampled.append(
                residuals[(start + j) % n]
            )

            if len(sampled) == n:
                break

    return np.asarray(sampled)


def residual_block_bootstrap(
    year,
    values,
    block_length=4,
    n_boot=20000
):
    year = np.asarray(year, dtype=float)
    values = np.asarray(values, dtype=float)

    fit = stats.linregress(year, values)

    fitted = (
        fit.intercept
        + fit.slope * year
    )

    residuals = values - fitted

    # centre residuals
    residuals = residuals - np.mean(residuals)

    slopes = np.empty(n_boot)

    for b in range(n_boot):

        resampled_residuals = circular_block_sample(
            residuals,
            block_length,
            rng
        )

        y_boot = fitted + resampled_residuals

        slopes[b] = stats.linregress(
            year,
            y_boot
        ).slope

    return {
        "observed_slope": fit.slope,

        "residual_lag1":
            lag1(residuals),

        "durbin_watson":
            durbin_watson(residuals),

        "bootstrap_median_slope":
            np.median(slopes),

        "bootstrap_low95":
            np.quantile(slopes, 0.025),

        "bootstrap_high95":
            np.quantile(slopes, 0.975),

        "bootstrap_prob_negative":
            np.mean(slopes < 0),
    }


# ------------------------------------------------------------
# Run several block lengths
#
# Because only 22 years are available, do not pretend one
# arbitrary block length is uniquely correct.
# ------------------------------------------------------------

series = {
    "balanced_primary":
        (
            ff["year"],
            ff["mean_ff_balanced"]
        ),

    "full_sample_sensitivity":
        (
            ff["year"],
            ff["mean_ff_full"]
        ),

    "balanced_count_ge3":
        (
            ff["year"],
            ff["mean_ff_balanced_count_ge3"]
        ),

    "balanced_count_weighted":
        (
            ff["year"],
            ff["mean_ff_balanced_count_weighted"]
        ),

    "district_WS":
        (
            ws["year"],
            ws["ws"]
        ),
}


results = []

for series_name, (year, values) in series.items():

    for block_length in (3, 4, 5):

        result = residual_block_bootstrap(
            year,
            values,
            block_length=block_length,
            n_boot=20000
        )

        results.append(
            {
                "series": series_name,
                "block_length": block_length,
                **result
            }
        )


results = pd.DataFrame(results)

results.to_csv(
    TABLES /
    "RiceFloodIT_temporal_robustness_corrected.csv",
    index=False
)


pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

print()
print("=" * 90)
print("CORRECTED TEMPORAL ROBUSTNESS")
print("=" * 90)

print(results.to_string(index=False))

print()
print("=" * 90)
print("PRIMARY BALANCED-PANEL RESULT")
print("=" * 90)

print(
    results.loc[
        results["series"] == "balanced_primary"
    ].to_string(index=False)
)

print()
print("Interpretation rule:")
print(
    "A trend is considered temporally robust only if its "
    "bootstrap interval remains below zero across reasonable "
    "block-length choices."
)

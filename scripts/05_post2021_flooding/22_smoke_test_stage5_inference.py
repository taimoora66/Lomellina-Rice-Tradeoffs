"""Stage 5 pre-reveal synthetic inference smoke test.

Scientific firewall
-------------------
This script uses synthetic data only. It MUST NOT read any real groundwater,
flooding-exposure, weather, eligibility, or post-2021 analytical data.

Its sole purpose is to verify that the exact inferential machinery frozen in
Stage 4 can execute before any 2022-2025 flooding-groundwater coefficient is
revealed.

Frozen implementation checks
----------------------------
- statsmodels OLS interface executes on a 12-cluster, four-year synthetic panel;
- WCR31 wild cluster bootstrap executes;
- the bootstrap null is imposed;
- Webb six-point weights execute;
- seed 20260831 is reproducible;
- a finite two-sided bootstrap p-value is returned;
- independently coded leave-one-cluster-out CV3J uncertainty is finite;
- all 12 leave-one-cluster-out fits preserve the coefficient of interest;
- the synthetic design matrix is full rank.

No synthetic numerical result has scientific interpretation.
"""

from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.formula.api as smf
from wildboottest.wildboottest import wildboottest


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "outputs" / "diagnostics" / "post2021"
OUT_JSON = OUT_DIR / "stage5_inference_smoke_test.json"

SEED = 20260831
B = 9999
BOOTSTRAP_TYPE = "31"
WEIGHTS_TYPE = "webb"
IMPOSE_NULL = True
PARAM = "ff_synth"
EXPECTED_CLUSTERS = 12
YEARS = (2022, 2023, 2024, 2025)
EXPECTED_ROWS = EXPECTED_CLUSTERS * len(YEARS)

FORMULA = "y_synth ~ ff_synth + a_synth + C(station) + C(year)"


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Required package {name!r} is not installed. "
            "Stage 5 real-data execution remains blocked."
        ) from exc


def build_synthetic_panel() -> pd.DataFrame:
    """Create a deterministic 12-cluster x 4-year synthetic panel."""
    rng = np.random.default_rng(SEED)

    station_ids = [f"S{i:02d}" for i in range(1, EXPECTED_CLUSTERS + 1)]
    station_effect = dict(zip(station_ids, rng.normal(0.0, 0.7, EXPECTED_CLUSTERS)))
    station_error = dict(zip(station_ids, rng.normal(0.0, 0.35, EXPECTED_CLUSTERS)))
    year_effect = {2022: -0.35, 2023: -0.10, 2024: 0.45, 2025: 0.05}

    rows: list[dict[str, float | int | str]] = []
    for station in station_ids:
        station_ff_shift = rng.normal(0.0, 0.25)
        station_a_shift = rng.normal(0.0, 0.35)
        for year in YEARS:
            year_index = year - YEARS[0]
            ff_synth = station_ff_shift + 0.12 * year_index + rng.normal(0.0, 0.30)
            a_synth = station_a_shift + 0.18 * year_index + rng.normal(0.0, 0.40)
            eps = station_error[station] + rng.normal(0.0, 0.45)
            y_synth = (
                0.55 * ff_synth
                + 0.30 * a_synth
                + station_effect[station]
                + year_effect[year]
                + eps
            )
            rows.append(
                {
                    "station": station,
                    "year": year,
                    "ff_synth": ff_synth,
                    "a_synth": a_synth,
                    "y_synth": y_synth,
                }
            )

    df = pd.DataFrame(rows)

    assert len(df) == EXPECTED_ROWS
    assert df["station"].nunique() == EXPECTED_CLUSTERS
    assert tuple(sorted(df["year"].unique())) == YEARS
    assert (df.groupby("station")["year"].nunique() == len(YEARS)).all()
    assert not df[["y_synth", "ff_synth", "a_synth"]].isna().any().any()
    assert not df.duplicated(["station", "year"]).any()

    return df


def extract_pvalue(result: pd.DataFrame, param: str) -> float:
    """Extract the tested-parameter p-value from wildboottest output."""
    if param in result.index and "p-value" in result.columns:
        return float(result.loc[param, "p-value"])

    if "param" in result.columns:
        row = result.loc[result["param"].astype(str) == param]
        if len(row) != 1:
            raise RuntimeError(f"Could not uniquely identify bootstrap result for {param!r}.")
        if "p-value" not in result.columns:
            raise RuntimeError("wildboottest result has no 'p-value' column.")
        return float(row["p-value"].iloc[0])

    raise RuntimeError(
        "Unsupported wildboottest result layout; cannot extract p-value safely."
    )


def run_wcr31(model, cluster: np.ndarray) -> tuple[pd.DataFrame, float]:
    """Run the exact frozen wild-cluster-bootstrap configuration."""
    result = wildboottest(
        model,
        param=PARAM,
        cluster=cluster,
        B=B,
        bootstrap_type=BOOTSTRAP_TYPE,
        impose_null=IMPOSE_NULL,
        weights_type=WEIGHTS_TYPE,
        seed=SEED,
        parallel=False,
        show=False,
    )
    pvalue = extract_pvalue(result, PARAM)

    if not np.isfinite(pvalue) or not 0.0 <= pvalue <= 1.0:
        raise RuntimeError(f"Invalid bootstrap p-value: {pvalue!r}")

    return result, pvalue


def run_cv3j(df: pd.DataFrame) -> dict[str, object]:
    """Compute the frozen leave-one-cluster-out CV3J variance independently."""
    full_fit = smf.ols(FORMULA, data=df).fit()
    if PARAM not in full_fit.params.index:
        raise RuntimeError(f"Full model does not contain coefficient {PARAM!r}.")

    stations = sorted(df["station"].unique())
    beta_minus: list[float] = []
    loo_rows: list[dict[str, object]] = []

    for omitted in stations:
        reduced = df.loc[df["station"] != omitted].copy()
        fit = smf.ols(FORMULA, data=reduced).fit()
        if PARAM not in fit.params.index:
            raise RuntimeError(
                f"Leave-one-cluster-out fit omitting {omitted} lost {PARAM!r}."
            )
        beta = float(fit.params[PARAM])
        if not np.isfinite(beta):
            raise RuntimeError(
                f"Non-finite leave-one-cluster-out coefficient omitting {omitted}."
            )
        beta_minus.append(beta)
        loo_rows.append(
            {
                "omitted_station": omitted,
                "n_rows": int(len(reduced)),
                "n_clusters": int(reduced["station"].nunique()),
                "beta_minus_g": beta,
            }
        )

    g = len(stations)
    if g != EXPECTED_CLUSTERS or len(beta_minus) != EXPECTED_CLUSTERS:
        raise RuntimeError("Unexpected number of CV3J leave-one-cluster-out fits.")

    beta_minus_array = np.asarray(beta_minus, dtype=float)
    beta_bar = float(beta_minus_array.mean())
    variance = float(((g - 1) / g) * np.sum((beta_minus_array - beta_bar) ** 2))
    se = float(np.sqrt(variance))

    if not np.isfinite(variance) or variance < 0.0:
        raise RuntimeError(f"Invalid CV3J variance: {variance!r}")
    if not np.isfinite(se) or se <= 0.0:
        raise RuntimeError(f"Invalid CV3J standard error: {se!r}")

    return {
        "beta_hat": float(full_fit.params[PARAM]),
        "beta_bar_jack": beta_bar,
        "cv3j_variance": variance,
        "cv3j_se": se,
        "leave_one_cluster_out": loo_rows,
    }


def main() -> None:
    wildboottest_version = _package_version("wildboottest")

    df = build_synthetic_panel()
    model = smf.ols(FORMULA, data=df)
    fitted = model.fit()

    exog = np.asarray(fitted.model.exog, dtype=float)
    matrix_rank = int(np.linalg.matrix_rank(exog))
    n_columns = int(exog.shape[1])
    if matrix_rank != n_columns:
        raise RuntimeError(
            f"Synthetic design matrix is rank deficient: rank={matrix_rank}, "
            f"columns={n_columns}."
        )

    # wildboottest 0.3.2 + Numba requires a numeric cluster array.
    # The scientific clustering unit is unchanged: one integer code per station.
    cluster_codes, cluster_levels = pd.factorize(
        df["station"],
        sort=True,
    )
    cluster = np.asarray(cluster_codes, dtype=np.int64)

    if len(cluster_levels) != EXPECTED_CLUSTERS:
        raise RuntimeError(
            f"Expected {EXPECTED_CLUSTERS} cluster levels; "
            f"found {len(cluster_levels)}."
        )

    _, pvalue_1 = run_wcr31(model, cluster)
    _, pvalue_2 = run_wcr31(model, cluster)

    reproducible = bool(pvalue_1 == pvalue_2)
    if not reproducible:
        raise RuntimeError(
            "Fixed-seed WCR31 Webb bootstrap was not exactly reproducible: "
            f"{pvalue_1!r} vs {pvalue_2!r}."
        )

    cv3j = run_cv3j(df)

    payload = {
        "status": "PASS",
        "scientific_interpretation": "NONE_SYNTHETIC_SMOKE_TEST_ONLY",
        "firewall": "NO_REAL_POST2021_DATA_READ",
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "statsmodels_version": statsmodels.__version__,
        "wildboottest_version": wildboottest_version,
        "formula": FORMULA,
        "tested_parameter": PARAM,
        "n_rows": int(len(df)),
        "n_clusters": int(df["station"].nunique()),
        "years": [int(y) for y in YEARS],
        "design_matrix_columns": n_columns,
        "design_matrix_rank": matrix_rank,
        "bootstrap": {
            "bootstrap_type": BOOTSTRAP_TYPE,
            "label": "WCR31",
            "weights_type": WEIGHTS_TYPE,
            "impose_null": IMPOSE_NULL,
            "B": B,
            "seed": SEED,
            "parallel": False,
            "pvalue_run_1": pvalue_1,
            "pvalue_run_2": pvalue_2,
            "fixed_seed_exactly_reproducible": reproducible,
        },
        "cv3j": cv3j,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== STAGE 5 PRE-REVEAL SYNTHETIC INFERENCE SMOKE TEST ===")
    print(f"wildboottest version: {wildboottest_version}")
    print(f"rows: {len(df)}")
    print(f"clusters: {df['station'].nunique()}")
    print(f"design rank: {matrix_rank}/{n_columns}")
    print(
        "bootstrap: "
        f"WCR{BOOTSTRAP_TYPE}, weights={WEIGHTS_TYPE}, "
        f"impose_null={IMPOSE_NULL}, B={B}, seed={SEED}"
    )
    print(f"bootstrap p-value run 1: {pvalue_1:.12g}")
    print(f"bootstrap p-value run 2: {pvalue_2:.12g}")
    print(f"CV3J SE: {cv3j['cv3j_se']:.12g}")
    print(f"output: {OUT_JSON}")
    print("STAGE 5 SMOKE TEST: PASS")
    print("REAL 2022-2025 ASSOCIATION COEFFICIENT: NOT RUN / NOT REVEALED")


if __name__ == "__main__":
    main()

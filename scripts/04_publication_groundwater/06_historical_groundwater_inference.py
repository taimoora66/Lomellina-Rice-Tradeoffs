from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from scipy.spatial.distance import cdist


# ---------------------------------------------------------------------
# Frozen historical publication model
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

PANEL = (
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

SUMMARY_OUT = OUTDIR / "historical_publication_inference_summary.csv"
BLOCK_OUT = OUTDIR / "historical_publication_block_loo.csv"
QA_OUT = OUTDIR / "historical_publication_inference_qa.csv"

TERM = "ff_10_anom"

FORMULA = (
    "gw_aug_mean_m ~ "
    "ff_10_anom + "
    "gw_pre_last_janfeb_m + "
    "P_A8 + T_A8 + "
    "C(station) + C(year)"
)

MODEL_COLS = [
    "gw_aug_mean_m",
    "ff_10_anom",
    "gw_pre_last_janfeb_m",
    "P_A8",
    "T_A8",
    "station",
    "year",
]

CUTOFFS_KM = [20.0, 30.0, 40.0]

BLOCK_SHIFTS = [
    (0.0, 0.0),
    (0.5, 0.0),
    (0.0, 0.5),
    (0.5, 0.5),
]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def bread_matrix(X):
    """
    Compute (X'X)^(-1).

    Moore-Penrose inversion is used for numerical safety. The script
    separately checks that the fitted design matrix is full rank.
    """
    return np.linalg.pinv(X.T @ X)


def sandwich(bread, meat):
    """
    Construct a symmetric sandwich covariance matrix.
    """
    cov = bread @ meat @ bread
    return (cov + cov.T) / 2.0


def hc0_meat(scores):
    """
    Observation-level HC0 meat.

    scores[i] = x_i * residual_i
    """
    return scores.T @ scores


def cluster_meat(scores, groups):
    """
    Uncorrected one-way cluster meat.

        M = sum_g S_g S_g'

    where S_g is the sum of score vectors within cluster g.
    """
    meat = np.zeros(
        (scores.shape[1], scores.shape[1]),
        dtype=float,
    )

    groups = np.asarray(groups)

    for group in pd.unique(groups):
        s = scores[groups == group].sum(axis=0)
        meat += np.outer(s, s)

    return meat


def spatial_same_year_meat(
    scores,
    years,
    coords_km,
    cutoff_km,
):
    """
    Same-year spatial-HAC meat using a Bartlett distance kernel.

        w(d) = 1 - d / cutoff,  if d < cutoff
             = 0,               otherwise

    Diagonal observations receive weight 1.

    Cross-year cross-station covariance is set to zero.

    Serial dependence within groundwater stations is handled separately
    by the station-cluster component.
    """
    meat = np.zeros(
        (scores.shape[1], scores.shape[1]),
        dtype=float,
    )

    years = np.asarray(years)
    coords_km = np.asarray(coords_km, dtype=float)

    for year in np.unique(years):
        idx = np.where(years == year)[0]

        S = scores[idx]
        C = coords_km[idx]

        D = cdist(
            C,
            C,
            metric="euclidean",
        )

        W = np.clip(
            1.0 - D / cutoff_km,
            0.0,
            1.0,
        )

        W[D >= cutoff_km] = 0.0

        np.fill_diagonal(W, 1.0)

        meat += S.T @ W @ S

    return meat


def robust_term_stats(
    beta,
    cov,
    term_idx,
    df_ref,
):
    """
    Extract inference for the frozen FF10 coefficient.

    Custom covariance estimates use t_(G-1), where G is the number
    of groundwater stations, as the reporting reference distribution.

    A normal-reference p-value is retained as a diagnostic only.
    """
    variance = float(
        cov[term_idx, term_idx]
    )

    if not np.isfinite(variance):
        raise RuntimeError(
            f"Non-finite variance for {TERM}: {variance}"
        )

    if variance <= 0:
        raise RuntimeError(
            f"Non-positive variance for {TERM}: {variance}"
        )

    se = np.sqrt(variance)

    stat = beta / se

    p_t = 2.0 * stats.t.sf(
        abs(stat),
        df=df_ref,
    )

    p_normal = 2.0 * stats.norm.sf(
        abs(stat)
    )

    crit = stats.t.ppf(
        0.975,
        df=df_ref,
    )

    return {
        "beta": float(beta),
        "se": float(se),
        "stat": float(stat),
        "p_t_station_df": float(p_t),
        "p_normal": float(p_normal),
        "ci95_low_t_station_df": float(
            beta - crit * se
        ),
        "ci95_high_t_station_df": float(
            beta + crit * se
        ),
        "reference_df": int(df_ref),
        "term_variance": variance,
    }


def covariance_diagnostics(
    name,
    cov,
):
    """
    Check covariance positive-semidefiniteness.

    Small negative values near floating-point tolerance are not counted
    as substantive negative eigenvalues.
    """
    sym = (cov + cov.T) / 2.0

    eig = np.linalg.eigvalsh(sym)

    return {
        "covariance": name,
        "min_eigenvalue": float(eig.min()),
        "max_eigenvalue": float(eig.max()),
        "negative_eigenvalues": int(
            (eig < -1e-10).sum()
        ),
        "psd_qa": (
            "PASS"
            if eig.min() >= -1e-10
            else "FAIL"
        ),
    }


# ---------------------------------------------------------------------
# Load and freeze estimation sample
# ---------------------------------------------------------------------

p = pd.read_csv(PANEL)

required = MODEL_COLS + [
    "utm_e",
    "utm_n",
]

missing = [
    c
    for c in required
    if c not in p.columns
]

if missing:
    raise RuntimeError(
        f"Required columns missing: {missing}"
    )

if p.duplicated(
    ["station", "year"]
).any():
    raise RuntimeError(
        "Duplicate station-year rows found "
        "in discovery panel."
    )

r = (
    p.dropna(subset=MODEL_COLS)
    .copy()
)

if r[
    ["utm_e", "utm_n"]
].isna().any().any():
    raise RuntimeError(
        "Frozen model sample contains "
        "missing well coordinates."
    )

r = (
    r.sort_values(
        ["station", "year"]
    )
    .reset_index(drop=True)
)


# ---------------------------------------------------------------------
# Cross-check production completeness flag
# ---------------------------------------------------------------------

flag_check = "not_available"

if "candidate_primary_complete" in p.columns:

    flag = (
        p["candidate_primary_complete"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(
            [
                "true",
                "1",
                "yes",
            ]
        )
    )

    flagged_keys = set(
        map(
            tuple,
            p.loc[
                flag,
                ["station", "year"],
            ].itertuples(
                index=False,
                name=None,
            ),
        )
    )

    model_keys = set(
        map(
            tuple,
            r[
                ["station", "year"]
            ].itertuples(
                index=False,
                name=None,
            ),
        )
    )

    flag_check = (
        "PASS"
        if flagged_keys == model_keys
        else "FAIL"
    )

    if flag_check != "PASS":
        raise RuntimeError(
            "candidate_primary_complete "
            "does not match the explicit "
            "frozen-model complete-case sample."
        )


# ---------------------------------------------------------------------
# Fit frozen coefficient exactly once
# ---------------------------------------------------------------------

ols = smf.ols(
    FORMULA,
    data=r,
).fit()

beta = float(
    ols.params[TERM]
)

term_idx = (
    list(ols.params.index)
    .index(TERM)
)

X = np.asarray(
    ols.model.exog,
    dtype=float,
)

u = np.asarray(
    ols.resid,
    dtype=float,
)

scores = X * u[:, None]

bread = bread_matrix(X)

stations = r[
    "station"
].to_numpy()

years = r[
    "year"
].to_numpy()

coords_km = (
    r[
        ["utm_e", "utm_n"]
    ]
    .to_numpy(dtype=float)
    / 1000.0
)

n = len(r)

n_wells = int(
    r["station"].nunique()
)

n_years = int(
    r["year"].nunique()
)

df_station = n_wells - 1

rank = int(
    np.linalg.matrix_rank(X)
)

k = int(
    X.shape[1]
)

if rank != k:
    raise RuntimeError(
        "Design matrix is rank deficient: "
        f"rank={rank}, columns={k}"
    )


# ---------------------------------------------------------------------
# Covariance components
# ---------------------------------------------------------------------

M_hc0 = hc0_meat(scores)

M_station = cluster_meat(
    scores,
    stations,
)

COV_HC0 = sandwich(
    bread,
    M_hc0,
)

COV_STATION_CR0 = sandwich(
    bread,
    M_station,
)

covariances = {
    "HC0": COV_HC0,
    "station_cluster_CR0": COV_STATION_CR0,
}

failed_combined_names = []

for cutoff in CUTOFFS_KM:

    cutoff_label = int(cutoff)

    M_spatial = spatial_same_year_meat(
        scores=scores,
        years=years,
        coords_km=coords_km,
        cutoff_km=cutoff,
    )

    # -------------------------------------------------------------
    # Original frozen inclusion-exclusion estimator
    #
    # Retained as QA only after the first execution demonstrated
    # that the resulting covariance matrices were indefinite.
    # These results are NOT publication inference.
    # -------------------------------------------------------------

    M_combined_failed = (
        M_station
        + M_spatial
        - M_hc0
    )

    failed_name = (
        "failed_inclusion_exclusion_"
        f"{cutoff_label}km"
    )

    covariances[failed_name] = sandwich(
        bread,
        M_combined_failed,
    )

    failed_combined_names.append(
        failed_name
    )

    # -------------------------------------------------------------
    # Same-year pure spatial HAC
    # -------------------------------------------------------------

    covariances[
        f"spatial_HAC_{cutoff_label}km"
    ] = sandwich(
        bread,
        M_spatial,
    )

    # -------------------------------------------------------------
    # Frozen QA-driven repair
    #
    # Conservative additive sandwich:
    #
    #   M_additive = M_station + M_spatial
    #
    # No HC0 subtraction is applied.
    #
    # This intentionally retains the overlapping diagonal variance
    # contribution rather than risking an indefinite covariance.
    # -------------------------------------------------------------

    M_additive = (
        M_station
        + M_spatial
    )

    covariances[
        f"additive_station_spatial_{cutoff_label}km"
    ] = sandwich(
        bread,
        M_additive,
    )


# ---------------------------------------------------------------------
# Covariance QA first
# ---------------------------------------------------------------------

cov_qa = [
    covariance_diagnostics(
        name,
        cov,
    )
    for name, cov
    in covariances.items()
]

cov_qa_df = pd.DataFrame(
    cov_qa
)

primary_cov_name = (
    "additive_station_spatial_20km"
)

primary_qa = (
    cov_qa_df.loc[
        cov_qa_df["covariance"].eq(
            primary_cov_name
        ),
        "psd_qa",
    ]
)

if len(primary_qa) != 1:
    raise RuntimeError(
        "Primary additive covariance QA "
        "could not be uniquely identified."
    )

if primary_qa.iloc[0] != "PASS":
    raise RuntimeError(
        "Primary additive covariance "
        "failed PSD QA."
    )


# ---------------------------------------------------------------------
# Build inference summary
# ---------------------------------------------------------------------

rows = []

ols_ci = (
    ols.conf_int()
    .loc[TERM]
)

rows.append(
    {
        "inference": "classical_OLS",
        "role": "benchmark",
        "beta": beta,
        "se": float(
            ols.bse[TERM]
        ),
        "stat": float(
            ols.tvalues[TERM]
        ),
        "p_t_station_df": np.nan,
        "p_normal": np.nan,
        "p_reported": float(
            ols.pvalues[TERM]
        ),
        "ci95_low_t_station_df": np.nan,
        "ci95_high_t_station_df": np.nan,
        "ci95_low_reported": float(
            ols_ci.iloc[0]
        ),
        "ci95_high_reported": float(
            ols_ci.iloc[1]
        ),
        "reference_df": int(
            ols.df_resid
        ),
        "term_variance": float(
            ols.cov_params()
            .loc[TERM, TERM]
        ),
        "N": n,
        "wells": n_wells,
        "years": n_years,
        "primary": False,
        "publishable_inference": True,
    }
)

for name, cov in covariances.items():

    z = robust_term_stats(
        beta=beta,
        cov=cov,
        term_idx=term_idx,
        df_ref=df_station,
    )

    if name.startswith(
        "failed_inclusion_exclusion_"
    ):
        role = "failed_QA_diagnostic"
        publishable = False
        primary = False

    elif name == "station_cluster_CR0":
        role = "benchmark"
        publishable = True
        primary = False

    elif name.startswith(
        "spatial_HAC_"
    ):
        role = "spatial_component_diagnostic"
        publishable = True
        primary = False

    elif name == primary_cov_name:
        role = "primary"
        publishable = True
        primary = True

    elif name.startswith(
        "additive_station_spatial_"
    ):
        role = "spatial_sensitivity"
        publishable = True
        primary = False

    else:
        role = "diagnostic"
        publishable = True
        primary = False

    qa_status = (
        cov_qa_df.loc[
            cov_qa_df[
                "covariance"
            ].eq(name),
            "psd_qa",
        ]
        .iloc[0]
    )

    rows.append(
        {
            "inference": name,
            "role": role,
            **z,
            "p_reported": (
                z["p_t_station_df"]
                if publishable
                else np.nan
            ),
            "ci95_low_reported": (
                z[
                    "ci95_low_t_station_df"
                ]
                if publishable
                else np.nan
            ),
            "ci95_high_reported": (
                z[
                    "ci95_high_t_station_df"
                ]
                if publishable
                else np.nan
            ),
            "N": n,
            "wells": n_wells,
            "years": n_years,
            "primary": primary,
            "publishable_inference": (
                publishable
                and qa_status == "PASS"
            ),
        }
    )

summary = pd.DataFrame(
    rows
)

summary.to_csv(
    SUMMARY_OUT,
    index=False,
)


# ---------------------------------------------------------------------
# QA output
# ---------------------------------------------------------------------

qa_rows = [
    {
        "check": "model_formula",
        "value": FORMULA,
    },
    {
        "check": "coefficient_term",
        "value": TERM,
    },
    {
        "check": "N",
        "value": n,
    },
    {
        "check": "wells",
        "value": n_wells,
    },
    {
        "check": "years",
        "value": n_years,
    },
    {
        "check": "year_min",
        "value": int(
            r["year"].min()
        ),
    },
    {
        "check": "year_max",
        "value": int(
            r["year"].max()
        ),
    },
    {
        "check": "design_columns",
        "value": k,
    },
    {
        "check": "design_rank",
        "value": rank,
    },
    {
        "check": (
            "candidate_primary_complete_match"
        ),
        "value": flag_check,
    },
    {
        "check": "station_reference_df",
        "value": df_station,
    },
    {
        "check": "primary_covariance",
        "value": primary_cov_name,
    },
    {
        "check": (
            "failed_inclusion_exclusion_retained"
        ),
        "value": "YES",
    },
]

for row in cov_qa:
    name = row["covariance"]

    for key in [
        "min_eigenvalue",
        "max_eigenvalue",
        "negative_eigenvalues",
        "psd_qa",
    ]:
        qa_rows.append(
            {
                "check": (
                    f"{name}_{key}"
                ),
                "value": row[key],
            }
        )

pd.DataFrame(
    qa_rows
).to_csv(
    QA_OUT,
    index=False,
)


# ---------------------------------------------------------------------
# Frozen 20-km shifted-grid leave-block-out stability
# ---------------------------------------------------------------------

well_xy = (
    r[
        [
            "station",
            "utm_e",
            "utm_n",
        ]
    ]
    .drop_duplicates("station")
    .sort_values("station")
    .reset_index(drop=True)
)

block_rows = []

block_km = 20.0
block_m = block_km * 1000.0

for sx, sy in BLOCK_SHIFTS:

    w = well_xy.copy()

    w["gx"] = np.floor(
        (
            w["utm_e"]
            - sx * block_m
        )
        / block_m
    ).astype(int)

    w["gy"] = np.floor(
        (
            w["utm_n"]
            - sy * block_m
        )
        / block_m
    ).astype(int)

    w["block"] = (
        w["gx"].astype(str)
        + "_"
        + w["gy"].astype(str)
    )

    block_map = (
        w.set_index("station")[
            "block"
        ]
    )

    q = r.copy()

    q["block"] = (
        q["station"]
        .map(block_map)
    )

    occupied = sorted(
        q["block"].unique()
    )

    for block in occupied:

        omitted_mask = (
            q["block"] == block
        )

        rr = (
            q.loc[~omitted_mask]
            .copy()
        )

        omitted_wells = sorted(
            q.loc[
                omitted_mask,
                "station",
            ].unique()
        )

        try:
            mm = smf.ols(
                FORMULA,
                data=rr,
            ).fit()

            beta_loo = float(
                mm.params[TERM]
            )

            status = "PASS"

        except Exception as exc:
            beta_loo = np.nan
            status = (
                "FAIL:"
                + type(exc).__name__
            )

        block_rows.append(
            {
                "block_km": block_km,
                "shift_x_fraction": sx,
                "shift_y_fraction": sy,
                "block": block,
                "omitted_wells_n": len(
                    omitted_wells
                ),
                "omitted_wells": ";".join(
                    omitted_wells
                ),
                "remaining_N": len(rr),
                "remaining_wells": int(
                    rr[
                        "station"
                    ].nunique()
                ),
                "beta_ff10_anom": (
                    beta_loo
                ),
                "full_sample_beta": beta,
                "beta_difference": (
                    beta_loo - beta
                    if np.isfinite(
                        beta_loo
                    )
                    else np.nan
                ),
                "same_sign_as_full": (
                    bool(
                        np.sign(beta_loo)
                        == np.sign(beta)
                    )
                    if np.isfinite(
                        beta_loo
                    )
                    else np.nan
                ),
                "status": status,
            }
        )

blocks = pd.DataFrame(
    block_rows
)

blocks.to_csv(
    BLOCK_OUT,
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
    "FROZEN HISTORICAL GROUNDWATER PUBLICATION MODEL"
)
print(
    "============================================================"
)
print()

print(FORMULA)

print()
print("N =", n)
print("wells =", n_wells)
print("years =", n_years)

print(
    "year range =",
    int(r["year"].min()),
    "-",
    int(r["year"].max()),
)

print(
    "design rank =",
    rank,
    "/",
    k,
)

print(
    "candidate_primary_complete QA =",
    flag_check,
)

print()
print(
    "=== COEFFICIENT / INFERENCE ==="
)

display_cols = [
    "inference",
    "role",
    "beta",
    "se",
    "p_reported",
    "ci95_low_reported",
    "ci95_high_reported",
    "primary",
    "publishable_inference",
]

print(
    summary[
        display_cols
    ].to_string(
        index=False
    )
)

print()
print(
    "=== COVARIANCE PSD QA ==="
)

print(
    cov_qa_df.to_string(
        index=False
    )
)

print()
print(
    "=== PRIMARY INFERENCE ==="
)

primary_row = (
    summary.loc[
        summary["primary"]
    ]
    .iloc[0]
)

print(
    "covariance =",
    primary_row["inference"],
)

print(
    "beta =",
    primary_row["beta"],
)

print(
    "SE =",
    primary_row["se"],
)

print(
    "p =",
    primary_row["p_reported"],
)

print(
    "95% CI =",
    [
        primary_row[
            "ci95_low_reported"
        ],
        primary_row[
            "ci95_high_reported"
        ],
    ],
)

print()
print(
    "=== 20-KM SHIFTED-GRID LEAVE-BLOCK-OUT ==="
)

valid_blocks = (
    blocks.loc[
        blocks[
            "beta_ff10_anom"
        ].notna()
    ]
    .copy()
)

if len(valid_blocks):

    print(
        "runs =",
        len(valid_blocks),
    )

    print(
        "beta min =",
        float(
            valid_blocks[
                "beta_ff10_anom"
            ].min()
        ),
    )

    print(
        "beta median =",
        float(
            valid_blocks[
                "beta_ff10_anom"
            ].median()
        ),
    )

    print(
        "beta max =",
        float(
            valid_blocks[
                "beta_ff10_anom"
            ].max()
        ),
    )

    print(
        "same sign as full sample =",
        bool(
            valid_blocks[
                "same_sign_as_full"
            ].all()
        ),
    )

print()
print("Outputs:")
print(SUMMARY_OUT)
print(BLOCK_OUT)
print(QA_OUT)

print()
print("DONE")
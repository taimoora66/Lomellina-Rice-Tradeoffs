"""Build frozen post-2021 10-km flooding-anomaly exposures through 2025.

Scientific role
---------------
This stage is intentionally groundwater-outcome blind.

It extends the already frozen post-2021 10-km exposure construction from
2022-2023 through 2025 while preserving the exact historical spatial geometry:

- RiceFloodIT cell centers in UTM;
- scipy.spatial.cKDTree;
- query_ball_point around each well;
- radius = exactly 10,000 m;
- unweighted arithmetic mean across cells inside the radius.

The flooding anomaly itself is already frozen before this script:

    ff_anomaly_2010_2021
        = reconstructed annual FF
        - cell-specific mean reconstructed FF over 2010-2021.

Integrity gates
---------------
1. Require the frozen 4,331-cell anomaly product for every year 2022-2025.
2. Reproduce the previously frozen 2022-2023 well-exposure artifact exactly
   over all common columns before accepting 2024-2025.
3. Reproduce the previously frozen geometry summary.
4. Reproduce the previously frozen 2022-2023 exposure-variation diagnostics.
5. Reproduce the previously frozen 2022-2023 cross-year diagnostic.

No groundwater observation table is read.
No groundwater depth is inspected.
No groundwater sample selection is performed.
No association model is fitted.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[2]

ANOMALY_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "frozen_ff_anomalies_2022_2025.csv"
)

RICE_GEO_IN = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "ricefloodit_georef.csv"
)

GW_META_IN = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "groundwater_station_metadata.csv"
)

PREVIOUS_EXPOSURE_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2023.csv"
)

PREVIOUS_GEOMETRY_QA_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_geometry_qa.csv"
)

PREVIOUS_VARIATION_QA_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_exposure_variation_qa.csv"
)

PREVIOUS_CROSSYEAR_QA_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_crossyear_qa.csv"
)

OUT = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2025.csv"
)

QA_GEOMETRY_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_geometry_qa_2022_2025.csv"
)

QA_VARIATION_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_exposure_variation_qa_2022_2025.csv"
)

QA_CROSSYEAR_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_crossyear_qa_2022_2025.csv"
)

QA_PREVIOUS_EXPOSURE_REPRO_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_2022_2023_exposure_reproduction_qa.csv"
)

QA_PREVIOUS_GEOMETRY_REPRO_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_2022_2023_geometry_reproduction_qa.csv"
)

QA_PREVIOUS_VARIATION_REPRO_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_2022_2023_variation_reproduction_qa.csv"
)

QA_PREVIOUS_CROSSYEAR_REPRO_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_2022_2023_crossyear_reproduction_qa.csv"
)


YEARS = (2022, 2023, 2024, 2025)
PREVIOUS_YEARS = (2022, 2023)

RADIUS_KM = 10
RADIUS_M = 10_000.0

EXPECTED_ISS_WELLS = 37
EXPECTED_RICE_CELLS = 4331
EXPECTED_ROWS = EXPECTED_ISS_WELLS * len(YEARS)


def compare_tables(
    generated: pd.DataFrame,
    frozen: pd.DataFrame,
    key: list[str],
    label: str,
    atol: float = 1e-12,
) -> pd.DataFrame:
    """Exact-key comparison over all common columns."""

    g = generated.copy()
    f = frozen.copy()

    if g.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate keys in generated table."
        )

    if f.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate keys in frozen table."
        )

    g = g.sort_values(key).reset_index(drop=True)
    f = f.sort_values(key).reset_index(drop=True)

    if len(g) != len(f):
        raise AssertionError(
            f"{label}: row-count mismatch: "
            f"generated={len(g)}, frozen={len(f)}."
        )

    gk = g[key].copy()
    fk = f[key].copy()

    for col in key:
        if col == "station":
            gk[col] = gk[col].astype(str)
            fk[col] = fk[col].astype(str)
        else:
            gk[col] = pd.to_numeric(
                gk[col],
                errors="raise",
            )
            fk[col] = pd.to_numeric(
                fk[col],
                errors="raise",
            )

    if not gk.equals(fk):
        raise AssertionError(
            f"{label}: key values do not reproduce."
        )

    common = [
        c
        for c in f.columns
        if c in g.columns
    ]

    rows = []

    for col in common:
        if col in key:
            continue

        a = f[col]
        b = g[col]

        if (
            pd.api.types.is_numeric_dtype(a)
            and pd.api.types.is_numeric_dtype(b)
        ):
            equal = np.isclose(
                pd.to_numeric(
                    a,
                    errors="coerce",
                ).to_numpy(dtype=float),
                pd.to_numeric(
                    b,
                    errors="coerce",
                ).to_numpy(dtype=float),
                equal_nan=True,
                rtol=0,
                atol=atol,
            )
        else:
            equal = (
                a.astype("string")
                .fillna("<NA>")
                .to_numpy()
                ==
                b.astype("string")
                .fillna("<NA>")
                .to_numpy()
            )

        mismatch_n = int(
            (~equal).sum()
        )

        rows.append(
            {
                "comparison": label,
                "column": col,
                "rows_compared": len(equal),
                "mismatch_n": mismatch_n,
                "exact_reproduction":
                    mismatch_n == 0,
            }
        )

    qa = pd.DataFrame(rows)

    if len(qa) and not qa[
        "exact_reproduction"
    ].all():
        bad = qa.loc[
            ~qa["exact_reproduction"]
        ]

        raise AssertionError(
            f"{label} failed:\n"
            + bad.to_string(index=False)
        )

    return qa


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    anomaly = pd.read_csv(ANOMALY_IN)
    georef = pd.read_csv(RICE_GEO_IN)
    wells = pd.read_csv(GW_META_IN)

    required_anomaly = {
        "rice_cell_id",
        "rice_x",
        "rice_y",
        "year",
        "ff_reconstructed",
        "ff_baseline_2010_2021",
        "ff_anomaly_2010_2021",
    }

    missing = required_anomaly - set(anomaly.columns)

    if missing:
        raise AssertionError(
            f"Frozen anomaly input missing columns: {sorted(missing)}"
        )

    required_georef = {
        "x",
        "y",
        "utm_e",
        "utm_n",
    }

    missing = required_georef - set(georef.columns)

    if missing:
        raise AssertionError(
            f"RiceFloodIT georeference missing columns: {sorted(missing)}"
        )

    required_wells = {
        "station",
        "utm_e",
        "utm_n",
        "aquifer_group",
    }

    missing = required_wells - set(wells.columns)

    if missing:
        raise AssertionError(
            f"Groundwater metadata missing columns: {sorted(missing)}"
        )

    wells = wells.loc[
        wells["aquifer_group"] == "ISS"
    ].copy()

    if len(wells) != EXPECTED_ISS_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_WELLS} ISS wells; "
            f"found {len(wells)}."
        )

    if wells["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            "ISS station metadata are not one row per well."
        )

    anomaly = anomaly.loc[
        anomaly["year"].isin(YEARS)
    ].copy()

    expected_anomaly_rows = (
        EXPECTED_RICE_CELLS
        * len(YEARS)
    )

    if len(anomaly) != expected_anomaly_rows:
        raise AssertionError(
            f"Expected {expected_anomaly_rows:,} anomaly cell-years; "
            f"found {len(anomaly):,}."
        )

    if anomaly.duplicated(
        [
            "rice_cell_id",
            "year",
        ]
    ).any():
        raise AssertionError(
            "Duplicate rice_cell_id-year rows in frozen anomaly input."
        )

    for year in YEARS:
        y = anomaly.loc[
            anomaly["year"] == year
        ]

        if len(y) != EXPECTED_RICE_CELLS:
            raise AssertionError(
                f"{year}: expected {EXPECTED_RICE_CELLS} cells; "
                f"found {len(y)}."
            )

        if y["ff_anomaly_2010_2021"].isna().any():
            raise AssertionError(
                f"{year}: missing frozen flooding anomaly."
            )

    return anomaly, georef, wells


def build_pixel_geometry(
    anomaly: pd.DataFrame,
    georef: pd.DataFrame,
) -> pd.DataFrame:
    """Reproduce the historical RiceFloodIT cell-center geometry."""

    geom = (
        georef[
            [
                "x",
                "y",
                "utm_e",
                "utm_n",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    if len(geom) != EXPECTED_RICE_CELLS:
        raise AssertionError(
            f"Expected {EXPECTED_RICE_CELLS} unique RiceFloodIT cells "
            f"in georeference; found {len(geom)}."
        )

    if geom.duplicated(
        [
            "x",
            "y",
        ]
    ).any():
        raise AssertionError(
            "Duplicate x/y coordinates remain in RiceFloodIT geometry."
        )

    frozen_cells = (
        anomaly[
            [
                "rice_x",
                "rice_y",
            ]
        ]
        .drop_duplicates()
    )

    if len(frozen_cells) != EXPECTED_RICE_CELLS:
        raise AssertionError(
            "Frozen anomaly panel does not contain 4,331 unique cells."
        )

    check = frozen_cells.merge(
        geom,
        left_on=[
            "rice_x",
            "rice_y",
        ],
        right_on=[
            "x",
            "y",
        ],
        how="left",
        validate="one_to_one",
    )

    if (
        check["utm_e"].isna().any()
        or check["utm_n"].isna().any()
    ):
        raise AssertionError(
            "Some frozen anomaly cells do not map to the historical "
            "RiceFloodIT UTM geometry."
        )

    geom = geom.reset_index(drop=True)
    geom["pixel_id"] = np.arange(len(geom))

    return geom


def build_exposures(
    anomaly: pd.DataFrame,
    pix: pd.DataFrame,
    wells: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    tree = cKDTree(
        pix[
            [
                "utm_e",
                "utm_n",
            ]
        ].to_numpy()
    )

    anomaly = anomaly.merge(
        pix[
            [
                "x",
                "y",
                "pixel_id",
            ]
        ],
        left_on=[
            "rice_x",
            "rice_y",
        ],
        right_on=[
            "x",
            "y",
        ],
        how="left",
        validate="many_to_one",
    )

    if anomaly["pixel_id"].isna().any():
        raise AssertionError(
            "Failed to assign pixel_id to every frozen anomaly row."
        )

    anomaly["pixel_id"] = anomaly["pixel_id"].astype(int)

    by_year = {
        int(year): d.set_index("pixel_id")
        for year, d in anomaly.groupby("year")
    }

    rows = []
    geometry_rows = []

    for w in wells.sort_values("station").itertuples(
        index=False
    ):
        ids = tree.query_ball_point(
            [
                float(w.utm_e),
                float(w.utm_n),
            ],
            RADIUS_M,
        )

        ids = sorted(ids)

        if not ids:
            geometry_rows.append(
                {
                    "station": w.station,
                    "radius_km": RADIUS_KM,
                    "cells_10km": 0,
                    "nearest_cell_distance_m": np.nan,
                    "farthest_included_cell_distance_m": np.nan,
                }
            )

            for year in YEARS:
                rows.append(
                    {
                        "station": w.station,
                        "year": year,
                        "radius_km": RADIUS_KM,
                        "n_cells_10km": 0,
                        "ff10_reconstructed": np.nan,
                        "ff10_baseline_2010_2021": np.nan,
                        "ff10_anomaly_2010_2021": np.nan,
                        "anomaly_identity_residual": np.nan,
                    }
                )

            continue

        coords = pix.loc[
            ids,
            [
                "utm_e",
                "utm_n",
            ],
        ].to_numpy()

        well_xy = np.array(
            [
                float(w.utm_e),
                float(w.utm_n),
            ]
        )

        distances = np.sqrt(
            np.sum(
                (coords - well_xy) ** 2,
                axis=1,
            )
        )

        if float(distances.max()) > RADIUS_M + 1e-9:
            raise AssertionError(
                f"{w.station}: query_ball_point returned a cell "
                "outside the frozen 10-km radius."
            )

        geometry_rows.append(
            {
                "station": w.station,
                "radius_km": RADIUS_KM,
                "cells_10km": len(ids),
                "nearest_cell_distance_m":
                    float(distances.min()),
                "farthest_included_cell_distance_m":
                    float(distances.max()),
            }
        )

        for year in YEARS:
            yr = by_year[year]

            q = yr.loc[
                yr.index.intersection(ids)
            ].copy()

            if len(q) != len(ids):
                raise AssertionError(
                    f"{w.station} {year}: frozen reconstructed product "
                    f"contains {len(q)} of {len(ids)} expected 10-km cells."
                )

            if q["ff_anomaly_2010_2021"].isna().any():
                raise AssertionError(
                    f"{w.station} {year}: missing frozen anomaly "
                    "inside 10-km exposure."
                )

            ff10_anomaly = float(
                q[
                    "ff_anomaly_2010_2021"
                ].mean()
            )

            ff10_reconstructed = float(
                q[
                    "ff_reconstructed"
                ].mean()
            )

            ff10_baseline = float(
                q[
                    "ff_baseline_2010_2021"
                ].mean()
            )

            residual = (
                ff10_anomaly
                - (
                    ff10_reconstructed
                    - ff10_baseline
                )
            )

            if abs(residual) > 1e-12:
                raise AssertionError(
                    f"{w.station} {year}: exposure anomaly identity "
                    f"failed ({residual})."
                )

            rows.append(
                {
                    "station": w.station,
                    "year": year,
                    "radius_km": RADIUS_KM,
                    "n_cells_10km": len(q),
                    "ff10_reconstructed":
                        ff10_reconstructed,
                    "ff10_baseline_2010_2021":
                        ff10_baseline,
                    "ff10_anomaly_2010_2021":
                        ff10_anomaly,
                    "anomaly_identity_residual":
                        residual,
                }
            )

    out = (
        pd.DataFrame(rows)
        .sort_values(
            [
                "station",
                "year",
            ]
        )
        .reset_index(drop=True)
    )

    geometry = (
        pd.DataFrame(geometry_rows)
        .sort_values("station")
        .reset_index(drop=True)
    )

    return out, geometry


def validate_output(
    out: pd.DataFrame,
    geometry: pd.DataFrame,
) -> None:
    if len(out) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} well-years; "
            f"found {len(out)}."
        )

    if out["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            "Unexpected number of ISS wells in exposure output."
        )

    observed_years = tuple(
        sorted(
            out["year"]
            .unique()
            .tolist()
        )
    )

    if observed_years != YEARS:
        raise AssertionError(
            f"Unexpected years in exposure output: {observed_years}."
        )

    missing_exposure = (
        out[
            "ff10_anomaly_2010_2021"
        ].isna()
    )

    if not (
        (
            out.loc[
                missing_exposure,
                "n_cells_10km",
            ]
            == 0
        ).all()
        and
        (
            out.loc[
                ~missing_exposure,
                "n_cells_10km",
            ]
            > 0
        ).all()
    ):
        raise AssertionError(
            "Exposure missingness is not explained exactly by "
            "zero 10-km geometric cell membership."
        )

    if out.duplicated(
        [
            "station",
            "year",
        ]
    ).any():
        raise AssertionError(
            "Duplicate station-year exposure records."
        )

    membership_check = (
        out.groupby(
            "station"
        )[
            "n_cells_10km"
        ]
        .nunique()
    )

    if not (
        membership_check == 1
    ).all():
        raise AssertionError(
            "10-km cell membership changes across years."
        )

    if len(geometry) != EXPECTED_ISS_WELLS:
        raise AssertionError(
            "Unexpected number of wells in geometry table."
        )


def make_variation_qa(
    out: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for year in YEARS:
        y = out.loc[
            out["year"] == year
        ]

        x = y[
            "ff10_anomaly_2010_2021"
        ]

        rows.append(
            {
                "year": year,
                "wells_total_n":
                    int(
                        y[
                            "station"
                        ].nunique()
                    ),
                "wells_with_ff10_n":
                    int(
                        x.notna().sum()
                    ),
                "ff10_anomaly_mean":
                    float(x.mean()),
                "ff10_anomaly_sd":
                    float(x.std()),
                "ff10_anomaly_min":
                    float(x.min()),
                "ff10_anomaly_p25":
                    float(
                        x.quantile(0.25)
                    ),
                "ff10_anomaly_median":
                    float(
                        x.median()
                    ),
                "ff10_anomaly_p75":
                    float(
                        x.quantile(0.75)
                    ),
                "ff10_anomaly_max":
                    float(x.max()),
            }
        )

    return pd.DataFrame(rows)


def make_crossyear_qa(
    out: pd.DataFrame,
) -> pd.DataFrame:
    wide = out.pivot(
        index="station",
        columns="year",
        values="ff10_anomaly_2010_2021",
    )

    if wide.shape != (
        EXPECTED_ISS_WELLS,
        len(YEARS),
    ):
        raise AssertionError(
            "Unexpected wide exposure-panel dimensions."
        )

    rows = []

    for i, year_a in enumerate(YEARS):
        for year_b in YEARS[
            i + 1:
        ]:
            pair = wide[
                [
                    year_a,
                    year_b,
                ]
            ].dropna()

            delta = (
                pair[year_b]
                - pair[year_a]
            )

            rows.append(
                {
                    "year_a": year_a,
                    "year_b": year_b,
                    "wells_total_n":
                        EXPECTED_ISS_WELLS,
                    "wells_with_both_years_n":
                        int(len(pair)),
                    "pearson":
                        float(
                            pair[
                                year_a
                            ].corr(
                                pair[
                                    year_b
                                ],
                                method="pearson",
                            )
                        )
                        if len(pair) >= 2
                        else np.nan,
                    "spearman":
                        float(
                            pair[
                                year_a
                            ].corr(
                                pair[
                                    year_b
                                ],
                                method="spearman",
                            )
                        )
                        if len(pair) >= 2
                        else np.nan,
                    "mean_change_b_minus_a":
                        float(
                            delta.mean()
                        ),
                    "sd_change_b_minus_a":
                        float(
                            delta.std()
                        ),
                    "min_change_b_minus_a":
                        float(
                            delta.min()
                        ),
                    "max_change_b_minus_a":
                        float(
                            delta.max()
                        ),
                }
            )

    return pd.DataFrame(rows)


def make_geometry_summary(
    out: pd.DataFrame,
    geometry: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "radius_km": RADIUS_KM,
                "wells_n": len(geometry),
                "wells_with_zero_cells_10km":
                    int(
                        (
                            geometry[
                                "cells_10km"
                            ]
                            == 0
                        ).sum()
                    ),
                "wells_with_positive_cells_10km":
                    int(
                        (
                            geometry[
                                "cells_10km"
                            ]
                            > 0
                        ).sum()
                    ),
                "min_cells_10km":
                    int(
                        geometry[
                            "cells_10km"
                        ].min()
                    ),
                "median_cells_10km":
                    float(
                        geometry[
                            "cells_10km"
                        ].median()
                    ),
                "mean_cells_10km":
                    float(
                        geometry[
                            "cells_10km"
                        ].mean()
                    ),
                "max_cells_10km":
                    int(
                        geometry[
                            "cells_10km"
                        ].max()
                    ),
                "max_farthest_included_distance_m":
                    float(
                        geometry[
                            "farthest_included_cell_distance_m"
                        ].max()
                    ),
                "max_abs_anomaly_identity_residual":
                    float(
                        out[
                            "anomaly_identity_residual"
                        ].abs().max()
                    ),
            }
        ]
    )


def main() -> None:
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    QA_GEOMETRY_OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    required_previous = [
        PREVIOUS_EXPOSURE_IN,
        PREVIOUS_GEOMETRY_QA_IN,
        PREVIOUS_VARIATION_QA_IN,
        PREVIOUS_CROSSYEAR_QA_IN,
    ]

    missing_previous = [
        p
        for p in required_previous
        if not p.exists()
    ]

    if missing_previous:
        raise FileNotFoundError(
            "Required frozen 2022-2023 regression targets are missing:\n"
            + "\n".join(
                str(p)
                for p in missing_previous
            )
        )

    anomaly, georef, wells = read_inputs()

    pix = build_pixel_geometry(
        anomaly,
        georef,
    )

    out, geometry = build_exposures(
        anomaly,
        pix,
        wells,
    )

    validate_output(
        out,
        geometry,
    )

    variation = make_variation_qa(
        out
    )

    crossyear = make_crossyear_qa(
        out
    )

    geometry_summary = make_geometry_summary(
        out,
        geometry,
    )

    # -------------------------------------------------------------
    # Regression gates against the already frozen 2022-2023 unit.
    # -------------------------------------------------------------

    previous_exposure = pd.read_csv(
        PREVIOUS_EXPOSURE_IN
    )

    generated_2022_2023 = out.loc[
        out[
            "year"
        ].isin(
            PREVIOUS_YEARS
        )
    ].copy()

    exposure_repro_qa = compare_tables(
        generated=generated_2022_2023,
        frozen=previous_exposure,
        key=[
            "station",
            "year",
        ],
        label="frozen_2022_2023_ff10_exposure",
    )

    previous_geometry = pd.read_csv(
        PREVIOUS_GEOMETRY_QA_IN
    )

    geometry_repro_qa = compare_tables(
        generated=geometry_summary,
        frozen=previous_geometry,
        key=[
            "radius_km",
        ],
        label="frozen_2022_2023_ff10_geometry",
    )

    previous_variation = pd.read_csv(
        PREVIOUS_VARIATION_QA_IN
    )

    generated_variation_2022_2023 = variation.loc[
        variation[
            "year"
        ].isin(
            PREVIOUS_YEARS
        )
    ].copy()

    variation_repro_qa = compare_tables(
        generated=generated_variation_2022_2023,
        frozen=previous_variation,
        key=[
            "year",
        ],
        label="frozen_2022_2023_ff10_variation",
    )

    previous_crossyear = pd.read_csv(
        PREVIOUS_CROSSYEAR_QA_IN
    )

    # Recreate the old single-pair schema exactly enough for
    # common-column comparison.
    wide = generated_2022_2023.pivot(
        index="station",
        columns="year",
        values="ff10_anomaly_2010_2021",
    )

    old_delta = (
        wide[2023]
        - wide[2022]
    )

    generated_old_crossyear = pd.DataFrame(
        [
            {
                "wells_total_n":
                    EXPECTED_ISS_WELLS,
                "wells_with_both_years_n":
                    int(
                        wide[
                            [
                                2022,
                                2023,
                            ]
                        ]
                        .dropna()
                        .shape[0]
                    ),
                "pearson_2022_2023":
                    float(
                        wide[2022].corr(
                            wide[2023],
                            method="pearson",
                        )
                    ),
                "spearman_2022_2023":
                    float(
                        wide[2022].corr(
                            wide[2023],
                            method="spearman",
                        )
                    ),
                "mean_change_2023_minus_2022":
                    float(
                        old_delta.mean()
                    ),
                "sd_change_2023_minus_2022":
                    float(
                        old_delta.std()
                    ),
                "min_change_2023_minus_2022":
                    float(
                        old_delta.min()
                    ),
                "max_change_2023_minus_2022":
                    float(
                        old_delta.max()
                    ),
            }
        ]
    )

    crossyear_repro_qa = compare_tables(
        generated=generated_old_crossyear,
        frozen=previous_crossyear,
        key=[
            "wells_total_n",
        ],
        label="frozen_2022_2023_ff10_crossyear",
    )

    print("")
    print(
        "Previous 2022-2023 FF10 exposure reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(exposure_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    print(
        "Previous 2022-2023 FF10 geometry reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(geometry_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    print(
        "Previous 2022-2023 FF10 variation reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(variation_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    print(
        "Previous 2022-2023 FF10 cross-year reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(crossyear_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    # -------------------------------------------------------------
    # Save only after all regression gates pass.
    # -------------------------------------------------------------

    out.to_csv(
        OUT,
        index=False,
    )

    geometry_summary.to_csv(
        QA_GEOMETRY_OUT,
        index=False,
    )

    variation.to_csv(
        QA_VARIATION_OUT,
        index=False,
    )

    crossyear.to_csv(
        QA_CROSSYEAR_OUT,
        index=False,
    )

    exposure_repro_qa.to_csv(
        QA_PREVIOUS_EXPOSURE_REPRO_OUT,
        index=False,
    )

    geometry_repro_qa.to_csv(
        QA_PREVIOUS_GEOMETRY_REPRO_OUT,
        index=False,
    )

    variation_repro_qa.to_csv(
        QA_PREVIOUS_VARIATION_REPRO_OUT,
        index=False,
    )

    crossyear_repro_qa.to_csv(
        QA_PREVIOUS_CROSSYEAR_REPRO_OUT,
        index=False,
    )

    print("=" * 72)
    print(
        "POST-2021 FROZEN 10-KM WELL EXPOSURES THROUGH 2025"
    )
    print("=" * 72)
    print("")

    print(
        "Historical geometry preserved:"
    )
    print(
        "  scipy.spatial.cKDTree"
    )
    print(
        "  query_ball_point"
    )
    print(
        "  radius = 10,000 m"
    )
    print(
        "  unweighted mean over included RiceFloodIT cell centers"
    )
    print("")

    print(
        "Geometry QA:"
    )
    print(
        geometry_summary.to_string(
            index=False
        )
    )
    print("")

    print(
        "Exposure availability and variation - all 37 ISS wells:"
    )
    print(
        variation.to_string(
            index=False
        )
    )
    print("")

    print(
        "Pairwise cross-year exposure diagnostics:"
    )
    print(
        crossyear.to_string(
            index=False
        )
    )
    print("")

    print(
        "No groundwater observation table was read."
    )
    print(
        "No groundwater depth was inspected."
    )
    print(
        "No groundwater sample selection was performed."
    )
    print(
        "No association model was fitted."
    )
    print("")

    print(
        f"Wrote: {OUT}"
    )
    print(
        f"Wrote: {QA_GEOMETRY_OUT}"
    )
    print(
        f"Wrote: {QA_VARIATION_OUT}"
    )
    print(
        f"Wrote: {QA_CROSSYEAR_OUT}"
    )
    print(
        f"Wrote: {QA_PREVIOUS_EXPOSURE_REPRO_OUT}"
    )
    print(
        f"Wrote: {QA_PREVIOUS_GEOMETRY_REPRO_OUT}"
    )
    print(
        f"Wrote: {QA_PREVIOUS_VARIATION_REPRO_OUT}"
    )
    print(
        f"Wrote: {QA_PREVIOUS_CROSSYEAR_REPRO_OUT}"
    )
    print("")
    print("DONE")


if __name__ == "__main__":
    main()

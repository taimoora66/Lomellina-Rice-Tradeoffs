"""Build frozen post-2021 10-km flooding-anomaly exposures for ISS wells.

This stage is intentionally groundwater-outcome blind.

It reproduces the spatial geometry of the historical exposure builder:

- RiceFloodIT cell centers in UTM;
- scipy.spatial.cKDTree;
- query_ball_point around each well;
- radius = exactly 10,000 m;
- unweighted arithmetic mean across cells inside the radius.

The exposure itself is already frozen before this script:

    ff_anomaly_2010_2021
        = reconstructed annual FF
        - cell-specific mean reconstructed FF over 2010-2021.

No groundwater depth values are read.
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

OUT = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2023.csv"
)

QA_GEOMETRY_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_geometry_qa.csv"
)

QA_VARIATION_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_exposure_variation_qa.csv"
)

QA_REPEAT_OUT = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_ff10_crossyear_qa.csv"
)

YEARS = (2022, 2023)
RADIUS_KM = 10
RADIUS_M = 10_000.0

EXPECTED_ISS_WELLS = 37
EXPECTED_RICE_CELLS = 4331
EXPECTED_ROWS = EXPECTED_ISS_WELLS * len(YEARS)


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

    # Only post-2021 years needed for the held-out groundwater extension.
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
    """
    Reproduce the historical exposure geometry.

    Historical script:
        pix = ff[["x","y","utm_e","utm_n"]].drop_duplicates()
        tree = cKDTree(pix[["utm_e","utm_n"]])

    Here the FF values come from the frozen reconstructed product, but
    the UTM cell-center geometry comes from the same RiceFloodIT
    georeference artifact.
    """

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

    if geom.duplicated(["x", "y"]).any():
        raise AssertionError(
            "Duplicate x/y coordinates remain in RiceFloodIT geometry."
        )

    # Verify that frozen anomaly coordinates map one-to-one to the
    # historical RiceFloodIT grid.
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

    if check["utm_e"].isna().any() or check["utm_n"].isna().any():
        raise AssertionError(
            "Some frozen anomaly cells do not map to the historical "
            "RiceFloodIT UTM geometry."
        )

    # Stable integer key analogous to the historical builder.
    geom = geom.reset_index(drop=True)
    geom["pixel_id"] = np.arange(len(geom))

    return geom


def main() -> None:
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    QA_GEOMETRY_OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    anomaly, georef, wells = read_inputs()

    pix = build_pixel_geometry(
        anomaly,
        georef,
    )

    tree = cKDTree(
        pix[
            [
                "utm_e",
                "utm_n",
            ]
        ].to_numpy()
    )

    # Attach the same stable pixel IDs to the frozen anomaly panel.
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
                "nearest_cell_distance_m": float(
                    distances.min()
                ),
                "farthest_included_cell_distance_m": float(
                    distances.max()
                ),
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

            # Exact analogue of historical ff_10:
            # unweighted mean across RiceFloodIT cells in the radius.
            ff10_anomaly = float(
                q["ff_anomaly_2010_2021"].mean()
            )

            # Retain reconstructed level only as a transparent
            # diagnostic. It is not the primary frozen exposure.
            ff10_reconstructed = float(
                q["ff_reconstructed"].mean()
            )

            ff10_baseline = float(
                q["ff_baseline_2010_2021"].mean()
            )

            # Mathematical identity check:
            # mean(cell annual - cell baseline)
            # == mean(cell annual) - mean(cell baseline)
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
        .reset_index(
            drop=True
        )
    )

    geometry = (
        pd.DataFrame(geometry_rows)
        .sort_values("station")
        .reset_index(drop=True)
    )

    if len(out) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} well-years; "
            f"found {len(out)}."
        )

    if out["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            "Unexpected number of ISS wells in exposure output."
        )

    if out["year"].nunique() != len(YEARS):
        raise AssertionError(
            "Unexpected number of years in exposure output."
        )

    missing_exposure = out["ff10_anomaly_2010_2021"].isna()

    if not (
        (out.loc[missing_exposure, "n_cells_10km"] == 0).all()
        and
        (out.loc[~missing_exposure, "n_cells_10km"] > 0).all()
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

    # Cell membership is purely geometric and must therefore not vary
    # between 2022 and 2023 for a given well.
    membership_check = (
        out.groupby("station")["n_cells_10km"]
        .nunique()
    )

    if not (
        membership_check == 1
    ).all():
        raise AssertionError(
            "10-km cell membership changes across years."
        )

    # -------------------------------------------------------------
    # Groundwater-blind exposure variation diagnostics.
    # -------------------------------------------------------------

    variation_rows = []

    for year in YEARS:
        y = out.loc[
            out["year"] == year
        ]

        x = y["ff10_anomaly_2010_2021"]

        variation_rows.append(
            {
                "year": year,
                "wells_total_n": int(
                    y["station"].nunique()
                ),
                "wells_with_ff10_n": int(
                    y["ff10_anomaly_2010_2021"].notna().sum()
                ),
                "ff10_anomaly_mean": float(
                    x.mean()
                ),
                "ff10_anomaly_sd": float(
                    x.std()
                ),
                "ff10_anomaly_min": float(
                    x.min()
                ),
                "ff10_anomaly_p25": float(
                    x.quantile(0.25)
                ),
                "ff10_anomaly_median": float(
                    x.median()
                ),
                "ff10_anomaly_p75": float(
                    x.quantile(0.75)
                ),
                "ff10_anomaly_max": float(
                    x.max()
                ),
            }
        )

    variation = pd.DataFrame(
        variation_rows
    )

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

    crossyear_delta = (
        wide[2023]
        - wide[2022]
    )

    crossyear = pd.DataFrame(
        [
            {
                "wells_total_n":
                    EXPECTED_ISS_WELLS,
                "wells_with_both_years_n":
                    int(
                        wide[[2022, 2023]]
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
                        crossyear_delta.mean()
                    ),
                "sd_change_2023_minus_2022":
                    float(
                        crossyear_delta.std()
                    ),
                "min_change_2023_minus_2022":
                    float(
                        crossyear_delta.min()
                    ),
                "max_change_2023_minus_2022":
                    float(
                        crossyear_delta.max()
                    ),
            }
        ]
    )

    geometry_summary = pd.DataFrame(
        [
            {
                "radius_km": RADIUS_KM,
                "wells_n": len(geometry),
                "wells_with_zero_cells_10km": int(
                    (geometry["cells_10km"] == 0).sum()
                ),
                "wells_with_positive_cells_10km": int(
                    (geometry["cells_10km"] > 0).sum()
                ),
                "min_cells_10km": int(
                    geometry["cells_10km"].min()
                ),
                "median_cells_10km": float(
                    geometry["cells_10km"].median()
                ),
                "mean_cells_10km": float(
                    geometry["cells_10km"].mean()
                ),
                "max_cells_10km": int(
                    geometry["cells_10km"].max()
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
        QA_REPEAT_OUT,
        index=False,
    )

    print(
        "POST-2021 FROZEN 10-KM WELL EXPOSURES COMPLETE"
    )
    print("")

    print(
        "Historical geometry reproduced:"
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
        "Exposure variation â€” all 37 ISS wells:"
    )
    print(
        variation.to_string(
            index=False
        )
    )
    print("")

    print(
        "Cross-year exposure diagnostics:"
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
        "No association model was fitted."
    )
    print("")
    print(f"Wrote: {OUT}")
    print(f"Wrote: {QA_GEOMETRY_OUT}")
    print(f"Wrote: {QA_VARIATION_OUT}")
    print(f"Wrote: {QA_REPEAT_OUT}")


if __name__ == "__main__":
    main()





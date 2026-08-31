from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =====================================================================
# Paths and frozen design
# =====================================================================

ROOT = Path(__file__).resolve().parents[2]

HIST_DIR = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
)

POST_DIR = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
)

DIAG_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

RAW_2024 = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "groundwater_pavia_2024"
    / "pavia_groundwater_quantitative_2024_update_2025-10-14.xlsx"
)

CLEAN_IN = HIST_DIR / "groundwater_clean.csv"
META_IN = HIST_DIR / "groundwater_station_metadata.csv"
HIST_ANNUAL_IN = HIST_DIR / "groundwater_annual_measures.csv"

# Frozen previous extension. This is used only as a regression-test target.
PREVIOUS_EXTENDED_IN = (
    POST_DIR
    / "groundwater_annual_measures_2008_2023.csv"
)

OUT = (
    POST_DIR
    / "groundwater_annual_measures_2008_2024.csv"
)

QA_OUT = (
    DIAG_DIR
    / "post2021_groundwater_annual_availability_2008_2024.csv"
)

HIST_REPRO_QA_OUT = (
    DIAG_DIR
    / "groundwater_annual_extension_historical_reproduction_qa.csv"
)

PRE2024_REPRO_QA_OUT = (
    DIAG_DIR
    / "groundwater_annual_extension_2008_2023_reproduction_qa.csv"
)

RAW2024_QA_OUT = (
    DIAG_DIR
    / "groundwater_2024_raw_integration_qa.csv"
)

START_YEAR = 2008
END_YEAR = 2024
HIST_END_YEAR = 2021
PREVIOUS_END_YEAR = 2023

EXPECTED_ISS_STATIONS = 37

EXPECTED_2024_RAW_ROWS = 267
EXPECTED_2024_RAW_STATIONS = 51
EXPECTED_2024_ISS_OBSERVED = 28
EXPECTED_2024_ISS_JANFEB = 16
EXPECTED_2024_ISS_AUG = 16
EXPECTED_2024_ISS_COMPLETE = 15


# =====================================================================
# Frozen annual-summary definitions
# =====================================================================

def yearly_record(g: pd.DataFrame) -> pd.Series:
    """
    Exact annual-summary definitions copied from the frozen historical
    production pipeline.

    No flooding exposure or groundwater-association model occurs here.
    """

    g = g.sort_values("date")

    janfeb = g[g["month"].isin([1, 2])]
    janmar = g[g["month"].isin([1, 2, 3])]
    aprmay = g[g["month"].isin([4, 5])]
    aug = g[g["month"] == 8]
    jja = g[g["month"].isin([6, 7, 8])]

    out = {
        "gw_obs_n": len(g),
        "gw_janfeb_n": len(janfeb),
        "gw_janfeb_mean_m": janfeb["gw_depth_m"].mean(),
        "gw_janmar_mean_m": janmar["gw_depth_m"].mean(),
        "gw_aprmay_mean_m": aprmay["gw_depth_m"].mean(),
        "gw_jja_mean_m": jja["gw_depth_m"].mean(),
        "gw_aug_n": len(aug),
        "gw_aug_mean_m": aug["gw_depth_m"].mean(),
    }

    # Strictly antecedent groundwater:
    # last valid observation in January-February.
    if len(janfeb):
        r = janfeb.iloc[-1]

        out.update(
            {
                "gw_pre_last_janfeb_m": r["gw_depth_m"],
                "gw_pre_last_janfeb_date":
                    r["date"].date().isoformat(),
                "gw_pre_last_janfeb_doy": r["doy"],
            }
        )
    else:
        out.update(
            {
                "gw_pre_last_janfeb_m": np.nan,
                "gw_pre_last_janfeb_date": None,
                "gw_pre_last_janfeb_doy": np.nan,
            }
        )

    # August timing measures.
    if len(aug):
        first = aug.iloc[0]
        last = aug.iloc[-1]

        target = pd.Timestamp(
            year=int(g["date"].dt.year.iloc[0]),
            month=8,
            day=23,
        )

        # Sorting by date before argmin preserves the historical
        # earlier-date tie rule.
        nearest = aug.iloc[
            (aug["date"] - target)
            .abs()
            .argmin()
        ]

        out.update(
            {
                "gw_aug_first_m": first["gw_depth_m"],
                "gw_aug_first_date":
                    first["date"].date().isoformat(),
                "gw_aug_first_doy": first["doy"],
                "gw_aug_last_m": last["gw_depth_m"],
                "gw_aug_last_date":
                    last["date"].date().isoformat(),
                "gw_aug_nearest_aug23_m":
                    nearest["gw_depth_m"],
                "gw_aug_nearest_aug23_date":
                    nearest["date"].date().isoformat(),
                "gw_aug_nearest_aug23_doy":
                    nearest["doy"],
            }
        )
    else:
        out.update(
            {
                "gw_aug_first_m": np.nan,
                "gw_aug_first_date": None,
                "gw_aug_first_doy": np.nan,
                "gw_aug_last_m": np.nan,
                "gw_aug_last_date": None,
                "gw_aug_nearest_aug23_m": np.nan,
                "gw_aug_nearest_aug23_date": None,
                "gw_aug_nearest_aug23_doy": np.nan,
            }
        )

    return pd.Series(out)


# =====================================================================
# Generic exact-overlap comparison
# =====================================================================

def compare_tables(
    generated: pd.DataFrame,
    frozen: pd.DataFrame,
    start_year: int,
    end_year: int,
    label: str,
) -> pd.DataFrame:
    """
    Compare every common field over an exact station-year key universe.

    Numeric values use atol=1e-12 and rtol=0.
    Non-numeric fields must match exactly after pandas NA normalization.
    """

    key = ["station", "year"]

    g = generated.loc[
        generated["year"].between(
            start_year,
            end_year,
        )
    ].copy()

    f = frozen.loc[
        frozen["year"].between(
            start_year,
            end_year,
        )
    ].copy()

    if g.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate station-year in generated table."
        )

    if f.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate station-year in frozen table."
        )

    g = (
        g.sort_values(key)
        .reset_index(drop=True)
    )

    f = (
        f.sort_values(key)
        .reset_index(drop=True)
    )

    if len(g) != len(f):
        raise AssertionError(
            f"{label}: row-count mismatch: "
            f"generated={len(g)}, frozen={len(f)}"
        )

    if not g[key].equals(f[key]):
        raise AssertionError(
            f"{label}: station-year keys do not reproduce."
        )

    common = [
        col
        for col in f.columns
        if col in g.columns
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
            a_num = pd.to_numeric(
                a,
                errors="coerce",
            )

            b_num = pd.to_numeric(
                b,
                errors="coerce",
            )

            equal = np.isclose(
                a_num.to_numpy(dtype=float),
                b_num.to_numpy(dtype=float),
                equal_nan=True,
                rtol=0,
                atol=1e-12,
            )

        else:
            a_str = (
                a.astype("string")
                .fillna("<NA>")
            )

            b_str = (
                b.astype("string")
                .fillna("<NA>")
            )

            equal = (
                a_str.to_numpy()
                == b_str.to_numpy()
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

    if len(qa) and not qa["exact_reproduction"].all():
        bad = qa.loc[
            ~qa["exact_reproduction"]
        ]

        raise AssertionError(
            f"{label} failed:\n"
            + bad.to_string(index=False)
        )

    return qa


# =====================================================================
# Load and clean authoritative 2024 workbook
# =====================================================================

def load_authoritative_2024(
    historical_station_meta: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Read the October 2025 ARPA Pavia update and convert it to the same
    observation-level schema used by groundwater_clean.csv.

    The June 2025 release is deliberately not used in production because
    the October update corrected metadata for PO0181220U0001.

    No selection uses groundwater/flooding association results.
    """

    if not RAW_2024.exists():
        raise FileNotFoundError(
            f"Authoritative 2024 workbook not found: {RAW_2024}"
        )

    raw = pd.read_excel(
        RAW_2024,
        sheet_name="2024",
    )

    expected_columns = [
        "CODICE",
        "PROVINCIA",
        "COMUNE",
        "Soggiacenza m da Qr",
        "Data",
        "ANNO",
        "X_WGS84",
        "Y_WGS84",
        "QUOTA_MISURA_m s.l.m. (Qr)",
        "PROFONDITA' m",
        "FILTRI_TOP m",
        "FILTRI_BOT m",
        "GroundWater Body (GWB_2015)",
    ]

    if list(raw.columns) != expected_columns:
        raise AssertionError(
            "Unexpected 2024 workbook schema.\n"
            f"Observed: {list(raw.columns)}"
        )

    if len(raw) != EXPECTED_2024_RAW_ROWS:
        raise AssertionError(
            "Unexpected 2024 raw row count: "
            f"{len(raw)}"
        )

    if raw["CODICE"].nunique() != EXPECTED_2024_RAW_STATIONS:
        raise AssertionError(
            "Unexpected 2024 station count: "
            f"{raw['CODICE'].nunique()}"
        )

    d = raw.rename(
        columns={
            "CODICE": "station",
            "PROVINCIA": "province",
            "COMUNE": "commune",
            "Soggiacenza m da Qr": "gw_depth_m",
            "Data": "date",
            "ANNO": "year_reported",
            "X_WGS84": "utm_e",
            "Y_WGS84": "utm_n",
            "QUOTA_MISURA_m s.l.m. (Qr)":
                "measuring_point_elev_masl",
            "PROFONDITA' m": "well_depth_m",
            "FILTRI_TOP m": "screen_top_m",
            "FILTRI_BOT m": "screen_bottom_m",
            "GroundWater Body (GWB_2015)": "gwb",
        }
    ).copy()

    d["date"] = pd.to_datetime(
        d["date"],
        errors="raise",
    )

    d["year_reported"] = pd.to_numeric(
        d["year_reported"],
        errors="raise",
    ).astype(int)

    d["year"] = d["date"].dt.year.astype(int)
    d["month"] = d["date"].dt.month.astype(int)
    d["doy"] = d["date"].dt.dayofyear.astype(int)

    if not d["year"].eq(2024).all():
        raise AssertionError(
            "2024 workbook contains observation dates outside 2024."
        )

    if not d["year_reported"].eq(2024).all():
        raise AssertionError(
            "2024 workbook contains reported years outside 2024."
        )

    if d.duplicated(["station", "date"]).any():
        bad = d.loc[
            d.duplicated(
                ["station", "date"],
                keep=False,
            )
        ].sort_values(["station", "date"])

        raise AssertionError(
            "Duplicate station-date rows in 2024 workbook:\n"
            + bad.to_string(index=False)
        )

    d["gw_depth_m"] = pd.to_numeric(
        d["gw_depth_m"],
        errors="coerce",
    )

    for col in [
        "utm_e",
        "utm_n",
        "measuring_point_elev_masl",
        "well_depth_m",
    ]:
        d[col] = pd.to_numeric(
            d[col],
            errors="coerce",
        )

    # ARPA may encode missing filter depths as "-" strings.
    # Preserve missingness rather than treating "-" as a measurement.
    for col in [
        "screen_top_m",
        "screen_bottom_m",
    ]:
        d[col] = pd.to_numeric(
            d[col],
            errors="coerce",
        )

    d["aquifer_group"] = (
        d["gwb"]
        .astype("string")
        .str.extract(
            r"\b(ISS|ISI|ISP)\b",
            expand=False,
        )
        .fillna("OTHER")
    )

    # -------------------------------------------------------------
    # Metadata continuity QA for historical ISS stations observed
    # in 2024.
    #
    # October 2025 is authoritative. We nevertheless verify that its
    # station coordinates agree with established metadata before use.
    # -------------------------------------------------------------

    hist_iss_meta = (
        historical_station_meta.loc[
            historical_station_meta[
                "aquifer_group"
            ].eq("ISS")
        ]
        .drop_duplicates("station")
        .set_index("station")
    )

    observed_iss = (
        d.loc[
            d["aquifer_group"].eq("ISS"),
            [
                "station",
                "utm_e",
                "utm_n",
            ],
        ]
        .drop_duplicates("station")
        .copy()
    )

    if len(observed_iss) != EXPECTED_2024_ISS_OBSERVED:
        raise AssertionError(
            "Unexpected number of observed ISS stations in 2024: "
            f"{len(observed_iss)}"
        )

    unknown_iss = sorted(
        set(observed_iss["station"])
        - set(hist_iss_meta.index)
    )

    if unknown_iss:
        raise AssertionError(
            "2024 contains ISS stations outside the frozen "
            "historical 37-well universe:\n"
            + "\n".join(unknown_iss)
        )

    metadata_rows = []

    for r in observed_iss.itertuples(index=False):
        h = hist_iss_meta.loc[r.station]

        east_match = bool(
            np.isclose(
                float(r.utm_e),
                float(h["utm_e"]),
                rtol=0,
                atol=1e-12,
                equal_nan=True,
            )
        )

        north_match = bool(
            np.isclose(
                float(r.utm_n),
                float(h["utm_n"]),
                rtol=0,
                atol=1e-12,
                equal_nan=True,
            )
        )

        metadata_rows.append(
            {
                "station": r.station,
                "utm_e_2024": r.utm_e,
                "utm_e_historical": h["utm_e"],
                "utm_e_match": east_match,
                "utm_n_2024": r.utm_n,
                "utm_n_historical": h["utm_n"],
                "utm_n_match": north_match,
                "coordinate_match":
                    east_match and north_match,
            }
        )

    metadata_qa = pd.DataFrame(
        metadata_rows
    )

    if not metadata_qa["coordinate_match"].all():
        bad = metadata_qa.loc[
            ~metadata_qa["coordinate_match"]
        ]

        raise AssertionError(
            "2024 authoritative coordinates disagree with "
            "historical ISS station metadata:\n"
            + bad.to_string(index=False)
        )

    # Use the historical station metadata as the canonical metadata
    # source for the frozen ISS universe. Observation-level 2024 rows
    # retain only fields needed for annual aggregation.
    keep = [
        "station",
        "province",
        "commune",
        "gw_depth_m",
        "date",
        "year_reported",
        "utm_e",
        "utm_n",
        "measuring_point_elev_masl",
        "well_depth_m",
        "screen_top_m",
        "screen_bottom_m",
        "gwb",
        "year",
        "month",
        "doy",
        "aquifer_group",
    ]

    d = d[keep].copy()

    return d, metadata_qa


# =====================================================================
# Main
# =====================================================================

def main() -> None:
    POST_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    DIAG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------
    # Historical cleaned observations through 2023
    # -------------------------------------------------------------

    clean = pd.read_csv(
        CLEAN_IN,
        parse_dates=["date"],
    )

    station_meta = pd.read_csv(
        META_IN
    )

    historical = pd.read_csv(
        HIST_ANNUAL_IN
    )

    if not PREVIOUS_EXTENDED_IN.exists():
        raise FileNotFoundError(
            "Frozen previous extension not found. "
            "Need existing 2008-2023 artifact for regression QA:\n"
            f"{PREVIOUS_EXTENDED_IN}"
        )

    previous_extended = pd.read_csv(
        PREVIOUS_EXTENDED_IN
    )

    # -------------------------------------------------------------
    # Authoritative 2024 observations
    # -------------------------------------------------------------

    raw2024, raw2024_metadata_qa = (
        load_authoritative_2024(
            station_meta
        )
    )

    # Append only the new calendar year. Never rewrite the historical
    # cleaned source artifact here.
    clean_pre2024 = clean.loc[
        clean["year"].between(
            START_YEAR,
            PREVIOUS_END_YEAR,
        )
    ].copy()

    if (clean_pre2024["year"] == 2024).any():
        raise AssertionError(
            "Historical clean input unexpectedly already contains 2024."
        )

    combined_clean = pd.concat(
        [
            clean_pre2024,
            raw2024[
                clean_pre2024.columns
            ],
        ],
        ignore_index=True,
    )

    # -------------------------------------------------------------
    # Frozen 37-well ISS station universe
    # -------------------------------------------------------------

    iss_stations = sorted(
        station_meta.loc[
            station_meta["aquifer_group"] == "ISS",
            "station",
        ]
    )

    if len(iss_stations) != EXPECTED_ISS_STATIONS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_STATIONS} ISS stations; "
            f"found {len(iss_stations)}."
        )

    iss = combined_clean.loc[
        (
            combined_clean["aquifer_group"]
            == "ISS"
        )
        & combined_clean["year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    # -------------------------------------------------------------
    # Balanced station-year skeleton
    # -------------------------------------------------------------

    grid = pd.MultiIndex.from_product(
        [
            iss_stations,
            range(
                START_YEAR,
                END_YEAR + 1,
            ),
        ],
        names=[
            "station",
            "year",
        ],
    ).to_frame(
        index=False
    )

    # -------------------------------------------------------------
    # Monthly means
    # -------------------------------------------------------------

    monthly = (
        iss.groupby(
            [
                "station",
                "year",
                "month",
            ]
        )["gw_depth_m"]
        .mean()
        .unstack("month")
        .rename(
            columns={
                m: f"gw_m{m:02d}_mean_m"
                for m in range(1, 13)
            }
        )
        .reset_index()
    )

    # Ensure all twelve monthly columns exist even if one month has
    # no observations anywhere in the full period.
    for m in range(1, 13):
        col = f"gw_m{m:02d}_mean_m"

        if col not in monthly.columns:
            monthly[col] = np.nan

    # -------------------------------------------------------------
    # Annual timing summaries
    # -------------------------------------------------------------

    annual_records = (
        iss.groupby(
            [
                "station",
                "year",
            ],
            group_keys=False,
        )
        .apply(
            yearly_record,
            include_groups=False,
        )
        .reset_index()
    )

    annual = (
        grid.merge(
            annual_records,
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
        .merge(
            monthly,
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
        .merge(
            station_meta,
            on="station",
            how="left",
            validate="many_to_one",
        )
    )

    expected_rows = (
        EXPECTED_ISS_STATIONS
        * (
            END_YEAR
            - START_YEAR
            + 1
        )
    )

    if len(annual) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} station-years; "
            f"found {len(annual)}."
        )

    # =================================================================
    # QA 1: reproduce frozen historical 2008-2021 artifact
    # =================================================================

    historical_reproduction_qa = (
        compare_tables(
            generated=annual,
            frozen=historical,
            start_year=START_YEAR,
            end_year=HIST_END_YEAR,
            label="frozen_2008_2021_historical",
        )
    )

    print(
        "Historical 2008-2021 annual-measures reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(historical_reproduction_qa),
    )
    print(
        "  mismatches: 0"
    )
    print()

    # =================================================================
    # QA 2: reproduce the complete previous 2008-2023 extension
    # =================================================================

    pre2024_reproduction_qa = (
        compare_tables(
            generated=annual,
            frozen=previous_extended,
            start_year=START_YEAR,
            end_year=PREVIOUS_END_YEAR,
            label="frozen_2008_2023_extension",
        )
    )

    print(
        "Previous 2008-2023 annual extension reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(pre2024_reproduction_qa),
    )
    print(
        "  mismatches: 0"
    )
    print()

    # =================================================================
    # QA 3: 2024 availability counts
    # =================================================================

    post = annual.loc[
        annual["year"].isin(
            [2022, 2023, 2024]
        )
    ].copy()

    post["complete_pre_plus_augmean"] = (
        post["gw_pre_last_janfeb_m"].notna()
        & post["gw_aug_mean_m"].notna()
    )

    post["complete_pre_plus_aug23"] = (
        post["gw_pre_last_janfeb_m"].notna()
        & post[
            "gw_aug_nearest_aug23_m"
        ].notna()
    )

    rows = []

    for year in [2022, 2023, 2024]:
        y = post.loc[
            post["year"] == year
        ]

        rows.append(
            {
                "year": year,
                "iss_station_universe_n":
                    EXPECTED_ISS_STATIONS,

                "stations_any_obs_n": int(
                    (
                        y["gw_obs_n"]
                        .fillna(0)
                        > 0
                    ).sum()
                ),

                "stations_janfeb_n": int(
                    y[
                        "gw_pre_last_janfeb_m"
                    ]
                    .notna()
                    .sum()
                ),

                "stations_augmean_n": int(
                    y[
                        "gw_aug_mean_m"
                    ]
                    .notna()
                    .sum()
                ),

                "stations_aug23_n": int(
                    y[
                        "gw_aug_nearest_aug23_m"
                    ]
                    .notna()
                    .sum()
                ),

                "complete_pre_plus_augmean_n":
                    int(
                        y[
                            "complete_pre_plus_augmean"
                        ].sum()
                    ),

                "complete_pre_plus_aug23_n":
                    int(
                        y[
                            "complete_pre_plus_aug23"
                        ].sum()
                    ),
            }
        )

    availability = pd.DataFrame(
        rows
    )

    # -------------------------------------------------------------
    # Hard QA against independent Stage 18 audit for 2024
    # -------------------------------------------------------------

    y2024 = availability.loc[
        availability["year"].eq(2024)
    ].iloc[0]

    observed_2024 = {
        "stations_any_obs_n":
            int(y2024["stations_any_obs_n"]),
        "stations_janfeb_n":
            int(y2024["stations_janfeb_n"]),
        "stations_augmean_n":
            int(y2024["stations_augmean_n"]),
        "complete_pre_plus_augmean_n":
            int(
                y2024[
                    "complete_pre_plus_augmean_n"
                ]
            ),
    }

    expected_2024 = {
        "stations_any_obs_n":
            EXPECTED_2024_ISS_OBSERVED,
        "stations_janfeb_n":
            EXPECTED_2024_ISS_JANFEB,
        "stations_augmean_n":
            EXPECTED_2024_ISS_AUG,
        "complete_pre_plus_augmean_n":
            EXPECTED_2024_ISS_COMPLETE,
    }

    raw2024_count_rows = []

    for metric, expected in expected_2024.items():
        observed = observed_2024[metric]

        status = (
            "PASS"
            if observed == expected
            else "FAIL"
        )

        raw2024_count_rows.append(
            {
                "check": metric,
                "expected": expected,
                "observed": observed,
                "status": status,
            }
        )

    count_qa = pd.DataFrame(
        raw2024_count_rows
    )

    if not count_qa["status"].eq("PASS").all():
        raise AssertionError(
            "2024 annual availability does not reproduce "
            "the independent Stage 18 audit:\n"
            + count_qa.to_string(index=False)
        )

    # -------------------------------------------------------------
    # Repeated completeness summary â€” counts only
    # -------------------------------------------------------------

    repeated = (
        post.loc[
            post[
                "complete_pre_plus_aug23"
            ]
        ]
        .groupby("station")["year"]
        .nunique()
        .value_counts()
        .sort_index()
        .rename_axis(
            "complete_years_per_station"
        )
        .reset_index(
            name="stations_n"
        )
    )

    if len(repeated):
        repeat_text = "; ".join(
            f"{int(r.complete_years_per_station)} year(s): "
            f"{int(r.stations_n)} station(s)"
            for r in repeated.itertuples(
                index=False
            )
        )
    else:
        repeat_text = "none"

    availability[
        "repeated_complete_aug23_distribution"
    ] = repeat_text

    # =================================================================
    # Save only after all integrity checks pass
    # =================================================================

    annual.to_csv(
        OUT,
        index=False,
    )

    historical_reproduction_qa.to_csv(
        HIST_REPRO_QA_OUT,
        index=False,
    )

    pre2024_reproduction_qa.to_csv(
        PRE2024_REPRO_QA_OUT,
        index=False,
    )

    availability.to_csv(
        QA_OUT,
        index=False,
    )

    raw2024_qa = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "check":
                            "authoritative_raw_rows",
                        "expected":
                            EXPECTED_2024_RAW_ROWS,
                        "observed":
                            EXPECTED_2024_RAW_ROWS,
                        "status": "PASS",
                    },
                    {
                        "check":
                            "authoritative_raw_stations",
                        "expected":
                            EXPECTED_2024_RAW_STATIONS,
                        "observed":
                            EXPECTED_2024_RAW_STATIONS,
                        "status": "PASS",
                    },
                    {
                        "check":
                            "observed_iss_metadata_coordinate_match",
                        "expected":
                            EXPECTED_2024_ISS_OBSERVED,
                        "observed":
                            int(
                                raw2024_metadata_qa[
                                    "coordinate_match"
                                ].sum()
                            ),
                        "status":
                            (
                                "PASS"
                                if raw2024_metadata_qa[
                                    "coordinate_match"
                                ].all()
                                else "FAIL"
                            ),
                    },
                ]
            ),
            count_qa,
        ],
        ignore_index=True,
    )

    raw2024_qa.to_csv(
        RAW2024_QA_OUT,
        index=False,
    )

    # =================================================================
    # Console output â€” availability only
    # =================================================================

    print("=" * 72)
    print(
        "POST-2021 GROUNDWATER ANNUAL EXTENSION THROUGH 2024"
    )
    print("=" * 72)
    print()

    print(
        "Authoritative 2024 source:"
    )
    print(
        RAW_2024
    )
    print()

    print(
        "2024 raw integration QA: PASS"
    )
    print(
        f"  raw rows: {EXPECTED_2024_RAW_ROWS}"
    )
    print(
        f"  raw stations: {EXPECTED_2024_RAW_STATIONS}"
    )
    print(
        f"  historical ISS observed: "
        f"{EXPECTED_2024_ISS_OBSERVED}"
    )
    print(
        "  ISS coordinate continuity: PASS"
    )
    print()

    print(
        "POST-2021 GROUNDWATER AVAILABILITY â€” COUNTS ONLY"
    )
    print(
        availability.to_string(
            index=False
        )
    )

    print()
    print(
        "No groundwater depth values were printed."
    )
    print(
        "No flooding exposure was merged."
    )
    print(
        "No association model was fitted."
    )

    print()
    print(
        f"Wrote: {OUT}"
    )
    print(
        f"Wrote: {HIST_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {PRE2024_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {QA_OUT}"
    )
    print(
        f"Wrote: {RAW2024_QA_OUT}"
    )

    print()
    print("DONE")


if __name__ == "__main__":
    main()

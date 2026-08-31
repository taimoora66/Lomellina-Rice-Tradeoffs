from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =====================================================================
# Paths and frozen design
# =====================================================================

ROOT = Path(__file__).resolve().parents[2]

HIST_DIR = ROOT / "data" / "processed" / "publication_groundwater"
POST_DIR = ROOT / "data" / "processed" / "post2021"
DIAG_DIR = ROOT / "outputs" / "diagnostics" / "post2021"

RAW_2024 = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "groundwater_pavia_2024"
    / "pavia_groundwater_quantitative_2024_update_2025-10-14.xlsx"
)

RAW_2025 = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "groundwater_2025"
    / "lombardia_groundwater_quantitative_2025.xlsx"
)

CLEAN_IN = HIST_DIR / "groundwater_clean.csv"
META_IN = HIST_DIR / "groundwater_station_metadata.csv"
HIST_ANNUAL_IN = HIST_DIR / "groundwater_annual_measures.csv"

# Frozen regression-test targets.
PRE2024_EXTENDED_IN = (
    POST_DIR
    / "groundwater_annual_measures_2008_2023.csv"
)

PREVIOUS_EXTENDED_IN = (
    POST_DIR
    / "groundwater_annual_measures_2008_2024.csv"
)

OUT = (
    POST_DIR
    / "groundwater_annual_measures_2008_2025.csv"
)

QA_OUT = (
    DIAG_DIR
    / "post2021_groundwater_annual_availability_2008_2025.csv"
)

HIST_REPRO_QA_OUT = (
    DIAG_DIR
    / "groundwater_annual_extension_historical_reproduction_qa.csv"
)

PRE2024_REPRO_QA_OUT = (
    DIAG_DIR
    / "groundwater_annual_extension_2008_2023_reproduction_qa.csv"
)

PRE2025_REPRO_QA_OUT = (
    DIAG_DIR
    / "groundwater_annual_extension_2008_2024_reproduction_qa.csv"
)

RAW2024_QA_OUT = (
    DIAG_DIR
    / "groundwater_2024_raw_integration_qa.csv"
)

RAW2025_QA_OUT = (
    DIAG_DIR
    / "groundwater_2025_raw_integration_qa.csv"
)

START_YEAR = 2008
HIST_END_YEAR = 2021
PRE2024_END_YEAR = 2023
PREVIOUS_END_YEAR = 2024
END_YEAR = 2025

EXPECTED_ISS_STATIONS = 37

# 2024 independently frozen expectations.
EXPECTED_2024_RAW_ROWS = 267
EXPECTED_2024_RAW_STATIONS = 51
EXPECTED_2024_ISS_OBSERVED = 28
EXPECTED_2024_ISS_JANFEB = 16
EXPECTED_2024_ISS_AUG = 16
EXPECTED_2024_ISS_COMPLETE = 15

# 2025 independently frozen expectations from Stage 20.
EXPECTED_2025_RAW_ROWS = 2294
EXPECTED_2025_RAW_STATIONS = 290
EXPECTED_2025_ROWS_AFTER_DUPLICATE_CLEANING = 2285
EXPECTED_2025_DUPLICATE_GROUPS = 6
EXPECTED_2025_CONFLICTING_GROUPS = 3
EXPECTED_2025_PAVIA_CONFLICTING_GROUPS = 0
EXPECTED_2025_PAVIA_ROWS = 276
EXPECTED_2025_PAVIA_STATIONS = 48
EXPECTED_2025_PAVIA_ISS_ROWS = 186
EXPECTED_2025_ISS_OBSERVED = 26
EXPECTED_2025_ISS_JANFEB = 18
EXPECTED_2025_ISS_AUG = 17
EXPECTED_2025_ISS_COMPLETE = 17

# 2025 UTM coordinates are published to 0.01 m. Historical metadata
# preserve extra decimals. This is a source-precision tolerance, not a
# substantive relocation tolerance.
COORDINATE_2025_ATOL_M = 0.01


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

    # Strictly antecedent groundwater: last valid observation in Jan-Feb.
    if len(janfeb):
        r = janfeb.iloc[-1]
        out.update(
            {
                "gw_pre_last_janfeb_m": r["gw_depth_m"],
                "gw_pre_last_janfeb_date": r["date"].date().isoformat(),
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

        # Sorting by date before argmin preserves historical earlier-date tie rule.
        nearest = aug.iloc[
            (aug["date"] - target)
            .abs()
            .argmin()
        ]

        out.update(
            {
                "gw_aug_first_m": first["gw_depth_m"],
                "gw_aug_first_date": first["date"].date().isoformat(),
                "gw_aug_first_doy": first["doy"],
                "gw_aug_last_m": last["gw_depth_m"],
                "gw_aug_last_date": last["date"].date().isoformat(),
                "gw_aug_nearest_aug23_m": nearest["gw_depth_m"],
                "gw_aug_nearest_aug23_date":
                    nearest["date"].date().isoformat(),
                "gw_aug_nearest_aug23_doy": nearest["doy"],
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
        generated["year"].between(start_year, end_year)
    ].copy()

    f = frozen.loc[
        frozen["year"].between(start_year, end_year)
    ].copy()

    if g.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate station-year in generated table."
        )

    if f.duplicated(key).any():
        raise AssertionError(
            f"{label}: duplicate station-year in frozen table."
        )

    g = g.sort_values(key).reset_index(drop=True)
    f = f.sort_values(key).reset_index(drop=True)

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
            a_num = pd.to_numeric(a, errors="coerce")
            b_num = pd.to_numeric(b, errors="coerce")

            equal = np.isclose(
                a_num.to_numpy(dtype=float),
                b_num.to_numpy(dtype=float),
                equal_nan=True,
                rtol=0,
                atol=1e-12,
            )
        else:
            a_str = a.astype("string").fillna("<NA>")
            b_str = b.astype("string").fillna("<NA>")

            equal = (
                a_str.to_numpy()
                == b_str.to_numpy()
            )

        mismatch_n = int((~equal).sum())

        rows.append(
            {
                "comparison": label,
                "column": col,
                "rows_compared": len(equal),
                "mismatch_n": mismatch_n,
                "exact_reproduction": mismatch_n == 0,
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
# Common source helpers
# =====================================================================

def classify_aquifer(gwb: pd.Series) -> pd.Series:
    return (
        gwb.astype("string")
        .str.extract(
            r"\b(ISS|ISI|ISP)\b",
            expand=False,
        )
        .fillna("OTHER")
    )


def historical_iss_metadata(
    station_meta: pd.DataFrame,
) -> pd.DataFrame:
    hist = (
        station_meta.loc[
            station_meta["aquifer_group"].eq("ISS")
        ]
        .drop_duplicates("station")
        .set_index("station")
    )

    if len(hist) != EXPECTED_ISS_STATIONS:
        raise AssertionError(
            "Historical station metadata does not contain "
            f"the frozen {EXPECTED_ISS_STATIONS}-well ISS universe."
        )

    return hist


# =====================================================================
# Load authoritative 2024 workbook
# =====================================================================

def load_authoritative_2024(
    historical_station_meta: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """
    Read the October 2025 ARPA Pavia update and convert it to the same
    observation-level schema used by groundwater_clean.csv.

    The June 2025 release is deliberately not used in production because
    the October update corrected metadata for PO0181220U0001.
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

    raw_rows = len(raw)
    raw_stations = int(raw["CODICE"].nunique())

    if raw_rows != EXPECTED_2024_RAW_ROWS:
        raise AssertionError(
            "Unexpected 2024 raw row count: "
            f"{raw_rows}"
        )

    if raw_stations != EXPECTED_2024_RAW_STATIONS:
        raise AssertionError(
            "Unexpected 2024 station count: "
            f"{raw_stations}"
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
        "screen_top_m",
        "screen_bottom_m",
    ]:
        d[col] = pd.to_numeric(
            d[col],
            errors="coerce",
        )

    d["aquifer_group"] = classify_aquifer(
        d["gwb"]
    )

    hist_iss_meta = historical_iss_metadata(
        historical_station_meta
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
                "delta_utm_e_m":
                    float(r.utm_e) - float(h["utm_e"]),
                "utm_e_match": east_match,
                "utm_n_2024": r.utm_n,
                "utm_n_historical": h["utm_n"],
                "delta_utm_n_m":
                    float(r.utm_n) - float(h["utm_n"]),
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

    stats = {
        "raw_rows": raw_rows,
        "raw_stations": raw_stations,
        "iss_observed": len(observed_iss),
    }

    return d, metadata_qa, stats


# =====================================================================
# Load and clean authoritative 2025 workbook
# =====================================================================

def load_authoritative_2025(
    historical_station_meta: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, int],
]:
    """
    Read the open Lombardia 2025 workbook, audit regional duplicate
    station-date groups, apply the frozen duplicate rule, retain Pavia,
    and verify continuity with the frozen historical ISS universe.

    Frozen duplicate rule:
    - exact duplicate rows are collapsed;
    - conflicting same-station/same-date groundwater groups are excluded;
    - conflicting groundwater values are never averaged.

    The three conflicting regional groups are outside Pavia.
    """

    if not RAW_2025.exists():
        raise FileNotFoundError(
            f"Authoritative 2025 workbook not found: {RAW_2025}"
        )

    raw = pd.read_excel(
        RAW_2025,
        sheet_name="2025",
        header=4,
    )

    expected_columns = [
        "CODICE",
        "PROVINCIA",
        "COMUNE",
        "Soggiacenza\nm da Qr",
        "Data",
        "ANNO",
        "X_WGS84/UTM32",
        "Y_WGS84/UTM322",
        "Quota di riferimento (Qr)\nm s.l.m.",
        "PROFONDITA'\nm",
        "FILTRI_TOP\nm",
        "FILTRI_BOT\nm",
        "GroundWater Body\n(GWB_2015)",
    ]

    if list(raw.columns) != expected_columns:
        raise AssertionError(
            "Unexpected 2025 workbook schema.\n"
            f"Observed: {list(raw.columns)}"
        )

    raw_rows = len(raw)
    raw_stations = int(raw["CODICE"].nunique())

    if raw_rows != EXPECTED_2025_RAW_ROWS:
        raise AssertionError(
            "Unexpected 2025 raw row count: "
            f"{raw_rows} != {EXPECTED_2025_RAW_ROWS}"
        )

    if raw_stations != EXPECTED_2025_RAW_STATIONS:
        raise AssertionError(
            "Unexpected 2025 raw station count: "
            f"{raw_stations} != {EXPECTED_2025_RAW_STATIONS}"
        )

    d = raw.rename(
        columns={
            "CODICE": "station",
            "PROVINCIA": "province",
            "COMUNE": "commune",
            "Soggiacenza\nm da Qr": "gw_depth_m",
            "Data": "date",
            "ANNO": "year_reported_raw",
            "X_WGS84/UTM32": "utm_e",
            "Y_WGS84/UTM322": "utm_n",
            "Quota di riferimento (Qr)\nm s.l.m.":
                "measuring_point_elev_masl",
            "PROFONDITA'\nm": "well_depth_m",
            "FILTRI_TOP\nm": "screen_top_m",
            "FILTRI_BOT\nm": "screen_bottom_m",
            "GroundWater Body\n(GWB_2015)": "gwb",
        }
    ).copy()

    d["date"] = pd.to_datetime(
        d["date"],
        errors="raise",
    )

    d["year"] = d["date"].dt.year.astype(int)
    d["month"] = d["date"].dt.month.astype(int)
    d["doy"] = d["date"].dt.dayofyear.astype(int)

    if not d["year"].eq(2025).all():
        raise AssertionError(
            "2025 workbook contains observation dates outside 2025."
        )

    # ARPA's 2025 ANNO field may be represented as either year-like or
    # date-like values. It is redundant with Data, so verify that any
    # interpretable value points to 2025 and then normalize to integer 2025.
    reported_raw = d["year_reported_raw"]

    reported_num = pd.to_numeric(
        reported_raw,
        errors="coerce",
    )

    reported_date = pd.to_datetime(
        reported_raw,
        errors="coerce",
    )

    valid_reported = (
        reported_num.eq(2025)
        | reported_date.dt.year.eq(2025)
    )

    if not valid_reported.all():
        bad = d.loc[
            ~valid_reported,
            [
                "station",
                "date",
                "year_reported_raw",
            ],
        ]

        raise AssertionError(
            "2025 workbook contains ANNO values inconsistent with 2025:\n"
            + bad.to_string(index=False)
        )

    d["year_reported"] = 2025

    d["gw_depth_m"] = pd.to_numeric(
        d["gw_depth_m"],
        errors="coerce",
    )

    for col in [
        "utm_e",
        "utm_n",
        "measuring_point_elev_masl",
        "well_depth_m",
        "screen_top_m",
        "screen_bottom_m",
    ]:
        d[col] = pd.to_numeric(
            d[col],
            errors="coerce",
        )

    d["aquifer_group"] = classify_aquifer(
        d["gwb"]
    )

    # -----------------------------------------------------------------
    # Regional duplicate station-date audit
    # -----------------------------------------------------------------

    key = [
        "station",
        "date",
    ]

    dup = d.loc[
        d.duplicated(
            key,
            keep=False,
        )
    ].copy()

    duplicate_rows = []
    conflict_keys = []

    if len(dup):
        for (
            station,
            date,
        ), g in dup.groupby(
            key,
            sort=True,
        ):
            gw_values = sorted(
                float(x)
                for x in (
                    pd.to_numeric(
                        g["gw_depth_m"],
                        errors="coerce",
                    )
                    .dropna()
                    .unique()
                )
            )

            conflict = len(gw_values) > 1

            provinces = sorted(
                g["province"]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )

            pavia_group = (
                "PV"
                in {
                    x.upper()
                    for x in provinces
                }
            )

            duplicate_rows.append(
                {
                    "station": station,
                    "date": date,
                    "province": ";".join(provinces),
                    "rows_n": len(g),
                    "unique_gw_values_n": len(gw_values),
                    "gw_values":
                        ";".join(str(x) for x in gw_values),
                    "exact_duplicate_group": not conflict,
                    "conflicting_gw_group": conflict,
                    "pavia_group": pavia_group,
                }
            )

            if conflict:
                conflict_keys.append(
                    (
                        station,
                        date,
                    )
                )

    duplicate_qa = pd.DataFrame(
        duplicate_rows
    )

    if len(duplicate_qa):
        duplicate_qa = (
            duplicate_qa
            .sort_values(
                [
                    "province",
                    "station",
                    "date",
                ]
            )
            .reset_index(drop=True)
        )

    duplicate_groups_n = len(duplicate_qa)

    conflicting_groups_n = (
        int(
            duplicate_qa[
                "conflicting_gw_group"
            ].sum()
        )
        if len(duplicate_qa)
        else 0
    )

    pavia_conflicting_groups_n = (
        int(
            (
                duplicate_qa[
                    "conflicting_gw_group"
                ]
                & duplicate_qa[
                    "pavia_group"
                ]
            ).sum()
        )
        if len(duplicate_qa)
        else 0
    )

    if duplicate_groups_n != EXPECTED_2025_DUPLICATE_GROUPS:
        raise AssertionError(
            "Unexpected 2025 duplicate station-date groups: "
            f"{duplicate_groups_n} != "
            f"{EXPECTED_2025_DUPLICATE_GROUPS}"
        )

    if conflicting_groups_n != EXPECTED_2025_CONFLICTING_GROUPS:
        raise AssertionError(
            "Unexpected 2025 conflicting station-date groups: "
            f"{conflicting_groups_n} != "
            f"{EXPECTED_2025_CONFLICTING_GROUPS}"
        )

    if (
        pavia_conflicting_groups_n
        != EXPECTED_2025_PAVIA_CONFLICTING_GROUPS
    ):
        raise AssertionError(
            "Unexpected 2025 Pavia conflicting station-date groups: "
            f"{pavia_conflicting_groups_n} != "
            f"{EXPECTED_2025_PAVIA_CONFLICTING_GROUPS}"
        )

    # Collapse exact repeated rows.
    d = d.drop_duplicates().copy()

    # Exclude complete conflicting station-date groups.
    if conflict_keys:
        conflict_index = pd.MultiIndex.from_tuples(
            conflict_keys,
            names=key,
        )

        row_index = pd.MultiIndex.from_frame(
            d[key]
        )

        d = d.loc[
            ~row_index.isin(conflict_index)
        ].copy()

    if d.duplicated(key).any():
        bad = d.loc[
            d.duplicated(
                key,
                keep=False,
            )
        ]

        raise AssertionError(
            "2025 duplicate station-date rows remain after cleaning:\n"
            + bad.to_string(index=False)
        )

    rows_after_cleaning = len(d)

    if (
        rows_after_cleaning
        != EXPECTED_2025_ROWS_AFTER_DUPLICATE_CLEANING
    ):
        raise AssertionError(
            "Unexpected 2025 row count after duplicate cleaning: "
            f"{rows_after_cleaning} != "
            f"{EXPECTED_2025_ROWS_AFTER_DUPLICATE_CLEANING}"
        )

    # -----------------------------------------------------------------
    # Pavia subset
    # -----------------------------------------------------------------

    pv = d.loc[
        d["province"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("PV")
    ].copy()

    pavia_rows = len(pv)
    pavia_stations = int(
        pv["station"].nunique()
    )

    if pavia_rows != EXPECTED_2025_PAVIA_ROWS:
        raise AssertionError(
            "Unexpected 2025 Pavia row count: "
            f"{pavia_rows} != {EXPECTED_2025_PAVIA_ROWS}"
        )

    if pavia_stations != EXPECTED_2025_PAVIA_STATIONS:
        raise AssertionError(
            "Unexpected 2025 Pavia station count: "
            f"{pavia_stations} != "
            f"{EXPECTED_2025_PAVIA_STATIONS}"
        )

    # -----------------------------------------------------------------
    # Historical ISS metadata continuity
    # -----------------------------------------------------------------

    hist_iss_meta = historical_iss_metadata(
        historical_station_meta
    )

    pavia_iss = pv.loc[
        pv["aquifer_group"].eq("ISS")
    ].copy()

    pavia_iss_rows = len(pavia_iss)

    observed_iss = (
        pavia_iss[
            [
                "station",
                "utm_e",
                "utm_n",
            ]
        ]
        .drop_duplicates("station")
        .copy()
    )

    if pavia_iss_rows != EXPECTED_2025_PAVIA_ISS_ROWS:
        raise AssertionError(
            "Unexpected 2025 Pavia ISS row count: "
            f"{pavia_iss_rows} != "
            f"{EXPECTED_2025_PAVIA_ISS_ROWS}"
        )

    if len(observed_iss) != EXPECTED_2025_ISS_OBSERVED:
        raise AssertionError(
            "Unexpected 2025 Pavia ISS station count: "
            f"{len(observed_iss)} != "
            f"{EXPECTED_2025_ISS_OBSERVED}"
        )

    unknown_iss = sorted(
        set(observed_iss["station"])
        - set(hist_iss_meta.index)
    )

    if unknown_iss:
        raise AssertionError(
            "2025 contains Pavia ISS stations outside the frozen "
            "historical 37-well universe:\n"
            + "\n".join(unknown_iss)
        )

    # Verify internally constant station coordinates before comparison.
    for station, g in pavia_iss.groupby(
        "station",
        sort=True,
    ):
        for col in [
            "utm_e",
            "utm_n",
        ]:
            values = (
                pd.to_numeric(
                    g[col],
                    errors="coerce",
                )
                .dropna()
                .unique()
            )

            if len(values) > 1:
                raise AssertionError(
                    "2025 Pavia ISS coordinates vary within station "
                    f"{station} for {col}: {list(values)}"
                )

    metadata_rows = []

    for r in observed_iss.itertuples(index=False):
        h = hist_iss_meta.loc[r.station]

        delta_e = (
            float(r.utm_e)
            - float(h["utm_e"])
        )

        delta_n = (
            float(r.utm_n)
            - float(h["utm_n"])
        )

        east_match = bool(
            np.isclose(
                float(r.utm_e),
                float(h["utm_e"]),
                rtol=0,
                atol=COORDINATE_2025_ATOL_M,
                equal_nan=True,
            )
        )

        north_match = bool(
            np.isclose(
                float(r.utm_n),
                float(h["utm_n"]),
                rtol=0,
                atol=COORDINATE_2025_ATOL_M,
                equal_nan=True,
            )
        )

        metadata_rows.append(
            {
                "station": r.station,
                "utm_e_2025": r.utm_e,
                "utm_e_historical": h["utm_e"],
                "delta_utm_e_m": delta_e,
                "utm_e_match": east_match,
                "utm_n_2025": r.utm_n,
                "utm_n_historical": h["utm_n"],
                "delta_utm_n_m": delta_n,
                "utm_n_match": north_match,
                "coordinate_delta_max_abs_m":
                    max(abs(delta_e), abs(delta_n)),
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
            "2025 Pavia ISS coordinates exceed the 0.01 m "
            "source-precision tolerance:\n"
            + bad.to_string(index=False)
        )

    # Normalize to the historical observation-level schema.
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

    pv = pv[keep].copy()

    stats = {
        "raw_rows": raw_rows,
        "raw_stations": raw_stations,
        "rows_after_duplicate_cleaning": rows_after_cleaning,
        "duplicate_groups": duplicate_groups_n,
        "conflicting_groups": conflicting_groups_n,
        "pavia_conflicting_groups": pavia_conflicting_groups_n,
        "pavia_rows": pavia_rows,
        "pavia_stations": pavia_stations,
        "pavia_iss_rows": pavia_iss_rows,
        "iss_observed": len(observed_iss),
    }

    return (
        pv,
        metadata_qa,
        duplicate_qa,
        stats,
    )


# =====================================================================
# Availability helpers
# =====================================================================

def build_availability(
    annual: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    post = annual.loc[
        annual["year"].isin(
            [
                2022,
                2023,
                2024,
                2025,
            ]
        )
    ].copy()

    post["complete_pre_plus_augmean"] = (
        post["gw_pre_last_janfeb_m"].notna()
        & post["gw_aug_mean_m"].notna()
    )

    post["complete_pre_plus_aug23"] = (
        post["gw_pre_last_janfeb_m"].notna()
        & post["gw_aug_nearest_aug23_m"].notna()
    )

    rows = []

    for year in [
        2022,
        2023,
        2024,
        2025,
    ]:
        y = post.loc[
            post["year"].eq(year)
        ]

        rows.append(
            {
                "year": year,
                "iss_station_universe_n":
                    EXPECTED_ISS_STATIONS,
                "stations_any_obs_n":
                    int(
                        (
                            y["gw_obs_n"]
                            .fillna(0)
                            > 0
                        ).sum()
                    ),
                "stations_janfeb_n":
                    int(
                        y[
                            "gw_pre_last_janfeb_m"
                        ]
                        .notna()
                        .sum()
                    ),
                "stations_augmean_n":
                    int(
                        y[
                            "gw_aug_mean_m"
                        ]
                        .notna()
                        .sum()
                    ),
                "stations_aug23_n":
                    int(
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

    return availability, post


def availability_count_qa(
    availability: pd.DataFrame,
    year: int,
    expected: dict[str, int],
) -> pd.DataFrame:
    y = availability.loc[
        availability["year"].eq(year)
    ]

    if len(y) != 1:
        raise AssertionError(
            f"Expected exactly one availability row for {year}."
        )

    y = y.iloc[0]

    rows = []

    for metric, expected_value in expected.items():
        observed = int(
            y[metric]
        )

        rows.append(
            {
                "check": metric,
                "expected": expected_value,
                "observed": observed,
                "status":
                    "PASS"
                    if observed == expected_value
                    else "FAIL",
            }
        )

    qa = pd.DataFrame(
        rows
    )

    if not qa["status"].eq("PASS").all():
        raise AssertionError(
            f"{year} annual availability does not reproduce "
            "the independent source audit:\n"
            + qa.to_string(index=False)
        )

    return qa


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

    # -----------------------------------------------------------------
    # Historical cleaned observations through 2023
    # -----------------------------------------------------------------

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

    if not PRE2024_EXTENDED_IN.exists():
        raise FileNotFoundError(
            "Frozen 2008-2023 extension not found for regression QA:\n"
            f"{PRE2024_EXTENDED_IN}"
        )

    pre2024_extended = pd.read_csv(
        PRE2024_EXTENDED_IN
    )

    if not PREVIOUS_EXTENDED_IN.exists():
        raise FileNotFoundError(
            "Frozen 2008-2024 extension not found for regression QA:\n"
            f"{PREVIOUS_EXTENDED_IN}"
        )

    previous_extended = pd.read_csv(
        PREVIOUS_EXTENDED_IN
    )

    # -----------------------------------------------------------------
    # Authoritative 2024 and 2025 observations
    # -----------------------------------------------------------------

    (
        raw2024,
        raw2024_metadata_qa,
        raw2024_stats,
    ) = load_authoritative_2024(
        station_meta
    )

    (
        raw2025,
        raw2025_metadata_qa,
        raw2025_duplicate_qa,
        raw2025_stats,
    ) = load_authoritative_2025(
        station_meta
    )

    # -----------------------------------------------------------------
    # Append only 2024 and 2025 to the frozen pre-2024 cleaned source.
    # -----------------------------------------------------------------

    clean_pre2024 = clean.loc[
        clean["year"].between(
            START_YEAR,
            PRE2024_END_YEAR,
        )
    ].copy()

    if clean["year"].ge(2024).any():
        # Historical clean may contain post-2023 rows from the original
        # workbook, but they are deliberately not used here. Production
        # 2024/2025 observations come only from the audited open releases.
        pass

    expected_observation_columns = list(
        clean_pre2024.columns
    )

    for label, frame in [
        (
            "2024",
            raw2024,
        ),
        (
            "2025",
            raw2025,
        ),
    ]:
        missing = sorted(
            set(expected_observation_columns)
            - set(frame.columns)
        )

        if missing:
            raise AssertionError(
                f"{label} source is missing historical clean columns:\n"
                + "\n".join(missing)
            )

    combined_clean = pd.concat(
        [
            clean_pre2024,
            raw2024[
                expected_observation_columns
            ],
            raw2025[
                expected_observation_columns
            ],
        ],
        ignore_index=True,
    )

    if combined_clean.duplicated(
        [
            "station",
            "date",
        ]
    ).any():
        bad = combined_clean.loc[
            combined_clean.duplicated(
                [
                    "station",
                    "date",
                ],
                keep=False,
            )
        ]

        raise AssertionError(
            "Duplicate station-date rows remain in combined "
            "2008-2025 observation source:\n"
            + bad.to_string(index=False)
        )

    # -----------------------------------------------------------------
    # Frozen 37-well ISS station universe
    # -----------------------------------------------------------------

    iss_stations = sorted(
        station_meta.loc[
            station_meta[
                "aquifer_group"
            ].eq("ISS"),
            "station",
        ]
        .dropna()
        .unique()
        .tolist()
    )

    if len(iss_stations) != EXPECTED_ISS_STATIONS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_STATIONS} ISS stations; "
            f"found {len(iss_stations)}."
        )

    iss = combined_clean.loc[
        combined_clean[
            "aquifer_group"
        ].eq("ISS")
        & combined_clean[
            "year"
        ].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    # -----------------------------------------------------------------
    # Balanced station-year skeleton
    # -----------------------------------------------------------------

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

    # -----------------------------------------------------------------
    # Monthly means
    # -----------------------------------------------------------------

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

    for m in range(1, 13):
        col = f"gw_m{m:02d}_mean_m"

        if col not in monthly.columns:
            monthly[col] = np.nan

    # -----------------------------------------------------------------
    # Annual timing summaries
    # -----------------------------------------------------------------

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
    # QA 1: frozen historical 2008-2021 reproduction
    # =================================================================

    historical_reproduction_qa = compare_tables(
        generated=annual,
        frozen=historical,
        start_year=START_YEAR,
        end_year=HIST_END_YEAR,
        label="frozen_2008_2021_historical",
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
    # QA 2: frozen 2008-2023 extension reproduction
    # =================================================================

    pre2024_reproduction_qa = compare_tables(
        generated=annual,
        frozen=pre2024_extended,
        start_year=START_YEAR,
        end_year=PRE2024_END_YEAR,
        label="frozen_2008_2023_extension",
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
    # QA 3: complete frozen 2008-2024 extension reproduction
    # =================================================================

    pre2025_reproduction_qa = compare_tables(
        generated=annual,
        frozen=previous_extended,
        start_year=START_YEAR,
        end_year=PREVIOUS_END_YEAR,
        label="frozen_2008_2024_extension",
    )

    print(
        "Previous 2008-2024 annual extension reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(pre2025_reproduction_qa),
    )
    print(
        "  mismatches: 0"
    )
    print()

    # =================================================================
    # QA 4: post-2021 annual availability
    # =================================================================

    availability, post = build_availability(
        annual
    )

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

    count_qa_2024 = availability_count_qa(
        availability,
        2024,
        expected_2024,
    )

    expected_2025 = {
        "stations_any_obs_n":
            EXPECTED_2025_ISS_OBSERVED,
        "stations_janfeb_n":
            EXPECTED_2025_ISS_JANFEB,
        "stations_augmean_n":
            EXPECTED_2025_ISS_AUG,
        "complete_pre_plus_augmean_n":
            EXPECTED_2025_ISS_COMPLETE,
    }

    count_qa_2025 = availability_count_qa(
        availability,
        2025,
        expected_2025,
    )

    # =================================================================
    # Save only after all integrity checks pass
    # =================================================================

    annual.to_csv(
        OUT,
        index=False,
    )

    historical_reproduction_qa.drop(
        columns=["comparison"],
    ).to_csv(
        HIST_REPRO_QA_OUT,
        index=False,
    )

    pre2024_reproduction_qa.to_csv(
        PRE2024_REPRO_QA_OUT,
        index=False,
    )

    pre2025_reproduction_qa.to_csv(
        PRE2025_REPRO_QA_OUT,
        index=False,
    )

    availability.to_csv(
        QA_OUT,
        index=False,
    )

    # -----------------------------------------------------------------
    # 2024 raw integration QA — actual observed values, not constants.
    # -----------------------------------------------------------------

    raw2024_qa = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "check": "authoritative_raw_rows",
                        "expected": EXPECTED_2024_RAW_ROWS,
                        "observed": raw2024_stats["raw_rows"],
                        "status":
                            "PASS"
                            if raw2024_stats["raw_rows"]
                            == EXPECTED_2024_RAW_ROWS
                            else "FAIL",
                    },
                    {
                        "check": "authoritative_raw_stations",
                        "expected": EXPECTED_2024_RAW_STATIONS,
                        "observed": raw2024_stats["raw_stations"],
                        "status":
                            "PASS"
                            if raw2024_stats["raw_stations"]
                            == EXPECTED_2024_RAW_STATIONS
                            else "FAIL",
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
                            "PASS"
                            if raw2024_metadata_qa[
                                "coordinate_match"
                            ].all()
                            else "FAIL",
                    },
                ]
            ),
            count_qa_2024,
        ],
        ignore_index=True,
    )

    if not raw2024_qa["status"].eq("PASS").all():
        raise AssertionError(
            "2024 raw integration QA failed:\n"
            + raw2024_qa.to_string(index=False)
        )

    raw2024_qa.to_csv(
        RAW2024_QA_OUT,
        index=False,
    )

    # -----------------------------------------------------------------
    # 2025 raw integration QA
    # -----------------------------------------------------------------

    max_coord_delta_2025 = float(
        raw2025_metadata_qa[
            "coordinate_delta_max_abs_m"
        ].max()
    )

    raw2025_checks = [
        (
            "authoritative_raw_rows",
            EXPECTED_2025_RAW_ROWS,
            raw2025_stats["raw_rows"],
        ),
        (
            "authoritative_raw_stations",
            EXPECTED_2025_RAW_STATIONS,
            raw2025_stats["raw_stations"],
        ),
        (
            "rows_after_duplicate_cleaning",
            EXPECTED_2025_ROWS_AFTER_DUPLICATE_CLEANING,
            raw2025_stats[
                "rows_after_duplicate_cleaning"
            ],
        ),
        (
            "duplicate_station_date_groups",
            EXPECTED_2025_DUPLICATE_GROUPS,
            raw2025_stats["duplicate_groups"],
        ),
        (
            "conflicting_duplicate_groups",
            EXPECTED_2025_CONFLICTING_GROUPS,
            raw2025_stats["conflicting_groups"],
        ),
        (
            "pavia_conflicting_duplicate_groups",
            EXPECTED_2025_PAVIA_CONFLICTING_GROUPS,
            raw2025_stats["pavia_conflicting_groups"],
        ),
        (
            "pavia_rows",
            EXPECTED_2025_PAVIA_ROWS,
            raw2025_stats["pavia_rows"],
        ),
        (
            "pavia_stations",
            EXPECTED_2025_PAVIA_STATIONS,
            raw2025_stats["pavia_stations"],
        ),
        (
            "pavia_iss_rows",
            EXPECTED_2025_PAVIA_ISS_ROWS,
            raw2025_stats["pavia_iss_rows"],
        ),
        (
            "historical_iss_stations_present",
            EXPECTED_2025_ISS_OBSERVED,
            raw2025_stats["iss_observed"],
        ),
        (
            "observed_iss_metadata_coordinate_match",
            EXPECTED_2025_ISS_OBSERVED,
            int(
                raw2025_metadata_qa[
                    "coordinate_match"
                ].sum()
            ),
        ),
    ]

    raw2025_count_rows = []

    for (
        check,
        expected,
        observed,
    ) in raw2025_checks:
        raw2025_count_rows.append(
            {
                "check": check,
                "expected": expected,
                "observed": observed,
                "status":
                    "PASS"
                    if observed == expected
                    else "FAIL",
            }
        )

    raw2025_qa = pd.concat(
        [
            pd.DataFrame(
                raw2025_count_rows
            ),
            count_qa_2025,
            pd.DataFrame(
                [
                    {
                        "check":
                            "max_coordinate_delta_within_0_01_m",
                        "expected":
                            COORDINATE_2025_ATOL_M,
                        "observed":
                            max_coord_delta_2025,
                        "status":
                            "PASS"
                            if (
                                max_coord_delta_2025
                                <= COORDINATE_2025_ATOL_M
                            )
                            else "FAIL",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    if not raw2025_qa[
        "status"
    ].eq("PASS").all():
        raise AssertionError(
            "2025 raw integration QA failed:\n"
            + raw2025_qa.to_string(index=False)
        )

    raw2025_qa.to_csv(
        RAW2025_QA_OUT,
        index=False,
    )

    # =================================================================
    # Console output — availability only
    # =================================================================

    print("=" * 72)
    print(
        "POST-2021 GROUNDWATER ANNUAL EXTENSION THROUGH 2025"
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
        f"  raw rows: {raw2024_stats['raw_rows']}"
    )
    print(
        f"  raw stations: {raw2024_stats['raw_stations']}"
    )
    print(
        "  historical ISS observed: "
        f"{raw2024_stats['iss_observed']}"
    )
    print(
        "  ISS coordinate continuity: PASS"
    )
    print()

    print(
        "Authoritative 2025 source:"
    )
    print(
        RAW_2025
    )
    print()

    print(
        "2025 raw integration QA: PASS"
    )
    print(
        f"  raw rows: {raw2025_stats['raw_rows']}"
    )
    print(
        f"  raw stations: {raw2025_stats['raw_stations']}"
    )
    print(
        "  duplicate station-date groups: "
        f"{raw2025_stats['duplicate_groups']}"
    )
    print(
        "  conflicting duplicate groups: "
        f"{raw2025_stats['conflicting_groups']}"
    )
    print(
        "  Pavia conflicting duplicate groups: "
        f"{raw2025_stats['pavia_conflicting_groups']}"
    )
    print(
        "  historical Pavia ISS observed: "
        f"{raw2025_stats['iss_observed']}"
    )
    print(
        "  ISS coordinate continuity: "
        "PASS AFTER SOURCE-PRECISION ROUNDING"
    )
    print(
        "  max coordinate delta (m): "
        f"{max_coord_delta_2025}"
    )
    print()

    print(
        "POST-2021 GROUNDWATER AVAILABILITY — COUNTS ONLY"
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
        f"Wrote: {PRE2025_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {QA_OUT}"
    )
    print(
        f"Wrote: {RAW2024_QA_OUT}"
    )
    print(
        f"Wrote: {RAW2025_QA_OUT}"
    )

    print()
    print("DONE")


if __name__ == "__main__":
    main()


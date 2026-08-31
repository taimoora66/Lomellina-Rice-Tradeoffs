from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =====================================================================
# Paths
# =====================================================================

ROOT = Path(__file__).resolve().parents[2]

RAW_2025 = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "groundwater_2025"
    / "lombardia_groundwater_quantitative_2025.xlsx"
)

HIST_CLEAN = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "groundwater_clean.csv"
)

OUTDIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True,
)

STATION_OUT = (
    OUTDIR
    / "groundwater_2025_availability_by_station.csv"
)

SUMMARY_OUT = (
    OUTDIR
    / "groundwater_2025_availability_summary.csv"
)

META_OUT = (
    OUTDIR
    / "groundwater_2025_historical_metadata_match.csv"
)

DUPLICATE_OUT = (
    OUTDIR
    / "groundwater_2025_duplicate_station_date_audit.csv"
)


# =====================================================================
# Frozen expectations from independently inspected workbook
# =====================================================================

EXPECTED_RAW_ROWS = 2294
EXPECTED_RAW_STATIONS = 290

EXPECTED_PAVIA_ROWS = 276
EXPECTED_PAVIA_STATIONS = 48

EXPECTED_PAVIA_ISS_ROWS = 186
EXPECTED_PAVIA_ISS_STATIONS = 26

EXPECTED_HISTORICAL_ISS_UNIVERSE = 37

EXPECTED_DUPLICATE_GROUPS = 6
EXPECTED_CONFLICTING_GROUPS = 3
EXPECTED_PAVIA_CONFLICTING_GROUPS = 0

EXPECTED_PAVIA_ISS_JANFEB = 18
EXPECTED_PAVIA_ISS_AUGUST = 17
EXPECTED_PAVIA_ISS_COMPLETE = 17


# =====================================================================
# Source-precision tolerances
# =====================================================================

# The 2025 workbook reports UTM coordinates to 0.01 m.
# Historical metadata retain additional decimal places.
#
# Independently observed maximum differences:
#   |delta E| <= ~0.0050 m
#   |delta N| <= ~0.0048 m
#
# Therefore 0.01 m represents source precision, not a substantive
# relocation tolerance.
COORDINATE_ATOL_M = 0.01

# Elevation and well-depth metadata are also published at coarser
# precision than the historical source. Use a separate explicit
# tolerance rather than silently reusing the coordinate logic.
METADATA_NUMERIC_ATOL = 0.01


# =====================================================================
# Helpers
# =====================================================================

def classify_aquifer(
    gwb: pd.Series,
) -> pd.Series:
    return (
        gwb.astype("string")
        .str.extract(
            r"\b(ISS|ISI|ISP)\b",
            expand=False,
        )
        .fillna("OTHER")
    )


def coordinate_equal(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:
    """
    Compare coordinates at the precision published in the 2025 source.
    """
    return np.isclose(
        pd.to_numeric(
            a,
            errors="coerce",
        ),
        pd.to_numeric(
            b,
            errors="coerce",
        ),
        rtol=0,
        atol=COORDINATE_ATOL_M,
        equal_nan=True,
    )


def metadata_numeric_equal(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:
    """
    Compare non-coordinate numeric metadata at published precision.
    """
    return np.isclose(
        pd.to_numeric(
            a,
            errors="coerce",
        ),
        pd.to_numeric(
            b,
            errors="coerce",
        ),
        rtol=0,
        atol=METADATA_NUMERIC_ATOL,
        equal_nan=True,
    )


# =====================================================================
# Load and clean authoritative 2025 workbook
# =====================================================================

def load_2025(
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not RAW_2025.exists():
        raise FileNotFoundError(
            "2025 groundwater workbook not found:\n"
            f"{RAW_2025}"
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
            f"Observed columns:\n{list(raw.columns)}"
        )

    if len(raw) != EXPECTED_RAW_ROWS:
        raise AssertionError(
            "Unexpected 2025 raw row count: "
            f"{len(raw)} != {EXPECTED_RAW_ROWS}"
        )

    raw_station_n = int(
        raw["CODICE"].nunique()
    )

    if raw_station_n != EXPECTED_RAW_STATIONS:
        raise AssertionError(
            "Unexpected 2025 raw station count: "
            f"{raw_station_n} != "
            f"{EXPECTED_RAW_STATIONS}"
        )

    d = raw.rename(
        columns={
            "CODICE":
                "station",

            "PROVINCIA":
                "province",

            "COMUNE":
                "commune",

            "Soggiacenza\nm da Qr":
                "gw_depth_m",

            "Data":
                "date",

            "ANNO":
                "year_reported",

            "X_WGS84/UTM32":
                "utm_e",

            "Y_WGS84/UTM322":
                "utm_n",

            "Quota di riferimento (Qr)\nm s.l.m.":
                "measuring_point_elev_masl",

            "PROFONDITA'\nm":
                "well_depth_m",

            "FILTRI_TOP\nm":
                "screen_top_m",

            "FILTRI_BOT\nm":
                "screen_bottom_m",

            "GroundWater Body\n(GWB_2015)":
                "gwb",
        }
    ).copy()

    # -----------------------------------------------------------------
    # Core normalization
    # -----------------------------------------------------------------

    d["date"] = pd.to_datetime(
        d["date"],
        errors="raise",
    )

    d["year"] = (
        d["date"]
        .dt.year
        .astype(int)
    )

    d["month"] = (
        d["date"]
        .dt.month
        .astype(int)
    )

    d["doy"] = (
        d["date"]
        .dt.dayofyear
        .astype(int)
    )

    if not d["year"].eq(2025).all():
        raise AssertionError(
            "Workbook contains observation dates outside 2025."
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

    # =================================================================
    # Duplicate station-date audit
    #
    # Frozen cleaning rule:
    # 1. exact duplicate rows may be collapsed;
    # 2. conflicting same-station/same-date GW values are excluded;
    # 3. conflicting values are never averaged.
    # =================================================================

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
            gw_values = (
                pd.to_numeric(
                    g["gw_depth_m"],
                    errors="coerce",
                )
                .dropna()
                .unique()
            )

            gw_values = sorted(
                float(x)
                for x in gw_values
            )

            unique_gw_n = len(
                gw_values
            )

            conflict = (
                unique_gw_n > 1
            )

            province_values = sorted(
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
                    for x in province_values
                }
            )

            duplicate_rows.append(
                {
                    "station":
                        station,

                    "date":
                        date,

                    "province":
                        ";".join(
                            province_values
                        ),

                    "rows_n":
                        int(
                            len(g)
                        ),

                    "unique_gw_values_n":
                        unique_gw_n,

                    "gw_values":
                        ";".join(
                            str(x)
                            for x in gw_values
                        ),

                    "exact_duplicate_group":
                        bool(
                            not conflict
                        ),

                    "conflicting_gw_group":
                        bool(
                            conflict
                        ),

                    "pavia_group":
                        bool(
                            pavia_group
                        ),
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
            .reset_index(
                drop=True
            )
        )

    duplicate_groups_n = int(
        len(
            duplicate_qa
        )
    )

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

    if (
        duplicate_groups_n
        != EXPECTED_DUPLICATE_GROUPS
    ):
        raise AssertionError(
            "Unexpected number of duplicate "
            "station-date groups: "
            f"{duplicate_groups_n} != "
            f"{EXPECTED_DUPLICATE_GROUPS}"
        )

    if (
        conflicting_groups_n
        != EXPECTED_CONFLICTING_GROUPS
    ):
        raise AssertionError(
            "Unexpected number of conflicting "
            "station-date groups: "
            f"{conflicting_groups_n} != "
            f"{EXPECTED_CONFLICTING_GROUPS}"
        )

    if (
        pavia_conflicting_groups_n
        != EXPECTED_PAVIA_CONFLICTING_GROUPS
    ):
        raise AssertionError(
            "Unexpected Pavia conflicting "
            "station-date groups: "
            f"{pavia_conflicting_groups_n} != "
            f"{EXPECTED_PAVIA_CONFLICTING_GROUPS}"
        )

    duplicate_qa.to_csv(
        DUPLICATE_OUT,
        index=False,
    )

    # -----------------------------------------------------------------
    # Collapse exact duplicated rows
    # -----------------------------------------------------------------

    d = (
        d.drop_duplicates()
        .copy()
    )

    # -----------------------------------------------------------------
    # Exclude complete conflicting station-date groups
    # -----------------------------------------------------------------

    if conflict_keys:
        conflict_index = (
            pd.MultiIndex
            .from_tuples(
                conflict_keys,
                names=key,
            )
        )

        row_index = (
            pd.MultiIndex
            .from_frame(
                d[key]
            )
        )

        conflict_mask = (
            row_index.isin(
                conflict_index
            )
        )

        d = d.loc[
            ~conflict_mask
        ].copy()

    if d.duplicated(key).any():
        bad = d.loc[
            d.duplicated(
                key,
                keep=False,
            )
        ]

        raise AssertionError(
            "Duplicate station-date rows remain "
            "after cleaning:\n"
            + bad.to_string(
                index=False
            )
        )

    return (
        d,
        duplicate_qa,
    )


# =====================================================================
# Historical frozen ISS universe
# =====================================================================

def load_historical_iss(
) -> pd.DataFrame:
    h = pd.read_csv(
        HIST_CLEAN
    )

    hist_iss = (
        h.loc[
            h[
                "aquifer_group"
            ].eq(
                "ISS"
            ),
            [
                "station",
                "commune",
                "utm_e",
                "utm_n",
                "measuring_point_elev_masl",
                "well_depth_m",
                "screen_top_m",
                "screen_bottom_m",
                "gwb",
            ],
        ]
        .drop_duplicates(
            "station"
        )
        .copy()
    )

    if (
        len(hist_iss)
        != EXPECTED_HISTORICAL_ISS_UNIVERSE
    ):
        raise AssertionError(
            "Expected frozen historical ISS universe of "
            f"{EXPECTED_HISTORICAL_ISS_UNIVERSE}; "
            f"found {len(hist_iss)}."
        )

    return hist_iss


# =====================================================================
# Metadata continuity QA
# =====================================================================

def build_metadata_qa(
    current_iss: pd.DataFrame,
    hist_iss: pd.DataFrame,
) -> pd.DataFrame:
    # -----------------------------------------------------------------
    # Verify metadata are internally constant within each 2025 station
    # before reducing to one station-level row.
    # -----------------------------------------------------------------

    for station, g in current_iss.groupby(
        "station",
        sort=True,
    ):
        for col in [
            "utm_e",
            "utm_n",
            "measuring_point_elev_masl",
            "well_depth_m",
            "gwb",
        ]:
            values = (
                g[col]
                .dropna()
                .astype(str)
                .unique()
            )

            if len(values) > 1:
                raise AssertionError(
                    "2025 metadata vary within station "
                    f"{station} for {col}: "
                    f"{list(values)}"
                )

    current_meta = (
        current_iss[
            [
                "station",
                "commune",
                "utm_e",
                "utm_n",
                "measuring_point_elev_masl",
                "well_depth_m",
                "gwb",
            ]
        ]
        .drop_duplicates(
            "station"
        )
        .copy()
    )

    hist_meta = (
        hist_iss[
            [
                "station",
                "commune",
                "utm_e",
                "utm_n",
                "measuring_point_elev_masl",
                "well_depth_m",
                "gwb",
            ]
        ]
        .rename(
            columns={
                "commune":
                    "commune_historical",

                "utm_e":
                    "utm_e_historical",

                "utm_n":
                    "utm_n_historical",

                "measuring_point_elev_masl":
                    "measuring_point_elev_masl_historical",

                "well_depth_m":
                    "well_depth_m_historical",

                "gwb":
                    "gwb_historical",
            }
        )
    )

    meta = current_meta.merge(
        hist_meta,
        on="station",
        how="left",
        validate="one_to_one",
    )

    hist_station_set = set(
        hist_iss["station"]
    )

    meta[
        "historical_iss_well"
    ] = (
        meta[
            "station"
        ].isin(
            hist_station_set
        )
    )

    # -----------------------------------------------------------------
    # Explicit coordinate deltas
    # -----------------------------------------------------------------

    meta[
        "delta_utm_e_m"
    ] = (
        pd.to_numeric(
            meta["utm_e"],
            errors="coerce",
        )
        - pd.to_numeric(
            meta["utm_e_historical"],
            errors="coerce",
        )
    )

    meta[
        "delta_utm_n_m"
    ] = (
        pd.to_numeric(
            meta["utm_n"],
            errors="coerce",
        )
        - pd.to_numeric(
            meta["utm_n_historical"],
            errors="coerce",
        )
    )

    meta[
        "abs_delta_utm_e_m"
    ] = (
        meta[
            "delta_utm_e_m"
        ].abs()
    )

    meta[
        "abs_delta_utm_n_m"
    ] = (
        meta[
            "delta_utm_n_m"
        ].abs()
    )

    meta[
        "coordinate_delta_max_abs_m"
    ] = np.maximum(
        meta[
            "abs_delta_utm_e_m"
        ],
        meta[
            "abs_delta_utm_n_m"
        ],
    )

    # -----------------------------------------------------------------
    # Precision-aware matching
    # -----------------------------------------------------------------

    meta[
        "utm_e_match"
    ] = coordinate_equal(
        meta["utm_e"],
        meta["utm_e_historical"],
    )

    meta[
        "utm_n_match"
    ] = coordinate_equal(
        meta["utm_n"],
        meta["utm_n_historical"],
    )

    meta[
        "coordinate_match"
    ] = (
        meta[
            "utm_e_match"
        ]
        & meta[
            "utm_n_match"
        ]
    )

    meta[
        "elevation_match"
    ] = metadata_numeric_equal(
        meta[
            "measuring_point_elev_masl"
        ],
        meta[
            "measuring_point_elev_masl_historical"
        ],
    )

    meta[
        "well_depth_match"
    ] = metadata_numeric_equal(
        meta[
            "well_depth_m"
        ],
        meta[
            "well_depth_m_historical"
        ],
    )

    return meta


# =====================================================================
# Station-level timing availability
# =====================================================================

def build_station_availability(
    iss: pd.DataFrame,
    hist_station_set: set[str],
) -> pd.DataFrame:
    rows = []

    for station, g in iss.groupby(
        "station",
        sort=True,
    ):
        g = (
            g.sort_values(
                "date"
            )
            .copy()
        )

        valid = g.loc[
            g[
                "gw_depth_m"
            ].notna()
        ]

        janfeb = valid.loc[
            valid[
                "month"
            ].isin(
                [
                    1,
                    2,
                ]
            )
        ]

        august = valid.loc[
            valid[
                "month"
            ].eq(
                8
            )
        ]

        rows.append(
            {
                "station":
                    station,

                "province":
                    g[
                        "province"
                    ].iloc[0],

                "commune":
                    g[
                        "commune"
                    ].iloc[0],

                "historical_iss_well":
                    bool(
                        station
                        in hist_station_set
                    ),

                "new_vs_historical_iss":
                    bool(
                        station
                        not in hist_station_set
                    ),

                "obs_n":
                    int(
                        len(g)
                    ),

                "valid_gw_n":
                    int(
                        len(valid)
                    ),

                "janfeb_n":
                    int(
                        len(janfeb)
                    ),

                "aug_n":
                    int(
                        len(august)
                    ),

                "has_janfeb":
                    bool(
                        len(janfeb) > 0
                    ),

                "has_aug":
                    bool(
                        len(august) > 0
                    ),

                "complete_pre_plus_aug":
                    bool(
                        len(janfeb) > 0
                        and
                        len(august) > 0
                    ),

                "first_obs_date":
                    (
                        valid[
                            "date"
                        ].min()
                        if len(valid)
                        else pd.NaT
                    ),

                "last_obs_date":
                    (
                        valid[
                            "date"
                        ].max()
                        if len(valid)
                        else pd.NaT
                    ),

                "janfeb_last_date":
                    (
                        janfeb[
                            "date"
                        ].max()
                        if len(janfeb)
                        else pd.NaT
                    ),

                "aug_first_date":
                    (
                        august[
                            "date"
                        ].min()
                        if len(august)
                        else pd.NaT
                    ),

                "aug_last_date":
                    (
                        august[
                            "date"
                        ].max()
                        if len(august)
                        else pd.NaT
                    ),

                "utm_e":
                    g[
                        "utm_e"
                    ].iloc[0],

                "utm_n":
                    g[
                        "utm_n"
                    ].iloc[0],
            }
        )

    return pd.DataFrame(
        rows
    )


# =====================================================================
# Main
# =====================================================================

def main() -> None:
    d, duplicate_qa = (
        load_2025()
    )

    hist_iss = (
        load_historical_iss()
    )

    hist_station_set = set(
        hist_iss[
            "station"
        ]
    )

    # -----------------------------------------------------------------
    # Duplicate diagnostics
    # -----------------------------------------------------------------

    duplicate_groups_n = int(
        len(
            duplicate_qa
        )
    )

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

    # -----------------------------------------------------------------
    # Pavia subset
    # -----------------------------------------------------------------

    pv = d.loc[
        d[
            "province"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(
            "PV"
        )
    ].copy()

    if len(pv) != EXPECTED_PAVIA_ROWS:
        raise AssertionError(
            "Unexpected Pavia row count after duplicate cleaning: "
            f"{len(pv)} != "
            f"{EXPECTED_PAVIA_ROWS}"
        )

    pavia_station_n = int(
        pv[
            "station"
        ].nunique()
    )

    if (
        pavia_station_n
        != EXPECTED_PAVIA_STATIONS
    ):
        raise AssertionError(
            "Unexpected Pavia station count after duplicate cleaning: "
            f"{pavia_station_n} != "
            f"{EXPECTED_PAVIA_STATIONS}"
        )

    # -----------------------------------------------------------------
    # Pavia ISS subset
    # -----------------------------------------------------------------

    iss = pv.loc[
        pv[
            "aquifer_group"
        ].eq(
            "ISS"
        )
    ].copy()

    if len(iss) != EXPECTED_PAVIA_ISS_ROWS:
        raise AssertionError(
            "Unexpected Pavia ISS row count after duplicate cleaning: "
            f"{len(iss)} != "
            f"{EXPECTED_PAVIA_ISS_ROWS}"
        )

    pavia_iss_station_n = int(
        iss[
            "station"
        ].nunique()
    )

    if (
        pavia_iss_station_n
        != EXPECTED_PAVIA_ISS_STATIONS
    ):
        raise AssertionError(
            "Unexpected Pavia ISS station count: "
            f"{pavia_iss_station_n} != "
            f"{EXPECTED_PAVIA_ISS_STATIONS}"
        )

    current_iss_stations = set(
        iss[
            "station"
        ].dropna()
    )

    new_iss = sorted(
        current_iss_stations
        - hist_station_set
    )

    historical_present = sorted(
        current_iss_stations
        & hist_station_set
    )

    if new_iss:
        raise AssertionError(
            "2025 contains Pavia ISS stations outside "
            "the frozen historical 37-well universe:\n"
            + "\n".join(
                new_iss
            )
        )

    # -----------------------------------------------------------------
    # Metadata continuity QA
    # -----------------------------------------------------------------

    meta = build_metadata_qa(
        iss,
        hist_iss,
    )

    meta.to_csv(
        META_OUT,
        index=False,
    )

    known_meta = meta.loc[
        meta[
            "historical_iss_well"
        ]
    ].copy()

    coordinate_match_n = int(
        known_meta[
            "coordinate_match"
        ].sum()
    )

    coordinate_mismatch_n = int(
        (
            ~known_meta[
                "coordinate_match"
            ]
        ).sum()
    )

    max_abs_easting_delta_m = float(
        known_meta[
            "abs_delta_utm_e_m"
        ].max()
    )

    max_abs_northing_delta_m = float(
        known_meta[
            "abs_delta_utm_n_m"
        ].max()
    )

    max_abs_coordinate_delta_m = float(
        known_meta[
            "coordinate_delta_max_abs_m"
        ].max()
    )

    if coordinate_mismatch_n:
        bad = known_meta.loc[
            ~known_meta[
                "coordinate_match"
            ]
        ]

        raise AssertionError(
            "2025 Pavia ISS coordinates exceed "
            "the 0.01 m source-precision tolerance:\n"
            + bad.to_string(
                index=False
            )
        )

    # -----------------------------------------------------------------
    # Timing availability
    # -----------------------------------------------------------------

    station = build_station_availability(
        iss,
        hist_station_set,
    )

    station.to_csv(
        STATION_OUT,
        index=False,
    )

    is_hist = station[
        "historical_iss_well"
    ]

    is_new = station[
        "new_vs_historical_iss"
    ]

    has_pre = station[
        "has_janfeb"
    ]

    has_aug = station[
        "has_aug"
    ]

    complete = station[
        "complete_pre_plus_aug"
    ]

    def n(
        mask: pd.Series,
    ) -> int:
        return int(
            mask.sum()
        )

    janfeb_n = n(
        has_pre
    )

    august_n = n(
        has_aug
    )

    complete_n = n(
        complete
    )

    if (
        janfeb_n
        != EXPECTED_PAVIA_ISS_JANFEB
    ):
        raise AssertionError(
            "Unexpected Pavia ISS Jan-Feb count: "
            f"{janfeb_n} != "
            f"{EXPECTED_PAVIA_ISS_JANFEB}"
        )

    if (
        august_n
        != EXPECTED_PAVIA_ISS_AUGUST
    ):
        raise AssertionError(
            "Unexpected Pavia ISS August count: "
            f"{august_n} != "
            f"{EXPECTED_PAVIA_ISS_AUGUST}"
        )

    if (
        complete_n
        != EXPECTED_PAVIA_ISS_COMPLETE
    ):
        raise AssertionError(
            "Unexpected Pavia ISS complete count: "
            f"{complete_n} != "
            f"{EXPECTED_PAVIA_ISS_COMPLETE}"
        )

    # -----------------------------------------------------------------
    # Summary output
    # -----------------------------------------------------------------

    summary = pd.DataFrame(
        [
            (
                "raw_2025_rows_before_duplicate_cleaning",
                EXPECTED_RAW_ROWS,
            ),

            (
                "all_2025_rows_after_duplicate_cleaning",
                len(d),
            ),

            (
                "all_2025_stations",
                d[
                    "station"
                ].nunique(),
            ),

            (
                "duplicate_station_date_groups",
                duplicate_groups_n,
            ),

            (
                "conflicting_duplicate_groups",
                conflicting_groups_n,
            ),

            (
                "pavia_conflicting_duplicate_groups",
                pavia_conflicting_groups_n,
            ),

            (
                "pavia_rows",
                len(pv),
            ),

            (
                "pavia_stations",
                pavia_station_n,
            ),

            (
                "pavia_iss_rows",
                len(iss),
            ),

            (
                "pavia_iss_stations",
                pavia_iss_station_n,
            ),

            (
                "historical_iss_stations_present",
                len(
                    historical_present
                ),
            ),

            (
                "new_iss_stations",
                len(
                    new_iss
                ),
            ),

            (
                "iss_with_janfeb",
                janfeb_n,
            ),

            (
                "iss_with_august",
                august_n,
            ),

            (
                "iss_complete_pre_plus_aug",
                complete_n,
            ),

            (
                "historical_iss_complete_pre_plus_aug",
                n(
                    is_hist
                    & complete
                ),
            ),

            (
                "new_iss_complete_pre_plus_aug",
                n(
                    is_new
                    & complete
                ),
            ),

            (
                "historical_iss_coordinate_matches",
                coordinate_match_n,
            ),

            (
                "historical_iss_coordinate_mismatches",
                coordinate_mismatch_n,
            ),

            (
                "coordinate_match_tolerance_m",
                COORDINATE_ATOL_M,
            ),

            (
                "max_abs_easting_delta_m",
                max_abs_easting_delta_m,
            ),

            (
                "max_abs_northing_delta_m",
                max_abs_northing_delta_m,
            ),

            (
                "max_abs_coordinate_delta_m",
                max_abs_coordinate_delta_m,
            ),
        ],
        columns=[
            "metric",
            "value",
        ],
    )

    summary.to_csv(
        SUMMARY_OUT,
        index=False,
    )

    # =================================================================
    # Console report
    # =================================================================

    print()
    print(
        "=" * 76
    )
    print(
        "ARPA LOMBARDIA / PAVIA 2025 "
        "GROUNDWATER AVAILABILITY AUDIT"
    )
    print(
        "=" * 76
    )

    print()
    print(
        "=== REGIONAL DUPLICATE QA ==="
    )

    print(
        "duplicate station-date groups =",
        duplicate_groups_n,
    )

    print(
        "conflicting duplicate groups =",
        conflicting_groups_n,
    )

    print(
        "Pavia conflicting duplicate groups =",
        pavia_conflicting_groups_n,
    )

    if len(duplicate_qa):
        print()
        print(
            duplicate_qa.to_string(
                index=False
            )
        )

    print()
    print(
        "=== AVAILABILITY SUMMARY ==="
    )

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print(
        "2025 overall date range:",
        d[
            "date"
        ].min(),
        "to",
        d[
            "date"
        ].max(),
    )

    print(
        "Pavia date range:",
        pv[
            "date"
        ].min(),
        "to",
        pv[
            "date"
        ].max(),
    )

    print()
    print(
        "New ISS stations relative to "
        "frozen historical 37-well universe:"
    )

    if new_iss:
        for station_id in new_iss:
            print(
                station_id
            )
    else:
        print(
            "None."
        )

    print()
    print(
        "=== COMPLETE PAVIA ISS WELLS ==="
    )

    complete_iss = (
        station.loc[
            complete,
            [
                "station",
                "commune",
                "historical_iss_well",
                "new_vs_historical_iss",
                "obs_n",
                "janfeb_n",
                "janfeb_last_date",
                "aug_n",
                "aug_first_date",
                "aug_last_date",
            ],
        ]
        .sort_values(
            "station"
        )
    )

    if len(complete_iss):
        print(
            complete_iss.to_string(
                index=False
            )
        )
    else:
        print(
            "None."
        )

    print()
    print(
        "=== HISTORICAL ISS COORDINATE CONTINUITY ==="
    )

    print(
        "historical ISS stations checked =",
        len(
            known_meta
        ),
    )

    print(
        "coordinate matches =",
        coordinate_match_n,
    )

    print(
        "coordinate mismatches =",
        coordinate_mismatch_n,
    )

    print(
        "coordinate tolerance (m) =",
        COORDINATE_ATOL_M,
    )

    print(
        "max |delta E| (m) =",
        max_abs_easting_delta_m,
    )

    print(
        "max |delta N| (m) =",
        max_abs_northing_delta_m,
    )

    print(
        "max coordinate delta (m) =",
        max_abs_coordinate_delta_m,
    )

    print()
    print(
        "Coordinate continuity status: "
        "PASS AFTER SOURCE-PRECISION ROUNDING"
    )

    print()
    print(
        f"Wrote: {DUPLICATE_OUT}"
    )

    print(
        f"Wrote: {STATION_OUT}"
    )

    print(
        f"Wrote: {SUMMARY_OUT}"
    )

    print(
        f"Wrote: {META_OUT}"
    )

    print()
    print(
        "Exact duplicate rows were collapsed."
    )

    print(
        "Conflicting same-station/same-date "
        "groundwater groups were excluded."
    )

    print(
        "Conflicting groundwater values were never averaged."
    )

    print(
        "2025 coordinate differences were evaluated "
        "against the published 0.01 m source precision."
    )

    print(
        "NO FLOODING EXPOSURE MERGED."
    )

    print(
        "NO EFFECT MODEL FIT."
    )

    print(
        "DONE"
    )


if __name__ == "__main__":
    main()
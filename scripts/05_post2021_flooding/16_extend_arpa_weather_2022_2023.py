"""Extend the frozen ARPA Lombardia weather pipeline through 2023.

Scientific role
---------------
This stage extends the historically established meteorological controls
without inspecting groundwater values.

It preserves the publication-track definitions:

Acquisition
    - official Regione Lombardia / ARPA Socrata SODA2 CSV endpoint
    - fixed sensor IDs already used in the historical pipeline
    - >=2021 precipitation dataset: pstb-pga6
    - >=2021 temperature dataset: w9wd-u6jh
    - deterministic idsensore,data ordering
    - explicit pagination

Sensor-day / sensor-month validation
    - stato == "VA"
    - temperature -999 treated as missing
    - expected cadence inferred sensor-year by 90th percentile
    - cadence snapped to historical COMMON_CADENCES
    - valid day requires >=80% expected observations
    - valid month requires >=80% valid days
    - precipitation monthly sum
    - temperature monthly mean

Well linkage
    - up to 3 nearest valid sensors
    - <=50 km
    - at least 2 sensors
    - inverse squared distance weights
    - minimum distance in weighting denominator = 0.5 km

Primary historical weather controls
    - P_A8: April-August cumulative precipitation
    - T_A8: April-August day-weighted mean temperature

Integrity gate
--------------
The newly implemented weather pipeline must reproduce the frozen
2008-2021 weather_sensor_monthly.csv artifact before any 2022-2023
weather result is trusted.

No groundwater depth values are read.
No groundwater association is calculated.
No regression is fitted.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT / "data" / "raw" / "arpa_meteo"

HIST_MONTHLY_IN = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "weather_sensor_monthly.csv"
)

WX_META_IN = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "weather_station_master.csv"
)

GW_META_IN = (
    ROOT
    / "data"
    / "processed"
    / "publication_groundwater"
    / "groundwater_station_metadata.csv"
)

FROZEN_IDS_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_primary_repeated_sample_ids.csv"
)

FF10_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2023.csv"
)

POST_DIR = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
)

QA_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

MONTHLY_OUT = (
    POST_DIR
    / "weather_sensor_monthly_2008_2023.csv"
)

WELL_WEATHER_OUT = (
    POST_DIR
    / "well_weather_A8_2022_2023.csv"
)

REPRO_QA_OUT = (
    QA_DIR
    / "post2021_weather_historical_reproduction_qa.csv"
)

COMPLETENESS_QA_OUT = (
    QA_DIR
    / "post2021_weather_primary_sample_completeness.csv"
)

DELTA_QA_OUT = (
    QA_DIR
    / "post2021_weather_primary_sample_delta_qa.csv"
)

PROVENANCE_QA_OUT = (
    QA_DIR
    / "post2021_weather_source_provenance.csv"
)


# ---------------------------------------------------------------------
# Frozen source definitions inherited from the historical downloader.
# ---------------------------------------------------------------------

PRECIP_DATASET = "pstb-pga6"
TEMP_DATASET = "w9wd-u6jh"

PRECIP_SENSORS = [
    2195,
    2368,
    8155,
    9863,
    12724,
    17437,
    17572,
]

TEMP_SENSORS = [
    2187,
    6698,
    8157,
    8196,
    9868,
    12716,
    17432,
    17573,
]

POST_JOBS = [
    (
        "precip_2022_2023",
        PRECIP_DATASET,
        2022,
        2023,
        PRECIP_SENSORS,
    ),
    (
        "temp_2022_2023",
        TEMP_DATASET,
        2022,
        2023,
        TEMP_SENSORS,
    ),
]

FILES = {
    "precip": [
        "precip_2008_2010.csv",
        "precip_2011_2020.csv",
        "precip_2021.csv",
        "precip_2022_2023.csv",
    ],
    "temp": [
        "temp_2008_2010.csv",
        "temp_2011_2020.csv",
        "temp_2021.csv",
        "temp_2022_2023.csv",
    ],
}

PAGE = 50_000

COMMON_CADENCES = np.array(
    [
        8,
        12,
        24,
        48,
        72,
        96,
        144,
        288,
    ]
)

START_YEAR = 2008
HIST_END_YEAR = 2021
END_YEAR = 2023

POST_YEARS = (2022, 2023)

EXPECTED_FROZEN_WELLS = 13

NEAREST_N = 3
MAX_KM = 50.0
MIN_STATIONS = 2


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as fh:
        while True:
            block = fh.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def download(
    name: str,
    dataset: str,
    y0: int,
    y1: int,
    sensors: list[int],
) -> dict:
    """Exact acquisition architecture used by historical downloader."""

    path = RAW_DIR / f"{name}.csv"

    ids = ",".join(
        f"'{x}'"
        for x in sensors
    )

    where = (
        f"idsensore in ({ids}) AND "
        f"data >= '{y0}-01-01T00:00:00' AND "
        f"data <= '{y1}-12-31T23:59:59'"
    )

    offset = 0
    wrote_header = False
    rows_total = 0

    acquisition_utc = datetime.now(
        timezone.utc
    ).isoformat()

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as fh:
        writer = None

        while True:
            query = urlencode(
                {
                    "$limit": PAGE,
                    "$offset": offset,
                    "$order": "idsensore,data",
                    "$where": where,
                }
            )

            url = (
                "https://www.dati.lombardia.it/"
                f"resource/{dataset}.csv?{query}"
            )

            with urlopen(
                url,
                timeout=120,
            ) as response:  # nosec B310: fixed official HTTPS endpoint
                text = (
                    response
                    .read()
                    .decode("utf-8-sig")
                )

            chunk = list(
                csv.DictReader(
                    text.splitlines()
                )
            )

            if not chunk:
                break

            if writer is None:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=chunk[0].keys(),
                )

            if not wrote_header:
                writer.writeheader()
                wrote_header = True

            writer.writerows(chunk)

            rows_total += len(chunk)
            offset += len(chunk)

            print(
                f"{name}: "
                f"{rows_total:,} rows"
            )

            if len(chunk) < PAGE:
                break

            time.sleep(0.15)

    if rows_total == 0:
        raise AssertionError(
            f"{name}: open-data query returned zero rows."
        )

    header = pd.read_csv(
        path,
        nrows=0,
    ).columns.tolist()

    expected_header = [
        "idsensore",
        "data",
        "valore",
        "stato",
    ]

    if header != expected_header:
        raise AssertionError(
            f"{name}: unexpected schema {header}; "
            f"expected {expected_header}."
        )

    digest = sha256_file(path)

    print(
        f"saved {path} "
        f"({rows_total:,} rows)"
    )

    return {
        "name": name,
        "dataset_id": dataset,
        "start_year": y0,
        "end_year": y1,
        "sensor_ids": ";".join(
            str(x)
            for x in sensors
        ),
        "rows_downloaded": rows_total,
        "acquisition_utc": acquisition_utc,
        "sha256": digest,
        "source": (
            "Regione Lombardia / ARPA Lombardia "
            "Open Data Socrata SODA2"
        ),
    }


def acquire_or_reuse(
    name: str,
    dataset: str,
    y0: int,
    y1: int,
    sensors: list[int],
) -> dict:
    """Reuse a validated existing download; otherwise fetch it."""

    path = RAW_DIR / f"{name}.csv"

    if not path.exists():
        return download(
            name,
            dataset,
            y0,
            y1,
            sensors,
        )

    header = pd.read_csv(
        path,
        nrows=0,
    ).columns.tolist()

    expected_header = [
        "idsensore",
        "data",
        "valore",
        "stato",
    ]

    if header != expected_header:
        raise AssertionError(
            f"{name}: unexpected existing-file schema "
            f"{header}; expected {expected_header}."
        )

    audit = pd.read_csv(
        path,
        usecols=[
            "idsensore",
            "data",
        ],
    )

    if len(audit) == 0:
        raise AssertionError(
            f"{name}: existing raw file is empty."
        )

    audit["idsensore"] = pd.to_numeric(
        audit["idsensore"],
        errors="raise",
    ).astype("int64")

    audit["data"] = pd.to_datetime(
        audit["data"],
        errors="raise",
    )

    unexpected_sensors = (
        set(audit["idsensore"].unique())
        - set(sensors)
    )

    if unexpected_sensors:
        raise AssertionError(
            f"{name}: unexpected sensor IDs "
            f"{sorted(unexpected_sensors)}."
        )

    if not audit["data"].dt.year.between(
        y0,
        y1,
    ).all():
        raise AssertionError(
            f"{name}: dates outside requested "
            f"{y0}-{y1} range."
        )

    digest = sha256_file(path)

    print(
        f"reusing {path} "
        f"({len(audit):,} rows)"
    )

    return {
        "name": name,
        "dataset_id": dataset,
        "start_year": y0,
        "end_year": y1,
        "sensor_ids": ";".join(
            str(x)
            for x in sensors
        ),
        "rows_downloaded": len(audit),
        "acquisition_utc": "existing_local_download",
        "sha256": digest,
        "source": (
            "Regione Lombardia / ARPA Lombardia "
            "Open Data Socrata SODA2"
        ),
    }


def read_daily(
    paths: list[Path],
    variable: str,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Exact historical daily validation logic,
    extended only by END_YEAR.
    """

    all_parts = []
    qa = []

    for path in paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}"
            )

        parts = []
        raw_rows = 0

        for d in pd.read_csv(
            path,
            usecols=[
                "idsensore",
                "data",
                "valore",
                "stato",
            ],
            chunksize=400_000,
        ):
            raw_rows += len(d)

            d["data"] = pd.to_datetime(
                d["data"],
                errors="coerce",
            )

            d = d[
                d["data"]
                .dt.year
                .between(
                    START_YEAR,
                    END_YEAR,
                )
            ]

            d["idsensore"] = pd.to_numeric(
                d["idsensore"],
                errors="coerce",
            ).astype("Int64")

            d["valore"] = pd.to_numeric(
                d["valore"],
                errors="coerce",
            )

            if variable == "temp":
                d.loc[
                    d["valore"].eq(-999),
                    "valore",
                ] = np.nan

            d.loc[
                d["stato"].ne("VA"),
                "valore",
            ] = np.nan

            d["date"] = (
                d["data"]
                .dt.floor("D")
            )

            z = (
                d.groupby(
                    [
                        "idsensore",
                        "date",
                    ],
                    as_index=False,
                )
                .agg(
                    n=("valore", "count"),
                    s=("valore", "sum"),
                    mean=("valore", "mean"),
                )
            )

            parts.append(z)

        if not parts:
            raise AssertionError(
                f"No readable rows in {path}."
            )

        z = pd.concat(
            parts,
            ignore_index=True,
        )

        if variable == "precip":
            z = (
                z.groupby(
                    [
                        "idsensore",
                        "date",
                    ],
                    as_index=False,
                )
                .agg(
                    n=("n", "sum"),
                    s=("s", "sum"),
                )
            )

        else:
            z["weighted_sum"] = (
                z["mean"]
                * z["n"]
            )

            z = (
                z.groupby(
                    [
                        "idsensore",
                        "date",
                    ],
                    as_index=False,
                )
                .agg(
                    n=("n", "sum"),
                    weighted_sum=(
                        "weighted_sum",
                        "sum",
                    ),
                )
            )

            z["mean"] = (
                z["weighted_sum"]
                / z["n"].replace(
                    0,
                    np.nan,
                )
            )

        all_parts.append(z)

        qa.append(
            {
                "metric":
                    f"raw_rows_{path.stem}",
                "value":
                    raw_rows,
            }
        )

    z = pd.concat(
        all_parts,
        ignore_index=True,
    )

    if variable == "precip":
        z = (
            z.groupby(
                [
                    "idsensore",
                    "date",
                ],
                as_index=False,
            )
            .agg(
                n=("n", "sum"),
                s=("s", "sum"),
            )
        )

    else:
        z["weighted_sum"] = (
            z["mean"]
            * z["n"]
        )

        z = (
            z.groupby(
                [
                    "idsensore",
                    "date",
                ],
                as_index=False,
            )
            .agg(
                n=("n", "sum"),
                weighted_sum=(
                    "weighted_sum",
                    "sum",
                ),
            )
        )

        z["mean"] = (
            z["weighted_sum"]
            / z["n"].replace(
                0,
                np.nan,
            )
        )

    z["year"] = (
        z["date"].dt.year
    )

    z["month"] = (
        z["date"].dt.month
    )

    cadence = (
        z.groupby(
            [
                "idsensore",
                "year",
            ]
        )["n"]
        .quantile(0.90)
        .reset_index(
            name="q90"
        )
    )

    cadence["expected"] = (
        cadence["q90"]
        .apply(
            lambda q:
                COMMON_CADENCES[
                    np.argmin(
                        np.abs(
                            COMMON_CADENCES - q
                        )
                    )
                ]
                if pd.notna(q)
                else np.nan
        )
    )

    z = z.merge(
        cadence[
            [
                "idsensore",
                "year",
                "expected",
            ]
        ],
        on=[
            "idsensore",
            "year",
        ],
        how="left",
        validate="many_to_one",
    )

    z["valid_day"] = (
        z["n"]
        >= 0.8 * z["expected"]
    )

    z["value"] = (
        z["s"]
        if variable == "precip"
        else z["mean"]
    )

    z.loc[
        ~z["valid_day"],
        "value",
    ] = np.nan

    return z, qa


def monthly(
    daily: pd.DataFrame,
    variable: str,
) -> pd.DataFrame:
    """Exact historical monthly aggregation rule."""

    fn = (
        "sum"
        if variable == "precip"
        else "mean"
    )

    m = (
        daily.groupby(
            [
                "idsensore",
                "year",
                "month",
            ],
            as_index=False,
        )
        .agg(
            value=("value", fn),
            valid_days=(
                "value",
                "count",
            ),
        )
    )

    m["days_in_month"] = [
        calendar.monthrange(
            int(y),
            int(mo),
        )[1]
        for y, mo in zip(
            m["year"],
            m["month"],
        )
    ]

    m["coverage"] = (
        m["valid_days"]
        / m["days_in_month"]
    )

    m.loc[
        m["coverage"] < 0.8,
        "value",
    ] = np.nan

    m["variable"] = variable

    return m[
        [
            "variable",
            "idsensore",
            "year",
            "month",
            "value",
            "valid_days",
            "days_in_month",
            "coverage",
        ]
    ]


def compare_historical_monthly(
    extended: pd.DataFrame,
    historical: pd.DataFrame,
) -> pd.DataFrame:
    """
    Require exact reproduction of the frozen 2008-2021
    sensor-month artifact, allowing only tiny floating-point
    representation differences.
    """

    key = [
        "variable",
        "idsensore",
        "year",
        "month",
    ]

    generated = (
        extended.loc[
            extended["year"].between(
                START_YEAR,
                HIST_END_YEAR,
            )
        ]
        .sort_values(key)
        .reset_index(drop=True)
    )

    historical = (
        historical
        .sort_values(key)
        .reset_index(drop=True)
    )

    if len(generated) != len(historical):
        raise AssertionError(
            "Historical weather reproduction row-count mismatch: "
            f"generated={len(generated)}, "
            f"frozen={len(historical)}."
        )

    generated_key = generated[key].copy()
    historical_key = historical[key].copy()

    generated_key["variable"] = generated_key["variable"].astype(str)
    historical_key["variable"] = historical_key["variable"].astype(str)

    for col in ["idsensore", "year", "month"]:
        generated_key[col] = pd.to_numeric(
            generated_key[col],
            errors="raise",
        ).astype("int64")

        historical_key[col] = pd.to_numeric(
            historical_key[col],
            errors="raise",
        ).astype("int64")

    if not generated_key.equals(historical_key):
        raise AssertionError(
            "Historical weather sensor-month key values do not reproduce."
        )
    common = [
        c
        for c in historical.columns
        if c in generated.columns
    ]

    rows = []

    for col in common:
        if col in key:
            continue

        a = historical[col]
        b = generated[col]

        if (
            pd.api.types
            .is_numeric_dtype(a)
            and
            pd.api.types
            .is_numeric_dtype(b)
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
                atol=1e-12,
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
                "column": col,
                "rows_compared":
                    len(equal),
                "mismatch_n":
                    mismatch_n,
                "exact_reproduction":
                    mismatch_n == 0,
            }
        )

    qa = pd.DataFrame(rows)

    if not qa[
        "exact_reproduction"
    ].all():
        bad = qa.loc[
            ~qa["exact_reproduction"]
        ]

        raise AssertionError(
            "Extended weather pipeline does not reproduce "
            "frozen 2008-2021 monthly weather:\n"
            + bad.to_string(index=False)
        )

    return qa


def link_months(
    panel: pd.DataFrame,
    monthly_weather: pd.DataFrame,
    meta: pd.DataFrame,
    variable: str,
    type_name: str,
    prefix: str,
) -> pd.DataFrame:
    """Exact historical well-to-weather spatial linkage rule."""

    wc = meta.loc[
        meta["Tipologia"].eq(
            type_name
        ),
        [
            "IdSensore",
            "UTM_Est",
            "UTM_Nord",
            "NomeStazione",
        ],
    ].copy()

    wc["IdSensore"] = (
        pd.to_numeric(
            wc["IdSensore"],
            errors="coerce",
        )
        .astype("Int64")
    )

    wc = (
        wc.dropna(
            subset=[
                "IdSensore",
                "UTM_Est",
                "UTM_Nord",
            ]
        )
        .drop_duplicates(
            "IdSensore"
        )
    )

    mm = monthly_weather.loc[
        monthly_weather[
            "variable"
        ].eq(variable)
    ].copy()

    wc = wc.loc[
        wc["IdSensore"].isin(
            mm[
                "idsensore"
            ]
            .dropna()
            .unique()
        )
    ]

    lookup = {
        (
            int(y),
            int(m),
        ):
        g.set_index(
            "idsensore"
        )["value"]
        for (y, m), g
        in mm.groupby(
            [
                "year",
                "month",
            ]
        )
    }

    rows = []

    for r in panel[
        [
            "station",
            "year",
            "utm_e",
            "utm_n",
        ]
    ].itertuples(
        index=False
    ):
        rec = {
            "station":
                r.station,
            "year":
                int(r.year),
        }

        for month in range(1, 9):
            a = (
                lookup.get(
                    (
                        int(r.year),
                        month,
                    ),
                    pd.Series(
                        dtype=float
                    ),
                )
                .dropna()
            )

            cand = wc.loc[
                wc[
                    "IdSensore"
                ].isin(
                    a.index
                )
            ].copy()

            if len(cand):
                cand["dist_km"] = (
                    np.hypot(
                        cand[
                            "UTM_Est"
                        ]
                        - r.utm_e,
                        cand[
                            "UTM_Nord"
                        ]
                        - r.utm_n,
                    )
                    / 1000.0
                )

                cand = (
                    cand.loc[
                        cand[
                            "dist_km"
                        ]
                        <= MAX_KM
                    ]
                    .sort_values(
                        "dist_km"
                    )
                    .head(
                        NEAREST_N
                    )
                )

            if len(cand) >= MIN_STATIONS:
                vals = (
                    a.reindex(
                        cand[
                            "IdSensore"
                        ]
                    )
                    .astype(float)
                    .to_numpy()
                )

                dd = (
                    cand[
                        "dist_km"
                    ]
                    .astype(float)
                    .to_numpy()
                )

                weights = (
                    1.0
                    / np.maximum(
                        dd,
                        0.5,
                    ) ** 2
                )

                weights /= (
                    weights.sum()
                )

                rec[
                    f"{prefix}{month}"
                ] = float(
                    np.sum(
                        vals
                        * weights
                    )
                )

                rec[
                    f"{prefix}{month}_n"
                ] = len(cand)

                rec[
                    f"{prefix}{month}_dmax_km"
                ] = float(
                    dd.max()
                )

            else:
                rec[
                    f"{prefix}{month}"
                ] = np.nan

                rec[
                    f"{prefix}{month}_n"
                ] = len(cand)

                rec[
                    f"{prefix}{month}_dmax_km"
                ] = np.nan

        rows.append(rec)

    return pd.DataFrame(rows)


def main() -> None:
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    POST_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    QA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------
    # 1. Open-data acquisition.
    # -------------------------------------------------------------

    provenance = []

    for job in POST_JOBS:
        provenance.append(acquire_or_reuse(*job))

    provenance_df = pd.DataFrame(
        provenance
    )

    provenance_df.to_csv(
        PROVENANCE_QA_OUT,
        index=False,
    )

    # -------------------------------------------------------------
    # 2. Rebuild sensor-month weather 2008-2023 using exact
    #    historical validation definitions.
    # -------------------------------------------------------------

    monthly_parts = []

    for variable, names in FILES.items():
        daily, _ = read_daily(
            [
                RAW_DIR / name
                for name in names
            ],
            variable,
        )

        monthly_parts.append(
            monthly(
                daily,
                variable,
            )
        )

    monthly_all = (
        pd.concat(
            monthly_parts,
            ignore_index=True,
        )
        .sort_values(
            [
                "variable",
                "idsensore",
                "year",
                "month",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    historical = pd.read_csv(
        HIST_MONTHLY_IN
    )

    repro_qa = (
        compare_historical_monthly(
            monthly_all,
            historical,
        )
    )

    repro_qa.to_csv(
        REPRO_QA_OUT,
        index=False,
    )

    print("")
    print(
        "Historical weather reproduction: PASS"
    )
    print(
        f"  columns reproduced: {len(repro_qa)}"
    )
    print(
        "  mismatches: 0"
    )
    print("")

    monthly_all.to_csv(
        MONTHLY_OUT,
        index=False,
    )

    # -------------------------------------------------------------
    # 3. Build weather controls for all 37 ISS wells, 2022-2023.
    #
    # Groundwater STATION METADATA only:
    # no groundwater observation/depth table is read.
    # -------------------------------------------------------------

    gw_meta = pd.read_csv(
        GW_META_IN
    )

    wells = (
        gw_meta.loc[
            gw_meta[
                "aquifer_group"
            ].eq("ISS"),
            [
                "station",
                "utm_e",
                "utm_n",
            ],
        ]
        .drop_duplicates(
            "station"
        )
        .copy()
    )

    if len(wells) != 37:
        raise AssertionError(
            f"Expected 37 ISS wells; found {len(wells)}."
        )

    panel = pd.MultiIndex.from_product(
        [
            wells["station"],
            POST_YEARS,
        ],
        names=[
            "station",
            "year",
        ],
    ).to_frame(
        index=False
    )

    panel = panel.merge(
        wells,
        on="station",
        how="left",
        validate="many_to_one",
    )

    weather_meta = pd.read_csv(
        WX_META_IN
    )

    precip = link_months(
        panel,
        monthly_all,
        weather_meta,
        "precip",
        "Precipitazione",
        "P",
    )

    temp = link_months(
        panel,
        monthly_all,
        weather_meta,
        "temp",
        "Temperatura",
        "T",
    )

    p = (
        panel.merge(
            precip,
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
        .merge(
            temp,
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
    )

    # Exact historical April-August definitions.
    months = list(
        range(
            4,
            9,
        )
    )

    p["P_A8"] = (
        p[
            [
                f"P{m}"
                for m in months
            ]
        ]
        .sum(
            axis=1,
            min_count=len(months),
        )
    )

    days = np.array(
        [
            calendar.monthrange(
                2001,
                m,
            )[1]
            for m in months
        ],
        dtype=float,
    )

    vals = p[
        [
            f"T{m}"
            for m in months
        ]
    ].to_numpy(
        dtype=float
    )

    p["T_A8"] = np.where(
        np.isfinite(
            vals
        ).all(axis=1),
        (
            (
                vals
                * days
            ).sum(axis=1)
            / days.sum()
        ),
        np.nan,
    )

    p[
        "has_weather_A8"
    ] = (
        p[
            [
                "P_A8",
                "T_A8",
            ]
        ]
        .notna()
        .all(axis=1)
    )

    p = p.sort_values(
        [
            "station",
            "year",
        ]
    )

    p.to_csv(
        WELL_WEATHER_OUT,
        index=False,
    )

    # -------------------------------------------------------------
    # 4. Frozen 13-well completeness audit.
    #
    # Frozen sample IDs were selected before weather/outcome
    # inspection. Still no groundwater values.
    # -------------------------------------------------------------

    ids = pd.read_csv(
        FROZEN_IDS_IN
    )

    if len(ids) != EXPECTED_FROZEN_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_FROZEN_WELLS} frozen wells; "
            f"found {len(ids)}."
        )

    if ids["station"].duplicated().any():
        raise AssertionError(
            "Frozen sample contains duplicate station IDs."
        )

    frozen_weather = p.loc[
        p["station"].isin(
            ids["station"]
        )
    ].copy()

    if (
        frozen_weather[
            "station"
        ].nunique()
        != EXPECTED_FROZEN_WELLS
    ):
        raise AssertionError(
            "Not all frozen wells were found in weather panel."
        )

    completeness_rows = []

    for year in POST_YEARS:
        y = frozen_weather.loc[
            frozen_weather[
                "year"
            ].eq(year)
        ]

        completeness_rows.append(
            {
                "year":
                    year,
                "frozen_wells_n":
                    EXPECTED_FROZEN_WELLS,
                "P_A8_complete_n":
                    int(
                        y[
                            "P_A8"
                        ]
                        .notna()
                        .sum()
                    ),
                "T_A8_complete_n":
                    int(
                        y[
                            "T_A8"
                        ]
                        .notna()
                        .sum()
                    ),
                "weather_A8_complete_n":
                    int(
                        y[
                            "has_weather_A8"
                        ]
                        .sum()
                    ),
            }
        )

    completeness = pd.DataFrame(
        completeness_rows
    )

    completeness.to_csv(
        COMPLETENESS_QA_OUT,
        index=False,
    )

    # -------------------------------------------------------------
    # 5. Weather-change diagnostics among frozen repeated wells.
    # -------------------------------------------------------------

    weather_wide = (
        frozen_weather[
            [
                "station",
                "year",
                "P_A8",
                "T_A8",
            ]
        ]
        .pivot(
            index="station",
            columns="year",
            values=[
                "P_A8",
                "T_A8",
            ],
        )
    )

    complete_both = (
        weather_wide
        .dropna()
        .copy()
    )

    delta_rows = []

    if len(complete_both):
        delta_p = (
            complete_both[
                ("P_A8", 2023)
            ]
            - complete_both[
                ("P_A8", 2022)
            ]
        )

        delta_t = (
            complete_both[
                ("T_A8", 2023)
            ]
            - complete_both[
                ("T_A8", 2022)
            ]
        )

        ff = pd.read_csv(
            FF10_IN
        )

        ff = ff.loc[
            ff[
                "station"
            ].isin(
                complete_both.index
            ),
            [
                "station",
                "year",
                "ff10_anomaly_2010_2021",
            ],
        ]

        ff_wide = ff.pivot(
            index="station",
            columns="year",
            values="ff10_anomaly_2010_2021",
        )

        common = (
            complete_both.index
            .intersection(
                ff_wide.index
            )
        )

        if len(common) != len(
            complete_both
        ):
            raise AssertionError(
                "Weather-complete frozen wells do not all "
                "have frozen FF10 exposure."
            )

        delta_ff = (
            ff_wide.loc[
                common,
                2023,
            ]
            - ff_wide.loc[
                common,
                2022,
            ]
        )

        delta_p = (
            delta_p.loc[
                common
            ]
        )

        delta_t = (
            delta_t.loc[
                common
            ]
        )

        delta_rows.append(
            {
                "weather_complete_repeated_wells_n":
                    len(common),

                "delta_P_A8_mean":
                    float(
                        delta_p.mean()
                    ),
                "delta_P_A8_sd":
                    float(
                        delta_p.std()
                    ),
                "delta_P_A8_min":
                    float(
                        delta_p.min()
                    ),
                "delta_P_A8_median":
                    float(
                        delta_p.median()
                    ),
                "delta_P_A8_max":
                    float(
                        delta_p.max()
                    ),

                "delta_T_A8_mean":
                    float(
                        delta_t.mean()
                    ),
                "delta_T_A8_sd":
                    float(
                        delta_t.std()
                    ),
                "delta_T_A8_min":
                    float(
                        delta_t.min()
                    ),
                "delta_T_A8_median":
                    float(
                        delta_t.median()
                    ),
                "delta_T_A8_max":
                    float(
                        delta_t.max()
                    ),

                "corr_delta_ff10_delta_P_A8":
                    float(
                        delta_ff.corr(
                            delta_p
                        )
                    ),
                "corr_delta_ff10_delta_T_A8":
                    float(
                        delta_ff.corr(
                            delta_t
                        )
                    ),
                "corr_delta_P_A8_delta_T_A8":
                    float(
                        delta_p.corr(
                            delta_t
                        )
                    ),
            }
        )

    delta_qa = pd.DataFrame(
        delta_rows
    )

    delta_qa.to_csv(
        DELTA_QA_OUT,
        index=False,
    )

    print(
        "POST-2021 WEATHER EXTENSION COMPLETE"
    )
    print("")

    print(
        "Frozen-sample weather completeness:"
    )
    print(
        completeness.to_string(
            index=False
        )
    )
    print("")

    print(
        "Frozen-sample weather-change QA:"
    )

    if len(delta_qa):
        print(
            delta_qa.to_string(
                index=False
            )
        )
    else:
        print(
            "No wells with complete weather in both years."
        )

    print("")
    print(
        "No groundwater observation table was read."
    )
    print(
        "No groundwater depth was inspected."
    )
    print(
        "No groundwater association was calculated."
    )
    print(
        "No regression was fitted."
    )
    print("")
    print(
        f"Wrote: {MONTHLY_OUT}"
    )
    print(
        f"Wrote: {WELL_WEATHER_OUT}"
    )
    print(
        f"Wrote: {REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {COMPLETENESS_QA_OUT}"
    )
    print(
        f"Wrote: {DELTA_QA_OUT}"
    )
    print(
        f"Wrote: {PROVENANCE_QA_OUT}"
    )


if __name__ == "__main__":
    main()



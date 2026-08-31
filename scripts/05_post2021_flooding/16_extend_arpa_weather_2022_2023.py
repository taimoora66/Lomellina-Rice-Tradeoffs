"""Extend the frozen ARPA Lombardia weather pipeline through 2025.

Scientific role
---------------
This stage extends the historically established meteorological controls
without reading groundwater observations or fitting any groundwater model.

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

Integrity gates
---------------
1. Reproduce frozen 2008-2021 weather_sensor_monthly.csv.
2. Reproduce the previously frozen 2008-2023 weather extension before
   accepting 2024-2025.
3. Reproduce the previously frozen 2022-2023 37-well weather panel before
   accepting 2024-2025.

No groundwater observation table is read.
No groundwater depth is inspected.
No flooding exposure is merged.
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

PREVIOUS_MONTHLY_IN = (
    POST_DIR
    / "weather_sensor_monthly_2008_2023.csv"
)

PREVIOUS_WELL_WEATHER_IN = (
    POST_DIR
    / "well_weather_A8_2022_2023.csv"
)

MONTHLY_OUT = (
    POST_DIR
    / "weather_sensor_monthly_2008_2025.csv"
)

WELL_WEATHER_OUT = (
    POST_DIR
    / "well_weather_A8_2022_2025.csv"
)

HIST_REPRO_QA_OUT = (
    QA_DIR
    / "post2021_weather_historical_reproduction_qa.csv"
)

PRE2024_MONTHLY_REPRO_QA_OUT = (
    QA_DIR
    / "post2021_weather_2008_2023_reproduction_qa.csv"
)

PRE2024_WELL_REPRO_QA_OUT = (
    QA_DIR
    / "post2021_weather_well_panel_2022_2023_reproduction_qa.csv"
)

COMPLETENESS_QA_OUT = (
    QA_DIR
    / "post2021_weather_all_iss_completeness_2022_2025.csv"
)

PROVENANCE_QA_OUT = (
    QA_DIR
    / "post2021_weather_source_provenance_2024_2025.csv"
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

NEW_JOBS = [
    (
        "precip_2024_2025",
        PRECIP_DATASET,
        2024,
        2025,
        PRECIP_SENSORS,
    ),
    (
        "temp_2024_2025",
        TEMP_DATASET,
        2024,
        2025,
        TEMP_SENSORS,
    ),
]

FILES = {
    "precip": [
        "precip_2008_2010.csv",
        "precip_2011_2020.csv",
        "precip_2021.csv",
        "precip_2022_2023.csv",
        "precip_2024_2025.csv",
    ],
    "temp": [
        "temp_2008_2010.csv",
        "temp_2011_2020.csv",
        "temp_2021.csv",
        "temp_2022_2023.csv",
        "temp_2024_2025.csv",
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
PREVIOUS_END_YEAR = 2023
END_YEAR = 2025

POST_YEARS = (2022, 2023, 2024, 2025)

EXPECTED_ISS_WELLS = 37

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
    """Exact acquisition architecture used by the historical downloader."""

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

    audit = pd.read_csv(
        path,
        usecols=[
            "idsensore",
            "data",
        ],
    )

    audit["data"] = pd.to_datetime(
        audit["data"],
        errors="raise",
    )

    observed_years = sorted(
        audit["data"]
        .dt.year
        .unique()
        .tolist()
    )

    expected_years = list(
        range(
            y0,
            y1 + 1,
        )
    )

    if observed_years != expected_years:
        raise AssertionError(
            f"{name}: downloaded years {observed_years}; "
            f"expected {expected_years}."
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
        "observed_date_min":
            audit["data"].min().isoformat(),
        "observed_date_max":
            audit["data"].max().isoformat(),
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

    observed_years = sorted(
        audit["data"]
        .dt.year
        .unique()
        .tolist()
    )

    expected_years = list(
        range(
            y0,
            y1 + 1,
        )
    )

    if observed_years != expected_years:
        raise AssertionError(
            f"{name}: existing raw file covers years "
            f"{observed_years}; expected {expected_years}. "
            "Delete the stale local file and rerun to reacquire."
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
        "observed_date_min":
            audit["data"].min().isoformat(),
        "observed_date_max":
            audit["data"].max().isoformat(),
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


def compare_tables(
    generated: pd.DataFrame,
    frozen: pd.DataFrame,
    key: list[str],
    label: str,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pd.DataFrame:
    """Compare all common columns over an exact key universe."""

    g = generated.copy()
    f = frozen.copy()

    if start_year is not None:
        g = g.loc[
            g["year"] >= start_year
        ].copy()
        f = f.loc[
            f["year"] >= start_year
        ].copy()

    if end_year is not None:
        g = g.loc[
            g["year"] <= end_year
        ].copy()
        f = f.loc[
            f["year"] <= end_year
        ].copy()

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

    g_key = g[key].copy()
    f_key = f[key].copy()

    for col in key:
        if col in {"variable", "station"}:
            g_key[col] = g_key[col].astype(str)
            f_key[col] = f_key[col].astype(str)
        else:
            g_key[col] = pd.to_numeric(
                g_key[col],
                errors="raise",
            ).astype("int64")

            f_key[col] = pd.to_numeric(
                f_key[col],
                errors="raise",
            ).astype("int64")

    if not g_key.equals(f_key):
        raise AssertionError(
            f"{label}: key values do not reproduce."
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


def build_well_weather(
    monthly_all: pd.DataFrame,
    gw_meta: pd.DataFrame,
    weather_meta: pd.DataFrame,
) -> pd.DataFrame:
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
        .sort_values("station")
        .reset_index(drop=True)
    )

    if len(wells) != EXPECTED_ISS_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_WELLS} ISS wells; "
            f"found {len(wells)}."
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

    return p.sort_values(
        [
            "station",
            "year",
        ]
    ).reset_index(drop=True)


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

    if not PREVIOUS_MONTHLY_IN.exists():
        raise FileNotFoundError(
            "Frozen previous weather monthly extension is required "
            "for regression QA:\n"
            f"{PREVIOUS_MONTHLY_IN}"
        )

    if not PREVIOUS_WELL_WEATHER_IN.exists():
        raise FileNotFoundError(
            "Frozen previous 2022-2023 well-weather panel is required "
            "for regression QA:\n"
            f"{PREVIOUS_WELL_WEATHER_IN}"
        )

    # -------------------------------------------------------------
    # 1. Acquire only new 2024-2025 raw weather.
    # -------------------------------------------------------------

    provenance = []

    for job in NEW_JOBS:
        provenance.append(
            acquire_or_reuse(*job)
        )

    provenance_df = pd.DataFrame(
        provenance
    )

    # -------------------------------------------------------------
    # 2. Rebuild sensor-month weather 2008-2025 using exact frozen
    #    validation definitions.
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

    historical_repro_qa = compare_tables(
        generated=monthly_all,
        frozen=historical,
        key=[
            "variable",
            "idsensore",
            "year",
            "month",
        ],
        label="frozen_2008_2021_weather_monthly",
        start_year=START_YEAR,
        end_year=HIST_END_YEAR,
    )

    print("")
    print(
        "Historical weather reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(historical_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    previous_monthly = pd.read_csv(
        PREVIOUS_MONTHLY_IN
    )

    pre2024_monthly_repro_qa = compare_tables(
        generated=monthly_all,
        frozen=previous_monthly,
        key=[
            "variable",
            "idsensore",
            "year",
            "month",
        ],
        label="frozen_2008_2023_weather_monthly",
        start_year=START_YEAR,
        end_year=PREVIOUS_END_YEAR,
    )

    print(
        "Previous 2008-2023 weather extension reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(pre2024_monthly_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    # -------------------------------------------------------------
    # 3. Build weather controls for all 37 frozen ISS wells.
    # -------------------------------------------------------------

    gw_meta = pd.read_csv(
        GW_META_IN
    )

    weather_meta = pd.read_csv(
        WX_META_IN
    )

    well_weather = build_well_weather(
        monthly_all,
        gw_meta,
        weather_meta,
    )

    expected_rows = (
        EXPECTED_ISS_WELLS
        * len(POST_YEARS)
    )

    if len(well_weather) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} well-years in 2022-2025 "
            f"weather panel; found {len(well_weather)}."
        )

    previous_well_weather = pd.read_csv(
        PREVIOUS_WELL_WEATHER_IN
    )

    pre2024_well_repro_qa = compare_tables(
        generated=well_weather,
        frozen=previous_well_weather,
        key=[
            "station",
            "year",
        ],
        label="frozen_2022_2023_well_weather",
        start_year=2022,
        end_year=2023,
    )

    print(
        "Previous 2022-2023 well-weather panel reproduction: PASS"
    )
    print(
        "  columns reproduced:",
        len(pre2024_well_repro_qa),
    )
    print(
        "  mismatches: 0"
    )
    print("")

    # -------------------------------------------------------------
    # 4. Weather completeness counts for all 37 ISS wells.
    # -------------------------------------------------------------

    completeness_rows = []

    for year in POST_YEARS:
        y = well_weather.loc[
            well_weather[
                "year"
            ].eq(year)
        ]

        completeness_rows.append(
            {
                "year": year,
                "iss_wells_n":
                    EXPECTED_ISS_WELLS,
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

    # -------------------------------------------------------------
    # 5. Save only after all integrity gates pass.
    # -------------------------------------------------------------

    monthly_all.to_csv(
        MONTHLY_OUT,
        index=False,
    )

    well_weather.to_csv(
        WELL_WEATHER_OUT,
        index=False,
    )

    historical_repro_qa.drop(
        columns=["comparison"],
    ).to_csv(
        HIST_REPRO_QA_OUT,
        index=False,
    )

    pre2024_monthly_repro_qa.to_csv(
        PRE2024_MONTHLY_REPRO_QA_OUT,
        index=False,
    )

    pre2024_well_repro_qa.to_csv(
        PRE2024_WELL_REPRO_QA_OUT,
        index=False,
    )

    completeness.to_csv(
        COMPLETENESS_QA_OUT,
        index=False,
    )

    provenance_df.to_csv(
        PROVENANCE_QA_OUT,
        index=False,
    )

    # -------------------------------------------------------------
    # 6. Console output: structure and availability only.
    # -------------------------------------------------------------

    print("=" * 72)
    print(
        "POST-2021 WEATHER EXTENSION THROUGH 2025"
    )
    print("=" * 72)
    print("")

    print(
        "New open-data acquisitions:"
    )
    print(
        provenance_df[
            [
                "name",
                "dataset_id",
                "start_year",
                "end_year",
                "rows_downloaded",
                "observed_date_min",
                "observed_date_max",
                "sha256",
            ]
        ].to_string(
            index=False
        )
    )

    print("")
    print(
        "ALL-ISS WEATHER COMPLETENESS - COUNTS ONLY"
    )
    print(
        completeness.to_string(
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
        "No flooding exposure was merged."
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
        f"Wrote: {HIST_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {PRE2024_MONTHLY_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {PRE2024_WELL_REPRO_QA_OUT}"
    )
    print(
        f"Wrote: {COMPLETENESS_QA_OUT}"
    )
    print(
        f"Wrote: {PROVENANCE_QA_OUT}"
    )

    print("")
    print("DONE")


if __name__ == "__main__":
    main()

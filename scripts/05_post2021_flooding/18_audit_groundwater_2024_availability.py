from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

RAW_2024 = (
    ROOT
    / "data"
    / "raw"
    / "arpa"
    / "groundwater_pavia_2024"
    / "pavia_groundwater_quantitative_2024_update_2025-10-14.xlsx"
)

HISTORICAL = (
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

OUTDIR.mkdir(parents=True, exist_ok=True)

STATION_OUT = OUTDIR / "groundwater_2024_availability_by_station.csv"
SUMMARY_OUT = OUTDIR / "groundwater_2024_availability_summary.csv"


# ------------------------------------------------------------
# Load authoritative October 2025 revision
# ------------------------------------------------------------

d = pd.read_excel(
    RAW_2024,
    sheet_name="2024",
)

rename = {
    "CODICE": "station",
    "PROVINCIA": "province",
    "COMUNE": "commune",
    "Soggiacenza m da Qr": "gw_depth_m",
    "Data": "date",
    "ANNO": "year",
    "X_WGS84": "utm_e",
    "Y_WGS84": "utm_n",
    "QUOTA_MISURA_m s.l.m. (Qr)": "measuring_point_elev_masl",
    "PROFONDITA' m": "well_depth_m",
    "FILTRI_TOP m": "screen_top_m",
    "FILTRI_BOT m": "screen_bottom_m",
    "GroundWater Body (GWB_2015)": "gwb",
}

missing = [
    c for c in rename
    if c not in d.columns
]

if missing:
    raise RuntimeError(
        f"Missing expected 2024 columns: {missing}"
    )

d = d.rename(columns=rename).copy()

d["date"] = pd.to_datetime(
    d["date"],
    errors="raise",
)

d["year"] = pd.to_numeric(
    d["year"],
    errors="raise",
).astype(int)

d["gw_depth_m"] = pd.to_numeric(
    d["gw_depth_m"],
    errors="coerce",
)

if not d["year"].eq(2024).all():
    raise RuntimeError(
        "Authoritative workbook contains rows outside 2024."
    )

if d.duplicated(["station", "date"]).any():
    dup = d.loc[
        d.duplicated(
            ["station", "date"],
            keep=False,
        )
    ].sort_values(["station", "date"])

    raise RuntimeError(
        "Duplicate station-date rows found:\n"
        + dup.to_string(index=False)
    )

d["month"] = d["date"].dt.month

d["aquifer_group"] = (
    d["gwb"]
    .astype(str)
    .str.extract(
        r"\b(ISS|ISI|ISP)\b",
        expand=False,
    )
    .fillna("OTHER")
)


# ------------------------------------------------------------
# Historical ISS universe
# ------------------------------------------------------------

h = pd.read_csv(HISTORICAL)

hist_iss = (
    h.loc[
        h["aquifer_group"].eq("ISS"),
        [
            "station",
            "commune",
            "utm_e",
            "utm_n",
            "measuring_point_elev_masl",
            "well_depth_m",
            "gwb",
        ],
    ]
    .drop_duplicates("station")
    .copy()
)

hist_iss_stations = set(
    hist_iss["station"]
)

if len(hist_iss_stations) != 37:
    raise RuntimeError(
        "Expected historical ISS universe of 37 wells; "
        f"found {len(hist_iss_stations)}."
    )


# ------------------------------------------------------------
# Station-level 2024 availability
# ------------------------------------------------------------

rows = []

for station, g in d.groupby(
    "station",
    sort=True,
):

    g = g.sort_values("date").copy()

    aquifers = sorted(
        g["aquifer_group"]
        .dropna()
        .unique()
        .tolist()
    )

    if len(aquifers) != 1:
        raise RuntimeError(
            f"Inconsistent aquifer classification for {station}: "
            f"{aquifers}"
        )

    aquifer = aquifers[0]

    janfeb = g[
        g["month"].isin([1, 2])
        & g["gw_depth_m"].notna()
    ]

    august = g[
        g["month"].eq(8)
        & g["gw_depth_m"].notna()
    ]

    valid = g[
        g["gw_depth_m"].notna()
    ]

    rows.append(
        {
            "station": station,
            "province": g["province"].iloc[0],
            "commune": g["commune"].iloc[0],
            "aquifer_group": aquifer,
            "gwb": g["gwb"].iloc[0],

            "obs_n": int(len(g)),
            "valid_gw_n": int(len(valid)),

            "janfeb_n": int(len(janfeb)),
            "aug_n": int(len(august)),

            "has_janfeb": bool(len(janfeb) > 0),
            "has_aug": bool(len(august) > 0),

            "complete_pre_plus_aug": bool(
                len(janfeb) > 0
                and len(august) > 0
            ),

            "first_obs_date": (
                valid["date"].min()
                if len(valid)
                else pd.NaT
            ),

            "last_obs_date": (
                valid["date"].max()
                if len(valid)
                else pd.NaT
            ),

            "janfeb_last_date": (
                janfeb["date"].max()
                if len(janfeb)
                else pd.NaT
            ),

            "aug_first_date": (
                august["date"].min()
                if len(august)
                else pd.NaT
            ),

            "aug_last_date": (
                august["date"].max()
                if len(august)
                else pd.NaT
            ),

            "historical_iss_well": bool(
                station in hist_iss_stations
            ),

            "new_vs_historical_iss": bool(
                aquifer == "ISS"
                and station not in hist_iss_stations
            ),

            "utm_e": g["utm_e"].iloc[0],
            "utm_n": g["utm_n"].iloc[0],
        }
    )

station = pd.DataFrame(rows)


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

def count(mask):
    return int(mask.sum())


is_iss = station["aquifer_group"].eq("ISS")
is_hist = station["historical_iss_well"]
is_new_iss = station["new_vs_historical_iss"]
has_pre = station["has_janfeb"]
has_aug = station["has_aug"]
complete = station["complete_pre_plus_aug"]


summary_rows = [
    ("all_2024_stations", len(station)),
    ("all_2024_observations", len(d)),
    ("iss_stations", count(is_iss)),
    ("historical_iss_stations_present", count(is_hist)),
    ("new_iss_stations", count(is_new_iss)),

    ("iss_with_janfeb", count(is_iss & has_pre)),
    ("iss_with_august", count(is_iss & has_aug)),
    ("iss_complete_pre_plus_aug", count(is_iss & complete)),

    (
        "historical_iss_with_janfeb",
        count(is_hist & has_pre),
    ),
    (
        "historical_iss_with_august",
        count(is_hist & has_aug),
    ),
    (
        "historical_iss_complete_pre_plus_aug",
        count(is_hist & complete),
    ),

    (
        "new_iss_complete_pre_plus_aug",
        count(is_new_iss & complete),
    ),
]

summary = pd.DataFrame(
    summary_rows,
    columns=["metric", "value"],
)


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

station.to_csv(
    STATION_OUT,
    index=False,
)

summary.to_csv(
    SUMMARY_OUT,
    index=False,
)


# ------------------------------------------------------------
# Console report
# ------------------------------------------------------------

print()
print("=" * 70)
print("ARPA PAVIA 2024 GROUNDWATER AVAILABILITY AUDIT")
print("=" * 70)

print()
print(summary.to_string(index=False))

print()
print("=== COMPLETE ISS WELLS ===")

complete_iss = station.loc[
    is_iss & complete,
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
].sort_values("station")

if len(complete_iss):
    print(
        complete_iss.to_string(
            index=False
        )
    )
else:
    print("None.")

print()
print("=== HISTORICAL ISS WELLS PRESENT BUT INCOMPLETE ===")

incomplete_hist = station.loc[
    is_hist & ~complete,
    [
        "station",
        "commune",
        "obs_n",
        "janfeb_n",
        "aug_n",
        "first_obs_date",
        "last_obs_date",
    ],
].sort_values("station")

if len(incomplete_hist):
    print(
        incomplete_hist.to_string(
            index=False
        )
    )
else:
    print("None.")

print()
print("Outputs:")
print(STATION_OUT)
print(SUMMARY_OUT)

print()
print("NO FLOODING-GROUNDWATER MODEL FIT.")
print("DONE")
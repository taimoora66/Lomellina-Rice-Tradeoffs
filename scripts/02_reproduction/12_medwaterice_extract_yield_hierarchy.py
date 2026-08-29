from pathlib import Path
import re

import pandas as pd


ROOT = Path(".")
RAW = ROOT / "data" / "raw" / "MEDWATERICE"
OUT = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"

OUT.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)


files = (
    list((RAW / "CS1_Lomellina_2019").glob("*.xlsx"))
    + list((RAW / "CS1_Lomellina_2020").glob("*.xlsx"))
)


records = []


def treatment_from_name(name):
    if "_AWD_" in name:
        return "AWD"
    if "_DFL_" in name:
        return "DFL"
    if "_WFL_" in name:
        return "WFL"
    return None


def year_from_name(name):
    if "2019" in name:
        return 2019
    if "2020" in name:
        return 2020
    return None


# ------------------------------------------------------------
# Known location-to-agronomic-treatment mappings
# from workbook metadata
# ------------------------------------------------------------

maps = {

    (2019, "WFL"): {
        "0 N": [2, 6, 10, 14],
        "100 N": [3, 7, 11, 15],
        "160 N + FUNG": [4, 8, 12, 16],
        "160 N + NO FUNG": [1, 5, 9, 13],
    },

    (2019, "AWD"): {
        "0 N": [18, 22, 26, 30],
        "100 N": [19, 23, 27, 31],
        "160 N + FUNG": [20, 24, 28, 32],
        "160 N + NO FUNG": [17, 21, 25, 29],
    },

    (2019, "DFL"): {
        "0 N": [34, 38, 42, 46],
        "100 N": [35, 39, 43, 47],
        "160 N + FUNG": [36, 40, 44, 48],
        "160 N + NO FUNG": [33, 37, 41, 45],
    },

    (2020, "AWD"): {
        "0 N": [2, 6, 10, 14],
        "100 N": [3, 7, 11, 15],
        "160 N + FUNG": [4, 8, 12, 16],
        "160 N + NO FUNG": [1, 5, 9, 13],
        "160 N + NO HERB": [49, 50, 51, 52],
    },

    (2020, "DFL"): {
        "0 N": [34, 38, 42, 46],
        "100 N": [35, 39, 43, 47],
        "160 N + FUNG": [36, 40, 44, 48],
        "160 N + NO FUNG": [33, 37, 41, 45],
        "160 N + NO HERB": [57, 58, 59, 60],
    },

    (2020, "WFL"): {
        "0 N": [18, 22, 26, 30],
        "100 N": [20, 23, 27, 31],
        "160 N + FUNG": [19, 24, 28, 32],
        "160 N + NO FUNG": [17, 21, 25, 29],
        "160 N + NO HERB": [53, 54, 55, 56],
    },
}


# ------------------------------------------------------------
# Physical plot mapping
#
# 2019:
# WFL 1-8 / 9-16
# AWD 17-24 / 25-32
# DFL 33-40 / 41-48
#
# 2020 same original blocks, with two new NO-HERB
# subplots per plot.
# ------------------------------------------------------------

def assign_plot(year, irrigation, location):

    if irrigation == "WFL":

        if year == 2019:
            return 1 if 1 <= location <= 8 else 2

        if year == 2020:
            if 17 <= location <= 24:
                return 1
            if 25 <= location <= 32:
                return 2
            if location in [53, 54]:
                return 1
            if location in [55, 56]:
                return 2

    elif irrigation == "AWD":

        if year == 2019:
            return 1 if 17 <= location <= 24 else 2

        if year == 2020:
            if 1 <= location <= 8:
                return 1
            if 9 <= location <= 16:
                return 2
            if location in [49, 50]:
                return 1
            if location in [51, 52]:
                return 2

    elif irrigation == "DFL":

        if 33 <= location <= 40:
            return 1
        if 41 <= location <= 48:
            return 2

        if year == 2020:
            if location in [57, 58]:
                return 1
            if location in [59, 60]:
                return 2

    return None


def agronomic_group(year, irrigation, location):

    for group, locations in maps[(year, irrigation)].items():

        if location in locations:
            return group

    return None


# ------------------------------------------------------------
# Extract
# ------------------------------------------------------------

for path in files:

    year = year_from_name(path.name)
    irrigation = treatment_from_name(path.name)

    if year is None or irrigation is None:
        continue

    df = pd.read_excel(
        path,
        sheet_name="Yield+product",
        header=1
    )

    location_col = df.columns[2]
    yield_col = df.columns[3]

    for _, row in df.iterrows():

        try:
            location = int(float(row[location_col]))
        except (TypeError, ValueError):
            continue

        try:
            yield_t_ha = float(row[yield_col])
        except (TypeError, ValueError):
            continue

        group = agronomic_group(
            year,
            irrigation,
            location
        )

        plot = assign_plot(
            year,
            irrigation,
            location
        )

        records.append(
            {
                "year": year,
                "irrigation": irrigation,
                "plot": plot,
                "location": location,
                "agronomic_treatment": group,
                "yield_t_ha_14pct": yield_t_ha,
                "source_workbook": path.name,
            }
        )


yield_df = pd.DataFrame(records)

yield_df = yield_df.sort_values(
    [
        "year",
        "irrigation",
        "plot",
        "location"
    ]
)

yield_df.to_csv(
    OUT /
    "MEDWATERICE_CS1_yield_hierarchy.csv",
    index=False
)


# ------------------------------------------------------------
# QA
# ------------------------------------------------------------

qa = (
    yield_df
    .groupby(
        [
            "year",
            "irrigation",
            "plot",
            "agronomic_treatment"
        ],
        dropna=False
    )
    .agg(
        n_subplots=("yield_t_ha_14pct", "size"),
        mean_yield=("yield_t_ha_14pct", "mean"),
        min_yield=("yield_t_ha_14pct", "min"),
        max_yield=("yield_t_ha_14pct", "max"),
    )
    .reset_index()
)

qa.to_csv(
    TABLES /
    "MEDWATERICE_yield_hierarchy_qa.csv",
    index=False
)


print()
print("=" * 110)
print("YIELD HIERARCHY QA")
print("=" * 110)

print(
    qa
    .round(3)
    .to_string(index=False)
)

print()
print("=" * 110)
print("TOTAL OBSERVATIONS")
print("=" * 110)

print(
    yield_df
    .groupby(["year", "irrigation"])
    .size()
    .to_string()
)

print()

missing = yield_df[
    yield_df["plot"].isna()
    | yield_df["agronomic_treatment"].isna()
]

print(
    "Rows with unresolved plot/agronomic assignment:",
    len(missing)
)

if len(missing):
    print(missing.to_string(index=False))


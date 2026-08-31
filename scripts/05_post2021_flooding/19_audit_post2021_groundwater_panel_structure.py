from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ANNUAL = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "groundwater_annual_measures_2008_2024.csv"
)

OUTDIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

WELL_OUT = OUTDIR / "groundwater_post2021_panel_structure_by_well.csv"
SUMMARY_OUT = OUTDIR / "groundwater_post2021_panel_structure_summary.csv"


# ------------------------------------------------------------
# Load annual groundwater measures
# ------------------------------------------------------------

d = pd.read_csv(ANNUAL)

required = [
    "station",
    "year",
    "aquifer_group",
    "gw_pre_last_janfeb_m",
    "gw_aug_mean_m",
]

missing = [
    c for c in required
    if c not in d.columns
]

if missing:
    raise RuntimeError(
        f"Missing columns: {missing}"
    )


# ------------------------------------------------------------
# Restrict to frozen historical ISS universe / post-2021 years
# ------------------------------------------------------------

p = d[
    d["year"].isin([2022, 2023, 2024])
    & d["aquifer_group"].eq("ISS")
].copy()

p["complete"] = (
    p["gw_pre_last_janfeb_m"].notna()
    & p["gw_aug_mean_m"].notna()
)


# ------------------------------------------------------------
# Wide well-year completeness
# ------------------------------------------------------------

wide = (
    p.pivot_table(
        index="station",
        columns="year",
        values="complete",
        aggfunc="first",
        fill_value=False,
    )
    .reindex(
        columns=[2022, 2023, 2024],
        fill_value=False,
    )
    .reset_index()
)

wide.columns = [
    "station",
    "complete_2022",
    "complete_2023",
    "complete_2024",
]

for c in [
    "complete_2022",
    "complete_2023",
    "complete_2024",
]:
    wide[c] = wide[c].astype(bool)

wide["complete_years_n"] = (
    wide[
        [
            "complete_2022",
            "complete_2023",
            "complete_2024",
        ]
    ]
    .sum(axis=1)
    .astype(int)
)

wide["complete_all_3"] = (
    wide["complete_years_n"] == 3
)

wide["complete_at_least_2"] = (
    wide["complete_years_n"] >= 2
)

wide["complete_exactly_1"] = (
    wide["complete_years_n"] == 1
)

wide["complete_2022_2023"] = (
    wide["complete_2022"]
    & wide["complete_2023"]
)

wide["complete_2023_2024"] = (
    wide["complete_2023"]
    & wide["complete_2024"]
)

wide["complete_2022_2024"] = (
    wide["complete_2022"]
    & wide["complete_2024"]
)

wide.to_csv(
    WELL_OUT,
    index=False,
)


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

def n(mask):
    return int(mask.sum())


summary = pd.DataFrame(
    [
        ("complete_2022", n(wide["complete_2022"])),
        ("complete_2023", n(wide["complete_2023"])),
        ("complete_2024", n(wide["complete_2024"])),
        ("complete_all_3_years", n(wide["complete_all_3"])),
        ("complete_at_least_2_years", n(wide["complete_at_least_2"])),
        ("complete_exactly_1_year", n(wide["complete_exactly_1"])),
        ("complete_2022_2023", n(wide["complete_2022_2023"])),
        ("complete_2023_2024", n(wide["complete_2023_2024"])),
        ("complete_2022_2024", n(wide["complete_2022_2024"])),
    ],
    columns=["metric", "value"],
)

summary.to_csv(
    SUMMARY_OUT,
    index=False,
)


# ------------------------------------------------------------
# Console
# ------------------------------------------------------------

print()
print("=" * 70)
print("POST-2021 GROUNDWATER PANEL STRUCTURE AUDIT")
print("=" * 70)

print()
print(summary.to_string(index=False))

print()
print("=== WELLS COMPLETE ALL 3 YEARS ===")

z = wide.loc[
    wide["complete_all_3"],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_years_n",
    ],
].sort_values("station")

if len(z):
    print(z.to_string(index=False))
else:
    print("None.")

print()
print("=== WELLS COMPLETE AT LEAST 2 YEARS ===")

z2 = wide.loc[
    wide["complete_at_least_2"],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_years_n",
    ],
].sort_values(
    ["complete_years_n", "station"],
    ascending=[False, True],
)

if len(z2):
    print(z2.to_string(index=False))
else:
    print("None.")

print()
print("Outputs:")
print(WELL_OUT)
print(SUMMARY_OUT)

print()
print("NO EFFECT MODEL FIT.")
print("DONE")
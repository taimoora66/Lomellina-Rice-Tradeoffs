from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ANNUAL = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "groundwater_annual_measures_2008_2025.csv"
)

OUTDIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

WELL_OUT = (
    OUTDIR
    / "groundwater_post2021_panel_structure_by_well_2022_2025.csv"
)

SUMMARY_OUT = (
    OUTDIR
    / "groundwater_post2021_panel_structure_summary_2022_2025.csv"
)

PATTERN_OUT = (
    OUTDIR
    / "groundwater_post2021_panel_completeness_patterns_2022_2025.csv"
)

TRANSITION_OUT = (
    OUTDIR
    / "groundwater_post2021_panel_year_transitions_2022_2025.csv"
)


YEARS = [2022, 2023, 2024, 2025]

EXPECTED_ISS_STATIONS = 37

EXPECTED_COMPLETE_BY_YEAR = {
    2022: 17,
    2023: 13,
    2024: 15,
    2025: 17,
}

EXPECTED_EXACTLY_2_YEARS = 4
EXPECTED_EXACTLY_3_YEARS = 2
EXPECTED_ALL_4_YEARS = 12


# ------------------------------------------------------------
# Load annual groundwater measures
# ------------------------------------------------------------

if not ANNUAL.exists():
    raise FileNotFoundError(
        f"Annual groundwater artifact not found: {ANNUAL}"
    )

d = pd.read_csv(ANNUAL)

required = [
    "station",
    "year",
    "aquifer_group",
    "gw_pre_last_janfeb_m",
    "gw_aug_mean_m",
    "gw_aug_nearest_aug23_m",
]

missing = [
    c
    for c in required
    if c not in d.columns
]

if missing:
    raise RuntimeError(
        f"Missing columns: {missing}"
    )


# ------------------------------------------------------------
# Basic integrity
# ------------------------------------------------------------

if d.duplicated(
    [
        "station",
        "year",
    ]
).any():
    bad = d.loc[
        d.duplicated(
            [
                "station",
                "year",
            ],
            keep=False,
        )
    ].sort_values(
        [
            "station",
            "year",
        ]
    )

    raise AssertionError(
        "Duplicate station-year rows in annual artifact:\n"
        + bad.to_string(index=False)
    )


# ------------------------------------------------------------
# Restrict to frozen historical ISS universe / post-2021 years
# ------------------------------------------------------------

p = d.loc[
    d["year"].isin(YEARS)
    & d["aquifer_group"].eq("ISS")
].copy()

iss_stations = sorted(
    p["station"]
    .dropna()
    .unique()
    .tolist()
)

if len(iss_stations) != EXPECTED_ISS_STATIONS:
    raise AssertionError(
        f"Expected frozen {EXPECTED_ISS_STATIONS}-well ISS universe; "
        f"found {len(iss_stations)}."
    )

expected_rows = (
    EXPECTED_ISS_STATIONS
    * len(YEARS)
)

if len(p) != expected_rows:
    raise AssertionError(
        f"Expected {expected_rows} ISS station-years across "
        f"{YEARS}; found {len(p)}."
    )


# ------------------------------------------------------------
# Frozen groundwater completeness definition
# ------------------------------------------------------------
#
# Primary panel completeness remains exactly:
#   antecedent Jan-Feb groundwater available
#   AND August mean groundwater available.
#
# We separately audit the Aug-23-nearest measure to verify that
# it produces the same repeated-sample membership in these years.
# ------------------------------------------------------------

p["complete_augmean"] = (
    p["gw_pre_last_janfeb_m"].notna()
    & p["gw_aug_mean_m"].notna()
)

p["complete_aug23"] = (
    p["gw_pre_last_janfeb_m"].notna()
    & p["gw_aug_nearest_aug23_m"].notna()
)

if not p[
    "complete_augmean"
].equals(
    p["complete_aug23"]
):
    bad = p.loc[
        p["complete_augmean"]
        != p["complete_aug23"],
        [
            "station",
            "year",
            "complete_augmean",
            "complete_aug23",
        ],
    ].sort_values(
        [
            "station",
            "year",
        ]
    )

    raise AssertionError(
        "Aug-mean and Aug-23 groundwater completeness "
        "do not define identical station-year membership:\n"
        + bad.to_string(index=False)
    )

p["complete"] = p[
    "complete_augmean"
]


# ------------------------------------------------------------
# Independent per-year count QA
# ------------------------------------------------------------

for year, expected in EXPECTED_COMPLETE_BY_YEAR.items():
    observed = int(
        p.loc[
            p["year"].eq(year),
            "complete",
        ].sum()
    )

    if observed != expected:
        raise AssertionError(
            f"{year} complete-well count mismatch: "
            f"observed={observed}, expected={expected}."
        )


# ------------------------------------------------------------
# Wide well-year completeness
# ------------------------------------------------------------

wide = (
    p.pivot(
        index="station",
        columns="year",
        values="complete",
    )
    .reindex(
        index=iss_stations,
        columns=YEARS,
    )
    .fillna(False)
    .reset_index()
)

wide.columns = [
    "station",
    "complete_2022",
    "complete_2023",
    "complete_2024",
    "complete_2025",
]

complete_cols = [
    "complete_2022",
    "complete_2023",
    "complete_2024",
    "complete_2025",
]

for c in complete_cols:
    wide[c] = wide[c].astype(bool)

wide["complete_years_n"] = (
    wide[
        complete_cols
    ]
    .sum(axis=1)
    .astype(int)
)

wide["complete_all_4"] = (
    wide["complete_years_n"] == 4
)

wide["complete_at_least_3"] = (
    wide["complete_years_n"] >= 3
)

wide["complete_at_least_2"] = (
    wide["complete_years_n"] >= 2
)

wide["complete_exactly_3"] = (
    wide["complete_years_n"] == 3
)

wide["complete_exactly_2"] = (
    wide["complete_years_n"] == 2
)

wide["complete_exactly_1"] = (
    wide["complete_years_n"] == 1
)

wide["complete_0"] = (
    wide["complete_years_n"] == 0
)


# ------------------------------------------------------------
# Exact year-pattern code
# ------------------------------------------------------------

def pattern_code(row):
    years = [
        str(year)
        for year in YEARS
        if bool(
            row[
                f"complete_{year}"
            ]
        )
    ]

    if not years:
        return "none"

    return "_".join(years)


wide["complete_year_pattern"] = wide.apply(
    pattern_code,
    axis=1,
)


# ------------------------------------------------------------
# Pairwise intersections
# ------------------------------------------------------------

pair_columns = []

for i, year_a in enumerate(YEARS):
    for year_b in YEARS[
        i + 1:
    ]:
        col = (
            f"complete_{year_a}_{year_b}"
        )

        wide[col] = (
            wide[
                f"complete_{year_a}"
            ]
            & wide[
                f"complete_{year_b}"
            ]
        )

        pair_columns.append(
            (
                year_a,
                year_b,
                col,
            )
        )


# ------------------------------------------------------------
# Consecutive-year transitions
# ------------------------------------------------------------

transition_rows = []

for year_a, year_b in zip(
    YEARS[:-1],
    YEARS[1:],
):
    a = wide[
        f"complete_{year_a}"
    ]

    b = wide[
        f"complete_{year_b}"
    ]

    retained = (
        a
        & b
    )

    exits = (
        a
        & ~b
    )

    entries = (
        ~a
        & b
    )

    neither = (
        ~a
        & ~b
    )

    transition_rows.append(
        {
            "from_year": year_a,
            "to_year": year_b,
            "complete_from_n":
                int(a.sum()),
            "complete_to_n":
                int(b.sum()),
            "retained_complete_n":
                int(retained.sum()),
            "exited_complete_sample_n":
                int(exits.sum()),
            "entered_complete_sample_n":
                int(entries.sum()),
            "neither_year_complete_n":
                int(neither.sum()),
        }
    )

transitions = pd.DataFrame(
    transition_rows
)


# ------------------------------------------------------------
# Exact pattern summary
# ------------------------------------------------------------

patterns = (
    wide.groupby(
        "complete_year_pattern",
        dropna=False,
    )
    .size()
    .reset_index(
        name="stations_n"
    )
    .sort_values(
        [
            "stations_n",
            "complete_year_pattern",
        ],
        ascending=[
            False,
            True,
        ],
    )
    .reset_index(drop=True)
)


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

def n(mask):
    return int(
        mask.sum()
    )


summary_rows = []

for year in YEARS:
    summary_rows.append(
        (
            f"complete_{year}",
            n(
                wide[
                    f"complete_{year}"
                ]
            ),
        )
    )

summary_rows.extend(
    [
        (
            "complete_all_4_years",
            n(
                wide[
                    "complete_all_4"
                ]
            ),
        ),
        (
            "complete_at_least_3_years",
            n(
                wide[
                    "complete_at_least_3"
                ]
            ),
        ),
        (
            "complete_at_least_2_years",
            n(
                wide[
                    "complete_at_least_2"
                ]
            ),
        ),
        (
            "complete_exactly_3_years",
            n(
                wide[
                    "complete_exactly_3"
                ]
            ),
        ),
        (
            "complete_exactly_2_years",
            n(
                wide[
                    "complete_exactly_2"
                ]
            ),
        ),
        (
            "complete_exactly_1_year",
            n(
                wide[
                    "complete_exactly_1"
                ]
            ),
        ),
        (
            "complete_0_years",
            n(
                wide[
                    "complete_0"
                ]
            ),
        ),
    ]
)

for (
    year_a,
    year_b,
    col,
) in pair_columns:
    summary_rows.append(
        (
            f"complete_{year_a}_{year_b}",
            n(
                wide[
                    col
                ]
            ),
        )
    )

summary = pd.DataFrame(
    summary_rows,
    columns=[
        "metric",
        "value",
    ],
)


# ------------------------------------------------------------
# Aggregate regression QA against Stage 14
# ------------------------------------------------------------

observed_exactly_2 = n(
    wide[
        "complete_exactly_2"
    ]
)

observed_exactly_3 = n(
    wide[
        "complete_exactly_3"
    ]
)

observed_all_4 = n(
    wide[
        "complete_all_4"
    ]
)

if (
    observed_exactly_2
    != EXPECTED_EXACTLY_2_YEARS
):
    raise AssertionError(
        "Exactly-two-year completeness mismatch: "
        f"observed={observed_exactly_2}, "
        f"expected={EXPECTED_EXACTLY_2_YEARS}."
    )

if (
    observed_exactly_3
    != EXPECTED_EXACTLY_3_YEARS
):
    raise AssertionError(
        "Exactly-three-year completeness mismatch: "
        f"observed={observed_exactly_3}, "
        f"expected={EXPECTED_EXACTLY_3_YEARS}."
    )

if (
    observed_all_4
    != EXPECTED_ALL_4_YEARS
):
    raise AssertionError(
        "Four-year balanced-panel mismatch: "
        f"observed={observed_all_4}, "
        f"expected={EXPECTED_ALL_4_YEARS}."
    )


# ------------------------------------------------------------
# Save only after all QA passes
# ------------------------------------------------------------

wide.to_csv(
    WELL_OUT,
    index=False,
)

summary.to_csv(
    SUMMARY_OUT,
    index=False,
)

patterns.to_csv(
    PATTERN_OUT,
    index=False,
)

transitions.to_csv(
    TRANSITION_OUT,
    index=False,
)


# ------------------------------------------------------------
# Console
# ------------------------------------------------------------

print()
print("=" * 72)
print(
    "POST-2021 GROUNDWATER PANEL STRUCTURE AUDIT, 2022-2025"
)
print("=" * 72)

print()
print(
    "ANNUAL INPUT:"
)
print(
    ANNUAL
)

print()
print(
    "FROZEN ISS UNIVERSE:"
)
print(
    f"  stations: {len(wide)}"
)

print()
print(
    "PRIMARY COMPLETENESS:"
)
print(
    "  Jan-Feb antecedent groundwater + August mean groundwater"
)
print(
    "  Aug-23-nearest membership matches primary completeness: PASS"
)

print()
print(
    "=== SUMMARY ==="
)
print(
    summary.to_string(
        index=False
    )
)

print()
print(
    "=== EXACT COMPLETENESS PATTERNS ==="
)
print(
    patterns.to_string(
        index=False
    )
)

print()
print(
    "=== CONSECUTIVE-YEAR TRANSITIONS ==="
)
print(
    transitions.to_string(
        index=False
    )
)

print()
print(
    "=== WELLS COMPLETE ALL 4 YEARS ==="
)

z4 = wide.loc[
    wide[
        "complete_all_4"
    ],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_2025",
        "complete_years_n",
        "complete_year_pattern",
    ],
].sort_values(
    "station"
)

if len(z4):
    print(
        z4.to_string(
            index=False
        )
    )
else:
    print(
        "None."
    )

print()
print(
    "=== WELLS COMPLETE EXACTLY 3 YEARS ==="
)

z3 = wide.loc[
    wide[
        "complete_exactly_3"
    ],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_2025",
        "complete_years_n",
        "complete_year_pattern",
    ],
].sort_values(
    [
        "complete_year_pattern",
        "station",
    ]
)

if len(z3):
    print(
        z3.to_string(
            index=False
        )
    )
else:
    print(
        "None."
    )

print()
print(
    "=== WELLS COMPLETE EXACTLY 2 YEARS ==="
)

z2 = wide.loc[
    wide[
        "complete_exactly_2"
    ],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_2025",
        "complete_years_n",
        "complete_year_pattern",
    ],
].sort_values(
    [
        "complete_year_pattern",
        "station",
    ]
)

if len(z2):
    print(
        z2.to_string(
            index=False
        )
    )
else:
    print(
        "None."
    )

print()
print(
    "=== WELLS COMPLETE AT LEAST 2 YEARS ==="
)

z_atleast2 = wide.loc[
    wide[
        "complete_at_least_2"
    ],
    [
        "station",
        "complete_2022",
        "complete_2023",
        "complete_2024",
        "complete_2025",
        "complete_years_n",
        "complete_year_pattern",
    ],
].sort_values(
    [
        "complete_years_n",
        "station",
    ],
    ascending=[
        False,
        True,
    ],
)

if len(z_atleast2):
    print(
        z_atleast2.to_string(
            index=False
        )
    )
else:
    print(
        "None."
    )

print()
print(
    "AGGREGATE REGRESSION QA:"
)
print(
    f"  exactly 2 complete years: "
    f"{observed_exactly_2} — PASS"
)
print(
    f"  exactly 3 complete years: "
    f"{observed_exactly_3} — PASS"
)
print(
    f"  complete all 4 years: "
    f"{observed_all_4} — PASS"
)

print()
print(
    "Outputs:"
)
print(
    WELL_OUT
)
print(
    SUMMARY_OUT
)
print(
    PATTERN_OUT
)
print(
    TRANSITION_OUT
)

print()
print(
    "NO FLOODING EXPOSURE MERGED."
)
print(
    "NO EFFECT MODEL FIT."
)
print(
    "DONE"
)
"""Audit integrated 2022-2025 analytical eligibility before model fitting.

Scientific role
---------------
This stage combines only prespecified data-availability rules across the
already frozen groundwater, flooding-exposure, and weather pipelines.

It DOES NOT fit an association model and DOES NOT inspect any model result.

Frozen eligibility ingredients
------------------------------
Groundwater:
    outcome     = gw_aug_nearest_aug23_m
    antecedent  = gw_pre_last_janfeb_m

Flooding exposure:
    exposure    = ff10_anomaly_2010_2021
    geometry    = n_cells_10km > 0

Weather:
    P_A8 and T_A8 both available

Primary integrated station-year eligibility:
    groundwater complete
    AND FF10 exposure available with positive 10-km support
    AND P_A8 available
    AND T_A8 available

Integrity gate
--------------
The 2022-2023 repeated integrated sample must reproduce the 13 station IDs
frozen before the original held-out groundwater confirmation.

No coefficient is calculated.
No regression is fitted.
No sample is chosen based on an effect estimate.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

GW_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "groundwater_annual_measures_2008_2025.csv"
)

FF_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_frozen_ff10_exposures_2022_2025.csv"
)

WEATHER_IN = (
    ROOT
    / "data"
    / "processed"
    / "post2021"
    / "well_weather_A8_2022_2025.csv"
)

FROZEN_IDS_IN = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
    / "post2021_primary_repeated_sample_ids.csv"
)

OUT_DIR = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "post2021"
)

STATION_YEAR_OUT = (
    OUT_DIR
    / "post2021_integrated_eligibility_by_station_year_2022_2025.csv"
)

YEAR_SUMMARY_OUT = (
    OUT_DIR
    / "post2021_integrated_eligibility_summary_2022_2025.csv"
)

WELL_PATTERN_OUT = (
    OUT_DIR
    / "post2021_integrated_eligibility_by_well_2022_2025.csv"
)

PATTERN_SUMMARY_OUT = (
    OUT_DIR
    / "post2021_integrated_eligibility_patterns_2022_2025.csv"
)

FROZEN_REPRO_OUT = (
    OUT_DIR
    / "post2021_integrated_eligibility_2022_2023_reproduction_qa.csv"
)

BALANCED4_IDS_OUT = (
    OUT_DIR
    / "post2021_integrated_balanced4_sample_ids.csv"
)

AT_LEAST3_IDS_OUT = (
    OUT_DIR
    / "post2021_integrated_at_least3_sample_ids.csv"
)

AT_LEAST2_IDS_OUT = (
    OUT_DIR
    / "post2021_integrated_at_least2_sample_ids.csv"
)


YEARS = (2022, 2023, 2024, 2025)
EXPECTED_ISS_WELLS = 37

OUTCOME = "gw_aug_nearest_aug23_m"
ANTECEDENT = "gw_pre_last_janfeb_m"
EXPOSURE = "ff10_anomaly_2010_2021"

EXPECTED_GW_COMPLETE = {
    2022: 17,
    2023: 13,
    2024: 15,
    2025: 17,
}

EXPECTED_FF_COMPLETE = {
    2022: 35,
    2023: 35,
    2024: 35,
    2025: 35,
}

EXPECTED_WEATHER_COMPLETE = {
    2022: 37,
    2023: 37,
    2024: 37,
    2025: 37,
}

EXPECTED_FROZEN_REPEATED_WELLS = 13


def require_unique(
    d: pd.DataFrame,
    key: list[str],
    label: str,
) -> None:
    if d.duplicated(key).any():
        bad = d.loc[
            d.duplicated(
                key,
                keep=False,
            ),
            key,
        ].sort_values(key)

        raise AssertionError(
            f"{label}: duplicate keys:\n"
            + bad.to_string(index=False)
        )


def pattern_code(
    row: pd.Series,
) -> str:
    years = [
        str(year)
        for year in YEARS
        if bool(
            row[
                f"eligible_{year}"
            ]
        )
    ]

    if not years:
        return "none"

    return "_".join(years)


def main() -> None:
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        GW_IN,
        FF_IN,
        WEATHER_IN,
        FROZEN_IDS_IN,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Required input not found: {path}"
            )

    # ---------------------------------------------------------
    # 1. Groundwater availability over the frozen ISS universe.
    # ---------------------------------------------------------

    gw = pd.read_csv(
        GW_IN,
        usecols=[
            "station",
            "year",
            "aquifer_group",
            OUTCOME,
            ANTECEDENT,
        ],
    )

    gw = gw.loc[
        gw["year"].isin(YEARS)
        & gw["aquifer_group"].eq("ISS")
    ].copy()

    require_unique(
        gw,
        [
            "station",
            "year",
        ],
        "groundwater",
    )

    if gw["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_WELLS} ISS groundwater wells; "
            f"found {gw['station'].nunique()}."
        )

    expected_rows = (
        EXPECTED_ISS_WELLS
        * len(YEARS)
    )

    if len(gw) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} ISS groundwater station-years; "
            f"found {len(gw)}."
        )

    gw["gw_outcome_available"] = (
        gw[OUTCOME].notna()
    )

    gw["gw_antecedent_available"] = (
        gw[ANTECEDENT].notna()
    )

    gw["gw_complete"] = (
        gw["gw_outcome_available"]
        & gw["gw_antecedent_available"]
    )

    for year, expected in EXPECTED_GW_COMPLETE.items():
        observed = int(
            gw.loc[
                gw["year"].eq(year),
                "gw_complete",
            ].sum()
        )

        if observed != expected:
            raise AssertionError(
                f"{year}: groundwater-complete count "
                f"{observed} != expected {expected}."
            )

    # ---------------------------------------------------------
    # 2. Frozen FF10 exposure availability.
    # ---------------------------------------------------------

    ff = pd.read_csv(
        FF_IN,
        usecols=[
            "station",
            "year",
            "n_cells_10km",
            EXPOSURE,
        ],
    )

    ff = ff.loc[
        ff["year"].isin(YEARS)
    ].copy()

    require_unique(
        ff,
        [
            "station",
            "year",
        ],
        "FF10 exposure",
    )

    if ff["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_WELLS} FF10 wells; "
            f"found {ff['station'].nunique()}."
        )

    if len(ff) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} FF10 station-years; "
            f"found {len(ff)}."
        )

    ff["ff_geometry_positive"] = (
        ff["n_cells_10km"] > 0
    )

    ff["ff10_available"] = (
        ff[EXPOSURE].notna()
        & ff["ff_geometry_positive"]
    )

    if not (
        ff["ff10_available"]
        .eq(
            ff[EXPOSURE].notna()
        )
    ).all():
        raise AssertionError(
            "FF10 availability does not match positive geometry exactly."
        )

    for year, expected in EXPECTED_FF_COMPLETE.items():
        observed = int(
            ff.loc[
                ff["year"].eq(year),
                "ff10_available",
            ].sum()
        )

        if observed != expected:
            raise AssertionError(
                f"{year}: FF10-complete count "
                f"{observed} != expected {expected}."
            )

    # ---------------------------------------------------------
    # 3. Weather-control availability.
    # ---------------------------------------------------------

    weather = pd.read_csv(
        WEATHER_IN,
        usecols=[
            "station",
            "year",
            "P_A8",
            "T_A8",
        ],
    )

    weather = weather.loc[
        weather["year"].isin(YEARS)
    ].copy()

    require_unique(
        weather,
        [
            "station",
            "year",
        ],
        "weather",
    )

    if weather["station"].nunique() != EXPECTED_ISS_WELLS:
        raise AssertionError(
            f"Expected {EXPECTED_ISS_WELLS} weather wells; "
            f"found {weather['station'].nunique()}."
        )

    if len(weather) != expected_rows:
        raise AssertionError(
            f"Expected {expected_rows} weather station-years; "
            f"found {len(weather)}."
        )

    weather["P_A8_available"] = (
        weather["P_A8"].notna()
    )

    weather["T_A8_available"] = (
        weather["T_A8"].notna()
    )

    weather["weather_complete"] = (
        weather["P_A8_available"]
        & weather["T_A8_available"]
    )

    for year, expected in EXPECTED_WEATHER_COMPLETE.items():
        observed = int(
            weather.loc[
                weather["year"].eq(year),
                "weather_complete",
            ].sum()
        )

        if observed != expected:
            raise AssertionError(
                f"{year}: weather-complete count "
                f"{observed} != expected {expected}."
            )

    # ---------------------------------------------------------
    # 4. Exact 37 x 4 integrated availability panel.
    # ---------------------------------------------------------

    panel = (
        gw[
            [
                "station",
                "year",
                "gw_outcome_available",
                "gw_antecedent_available",
                "gw_complete",
            ]
        ]
        .merge(
            ff[
                [
                    "station",
                    "year",
                    "n_cells_10km",
                    "ff_geometry_positive",
                    "ff10_available",
                ]
            ],
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
        .merge(
            weather[
                [
                    "station",
                    "year",
                    "P_A8_available",
                    "T_A8_available",
                    "weather_complete",
                ]
            ],
            on=[
                "station",
                "year",
            ],
            how="left",
            validate="one_to_one",
        )
        .sort_values(
            [
                "station",
                "year",
            ]
        )
        .reset_index(drop=True)
    )

    if len(panel) != expected_rows:
        raise AssertionError(
            "Integrated panel is not exactly 37 wells x 4 years."
        )

    availability_cols = [
        "gw_outcome_available",
        "gw_antecedent_available",
        "gw_complete",
        "ff_geometry_positive",
        "ff10_available",
        "P_A8_available",
        "T_A8_available",
        "weather_complete",
    ]

    if panel[
        availability_cols
    ].isna().any().any():
        raise AssertionError(
            "Integrated availability indicators contain missing values."
        )

    panel["eligible"] = (
        panel["gw_complete"]
        & panel["ff10_available"]
        & panel["weather_complete"]
    )

    panel["removed_by_groundwater"] = (
        ~panel["gw_complete"]
    )

    panel["removed_by_ff_after_gw"] = (
        panel["gw_complete"]
        & ~panel["ff10_available"]
    )

    panel["removed_by_weather_after_gw_ff"] = (
        panel["gw_complete"]
        & panel["ff10_available"]
        & ~panel["weather_complete"]
    )

    panel["exclusion_reason"] = "eligible"

    panel.loc[
        panel["removed_by_groundwater"],
        "exclusion_reason",
    ] = "groundwater_incomplete"

    panel.loc[
        panel["removed_by_ff_after_gw"],
        "exclusion_reason",
    ] = "ff10_unavailable_after_groundwater"

    panel.loc[
        panel["removed_by_weather_after_gw_ff"],
        "exclusion_reason",
    ] = "weather_unavailable_after_groundwater_ff10"

    # ---------------------------------------------------------
    # 5. Year-level availability/exclusion summary.
    # ---------------------------------------------------------

    summary_rows = []

    for year in YEARS:
        y = panel.loc[
            panel["year"].eq(year)
        ]

        summary_rows.append(
            {
                "year": year,
                "iss_wells_n":
                    EXPECTED_ISS_WELLS,
                "gw_complete_n":
                    int(
                        y["gw_complete"].sum()
                    ),
                "ff10_complete_n":
                    int(
                        y["ff10_available"].sum()
                    ),
                "weather_complete_n":
                    int(
                        y["weather_complete"].sum()
                    ),
                "eligible_n":
                    int(
                        y["eligible"].sum()
                    ),
                "removed_by_groundwater_n":
                    int(
                        y[
                            "removed_by_groundwater"
                        ].sum()
                    ),
                "removed_by_ff_after_gw_n":
                    int(
                        y[
                            "removed_by_ff_after_gw"
                        ].sum()
                    ),
                "removed_by_weather_after_gw_ff_n":
                    int(
                        y[
                            "removed_by_weather_after_gw_ff"
                        ].sum()
                    ),
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    # ---------------------------------------------------------
    # 6. Reproduce the frozen 2022-2023 repeated sample exactly.
    # ---------------------------------------------------------

    frozen_ids = pd.read_csv(
        FROZEN_IDS_IN
    )

    if list(frozen_ids.columns) != ["station"]:
        raise AssertionError(
            "Frozen repeated-sample ID file must contain only station."
        )

    if len(frozen_ids) != EXPECTED_FROZEN_REPEATED_WELLS:
        raise AssertionError(
            "Unexpected number of frozen 2022-2023 repeated wells."
        )

    if frozen_ids["station"].duplicated().any():
        raise AssertionError(
            "Frozen repeated-sample IDs contain duplicates."
        )

    frozen_set = set(
        frozen_ids["station"]
    )

    eligible_2022 = set(
        panel.loc[
            panel["year"].eq(2022)
            & panel["eligible"],
            "station",
        ]
    )

    eligible_2023 = set(
        panel.loc[
            panel["year"].eq(2023)
            & panel["eligible"],
            "station",
        ]
    )

    repeated_2022_2023 = (
        eligible_2022
        & eligible_2023
    )

    if repeated_2022_2023 != frozen_set:
        missing_from_generated = sorted(
            frozen_set
            - repeated_2022_2023
        )

        unexpected_generated = sorted(
            repeated_2022_2023
            - frozen_set
        )

        raise AssertionError(
            "Integrated eligibility does not reproduce the frozen "
            "2022-2023 repeated sample.\n"
            f"Missing from generated: {missing_from_generated}\n"
            f"Unexpected generated: {unexpected_generated}"
        )

    frozen_repro_qa = pd.DataFrame(
        [
            {
                "check":
                    "eligible_2022_count",
                "expected":
                    17,
                "observed":
                    int(
                        summary.loc[
                            summary["year"].eq(2022),
                            "eligible_n",
                        ].iloc[0]
                    ),
                "status":
                    "PASS",
            },
            {
                "check":
                    "eligible_2023_count",
                "expected":
                    13,
                "observed":
                    int(
                        summary.loc[
                            summary["year"].eq(2023),
                            "eligible_n",
                        ].iloc[0]
                    ),
                "status":
                    "PASS",
            },
            {
                "check":
                    "repeated_2022_2023_wells",
                "expected":
                    EXPECTED_FROZEN_REPEATED_WELLS,
                "observed":
                    len(
                        repeated_2022_2023
                    ),
                "status":
                    "PASS",
            },
            {
                "check":
                    "exact_station_id_set",
                "expected":
                    EXPECTED_FROZEN_REPEATED_WELLS,
                "observed":
                    len(
                        repeated_2022_2023
                        & frozen_set
                    ),
                "status":
                    "PASS",
            },
        ]
    )

    # ---------------------------------------------------------
    # 7. Well-level integrated eligibility patterns.
    # ---------------------------------------------------------

    wide = (
        panel.pivot(
            index="station",
            columns="year",
            values="eligible",
        )
        .reindex(
            columns=YEARS,
            fill_value=False,
        )
        .reset_index()
    )

    wide.columns = [
        "station",
        "eligible_2022",
        "eligible_2023",
        "eligible_2024",
        "eligible_2025",
    ]

    eligibility_cols = [
        "eligible_2022",
        "eligible_2023",
        "eligible_2024",
        "eligible_2025",
    ]

    for col in eligibility_cols:
        wide[col] = (
            wide[col]
            .fillna(False)
            .astype(bool)
        )

    wide["eligible_years_n"] = (
        wide[
            eligibility_cols
        ]
        .sum(axis=1)
        .astype(int)
    )

    wide["eligible_all_4"] = (
        wide["eligible_years_n"] == 4
    )

    wide["eligible_at_least_3"] = (
        wide["eligible_years_n"] >= 3
    )

    wide["eligible_at_least_2"] = (
        wide["eligible_years_n"] >= 2
    )

    wide["eligible_exactly_3"] = (
        wide["eligible_years_n"] == 3
    )

    wide["eligible_exactly_2"] = (
        wide["eligible_years_n"] == 2
    )

    wide["eligible_exactly_1"] = (
        wide["eligible_years_n"] == 1
    )

    wide["eligible_0"] = (
        wide["eligible_years_n"] == 0
    )

    wide["eligible_year_pattern"] = (
        wide.apply(
            pattern_code,
            axis=1,
        )
    )

    wide = wide.sort_values(
        "station"
    ).reset_index(drop=True)

    pattern_summary = (
        wide.groupby(
            "eligible_year_pattern",
            dropna=False,
        )
        .size()
        .reset_index(
            name="wells_n"
        )
        .sort_values(
            [
                "wells_n",
                "eligible_year_pattern",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    balanced4 = (
        wide.loc[
            wide["eligible_all_4"],
            ["station"],
        ]
        .sort_values("station")
        .reset_index(drop=True)
    )

    at_least3 = (
        wide.loc[
            wide["eligible_at_least_3"],
            [
                "station",
                "eligible_years_n",
                "eligible_year_pattern",
            ],
        ]
        .sort_values(
            [
                "eligible_years_n",
                "station",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    at_least2 = (
        wide.loc[
            wide["eligible_at_least_2"],
            [
                "station",
                "eligible_years_n",
                "eligible_year_pattern",
            ],
        ]
        .sort_values(
            [
                "eligible_years_n",
                "station",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # 8. Save only after all integrity gates pass.
    # ---------------------------------------------------------

    panel.to_csv(
        STATION_YEAR_OUT,
        index=False,
    )

    summary.to_csv(
        YEAR_SUMMARY_OUT,
        index=False,
    )

    wide.to_csv(
        WELL_PATTERN_OUT,
        index=False,
    )

    pattern_summary.to_csv(
        PATTERN_SUMMARY_OUT,
        index=False,
    )

    frozen_repro_qa.to_csv(
        FROZEN_REPRO_OUT,
        index=False,
    )

    balanced4.to_csv(
        BALANCED4_IDS_OUT,
        index=False,
    )

    at_least3.to_csv(
        AT_LEAST3_IDS_OUT,
        index=False,
    )

    at_least2.to_csv(
        AT_LEAST2_IDS_OUT,
        index=False,
    )

    # ---------------------------------------------------------
    # 9. Console: availability/sample structure only.
    # ---------------------------------------------------------

    print("")
    print("=" * 76)
    print(
        "INTEGRATED 2022-2025 ANALYTICAL ELIGIBILITY AUDIT"
    )
    print("=" * 76)

    print("")
    print(
        "Eligibility definition:"
    )
    print(
        "  groundwater outcome + antecedent available"
    )
    print(
        "  AND FF10 anomaly available with positive 10-km geometry"
    )
    print(
        "  AND P_A8 and T_A8 available"
    )

    print("")
    print(
        "=== YEAR-LEVEL SUMMARY ==="
    )
    print(
        summary.to_string(
            index=False
        )
    )

    print("")
    print(
        "=== FROZEN 2022-2023 REPRODUCTION ==="
    )
    print(
        frozen_repro_qa.to_string(
            index=False
        )
    )

    print("")
    print(
        "=== 2022-2025 ELIGIBILITY PATTERNS ==="
    )
    print(
        pattern_summary.to_string(
            index=False
        )
    )

    print("")
    print(
        "=== BALANCED 4-YEAR ELIGIBLE WELLS ==="
    )

    if len(balanced4):
        print(
            balanced4.to_string(
                index=False
            )
        )
    else:
        print(
            "None."
        )

    print("")
    print(
        "=== ELIGIBLE IN AT LEAST 3 YEARS ==="
    )

    if len(at_least3):
        print(
            at_least3.to_string(
                index=False
            )
        )
    else:
        print(
            "None."
        )

    print("")
    print(
        "=== ELIGIBLE IN AT LEAST 2 YEARS ==="
    )

    if len(at_least2):
        print(
            at_least2.to_string(
                index=False
            )
        )
    else:
        print(
            "None."
        )

    print("")
    print(
        "No association coefficient was calculated."
    )
    print(
        "No regression was fitted."
    )
    print(
        "No sample was selected using a model result."
    )

    print("")
    print(
        f"Wrote: {STATION_YEAR_OUT}"
    )
    print(
        f"Wrote: {YEAR_SUMMARY_OUT}"
    )
    print(
        f"Wrote: {WELL_PATTERN_OUT}"
    )
    print(
        f"Wrote: {PATTERN_SUMMARY_OUT}"
    )
    print(
        f"Wrote: {FROZEN_REPRO_OUT}"
    )
    print(
        f"Wrote: {BALANCED4_IDS_OUT}"
    )
    print(
        f"Wrote: {AT_LEAST3_IDS_OUT}"
    )
    print(
        f"Wrote: {AT_LEAST2_IDS_OUT}"
    )

    print("")
    print("DONE")


if __name__ == "__main__":
    main()

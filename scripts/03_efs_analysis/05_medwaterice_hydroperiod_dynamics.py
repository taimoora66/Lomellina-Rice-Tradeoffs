from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"
DIAG = ROOT / "outputs" / "diagnostics"

TABLES.mkdir(parents=True, exist_ok=True)
DIAG.mkdir(parents=True, exist_ok=True)

src = DATA / "MEDWATERICE_CS1_hydrology_daily.csv"

df = pd.read_csv(src)
df["date"] = pd.to_datetime(df["date"], errors="raise")
df["ponding_level_mm"] = pd.to_numeric(
    df["ponding_level_mm"],
    errors="coerce"
)


# ============================================================
# IMPORTANT DEFINITION
#
# Wet day = measured daily mean ponding level > 0 mm
# Dry day = measured daily mean ponding level <= 0 mm
#
# This is an observational hydroperiod-state definition.
# It is NOT equivalent to soil water deficit or agronomic AWD
# threshold status.
# ============================================================


def spell_lengths(states, target):
    """
    Return lengths and start/end positions of consecutive
    runs equal to target.
    """

    runs = []
    start = None

    for i, value in enumerate(states):

        if value == target:

            if start is None:
                start = i

        else:

            if start is not None:
                runs.append(
                    (start, i - 1, i - start)
                )
                start = None

    if start is not None:
        runs.append(
            (start, len(states) - 1, len(states) - start)
        )

    return runs


summary_rows = []
spell_rows = []
daily_frames = []


for (year, treatment), g in df.groupby(
    ["year", "treatment"]
):

    g = (
        g.sort_values("date")
        .reset_index(drop=True)
        .copy()
    )

    valid = g["ponding_level_mm"].notna()

    if not valid.all():
        raise ValueError(
            f"Missing ponding values in {year} {treatment}. "
            "Hydroperiod analysis requires complete daily state."
        )

    g["wet_state"] = (
        g["ponding_level_mm"] > 0
    ).astype(int)

    g["dry_state"] = (
        g["ponding_level_mm"] <= 0
    ).astype(int)

    states = g["wet_state"].tolist()

    wet_runs = spell_lengths(states, 1)
    dry_runs = spell_lengths(states, 0)


    # --------------------------------------------------------
    # transitions
    # --------------------------------------------------------

    transition = g["wet_state"].diff()

    wet_to_dry = int((transition == -1).sum())
    dry_to_wet = int((transition == 1).sum())


    # --------------------------------------------------------
    # spell table
    # --------------------------------------------------------

    for spell_id, (start, end, length) in enumerate(
        wet_runs,
        start=1
    ):

        spell_rows.append(
            {
                "year": year,
                "treatment": treatment,
                "state": "wet",
                "spell_id": spell_id,
                "start_date": g.loc[start, "date"],
                "end_date": g.loc[end, "date"],
                "length_days": length,
                "start_index": start,
                "end_index": end,
            }
        )


    for spell_id, (start, end, length) in enumerate(
        dry_runs,
        start=1
    ):

        spell_rows.append(
            {
                "year": year,
                "treatment": treatment,
                "state": "dry",
                "spell_id": spell_id,
                "start_date": g.loc[start, "date"],
                "end_date": g.loc[end, "date"],
                "length_days": length,
                "start_index": start,
                "end_index": end,
            }
        )


    # --------------------------------------------------------
    # longest spells
    # --------------------------------------------------------

    longest_wet = (
        max([r[2] for r in wet_runs])
        if wet_runs else 0
    )

    longest_dry = (
        max([r[2] for r in dry_runs])
        if dry_runs else 0
    )


    # longest dry spell date
    if dry_runs:

        dry_longest_record = max(
            dry_runs,
            key=lambda x: x[2]
        )

        longest_dry_start = (
            g.loc[
                dry_longest_record[0],
                "date"
            ]
        )

        longest_dry_end = (
            g.loc[
                dry_longest_record[1],
                "date"
            ]
        )

    else:

        longest_dry_start = pd.NaT
        longest_dry_end = pd.NaT


    # --------------------------------------------------------
    # first dry spell
    # --------------------------------------------------------

    if dry_runs:

        first_dry = dry_runs[0]

        first_dry_start = (
            g.loc[first_dry[0], "date"]
        )

        first_dry_length = first_dry[2]

        days_to_first_dry = (
            first_dry_start - g["date"].iloc[0]
        ).days

    else:

        first_dry_start = pd.NaT
        first_dry_length = 0
        days_to_first_dry = np.nan


    # --------------------------------------------------------
    # ponding-depth descriptors
    # --------------------------------------------------------

    h = g["ponding_level_mm"]

    positive_h = h.loc[h > 0]

    summary_rows.append(
        {
            "year": year,
            "treatment": treatment,

            "start_date": g["date"].min(),
            "end_date": g["date"].max(),
            "n_days": len(g),

            "wet_days": int((g["wet_state"] == 1).sum()),
            "dry_days": int((g["wet_state"] == 0).sum()),

            "wet_fraction":
                (g["wet_state"] == 1).mean(),

            "dry_fraction":
                (g["wet_state"] == 0).mean(),

            "n_wet_spells": len(wet_runs),
            "n_dry_spells": len(dry_runs),

            "wet_to_dry_transitions": wet_to_dry,
            "dry_to_wet_transitions": dry_to_wet,

            "longest_wet_spell_days":
                longest_wet,

            "longest_dry_spell_days":
                longest_dry,

            "first_dry_spell_start":
                first_dry_start,

            "first_dry_spell_length_days":
                first_dry_length,

            "days_from_record_start_to_first_dry":
                days_to_first_dry,

            "longest_dry_spell_start":
                longest_dry_start,

            "longest_dry_spell_end":
                longest_dry_end,

            "mean_ponding_level_mm":
                h.mean(),

            "median_ponding_level_mm":
                h.median(),

            "ponding_p25_mm":
                h.quantile(0.25),

            "ponding_p75_mm":
                h.quantile(0.75),

            "ponding_p95_mm":
                h.quantile(0.95),

            "max_ponding_level_mm":
                h.max(),

            "mean_positive_ponding_mm":
                positive_h.mean()
                if len(positive_h)
                else np.nan,

            "median_positive_ponding_mm":
                positive_h.median()
                if len(positive_h)
                else np.nan,

            # Sum of daily mean ponding levels.
            # This is an integrated ponding-state index,
            # not a water-volume balance term.
            "cumulative_daily_ponding_index_mm_days":
                h.clip(lower=0).sum(),
        }
    )

    daily_frames.append(g)


summary = pd.DataFrame(summary_rows)
spells = pd.DataFrame(spell_rows)
daily = pd.concat(
    daily_frames,
    ignore_index=True
)


# ============================================================
# COMMON CALENDAR WINDOW
#
# Important because DFL records begin earlier.
# ============================================================

common_summary_rows = []

for year, gy in daily.groupby("year"):

    ranges = (
        gy.groupby("treatment")
        .agg(
            start=("date", "min"),
            end=("date", "max")
        )
    )

    common_start = ranges["start"].max()
    common_end = ranges["end"].min()

    for treatment, gt in gy.groupby("treatment"):

        g = (
            gt.loc[
                gt["date"].between(
                    common_start,
                    common_end
                )
            ]
            .sort_values("date")
            .reset_index(drop=True)
            .copy()
        )

        states = g["wet_state"].tolist()

        wet_runs = spell_lengths(states, 1)
        dry_runs = spell_lengths(states, 0)

        transition = g["wet_state"].diff()

        h = g["ponding_level_mm"]

        common_summary_rows.append(
            {
                "year": year,
                "treatment": treatment,

                "common_start": common_start,
                "common_end": common_end,
                "n_days": len(g),

                "wet_days":
                    int(g["wet_state"].sum()),

                "dry_days":
                    int((g["wet_state"] == 0).sum()),

                "wet_fraction":
                    g["wet_state"].mean(),

                "dry_fraction":
                    (g["wet_state"] == 0).mean(),

                "n_wet_spells":
                    len(wet_runs),

                "n_dry_spells":
                    len(dry_runs),

                "wet_to_dry_transitions":
                    int((transition == -1).sum()),

                "dry_to_wet_transitions":
                    int((transition == 1).sum()),

                "longest_wet_spell_days":
                    max(
                        [r[2] for r in wet_runs],
                        default=0
                    ),

                "longest_dry_spell_days":
                    max(
                        [r[2] for r in dry_runs],
                        default=0
                    ),

                "mean_ponding_level_mm":
                    h.mean(),

                "median_ponding_level_mm":
                    h.median(),

                "ponding_p25_mm":
                    h.quantile(0.25),

                "ponding_p75_mm":
                    h.quantile(0.75),

                "ponding_p95_mm":
                    h.quantile(0.95),

                "max_ponding_level_mm":
                    h.max(),

                "cumulative_daily_ponding_index_mm_days":
                    h.clip(lower=0).sum(),
            }
        )


common_summary = pd.DataFrame(
    common_summary_rows
)


# ============================================================
# SAVE OUTPUTS
# ============================================================

summary.to_csv(
    TABLES /
    "MEDWATERICE_hydroperiod_fullseason_summary.csv",
    index=False
)

common_summary.to_csv(
    TABLES /
    "MEDWATERICE_hydroperiod_common_window_summary.csv",
    index=False
)

spells.to_csv(
    TABLES /
    "MEDWATERICE_hydroperiod_spell_inventory.csv",
    index=False
)

daily[
    [
        "year",
        "treatment",
        "date",
        "ponding_level_mm",
        "wet_state",
        "dry_state",
    ]
].to_csv(
    DIAG /
    "MEDWATERICE_hydroperiod_daily_states.csv",
    index=False
)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 30)

show = [
    "year",
    "treatment",
    "n_days",
    "wet_days",
    "dry_days",
    "wet_fraction",
    "n_wet_spells",
    "n_dry_spells",
    "wet_to_dry_transitions",
    "dry_to_wet_transitions",
    "longest_wet_spell_days",
    "longest_dry_spell_days",
    "mean_ponding_level_mm",
    "median_ponding_level_mm",
    "cumulative_daily_ponding_index_mm_days",
]

print()
print("=" * 105)
print("FULL-SEASON HYDROPERIOD DYNAMICS")
print("=" * 105)
print(
    summary[show]
    .round(3)
    .to_string(index=False)
)

print()
print("=" * 105)
print("COMMON-WINDOW HYDROPERIOD DYNAMICS")
print("=" * 105)
print(
    common_summary[show]
    .round(3)
    .to_string(index=False)
)

print()
print(
    "IMPORTANT: wet/dry states are defined only from measured "
    "daily mean ponding level > 0 or <= 0 mm."
)

print(
    "They are not equivalent to agronomic AWD thresholds, "
    "soil moisture stress, or continuous within-day flooding."
)

print()
print("MEDWATERICE hydroperiod analysis completed.")

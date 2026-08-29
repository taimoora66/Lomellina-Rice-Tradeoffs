from pathlib import Path
import pandas as pd


ROOT = Path(".")
DATA = ROOT / "data" / "interim" / "MEDWATERICE"
TABLES = ROOT / "outputs" / "tables"

TABLES.mkdir(parents=True, exist_ok=True)

src = DATA / "MEDWATERICE_CS1_hydrology_daily.csv"

df = pd.read_csv(src)
df["date"] = pd.to_datetime(df["date"], errors="raise")
df["ponding_level_mm"] = pd.to_numeric(
    df["ponding_level_mm"],
    errors="coerce"
)


# ============================================================
# Threshold sensitivity
#
# Wet state defined as:
# h_lev > 0 mm
# h_lev > 1 mm
# h_lev > 5 mm
#
# Purpose:
# test whether qualitative hydroperiod conclusions depend
# strongly on small near-zero ponding values.
# ============================================================

thresholds = [0, 1, 5]


def spell_lengths(states, target):
    runs = []
    start = None

    for i, value in enumerate(states):

        if value == target:
            if start is None:
                start = i
        else:
            if start is not None:
                runs.append((start, i - 1, i - start))
                start = None

    if start is not None:
        runs.append(
            (start, len(states) - 1, len(states) - start)
        )

    return runs


rows = []


for year, gy in df.groupby("year"):

    coverage = (
        gy.groupby("treatment")
        .agg(
            start=("date", "min"),
            end=("date", "max")
        )
    )

    common_start = coverage["start"].max()
    common_end = coverage["end"].min()

    gy = gy.loc[
        gy["date"].between(
            common_start,
            common_end
        )
    ].copy()


    for threshold in thresholds:

        for treatment, g in gy.groupby("treatment"):

            g = (
                g.sort_values("date")
                .reset_index(drop=True)
                .copy()
            )

            h = g["ponding_level_mm"]

            if h.isna().any():
                raise ValueError(
                    f"Missing h_lev values: "
                    f"{year} {treatment}"
                )

            wet = (h > threshold).astype(int)

            wet_runs = spell_lengths(
                wet.tolist(), 1
            )

            dry_runs = spell_lengths(
                wet.tolist(), 0
            )

            transition = wet.diff()

            rows.append(
                {
                    "year": year,
                    "treatment": treatment,
                    "threshold_mm": threshold,

                    "common_start": common_start,
                    "common_end": common_end,
                    "n_days": len(g),

                    "wet_days":
                        int(wet.sum()),

                    "dry_days":
                        int((wet == 0).sum()),

                    "wet_fraction":
                        wet.mean(),

                    "dry_fraction":
                        (wet == 0).mean(),

                    "n_wet_spells":
                        len(wet_runs),

                    "n_dry_spells":
                        len(dry_runs),

                    "wet_to_dry_transitions":
                        int(
                            (transition == -1).sum()
                        ),

                    "dry_to_wet_transitions":
                        int(
                            (transition == 1).sum()
                        ),

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
                }
            )


result = pd.DataFrame(rows)

result.to_csv(
    TABLES /
    "MEDWATERICE_hydroperiod_threshold_sensitivity.csv",
    index=False
)


# ============================================================
# Compact comparison table
# ============================================================

display_cols = [
    "year",
    "treatment",
    "threshold_mm",
    "wet_fraction",
    "n_wet_spells",
    "n_dry_spells",
    "wet_to_dry_transitions",
    "dry_to_wet_transitions",
    "longest_wet_spell_days",
    "longest_dry_spell_days",
]

pd.set_option("display.width", 180)

print()
print("=" * 110)
print("HYDROPERIOD THRESHOLD SENSITIVITY")
print("=" * 110)

print(
    result[display_cols]
    .round(3)
    .to_string(index=False)
)


# ============================================================
# Quantify sensitivity relative to threshold = 0
# ============================================================

base = (
    result.loc[
        result["threshold_mm"] == 0
    ]
    .set_index(["year", "treatment"])
)

sensitivity_rows = []

for _, r in result.iterrows():

    if r["threshold_mm"] == 0:
        continue

    b = base.loc[
        (r["year"], r["treatment"])
    ]

    sensitivity_rows.append(
        {
            "year": r["year"],
            "treatment": r["treatment"],
            "threshold_mm": r["threshold_mm"],

            "wet_fraction_change":
                r["wet_fraction"]
                - b["wet_fraction"],

            "wet_spells_change":
                r["n_wet_spells"]
                - b["n_wet_spells"],

            "dry_spells_change":
                r["n_dry_spells"]
                - b["n_dry_spells"],

            "wet_to_dry_change":
                r["wet_to_dry_transitions"]
                - b["wet_to_dry_transitions"],

            "longest_dry_spell_change_days":
                r["longest_dry_spell_days"]
                - b["longest_dry_spell_days"],
        }
    )

sensitivity = pd.DataFrame(
    sensitivity_rows
)

sensitivity.to_csv(
    TABLES /
    "MEDWATERICE_hydroperiod_threshold_change_vs_zero.csv",
    index=False
)

print()
print("=" * 110)
print("CHANGE RELATIVE TO >0 mm DEFINITION")
print("=" * 110)

print(
    sensitivity
    .round(3)
    .to_string(index=False)
)

print()
print(
    "Interpretation rule: threshold sensitivity is acceptable "
    "only if the main qualitative conclusions remain stable."
)

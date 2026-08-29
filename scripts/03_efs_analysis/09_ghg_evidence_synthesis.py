from pathlib import Path
import pandas as pd


ROOT = Path(".")
LIT = ROOT / "literature"
OUT = ROOT / "outputs" / "tables"

OUT.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD REGISTER
# ============================================================

d = pd.read_csv(
    LIT / "GHG_evidence_register.csv"
)


# ============================================================
# BASIC FLAGS
# ============================================================

d["is_direct_ghg"] = (
    d["direct_GHG_measurement"]
    .astype(str)
    .str.lower()
    .eq("yes")
)

d["is_italian"] = (
    d["study_location"]
    .astype(str)
    .str.contains(
        "Italy|Italian",
        case=False,
        regex=True
    )
)

d["is_local_high_relevance"] = (
    d["evidence_tier"]
    .astype(str)
    .isin(["A1", "A2"])
)

d["is_global_synthesis"] = (
    d["evidence_tier"]
    .astype(str)
    .eq("C")
)


# ============================================================
# 1. STUDY INVENTORY
# ============================================================

inventory = pd.DataFrame(
    {
        "metric": [
            "total_studies",
            "direct_GHG_studies",
            "italian_or_italy_studies",
            "high_local_relevance_A1_A2",
            "global_synthesis_tier_C",
        ],
        "value": [
            len(d),
            int(d["is_direct_ghg"].sum()),
            int(d["is_italian"].sum()),
            int(d["is_local_high_relevance"].sum()),
            int(d["is_global_synthesis"].sum()),
        ],
    }
)

inventory.to_csv(
    OUT /
    "GHG_evidence_inventory_summary.csv",
    index=False
)


# ============================================================
# 2. DIRECTIONAL COUNTS
#
# We do not average effect sizes across meta-analyses because
# their primary-study databases may overlap.
# ============================================================

def directional_counts(
    data,
    variable,
    label
):

    x = (
        data[variable]
        .fillna("missing")
        .astype(str)
    )

    counts = (
        x.value_counts()
        .rename_axis("direction")
        .reset_index(name="n_studies")
    )

    counts.insert(
        0,
        "evidence_subset",
        label
    )

    counts.insert(
        1,
        "outcome",
        variable
    )

    return counts


directional_tables = []

for subset_name, subset in [
    (
        "all_direct_GHG",
        d[d["is_direct_ghg"]]
    ),
    (
        "local_A1_A2_direct_GHG",
        d[
            d["is_direct_ghg"]
            & d["is_local_high_relevance"]
        ]
    ),
    (
        "global_tier_C_direct_GHG",
        d[
            d["is_direct_ghg"]
            & d["is_global_synthesis"]
        ]
    ),
]:

    for variable in [
        "CH4_direction",
        "N2O_direction",
        "GWP_direction",
    ]:

        directional_tables.append(
            directional_counts(
                subset,
                variable,
                subset_name
            )
        )


directional = pd.concat(
    directional_tables,
    ignore_index=True
)

directional.to_csv(
    OUT /
    "GHG_directional_evidence_counts.csv",
    index=False
)


# ============================================================
# 3. STUDY-LEVEL CLAIM SUPPORT TABLE
# ============================================================

claim_rows = []

for _, row in d.iterrows():

    # CH4 mitigation
    claim_rows.append(
        {
            "study_id": row["study_id"],
            "evidence_tier":
                row["evidence_tier"],
            "claim":
                "aerobic_or_drained_management_reduces_CH4",
            "support":
                "support"
                if row["CH4_direction"] == "decrease"
                else (
                    "not_applicable"
                    if row["CH4_direction"]
                    in [
                        "not_measured",
                        "not_primary"
                    ]
                    else "mixed_or_no_support"
                ),
        }
    )

    # N2O increase
    claim_rows.append(
        {
            "study_id": row["study_id"],
            "evidence_tier":
                row["evidence_tier"],
            "claim":
                "aerobic_or_drained_management_can_increase_N2O",
            "support":
                "support"
                if row["N2O_direction"] == "increase"
                else (
                    "qualified"
                    if row["N2O_direction"]
                    == "no_clear_increase"
                    else (
                        "not_applicable"
                        if row["N2O_direction"]
                        in [
                            "not_measured",
                            "not_primary"
                        ]
                        else "mixed_or_no_support"
                    )
                ),
        }
    )

    # GWP reduction
    claim_rows.append(
        {
            "study_id": row["study_id"],
            "evidence_tier":
                row["evidence_tier"],
            "claim":
                "aerobic_or_drained_management_generally_reduces_GWP",
            "support":
                "support"
                if row["GWP_direction"]
                in [
                    "decrease",
                    "usually_decrease"
                ]
                else (
                    "counterexample"
                    if row["GWP_direction"]
                    == "increase"
                    else "not_applicable"
                ),
        }
    )


claim_support = pd.DataFrame(
    claim_rows
)

claim_support.to_csv(
    OUT /
    "GHG_claim_support_matrix.csv",
    index=False
)


# ============================================================
# 4. CLAIM-LEVEL SUMMARY
# ============================================================

claim_summary = (
    claim_support
    .groupby(
        [
            "claim",
            "support"
        ]
    )
    .size()
    .reset_index(
        name="n_studies"
    )
)

claim_summary.to_csv(
    OUT /
    "GHG_claim_support_summary.csv",
    index=False
)


# ============================================================
# 5. LOCAL DIRECT-EVIDENCE TABLE
# ============================================================

local_direct = d[
    d["is_direct_ghg"]
    & d["is_local_high_relevance"]
].copy()

local_direct = local_direct[
    [
        "study_id",
        "year",
        "study_location",
        "evidence_tier",
        "comparison",
        "CH4_direction",
        "N2O_direction",
        "GWP_direction",
        "yield_direction",
        "drying_severity",
        "transferability_to_Lomellina",
        "key_limitation",
        "doi",
    ]
]

local_direct.to_csv(
    OUT /
    "GHG_local_direct_evidence.csv",
    index=False
)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

pd.set_option(
    "display.width",
    180
)

pd.set_option(
    "display.max_columns",
    30
)


print()
print("=" * 105)
print("GHG EVIDENCE INVENTORY")
print("=" * 105)

print(
    inventory.to_string(
        index=False
    )
)


print()
print("=" * 105)
print("LOCAL A1/A2 DIRECT GHG EVIDENCE")
print("=" * 105)

print(
    local_direct[
        [
            "study_id",
            "study_location",
            "CH4_direction",
            "N2O_direction",
            "GWP_direction",
            "yield_direction",
            "drying_severity",
        ]
    ]
    .to_string(index=False)
)


print()
print("=" * 105)
print("DIRECTIONAL EVIDENCE COUNTS")
print("=" * 105)

print(
    directional.to_string(
        index=False
    )
)


print()
print("=" * 105)
print("CLAIM SUPPORT SUMMARY")
print("=" * 105)

print(
    claim_summary.to_string(
        index=False
    )
)


print()
print("=" * 105)
print("INTERPRETATION RULES")
print("=" * 105)

print(
    "1. CH4 direction may be synthesized qualitatively "
    "across direct GHG studies."
)

print(
    "2. N2O response must remain explicitly conditional "
    "because Italian and temperate studies differ."
)

print(
    "3. GWP reduction is the dominant result across global "
    "syntheses but is not universal; Italian counterexamples "
    "must be retained."
)

print(
    "4. Exact literature effect percentages must NOT be "
    "applied directly to Lomellina parcels or MEDWATERICE plots."
)

print(
    "5. Meta-analysis effect sizes are NOT averaged together "
    "because underlying primary-study databases may overlap."
)

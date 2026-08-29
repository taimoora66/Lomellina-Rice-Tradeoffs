from pathlib import Path
import pandas as pd


ROOT = Path(".")
LIT = ROOT / "literature"
OUT = ROOT / "outputs" / "tables"

OUT.mkdir(parents=True, exist_ok=True)


d = pd.read_csv(
    LIT / "habitat_evidence_register.csv"
)


# ------------------------------------------------------------
# FLAGS
# ------------------------------------------------------------

d["is_local_A1"] = d["evidence_tier"].eq("A1")
d["is_local_or_italian"] = d["evidence_tier"].isin(["A1", "A2"])
d["is_direct_biological"] = (
    d["direct_biological_data"]
    .astype(str)
    .str.lower()
    .eq("yes")
)


# ------------------------------------------------------------
# 1. INVENTORY
# ------------------------------------------------------------

inventory = pd.DataFrame(
    {
        "metric": [
            "total_studies",
            "A1_local_high_relevance",
            "A1_A2_local_or_Italian",
            "direct_biological_evidence",
        ],
        "value": [
            len(d),
            int(d["is_local_A1"].sum()),
            int(d["is_local_or_italian"].sum()),
            int(d["is_direct_biological"].sum()),
        ],
    }
)

inventory.to_csv(
    OUT / "habitat_evidence_inventory_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 2. CLAIM SUPPORT MATRIX
# ------------------------------------------------------------

rows = []

for _, r in d.iterrows():

    # Claim 1:
    # rice paddies function as temporary wetland-like habitat
    rows.append(
        {
            "study_id": r["study_id"],
            "evidence_tier": r["evidence_tier"],
            "claim":
                "rice_paddies_provide_temporary_wetland_like_habitat",
            "support":
                "support"
        }
    )

    # Claim 2:
    # water availability / hydroperiod matters
    if r["hydroperiod_or_water_link"] in [
        "direct",
        "direct_context",
        "water_availability",
        "management_context",
        "conceptual",
        "indirect",
    ]:
        support = "support"
    else:
        support = "unclear"

    rows.append(
        {
            "study_id": r["study_id"],
            "evidence_tier": r["evidence_tier"],
            "claim":
                "water_timing_duration_or_continuity_affects_habitat_or_community",
            "support": support
        }
    )

    # Claim 3:
    # hydroperiod alone is sufficient to infer biodiversity change
    rows.append(
        {
            "study_id": r["study_id"],
            "evidence_tier": r["evidence_tier"],
            "claim":
                "hydroperiod_alone_quantifies_biodiversity_change",
            "support":
                "no_support"
        }
    )


claim_support = pd.DataFrame(rows)

claim_support.to_csv(
    OUT / "habitat_claim_support_matrix.csv",
    index=False
)


summary = (
    claim_support
    .groupby(
        ["claim", "support"]
    )
    .size()
    .reset_index(name="n_studies")
)

summary.to_csv(
    OUT / "habitat_claim_support_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 3. LOCAL EVIDENCE TABLE
# ------------------------------------------------------------

local = d[
    d["is_local_or_italian"]
].copy()

local = local[
    [
        "study_id",
        "year",
        "study_location",
        "evidence_tier",
        "taxon_or_endpoint",
        "hydroperiod_or_water_link",
        "main_finding",
        "relevance_to_Lomellina",
        "evidence_strength",
        "key_limitation",
        "doi",
    ]
]

local.to_csv(
    OUT / "habitat_local_evidence.csv",
    index=False
)


# ------------------------------------------------------------
# TERMINAL OUTPUT
# ------------------------------------------------------------

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
print("HABITAT EVIDENCE INVENTORY")
print("=" * 105)

print(
    inventory.to_string(
        index=False
    )
)


print()
print("=" * 105)
print("LOCAL / ITALIAN HABITAT EVIDENCE")
print("=" * 105)

print(
    local[
        [
            "study_id",
            "study_location",
            "evidence_tier",
            "taxon_or_endpoint",
            "hydroperiod_or_water_link",
            "evidence_strength",
        ]
    ]
    .to_string(index=False)
)


print()
print("=" * 105)
print("HABITAT CLAIM SUPPORT SUMMARY")
print("=" * 105)

print(
    summary.to_string(
        index=False
    )
)


print()
print("=" * 105)
print("INTERPRETATION RULES")
print("=" * 105)

print(
    "1. Flooded rice paddies may be interpreted as temporary "
    "wetland-like habitat where supported by local ecological evidence."
)

print(
    "2. Hydroperiod, flooding continuity and irrigation timing may "
    "affect habitat availability and community composition."
)

print(
    "3. RiceFloodIT hydroperiod metrics must NOT be converted directly "
    "into species richness, abundance or biodiversity-loss estimates."
)

print(
    "4. The EFS endpoint is wetland-habitat availability, "
    "not measured biodiversity change."
)

print(
    "5. Ecological responses are taxon- and management-specific, "
    "so no universal hydroperiod threshold is assumed."
)

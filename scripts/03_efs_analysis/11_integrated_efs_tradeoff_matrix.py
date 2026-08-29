from pathlib import Path
import pandas as pd


ROOT = Path(".")
OUT = ROOT / "outputs" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


rows = [

    {
        "component": "Hydroperiod change",
        "indicator": "RiceFloodIT flooding-frequency trajectory 2000-2021",
        "evidence_source": "RiceFloodIT remote sensing",
        "evidence_class": "Observed spatial-temporal",
        "direction": "decrease",
        "confidence": "high",
        "claim": (
            "Flooding frequency declined substantially across the "
            "balanced Lomellina panel between the early 2000s and "
            "late 2010s/early 2020s."
        ),
        "allowed_inference": "observed descriptive trend",
        "prohibited_inference": (
            "Do not infer farmer motivation, AWD adoption, or biodiversity loss directly."
        ),
    },

    {
        "component": "Field water regulation",
        "indicator": "Qin, Qout, net irrigation, ponding",
        "evidence_source": "MEDWATERICE Castello d'Agogna 2019-2020",
        "evidence_class": "Local experimental descriptive",
        "direction": "context-dependent",
        "confidence": "moderate",
        "claim": (
            "Water-management regimes exhibited substantial differences "
            "in inflow, outflow, net irrigation and ponding within each season."
        ),
        "allowed_inference": "within-year descriptive comparison",
        "prohibited_inference": (
            "Do not claim universal field-water saving or basin-scale water saving."
        ),
    },

    {
        "component": "Percolation / subsurface transfer",
        "indicator": "Perc_Bal",
        "evidence_source": "MEDWATERICE water balance",
        "evidence_class": "Local derived hydrological",
        "direction": "context-dependent",
        "confidence": "moderate",
        "claim": (
            "Water-balance-derived percolation beneath the less-conductive "
            "layer differed strongly among regimes and reversed ordering between years."
        ),
        "allowed_inference": "descriptive water-balance difference",
        "prohibited_inference": (
            "Do not equate Perc_Bal directly with aquifer recharge."
        ),
    },

    {
        "component": "Groundwater context",
        "indicator": "Piezometric groundwater depth",
        "evidence_source": "MEDWATERICE piezometers",
        "evidence_class": "Local observed hydrological",
        "direction": "shared seasonal structure",
        "confidence": "moderate",
        "claim": (
            "Groundwater and surface-water variables shared substantial seasonal "
            "structure, consistent with a connected shallow-groundwater setting."
        ),
        "allowed_inference": "shared hydrological context",
        "prohibited_inference": (
            "Do not claim stable causal short-lag treatment effects on groundwater."
        ),
    },

    {
        "component": "Methane regulation",
        "indicator": "CH4 response to aerobic/drained management",
        "evidence_source": "Italian field studies + global meta-analyses",
        "evidence_class": "Literature-supported",
        "direction": "decrease",
        "confidence": "high",
        "claim": (
            "Introducing aerobic or drained periods generally reduces CH4 "
            "relative to continuous flooding."
        ),
        "allowed_inference": "directional literature-supported",
        "prohibited_inference": (
            "Do not assign literature percentage reductions directly to Lomellina plots."
        ),
    },

    {
        "component": "Nitrous oxide disservice",
        "indicator": "N2O response to aerobic/drained management",
        "evidence_source": "Italian field studies + global meta-analyses",
        "evidence_class": "Literature-supported",
        "direction": "increase often",
        "confidence": "moderate-high",
        "claim": (
            "N2O commonly increases under aerobic or drained rice-water management, "
            "although the magnitude is strongly context dependent."
        ),
        "allowed_inference": "conditional directional literature-supported",
        "prohibited_inference": (
            "Do not assume a fixed N2O penalty for Lomellina."
        ),
    },

    {
        "component": "Combined climate regulation",
        "indicator": "Combined GWP response",
        "evidence_source": "Italian field studies + global meta-analyses",
        "evidence_class": "Literature-supported",
        "direction": "usually decrease",
        "confidence": "moderate",
        "claim": (
            "Combined GWP usually declines under moderate AWD or drainage because "
            "CH4 reductions outweigh N2O increases, but Italian counterexamples exist."
        ),
        "allowed_inference": "conditional synthesis",
        "prohibited_inference": (
            "Do not state that AWD universally lowers total GHG impact."
        ),
    },

    {
        "component": "Rice production",
        "indicator": "Rice grain yield at 14% humidity",
        "evidence_source": "MEDWATERICE two plots per regime per year",
        "evidence_class": "Local experimental descriptive",
        "direction": "AWD broadly maintained; DFL lower in several strata",
        "confidence": "moderate-low",
        "claim": (
            "Under comparable fertilized management, AWD yield was broadly "
            "maintained relative to WFL in both years."
        ),
        "allowed_inference": "plot-level descriptive consistency",
        "prohibited_inference": (
            "Do not claim a definitive causal treatment effect from n=2 plots per regime."
        ),
    },

    {
        "component": "Wetland-habitat availability",
        "indicator": "Flooded-field habitat opportunity",
        "evidence_source": "Lomellina/Italian ecological studies + RiceFloodIT context",
        "evidence_class": "Observed hydroperiod + literature-supported ecological",
        "direction": "reduced with less/shorter flooding opportunity",
        "confidence": "moderate-high",
        "claim": (
            "Flooded rice fields provide temporary wetland-like habitat, and changes "
            "in flooding timing, duration and continuity alter habitat opportunity."
        ),
        "allowed_inference": "habitat-availability interpretation",
        "prohibited_inference": (
            "Do not convert hydroperiod decline directly into biodiversity-loss estimates."
        ),
    },

]


df = pd.DataFrame(rows)

df.to_csv(
    OUT / "EFS_integrated_tradeoff_matrix.csv",
    index=False
)


print()
print("=" * 120)
print("INTEGRATED EFS TRADE-OFF MATRIX")
print("=" * 120)

print(
    df[
        [
            "component",
            "direction",
            "confidence",
            "evidence_class",
            "allowed_inference",
        ]
    ].to_string(index=False)
)

print()
print("=" * 120)
print("CORE SYNTHESIS")
print("=" * 120)

print(
    "1. Lomellina flooding frequency has declined substantially over 2000-2021."
)

print(
    "2. Local experimental evidence shows that altered water management changes "
    "field water fluxes, ponding and percolation, but the magnitude and ordering "
    "are strongly year dependent."
)

print(
    "3. Reduced flooding is generally associated in the literature with lower CH4, "
    "but often higher N2O; combined GWP usually declines but not universally."
)

print(
    "4. Local AWD yields were broadly maintained relative to WFL under comparable "
    "fertilized management in both study years, while DFL was lower in several strata."
)

print(
    "5. Reduced or less continuous inundation can reduce temporary wetland-habitat "
    "availability, but does not directly quantify biodiversity change."
)

print()
print("=" * 120)
print("GLOBAL INTERPRETATION LIMIT")
print("=" * 120)

print(
    "The integrated result is a conditional ecosystem-service trade-off synthesis, "
    "not a causal ranking of WFL, DFL and AWD and not a universal optimization result."
)

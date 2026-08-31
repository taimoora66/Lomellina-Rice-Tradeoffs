# MODIS-to-RiceFloodIT method recovery

Status: MEASUREMENT DEVELOPMENT
Date: 2026-08-31

## Purpose

Develop an independently reproducible post-2021 flooding metric that is
demonstrably compatible with RiceFloodIT before any 2022–2025 groundwater
outcome is inspected.

The historical RiceFloodIT values are the measurement-validation target.
Groundwater outcomes must not be used to choose satellite-processing rules.

## Recovered with high confidence

### Source satellite product

RiceFloodIT uses MODIS Terra MOD09A1 surface reflectance.

Current continuation product:
MOD09A1.061
MODIS/Terra Surface Reflectance 8-Day L3 Global 500 m SIN Grid V061.

The product:
- is an 8-day Level-3 composite;
- has approximately 500 m spatial resolution;
- uses the MODIS sinusoidal grid;
- provides surface-reflectance Bands 1-7;
- includes quality-assurance information;
- includes observation-day information.

### Study-area MODIS tile

The reconstructed RiceFloodIT/Lomellina spatial extent lies within:

h18v04

This tile assignment was independently calculated from the RiceFloodIT
MODIS-sinusoidal coordinates.

### Spectral quantities

Required reflectance bands:

- Band 1: red
- Band 2: near infrared
- Band 7: SWIR2

Candidate indices documented by the RiceFloodIT method lineage:

NDVI = (NIR - RED) / (NIR + RED)

NDFI = (RED - SWIR2) / (RED + SWIR2)

### Quality filtering

The 2021 RiceFloodIT update states that low- and medium-quality MOD09A1
observations associated with cloud, cirrus, or cloud proximity were filtered.

Exact bit-level reproduction of the authors' quality filter remains to be
verified from the primary methodological documentation.

### Vegetation reliability

The 2016 methodology establishes that MODIS flooding-fraction reliability
declines as rice vegetation develops and uses MODIS NDVI to identify unreliable
predictions.

The exact operational NDVI rule used in each RiceFloodIT release must be
verified before it is hard-coded into the production bridge.

### Temporal aggregation

The updated 2000-2021 analysis reports:

- 330 MOD09A1 images in total;
- 15 images per analysed year;
- acquisitions between March and June.

The 2018 methodology provides more specific seasonal-processing details.

The exact mapping between the earlier DOY-window implementation and the
updated March-June description is a measurement-recovery question and must
be evaluated against RiceFloodIT, not against groundwater outcomes.

### Spatial aggregation

Published flooding fraction is evaluated at approximately 1 x 1 km.
The independently reconstructed RiceFloodIT grid has spacing approximately
926.6254 m, consistent with aggregation on the MODIS sinusoidal grid.

## Unresolved

1. Exact final published empirical MODIS NDFI -> flooding-fraction equation.
2. Exact bit-level QA filter used in the production RiceFloodIT series.
3. Exact updated 2021 seasonal-composite selection/aggregation details.
4. Effects of historical MODIS collection version versus current V061.
5. Exact original georeferenced-product CRS declaration.

These uncertainties must be resolved empirically or documented explicitly.
They must not be filled with outcome-driven assumptions.

## Bridge policy

If the exact original empirical FF equation is recovered from an authoritative
open source, it will be implemented directly.

Otherwise, a compatible bridge may be estimated using historical MODIS V061
predictors and published RiceFloodIT values.

Any calibration will use only historical RiceFloodIT overlap data.

Post-2021 groundwater outcomes are prohibited from:
- model selection;
- parameter tuning;
- temporal-window selection;
- QA-rule selection;
- spatial-aggregation selection.

## Initial development year

2021 only.

2021 is used first to verify:
- data discovery;
- correct MODIS tile;
- band names;
- scale factors;
- QA decoding;
- observation dates;
- CRS alignment;
- overlap with the published RiceFloodIT grid.

Only after this alignment gate passes will historical multi-year bridge
calibration begin.

## Source anchors

Ranghetti et al. 2016:
Testing estimation of water surface in Italian rice district from MODIS
satellite data.
DOI: 10.1016/j.jag.2016.06.018

Ranghetti et al. 2018:
Assessment of Water Management Changes in the Italian Rice Paddies from
2000 to 2016 Using Satellite Data.
DOI: 10.3390/rs10030416

Ranghetti and Boschetti 2022:
Updated trends of water management practice in the Italian rice paddies
from remotely sensed imagery.
DOI: 10.1080/22797254.2021.2002726

NASA:
MOD09A1.061 - MODIS/Terra Surface Reflectance 8-Day L3 Global 500m SIN Grid.
DOI: 10.5067/MODIS/MOD09A1.061

## 2021 CMR acquisition audit — 2026-08-31

CMR collection:
`C2343111356-LPCLOUD`

Product:
`MOD09A1.061`

Tile:
`h18v04`

A temporal-intersection search from 2021-03-01 through 2021-06-30 returned
16 MOD09A1 granules.

The first returned granule begins 2021-02-26 (DOY 057) because its 8-day
composite overlaps the March search interval.

After restricting by COMPOSITE START DATE to March 1 through June 30,
exactly 15 granules remain:

DOY:
065, 073, 081, 089, 097, 105, 113, 121, 129, 137, 145, 153, 161, 169, 177.

Calendar start dates:
2021-03-06 through 2021-06-26.

This provides strong independent support for interpreting the updated
RiceFloodIT statement "15 MOD09A1 images between March and June per year"
as the 15 MOD09A1 8-day composites whose start dates fall within March-June.

This is currently treated as a recovered measurement rule, not yet as
definitive proof of the authors' exact implementation.

No groundwater information was used in this determination.
No satellite granules were downloaded during the discovery stage.

## Native-grid registration result — 2026-08-31

The RiceFloodIT grid was compared directly with the standard MOD09A1 h18v04
sinusoidal tile geometry.

Results:

- MOD09A1 native pixel size: 463.312717 m.
- RiceFloodIT median x spacing: 926.625400 m.
- RiceFloodIT median y spacing: 926.625400 m.
- Spacing ratio: 1.99999993 in both dimensions.
- All 4,331 RiceFloodIT coordinates fall inside h18v04.
- All 4,331 coordinates map to valid native MOD09A1 2x2 blocks.
- Median residual from the implied 2x2 block center: 0.181267 m.
- Maximum residual from the implied 2x2 block center: 0.182391 m.
- Maximum column-edge residual: 0.0000576120 MODIS pixels.
- Maximum row-edge residual: 0.0003903345 MODIS pixels.
- Left-column parity is invariant: [0].
- Top-row parity is invariant: [1].

Interpretation:

The RiceFloodIT grid is effectively registered as a deterministic 2x2
aggregation of native MOD09A1 500-m pixels.

This spatial-registration rule is now treated as recovered and frozen for the
historical measurement bridge.

Future reconstruction should use the exact four native MOD09A1 cells belonging
to each RiceFloodIT coordinate rather than arbitrary interpolation or
reprojection.

No groundwater outcome, QA-rule choice, spectral index choice, or flooding
fraction model was used to establish this geometry.

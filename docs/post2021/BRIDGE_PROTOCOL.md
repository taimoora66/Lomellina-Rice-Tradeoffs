# Historical RiceFloodIT bridge protocol

Status: PRE-GROUNDWATER MEASUREMENT PROTOCOL
Date: 2026-08-31

## Research objective

Determine whether an independently reconstructed MODIS V061 flooding signal
can provide a defensible continuation of RiceFloodIT after 2021.

## Prohibited information during bridge development

Do not inspect:
- 2022-2025 groundwater/FF coefficients;
- post-2021 groundwater association signs;
- post-2021 model p-values;
- post-2021 buffer-specific effects.

Groundwater must play no role in selecting the satellite reconstruction.

## Stage 1 - technical alignment

Development year: 2021.

Required checks:
1. MOD09A1.061 can be discovered reproducibly.
2. Lomellina is covered by MODIS tile h18v04.
3. Required red, NIR and SWIR2 reflectances are available.
4. Scale factors and fill values are correctly applied.
5. QA/state information is available.
6. MODIS sinusoidal coordinates align with the reconstructed RiceFloodIT grid.
7. Acquisition dates cover the documented sowing-period range.

Failure at this stage stops expansion to additional years.

## Stage 2 - historical bridge development

After technical alignment, use historical overlap only.

A temporal calibration/validation split must be fixed before model fitting.

The target is published RiceFloodIT FF, not groundwater.

Candidate predictors may include only physically/methodologically justified
MODIS quantities documented before fitting:
- NDFI
- NDVI
- observation timing
- QA-qualified observation availability

Prefer simple models over flexible machine-learning models.

## Stage 3 - validation levels

### Pixel-year

Report:
- Pearson correlation
- R-squared
- MAE
- RMSE
- mean bias
- calibration intercept
- calibration slope

### Within-pixel anomaly

Demean FF by pixel and compare reconstructed versus published annual anomalies.

Report:
- correlation
- RMSE
- sign agreement
- rank agreement

### Well-buffer exposure

Using the existing groundwater-well coordinates but NOT groundwater outcomes,
compare reconstructed and published exposure at:
- 2 km
- 5 km
- 10 km

Report both levels and within-well annual anomalies.

## Acceptance logic

No single significance threshold defines success.

A bridge is acceptable only if:

1. spatial alignment is correct;
2. temporal ordering is correct;
3. historical FF levels have no severe systematic bias;
4. within-location anomalies are well preserved;
5. 10-km well-buffer anomalies are sufficiently stable for the intended
   groundwater application;
6. validation-year performance is not dependent on one unusual year;
7. there is no obvious collection-induced discontinuity around 2021.

If these conditions are not met, the post-2021 groundwater validation is not
performed with that metric.

## Stage 4 - freeze

Before generating 2022-2025 FF, record:
- product and collection;
- acquisition source;
- MODIS tile(s);
- bands;
- scale factors;
- QA rules;
- NDVI/NDFI definitions;
- seasonal window;
- missing-data rule;
- spatial aggregation;
- bridge equation/model;
- historical calibration years;
- historical validation years;
- acceptance results.

After this freeze, no rule may be altered because of post-2021 groundwater
results.

## Stage 5 - post-2021 generation

Only after bridge acceptance and freeze:
- generate 2022;
- generate 2023;
- generate 2024;
- generate 2025.

The groundwater validation is a separate subsequent stage.

## Spatial registration freeze — 2026-08-31

Historical geometry auditing established that all 4,331 RiceFloodIT
coordinates correspond to deterministic native MOD09A1 2x2 blocks.

Verified geometry:

- MOD09A1 native pixel size: 463.312717 m.
- RiceFloodIT grid spacing: 926.625400 m.
- Spacing ratio: 1.99999993.
- All 4,331 RiceFloodIT coordinates fall inside h18v04.
- All 4,331 coordinates have valid native 2x2 registrations.
- Median residual to implied 2x2 block center: 0.181267 m.
- Maximum residual: 0.182391 m.
- Left-column parity is invariant: [0].
- Top-row parity is invariant: [1].

Therefore the primary historical bridge will:

1. preserve MOD09A1 native 500-m sinusoidal geometry;
2. identify the exact four native cells associated with each RiceFloodIT cell;
3. retain native-cell observations through QA and spectral-index construction;
4. avoid arbitrary interpolation or reprojection;
5. aggregate only according to the recovered RiceFloodIT processing sequence.

Geometry is frozen.

The following remain unfrozen:

- exact QA exclusion rule;
- NDVI reliability rule;
- NDFI-to-flooding-fraction estimator;
- order of native-pixel FF calculation versus 2x2 aggregation;
- final seasonal aggregation rule;
- historical calibration/validation design.

No groundwater outcome was used to establish this geometry.

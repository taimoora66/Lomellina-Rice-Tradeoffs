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

## Historical bridge acceptance protocol — 2026-08-31

### Objective

The purpose of the historical bridge is to determine whether openly available
MOD09A1.061 data can reproduce the spatial and interannual flooding signal
represented by the published RiceFloodIT product closely enough to support a
2022–2025 extension.

The bridge is a measurement-validation exercise. It is not optimized against
groundwater outcomes.

### Data separation

Published RiceFloodIT observations through 2021 are the reference product.

Post-2021 groundwater outcomes remain held out and must not be inspected or
used to choose:

- MODIS QA rules;
- NDVI reliability rules;
- NDFI processing;
- spatial aggregation order;
- temporal aggregation;
- bridge equation;
- historical calibration or validation choices.

### Historical validation design

The same MOD09A1.061 reconstruction procedure must be applied to multiple
historical years for which published RiceFloodIT values already exist.

A bridge rule may not be accepted solely because it performs well in 2021.

Historical years will be divided into:

- development/calibration years;
- held-out historical validation years.

The split must be recorded before fitting the final bridge.

### Admissible processing choices

Candidate rules may differ only where the published/open methodology remains
unresolved.

Candidate differences may include:

- documented MODIS QA interpretations;
- documented or explicitly tested NDVI reliability treatment;
- order of native 500-m processing and 2x2 aggregation;
- temporal summarization across the recovered March–June composites;
- bridge equation linking the recovered spectral signal to RiceFloodIT FF.

The candidate set must remain small, scientifically interpretable and fixed
before historical validation results are inspected.

No arbitrary threshold search or large parameter grid will be used.

### Validation quantities

For each historical validation year, reconstruction will be evaluated against
published RiceFloodIT using complementary diagnostics:

- spatial correlation;
- rank correlation;
- mean bias;
- RMSE or equivalent prediction error;
- regression slope and intercept;
- spatial coverage and missingness;
- preservation of the annual spatial distribution;
- preservation of interannual anomalies when multiple years are combined.

No single metric will determine acceptance.

### Acceptance principle

The bridge will be accepted only if one fixed reconstruction rule shows
consistent agreement with RiceFloodIT across multiple historical years and does
not depend on a single year, location, QA threshold or tuning choice.

A candidate that improves one metric while materially degrading others will
not automatically be preferred.

A candidate showing strong 2021 agreement but unstable historical performance
will be rejected.

If no scientifically defensible candidate reproduces RiceFloodIT adequately,
the 2022–2025 extension will not be presented as a continuation of RiceFloodIT.

### Freeze

After historical validation is accepted, the following will be frozen:

- MODIS product and collection;
- acquisition window;
- tile;
- bands;
- reflectance validity rules;
- QA mask;
- NDVI/NDFI definitions;
- NDVI reliability treatment;
- spatial aggregation order;
- temporal aggregation rule;
- bridge equation;
- calibration years;
- historical validation years;
- missing-data treatment.

Only after this freeze will 2022–2025 flooding values be generated.

Post-2021 groundwater results cannot cause any of these rules to be changed.

## Historical calibration/validation split — 2026-08-31

The historical bridge will use a chronological split fixed before fitting the
final reconstruction model.

Development/calibration years:

- 2017
- 2018
- 2019

Held-out historical validation years:

- 2020
- 2021

The primary validation sample is the year-specific set of RiceFloodIT cells
for which published FF is available in that year.

A secondary robustness analysis will use the balanced set of 3,062 grid cells
present in all five years from 2017 through 2021.

This split is chronological because the intended application is forward
extension beyond 2021.

The held-out 2020-2021 RiceFloodIT FF values may be used only for final
historical bridge evaluation after candidate processing rules and model form
have been fixed using 2017-2019.

Post-2021 groundwater outcomes remain entirely outside this process.

## Bridge Experiment 1 result and confirmatory revision — 2026-08-31

### Experiment 1

The prespecified historical bridge experiment used:

- development: 2017-2019;
- held-out historical validation: 2020-2021;
- three candidate QA rules;
- two candidate 500-m / 1-km aggregation orders;
- a linear FF-on-seasonal-NDFI bridge.

The experiment showed strong historical measurement agreement but the linear
bridge was not accepted or frozen.

Across the six prespecified candidates, pooled 2020-2021 spatial Pearson
correlations were approximately 0.842-0.855 and Spearman correlations were
approximately 0.828-0.838.

However, all linear candidates produced large numbers of FF predictions below
zero. Because flooding fraction is physically bounded to [0,1], the unbounded
linear bridge fails the physical-support criterion.

The 2020 and 2021 RiceFloodIT values have now been inspected and therefore
must not be treated as untouched validation data for any revised bridge.

### Revised bridge architecture

The revised bridge is specified before examining performance in a new
historical confirmation period.

Processing rule:

- MOD09A1.061;
- h18v04;
- the fixed 15 March-June composite starts;
- native 500-m geometry;
- exact previously recovered 2x2 registration to the RiceFloodIT grid;
- require valid red/Band 1 and SWIR2/Band 7 reflectance for NDFI;
- calculate NDFI at native 500-m resolution;
- average valid native NDFI within the exact 2x2 RiceFloodIT block for each
  composite;
- average composite-level NDFI across the fixed seasonal window.

Bridge model:

- fractional-logit mean model;
- FF is the response;
- seasonal NDFI is the sole predictor;
- predictions are therefore constrained to [0,1];
- no clipping, polynomial terms, groundwater variables, threshold search, or
  additional predictors will be introduced for the confirmation experiment.

Model-development evidence:

- 2017
- 2018
- 2019
- 2020
- 2021

New untouched historical confirmation years:

- 2014
- 2015
- 2016

RiceFloodIT performance for 2014-2016 must not be inspected until the revised
processing rule and model have been implemented and fitted using 2017-2021.

The 2014-2016 confirmation is an independent historical check, not a claim of
forward temporal validation.

Post-2021 groundwater outcomes remain entirely outside measurement-bridge
development and validation.

## Bounded bridge confirmation result — 2014-2016

The prespecified bounded confirmation experiment has been completed.

The model was fitted using RiceFloodIT observations from 2017-2021 before
RiceFloodIT FF for the 2014-2016 confirmation period was opened.

Frozen specification tested:

- MOD09A1.061;
- fixed 15 March-June composites;
- native 500-m NDFI;
- exact 2x2 RiceFloodIT registration;
- valid Band 1 and Band 7 reflectance;
- index-then-aggregate spatial processing;
- seasonal mean NDFI;
- fractional-logit bridge;
- seasonal NDFI as the sole predictor.

Fitted development coefficients:

- intercept = -0.589681615540
- seasonal-NDFI slope = 15.145272547528

Independent historical confirmation results:

- 2014 Pearson r = 0.931648; Spearman rho = 0.918460
- 2015 Pearson r = 0.934467; Spearman rho = 0.920736
- 2016 Pearson r = 0.944850; Spearman rho = 0.925436
- pooled 2014-2016 Pearson r = 0.932687
- pooled 2014-2016 Spearman rho = 0.919143
- pooled RMSE = 0.056936
- pooled bias = 0.003707
- no predictions fell outside [0,1]

Balanced-confirmation robustness was similar:

- Pearson r = 0.932790
- Spearman rho = 0.928511

The spatial and physical-range confirmation criteria therefore pass strongly.

Interannual preservation is not yet frozen as adequate. Across only three
confirmation years, annual-mean Pearson correlation was 0.727555, Spearman
correlation was 0.5, annual-mean RMSE was 0.012906, and maximum absolute
annual-mean error was 0.020194.

Because the intended groundwater analysis depends on interannual flooding
anomalies, the measurement bridge will not yet be frozen for post-2021 use.

No model modification or refitting will be made in response to the 2014-2016
confirmation results. Additional historical years will be used only as an
extended confirmation of the already fixed specification and coefficients.

Post-2021 groundwater outcomes remain unused.

## Measurement bridge freeze — extended historical confirmation

The bounded RiceFloodIT-compatible MODIS bridge is now frozen for post-2021
generation.

No further tuning of the historical measurement bridge will be performed.

Frozen satellite product and domain:

- MOD09A1.061
- Terra
- tile h18v04
- fixed 15 March-June composite starts, DOY 065 through 177 at 8-day spacing
- native MODIS sinusoidal geometry
- exact empirically recovered 2x2 native-pixel registration to each
  RiceFloodIT grid cell

Frozen spectral processing:

- Band 1 red
- Band 7 SWIR2
- valid Band 1 and Band 7 reflectance required for NDFI
- NDFI = (red - SWIR2) / (red + SWIR2)
- NDFI calculated at native 500-m resolution
- valid native NDFI values averaged within the exact 2x2 RiceFloodIT block
  for each composite
- composite-level NDFI averaged across the fixed 15-composite season

Frozen bridge model:

- fractional-logit mean model
- seasonal NDFI is the sole predictor
- intercept = -0.589681615540
- seasonal-NDFI slope = 15.145272547528
- no clipping
- no polynomial terms
- no additional satellite predictors
- no groundwater information

The model was fitted using 2017-2021 RiceFloodIT observations.

Independent historical confirmation:

2014-2016:
- pooled Pearson r = 0.932687
- pooled Spearman rho = 0.919143
- pooled RMSE = 0.056936
- no predictions outside [0,1]

Additional untouched confirmation in 2010-2013 used the identical stored
coefficients and unchanged processing rule:

- 2010 Pearson r = 0.950553
- 2011 Pearson r = 0.929359
- 2012 Pearson r = 0.959707
- 2013 Pearson r = 0.949693
- pooled 2010-2013 Pearson r = 0.945527
- pooled 2010-2013 Spearman rho = 0.936057

Across the full independent 2010-2016 annual-mean confirmation:

- Pearson r = 0.957774
- Spearman rho = 0.928571
- annual-mean RMSE = 0.034394
- annual-mean MAE = 0.025897
- annual-mean bias = +0.023164
- maximum absolute annual-mean error = 0.075724

Interpretation:

The bridge passes the spatial-agreement, physical-range, and interannual
covariation requirements sufficiently to support generation of a
RiceFloodIT-compatible post-2021 flooding signal.

The reconstruction must not be described as an exact reproduction of the
original RiceFloodIT algorithm or as direct irrigation volume.

Absolute reconstructed FF levels retain measurable calibration error,
including substantial overprediction in some historical years. Accordingly,
the intended groundwater analysis will emphasize interannual flooding
anomalies rather than interpreting reconstructed FF levels literally.

The measurement specification and coefficients are frozen before generation
of 2022-2025 flooding values and before inspection of post-2021 groundwater
outcomes.

Post-2021 groundwater outcomes remain held out.

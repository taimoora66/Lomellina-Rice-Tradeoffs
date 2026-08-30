# Planned 2022–2025 out-of-sample flooding validation

**Status:** planned; no extension metric has been accepted yet.

## Objective

Construct a 2022–2025 flooding/hydroperiod metric using only open satellite data and a method that can be quantitatively bridged to RiceFloodIT over a substantial historical overlap. Years 2022–2025 will remain untouched by groundwater-outcome model selection until the compatibility gate is decided.

## Preferred scientific design

1. Reconstruct candidate annual March–June surface-water/flooding metrics from open MODIS first, because RiceFloodIT itself is MODIS-based and spatial support is approximately 1 km.
2. Consider Sentinel-1/2 or HLS only as an independent higher-resolution sensitivity/validation layer, not as an uncalibrated replacement for RiceFloodIT.
3. Build the new metric for an overlap window within 2000–2021 **before** examining 2022–2025 groundwater associations.
4. Compare candidate metric against RiceFloodIT at pixel-year and 10-km well-buffer/year support using correlation, bias, RMSE, rank stability, temporal trend agreement and classification/calibration diagnostics.
5. Freeze one bridging transformation (or reject compatibility) before extracting 2022–2025 validation exposures.
6. Use 2022–2025 as a held-out validation period with ARPA groundwater/weather processed under the already frozen outcome/control definitions.

## Compatibility gate

The extension is not accepted merely because it correlates visually with RiceFloodIT. Quantitative thresholds must be fixed before evaluating the post-2021 groundwater result. At minimum the audit must report:

- common-pixel/common-year support;
- year-wise and pooled bias;
- RMSE/MAE;
- Pearson and Spearman correlation;
- agreement of within-location anomalies;
- agreement after aggregation to 2/5/10-km buffers;
- sensitivity to cloud/observation counts;
- evidence of sensor-era discontinuity.

If no defensible bridge exists, the publication remains 2008–2021 and 2022–2025 is not used as pseudo-validation.

## Important separation

The extension project answers two different questions:

1. **Measurement question:** can an open post-2021 metric reproduce the RiceFloodIT construct?
2. **Validation question:** after the measurement bridge is frozen, does the pre-specified groundwater association replicate in 2022–2025?

They must not be optimized simultaneously.

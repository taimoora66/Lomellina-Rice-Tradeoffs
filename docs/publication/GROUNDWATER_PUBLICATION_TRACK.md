# Groundwater publication track

**Status:** exploratory result recovered; confirmatory analysis NOT frozen.
**Started:** 2026-08-30.
**Recovery/update:** 2026-08-31.

## Why this track exists

The earlier fixed-composition irrigation-configuration publication concept remains blocked by unavailable operational topology/capacity evidence and must not be rescued with request-only or unpublished data. The current publication candidate instead uses data that are openly accessible now.

## Candidate empirical question

Are interannual anomalies in remotely observed sowing-period rice inundation associated with subsequent shallow-groundwater dynamics within locations, after accounting for antecedent groundwater conditions, meteorological variability, persistent spatial heterogeneity and common annual shocks?

This is an observational association question. It is **not** a causal recharge study.

## Open evidence base

- RiceFloodIT: 2000–2021, 4,331 pixels, 80,926 pixel-years; balanced panel 2,419 pixels.
- ARPA Pavia groundwater recovery workbook: 2008–2023; current linked analysis uses 2008–2021 to overlap RiceFloodIT.
- ARPA Lombardia precipitation and air temperature: public Socrata datasets, high-frequency measurements.

## Exploratory findings recovered from the chat analysis

These findings are **discovery results** and must not be represented as preregistered or confirmatory.

1. The broad long-term RiceFloodIT flooding signal declined strongly; this is context rather than publication novelty.
2. Local 2–5 km groundwater associations were weak/inconsistent; a broader 10-km landscape signal was more persistent.
3. Simple local flooding → groundwater recharge was rejected: the sign and seasonal timing do not support that mechanism.
4. Weather-controlled within-location annual FF anomalies were associated with late-season groundwater behavior in selected models.
5. The timing pattern was approximately null in June and July and positive by August in selected monthly-weather specifications.
6. One selected spring→August model gave beta ≈ +6.44 depth-m per FF unit, nominal p ≈ 0.027; roughly 0.2 m per one-SD FF anomaly. This is exploratory and not multiplicity/spatial-correlation corrected.
7. Day-of-year adjustment did not explain the August result, but fixed-date interpolation was unstable because ARPA groundwater sampling is sparse.
8. Lead/lag and reverse-timing falsification results improved in the preferred exploratory specifications but were not universally clean across every parameter-heavy sensitivity.
9. A sharp nonlinear threshold was not established; at most there is suggestive asymmetry.
10. Event-study treatment framing was rejected because of sparse outcome data, synchronized transition timing, and pre-trend problems.

## Claims currently allowed

- observational association;
- landscape-scale hydroperiod signal;
- within-location annual anomaly;
- late-season/seasonal timing as an exploratory pattern;
- explicit uncertainty and failed robustness tests.

## Claims currently prohibited

- FF is irrigation volume or AWD/WFL/DFL adoption;
- higher FF causes groundwater depletion;
- lower FF causes recharge loss;
- a causal hydrological threshold exists;
- the selected nominal p-value is confirmatory;
- 32 wells are spatially independent simply because SEs are clustered by well.

## Mandatory confirmatory gates before manuscript drafting

1. Recover exact provenance and exact construction of every analytical variable, especially antecedent groundwater (`pre`).
2. Validate the RiceFloodIT CRS transformation against an authoritative georeferenced source.
3. Use a temporally clean primary groundwater outcome with strictly antecedent groundwater adjustment.
4. Run Conley/spatial-HAC and geographic-block inference for overlapping 10-km exposures.
5. Address analysis multiplicity with a frozen model family/specification curve and simultaneous inference.
6. Audit well depth/screen heterogeneity and sample-selection/missingness.
7. Add defensible open hydrological forcing controls where available; do not imply unobserved canal delivery or pumping is controlled.
8. Re-run once from raw public inputs after the specification is frozen.
9. Independently reproduce a RiceFloodIT-compatible 2022–2025 flooding metric from open MODIS/Sentinel data and use 2022–2025 only as genuine out-of-sample validation if compatibility gates pass.

## Kill rule

If the August/late-season association does not survive spatially robust and multiple-analysis-aware inference under the temporally clean frozen model, the groundwater-coupling headline is abandoned. No switching to another month, buffer or outcome to recover significance.

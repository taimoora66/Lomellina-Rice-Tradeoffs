# Project Status

**Last updated:** 2026-08-31

## Overall status

ACTIVE — PUBLICATION REPRODUCIBILITY RECOVERY

## Completed foundation

- EFS hydroperiod, MEDWATERICE hydrology/production and ecosystem-service synthesis preserved through commit `70b0404`.
- RiceFloodIT 2000–2021 acquisition, integrity QA and balanced-panel analysis completed.
- ARPA Pavia groundwater workbook acquired and audited for the observational publication track.
- ARPA Lombardia precipitation and temperature subsets for 2008–2021 acquired from open Socrata endpoints and QA'd.
- RiceFloodIT ↔ ARPA groundwater spatial alignment established after resolving the MODIS-sinusoidal coordinate behavior.
- Extensive exploratory groundwater analyses and hostile falsification testing completed interactively on 2026-08-30/31.
- Hostile novelty audit indicates a narrow empirical niche remains defensible; broad irrigation/recharge novelty claims are occupied.

## Active publication track

**Candidate:** landscape rice-hydroperiod anomalies × observed shallow-groundwater seasonality.

**Interpretation:** observational association only.

The previous fixed-composition canal-network configuration publication concept is inactive because the required operational/topological inputs are not openly accessible at the needed standard.

## Current hard blockers

1. The exploratory analysis is not yet reproducible end-to-end from raw open inputs.
2. Exact ARPA groundwater and station-master catalogue provenance must be recorded.
3. The exact construction/provenance of every intermediate variable (especially antecedent groundwater `pre`) must be rebuilt.
4. RiceFloodIT georeferencing must be formally validated against an authoritative georeferenced source.
5. 10-km exposure overlap requires spatial-HAC/geographic-block inference.
6. Extensive exploratory model selection requires multiplicity/post-selection-aware inference.
7. A temporally clean primary outcome/control specification must be frozen.

## Current phase

### Phase P0 — Reproducibility recovery and statistical design freeze

No new result-driven specification search is authorized during this phase.

## Immediate tasks

1. Rebuild groundwater cleaning, RiceFloodIT georeferencing, weather processing and panel construction as numbered production scripts.
2. Generate sample-flow/provenance diagnostics from those scripts.
3. Freeze the primary model before re-reading the final coefficient.
4. Implement Conley/spatial-HAC and geographic-block inference.
5. Implement a transparent model-family/specification-curve analysis with simultaneous/multiplicity-aware inference.
6. Audit well depth/screen heterogeneity and sample missingness.
7. Re-run the full 2008–2021 discovery sample once from raw open inputs.

## Parallel validation phase

### Phase P1 — Open 2022–2025 flooding reconstruction

Construct a post-2021 flooding metric independently from open MODIS/Sentinel data, bridge it to RiceFloodIT on historical overlap, freeze the bridge, and only then evaluate 2022–2025 groundwater as held-out validation.

See `docs/publication/NEXT_STAGE_2022_2025_VALIDATION.md`.

## Kill rule

If the late-season association fails spatially robust and multiple-analysis-aware inference under the frozen temporally clean model, abandon the groundwater-coupling headline. Do not switch months, buffers or outcomes to recover significance.

## Repository branch

Current recovery branch: `publication-groundwater-reproducibility`.

---

## 2026-08-31 — Groundwater publication reproducibility milestone

The 2008–2021 groundwater publication data pipeline has now been reconstructed and run locally from source/raw inputs using the numbered production scripts in:

`scripts/04_publication_groundwater/`

### Completed computational reconstruction

PASS:

- ARPA groundwater cleaning and duplicate handling.
- ISS superficial-aquifer selection.
- RiceFloodIT numerical georeferencing reconstruction.
- ARPA meteorological download and monthly aggregation.
- 2 km, 5 km and 10 km well-buffer RiceFloodIT exposure construction.
- 2008–2021 discovery-panel construction.
- Executable pipeline QA tests.

### Reproduced groundwater QA

- Raw groundwater observations: 5,946.
- Raw monitoring stations: 68.
- Duplicate station-date groups: 249.
- Conflicting duplicate station-date groups: 1.
- Clean groundwater observations: 5,696.
- ISS monitoring wells: 37.
- Clean ISS observations: 3,084.
- ISS discovery well-year grid: 518.
- Observed ISS well-years: 330.
- Well-years with Jan-Feb antecedent groundwater and August groundwater: 221.

### Reproduced RiceFloodIT QA

- Pixel-year rows: 80,926.
- Years: 2000–2021.
- Unique pixels: 4,331.
- Balanced 22-year pixels: 2,419.
- Median positive raster-grid spacing: approximately 926.6254 m.
- ISS wells checked against transformed RiceFloodIT support: 37.
- Median nearest-pixel distance: approximately 0.54 km.
- Maximum nearest-pixel distance: approximately 16.70 km.

The numerical transformation is internally consistent with a MODIS sinusoidal grid and the Lomellina spatial extent, but authoritative original-product CRS confirmation remains open.

### Reproduced weather QA

Precipitation raw rows:

- 2008–2010: 574,046.
- 2011–2020: 2,322,108.
- 2021: 323,353.

Temperature raw rows:

- 2008–2010: 408,884.
- 2011–2020: 2,646,837.
- 2021: 376,004.

Monthly sensor QA:

- Precipitation sensor-month rows: 1,004.
- Valid precipitation sensor-months: 952.
- Temperature sensor-month rows: 1,172.
- Valid temperature sensor-months: 1,079.
- Unique sensors represented: 11 for precipitation and 11 for temperature.

### Reproduced RiceFloodIT well-buffer exposure QA

2 km:

- Median pixels: 9.
- Median balanced pixels: 4.
- Station-years with FF: 402.

5 km:

- Median pixels: 52.
- Median balanced pixels: 25.
- Station-years with FF: 433.

10 km:

- Median pixels: 182.
- Median balanced pixels: 72.
- Station-years with FF: 479.

Overall exposure grid:

- Rows: 518.
- Wells: 37.
- Years: 14.

### Reproduced discovery-panel QA

- Rows: 518.
- Wells: 37.
- Years: 14.
- Jan-Feb antecedent groundwater + August groundwater rows: 221.
- Candidate primary complete rows: 194.
- Candidate primary complete wells: 32.

Candidate complete rows by year:

- 2008: 10
- 2009: 6
- 2010: 9
- 2011: 10
- 2012: 6
- 2013: 12
- 2014: 13
- 2015: 6
- 2016: 20
- 2017: 25
- 2018: 28
- 2019: 21
- 2020: 10
- 2021: 18

No groundwater-RiceFloodIT regression was fitted during this reconstruction stage.

### Executable QA gate

`tests/test_publication_pipeline.py` was run locally with Python 3.13.15 and pytest 9.1.1.

Result:

`4 passed`

The tests currently verify groundwater reconstruction, RiceFloodIT reconstruction, exposure-panel construction and discovery-panel construction.

### Current interpretation

The 2008–2021 raw-to-panel computational pipeline is considered locally reproducible.

This does NOT yet mean that the groundwater scientific association is confirmed. The previous August/10-km result remains exploratory until the statistical model, spatial inference and multiplicity-aware analysis are frozen and rerun.

### Remaining reproducibility gates

OPEN:

- Authoritative confirmation of the original RiceFloodIT coordinate reference system / georeferenced source product.
- Exact stable public acquisition route and provenance for the Pavia ARPA groundwater workbook.
- Formal per-well spatial-support / edge-well diagnostic.
- Clean-clone end-to-end reconstruction from GitHub.
- Final environment/requirements reproducibility check.
- Frozen statistical-model and inference specification.

### Next research stage

The next new-data stage is development of a RiceFloodIT-compatible flooding metric for 2022–2025 using openly available satellite data.

The measurement bridge must first be developed and evaluated on historical RiceFloodIT overlap years.

Post-2021 groundwater outcomes must not be inspected while the satellite reconstruction method is being tuned.


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

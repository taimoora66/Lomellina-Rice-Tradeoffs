# Lomellina Rice Trade-offs

Open-data research on rice hydroperiod change, hydrology and ecosystem-service trade-offs in Lomellina (Pavia, northern Italy).

## Repository state

The repository now contains two clearly separated research products:

1. **EFS synthesis** — the completed course-oriented hydroperiod and ecosystem-service analysis preserved in `scripts/03_efs_analysis/` and its associated outputs.
2. **Groundwater publication track** — a new observational, open-data research track reconstructed from exploratory work conducted on 2026-08-30/31. Its documentation is in `docs/publication/` and scripts in `scripts/04_publication_groundwater/`.

The earlier fixed-composition irrigation-configuration publication concept is retained as project history but is no longer the active publication route because its key operational/topological inputs are not openly available at the required standard.

## Reproducibility principle

The publication track is designed around data that can be accessed openly without author requests, private irrigation-association data, institutional-only access or unpublished code.

Large raw files are intentionally excluded from Git. The repository should instead contain:

- stable source identifiers and URLs;
- acquisition scripts;
- checksums and provenance records;
- deterministic cleaning and linkage scripts;
- compact diagnostics;
- frozen statistical specifications;
- final tables/figures generated from the pipeline.

## Current publication status

**Discovery result only — not submission-ready.**

The candidate signal is a within-location association between annual landscape-scale sowing-period flooding anomalies and late-season shallow-groundwater dynamics. The simple recharge interpretation has been rejected. Spatial dependence, post-selection/multiplicity, temporal ordering and data-provenance gates remain mandatory before the result can be treated as confirmatory.

Read in this order:

1. `PROJECT_MASTER.md`
2. `PROJECT_STATUS.md`
3. `docs/publication/GROUNDWATER_PUBLICATION_TRACK.md`
4. `docs/publication/HOSTILE_AUDIT_2026-08-31.md`
5. `docs/publication/NEXT_STAGE_2022_2025_VALIDATION.md`
6. `docs/data/ARPA_PUBLICATION_REPRODUCIBILITY.md`

## Immediate research priorities

1. reconstruct the publication analysis end-to-end from raw open inputs;
2. validate RiceFloodIT georeferencing and exact ARPA provenance;
3. freeze a temporally clean primary model;
4. run spatial-HAC/geographic-block inference and multiplicity-aware specification analysis;
5. independently reconstruct a RiceFloodIT-compatible 2022–2025 flooding metric and use it only as held-out validation after the measurement bridge is frozen.

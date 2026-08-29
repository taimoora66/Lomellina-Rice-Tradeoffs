# Project Status

Last updated: 2026-08-29

## Current Phase

Phase 1B — Reproducibility and project foundation

## Overall Status

ACTIVE

## Completed

- Hostile independent audit completed.
- Original over-scoped research design rejected.
- EFS and publication tracks separated.
- EFS research question frozen.
- Publication research question frozen.
- Spatial scope frozen.
- Temporal scope frozen.
- Publication hypotheses frozen.
- Claim boundaries established.
- GO/NO-GO framework established.
- Private GitHub repository created.
- Local repository connected to GitHub.

## Current Task

Build and freeze the project continuity and reproducibility infrastructure.

## Immediate Tasks

1. Create project directory structure.
2. Create `.gitignore`.
3. Add `PROJECT_MASTER.md`.
4. Add protocol files.
5. Add decision log.
6. Add data-access register.
7. Add claim register.
8. Verify repository.
9. Commit Phase-1 foundation.
10. Push to GitHub.
11. Create tag `v0.1-protocol-freeze`.

## Next Phase

Phase 2 — Evidence and Data Acquisition

### Phase 2A

Systematic literature and competitor verification.

### Phase 2B

Acquire and inventory:

- MEDWATERICE
- RiceFloodIT
- DUSAF
- RIRU
- ARPA datasets
- ecological/protected-area GIS layers

### Phase 2C

Prepare publication-critical data requests.

## Publication Path P1

Status:

NOT YET AUTHORIZED

Outstanding requirements:

- novelty verification;
- hydrological model access;
- operational irrigation data;
- groundwater constraints;
- return-flow constraints;
- independent validation.

## Sentinel Publication Path P2

Status:

FALLBACK ONLY

Requires independent novelty and validation assessment.

## Optimization

Status:

PROHIBITED

Optimization cannot begin until the fixed-composition configuration
effect exceeds combined uncertainty.

## Current Hard Stop

Do not begin new modelling before Phase 2 evidence and data audits are complete.

## Next Exact Action

Finish and commit the Phase-1 repository foundation.
## Phase 2A Update — 2026-08-29

Hostile novelty search started.

Current G1 verdict:

**AMBER / OPEN**

Broad novelty claims have been rejected for:

- spatial irrigation allocation;
- upstream/downstream positioning;
- staggered irrigation;
- peak-demand reduction;
- canal scheduling;
- groundwater-canal coupling.

The surviving candidate contribution remains the strict
fixed-composition configuration/synchronization experiment.

### Next Exact Action

Identify and fully compare the strongest 8–15 competitor studies against
the fixed-composition criteria before declaring G1 GO or NO-GO.

## G1 Interim Decision — 2026-08-29

The initial hostile competitor audit now contains 15 bibliographically
verified competitors.

**G1 status: GO-CONDITIONAL / REFRAME**

Meaning:

The broad publication concept is rejected as novel.

The publication track may continue only around the narrow hypothesis
that irrigation-regime configuration has an independent hydrological
effect when management composition is held exactly constant.

This is not final novelty certification.

Forward/backward citation searching and a final pre-submission novelty
audit remain mandatory.

### Next Exact Action

Begin Phase 2B data acquisition and reproducibility audit, starting with
MEDWATERICE and RiceFloodIT, while continuing targeted citation chasing
of the strongest novelty competitors.

## Current Phase Time Estimate

Phase 2 — Evidence and data acquisition

Estimated duration:

**7–12 working days**

Current subsection:

**Phase 2B — Open-data acquisition and provenance audit**

Immediate order:

1. MEDWATERICE
2. RiceFloodIT
3. core GIS layers
4. restricted publication-critical data requests

## G3 Decision — MEDWATERICE

**Status: GO WITH RESTRICTIONS**

The Lomellina 2019–2020 field datasets are usable for constrained
field-scale hydrological and production evidence.

Main limitations:

- only one instrumented plot per irrigation regime;
- repeated measurements are not independent replicates;
- management regimes include seeding-method differences;
- groundwater piezometer layouts differ among treatments/years;
- percolation includes derived/model-estimated quantities;
- local GHG observations are inadequate.

### Next Exact Action

Perform numerical QA and reproduction of MEDWATERICE key hydrological
variables, while beginning RiceFloodIT acquisition for the independent
2000–2021 historical hydroperiod analysis.

## RiceFloodIT G2 Decision

**G2 = GO WITH DESIGN CONTROL**

RiceFloodIT version 2021.01 was acquired from Zenodo and verified by
file size and MD5 checksum.

### QA results

- temporal coverage: 2000–2021;
- 22 complete years;
- 80,926 pixel-year observations;
- 4,331 unique pixels;
- seven stable subdistricts A–G;
- no missing values;
- no duplicate pixel-year records;
- FF values remain within the documented 0–1 range;
- no pixel changes subdistrict through time.

### Spatial-support issue

Only 2,419 pixels occur in all 22 years.

Because the annual spatial sample changes substantially through time,
the primary long-term FF analysis will use the fixed 2,419-pixel
balanced panel.

The changing-support full dataset will be retained as a sensitivity
analysis.

### Observation-support issue

Number of MODIS images contributing to a pixel-year FF estimate ranges
from 1 to 6.

Primary balanced-panel results will therefore be complemented by
sensitivity analyses based on MODIS image-count support.

### Inference rule

Pixel-year observations are repeated spatial-temporal measurements,
not independent experimental replicates.

Long-term statistical inference will therefore be conducted on annual
and/or explicitly modelled spatial-temporal structure rather than by
treating 80,926 records as independent observations.

## Frozen Result R1 — RiceFloodIT Long-Term Hydroperiod Signal

### Analytical population

Primary analysis uses the 2,419 RiceFloodIT pixels observed in every
year from 2000 through 2021.

Changing-support full-sample results are retained as sensitivity
analysis.

### Primary result

Mean balanced-panel FF:

- 2000: 0.383478
- 2021: 0.082912

Equal six-year period comparison:

- 2000–2005 mean FF: 0.331694
- 2016–2021 mean FF: 0.123661
- absolute change: -0.208033
- relative change: -62.72%

### Trend estimates

Primary balanced-panel OLS descriptive slope:

- -0.013236 FF units/year

Theil-Sen robust slope:

- -0.013313 FF units/year
- 95% interval: -0.016348 to -0.010195

### Temporal-dependence robustness

Residual lag-1 correlation:

- 0.278

Durbin-Watson:

- 1.432

Residual moving/circular block bootstrap:

Block length 3:
- 95% slope interval: -0.016332 to -0.010126

Block length 4:
- 95% slope interval: -0.016368 to -0.010096

Block length 5:
- 95% slope interval: -0.016399 to -0.009991

All tested intervals remained below zero.

### Sensitivity

The declining trajectory is also present when:

- all available yearly pixels are used;
- balanced-panel observations with count < 3 are excluded;
- FF values are weighted by MODIS-image count.

The independent RiceFloodIT water-seeded proportion (WS) series also
shows a negative temporal trajectory.

### Interpretation Boundary

This result supports a marked long-term decline in the remotely sensed
sowing-period flooding signal.

It does not by itself establish:

- causal effects of a particular irrigation regime;
- proportional biodiversity loss;
- proportional groundwater-recharge loss;
- proportional irrigation-water saving;
- continuous flooded-day duration.


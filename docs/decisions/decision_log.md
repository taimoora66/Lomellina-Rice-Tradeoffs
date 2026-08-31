# Scientific Decision Log

This file records substantive scientific and methodological decisions.

Old decisions must not be silently rewritten.

If a decision changes, append a new dated entry explaining:

- what changed;
- why;
- supporting evidence;
- consequences for prior analyses.

---

## 2026-08-29 — Original Integrated Design Rejected

Decision:

Do not proceed with the original large integrated remote-sensing,
hydrology, greenhouse-gas, yield, biodiversity and optimization design.

Reason:

The hostile audit identified excessive scope, inadequate validation,
weak proxies, existing competing literature and substantial feasibility
risks.

Status:

FROZEN

---

## 2026-08-29 — Separate EFS and Publication Outputs

Decision:

The EFS technical report and publication-track analysis are separate
scientific products.

Reason:

The EFS report must remain feasible even if publication-critical
hydrological datasets cannot be obtained.

Status:

FROZEN

---

## 2026-08-29 — Historical Hydroperiod Period

Decision:

Use 2000–2021 as the authoritative historical hydroperiod period for the
initial EFS analysis.

Reason:

This corresponds to the existing validated RiceFloodIT evidence base.

Status:

FROZEN

---

## 2026-08-29 — Publication Hypothesis

Decision:

Test whether management placement and temporal synchronization have an
independent hydrological effect while management composition is fixed.

Status:

PROVISIONAL NOVELTY

Requirement:

Must survive the Phase-2 literature and competitor audit.

---

## 2026-08-29 — Ecological Terminology

Decision:

Without direct biological observations, describe hydroperiod-related
outputs as wetland-habitat availability or landscape water connectivity,
not biodiversity.

Status:

FROZEN

---

## 2026-08-29 — Optimization Rule

Decision:

Optimization cannot begin unless the fixed-composition configuration
effect exceeds relevant observational and model uncertainty.

Status:

FROZEN

Failure of this condition requires optimization to stop.

---

## 2026-08-31 — Publication track pivot to open-data groundwater analysis

**Decision:** The earlier fixed-composition canal-network/configuration publication concept is no longer the active publication route. The active candidate is an observational RiceFloodIT × ARPA groundwater analysis using only data already openly accessible.

**Reason:** Operational/topological evidence needed for the configuration experiment is not openly available at the required standard, whereas RiceFloodIT, ARPA groundwater and ARPA meteorology support an independent empirical panel.

**Restriction:** No author requests, AIES requests, unpublished code or restricted/institutional-only data may be treated as required inputs.

**Interpretation boundary:** Association only; no causal recharge/depletion claim.

## 2026-08-31 — Exploratory results reclassified as discovery only

**Decision:** All groundwater coefficients and nominal p-values produced during 2026-08-30/31 interactive exploration are classified as discovery results.

**Reason:** Multiple months, spatial supports, transformations, falsifications and model structures were explored before the August/10-km pattern emerged. Spatial overlap among 10-km exposure fields also invalidates reliance on well-clustered SEs alone.

**Consequence:** A new protocol freeze cannot retroactively make these results confirmatory. Spatially robust and multiplicity-aware inference are mandatory.

## 2026-08-31 — Post-2021 extension designated held-out validation

**Decision:** Prioritize independent reconstruction of a RiceFloodIT-compatible 2022–2025 flooding metric using open satellite data.

**Guardrail:** The measurement bridge must be chosen using overlap with RiceFloodIT, without using 2022–2025 groundwater outcomes. If the bridge cannot be defended quantitatively, the extension is rejected.

---

## 2026-08-31 — Decision: freeze reconstructed 2008–2021 data foundation

### Decision

The 2008–2021 groundwater publication data foundation is accepted as locally computationally reproducible and will be treated as the production baseline for subsequent work.

This decision applies to DATA RECONSTRUCTION ONLY. It does not confirm the previously discovered groundwater association.

### Evidence

The following production scripts were run locally:

- `01_groundwater_clean.py`
- `02_ricefloodit_georeference.py`
- `03_weather_clean_aggregate.py`
- `04_build_well_exposures.py`
- `05_build_analysis_panel.py`

The reconstructed pipeline reproduced the expected groundwater, satellite, weather, exposure and analysis-panel QA counts.

Key reproduced values include:

- 5,946 raw groundwater records.
- 5,696 cleaned groundwater records.
- 37 ISS wells.
- 80,926 RiceFloodIT pixel-years.
- 4,331 RiceFloodIT pixels.
- 2,419 balanced RiceFloodIT pixels.
- 518 ISS well-year grid rows for 2008–2021.
- 479 well-years with 10-km FF support.
- 221 well-years with Jan-Feb antecedent groundwater and August groundwater.
- 194 candidate complete observations across 32 wells.

Automated QA:

- `tests/test_publication_pipeline.py`
- Result: 4/4 tests passed locally.

### Important methodological correction

The undocumented exploratory variable `pre` is not used in the production pipeline.

Groundwater timing variables are now explicitly reconstructed from raw observation dates, including:

- last valid Jan-Feb groundwater measurement;
- Jan-Feb mean;
- Jan-Mar mean;
- August measurements;
- Apr-May mean;
- other monthly summaries.

This removes a major earlier provenance ambiguity.

### Exploratory-history policy

Recovered scripts and exploratory outputs are retained as research-history provenance but are not part of the production pipeline.

They document the researcher degrees of freedom that produced the exploratory late-season/10-km signal and therefore must not be presented as preregistered analysis.

### Generated-data policy

Files in `data/processed/publication_groundwater/` are generated artifacts.

They should be reconstructed by production scripts and should not be treated as independent source data.

Compact QA outputs, manifests, code and documentation may be version controlled.

### Open data/provenance gates

The following remain unresolved and must remain visible:

1. authoritative RiceFloodIT CRS/source-product confirmation;
2. exact public acquisition provenance for the Pavia ARPA groundwater workbook;
3. final station-master provenance verification;
4. spatial edge/support diagnostics;
5. clean-clone reproduction.

### Scientific-analysis status

No new groundwater-RiceFloodIT regression was fitted during the reconstruction stage.

The previous August/10-km association remains exploratory.

The following must be frozen before the next confirmatory discovery-period model is interpreted:

- primary outcome;
- antecedent groundwater definition;
- exposure definition;
- weather specification;
- spatial-HAC inference;
- geographic-block robustness;
- multiplicity/specification universe;
- stopping rule.

### 2022–2025 validation policy

The next satellite-development stage will construct a RiceFloodIT-compatible flooding metric using only openly accessible satellite data.

The method must first be calibrated/validated against historical RiceFloodIT overlap years.

The post-2021 groundwater outcome data are designated held-out validation information and must not be inspected while choosing or tuning the satellite measurement bridge.

If the historical bridge cannot reproduce RiceFloodIT adequately, the 2022–2025 groundwater validation will not proceed using that metric.


---

## 2026-08-31 — Decision: freeze native MOD09A1-to-RiceFloodIT geometry

### Decision

The RiceFloodIT approximately 1-km grid will be treated as a deterministic
2x2 aggregation of native MOD09A1 500-m pixels.

### Evidence

The registration audit produced:

- 4,331 RiceFloodIT coordinates.
- 4,331 valid native 2x2 MOD09A1 registrations.
- 0 coordinates outside MODIS tile h18v04.
- MOD09A1 pixel size: 463.312717 m.
- RiceFloodIT grid spacing: 926.625400 m.
- Grid-spacing ratio: 1.99999993.
- Median implied 2x2 block-center residual: 0.181267 m.
- Maximum implied 2x2 block-center residual: 0.182391 m.
- Invariant left-column parity: [0].
- Invariant top-row parity: [1].

### Interpretation

The observed approximately 327-m distance from a RiceFloodIT coordinate to the
nearest individual 500-m MODIS pixel center is the expected diagonal
half-pixel offset when the RiceFloodIT coordinate lies at the center of four
adjacent MOD09A1 cells.

The sub-metre residual to the implied 2x2 block center demonstrates that this
offset is systematic rather than a CRS or geolocation mismatch.

### Production rule

Future satellite reconstruction will preserve MOD09A1 native geometry and map
each RiceFloodIT coordinate to its exact four-cell native MODIS block.

No bilinear interpolation or arbitrary 1-km reprojection will be used for the
primary RiceFloodIT bridge.

### What remains unfrozen

This decision freezes geometry only.

The following remain open:

- exact RiceFloodIT MODIS QA exclusion rule;
- exact NDFI-to-flooding-fraction estimator;
- order of 500-m FF calculation versus 2x2 aggregation;
- NDVI reliability rule;
- seasonal aggregation details beyond the recovered 15-composite
  March-June acquisition sequence;
- historical bridge calibration and validation design.

No groundwater outcome was used in this decision.

## Historical exploratory groundwater model reproduction

The previously reported exploratory August groundwater association was
reproduced from the preserved exploratory pre-weather panel combined with
the publication weather reconstruction.

Recovered exploratory specification:

`d_spr_8 ~ ff10_anom + P_A8 + T_A8 + pre + C(station) + C(year)`

Definitions:
- `d_spr_8 = m8 - aprmay`;
- `ff10_anom` is `ff_10` centered on the station-specific historical mean;
- `pre` is the groundwater-state variable preserved in the recovered
  exploratory panel;
- standard errors are clustered by groundwater station.

Reproduced result:
- N = 191;
- wells = 32;
- beta = 6.440268535973067;
- clustered SE = 2.907251833007603;
- p = 0.026743407265692277;
- 95% CI = [0.7421596492901097, 12.138377422656024].

The reproduced coefficient differs from the previously documented
6.440269 by approximately -4.64e-07, and the p-value differs from
0.026743 by approximately +4.07e-07.

Status: PASS for historical computational reproduction.

This result remains exploratory. Reproduction does not make the
specification confirmatory and does not resolve spatial dependence,
post-selection, or multiplicity.

## Historical groundwater spatial-inference freeze

This inference design was frozen before inspection of the clean historical
publication-model coefficient.

Primary exposure geometry:
- the primary flooding exposure is the mean flooding fraction within 10 km
  of each groundwater well;
- two 10-km supports may overlap for wells separated by as much as
  approximately 20 km;
- therefore 20 km is the prespecified primary spatial-HAC cutoff.

Geometry audit:
- 37 groundwater wells;
- median pairwise distance = 27.09 km;
- median neighbors within 10 km = 3;
- median neighbors within 20 km = 11;
- median neighbors within 30 km = 22;
- median neighbors within 40 km = 28.

Frozen primary covariance estimator:
- OLS coefficient from the frozen historical publication specification;
- station-cluster component to allow arbitrary serial covariance within well;
- same-year spatial-HAC component with a Bartlett distance kernel and
  20-km cutoff;
- subtract the observation-level HC0 intersection component to avoid
  double-counting the diagonal.

Frozen spatial-HAC sensitivity cutoffs:
- 30 km;
- 40 km.

The 20-km cutoff is primary because it follows directly from the geometry of
the 10-km exposure support and was selected before viewing the clean-model
result. Larger cutoffs are conservative sensitivity analyses and will not be
selected according to statistical significance.

Geographic-block audit:
- 20-km shifted grids produce only 10-11 occupied blocks;
- 30-km grids produce 6-7 occupied blocks;
- 40-km grids produce 4-6 occupied blocks.

Because these cluster counts are small, ordinary block-cluster asymptotic
p-values will not be treated as primary inference. Twenty-km shifted blocks
will instead be used for geographic influence / leave-block-out coefficient
stability diagnostics.

The previously reproduced exploratory +6.44 result was not used to select
the spatial cutoff or covariance design.

## Historical groundwater publication-model freeze

This specification was frozen before inspection of the clean historical
publication-model coefficient.

Primary historical model:

`gw_aug_mean_m ~ ff_10_anom + gw_pre_last_janfeb_m + P_A8 + T_A8 + C(station) + C(year)`

Definitions:
- outcome: mean August groundwater depth, `gw_aug_mean_m`;
- exposure: within-station anomaly in the 10-km flooding fraction,
  `ff_10_anom`;
- antecedent groundwater: last valid January-February groundwater
  observation, `gw_pre_last_janfeb_m`;
- meteorological controls: cumulative April-August precipitation `P_A8`
  and April-August day-weighted mean temperature `T_A8`;
- fixed effects: groundwater station and calendar year.

The primary coefficient is the coefficient on `ff_10_anom`.

No alternative outcome month, flooding radius, antecedent-groundwater
construction, weather specification, transformation, or model form will
replace the primary model according to statistical significance.

Frozen inference:
- primary: combined station-serial plus same-year 20-km Bartlett
  spatial-HAC covariance;
- spatial sensitivities: 30 km and 40 km;
- benchmark: conventional station-clustered covariance;
- 20-km shifted geographic grids: coefficient-stability diagnostics only.

Multiplicity / historical selection audit:
- the recovered exploratory monthly-timing script contains at least nine
  directly comparable flooding-coefficient tests:
  three target months under cumulative weather plus pre,
  three target months under separate weather plus pre,
  and three target months under cumulative weather without pre;
- nine is therefore a documented lower bound, not the complete historical
  specification-search universe;
- the historical exploratory nominal p-value will be reported with at least
  a nine-test Bonferroni audit;
- exact Holm and Benjamini-Hochberg adjustments will be reported only if all
  nine corresponding nominal p-values are recovered;
- the multiplicity audit will not be used to select a replacement model.

The clean publication model is distinct from the recovered exploratory
spring-to-August model and is not expected to reproduce its +6.44
coefficient.

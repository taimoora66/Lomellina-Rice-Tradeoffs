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


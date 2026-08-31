# Publication reproducibility checklist

This checklist is a release gate, not a planning wish list.

## A. Source provenance

- [ ] Exact ARPA groundwater catalogue/download URL recorded.
- [ ] Exact ARPA weather station-master dataset identifier recorded.
- [x] ARPA meteorological Socrata dataset IDs recorded.
- [x] Recovery-copy SHA-256 checksums recorded.
- [ ] RiceFloodIT source DOI/version/checksum linked directly from publication-track docs.
- [ ] Satellite source/product identifiers for the 2022–2025 extension frozen before extraction.

## B. Raw-to-analysis pipeline

- [x] Recovered exploratory scripts preserved as historical code.
- [x] Reproducible ARPA weather download script added.
- [ ] Groundwater cleaning script rebuilt from raw workbook.
- [ ] RiceFloodIT coordinate transformation rebuilt and formally validated.
- [ ] Weather daily/monthly aggregation rebuilt.
- [ ] Well-buffer FF exposure construction rebuilt.
- [ ] Final panel builder rebuilt, including an explicit definition of antecedent groundwater (`pre`).
- [ ] One command or documented command sequence recreates all analytical inputs from raw open data.

## C. Statistical design freeze

- [ ] Primary exposure frozen.
- [ ] Primary outcome frozen with strictly antecedent groundwater adjustment.
- [ ] Weather control family frozen.
- [ ] Spatial inference method/bandwidth family frozen before reading final estimates.
- [ ] Multiplicity/specification family frozen.
- [ ] Well/screen-depth exclusions/interactions frozen.
- [ ] Missingness/sample-flow rules frozen.
- [ ] Claim boundaries frozen.

## D. Confirmatory rerun

- [ ] Clean clone passes acquisition/processing tests.
- [ ] Discovery-sample analysis rerun once from raw inputs after freeze.
- [ ] Conley/spatial-HAC results generated.
- [ ] Geographic-block/small-sample sensitivity generated.
- [ ] Specification-curve/multiplicity-aware inference generated.
- [ ] Influence and well-depth/screen-depth diagnostics generated.
- [ ] Full sample-flow table generated.

## E. 2022–2025 held-out validation

- [ ] Candidate open flooding metric reconstructed without post-2021 groundwater tuning.
- [ ] Historical overlap bridge quantified against RiceFloodIT.
- [ ] Compatibility decision frozen.
- [ ] Post-2021 exposure calculated only after bridge freeze.
- [ ] 2022–2025 outcome/control definitions copied unchanged from the frozen discovery design.
- [ ] Validation result reported regardless of direction/significance.

## F. Release quality

- [ ] No absolute local paths in production scripts.
- [ ] No request-only or unpublished required inputs.
- [ ] Environment/version lock recorded.
- [ ] `git diff --check` clean.
- [ ] Generated outputs trace to script + input checksum.
- [ ] README and project status match actual repository state.
- [ ] Final tag created only after a clean-clone reproduction test.

---

## 2026-08-31 reproducibility milestone

### Completed

- [x] Groundwater cleaning script rebuilt from the raw ARPA workbook.
- [x] Duplicate station-date QA reproduced.
- [x] Conflicting duplicate handling documented and reproduced.
- [x] ISS superficial-aquifer restriction reproduced.
- [x] RiceFloodIT numerical georeferencing script rebuilt.
- [x] ARPA meteorological download script operational.
- [x] ARPA meteorological daily/monthly QA and aggregation rebuilt.
- [x] Well-buffer FF exposure construction rebuilt for 2 km, 5 km and 10 km.
- [x] Balanced-pixel and contemporaneous-pixel exposure variants reconstructed.
- [x] Final 2008–2021 discovery-panel builder rebuilt.
- [x] Undocumented exploratory `pre` variable removed from the production pipeline.
- [x] Explicit antecedent groundwater variables created.
- [x] Explicit August groundwater variables created.
- [x] Compact QA outputs generated for pipeline stages.
- [x] Automated reproducibility tests added.
- [x] Automated pipeline tests pass locally: 4/4.
- [x] Python environment snapshot recorded.
- [x] Production scripts separated from recovered exploratory scripts.
- [x] Processed analytical CSVs treated as regenerable artifacts rather than source data.

### Still open before publication/release

- [ ] Verify RiceFloodIT CRS against an authoritative original georeferenced product or source.
- [ ] Document exact stable public acquisition URL/workflow for the Pavia ARPA groundwater workbook.
- [ ] Replace or document the ARPA weather-station-master acquisition with an exact official dataset route.
- [ ] Add per-well RiceFloodIT spatial-support/edge-distance diagnostic.
- [ ] Add physical-value anomaly diagnostic for ARPA weather, including extreme/negative precipitation records.
- [ ] Perform a clean-clone reconstruction in a new directory/environment.
- [ ] Confirm generated processed data are correctly excluded from Git tracking.
- [ ] Confirm all required raw-data acquisition instructions are present in the runbook.
- [ ] Freeze primary groundwater outcome.
- [ ] Freeze antecedent groundwater definition.
- [ ] Freeze primary FF exposure definition.
- [ ] Freeze meteorological controls.
- [ ] Freeze Conley/spatial-HAC bandwidths.
- [ ] Freeze geographic-block robustness design.
- [ ] Freeze multiplicity/specification universe.
- [ ] Freeze scientific go/no-go rule.
- [ ] Run one final 2008–2021 confirmatory rerun after freeze.
- [ ] Build historical MODIS-to-RiceFloodIT measurement bridge.
- [ ] Freeze post-2021 flooding reconstruction method before inspecting 2022–2025 groundwater outcomes.
- [ ] Conduct held-out 2022–2025 validation.


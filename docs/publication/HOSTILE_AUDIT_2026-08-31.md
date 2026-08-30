# Hostile publication audit — 2026-08-31

## Current verdict

Promising observational paper; **not submission-ready**. Approximate overall publication potential today: **5.7/10**. Potential after mandatory statistical/provenance gates: **7.5–8/10** for a solid hydrology/agricultural-water journal. Causal evidence remains weak.

## Scorecard

| Domain | Score /10 | Main risk |
|---|---:|---|
| Scientific importance | 8.0 | None material |
| Narrow empirical novelty | 7.5 | Generic irrigation/groundwater claims are occupied |
| Open-data basis | 8.0 | Exact groundwater/station-master provenance still incomplete |
| Reproducibility today | 4.5 | Chat-era scripts/panels not yet one end-to-end pipeline |
| RiceFloodIT exposure | 5.5 | 1-km proxy, March–June aggregate, measurement error |
| Groundwater outcome | 5.5 | Sparse dates, heterogeneous well/screen depths |
| Weather controls | 7.0 | Spatial interpolation and evaporative demand sensitivity remain |
| Temporal identification | 5.0 | Spring baseline overlaps FF observation window |
| Spatial design/inference | 3.0 | Strongly overlapping 10-km exposures; cluster-by-well is insufficient |
| Statistical inference | 3.0 | Extensive exploratory specification search/multiplicity |
| Robustness/falsification | 7.0 | Several attractive hypotheses were correctly rejected |
| Confounding/identification | 4.0 | Canal delivery, pumping, drainage and allocation unobserved |
| Mechanistic evidence | 3.0 | Sign/timing reject simple recharge but do not identify mechanism |
| Generalizability | 5.5 | Specific managed alluvial rice landscape |
| Manuscript readiness | 3.5 | Do not draft final paper until gates pass |

## Two decisive blockers

### Spatial pseudo-replication

The 10-km FF exposure fields overlap strongly among nearby wells. Well-clustered SEs handle serial dependence within wells but not common exposure/aquifer shocks across wells. Spatial-HAC and geographic-block inference are mandatory.

### Multiplicity/post-selection

The surviving August/10-km model emerged after examination of multiple months, spatial supports, transformations, trends, leads/lags, regimes, event studies, nonlinear models and interpolation choices. Nominal p-values are discovery statistics, not confirmatory error-controlled inference.

## Data gaps that remain scientifically important

- actual canal delivery/diversion by local service area and year;
- groundwater abstraction/pumping volumes;
- field drainage and return flows;
- exact within-March–June timing of RiceFloodIT FF observations in the released aggregate;
- homogeneous well-construction information for all outcome stations;
- fully recorded source provenance for the recovered ARPA groundwater and weather station-master files.

None of these gaps may be silently replaced with assumed values or request-only information.

## Decision rule

Proceed because the open-data empirical signal is scientifically interesting. Do not submit or causalize it unless the spatial-inference, multiplicity, temporal-ordering and reproducibility gates pass.

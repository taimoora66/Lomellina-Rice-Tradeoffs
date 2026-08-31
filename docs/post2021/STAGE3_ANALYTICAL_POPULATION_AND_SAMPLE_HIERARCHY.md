# Stage 3 â€” Analytical Population and Sample Hierarchy

Status: PROPOSED FOR FREEZE
Date: 2026-08-31

## Purpose

This stage freezes the analytical population hierarchy for the 2022â€“2025
groundwater extension before any 2022â€“2025 floodingâ€“groundwater association
coefficient is fitted or inspected.

The choice is based only on already audited availability and panel structure.

No candidate sample may be promoted or demoted according to its later
coefficient, confidence interval, p-value, or apparent agreement with the
historical result.

---

## 1. Frozen eligibility definition

Primary station-year eligibility requires all of the following:

- gw_aug_nearest_aug23_m;
- gw_pre_last_janfeb_m;
- frozen f10_anomaly_2010_2021;
- positive 10-km flooding geometry.

Weather-robustness eligibility additionally requires:

- P_A8;
- T_A8.

The integrated eligibility audit was completed before any 2022-2025
association model was fitted.

Observed primary-eligible counts are:

- 2022: 17 wells;
- 2023: 13 wells;
- 2024: 15 wells;
- 2025: 17 wells.

Flooding exposure removed zero groundwater-complete station-years.

Weather availability removed zero primary-eligible station-years.

Therefore the realized station-year membership is identical for the
primary and weather-robustness analyses, even though weather is not part
of the primary eligibility definition.

The generalized eligibility pipeline exactly reproduced the 13 station IDs
used in the frozen 2022-2023 held-out confirmation.

---

## 2. Observed repeated-sample structure

Across 2022â€“2025:

- 12 wells are eligible in all four years;
- 14 wells are eligible in at least three years;
- 18 wells are eligible in at least two years;
- 19 of the 37 frozen ISS wells are eligible in none of the four years.

Eligibility patterns among repeated wells are:

- 12 wells: 2022, 2023, 2024, 2025;
- 2 wells: 2022, 2024, 2025;
- 1 well: 2022, 2023;
- 2 wells: 2022, 2025;
- 1 well: 2024, 2025.

No well is eligible in exactly one year.

These patterns were known before the 2022â€“2025 association coefficient was
fitted.

---

## 3. Candidate A â€” 12-well balanced four-year population

Definition:

The 12 wells eligible in every calendar year from 2022 through 2025.

Advantages:

- every included well contributes the same four years;
- year-to-year comparisons are not confounded by changing well composition;
- the panel is rectangular and transparent;
- the same units contribute to all common-year effects;
- missingness does not determine which wells contribute to a given included
  year once the sample is frozen;
- 12 of the original 13 held-out wells persist through all four years.

Disadvantages:

- only 12 groundwater wells contribute independent spatial units;
- valid information from six additional repeated wells is excluded;
- continuous four-year monitoring may define a selected subgroup of the
  historical ISS universe;
- statistical power and small-cluster inference remain limited.

Hostile interpretation:

A reviewer could argue that the balanced sample sacrifices external validity
and information for design simplicity.

Response:

That limitation is accepted explicitly. The balanced population is chosen for
the primary temporal comparison because constant well composition across all
four years minimizes ambiguity about whether a temporal change reflects the
hydrological relationship or changing membership.

---

## 4. Candidate B â€” 18-well repeated unbalanced population

Definition:

All wells eligible in at least two years during 2022â€“2025.

Advantages:

- retains all wells capable of contributing within-well temporal information;
- increases the number of spatial units from 12 to 18;
- better represents the monitored repeated-well universe;
- can improve precision when correctly estimated as an unbalanced panel.

Disadvantages:

- different wells contribute to different year contrasts;
- year composition changes across the panel;
- the 2023 sample is especially narrow;
- the estimand becomes an average within-well association over an unbalanced
  observation pattern;
- finite-sample inference remains difficult despite the larger well count.

Hostile interpretation:

A reviewer could argue that an apparent temporal effect partly reflects which
wells happen to be observed in each year.

Response:

This is why the unbalanced population is not the primary analysis. It is
retained as a prespecified robustness analysis to evaluate whether the balanced
result depends strongly on excluding otherwise usable repeated wells.

---

## 5. Candidate C â€” 14-well at-least-three-year population

Definition:

All wells eligible in at least three of the four years.

Advantages:

- only two additional wells are added beyond the balanced population;
- each included well contributes substantial temporal information;
- less composition variability than the 18-well population.

Disadvantages:

- it has no uniquely compelling scientific interpretation;
- it is neither fully balanced nor maximally inclusive;
- choosing it as primary could appear as an arbitrary compromise;
- it creates another degree of freedom without solving the core trade-off.

Hostile interpretation:

A reviewer could reasonably ask why three years, rather than two or four, was
chosen.

Response:

There is no sufficiently strong reason to make this the primary population.
It is retained only as a sample-stability diagnostic.

---

## 6. Primary population decision

PRIMARY ANALYTICAL POPULATION:

The 12 wells eligible in all four years 2022â€“2025.

Rationale:

The primary purpose of the extension is to evaluate temporal consistency over
four subsequent years using a constant set of monitored groundwater wells.

The balanced sample ensures that all included wells contribute to every year
and that calendar-year contrasts are not accompanied by changes in analytical
well membership.

This decision is made with eligibility structure known but before inspection
of any 2022â€“2025 association coefficient.

It is therefore a pre-analysis sample decision, not a pristine preregistration
made before data availability was known.

---

## 7. Frozen primary well identities

The primary 12-well balanced population is:

- PO018043NUP001
- PO018047NR0001
- PO0180480U0004
- PO018048NRP001
- PO018072NUP001
- PO0180810U0111
- PO0181100U0111
- PO0181140U0002
- PO018162NUP001
- PO018173NUP001
- PO018176NUP001
- PO018180NUP001

No well may be added to or removed from this primary population because of
its later coefficient contribution, leverage, Cook's distance, residual,
groundwater value, or flooding value unless an independently documented data
error is discovered.

Any such data-error exclusion must be recorded separately and cannot be used
silently.

---

## 8. Secondary repeated-population robustness

SECONDARY ROBUSTNESS POPULATION:

All 18 wells eligible in at least two of the four years.

Purpose:

Evaluate whether the substantive conclusion from the balanced primary
population is highly dependent on restricting the analysis to wells observed
in all four years.

This analysis must use the same outcome, exposure, antecedent construct, and
predefined model architecture appropriate for the unbalanced panel.

It cannot replace the primary balanced result according to:

- coefficient magnitude;
- sign;
- standard error;
- confidence interval;
- p-value;
- agreement with the historical coefficient.

---

## 9. Three-year sample-stability diagnostic

DIAGNOSTIC POPULATION:

The 14 wells eligible in at least three years.

Purpose:

Provide an intermediate sample-stability check between the balanced primary
population and the maximally repeated unbalanced robustness population.

This population is not a candidate primary analysis.

Its result is diagnostic only and cannot be elevated because it appears more
stable, precise, or statistically significant.

---

## 10. Relationship to the original 2022â€“2023 held-out sample

The original frozen held-out sample contains 13 wells.

Twelve of those 13 wells belong to the balanced 2022â€“2025 primary population.

The remaining original held-out well, `PO018003NR0009`, is eligible only in
2022 and 2023.

The original 13-well held-out result remains unchanged.

The 12-well four-year analysis does not retrospectively redefine the original
held-out sample.

---

## 11. Missingness interpretation

The primary balanced population is not a random sample of Lomellina wells.

Eligibility depends primarily on groundwater monitoring completeness.

Within the frozen 37-well ISS universe:

- FF10 availability does not remove groundwater-complete observations;
- weather availability does not remove groundwater-plus-FF10-complete
  observations;
- groundwater monitoring availability is therefore the operative source of
  post-2021 sample restriction.

This does not imply groundwater missingness is random.

Representativeness of the balanced population relative to the 37-well universe
must be audited later using geography and pre-existing well metadata.

---

## 12. Reporting rule

The manuscript must report the sample hierarchy transparently:

Primary:
- 12 wells complete in all four years; 48 station-year observations.

Secondary robustness:
- 18 wells complete in at least two years; 62 station-year observations.

Sample-stability diagnostic:
- 14 wells complete in at least three years; 54 station-year observations.

The number of station-year observations must be reported together with the
number of distinct wells.

No analysis may describe station-year rows as independent groundwater units.

---

## 13. Symmetric decision rule

The population hierarchy will remain unchanged if the primary result is:

- positive;
- negative;
- near zero;
- statistically significant;
- statistically non-significant;
- imprecise;
- inconsistent with historical estimates;
- sensitive to one well or year.

A weak primary result cannot be replaced by a stronger secondary-sample
result.

A strong primary result cannot be insulated from a conflicting secondary
result by omitting that robustness analysis.

---

## Stage-3 conclusion

The 12-well balanced 2022â€“2025 population is the primary analytical
population because it provides constant well composition over all four years.

The 18-well repeated unbalanced population is a prespecified robustness
population.

The 14-well at-least-three-year population is a sample-stability diagnostic.

This hierarchy is frozen before inspection of any 2022â€“2025
floodingâ€“groundwater association coefficient.

Status: STAGE 3 FROZEN



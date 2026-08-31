# Stage 2 â€” Scientific Question and Estimand

Status: PROPOSED FOR FREEZE
Date: 2026-08-31

## Purpose

This stage defines the scientific question and the estimand for the forthcoming
2022â€“2025 groundwater extension before any 2022â€“2025 floodingâ€“groundwater
association coefficient is fitted or inspected.

This stage does not define a causal effect.

It defines the observational quantity that the primary analysis will attempt
to estimate and the interpretation boundaries that will apply regardless of
the numerical result.

---

## 1. Scientific question

Primary question:

> Among the groundwater wells retained in the prespecified post-2021 analysis,
> is within-well interannual variation in the frozen 10-km
> RiceFloodIT-compatible flooding anomaly associated with late-season
> groundwater depth during 2022â€“2025 after accounting for antecedent
> groundwater state and shocks common to all wells in a calendar year?

This is a subsequent observational extension informed by the prior research
history documented in `EVIDENCE_CHRONOLOGY.md`.

It is not described as:

- a causal treatment-effect question;
- an untouched independent replication;
- a preregistered question formulated before the 2022â€“2023 result;
- a test of irrigation volume;
- a test of the exact undocumented RiceFloodIT algorithm.

---

## 2. Population and observation unit

Scientific population:

The monitored historical ISS groundwater-well universe used in the publication
groundwater pipeline.

Primary analytical population will be frozen separately in the sample-design
stage before model fitting.

Observation unit:

A groundwater-well Ã— calendar-year record.

The number of station-year rows must not be interpreted as the number of
independent hydrological systems. Repeated observations are nested within
groundwater wells.

---

## 3. Outcome construct

Primary outcome construct:

Late-season groundwater depth near 23 August.

Operational variable:

`gw_aug_nearest_aug23_m`

Interpretation:

Larger values indicate greater groundwater depth below the measuring reference,
that is, deeper groundwater.

The outcome definition is inherited unchanged from the frozen 2022â€“2023
held-out analysis.

No alternate August summary, groundwater month, date window, or transformation
will replace this outcome according to the 2022â€“2025 result.

---

## 4. Exposure construct

Primary exposure construct:

The 10-km unweighted well-buffer mean of the frozen cell-level reconstructed
flooding anomaly.

Operational variable:

`ff10_anomaly_2010_2021`

Cell-level anomaly definition:

`reconstructed annual FF - cell-specific mean reconstructed FF over 2010â€“2021`

The reconstruction is a RiceFloodIT-compatible MODIS-derived flooding signal.

It is not interpreted as:

- direct irrigation volume;
- exact RiceFloodIT output;
- a randomized management treatment.

The 10-km radius is retained because it was frozen for the post-2021 analysis
before the original held-out groundwater result was inspected.

Its exploratory historical origin remains part of the evidence chronology.

---

## 5. Antecedent state construct

Primary antecedent-groundwater control:

`gw_pre_last_janfeb_m`

This is the last valid Januaryâ€“February groundwater observation in the same
calendar year.

Scientific role:

It conditions the association on the measured groundwater state preceding the
Marchâ€“June flooding period.

It is not interpreted as eliminating all hydrological confounding.

It may itself reflect prior recharge, extraction, climatic conditions, aquifer
persistence, and other antecedent processes.

---

## 6. Common annual shocks

The primary multi-year analysis will account for calendar-year effects.

Scientific role:

Year effects absorb conditions common to all included wells in a given year,
including broad regional temporal shifts that are not uniquely attributable to
the local FF10 exposure.

Consequently, the primary estimand is not the association between a
Lomellina-wide increase in flooding and a Lomellina-wide groundwater shift.

Instead, identification comes from FF10 differences that remain after
accounting for:

- persistent well-specific differences; and
- calendar-year conditions common to all included wells.

This distinction must remain explicit in the manuscript.

---

## 7. Primary estimand

Conceptual estimand:

The adjusted within-well association between the frozen FF10 anomaly and
late-season groundwater depth during 2022â€“2025, conditional on antecedent
groundwater depth and common annual shocks.

Let:

- `Y_it` = late-season groundwater depth for well `i` in year `t`;
- `F_it` = frozen 10-km flooding anomaly;
- `A_it` = antecedent Januaryâ€“February groundwater depth;
- `alpha_i` = well-specific time-invariant component;
- `lambda_t` = common calendar-year component.

The target association parameter is `beta` in:

`Y_it = beta F_it + gamma A_it + alpha_i + lambda_t + error_it`

The parameter `beta` is the primary estimand.

---

## 8. Interpretation of beta

A positive `beta` means:

Within the analyzed wells and years, larger FF10 anomalies after accounting
for persistent well-specific differences and common calendar-year conditions
are associated with larger late-season groundwater-depth values after
conditioning on antecedent groundwater depth.

Because larger groundwater-depth values indicate deeper groundwater, a positive
coefficient corresponds to an association with deeper late-season groundwater.

A negative `beta` corresponds to an association with shallower late-season
groundwater.

Neither sign is interpreted causally.

---

## 9. What beta does not identify

The primary coefficient does not identify:

- the causal effect of rice flooding on groundwater;
- groundwater recharge caused by irrigation;
- groundwater depletion caused by rice management;
- the response to a region-wide flooding shock that is absorbed by year effects;
- the effect of canal operations;
- the effect of pumping or groundwater abstraction;
- the effect of direct irrigation volume;
- a biological or ecosystem-service effect.

Potential omitted and simultaneous drivers remain, including:

- surface-water availability;
- groundwater abstraction;
- irrigation-delivery conditions;
- management adaptation;
- soil and aquifer heterogeneity;
- unmeasured hydrological conditions.

---

## 10. Weather controls

`P_A8` and `T_A8` remain prespecified robustness controls inherited from the
original held-out protocol.

They are not part of the definition of the primary estimand.

Their role is to examine whether the estimated flooding association is
materially altered after additional adjustment for measured Aprilâ€“August
precipitation and temperature.

Weather-adjusted models cannot replace the primary specification according to
coefficient sign, magnitude, confidence interval, or p-value.

---

## 11. Relationship to the historical analysis

The historical clean model and the 2022â€“2025 extension do not estimate
perfectly identical empirical quantities.

Historical work used a different late-season groundwater summary and arose
from a historically exploratory research program.

The post-2021 extension retains the outcome definition frozen for the genuine
2022â€“2023 held-out test.

Therefore comparisons across historical and post-2021 periods concern
direction, magnitude, uncertainty, and temporal consistency of related
observational groundwaterâ€“flooding associations.

They are not presented as exact replication of one invariant structural
parameter.

---

## 12. Relationship to the 2022â€“2023 held-out test

The 2022â€“2023 first-difference analysis remains the genuine held-out
confirmation/falsification exercise.

Its result is not replaced by the 2022â€“2025 extension.

The 2022â€“2025 analysis asks whether the same frozen post-2021 constructs show a
stable or unstable observational relationship when two later years are added.

Because the motivation for the longer extension arose after the 2022â€“2023
result was known, the extension is described as a subsequent prespecified
analysis, not as a second untouched confirmation.

---

## 13. Symmetric interpretation rule

The primary estimand and scientific question do not change according to the
observed coefficient.

Before model fitting, the following interpretations are all considered
reportable:

- positive association;
- negative association;
- near-zero association;
- high statistical uncertainty;
- temporal instability;
- dependence on individual wells or years.

No result category will trigger a redefinition of the estimand.

---

## Stage-2 conclusion

The forthcoming 2022â€“2025 analysis targets a non-causal, adjusted within-well
association between the frozen 10-km RiceFloodIT-compatible flooding anomaly
and late-season groundwater depth, conditional on antecedent groundwater state
and common calendar-year conditions.

The estimand is defined before inspection of any 2022â€“2025 association
coefficient.

Status: STAGE 2 FROZEN


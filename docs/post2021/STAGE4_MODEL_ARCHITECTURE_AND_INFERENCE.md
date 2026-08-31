# Stage 4 â€” Model Architecture and Inference

Status: STAGE 4 FROZEN
Date: 2026-08-31

## Purpose

This stage freezes the model architecture, inferential hierarchy, diagnostic
procedures, and reporting rules for the 2022â€“2025 groundwater extension before
any 2022â€“2025 floodingâ€“groundwater association coefficient is fitted or
inspected.

No model may be added, removed, promoted, or demoted after seeing the primary
coefficient except to correct a documented implementation or data error.

This stage does not create a causal estimand.

---

## 1. Primary analytical population

The primary analysis uses the Stage-3 balanced population:

- 12 groundwater wells;
- four years: 2022, 2023, 2024, 2025;
- 48 station-year observations before any unexpected implementation loss.

Every primary well must contribute exactly four eligible station-year records.

If the implemented primary design does not contain exactly 12 wells and
48 rows, execution must stop before fitting the association model.

---

## 2. Primary variables

Outcome:

`gw_aug_nearest_aug23_m`

Exposure:

`ff10_anomaly_2010_2021`

Antecedent groundwater control:

`gw_pre_last_janfeb_m`

Panel identifiers:

- `station`;
- `year`.

No transformation, alternate August outcome, alternate flooding radius,
alternate anomaly baseline, or alternate antecedent groundwater definition may
replace these variables according to the observed result.

---

## 3. Primary model

The primary model is ordinary least squares with groundwater-well and
calendar-year fixed effects:

`gw_aug_nearest_aug23_m ~ ff10_anomaly_2010_2021 + gw_pre_last_janfeb_m + C(station) + C(year)`

Conceptually:

`Y_it = beta F_it + gamma A_it + alpha_i + lambda_t + error_it`

where:

- `Y_it` is late-season groundwater depth;
- `F_it` is the frozen 10-km flooding anomaly;
- `A_it` is antecedent Januaryâ€“February groundwater depth;
- `alpha_i` is the well fixed effect;
- `lambda_t` is the calendar-year fixed effect;
- `beta` is the Stage-2 primary estimand.

The coefficient of interest is exactly the coefficient on:

`ff10_anomaly_2010_2021`

---

## 4. Identification represented by the model

The fixed-effects model does not use persistent cross-sectional differences
between wells to identify `beta`.

It also does not use variation that is perfectly common to all included wells
within a calendar year.

The coefficient is identified by residual within-well, across-year FF10
variation after adjustment for:

- persistent well differences;
- common calendar-year conditions;
- antecedent groundwater depth.

A strong region-wide annual shift in reconstructed flooding may therefore
contribute little to the primary coefficient after year effects are included.

That feature is part of the estimand and cannot be removed after inspecting the
result.

---

## 5. Point estimate

The primary point estimate is the OLS coefficient `beta_hat` on
`ff10_anomaly_2010_2021` from the exact primary model.

It must be reported in:

- metres of groundwater-depth difference per 1.0 FF10-anomaly unit; and
- metres per 0.01 FF10-anomaly unit.

The per-0.01 quantity is:

`0.01 * beta_hat`

Both scales are descriptive association scales, not causal-effect scales.

---

## 6. Why ordinary HC standard errors are insufficient as primary inference

The 48 primary station-year observations arise from only 12 repeated
groundwater wells.

Errors may be correlated within a well across years.

Therefore station-year rows cannot be treated as independent observations.

HC0, HC1, HC2, or HC3 standard errors that ignore the repeated-well cluster
structure are not the primary inferential procedure.

HC3 is retained only as a continuity diagnostic relative to the original
two-year held-out workflow.

---

## 7. Primary cluster-aware uncertainty estimate

The primary standard-error and confidence-interval calculation is the
leave-one-well-out CV3J cluster-jackknife variance estimator for the
coefficient of interest.

Let `G` be the number of included groundwater wells.

For the primary model:

`G = 12`

Fit the same model `G` times, each time removing exactly one groundwater well.

Let the resulting flooding coefficients be:

`beta_hat_minus_g`

and let:

`beta_bar_jack = mean(beta_hat_minus_g)`

The frozen CV3J variance is:

`V_J = ((G - 1) / G) * sum((beta_hat_minus_g - beta_bar_jack)^2)`

The frozen CV3J standard error is:

`SE_J = sqrt(V_J)`

The primary CV3J 95% confidence interval is:

`beta_hat +/- t_(0.975, G - 1) * SE_J`

For the primary balanced analysis the reference degrees of freedom are:

`G - 1 = 11`

The central OLS point estimate remains `beta_hat`; the jackknife estimates are
used for uncertainty and influence assessment, not to replace the point
estimate.

---

## 8. Primary small-cluster bootstrap test

Because the number of clusters is small, the analysis will also report a
two-sided wild cluster bootstrap p-value for the null:

`H0: beta = 0`

The bootstrap is clustered by groundwater well.

Frozen bootstrap design:

- restricted wild cluster bootstrap;
- null imposed;
- bootstrap type: WCR31;
- bootstrap weights: Webb six-point weights;
- bootstrap replications: 9,999;
- random seed: 20260831;
- two-sided test;
- clustering variable: `station`;
- tested parameter: `ff10_anomaly_2010_2021`.

Implementation target:

Python package `wildboottest`, publicly available from PyPI and GitHub.

The implementation must record the exact installed package version before the
coefficient is revealed.

If the frozen package/API cannot execute the prespecified test, execution must
stop. A different bootstrap algorithm may not be silently substituted.

The wild-bootstrap p-value supplements rather than replaces the jackknife
confidence interval because the current Python implementation does not provide
confidence intervals by test inversion.

---

## 9. Inferential reporting hierarchy

PRIMARY numerical reporting:

1. OLS `beta_hat`;
2. leave-one-well-out jackknife `SE_J`;
3. 95% jackknife/t confidence interval using 11 reference degrees of freedom;
4. two-sided WCR31 Webb wild-cluster-bootstrap p-value.

BENCHMARK reporting:

- conventional CRV1 standard error clustered by `station`;
- CRV1 t-based p-value using `G - 1` reference degrees of freedom.

CONTINUITY diagnostic:

- HC3 standard error and confidence interval.

No method may be selected as the headline procedure because it gives a more
favorable p-value.

Disagreement among inferential methods must be reported as evidence of
finite-sample fragility.

---

## 10. Weather robustness models

Weather controls remain prespecified robustness analyses and do not replace the
primary model.

W1:

`Y ~ F + A + P_A8 + C(station) + C(year)`

W2:

`Y ~ F + A + T_A8 + C(station) + C(year)`

W3:

`Y ~ F + A + P_A8 + T_A8 + C(station) + C(year)`

where `Y`, `F`, and `A` retain the exact primary definitions.

For every weather model, report the flooding coefficient and the same
cluster-aware inferential hierarchy where estimable.

No weather model can become primary according to its result.

---

## 11. Secondary 18-well unbalanced robustness population

The Stage-3 secondary population contains all wells eligible in at least two
years.

The same substantive model is fitted:

`Y_it = beta F_it + gamma A_it + alpha_i + lambda_t + error_it`

using all eligible station-years for those 18 wells.

The model remains a well- and year-fixed-effects regression.

Inference remains clustered by groundwater well.

The same jackknife, WCR31 Webb bootstrap, CRV1 benchmark, and HC3 diagnostic
hierarchy is used, with degrees of freedom determined by the actual number of
included wells.

The unbalanced result cannot replace the balanced primary result.

---

## 12. Fourteen-well sample-stability diagnostic

The Stage-3 at-least-three-year population is fitted only as a
sample-stability diagnostic.

It uses the same outcome, exposure, antecedent variable, fixed effects, and
cluster unit.

Its purpose is to reveal whether the estimated association changes materially
under the intermediate sample definition.

It cannot be promoted to primary or secondary status because of its numerical
result.

---

## 13. Leave-one-well-out influence diagnostic

The 12 primary leave-one-well-out fits already required for the jackknife are
also an influence diagnostic.

For each omitted well, record:

- omitted station ID;
- remaining number of wells;
- remaining station-year count;
- flooding coefficient;
- change from the full-primary coefficient;
- coefficient sign.

Summarize:

- minimum leave-one-well-out coefficient;
- maximum leave-one-well-out coefficient;
- whether the sign changes;
- maximum absolute change from the full estimate.

No well is removed from the primary result because it is influential.

A well may be excluded only for a separately documented data-integrity error.

---

## 14. Leave-one-year-out temporal diagnostic

Fit the primary model four additional times, omitting one calendar year at a
time:

- omit 2022;
- omit 2023;
- omit 2024;
- omit 2025.

Each fit must retain well fixed effects and the remaining year fixed effects.

Record:

- omitted year;
- flooding coefficient;
- number of wells;
- station-year count;
- coefficient sign;
- change from the full-primary coefficient.

This is a temporal-stability diagnostic, not an alternate primary model.

A year may not be removed from the primary result because its omission produces
a more favorable estimate.

---

## 15. Classical leverage and Cook's-distance diagnostics

For the full primary OLS design, record standard observation-level:

- leverage;
- internally available OLS residual diagnostics;
- Cook's distance.

These diagnostics describe numerical influence at the station-year level.

They do not define independent inferential units and do not justify automatic
row deletion.

Because clustering is by well, the leave-one-well-out diagnostic has greater
scientific priority than observation-level Cook's-distance deletion rules.

No fixed Cook's-distance cutoff is used to remove observations.

---

## 16. Exposure information-content diagnostic before interpretation

After the model architecture is frozen but independently of the groundwater
coefficient interpretation, quantify how much FF10 variation survives the
fixed-effects structure.

At minimum report:

- raw FF10 variance in the primary sample;
- FF10 variance after removing well fixed effects;
- FF10 variance after removing year fixed effects;
- FF10 variance after removing both well and year fixed effects;
- ratio of two-way-residualized variance to raw variance;
- minimum, maximum, and standard deviation of the two-way-residualized FF10
  exposure.

This diagnostic does not alter the model.

Its purpose is to establish how much exposure information actually identifies
`beta`, especially when a calendar year contains a strong common regional
shift.

---

## 17. Rank and estimability gates

Before reporting any coefficient, the implementation must verify:

- exactly 12 primary wells;
- exactly 48 primary station-year rows;
- every primary well has exactly four years;
- years are exactly 2022, 2023, 2024, 2025;
- no missing primary outcome;
- no missing primary exposure;
- no missing antecedent groundwater value;
- no duplicate station-year rows;
- design matrix has full estimable rank after the standard dummy-variable
  reference-category parameterization;
- `ff10_anomaly_2010_2021` has non-zero residual variation after projecting out
  well effects, year effects, and the antecedent covariate.

If any gate fails, stop before association-result reporting.

---

## 18. No model-selection search

The following are prohibited before the primary result is permanently recorded:

- trying alternate flooding radii;
- changing the 2010â€“2021 anomaly baseline;
- switching between August groundwater outcomes;
- removing year fixed effects because they reduce apparent signal;
- removing well fixed effects because they reduce apparent signal;
- adding polynomial flooding terms;
- adding flooding-by-year interactions as a rescue specification;
- selecting covariates by p-value;
- deleting influential wells or years based on regression diagnostics;
- choosing among inference methods according to significance.

Any later exploratory model must be explicitly labeled post-result exploratory
and cannot alter the frozen primary evidence.

---

## 19. Multiple-result interpretation

The analysis will generate several prespecified numerical summaries.

The scientific conclusion must give priority to:

1. primary balanced-sample point estimate and uncertainty;
2. finite-cluster inferential fragility or stability;
3. leave-one-well and leave-one-year stability;
4. secondary unbalanced-sample robustness;
5. weather robustness;
6. intermediate 14-well sample diagnostic.

No single nominal p-value determines the substantive conclusion.

The result will be described using effect magnitude, direction, uncertainty,
and stability.

---

## 20. Symmetric reporting commitment

The complete primary result will be permanently reported if it is:

- positive;
- negative;
- near zero;
- statistically significant;
- statistically non-significant;
- extremely imprecise;
- opposite to the historical association;
- similar to the historical association;
- sensitive to one well;
- sensitive to one year.

No result category permits redefining the model, estimand, sample, or primary
inference method.

---

## 21. Pre-reveal implementation smoke test

Before any real 2022-2025 groundwater outcome is supplied to the association
model, the inference implementation must pass a synthetic-data smoke test.

The smoke test must verify:

- the installed wildboottest version is recorded;
- the documented statsmodels interface executes successfully;
- clustering is accepted at the synthetic well level;
- ootstrap_type='31' executes successfully;
- impose_null=True executes successfully;
- weights_type='webb' executes successfully;
- the fixed random seed produces reproducible output;
- a two-sided bootstrap p-value is returned;
- the independently coded CV3J calculation returns a finite standard error;
- leave-one-cluster-out model fits preserve the coefficient of interest.

Synthetic smoke-test results have no scientific interpretation.

If this gate fails, the real association model must not be run.

Any necessary implementation change must be documented and Stage 4 amended
before the 2022-2025 coefficient is revealed.

---

## 22. Software and reproducibility gate

The implementation must use openly accessible software.

Core regression and data processing may use public Python packages already
used in the repository.

Wild-cluster-bootstrap inference will use the public `wildboottest` package.

Before the reveal script is run, record:

- Python version;
- NumPy version;
- pandas version;
- SciPy version;
- statsmodels version;
- wildboottest version;
- bootstrap seed;
- bootstrap replications;
- bootstrap type;
- bootstrap weight distribution.

The analysis script and terminal QA output must be committed before scientific
interpretation is written.

---

## 23. Methodological rationale

There are only 12 independent groundwater-well clusters in the primary
analysis.

Conventional cluster-robust inference can perform poorly with few clusters.

The cluster jackknife/CRV3 family and modern wild-cluster-bootstrap procedures
are therefore used to make finite-cluster uncertainty visible rather than to
maximize statistical significance.

Webb six-point weights are prespecified because few clusters produce a limited
number of distinct two-point bootstrap weight combinations.

WCR31 is prespecified as the restricted small-cluster bootstrap variant.

The procedure remains an observational inference framework and does not repair
unmeasured confounding, simultaneity, exposure measurement error, or
non-random groundwater monitoring.

---

## Stage-4 conclusion

The primary 2022â€“2025 model is a 12-well, 48-observation well- and year-fixed
effects OLS regression of late-season groundwater depth on the frozen 10-km
flooding anomaly and antecedent groundwater depth.

The central uncertainty estimate is the leave-one-well-out CV3J cluster jackknife,
with a 95% t interval using 11 reference degrees of freedom.

A two-sided restricted WCR31 wild cluster bootstrap test using Webb weights,
9,999 replications, seed 20260831, and clustering by groundwater well is
prespecified as the small-cluster bootstrap test.

CRV1, HC3, weather models, the 18-well unbalanced population, the 14-well
intermediate population, leave-one-well-out fits, leave-one-year-out fits, and
exposure-information diagnostics are prespecified supporting analyses.

No 2022â€“2025 floodingâ€“groundwater association coefficient may be inspected
until this stage is frozen and committed.

Status: STAGE 4 FROZEN




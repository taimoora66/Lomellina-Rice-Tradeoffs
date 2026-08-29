# LOMELLINA RICE–WATER TRADE-OFFS

## Master Project Record and Research Handoff

**Repository:** `taimoora66/Lomellina-Rice-Tradeoffs`
**Project status:** Active
**Protocol freeze:** 29 August 2026
**Current stage:** Phase 1B — Research and reproducibility foundation
**Next stage:** Phase 2 — Literature verification and data acquisition

---

# 1. PURPOSE OF THIS DOCUMENT

This document is the authoritative continuity record for the entire project.

It exists so that the project can be reconstructed quickly if:

* a ChatGPT conversation reaches its limit;
* work is resumed after several weeks or months;
* a different researcher or AI assistant continues the project;
* files become separated from previous discussions;
* methodological decisions need to be audited;
* the publication strategy changes;
* a reviewer asks how a particular decision was made.

Before proposing new analyses or changing the research direction, this document should be read first together with:

1. `docs/protocol/`
2. `docs/decisions/decision_log.md`
3. `PROJECT_STATUS.md`
4. `docs/data/data_access_register.csv`
5. `docs/claims/claim_register.csv`

This project must be treated as a continuation of an audited research programme, not restarted from scratch.

---

# 2. RESEARCH CONTEXT

This work originates from a University of Milan Ecosystem Functioning and Services course report.

The broad subject is water management in rice agroecosystems of Lombardy, with particular attention to Lomellina.

The original project attempted to integrate:

* remote sensing;
* irrigation management;
* groundwater;
* canal networks;
* methane;
* nitrous oxide;
* rice yield;
* biodiversity;
* ecosystem services;
* spatial optimization.

An independent hostile audit determined that this design was too broad and scientifically vulnerable.

The major problems were:

* excessive scope;
* unproven novelty;
* reliance on weak parcel-level proxies;
* risk of pseudoreplication;
* inadequate distinction between field water savings and district/basin water savings;
* biodiversity claims without biological observations;
* potential duplication of existing Northern Italian hydrological work;
* optimization before establishing that spatial configuration actually matters.

The project was therefore redesigned.

The current project deliberately separates:

1. a rigorous EFS course report; and
2. a narrower conditional publication-track study.

The publication extension is not assumed to succeed.

Failure of the publication hypothesis is an acceptable scientific outcome.

---

# 3. TWO DISTINCT RESEARCH PRODUCTS

## Product A — EFS Course Report

### Working title

**Hydroperiod Change and Ecosystem-Service Trade-offs in Lomellina Rice Agroecosystems**

### Purpose

Produce a rigorous quantitative EFS report examining how changing rice-field hydroperiod relates to:

* water regulation;
* groundwater recharge and hydrological functioning;
* greenhouse-gas regulation/disservice;
* rice production;
* temporary aquatic/wetland-habitat availability.

This report must remain feasible using primarily open and already available evidence.

It must not depend on successful access to restricted publication-level hydrological datasets.

---

## Product B — Conditional Publication-Track Study

### Working title

**Does Management Placement Matter? Fixed-Composition Rice-Irrigation Mosaics and Peak Water Demand in a Shallow-Groundwater Canal Network in Lomellina**

### Purpose

Test a much narrower hypothesis:

whether the spatial placement and temporal synchronization of irrigation regimes has an independent hydrological effect after the proportion of those regimes is held constant.

This publication study proceeds only if the required novelty, data access, validation and uncertainty requirements are satisfied.

---

# 4. FINAL EFS RESEARCH QUESTION

**How have rice-field flooding patterns changed across Lomellina, and what do spatial observations and local and European experimental evidence indicate about resulting trade-offs among water regulation, greenhouse-gas regulation/disservice, rice production and wetland-habitat availability?**

The wording is intentionally non-causal.

The project must distinguish between:

* observation;
* statistical association;
* literature-supported mechanisms;
* model-estimated effects;
* counterfactual scenarios;
* causal inference.

---

# 5. EFS SUBQUESTIONS

## RQ1 — Ecosystem functioning

How do hydroperiod, soil conditions, shallow groundwater, irrigation infrastructure and farm management interact to regulate:

* soil redox conditions;
* methanogenesis;
* nitrification and denitrification;
* infiltration and percolation;
* groundwater recharge;
* plant production;
* temporary aquatic habitat?

## RQ2 — Historical change

How has remotely observable rice-field flooding changed spatially and temporally during 2000–2021?

## RQ3 — Water regulation

Why can reductions in field-level irrigation input differ from changes in:

* district diversion;
* groundwater recharge;
* return flows;
* peak irrigation demand?

## RQ4 — Climate and production

What does experimental evidence show regarding WFL, DFL and safe-AWD effects on:

* methane;
* nitrous oxide;
* irrigation requirement;
* yield?

## RQ5 — Habitat

How could changes in the timing, duration and spatial continuity of surface-water availability alter temporary wetland-habitat availability?

Direct biodiversity effects are outside the supported inference unless biological observations are later obtained.

---

# 6. FINAL PUBLICATION RESEARCH QUESTION

**Holding the proportion of operationally feasible rice-water regimes constant, does their spatial placement and temporal synchronization within a connected canal–groundwater system materially change peak irrigation diversion and groundwater-recharge/return-flow dynamics beyond observational and model uncertainty?**

This is the principal publication hypothesis.

The project is not attempting to prove that AWD is universally better.

It is not attempting to build a generic multi-objective sustainability optimization model.

It is testing whether **configuration itself matters after composition is controlled**.

---

# 7. PUBLICATION HYPOTHESES

## H1 — Configuration effect

At equal management composition, different spatial and temporal configurations may generate different peak irrigation demand.

## H2 — Timing versus seasonal-total effect

Configuration is expected to affect peak and temporal water demand more strongly than total seasonal diversion.

## H3 — Network mechanism

Any configuration effect should be explicable through mechanisms such as:

* irrigation-network hierarchy;
* turnout grouping;
* groundwater conditions;
* soils;
* drainage;
* return-flow pathways;
* temporal synchronization.

Pure geometric adjacency is not considered sufficient explanation.

## H4 — Robustness

A configuration effect is scientifically meaningful only if it exceeds combined:

* measurement uncertainty;
* parameter uncertainty;
* model uncertainty;
* relevant structural uncertainty.

## Null hypothesis

After composition, weather and hydrological conditions are controlled:

**spatial configuration has no practically meaningful independent effect.**

A robust null result is scientifically acceptable.

---

# 8. CONFIGURATION VERSUS COMPOSITION

This distinction is central to the publication study.

Example management composition:

* 30% WFL;
* 40% DFL;
* 30% safe AWD.

For a configuration experiment:

the percentages must remain unchanged.

Only:

* location;
* network position;
* grouping;
* synchronization

may change.

Therefore:

**Composition = fixed**

**Configuration = variable**

If management percentages change between scenarios, the resulting effect cannot be attributed exclusively to spatial configuration.

---

# 9. SPATIAL HIERARCHY

## Level 1 — Lombardy

Used for:

* regional background;
* policy context;
* rice-production importance;
* climate/agriculture context.

It is not the primary modelling domain.

## Level 2 — Lomellina / Province of Pavia rice landscape

Primary EFS analytical landscape.

Used for:

* hydroperiod change;
* rice distribution;
* irrigation-network context;
* permanent wetlands;
* ecological-network context;
* spatial ecosystem-service interpretation.

## Level 3 — Operational irrigation district

Likely candidate:

**San Giorgio di Lomellina**

or another district if superior operational and validation data become available.

This level is reserved primarily for the publication-track hydrological experiment.

---

# 10. TEMPORAL SCOPE

## Historical EFS hydroperiod

**2000–2021**

Reason:

this period is directly supported by the existing RiceFloodIT historical evidence base.

Do not automatically describe 2022–2025 as remotely observed hydroperiod years.

## Agricultural/contextual information

May extend to 2025 or later where official datasets support it.

## Sentinel-1 pilot

Begin with:

**2019 and 2020**

because these years overlap useful local MEDWATERICE experimental work.

Do not initially process the full 2015–2025 Sentinel period.

## Publication hydrology

Use only years for which suitable:

* inputs;
* operational records;
* calibration data;
* validation data

exist.

---

# 11. CURRENT NOVELTY POSITION

The original broad novelty claim has been rejected.

The following are not considered sufficient novelty:

* studying Lombardy;
* studying Lomellina;
* integrating several ecosystem services;
* applying Sentinel-1 to rice flooding;
* modelling WFL/DFL/AWD;
* modelling groundwater recharge;
* spatial irrigation optimization by itself;
* combining water, yield, GHG and biodiversity;
* generating a Pareto frontier.

Existing work already covers substantial portions of these topics.

Particularly important novelty threats include:

* Northern Italian rice-groundwater studies;
* MEDWATERICE;
* QGIS-SWAP-Paddy;
* current QGIS-SWAP-Paddy/MODFLOW development;
* historical Italian rice flooding remote sensing;
* Sentinel-1 rice inundation mapping;
* ecological connectivity analyses in Northern Italian rice landscapes;
* global and regional spatial irrigation-allocation studies.

The provisional surviving contribution is:

**a controlled test of whether spatial placement and temporal synchronization independently alter practical hydrological outcomes after irrigation-regime composition is held fixed in a shallow-groundwater, collectively managed canal system.**

This contribution remains provisional until the literature/competitor search in Phase 2 is completed.

---

# 12. CORE DATA STRATEGY

## Open/high-priority datasets

### RiceFloodIT

Purpose:

* historical rice flooding analysis;
* 2000–2021 hydroperiod context;
* reproduction of published trends before extension.

### MEDWATERICE

Purpose:

* local experimental evidence;
* irrigation management;
* water balance;
* groundwater;
* crop development;
* yield;
* management definitions.

MEDWATERICE data should be inspected directly rather than replaced by generic literature multipliers.

### DUSAF

Purpose:

* land use;
* rice landscape context;
* spatial overlays.

### Regional irrigation network / RIRU

Purpose:

* canal-network geometry;
* irrigation landscape structure.

It must not automatically be interpreted as an operational hydraulic network.

### ARPA Lombardia

Potential uses:

* meteorology;
* precipitation;
* temperature;
* groundwater/piezometric information.

### Ecological/protected-area datasets

Potential uses:

* Natura 2000;
* regional ecological network;
* permanent/semi-natural wetlands;
* proximity/connectivity context.

---

# 13. PUBLICATION-CRITICAL DATA

Publication Path P1 may require access to:

* Est Sesia irrigation operations;
* district diversion records;
* canal hierarchy;
* turnout information;
* capacities;
* irrigation schedules/rotations;
* drainage;
* return flows;
* local groundwater observations;
* QGIS-SWAP-Paddy inputs/model access;
* relevant MODFLOW implementation;
* SmartWT observations;
* detailed local soil information.

If these data cannot adequately constrain the hydrological system, the publication claim must be reduced or Publication Path P1 abandoned.

---

# 14. SENTINEL-1 ROLE

Sentinel-1 is no longer mandatory for the main hydrological publication.

Its possible roles are:

## Role A

Support the EFS analysis.

## Role B

Develop and validate a higher-resolution inundation/hydroperiod product.

## Role C

Provide a fallback publication pathway if the hydrological configuration experiment becomes impossible.

Sentinel-1 must not be claimed to:

* directly identify AWD;
* continuously measure flooded days;
* detect every short dry-down;
* provide independent biological evidence.

The initial validation pilot should use 2019–2020.

Validation should be performed using field/year-blocked methods rather than random pixel splitting.

---

# 15. GREENHOUSE-GAS STRATEGY

## EFS report

Methane and nitrous oxide remain important ecosystem-functioning/service indicators.

Use:

* local empirical observations where available;
* European evidence;
* appropriate meta-analysis;
* uncertainty ranges.

## Publication study

GHG should initially be treated as a secondary scenario or constraint.

Do not create parcel-level CH4/N2O maps from generic literature multipliers.

Detailed process modelling should proceed only if adequate local inputs and calibration data become available.

---

# 16. PRODUCTION STRATEGY

## EFS

Use local and experimentally supported yield evidence.

## Publication

Production should initially function as a feasibility/non-inferiority constraint rather than a falsely precise parcel-level objective.

Any production threshold must be:

* justified before optimization;
* sensitivity-tested;
* clearly distinguished from observed yields.

---

# 17. ECOLOGY STRATEGY

Without independent biological observations, permitted ecological outputs include:

* flooded-habitat availability;
* hydroperiod availability;
* inundated-area continuity;
* distance to permanent wetlands;
* landscape water connectivity;
* refuge availability.

Do not convert these indicators into claims about:

* biodiversity increase;
* species richness;
* amphibian abundance;
* waterbird abundance;
* ecological condition

without relevant biological evidence.

---

# 18. HARD PROHIBITED CLAIMS

Unless new evidence explicitly supports them, do not state that:

1. AWD is universally environmentally superior.
2. Sentinel-1 directly identifies AWD.
3. Sentinel-1 continuously observes flooded days.
4. reduced field irrigation equals district water saving.
5. reduced field irrigation equals basin water saving.
6. hydroperiod equals biodiversity.
7. inundated area equals biodiversity.
8. literature multipliers precisely predict parcel methane.
9. literature multipliers precisely predict parcel nitrous oxide.
10. literature multipliers precisely predict parcel yield.
11. pixels are independent experimental replicates.
12. simulated scenarios automatically establish causality.
13. optimization demonstrates the socially optimal policy.
14. integration of several outcomes is itself novelty.
15. application to Lomellina is itself novelty.
16. model outputs are observations.
17. district results automatically generalize to Europe.

---

# 19. REQUIRED INFERENCE LANGUAGE

Every major result should be classified using suitable language.

## Observed

Directly measured or retrieved.

## Descriptive

Summary of observed patterns.

## Associated

Statistical relationship without causal identification.

## Literature-supported

Supported by external empirical literature.

## Model-estimated

Produced by a model.

## Counterfactual

Hypothetical scenario generated by modelling.

## Causal

Use only where the research design genuinely permits causal inference.

---

# 20. GO / NO-GO GATES

## G1 — Novelty

Question:

Does the fixed-composition configuration/synchronization gap survive the Phase-2 competitor search?

Failure:

reframe or abandon the publication hypothesis.

## G2 — EFS open-data feasibility

Question:

Can the EFS report be completed using reproducible open datasets and evidence?

Failure:

redesign the quantitative EFS component.

## G3 — MEDWATERICE usability

Question:

Can local experimental datasets be correctly interpreted and reproduced?

Failure:

use verified published results rather than constructing unsupported variables.

## G4 — Sentinel validation

Question:

Does independently validated Sentinel performance support the intended inference?

Failure:

drop or restrict remote-sensing claims.

## G5 — Hydrological platform

Question:

Can a suitable existing Lomellina/San Giorgio platform be accessed, reproduced and validated?

Failure:

abandon Publication Path P1.

## G6 — Operational hydrology

Question:

Are diversion, network, groundwater and return-flow components sufficiently constrained?

Failure:

no district water-saving/configuration claim.

## G7 — Configuration signal

Question:

Is the fixed-composition configuration effect practically meaningful and greater than combined uncertainty?

Failure:

**stop optimization.**

## G8 — Biological evidence

Question:

Are suitable biological observations available?

Failure:

use habitat proxies only.

## G9 — GHG modelling

Question:

Are adequate local inputs/calibration available?

Failure:

use aggregate literature-based scenario evidence only.

## G10 — Final novelty audit

Immediately before submission, repeat the literature and competitor search.

If the gap has been closed by new research, revise or abandon the novelty claim.

---

# 21. FINAL PROJECT PHASES

## Phase 1 — Protocol Freeze

Purpose:

prevent moving research questions and post-hoc methodological changes.

Outputs:

* research questions;
* hypotheses;
* spatial/temporal boundaries;
* claim boundaries;
* GO/NO-GO rules;
* reproducibility protocol.

Status:

**SCIENTIFICALLY COMPLETE**

Repository infrastructure remains under final setup.

---

## Phase 2 — Evidence and Data Acquisition

Tasks:

* systematic literature search;
* competitor/novelty search;
* source verification;
* MEDWATERICE inventory;
* RiceFloodIT acquisition;
* GIS acquisition;
* restricted-data requests.

Outputs:

* literature database;
* competitor matrix;
* evidence matrix;
* data-access register;
* data inventory.

---

## Phase 3 — Data Audit and Reproduction

Before new analysis:

reproduce important published/local results.

Examples:

* RiceFloodIT historical trends;
* MEDWATERICE management/water/yield summaries.

Purpose:

ensure datasets and interpretation are correct.

---

## Phase 4 — EFS Quantitative Analysis

Potential analyses:

* hydroperiod trends;
* spatial hydroperiod changes;
* rice/wetland/canal landscape relationships;
* evidence-based trade-offs;
* field-versus-district water regulation;
* ecosystem-functioning synthesis.

Output:

core EFS results and figures.

---

## Phase 5 — Sentinel Pilot

Initial period:

2019–2020.

Purpose:

determine whether field-scale inundation analysis can be independently validated.

This phase is conditional, not required for basic EFS success.

---

## Phase 6 — EFS Freeze and Publication Gate

Complete the course report.

Then make an explicit decision:

* Publication P1;
* Publication P2;
* alternative publication;
* stop publication extension.

---

## Phase 7 — Hydrological Reproduction

If Publication P1 survives:

reproduce and validate an existing district-scale hydrological platform.

Do not immediately build another generic Lomellina model.

---

## Phase 8 — Fixed-Composition Configuration Experiment

Hold regime proportions constant.

Change only:

* spatial placement;
* network position;
* temporal synchronization.

Estimate effect on:

* peak diversion;
* seasonal diversion;
* recharge;
* groundwater;
* return-flow timing.

---

## Phase 9 — Robust Decision Analysis

Proceed only if configuration signal survives G7.

Include:

* parameter uncertainty;
* model uncertainty;
* observational uncertainty;
* production constraints;
* optional GHG constraints.

Optimization is conditional.

---

## Phase 10 — Publication Freeze

Before submission:

* rerun novelty search;
* audit every claim;
* reproduce all results from clean environment;
* freeze figures/tables;
* verify references;
* tag repository;
* prepare reproducibility release.

---

# 22. EXPECTED SCIENTIFIC OUTCOMES

These are hypotheses/priors, not predetermined findings.

Current expectations include:

* long-term reduction/reorganization of traditional early-season flooding;
* field irrigation reductions may not translate one-to-one into district water savings;
* delayed flooding may shift irrigation demand later in the season;
* safe AWD may reduce field irrigation while maintaining yield under appropriate local conditions;
* reduction of standing water may alter temporary aquatic habitat availability;
* composition will probably influence seasonal water demand more than configuration;
* configuration/synchronization may influence peak demand more strongly than seasonal totals.

These expectations must not be converted into conclusions before analysis.

---

# 23. CURRENT PUBLICATION OPTIONS

## Preferred — P1

Fixed-composition configuration/synchronization experiment using a validated Lomellina hydrological platform.

Current status:

**CONDITIONAL**

Main requirements:

* novelty survives;
* operational data available;
* model reproducible;
* hydrology validated;
* effect exceeds uncertainty.

## Fallback — P2

Sentinel-based study of long-term reorganization of rice inundation timing/synchronization and hydrological context.

This pathway also requires a new novelty audit because generic Sentinel rice-flooding mapping already exists.

## Rejected

Broad integrated water–GHG–yield–biodiversity optimization without suitable local observations.

---

# 24. REPRODUCIBILITY ARCHITECTURE

The required scientific chain is:

**Raw data
→ processing code
→ processed data
→ analytical dataset
→ analysis/model
→ diagnostics
→ figure/table
→ scientific claim**

Every important manuscript claim should eventually be traceable through this chain.

---

# 25. GIT/GITHUB RULES

The GitHub repository is the authoritative version-controlled research record.

## Git contains

* source code;
* protocols;
* documentation;
* decision records;
* metadata;
* literature records;
* small legal-to-share processed data;
* figures/tables;
* diagnostics;
* environment specification.

## Git generally does not contain

* large raw rasters;
* Sentinel archives;
* restricted institutional data;
* farmer-level confidential information;
* credentials;
* tokens;
* externally licensed data that cannot legally be redistributed.

## One authoritative script per analytical task

Do not create:

* `analysis_final.py`;
* `analysis_final2.py`;
* `analysis_REAL_FINAL.py`.

Git preserves history.

The authoritative filename remains stable.

## Meaningful commits

Examples:

* `Freeze research protocol`
* `Inventory MEDWATERICE datasets`
* `Reproduce RiceFloodIT annual flooding trend`
* `Add spatial-block validation`
* `Reject configuration hypothesis after uncertainty test`

Avoid vague commits such as:

* `stuff`
* `changes`
* `final`
* `updates`

---

# 26. IMPORTANT PROJECT FILES

## `PROJECT_MASTER.md`

This document.

Highest-level continuity record.

## `PROJECT_STATUS.md`

Short current-state record.

Must show:

* current phase;
* recently completed work;
* next action;
* blocked tasks;
* current GO/NO-GO status.

## `docs/decisions/decision_log.md`

Permanent methodological decision history.

Old decisions must not be silently deleted.

## `docs/data/data_access_register.csv`

Every dataset must be registered before analytical use.

## `docs/claims/claim_register.csv`

Maps claims to:

* evidence;
* data;
* scripts;
* outputs;
* uncertainty;
* limitations.

## `docs/protocol/`

Contains frozen scientific protocol documents.

---

# 27. PROJECT RESTART PROCEDURE

If work is resumed after losing context, do the following in order.

### Step 1

Read:

`PROJECT_MASTER.md`

### Step 2

Read:

`PROJECT_STATUS.md`

### Step 3

Read the latest entries in:

`docs/decisions/decision_log.md`

### Step 4

Check Git:

```bash
git status
git log --oneline --decorate -10
git tag
```

### Step 5

Check:

`docs/data/data_access_register.csv`

to see what datasets have actually been acquired.

### Step 6

Check:

`docs/claims/claim_register.csv`

to see what conclusions are currently supported.

### Step 7

Continue from the exact task recorded under:

**NEXT ACTION**

in `PROJECT_STATUS.md`.

Do not reconstruct the research programme from memory or start a new methodology without checking these files.

---

# 28. CURRENT PROJECT STATE — 29 AUGUST 2026

## Completed scientifically

* original research concept critically audited;
* overly broad publication design rejected;
* EFS and publication products separated;
* spatial hierarchy established;
* temporal hierarchy established;
* EFS research question frozen;
* publication question frozen;
* hypotheses frozen;
* claim boundaries established;
* configuration-versus-composition distinction established;
* conditional optimization rule established;
* publication stopping rules established;
* principal data sources identified;
* GitHub private repository created.

## Git repository

Local repository:

`C:\Users\Admin\Documents\EFS-Lomellina-Rice-Tradeoffs`

Remote:

`https://github.com/taimoora66/Lomellina-Rice-Tradeoffs.git`

Branch:

`main`

Repository status at foundation:

no analytical work committed yet.

---

# 29. NEXT ACTION

Current immediate task:

**Finish Phase 1B repository foundation before downloading or analysing data.**

Required actions:

1. create repository folder structure;
2. create `.gitignore`;
3. add this `PROJECT_MASTER.md`;
4. create `PROJECT_STATUS.md`;
5. create frozen protocol files;
6. create decision log;
7. create data-access register;
8. create claim register;
9. review `git status`;
10. make first scientific commit;
11. push to GitHub;
12. create tag:

`v0.1-protocol-freeze`

Only after this is complete should Phase 2 begin.

---

# 30. PHASE 2 FIRST PRIORITIES

Once Phase 1B is frozen:

## Phase 2A

Systematic literature and competitor verification.

Primary objective:

determine whether the fixed-composition configuration/synchronization publication gap genuinely survives.

## Phase 2B

Acquire and inventory:

* MEDWATERICE;
* RiceFloodIT;
* essential GIS layers.

## Phase 2C

Prepare requests for:

* Est Sesia operational data;
* SmartWT observations;
* hydrological-model access;
* other publication-critical restricted datasets.

No new modelling should begin before these foundations are complete.

---

# 31. GOVERNING SCIENTIFIC PRINCIPLE

The project does not exist to demonstrate that a predetermined management strategy is superior.

It exists to determine what the available evidence supports.

The following outcomes are all acceptable:

* configuration matters substantially;
* configuration matters only for peak demand;
* composition dominates configuration;
* spatial configuration is negligible;
* Sentinel is useful only during part of the season;
* ecological conclusions remain limited to habitat;
* hydrological data are inadequate for publication P1;
* the apparent novelty is closed by another study.

A scientifically justified rejection of a hypothesis is preferable to an unsupported positive conclusion.

---

# 32. ONE-SENTENCE PROJECT SUMMARY

**This project first quantifies and synthesizes hydroperiod-related ecosystem-functioning and service trade-offs in Lomellina rice landscapes for an EFS report, and then conditionally tests whether the spatial placement and synchronization of irrigation regimes has an independent effect on district hydrology when management composition is held constant.**

---

# 33. RULE FOR FUTURE RESEARCH ASSISTANTS OR AI SYSTEMS

Before continuing this project:

**Do not redesign it from scratch.**

First reconstruct the current state from:

* this master record;
* Git history;
* frozen protocols;
* decision log;
* data register;
* claim register;
* current outputs.

Existing analyses must be treated as candidates to verify rather than assumptions to inherit.

New methods should be proposed only when:

* existing project evidence is insufficient;
* a current GO/NO-GO gate requires them;
* or new literature/data materially change the scientific position.

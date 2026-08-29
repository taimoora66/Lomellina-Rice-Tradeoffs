# MEDWATERICE Reproducibility Checklist

## Gate G3

Question:

Can the MEDWATERICE datasets, treatment definitions and published
results be interpreted and reproduced reliably?

Current status:

**OPEN**

## Required Checks

- [ ] Identify all Lomellina/Northern Italy datasets.
- [ ] Verify dataset DOI and version.
- [ ] Verify licence.
- [ ] Identify field/site names.
- [ ] Identify experiment years.
- [ ] Extract exact WFL definition.
- [ ] Extract exact DFL definition.
- [ ] Extract exact AWD definition.
- [ ] Verify irrigation units.
- [ ] Verify rainfall units.
- [ ] Verify percolation/recharge variables.
- [ ] Verify groundwater variables.
- [ ] Verify yield units.
- [ ] Identify missing values and flags.
- [ ] Identify experimental replication.
- [ ] Identify field/plot hierarchy.
- [ ] Link datasets to associated publications.
- [ ] Reproduce at least one published treatment summary.
- [ ] Compare reproduced values with publication values.
- [ ] Document discrepancies.
- [ ] Issue G3 GO / RESTRICT / NO-GO verdict.

## Important Rule

Do not harmonize treatment labels across experiments until their actual
operational definitions have been checked.

A label such as AWD does not guarantee identical water-management
implementation across sites or years.

# G3 MEDWATERICE Usability Decision — 2026-08-29

## Verdict

**G3 = GO WITH RESTRICTIONS**

The 2019–2020 Castello d'Agogna CS1 datasets are suitable for local
field-scale quantitative evidence on irrigation management, water
balance, groundwater dynamics and rice production.

## Experimental Structure

For each irrigation-management regime:

- two plots of approximately 0.15 ha were established;
- only one plot was instrumented for water-flux and storage monitoring;
- crop-development observations were principally collected in the
  instrumented plot;
- yield and product-quality observations were collected in both plots;
- plots contain subplots with differing fertilizer and crop-protection
  treatments.

Therefore daily observations, sensors and subplots must not be treated
as independent irrigation-treatment replicates.

## Supported Outcomes

- irrigation inflow;
- irrigation outflow;
- net irrigation;
- ponding-water level;
- rainfall;
- evapotranspiration context;
- groundwater depth/time series;
- water-balance-derived percolation;
- model-estimated percolation;
- rice grain yield and selected product-quality variables.

## Restricted Outcomes

Greenhouse-gas observations are insufficient in these workbooks for
local quantitative treatment comparison.

No direct biodiversity inference is supported.

## Important Interpretation Rule

WFL, DFL and AWD represent management systems rather than isolated
irrigation treatments.

DFL differs from WFL/AWD in seeding practice as well as flooding timing.

Observed differences must therefore not automatically be attributed to
a single water-management mechanism.

## Groundwater Restriction

Piezometer identity and layout differ among treatment/year
combinations.

Groundwater time-series observations therefore require explicit spatial
and repeated-measures interpretation.

## Percolation Terminology

Perc_Bal = water-balance-derived percolation estimate.

Perc_MODEL = model-estimated percolation from the distributed
Darcy-type framework.

Neither should automatically be labelled directly observed aquifer
recharge.

## QA Issue

Apparent dates such as 1/10/1900 in AWD 2020 groundwater chemistry
columns are suspected Excel number-format artifacts.

Underlying cell values and formats must be inspected before cleaning.

## Decision

MEDWATERICE passes G3 for constrained field-scale analysis and
reproduction.

It does not authorize causal or district-scale extrapolation.

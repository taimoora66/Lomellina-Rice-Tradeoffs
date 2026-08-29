# Data Directory

This directory contains datasets used by the Lomellina rice-water
trade-offs project.

## raw/

Original source data exactly as obtained.

Rules:

- never manually edit;
- preserve original filenames;
- preserve source metadata;
- record every dataset in the data-access register.

Raw data are excluded from Git by default.

## external/

Provider-supplied or externally harmonized datasets.

## interim/

Temporary processing products.

These files may be regenerated and should not be treated as final results.

## processed/

Analytical datasets generated reproducibly from scripts.

Before committing any processed dataset, verify:

- licence;
- confidentiality;
- file size;
- redistribution rights;
- provenance.

## Dataset Register

Every dataset used analytically must be recorded in:

`docs/data/data_access_register.csv`

No dataset should enter the analytical workflow without a provenance record.
# Publication groundwater scripts

This directory separates the new observational publication track from the completed EFS analyses.

## `recovered/`

Scripts recovered from exploratory analyses conducted interactively on 2026-08-30/31. They preserve the actual analytical history. They are intentionally **not renamed as a final pipeline** and may contain absolute `/mnt/data` paths or intermediate dependencies. Their purpose is auditability.

## Reproducible acquisition

`00_download_arpa_meteo.py` is the first rebuilt production component. It reconstructs the six ARPA meteorological subsets used in the 2008–2021 linked panel using public Socrata endpoints with pagination.

## Production pipeline to build next

Planned frozen sequence:

1. `01_groundwater_clean.py`
2. `02_ricefloodit_georeference.py`
3. `03_weather_clean_aggregate.py`
4. `04_build_well_exposures.py`
5. `05_build_analysis_panel.py`
6. `06_primary_model.py`
7. `07_spatial_inference.py`
8. `08_multiverse_simultaneous_inference.py`
9. `09_sample_well_robustness.py`
10. `10_make_tables_figures.py`
11. `20_reconstruct_post2021_flooding.py`
12. `21_bridge_ricefloodit_post2021.py`
13. `22_validate_2022_2025.py`

Do not create result-driven variants outside this numbered pipeline after model freeze.

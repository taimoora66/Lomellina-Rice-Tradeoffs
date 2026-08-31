# Groundwater publication — reconstruction runbook

This runbook reconstructs the full 2008–2021 discovery dataset from open/raw inputs before any new hypothesis testing.

## Research-stage labels

- **QA**: data integrity and reconstruction only; no outcome-driven model changes.
- **EXPLORE**: analytical development; results are exploratory.
- **FREEZE**: choices are fixed before the next confirmatory rerun.
- **VALIDATE**: held-out 2022–2025 work; no tuning against groundwater outcomes.

The scripts below are **QA**.

## Expected local raw inputs

Git intentionally does not track raw ARPA files.

Place:

- `data/raw/arpa/groundwater_pavia.xlsx`
- `data/raw/arpa/weather_station_master.csv`

RiceFloodIT already lives at:

- `data/raw/RiceFloodIT/ffavg_2021.csv`

Meteorological observations are downloaded reproducibly by script `00_download_arpa_meteo.py` to `data/raw/arpa_meteo/`.

## Environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-publication.txt
```

## Run one step at a time

### 0. Download ARPA meteorology

```powershell
python scripts/04_publication_groundwater/00_download_arpa_meteo.py
```

### 1. Groundwater cleaning

```powershell
python scripts/04_publication_groundwater/01_groundwater_clean.py
```

Expected core QA:

- raw rows = 5,946
- stations = 68
- duplicate station-date groups = 249
- conflicting station-date groups = 1
- cleaned rows = 5,696
- ISS wells = 37
- ISS cleaned rows = 3,084
- 2008–2021 ISS station-year grid = 518
- observed ISS station-years = 330
- Jan–Feb + August station-years = 221

### 2. RiceFloodIT georeferencing

```powershell
python scripts/04_publication_groundwater/02_ricefloodit_georeference.py
```

Expected core QA:

- rows = 80,926
- years = 22 (2000–2021)
- unique pixels = 4,331
- balanced pixels = 2,419
- median positive x-grid spacing ≈ 926.6254 m

The MODIS-sinusoidal interpretation is numerically supported and exactly reproduces the earlier buffer metrics, but authoritative source-product CRS confirmation remains a publication gate.

### 3. Weather cleaning and monthly aggregation

```powershell
python scripts/04_publication_groundwater/03_weather_clean_aggregate.py
```

Expected current download QA:

- precipitation raw rows: 574,046 / 2,322,108 / 323,353
- temperature raw rows: 408,884 / 2,646,837 / 376,004
- valid precipitation sensor-months = 952
- valid temperature sensor-months = 1,079

### 4. RiceFloodIT well-buffer exposures

```powershell
python scripts/04_publication_groundwater/04_build_well_exposures.py
```

Expected core QA:

- rows = 518 = 37 wells × 14 years
- median pixels: 2 km = 9, 5 km = 52, 10 km = 182
- station-years with FF: 2 km = 402, 5 km = 433, 10 km = 479

This reconstruction was checked against the recovered exploratory panel: all `ff`, count-weighted `ffw`, balanced-pixel `ffb`, `n`, and `nbal` values at 2/5/10 km reproduced exactly.

### 5. Build discovery panel

```powershell
python scripts/04_publication_groundwater/05_build_analysis_panel.py
```

Expected current QA:

- rows = 518
- wells = 37
- years = 14
- Jan–Feb antecedent + August outcome availability = 221
- complete candidate August/FF10/weather/antecedent-GW rows = 194
- complete candidate wells = 32

The reconstructed April–August precipitation and temperature controls reproduce the recovered exploratory weather panel exactly for `P_A6/T_A6`, `P_A7/T_A7`, and `P_A8/T_A8`.

## Important difference from the old exploratory panel

The recovered exploratory panel contained an undocumented column named `pre`. We do **not** propagate that ambiguous variable into the production pipeline.

The reconstructed panel instead contains transparent groundwater fields, including:

- `gw_pre_last_janfeb_m`: last valid January–February measurement
- `gw_janfeb_mean_m`
- `gw_janmar_mean_m`
- `gw_aug_mean_m`
- August first/last/nearest-Aug-23 alternatives
- monthly groundwater means

The next research stage must freeze which of these is primary **before** inspecting the new primary model.

## Generated files

The scripts create local derived data under:

`data/processed/publication_groundwater/`

and compact audit tables under:

`outputs/diagnostics/publication_groundwater/`

Do not edit derived CSVs manually. Regenerate them from the scripts.

## Where the project resumes after QA

Once all five steps reproduce locally, do not repeat the earlier exploratory regressions. Resume at the unresolved scientific stage:

1. freeze the direct-August model with strictly antecedent groundwater;
2. run the 2008–2021 model once;
3. implement Conley/spatial-HAC and geographic-block inference;
4. implement multiplicity/specification-curve inference;
5. apply the predeclared kill rule;
6. only if the discovery relationship survives, build and freeze a MODIS-compatible 2022–2025 flooding extension before looking at held-out groundwater outcomes.

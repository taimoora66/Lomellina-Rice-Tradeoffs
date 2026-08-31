$ErrorActionPreference = "Stop"

Write-Host "[0/5] Downloading ARPA meteorology (skip if already present)" -ForegroundColor Cyan
python scripts/04_publication_groundwater/00_download_arpa_meteo.py

Write-Host "[1/5] Cleaning groundwater" -ForegroundColor Cyan
python scripts/04_publication_groundwater/01_groundwater_clean.py

Write-Host "[2/5] Georeferencing RiceFloodIT" -ForegroundColor Cyan
python scripts/04_publication_groundwater/02_ricefloodit_georeference.py

Write-Host "[3/5] Cleaning and aggregating weather" -ForegroundColor Cyan
python scripts/04_publication_groundwater/03_weather_clean_aggregate.py

Write-Host "[4/5] Building well-buffer flooding exposures" -ForegroundColor Cyan
python scripts/04_publication_groundwater/04_build_well_exposures.py

Write-Host "[5/5] Building discovery panel" -ForegroundColor Cyan
python scripts/04_publication_groundwater/05_build_analysis_panel.py

Write-Host "Pipeline complete. Review outputs/diagnostics/publication_groundwater before fitting models." -ForegroundColor Green

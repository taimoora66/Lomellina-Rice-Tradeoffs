# ============================================================
# EFS LOMELLINA RICE TRADE-OFFS
# SPATIAL PUBLICATION READINESS GATE
#
# Purpose:
# Determine whether the repository contains the minimum
# evidence required to begin field-level scenario modelling.
#
# This script does NOT modify data.
# This script does NOT run statistical models.
# This script does NOT infer missing evidence.
# ============================================================

$ErrorActionPreference = "Stop"

$root = (Get-Location).Path

Write-Host ""
Write-Host ("=" * 110)
Write-Host "EFS LOMELLINA RICE TRADE-OFFS"
Write-Host "SPATIAL PUBLICATION READINESS GATE"
Write-Host ("=" * 110)
Write-Host ""
Write-Host "Repository:"
Write-Host $root
Write-Host ""

# ------------------------------------------------------------
# Required directory families
# ------------------------------------------------------------

$directories = @(
    "data",
    "data\raw",
    "data\interim",
    "data\processed",
    "outputs",
    "outputs\tables",
    "outputs\diagnostics",
    "validation",
    "figures",
    "scripts",
    "docs",
    "literature"
)

Write-Host "DIRECTORY STRUCTURE"
Write-Host ("-" * 110)

foreach ($d in $directories) {

    $path = Join-Path $root $d

    if (Test-Path $path) {
        Write-Host ("PASS   {0}" -f $d)
    }
    else {
        Write-Host ("MISS   {0}" -f $d)
    }
}

# ------------------------------------------------------------
# File inventory
# ------------------------------------------------------------

$allFiles = Get-ChildItem `
    -Path $root `
    -Recurse `
    -File

Write-Host ""
Write-Host "TOTAL FILE INVENTORY"
Write-Host ("-" * 110)

Write-Host ("Total files: {0}" -f $allFiles.Count)

# ------------------------------------------------------------
# Evidence families
# ------------------------------------------------------------

$checks = @(
    @{
        Name = "Rice-field / parcel spatial data"
        Patterns = @(
            "rice.*mask",
            "rice.*field",
            "field.*boundary",
            "field.*parcel",
            "parcel",
            "SIARL",
            "SISCO",
            "DUSAF",
            "\.shp$",
            "\.gpkg$",
            "\.geojson$"
        )
    },

    @{
        Name = "Sentinel-1 / radar data"
        Patterns = @(
            "sentinel",
            "S1",
            "VV",
            "VH",
            "radar"
        )
    },

    @{
        Name = "Hydroperiod / flooding outputs"
        Patterns = @(
            "hydroperiod",
            "flooded",
            "flooding",
            "water.*state"
        )
    },

    @{
        Name = "Independent flooding validation"
        Patterns = @(
            "validation.*flood",
            "flood.*validation",
            "confusion",
            "precision",
            "recall",
            "F1",
            "balanced.*accuracy",
            "ground.*truth"
        )
    },

    @{
        Name = "Irrigation district / canal network"
        Patterns = @(
            "irrigation.*district",
            "district.*irrigation",
            "canal",
            "network",
            "Est.*Sesia",
            "return.*flow"
        )
    },

    @{
        Name = "District groundwater observations"
        Patterns = @(
            "groundwater",
            "water.*table",
            "piezometer",
            "ARPA"
        )
    },

    @{
        Name = "Soil spatial data"
        Patterns = @(
            "soil.*map",
            "soil.*spatial",
            "soil.*GIS",
            "texture",
            "hydraulic.*conductivity"
        )
    },

    @{
        Name = "Meteorological data"
        Patterns = @(
            "meteor",
            "rainfall",
            "precipitation",
            "temperature",
            "weather"
        )
    },

    @{
        Name = "GHG evidence / parameters"
        Patterns = @(
            "GHG",
            "methane",
            "CH4",
            "N2O",
            "emission"
        )
    },

    @{
        Name = "Yield / production evidence"
        Patterns = @(
            "yield",
            "production",
            "water.*productivity"
        )
    },

    @{
        Name = "Habitat evidence / indicators"
        Patterns = @(
            "habitat",
            "hydroperiod",
            "connectivity",
            "wetland"
        )
    },

    @{
        Name = "Scenario / mosaic / optimization outputs"
        Patterns = @(
            "scenario",
            "mosaic",
            "spatial",
            "pareto",
            "optim",
            "uncertainty",
            "sensitivity",
            "robust"
        )
    }
)

$results = @()

Write-Host ""
Write-Host "EVIDENCE FAMILY SEARCH"
Write-Host ("-" * 110)

foreach ($check in $checks) {

    $matches = $allFiles | Where-Object {

        $name = $_.Name

        foreach ($pattern in $check.Patterns) {

            if ($name -match $pattern) {
                return $true
            }
        }

        return $false
    }

    $results += [PSCustomObject]@{
        EvidenceFamily = $check.Name
        FileCount      = $matches.Count
        Status         = if ($matches.Count -gt 0) { "PRESENT" } else { "MISSING" }
    }

    if ($matches.Count -gt 0) {

        Write-Host ""
        Write-Host ("[{0}]  {1} files" -f $check.Name, $matches.Count)

        $matches |
            Sort-Object FullName |
            Select-Object -First 15 FullName, Length |
            Format-Table -AutoSize
    }
    else {

        Write-Host ""
        Write-Host ("[{0}]  MISSING" -f $check.Name)
    }
}

# ------------------------------------------------------------
# Existing analytical outputs
# ------------------------------------------------------------

Write-Host ""
Write-Host ("=" * 110)
Write-Host "EXISTING EMPIRICAL / EFS OUTPUTS"
Write-Host ("=" * 110)

$outputPatterns = @(
    "MEDWATERICE",
    "RiceFloodIT",
    "GHG",
    "habitat",
    "yield",
    "groundwater",
    "tradeoff"
)

$outputMatches = $allFiles | Where-Object {

    $name = $_.Name

    foreach ($pattern in $outputPatterns) {

        if ($name -match $pattern) {
            return $true
        }
    }

    return $false
}

$outputMatches |
    Sort-Object FullName |
    Select-Object FullName, Length |
    Format-Table -AutoSize

# ------------------------------------------------------------
# Explicit publication gate logic
# ------------------------------------------------------------

$spatialFamilies = @(
    "Rice-field / parcel spatial data",
    "Sentinel-1 / radar data",
    "Hydroperiod / flooding outputs",
    "Independent flooding validation",
    "Irrigation district / canal network",
    "District groundwater observations"
)

$presentSpatial = $results |
    Where-Object {
        $_.EvidenceFamily -in $spatialFamilies -and
        $_.Status -eq "PRESENT"
    }

$missingSpatial = $results |
    Where-Object {
        $_.EvidenceFamily -in $spatialFamilies -and
        $_.Status -eq "MISSING"
    }

Write-Host ""
Write-Host ("=" * 110)
Write-Host "PUBLICATION GATE DECISION"
Write-Host ("=" * 110)

Write-Host ""
Write-Host "Spatial evidence families present:"
Write-Host $presentSpatial.Count

Write-Host ""
Write-Host "Spatial evidence families missing:"
Write-Host $missingSpatial.Count

Write-Host ""

if ($missingSpatial.Count -eq 0) {

    Write-Host "GATE STATUS: PROVISIONALLY OPEN" -ForegroundColor Green
    Write-Host ""
    Write-Host "All minimum spatial evidence families appear to exist."
    Write-Host "Next step: inspect each dataset for scientific validity,"
    Write-Host "independence and temporal/spatial coverage before modelling."
}
else {

    Write-Host "GATE STATUS: NOT YET OPEN" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Missing spatial evidence families:"
    $missingSpatial |
        Format-Table EvidenceFamily, Status -AutoSize

    Write-Host ""
    Write-Host "Do NOT begin spatial optimization yet."
    Write-Host "Resolve or formally document the missing dependencies first."
}

# ------------------------------------------------------------
# Existing scenario outputs check
# ------------------------------------------------------------

$scenarioMatches = $allFiles |
    Where-Object {
        $_.Name -match "scenario|mosaic|pareto|optim"
    }

Write-Host ""
Write-Host ("=" * 110)
Write-Host "SCENARIO / OPTIMIZATION STATUS"
Write-Host ("=" * 110)

if ($scenarioMatches.Count -eq 0) {

    Write-Host "No scenario / mosaic / Pareto / optimization output files detected."
    Write-Host "This is CONSISTENT with the current project status."
}
else {

    Write-Host ("Detected files: {0}" -f $scenarioMatches.Count)

    $scenarioMatches |
        Sort-Object FullName |
        Select-Object FullName, Length |
        Format-Table -AutoSize
}

# ------------------------------------------------------------
# Final interpretation
# ------------------------------------------------------------

Write-Host ""
Write-Host ("=" * 110)
Write-Host "FINAL INTERPRETATION"
Write-Host ("=" * 110)

Write-Host ""
Write-Host "Completed foundation:"
Write-Host "  - MEDWATERICE empirical processing"
Write-Host "  - hydrological QA"
Write-Host "  - groundwater descriptive coupling"
Write-Host "  - yield hierarchy and plot-level analysis"
Write-Host "  - GHG evidence synthesis"
Write-Host "  - habitat evidence synthesis"
Write-Host "  - integrated EFS trade-off matrix"

Write-Host ""
Write-Host "Publication-track components still requiring explicit execution:"
Write-Host "  - spatial field representation"
Write-Host "  - validated field hydroperiod reconstruction"
Write-Host "  - scenario counterfactuals"
Write-Host "  - spatial configuration experiment"
Write-Host "  - Pareto analysis"
Write-Host "  - ecological constraints"
Write-Host "  - uncertainty propagation"
Write-Host "  - sensitivity analysis"
Write-Host "  - robustness / negative controls"
Write-Host "  - final freeze and claim audit"

Write-Host ""
Write-Host "IMPORTANT:"
Write-Host "Presence of a filename does not constitute scientific validation."
Write-Host "Each dataset must be checked for actual content, independence,"
Write-Host "spatial coverage, temporal coverage and provenance."
Write-Host ""

# ------------------------------------------------------------
# Save audit table
# ------------------------------------------------------------

$results |
    Export-Csv `
        "outputs\diagnostics\spatial_publication_readiness_gate.csv" `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host "Saved:"
Write-Host "outputs\diagnostics\spatial_publication_readiness_gate.csv"
Write-Host ""
Write-Host ("=" * 110)
Write-Host "SPATIAL PUBLICATION READINESS GATE COMPLETE"
Write-Host ("=" * 110)

# ============================================================
# RiceFloodIT balanced-panel QA
# ============================================================

$ErrorActionPreference = "Stop"

$path = "data\raw\RiceFloodIT\ffavg_2021.csv"
$outDir = "docs\data"

Write-Host "Loading RiceFloodIT..." -ForegroundColor Cyan

$rows = Import-Csv $path

# Build pixel-year structure
$pixelYears = @{}
$pixelSubdistricts = @{}

foreach ($r in $rows) {

    $pixel = "$($r.x)|$($r.y)"
    $year = [int]$r.year

    if (-not $pixelYears.ContainsKey($pixel)) {
        $pixelYears[$pixel] = @{}
        $pixelSubdistricts[$pixel] = @{}
    }

    $pixelYears[$pixel][$year] = $true
    $pixelSubdistricts[$pixel][$r.subdistrict] = $true
}

# Complete 22-year pixels
$balancedPixels = @{}

foreach ($pixel in $pixelYears.Keys) {

    if ($pixelYears[$pixel].Count -eq 22) {
        $balancedPixels[$pixel] = $true
    }
}

# Check whether any pixel changes subdistrict assignment
$unstableSubdistrict = foreach ($pixel in $pixelSubdistricts.Keys) {

    if ($pixelSubdistricts[$pixel].Count -gt 1) {

        [PSCustomObject]@{
            pixel = $pixel
            n_subdistricts = $pixelSubdistricts[$pixel].Count
            subdistricts = (($pixelSubdistricts[$pixel].Keys | Sort-Object) -join ",")
        }
    }
}

# Full versus balanced annual summaries
$annual = foreach ($year in 2000..2021) {

    $yr = @($rows | Where-Object {[int]$_.year -eq $year})

    $balanced = @(
        $yr | Where-Object {
            $pixel = "$($_.x)|$($_.y)"
            $balancedPixels.ContainsKey($pixel)
        }
    )

    $fullFF = @($yr | ForEach-Object {[double]$_.ff})
    $balFF  = @($balanced | ForEach-Object {[double]$_.ff})

    [PSCustomObject]@{
        year = $year

        n_full = $yr.Count
        mean_ff_full = [math]::Round(
            ($fullFF | Measure-Object -Average).Average, 6
        )

        n_balanced = $balanced.Count
        mean_ff_balanced = [math]::Round(
            ($balFF | Measure-Object -Average).Average, 6
        )

        difference = [math]::Round(
            (($balFF | Measure-Object -Average).Average -
             ($fullFF | Measure-Object -Average).Average), 6
        )
    }
}

$annual |
Export-Csv `
"$outDir\RiceFloodIT_full_vs_balanced_annual.csv" `
-NoTypeInformation `
-Encoding UTF8

$unstableSubdistrict |
Export-Csv `
"$outDir\RiceFloodIT_subdistrict_stability.csv" `
-NoTypeInformation `
-Encoding UTF8

# Observation-count distribution
$countSummary = $rows |
Group-Object count |
Sort-Object {[int]$_.Name} |
ForEach-Object {

    [PSCustomObject]@{
        image_count = [int]$_.Name
        records = $_.Count
        percent = [math]::Round(
            100 * $_.Count / $rows.Count, 3
        )
    }
}

$countSummary |
Export-Csv `
"$outDir\RiceFloodIT_image_count_distribution.csv" `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "================ PANEL SUMMARY ================" -ForegroundColor Green
Write-Host "All unique pixels:" $pixelYears.Count
Write-Host "22-year balanced pixels:" $balancedPixels.Count
Write-Host "Pixels changing subdistrict:" @($unstableSubdistrict).Count

Write-Host ""
Write-Host "================ FULL vs BALANCED =============" -ForegroundColor Green
$annual | Format-Table -AutoSize

Write-Host ""
Write-Host "================ MODIS IMAGE COUNT ============" -ForegroundColor Green
$countSummary | Format-Table -AutoSize

Write-Host ""
Write-Host "Balanced-panel QA complete." -ForegroundColor Green

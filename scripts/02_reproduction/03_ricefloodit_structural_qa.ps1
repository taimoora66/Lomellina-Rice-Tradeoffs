# ============================================================
# RiceFloodIT FAST structural QA
# ============================================================

$ErrorActionPreference = "Stop"

$ffPath = "data\raw\RiceFloodIT\ffavg_2021.csv"
$wsPath = "data\raw\RiceFloodIT\ws_2021.csv"

$docDir = "docs\data"
New-Item -ItemType Directory -Force -Path $docDir | Out-Null

Write-Host ""
Write-Host "FAST RiceFloodIT QA starting..." -ForegroundColor Cyan

# ------------------------------------------------------------
# FFAVG: STREAM THROUGH CSV ONCE
# ------------------------------------------------------------

$ffRows = 0

$yearCounts = @{}
$yearPixels = @{}
$yearSubdistricts = @{}

$pixelYears = @{}
$pixelYearSeen = @{}

$subdistrictSet = @{}

$missingX = 0
$missingY = 0
$missingSub = 0
$missingYear = 0
$missingFF = 0
$missingCount = 0

$duplicatePixelYears = 0

$yearMin = [int]::MaxValue
$yearMax = [int]::MinValue

$ffMin = [double]::PositiveInfinity
$ffMax = [double]::NegativeInfinity
$ffSum = 0.0

$countMin = [int]::MaxValue
$countMax = [int]::MinValue

$xMin = [double]::PositiveInfinity
$xMax = [double]::NegativeInfinity
$yMin = [double]::PositiveInfinity
$yMax = [double]::NegativeInfinity

Write-Host "Reading ffavg_2021.csv..." -ForegroundColor Cyan

Import-Csv $ffPath | ForEach-Object {

    $ffRows++

    if ([string]::IsNullOrWhiteSpace($_.x)) { $missingX++ }
    if ([string]::IsNullOrWhiteSpace($_.y)) { $missingY++ }
    if ([string]::IsNullOrWhiteSpace($_.subdistrict)) { $missingSub++ }
    if ([string]::IsNullOrWhiteSpace($_.year)) { $missingYear++ }
    if ([string]::IsNullOrWhiteSpace($_.ff)) { $missingFF++ }
    if ([string]::IsNullOrWhiteSpace($_.count)) { $missingCount++ }

    if (
        -not [string]::IsNullOrWhiteSpace($_.x) -and
        -not [string]::IsNullOrWhiteSpace($_.y) -and
        -not [string]::IsNullOrWhiteSpace($_.year)
    ) {

        $x = [double]$_.x
        $y = [double]$_.y
        $year = [int]$_.year

        if ($x -lt $xMin) { $xMin = $x }
        if ($x -gt $xMax) { $xMax = $x }

        if ($y -lt $yMin) { $yMin = $y }
        if ($y -gt $yMax) { $yMax = $y }

        if ($year -lt $yearMin) { $yearMin = $year }
        if ($year -gt $yearMax) { $yearMax = $year }

        if (-not $yearCounts.ContainsKey($year)) {
            $yearCounts[$year] = 0
            $yearPixels[$year] = @{}
            $yearSubdistricts[$year] = @{}
        }

        $yearCounts[$year]++

        $pixelKey = "$x|$y"
        $pixelYearKey = "$pixelKey|$year"

        if ($pixelYearSeen.ContainsKey($pixelYearKey)) {
            $duplicatePixelYears++
        }
        else {
            $pixelYearSeen[$pixelYearKey] = $true
        }

        $yearPixels[$year][$pixelKey] = $true

        if (-not $pixelYears.ContainsKey($pixelKey)) {
            $pixelYears[$pixelKey] = @{}
        }

        $pixelYears[$pixelKey][$year] = $true
    }

    if (-not [string]::IsNullOrWhiteSpace($_.subdistrict)) {

        $subdistrict = $_.subdistrict
        $subdistrictSet[$subdistrict] = $true

        if (-not [string]::IsNullOrWhiteSpace($_.year)) {
            $year = [int]$_.year

            if (-not $yearSubdistricts.ContainsKey($year)) {
                $yearSubdistricts[$year] = @{}
            }

            $yearSubdistricts[$year][$subdistrict] = $true
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($_.ff)) {

        $ff = [double]$_.ff

        if ($ff -lt $ffMin) { $ffMin = $ff }
        if ($ff -gt $ffMax) { $ffMax = $ff }

        $ffSum += $ff
    }

    if (-not [string]::IsNullOrWhiteSpace($_.count)) {

        $count = [int]$_.count

        if ($count -lt $countMin) { $countMin = $count }
        if ($count -gt $countMax) { $countMax = $count }
    }

    if (($ffRows % 50000) -eq 0) {
        Write-Host "  processed $ffRows rows..."
    }
}

Write-Host "ffavg complete: $ffRows rows" -ForegroundColor Green

# ------------------------------------------------------------
# WS
# ------------------------------------------------------------

Write-Host ""
Write-Host "Reading ws_2021.csv..." -ForegroundColor Cyan

$ws = Import-Csv $wsPath

$wsDuplicate = @{}
$wsDuplicateCount = 0
$wsSubdistrictSet = @{}

$wsMin = [double]::PositiveInfinity
$wsMax = [double]::NegativeInfinity

foreach ($row in $ws) {

    $key = "$($row.subdistrict)|$($row.year)"

    if ($wsDuplicate.ContainsKey($key)) {
        $wsDuplicateCount++
    }
    else {
        $wsDuplicate[$key] = $true
    }

    $wsSubdistrictSet[$row.subdistrict] = $true

    $v = [double]$row.ws

    if ($v -lt $wsMin) { $wsMin = $v }
    if ($v -gt $wsMax) { $wsMax = $v }
}

# ------------------------------------------------------------
# YEAR COMPLETENESS
# ------------------------------------------------------------

$yearAudit = foreach ($year in 2000..2021) {

    $records = 0
    $pixels = 0
    $subs = ""

    if ($yearCounts.ContainsKey($year)) {
        $records = $yearCounts[$year]
        $pixels = $yearPixels[$year].Count
        $subs = (($yearSubdistricts[$year].Keys | Sort-Object) -join ",")
    }

    $wsRowsYear = @($ws | Where-Object {[int]$_.year -eq $year})

    [PSCustomObject]@{
        year             = $year
        ff_records       = $records
        ff_pixels        = $pixels
        ff_subdistricts  = $subs
        ws_records       = $wsRowsYear.Count
        ws_subdistricts  = (($wsRowsYear.subdistrict | Sort-Object -Unique) -join ",")
    }
}

$yearAudit |
Export-Csv `
"$docDir\RiceFloodIT_year_completeness.csv" `
-NoTypeInformation `
-Encoding UTF8

# ------------------------------------------------------------
# PIXEL COVERAGE DISTRIBUTION
# ------------------------------------------------------------

$coverageCounts = @{}

foreach ($pixelKey in $pixelYears.Keys) {

    $n = $pixelYears[$pixelKey].Count

    if (-not $coverageCounts.ContainsKey($n)) {
        $coverageCounts[$n] = 0
    }

    $coverageCounts[$n]++
}

$coverageSummary = foreach ($n in ($coverageCounts.Keys | Sort-Object {[int]$_})) {

    [PSCustomObject]@{
        n_years = [int]$n
        pixels  = $coverageCounts[$n]
    }
}

$coverageSummary |
Export-Csv `
"$docDir\RiceFloodIT_pixel_coverage_summary.csv" `
-NoTypeInformation `
-Encoding UTF8

# ------------------------------------------------------------
# MAIN SUMMARY
# ------------------------------------------------------------

$summary = [PSCustomObject]@{
    ff_rows                  = $ffRows
    year_min                 = $yearMin
    year_max                 = $yearMax
    number_of_years          = $yearCounts.Count
    unique_pixels            = $pixelYears.Count
    subdistricts             = (($subdistrictSet.Keys | Sort-Object) -join ",")
    ff_min                   = $ffMin
    ff_max                   = $ffMax
    ff_mean                  = [math]::Round(($ffSum / ($ffRows - $missingFF)),6)
    image_count_min          = $countMin
    image_count_max          = $countMax
    x_min                    = $xMin
    x_max                    = $xMax
    y_min                    = $yMin
    y_max                    = $yMax
    duplicate_pixel_years    = $duplicatePixelYears
    missing_x                = $missingX
    missing_y                = $missingY
    missing_subdistrict      = $missingSub
    missing_year             = $missingYear
    missing_ff               = $missingFF
    missing_count            = $missingCount
    ws_rows                  = $ws.Count
    ws_min                   = $wsMin
    ws_max                   = $wsMax
    ws_subdistricts          = (($wsSubdistrictSet.Keys | Sort-Object) -join ",")
    duplicate_ws_year_records = $wsDuplicateCount
}

$summary |
Export-Csv `
"$docDir\RiceFloodIT_fast_QA_summary.csv" `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "================ RICEFLOODIT FAST QA ================" -ForegroundColor Green
$summary | Format-List

Write-Host ""
Write-Host "================ PIXEL TEMPORAL COVERAGE ============" -ForegroundColor Green
$coverageSummary | Format-Table -AutoSize

Write-Host ""
Write-Host "================ YEAR COMPLETENESS ==================" -ForegroundColor Green
$yearAudit | Format-Table -AutoSize

Write-Host ""
Write-Host "FAST QA COMPLETE." -ForegroundColor Green

$ErrorActionPreference = "Stop"

$outDir = "data\interim\MEDWATERICE"
$outFile = Join-Path $outDir "MEDWATERICE_CS1_groundwater_depth_long.csv"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$files = Get-ChildItem `
"data\raw\MEDWATERICE\CS1_Lomellina_2019", `
"data\raw\MEDWATERICE\CS1_Lomellina_2020" `
-Filter "*.xlsx"

$rows = @()

foreach ($file in $files) {

    $name = $file.Name

    if ($name -match "2019") {
        $year = 2019
    }
    elseif ($name -match "2020") {
        $year = 2020
    }
    else {
        continue
    }

    if ($name -match "_AWD_") {
        $treatment = "AWD"
    }
    elseif ($name -match "_DFL_") {
        $treatment = "DFL"
    }
    elseif ($name -match "_WFL_") {
        $treatment = "WFL"
    }
    else {
        continue
    }

    Write-Host ""
    Write-Host "Extracting groundwater: $year $treatment" -ForegroundColor Cyan

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    try {

        $wb = $excel.Workbooks.Open($file.FullName)
        $ws = $wb.Worksheets.Item("Groundwater")

        $used = $ws.UsedRange
        $nRows = $used.Rows.Count
        $nCols = $used.Columns.Count

        # Detect date column
        $dateCol = $null

        for ($c = 1; $c -le $nCols; $c++) {

            $header = $ws.Cells.Item(2,$c).Text.Trim()

            if ($header -match "^(Date|DATE)$") {
                $dateCol = $c
                break
            }
        }

        if ($null -eq $dateCol) {
            throw "Date column not found in $name"
        }

        # Detect groundwater-depth columns from headers
        $depthCols = @()

        for ($c = 1; $c -le $nCols; $c++) {

            $header = $ws.Cells.Item(2,$c).Text.Trim()

            if ($header -match "Depth.*PIEZOMETER\s+P?([0-9]+)") {

                $piezometer = "P" + $matches[1]

                $depthCols += [PSCustomObject]@{
                    column = $c
                    piezometer = $piezometer
                    header = $header
                }
            }
        }

        Write-Host "Depth columns detected: $($depthCols.Count)"

        foreach ($dc in $depthCols) {
            Write-Host "  $($dc.piezometer) -> column $($dc.column)"
        }

        for ($r = 3; $r -le $nRows; $r++) {

            $rawDate = $ws.Cells.Item($r,$dateCol).Value2

            if ($null -eq $rawDate -or "$rawDate".Trim() -eq "") {
                continue
            }

            $date = $null

            if ($rawDate -is [double] -or $rawDate -is [int]) {

                try {
                    $date = [datetime]::FromOADate([double]$rawDate)
                }
                catch {
                    continue
                }

            }
            else {

                $parsed = [datetime]::MinValue

                if ([datetime]::TryParse("$rawDate",[ref]$parsed)) {
                    $date = $parsed
                }
                else {
                    continue
                }
            }

            foreach ($dc in $depthCols) {

                $rawValue = $ws.Cells.Item($r,$dc.column).Value2

                if ($null -eq $rawValue -or "$rawValue".Trim() -eq "") {
                    continue
                }

                $number = 0.0

                if (-not [double]::TryParse(
                    "$rawValue",
                    [System.Globalization.NumberStyles]::Any,
                    [System.Globalization.CultureInfo]::InvariantCulture,
                    [ref]$number
                )) {
                    continue
                }

                $rows += [PSCustomObject]@{
                    year = $year
                    treatment = $treatment
                    date = $date.ToString("yyyy-MM-dd")
                    piezometer = $dc.piezometer
                    groundwater_depth_cm = $number
                    source_header = $dc.header
                    source_workbook = $name
                    source_sheet = "Groundwater"
                    source_row = $r
                }
            }
        }

        $wb.Close($false)
    }
    finally {

        $excel.Quit()

        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) |
            Out-Null

        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

$rows |
Sort-Object year,treatment,piezometer,date |
Export-Csv `
$outFile `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "Groundwater extraction complete." -ForegroundColor Green
Write-Host "Rows extracted: $($rows.Count)"
Write-Host "Output: $outFile"

$rows |
Group-Object year,treatment,piezometer |
Select-Object Name,Count |
Format-Table -AutoSize

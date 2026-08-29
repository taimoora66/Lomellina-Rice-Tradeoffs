# ============================================================
# MEDWATERICE CS1 — STANDARDISED DAILY HYDROLOGY EXTRACTION
# Corrected semantic version
#
# IMPORTANT:
# 2019 contains Perc_MODEL.
# 2020 contains Perc_MODEL_havier_soil_zone instead.
# These are stored in separate variables and MUST NOT be pooled.
# ============================================================

$ErrorActionPreference = "Stop"

$outDir = "data\interim\MEDWATERICE"
$outFile = Join-Path $outDir "MEDWATERICE_CS1_hydrology_daily.csv"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$datasets = @(

    @{
        year=2019; treatment="WFL"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_WFL_2019.xlsx"
        map=@{
            date=1; das=2; qin=3; qout=4; hlev=5; rain=6; et=7
            deltaL=8; deltaS=9; percBal=10
            qnet=$null
            percModel=11
            percModelHeavy=$null
        }
    },

    @{
        year=2019; treatment="DFL"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_DFL_2019.xlsx"
        map=@{
            date=1; das=2; qin=3; qout=4; hlev=5; rain=6; et=7
            deltaL=8; deltaS=9; percBal=10
            qnet=$null
            percModel=11
            percModelHeavy=$null
        }
    },

    @{
        year=2019; treatment="AWD"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_AWD_2019.xlsx"
        map=@{
            date=1; das=2; qin=3; qout=4; hlev=5; rain=6; et=7
            deltaL=8; deltaS=9; percBal=10
            qnet=$null
            percModel=11
            percModelHeavy=$null
        }
    },

    @{
        year=2020; treatment="WFL"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_WFL_2020_03_12_2021.xlsx"
        map=@{
            date=1; das=$null; qin=2; qout=3; hlev=4; rain=5; et=6
            deltaL=7; deltaS=8; percBal=9
            qnet=10
            percModel=$null
            percModelHeavy=11
        }
    },

    @{
        year=2020; treatment="DFL"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_DFL_2020_03_12_2021.xlsx"
        map=@{
            date=1; das=2; qin=3; qout=4; hlev=5; rain=6; et=7
            deltaL=8; deltaS=9; percBal=10
            qnet=11
            percModel=$null
            percModelHeavy=12
        }
    },

    @{
        year=2020; treatment="AWD"
        file="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_AWD_2020_03_12_2021.xlsx"
        map=@{
            date=1; das=2; qin=3; qout=4; hlev=5; rain=6; et=7
            deltaL=8; deltaS=9; percBal=10
            qnet=11
            percModel=$null
            percModelHeavy=12
        }
    }
)


function Get-Value {
    param($Sheet,[int]$Row,$Column)

    if ($null -eq $Column) {
        return $null
    }

    $v = $Sheet.Cells.Item($Row,$Column).Value2

    if ($null -eq $v -or "$v".Trim() -eq "") {
        return $null
    }

    return $v
}


function Get-Numeric {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $number = 0.0

    if ([double]::TryParse(
        "$Value",
        [System.Globalization.NumberStyles]::Any,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$number
    )) {
        return $number
    }

    return $null
}


$rows = @()


foreach ($d in $datasets) {

    Write-Host ""
    Write-Host "Extracting $($d.year) $($d.treatment)..." -ForegroundColor Cyan

    if (-not (Test-Path $d.file)) {
        throw "Workbook missing: $($d.file)"
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    try {

        $wb = $excel.Workbooks.Open((Resolve-Path $d.file))
        $sheet = $wb.Worksheets.Item("Other water")

        $lastRow = $sheet.UsedRange.Rows.Count

        for ($r = 3; $r -le $lastRow; $r++) {

            $rawDate = Get-Value $sheet $r $d.map.date

            if ($null -eq $rawDate) {
                continue
            }

            if ($rawDate -is [double] -or $rawDate -is [int]) {

                try {
                    $date = [datetime]::FromOADate([double]$rawDate)
                }
                catch {
                    continue
                }

            } else {

                $parsed = [datetime]::MinValue

                if (-not [datetime]::TryParse("$rawDate",[ref]$parsed)) {
                    continue
                }

                $date = $parsed
            }

            if ($date.Year -ne $d.year) {
                continue
            }

            $qin  = Get-Numeric (Get-Value $sheet $r $d.map.qin)
            $qout = Get-Numeric (Get-Value $sheet $r $d.map.qout)

            $qnetCalc = $null

            if ($null -ne $qin -and $null -ne $qout) {
                $qnetCalc = $qin - $qout
            }

            $rows += [PSCustomObject]@{

                year = $d.year
                treatment = $d.treatment
                date = $date.ToString("yyyy-MM-dd")

                days_after_sowing =
                    Get-Numeric (Get-Value $sheet $r $d.map.das)

                irrigation_inflow_mm = $qin
                irrigation_outflow_mm = $qout

                net_irrigation_calculated_mm = $qnetCalc

                net_irrigation_reported_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.qnet)

                ponding_level_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.hlev)

                rainfall_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.rain)

                etc_adjusted_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.et)

                delta_ponding_storage_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.deltaL)

                delta_soil_storage_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.deltaS)

                percolation_balance_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.percBal)

                percolation_model_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.percModel)

                percolation_model_heavy_soil_zone_mm =
                    Get-Numeric (Get-Value $sheet $r $d.map.percModelHeavy)

                source_workbook = Split-Path $d.file -Leaf
                source_sheet = "Other water"
                source_row = $r
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
Sort-Object year,treatment,date |
Export-Csv `
    $outFile `
    -NoTypeInformation `
    -Encoding UTF8


Write-Host ""
Write-Host "Corrected extraction complete." -ForegroundColor Green
Write-Host "Rows extracted: $($rows.Count)"
Write-Host "Output: $outFile"

$rows |
Group-Object year,treatment |
Select-Object Name,Count |
Format-Table -AutoSize

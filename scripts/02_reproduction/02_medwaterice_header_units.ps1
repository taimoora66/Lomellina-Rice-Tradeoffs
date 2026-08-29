# ============================================================
# MEDWATERICE CS1 HEADER / UNIT INSPECTION
# ============================================================

$ErrorActionPreference = "Stop"

$files = @(
    @{year=2019; treatment="WFL"; path="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_WFL_2019.xlsx"},
    @{year=2019; treatment="DFL"; path="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_DFL_2019.xlsx"},
    @{year=2019; treatment="AWD"; path="data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_AWD_2019.xlsx"},
    @{year=2020; treatment="WFL"; path="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_WFL_2020_03_12_2021.xlsx"},
    @{year=2020; treatment="DFL"; path="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_DFL_2020_03_12_2021.xlsx"},
    @{year=2020; treatment="AWD"; path="data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_AWD_2020_03_12_2021.xlsx"}
)

$sheetsToInspect = @(
    "General",
    "Groundwater",
    "Irrig",
    "Other water",
    "Crop evol",
    "Yield+product",
    "Gas emiss",
    "Managem oper"
)

$out = @()

foreach ($item in $files) {

    Write-Host ""
    Write-Host "$($item.year) $($item.treatment)" -ForegroundColor Cyan

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    try {

        $wb = $excel.Workbooks.Open((Resolve-Path $item.path))

        foreach ($sheetName in $sheetsToInspect) {

            $sheet = $wb.Worksheets.Item($sheetName)

            $maxRows = [Math]::Min(15, $sheet.UsedRange.Rows.Count)
            $maxCols = [Math]::Min(60, $sheet.UsedRange.Columns.Count)

            for ($r = 1; $r -le $maxRows; $r++) {

                for ($c = 1; $c -le $maxCols; $c++) {

                    $text = $sheet.Cells.Item($r,$c).Text

                    if (-not [string]::IsNullOrWhiteSpace($text)) {

                        $out += [PSCustomObject]@{
                            year      = $item.year
                            treatment = $item.treatment
                            sheet     = $sheetName
                            row       = $r
                            column    = $c
                            cell      = $sheet.Cells.Item($r,$c).Address($false,$false)
                            text      = $text
                        }
                    }
                }
            }
        }

        $wb.Close($false)
    }
    finally {

        $excel.Quit()

        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null

        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

$out |
Export-Csv `
"docs\data\MEDWATERICE_CS1_header_unit_inventory.csv" `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "Header/unit inventory complete." -ForegroundColor Green
Write-Host "Rows extracted: $($out.Count)"

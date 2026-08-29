# ============================================================
# MEDWATERICE CS1 WORKBOOK STRUCTURAL QA
# ============================================================

$ErrorActionPreference = "Stop"

$files = @(
    "data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_WFL_2019.xlsx",
    "data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_DFL_2019.xlsx",
    "data\raw\MEDWATERICE\CS1_Lomellina_2019\MEDWATERICE DMP_CS1_ITALY_AWD_2019.xlsx",
    "data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_WFL_2020_03_12_2021.xlsx",
    "data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_DFL_2020_03_12_2021.xlsx",
    "data\raw\MEDWATERICE\CS1_Lomellina_2020\MEDWATERICE DMP_CS1_ITALY_AWD_2020_03_12_2021.xlsx"
)

$results = @()

foreach ($file in $files) {

    if (-not (Test-Path $file)) {
        throw "Missing workbook: $file"
    }

    Write-Host ""
    Write-Host "Inspecting: $file" -ForegroundColor Cyan

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    try {
        $wb = $excel.Workbooks.Open((Resolve-Path $file))

        foreach ($sheet in $wb.Worksheets) {

            $used = $sheet.UsedRange

            $rows = $used.Rows.Count
            $cols = $used.Columns.Count

            $headers = @()

            for ($c = 1; $c -le $cols; $c++) {
                $value = $sheet.Cells.Item(1,$c).Text
                if ($value) {
                    $headers += $value
                }
            }

            $results += [PSCustomObject]@{
                workbook = Split-Path $file -Leaf
                sheet = $sheet.Name
                used_rows = $rows
                used_columns = $cols
                first_row_headers = ($headers -join " | ")
            }
        }

        $wb.Close($false)
    }
    finally {
        $excel.Quit()

        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null

        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

$results |
Export-Csv `
    "docs\data\MEDWATERICE_CS1_workbook_structure.csv" `
    -NoTypeInformation `
    -Encoding UTF8

Write-Host ""
Write-Host "Workbook structural QA complete." -ForegroundColor Green

$results |
Format-Table workbook,sheet,used_rows,used_columns -AutoSize

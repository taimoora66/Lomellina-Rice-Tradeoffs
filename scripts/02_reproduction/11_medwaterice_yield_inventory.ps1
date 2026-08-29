$ErrorActionPreference = "Stop"

$files = Get-ChildItem `
"data\raw\MEDWATERICE\CS1_Lomellina_2019", `
"data\raw\MEDWATERICE\CS1_Lomellina_2020" `
-Filter "*.xlsx"

$outFile = "outputs\diagnostics\MEDWATERICE_yield_sheet_inventory.csv"

$records = @()

foreach ($file in $files) {

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host $file.Name -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Cyan

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    try {

        $wb = $excel.Workbooks.Open($file.FullName)

        $sheetNames = @()

        foreach ($sheet in $wb.Worksheets) {
            $sheetNames += $sheet.Name
        }

        $target = $null

        foreach ($candidate in @(
            "Yield+product",
            "Yield + product",
            "Yield",
            "Yield product"
        )) {
            if ($sheetNames -contains $candidate) {
                $target = $candidate
                break
            }
        }

        if ($null -eq $target) {
            Write-Host "Yield sheet not found." -ForegroundColor Red
            $wb.Close($false)
            continue
        }

        $ws = $wb.Worksheets.Item($target)
        $used = $ws.UsedRange

        $nRows = $used.Rows.Count
        $nCols = $used.Columns.Count

        Write-Host "Sheet: $target"
        Write-Host "Used rows: $nRows"
        Write-Host "Used cols: $nCols"

        Write-Host ""
        Write-Host "NON-EMPTY CELLS, FIRST 30 ROWS" -ForegroundColor Green

        for ($r = 1; $r -le [Math]::Min($nRows,30); $r++) {

            $rowText = ""

            for ($c = 1; $c -le $nCols; $c++) {

                $cell = $ws.Cells.Item($r,$c)
                $v = $cell.Text

                if ($v -ne "") {

                    $rowText += " | C$c=$v"

                    $records += [PSCustomObject]@{
                        workbook = $file.Name
                        sheet = $target
                        row = $r
                        column = $c
                        displayed_value = $v
                        raw_value = $cell.Value2
                        formula = $cell.Formula
                        number_format = $cell.NumberFormat
                    }
                }
            }

            if ($rowText -ne "") {
                Write-Host "ROW $r$rowText"
            }
        }

        Write-Host ""
        Write-Host "KEY TERM MATCHES" -ForegroundColor Green

        for ($r = 1; $r -le $nRows; $r++) {

            $rowText = ""

            for ($c = 1; $c -le $nCols; $c++) {

                $v = $ws.Cells.Item($r,$c).Text

                if ($v -ne "") {
                    $rowText += " | C$c=$v"
                }
            }

            if (
                $rowText -match "yield|grain|14%|humidity|plot|subplot|replicate|fertiliz|fungic|herbic|harvest|production|t/ha|kg|area"
            ) {
                Write-Host "ROW $r$rowText"
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

$records |
Export-Csv `
$outFile `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "Yield inventory complete." -ForegroundColor Green
Write-Host "Saved: $outFile"

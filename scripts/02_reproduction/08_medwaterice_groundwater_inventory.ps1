$ErrorActionPreference = "Stop"

$files = Get-ChildItem `
"data\raw\MEDWATERICE\CS1_Lomellina_2019", `
"data\raw\MEDWATERICE\CS1_Lomellina_2020" `
-Filter "*.xlsx"

$outDir = "outputs\diagnostics"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$rows = @()

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
        $ws = $wb.Worksheets.Item("Groundwater")
        $used = $ws.UsedRange

        $nRows = $used.Rows.Count
        $nCols = $used.Columns.Count

        Write-Host "Used rows: $nRows"
        Write-Host "Used cols: $nCols"

        Write-Host ""
        Write-Host "ROW 1:" -ForegroundColor Green

        for ($c = 1; $c -le $nCols; $c++) {
            $v = $ws.Cells.Item(1,$c).Text
            if ($v -ne "") {
                Write-Host ("C{0}: {1}" -f $c,$v)
            }
        }

        Write-Host ""
        Write-Host "ROW 2:" -ForegroundColor Green

        for ($c = 1; $c -le $nCols; $c++) {
            $v = $ws.Cells.Item(2,$c).Text
            if ($v -ne "") {
                Write-Host ("C{0}: {1}" -f $c,$v)
            }
        }

        Write-Host ""
        Write-Host "TEXT / NOTES MATCHES:" -ForegroundColor Green

        for ($r = 1; $r -le [Math]::Min($nRows,40); $r++) {
            for ($c = 1; $c -le $nCols; $c++) {

                $v = $ws.Cells.Item($r,$c).Text

                if (
                    $v -match "piez|ground|water table|depth|head|level|m a.s.l|m asl|meter|surface|soil|sensor|manual|automatic|position|distance|datum"
                ) {
                    Write-Host ("R{0}C{1}: {2}" -f $r,$c,$v)
                }
            }
        }

        # Save first 15 rows / all columns for later audit
        for ($r = 1; $r -le [Math]::Min($nRows,15); $r++) {

            for ($c = 1; $c -le $nCols; $c++) {

                $v = $ws.Cells.Item($r,$c).Text

                if ($v -ne "") {

                    $rows += [PSCustomObject]@{
                        workbook = $file.Name
                        sheet = "Groundwater"
                        row = $r
                        column = $c
                        value = $v
                    }
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
Export-Csv `
"outputs\diagnostics\MEDWATERICE_groundwater_sheet_inventory.csv" `
-NoTypeInformation `
-Encoding UTF8

Write-Host ""
Write-Host "Groundwater inventory complete." -ForegroundColor Green
Write-Host "Saved: outputs\diagnostics\MEDWATERICE_groundwater_sheet_inventory.csv"

# ============================================================
# RiceFloodIT Zenodo metadata + file inventory
# Record: 4313730
# DOI: 10.5281/zenodo.4313730
# ============================================================

$ErrorActionPreference = "Stop"

$recordId = "4313730"
$apiUrl   = "https://zenodo.org/api/records/$recordId"

$outMeta = "outputs\diagnostics\RiceFloodIT_zenodo_record.json"
$outCsv  = "docs\data\RiceFloodIT_file_inventory.csv"

New-Item -ItemType Directory -Force -Path "outputs\diagnostics" | Out-Null
New-Item -ItemType Directory -Force -Path "docs\data" | Out-Null

Write-Host "Querying Zenodo record $recordId ..." -ForegroundColor Cyan

$record = Invoke-RestMethod -Uri $apiUrl -Method Get

$record |
ConvertTo-Json -Depth 20 |
Set-Content $outMeta -Encoding UTF8

Write-Host ""
Write-Host "Title: $($record.metadata.title)" -ForegroundColor Green
Write-Host "DOI:   $($record.doi)"
Write-Host "Version: $($record.metadata.version)"
Write-Host "Published: $($record.created)"
Write-Host "Files: $($record.files.Count)"

$rows = foreach ($file in $record.files) {

    $checksumType = ""
    $checksumValue = ""

    if ($file.checksum -match "^([^:]+):(.+)$") {
        $checksumType  = $Matches[1]
        $checksumValue = $Matches[2]
    }

    [PSCustomObject]@{
        record_id       = $recordId
        doi             = $record.doi
        concept_doi     = $record.conceptdoi
        dataset_title   = $record.metadata.title
        version         = $record.metadata.version
        filename        = $file.key
        size_bytes      = $file.size
        checksum_type   = $checksumType
        checksum_value  = $checksumValue
        download_url    = $file.links.self
    }
}

$rows |
Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "RiceFloodIT inventory complete." -ForegroundColor Green
Write-Host ""
$rows |
Format-Table filename,size_bytes,checksum_type -AutoSize

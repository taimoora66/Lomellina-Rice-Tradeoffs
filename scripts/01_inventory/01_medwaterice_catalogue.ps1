# ============================================================
# MEDWATERICE DATASET INVENTORY
# Project: Lomellina Rice-Water Trade-offs
# Purpose: Query UNIMI Dataverse and export dataset catalogue
# ============================================================

$ErrorActionPreference = "Stop"

$BaseUrl = "https://dataverse.unimi.it"
$DataverseAlias = "MEDWATERICE"

$OutputDir = "outputs\diagnostics"
$InventoryDir = "docs\data"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $InventoryDir | Out-Null

Write-Host ""
Write-Host "Querying MEDWATERICE Dataverse..." -ForegroundColor Cyan

$SearchUrl = "$BaseUrl/api/search?q=*&type=dataset&subtree=$DataverseAlias&per_page=100"

$response = Invoke-RestMethod `
    -Uri $SearchUrl `
    -Method Get `
    -Headers @{Accept="application/json"}

if ($response.status -ne "OK") {
    throw "Dataverse API returned status: $($response.status)"
}

$items = $response.data.items

Write-Host "Datasets returned: $($items.Count)" -ForegroundColor Green

# Save raw API response for provenance
$response |
    ConvertTo-Json -Depth 20 |
    Set-Content `
        "$OutputDir\MEDWATERICE_search_api_raw.json" `
        -Encoding UTF8

# Build simplified inventory
$inventory = foreach ($item in $items) {

    [PSCustomObject]@{
        dataset_title     = $item.name
        persistent_id     = $item.global_id
        url               = $item.url
        publication_date  = $item.published_at
        description       = $item.description
        authors           = ($item.authors -join "; ")
        subjects          = ($item.subjects -join "; ")
        type              = $item.type
    }
}

$inventory |
    Sort-Object publication_date |
    Export-Csv `
        "$InventoryDir\MEDWATERICE_catalogue.csv" `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host ""
Write-Host "Created:" -ForegroundColor Cyan
Write-Host "  docs\data\MEDWATERICE_catalogue.csv"
Write-Host "  outputs\diagnostics\MEDWATERICE_search_api_raw.json"

Write-Host ""
Write-Host "Catalogue preview:" -ForegroundColor Cyan

$inventory |
    Select-Object dataset_title,persistent_id,publication_date |
    Format-Table -AutoSize

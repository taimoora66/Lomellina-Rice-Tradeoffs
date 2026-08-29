# ============================================================
# MEDWATERICE METADATA ENRICHMENT
# Project: Lomellina Rice-Water Trade-offs
# Purpose:
#   Query dataset-level metadata for every MEDWATERICE dataset
#   and create a detailed catalogue for relevance screening.
# ============================================================

$ErrorActionPreference = "Stop"

$BaseUrl = "https://dataverse.unimi.it"

$InputCatalogue = "docs\data\MEDWATERICE_catalogue.csv"
$OutputCatalogue = "docs\data\MEDWATERICE_catalogue_enriched.csv"
$FileInventory = "docs\data\MEDWATERICE_file_inventory.csv"
$RawDir = "outputs\diagnostics\medwaterice_metadata"

New-Item -ItemType Directory -Force -Path $RawDir | Out-Null

if (-not (Test-Path $InputCatalogue)) {
    throw "Missing catalogue: $InputCatalogue"
}

$datasets = Import-Csv $InputCatalogue

Write-Host ""
Write-Host "MEDWATERICE datasets to inspect: $($datasets.Count)" -ForegroundColor Cyan
Write-Host ""

function Get-MetadataField {
    param(
        $Fields,
        [string]$Name
    )

    $field = $Fields | Where-Object { $_.typeName -eq $Name } | Select-Object -First 1

    if ($null -eq $field) {
        return ""
    }

    $value = $field.value

    if ($value -is [string]) {
        return $value
    }

    try {
        return ($value | ConvertTo-Json -Depth 10 -Compress)
    }
    catch {
        return "$value"
    }
}

$enriched = @()
$fileRows = @()

$i = 0

foreach ($dataset in $datasets) {

    $i++

    $persistentId = $dataset.persistent_id

    Write-Host "[$i/$($datasets.Count)] $persistentId" -ForegroundColor Yellow

    $encodedPid = [System.Uri]::EscapeDataString($persistentId)

    $url = "$BaseUrl/api/datasets/:persistentId/?persistentId=$encodedPid"

    try {
        $response = Invoke-RestMethod `
            -Uri $url `
            -Method Get `
            -Headers @{Accept="application/json"}

        if ($response.status -ne "OK") {
            throw "API status: $($response.status)"
        }

        $response |
            ConvertTo-Json -Depth 30 |
            Set-Content `
                "$RawDir\$($persistentId.Replace(':','_').Replace('/','_')).json" `
                -Encoding UTF8

        $latest = $response.data.latestVersion

        $citationBlock = $latest.metadataBlocks.citation

        $fields = $citationBlock.fields

        $title = Get-MetadataField $fields "title"
        $authorRaw = Get-MetadataField $fields "author"
        $descriptionRaw = Get-MetadataField $fields "dsDescription"
        $subjectRaw = Get-MetadataField $fields "subject"
        $keywordRaw = Get-MetadataField $fields "keyword"
        $geoRaw = Get-MetadataField $fields "geographicCoverage"
        $producerRaw = Get-MetadataField $fields "producer"
        $grantRaw = Get-MetadataField $fields "grantNumber"
        $relatedRaw = Get-MetadataField $fields "relatedMaterial"
        $publicationRaw = Get-MetadataField $fields "publication"

        $files = $latest.files

        $enriched += [PSCustomObject]@{
            persistent_id       = $persistentId
            title               = $title
            version             = "$($latest.versionNumber).$($latest.versionMinorNumber)"
            version_state       = $latest.versionState
            publication_date    = $latest.releaseTime
            authors_raw         = $authorRaw
            descriptions_raw    = $descriptionRaw
            subjects_raw        = $subjectRaw
            keywords_raw        = $keywordRaw
            geography_raw       = $geoRaw
            producers_raw       = $producerRaw
            grants_raw          = $grantRaw
            related_material    = $relatedRaw
            publications_raw    = $publicationRaw
            file_count          = @($files).Count
            terms_of_use        = $latest.termsOfUse
        }

        foreach ($f in $files) {

            $df = $f.dataFile

            $fileRows += [PSCustomObject]@{
                persistent_id     = $persistentId
                dataset_title     = $title
                file_id           = $df.id
                filename          = $df.filename
                content_type      = $df.contentType
                filesize_bytes    = $df.filesize
                checksum_type     = $df.checksum.type
                checksum_value    = $df.checksum.value
                description       = $f.description
                directory_label   = $f.directoryLabel
                restricted        = $f.restricted
            }
        }
    }
    catch {

        Write-Warning "Failed: $persistentId"
        Write-Warning $_.Exception.Message

        $enriched += [PSCustomObject]@{
            persistent_id       = $persistentId
            title               = $dataset.dataset_title
            version             = ""
            version_state       = ""
            publication_date    = ""
            authors_raw         = ""
            descriptions_raw    = ""
            subjects_raw        = ""
            keywords_raw        = ""
            geography_raw       = ""
            producers_raw       = ""
            grants_raw          = ""
            related_material    = ""
            publications_raw    = ""
            file_count          = ""
            terms_of_use        = ""
        }
    }
}

$enriched |
    Export-Csv `
        $OutputCatalogue `
        -NoTypeInformation `
        -Encoding UTF8

$fileRows |
    Export-Csv `
        $FileInventory `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host ""
Write-Host "Metadata enrichment complete." -ForegroundColor Green
Write-Host ""
Write-Host "Created:"
Write-Host "  $OutputCatalogue"
Write-Host "  $FileInventory"
Write-Host "  $RawDir"
Write-Host ""

Write-Host "Dataset summary:" -ForegroundColor Cyan

$enriched |
    Select-Object persistent_id,title,file_count,version |
    Format-Table -Wrap -AutoSize



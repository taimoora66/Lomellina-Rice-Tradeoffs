$ErrorActionPreference = "Stop"

$BaseUrl = "https://dataverse.unimi.it"
$Manifest = "docs\data\MEDWATERICE_priorityA_download_manifest.csv"
$Root = "data\raw\MEDWATERICE"

if (-not (Test-Path $Manifest)) {
    throw "Manifest not found: $Manifest"
}

$rows = Import-Csv $Manifest

Write-Host "Files in manifest: $($rows.Count)" -ForegroundColor Cyan

foreach ($row in $rows) {

    switch ($row.persistent_id) {
        "doi:10.13130/RD_UNIMI/LQAFO9" { $yearFolder = "CS1_Lomellina_2019" }
        "doi:10.13130/RD_UNIMI/OZSVBI" { $yearFolder = "CS1_Lomellina_2020" }
        "doi:10.13130/RD_UNIMI/UE2OA1" { $yearFolder = "CS1_Brandezzata_2021" }
        default { throw "Unexpected dataset: $($row.persistent_id)" }
    }

    $targetDir = Join-Path $Root $yearFolder
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $targetFile = Join-Path $targetDir $row.filename
    $url = "$BaseUrl/api/access/datafile/$($row.file_id)"

    Write-Host ""
    Write-Host "Downloading: $($row.filename)" -ForegroundColor Cyan

    Invoke-WebRequest `
        -Uri $url `
        -OutFile $targetFile

    if (-not (Test-Path $targetFile)) {
        throw "Download failed: $targetFile"
    }

    $actualSize = (Get-Item $targetFile).Length

    if ($row.filesize_bytes) {
        $expectedSize = [int64]$row.filesize_bytes

        if ($actualSize -ne $expectedSize) {
            throw "Size mismatch for $($row.filename). Expected $expectedSize bytes, got $actualSize."
        }
    }

    Write-Host "  size OK" -ForegroundColor Green

    if ($row.checksum_value) {

        $algorithm = switch -Regex ($row.checksum_type) {
            "^MD5$"     { "MD5" }
            "^SHA-1$"   { "SHA1" }
            "^SHA1$"    { "SHA1" }
            "^SHA-256$" { "SHA256" }
            "^SHA256$"  { "SHA256" }
            default     { $null }
        }

        if ($algorithm) {

            $actualHash = (
                Get-FileHash `
                    -Path $targetFile `
                    -Algorithm $algorithm
            ).Hash.ToLower()

            $expectedHash = $row.checksum_value.ToLower()

            if ($actualHash -ne $expectedHash) {
                throw "Checksum mismatch: $($row.filename)"
            }

            Write-Host "  checksum OK ($algorithm)" -ForegroundColor Green
        }
        else {
            Write-Host "  checksum type not supported automatically: $($row.checksum_type)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Priority-A MEDWATERICE download complete." -ForegroundColor Green

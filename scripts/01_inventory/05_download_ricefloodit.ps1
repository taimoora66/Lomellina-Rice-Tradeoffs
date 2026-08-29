# ============================================================
# RiceFloodIT verified download
# DOI: 10.5281/zenodo.4313730
# ============================================================

$ErrorActionPreference = "Stop"

$manifest = "docs\data\RiceFloodIT_file_inventory.csv"
$targetDir = "data\raw\RiceFloodIT"

if (-not (Test-Path $manifest)) {
    throw "Inventory not found: $manifest"
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$files = Import-Csv $manifest

Write-Host "Files to download: $($files.Count)" -ForegroundColor Cyan

foreach ($file in $files) {

    $target = Join-Path $targetDir $file.filename

    Write-Host ""
    Write-Host "Downloading: $($file.filename)" -ForegroundColor Cyan

    Invoke-WebRequest `
        -Uri $file.download_url `
        -OutFile $target

    if (-not (Test-Path $target)) {
        throw "Download failed: $target"
    }

    $actualSize = (Get-Item $target).Length
    $expectedSize = [int64]$file.size_bytes

    if ($actualSize -ne $expectedSize) {
        throw "Size mismatch for $($file.filename): expected $expectedSize, got $actualSize"
    }

    Write-Host "  size OK" -ForegroundColor Green

    if ($file.checksum_type -eq "md5") {

        $actualHash = (
            Get-FileHash `
                -Path $target `
                -Algorithm MD5
        ).Hash.ToLower()

        $expectedHash = $file.checksum_value.ToLower()

        if ($actualHash -ne $expectedHash) {
            throw "Checksum mismatch: $($file.filename)"
        }

        Write-Host "  checksum OK (MD5)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "RiceFloodIT download complete." -ForegroundColor Green

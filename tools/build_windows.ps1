<#
.SYNOPSIS
    Build the Junction Windows onedir distribution with PyInstaller.

.DESCRIPTION
    Produces dist\Junction\Junction.exe, optional release ZIP, and SHA-256 checksum.
    Run from the repository root:

        .\tools\build_windows.ps1
        .\tools\build_windows.ps1 -Clean
        .\tools\build_windows.ps1 -SkipZip

.PARAMETER Clean
    Remove designated build\ and dist\Junction output before building.

.PARAMETER SkipZip
    Build the onedir folder only; skip ZIP and checksum generation.
#>
[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "packaging\Junction.spec"
$DistDir = Join-Path $Root "dist\Junction"
$ExePath = Join-Path $DistDir "Junction.exe"
$ReleaseDir = Join-Path $Root "release"
$Version = "0.1.0"
$ZipName = "Junction-v$Version-windows-x64.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName
$ChecksumPath = "$ZipPath.sha256"

Write-Step "Validating environment"
if (-not (Test-Path $Python)) {
    throw "Virtual environment interpreter not found: $Python"
}
if (-not (Test-Path $Spec)) {
    throw "PyInstaller spec not found: $Spec"
}

& $Python --version
$pyVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pyVersion -ne "3.13") {
    throw "Expected Python 3.13 in .venv, found $pyVersion"
}

& $Python -c "import PyInstaller; print(f'PyInstaller {PyInstaller.__version__}')"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
}

& $Python -c "import fileforge; print(f'fileforge {fileforge.__version__} / {fileforge.__app_name__}')"
if ($LASTEXITCODE -ne 0) {
    throw "fileforge package is not importable. Install with: .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
}

if ($Clean) {
    Write-Step "Cleaning designated build outputs"
    $targets = @(
        (Join-Path $Root "build"),
        (Join-Path $Root "dist\Junction")
    )
    foreach ($target in $targets) {
        if (Test-Path $target) {
            Write-Host "Removing $target"
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

Write-Step "Running PyInstaller"
& $Python -m PyInstaller --noconfirm --clean --distpath (Join-Path $Root "dist") --workpath (Join-Path $Root "build") $Spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $ExePath)) {
    throw "Expected executable was not created: $ExePath"
}

Write-Host "Built: $ExePath"
Get-Item $ExePath | Format-List FullName, Length, LastWriteTime

$LicenseSrc = Join-Path $Root "LICENSE"
if (Test-Path $LicenseSrc) {
    Copy-Item -LiteralPath $LicenseSrc -Destination (Join-Path $DistDir "LICENSE") -Force
    Write-Host "Copied LICENSE into distribution folder."
}

if ($SkipZip) {
    Write-Step "Skipping ZIP (-SkipZip)"
    Write-Host "Onedir output: $DistDir"
    exit 0
}

Write-Step "Creating portable ZIP"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
if (Test-Path $ChecksumPath) {
    Remove-Item -LiteralPath $ChecksumPath -Force
}

# Brief pause avoids occasional file locks from Defender scanning the fresh build.
Start-Sleep -Seconds 2

# Compress the Junction folder so extract yields Junction\Junction.exe.
# Prefer .NET ZipFile for reliability over Compress-Archive on large trees.
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $DistDir,
    $ZipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $true
)
if (-not (Test-Path $ZipPath)) {
    throw "ZIP was not created: $ZipPath"
}

Write-Step "Computing SHA-256"
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
$checksumBody = @"
$hash  $ZipName
"@
Set-Content -LiteralPath $ChecksumPath -Value $checksumBody -Encoding ascii

$zipSize = (Get-Item $ZipPath).Length
Write-Host "ZIP: $ZipPath"
Write-Host ("Size: {0:N0} bytes ({1:N1} MB)" -f $zipSize, ($zipSize / 1MB))
Write-Host "SHA-256: $hash"
Write-Host "Checksum file: $ChecksumPath"
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green

# MedSearch — build MedSearch.exe and the Windows installer (Setup).
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
#
# Needs a Python with requirements.txt and PyInstaller installed (-Python names
# it; default: python), and Inno Setup 6. Writes, in the MedSearch folder:
#   dist\MedSearch\MedSearch.exe
#   dist\MedSearch-<version>-Setup.exe
param([string]$Python = "python")
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\MedSearch.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

# Inno Setup's compiler: on the PATH, or where its installer puts it.
$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
foreach ($Candidate in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                         "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                         "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
  if (-not $Iscc -and (Test-Path $Candidate)) { $Iscc = $Candidate }
}
if (-not $Iscc) { throw "Inno Setup 6 (ISCC.exe) was not found" }

& $Iscc /Q packaging\MedSearch.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed ($LASTEXITCODE)" }

$Version = (Get-Content VERSION -Raw).Trim()
Write-Host "Built dist\MedSearch-$Version-Setup.exe"

param(
  [string]$VenvPath   = ".\venv",
  [string]$AppName    = "SRE_Applications_Cockpit",
  [string]$IconPath   = ".\sap_sre_icon.ico",
  [string]$ReleaseDir = ".\release_alpha"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Get-Location).Path
$ReleaseDirAbs = (Resolve-Path $ReleaseDir).Path

# ----------------------------
# Paths (project)
# ----------------------------
$AppsSrcDir       = Join-Path $ProjectRoot "applications"
$BannerSrc        = Join-Path $ProjectRoot "banner.txt"
$CockpitReqSrc    = Join-Path $ProjectRoot "cockpit-requirements.txt"
$LauncherStateSrc = Join-Path $ProjectRoot "launcher_state.json"

# ----------------------------
# Paths (release)
# ----------------------------
$AppsDstDir       = Join-Path $ReleaseDirAbs "applications"
$BannerDst        = Join-Path $ReleaseDirAbs "banner.txt"
$CockpitReqDst    = Join-Path $ReleaseDirAbs "cockpit-requirements.txt"
$LauncherStateDst = Join-Path $ReleaseDirAbs "launcher_state.json"
$ExeDst           = Join-Path $ReleaseDirAbs "$AppName.exe"

# ----------------------------
# Ensure release folders exist
# ----------------------------
New-Item -ItemType Directory -Force -Path $ReleaseDirAbs | Out-Null
New-Item -ItemType Directory -Force -Path $AppsDstDir   | Out-Null

# ----------------------------
# Create defaults ONLY if missing
# ----------------------------
if (-not (Test-Path $BannerSrc)) {
@"
SRE Applications Cockpit
- Drop shortcuts, EXEs, folders, or URLs into ./applications
- Use Load from Git to pull public GitHub repos (with root main.py)
"@ | Set-Content -Encoding UTF8 $BannerSrc
}

if (-not (Test-Path $CockpitReqSrc)) {
@"
# Shared runtime dependencies for Python apps launched from the cockpit.
# This file can grow as you install more app dependencies.
requests
"@ | Set-Content -Encoding UTF8 $CockpitReqSrc
}

if (-not (Test-Path $LauncherStateSrc)) {
@"
{
  "favorites": [],
  "hidden": [],
  "order": [],
  "title_overrides": {},
  "icon_overrides": {},
  "tile_sizes": {},
  "ui_filter_bucket": "all",
  "ui_sort_mode": "manual"
}
"@ | Set-Content -Encoding UTF8 $LauncherStateSrc
}

# Ensure applications exists in project (and contains git-repos if you already have it)
if (-not (Test-Path $AppsSrcDir)) {
  New-Item -ItemType Directory -Force -Path $AppsSrcDir | Out-Null
  # Create a starter git-repos if none exists
  $GitReposPath = Join-Path $AppsSrcDir "git-repos"
  if (-not (Test-Path $GitReposPath)) {
@"
# One entry per line.
# GitHub repo example:
# https://github.com/eabdiel/ProgreTomato
# URL shortcut example:
# https://github.com
"@ | Set-Content -Encoding UTF8 $GitReposPath
  }
}

# ----------------------------
# Use venv Python explicitly
# ----------------------------
$Py = Join-Path $ProjectRoot ($VenvPath + "\Scripts\python.exe")
if (-not (Test-Path $Py)) {
  throw "Venv python not found at: $Py  (Create it with: python -m venv venv)"
}

# ----------------------------
# Install build deps in venv (idempotent)
# ----------------------------
& $Py -m pip install --upgrade pip setuptools wheel | Out-Null
& $Py -m pip install --upgrade pyinstaller PySide6 requests | Out-Null

# ----------------------------
# Clean old build output
# ----------------------------
if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }
if (Test-Path ".\dist")  { Remove-Item -Recurse -Force ".\dist"  }

# ----------------------------
# Build EXE
# ----------------------------
if (-not (Test-Path $IconPath)) {
  throw "Icon not found: $IconPath"
}

& $Py -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name $AppName `
  --icon $IconPath `
  --collect-all PySide6 `
  main.py

# ----------------------------
# Stage release folder
# ----------------------------
Copy-Item ".\dist\$AppName.exe" -Destination $ExeDst -Force
Copy-Item $BannerSrc        -Destination $BannerDst -Force
Copy-Item $CockpitReqSrc    -Destination $CockpitReqDst -Force
Copy-Item $LauncherStateSrc -Destination $LauncherStateDst -Force

# Copy the user's existing applications folder (including your git-repos and any shortcuts)
# -Force overwrite; remove destination first to avoid stale files
if (Test-Path $AppsDstDir) { Remove-Item -Recurse -Force $AppsDstDir }
Copy-Item $AppsSrcDir -Destination $AppsDstDir -Recurse -Force

Write-Host ""
Write-Host "✅ Release created at: $ReleaseDirAbs"
Write-Host "   - $AppName.exe"
Write-Host "   - banner.txt"
Write-Host "   - cockpit-requirements.txt"
Write-Host "   - launcher_state.json"
Write-Host "   - applications\ (copied from your project, including git-repos)"
Write-Host ""

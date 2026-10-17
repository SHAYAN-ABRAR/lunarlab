# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
  Build the static demo locally (frontend in demo mode + the snapshot in demo/api) and serve it.

.DESCRIPTION
  1. python -m lunarlab export-demo --experiment-ids <ids>   (writes demo/api)
  2. scripts\build-demo.ps1                                  (builds frontend/dist-demo, serves it)
  The hosted copy is built the same way by .github/workflows/pages.yml.
#>
param(
  [string]$Base = "/",
  [int]$Port = 8080,
  [switch]$NoServe
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$snapshot = Join-Path $root "demo\api"
if (-not (Test-Path (Join-Path $snapshot "demo.json"))) {
  throw "No snapshot in demo\api. Run: python -m lunarlab export-demo --experiment-ids <ids>"
}
Push-Location (Join-Path $root "frontend")
try {
  $env:VITE_DEMO = "1"
  $env:VITE_BASE = $Base
  npx tsc -b
  if ($LASTEXITCODE -ne 0) { throw "typecheck failed" }
  npx vite build --outDir dist-demo --emptyOutDir
  if ($LASTEXITCODE -ne 0) { throw "build failed" }
} finally {
  Remove-Item Env:VITE_DEMO, Env:VITE_BASE -ErrorAction SilentlyContinue
  Pop-Location
}
$dist = Join-Path $root "frontend\dist-demo"
Copy-Item -Recurse -Force $snapshot (Join-Path $dist "demo-api")
Copy-Item -Force (Join-Path $dist "index.html") (Join-Path $dist "404.html")
Write-Host "Static demo built in $dist"
if (-not $NoServe) {
  Write-Host "Serving on http://127.0.0.1:$Port (Ctrl+C to stop). Deep links need the 404.html fallback of a real host."
  & (Join-Path $root ".venv\Scripts\python.exe") -m http.server $Port --bind 127.0.0.1 --directory $dist
}

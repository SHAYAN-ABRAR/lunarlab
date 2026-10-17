# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    Start the LunarLab web application (backend + built UI) on http://127.0.0.1:<Port>.

.DESCRIPTION
    By default the server runs in this console: press Ctrl+C to stop it. Before exiting it asks
    running training jobs to stop at a safe boundary (they become "interrupted" and can be resumed).
    With -Background the server runs without a console window; stop it with scripts\stop.ps1.

    Training continues while the browser is closed, as long as the backend and laptop are running.
    It pauses while the laptop sleeps and does not run while it is powered off.

        powershell -ExecutionPolicy Bypass -File scripts\start.ps1
        powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Background -NoBrowser

.PARAMETER Port
    Local port (default 8765). The server binds to 127.0.0.1 only.
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$Background,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
# The server keeps its data (and backend.json) under LUNARLAB_HOME when that is set, the project folder otherwise.
$HomeDir = if ($env:LUNARLAB_HOME) { $env:LUNARLAB_HOME } else { $Root }
$Data = Join-Path $HomeDir 'data'
$Url = "http://127.0.0.1:$Port"

function Fail([string]$Message) { Write-Host "ERROR: $Message" -ForegroundColor Red; exit 1 }

function Test-Health([string]$BaseUrl) {
    try {
        $r = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 2
        return ($r.status -eq 'ok')
    } catch { return $false }
}

if (-not (Test-Path $VenvPython)) {
    Fail "No virtual environment found. Run scripts\setup.ps1 first."
}
if (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) {
    Write-Host "Note: the web UI is not built (frontend\dist missing). Run scripts\setup.ps1 with Node.js installed. The API still starts." -ForegroundColor Yellow
}

# Already running? (data\backend.json is written by the server while it runs)
$info = Join-Path $Data 'backend.json'
if (Test-Path $info) {
    $existing = Get-Content $info -Raw | ConvertFrom-Json
    if (Test-Health "http://127.0.0.1:$($existing.port)") {
        Write-Host "LunarLab is already running at http://127.0.0.1:$($existing.port) (pid $($existing.pid))." -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$($existing.port)" }
        exit 0
    }
}
if (Test-Health $Url) { Fail "Port $Port already serves something that answers as LunarLab. Run scripts\stop.ps1 first." }

$serveArgs = @('-m', 'lunarlab', 'serve', '--host', '127.0.0.1', '--port', "$Port")
$env:PYTHONIOENCODING = 'utf-8'

if ($Background) {
    New-Item -ItemType Directory -Force -Path $Data | Out-Null
    $log = Join-Path $Data 'backend.log'
    $err = Join-Path $Data 'backend.err.log'
    $p = Start-Process -FilePath $VenvPython -ArgumentList $serveArgs -WorkingDirectory $Root `
        -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Health $Url) { break }
        if ($p.HasExited) { Fail "The server exited during startup (code $($p.ExitCode)). See $err" }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Health $Url)) { Fail "The server did not answer on $Url within 30 s. See $err" }
    $serverPid = $p.Id
    if (Test-Path $info) { $serverPid = (Get-Content $info -Raw | ConvertFrom-Json).pid }
    Write-Host "LunarLab is running in the background at $Url (pid $serverPid). Stop it with scripts\stop.ps1" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}

if (-not $NoBrowser) {
    # Open the browser once the server answers, without blocking this console.
    Start-Job -ScriptBlock {
        param($u)
        for ($i = 0; $i -lt 60; $i++) {
            try { Invoke-RestMethod -Uri "$u/api/health" -TimeoutSec 2 | Out-Null; Start-Process $u; return } catch { Start-Sleep -Milliseconds 500 }
        }
    } -ArgumentList $Url | Out-Null
}

Write-Host "Starting LunarLab at $Url  (Ctrl+C stops the server; running jobs are checkpointed first)" -ForegroundColor Cyan
Push-Location $Root
try {
    & $VenvPython @serveArgs
    $code = $LASTEXITCODE
}
finally { Pop-Location }
if ($code -eq 2) { Fail 'Another LunarLab backend already holds data\backend.lock. Use scripts\stop.ps1 first.' }
exit $code

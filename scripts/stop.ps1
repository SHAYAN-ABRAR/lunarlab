<#
.SYNOPSIS
    Stop the LunarLab backend gracefully.

.DESCRIPTION
    Asks the server to shut down through its own API. Before exiting, the server asks running
    training jobs to stop at a safe boundary and write a checkpoint (state "interrupted";
    resume them later from the UI or with `python -m lunarlab resume --run-id <id>`). This can
    take up to about a minute while a worker finishes an update or a validation pass.

    -Force terminates the backend and LunarLab workers that are still running afterwards. A process
    is only terminated after verifying it belongs to this project (its command line runs
    "lunarlab serve"/"lunarlab worker" with this project's Python); a stale PID alone is never enough.

        powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
        powershell -ExecutionPolicy Bypass -File scripts\stop.ps1 -Force
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [int]$TimeoutSeconds = 75,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = (Join-Path $Root '.venv\Scripts\python.exe')
$HomeDir = if ($env:LUNARLAB_HOME) { $env:LUNARLAB_HOME } else { $Root }
$info = Join-Path $HomeDir 'data\backend.json'

function Test-Health([string]$BaseUrl) {
    try { return ((Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 2).status -eq 'ok') } catch { return $false }
}

if ($Port -eq 0) {
    if (Test-Path $info) { $Port = [int]((Get-Content $info -Raw | ConvertFrom-Json).port) } else { $Port = 8765 }
}
$Url = "http://127.0.0.1:$Port"

if (Test-Health $Url) {
    Write-Host "Asking LunarLab at $Url to shut down (running jobs are checkpointed first)..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Method Post -Uri "$Url/api/shutdown" -Headers @{ 'X-LunarLab' = '1' } `
            -ContentType 'application/json' -Body '{}' -TimeoutSec 10 | Out-Null
    } catch {
        Write-Host "Shutdown request failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline -and (Test-Health $Url)) { Start-Sleep -Seconds 1 }
    if (Test-Health $Url) {
        Write-Host "The server is still answering after $TimeoutSeconds s." -ForegroundColor Yellow
    } else {
        Write-Host 'LunarLab backend stopped.' -ForegroundColor Green
    }
} else {
    Write-Host "No LunarLab backend answering at $Url."
}

# Remaining processes are identified by `lunarlab processes`, which verifies the command line
# (-m lunarlab serve|worker) AND that the working directory is this project.
if (-not (Test-Path $VenvPython)) { exit 0 }
$listing = & $VenvPython -m lunarlab processes
if ($LASTEXITCODE -ne 0) { Write-Host 'Could not list LunarLab processes.' -ForegroundColor Yellow; exit 1 }
if (($listing | Out-String) -match 'No LunarLab processes') { exit 0 }

Write-Host "`nLunarLab processes still running:" -ForegroundColor Yellow
$listing | ForEach-Object { Write-Host "  $_" }
if (-not $Force) {
    Write-Host "`nWorkers finish their current job or stop at the next safe boundary. Run again with -Force to terminate them (no stop checkpoint is written)."
    exit 0
}
& $VenvPython -m lunarlab processes --terminate
exit $LASTEXITCODE

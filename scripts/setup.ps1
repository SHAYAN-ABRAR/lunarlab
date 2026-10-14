<#
.SYNOPSIS
    Set up LunarLab: Python virtual environment, locked dependencies, frontend build, self-check.

.DESCRIPTION
    Creates .venv in the project folder with Python 3.12 or 3.13 (Box2D and pygame publish
    Windows wheels only up to 3.13), installs requirements.lock, installs the lunarlab package
    in editable mode, builds the web UI if Node.js is available, and runs `lunarlab doctor`.
    Nothing is installed system-wide and no machine setting is changed.

    Run from any folder (paths with spaces are fine):
        powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
    "-ExecutionPolicy Bypass" applies to this one process only; it does not change your policy.

.PARAMETER SkipFrontend
    Do not install/build the web UI (the CLI still works).

.PARAMETER SkipDoctor
    Do not run the post-install self-check.
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipDoctor
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$Lock = Join-Path $Root 'requirements.lock'
$Frontend = Join-Path $Root 'frontend'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { Write-Host "`nERROR: $Message" -ForegroundColor Red; exit 1 }
function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE -ne 0) { Fail "$What failed (exit code $LASTEXITCODE). See the output above." }
}

function Get-PythonVersion([string]$Exe, [string[]]$PrefixArgs = @()) {
    try {
        $v = & $Exe @PrefixArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { return ($v | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}

Write-Step "LunarLab setup in: $Root"

# --------------------------------------------------------------------------- #
# 1. Python 3.12 / 3.13
# --------------------------------------------------------------------------- #
$Supported = @('3.12', '3.13')
$Uv = Get-Command uv -ErrorAction SilentlyContinue

if (Test-Path $VenvPython) {
    $have = Get-PythonVersion $VenvPython
    if ($Supported -notcontains $have) {
        Fail ("Existing .venv uses Python $have. LunarLab needs 3.12 or 3.13 (Box2D/pygame wheels). " +
              "Delete the .venv folder and run this script again.")
    }
    Write-Host "Using existing virtual environment (Python $have)."
}
else {
    Write-Step 'Creating virtual environment (.venv)'
    $created = $false
    if ($Uv) {
        # uv finds an installed 3.12, or downloads a managed CPython into your user profile.
        & $Uv.Source venv --python 3.12 "$Venv"
        $created = ($LASTEXITCODE -eq 0)
    }
    if (-not $created) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        foreach ($ver in $Supported) {
            if ($py -and (Get-PythonVersion $py.Source @("-$ver")) -eq $ver) {
                & $py.Source "-$ver" -m venv "$Venv"
                Assert-LastExit "Creating the virtual environment with Python $ver"
                $created = $true
                break
            }
        }
    }
    if (-not $created) {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if ($python -and ($Supported -contains (Get-PythonVersion $python.Source))) {
            & $python.Source -m venv "$Venv"
            Assert-LastExit 'Creating the virtual environment'
            $created = $true
        }
    }
    if (-not $created) {
        Fail ("No Python 3.12 or 3.13 found. Install one of them (python.org installer, or `uv python install 3.12`) " +
              "and run this script again. Python 3.14 is not supported yet: Box2D and pygame have no Windows wheels for it.")
    }
}

# --------------------------------------------------------------------------- #
# 2. Dependencies (exact versions from requirements.lock)
# --------------------------------------------------------------------------- #
Write-Step 'Installing locked Python dependencies'
if ($Uv) {
    & $Uv.Source pip install --python "$VenvPython" -r "$Lock"
    Assert-LastExit 'uv pip install -r requirements.lock'
    & $Uv.Source pip install --python "$VenvPython" --no-deps -e "$Root"
    Assert-LastExit 'Installing the lunarlab package'
}
else {
    & $VenvPython -m pip install --upgrade pip
    Assert-LastExit 'Upgrading pip'
    & $VenvPython -m pip install -r "$Lock"
    if ($LASTEXITCODE -ne 0) {
        Fail ("pip could not install the locked dependencies. If the error mentions Box2D/box2d-py or SWIG: LunarLab " +
              "uses the prebuilt 'Box2D==2.3.10' wheel, which exists only for CPython 3.10-3.13 on Windows. Check that " +
              ".venv uses 3.12 or 3.13; do not install box2d-py, which needs SWIG and Microsoft C++ Build Tools.")
    }
    & $VenvPython -m pip install --no-deps -e "$Root"
    Assert-LastExit 'Installing the lunarlab package'
}

# --------------------------------------------------------------------------- #
# 3. Web UI
# --------------------------------------------------------------------------- #
if (-not $SkipFrontend) {
    Write-Step 'Building the web UI'
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -or -not $npm) {
        Write-Host ("Node.js not found. The CLI works without it; for the web UI install Node.js 22 LTS " +
                    "(Vite needs ^20.19 or >=22.12) and run this script again.") -ForegroundColor Yellow
    }
    else {
        $nodeVersion = (& $node.Source --version).Trim()
        $m = [regex]::Match($nodeVersion, 'v(\d+)\.(\d+)')
        $major = [int]$m.Groups[1].Value; $minor = [int]$m.Groups[2].Value
        $ok = ($major -eq 20 -and $minor -ge 19) -or ($major -eq 22 -and $minor -ge 12) -or ($major -gt 22)
        if (-not $ok) { Fail "Node $nodeVersion is too old for Vite 8 (needs ^20.19.0 or >=22.12.0)." }
        Push-Location $Frontend
        try {
            & $npm.Source ci --no-audit --no-fund
            Assert-LastExit 'npm ci'
            & $npm.Source run build
            Assert-LastExit 'npm run build'
        }
        finally { Pop-Location }
    }
}

# --------------------------------------------------------------------------- #
# 4. Self-check
# --------------------------------------------------------------------------- #
if (-not $SkipDoctor) {
    Write-Step 'Running lunarlab doctor'
    & $VenvPython -m lunarlab doctor
    Assert-LastExit 'lunarlab doctor'
}

Write-Host "`nSetup complete. Start the app with:" -ForegroundColor Green
Write-Host "    powershell -ExecutionPolicy Bypass -File `"$Root\scripts\start.ps1`""

<#
.SYNOPSIS
  Start AIChat in this terminal: database (Docker), API (FastAPI) and website (Next.js).
  Output of both servers is shown here, prefixed with [api] / [web]. Press Ctrl+C to stop both.

.EXAMPLE
  .\start.ps1                          # API on 8002, website on 3002
  .\start.ps1 -ApiPort 8010 -WebPort 3010
  .\start.ps1 -NoBrowser
#>
param(
    [int]$ApiPort = 8002,
    [int]$WebPort = 3002,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$logDir = Join-Path $root ".logs"

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

function Test-Port([int]$port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Until([scriptblock]$check, [int]$seconds, [string]$what) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (& $check) { return }
        Start-Sleep -Seconds 1
    }
    Fail "Timed out waiting for $what."
}

# Run $command in this console (no new window); its output goes to a log file we print from.
function Start-Server([string]$name, [string]$dir, [string]$command, [string]$color) {
    $log = Join-Path $logDir "$name.log"
    $proc = Start-Process cmd -ArgumentList "/c", "$command 2>&1" -WorkingDirectory $dir `
        -RedirectStandardOutput $log -NoNewWindow -PassThru
    [pscustomobject]@{ Name = $name; Proc = $proc; Log = $log; Pos = 0L; Rest = ""; Color = $color }
}

# Print lines added to the server's log since the last call.
function Show-Output($server) {
    if (-not (Test-Path $server.Log)) { return }
    $fs = [IO.File]::Open($server.Log, "Open", "Read", "ReadWrite")
    try {
        [void]$fs.Seek($server.Pos, "Begin")
        $text = (New-Object IO.StreamReader($fs)).ReadToEnd()
        $server.Pos = $fs.Length
    } finally {
        $fs.Dispose()
    }
    if (-not $text) { return }
    $lines = ($server.Rest + $text) -split "`r?`n"
    $server.Rest = $lines[-1]
    foreach ($line in $lines[0..($lines.Count - 2)]) {
        Write-Host ("[{0}] " -f $server.Name) -ForegroundColor $server.Color -NoNewline
        Write-Host $line
    }
}

# --- tools -----------------------------------------------------------------
foreach ($tool in "docker", "uv", "npm") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "'$tool' is not installed or not in PATH." }
}
foreach ($port in $ApiPort, $WebPort) {
    if (Test-Port $port) { Fail "Port $port is already in use. Run .\stop.ps1 first (or pick another port)." }
}

# --- database --------------------------------------------------------------
Step "Checking Docker"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $desktop)) { Fail "Docker is not running. Start Docker Desktop and try again." }
    Step "Starting Docker Desktop (this can take a minute)"
    Start-Process $desktop
    Wait-Until { docker info *> $null; $LASTEXITCODE -eq 0 } 180 "Docker"
}

Step "Starting Postgres"
Push-Location $root
docker compose up -d
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "docker compose failed." }
Wait-Until { docker compose exec -T db pg_isready -U aichat *> $null; $LASTEXITCODE -eq 0 } 60 "Postgres"
Pop-Location

# --- first-time installs ---------------------------------------------------
if (-not (Test-Path (Join-Path $backend ".venv"))) {
    Step "Installing backend packages (first run)"
    Push-Location $backend; uv sync; Pop-Location
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Step "Installing website packages (first run)"
    Push-Location $frontend; npm install; Pop-Location
}

# --- database tables -------------------------------------------------------
Step "Updating database tables"
Push-Location $backend
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "Database migration failed." }
Pop-Location

# --- servers ---------------------------------------------------------------
$apiUrl = "http://localhost:$ApiPort/api/v1"
$webUrl = "http://localhost:$WebPort"
New-Item -ItemType Directory -Force $logDir | Out-Null

# Child processes inherit these; they link the website and the API.
$env:CORS_ORIGINS = "[`"$webUrl`"]"
$env:NEXT_PUBLIC_API_URL = $apiUrl

Step "Starting API on port $ApiPort and website on port $WebPort (Ctrl+C stops both)"
$servers = @(
    (Start-Server "api" $backend "uv run uvicorn app.main:app --reload --port $ApiPort" "Yellow"),
    (Start-Server "web" $frontend "npx next dev --port $WebPort" "Magenta")
)

try {
    $ready = $false
    while ($true) {
        foreach ($s in $servers) {
            Show-Output $s
            if ($s.Proc.HasExited) {
                Start-Sleep -Milliseconds 300
                Show-Output $s
                Write-Host "The $($s.Name) server stopped (exit code $($s.Proc.ExitCode))." -ForegroundColor Red
                return
            }
        }
        if (-not $ready -and (Test-Port $ApiPort) -and (Test-Port $WebPort)) {
            $ready = $true
            Write-Host ""
            Write-Host "AIChat is running" -ForegroundColor Green
            Write-Host "  Website : $webUrl"
            Write-Host "  API     : $apiUrl"
            Write-Host "  API docs: http://localhost:$ApiPort/docs"
            Write-Host "  MCP     : http://localhost:$ApiPort/mcp  (for AI agents)"
            Write-Host "  Stop    : Ctrl+C"
            Write-Host ""
            if (-not $NoBrowser) { Start-Process $webUrl }
        }
        Start-Sleep -Milliseconds 300
    }
} finally {
    Write-Host "Stopping servers..." -ForegroundColor Cyan
    foreach ($s in $servers) {
        if (-not $s.Proc.HasExited) { taskkill /PID $s.Proc.Id /T /F *> $null }
    }
    # Catch anything still holding the ports (e.g. a reloader child).
    & (Join-Path $root "stop.ps1") -ApiPort $ApiPort -WebPort $WebPort | Out-Null
    Write-Host "Stopped." -ForegroundColor Cyan
}

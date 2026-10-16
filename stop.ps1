<#
.SYNOPSIS
  Stop the AIChat API and website. Add -Db to also stop the Postgres container (data is kept).

.EXAMPLE
  .\stop.ps1
  .\stop.ps1 -Db
  .\stop.ps1 -ApiPort 8010 -WebPort 3010
#>
param(
    [int]$ApiPort = 8002,
    [int]$WebPort = 3002,
    [switch]$Db
)

foreach ($port in $ApiPort, $WebPort) {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $pids) {
        Write-Output "Nothing running on port $port"
        continue
    }
    foreach ($id in $pids) {
        # uvicorn --reload and next dev run child processes; stop the whole tree.
        taskkill /PID $id /T /F *> $null
        Write-Output "Stopped process $id on port $port"
    }
}

if ($Db) {
    Push-Location $PSScriptRoot
    docker compose stop
    Pop-Location
}

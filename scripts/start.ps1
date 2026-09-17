[CmdletBinding()]
param(
    [switch]$Foreground
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env'
$envExample = Join-Path $projectRoot '.env.example'

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host 'Created .env from .env.example. Change the PostgreSQL password before deployment.' -ForegroundColor Yellow
}

$wslProjectRoot = (wsl -- wslpath -a "$projectRoot").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve project path in WSL.' }
$wslProjectRoot = $wslProjectRoot.Replace("'", "'\''")
$composeCommand = 'docker compose up --build'
if (-not $Foreground) {
    $composeCommand += ' -d'
}

Write-Host 'Starting AI Analyst...' -ForegroundColor Cyan
wsl -u root -- bash -lc "cd '$wslProjectRoot' && docker compose down --remove-orphans"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose cleanup exited with code $LASTEXITCODE."
}

wsl -u root -- bash -lc "cd '$wslProjectRoot' && $composeCommand"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose exited with code $LASTEXITCODE."
}

if (-not $Foreground) {
    Write-Host ''
    Write-Host 'AI Analyst is running:' -ForegroundColor Green
    Write-Host '  Frontend: http://localhost:4200'
    Write-Host '  API:      http://localhost:8000/docs'
}

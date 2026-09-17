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
    Write-Host 'Создан .env из .env.example. Перед публикацией измените пароль PostgreSQL.' -ForegroundColor Yellow
}

$wslProjectRoot = '/mnt/c/Users/love-/OneDrive/Documents/ChatGPT/AI Analyst'
$composeCommand = 'docker compose up --build'
if (-not $Foreground) {
    $composeCommand += ' -d'
}

Write-Host 'Запускаю AI Analyst…' -ForegroundColor Cyan
wsl -u root -- bash -lc "cd '$wslProjectRoot' && $composeCommand"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose завершился с кодом $LASTEXITCODE."
}

if (-not $Foreground) {
    Write-Host ''
    Write-Host 'AI Analyst запущен:' -ForegroundColor Green
    Write-Host '  Frontend: http://localhost:4200'
    Write-Host '  API:      http://localhost:8000/docs'
}

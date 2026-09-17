[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$wslProjectRoot = (wsl -- wslpath -a "$projectRoot").Trim().Replace("'", "'\''")
wsl -u root -- bash -lc "cd '$wslProjectRoot' && docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build"

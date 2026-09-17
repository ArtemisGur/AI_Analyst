$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$wslProjectRoot = (wsl -- wslpath -a "$projectRoot").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve project path in WSL.' }
$wslProjectRoot = $wslProjectRoot.Replace("'", "'\''")

wsl -u root -- bash -lc "cd '$wslProjectRoot' && docker compose down"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose exited with code $LASTEXITCODE."
}

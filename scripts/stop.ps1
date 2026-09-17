$ErrorActionPreference = 'Stop'
$wslProjectRoot = '/mnt/c/Users/love-/OneDrive/Documents/ChatGPT/AI Analyst'

wsl -u root -- bash -lc "cd '$wslProjectRoot' && docker compose down"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose exited with code $LASTEXITCODE."
}

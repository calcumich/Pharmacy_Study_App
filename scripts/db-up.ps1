$ErrorActionPreference = "Stop"

docker compose up -d db
Write-Host "Waiting for Postgres to be ready..."

do {
    Start-Sleep -Seconds 1
    docker compose exec db pg_isready -U app -d pharmdb -q | Out-Null
    $ready = $LASTEXITCODE -eq 0
} until ($ready)

Write-Host "Postgres is ready."

Write-Host "=== Financial SaaS Edge Relay Deployment ===" -ForegroundColor Cyan

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Error "Error: npx is required to deploy Cloudflare Worker."
    exit 1
}

Write-Host "1. Validating Worker files..."
if (-not (Test-Path "wrangler.toml") -or -not (Test-Path "schema.sql")) {
    Write-Error "Error: Run deploy script inside the edge-relay directory."
    exit 1
}

Write-Host "2. Checking Cloudflare authentication..."
npx wrangler whoami
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Please log in to Cloudflare first via 'npx wrangler login'."
    exit 1
}

Write-Host "3. Deploying Cloudflare Worker..."
npx wrangler deploy

Write-Host "Deployment complete! Edge relay is active." -ForegroundColor Green

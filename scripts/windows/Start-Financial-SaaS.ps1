[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Runtime = Join-Path $Root '.runtime'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
$Container = 'financial-saas-postgres'

function Test-TrackedProcess([string]$Name, [string]$ExpectedCommand, [string]$ExpectedExecutable = '') {
    $pidFile = Join-Path $Runtime "$Name.pid"
    if (-not (Test-Path $pidFile)) { return $false }
    $processId = (Get-Content $pidFile -Raw).Trim()
    if ($processId -notmatch '^\d+$') { Remove-Item $pidFile -Force; return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if (-not $process -or $process.CommandLine -notlike "*$ExpectedCommand*" -or
        ($ExpectedExecutable -and $process.ExecutablePath -ne $ExpectedExecutable)) {
        Remove-Item $pidFile -Force
        return $false
    }
    return $true
}

function Wait-Http([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try { return Invoke-RestMethod -Uri $Url -TimeoutSec 3 }
        catch { Start-Sleep -Seconds 1 }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Url"
}

New-Item -ItemType Directory -Force -Path $Runtime, 'C:\financial-saas\storage' | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI is not available.' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running.' }

docker container inspect $Container *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker container '$Container' does not exist." }
$containerRunning = docker inspect -f '{{.State.Running}}' $Container
if ($containerRunning -ne 'true') { docker start $Container | Out-Null }

$deadline = (Get-Date).AddSeconds(60)
do {
    docker exec $Container pg_isready -U postgres -d financial_saas *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not become ready.' }

if (-not (Test-Path (Join-Path $Backend '.env'))) {
    Copy-Item (Join-Path $Backend '.env.example') (Join-Path $Backend '.env')
    Write-Warning 'Created backend/.env from .env.example. Replace its development SECRET_KEY before shared use.'
}

if (-not (Test-Path $Python)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv (Join-Path $Backend '.venv') --python 3.11 }
    else { py -3.11 -m venv (Join-Path $Backend '.venv') }
}
Push-Location $Backend
try {
    & $Python -m pip install --disable-pip-version-check -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Alembic migration failed.' }
} finally { Pop-Location }

$packageLockHash = (Get-FileHash (Join-Path $Frontend 'package-lock.json') -Algorithm SHA256).Hash
$packageLockHashFile = Join-Path $Frontend 'node_modules\.financial-saas-package-lock.sha256'
$installedPackageLockHash = if (Test-Path $packageLockHashFile) { (Get-Content $packageLockHashFile -Raw).Trim() } else { '' }
if (-not (Test-Path (Join-Path $Frontend 'node_modules\.bin\vite.cmd')) -or $installedPackageLockHash -ne $packageLockHash) {
    Push-Location $Frontend
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        Set-Content $packageLockHashFile $packageLockHash
    } finally { Pop-Location }
}

if (-not (Test-TrackedProcess 'backend' 'src.main:app' $Python)) {
    $process = Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $Backend -RedirectStandardOutput (Join-Path $Runtime 'backend.log') -RedirectStandardError (Join-Path $Runtime 'backend.error.log') -PassThru
    Set-Content (Join-Path $Runtime 'backend.pid') $process.Id
}
$health = Wait-Http 'http://127.0.0.1:8000/health'
$ready = Wait-Http 'http://127.0.0.1:8000/ready'
if ($health.status -ne 'healthy' -or $ready.status -ne 'ready') { throw 'Backend health checks failed.' }

$viteScript = Join-Path $Frontend 'node_modules\vite\bin\vite.js'
if (-not (Test-TrackedProcess 'frontend' 'vite.js')) {
    $process = Start-Process -FilePath (Get-Command node).Source -ArgumentList $viteScript,'--host','127.0.0.1','--port','5173' -WorkingDirectory $Frontend -RedirectStandardOutput (Join-Path $Runtime 'frontend.log') -RedirectStandardError (Join-Path $Runtime 'frontend.error.log') -PassThru
    Set-Content (Join-Path $Runtime 'frontend.pid') $process.Id
}
Wait-Http 'http://127.0.0.1:5173' | Out-Null

Write-Host 'Financial SaaS is ready: http://127.0.0.1:5173'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
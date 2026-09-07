[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [string]$WhatsAppSessionPath = ''
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Runtime = Join-Path $Root '.runtime'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
$Container = 'financial-saas-postgres'
$HermesInstall = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent'
$BridgeScript = Join-Path $HermesInstall 'scripts\whatsapp-bridge\bridge.js'
$BridgeDirectory = Split-Path $BridgeScript -Parent
$BridgePort = 3000

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $name, $value = $line -split '=', 2
        $values[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Get-BackendSetting([hashtable]$Values, [string]$Name) {
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($processValue) { return $processValue }
    return $Values[$Name]
}

function Resolve-WhatsAppSession([string]$ExplicitPath) {
    if ($ExplicitPath) { return [IO.Path]::GetFullPath($ExplicitPath) }
    if ($env:FINANCIAL_SAAS_WHATSAPP_SESSION) {
        return [IO.Path]::GetFullPath($env:FINANCIAL_SAAS_WHATSAPP_SESSION)
    }
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'hermes\profiles\financial-saas\platforms\whatsapp\session'),
        (Join-Path $env:LOCALAPPDATA 'hermes\profiles\financial-saas\whatsapp\session'),
        (Join-Path $env:USERPROFILE '.hermes\whatsapp\session')
    )) {
        if (Test-Path (Join-Path $candidate 'creds.json')) { return $candidate }
    }
    return $null
}

function Test-TrackedProcess([string]$Name, [string]$ExpectedCommand, [string]$ExpectedExecutable = '') {
    $pidFile = Join-Path $Runtime "$Name.pid"
    if (Test-Path $pidFile) {
        $processId = (Get-Content $pidFile -Raw).Trim()
        if ($processId -match '^\d+$') {
            $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
            if ($process -and $process.CommandLine -like "*$ExpectedCommand*") { return $true }
            $child = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                $_.ParentProcessId -eq [int]$processId -and $_.CommandLine -like "*$ExpectedCommand*"
            } | Select-Object -First 1
            if ($child) { Set-Content $pidFile $child.ProcessId; return $true }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    # Recover PID if process is already running
    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_ -and $_.CommandLine -like "*$ExpectedCommand*" -and
        ($_.ExecutablePath -like '*\python.exe' -or $_.ExecutablePath -like '*\node.exe' -or $_.ExecutablePath -like '*\cmd.exe')
    } | Select-Object -First 1
    if ($running) {
        Set-Content $pidFile $running.ProcessId
        return $true
    }
    return $false
}

function Wait-Http([string]$Url, [int]$Seconds = 60, [scriptblock]$Condition = $null) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $resp = Invoke-RestMethod -Uri $Url -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if (-not $Condition -or (& $Condition $resp)) {
                return $resp
            }
            Start-Sleep -Seconds 1
        }
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
    docker exec $Container pg_isready -U financial -d financial_saas *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not become ready.' }

if (-not (Test-Path (Join-Path $Backend '.env'))) {
    Copy-Item (Join-Path $Backend '.env.example') (Join-Path $Backend '.env')
    Write-Warning 'Created backend/.env from .env.example. Replace its development SECRET_KEY before shared use.'
}

# Ensure database credentials match financial-saas-postgres container if defaults present
$envPath = Join-Path $Backend '.env'
$envContent = Get-Content $envPath -Raw
if ($envContent -match 'postgres:postgres@localhost:5432/financial_saas') {
    $envContent = $envContent.Replace('postgres:postgres@localhost:5432/financial_saas', 'financial:financial_dev_2026@localhost:5432/financial_saas')
    Set-Content $envPath $envContent
}
$backendEnv = Read-DotEnv $envPath
$WhatsAppEnabled = (Get-BackendSetting $backendEnv 'WHATSAPP_PROVIDER') -eq 'baileys'
if ($WhatsAppEnabled) {
    foreach ($required in @('WHATSAPP_ADAPTER_TOKEN', 'WHATSAPP_TENANT_TOKENS')) {
        if (-not (Get-BackendSetting $backendEnv $required)) { throw "Local WhatsApp requires $required in backend/.env or the process environment." }
    }
    if (-not (Test-Path $BridgeScript)) { throw "Local Baileys bridge not found at $BridgeScript." }
    $WhatsAppSession = Resolve-WhatsAppSession $WhatsAppSessionPath
    if (-not $WhatsAppSession -or -not (Test-Path (Join-Path $WhatsAppSession 'creds.json'))) {
        throw "WhatsApp is configured but no paired local session was found. Pair once with 'hermes whatsapp'."
    }
}

$pyprojectHash = (Get-FileHash (Join-Path $Backend 'pyproject.toml') -Algorithm SHA256).Hash
$pyprojectHashFile = Join-Path $Backend '.venv\.financial-saas-pyproject.sha256'
$installedPyprojectHash = if (Test-Path $pyprojectHashFile) { (Get-Content $pyprojectHashFile -Raw).Trim() } else { '' }
if (-not (Test-Path $Python) -or $installedPyprojectHash -ne $pyprojectHash) {
    if (-not (Test-Path $Python)) {
        if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv (Join-Path $Backend '.venv') --python 3.11 }
        else { py -3.11 -m venv (Join-Path $Backend '.venv') }
    }
    Push-Location $Backend
    try {
        & $Python -m pip install --disable-pip-version-check -e '.[dev]'
        if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
        Set-Content $pyprojectHashFile $pyprojectHash
    } finally { Pop-Location }
}
Push-Location $Backend
try {
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

function Start-TrackedBackgroundProcess(
    [string]$Name,
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$LogBaseName,
    [hashtable]$Environment = @{}
) {
    $stdout = Join-Path $Runtime "$LogBaseName.log"
    $stderr = Join-Path $Runtime "$LogBaseName.error.log"
    $batFile = Join-Path $Runtime "run-$Name.bat"
    $argString = ($Arguments | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '
    $envLines = @($Environment.GetEnumerator() | ForEach-Object {
        if ([string]$_.Value -match '[\r\n"]') { throw "Invalid process environment value for $($_.Key)." }
        "set `"$($_.Key)=$($_.Value)`""
    })
    $batContent = (@('@echo off') + $envLines + @("`"$FilePath`" $argString >> `"$stdout`" 2>> `"$stderr`"")) -join "`r`n"
    Set-Content -Path $batFile -Value $batContent -Encoding ASCII
    $cmdProcess = Start-Process -WindowStyle Hidden -FilePath $batFile -WorkingDirectory $WorkingDirectory -PassThru
    Start-Sleep -Milliseconds 400
    $child = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ParentProcessId -eq $cmdProcess.Id
    } | Select-Object -First 1
    $actualPid = if ($child) { $child.ProcessId } else { $cmdProcess.Id }
    Set-Content (Join-Path $Runtime "$Name.pid") $actualPid
}

if ($WhatsAppEnabled) {
    & (Get-Command node).Source (Join-Path $Root 'scripts\verify_and_patch_baileys_bridge.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Local Baileys bridge verification failed.' }
    if (-not (Test-TrackedProcess 'baileys' 'whatsapp-bridge\bridge.js')) {
        Push-Location $Backend
        try {
            $allowedUsers = (& $Python 'scripts/export_whatsapp_allowlist.py').Trim()
            if ($LASTEXITCODE -ne 0) { throw 'Could not load the local WhatsApp sender allowlist.' }
        } finally { Pop-Location }
        if (-not $allowedUsers) {
            throw 'Local WhatsApp has no active authorized sender. Register an Owner sender first.'
        }
        $bridgeEnv = @{
            WHATSAPP_MODE = 'bot'
            WHATSAPP_ALLOWED_USERS = $allowedUsers
            WHATSAPP_DM_POLICY = 'allowlist'
            HERMES_IMAGE_CACHE_DIR = (Join-Path $Runtime 'whatsapp-cache\images')
            HERMES_DOCUMENT_CACHE_DIR = (Join-Path $Runtime 'whatsapp-cache\documents')
            HERMES_AUDIO_CACHE_DIR = (Join-Path $Runtime 'whatsapp-cache\audio')
        }
        New-Item -ItemType Directory -Force -Path $bridgeEnv.HERMES_IMAGE_CACHE_DIR, $bridgeEnv.HERMES_DOCUMENT_CACHE_DIR, $bridgeEnv.HERMES_AUDIO_CACHE_DIR | Out-Null
        $nodeExecutable = (Get-Command node).Source
        Start-TrackedBackgroundProcess 'baileys' $nodeExecutable @($BridgeScript, '--port', "$BridgePort", '--session', $WhatsAppSession, '--mode', 'bot') $BridgeDirectory 'baileys' $bridgeEnv
    }
    $bridgeHealth = Wait-Http "http://127.0.0.1:$BridgePort/health" 30 { param($r) $r.status -eq 'connected' }
    if ($bridgeHealth.status -ne 'connected') { throw "Local WhatsApp bridge is not connected (status: $($bridgeHealth.status))." }
}

if (-not (Test-TrackedProcess 'backend' 'src.main:app' $Python)) {
    Start-TrackedBackgroundProcess 'backend' $Python @('-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000') $Backend 'backend'
    Test-TrackedProcess 'backend' 'src.main:app' $Python | Out-Null
}
$health = Wait-Http 'http://127.0.0.1:8000/health' 60 { param($r) $r.status -eq 'healthy' }
$ready = Wait-Http 'http://127.0.0.1:8000/ready' 60 { param($r) $r.status -eq 'ready' }
if ($health.status -ne 'healthy' -or $ready.status -ne 'ready') { throw 'Backend health checks failed.' }

# Start PostgreSQL-backed background job worker
if (-not (Test-TrackedProcess 'worker' 'src.worker' $Python)) {
    Start-TrackedBackgroundProcess 'worker' $Python @('-m','src.worker') $Backend 'worker'
    Test-TrackedProcess 'worker' 'src.worker' $Python | Out-Null
}

$viteScript = Join-Path $Frontend 'node_modules\vite\bin\vite.js'
if (-not (Test-TrackedProcess 'frontend' 'vite.js')) {
    $node = (Get-Command node).Source
    Start-TrackedBackgroundProcess 'frontend' $node @($viteScript,'--host','127.0.0.1','--port','5173') $Frontend 'frontend'
}
Wait-Http 'http://127.0.0.1:5173' | Out-Null

Write-Host 'Financial SaaS is ready: http://127.0.0.1:5173'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
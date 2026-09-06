[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runtime = Join-Path $Root '.runtime'

foreach ($entry in @(
    @{ Name = 'frontend'; Match = 'vite.js' },
    @{ Name = 'worker'; Match = 'src.worker' },
    @{ Name = 'backend'; Match = 'src.main:app' }
)) {
    $pidFile = Join-Path $Runtime "$($entry.Name).pid"
    if (Test-Path $pidFile) {
        $processId = (Get-Content $pidFile -Raw).Trim()
        if ($processId -match '^\d+$') {
            Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    
    # Clean up any lingering process matching the command line
    $remaining = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_ -and $_.CommandLine -like "*$($entry.Match)*"
    }
    foreach ($rem in $remaining) {
        Stop-Process -Id $rem.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

docker container inspect financial-saas-postgres *> $null
if ($LASTEXITCODE -eq 0) { docker stop financial-saas-postgres | Out-Null }
Write-Host 'Financial SaaS local runtime stopped.'
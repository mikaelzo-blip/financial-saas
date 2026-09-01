[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runtime = Join-Path $Root '.runtime'

foreach ($entry in @(
    @{ Name = 'frontend'; Match = 'vite.js'; Executable = (Get-Command node -ErrorAction SilentlyContinue).Source },
    @{ Name = 'backend'; Match = 'src.main:app'; Executable = (Join-Path $Root 'backend\.venv\Scripts\python.exe') }
)) {
    $pidFile = Join-Path $Runtime "$($entry.Name).pid"
    if (-not (Test-Path $pidFile)) { continue }
    $processId = (Get-Content $pidFile -Raw).Trim()
    if ($processId -match '^\d+$') {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine -like "*$($entry.Match)*" -and
            $entry.Executable -and $process.ExecutablePath -eq $entry.Executable) {
            Stop-Process -Id $processId -Force
        }
    }
    Remove-Item $pidFile -Force
}

docker container inspect financial-saas-postgres *> $null
if ($LASTEXITCODE -eq 0) { docker stop financial-saas-postgres | Out-Null }
Write-Host 'Financial SaaS local runtime stopped.'
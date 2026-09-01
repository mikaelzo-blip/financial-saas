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
        $targets = @($process) + @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.ParentProcessId -eq [int]$processId
        })
        $target = $targets | Where-Object {
            $_ -and $_.CommandLine -like "*$($entry.Match)*" -and
            $entry.Executable -and $_.ExecutablePath -eq $entry.Executable
        } | Select-Object -First 1
        if ($target) { Stop-Process -Id $target.ProcessId -Force }
    }
    Remove-Item $pidFile -Force
}

docker container inspect financial-saas-postgres *> $null
if ($LASTEXITCODE -eq 0) { docker stop financial-saas-postgres | Out-Null }
Write-Host 'Financial SaaS local runtime stopped.'
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runtime = Join-Path $Root '.runtime'

foreach ($entry in @(
    @{ Name = 'frontend'; Match = 'vite.js' },
    @{ Name = 'worker'; Match = 'src.worker' },
    @{ Name = 'backend'; Match = 'src.main:app' },
    @{ Name = 'baileys'; Match = 'whatsapp-bridge\bridge.js' }
)) {
    $pidFile = Join-Path $Runtime "$($entry.Name).pid"
    if (Test-Path $pidFile) {
        $processId = (Get-Content $pidFile -Raw).Trim()
        if ($processId -match '^\d+$') {
            # Stop children first, then parent
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                $_.ParentProcessId -eq [int]$processId
            } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    
    # Clean up any lingering process matching the command line
    $remaining = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_ -and $_.ProcessId -ne $PID -and $_.CommandLine -like "*$($entry.Match)*" -and
        ($_.ExecutablePath -like '*\python.exe' -or $_.ExecutablePath -like '*\node.exe' -or $_.ExecutablePath -like '*\cmd.exe')
    }
    foreach ($rem in $remaining) {
        Stop-Process -Id $rem.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

docker container inspect financial-saas-postgres *> $null
if ($LASTEXITCODE -eq 0) { docker stop financial-saas-postgres | Out-Null }
Write-Host 'Financial SaaS local runtime stopped.'
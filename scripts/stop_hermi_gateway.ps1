param(
    [int]$Port = 8789
)

$ErrorActionPreference = "Stop"

$targets = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -in @("python.exe", "pythonw.exe")) -and
    ($_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*hermi_gateway.app:app*")
}

if (-not $targets) {
    Write-Host "No Hermi Gateway uvicorn process found."
    exit 0
}

foreach ($proc in $targets) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped Hermi Gateway process $($proc.ProcessId)."
    } catch {
        Write-Host "Failed to stop process $($proc.ProcessId): $($_.Exception.Message)"
        exit 1
    }
}

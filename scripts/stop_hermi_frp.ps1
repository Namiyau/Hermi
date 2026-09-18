$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "state\hermi_frp\hermi_frp.pid"
if (-not (Test-Path -LiteralPath $PidFile)) { Write-Host "Hermi FRP is not running."; exit 0 }
$frpPid = [int](Get-Content -LiteralPath $PidFile -Raw)
$process = Get-Process -Id $frpPid -ErrorAction SilentlyContinue
if ($process) {
    if ($process.ProcessName -notmatch "frpc|natfrp") { throw "PID $frpPid is not an FRP client; refusing to stop it." }
    Stop-Process -Id $frpPid -Force
    Write-Host "Hermi FRP stopped. PID=$frpPid"
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue

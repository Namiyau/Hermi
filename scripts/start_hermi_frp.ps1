param(
    [string]$FrpcPath = $env:HERMI_FRPC_PATH,
    [string]$ConfigPath = $env:HERMI_FRPC_CONFIG
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $Root "state\hermi_frp"
$PidFile = Join-Path $StateDir "hermi_frp.pid"
$OutLog = Join-Path $StateDir "frpc.stdout.log"
$ErrLog = Join-Path $StateDir "frpc.stderr.log"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if (-not $ConfigPath) { $ConfigPath = Join-Path $Root "frp\frpc.hermi.local.toml" }
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "FRP config missing: $ConfigPath. Copy frp\frpc.hermi.example.toml first."
}
$ConfigPath = (Resolve-Path -LiteralPath $ConfigPath).Path
$text = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8
if ($text.Contains("CHANGE_ME")) { throw "FRP config still contains CHANGE_ME. Fill server address and token first." }

& (Join-Path $PSScriptRoot "test_hermi_frp_config.ps1") -ConfigPath $ConfigPath
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8789/health" -TimeoutSec 5
    if ($health.status -ne "ok") { throw "unexpected health response" }
} catch {
    throw "Hermi 8789 is not healthy. Start Hermi before FRP. $($_.Exception.Message)"
}

if (-not $FrpcPath) {
    $command = Get-Command frpc -ErrorAction SilentlyContinue
    if ($command) { $FrpcPath = $command.Source }
}
if (-not $FrpcPath -or -not (Test-Path -LiteralPath $FrpcPath)) {
    throw "frpc executable not found. Set HERMI_FRPC_PATH to frpc.exe."
}
$FrpcPath = (Resolve-Path -LiteralPath $FrpcPath).Path

if (Test-Path -LiteralPath $PidFile) {
    $oldPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Hermi FRP is already running with PID $oldPid." }
    Remove-Item -LiteralPath $PidFile -Force
}

$process = Start-Process -FilePath $FrpcPath -ArgumentList @("-c", $ConfigPath) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
$process.Id | Set-Content -LiteralPath $PidFile -Encoding ASCII
Write-Host "Hermi FRP started. PID=$($process.Id)"
Write-Host "Config: $ConfigPath"
Write-Host "Logs: $StateDir"

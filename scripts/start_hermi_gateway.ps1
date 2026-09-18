param(
    [string]$HostName = "0.0.0.0",
    [int]$Port = 0,
    [string]$OwnerToken = "",
    [string]$ChannelToken = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $Root "state"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Import-EnvFile([string]$Path, [switch]$Force) {
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim().TrimStart([char]0xFEFF)
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name -and ($Force -or -not (Test-Path "Env:$name"))) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

$LocalEnv = Join-Path $Root "secrets.local.env"
if (-not (Test-Path $LocalEnv)) {
@"
HERMI_OWNER_TOKEN=replace-with-owner-token
HERMI_CHANNEL_TOKEN=replace-with-channel-token
HERMI_HERMES_API_URL=http://127.0.0.1:8642/v1/chat/completions
HERMI_PORT=8789
HERMI_DB_PATH=./state/hermi_gateway.db
"@ | Set-Content -LiteralPath $LocalEnv -Encoding UTF8
}

Import-EnvFile $LocalEnv -Force

$DocumentsDir = Split-Path -Parent $Root
$QlosEnv = Get-ChildItem -LiteralPath $DocumentsDir -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "secrets.local.env" } |
    Where-Object {
        (Test-Path -LiteralPath $_) -and
        (Select-String -LiteralPath $_ -Pattern "^QLOS_HERMES_API_KEY=" -Quiet)
    } |
    Select-Object -First 1
if ($QlosEnv) {
    Import-EnvFile $QlosEnv
}

if ($OwnerToken) {
    $env:HERMI_OWNER_TOKEN = $OwnerToken
}
if ($ChannelToken) {
    $env:HERMI_CHANNEL_TOKEN = $ChannelToken
}
if (-not $env:HERMI_OWNER_TOKEN) {
    $env:HERMI_OWNER_TOKEN = "replace-with-owner-token"
}
if (-not $env:HERMI_CHANNEL_TOKEN) {
    $env:HERMI_CHANNEL_TOKEN = "replace-with-channel-token"
}
if (-not $env:HERMI_HERMES_API_KEY -and $env:QLOS_HERMES_API_KEY) {
    $env:HERMI_HERMES_API_KEY = $env:QLOS_HERMES_API_KEY
}
if (-not $env:HERMI_QLOS_SEND_TOKEN -and $env:QLOS_HERMI_GATEWAY_TOKEN) {
    $env:HERMI_QLOS_SEND_TOKEN = $env:QLOS_HERMI_GATEWAY_TOKEN
}
if (-not $env:HERMI_DB_PATH) {
    $env:HERMI_DB_PATH = Join-Path $StateDir "hermi_gateway.db"
}
if (-not $env:HERMI_MEDIA_DIR) {
    $mediaFolder = "Hermi$([char]0x8D44)$([char]0x6599)"
    $env:HERMI_MEDIA_DIR = Join-Path ([Environment]::GetFolderPath("MyDocuments")) (Join-Path $mediaFolder "media")
}
if (-not $env:HERMI_SCHEDULER_ENABLED) {
    $env:HERMI_SCHEDULER_ENABLED = "1"
}
if ($Port -le 0) {
    $Port = if ($env:HERMI_PORT) { [int]$env:HERMI_PORT } else { 8789 }
}

$selfPid = $PID
$parentPid = if ($env:HERMI_RESTART_PARENT_PID) { [int]$env:HERMI_RESTART_PARENT_PID } else { 0 }

function Stop-HermiProcess($proc) {
    if (-not $proc -or $proc.ProcessId -eq $selfPid) {
        return
    }
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped old Hermi Gateway process $($proc.ProcessId)."
    } catch {
        Write-Host "Failed to stop old Hermi Gateway process $($proc.ProcessId): $($_.Exception.Message)"
    }
}

$existing = Get-CimInstance Win32_Process | Where-Object {
    ($_.ProcessId -ne $selfPid) -and
    ($_.Name -in @("python.exe", "pythonw.exe")) -and
    (
        ($_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*hermi_gateway.app*") -or
        ($parentPid -gt 0 -and $_.ProcessId -eq $parentPid)
    )
}
foreach ($proc in $existing) {
    Stop-HermiProcess $proc
}

$portUsers = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Where-Object {
    $_.OwningProcess -ne 0
}
foreach ($item in $portUsers) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($item.OwningProcess)" -ErrorAction SilentlyContinue
    if ($proc -and ($proc.CommandLine -like "*hermi_gateway.app*")) {
        Stop-HermiProcess $proc
        continue
    }
    if ($proc) {
        Write-Host "Port $Port is already used by process $($item.OwningProcess): $($proc.Name)"
        Write-Host $proc.CommandLine
        Write-Host "Change port with: scripts\start_hermi_gateway.ps1 -Port 8790"
        exit 1
    }
}

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    $stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Where-Object {
        $_.OwningProcess -ne 0
    }
    if (-not $stillListening) {
        break
    }
    Start-Sleep -Milliseconds 300
}

$runtimeInfo = Join-Path $StateDir "hermi_gateway_runtime.txt"
$LocalUrl = "http://127.0.0.1:${Port}"
$TailscaleIp = ""
try {
    $TailscaleIp = (& tailscale ip -4 2>$null | Select-Object -First 1).Trim()
} catch {
    $TailscaleIp = ""
}
$TailscaleUrl = if ($TailscaleIp) { "http://${TailscaleIp}:${Port}" } else { "tailscale ip -4 unavailable" }
@"
Hermi Gateway
LOCAL_URL=$LocalUrl
TAILSCALE_URL=$TailscaleUrl
QLOS_ENV=QLOS_HERMI_GATEWAY_URL=$LocalUrl
QLOS_CHANNEL_TOKEN=configured
"@ | Set-Content -LiteralPath $runtimeInfo -Encoding UTF8

Write-Host "Hermi Gateway"
Write-Host "Root: $Root"
Write-Host "Local URL:  $LocalUrl"
Write-Host "Tailscale URL: $TailscaleUrl"
Write-Host "Owner token: configured"
Write-Host "Channel token for QLOS: configured"
Write-Host "Runtime info: $runtimeInfo"
Write-Host ""
Write-Host "Press Ctrl+C to stop."
Write-Host ""

if (-not $NoOpen) {
    Start-Process $LocalUrl
}

$VenvPython = "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}
& $VenvPython -m uvicorn hermi_gateway.app:app --host $HostName --port $Port


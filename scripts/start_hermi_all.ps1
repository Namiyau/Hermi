param(
    [string]$BotQQ = "",
    [switch]$OpenHermi,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$HermiRoot = Split-Path -Parent $PSScriptRoot
$DocumentsRoot = Split-Path -Parent $HermiRoot
$QlosFolder = "$([char]0x81EA)$([char]0x52A8)QQ"
$QlosRoot = Join-Path $DocumentsRoot $QlosFolder
$StateDir = Join-Path $HermiRoot "state\all_stack"
$LogDir = Join-Path $StateDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Import-EnvFile([string]$Path, [switch]$Force) {
    if (-not (Test-Path -LiteralPath $Path)) {
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

function Test-PortOpen([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-Port([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Resolve-HermesExe {
    $candidates = @()
    if ($env:HERMES_EXE) {
        $candidates += $env:HERMES_EXE
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\hermes.exe")
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $cmd = Get-Command "hermes" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Hermes exe not found."
}

function Resolve-PythonExe([string]$HermesExe) {
    $scriptsDir = Split-Path -Parent $HermesExe
    $venvPython = Join-Path $scriptsDir "python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }
    $cmd = Get-Command "python" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Python not found."
}

function Stop-MatchingProcesses {
    $selfPid = $PID
    $targets = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $selfPid -and (
            ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*hermi_gateway.app*") -or
            ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*qlos_lite.onebot_server*") -or
            ($_.CommandLine -like "*hermes_cli.main*gateway*") -or
            ($_.CommandLine -like "*hermes.exe* gateway*") -or
            ($_.Name -eq "NapCatWinBootMain.exe")
        )
    }
    foreach ($proc in $targets) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "stopped $($proc.Name) $($proc.ProcessId)"
        } catch {
            Write-Host "skip stopped process $($proc.ProcessId)"
        }
    }
}

function Start-HiddenProcess([string]$Name, [string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory) {
    $outLog = Join-Path $LogDir "$Name.out.log"
    $errLog = Join-Path $LogDir "$Name.err.log"
    Write-Host "starting $Name..."
    Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog | Out-Null
}

if (-not (Test-Path -LiteralPath $QlosRoot)) {
    throw "QLOS root not found: $QlosRoot"
}

Import-EnvFile (Join-Path $HermiRoot "secrets.local.env") -Force
Import-EnvFile (Join-Path $QlosRoot "secrets.local.env")

if (-not $env:HERMI_OWNER_TOKEN) {
    $env:HERMI_OWNER_TOKEN = "replace-with-owner-token"
}
if (-not $env:HERMI_CHANNEL_TOKEN) {
    $env:HERMI_CHANNEL_TOKEN = "replace-with-channel-token"
}
if (-not $env:HERMI_HERMES_API_URL) {
    $env:HERMI_HERMES_API_URL = "http://127.0.0.1:8642/v1/chat/completions"
}
if (-not $env:HERMI_PORT) {
    $env:HERMI_PORT = "8789"
}
if (-not $env:HERMI_DB_PATH) {
    $env:HERMI_DB_PATH = Join-Path $HermiRoot "state\hermi_gateway.db"
}
if (-not $env:HERMI_TOOL_GUARD_IDENTITY_FILE) {
    $env:HERMI_TOOL_GUARD_IDENTITY_FILE = Join-Path $HermiRoot "state\hermi_tool_identity.jsonl"
}
if (-not $env:HERMI_HERMES_API_KEY -and $env:QLOS_HERMES_API_KEY) {
    $env:HERMI_HERMES_API_KEY = $env:QLOS_HERMES_API_KEY
}
if (-not $env:HERMI_QLOS_SEND_TOKEN -and $env:QLOS_HERMI_GATEWAY_TOKEN) {
    $env:HERMI_QLOS_SEND_TOKEN = $env:QLOS_HERMI_GATEWAY_TOKEN
}
if (-not $env:API_SERVER_KEY -and $env:QLOS_HERMES_API_KEY) {
    $env:API_SERVER_KEY = $env:QLOS_HERMES_API_KEY
}
if (-not $env:QLOS_HERMI_GATEWAY_URL) {
    $env:QLOS_HERMI_GATEWAY_URL = "http://127.0.0.1:$($env:HERMI_PORT)"
}
if (-not $env:QLOS_HERMI_GATEWAY_TOKEN) {
    $env:QLOS_HERMI_GATEWAY_TOKEN = $env:HERMI_CHANNEL_TOKEN
}
if (-not $env:AUXILIARY_VISION_PROVIDER) {
    $env:AUXILIARY_VISION_PROVIDER = "gemini"
}
if (-not $env:AUXILIARY_VISION_MODEL -or $env:AUXILIARY_VISION_MODEL -eq "gemini-2.0-flash-exp") {
    $env:AUXILIARY_VISION_MODEL = "gemini-3.5-flash"
}
$mediaFolder = "Hermi$([char]0x8D44)$([char]0x6599)"
if (-not $env:QLOS_MEDIA_DIR) {
    $env:QLOS_MEDIA_DIR = Join-Path $DocumentsRoot $mediaFolder
}
if (-not $env:HERMI_MEDIA_DIR) {
    $env:HERMI_MEDIA_DIR = Join-Path (Join-Path $DocumentsRoot $mediaFolder) "media"
}
if (-not $BotQQ) {
    $BotQQ = if ($env:QLOS_BOT_QQ_ID) { $env:QLOS_BOT_QQ_ID } else { "replace-with-bot-qq-id" }
}

$HermesExe = Resolve-HermesExe
$PythonExe = Resolve-PythonExe $HermesExe
$NapCatRoot = if ($env:NAPCAT_ROOT) { $env:NAPCAT_ROOT } else { Join-Path $QlosRoot "external\NapCat" }
$NapCatDir = Join-Path $NapCatRoot "shell"
if (-not (Test-Path -LiteralPath (Join-Path $NapCatDir "launcher.bat"))) {
    throw "External NapCat launcher not found. Set NAPCAT_ROOT: $NapCatRoot"
}

if ($Restart) {
    Stop-MatchingProcesses
    Start-Sleep -Seconds 2
}

$hermiPort = [int]$env:HERMI_PORT
if (-not (Test-PortOpen 8642)) {
    Start-HiddenProcess "hermes_trainee_gateway" $PythonExe @($HermesExe, "-p", "trainee", "gateway") (Split-Path -Parent (Split-Path -Parent $HermesExe))
} else {
    Write-Host "Hermes trainee gateway already on 8642"
}
if (-not (Test-PortOpen 8643)) {
    Start-HiddenProcess "hermes_imouto_gateway" $PythonExe @($HermesExe, "-p", "imouto", "gateway") (Split-Path -Parent (Split-Path -Parent $HermesExe))
} else {
    Write-Host "Hermes imouto gateway already on 8643"
}
if (-not (Test-PortOpen 8644)) {
    Start-HiddenProcess "hermes_maid_gateway" $PythonExe @($HermesExe, "-p", "maid", "gateway") (Split-Path -Parent (Split-Path -Parent $HermesExe))
} else {
    Write-Host "Hermes maid gateway already on 8644"
}

if (-not (Test-PortOpen 8766)) {
    Start-HiddenProcess "qlos_lite" $PythonExe @("-m", "qlos_lite.onebot_server") $QlosRoot
} else {
    Write-Host "QLOS already on 8766"
}

if (-not (Test-PortOpen 3000)) {
    Start-HiddenProcess "napcat" "cmd.exe" @("/c", "launcher.bat -q $BotQQ") $NapCatDir
} else {
    Write-Host "NapCat already on 3000"
}

if (-not (Test-PortOpen $hermiPort)) {
    Start-HiddenProcess "hermi_gateway" $PythonExe @("-m", "uvicorn", "hermi_gateway.app:app", "--host", "0.0.0.0", "--port", "$hermiPort") $HermiRoot
} else {
    Write-Host "Hermi already on $hermiPort"
}

Write-Host ""
Write-Host "waiting for ports..."
$okHermes = Wait-Port 8642 40
$okImouto = Wait-Port 8643 40
$okMaid = Wait-Port 8644 40
$okQlos = Wait-Port 8766 30
$okNapCat = Wait-Port 3000 60
$okHermi = Wait-Port $hermiPort 40

$runtimeInfo = Join-Path $HermiRoot "state\hermi_all_runtime.txt"
$tailscaleIp = ""
try {
    $tailscaleIp = (& tailscale ip -4 2>$null | Select-Object -First 1).Trim()
} catch {
    $tailscaleIp = ""
}
$localUrl = "http://127.0.0.1:$hermiPort"
$tailscaleUrl = if ($tailscaleIp) { "http://${tailscaleIp}:$hermiPort" } else { "tailscale unavailable" }
@"
Hermi all stack
LOCAL_URL=$localUrl
TAILSCALE_URL=$tailscaleUrl
HERMI_PORT=$hermiPort
HERMES_TRAINEE_GATEWAY=http://127.0.0.1:8642
HERMES_IMOUTO_GATEWAY=http://127.0.0.1:8643
HERMES_MAID_GATEWAY=http://127.0.0.1:8644
QLOS=http://127.0.0.1:8766
NAPCAT=http://127.0.0.1:3000
QLOS_MEDIA_DIR=$env:QLOS_MEDIA_DIR
LOG_DIR=$LogDir
"@ | Set-Content -LiteralPath $runtimeInfo -Encoding UTF8

Write-Host ""
Write-Host "status:"
Write-Host "Hermi  $hermiPort : $okHermi"
Write-Host "Trainee 8642: $okHermes"
Write-Host "Ember  8643: $okImouto"
Write-Host "Vera   8644: $okMaid"
Write-Host "QLOS   8766: $okQlos"
Write-Host "NapCat 3000: $okNapCat"
Write-Host ""
Write-Host "Hermi local:     $localUrl"
Write-Host "Hermi tailscale: $tailscaleUrl"
Write-Host "runtime: $runtimeInfo"
Write-Host "logs:    $LogDir"

if ($OpenHermi -and $okHermi) {
    Start-Process $localUrl
}

if (-not ($okHermi -and $okHermes -and $okImouto -and $okMaid -and $okQlos -and $okNapCat)) {
    exit 1
}



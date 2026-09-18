param(
    [switch]$OpenHermi
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $Root "state\all_stack"
$LogDir = Join-Path $StateDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

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

function Test-OpenWebUI {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8080" -TimeoutSec 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
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

function Get-ShortcutTarget([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    return [pscustomobject]@{
        Target = $shortcut.TargetPath
        Arguments = $shortcut.Arguments
        WorkingDirectory = $shortcut.WorkingDirectory
    }
}

function Start-OpenWebUI {
    $desktopCmd = Join-Path ([Environment]::GetFolderPath("Desktop")) "$([char]0x542F)$([char]0x52A8) Open WebUI.cmd"
    $webuiScript = "C:\OpenWebUI\Start-OpenWebUI.ps1"
    if (Test-OpenWebUI) {
        Write-Host "Open WebUI already on 8080"
        return
    }
    if (Test-Path -LiteralPath $webuiScript) {
        Write-Host "starting Open WebUI..."
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $webuiScript) `
            -WorkingDirectory (Split-Path -Parent $webuiScript) `
            -WindowStyle Hidden | Out-Null
        return
    }
    if (Test-Path -LiteralPath $desktopCmd) {
        Write-Host "starting Open WebUI by desktop cmd..."
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList @("/c", $desktopCmd) `
            -WorkingDirectory (Split-Path -Parent $desktopCmd) `
            -WindowStyle Hidden | Out-Null
        return
    }
    throw "Open WebUI launcher not found."
}

function Start-SakuraFrp {
    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "SakuraLauncher.exe" -or $_.CommandLine -like "*SakuraFrpLauncher*"
    } | Select-Object -First 1
    if ($running) {
        Write-Host "SakuraFRP already running with PID $($running.ProcessId)"
        return
    }

    $links = @(
        (Join-Path $env:PUBLIC "Desktop\SakuraFrp $([char]0x542F)$([char]0x52A8)$([char]0x5668).lnk"),
        (Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\SakuraFrp $([char]0x542F)$([char]0x52A8)$([char]0x5668)\SakuraFrp $([char]0x542F)$([char]0x52A8)$([char]0x5668).lnk")
    )
    foreach ($link in $links) {
        $target = Get-ShortcutTarget $link
        if ($target -and (Test-Path -LiteralPath $target.Target)) {
            Write-Host "starting SakuraFRP..."
            $args = @{}
            if ($target.Arguments) {
                $args.ArgumentList = $target.Arguments
            }
            if ($target.WorkingDirectory -and (Test-Path -LiteralPath $target.WorkingDirectory)) {
                $args.WorkingDirectory = $target.WorkingDirectory
            }
            Start-Process -FilePath $target.Target -WindowStyle Minimized @args | Out-Null
            return
        }
    }

    $exe = "C:\Program Files\SakuraFrpLauncher\SakuraLauncher.exe"
    if (Test-Path -LiteralPath $exe) {
        Write-Host "starting SakuraFRP..."
        Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -WindowStyle Minimized | Out-Null
        return
    }
    throw "SakuraFRP launcher not found."
}

function Test-WatchdogRunning {
    return [bool](Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -in @("py.exe", "python.exe", "pythonw.exe") -and
        $_.CommandLine -like "*host_watchdog.py*watchdog-loop*"
    } | Select-Object -First 1)
}

function Start-Watchdog {
    if (Test-WatchdogRunning) {
        Write-Host "base watchdog already running"
        return
    }

    $watchdogDir = "C:\$([char]0x7CFB)$([char]0x7EDF)$([char]0x811A)$([char]0x672C)\$([char]0x57FA)$([char]0x7840)$([char]0x76D1)$([char]0x63A7)"
    $watchdogBat = Join-Path $watchdogDir "4_watchdog_loop.bat"
    if (-not (Test-Path -LiteralPath $watchdogBat)) {
        throw "Base watchdog launcher not found: $watchdogBat"
    }

    Write-Host "starting base watchdog..."
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", $watchdogBat) `
        -WorkingDirectory $watchdogDir -WindowStyle Hidden | Out-Null
}

Write-Host "starting Hermi + Hermes + QLOS + NapCat..."
& (Join-Path $PSScriptRoot "start_hermi_all.ps1")

Start-OpenWebUI
Start-SakuraFrp
Start-Watchdog

$okHermi = Wait-Port 8789 5
$okHermes = Wait-Port 8642 5
$okQlos = Wait-Port 8766 5
$okNapCat = Wait-Port 3000 5
$okOpenWebUI = $false
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    if (Test-OpenWebUI) {
        $okOpenWebUI = $true
        break
    }
    Start-Sleep -Seconds 1
}
$okWatchdog = $false
$watchdogDeadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $watchdogDeadline) {
    if (Test-WatchdogRunning) {
        $okWatchdog = $true
        break
    }
    Start-Sleep -Milliseconds 500
}
$sakura = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "SakuraLauncher.exe" -or $_.CommandLine -like "*SakuraFrpLauncher*"
} | Select-Object -First 1

$statusFile = Join-Path $StateDir "all_6_runtime.txt"
@"
ALL-start status (7 services)
HERMI=http://127.0.0.1:8789
HERMES=http://127.0.0.1:8642
QLOS=http://127.0.0.1:8766
NAPCAT=http://127.0.0.1:3000
OPEN_WEBUI=http://127.0.0.1:8080
SAKURA_FRP=$([bool]$sakura)
WATCHDOG=$okWatchdog
LOG_DIR=$LogDir
"@ | Set-Content -LiteralPath $statusFile -Encoding UTF8

Write-Host ""
Write-Host "ALL-start status:"
Write-Host "Hermi      8789: $okHermi"
Write-Host "Hermes     8642: $okHermes"
Write-Host "QLOS       8766: $okQlos"
Write-Host "NapCat     3000: $okNapCat"
Write-Host "Open WebUI 8080: $okOpenWebUI"
Write-Host "SakuraFRP      : $([bool]$sakura)"
Write-Host "Watchdog       : $okWatchdog"
Write-Host "runtime: $statusFile"

if ($OpenHermi -and $okHermi) {
    Start-Process "http://127.0.0.1:8789"
}

if (-not ($okHermi -and $okHermes -and $okQlos -and $okNapCat -and $okOpenWebUI -and $sakura -and $okWatchdog)) {
    exit 1
}

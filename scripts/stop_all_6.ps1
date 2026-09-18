param(
    [switch]$StopQQ
)

$ErrorActionPreference = "Continue"
$selfPid = $PID

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

function Stop-ProcessTree([int]$ProcessId, [string]$Label) {
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Host "stopped $Label $ProcessId"
        return
    } catch {
        Write-Host "Stop-Process failed for $Label ${ProcessId}: $($_.Exception.Message)"
    }
    try {
        & taskkill.exe /PID $ProcessId /T /F | Out-Host
    } catch {
        Write-Host "taskkill failed for $Label ${ProcessId}: $($_.Exception.Message)"
    }
}

Write-Host "stopping Hermi + Hermes + QLOS + NapCat..."
& (Join-Path $PSScriptRoot "stop_hermi_all.ps1") @PSBoundParameters

$leftoverTargets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $selfPid -and (
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*hermi_gateway.app*") -or
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*qlos_lite.onebot_server*") -or
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*hermes_cli.main*gateway*") -or
        ($_.CommandLine -like "*hermes.exe* gateway*")
    )
}
foreach ($proc in $leftoverTargets) {
    Stop-ProcessTree ([int]$proc.ProcessId) "$($proc.Name)"
}

$napcatTargets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $selfPid -and ($_.Name -eq "NapCatWinBootMain.exe" -or $_.CommandLine -like "*NapCat*")
}
foreach ($proc in $napcatTargets) {
    Stop-ProcessTree ([int]$proc.ProcessId) "$($proc.Name)"
}

Write-Host "stopping Open WebUI..."
$targets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $selfPid -and (
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*open-webui*" -and $_.CommandLine -like "*serve*") -or
        ($_.Name -in @("uv.exe", "uvx.exe") -and $_.CommandLine -like "*open-webui*") -or
        ($_.Name -in @("powershell.exe", "pwsh.exe") -and $_.CommandLine -like "*Start-OpenWebUI.ps1*") -or
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*hermes_cli.main*gateway*")
    )
}
foreach ($proc in $targets) {
    Stop-ProcessTree ([int]$proc.ProcessId) "$($proc.Name)"
}

Write-Host "stopping SakuraFRP..."
try {
    & (Join-Path $PSScriptRoot "stop_hermi_frp.ps1")
} catch {
    Write-Host "Hermi FRP stop skipped: $($_.Exception.Message)"
}

$frpTargets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $selfPid -and (
        $_.Name -eq "SakuraLauncher.exe" -or
        $_.CommandLine -like "*SakuraFrpLauncher*" -or
        ($_.Name -in @("frpc.exe", "natfrp.exe") -and ($_.CommandLine -like "*Sakura*" -or $_.CommandLine -like "*natfrp*"))
    )
}
foreach ($proc in $frpTargets) {
    Stop-ProcessTree ([int]$proc.ProcessId) "$($proc.Name)"
}

Write-Host "stopping base watchdog..."
$watchdogTargets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $selfPid -and (
        $_.CommandLine -like "*host_watchdog.py*watchdog-loop*" -or
        $_.CommandLine -like "*4_watchdog_loop.bat*"
    )
}
foreach ($proc in $watchdogTargets) {
    Stop-ProcessTree ([int]$proc.ProcessId) "$($proc.Name)"
}

Start-Sleep -Seconds 1
Write-Host ""
Write-Host "ALL-stop port status:"
foreach ($item in @(
    @{Name = "Hermi"; Port = 8789},
    @{Name = "Hermes"; Port = 8642},
    @{Name = "QLOS"; Port = 8766},
    @{Name = "NapCat"; Port = 3000},
    @{Name = "Open WebUI"; Port = 8080}
)) {
    $open = Test-PortOpen ([int]$item.Port)
    Write-Host ("{0} {1}: {2}" -f $item.Name, $item.Port, $(if ($open) { "open" } else { "closed" }))
}

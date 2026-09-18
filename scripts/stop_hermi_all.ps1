param(
    [switch]$StopQQ
)

$ErrorActionPreference = "Continue"

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

$selfPid = $PID
$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $selfPid -and (
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*hermi_gateway.app*") -or
        ($_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*qlos_lite.onebot_server*") -or
        ($_.CommandLine -like "*hermes.exe* gateway*") -or
        ($_.Name -eq "NapCatWinBootMain.exe") -or
        ($StopQQ -and $_.Name -in @("QQ.exe", "QQEX.exe"))
    )
}

if (-not $targets) {
    Write-Host "No Hermi all stack processes found."
} else {
    foreach ($proc in $targets) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "stopped $($proc.Name) $($proc.ProcessId)"
        } catch {
            Write-Host "failed $($proc.Name) $($proc.ProcessId): $($_.Exception.Message)"
        }
    }
}

Start-Sleep -Seconds 1
Write-Host ""
Write-Host "port status:"
foreach ($item in @(
    @{Name = "Hermi"; Port = 8789},
    @{Name = "Hermes"; Port = 8642},
    @{Name = "QLOS"; Port = 8766},
    @{Name = "NapCat"; Port = 3000}
)) {
    $open = Test-PortOpen ([int]$item.Port)
    Write-Host ("{0} {1}: {2}" -f $item.Name, $item.Port, $(if ($open) { "open" } else { "closed" }))
}

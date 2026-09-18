param([string]$ConfigPath = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $ConfigPath) {
    $local = Join-Path $Root "frp\frpc.hermi.local.toml"
    $ConfigPath = if (Test-Path -LiteralPath $local) { $local } else { Join-Path $Root "frp\frpc.hermi.example.toml" }
}
$text = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8
$ports = [regex]::Matches($text, '(?m)^\s*localPort\s*=\s*(\d+)\s*$') | ForEach-Object { [int]$_.Groups[1].Value }
if (-not $ports -or $ports.Count -ne 1 -or $ports[0] -ne 8789) {
    throw "Forbidden local port. Hermi FRP config must expose only localPort 8789."
}
if ($text -notmatch '(?m)^\s*localIP\s*=\s*"127\.0\.0\.1"\s*$') { throw 'localIP must be "127.0.0.1".' }
foreach ($forbidden in 3000, 8642, 8643, 8644, 8766) {
    if ($ports -contains $forbidden) { throw "Forbidden local port: $forbidden" }
}
Write-Host "FRP config safety check passed: only 127.0.0.1:8789 is exposed."

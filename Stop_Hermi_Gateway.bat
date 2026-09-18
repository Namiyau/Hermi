@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_hermi_gateway.ps1"
echo.
echo Press any key to close.
pause >nul
endlocal


@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_hermi_gateway.ps1"
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Hermi Gateway exited with code %EXITCODE%.
  echo Check the message above, then press any key to close.
  pause >nul
)
endlocal


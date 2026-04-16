@echo off
:: Check for admin rights (needed for Task Scheduler)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator rights...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
echo Starting Claude Usage Monitor installer...
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"

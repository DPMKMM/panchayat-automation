@echo off
TITLE e-Panchayat 1-Click Complete Installer & Launcher (Windows 11 Pro)
COLOR 0A

:: Self-elevate to Administrator with single UAC click
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Requesting Administrator privileges for 1-Click setup...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat Automated Portal - 1-Click Setup ^& Launch
echo    Target Environment: Windows 11 Pro / Windows 10 (64-bit)
echo =====================================================================
echo.
echo [*] Installing dependencies, configuring 24/7 power, and starting server...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup_Office_Desktop.ps1" -AutoStartServer

exit /b

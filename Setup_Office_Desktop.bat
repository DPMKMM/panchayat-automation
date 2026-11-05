@echo off
TITLE e-Panchayat Office Desktop 1-Click Installer (Windows 11 Pro)
COLOR 0B

echo =====================================================================
echo    e-Panchayat Automated Portal - 1-Click Office Desktop Setup
echo    Target Environment: Windows 11 Pro / Windows 10 (64-bit)
echo =====================================================================
echo.

:: Check for Administrator privileges and auto-elevate seamlessly
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Administrator privileges required. Requesting elevation...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo [*] Launching automated 1-Click setup and server launch...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup_Office_Desktop.ps1" -AutoStartServer

exit /b

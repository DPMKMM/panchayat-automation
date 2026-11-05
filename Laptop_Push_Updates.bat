@echo off
TITLE Laptop to Office System - 1-Click Code Push
COLOR 0B

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat: Push Latest Code from Laptop to Office Desktop
echo =====================================================================
echo.

echo [*] Checking modified files...
git status -s
echo.

set "MSG="
set /p MSG="Enter update description (or press Enter for auto-timestamp): "

if "%MSG%"=="" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
    set "MSG=Update from laptop %DATE% %TIME%"
)

echo.
echo [*] Staging all changes...
git add .

echo [*] Committing changes: "%MSG%"...
git commit -m "%MSG%"

echo [*] Pushing to GitHub (origin main)...
git push origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =====================================================================
    echo  🎉 SUCCESS! Updates pushed to GitHub repository!
    echo.
    echo  Your Office Desktop (Windows 11 Pro) will automatically:
    echo    1. Detect these new commits within 60 seconds
    echo    2. Run 'git pull origin main'
    echo    3. Refresh the live website and background services
    echo =====================================================================
) else (
    echo.
    echo [ERROR] Git push failed. Please verify your internet connection or GitHub credentials.
)

echo.
pause

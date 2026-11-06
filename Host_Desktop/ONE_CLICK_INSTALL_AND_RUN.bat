@echo off
title Telangana ePanchayat - One-Click Office Desktop Installer
cd /d "%~dp0"
cls

echo =====================================================================
echo   Telangana ePanchayat Portal - One-Click Desktop Host Installer
echo   Target Location: D:\DPM-ept
echo   Domain: https://www.panchayatautomation.in
echo =====================================================================
echo.

:: 1. Verify D: drive exists
if not exist "D:\" (
    echo [ERROR] Drive D:\ not detected on this system!
    echo Please make sure your D: drive is accessible.
    pause
    exit /b 1
)

:: 2. Check if D:\DPM-ept exists; clone or pull
if not exist "D:\DPM-ept" (
    echo [*] Creating D:\DPM-ept and cloning latest repository...
    git clone https://github.com/DPMKMM/panchayat-automation.git "D:\DPM-ept"
    if errorlevel 1 (
        echo [ERROR] Git clone failed. Please ensure Git is installed.
        pause
        exit /b 1
    )
) else (
    echo [*] D:\DPM-ept already exists. Pulling latest code updates...
    cd /d "D:\DPM-ept"
    git pull origin main
)

cd /d "D:\DPM-ept"

:: 3. Copy host runner scripts into D:\DPM-ept
if exist "%~dp0Start_Office_Host_Hidden.vbs" copy /y "%~dp0Start_Office_Host_Hidden.vbs" "D:\DPM-ept\" >nul
if exist "%~dp0run_silent.bat" copy /y "%~dp0run_silent.bat" "D:\DPM-ept\" >nul
if exist "%~dp0auto_sync_live.bat" copy /y "%~dp0auto_sync_live.bat" "D:\DPM-ept\" >nul
if exist "%~dp0Stop_Office_Host.bat" copy /y "%~dp0Stop_Office_Host.bat" "D:\DPM-ept\" >nul
if exist "%~dp0Check_Office_Host_Status.bat" copy /y "%~dp0Check_Office_Host_Status.bat" "D:\DPM-ept\" >nul

:: 4. Write permanent .env credentials
echo [*] Configuring D:\DPM-ept\.env with permanent Cloudflare token...
(
    echo WEB_SESSION_SECRET=b71c84f509e5bca393c5d888f4c2810ab512a863d0859339e1a10ebf19a3b6d2
    echo DATA_DIR=./data
    echo MAX_UPLOAD_BYTES=31457280
    echo LOG_LEVEL=INFO
    echo CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiOTFjZWUxYjY3ZGY5MzYwNzZlZDg1NDI5MGIxZTgwNTMiLCJ0IjoiZTU3ZmZkZTgtZGRjYy00NTI4LTg2NTUtNjhmZmEwOWUwMjIyIiwicyI6Ik1qQmxORFV5TXpJdFpESTJZUzAwWWpFeUxXSmxObVl0WmpaaU9UTTNaakk0WTJaaCJ9
    echo CUSTOM_DOMAIN=panchayatautomation.in
) > "D:\DPM-ept\.env"

:: 5. Create storage directories
if not exist "data\reports" mkdir "data\reports"
if not exist "data\sessions" mkdir "data\sessions"

:: 6. Setup Python virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up Python virtual environment in D:\DPM-ept\.venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python not found in PATH! Please install Python 3.10+.
        pause
        exit /b 1
    )
    echo [*] Installing dependencies from requirements.txt...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\pip.exe install -r requirements.txt
    echo [*] Installing Playwright Chromium browser...
    .\.venv\Scripts\playwright.exe install chromium
)

:: 7. Create Desktop shortcut for 1-click silent start
echo [*] Creating Desktop shortcut: 'Start ePanchayat Portal (Background)'...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), 'Start ePanchayat Portal (Background).lnk')); $s.TargetPath = 'D:\DPM-ept\Start_Office_Host_Hidden.vbs'; $s.WorkingDirectory = 'D:\DPM-ept'; $s.Save()"

echo.
echo =====================================================================
echo   SUCCESS! ONE-CLICK INSTALLATION COMPLETE!
echo   Location: D:\DPM-ept
echo   A desktop shortcut has been created:
echo   'Start ePanchayat Portal (Background)'
echo =====================================================================
echo.
echo Launching the portal silently in the background now...
cscript //nologo "D:\DPM-ept\Start_Office_Host_Hidden.vbs"

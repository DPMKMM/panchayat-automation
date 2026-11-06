@echo off
title Telangana ePanchayat - Setup Office Desktop (D:\DPM-ept)
cls

echo =====================================================================
echo   Telangana ePanchayat Portal - Office Desktop Setup
echo   Target Directory: D:\DPM-ept
echo   Domain: https://www.panchayatautomation.in
echo =====================================================================
echo.

:: 1. Ensure D: drive exists
if not exist "D:\" (
    echo [ERROR] Drive D:\ not found on this computer!
    pause
    exit /b 1
)

:: 2. Check if D:\DPM-ept already exists
if not exist "D:\DPM-ept" (
    echo [*] Creating D:\DPM-ept and cloning latest repository from GitHub...
    git clone https://github.com/DPMKMM/panchayat-automation.git "D:\DPM-ept"
    if errorlevel 1 (
        echo [ERROR] Failed to clone repository! Please ensure Git is installed.
        pause
        exit /b 1
    )
) else (
    echo [*] D:\DPM-ept already exists. Pulling latest updates from GitHub...
    cd /d "D:\DPM-ept"
    git pull origin main
)

cd /d "D:\DPM-ept"

:: 3. Setup .env with permanent Cloudflare Tunnel token
echo [*] Writing permanent credentials into D:\DPM-ept\.env...
(
    echo WEB_SESSION_SECRET=b71c84f509e5bca393c5d888f4c2810ab512a863d0859339e1a10ebf19a3b6d2
    echo DATA_DIR=./data
    echo MAX_UPLOAD_BYTES=31457280
    echo LOG_LEVEL=INFO
    echo CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiOTFjZWUxYjY3ZGY5MzYwNzZlZDg1NDI5MGIxZTgwNTMiLCJ0IjoiZTU3ZmZkZTgtZGRjYy00NTI4LTg2NTUtNjhmZmEwOWUwMjIyIiwicyI6Ik1qQmxORFV5TXpJdFpESTJZUzAwWWpFeUxXSmxObVl0WmpaaU9UTTNaakk0WTJaaCJ9
    echo CUSTOM_DOMAIN=panchayatautomation.in
) > "D:\DPM-ept\.env"

:: 4. Create data directories
if not exist "data\reports" mkdir "data\reports"
if not exist "data\sessions" mkdir "data\sessions"

:: 5. Setup Python Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up Python virtual environment (.venv)...
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\pip.exe install -r requirements.txt
    .\.venv\Scripts\playwright.exe install chromium
)

:: 6. Create Desktop Shortcut for 1-click Hidden Launch
echo [*] Creating Desktop shortcut 'Start ePanchayat Portal (Background)'...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), 'Start ePanchayat Portal (Background).lnk')); $s.TargetPath = 'D:\DPM-ept\Start_Office_Host_Hidden.vbs'; $s.WorkingDirectory = 'D:\DPM-ept'; $s.Save()"

echo.
echo =====================================================================
echo   SETUP COMPLETE!
echo   Location: D:\DPM-ept
echo   Desktop shortcut created: 'Start ePanchayat Portal (Background)'
echo =====================================================================
echo.
echo Launching portal now in silent background mode...
cscript //nologo "D:\DPM-ept\Start_Office_Host_Hidden.vbs"

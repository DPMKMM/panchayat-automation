@echo off
title Telangana ePanchayat - Permanent Office Host & Auto-Sync
cd /d "%~dp0"
cls

echo =====================================================================
echo   Telangana ePanchayat Portal - Office Desktop Permanent Host
echo   Permanent Domain: https://panchayatautomation.in
echo =====================================================================
echo.

:: 1. Auto-generate .env with permanent Cloudflare Tunnel token if not present
if not exist ".env" (
    echo [*] Generating .env configuration...
    (
        echo WEB_SESSION_SECRET=b71c84f509e5bca393c5d888f4c2810ab512a863d0859339e1a10ebf19a3b6d2
        echo DATA_DIR=./data
        echo MAX_UPLOAD_BYTES=31457280
        echo LOG_LEVEL=INFO
        echo CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiOTFjZWUxYjY3ZGY5MzYwNzZlZDg1NDI5MGIxZTgwNTMiLCJ0IjoiZTU3ZmZkZTgtZGRjYy00NTI4LTg2NTUtNjhmZmEwOWUwMjIyIiwicyI6Ik1qQmxORFV5TXpJdFpESTJZUzAwWWpFeUxXSmxObVl0WmpaaU9UTTNaakk0WTJaaCJ9
        echo CUSTOM_DOMAIN=panchayatautomation.in
    ) > ".env"
    echo [+] .env created successfully.
)

:: 2. Auto-create data directories
if not exist "data\reports" mkdir "data\reports"
if not exist "data\sessions" mkdir "data\sessions"

:: 3. Setup Python Virtual Environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up Python virtual environment (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+ from python.org
        pause
        exit /b 1
    )
    echo [*] Installing dependencies from requirements.txt...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\pip.exe install -r requirements.txt
    echo [*] Installing Playwright Chromium browser...
    .\.venv\Scripts\playwright.exe install chromium
    echo [+] Environment setup complete!
)

:: 4. Pull latest updates from GitHub before starting
echo [*] Checking for latest code updates from GitHub (main)...
git pull origin main

:: 5. Launch Git Auto-Sync Watcher in a minimized background window
echo [*] Starting Git Auto-Sync Watcher (auto-pulls laptop updates every 60s)...
start "Git Auto-Sync Watcher" /min cmd /c "auto_sync_live.bat"

:: 6. Launch Cloudflare Tunnel and Local Uvicorn Portal
echo.
echo =====================================================================
echo   Connecting https://panchayatautomation.in to local port 8000...
echo   Keep this window OPEN while hosting the portal!
echo =====================================================================
echo.

.\.venv\Scripts\python.exe run_cloudflare_portal.py
pause

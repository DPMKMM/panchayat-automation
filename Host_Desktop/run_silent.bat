@echo off
setlocal
cd /d "D:\DPM-ept"

:: 1. Auto-generate .env with permanent Cloudflare Tunnel token if not present
if not exist ".env" (
    (
        echo WEB_SESSION_SECRET=b71c84f509e5bca393c5d888f4c2810ab512a863d0859339e1a10ebf19a3b6d2
        echo DATA_DIR=./data
        echo MAX_UPLOAD_BYTES=31457280
        echo LOG_LEVEL=INFO
        echo CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiOTFjZWUxYjY3ZGY5MzYwNzZlZDg1NDI5MGIxZTgwNTMiLCJ0IjoiZTU3ZmZkZTgtZGRjYy00NTI4LTg2NTUtNjhmZmEwOWUwMjIyIiwicyI6Ik1qQmxORFV5TXpJdFpESTJZUzAwWWpFeUxXSmxObVl0WmpaaU9UTTNaakk0WTJaaCJ9
        echo CUSTOM_DOMAIN=panchayatautomation.in
    ) > ".env"
)

:: 2. Auto-create data directories
if not exist "data\reports" mkdir "data\reports"
if not exist "data\sessions" mkdir "data\sessions"

:: 3. Setup Python Virtual Environment if missing
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\pip.exe install -r requirements.txt
    .\.venv\Scripts\playwright.exe install chromium
)

:: 4. Start Git Auto-Sync Watcher in hidden mode (pulls laptop commits every 60s)
if exist "auto_sync_live.bat" (
    powershell -WindowStyle Hidden -Command "Start-Process cmd -ArgumentList '/c auto_sync_live.bat' -WindowStyle Hidden"
)

:: 5. Launch Cloudflare Tunnel and Uvicorn Portal
.\.venv\Scripts\python.exe run_cloudflare_portal.py

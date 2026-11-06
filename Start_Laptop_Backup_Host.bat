@echo off
title Telangana ePanchayat - Laptop Standby Backup Host
cd /d "%~dp0"
cls

echo =====================================================================
echo   Telangana ePanchayat Portal - Laptop Standby Backup Host
echo   Permanent Domain: https://www.panchayatautomation.in
echo =====================================================================
echo.
echo [*] Checking environment on Laptop...

:: 1. Ensure .env has credentials
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
)

:: 2. Pull latest git code
echo [*] Pulling latest updates from GitHub (main)...
git pull origin main

:: 3. Launch portal and connect redundant Cloudflare Tunnel replica
echo.
echo =====================================================================
echo   STANDBY BACKUP SERVER IS NOW RUNNING!
echo   Connected to Cloudflare edge as a redundant failover replica.
echo   If office internet drops, all traffic automatically routes here!
echo   Keep this window open while providing backup coverage.
echo =====================================================================
echo.

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" set PYTHON_CMD=.venv\Scripts\python.exe

%PYTHON_CMD% run_cloudflare_portal.py
pause

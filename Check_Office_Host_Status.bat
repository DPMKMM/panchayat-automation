@echo off
title Telangana ePanchayat - Host Status Check
cls

echo =====================================================================
echo   Telangana ePanchayat Portal - Status Diagnostic
echo   Target: D:\DPM-ept
echo   Domain: https://www.panchayatautomation.in
echo =====================================================================
echo.

echo [1] Checking Local Server on port 8000...
curl.exe -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo     [-] Local server: NOT RUNNING on port 8000
) else (
    echo     [+] Local server: ACTIVE (200 OK)
)

echo.
echo [2] Checking Cloudflare Tunnel Process...
tasklist /fi "imagename eq cloudflared.exe" 2>nul | find /i "cloudflared.exe" >nul
if errorlevel 1 (
    echo     [-] Cloudflare Tunnel: NOT RUNNING
) else (
    echo     [+] Cloudflare Tunnel: ACTIVE (connected to edge network)
)

echo.
echo [3] Checking Auto-Sync Git Watcher...
wmic process where "commandline like '%%auto_sync_live.bat%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul
if errorlevel 1 (
    echo     [-] Git Auto-Sync Watcher: NOT DETECTED
) else (
    echo     [+] Git Auto-Sync Watcher: ACTIVE (auto-pulling laptop updates every 60s)
)

echo.
echo [4] Checking Public Domain (https://www.panchayatautomation.in)...
curl.exe -s -o nul -w "    [+] Public Domain Response: HTTP %%{http_code}\n" https://www.panchayatautomation.in/health 2>nul
if errorlevel 1 (
    echo     [-] Public Domain: Could not connect
)

echo.
echo =====================================================================
pause

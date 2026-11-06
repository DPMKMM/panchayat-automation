@echo off
title Telangana ePanchayat - Stop Background Host
cls

echo =====================================================================
echo   Stopping Telangana ePanchayat Portal & Cloudflare Tunnel
echo   Location: D:\DPM-ept
echo =====================================================================
echo.

echo [*] Terminating Cloudflare Tunnel process...
taskkill /F /IM "cloudflared.exe" >nul 2>&1

echo [*] Terminating local server on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [*] Terminating Auto-Sync Git Watcher...
wmic process where "commandline like '%%auto_sync_live.bat%%'" call terminate >nul 2>&1

echo.
echo [+] Background portal and tunnel stopped cleanly.
echo.
pause

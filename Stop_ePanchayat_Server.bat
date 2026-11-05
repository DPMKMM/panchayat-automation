@echo off
TITLE Stop e-Panchayat Background Services
COLOR 0C

cd /d "%~dp0"

echo =====================================================================
echo           Stopping e-Panchayat Background Services...
echo =====================================================================
echo.

:: 1. Stop Cloudflare Tunnel
echo [*] Terminating Cloudflare tunnel...
taskkill /F /IM cloudflared.exe >nul 2>&1

:: 2. Stop Auto-Sync Daemon
echo [*] Terminating Auto-Sync daemon...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*auto_sync_office.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

:: 3. Stop Uvicorn on Port 8000
echo [*] Terminating Uvicorn web server...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo =====================================================================
echo  [+] All e-Panchayat background services have been stopped.
echo =====================================================================
echo.
timeout /t 3 >nul

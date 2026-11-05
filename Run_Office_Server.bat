@echo off
TITLE e-Panchayat Automated Portal - Office Host Service
COLOR 0A

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat Automated Console ^& Reporting Server (Office Host)
echo    Windows 11 Pro Master Server + Online Gateway + Auto-Sync
echo =====================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: 1. Launch Auto-Sync Watcher in a background minimized window
echo [1/2] Starting background Auto-Sync Watcher (checks GitHub for laptop updates)...
start "e-Panchayat Auto-Sync" /min "%PY_CMD%" auto_sync_office.py

:: 2. Launch Cloudflare Public Gateway and Uvicorn Server
echo [2/2] Launching Uvicorn server and Cloudflare Public Tunnel...
echo.
"%PY_CMD%" run_cloudflare_portal.py

pause

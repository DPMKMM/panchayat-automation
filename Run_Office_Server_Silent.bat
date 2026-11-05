@echo off
TITLE e-Panchayat Background Host Launcher
cd /d "%~dp0"

:: Ensure logs directory exists
if not exist "data\logs" mkdir "data\logs"

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: 1. Launch Auto-Sync Daemon silently
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%PY_CMD%' -ArgumentList 'auto_sync_office.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput 'data\logs\autosync.log' -RedirectStandardError 'data\logs\autosync_err.log'"

:: 2. Launch Cloudflare Tunnel and Uvicorn Portal silently
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%PY_CMD%' -ArgumentList 'run_cloudflare_portal.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput 'data\logs\cloudflare.log' -RedirectStandardError 'data\logs\cloudflare_err.log'"

exit /b

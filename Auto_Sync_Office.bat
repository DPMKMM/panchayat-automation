@echo off
TITLE e-Panchayat Background Auto-Sync Watcher
COLOR 0E

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat Office Desktop - Automatic GitHub Sync Watcher
echo    Checks for laptop commits every 60 seconds and auto-updates.
echo =====================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" auto_sync_office.py
pause

@echo off
TITLE Telangana Panchayat Raj - Automated DSR Portal & Public Gateway
COLOR 0A

cd /d "%~dp0"

echo =====================================================================
echo    Telangana Panchayat Raj - Automated DSR Portal ^& Public Gateway
echo    Starting local server and generating single clean Public URL...
echo =====================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" run_cloudflare_portal.py
pause

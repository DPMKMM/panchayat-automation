@echo off
TITLE e-Panchayat Manual Update and Background Restart
COLOR 0E

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat: Pull Updates ^& Restart in Background (Office Desktop)
echo =====================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

echo [1/3] Pulling latest code from GitHub...
git pull origin main

echo.
echo [2/3] Checking requirements...
"%PY_CMD%" -m pip install -r requirements.txt --quiet

echo.
echo [3/3] Stopping previous background services...
call Stop_ePanchayat_Server.bat >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo =====================================================================
echo  Update completed! Launching silently in background...
echo =====================================================================
wscript.exe "%~dp0Start_ePanchayat_Background.vbs"

echo  [+] Server running silently in background.
timeout /t 3 >nul

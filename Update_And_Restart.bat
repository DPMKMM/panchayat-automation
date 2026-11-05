@echo off
TITLE e-Panchayat Force Update & Background Restart
COLOR 0E

cd /d "%~dp0"

echo =====================================================================
echo    e-Panchayat: Force Synchronize Updates with GitHub ^& Restart
echo =====================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

echo [1/5] Configuring Git environment and removing stale locks...
git config --global --add safe.directory "*" >nul 2>&1
git config safe.directory "*" >nul 2>&1
if exist ".git\index.lock" del /f /q ".git\index.lock" >nul 2>&1
if exist ".git\FETCH_HEAD.lock" del /f /q ".git\FETCH_HEAD.lock" >nul 2>&1

echo.
echo [2/5] Fetching latest commits from GitHub (origin/main)...
git fetch --all --prune
if %ERRORLEVEL% NEQ 0 (
    echo [!] Warning: git fetch reported an issue, trying direct origin fetch...
    git fetch origin main
)

echo.
echo [3/5] Force-aligning local repository with GitHub main branch...
git reset --hard origin/main

echo.
echo [4/5] Verifying dependencies...
"%PY_CMD%" -m pip install -r requirements.txt --quiet

echo.
echo [5/5] Stopping previous background services and restarting fresh...
call Stop_ePanchayat_Server.bat >nul 2>&1
timeout /t 2 /nobreak >nul

wscript.exe "%~dp0Start_ePanchayat_Background.vbs"

echo.
echo =====================================================================
echo  [+] SUCCESS! Code synchronized to latest commit:
git rev-parse --short HEAD
echo  [+] Server running silently in background.
echo =====================================================================
echo.
timeout /t 5

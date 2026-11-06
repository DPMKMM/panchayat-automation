@echo off
title Telangana ePanchayat - Git Auto-Sync Watcher
cd /d "%~dp0"

echo ========================================================
echo   Auto-Sync Git Watcher Active
echo   Auto-pulling latest laptop updates every 60 seconds...
echo ========================================================

:loop
git fetch origin main >nul 2>&1
for /f %%i in ('git rev-parse HEAD') do set LOCAL_HASH=%%i
for /f %%i in ('git rev-parse origin/main') do set REMOTE_HASH=%%i

if not "%LOCAL_HASH%"=="%REMOTE_HASH%" (
    echo [%DATE% %TIME%] New update detected from GitHub! Pulling changes...
    git pull origin main
    echo [%DATE% %TIME%] Code updated! Uvicorn reloads automatically.
)

timeout /t 60 /nobreak >nul
goto loop

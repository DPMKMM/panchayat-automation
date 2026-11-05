@echo off
TITLE Force Git Sync to Latest Commit
COLOR 0A

cd /d "%~dp0"

echo =====================================================================
echo       e-Panchayat: Immediate Force Sync to Latest GitHub Commit
echo =====================================================================
echo.

echo [*] Removing any OneDrive or Git locks...
if exist ".git\index.lock" del /f /q ".git\index.lock" >nul 2>&1
if exist ".git\FETCH_HEAD.lock" del /f /q ".git\FETCH_HEAD.lock" >nul 2>&1
if exist ".git\refs\remotes\origin\main.lock" del /f /q ".git\refs\remotes\origin\main.lock" >nul 2>&1

echo [*] Setting Git safe directory...
git config --global --add safe.directory "*"
git config safe.directory "*"

echo [*] Fetching from GitHub...
git fetch origin main

echo [*] Resetting to latest commit...
git reset --hard origin/main

echo.
echo =====================================================================
echo  Current commit is now:
git log -n 1 --oneline
echo =====================================================================
echo.
echo You can now close this window or launch Start_ePanchayat_Server.bat!
echo.
pause

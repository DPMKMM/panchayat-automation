@echo off
title Telangana ePanchayat Portal - Permanent Host
cd /d "%~dp0"

echo ========================================================
echo   Starting Telangana ePanchayat Permanent Host
echo   Domain: https://panchayatautomation.in
echo ========================================================

:: 1. Start Auto-Sync Git Watcher in background
start "Git Auto-Sync Watcher" /min cmd /c "auto_sync_live.bat"

:: 2. Launch Cloudflare Tunnel & Uvicorn Portal
set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" set PYTHON_CMD=.venv\Scripts\python.exe

%PYTHON_CMD% run_cloudflare_portal.py
pause

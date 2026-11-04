@echo off
title Telangana Panchayat Raj - Automated DSR Portal
cd /d "%~dp0"
set "DATA_DIR=%~dp0data"
set "PYTHONDONTWRITEBYTECODE=1"
echo ===================================================================
echo   Telangana Panchayat Raj - Automated DSR Portal
echo   Launching local server with Real-Time e-Panchayat Browser Robot...
echo ===================================================================
echo.
echo Starting server on http://localhost:8000/naresh ...
start "" "http://localhost:8000/naresh"
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
pause

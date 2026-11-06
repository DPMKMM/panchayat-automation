@echo off
title Telangana ePanchayat Portal - Local Server
cd /d "%~dp0"

echo ========================================================
echo   Starting Telangana ePanchayat Portal (Modular 4.0)
echo   Modules: DSR Attendance, House Tax DCB, GP Balance
echo ========================================================

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" set PYTHON_CMD=.venv\Scripts\python.exe
if exist "..\EPT_AUTOMATION\.venv\Scripts\python.exe" set PYTHON_CMD=..\EPT_AUTOMATION\.venv\Scripts\python.exe

%PYTHON_CMD% -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause

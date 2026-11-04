@echo off
TITLE e-Panchayat Automated Console Server
COLOR 0A

echo =====================================================================
echo           e-Panchayat Automated Console ^& Reporting Server
echo =====================================================================
echo.
echo [1/3] Navigating to project workspace...
cd /d "%~dp0"
set "DATA_DIR=%~dp0data"
set "PYTHONDONTWRITEBYTECODE=1"

echo [2/3] Checking Python virtual environment...
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    echo Virtual environment detected: .venv
) else (
    set "PY_CMD=python"
    echo Using system Python.
)

echo [3/3] Launching web browser (http://127.0.0.1:8000/) ...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000/"

echo.
echo =====================================================================
echo Server starting at http://127.0.0.1:8000 ...
echo Real-time attendance, DSR, Balance Entry, and DCB Analytics active.
echo Press Ctrl+C in this window anytime to stop the server.
echo =====================================================================
echo.

"%PY_CMD%" -m uvicorn app:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server terminated unexpectedly with exit code %ERRORLEVEL%.
    pause
)

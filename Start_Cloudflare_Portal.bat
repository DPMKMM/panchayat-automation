@echo off
title Telangana ePanchayat Portal - Cloudflare Public Access
cd /d "%~dp0"

echo ========================================================
echo   Launching ePanchayat Portal via Cloudflare Tunnel
echo ========================================================

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" set PYTHON_CMD=.venv\Scripts\python.exe

%PYTHON_CMD% run_cloudflare_portal.py
pause

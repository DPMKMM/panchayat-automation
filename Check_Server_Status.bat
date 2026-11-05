@echo off
TITLE e-Panchayat Host Server - Background Status Check
COLOR 0B

cd /d "%~dp0"

echo =====================================================================
echo           e-Panchayat Host Server - Live Background Status
echo =====================================================================
echo.

:: 1. Check Port 8000 (Uvicorn Server)
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [1] Uvicorn Web Server   :  [ ACTIVE - Running on Port 8000 ]
) else (
    echo  [1] Uvicorn Web Server   :  [ STOPPED / NOT LISTENING ]
)

:: 2. Check Cloudflare Tunnel
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | findstr /I /C:"cloudflared.exe" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [2] Cloudflare Gateway   :  [ ACTIVE - Online Tunnel Connected ]
) else (
    echo  [2] Cloudflare Gateway   :  [ STOPPED ]
)

:: 3. Check Auto-Sync Daemon
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*auto_sync_office.py*' } | Select-Object -First 1" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [3] Auto-Sync Daemon     :  [ ACTIVE - Checking GitHub every 60s ]
) else (
    echo  [3] Auto-Sync Daemon     :  [ STOPPED ]
)

:: 4. Check Active User Sessions
powershell -NoProfile -Command ^
    "$ProgressPreference = 'SilentlyContinue'; try { " ^
    "   $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/system/sessions' -TimeoutSec 2; " ^
    "   Write-Host (' [4] Active User Sessions :  [' + $r.total_sessions + ' Total Session(s) | ' + $r.authenticated_sessions + ' Authenticated Officer(s) ]') -ForegroundColor Green; " ^
    "   foreach ($s in $r.sessions) { " ^
    "       $user = if ($s.user_id) { $s.user_id } else { 'Guest' }; " ^
    "       $st = if ($s.authenticated) { 'Authenticated' } elseif ($s.status -eq 'awaiting_otp') { 'Awaiting OTP' } else { 'Idle' }; " ^
    "       Write-Host ('       * Officer: ' + $user + ' | Status: ' + $st + ' | Active: ' + $s.age_minutes + ' min | Session: ' + $s.session_id_short) -ForegroundColor Cyan; " ^
    "   } " ^
    "} catch { Write-Host ' [4] Active User Sessions :  [ Server starting up or idle ]' -ForegroundColor Yellow }"

:: 5. Background Playwright / Chrome Browsers
powershell -NoProfile -Command ^
    "$chromeCount = (Get-Process -Name 'chrome' -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*chrome.exe*' }).Count; " ^
    "Write-Host (' [5] Background Browsers   :  [' + $chromeCount + ' Headless Chrome Engine(s) Running ]') -ForegroundColor Green"

echo.
echo =====================================================================
echo  Current Live Website Access Address:
echo =====================================================================
if exist "latest_public_url.txt" (
    type "latest_public_url.txt"
) else (
    echo  Local Address: http://127.0.0.1:8000/
)
echo =====================================================================
echo.
echo  * All services are running silently in the background.
echo  * You can safely close this status window anytime.
echo.
pause

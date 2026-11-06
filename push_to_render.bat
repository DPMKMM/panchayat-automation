@echo off
set "PATH=C:\Users\dpmkm\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd;%PATH%"
cd /d "E:\Google Antigravity\EPT_AUTOMATION"
echo ========================================================
echo Pushing updates to GitHub (DPMKMM/panchayat-automation)...
echo Render will auto-deploy to https://ept-automation.onrender.com
echo ========================================================
echo.
git push origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Pushed to GitHub! Render build and deployment triggered.
) else (
    echo [FAILED] Push failed. If a browser window opened, please complete GitHub sign-in.
)
echo.
pause

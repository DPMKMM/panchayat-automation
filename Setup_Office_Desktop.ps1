# =====================================================================
# e-Panchayat Office Desktop 1-Click Automated Installer (Windows 11 Pro)
# Sets up Python, Git, Playwright, Firewall, Power, and Background Host
# =====================================================================

param(
    [switch]$AutoStartServer = $true
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  e-Panchayat Automated Executive Analytics & Reporting Platform     " -ForegroundColor Yellow
Write-Host "  1-Click Automated Windows 11 Pro Office Desktop Setup              " -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Administrator Verification
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "[!] Running without Administrator privileges. Some system settings (Firewall/Power) may be skipped."
}

# 2. Check and Install Git
Write-Host "[1/9] Verifying Git installation..." -ForegroundColor Green
$gitCmd = Get-Command "git" -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Host "[*] Git not detected. Installing Git for Windows via winget..." -ForegroundColor Yellow
    try {
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        Write-Warning "[!] Automatic winget install failed. Please install Git manually from https://git-scm.com/download/win"
    }
} else {
    Write-Host "[+] Git is installed: $(git --version)" -ForegroundColor Green
}

# 3. Check and Install Python
Write-Host "[2/9] Verifying Python installation..." -ForegroundColor Green
$pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
$needPyInstall = $false

if (-not $pyCmd) {
    $needPyInstall = $true
} else {
    try {
        $pyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ([float]$pyVer -lt 3.10) {
            Write-Host "[!] Found older Python $pyVer. Need Python 3.11 or 3.12." -ForegroundColor Yellow
            $needPyInstall = $true
        } else {
            Write-Host "[+] Python is installed: Python $pyVer" -ForegroundColor Green
        }
    } catch {
        $needPyInstall = $true
    }
}

if ($needPyInstall) {
    Write-Host "[*] Installing Python 3.12 64-bit via winget..." -ForegroundColor Yellow
    try {
        winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        Write-Warning "[!] winget install failed. Please install Python 3.12 from https://www.python.org/downloads/ (check 'Add python.exe to PATH')"
    }
}

# 4. Create Virtual Environment (.venv)
Write-Host "[3/9] Setting up Python Virtual Environment (.venv)..." -ForegroundColor Green
$venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[*] Creating .venv in $ScriptDir..." -ForegroundColor Yellow
    & python -m venv "$ScriptDir\.venv"
}

if (Test-Path $venvPython) {
    Write-Host "[+] Virtual environment ready at $ScriptDir\.venv" -ForegroundColor Green
} else {
    Write-Error "[ERROR] Could not create virtual environment. Ensure python is in your PATH."
    exit 1
}

# 5. Upgrade pip and Install Dependencies
Write-Host "[4/9] Installing / Updating Python requirements..." -ForegroundColor Green
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$ScriptDir\requirements.txt"

# 6. Install Playwright Chromium Browser
Write-Host "[5/9] Installing Playwright Chromium browser engine..." -ForegroundColor Green
& $venvPython -m playwright install chromium

# 7. Configure Windows 11 Power Settings (Never Sleep on AC Power)
Write-Host "[6/9] Configuring Windows 11 Power & Fast Startup settings..." -ForegroundColor Green
try {
    # Standby: Never sleep when connected to power
    powercfg /change standby-timeout-ac 0
    # Hibernate: Never hibernate
    powercfg /change hibernate-timeout-ac 0
    # Monitor: Turn off screen after 15 mins to save power, but keep CPU awake 24/7
    powercfg /change monitor-timeout-ac 15

    # Disable Windows Fast Startup (Hiberboot) - Crucial for clean Wake-on-LAN and BIOS auto-power-on
    if ($isAdmin) {
        Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" -Name "HiberbootEnabled" -Value 0 -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[+] Power settings configured: PC will NEVER sleep or hibernate on AC power." -ForegroundColor Green
} catch {
    Write-Warning "[!] Could not configure all power settings: $_"
}

# 8. Configure Windows Firewall Rule for Port 8000
Write-Host "[7/9] Configuring Windows Firewall rule for Port 8000..." -ForegroundColor Green
if ($isAdmin) {
    try {
        $ruleName = "e-Panchayat Automated Portal (Port 8000)"
        $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if (-not $existingRule) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Any | Out-Null
            Write-Host "[+] Inbound Firewall rule created for TCP port 8000." -ForegroundColor Green
        } else {
            Write-Host "[+] Firewall rule already exists." -ForegroundColor Green
        }
    } catch {
        Write-Warning "[!] Could not configure firewall rule: $_"
    }
}

# 9. Create Auto-Start Task and Desktop Shortcuts
Write-Host "[8/9] Creating Desktop shortcuts & Silent Auto-Start task..." -ForegroundColor Green
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath("Desktop")

# Shortcut 1: Check Server Status
$scStatus = $WshShell.CreateShortcut("$DesktopPath\Check_ePanchayat_Status.lnk")
$scStatus.TargetPath = "$ScriptDir\Check_Server_Status.bat"
$scStatus.WorkingDirectory = "$ScriptDir"
$scStatus.Description = "Check live status of e-Panchayat background server & public link"
$scStatus.Save()

# Shortcut 2: Start Portal (Silent Background)
$shortcutPortal = $WshShell.CreateShortcut("$DesktopPath\Start_ePanchayat_Silent.lnk")
$shortcutPortal.TargetPath = "wscript.exe"
$shortcutPortal.Arguments = "`"$ScriptDir\Start_ePanchayat_Background.vbs`""
$shortcutPortal.WorkingDirectory = "$ScriptDir"
$shortcutPortal.Description = "Start e-Panchayat Automated Server Silently in Background (No Windows)"
$shortcutPortal.Save()

# Shortcut 3: Stop Portal
$scStop = $WshShell.CreateShortcut("$DesktopPath\Stop_ePanchayat.lnk")
$scStop.TargetPath = "$ScriptDir\Stop_ePanchayat_Server.bat"
$scStop.WorkingDirectory = "$ScriptDir"
$scStop.Description = "Stop e-Panchayat background services"
$scStop.Save()

# Shortcut 4: Update & Restart
$shortcutUpdate = $WshShell.CreateShortcut("$DesktopPath\Update_From_GitHub.lnk")
$shortcutUpdate.TargetPath = "$ScriptDir\Update_And_Restart.bat"
$shortcutUpdate.WorkingDirectory = "$ScriptDir"
$shortcutUpdate.Description = "Pull latest code updates from GitHub and restart in background"
$shortcutUpdate.Save()

# Configure Windows Startup Task Scheduler (Runs SILENTLY in background on boot)
if ($isAdmin) {
    try {
        $taskName = "ePanchayat_AutoStart_Office"
        $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$ScriptDir\Start_ePanchayat_Background.vbs`"" -WorkingDirectory "$ScriptDir"
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
        Write-Host "[+] Windows Scheduled Task '$taskName' registered (Runs SILENTLY on every login with zero CMD windows)." -ForegroundColor Green
    } catch {
        Write-Warning "[!] Could not register Scheduled Task: $_"
    }
}

# Copy silent startup VBS to user Startup folder as fallback
try {
    $startupFolder = [System.Environment]::GetFolderPath("Startup")
    $startupLnk = $WshShell.CreateShortcut("$startupFolder\ePanchayat_Startup.lnk")
    $startupLnk.TargetPath = "wscript.exe"
    $startupLnk.Arguments = "`"$ScriptDir\Start_ePanchayat_Background.vbs`""
    $startupLnk.WorkingDirectory = "$ScriptDir"
    $startupLnk.Save()
    Write-Host "[+] Startup shortcut created in Windows Startup folder." -ForegroundColor Green
} catch {}

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  🎉 INSTALLATION COMPLETED!                                         " -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  1. Python & virtual environment (.venv) are ready." -ForegroundColor White
Write-Host "  2. Playwright Chromium browser is installed." -ForegroundColor White
Write-Host "  3. Sleep/Hibernate disabled (PC stays awake 24/7 on AC power)." -ForegroundColor White
Write-Host "  4. Firewall rule opened for port 8000." -ForegroundColor White
Write-Host "  5. Silent Background Task configured (No CMD windows to close)." -ForegroundColor White
Write-Host "  6. Desktop shortcuts created for Status, Start, Stop & Update." -ForegroundColor White
Write-Host "=====================================================================" -ForegroundColor Cyan

# 10. Automatically Launch Server Silently and Open Browser (One-Click Experience!)
if ($AutoStartServer) {
    Write-Host ""
    Write-Host "[9/9] Starting e-Panchayat host server SILENTLY in the background..." -ForegroundColor Yellow
    
    # Launch Start_ePanchayat_Background.vbs
    Start-Process "wscript.exe" -ArgumentList "`"$ScriptDir\Start_ePanchayat_Background.vbs`"" -WorkingDirectory "$ScriptDir"
    
    Write-Host "[*] Services running invisibly in the background. Waiting 4 seconds..." -ForegroundColor Cyan
    Start-Sleep -Seconds 4
    
    # Open local console in default browser
    Start-Process "http://127.0.0.1:8000/"
    
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Green
    Write-Host "  🚀 SERVER IS LIVE IN THE BACKGROUND!                               " -ForegroundColor Green
    Write-Host "  * No command prompt window is visible on your screen.              " -ForegroundColor Green
    Write-Host "  * Nobody can accidentally close it by clicking 'X'.                " -ForegroundColor Green
    Write-Host "  * To check live status, double-click 'Check_ePanchayat_Status.lnk' " -ForegroundColor Green
    Write-Host "=====================================================================" -ForegroundColor Green
    Start-Sleep -Seconds 3
}

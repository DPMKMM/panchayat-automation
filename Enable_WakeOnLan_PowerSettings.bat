@echo off
TITLE Configure Windows 11 Pro Wake-on-LAN & 24/7 Power Settings
COLOR 0B

echo =====================================================================
echo    Windows 11 Pro: Wake-on-LAN ^& 24/7 Server Power Configuration
echo =====================================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Administrator privileges required. Elevating...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [1/4] Disabling Windows Sleep and Hibernation (PC stays awake 24/7)...
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 15
echo [+] Sleep and Hibernate disabled for AC power.

echo.
echo [2/4] Disabling Windows Fast Startup (Crucial for Clean Hardware Power State)...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f >nul 2>&1
echo [+] Fast Startup disabled.

echo.
echo [3/4] Enabling Wake-on-LAN in Windows Network Adapters...
powershell -NoProfile -Command "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -or $_.PhysicalMediaType -eq '802.3' } | ForEach-Object { try { Set-NetAdapterPowerManagement -Name $_.Name -WakeOnMagicPacket Enabled -DeviceSleepOnDisconnect Disabled -ErrorAction SilentlyContinue; Write-Host ('[+] Enabled WoL on adapter: ' + $_.InterfaceDescription) -ForegroundColor Green } catch {} }"

echo.
echo [4/4] Detecting your Office Desktop Network Identity:
echo ---------------------------------------------------------------------
powershell -NoProfile -Command "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object Name, InterfaceDescription, MacAddress, Status | Format-Table -AutoSize"
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet' } | Select-Object IPAddress, InterfaceAlias | Format-Table -AutoSize"
echo ---------------------------------------------------------------------

echo.
echo =====================================================================
echo  CONFIGURATION FINISHED!
echo.
echo  REMEMBER TO CHECK YOUR BIOS/UEFI SETTINGS:
echo  1. Restart desktop and press F2, F12, or DEL to enter BIOS.
echo  2. Look for 'Power Management' or 'APM Configuration':
echo     - 'Restore on AC Power Loss' -> Set to 'POWER ON' (or 'Turn On')
echo     - 'Wake on LAN' / 'Power On By PCIE' -> Set to 'ENABLED'
echo  3. Save and Exit (F10).
echo =====================================================================
echo.
pause

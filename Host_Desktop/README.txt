=====================================================================
  Telangana ePanchayat Portal - Office Desktop Host (D:\DPM-ept)
  Permanent Website: https://www.panchayatautomation.in
=====================================================================

HOW TO USE ON YOUR OFFICE DESKTOP:

1. Double-click "ONE_CLICK_INSTALL_AND_RUN.bat".
   That is the ONLY thing you need to do!
   
   It will:
   - Setup D:\DPM-ept
   - Configure .env with your permanent Cloudflare tunnel token
   - Create Python .venv & install Chromium
   - Pull the latest code from GitHub
   - Create a desktop shortcut: 'Start ePanchayat Portal (Background)'
   - Launch the portal completely in the background (0 open CMD windows)

2. SAFE FROM ACCIDENTAL CLOSING:
   The portal runs completely silent in the background. 
   Closing Command Prompt windows or locking the PC will NOT stop the server!

3. TO CHECK STATUS:
   Double-click "Check_Office_Host_Status.bat"

4. TO STOP THE PORTAL:
   Double-click "Stop_Office_Host.bat"

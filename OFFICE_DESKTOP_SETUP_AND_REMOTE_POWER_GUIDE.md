# Office Desktop (Windows 11 Pro) Deployment & Remote Mobile Power Guide

This guide explains how to set up your **Office Desktop (Windows 11 Pro)** as the persistent 24/7 host for your e-Panchayat website, how to **automatically push updates from your laptop**, and how to **turn on the office desktop from your mobile phone from anywhere in the world** if someone shuts it down.

---

## 1. System Architecture Overview

```
 [ Your Laptop ]                [ GitHub Repository ]             [ Office Desktop (Win 11 Pro) ]
  (Development)                  (Code Hub: panchayat-automation)      (24/7 Live Host)
       |                                |                                     |
 1. Edit code                           |                                     |
 2. Run Laptop_Push_Updates.bat --------> git push origin main                |
                                        |                                     |
                                        |--- 3. Auto-Sync daemon polls every 60s
                                                (Runs git pull & reloads server)
                                                                              |
                                                                              v
                                                                 [ Cloudflare Hyderabad Edge ]
                                                                              |
                                                                 [ Public Online Website ]
                                                               (Accessible on any Mobile Phone)
```

- **Your Laptop**: Used exclusively for coding, debugging, and testing.
- **GitHub**: Acts as the bridge between your laptop and office desktop.
- **Office Desktop (Windows 11 Pro)**: Runs the live Uvicorn server, Cloudflare tunnel, and background Playwright browser engine.

---

## 2. Turnkey Setup on Your Office Desktop (One-Time Setup)

On your Office Desktop running **Windows 11 Pro**:

1. **Get the Project Folder**:
   - Either clone the repository via Git:
     ```cmd
     git clone https://github.com/DPMKMM/panchayat-automation.git
     ```
   - Or copy the `EPT_AUTOMATION` folder from your external drive or network share to your office desktop (e.g., `C:\ePanchayat` or `D:\EPT_AUTOMATION`).

2. **Run the Automated Installer**:
   - Open the folder on your office desktop.
   - Right-click **`Setup_Office_Desktop.bat`** and select **"Run as administrator"**.

3. **What `Setup_Office_Desktop.bat` Automates**:
   - ✅ Installs **Git** and **Python 3.12** automatically if not already present.
   - ✅ Sets up the `.venv` virtual environment.
   - ✅ Installs all dependencies (`fastapi`, `uvicorn`, `playwright`, `ddddocr`, `reportlab`, etc.).
   - ✅ Installs the **Playwright Chromium** browser automation engine.
   - ✅ Configures Windows 11 Power settings: **Disables sleep and hibernation** so the PC stays awake 24/7 on AC power.
   - ✅ Disables Windows **Fast Startup** (ensures clean hardware state for Wake-on-LAN and BIOS auto-boot).
   - ✅ Opens Windows Firewall for **TCP port 8000**.
   - ✅ Creates a **Windows Task Scheduler** task (`ePanchayat_AutoStart_Office`) so the server and tunnel automatically launch every time Windows starts up!
   - ✅ Creates convenient shortcuts on your desktop: `Start_ePanchayat_Portal` and `Update_From_GitHub`.

---

## 3. How to Push Updates from Laptop to Office Desktop

Whenever you make improvements or changes on your laptop:

1. Double-click **`Laptop_Push_Updates.bat`** on your laptop.
2. Type an optional description (or press `Enter` to use the current date and time).
3. The script commits and pushes your code directly to GitHub (`origin main`).
4. **On your Office Desktop**:
   - The background **`auto_sync_office.py`** watcher checks GitHub every 60 seconds.
   - It automatically runs `git pull origin main`, updates any modified dependencies, and refreshes the live website without you needing to do anything on the office PC!
5. **Manual Update Option**: If you are in the office and want to update immediately without waiting 60 seconds, simply double-click **`Update_And_Restart.bat`**.

---

## 4. How to Turn ON the Office Desktop from Mobile Phone from ANYWHERE

If someone in your office accidentally shuts down the desktop computer, you can turn it back ON from your mobile phone using the methods below.

### Method 1: Smart Wi-Fi Plug + BIOS "Restore on AC Power Loss" (⭐ 100% Guaranteed & Recommended)

This is the industry standard for remote computers. It works across any office network, requires zero router port forwarding, and can be triggered from anywhere via 4G/5G.

#### Step A: Configure Desktop BIOS/UEFI (2-Minute One-Time Setup)
1. Turn on or restart your Office Desktop.
2. Repeatedly press the BIOS key (**`F2`**, **`F12`**, or **`Delete`** depending on brand):
   - **Dell**: Press **`F2`** or **`F12`**
   - **HP**: Press **`F10`** or **`Esc`**
   - **Lenovo**: Press **`F1`** or **`Enter`**
   - **Asus / Gigabyte / MSI**: Press **`Delete`** or **`F2`**
3. Navigate to **Power Management** (or **APM Configuration** / **Advanced Power Settings**).
4. Find the setting named:
   - **"AC Power Recovery"** (Dell)
   - **"After Power Loss"** (HP / Lenovo)
   - **"Restore AC Power Loss"** (Asus / MSI / Gigabyte)
   - **"State After Power Failure"**
5. Change it from *Off* to **"Power On"** (or **"Always On"** / **"Last State"**).
6. Press **`F10`** to Save and Exit.

> **Why this works**: Motherboards with this setting automatically boot the PC the moment AC power is supplied to the power supply.

#### Step B: Plug Desktop into an Inexpensive Smart Wi-Fi Plug
1. Purchase any standard Smart Wi-Fi Plug (e.g. **TP-Link Tapo P100 / P110**, **Wipro Smart Plug**, **Oakter**, or **Tuya/Smart Life** — cost is approx. ₹499 to ₹799 on Amazon/Flipkart).
2. Plug the smart plug into your office wall socket, and plug your Desktop CPU power cable into the smart plug.
3. Connect the smart plug to the office Wi-Fi using the mobile app on your Android or iPhone (e.g. *Tapo* or *Smart Life*).

#### Step C: The Mobile Power-On Action (From Anywhere on Mobile Data)
If someone shuts down your office PC:
1. Open the Smart Plug app on your mobile phone (anywhere in the world via 4G/5G).
2. Toggle the smart plug **OFF**.
3. Wait 5 seconds.
4. Toggle the smart plug **ON**.
5. The motherboard senses electrical power restoration and **instantly boots the PC**!
6. Windows 11 starts up, the Task Scheduler automatically runs `Run_Office_Server.bat`, and your e-Panchayat website is live within 30 to 45 seconds!

---

### Method 2: Scheduled Daily Automatic Power-On (RTC Alarm)

As a backup safety net, you can instruct the computer to turn itself on every morning even if someone shut it down the night before:

1. Enter BIOS (press **`F2`** or **`Del`** during boot).
2. Go to **Power Management** -> **Resume By RTC Alarm** (or **Auto Power On**).
3. Set to **Enabled**.
4. Set Time: e.g. **`08:00:00`** (8:00 AM) and Frequency: **Every Day**.
5. Save and Exit (**`F10`**).
6. Every morning at 8:00 AM, the computer will automatically power on without anyone touching it.

---

### Method 3: Wake-on-LAN (WoL) Configuration

Your office system also has Wake-on-LAN enabled via our automated script:

1. Right-click **`Enable_WakeOnLan_PowerSettings.bat`** and run as administrator.
2. The script displays your desktop's:
   - **MAC Address** (e.g. `00:1A:2B:3C:4D:5E`)
   - **Local IP Address** (e.g. `192.168.1.150`)
3. In your mobile phone app (such as *Wake On Lan* by Aquila or *WolOn* on Android/iOS):
   - Enter the desktop's MAC Address.
   - Send the Wake packet.
   > *Note: Wake-on-LAN over the internet requires your office router to support WAN broadcast forwarding. For 100% reliable remote power-on through any office firewall, Method 1 (Smart Wi-Fi Plug) is recommended.*

---

## 5. Setting Windows 11 Pro to Auto-Logon (Optional)

If your office desktop requires a password on boot, Windows will wait at the lock screen. While our Task Scheduler runs even before login, setting Windows 11 Pro to Auto-Logon ensures all desktop UI automation tools launch with full graphics acceleration:

1. Press **`Win + R`**, type **`netplwiz`**, and press Enter.
2. Uncheck **"Users must enter a user name and password to use this computer"**.
3. Click **Apply**, enter your Windows user password, and click **OK**.
4. Now whenever the computer turns on, it will log in straight to the desktop and start the server immediately!

---

## 6. Summary of Key Files

| File | Purpose |
| :--- | :--- |
| **`Setup_Office_Desktop.bat`** | 1-Click installer for Windows 11 Pro office PC (installs Python, Git, Playwright, Firewall, Power, Task Scheduler). |
| **`Laptop_Push_Updates.bat`** | 1-Click script on your laptop to push latest updates to GitHub. |
| **`Auto_Sync_Office.bat`** | Background watcher on office desktop: checks GitHub every 60s and auto-updates the live website. |
| **`Run_Office_Server.bat`** | Master host launcher: runs Uvicorn + Cloudflare Public Gateway + Auto-Sync daemon. |
| **`Update_And_Restart.bat`** | 1-Click manual update script for office desktop. |
| **`Enable_WakeOnLan_PowerSettings.bat`** | Configures Windows 11 network card for Wake-on-LAN and disables sleep. |
| **`latest_public_url.txt`** | Automatically updated text file showing the current live public website URL. |

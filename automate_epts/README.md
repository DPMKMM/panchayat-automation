# e-Panchayat Telangana (EPTS) Automated Report Pipeline (`automate_epts`)

High-reliability browser automation pipeline built for **e-Panchayat Telangana (EPTS)**:
- Automated Department Login with AI CAPTCHA recognition (DDDDOCR deep-learning ONNX model)
- 6-digit SMS OTP verification and 12-hour session state persistence
- Multi-frame ASP.NET navigation (`GP Monitoring` -> `GM-R 1. Sanitation reports` -> `DSR REPORTS`)
- Automated download of official raw reports:
  1. **GM-R 1.2.7 DSR Raw Data Report** (`raw_dsr.xls`)
  2. **GM-R 1.2.11 Report on Presenties Data** (`presentees.xls`)
  3. **GM-R 1.2.10 Report on Absentees Data** (`absentees.xls`)
- Multi-report compilation into official **7-Section District Attendance & DSR PDF Report** via `report_generator.py`
- GP Thursday Balance Entry Report automation (`GM-R 14.2`)

---

## 🏗️ Architecture & Threading Model

1. **Greenlet Thread Affinity**:
   Playwright's synchronous API requires all browser operations to run on the exact same thread. The service uses `concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="EPTS_BotThread")` and `_generation_lock` serialization to guarantee zero greenlet cross-thread conflicts.

2. **Session Persistence & Recovery (`data/session_state.json`)**:
   Upon OTP verification, session credentials, timestamps, and active modes are persisted to disk. The server can restart or recover sessions up to 12 hours without re-prompting for login.

3. **Dual Browser Engine Resilience**:
   Automatically detects and launches the system **Google Chrome** persistent profile. If Google Chrome is absent or restricted, it seamlessly falls back to **Microsoft Edge** (`channel="msedge"`), ensuring 100% compatibility across all Windows PCs.

4. **Keepalive Daemon**:
   A background daemon evaluates `document.title` every 120 seconds to prevent the government portal ASP.NET session from timing out.

---

## 📂 Directory Layout

```
automate_epts/
├── automation_service.py     # Main service controller (threading, session persistence, API bridge)
├── epts_automation.py        # Core Playwright browser engine & ddddocr CAPTCHA solver
├── dsr_auto_download.py      # Iframe report download pipeline (1.2.7, 1.2.11, 1.2.10)
├── config.json               # Credentials configuration
├── downloads/                # Raw downloaded .xls files from portal
├── browser_profile/          # Persistent Chrome/Edge user data directory (cookies & local state)
├── temp_captcha.png          # Real-time screenshot of extracted portal CAPTCHA
└── README.md
```

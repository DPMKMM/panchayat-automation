# Telangana ePanchayat Automation & Analytics Portal (v4.0)

Clean, modular executive automation platform for Telangana Panchayat Raj & Rural Development.
Engineered for multi-session browser automation, official report generation, and real-time portal monitoring.

---

## 🏛️ Modular Architecture

Each functional domain is organized into an isolated, self-contained module:

```
ePanchayat_Automation/
├── core/                       # Shared platform utilities
│   ├── config.py               # Central environment configuration & paths
│   ├── integrations.py         # Job tracking (SQLite) & storage protocols
│   └── session_manager.py      # Session registry & multi-browser isolation
│
├── dcb/                        # Demand Collection Balance (DCB) Module
│   ├── service.py              # 100% Live Web Scraped from epanchayat portal (No offline Excel)
│   ├── pdf_generator.py        # Official Landscape PDF Report (Page 1 Mandal Abstract)
│   ├── powerbi_pdf_generator.py# Power BI Visual Report (KPIs, Radial Gauge, Donut Chart)
│   ├── html.py                 # Interactive Web DCB Dashboard (1-decimal precision)
│   └── router.py               # FastAPI APIRouter for all /api/tax/* endpoints
│
├── dsr/                        # Daily Status Report (DSR) & Attendance Module
│   ├── automation.py           # Playwright automation (ePTS login, captcha OCR, OTP)
│   ├── service.py              # Concurrent worker threads, keepalive & auto-expiry
│   ├── auto_download.py        # Scheduled automatic portal downloading
│   ├── pdf_generator.py        # GP Attendance & DSR Report generator (Page 1 & 2)
│   ├── html.py                 # Unified Executive Dashboard (naresh_html)
│   ├── upload_html.py          # Manual attendance file upload console
│   └── router.py               # FastAPI APIRouter for all /api/naresh/* & /api/web/*
│
├── gp_balance/                 # Thursday GP Bank/Cash Balance (GM-R 14.2) Module
│   ├── automation.py           # Playwright scraper for Thursday dates & GP balances
│   ├── service.py              # Balance aggregation & pending accounts audit
│   ├── models.py               # Data models for accounts and Mandal compliance
│   ├── pdf_generator.py        # Landscape GP Balance PDF generator
│   ├── excel_generator.py      # Multi-sheet Excel workbook generator
│   └── router.py               # FastAPI APIRouter for all /api/balance/* endpoints
│
├── tests/                      # Automated test suite
│   ├── test_dcb.py             # DCB scraping, calculations, and PDF generation tests
│   ├── test_dsr.py             # DSR navigation and session tests
│   └── test_gp_balance.py      # Thursday balance normalization & accounts tests
│
├── data/                       # Dynamic runtime storage (gitignored)
│   ├── reports/                # Generated PDFs during active user sessions
│   ├── sessions/               # Active officer login states
│   └── browser_profiles/       # Isolated Playwright profiles
│
├── app.py                      # Root FastAPI application mounting all modules
├── run_cloudflare_portal.py    # Instant secure public HTTPS tunnel runner
├── Start_Portal.bat            # One-click Windows local launcher
├── Start_Cloudflare_Portal.bat # One-click Cloudflare tunnel launcher
├── requirements.txt            # Python dependencies
└── .gitignore                  # Clean exclusion of temporary files & offline data
```

---

## ⚡ Zero Offline Excel / 100% Live Web Scraped

In compliance with executive data governance:
- **No offline `.xls`, `.xlsx`, or `.csv.gz` files** are stored or bundled in this repository.
- House Tax DCB data is fetched **live in real-time** from `https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp` with dynamic in-memory caching.
- GP Balances and Daily Attendance reports are extracted directly from authenticated e-Panchayat web sessions.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run Local Server
Double-click `Start_Portal.bat` or run:
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
- **Unified Portal**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **House Tax DCB Dashboard**: [http://127.0.0.1:8000/reports/tax-dcb](http://127.0.0.1:8000/reports/tax-dcb)
- **Manual Upload Console**: [http://127.0.0.1:8000/reports/ps-attendance](http://127.0.0.1:8000/reports/ps-attendance)

### 3. Public Cloudflare Access
Double-click `Start_Cloudflare_Portal.bat` to launch the zero-configuration public tunnel accessible securely across mobile networks and external offices.

---

## 🧪 Running Tests
```bash
pytest tests/ -v
```

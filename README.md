# Telangana e-Panchayat Automated Console (PRKMM)
### Office of the District Panchayat Officer, Khammam District, Telangana

A comprehensive, production-grade automated intelligence and reporting portal for Telangana Gram Panchayats. Built with **FastAPI**, **Playwright headless browser automation**, **DDDDOCR deep learning neural network**, **Pandas**, **ReportLab**, and **PyPDF**.

---

## 🏛️ System Architecture & Core Modules

The platform unites three core government reporting workflows into a single unified console:

```mermaid
flowchart TD
    User["🏛️ Department Officer / District Admin"] --> UI["🖥️ Unified Automated Console (UI/home.py)"]

    subgraph Web_Layer["FastAPI Application Core (app.py)"]
        UI --> Endpoints["FastAPI Endpoints"]
        Endpoints --> Mod1["1. DSR Attendance Robot Station"]
        Endpoints --> Mod2["2. House Tax Collection (DCB) Station"]
        Endpoints --> Mod3["3. GP Thursday Balance Entry Module"]
    end

    subgraph Automation_Pipeline["Browser Automation & AI OCR Engine (DSR/)"]
        Mod1 --> BotThread["Dedicated Bot Thread Worker (greenlet-safe)"]
        BotThread --> PW["Playwright Browser Controller (Chrome / MS Edge)"]
        PW --> OCR["DDDDOCR Neural Engine (auto-solves #img1 Captcha)"]
        PW --> Portal["Telangana e-Panchayat Portal (epanchayat.telangana.gov.in)"]
        Portal --> Scrape["ASP.NET Iframe Scraper (my-iframe)"]
        Scrape --> Downloader["Downloads GM-R 1.2.7, 1.2.11 & 1.2.10"]
        Downloader --> DSRGen["7-Section District Attendance PDF (DSR/report_generator.py)"]
    end

    subgraph Live_Tax_Engine["Real-Time House Tax DCB Engine (DCB/tax_service.py)"]
        Mod2 --> LiveFetch["Live Portal Ingestion (epmis/allgpdata.jsp)"]
        LiveFetch --> LiveData["12,760 GPs across all 31 Telangana Districts"]
        LiveData --> Sorter["Mandal Abstract Sorter (% Collected Ascending)"]
        Sorter --> LowTop["Lowest Collected Mandals at Top (Yerrupalem #1)"]
        LowTop --> DCBPdf["Landscape Multi-Page Official PDF (DCB/dcb_pdf_generator.py)"]
        LowTop --> PBIPdf["PowerBI Executive Visual PDF (DCB/powerbi_pdf_generator.py)"]
    end

    subgraph Storage["Runtime Data (data/)"]
        DSRGen --> OutRep["data/reports/*.pdf"]
        DCBPdf --> OutRep
        PBIPdf --> OutRep
        BotThread --> SessionState["data/attendance_jobs.sqlite3 (jobs/progress only)"]
    end
```

---

## ⚡ Key Modules & Capabilities

### 1. DSR & Attendance Robot Station (`DSR/`)
* **AI CAPTCHA Solving**: Automatically extracts the `#img1` challenge image from the e-Panchayat login modal, evaluates it via the `ddddocr` ONNX neural model, and types the solution in milliseconds with up to 5 auto-retries.
* **OTP Authentication**: Triggers and verifies the 6-digit SMS OTP. Authenticated state lives only in the running server process; a restart requires a fresh login.
* **Frame-Aware Portal Automation**: Traverses ASP.NET iframes (`my-iframe` / `PSPerformance`), expands `DSR REPORTS`, unlocks `readonly` calendar date fields, and extracts:
  * **GM-R 1.2.7**: Attendance Status & DSR Raw Data
  * **GM-R 1.2.11**: Presentees Data of Panchayat Secretaries
  * **GM-R 1.2.10**: Absentees Data of Panchayat Secretaries
* **Official 7-Section PDF Generator**:
  1. District Attendance Abstract (Total GPs, Submitted, Attendance Before 9 AM %)
  2. Mandal-wise Attendance Abstract
  3. GPs with Attendance Pending (Secretary Name, Nature of Posting, Mobile Phone)
  4. GPs with Attendance Marked After 9 AM
  5. Mandal-wise DSR Submission Abstract (Ranked by pending count)
  6. GPs with DSR Entry Pending (Secretary Name & Phone for follow-up)
  7. Absent Secretaries List with leave/deputation remarks

### 2. House Tax Collection (DCB) Analytics Station (`DCB/tax_service.py`)
* **100% Live Portal Data**: Fetches real-time Demand, Collection, and Balance (DCB) directly from `https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp`.
* **Zero Stale Files**: No offline or pre-saved Excel files are used; every analysis reflects live government portal records across **12,760 GPs and 31 Districts**.
* **Strict Ranking Rule**: On both the Web Console and the Official Landscape PDF, Page 1 displays the Mandal Abstract **sorted ascending by % Collected** (lowest collection on top):
  * **Rank 1**: Yerrupalem (Lowest % collected)
  * ...
  * **Rank 20**: Penuballi (Highest % collected)
* **Dual PDF Export**:
  * **Official Landscape DCB Report**: Page 1 Mandal Abstract + Mandals & GP details with running page numbers (`Page X of Y`).
  * **PowerBI Executive Visual Report**: Visual analytics charts with color-coded performance bars.

### 3. Thursday GP Balance Entry Module (`GPBalance/`)
* Scrapes and compiles weekly Gram Panchayat balance entries across 6 major bank accounts:
  1. GP PD Account (General Fund, 15th FC, SFC - IFMIS)
  2. State Matching Grant (TG-bPASS Account)
  3. 15th Finance Commission Grant - Tied (e-Gram Swaraj)
  4. 15th Finance Commission Grant - Untied (e-Gram Swaraj)
  5. Village Water and Sanitation Committee (VWSC / SBM)
  6. MGNREGS (Material Component)
* Automatically cross-references non-entered Gram Panchayats with secretary phone numbers for follow-up calls.

---

## 🛠️ API Reference

### Department Authentication & DSR Automation (`/api/naresh/*`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/naresh/login` | Connects browser bot, solves Captcha with AI OCR, triggers OTP |
| `POST` | `/api/naresh/verify-otp` | Validates 6-digit OTP and authenticates officer session |
| `GET`  | `/api/naresh/session-status`| Returns live background browser engine status & authenticated officer |
| `POST` | `/api/naresh/logout` | Clicks portal logout when available, clears portal cookies, stops the background browser, and clears session state |
| `POST` | `/api/naresh/generate` | Executes live download of GM-R 1.2.7, 1.2.11, 1.2.10 and generates PDF |
| `GET`  | `/api/naresh/view` | Streams latest official 7-section DSR PDF for in-browser viewing |
| `GET`  | `/api/naresh/download` | Downloads latest official DSR PDF |

### House Tax Collection (DCB) Analytics (`/api/tax/*`)
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/tax/districts` | Returns all 31 Telangana districts with totals and GP counts |
| `GET`  | `/api/tax/mandals` | Returns list of mandals for selected district (`?district=Khammam`) |
| `GET`  | `/api/tax/data` | Returns live DCB summary, sorted mandal abstract, and GP records |
| `GET`  | `/api/tax/report.pdf` | Streams official Landscape multi-page House Tax DCB PDF |
| `GET`  | `/api/tax/powerbi-report.pdf` | Streams executive PowerBI visualization PDF report |
| `GET`  | `/api/tax/download` | Exports consolidated Excel spreadsheet for the district |
| `POST` | `/api/tax/refresh` | Forces live re-download directly from e-Panchayat portal |

### Thursday GP Balance Entry (`/api/balance/*`)
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/balance/dates` | Reads available Thursday dates from the authenticated live portal session |
| `GET`  | `/api/balance/data` | Returns Thursday balance entry summary and pending GP list |
| `GET`  | `/api/balance/view-pdf` | Streams official GP Balance Entry PDF |
| `GET`  | `/api/balance/download-pdf`| Downloads GP Balance Entry PDF |
| `GET`  | `/api/balance/download-excel`| Downloads GP Balance Entry Excel workbook |

---

## 💻 How to Run Locally

### Option 1: 1-Click Desktop Launcher
Double-click `Start_ePanchayat_Server.bat` on your Desktop.

### Option 2: PowerShell (Developer Mode)
```powershell
Set-Location "C:\Users\dpmkm\Desktop\Reportsept"
$env:DATA_DIR = Join-Path (Get-Location) "data"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000
```
Open your browser to: `http://127.0.0.1:8000/`

### Cloud deployment for remote users

The root `Dockerfile`, `compose.yaml`, `render.yaml`, and `Caddyfile` contain the deployment configuration. Verify portal network reachability from the selected cloud host before sharing the console.

## Project layout

```text
app.py          FastAPI entry point and API routes
UI/             Home and login console page
DSR/            e-Panchayat login, DSR automation, and Attendance PDF generation
DCB/            Live House Tax data and DCB PDF reports
GPBalance/      GM-R 14.2 balance automation and reports
shared/         Common storage, database, and path helpers
data/           Runtime state, temporary portal data, and generated reports
```

---

## 🛡️ License & Confidentiality
Designed and developed exclusively for the **Office of the District Panchayat Officer, Khammam District, Government of Telangana**. All rights reserved.

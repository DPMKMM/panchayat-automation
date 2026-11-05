---
name: epanchayat-automation
description: Expert operational reference for the Telangana e-Panchayat (EPTS) automation platform, DSR attendance reporting, and real-time House Tax DCB analytics.
---

# Telangana e-Panchayat (EPTS) Automation Expert Skill

This skill provides comprehensive operational context, architectural rules, and execution procedures for the **Telangana e-Panchayat Automated Console**.

## 1. System Architecture & Workflows

### Module 1: DSR & Attendance Robot Station (`automate_epts/`)
- **Portal Targets**: `https://epanchayat.telangana.gov.in/cs` & `https://tgprepanchayat.telangana.gov.in/`
- **Department Credentials**: Dynamic department credentials input per officer (District Panchayat Officer Account).
- **CAPTCHA Engine**: `ddddocr.DdddOcr(show_ad=False)` using bundled ONNX neural models (`common.onnx`). Evaluates `#img1` element, auto-refreshes if under 4 characters.
- **OTP Relay**: Polls for 6-digit OTP, submits to portal, verifies landing URL contains `deptLoginVerified` and text contains `Office ID:`.
- **Navigation & Downloading**: Traverses `my-iframe` under `GP Monitoring` -> `GM-R 1. Sanitation reports` -> `DSR REPORTS`. Unlocks `readonly` date inputs via DOM dispatch events.
- **Reports Downloaded**:
  - `GM-R 1.2.7`: DSR Raw Data
  - `GM-R 1.2.11`: Presentees Data
  - `GM-R 1.2.10`: Absentees Data
- **Output**: 7-Section official District PDF (`report_generator.py`) saved in `data/reports/`.
- **Threading Rule**: Playwright sync API operations MUST be scheduled onto the dedicated single-thread executor (`EPTS_BotThread` in `automation_service.py`) via `run_in_bot_thread()`.

### Module 2: House Tax Collection (DCB) Analytics Station (`tax_service.py`)
- **Data Source**: Always live directly from `https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp`.
- **Zero Saved Excels**: No offline `.xls` files are used. The portal's raw response (12,760 GPs across 31 districts) is parsed directly in memory.
- **Sorting Rule**: Mandal Abstract table (both Web UI and Official Landscape PDF Page 1) MUST be sorted **ascending by % Collected** (lowest collection percentage on top, highest at bottom).
- **PDF Generation**:
  - Landscape multi-page PDF (`dcb_pdf_generator.py`) with `NumberedCanvas` (`Page X of Y`).
  - PowerBI visual PDF (`powerbi_pdf_generator.py`).

### Module 3: GP Thursday Balance Entry Module (`GPBALNCE/`)
- **Portal GM-R 14.2**: Scrapes weekly balance entries for 6 active bank accounts (`GP PD`, `TG-bPASS`, `15th FC Tied`, `15th FC Untied`, `VWSC (SBM)`, `MGNREGS (Material)`). PMAGY is excluded per official instruction.
- **Real GP Name Integrity**: NEVER synthesize placeholder names like `<Mandal> GP-1` or `<Mandal> GP-2`. Exact real Gram Panchayat names MUST always be extracted directly from portal drill-down DOM cells.
- **DataTables Drill-Down & Stem Normalization**:
  - Automatically filters DataTables via search box and fuzzy stem matching to reach every pending mandal (e.g. `Nelakondapally`/`Nelakondapalle`, `Penubally`/`Penuballi`).
  - Expands table length to maximum so all mandals and GPs remain visible across DOM queries.
- **Account Granularity**:
  - Inspects each bank account independently.
  - If a Gram Panchayat entered 5 accounts and only missed 1 (e.g. only `VWSC (SBM)`), the pending list displays ONLY that specific missed bank account, never an indiscriminate dump of all 6 accounts.
- **Secretary Follow-Up**: Matches pending Gram Panchayats with secretary phone numbers from live portal directory for immediate telephonic follow-up.

---

## 2. Session Persistence & Thread Safety

- **Session State**: Saved in `data/session_state.json`. Loaded automatically on startup.
- **Lifespan**: 12 hours (43,200 seconds).
- **Persistent Profile**: Playwright browser profile stored in `automate_epts/browser_profile/`.
- **Keepalive**: Daemon ping runs every 120 seconds to prevent ASP.NET session expiration.
- **Server Rule**: Uvicorn MUST be run **without `--reload`** to prevent file writes in `data/reports/` from restarting the server and killing in-memory session threads.
- **District Neutrality**: Codebase and skills are strictly district-neutral, serving all districts statewide without hardcoded officer credentials or district assumptions.

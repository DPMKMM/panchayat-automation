# DSR & Attendance module

This package handles e-Panchayat Department Login, OTP verification, portal report downloads, and generation of the official 7-section Attendance & DSR PDF.

## Source files

- `automation_service.py` — per-browser session state, single-thread Playwright worker, report queue and progress.
- `epts_automation.py` — browser controls, CAPTCHA OCR, login, OTP and portal logout.
- `dsr_auto_download.py` — downloads GM-R 1.2.7, 1.2.11 and 1.2.10 from the live portal into memory.
- `report_generator.py` — parses fresh portal responses and creates the official report.

Runtime files are under `data/DSR/`; generated PDFs are under `data/reports/`. Portal workbook responses are processed in memory and are not kept as source files.

## Session behavior

Authenticated state belongs to the running server process and browser instance. A server restart starts logged out and requires a fresh login and OTP. Do not reload the authenticated e-Panchayat page; use Logout in the console to stop the worker and clear the portal session.

For standalone automation, run `python -m DSR.dsr_auto_download` from the project root. The main console starts with `Start_ePanchayat_Server.bat`.

"""Centralized configuration and environment settings for ePanchayat Automation."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Storage and Data Directories
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
REPORTS_DIR = DATA_DIR / "reports"
SESSIONS_DIR = DATA_DIR / "sessions"
PROFILES_DIR = DATA_DIR / "browser_profiles"
DOWNLOADS_DIR = DATA_DIR / "downloads"
INPUTS_DIR = DATA_DIR / "inputs"

for directory in (DATA_DIR, REPORTS_DIR, SESSIONS_DIR, PROFILES_DIR, DOWNLOADS_DIR, INPUTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Security and Session Limits
WEB_SESSION_SECRET = os.getenv("WEB_SESSION_SECRET", "khammam-epanchayat-automation-secure-key-2026")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 30 * 1024 * 1024))
SESSION_DEFAULT_DURATION = 600    # 10 minutes initial limit
SESSION_EXTENSION_DURATION = 600  # +10 minutes extension
SESSION_MAX_DURATION = 1200       # 20 minutes maximum total cap

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Live Portal URLs
URL_ALL_GP_DATA = "https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp"
URL_DISTRICT_LIVE = "https://epanchayat.telangana.gov.in/epmis/epmisPRHTAXDCBLive.jsp"
URL_EPTS_LOGIN = "https://epanchayat.telangana.gov.in/epts/login.do"

# Optional DCB Proxy
DCB_PORTAL_PROXY_URL = (os.getenv("DCB_PORTAL_PROXY_URL") or "").strip().rstrip("/")
DCB_PORTAL_PROXY_TOKEN = (os.getenv("DCB_PORTAL_PROXY_TOKEN") or "").strip()

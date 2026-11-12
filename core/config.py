"""Centralized configuration and environment settings for e-Panchayat Automation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_logger = logging.getLogger("epanchayat_config")

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"


def get_data_dir() -> Path:
    """Resolve runtime DATA_DIR dynamically from environment or default ./data."""
    raw = os.getenv("DATA_DIR", "").strip()
    target = Path(raw).resolve() if raw else (BASE_DIR / "data").resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_db_path() -> Path:
    """Resolve centralized SQLite user/auth database path."""
    override = os.getenv("EPANCHAYAT_DB_PATH", "").strip()
    if override:
        p = Path(override).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return get_data_dir() / "epanchayat_users.db"


def get_jobs_db_path() -> Path:
    """Resolve reporting job tracker SQLite database path."""
    override = os.getenv("ATTENDANCE_JOBS_DB_PATH", "").strip()
    if override:
        p = Path(override).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return get_data_dir() / "attendance_jobs.sqlite3"


def get_reports_dir() -> Path:
    p = get_data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_downloads_dir() -> Path:
    p = get_data_dir() / "downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_debug_dir() -> Path:
    p = get_data_dir() / "debug"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_temp_uploads_dir() -> Path:
    p = get_data_dir() / "temp_uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


# Storage and Data Directories (kept for backward compatibility)
DATA_DIR = get_data_dir()
REPORTS_DIR = get_reports_dir()
SESSIONS_DIR = DATA_DIR / "sessions"
PROFILES_DIR = DATA_DIR / "browser_profiles"
DOWNLOADS_DIR = get_downloads_dir()
INPUTS_DIR = DATA_DIR / "inputs"
DEBUG_DIR = get_debug_dir()
TEMP_UPLOADS_DIR = get_temp_uploads_dir()

for _directory in (
    DATA_DIR,
    REPORTS_DIR,
    SESSIONS_DIR,
    PROFILES_DIR,
    DOWNLOADS_DIR,
    INPUTS_DIR,
    DEBUG_DIR,
    TEMP_UPLOADS_DIR,
):
    _directory.mkdir(parents=True, exist_ok=True)

# Temp file retention & upload limits
_DEV_DEFAULT_SECRET = "khammam-epanchayat-automation-secure-key-2026"
WEB_SESSION_SECRET = os.getenv("WEB_SESSION_SECRET", _DEV_DEFAULT_SECRET).strip() or _DEV_DEFAULT_SECRET
if IS_PRODUCTION and WEB_SESSION_SECRET == _DEV_DEFAULT_SECRET:
    _logger.warning("WEB_SESSION_SECRET is using default value in production; set a strong random secret in .env!")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))
TEMP_RETENTION_HOURS = float(os.getenv("TEMP_RETENTION_HOURS", "24"))
SESSION_DEFAULT_DURATION = 86400    # 24 hours persistent session
SESSION_EXTENSION_DURATION = 86400
SESSION_MAX_DURATION = 86400

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Live Portal URLs
URL_ALL_GP_DATA = "https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp"
URL_DISTRICT_LIVE = "https://epanchayat.telangana.gov.in/epmis/epmisPRHTAXDCBLive.jsp"
URL_EPTS_LOGIN = "https://epanchayat.telangana.gov.in/epts/login.do"

# Optional DCB Proxy
DCB_PORTAL_PROXY_URL = (os.getenv("DCB_PORTAL_PROXY_URL") or "").strip().rstrip("/")
DCB_PORTAL_PROXY_TOKEN = (os.getenv("DCB_PORTAL_PROXY_TOKEN") or "").strip()

# Firebase Project & Authentication Configuration (Defaults provisioned for epanchayat-automation-tg)
DEFAULT_FIREBASE_PROJECT_ID = "epanchayat-automation-tg"
DEFAULT_FIREBASE_API_KEY = "AIzaSyCmMfCAHuKE70pMwFuq7uP6evUvY1hYVb8"
DEFAULT_FIREBASE_AUTH_DOMAIN = "epanchayat-automation-tg.firebaseapp.com"
DEFAULT_FIREBASE_STORAGE_BUCKET = "epanchayat-automation-tg.firebasestorage.app"
DEFAULT_FIREBASE_MESSAGING_SENDER_ID = "572548123520"
DEFAULT_FIREBASE_APP_ID = "1:572548123520:web:bdad6aa6e2d7f2a7e20f65"

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", DEFAULT_FIREBASE_PROJECT_ID).strip() or DEFAULT_FIREBASE_PROJECT_ID
FIREBASE_DATABASE_ID = os.getenv("FIREBASE_DATABASE_ID", "(default)").strip() or "(default)"


def get_firebase_web_config() -> dict[str, str]:
    """Return public Firebase Web SDK configuration dictionary for client authentication."""
    project_id = (
        os.getenv("FIREBASE_PROJECT_ID", DEFAULT_FIREBASE_PROJECT_ID).strip()
        or DEFAULT_FIREBASE_PROJECT_ID
    )
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", DEFAULT_FIREBASE_API_KEY).strip() or DEFAULT_FIREBASE_API_KEY,
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", DEFAULT_FIREBASE_AUTH_DOMAIN).strip()
        or f"{project_id}.firebaseapp.com",
        "projectId": project_id,
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", DEFAULT_FIREBASE_STORAGE_BUCKET).strip()
        or f"{project_id}.firebasestorage.app",
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", DEFAULT_FIREBASE_MESSAGING_SENDER_ID).strip()
        or DEFAULT_FIREBASE_MESSAGING_SENDER_ID,
        "appId": os.getenv("FIREBASE_APP_ID", DEFAULT_FIREBASE_APP_ID).strip() or DEFAULT_FIREBASE_APP_ID,
    }


def is_cloud_sync_fallback_allowed() -> bool:
    """Allow offline simulated EPTS OTP only outside production (unless explicitly enabled)."""
    if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
        return os.getenv("ALLOW_CLOUD_SYNC_FALLBACK", "false").strip().lower() in ("1", "true", "yes")
    return os.getenv("ALLOW_CLOUD_SYNC_FALLBACK", "true").strip().lower() in ("1", "true", "yes", "on")


REVOKED_ADMIN_EMAILS: frozenset[str] = frozenset({
    "dpmkhammam7@gmail.com",
    "dpmkmm7@gmail.com",
})


def get_admin_emails() -> set[str]:
    """Return configured lowercase administrator email addresses from ADMIN_EMAILS env."""
    raw = os.getenv("ADMIN_EMAILS", "")
    return {
        e.strip().lower()
        for e in raw.split(",")
        if e.strip() and "@" in e and e.strip().lower() not in REVOKED_ADMIN_EMAILS
    }


def is_admin_email(email: str) -> bool:
    clean = str(email or "").strip().lower()
    if not clean or clean in REVOKED_ADMIN_EMAILS:
        return False
    return clean in get_admin_emails()

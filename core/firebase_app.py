"""Firebase Admin SDK initialization, ID Token verification, and Firestore Client factory."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token

from core.config import (
    BASE_DIR,
    FIREBASE_DATABASE_ID,
    FIREBASE_PROJECT_ID,
    IS_PRODUCTION,
    get_firebase_web_config,
)

logger = logging.getLogger("firebase_app")

_APP_LOCK = threading.Lock()
_CACHED_APP: Optional[firebase_admin.App] = None
_CACHED_APP_KEY: Optional[tuple[str, str]] = None
_CACHED_HAS_CREDENTIAL: bool = False
_GOOGLE_REQUEST = google_auth_requests.Request()


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_inmemory_firestore_enabled() -> bool:
    """Return True when the in-memory Firestore backend is explicitly enabled for tests."""
    return _parse_bool_env("USE_INMEMORY_FIRESTORE_FOR_TESTS", False)


def resolve_service_account_source() -> tuple[Optional[str], Optional[Any], str]:
    """Locate Firebase Admin Service Account credentials from env vars or local key files."""
    raw_json = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
    if raw_json:
        payload = raw_json
        if not payload.startswith("{"):
            try:
                payload = base64.b64decode(payload).decode("utf-8")
            except Exception:
                pass
        try:
            cert_dict = json.loads(payload)
            return "json", cert_dict, f"env_json:{cert_dict.get('client_email', '')}"
        except Exception as exc:
            raise RuntimeError(f"Invalid FIREBASE_SERVICE_ACCOUNT_JSON payload: {exc}") from exc

    env_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        if p.exists() and p.is_file():
            return "file", str(p), f"file:{p}"
        logger.warning("Configured Firebase service account file not found: %s", p)

    candidate_files: list[Path] = [
        BASE_DIR / "firebase-service-account.json",
        BASE_DIR / "service-account.json",
        BASE_DIR / "secrets" / "firebase-service-account.json",
        BASE_DIR / "secrets" / "service-account.json",
    ]
    for folder in (BASE_DIR, BASE_DIR / "secrets"):
        if folder.exists() and folder.is_dir():
            for match in sorted(folder.glob("*firebase-adminsdk*.json")):
                candidate_files.append(match)

    for cand in candidate_files:
        if cand.exists() and cand.is_file():
            return "file", str(cand), f"file:{cand}"

    return None, None, "none"


def _active_project_id() -> str:
    return (os.getenv("FIREBASE_PROJECT_ID") or FIREBASE_PROJECT_ID or "epanchayat-automation-tg").strip()


def _active_database_id() -> str:
    return (os.getenv("FIREBASE_DATABASE_ID") or FIREBASE_DATABASE_ID or "(default)").strip()


def get_firebase_admin_app() -> tuple[firebase_admin.App, bool]:
    """Initialize (or reuse) a Firebase Admin App scoped to the configured project."""
    global _CACHED_APP, _CACHED_APP_KEY, _CACHED_HAS_CREDENTIAL

    project_id = _active_project_id()
    src_kind, src_val, fingerprint = resolve_service_account_source()
    cache_key = (project_id, fingerprint)

    with _APP_LOCK:
        if _CACHED_APP is not None and _CACHED_APP_KEY == cache_key:
            return _CACHED_APP, _CACHED_HAS_CREDENTIAL

        cred_obj: Optional[credentials.Base] = None
        has_cred = False
        if src_kind in ("json", "file") and src_val is not None:
            cred_obj = credentials.Certificate(src_val)
            has_cred = True
        elif os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCE_METADATA_HOST"):
            try:
                cred_obj = credentials.ApplicationDefault()
                has_cred = True
            except Exception:
                cred_obj = None
                has_cred = False

        app_name = f"epanchayat_{abs(hash(cache_key))}"
        try:
            app_inst = firebase_admin.get_app(app_name)
        except ValueError:
            app_inst = firebase_admin.initialize_app(
                cred_obj,
                options={"projectId": project_id},
                name=app_name,
            )

        _CACHED_APP = app_inst
        _CACHED_APP_KEY = cache_key
        _CACHED_HAS_CREDENTIAL = has_cred
        return app_inst, has_cred


def get_live_firestore_client() -> Optional[Any]:
    """Return a live (or emulator) Cloud Firestore client when configured, else None."""
    if is_inmemory_firestore_enabled():
        return None

    emulator_host = (os.getenv("FIRESTORE_EMULATOR_HOST") or "").strip()
    app_inst, has_cred = get_firebase_admin_app()
    if not has_cred and not emulator_host:
        if IS_PRODUCTION:
            raise RuntimeError(
                "Cloud Firestore credentials missing in production. Set FIREBASE_SERVICE_ACCOUNT_PATH, "
                "GOOGLE_APPLICATION_CREDENTIALS, or FIREBASE_SERVICE_ACCOUNT_JSON."
            )
        return None

    db_id = _active_database_id()
    return firestore.client(app=app_inst, database_id=db_id)


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase Authentication ID token and return normalized officer identity claims."""
    clean_token = str(id_token or "").strip()
    if not clean_token:
        raise ValueError("Firebase ID token is required.")

    project_id = _active_project_id()
    app_inst, has_cred = get_firebase_admin_app()
    emulator_auth = bool((os.getenv("FIREBASE_AUTH_EMULATOR_HOST") or "").strip())

    try:
        # Tolerate up to 60s NTP drift between local OS clock and Google Auth servers
        if has_cred or emulator_auth:
            decoded = fb_auth.verify_id_token(
                clean_token,
                app=app_inst,
                check_revoked=False,
                clock_skew_seconds=60,
            )
        else:
            # Cryptographically verify RS256 Firebase JWT against Google's public certificates
            decoded = google_id_token.verify_firebase_token(
                clean_token,
                _GOOGLE_REQUEST,
                audience=project_id,
                clock_skew_in_seconds=60,
            )
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        raise ValueError("Invalid or expired Firebase ID token.") from exc

    if not isinstance(decoded, dict):
        raise ValueError("Invalid Firebase ID token payload.")

    uid = str(decoded.get("uid") or decoded.get("user_id") or decoded.get("sub") or "").strip()
    email = str(decoded.get("email") or "").strip().lower()
    if not uid or not email:
        raise ValueError("Firebase token is missing verified UID or email address.")

    if decoded.get("email_verified") is False:
        raise ValueError("Google account email address must be verified.")

    firebase_meta = decoded.get("firebase") if isinstance(decoded.get("firebase"), dict) else {}
    provider = str(firebase_meta.get("sign_in_provider") or "google.com").strip()

    return {
        "firebase_uid": uid,
        "gmail": email,
        "name": str(decoded.get("name") or email.split("@")[0]).strip(),
        "profile_picture": str(decoded.get("picture") or "").strip(),
        "sign_in_provider": provider,
        "email_verified": True,
    }


def get_firebase_runtime_status() -> dict[str, Any]:
    """Return non-secret Firebase runtime and Firestore connectivity posture."""
    cfg = get_firebase_web_config()
    _, _, fingerprint = resolve_service_account_source()
    emulator_host = (os.getenv("FIRESTORE_EMULATOR_HOST") or "").strip()
    has_creds = fingerprint != "none"
    if is_inmemory_firestore_enabled():
        mode = "in_memory_test"
    elif emulator_host:
        mode = "emulator"
    elif has_creds:
        mode = "live_firestore"
    else:
        mode = "in_memory_dev"

    return {
        "project_id": cfg["projectId"],
        "auth_domain": cfg["authDomain"],
        "database_id": _active_database_id(),
        "location": "asia-south1",
        "firestore_mode": mode,
        "service_account_configured": has_creds,
        "auth_configured": bool(cfg.get("apiKey") and cfg.get("projectId")),
    }

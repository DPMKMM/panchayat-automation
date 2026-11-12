"""Centralized Cloud Firestore Identity, Session, Policy, Feedback & Analytics Store."""

from __future__ import annotations

import copy
import hashlib
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from core.config import IS_PRODUCTION, REVOKED_ADMIN_EMAILS, is_admin_email
from core.firebase_app import get_live_firestore_client

logger = logging.getLogger("firebase_store")

VALID_DESIGNATIONS = {"DPO", "DPM", "DLPO", "MPDO", "MPO", "PS", "DEO"}
VALID_ROLES = {"Mandal Level", "Division Level", "District Level"}
VALID_SCOPES = {"portal", "console"}
VALID_STATUSES = {"Active", "Disabled"}
SESSION_TTL_SECONDS = 86400 * 7  # 7 days persistent scoped session

COL_USERS = "users"
COL_SESSIONS = "sessions"
COL_POLICY = "access_policy"
COL_FEEDBACK = "feedback"
COL_USAGE = "usage_logs"

_MEM_LOCK = threading.RLock()
_MEM_WARNED = False


class _InMemoryDocSnapshot:
    def __init__(self, doc_id: str, data: Optional[dict[str, Any]]) -> None:
        self.id = doc_id
        self._data = copy.deepcopy(data) if data is not None else None

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> Optional[dict[str, Any]]:
        return copy.deepcopy(self._data)


class _InMemoryDocRef:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    def get(self) -> _InMemoryDocSnapshot:
        with _MEM_LOCK:
            return _InMemoryDocSnapshot(self.id, self._store.get(self.id))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        with _MEM_LOCK:
            payload = copy.deepcopy(data)
            if merge and self.id in self._store:
                merged = copy.deepcopy(self._store[self.id])
                merged.update(payload)
                self._store[self.id] = merged
            else:
                self._store[self.id] = payload

    def update(self, data: dict[str, Any]) -> None:
        with _MEM_LOCK:
            if self.id not in self._store:
                raise KeyError(f"Document {self.id} does not exist")
            merged = copy.deepcopy(self._store[self.id])
            merged.update(copy.deepcopy(data))
            self._store[self.id] = merged

    def delete(self) -> None:
        with _MEM_LOCK:
            self._store.pop(self.id, None)


class _InMemoryQuery:
    def __init__(
        self,
        store: dict[str, dict[str, Any]],
        filters: Optional[list[tuple[str, str, Any]]] = None,
        limit_val: Optional[int] = None,
    ) -> None:
        self._store = store
        self._filters = filters or []
        self._limit = limit_val

    def where(
        self,
        field_path: Optional[str] = None,
        op_string: Optional[str] = None,
        value: Any = None,
        *,
        filter: Optional[FieldFilter] = None,
    ) -> "_InMemoryQuery":
        next_filters = list(self._filters)
        if filter is not None:
            next_filters.append((filter.field_path, filter.op_string, filter.value))
        elif field_path is not None and op_string is not None:
            next_filters.append((field_path, op_string, value))
        return _InMemoryQuery(self._store, next_filters, self._limit)

    def limit(self, count: int) -> "_InMemoryQuery":
        return _InMemoryQuery(self._store, list(self._filters), count)

    def stream(self) -> list[_InMemoryDocSnapshot]:
        with _MEM_LOCK:
            items = list(self._store.items())
        out: list[_InMemoryDocSnapshot] = []
        for doc_id, data in items:
            if _matches_filters(data, self._filters):
                out.append(_InMemoryDocSnapshot(doc_id, data))
                if self._limit is not None and len(out) >= self._limit:
                    break
        return out


class _InMemoryCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: Optional[str] = None) -> _InMemoryDocRef:
        key = doc_id or f"auto_{secrets.token_hex(8)}"
        return _InMemoryDocRef(self._store, key)

    def where(
        self,
        field_path: Optional[str] = None,
        op_string: Optional[str] = None,
        value: Any = None,
        *,
        filter: Optional[FieldFilter] = None,
    ) -> _InMemoryQuery:
        return _InMemoryQuery(self._store).where(field_path, op_string, value, filter=filter)

    def limit(self, count: int) -> _InMemoryQuery:
        return _InMemoryQuery(self._store, limit_val=count)

    def stream(self) -> list[_InMemoryDocSnapshot]:
        return _InMemoryQuery(self._store).stream()


class _InMemoryFirestoreClient:
    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _InMemoryCollection:
        with _MEM_LOCK:
            bucket = self._collections.setdefault(name, {})
        return _InMemoryCollection(bucket)

    def reset(self) -> None:
        with _MEM_LOCK:
            self._collections.clear()


_INMEM_CLIENT = _InMemoryFirestoreClient()


def _matches_filters(doc: dict[str, Any], filters: list[tuple[str, str, Any]]) -> bool:
    for field_path, op, val in filters:
        actual = doc.get(field_path)
        if op == "==":
            if actual != val:
                return False
        elif op == "!=":
            if actual == val:
                return False
        elif op == ">=":
            if actual is None or actual < val:
                return False
        elif op == "<=":
            if actual is None or actual > val:
                return False
        elif op == ">":
            if actual is None or actual <= val:
                return False
        elif op == "<":
            if actual is None or actual >= val:
                return False
        elif op == "in":
            if actual not in (val or ()):
                return False
    return True


def reset_inmemory_firestore() -> None:
    """Clear the test in-memory Firestore collections cleanly between isolated test runs."""
    _INMEM_CLIENT.reset()


def _db():
    """Return active Cloud Firestore client, or development/test in-memory backend."""
    global _MEM_WARNED
    live = get_live_firestore_client()
    if live is not None:
        return live

    if IS_PRODUCTION:
        raise RuntimeError("Cloud Firestore client unavailable in production.")

    if not _MEM_WARNED:
        logger.warning(
            "Cloud Firestore service account credentials not configured; using ephemeral "
            "development in-memory Firestore store. Set FIREBASE_SERVICE_ACCOUNT_PATH for live persistence."
        )
        _MEM_WARNED = True
    return _INMEM_CLIENT


def init_db(*args: Any, **kwargs: Any) -> None:
    """Verify Firestore store handle initializes cleanly on startup."""
    _db()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_doc_id(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _normalize_user_doc(doc_id: str, raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    d = dict(raw)
    gmail = str(d.get("gmail") or d.get("email") or "").strip().lower()
    desig = str(d.get("designation") or "").strip().upper()
    role = str(d.get("role") or "").strip() or designation_to_role(desig)
    uid = str(d.get("firebase_uid") or d.get("google_uid") or "").strip()
    if gmail in REVOKED_ADMIN_EMAILS:
        is_adm = False
    else:
        is_adm = bool(d.get("is_admin", False)) or is_admin_email(gmail)
    return {
        "user_id": str(d.get("user_id") or doc_id),
        "firebase_uid": uid,
        "google_uid": uid,
        "email": gmail,
        "gmail": gmail,
        "name": str(d.get("name") or "").strip(),
        "designation": desig,
        "role": role,
        "mobile_number": str(d.get("mobile_number") or "").strip(),
        "profile_picture": str(d.get("profile_picture") or "").strip(),
        "registration_date": str(d.get("registration_date") or ""),
        "last_login": str(d.get("last_login") or ""),
        "updated_at": str(d.get("updated_at") or d.get("last_login") or ""),
        "account_status": str(d.get("account_status") or "Active"),
        "profile_completed": bool(d.get("profile_completed", False)),
        "is_admin": is_adm,
        "can_access_portal": bool(d.get("can_access_portal", True)),
        "can_access_console": bool(d.get("can_access_console", True)),
    }


def designation_to_role(designation: str) -> str:
    d = str(designation or "").strip().upper()
    if d in {"DPO", "DPM"}:
        return "District Level"
    if d == "DLPO":
        return "Division Level"
    if d in {"MPDO", "MPO", "PS", "DEO"}:
        return "Mandal Level"
    return ""


def get_user_by_firebase_uid(firebase_uid: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by Firebase UID (falling back to legacy google_uid)."""
    clean_uid = str(firebase_uid or "").strip()
    if not clean_uid:
        return None
    col = _db().collection(COL_USERS)
    for field_name in ("firebase_uid", "google_uid"):
        snaps = list(col.where(filter=FieldFilter(field_name, "==", clean_uid)).limit(1).stream())
        if snaps:
            return _normalize_user_doc(snaps[0].id, snaps[0].to_dict())
    return None


get_user_by_google_uid = get_user_by_firebase_uid


def get_user_by_gmail(gmail: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by authenticated Gmail address."""
    clean_email = str(gmail or "").strip().lower()
    if not clean_email:
        return None
    col = _db().collection(COL_USERS)
    snaps = list(col.where(filter=FieldFilter("gmail", "==", clean_email)).limit(1).stream())
    if snaps:
        return _normalize_user_doc(snaps[0].id, snaps[0].to_dict())
    return None


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by internal user_id."""
    clean_id = str(user_id or "").strip()
    if not clean_id:
        return None
    snap = _db().collection(COL_USERS).document(clean_id).get()
    if snap.exists:
        return _normalize_user_doc(snap.id, snap.to_dict())
    snaps = list(_db().collection(COL_USERS).where(filter=FieldFilter("user_id", "==", clean_id)).limit(1).stream())
    if snaps:
        return _normalize_user_doc(snaps[0].id, snaps[0].to_dict())
    return None


def get_or_create_firebase_user(
    firebase_uid: str,
    gmail: str,
    name: str = "",
    profile_picture: str = "",
) -> tuple[dict[str, Any], bool]:
    """Find officer by firebase_uid or gmail in Cloud Firestore, or create a new officer profile."""
    now = _utc_now_iso()
    clean_uid = str(firebase_uid or "").strip()
    clean_email = str(gmail or "").strip().lower()
    clean_name = str(name or "").strip() or (clean_email.split("@")[0] if "@" in clean_email else "Officer")
    clean_pic = str(profile_picture or "").strip()

    if not clean_uid and not clean_email:
        raise ValueError("Both firebase_uid and gmail cannot be empty")
    if not clean_uid:
        clean_uid = f"firebase:{clean_email}"

    existing = get_user_by_firebase_uid(clean_uid)
    if existing is None and clean_email:
        existing = get_user_by_gmail(clean_email)

    col = _db().collection(COL_USERS)
    if existing is not None:
        updates: dict[str, Any] = {
            "firebase_uid": clean_uid,
            "google_uid": clean_uid,
            "email": clean_email or existing["gmail"],
            "gmail": clean_email or existing["gmail"],
            "last_login": now,
            "updated_at": now,
        }
        if clean_pic:
            updates["profile_picture"] = clean_pic
        if not existing.get("name") and clean_name:
            updates["name"] = clean_name
        if clean_email in REVOKED_ADMIN_EMAILS:
            if existing.get("is_admin"):
                updates["is_admin"] = False
        elif is_admin_email(clean_email) and not existing.get("is_admin"):
            updates["is_admin"] = True
        col.document(existing["user_id"]).update(updates)
        updated = get_user_by_id(existing["user_id"])
        return updated or existing, False

    new_user_id = f"usr_{secrets.token_hex(6)}"
    doc_payload = {
        "user_id": new_user_id,
        "firebase_uid": clean_uid,
        "google_uid": clean_uid,
        "email": clean_email,
        "gmail": clean_email,
        "name": clean_name,
        "designation": "",
        "role": "",
        "mobile_number": "",
        "profile_picture": clean_pic,
        "registration_date": now,
        "last_login": now,
        "updated_at": now,
        "account_status": "Active",
        "profile_completed": False,
        "is_admin": is_admin_email(clean_email),
        "can_access_portal": True,
        "can_access_console": True,
    }
    col.document(new_user_id).set(doc_payload)
    created = get_user_by_id(new_user_id)
    return created or doc_payload, True


def complete_user_profile(
    user_id: str,
    full_name: str,
    designation: str,
    mobile_number: str,
    role: str = "",
) -> dict[str, Any]:
    """Validate and save mandatory officer profile details in Cloud Firestore."""
    clean_uid = str(user_id or "").strip()
    clean_name = re.sub(r"\s+", " ", str(full_name or "").strip())
    if len(clean_name) < 2:
        raise ValueError("Please enter your valid full name.")

    clean_desig = str(designation or "").strip().upper()
    if clean_desig not in VALID_DESIGNATIONS:
        raise ValueError(f"Invalid designation. Allowed: {', '.join(sorted(VALID_DESIGNATIONS))}")

    digits = re.sub(r"\D+", "", str(mobile_number or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("Mobile number must be a valid 10-digit Indian number (starting with 6-9).")

    existing = get_user_by_id(clean_uid)
    if existing is None:
        raise ValueError("Officer account not found.")

    clean_role = str(role or "").strip()
    if clean_role:
        if clean_role not in VALID_ROLES:
            raise ValueError(f"Invalid role level. Allowed: {', '.join(sorted(VALID_ROLES))}")
    else:
        clean_role = designation_to_role(clean_desig)

    _db().collection(COL_USERS).document(clean_uid).update(
        {
            "name": clean_name,
            "designation": clean_desig,
            "role": clean_role,
            "mobile_number": digits,
            "profile_completed": True,
            "updated_at": _utc_now_iso(),
        }
    )
    updated = get_user_by_id(clean_uid)
    if updated is None:
        raise RuntimeError("Failed to read updated officer profile from Cloud Firestore.")
    return updated


def authenticate_or_register_firebase_user(
    firebase_uid: str,
    gmail: str,
    name: str,
    profile_picture: str = "",
    platform_scope: str = "portal",
) -> tuple[dict[str, Any], bool]:
    """Authenticate an existing Firebase officer or register a new profile."""
    user, is_new = get_or_create_firebase_user(
        firebase_uid=firebase_uid,
        gmail=gmail,
        name=name,
        profile_picture=profile_picture,
    )
    if user.get("account_status") != "Active":
        raise PermissionError("Your account has been disabled by an administrator. Please contact district support.")
    scope = str(platform_scope or "portal").strip().lower()
    if scope == "portal" and not user.get("can_access_portal", True):
        raise PermissionError("Access to e-Panchayat Automation is restricted for your account.")
    if scope == "console" and not user.get("can_access_console", True):
        raise PermissionError("Access to e-Panchayat Automation Console is restricted for your account.")
    return user, is_new


def register_user_profile(
    user_id: str,
    name: str = "",
    designation: str = "",
    role: str = "",
    mobile_number: str = "",
    *,
    full_name: str = "",
) -> tuple[bool, str, Optional[dict[str, Any]]]:
    """Validate and persist mandatory officer profile completion values cleanly."""
    chosen_name = name or full_name
    try:
        updated = complete_user_profile(
            user_id=user_id,
            full_name=chosen_name,
            designation=designation,
            mobile_number=mobile_number,
            role=role,
        )
        return True, "Officer profile registered successfully!", updated
    except ValueError as exc:
        return False, str(exc), None
    except Exception as exc:
        logger.error("Failed to save profile in Cloud Firestore: %s", exc)
        return False, f"Failed to save profile: {exc}", None


def create_session(
    user_id: str,
    app_scope: str = "portal",
    user_agent: str = "",
    ip_address: str = "",
) -> str:
    """Create a persistent Firestore session token scoped strictly to portal or console."""
    scope = str(app_scope or "portal").strip().lower()
    if scope not in VALID_SCOPES:
        scope = "portal"
    token = secrets.token_urlsafe(32)
    now_ts = time.time()
    exp_ts = now_ts + SESSION_TTL_SECONDS
    now_iso = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
    exp_iso = datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()

    doc_id = _token_doc_id(token)
    _db().collection(COL_SESSIONS).document(doc_id).set(
        {
            "token_hash": doc_id,
            "user_id": str(user_id),
            "app_scope": scope,
            "user_agent": str(user_agent or "")[:255],
            "ip_address": str(ip_address or "")[:64],
            "created_at": now_iso,
            "expires_at": exp_iso,
            "expires_at_ts": exp_ts,
            "revoked": False,
        }
    )
    return token


def create_portal_session(
    user_id: str,
    app_scope: str = "portal",
    user_agent: str = "",
    ip_address: str = "",
) -> str:
    """Issue a scoped backend session cookie token for portal or console."""
    return create_session(
        user_id=user_id,
        app_scope=app_scope,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def get_session_user(token: str, app_scope: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Validate Firestore session token (matching app_scope if specified) and return user."""
    clean_tok = str(token or "").strip()
    if not clean_tok:
        return None
    snap = _db().collection(COL_SESSIONS).document(_token_doc_id(clean_tok)).get()
    if not snap.exists:
        return None
    sess = snap.to_dict() or {}
    if sess.get("revoked"):
        return None
    exp_ts = float(sess.get("expires_at_ts") or 0)
    if exp_ts <= time.time():
        return None
    if app_scope is not None:
        wanted = str(app_scope).strip().lower()
        if str(sess.get("app_scope") or "").strip().lower() != wanted:
            return None

    user = get_user_by_id(str(sess.get("user_id") or ""))
    if user is None or user.get("account_status") != "Active":
        return None
    user["session_scope"] = str(sess.get("app_scope") or "portal")
    return user


def get_portal_session(token: str, app_scope: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Validate persistent Firestore session token scoped cleanly to portal or console."""
    return get_session_user(token, app_scope=app_scope)


def revoke_session(token: str) -> bool:
    """Mark a persistent Firestore session token as revoked."""
    clean_tok = str(token or "").strip()
    if not clean_tok:
        return False
    ref = _db().collection(COL_SESSIONS).document(_token_doc_id(clean_tok))
    if ref.get().exists:
        ref.update({"revoked": True})
        return True
    return False


def revoke_portal_session(token: str) -> bool:
    """Revoke portal/console session token on logout."""
    return revoke_session(token)


def revoke_user_sessions(user_id: str, app_scope: Optional[str] = None) -> None:
    """Revoke all active sessions belonging to user_id (optionally filtered by app_scope)."""
    clean_uid = str(user_id or "").strip()
    if not clean_uid:
        return
    snaps = _db().collection(COL_SESSIONS).where(filter=FieldFilter("user_id", "==", clean_uid)).stream()
    wanted_scope = str(app_scope).strip().lower() if app_scope in VALID_SCOPES else None
    col = _db().collection(COL_SESSIONS)
    for snap in snaps:
        data = snap.to_dict() or {}
        if data.get("revoked"):
            continue
        if wanted_scope and str(data.get("app_scope") or "").strip().lower() != wanted_scope:
            continue
        col.document(snap.id).update({"revoked": True})


def list_users(
    search: str = "",
    designation: str = "",
    role: str = "",
    account_status: str = "",
    status: str = "",
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List officer records from Cloud Firestore with admin filters and pagination."""
    q = str(search or "").strip().lower()
    desig = str(designation or "").strip().upper()
    role_f = str(role or "").strip()
    stat_f = str(account_status or status or "").strip()

    rows: list[dict[str, Any]] = []
    for snap in _db().collection(COL_USERS).stream():
        u = _normalize_user_doc(snap.id, snap.to_dict())
        if u is None:
            continue
        if q:
            haystack = " ".join(
                [u["name"].lower(), u["gmail"].lower(), u["mobile_number"].lower(), u["user_id"].lower()]
            )
            if q not in haystack:
                continue
        if desig and u["designation"] != desig:
            continue
        if role_f and u["role"] != role_f:
            continue
        if stat_f and u["account_status"] != stat_f:
            continue
        rows.append(u)

    rows.sort(key=lambda item: str(item.get("last_login") or item.get("registration_date") or ""), reverse=True)
    total = len(rows)
    start = max(0, int(offset or 0))
    lim = max(1, int(limit or 200))
    return rows[start : start + lim], total


def update_user_admin(
    user_id: str,
    updates_dict: Optional[dict[str, Any]] = None,
    *,
    designation: Optional[str] = None,
    account_status: Optional[str] = None,
    is_admin: Optional[bool] = None,
    can_access_portal: Optional[bool] = None,
    can_access_console: Optional[bool] = None,
) -> tuple[bool, str, Optional[dict[str, Any]]]:
    """Update admin-controlled permissions and status for an officer in Cloud Firestore."""
    existing = get_user_by_id(user_id)
    if existing is None:
        return False, "Officer account not found.", None

    raw = dict(updates_dict or {})
    if designation is not None:
        raw["designation"] = designation
    if account_status is not None:
        raw["account_status"] = account_status
    if is_admin is not None:
        raw["is_admin"] = is_admin
    if can_access_portal is not None:
        raw["can_access_portal"] = can_access_portal
    if can_access_console is not None:
        raw["can_access_console"] = can_access_console

    updates: dict[str, Any] = {}
    if "name" in raw and raw["name"] is not None:
        clean_name = re.sub(r"\s+", " ", str(raw["name"]).strip())
        if len(clean_name) < 2:
            return False, "Officer name must be at least 2 characters.", None
        updates["name"] = clean_name

    if "designation" in raw and raw["designation"] is not None:
        d = str(raw["designation"]).strip().upper()
        if d not in VALID_DESIGNATIONS:
            return False, "Invalid designation.", None
        updates["designation"] = d
        updates["role"] = designation_to_role(d)

    if "role" in raw and raw["role"] is not None and "designation" not in updates:
        r = str(raw["role"]).strip()
        if r not in VALID_ROLES:
            return False, "Invalid role level.", None
        updates["role"] = r

    if "mobile_number" in raw and raw["mobile_number"] is not None:
        digits = re.sub(r"\D+", "", str(raw["mobile_number"]))
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if digits and not re.fullmatch(r"[6-9]\d{9}", digits):
            return False, "Mobile number must be a valid 10-digit Indian number (starting with 6-9).", None
        updates["mobile_number"] = digits

    eff_status = raw.get("account_status")
    if eff_status is not None:
        st = str(eff_status).strip()
        if st not in VALID_STATUSES:
            return False, "Status must be 'Active' or 'Disabled'.", None
        updates["account_status"] = st

    if "is_admin" in raw and raw["is_admin"] is not None:
        if str(existing.get("gmail") or "").strip().lower() in REVOKED_ADMIN_EMAILS and bool(raw["is_admin"]):
            return False, "Admin privileges are revoked for this account on user portals.", None
        updates["is_admin"] = bool(raw["is_admin"])
    if "can_access_portal" in raw and raw["can_access_portal"] is not None:
        updates["can_access_portal"] = bool(raw["can_access_portal"])
    if "can_access_console" in raw and raw["can_access_console"] is not None:
        updates["can_access_console"] = bool(raw["can_access_console"])

    if updates:
        updates["updated_at"] = _utc_now_iso()
        _db().collection(COL_USERS).document(existing["user_id"]).update(updates)

    if updates.get("account_status") == "Disabled":
        revoke_user_sessions(existing["user_id"])
    else:
        if updates.get("can_access_portal") is False:
            revoke_user_sessions(existing["user_id"], app_scope="portal")
        if updates.get("can_access_console") is False:
            revoke_user_sessions(existing["user_id"], app_scope="console")

    updated = get_user_by_id(existing["user_id"])
    return True, "Officer permissions updated successfully.", updated


def log_usage(
    *,
    user_id: str = "",
    gmail: str = "",
    platform_scope: str = "portal",
    module: str = "",
    action: str = "",
    details: str = "",
) -> None:
    """Append a lightweight analytics event to Firestore usage_logs."""
    try:
        now_ts = time.time()
        doc_id = f"log_{int(now_ts * 1000)}_{secrets.token_hex(4)}"
        _db().collection(COL_USAGE).document(doc_id).set(
            {
                "log_id": doc_id,
                "user_id": str(user_id or ""),
                "gmail": str(gmail or "").lower(),
                "platform_scope": str(platform_scope or "portal"),
                "module": str(module or ""),
                "action": str(action or ""),
                "details": str(details or "")[:255],
                "created_at": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
                "created_at_ts": now_ts,
            }
        )
    except Exception as exc:
        logger.debug("Non-fatal Firestore usage_log skip: %s", exc)


def get_usage_stats(days: int = 30) -> dict[str, Any]:
    """Return aggregate officer, session, feedback, and recent N-day module usage KPIs."""
    lookback_days = max(1, int(days or 30))
    users, total_users = list_users(limit=5000)
    active_users = sum(1 for u in users if u["account_status"] == "Active")
    disabled_users = total_users - active_users
    completed_profiles = sum(1 for u in users if u["profile_completed"])

    desig_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for u in users:
        d_key = u["designation"] or "Pending"
        desig_counts[d_key] = desig_counts.get(d_key, 0) + 1
        r_key = u["role"] or "Pending"
        role_counts[r_key] = role_counts.get(r_key, 0) + 1

    now_ts = time.time()
    session_counts: dict[str, int] = {}
    for snap in _db().collection(COL_SESSIONS).where(filter=FieldFilter("revoked", "==", False)).stream():
        s = snap.to_dict() or {}
        if float(s.get("expires_at_ts") or 0) > now_ts:
            sc = str(s.get("app_scope") or "portal")
            session_counts[sc] = session_counts.get(sc, 0) + 1

    total_feedback = sum(1 for _ in _db().collection(COL_FEEDBACK).stream())

    cutoff_ts = now_ts - lookback_days * 86400
    usage_counts: dict[tuple[str, str], int] = {}
    for snap in _db().collection(COL_USAGE).where(filter=FieldFilter("created_at_ts", ">=", cutoff_ts)).stream():
        row = snap.to_dict() or {}
        k = (str(row.get("platform_scope") or "portal"), str(row.get("module") or "action"))
        usage_counts[k] = usage_counts.get(k, 0) + 1

    by_desig = sorted(
        [{"designation": k, "count": v} for k, v in desig_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    by_role = sorted(
        [{"role": k, "count": v} for k, v in role_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    active_sessions = [
        {"app_scope": k, "count": v} for k, v in sorted(session_counts.items())
    ]
    module_usage = sorted(
        [{"platform_scope": sc, "module": mod, "count": cnt} for (sc, mod), cnt in usage_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:20]

    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "completed_profiles": completed_profiles,
        "by_designation": by_desig,
        "by_role": by_role,
        "active_sessions": active_sessions,
        "total_feedback": total_feedback,
        "module_usage": module_usage,
    }


def get_all_policy_entries() -> dict[str, dict[str, str]]:
    """Fetch all persisted access_policy flags from Cloud Firestore."""
    out: dict[str, dict[str, str]] = {}
    for snap in _db().collection(COL_POLICY).stream():
        d = snap.to_dict() or {}
        key = str(d.get("key") or snap.id)
        out[key] = {
            "value": str(d.get("value") or "true"),
            "updated_at": str(d.get("updated_at") or ""),
            "updated_by": str(d.get("updated_by") or ""),
        }
    return out


def set_policy_entry(key: str, value: str, updated_by: str = "") -> None:
    """Persist an administrator access policy flag to Cloud Firestore."""
    now = _utc_now_iso()
    clean_key = str(key).strip()
    _db().collection(COL_POLICY).document(clean_key).set(
        {
            "key": clean_key,
            "value": str(value).strip(),
            "updated_at": now,
            "updated_by": str(updated_by or "").strip(),
        }
    )


def save_feedback(
    *,
    message: str,
    name: str = "",
    email: str = "",
    gmail: str = "",
    designation: str = "",
    role: str = "",
    category: str = "General Feedback",
    rating: int = 5,
    user_id: str = "",
    app_scope: str = "portal",
) -> dict[str, Any]:
    """Persist an officer feedback submission in Cloud Firestore and return the saved record."""
    now = _utc_now_iso()
    feedback_id = f"fb_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
    clean_email = str(email or gmail or "").strip().lower()
    record = {
        "feedback_id": feedback_id,
        "id": feedback_id,
        "user_id": str(user_id or ""),
        "email": clean_email,
        "gmail": clean_email,
        "name": str(name or "").strip(),
        "designation": str(designation or "").strip(),
        "role": str(role or "").strip(),
        "category": str(category or "General Feedback").strip(),
        "message": str(message or "").strip(),
        "rating": max(1, min(5, int(rating or 5))),
        "app_scope": str(app_scope or "portal"),
        "created_at": now,
    }
    _db().collection(COL_FEEDBACK).document(feedback_id).set(record)
    return record


def get_recent_feedback(limit: int = 50) -> list[dict[str, Any]]:
    """Return latest officer feedback submissions ordered newest first."""
    items = []
    for snap in _db().collection(COL_FEEDBACK).stream():
        d = snap.to_dict()
        if d:
            item = dict(d)
            item.setdefault("feedback_id", snap.id)
            item.setdefault("id", snap.id)
            item.setdefault("email", item.get("gmail") or "")
            items.append(item)
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]

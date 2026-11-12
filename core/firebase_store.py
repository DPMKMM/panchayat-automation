"""Centralized Cloud Firestore Identity, Session, Policy, Feedback & Analytics Store."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from core.config import IS_PRODUCTION, REVOKED_ADMIN_EMAILS, get_data_dir, is_admin_email
from core.firebase_app import get_live_firestore_client, is_inmemory_firestore_enabled

logger = logging.getLogger("firebase_store")

VALID_DESIGNATIONS = {"DPO", "DPM", "DLPO", "MPDO", "MPO", "PS", "DEO"}
VALID_ROLES = {"Mandal Level", "Division Level", "District Level"}
VALID_SCOPES = {"portal", "console"}
VALID_STATUSES = {"Active", "Disabled"}
VALID_SUBSCRIPTION_STATUSES = {"free_preview", "trial", "active", "past_due", "cancelled", "expired"}
SESSION_TTL_SECONDS = 86400 * 7  # 7 days persistent scoped session

COL_USERS = "users"
COL_SESSIONS = "sessions"
COL_POLICY = "access_policy"
COL_FEEDBACK = "feedback"
COL_USAGE = "usage_logs"
COL_PLANS = "subscription_plans"
COL_SUBSCRIPTIONS = "subscriptions"
COL_PAYMENTS = "payments"

DEFAULT_SUBSCRIPTION_PLANS: tuple[dict[str, Any], ...] = (
    {
        "plan_id": "plan_monthly",
        "code": "monthly",
        "name": "Monthly Officer Pass",
        "description": "Full access to Automated Portal Robots, Multi-Day DSR, and Priority Utilities for 30 days.",
        "amount_inr": 99.0,
        "amount_paise": 9900,
        "currency": "INR",
        "duration_days": 30,
        "razorpay_plan_id": "",
        "features": [
            "Unlimited Automated Portal Robots (DSR, GP Balance, MAS)",
            "Live House Tax DCB Analytics & Exports",
            "Full Excel & PDF Studio Access",
        ],
        "is_active": True,
        "sort_order": 1,
    },
    {
        "plan_id": "plan_quarterly",
        "code": "quarterly",
        "name": "Quarterly Mandal/District Pass",
        "description": "90-day governance automation & live portal reporting access.",
        "amount_inr": 249.0,
        "amount_paise": 24900,
        "currency": "INR",
        "duration_days": 90,
        "razorpay_plan_id": "",
        "features": [
            "Everything in Monthly Officer Pass",
            "90-Day Uninterrupted Portal Robot Access",
            "Priority Reporting Queue",
        ],
        "is_active": True,
        "sort_order": 2,
    },
    {
        "plan_id": "plan_annual",
        "code": "annual",
        "name": "Annual Governance Pass",
        "description": "365-day unlimited access across all reporting & utility modules.",
        "amount_inr": 899.0,
        "amount_paise": 89900,
        "currency": "INR",
        "duration_days": 365,
        "razorpay_plan_id": "",
        "features": [
            "1 Full Year Unlimited Portal & Console Access",
            "All Excel, PDF & Manual DSR Studios",
            "Save 25% vs Monthly Plan",
        ],
        "is_active": True,
        "sort_order": 3,
    },
)

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
    def __init__(
        self,
        store: dict[str, dict[str, Any]],
        doc_id: str,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self._store = store
        self.id = doc_id
        self._on_change = on_change

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
            if self._on_change:
                self._on_change()

    def update(self, data: dict[str, Any]) -> None:
        with _MEM_LOCK:
            if self.id not in self._store:
                raise KeyError(f"Document {self.id} does not exist")
            merged = copy.deepcopy(self._store[self.id])
            merged.update(copy.deepcopy(data))
            self._store[self.id] = merged
            if self._on_change:
                self._on_change()

    def delete(self) -> None:
        with _MEM_LOCK:
            self._store.pop(self.id, None)
            if self._on_change:
                self._on_change()


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
    def __init__(
        self,
        store: dict[str, dict[str, Any]],
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self._store = store
        self._on_change = on_change

    def document(self, doc_id: Optional[str] = None) -> _InMemoryDocRef:
        key = doc_id or f"auto_{secrets.token_hex(8)}"
        return _InMemoryDocRef(self._store, key, on_change=self._on_change)

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
    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}
        self._persist_path = persist_path
        if self._persist_path is not None:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                with _MEM_LOCK:
                    self._collections = raw
        except Exception as exc:
            logger.warning("Could not load fallback store %s: %s", self._persist_path, exc)

    def _save_to_disk(self) -> None:
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._persist_path.with_suffix(".tmp")
            payload = json.dumps(self._collections, ensure_ascii=False)
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, self._persist_path)
        except Exception as exc:
            logger.warning("Could not persist fallback store %s: %s", self._persist_path, exc)

    def collection(self, name: str) -> _InMemoryCollection:
        with _MEM_LOCK:
            bucket = self._collections.setdefault(name, {})
        on_change = self._save_to_disk if self._persist_path is not None else None
        return _InMemoryCollection(bucket, on_change=on_change)

    def reset(self) -> None:
        with _MEM_LOCK:
            self._collections.clear()
            if self._persist_path is not None:
                self._save_to_disk()


_INMEM_CLIENT = _InMemoryFirestoreClient()
_DEV_PERSIST_CLIENT: Optional[_InMemoryFirestoreClient] = None
_DEV_PERSIST_PATH: Optional[Path] = None


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
    """Return active Cloud Firestore client, isolated test RAM store, or disk-backed dev store."""
    global _MEM_WARNED, _DEV_PERSIST_CLIENT, _DEV_PERSIST_PATH
    live = get_live_firestore_client()
    if live is not None:
        return live

    if IS_PRODUCTION:
        raise RuntimeError("Cloud Firestore client unavailable in production.")

    if is_inmemory_firestore_enabled():
        return _INMEM_CLIENT

    target_path = (get_data_dir() / "dev_firestore_store.json").resolve()
    with _MEM_LOCK:
        if _DEV_PERSIST_CLIENT is None or _DEV_PERSIST_PATH != target_path:
            _DEV_PERSIST_CLIENT = _InMemoryFirestoreClient(persist_path=target_path)
            _DEV_PERSIST_PATH = target_path
        if not _MEM_WARNED:
            logger.warning(
                "Cloud Firestore service account credentials not configured; persisting local store at %s. "
                "Add secrets/firebase-service-account.json or set FIREBASE_SERVICE_ACCOUNT_PATH for Cloud Firestore.",
                target_path,
            )
            _MEM_WARNED = True
        return _DEV_PERSIST_CLIENT


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
    has_sub = bool(d.get("has_automated_subscription", False))
    sub_status = str(d.get("subscription_status") or ("active" if has_sub else "free_preview")).strip().lower()
    if sub_status not in VALID_SUBSCRIPTION_STATUSES:
        sub_status = "active" if has_sub else "free_preview"
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
        "has_automated_subscription": has_sub or sub_status == "active",
        "subscription_status": sub_status,
        "subscription_plan_id": str(d.get("subscription_plan_id") or "").strip(),
        "subscription_plan_name": str(d.get("subscription_plan_name") or "").strip(),
        "subscription_expires_at": str(d.get("subscription_expires_at") or "").strip(),
        "razorpay_customer_id": str(d.get("razorpay_customer_id") or "").strip(),
        "razorpay_subscription_id": str(d.get("razorpay_subscription_id") or "").strip(),
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


def _pick_best_user_doc(snaps: list[Any]) -> Optional[dict[str, Any]]:
    """Return normalized officer doc from snaps, preferring completed profiles if duplicates exist."""
    best: Optional[dict[str, Any]] = None
    for snap in snaps:
        candidate = _normalize_user_doc(snap.id, snap.to_dict())
        if candidate is None:
            continue
        if best is None:
            best = candidate
        if candidate.get("profile_completed") and candidate.get("designation") and candidate.get("mobile_number"):
            return candidate
    return best


def get_user_by_firebase_uid(firebase_uid: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by Firebase UID (falling back to legacy google_uid)."""
    clean_uid = str(firebase_uid or "").strip()
    if not clean_uid:
        return None
    col = _db().collection(COL_USERS)
    for field_name in ("firebase_uid", "google_uid"):
        snaps = list(col.where(filter=FieldFilter(field_name, "==", clean_uid)).stream())
        picked = _pick_best_user_doc(snaps)
        if picked is not None:
            return picked
    return None


get_user_by_google_uid = get_user_by_firebase_uid


def get_user_by_gmail(gmail: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by authenticated Gmail address."""
    clean_email = str(gmail or "").strip().lower()
    if not clean_email:
        return None
    col = _db().collection(COL_USERS)
    for field_name in ("gmail", "email"):
        snaps = list(col.where(filter=FieldFilter(field_name, "==", clean_email)).stream())
        picked = _pick_best_user_doc(snaps)
        if picked is not None:
            return picked
    return None


def _resolve_user_doc_id(col: Any, user_id: str) -> Optional[str]:
    """Return actual Firestore document ID for user_id across direct keys and migrated docs."""
    clean_id = str(user_id or "").strip()
    if not clean_id:
        return None
    if col.document(clean_id).get().exists:
        return clean_id
    snaps = list(col.where(filter=FieldFilter("user_id", "==", clean_id)).limit(1).stream())
    return snaps[0].id if snaps else None


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    """Retrieve officer record by internal user_id."""
    col = _db().collection(COL_USERS)
    doc_id = _resolve_user_doc_id(col, user_id)
    if not doc_id:
        return None
    snap = col.document(doc_id).get()
    return _normalize_user_doc(snap.id, snap.to_dict()) if snap.exists else None


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
        target_doc_id = _resolve_user_doc_id(col, existing["user_id"]) or existing["user_id"]
        col.document(target_doc_id).update(updates)
        updated = _normalize_user_doc(target_doc_id, col.document(target_doc_id).get().to_dict())
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
        "has_automated_subscription": False,
        "subscription_status": "free_preview",
        "subscription_plan_id": "",
        "subscription_plan_name": "",
        "subscription_expires_at": "",
        "razorpay_customer_id": "",
        "razorpay_subscription_id": "",
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

    col = _db().collection(COL_USERS)
    target_doc_id = _resolve_user_doc_id(col, clean_uid)
    if not target_doc_id:
        raise ValueError("Officer account not found.")

    col.document(target_doc_id).update(
        {
            "user_id": clean_uid,
            "name": clean_name,
            "designation": clean_desig,
            "role": clean_role,
            "mobile_number": digits,
            "profile_completed": True,
            "updated_at": _utc_now_iso(),
        }
    )
    updated = _normalize_user_doc(target_doc_id, col.document(target_doc_id).get().to_dict())
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
    if "subscription_status" in raw and raw["subscription_status"] is not None:
        st_sub = str(raw["subscription_status"]).strip().lower()
        if st_sub not in VALID_SUBSCRIPTION_STATUSES:
            return False, f"Invalid subscription status: {st_sub}", None
        updates["subscription_status"] = st_sub
        if "has_automated_subscription" not in raw:
            updates["has_automated_subscription"] = st_sub == "active"
    if "has_automated_subscription" in raw and raw["has_automated_subscription"] is not None:
        has_sub_val = bool(raw["has_automated_subscription"])
        updates["has_automated_subscription"] = has_sub_val
        if "subscription_status" not in updates:
            updates["subscription_status"] = "active" if has_sub_val else "free_preview"
    if "subscription_plan_id" in raw and raw["subscription_plan_id"] is not None:
        updates["subscription_plan_id"] = str(raw["subscription_plan_id"]).strip()[:64]
    if "subscription_plan_name" in raw and raw["subscription_plan_name"] is not None:
        updates["subscription_plan_name"] = str(raw["subscription_plan_name"]).strip()[:120]
    if "subscription_expires_at" in raw and raw["subscription_expires_at"] is not None:
        updates["subscription_expires_at"] = str(raw["subscription_expires_at"]).strip()[:40]

    col = _db().collection(COL_USERS)
    target_doc_id = _resolve_user_doc_id(col, existing["user_id"]) or existing["user_id"]
    if updates:
        updates["updated_at"] = _utc_now_iso()
        col.document(target_doc_id).update(updates)

    if updates.get("account_status") == "Disabled":
        revoke_user_sessions(existing["user_id"])
    else:
        if updates.get("can_access_portal") is False:
            revoke_user_sessions(existing["user_id"], app_scope="portal")
        if updates.get("can_access_console") is False:
            revoke_user_sessions(existing["user_id"], app_scope="console")

    updated = get_user_by_id(existing["user_id"])
    return True, "Officer permissions updated successfully.", updated


def _classify_tool_usage(module: str, action: str = "", platform_scope: str = "portal", tool_id: str = "", category: str = "") -> tuple[str, str, str]:
    """Return canonical (tool_id, human_label, category) for usage analytics."""
    raw_id = str(tool_id or module or action or "activity").strip()
    mod = str(module or "").strip()
    if category:
        cat = str(category).strip()
    elif mod.startswith("excel:") or mod in {"excel_viewer", "excel_editor"}:
        cat = "Excel & Data Studio"
    elif mod.startswith("pdf:"):
        cat = "PDF Studio"
    elif mod in {"dsr_manual", "dsr_multiday", "dcb_live"}:
        cat = "Manual Reports & DCB"
    elif mod in {"dsr_automation", "gp_balance", "mas_consolidated", "epts_auth"}:
        cat = "Automated Portal Console"
    elif mod in {"billing", "razorpay"}:
        cat = "Subscriptions & Billing"
    elif platform_scope == "tools":
        cat = "Tools & Utilities"
    elif platform_scope == "console":
        cat = "Automated Portal Console"
    else:
        cat = "Portal & Authentication"

    if raw_id.startswith("excel:"):
        slug = raw_id.split(":", 1)[1]
        label = slug.replace("_", " ").title()
        if "Xls" in label or "Xlsx" in label or "Csv" in label or "Pdf" in label or "Sql" in label or "Xml" in label:
            for ac in ("Xlsx", "Xlsb", "Xlsm", "Xls", "Csv", "Tsv", "Pdf", "Json", "Xml", "Sql", "Html", "Ods", "Qbo", "Iif", "Ofx", "Ics", "Yaml"):
                label = re.sub(rf"\b{ac}\b", ac.upper(), label)
        return raw_id, label, cat
    if raw_id.startswith("pdf:"):
        slug = raw_id.split(":", 1)[1]
        label = slug.replace("-", " ").replace("_", " ").title()
        label = re.sub(r"\bPdf\b", "PDF", label)
        label = re.sub(r"\bOcr\b", "OCR", label)
        label = re.sub(r"\bJpg\b", "JPG", label)
        return raw_id, label, cat

    known_labels = {
        "excel_viewer": "Excel Viewer & Editor",
        "dsr_manual": "Manual DSR PDF Generator",
        "dsr_multiday": "Multi-Day DSR Consolidation",
        "dcb_live": "Live House Tax DCB Analytics",
        "dsr_automation": "Automated DSR & Attendance Robot",
        "gp_balance": "Thursday GP Balance Robot",
        "mas_consolidated": "MAS 18-Indicator Robot",
        "epts_auth": "e-Panchayat Portal OTP Session",
        "portal": "Officer Google Sign-In & Profile",
        "admin": "Admin Governance Action",
        "billing": "Subscription & Razorpay Billing",
    }
    label = known_labels.get(mod, raw_id.replace("_", " ").replace("-", " ").title())
    return raw_id, label, cat


def _parse_iso_ts(iso_str: str) -> float:
    if not iso_str:
        return 0.0
    try:
        cleaned = str(iso_str).strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned).timestamp()
    except Exception:
        return 0.0


def log_usage(
    *,
    user_id: str = "",
    gmail: str = "",
    user_name: str = "",
    designation: str = "",
    platform_scope: str = "portal",
    module: str = "",
    action: str = "",
    tool_id: str = "",
    tool_name: str = "",
    category: str = "",
    details: str = "",
) -> None:
    """Append a lightweight analytics event to Firestore usage_logs."""
    try:
        now_ts = time.time()
        resolved_id, resolved_label, resolved_cat = _classify_tool_usage(
            module=module,
            action=action,
            platform_scope=platform_scope,
            tool_id=tool_id,
            category=category,
        )
        doc_id = f"log_{int(now_ts * 1000)}_{secrets.token_hex(4)}"
        _db().collection(COL_USAGE).document(doc_id).set(
            {
                "log_id": doc_id,
                "user_id": str(user_id or ""),
                "gmail": str(gmail or "").lower(),
                "user_name": str(user_name or "")[:120],
                "designation": str(designation or "")[:32],
                "platform_scope": str(platform_scope or "portal"),
                "module": str(module or ""),
                "action": str(action or ""),
                "tool_id": resolved_id,
                "tool_name": str(tool_name or resolved_label)[:120],
                "category": resolved_cat,
                "details": str(details or "")[:255],
                "created_at": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
                "created_at_ts": now_ts,
            }
        )
    except Exception as exc:
        logger.debug("Non-fatal Firestore usage_log skip: %s", exc)


def get_tool_usage_analytics(days: int = 30) -> dict[str, Any]:
    """Return detailed per-tool, per-category, and recent activity analytics over the lookback window."""
    lookback_days = max(1, int(days or 30))
    now_ts = time.time()
    cutoff_ts = now_ts - lookback_days * 86400
    cutoff_24h = now_ts - 86400
    cutoff_7d = now_ts - 7 * 86400

    tools_map: dict[str, dict[str, Any]] = {}
    categories_map: dict[str, int] = {}
    module_counts: dict[tuple[str, str], int] = {}
    recent_events: list[dict[str, Any]] = []
    active_uids_24h: set[str] = set()
    active_uids_7d: set[str] = set()

    for snap in _db().collection(COL_USAGE).where(filter=FieldFilter("created_at_ts", ">=", cutoff_ts)).stream():
        row = snap.to_dict() or {}
        ts_val = float(row.get("created_at_ts") or 0)
        scope = str(row.get("platform_scope") or "portal")
        mod = str(row.get("module") or "action")
        uid = str(row.get("user_id") or "").strip()
        if uid and uid != "anonymous":
            if ts_val >= cutoff_24h:
                active_uids_24h.add(uid)
            if ts_val >= cutoff_7d:
                active_uids_7d.add(uid)

        t_id, t_label, t_cat = _classify_tool_usage(
            module=mod,
            action=str(row.get("action") or ""),
            platform_scope=scope,
            tool_id=str(row.get("tool_id") or ""),
            category=str(row.get("category") or ""),
        )
        t_label = str(row.get("tool_name") or t_label)

        module_counts[(scope, mod)] = module_counts.get((scope, mod), 0) + 1
        categories_map[t_cat] = categories_map.get(t_cat, 0) + 1

        entry = tools_map.get(t_id)
        if entry is None:
            entry = {
                "tool_id": t_id,
                "tool_name": t_label,
                "category": t_cat,
                "platform_scope": scope,
                "count": 0,
                "_users": set(),
                "last_used_at": "",
                "_last_ts": 0.0,
            }
            tools_map[t_id] = entry
        entry["count"] += 1
        if uid:
            entry["_users"].add(uid)
        created_at_str = str(row.get("created_at") or "")
        if ts_val >= entry["_last_ts"]:
            entry["_last_ts"] = ts_val
            entry["last_used_at"] = created_at_str

        recent_events.append(
            {
                "log_id": str(row.get("log_id") or snap.id),
                "user_id": uid or "guest",
                "user_name": str(row.get("user_name") or "") or (str(row.get("gmail") or "").split("@")[0] if row.get("gmail") else "Officer / Guest"),
                "gmail": str(row.get("gmail") or ""),
                "designation": str(row.get("designation") or ""),
                "tool_id": t_id,
                "tool_name": t_label,
                "category": t_cat,
                "platform_scope": scope,
                "action": str(row.get("action") or ""),
                "details": str(row.get("details") or ""),
                "created_at": created_at_str,
                "_ts": ts_val,
            }
        )

    tool_usage = []
    for item in tools_map.values():
        tool_usage.append(
            {
                "tool_id": item["tool_id"],
                "tool_name": item["tool_name"],
                "category": item["category"],
                "platform_scope": item["platform_scope"],
                "count": item["count"],
                "unique_users": len(item["_users"]),
                "last_used_at": item["last_used_at"],
            }
        )
    tool_usage.sort(key=lambda x: x["count"], reverse=True)

    category_usage = sorted(
        [{"category": k, "count": v} for k, v in categories_map.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    module_usage = sorted(
        [{"platform_scope": sc, "module": mod, "count": cnt} for (sc, mod), cnt in module_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:25]
    recent_events.sort(key=lambda x: x["_ts"], reverse=True)
    for ev in recent_events:
        ev.pop("_ts", None)

    return {
        "days": lookback_days,
        "total_events": sum(item["count"] for item in tool_usage),
        "unique_tools_used": len(tool_usage),
        "tool_usage": tool_usage[:50],
        "category_usage": category_usage,
        "module_usage": module_usage,
        "recent_activity": recent_events[:30],
        "active_uids_24h": active_uids_24h,
        "active_uids_7d": active_uids_7d,
    }


def get_usage_stats(days: int = 30) -> dict[str, Any]:
    """Return aggregate officer, live session, tool usage, feedback, and subscription revenue KPIs."""
    users, total_users = list_users(limit=5000)
    active_users = sum(1 for u in users if u["account_status"] == "Active")
    disabled_users = total_users - active_users
    completed_profiles = sum(1 for u in users if u["profile_completed"])
    subscribed_users = sum(
        1 for u in users if bool(u.get("has_automated_subscription")) or u.get("subscription_status") == "active"
    )
    trial_users = sum(1 for u in users if u.get("subscription_status") == "trial")
    free_users = max(0, total_users - subscribed_users - trial_users)

    desig_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    now_ts = time.time()
    cutoff_24h = now_ts - 86400
    cutoff_7d = now_ts - 7 * 86400
    active_uids_24h: set[str] = set()
    active_uids_7d: set[str] = set()

    for u in users:
        d_key = u["designation"] or "Pending"
        desig_counts[d_key] = desig_counts.get(d_key, 0) + 1
        r_key = u["role"] or "Pending"
        role_counts[r_key] = role_counts.get(r_key, 0) + 1
        ll_ts = _parse_iso_ts(u.get("last_login", ""))
        if ll_ts >= cutoff_24h:
            active_uids_24h.add(u["user_id"])
        if ll_ts >= cutoff_7d:
            active_uids_7d.add(u["user_id"])

    session_counts: dict[str, int] = {}
    live_session_user_ids: set[str] = set()
    for snap in _db().collection(COL_SESSIONS).where(filter=FieldFilter("revoked", "==", False)).stream():
        s = snap.to_dict() or {}
        if float(s.get("expires_at_ts") or 0) > now_ts:
            sc = str(s.get("app_scope") or "portal")
            session_counts[sc] = session_counts.get(sc, 0) + 1
            uid = str(s.get("user_id") or "").strip()
            if uid:
                live_session_user_ids.add(uid)

    total_feedback = sum(1 for _ in _db().collection(COL_FEEDBACK).stream())

    usage_report = get_tool_usage_analytics(days=days)
    active_uids_24h |= usage_report.pop("active_uids_24h", set())
    active_uids_7d |= usage_report.pop("active_uids_7d", set())

    payments = list_payments(limit=1000)
    captured_payments = [p for p in payments if p.get("status") == "captured"]
    total_revenue_inr = round(sum(float(p.get("amount_inr") or 0.0) for p in captured_payments), 2)
    cutoff_30d = now_ts - 30 * 86400
    monthly_revenue_inr = round(
        sum(
            float(p.get("amount_inr") or 0.0)
            for p in captured_payments
            if _parse_iso_ts(p.get("captured_at") or p.get("created_at") or "") >= cutoff_30d
        ),
        2,
    )
    subscriptions = list_subscriptions(limit=1000)

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

    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "completed_profiles": completed_profiles,
        "active_users_now": len(live_session_user_ids),
        "active_users_24h": len(active_uids_24h),
        "active_users_7d": len(active_uids_7d),
        "subscribed_users": subscribed_users,
        "trial_users": trial_users,
        "free_users": free_users,
        "total_subscriptions_count": len(subscriptions),
        "captured_payments_count": len(captured_payments),
        "total_revenue_inr": total_revenue_inr,
        "monthly_revenue_inr": monthly_revenue_inr,
        "by_designation": by_desig,
        "by_role": by_role,
        "active_sessions": active_sessions,
        "total_feedback": total_feedback,
        "total_tool_runs": usage_report["total_events"],
        "unique_tools_used": usage_report["unique_tools_used"],
        "module_usage": usage_report["module_usage"],
        "tool_usage": usage_report["tool_usage"],
        "category_usage": usage_report["category_usage"],
        "recent_activity": usage_report["recent_activity"],
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


# ---------------------------------------------------------------------------
# Subscriptions, Plans & Razorpay Payment Ledger Database Layer
# ---------------------------------------------------------------------------


def ensure_default_subscription_plans() -> list[dict[str, Any]]:
    """Ensure starter subscription plans exist in Cloud Firestore subscription_plans."""
    col = _db().collection(COL_PLANS)
    existing_snaps = list(col.stream())
    if existing_snaps:
        plans = [dict(s.to_dict() or {}, plan_id=s.id) for s in existing_snaps]
        plans.sort(key=lambda x: (int(x.get("sort_order") or 99), float(x.get("amount_inr") or 0)))
        return plans

    now = _utc_now_iso()
    created: list[dict[str, Any]] = []
    for plan in DEFAULT_SUBSCRIPTION_PLANS:
        doc = {**plan, "created_at": now, "updated_at": now}
        col.document(plan["plan_id"]).set(doc)
        created.append(doc)
    return created


def list_subscription_plans(include_inactive: bool = False) -> list[dict[str, Any]]:
    """Return configured subscription plans ordered by sort_order/price."""
    plans = ensure_default_subscription_plans()
    if not include_inactive:
        plans = [p for p in plans if bool(p.get("is_active", True))]
    return plans


def get_subscription_plan(plan_id: str) -> Optional[dict[str, Any]]:
    """Fetch a subscription plan by plan_id or code."""
    clean_id = str(plan_id or "").strip()
    if not clean_id:
        return None
    plans = list_subscription_plans(include_inactive=True)
    for p in plans:
        if p.get("plan_id") == clean_id or p.get("code") == clean_id:
            return p
    return None


def upsert_subscription_plan(
    *,
    plan_id: str,
    name: str,
    amount_inr: float,
    duration_days: int = 30,
    description: str = "",
    code: str = "",
    razorpay_plan_id: str = "",
    features: Optional[list[str]] = None,
    is_active: bool = True,
    sort_order: int = 10,
) -> dict[str, Any]:
    """Create or update a subscription plan record in Cloud Firestore."""
    ensure_default_subscription_plans()
    clean_id = re.sub(r"[^a-z0-9_]+", "_", str(plan_id or "").strip().lower()).strip("_")
    if not clean_id:
        raise ValueError("plan_id is required.")
    clean_name = str(name or "").strip()
    if len(clean_name) < 2:
        raise ValueError("Plan name must be at least 2 characters.")
    amt = max(0.0, float(amount_inr))
    paise = int(round(amt * 100))
    days_val = max(1, int(duration_days or 30))
    now = _utc_now_iso()

    col = _db().collection(COL_PLANS)
    existing_snap = col.document(clean_id).get()
    created_at = (existing_snap.to_dict() or {}).get("created_at", now) if existing_snap.exists else now

    doc = {
        "plan_id": clean_id,
        "code": str(code or clean_id.replace("plan_", "")).strip(),
        "name": clean_name,
        "description": str(description or "").strip(),
        "amount_inr": round(amt, 2),
        "amount_paise": paise,
        "currency": "INR",
        "duration_days": days_val,
        "razorpay_plan_id": str(razorpay_plan_id or "").strip(),
        "features": [str(f).strip() for f in (features or []) if str(f).strip()],
        "is_active": bool(is_active),
        "sort_order": int(sort_order),
        "created_at": created_at,
        "updated_at": now,
    }
    col.document(clean_id).set(doc)
    return doc


def grant_or_activate_subscription(
    *,
    user_id: str,
    plan_id: str = "plan_monthly",
    duration_days: Optional[int] = None,
    amount_inr: Optional[float] = None,
    provider: str = "admin_grant",
    razorpay_order_id: str = "",
    razorpay_payment_id: str = "",
    razorpay_subscription_id: str = "",
    razorpay_customer_id: str = "",
    granted_by: str = "",
    notes: str = "",
    record_payment: bool = False,
) -> dict[str, Any]:
    """Activate a subscription for an officer, persist in subscriptions, and sync user flags."""
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("Officer account not found.")

    plan = get_subscription_plan(plan_id) or list_subscription_plans(include_inactive=True)[0]
    eff_days = max(1, int(duration_days or plan.get("duration_days") or 30))
    eff_amt = float(plan.get("amount_inr") or 0.0) if amount_inr is None else max(0.0, float(amount_inr))
    eff_paise = int(round(eff_amt * 100))

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    exp_dt = now_dt + timedelta(days=eff_days)
    exp_iso = exp_dt.isoformat()

    sub_id = f"sub_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
    sub_doc = {
        "subscription_id": sub_id,
        "user_id": user["user_id"],
        "gmail": user["gmail"],
        "user_name": user["name"],
        "plan_id": plan["plan_id"],
        "plan_name": plan["name"],
        "amount_inr": round(eff_amt, 2),
        "currency": "INR",
        "duration_days": eff_days,
        "status": "active",
        "provider": str(provider or "admin_grant"),
        "razorpay_subscription_id": str(razorpay_subscription_id or ""),
        "razorpay_customer_id": str(razorpay_customer_id or user.get("razorpay_customer_id") or ""),
        "razorpay_order_id": str(razorpay_order_id or ""),
        "razorpay_payment_id": str(razorpay_payment_id or ""),
        "started_at": now_iso,
        "expires_at": exp_iso,
        "created_at": now_iso,
        "updated_at": now_iso,
        "granted_by": str(granted_by or ""),
        "notes": str(notes or "")[:255],
    }
    _db().collection(COL_SUBSCRIPTIONS).document(sub_id).set(sub_doc)

    # Mark any older active subscriptions for this user as superseded
    for snap in _db().collection(COL_SUBSCRIPTIONS).where(filter=FieldFilter("user_id", "==", user["user_id"])).stream():
        if snap.id == sub_id:
            continue
        old = snap.to_dict() or {}
        if old.get("status") == "active":
            _db().collection(COL_SUBSCRIPTIONS).document(snap.id).update({"status": "superseded", "updated_at": now_iso})

    user_col = _db().collection(COL_USERS)
    target_doc_id = _resolve_user_doc_id(user_col, user["user_id"]) or user["user_id"]
    user_updates: dict[str, Any] = {
        "has_automated_subscription": True,
        "subscription_status": "active",
        "subscription_plan_id": plan["plan_id"],
        "subscription_plan_name": plan["name"],
        "subscription_expires_at": exp_iso,
        "updated_at": now_iso,
    }
    if razorpay_customer_id:
        user_updates["razorpay_customer_id"] = str(razorpay_customer_id)
    if razorpay_subscription_id:
        user_updates["razorpay_subscription_id"] = str(razorpay_subscription_id)
    user_col.document(target_doc_id).update(user_updates)

    if record_payment and eff_amt > 0:
        pay_id = f"pay_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        _db().collection(COL_PAYMENTS).document(pay_id).set(
            {
                "payment_id": pay_id,
                "user_id": user["user_id"],
                "gmail": user["gmail"],
                "user_name": user["name"],
                "subscription_id": sub_id,
                "plan_id": plan["plan_id"],
                "plan_name": plan["name"],
                "amount_paise": eff_paise,
                "amount_inr": round(eff_amt, 2),
                "currency": "INR",
                "status": "captured",
                "provider": str(provider or "admin_grant"),
                "razorpay_order_id": str(razorpay_order_id or ""),
                "razorpay_payment_id": str(razorpay_payment_id or ""),
                "signature_verified": bool(razorpay_payment_id),
                "method": "razorpay" if razorpay_payment_id else "admin",
                "notes": str(notes or "Recorded with subscription activation")[:255],
                "created_at": now_iso,
                "captured_at": now_iso,
            }
        )

    return sub_doc


def revoke_user_subscription(user_id: str, actor: str = "", status: str = "cancelled") -> dict[str, Any]:
    """Cancel or expire active subscriptions for an officer and update user profile flags."""
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("Officer account not found.")
    st = str(status or "cancelled").strip().lower()
    if st not in {"cancelled", "expired", "free_preview"}:
        st = "cancelled"
    now_iso = _utc_now_iso()

    for snap in _db().collection(COL_SUBSCRIPTIONS).where(filter=FieldFilter("user_id", "==", user["user_id"])).stream():
        d = snap.to_dict() or {}
        if d.get("status") == "active":
            _db().collection(COL_SUBSCRIPTIONS).document(snap.id).update(
                {"status": st if st != "free_preview" else "cancelled", "updated_at": now_iso, "cancelled_by": str(actor or "")}
            )

    user_col = _db().collection(COL_USERS)
    target_doc_id = _resolve_user_doc_id(user_col, user["user_id"]) or user["user_id"]
    user_col.document(target_doc_id).update(
        {
            "has_automated_subscription": False,
            "subscription_status": st,
            "updated_at": now_iso,
        }
    )
    return get_user_by_id(user["user_id"]) or user


def list_subscriptions(limit: int = 200, status: str = "") -> list[dict[str, Any]]:
    """Return subscription records ordered newest first."""
    clean_st = str(status or "").strip().lower()
    items: list[dict[str, Any]] = []
    for snap in _db().collection(COL_SUBSCRIPTIONS).stream():
        d = snap.to_dict()
        if not d:
            continue
        item = dict(d)
        item.setdefault("subscription_id", snap.id)
        if clean_st and str(item.get("status") or "").lower() != clean_st:
            continue
        items.append(item)
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def record_payment_order(
    *,
    user_id: str,
    plan: dict[str, Any],
    razorpay_order_id: str,
    provider: str = "razorpay",
    notes: str = "",
) -> dict[str, Any]:
    """Persist an initiated Razorpay order transaction in Cloud Firestore payments."""
    user = get_user_by_id(user_id)
    now_iso = _utc_now_iso()
    pay_id = f"pay_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
    doc = {
        "payment_id": pay_id,
        "user_id": str(user_id),
        "gmail": (user or {}).get("gmail", ""),
        "user_name": (user or {}).get("name", ""),
        "subscription_id": "",
        "plan_id": str(plan.get("plan_id") or ""),
        "plan_name": str(plan.get("name") or ""),
        "amount_paise": int(plan.get("amount_paise") or 0),
        "amount_inr": round(float(plan.get("amount_inr") or 0.0), 2),
        "currency": str(plan.get("currency") or "INR"),
        "status": "created",
        "provider": provider,
        "razorpay_order_id": str(razorpay_order_id),
        "razorpay_payment_id": "",
        "signature_verified": False,
        "method": "razorpay",
        "notes": str(notes or "")[:255],
        "created_at": now_iso,
        "captured_at": "",
    }
    _db().collection(COL_PAYMENTS).document(pay_id).set(doc)
    return doc


def capture_razorpay_payment(
    *,
    user_id: str,
    plan_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    method: str = "razorpay",
) -> dict[str, Any]:
    """Mark verified Razorpay payment captured (idempotently) and activate subscription."""
    existing = list(
        _db()
        .collection(COL_PAYMENTS)
        .where(filter=FieldFilter("razorpay_payment_id", "==", str(razorpay_payment_id)))
        .limit(1)
        .stream()
    )
    if existing:
        existing_doc = dict(existing[0].to_dict() or {}, payment_id=existing[0].id)
        if existing_doc.get("status") == "captured":
            return {"payment": existing_doc, "already_captured": True}

    plan = get_subscription_plan(plan_id) or list_subscription_plans(include_inactive=True)[0]
    sub = grant_or_activate_subscription(
        user_id=user_id,
        plan_id=plan["plan_id"],
        provider="razorpay",
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        granted_by="razorpay_checkout",
        notes=f"Razorpay order {razorpay_order_id}",
        record_payment=False,
    )

    now_iso = _utc_now_iso()
    matched = list(
        _db()
        .collection(COL_PAYMENTS)
        .where(filter=FieldFilter("razorpay_order_id", "==", str(razorpay_order_id)))
        .limit(1)
        .stream()
    )
    if matched:
        doc_id = matched[0].id
        _db().collection(COL_PAYMENTS).document(doc_id).update(
            {
                "subscription_id": sub["subscription_id"],
                "razorpay_payment_id": str(razorpay_payment_id),
                "status": "captured",
                "signature_verified": True,
                "method": str(method or "razorpay"),
                "captured_at": now_iso,
            }
        )
        pay_doc = dict(_db().collection(COL_PAYMENTS).document(doc_id).get().to_dict() or {}, payment_id=doc_id)
    else:
        user = get_user_by_id(user_id) or {}
        pay_id = f"pay_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        pay_doc = {
            "payment_id": pay_id,
            "user_id": str(user_id),
            "gmail": user.get("gmail", ""),
            "user_name": user.get("name", ""),
            "subscription_id": sub["subscription_id"],
            "plan_id": plan["plan_id"],
            "plan_name": plan["name"],
            "amount_paise": int(plan.get("amount_paise") or 0),
            "amount_inr": round(float(plan.get("amount_inr") or 0.0), 2),
            "currency": "INR",
            "status": "captured",
            "provider": "razorpay",
            "razorpay_order_id": str(razorpay_order_id),
            "razorpay_payment_id": str(razorpay_payment_id),
            "signature_verified": True,
            "method": str(method or "razorpay"),
            "notes": "Captured via Razorpay verification",
            "created_at": now_iso,
            "captured_at": now_iso,
        }
        _db().collection(COL_PAYMENTS).document(pay_id).set(pay_doc)

    return {"payment": pay_doc, "subscription": sub, "already_captured": False}


def list_payments(limit: int = 200, status: str = "") -> list[dict[str, Any]]:
    """Return payment ledger records ordered newest first."""
    clean_st = str(status or "").strip().lower()
    items: list[dict[str, Any]] = []
    for snap in _db().collection(COL_PAYMENTS).stream():
        d = snap.to_dict()
        if not d:
            continue
        item = dict(d)
        item.setdefault("payment_id", snap.id)
        if clean_st and str(item.get("status") or "").lower() != clean_st:
            continue
        items.append(item)
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items[: max(1, int(limit))]


def get_user_billing_summary(user_id: str) -> dict[str, Any]:
    """Return subscription & payment history summary for a single officer."""
    clean_uid = str(user_id or "").strip()
    subs = [
        dict(s.to_dict() or {}, subscription_id=s.id)
        for s in _db().collection(COL_SUBSCRIPTIONS).where(filter=FieldFilter("user_id", "==", clean_uid)).stream()
    ]
    subs.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    pays = [
        dict(p.to_dict() or {}, payment_id=p.id)
        for p in _db().collection(COL_PAYMENTS).where(filter=FieldFilter("user_id", "==", clean_uid)).stream()
    ]
    pays.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    active_sub = next((s for s in subs if s.get("status") == "active"), None)
    return {
        "active_subscription": active_sub,
        "subscriptions": subs[:20],
        "payments": pays[:20],
    }

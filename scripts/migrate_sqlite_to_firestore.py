"""Idempotent migration tool: legacy data/epanchayat_users.db (SQLite) -> Cloud Firestore.

Migrates users (matching by legacy user_id / gmail), feedback records, and
access_policy entries to Cloud Firestore without deleting or modifying the source SQLite file.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.firebase_app import get_firebase_runtime_status, get_live_firestore_client
from core.firebase_store import (
    COL_FEEDBACK,
    COL_POLICY,
    COL_USERS,
    designation_to_role,
)


_SYNTHETIC_EMAIL_PREFIXES = (
    "test",
    "mock",
    "blocked_",
    "target_",
    "non_admin",
    "admin.epanchayat",
    "autoload_",
    "portal_only",
    "console_epts",
    "dept_mgr",
    "officer_",
    "mpo_",
    "dpo_",
    "dpm_",
    "dlpo_",
    "mpdo_",
    "ps_",
    "deo_",
    "isolated_",
    "dual_",
    "brand_e2e_",
)


def _is_synthetic_email(email: str) -> bool:
    low = str(email or "").strip().lower()
    if not low or low.endswith("@example.com"):
        return True
    if low == "venkatesh.mpo@gmail.com":
        return True
    return low.startswith(_SYNTHETIC_EMAIL_PREFIXES)


def migrate_sqlite_to_firestore(
    sqlite_path: Path,
    *,
    dry_run: bool = False,
    exclude_test_records: bool = False,
) -> dict[str, int]:
    """Copy users, feedback, and access_policy rows from SQLite into Cloud Firestore."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite source database not found: {sqlite_path}")

    client = get_live_firestore_client()
    if client is None and not dry_run:
        raise RuntimeError(
            "Cloud Firestore live client is not connected. Set FIREBASE_SERVICE_ACCOUNT_PATH, "
            "GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_SERVICE_ACCOUNT_JSON, or FIRESTORE_EMULATOR_HOST "
            "before running migration (or pass --dry-run to preview counts)."
        )

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row

    counts = {"users_migrated": 0, "users_skipped": 0, "feedback_migrated": 0, "feedback_skipped": 0, "policy_migrated": 0}
    try:
        user_rows = conn.execute("SELECT * FROM users").fetchall()
        for row in user_rows:
            d = dict(row)
            uid = str(d.get("user_id") or "").strip()
            gmail = str(d.get("gmail") or "").strip().lower()
            desig = str(d.get("designation") or "").strip().upper()
            role = str(d.get("role") or "").strip() or designation_to_role(desig)
            reg_date = str(d.get("registration_date") or "")
            last_login = str(d.get("last_login") or reg_date)
            if not uid or not gmail or (exclude_test_records and _is_synthetic_email(gmail)):
                counts["users_skipped"] += 1
                continue

            payload = {
                "user_id": uid,
                "firebase_uid": str(d.get("google_uid") or "").strip(),
                "google_uid": str(d.get("google_uid") or "").strip(),
                "email": gmail,
                "gmail": gmail,
                "name": str(d.get("name") or "").strip(),
                "designation": desig,
                "role": role,
                "mobile_number": str(d.get("mobile_number") or "").strip(),
                "profile_picture": str(d.get("profile_picture") or "").strip(),
                "registration_date": reg_date,
                "last_login": last_login,
                "updated_at": last_login or reg_date,
                "account_status": str(d.get("account_status") or "Active"),
                "profile_completed": bool(d.get("profile_completed", 0)),
                "is_admin": bool(d.get("is_admin", 0)),
                "can_access_portal": bool(d.get("can_access_portal", 1)),
                "can_access_console": bool(d.get("can_access_console", 1)),
                "migrated_from_sqlite": True,
            }
            if not dry_run and client is not None:
                ref = client.collection(COL_USERS).document(uid)
                existing_snap = ref.get()
                if existing_snap.exists:
                    existing_data = existing_snap.to_dict() or {}
                    # Keep newer firebase_uid if officer already logged into Firebase Auth
                    if existing_data.get("firebase_uid"):
                        payload["firebase_uid"] = existing_data["firebase_uid"]
                ref.set(payload, merge=True)
            counts["users_migrated"] += 1

        fb_rows = conn.execute("SELECT * FROM feedback").fetchall()
        for row in fb_rows:
            d = dict(row)
            fb_email = str(d.get("email") or "").strip().lower()
            if exclude_test_records and _is_synthetic_email(fb_email):
                counts["feedback_skipped"] += 1
                continue
            fb_id = f"legacy_fb_{d.get('id')}"
            payload = {
                "feedback_id": fb_id,
                "id": fb_id,
                "user_id": str(d.get("user_id") or ""),
                "email": fb_email,
                "gmail": fb_email,
                "name": str(d.get("name") or "").strip(),
                "designation": str(d.get("designation") or "").strip(),
                "role": str(d.get("role") or "").strip(),
                "category": str(d.get("category") or "General Feedback").strip(),
                "message": str(d.get("message") or "").strip(),
                "rating": int(d.get("rating") or 5),
                "app_scope": str(d.get("app_scope") or "portal"),
                "created_at": str(d.get("created_at") or ""),
            }
            if not dry_run and client is not None:
                client.collection(COL_FEEDBACK).document(fb_id).set(payload, merge=True)
            counts["feedback_migrated"] += 1

        pol_rows = conn.execute("SELECT * FROM access_policy").fetchall()
        for row in pol_rows:
            d = dict(row)
            key = str(d.get("key") or "").strip()
            if not key:
                continue
            payload = {
                "key": key,
                "value": str(d.get("value") or "true"),
                "updated_at": str(d.get("updated_at") or ""),
                "updated_by": str(d.get("updated_by") or ""),
            }
            if not dry_run and client is not None:
                client.collection(COL_POLICY).document(key).set(payload, merge=True)
            counts["policy_migrated"] += 1
    finally:
        conn.close()

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy SQLite users/feedback/policy to Cloud Firestore.")
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=BASE_DIR / "data" / "epanchayat_users.db",
        help="Path to legacy SQLite database (default: ./data/epanchayat_users.db)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect migration counts without writing to Firestore.")
    parser.add_argument(
        "--exclude-test-records",
        action="store_true",
        help="Skip synthetic pytest/e2e rows when migrating from SQLite to live Cloud Firestore.",
    )
    args = parser.parse_args()

    print("Firebase runtime:", get_firebase_runtime_status())
    summary = migrate_sqlite_to_firestore(
        args.sqlite_path,
        dry_run=args.dry_run,
        exclude_test_records=args.exclude_test_records,
    )
    print("Migration summary:" + (" (DRY RUN)" if args.dry_run else ""), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

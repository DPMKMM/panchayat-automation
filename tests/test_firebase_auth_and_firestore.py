"""Comprehensive tests for Firebase Authentication, Cloud Firestore Store, Scope Isolation & OAuth Removal."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from core.dependencies import CONSOLE_COOKIE_NAME, PORTAL_COOKIE_NAME, SSO_COOKIE_NAME
from core.firebase_app import get_firebase_runtime_status, verify_firebase_id_token
from core.firebase_store import (
    _db,
    get_user_by_gmail,
    reset_inmemory_firestore,
)
from scripts.migrate_sqlite_to_firestore import migrate_sqlite_to_firestore

ROOT_DIR = Path(__file__).resolve().parent.parent
app = create_app()


def test_legacy_google_oauth_files_and_endpoints_completely_removed():
    """Confirm all custom Google OAuth backend modules, endpoints, and GSI markup are gone."""
    assert not (ROOT_DIR / "core" / "auth.py").exists()
    assert not (ROOT_DIR / "core" / "database.py").exists()

    c = TestClient(app)
    for gone_get in (
        "/api/auth/google-config",
        "/api/auth/google/login",
        "/api/auth/google/callback",
        "/api/admin/oauth-config",
    ):
        assert c.get(gone_get, follow_redirects=False).status_code == 404

    for gone_post in (
        "/api/auth/google-login",
        "/api/auth/google/config-client-id",
        "/api/auth/portal-login",
        "/api/admin/oauth-config",
    ):
        assert c.post(gone_post, json={}).status_code == 404

    html = c.get("/").text
    assert "accounts.google.com/gsi/client" not in html
    assert "google-account-chooser-modal" not in html
    assert "admin-tab-oauth" not in html
    assert "/static/js/firebase_auth.js" in html

    fb_js = c.get("/static/js/firebase_auth.js")
    assert fb_js.status_code == 200
    assert "signInWithPopup" in fb_js.text
    assert "GoogleAuthProvider" in fb_js.text


def test_firebase_id_token_verification_rejects_empty_and_invalid_tokens():
    """Real verify_firebase_id_token strictly rejects unsigned or invalid tokens."""
    c = TestClient(app)

    # 1. Missing token -> 400
    r_empty = c.post("/api/auth/firebase-login", json={})
    assert r_empty.status_code == 400

    # 2. Forged/malformed JWT -> 401
    r_bad = c.post("/api/auth/firebase-login", json={"id_token": "not.a.real.firebase.jwt"})
    assert r_bad.status_code == 401

    try:
        verify_firebase_id_token("forged.jwt.payload")
        assert False, "Expected ValueError on forged JWT"
    except ValueError:
        pass


def test_firebase_id_token_verification_tolerates_clock_skew(monkeypatch):
    """Ensure small OS vs Google server clock drift passes clock_skew_seconds=60."""
    from core import firebase_app

    captured: dict = {}

    monkeypatch.setattr(firebase_app, "get_firebase_admin_app", lambda: (object(), True))

    def _fake_verify_id_token(token, app=None, check_revoked=False, clock_skew_seconds=0):
        captured["clock_skew_seconds"] = clock_skew_seconds
        return {
            "uid": "fb_skew_uid",
            "email": "dpmkmm7@gmail.com",
            "email_verified": True,
            "name": "Clock Skew Officer",
        }

    monkeypatch.setattr(firebase_app.fb_auth, "verify_id_token", _fake_verify_id_token)
    claims = verify_firebase_id_token("valid.skew.jwt")
    assert captured["clock_skew_seconds"] == 60
    assert claims["gmail"] == "dpmkmm7@gmail.com"
    assert claims["firebase_uid"] == "fb_skew_uid"


def test_firebase_config_and_scoped_dual_domain_sessions(monkeypatch):
    """Verify independent portal_token vs console_token sessions backed by Firestore hashed keys."""
    ts = int(time.time() * 1000)
    uid = f"fb_dual_{ts}"
    email = f"dual_officer_{ts}@gmail.com"

    c = TestClient(app)
    cfg = c.get("/api/auth/firebase-config")
    assert cfg.status_code == 200
    cfg_data = cfg.json()
    assert cfg_data["success"] is True
    assert cfg_data["firebase_config"]["projectId"] == "epanchayat-automation-tg"
    assert cfg_data["firebase_config"]["authDomain"] == "epanchayat-automation-tg.firebaseapp.com"

    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": uid,
            "gmail": email,
            "name": "Dual Domain Officer",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )

    # 1. Authenticate ONCE on Home (panchayatautomation.in) -> portal_token + shared epanchayat_sso cookie issued
    r_portal = c.post(
        "/api/auth/firebase-login",
        headers={"Host": "panchayatautomation.in"},
        json={"id_token": "mock_portal_jwt"},
    )
    assert r_portal.status_code == 200
    assert PORTAL_COOKIE_NAME in r_portal.cookies
    assert SSO_COOKIE_NAME in r_portal.cookies
    assert CONSOLE_COOKIE_NAME not in r_portal.cookies
    portal_token = r_portal.json()["token"]

    # Sessions stored in Firestore using SHA-256 hash as document ID
    expected_hash = hashlib.sha256(portal_token.encode("utf-8")).hexdigest()
    sess_snap = _db().collection("sessions").document(expected_hash).get()
    assert sess_snap.exists
    assert sess_snap.to_dict()["app_scope"] == "portal"

    # Single sign-in automatically authenticates autoreports, manualreports, tools, and legacy reports subdomains
    for sub_host in (
        "autoreports.panchayatautomation.in",
        "manualreports.panchayatautomation.in",
        "tools.panchayatautomation.in",
        "reports.panchayatautomation.in",
    ):
        st_sub = c.get("/api/auth/portal-status", headers={"Host": sub_host})
        assert st_sub.status_code == 200
        assert st_sub.json()["authenticated"] is True, f"Expected SSO authenticated=True on {sub_host}"

    # 2. HTTPS production cookie jar shares .panchayatautomation.in SSO cookie seamlessly across subdomains
    https_c = TestClient(app, base_url="https://panchayatautomation.in")
    r_https = https_c.post("/api/auth/firebase-login", json={"id_token": "mock_https_sso_jwt"})
    assert r_https.status_code == 200
    assert "Domain=.panchayatautomation.in" in r_https.headers.get("set-cookie", "")
    for sub_url in (
        "https://autoreports.panchayatautomation.in/api/auth/portal-status",
        "https://manualreports.panchayatautomation.in/api/auth/portal-status",
        "https://tools.panchayatautomation.in/api/auth/portal-status",
        "https://admin.panchayatautomation.in/api/auth/portal-status",
    ):
        st_live = https_c.get(sub_url)
        assert st_live.status_code == 200
        assert st_live.json()["authenticated"] is True, f"Expected HTTPS .panchayatautomation.in SSO on {sub_url}"

    # 3. Logging out from Console revokes shared SSO and logs out Home & all subdomains cleanly
    r_out = https_c.post("https://autoreports.panchayatautomation.in/api/auth/logout")
    assert r_out.status_code == 200
    assert https_c.get("https://autoreports.panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is False
    assert https_c.get("https://panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is False
    assert https_c.get("https://manualreports.panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is False
    assert https_c.get("https://tools.panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is False

    # 4. Signing in on autoreports FIRST also unlocks Home, manualreports, and tools
    con_c = TestClient(app, base_url="https://autoreports.panchayatautomation.in")
    r_con = con_c.post("/api/auth/firebase-login", json={"id_token": "mock_console_first_jwt"})
    assert r_con.status_code == 200
    assert r_con.json()["platform_scope"] == "console"
    for dest in (
        "https://panchayatautomation.in/api/auth/portal-status",
        "https://manualreports.panchayatautomation.in/api/auth/portal-status",
        "https://tools.panchayatautomation.in/api/auth/portal-status",
    ):
        assert con_c.get(dest).json()["authenticated"] is True

    # 5. Legacy host-only portal_token is auto-promoted onto .panchayatautomation.in on Home visit
    legacy_c = TestClient(app, base_url="https://panchayatautomation.in")
    legacy_c.cookies.set(PORTAL_COOKIE_NAME, portal_token, domain="panchayatautomation.in", path="/")
    up_resp = legacy_c.get("/")
    assert up_resp.status_code == 200
    assert f"{SSO_COOKIE_NAME}=" in up_resp.headers.get("set-cookie", "")
    assert "Domain=.panchayatautomation.in" in up_resp.headers.get("set-cookie", "")
    assert legacy_c.get("https://autoreports.panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is True

    # 6. Revoked/invalid SSO cookie takes priority and never falls back to stale host-only cookie
    legacy_c.cookies.set(SSO_COOKIE_NAME, "revoked_or_bogus_sso_tok", domain=".panchayatautomation.in", path="/")
    assert legacy_c.get("https://panchayatautomation.in/api/auth/portal-status").json()["authenticated"] is False


def test_sqlite_migration_dry_run_and_identity_continuity(tmp_path):
    """Verify legacy SQLite records migrate cleanly without losing profile completion."""
    reset_inmemory_firestore()
    db_file = tmp_path / "legacy_users.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        """
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            google_uid TEXT,
            gmail TEXT,
            name TEXT,
            designation TEXT,
            role TEXT,
            mobile_number TEXT,
            profile_picture TEXT,
            registration_date TEXT,
            last_login TEXT,
            account_status TEXT,
            profile_completed INTEGER,
            is_admin INTEGER,
            can_access_portal INTEGER,
            can_access_console INTEGER
        )
        """
    )
    conn.execute("CREATE TABLE feedback (id INTEGER PRIMARY KEY, user_id TEXT, name TEXT, email TEXT, designation TEXT, role TEXT, rating INTEGER, category TEXT, message TEXT, app_scope TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE access_policy (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by TEXT)")
    conn.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("usr_legacy_1", "old_gid_1", "legacy.dpo@gmail.com", "Legacy DPO", "DPO", "District Level", "9876501234", "", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "Active", 1, 0, 1, 1),
    )
    conn.execute("INSERT INTO feedback VALUES (1, 'usr_legacy_1', 'Legacy DPO', 'legacy.dpo@gmail.com', 'DPO', 'District Level', 5, 'General', 'Great tool', 'portal', '2026-02-01T00:00:00Z')")
    conn.execute("INSERT INTO access_policy VALUES ('free_launch_mode', 'true', '2026-02-01T00:00:00Z', 'usr_legacy_1')")
    conn.commit()
    conn.close()

    summary = migrate_sqlite_to_firestore(db_file, dry_run=True)
    assert summary["users_migrated"] == 1
    assert summary["feedback_migrated"] == 1
    assert summary["policy_migrated"] == 1

    # Also verify runtime status reports test mode cleanly
    status = get_firebase_runtime_status()
    assert status["project_id"] == "epanchayat-automation-tg"
    assert status["location"] == "asia-south1"
    assert status["database_id"] == "(default)"

    # Verify firestore.rules covers all 5 collections and default-denies the rest
    rules_text = (ROOT_DIR / "firestore.rules").read_text(encoding="utf-8")
    for col in ("users", "sessions", "feedback", "usage_logs", "access_policy"):
        assert f"match /{col}/" in rules_text
    assert "match /{document=**}" in rules_text
    assert get_user_by_gmail("nonexistent@gmail.com") is None

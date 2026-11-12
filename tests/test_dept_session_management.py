"""Tests for Centralized Department Login Session Management, MAS Fix, Security & Expiry."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app

ROOT_DIR = Path(__file__).resolve().parent.parent
app = create_app()


def _console_login(client: TestClient, monkeypatch, suffix: str) -> dict:
    email = f"dept_mgr_{suffix}@gmail.com"
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": f"fb_dept_{suffix}",
            "gmail": email,
            "name": f"Officer {suffix}",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    res = client.post(
        "/api/auth/firebase-login",
        headers={"Host": "reports.panchayatautomation.in"},
        json={"id_token": f"tok_{suffix}"},
    )
    assert res.status_code == 200
    return res.json()


def test_centralized_department_status_and_cookie_sync(monkeypatch):
    ts = int(time.time() * 1000)
    c = TestClient(app)

    # Initial page boot sets epts_session_id cookie
    home = c.get("/?site=console")
    assert home.status_code == 200
    initial_cookie = c.cookies.get("epts_session_id")
    assert initial_cookie and len(initial_cookie) >= 8

    # /api/auth/portal-status echoes epts_session_id matching cookie
    st_boot = c.get("/api/auth/portal-status", headers={"Host": "reports.panchayatautomation.in"}).json()
    assert st_boot["epts_session_id"] == initial_cookie

    _console_login(c, monkeypatch, f"sync_{ts}")

    # Sending X-Session-ID syncs HttpOnly epts_session_id cookie on response
    custom_sid = f"sid_custom_{ts}"
    dep_st = c.get(
        "/api/auth/department-status",
        headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": custom_sid},
    )
    assert dep_st.status_code == 200
    assert c.cookies.get("epts_session_id") == custom_sid
    body = dep_st.json()
    assert body["authenticated"] is False
    assert body["department_authenticated"] is False
    assert body["active"] is False


def test_single_dept_login_unlocks_all_modules_and_blocks_unauthorized(monkeypatch):
    from core import session_manager
    from gp_balance import service as gp_balance_service
    from gp_balance.models import DistrictBalanceReport

    ts = int(time.time() * 1000)
    sid = f"sid_all_mods_{ts}"
    c = TestClient(app)
    _console_login(c, monkeypatch, f"mods_{ts}")

    # Before Department Login: Console report data & generation APIs MUST reject with 401
    console_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}
    for ep in (
        "/api/naresh/data",
        "/api/naresh/view",
        "/api/naresh/download",
        "/api/balance/data",
        "/api/balance/report.pdf",
        "/api/tax/data?district=Khammam",
    ):
        resp = c.get(ep, headers=console_hdrs)
        assert resp.status_code == 401, f"Expected 401 before Dept Login on {ep}, got {resp.status_code}"
        assert resp.headers.get("X-Dept-Auth-Required") == "true"

    for gen_ep in ("/api/naresh/generate", "/api/balance/generate", "/api/reports/mas-consolidated/generate", "/api/mas/generate"):
        g_resp = c.post(gen_ep, headers=console_hdrs)
        assert g_resp.status_code == 401, f"Expected 401 before Dept Login on {gen_ep}, got {g_resp.status_code}"

    # Portal Home DCB stays open without Console/Department login
    home_client = TestClient(app)
    home_tax = home_client.get("/api/tax/data?district=Khammam", headers={"Host": "panchayatautomation.in"})
    assert home_tax.status_code == 200

    # Complete Stage-2 Department Session ONCE via cloud_sync verification
    monkeypatch.setattr(session_manager, "is_cloud_sync_fallback_allowed", lambda: True)
    sess = session_manager.get_or_create_session(sid)
    sess["user_id"] = "DPOA3698"
    sess["mode"] = "cloud_sync"
    sess["status"] = "awaiting_otp"
    otp_res = c.post(
        "/api/naresh/verify-otp",
        headers=console_hdrs,
        data={"otp": "123456"},
    )
    assert otp_res.status_code == 200
    assert otp_res.json()["success"] is True

    # Centralized department-status confirms active session
    dep = c.get("/api/auth/department-status", headers=console_hdrs).json()
    assert dep["authenticated"] is True
    assert dep["department_authenticated"] is True
    assert dep["user_id"] == "DPOA3698"

    # Populate sample cache to verify ALL active modules work under that single Dept Login
    gp_balance_service._session_reports[(sid, "29-10-2026")] = DistrictBalanceReport(
        district_name="Khammam",
        report_date_str="29-10-2026",
        generated_at="2026-10-29",
    )

    # Single login now unlocks DSR, Balance, Console Tax DCB & MAS without re-auth
    assert c.get("/api/naresh/data", headers=console_hdrs).status_code == 200
    assert c.get("/api/balance/data?date=29-10-2026", headers=console_hdrs).status_code == 200
    assert c.get("/api/tax/data?district=Khammam", headers=console_hdrs).status_code == 200
    assert c.get("/api/reports/mas-consolidated/modules", headers=console_hdrs).status_code == 200
    assert c.get("/api/mas/modules", headers=console_hdrs).status_code == 200


def test_session_expiration_returns_401_and_marks_expired(monkeypatch):
    from core import session_manager
    from gp_balance import service as gp_balance_service

    ts = int(time.time() * 1000)
    sid = f"sid_expire_{ts}"
    c = TestClient(app)
    _console_login(c, monkeypatch, f"exp_{ts}")
    console_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}

    # Authenticate session initially
    monkeypatch.setattr(session_manager, "is_cloud_sync_fallback_allowed", lambda: True)
    sess = session_manager.get_or_create_session(sid)
    sess["user_id"] = "DPOA3698"
    sess["mode"] = "cloud_sync"
    sess["status"] = "awaiting_otp"
    c.post("/api/naresh/verify-otp", headers=console_hdrs, data={"otp": "654321"})
    assert session_manager.is_authenticated(sid) is True

    # Simulate upstream session expiration during Balance generate -> returns 401 and sets status='expired'
    def _raise_perm(*args, **kwargs):
        raise PermissionError("e-Panchayat browser session is not active. Please log in again.")

    monkeypatch.setattr(gp_balance_service, "generate_balance_report_pipeline", _raise_perm)
    gen_res = c.post(
        "/api/balance/generate",
        headers=console_hdrs,
        data={"report_date": "29-10-2026"},
    )
    assert gen_res.status_code == 401
    assert gen_res.headers.get("X-Dept-Auth-Required") == "true"

    # Centralized status now reports expired=True, authenticated=False
    st = c.get("/api/auth/department-status", headers=console_hdrs).json()
    assert st["authenticated"] is False
    assert st["expired"] is True
    assert st["status"] == "expired"

    # All data endpoints deny expired session immediately
    assert c.get("/api/balance/data", headers=console_hdrs).status_code == 401
    assert c.get("/api/naresh/data", headers=console_hdrs).status_code == 401


def test_no_plaintext_password_stored_anywhere(monkeypatch):
    from core import session_manager
    from core.config import SESSIONS_DIR

    ts = int(time.time() * 1000)
    sid = f"sid_nopwd_{ts}"
    secret_pw = f"SecretPw!{ts}"
    c = TestClient(app)
    _console_login(c, monkeypatch, f"pwd_{ts}")
    console_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}

    monkeypatch.setattr(session_manager, "is_cloud_sync_fallback_allowed", lambda: True)

    class _FakeBot:
        page = None

        def __init__(self, *args, **kwargs):
            pass

        def start_browser(self):
            raise RuntimeError("cloud_sync_fallback")

    monkeypatch.setattr("dsr.automation.EPTSAutomation", _FakeBot)
    login_res = c.post(
        "/api/naresh/login",
        headers=console_hdrs,
        data={"username": "DPOA3698", "password": secret_pw},
    )
    assert login_res.status_code == 200
    otp_res = c.post("/api/naresh/verify-otp", headers=console_hdrs, data={"otp": "123456"})
    assert otp_res.status_code == 200

    # Verify in-memory session dict does not retain password
    sess = session_manager.get_or_create_session(sid)
    assert secret_pw not in json.dumps({k: v for k, v in sess.items() if isinstance(v, (str, int, float, bool))})

    # Verify persisted session JSON does not contain password
    persisted_file = SESSIONS_DIR / f"session_{sid}.json"
    if persisted_file.exists():
        assert secret_pw not in persisted_file.read_text(encoding="utf-8")

    # Verify status endpoint does not expose password
    st_text = c.get("/api/auth/department-status", headers=console_hdrs).text
    assert secret_pw not in st_text


def test_console_bundles_and_live_mas_integration():
    c = TestClient(app)

    for mas_path in ("/reports/mas?site=console", "/mas"):
        mas_res = c.get(mas_path)
        assert mas_res.status_code == 200
        assert 'id="mas-reporting-card"' in mas_res.text
        assert "/static/js/dept_session.js" in mas_res.text

    assert c.get("/api/mas/modules").status_code == 200
    assert c.get("/api/reports/mas-consolidated/modules").status_code == 200

    portal_html = c.get("/?site=console").text
    assert "/static/js/dept_session.js" in portal_html
    assert 'id="nav-btn-mas"' not in portal_html
    assert 'id="card-policy-module_mas_automation"' in portal_html
    assert "Monthly Activity Statement (MAS)" in portal_html
    assert 'id="console-mas-link"' in portal_html
    assert "openMasRobot" in portal_html

    for js_name in ("dept_session.js", "auth.js", "console.js", "admin.js"):
        r = c.get(f"/static/js/{js_name}")
        assert r.status_code == 200
        body = r.text
        assert "alert(" not in body
        assert "confirm(" not in body
        assert "prompt(" not in body
        assert "localStorage.clear(" not in body
        assert "sessionStorage.clear(" not in body


def test_department_login_live_progress_endpoint_and_ui(monkeypatch):
    from core import session_manager

    ts = int(time.time() * 1000)
    sid = f"sid_prog_{ts}"
    c = TestClient(app)
    _console_login(c, monkeypatch, f"prog_{ts}")
    console_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}

    session_manager._reset_login_progress(sid)
    session_manager._push_login_progress(sid, "[*] Launching browser (Headless: True)...")
    session_manager._push_login_progress(sid, "[*] Navigating to https://epanchayat.telangana.gov.in/cs ...")
    session_manager._push_login_progress(sid, "[+] Department Login modal is open.")
    session_manager._push_login_progress(sid, "Entering User ID & Password")
    session_manager._push_login_progress(sid, "[+] Captcha auto-detected (attempt 1): 1kfu61")
    session_manager._push_login_progress(sid, "Logging In")

    prog_res = c.get("/api/naresh/login-progress", headers=console_hdrs)
    assert prog_res.status_code == 200
    prog = prog_res.json()
    assert prog["active"] is True
    assert [row["text"] for row in prog["logs"]] == [
        "Browser Opened",
        "Entering User ID & Password",
        "Solving Captcha",
        "Logging In",
    ]
    assert prog["logs"][0]["status"] == "done"
    assert prog["logs"][-1]["status"] == "active"
    joined = " ".join(row["text"] for row in prog["logs"])
    assert "https://" not in joined
    assert "Headless" not in joined
    assert "1kfu61" not in joined
    assert "[*]" not in joined
    assert "[+]" not in joined

    html = c.get("/?site=console").text
    assert 'id="dept-modal-live-progress"' in html
    assert 'id="dept-modal-progress-list"' in html
    assert 'id="dept-modal-otp-msg" style="margin:0; font-size:0.84rem; color:#dc2626;' in html

    console_js = c.get("/static/js/console.js").text
    assert "/api/naresh/login-progress" in console_js
    assert "renderDeptLoginProgress" in console_js


def test_no_automatic_report_generation_on_login_or_station_open():
    """Verify report pipelines require explicit user action and never auto-generate right after login."""
    c = TestClient(app)

    console_js = c.get("/static/js/console.js").text
    auth_js = c.get("/static/js/auth.js").text
    dept_js = c.get("/static/js/dept_session.js").text
    mas_html = c.get("/reports/mas?site=console").text
    dcb_html = c.get("/reports/tax-dcb?site=console").text

    for name, src in (
        ("console.js", console_js),
        ("auth.js", auth_js),
        ("dept_session.js", dept_js),
    ):
        assert "autoGenerate !== false" not in src, f"{name} must use opt-in (=== true), never autoGenerate !== false"
        assert "autoGenerate !== '0'" not in src
        assert "auto_generate') !== '0'" not in src, f"{name} must require auto_generate === '1'"

    assert "pendingObj = { module: target, autoGenerate: true" not in console_js
    assert "pendingObj = { module: window.pendingStation, autoGenerate: true" not in console_js
    assert "if (opts.autoGenerate === true)" in console_js
    assert "retUrl.searchParams.set('auto_generate', '1')" not in dcb_html
    assert "autoGenerate: true," not in dcb_html
    assert "redirectMasToConsoleLogin('required', true)" not in mas_html
    assert "redirectMasToConsoleLogin('expired', true)" not in mas_html


def test_keepalive_storage_state_restore_and_missing_bot_401(monkeypatch):
    """Verify real EPTS keepalive pings, storage_state re-attach, and 401 expiry when bot is inactive."""
    from core import session_manager
    import dsr.automation as dsr_auto

    ts = int(time.time() * 1000)
    sid = f"sid_keepalive_{ts}"
    c = TestClient(app)
    _console_login(c, monkeypatch, f"keepalive_{ts}")
    console_hdrs = {"Host": "autoreports.panchayatautomation.in", "X-Session-ID": sid}

    # 1. Dead/cloud_sync session on /api/naresh/generate returns 401 + X-Dept-Auth-Required & marks expired
    monkeypatch.setattr(session_manager, "is_cloud_sync_fallback_allowed", lambda: True)
    sess = session_manager.get_or_create_session(sid)
    sess["user_id"] = "DPOA3698"
    sess["mode"] = "cloud_sync"
    sess["status"] = "awaiting_otp"
    c.post("/api/naresh/verify-otp", headers=console_hdrs, data={"otp": "123456"})

    gen_dead = c.post(
        "/api/naresh/generate",
        headers=console_hdrs,
        data={"module": "dsr_full", "date": "2026-11-12"},
    )
    assert gen_dead.status_code == 401
    assert gen_dead.headers.get("X-Dept-Auth-Required") == "true"
    assert session_manager.get_session_status(sid)["expired"] is True

    # 2. Active live_portal keepalive pings /deptLoginVerified & updates storage_state.json
    ping_calls = []

    class _FakeResp:
        ok = True
        def __init__(self, body_txt: str):
            self._txt = body_txt
        def text(self):
            return self._txt

    class _FakeReq:
        def __init__(self, body_txt: str):
            self._txt = body_txt
        def get(self, url, timeout=15000):
            ping_calls.append(url)
            return _FakeResp(self._txt)

    class _FakePage:
        url = "https://epanchayat.telangana.gov.in/deptLoginVerified"
        def is_closed(self):
            return False

    class _FakeContext:
        def __init__(self, body_txt: str):
            self.request = _FakeReq(body_txt)
        def storage_state(self, path: str):
            Path(path).write_text('{"cookies":[{"name":"JSESSIONID","value":"ok"}]}', encoding="utf-8")

    class _FakeBot:
        def __init__(self, body_txt: str = "Office ID: 3698"):
            self.page = _FakePage()
            self.context = _FakeContext(body_txt)
        def close(self):
            pass

    sid2 = f"sid_restore_{ts}"
    sess2 = session_manager.get_or_create_session(sid2)
    sess2["status"] = "authenticated"
    sess2["mode"] = "live_portal"
    sess2["user_id"] = "DPOA3698"
    sess2["authenticated_at"] = time.time()
    sess2["bot"] = _FakeBot()
    sess2["_last_epts_ping_at"] = 0.0

    session_manager._keepalive_ping(sess2)
    assert ping_calls == ["https://epanchayat.telangana.gov.in/deptLoginVerified"]
    ss_file = Path(sess2["profile_dir"]) / "storage_state.json"
    assert ss_file.exists()

    # 3. Simulated process crash (bot = None) seamlessly restores bot via saved storage_state.json
    sess2["bot"] = None

    class _RestoredBot(_FakeBot):
        def __init__(self, *args, **kwargs):
            super().__init__()
        def start_browser(self):
            pass
        def is_logged_in(self):
            return True

    monkeypatch.setattr(dsr_auto, "EPTSAutomation", _RestoredBot)
    st = session_manager.run_in_session_thread(sess2, session_manager._get_session_status_impl, sess2)
    assert st["authenticated"] is True
    assert st["bot_alive"] is True
    assert sess2["bot"] is not None

    # 4. Upstream logout detected after 2 consecutive unauthenticated keepalive responses
    sess2["bot"].context.request = _FakeReq("<html>Department Login</html>")
    sess2["_last_epts_ping_at"] = 0.0
    session_manager._keepalive_ping(sess2)
    assert sess2["status"] == "authenticated"
    sess2["_last_epts_ping_at"] = 0.0
    session_manager._keepalive_ping(sess2)
    assert sess2["status"] == "expired"
    assert not ss_file.exists()

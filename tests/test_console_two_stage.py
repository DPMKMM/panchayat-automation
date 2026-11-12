"""Tests for Console Two-Stage Auth Gate, exception handling, subpage ?site= propagation & Dockerfile."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app

ROOT_DIR = Path(__file__).resolve().parent.parent
app = create_app()


def _firebase_login(
    client: TestClient,
    monkeypatch,
    email: str,
    name: str,
    host: str = "panchayatautomation.in",
):
    uid = f"fb_{abs(hash(email))}"
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": uid,
            "gmail": email,
            "name": name,
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    return client.post(
        "/api/auth/firebase-login",
        headers={"Host": host},
        json={"id_token": f"tok_{uid}"},
    )


def test_console_stage1_gating_rejects_unauth_and_portal_token(monkeypatch):
    ts = int(time.time() * 1000)

    # 1. Unauthenticated Console host requests -> 401
    anon = TestClient(app)
    for ep in (
        "/api/naresh/data",
        "/api/naresh/session-status",
        "/api/balance/portal-dates",
        "/api/balance/data",
    ):
        r = anon.get(ep, headers={"Host": "reports.panchayatautomation.in"})
        assert r.status_code == 401, f"Expected 401 for unauth Console {ep}, got {r.status_code}"

    # 2. Single Firebase sign-in on Home unlocks Console SSO when allowed, while revoked Console access gets 403
    from core.firebase_store import COL_USERS, _db

    portal_sso = TestClient(app)
    r_sso = _firebase_login(
        portal_sso,
        monkeypatch,
        email=f"portal_sso_{ts}@gmail.com",
        name="Portal SSO User",
        host="panchayatautomation.in",
    )
    assert r_sso.status_code == 200
    for stage1_ep in ("/api/naresh/session-status", "/api/balance/portal-dates"):
        assert portal_sso.get(stage1_ep, headers={"Host": "autoreports.panchayatautomation.in"}).status_code == 200
    r_dept = portal_sso.get("/api/naresh/data", headers={"Host": "autoreports.panchayatautomation.in"})
    assert r_dept.status_code == 401
    assert r_dept.headers.get("X-Dept-Auth-Required") == "true"

    # Disabling Console access on the user immediately enforces 403 even with valid SSO cookie
    uid = r_sso.json()["user"]["user_id"]
    _db().collection(COL_USERS).document(uid).update({"can_access_console": False})
    for ep in ("/api/naresh/session-status", "/api/naresh/data", "/api/balance/portal-dates"):
        r = portal_sso.get(ep, headers={"Host": "autoreports.panchayatautomation.in"})
        assert r.status_code == 403


def test_console_stage2_error_handling_does_not_fake_success(monkeypatch):
    ts = int(time.time() * 1000)
    c = TestClient(app)
    _firebase_login(
        c,
        monkeypatch,
        email=f"console_epts_{ts}@gmail.com",
        name="Console Officer",
        host="reports.panchayatautomation.in",
    )

    # Mock unexpected login exception -> must NOT return 200 success!
    def _boom_login(*args, **kwargs):
        raise RuntimeError("Upstream ePanchayat portal unreachable")

    monkeypatch.setattr("dsr.service.start_server_login", _boom_login)
    login_err = c.post(
        "/api/naresh/login",
        headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": f"sess_{ts}"},
        data={"username": "DPOA3698", "password": "secret"},
    )
    assert login_err.status_code == 502

    # Invalid short OTP -> 400
    bad_otp = c.post(
        "/api/naresh/verify-otp",
        headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": f"sess_{ts}"},
        data={"otp": "12"},
    )
    assert bad_otp.status_code == 400

    # Mock unexpected OTP failure -> 502 (never falls through to success)
    def _boom_otp(*args, **kwargs):
        raise RuntimeError("Session expired unexpectedly")

    monkeypatch.setattr("dsr.service.verify_server_otp", _boom_otp)
    otp_err = c.post(
        "/api/naresh/verify-otp",
        headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": f"sess_{ts}"},
        data={"otp": "123456"},
    )
    assert otp_err.status_code == 502


def test_console_autoload_does_not_leak_across_sessions(monkeypatch):
    ts = int(time.time() * 1000)
    c = TestClient(app)
    _firebase_login(
        c,
        monkeypatch,
        email=f"autoload_{ts}@gmail.com",
        name="Autoload Officer",
        host="reports.panchayatautomation.in",
    )
    # Empty session-specific downloads_dir returns 404 (never falls back to global downloads dir)
    r = c.post(
        "/api/web/reports/auto-load",
        headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": f"isolated_{ts}"},
        data={"report_mode": "district"},
    )
    assert r.status_code == 404


def test_subpages_static_bundles_and_dockerfile_integrity():
    client = TestClient(app)

    # Console subpages render with console pill & zero native alert()/confirm()/.clear()
    for path in (
        "/services?site=console",
        "/privacy-legal?site=console",
        "/reports/ps-attendance?site=console",
        "/reports/tax-dcb?district=Khammam&site=console",
        "/reports/mas?site=console",
    ):
        resp = client.get(path)
        assert resp.status_code == 200
        html = resp.text
        assert 'id="subpage-console-pill" style="display:inline-flex;' in html
        assert "e-Panchayat Automation" in html
        assert "Simplifying Panchayat Administration through Smart Reporting and Automation." in html
        assert "alert(" not in html
        assert "confirm(" not in html
        assert "localStorage.clear(" not in html
        assert "sessionStorage.clear(" not in html
        assert "searchParams.set('site'" in html or "getConsoleHomeUrl" in html

    # All external JS bundles served cleanly without dialogs or storage.clear()
    for js_name in ("dept_session.js", "auth.js", "console.js", "admin.js"):
        r = client.get(f"/static/js/{js_name}")
        assert r.status_code == 200
        body = r.text
        assert "alert(" not in body
        assert "confirm(" not in body
        assert "prompt(" not in body
        assert "localStorage.clear(" not in body
        assert "sessionStorage.clear(" not in body

    assert client.get("/static/js/free_tools.js").status_code == 404
    assert client.get("/api/free/modules").status_code == 404

    # Verify Dockerfile includes all required runtime packages & templates
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")
    for req_dir in ("core/", "portal/", "templates/", "dsr/", "dcb/", "gp_balance/", "mas/", "static/", "scripts/"):
        assert req_dir in dockerfile, f"Missing {req_dir} COPY in Dockerfile"
    assert "free_tools/" not in dockerfile
    assert (ROOT_DIR / "mas").exists()


def test_buttons_modals_and_navigation_regression_guards():
    client = TestClient(app)

    # 1. Confirm modal supports both config-object and (title, message) callers + safe close helpers + scoped links
    auth_js = client.get("/static/js/auth.js").text
    assert "closeModalByIdSafely" in auth_js
    assert "optsOrTitle && typeof optsOrTitle === 'object'" in auth_js
    assert 'b.setAttribute(\'aria-disabled\', \'true\')' in auth_js
    assert "'btn-open-tool-excel'" in auth_js
    assert "'btn-launch-free-dsr'" in auth_js
    assert "Open Free Access" not in auth_js
    assert "UPCOMING_BADGE_LABELS" in auth_js
    assert "module_dsr_multiday: 'Upcoming'" in auth_js

    # 2. Console.js uses config-object confirm calls, stepper guards, safe tax fullscreen link, and single Escape flow
    console_js = client.get("/static/js/console.js").text
    assert "window.onStepperNavClick" in console_js
    assert "window.openTaxFullscreenPdf" in console_js
    assert "renderDeptModalOtpPrompt" in console_js
    assert "confirmLabel: 'Disconnect'" in console_js
    assert "confirmLabel: 'Sync Code'" in console_js
    assert "document.addEventListener('keydown'" not in console_js

    # 3. DeptSessionManager handles autoreports.* subdomain equally with reports.*
    dept_js = client.get("/static/js/dept_session.js").text
    assert "host.indexOf('autoreports.') === 0" in dept_js
    assert "host.indexOf('www.autoreports.') === 0" in dept_js

    # 4. Main shell wires guarded stepper clicks and non-navigating tax fullscreen PDF link
    shell_html = client.get("/").text
    assert 'onclick="onStepperNavClick(1)"' in shell_html
    assert 'onclick="onStepperNavClick(3)"' in shell_html
    assert 'id="tax-pdf-fullscreen-btn"' in shell_html
    assert 'target="_blank" rel="noopener noreferrer" onclick="return openTaxFullscreenPdf(event);"' in shell_html

    # 5. DCB page has no ReferenceError typos (onDistrictChange / chartClustered / chartRanking / chartPie)
    dcb_html = client.get("/reports/tax-dcb").text
    assert "onDistrictChange(" not in dcb_html
    assert "await onDistrictChanged();" in dcb_html
    assert "chartClustered" not in dcb_html
    assert "chartDistClustered" in dcb_html

    # 6. Tools Studio pages preserve ?site=console on navigation links and support Escape/backdrop closing
    for tool_path in ("/tools/excel?site=console", "/tools/pdf?site=console"):
        t_resp = client.get(tool_path)
        assert t_resp.status_code == 200
        t_html = t_resp.text
        assert "searchParams.set('site'" in t_html
        assert "'Escape'" in t_html
        assert "addEventListener('keydown'" in t_html
        assert "alert(" not in t_html
        assert "confirm(" not in t_html

    # 7. DSR upload hub prevents double hash-triggering and resets clean MAS period on report type change
    dsr_html = client.get("/reports/ps-attendance").text
    assert "handleHash(true);" in dsr_html
    assert "return false;" in dsr_html
    mas_html = client.get("/reports/mas").text
    assert "if (btn && btn.disabled) return;" in mas_html


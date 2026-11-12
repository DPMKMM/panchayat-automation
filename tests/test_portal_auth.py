"""Comprehensive test suite for Firebase Auth & Officer Profile Registration System."""

from __future__ import annotations

import time
from fastapi.testclient import TestClient

from app import create_app
from core.firebase_store import (
    VALID_DESIGNATIONS,
    VALID_ROLES,
    complete_user_profile,
    create_session,
    get_or_create_firebase_user,
    get_session_user,
    get_user_by_firebase_uid,
    get_user_by_gmail,
    init_db,
    revoke_session,
)

client = TestClient(create_app())


def _firebase_login(
    test_client: TestClient,
    monkeypatch,
    *,
    firebase_uid: str,
    gmail: str,
    name: str = "Officer",
    profile_picture: str = "",
    host: str = "panchayatautomation.in",
):
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": firebase_uid,
            "gmail": gmail,
            "name": name,
            "profile_picture": profile_picture,
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    return test_client.post(
        "/api/auth/firebase-login",
        headers={"Host": host},
        json={"id_token": f"mock_id_token_{firebase_uid}"},
    )


def test_section_6_firestore_schema_and_constraints():
    """Verify Cloud Firestore store model, unique Firebase UID lookup, and session tracking."""
    init_db()
    ts = int(time.time() * 1000)
    uid = f"firebase_uid_{ts}"
    email = f"officer_{ts}@gmail.com"

    # 1. Create first-time user
    user, is_new = get_or_create_firebase_user(
        firebase_uid=uid,
        gmail=email,
        name="Sri K. Ramesh",
        profile_picture="https://lh3.googleusercontent.com/test_pic.jpg",
    )
    assert is_new is True
    assert user["user_id"].startswith("usr_")
    assert user["firebase_uid"] == uid
    assert user["gmail"] == email
    assert user["name"] == "Sri K. Ramesh"
    assert user["profile_picture"] == "https://lh3.googleusercontent.com/test_pic.jpg"
    assert user["account_status"] == "Active"
    assert user["profile_completed"] is False
    assert user["registration_date"]
    assert user["last_login"]

    # 2. Prevent duplicate user creation with same Firebase identity
    existing_user, is_new_again = get_or_create_firebase_user(
        firebase_uid=uid,
        gmail=email,
        name="Sri K. Ramesh Updated",
    )
    assert is_new_again is False
    assert existing_user["user_id"] == user["user_id"]
    assert get_user_by_firebase_uid(uid)["user_id"] == user["user_id"]
    assert get_user_by_gmail(email)["user_id"] == user["user_id"]

    # 3. Session lifecycle (SHA-256 hashed session token)
    token = create_session(user["user_id"])
    assert bool(token)
    sess_user = get_session_user(token)
    assert sess_user is not None
    assert sess_user["user_id"] == user["user_id"]
    assert sess_user["gmail"] == email

    assert revoke_session(token) is True
    assert get_session_user(token) is None


def test_section_1_and_7_login_page_firebase_google_and_no_passwords():
    """Verify Login page uses Firebase Google Sign-In, zero custom OAuth GSI scripts, zero passwords."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert "Sign in with Google" in html
    assert "btn-google-login-action" in html
    assert "/static/js/firebase_auth.js" in html
    assert "accounts.google.com/gsi/client" not in html
    assert "google-account-chooser-modal" not in html

    assert 'id="portal-user"' not in html
    assert 'id="portal-pwd"' not in html
    assert "portal-login-form" not in html
    assert "tab-auth-register" not in html

    assert "Government of Telangana" not in html
    assert "Panchayat Raj & Rural Development" not in html
    assert "Panchayat Raj &amp; Rural Development" not in html
    assert "Authorized Officer Access" in html


def test_section_2_officer_profile_modal_completely_removed():
    """Verify the Officer Profile / User Profile Registration popup and click trigger are completely removed."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    auth_js = client.get("/static/js/auth.js?v=25").text

    for removed_id in (
        "officer-profile-modal",
        "prof-gmail",
        "prof-name",
        "prof-desig",
        "prof-role",
        "prof-phone",
        "Submit / Complete Registration",
        "Save Profile Changes",
        "openOfficerProfileView",
        "showOfficerProfileModal",
    ):
        assert removed_id not in html
        assert removed_id not in auth_js


def test_section_2_and_3_profile_registration_validations(monkeypatch):
    """Verify Firebase Auth + mandatory profile validations."""
    ts = int(time.time() * 1000)
    uid = f"fb_val_{ts}"
    email = f"officer_val_{ts}@gmail.com"

    res_auth = _firebase_login(
        client,
        monkeypatch,
        firebase_uid=uid,
        gmail=email,
        name="K. Srinivas",
        profile_picture="https://lh3.googleusercontent.com/avatar.jpg",
    )
    assert res_auth.status_code == 200
    auth_data = res_auth.json()
    assert auth_data["success"] is True
    assert auth_data["is_first_time"] is True
    assert auth_data["profile_completed"] is False
    token = auth_data["token"]

    # Reject non-10 digit mobile
    res_bad1 = client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={"name": "K. Srinivas", "designation": "MPO", "role": "Mandal Level", "mobile_number": "12345"},
    )
    assert res_bad1.status_code == 200
    assert res_bad1.json()["success"] is False
    assert "valid 10-digit Indian number" in res_bad1.json()["message"]

    # Reject numbers starting with 0-5
    res_bad2 = client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={"name": "K. Srinivas", "designation": "MPO", "role": "Mandal Level", "mobile_number": "5987654321"},
    )
    assert res_bad2.status_code == 200
    assert res_bad2.json()["success"] is False

    # Reject invalid designation
    res_bad_desig = client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={"name": "K. Srinivas", "designation": "INVALID_POST", "role": "Mandal Level", "mobile_number": "9876543210"},
    )
    assert res_bad_desig.status_code == 200
    assert res_bad_desig.json()["success"] is False

    # Reject invalid role
    res_bad_role = client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={"name": "K. Srinivas", "designation": "MPO", "role": "Unknown Level", "mobile_number": "9876543210"},
    )
    assert res_bad_role.status_code == 200
    assert res_bad_role.json()["success"] is False

    # Successful profile completion
    res_ok = client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={
            "name": "K. Srinivas Rao",
            "designation": "MPO",
            "role": "Mandal Level",
            "mobile_number": "9876543210",
        },
    )
    assert res_ok.status_code == 200
    ok_data = res_ok.json()
    assert ok_data["success"] is True
    assert ok_data["user"]["profile_completed"] is True
    assert ok_data["user"]["designation"] == "MPO"
    assert ok_data["user"]["role"] == "Mandal Level"
    assert ok_data["user"]["mobile_number"] == "9876543210"
    assert ok_data["user"]["gmail"] == email


def test_section_3_and_4_returning_user_direct_dashboard(monkeypatch):
    """Verify returning Firebase officer is recognized automatically without re-registration."""
    ts = int(time.time() * 1000)
    uid = f"fb_return_{ts}"
    email = f"officer_return_{ts}@gmail.com"

    res1 = _firebase_login(client, monkeypatch, firebase_uid=uid, gmail=email, name="Returning Officer")
    token1 = res1.json()["token"]
    client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token1},
        json={"name": "Returning Officer", "designation": "DPO", "role": "District Level", "mobile_number": "9123456789"},
    )

    res2 = _firebase_login(client, monkeypatch, firebase_uid=uid, gmail=email, name="Returning Officer")
    assert res2.status_code == 200
    login_data = res2.json()
    assert login_data["success"] is True
    assert login_data["is_first_time"] is False
    assert login_data["profile_completed"] is True
    assert login_data["user"]["designation"] == "DPO"
    assert login_data["user"]["role"] == "District Level"


def test_section_5_dashboard_user_information_and_logout(monkeypatch):
    """Verify header displays officer info from Firestore and logout revokes session."""
    ts = int(time.time() * 1000)
    uid = f"fb_dash_{ts}"
    email = f"officer_dash_{ts}@gmail.com"

    res_auth = _firebase_login(
        client,
        monkeypatch,
        firebase_uid=uid,
        gmail=email,
        name="Header Officer",
        profile_picture="https://lh3.googleusercontent.com/avatar_test.jpg",
    )
    token = res_auth.json()["token"]
    client.post(
        "/api/auth/register-profile",
        headers={"X-Portal-Token": token},
        json={"name": "Header Officer", "designation": "DEO", "role": "Mandal Level", "mobile_number": "8877665544"},
    )

    res_me = client.get("/api/auth/portal-status", headers={"X-Portal-Token": token})
    assert res_me.status_code == 200
    me = res_me.json()
    assert me["authenticated"] is True
    assert me["profile_completed"] is True
    assert me["firebase_config"]["projectId"] == "epanchayat-automation-tg"
    u = me["user"]
    assert u["name"] == "Header Officer"
    assert u["gmail"] == email
    assert u["designation"] == "DEO"
    assert u["role"] == "Mandal Level"
    assert u["mobile_number"] == "8877665544"
    assert u["profile_picture"] == "https://lh3.googleusercontent.com/avatar_test.jpg"

    res_logout = client.post("/api/auth/logout", headers={"X-Portal-Token": token})
    assert res_logout.status_code == 200
    assert res_logout.json()["success"] is True

    res_after = client.get("/api/auth/portal-status", headers={"X-Portal-Token": token})
    assert res_after.json()["authenticated"] is False


def test_all_official_designations_and_roles_mapping(monkeypatch):
    """Verify all 7 designations (DPO, DPM, DLPO, MPDO, MPO, PS, DEO) and 3 roles."""
    test_cases = [
        ("DPO", "District Level"),
        ("DPM", "District Level"),
        ("DLPO", "Division Level"),
        ("MPDO", "Mandal Level"),
        ("MPO", "Mandal Level"),
        ("PS", "Mandal Level"),
        ("DEO", "Mandal Level"),
    ]

    for desig, role in test_cases:
        ts = int(time.time() * 1000)
        uid = f"fb_{desig.lower()}_{ts}"
        email = f"{desig.lower()}_{ts}@gmail.com"

        res = _firebase_login(client, monkeypatch, firebase_uid=uid, gmail=email, name=f"Officer {desig}")
        token = res.json()["token"]

        res_reg = client.post(
            "/api/auth/register-profile",
            headers={"X-Portal-Token": token},
            json={"name": f"Officer {desig}", "designation": desig, "role": role, "mobile_number": "9988776655"},
        )
        assert res_reg.status_code == 200
        u = res_reg.json()["user"]
        assert u["designation"] == desig
        assert u["role"] == role
        assert u["profile_completed"] is True


def test_feedback_api_and_firestore_persistence():
    """Verify feedback submission, validation, and Cloud Firestore storage."""
    res_empty = client.post("/api/feedback", json={"message": ""})
    assert res_empty.status_code == 400
    assert res_empty.json()["success"] is False

    payload = {
        "name": "Sri K. Venkatesh",
        "email": "venkatesh.mpo@gmail.com",
        "designation": "MPO",
        "role": "Mandal Level",
        "rating": 5,
        "category": "Feature Request",
        "message": "The combined landscape PDF is extremely helpful for weekly Mandal review meetings.",
    }
    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "submitted successfully" in data["message"]
    assert data["record"]["name"] == "Sri K. Venkatesh"


def test_privacy_legal_pages():
    """Verify privacy and legal transparency pages are accessible."""
    res_priv = client.get("/privacy-legal")
    assert res_priv.status_code == 200
    assert "Privacy Policy" in res_priv.text
    assert "Terms of Service" in res_priv.text

    res_leg = client.get("/legal")
    assert res_leg.status_code == 200
    assert "e-Panchayat Automation" in res_leg.text
    for route in ("/", "/privacy-legal", "/legal", "/services", "/mas", "/reports/ps-attendance"):
        page = client.get(route).text
        assert "Government of Telangana" not in page
        assert "Panchayat Raj & Rural Development" not in page
        assert "Panchayat Raj &amp; Rural Development" not in page


def test_login_screen_layout_and_navigation_bar():
    """Verify top navbar strip is removed, login quick-links & hero left branding match cleanly."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert '<header class="navbar"' not in html
    assert 'id="hero-welcome-message"' not in html
    assert "gov-brand-subbadge" not in html
    assert '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>' in html

    assert "Services" in html
    assert "Privacy &amp; Legal" in html or "Privacy & Legal" in html
    assert "Feedback" in html
    assert "openPrivacyLegalModal" in html
    assert "openFeedbackModal" in html

    assert "Zero-Wait Background Robot Engine" not in html
    assert "gov-about-portal-section" not in html
    assert "gov-features-grid" not in html
    assert "gov-card-left" not in html
    assert "Open Free Access Across Reporting" not in html

    assert "Sign in with Google" in html
    assert "Firebase Auth" in html
    assert "google-account-chooser-modal" not in html
    assert "accounts.google.com/gsi/client" not in html

    auth_js = client.get("/static/js/auth.js").text
    assert "nav-btn-console-switch" in auth_js
    assert "if (btnPrivacy) btnPrivacy.style.display = 'none';" in auth_js
    assert "if (btnFeedback) btnFeedback.style.display = 'none';" in auth_js
    assert "if (btnServices) btnServices.style.display = 'none';" in auth_js
    assert "if (btnConsoleSwitch) btnConsoleSwitch.style.display = 'none';" in auth_js


def test_unified_home_login_and_manual_plus_automated_reports(monkeypatch):
    """Verify Home renders Google Sign-In first and asks Manual vs Automated after login (no subscription required now)."""
    html = client.get("/").text
    assert "portal-open-home" not in html
    assert 'id="portal-hero-card"' in html
    assert "Sign in with Google" in html
    assert 'id="post-login-dashboard" style="display: none;"' in html
    assert 'id="workspace-mode-selector"' in html
    assert 'id="card-choose-manual"' in html
    assert 'id="card-choose-automated"' in html
    assert 'id="card-choose-tools"' in html
    assert 'id="btn-choose-manual"' in html
    assert 'id="btn-choose-automated"' in html
    assert 'id="btn-choose-tools"' in html
    assert 'id="tools-modules-section"' in html
    assert 'id="card-tool-excel"' in html
    assert 'id="card-tool-pdf"' in html
    assert 'href="/tools/excel"' in html
    assert 'href="/tools/pdf"' in html
    assert 'id="card-tools-under-prep"' not in html
    assert "dpoa-fresh-toggle-wrap" not in html
    assert 'value="DPOA3698"' not in html
    assert "Officer DPOA3698 Exclusive" not in html
    assert 'id="badge-manual-mode-access"' not in html
    assert "Available Free (Pre-Subscription)" not in html
    assert "Subscription enforcement will be added later" not in html
    assert 'id="portal-modules-section" style="display:none;"' in html
    assert 'id="console-modules-section" style="display:none; margin-top:28px;"' in html
    assert 'id="automation-live-stage"' in html
    assert 'class="auto-pipeline-flow"' in html
    assert "state-home-login" in html
    assert 'id="live-dcb-analytics-section"' in html
    assert 'id="card-policy-module_dsr_excel"' in html
    assert 'id="card-policy-module_dsr_multiday"' in html
    assert 'id="card-policy-module_dsr_automation"' in html
    assert 'id="card-policy-module_gp_balance_automation"' in html
    assert 'id="card-policy-module_mas_automation"' in html
    assert 'id="card-policy-module_dcb_live"' in html
    assert 'id="console-tax-card"' not in html
    assert 'id="nav-btn-mas"' not in html
    assert "/reports/ps-attendance#reports" in html
    assert "Open Free Access" not in html
    assert 'id="badge-policy-module_dsr_multiday">Upcoming<' in html
    assert 'id="btn-launch-multiday-dsr"' in html
    assert "/reports/mas" in html
    assert "openMasRobot" in html
    assert "Resend OTP" not in html
    assert ">Department Login<" in html

    css_text = client.get("/static/css/common.css").text
    assert "html.portal-open-home" not in css_text
    assert "body.state-home-login" in css_text
    assert "body.state-workspace-hub" in css_text
    assert "body.state-automation-page" in css_text
    assert "@keyframes autoPacketFlow" in css_text

    auth_js = client.get("/static/js/auth.js").text
    assert "window.applyScreenVisualState" in auth_js
    assert "window.selectWorkspaceMode" in auth_js
    assert "window.showWorkspaceModeSelector" in auth_js
    assert "window.isAdminHost" in auth_js
    assert "window.isManualHost" in auth_js
    assert "window.isToolsHost" in auth_js
    assert "https://manualreports.panchayatautomation.in/" in auth_js
    assert "https://autoreports.panchayatautomation.in/" in auth_js
    assert "https://tools.panchayatautomation.in/" in auth_js
    assert 'id="login-section-nav"' in html
    assert 'id="login-link-autoreports"' in html
    assert 'id="login-link-manualreports"' in html
    assert 'id="login-link-tools"' in html
    assert "automated_subscription_required" in auth_js
    assert "Available Free (Pre-Subscription)" not in auth_js
    assert "Subscription enforcement will be added later" not in auth_js
    assert "portal-open-home" not in auth_js

    console_js = client.get("/static/js/console.js").text
    assert "isDpoAdmin" not in console_js
    assert "Admin DPOA3698" not in console_js
    assert "https://admin.panchayatautomation.in" in console_js

    # Home login cookie allows /api/reports/mas-consolidated/modules & /api/auth/department-status across non-reports host
    ts = int(time.time() * 1000)
    home_client = TestClient(create_app())
    _firebase_login(
        home_client,
        monkeypatch,
        firebase_uid=f"fb_home_{ts}",
        gmail=f"home_officer_{ts}@gmail.com",
        name="Home Officer",
        host="panchayatautomation.in",
    )
    assert home_client.get("/api/reports/mas-consolidated/modules", headers={"Host": "panchayatautomation.in"}).status_code == 200
    assert home_client.get("/api/auth/department-status", headers={"Host": "panchayatautomation.in"}).status_code == 200

    # Regression guard: Google sign-in does NOT pop up mandatory User Profile Registration modal
    assert "showOfficerProfileModal(user, { allowClose: false })" not in auth_js
    assert "showOfficerProfileModal(portalUser, { allowClose: false })" not in auth_js
    assert "allowClose: false" not in auth_js


def test_authenticated_module_load_hides_login_card_ssr(monkeypatch):
    client = TestClient(create_app())

    # Unauthenticated visitor should see the Google Sign-In hero card immediately
    anon_res = client.get("/", headers={"Host": "panchayatautomation.in"})
    assert anon_res.status_code == 200
    assert "state-auth-resolving" not in anon_res.text.split("</body")[0].split("<body")[1].split(">")[0]
    assert 'id="portal-hero-card" style="display:none;' not in anon_res.text

    # Authenticated visitor opening any module/subdomain should NOT flash the Google Sign-In screen
    ts = int(time.time() * 1000)
    _firebase_login(
        client,
        monkeypatch,
        firebase_uid=f"fb_ssr_{ts}",
        gmail=f"ssr_officer_{ts}@gmail.com",
        name="SSR Officer",
        host="panchayatautomation.in",
    )

    for host, path in [
        ("autoreports.panchayatautomation.in", "/"),
        ("manualreports.panchayatautomation.in", "/"),
        ("tools.panchayatautomation.in", "/"),
        ("panchayatautomation.in", "/autoreports"),
        ("panchayatautomation.in", "/manualreports"),
    ]:
        page = client.get(path, headers={"Host": host})
        assert page.status_code == 200
        body_tag = "<body" + page.text.split("<body", 1)[1].split(">", 1)[0] + ">"
        assert "state-auth-resolving" in body_tag
        assert '<div id="portal-hero-card" class="gov-login-wrapper" style="display:none; margin-bottom: 24px;">' in page.text

    css_res = client.get("/static/css/common.css?v=13", headers={"Host": "panchayatautomation.in"})
    assert css_res.status_code == 200
    assert "body.state-auth-resolving #portal-hero-card" in css_res.text

    js_res = client.get("/static/js/auth.js?v=25", headers={"Host": "panchayatautomation.in"})
    assert js_res.status_code == 200
    assert "state-auth-resolving" in js_res.text
    assert "cachedToken && cachedUser" in js_res.text

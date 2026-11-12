"""Tests for Administrator Governance Dashboard APIs, RBAC, self-lockout protection & policy controls."""

from __future__ import annotations

import time
from fastapi.testclient import TestClient

from app import create_app

app = create_app()


def _login(
    monkeypatch,
    email: str,
    name: str,
    host: str = "panchayatautomation.in",
) -> tuple[TestClient, dict]:
    c = TestClient(app)
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
    res = c.post(
        "/api/auth/firebase-login",
        headers={"Host": host},
        json={"id_token": f"tok_{uid}"},
    )
    assert res.status_code == 200
    return c, res.json()


def test_admin_endpoints_enforce_strict_rbac(monkeypatch):
    anon = TestClient(app)
    for ep in ("/api/admin/overview", "/api/admin/users", "/api/admin/policy", "/api/admin/feedback"):
        assert anon.get(ep).status_code == 401

    assert anon.get("/api/admin/oauth-config").status_code == 404

    ts = int(time.time() * 1000)
    regular, _ = _login(monkeypatch, f"non_admin_{ts}@gmail.com", "Non Admin")
    for ep in ("/api/admin/overview", "/api/admin/users", "/api/admin/policy", "/api/admin/feedback"):
        assert regular.get(ep).status_code == 403
    assert regular.post("/api/admin/policy", json={"portal_enabled": False}).status_code == 403


def test_admin_overview_users_patch_and_self_lockout_guards(monkeypatch):
    ts = int(time.time() * 1000)
    admin, admin_body = _login(monkeypatch, "admin.epanchayat@gmail.com", "State Admin")
    admin_uid = admin_body["user"]["user_id"]
    assert admin_body["user"]["is_admin"] is True

    # Create target officer
    target_email = f"target_officer_{ts}@gmail.com"
    target_client, target_body = _login(monkeypatch, target_email, "Target Officer")
    target_uid = target_body["user"]["user_id"]
    target_client.post(
        "/api/auth/register-profile",
        headers={"Host": "panchayatautomation.in"},
        json={
            "name": "Target Officer",
            "designation": "MPO",
            "role": "Mandal Level",
            "mobile_number": "9123456780",
        },
    )

    # 1. Overview stats include Firebase posture (never legacy OAuth)
    ov = admin.get("/api/admin/overview")
    assert ov.status_code == 200
    ov_data = ov.json()
    assert ov_data["success"] is True
    assert "oauth" not in ov_data
    assert ov_data["firebase"]["project_id"] == "epanchayat-automation-tg"
    assert ov_data["stats"]["total_users"] >= 2
    assert isinstance(ov_data["stats"]["by_designation"], list)
    assert any(item.get("designation") == "MPO" for item in ov_data["stats"]["by_designation"])

    # 2. Users listing & search/filter
    ul = admin.get(f"/api/admin/users?search={target_email}")
    assert ul.status_code == 200
    assert any(u["user_id"] == target_uid for u in ul.json()["users"])

    # 3. Admin updates target designation & disables Console access -> target blocked on Console
    upd_res = admin.patch(
        f"/api/admin/users/{target_uid}",
        json={"designation": "DPM", "can_access_console": False},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["user"]["designation"] == "DPM"
    assert upd_res.json()["user"]["can_access_console"] is False

    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": target_body["user"]["firebase_uid"],
            "gmail": target_email,
            "name": "Target Officer",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    blocked_console_login = TestClient(app).post(
        "/api/auth/firebase-login",
        headers={"Host": "reports.panchayatautomation.in"},
        json={"id_token": "tok_blocked_console"},
    )
    assert blocked_console_login.status_code == 403

    # Disable target account completely -> existing session immediately invalidated
    dis_res = admin.patch(f"/api/admin/users/{target_uid}", json={"account_status": "Disabled"})
    assert dis_res.status_code == 200
    assert target_client.get("/api/auth/portal-status", headers={"Host": "panchayatautomation.in"}).json()["authenticated"] is False

    # Restore target active status
    admin.patch(f"/api/admin/users/{target_uid}", json={"account_status": "Active", "can_access_console": True})

    # 4. Self-lockout 400 protections
    assert admin.patch(f"/api/admin/users/{admin_uid}", json={"account_status": "Disabled"}).status_code == 400
    assert admin.patch(f"/api/admin/users/{admin_uid}", json={"is_admin": False}).status_code == 400
    assert (
        admin.patch(
            f"/api/admin/users/{admin_uid}",
            json={"can_access_portal": False, "can_access_console": False},
        ).status_code
        == 400
    )


def test_admin_policy_toggle_and_feedback_inbox(monkeypatch):
    ts = int(time.time() * 1000)
    admin, _ = _login(monkeypatch, "admin.epanchayat@gmail.com", "State Admin")

    # Feedback submission & admin visibility
    fb_res = admin.post(
        "/api/feedback",
        json={"message": f"Admin check feedback {ts}", "rating": 5, "category": "Console"},
    )
    assert fb_res.status_code == 200
    fb_list = admin.get("/api/admin/feedback")
    assert fb_list.status_code == 200
    assert any(f"Admin check feedback {ts}" in row["message"] for row in fb_list.json()["feedback"])

    # Disable console globally via policy -> Console Firebase login blocked with 403
    try:
        p_off = admin.post("/api/admin/policy", json={"console_enabled": False})
        assert p_off.status_code == 200
        assert p_off.json()["flags"]["console_enabled"] is False

        monkeypatch.setattr(
            "portal.router.verify_firebase_id_token",
            lambda tok: {
                "firebase_uid": f"fb_blocked_{ts}",
                "gmail": f"blocked_{ts}@gmail.com",
                "name": "Blocked Officer",
                "profile_picture": "",
                "sign_in_provider": "google.com",
                "email_verified": True,
            },
        )
        c_attempt = TestClient(app).post(
            "/api/auth/firebase-login",
            headers={"Host": "reports.panchayatautomation.in"},
            json={"id_token": "tok_policy_blocked"},
        )
        assert c_attempt.status_code == 403
    finally:
        p_on = admin.post("/api/admin/policy", json={"console_enabled": True})
        assert p_on.status_code == 200
        assert p_on.json()["flags"]["console_enabled"] is True


def test_subscription_gate_open_now_and_enforced_when_enabled(monkeypatch):
    """Automated Console works without subscription by default, and enforces when toggled on."""
    ts = int(time.time() * 1000)
    admin, _ = _login(monkeypatch, "admin.epanchayat@gmail.com", "State Admin")

    # Regular officer logging in on Home host
    officer_client, officer_body = _login(
        monkeypatch, f"sub_check_{ts}@gmail.com", "Subscription Tester", host="panchayatautomation.in"
    )
    assert officer_body["user"]["can_access_automated"] is True

    # 1. Default rollout: automated_subscription_required is False -> Automated APIs open without subscription
    pol = admin.get("/api/admin/policy").json()["flags"]
    assert pol["automated_subscription_required"] is False
    assert officer_client.get("/api/reports/mas-consolidated/modules", headers={"Host": "panchayatautomation.in"}).status_code == 200

    # 2. When admin enables automated_subscription_required -> non-subscribed officer gets 403 & can_access_automated=False
    try:
        r_on = admin.post("/api/admin/policy", json={"automated_subscription_required": True})
        assert r_on.status_code == 200
        assert r_on.json()["flags"]["automated_subscription_required"] is True

        st = officer_client.get("/api/auth/portal-status", headers={"Host": "panchayatautomation.in"}).json()
        assert st["user"]["can_access_automated"] is False
        assert officer_client.get("/api/reports/mas-consolidated/modules", headers={"Host": "panchayatautomation.in"}).status_code == 403
    finally:
        admin.post("/api/admin/policy", json={"automated_subscription_required": False})


def test_revoked_admin_accounts_and_separate_admin_host(monkeypatch):
    """DPOA3698 & dpmkhammam7/dpmkmm7 have zero admin rights; /api/admin/* requires admin.panchayatautomation.in on prod domains."""
    from core.config import is_admin_email

    # 1. Revoked emails are NEVER admin even if placed in ADMIN_EMAILS
    monkeypatch.setenv("ADMIN_EMAILS", "admin.epanchayat@gmail.com,dpmkhammam7@gmail.com,dpmkmm7@gmail.com")
    assert is_admin_email("admin.epanchayat@gmail.com") is True
    assert is_admin_email("dpmkhammam7@gmail.com") is False
    assert is_admin_email("dpmkmm7@gmail.com") is False

    # 2. Signing in as dpmkhammam7@gmail.com yields is_admin=False & 403 even on admin host
    revoked_client, revoked_body = _login(
        monkeypatch, "dpmkhammam7@gmail.com", "Former Admin", host="admin.panchayatautomation.in"
    )
    assert revoked_body["user"]["is_admin"] is False
    assert revoked_client.get("/api/admin/overview", headers={"Host": "admin.panchayatautomation.in"}).status_code == 403
    assert revoked_client.get("/api/system/sessions", headers={"Host": "admin.panchayatautomation.in"}).status_code == 403

    # 3. Valid admin can manage /api/admin/* ONLY on admin.panchayatautomation.in (blocked with 403 on public/report hosts)
    admin_client, admin_body = _login(
        monkeypatch, "admin.epanchayat@gmail.com", "State Admin", host="admin.panchayatautomation.in"
    )
    assert admin_body["user"]["is_admin"] is True
    assert admin_client.get("/api/admin/overview", headers={"Host": "admin.panchayatautomation.in"}).status_code == 200
    assert admin_client.get("/api/system/sessions", headers={"Host": "admin.panchayatautomation.in"}).status_code == 200
    for non_admin_host in ("panchayatautomation.in", "autoreports.panchayatautomation.in", "reports.panchayatautomation.in"):
        assert admin_client.get("/api/admin/overview", headers={"Host": non_admin_host}).status_code == 403
        assert admin_client.get("/api/system/sessions", headers={"Host": non_admin_host}).status_code == 403


def test_admin_host_branding_tool_telemetry_and_razorpay_database(monkeypatch):
    """Verify dedicated admin host routing, per-tool usage telemetry, and subscription/Razorpay ledger DB."""
    import hashlib
    import hmac
    import pymupdf

    ts = int(time.time() * 1000)
    admin_client, _ = _login(
        monkeypatch, "admin.epanchayat@gmail.com", "State Admin", host="admin.panchayatautomation.in"
    )
    officer_email = f"razorpay_officer_{ts}@gmail.com"
    officer_client, officer_body = _login(
        monkeypatch, officer_email, "Subscribed Officer", host="panchayatautomation.in"
    )
    officer_uid = officer_body["user"]["user_id"]

    # 1. Admin host renders dedicated Admin Control Center branding & tabs (no generic landing trap)
    adm_html = admin_client.get("/", headers={"Host": "admin.panchayatautomation.in"}).text
    assert "Admin Control Center" in adm_html
    assert 'id="admin-tab-tools"' in adm_html
    assert 'id="admin-tab-subscriptions"' in adm_html
    assert 'id="admin-nonadmin-gate"' in adm_html
    assert admin_client.get("/admin").status_code == 200

    auth_js = admin_client.get("/static/js/auth.js?v=20").text
    assert "window.isAdminRouteOrHost" in auth_js
    assert "if (dedSection === 'admin'" in auth_js

    # 2. Simulate tool runs (Excel + PDF) and verify real tool usage telemetry in Admin Overview & Tool Analytics
    ex_resp = officer_client.post(
        "/api/tools/excel/execute",
        headers={"Host": "tools.panchayatautomation.in"},
        data={"tool_id": "xls_to_xlsx"},
        files={"files": ("demo.xls", b"<html><table><tr><th>A</th></tr><tr><td>1</td></tr></table></html>", "application/vnd.ms-excel")},
    )
    assert ex_resp.status_code == 200, ex_resp.text

    def _pdf_bytes(lbl: str) -> bytes:
        doc = pymupdf.open()
        doc.new_page().insert_text((50, 50), lbl)
        out = doc.tobytes()
        doc.close()
        return out

    pdf_resp = officer_client.post(
        "/api/tools/pdf/merge",
        headers={"Host": "tools.panchayatautomation.in"},
        files=[
            ("files", ("one.pdf", _pdf_bytes("One"), "application/pdf")),
            ("files", ("two.pdf", _pdf_bytes("Two"), "application/pdf")),
        ],
    )
    assert pdf_resp.status_code == 200, pdf_resp.text

    ov = admin_client.get("/api/admin/overview", headers={"Host": "admin.panchayatautomation.in"}).json()
    stats = ov["stats"]
    assert stats["total_users"] >= 2
    assert stats["active_users"] >= 2
    assert stats["active_users_now"] >= 2
    assert stats["total_tool_runs"] >= 2
    tool_ids = {t["tool_id"] for t in stats["tool_usage"]}
    assert "excel:xls_to_xlsx" in tool_ids
    assert "pdf:merge" in tool_ids

    tool_analytics = admin_client.get(
        "/api/admin/tool-usage?days=30", headers={"Host": "admin.panchayatautomation.in"}
    ).json()
    assert tool_analytics["unique_tools_used"] >= 2
    assert any(ev["tool_id"] == "excel:xls_to_xlsx" for ev in tool_analytics["recent_activity"])

    # 3. Billing readiness (unconfigured Razorpay) + Plans + Admin Grant/Revoke
    plans_res = officer_client.get("/api/billing/plans", headers={"Host": "panchayatautomation.in"})
    assert plans_res.status_code == 200
    assert plans_res.json()["razorpay"]["configured"] is False
    assert any(p["plan_id"] == "plan_monthly" for p in plans_res.json()["plans"])

    unconf_order = officer_client.post(
        "/api/billing/razorpay/create-order",
        headers={"Host": "panchayatautomation.in"},
        json={"plan_id": "plan_monthly"},
    )
    assert unconf_order.status_code == 503

    plan_save = admin_client.post(
        "/api/admin/plans",
        headers={"Host": "admin.panchayatautomation.in"},
        json={"plan_id": "plan_custom", "name": "Half Yearly Pass", "amount_inr": 499, "duration_days": 180},
    )
    assert plan_save.status_code == 200
    assert plan_save.json()["plan"]["amount_paise"] == 49900

    grant_res = admin_client.post(
        "/api/admin/subscriptions/grant",
        headers={"Host": "admin.panchayatautomation.in"},
        json={"user_id": officer_uid, "plan_id": "plan_monthly", "record_payment": True, "notes": "Pilot grant"},
    )
    assert grant_res.status_code == 200, grant_res.text

    try:
        assert admin_client.post(
            "/api/admin/policy",
            headers={"Host": "admin.panchayatautomation.in"},
            json={"automated_subscription_required": True},
        ).status_code == 200
        # Subscribed officer keeps Console access even when gate is enforced
        st_sub = officer_client.get("/api/auth/portal-status", headers={"Host": "panchayatautomation.in"}).json()
        assert st_sub["user"]["has_automated_subscription"] is True
        assert st_sub["user"]["can_access_automated"] is True

        subs_data = admin_client.get("/api/admin/subscriptions", headers={"Host": "admin.panchayatautomation.in"}).json()
        assert subs_data["summary"]["subscribed_users"] >= 1
        assert subs_data["summary"]["total_revenue_inr"] >= 99.0

        # Revoke removes Console access when gate is enforced
        rev_res = admin_client.post(
            f"/api/admin/subscriptions/{officer_uid}/revoke",
            headers={"Host": "admin.panchayatautomation.in"},
        )
        assert rev_res.status_code == 200
        st_rev = officer_client.get("/api/auth/portal-status", headers={"Host": "panchayatautomation.in"}).json()
        assert st_rev["user"]["has_automated_subscription"] is False
        assert st_rev["user"]["can_access_automated"] is False
    finally:
        admin_client.post(
            "/api/admin/policy",
            headers={"Host": "admin.panchayatautomation.in"},
            json={"automated_subscription_required": False},
        )

    # 4. Simulated Razorpay payment signature verification & activation
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_demo123456")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_test_key_999")
    rzp_order_id = f"order_demo_{ts}"
    rzp_pay_id = f"pay_demo_{ts}"
    bad_verify = officer_client.post(
        "/api/billing/razorpay/verify",
        headers={"Host": "panchayatautomation.in"},
        json={
            "plan_id": "plan_annual",
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_pay_id,
            "razorpay_signature": "tampered_sig",
        },
    )
    assert bad_verify.status_code == 400

    valid_sig = hmac.new(
        b"secret_test_key_999",
        f"{rzp_order_id}|{rzp_pay_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    good_verify = officer_client.post(
        "/api/billing/razorpay/verify",
        headers={"Host": "panchayatautomation.in"},
        json={
            "plan_id": "plan_annual",
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_pay_id,
            "razorpay_signature": valid_sig,
        },
    )
    assert good_verify.status_code == 200, good_verify.text
    bill_status = officer_client.get("/api/billing/status", headers={"Host": "panchayatautomation.in"}).json()
    assert bill_status["user"]["has_automated_subscription"] is True
    assert bill_status["active_subscription"]["plan_id"] == "plan_annual"
    assert any(p["razorpay_payment_id"] == rzp_pay_id and p["status"] == "captured" for p in bill_status["payments"])

"""Unit tests for Daily Status Report (DSR) & Attendance endpoints."""

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_home_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "e-Panchayat" in resp.text or "Attendance" in resp.text


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "DSR" in data["modules"]


def test_session_status():
    resp = client.get("/api/naresh/session-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_system_sessions():
    from dsr import service as automation_service

    # 1. Non-admin or unauthenticated call must be restricted
    resp = client.get("/api/system/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "restricted" in data["error"].lower()

    # 2. Administrator DPOA3698 call must succeed
    admin_sid = "test_admin_dpoa3698"
    s = automation_service.get_or_create_session(admin_sid)
    s["user_id"] = "DPOA3698"
    s["status"] = "authenticated"
    s["mode"] = "cloud_sync"

    resp_admin = client.get("/api/system/sessions", headers={"X-Session-ID": admin_sid})
    assert resp_admin.status_code == 200
    data_admin = resp_admin.json()
    assert data_admin["success"] is True
    assert "total_sessions" in data_admin


def test_manual_upload_page():
    resp = client.get("/reports/ps-attendance")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

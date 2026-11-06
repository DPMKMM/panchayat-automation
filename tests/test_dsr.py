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
    resp = client.get("/api/system/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_manual_upload_page():
    resp = client.get("/reports/ps-attendance")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

import time
import pytest
from starlette.testclient import TestClient

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "automate_epts"))

import automation_service
from app import create_app


def test_session_timer_initial_defaults():
    sid = "test_timer_user_1"
    session = automation_service.get_or_create_session(sid)
    assert session["session_duration"] == 600
    assert session["extended"] is False


def test_session_authenticated_and_timer_status():
    sid = "test_timer_user_2"
    session = automation_service.get_or_create_session(sid)
    session["status"] = "authenticated"
    session["authenticated_at"] = time.time()
    session["user_id"] = "9999"
    session["mode"] = "cloud_sync"
    session["session_duration"] = 600
    session["extended"] = False

    status = automation_service.get_session_status(sid)
    assert status["authenticated"] is True
    assert status["session_duration"] == 600
    assert status["expires_in"] <= 600 and status["expires_in"] >= 595
    assert status["can_extend"] is True
    assert status["extended"] is False
    assert status["max_duration"] == 1200


def test_session_extend_by_ten_minutes():
    sid = "test_timer_user_3"
    session = automation_service.get_or_create_session(sid)
    session["status"] = "authenticated"
    session["authenticated_at"] = time.time()
    session["user_id"] = "8888"
    session["mode"] = "cloud_sync"
    session["session_duration"] = 600
    session["extended"] = False

    # Extend session by 10 minutes
    res = automation_service.extend_session(sid)
    assert res["success"] is True
    assert res["session_duration"] == 1200
    assert res["can_extend"] is False
    assert res["extended"] is True
    assert res["expires_in"] <= 1200 and res["expires_in"] >= 1195

    # Second extension attempt must be rejected (capped at 20 mins)
    with pytest.raises(ValueError, match="Maximum session extension reached"):
        automation_service.extend_session(sid)


def test_session_auto_expire_after_time_limit():
    sid = "test_timer_user_4"
    session = automation_service.get_or_create_session(sid)
    session["status"] = "authenticated"
    # Simulate session authenticated 650 seconds ago (past 600s limit)
    session["authenticated_at"] = time.time() - 650
    session["user_id"] = "7777"
    session["mode"] = "cloud_sync"
    session["session_duration"] = 600
    session["extended"] = False

    status = automation_service.get_session_status(sid)
    assert status["authenticated"] is False
    assert status["status"] == "expired"
    assert "expired" in status["message"].lower()


def test_extend_session_api_endpoint():
    app = create_app()
    client = TestClient(app)
    sid = "test_api_timer_officer"

    # Set up active authenticated session
    session = automation_service.get_or_create_session(sid)
    session["status"] = "authenticated"
    session["authenticated_at"] = time.time()
    session["user_id"] = "5555"
    session["mode"] = "cloud_sync"
    session["session_duration"] = 600
    session["extended"] = False

    # Send extend request
    resp = client.post(
        "/api/naresh/extend-session",
        cookies={"epts_session_id": sid},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["session_duration"] == 1200
    assert data["can_extend"] is False
    assert data["extended"] is True

    # Attempt to extend again via API
    resp2 = client.post(
        "/api/naresh/extend-session",
        cookies={"epts_session_id": sid},
    )
    assert resp2.status_code == 400
    assert "Maximum session extension reached" in resp2.json()["detail"]

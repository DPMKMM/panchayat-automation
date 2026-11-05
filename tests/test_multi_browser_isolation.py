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


def test_anti_caching_headers_present():
    app = create_app()
    client = TestClient(app)

    # Check root HTML response
    resp = client.get("/")
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "no-cache" in resp.headers.get("Cache-Control", "")
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"

    # Check session-status API response
    resp_api = client.get("/api/naresh/session-status")
    assert resp_api.status_code == 200
    assert "no-store" in resp_api.headers.get("Cache-Control", "")
    assert resp_api.headers.get("Pragma") == "no-cache"


def test_independent_devices_isolation():
    app = create_app()
    client = TestClient(app)

    sid_device_a = "client_desktop_chrome_9911"
    sid_device_b = "client_mobile_safari_8822"

    # 1. Device A logs in
    session_a = automation_service.get_or_create_session(sid_device_a)
    session_a["status"] = "authenticated"
    session_a["authenticated_at"] = time.time()
    session_a["user_id"] = "OFFICER_A"
    session_a["mode"] = "cloud_sync"
    session_a["session_duration"] = 600

    # 2. Query Device A status via API
    resp_a = client.get(
        "/api/naresh/session-status",
        headers={"X-Session-ID": sid_device_a},
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["authenticated"] is True
    assert data_a["user_id"] == "OFFICER_A"
    assert data_a["session_id"] == sid_device_a

    # 3. Query Device B status via API (different device / browser)
    resp_b = client.get(
        "/api/naresh/session-status",
        headers={"X-Session-ID": sid_device_b},
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    # Device B MUST NOT be authenticated!
    assert data_b["authenticated"] is False
    assert data_b["status"] == "idle"
    assert data_b["session_id"] == sid_device_b

    # 4. Device B logs out
    client.post(
        "/api/naresh/logout",
        headers={"X-Session-ID": sid_device_b},
    )

    # 5. Verify Device A is STILL authenticated and unaffected!
    resp_a_after = client.get(
        "/api/naresh/session-status",
        headers={"X-Session-ID": sid_device_a},
    )
    data_a_after = resp_a_after.json()
    assert data_a_after["authenticated"] is True
    assert data_a_after["user_id"] == "OFFICER_A"

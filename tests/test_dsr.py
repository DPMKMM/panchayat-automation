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


def test_combined_landscape_pdf_generation(tmp_path):
    from datetime import date
    import pypdf
    from dsr.pdf_generator import ReportData, generate_pdf

    mandals = ["Bonakal", "Chinthakani", "Khammam (Rural)", "Yerrupalem"]
    mandal_rows = [
        {
            "serial": i, "mandal": m, "total_gps": 25,
            "before_9": 22, "before_9_pct": 88.0, "attendance_pct": 92.0,
            "on_leave": 1, "meeting_training": 1, "pending": 1,
        }
        for i, m in enumerate(mandals, start=1)
    ]
    dsr_mandal_rows = [
        {
            "serial": i, "mandal": m, "total_gps": 25,
            "present_ps": 23, "dsr_entered": 21, "dsr_pending": 2, "dsr_pct": 91.3,
        }
        for i, m in enumerate(mandals, start=1)
    ]
    district_total = {
        "total_gps": 100, "before_9": 88, "before_9_pct": 88.0, "attendance_pct": 92.0,
        "on_leave": 4, "meeting_training": 4, "pending": 4,
    }
    dsr_district_total = {
        "total_gps": 100, "present_ps": 92, "dsr_entered": 84, "dsr_pending": 8, "dsr_pct": 91.3,
    }

    report = ReportData(
        district_name="Khammam",
        report_date=date(2026, 11, 8),
        source_row_count=100,
        unique_gp_count=100,
        missing_lgd_rows=0,
        duplicate_lgd_rows=0,
        conflicts=[],
        mandal_rows=mandal_rows,
        district_total=district_total,
        pending_rows=[{"serial": 1, "mandal": "Bonakal", "gp": "GP1", "ps_name": "PS1", "nature_of_posting": "Reg", "mobile": "999"}],
        leave_rows=[],
        meeting_training_rows=[],
        after_9_rows=[],
        dsr_mandal_rows=dsr_mandal_rows,
        dsr_district_total=dsr_district_total,
        dsr_pending_rows=[],
        all_gp_rows=[],
    )

    pdf_out = tmp_path / "test_report.pdf"
    generate_pdf(report, pdf_out)
    assert pdf_out.exists()

    reader = pypdf.PdfReader(str(pdf_out))
    assert len(reader.pages) >= 2

    # Page 1 must be Landscape
    p1 = reader.pages[0]
    assert float(p1.mediabox.width) > float(p1.mediabox.height)
    p1_txt = p1.extract_text()
    assert "ATTENDANCE ABSTRACT" in p1_txt
    assert "DSR ABSTRACT REPORT" in p1_txt
    assert "DISTRICT TOTAL" in p1_txt
    assert "Total PS" in p1_txt

    # Page 2 must be Portrait
    p2 = reader.pages[1]
    assert float(p2.mediabox.height) > float(p2.mediabox.width)


def test_dpoa3698_persistent_session():
    from dsr.service import _get_session_status_impl, _extend_session_impl
    import time

    mock_session = {
        'session_id': 'test_dpoa3698_sess',
        'user_id': 'DPOA3698',
        'status': 'authenticated',
        'mode': 'cloud_sync',
        'authenticated_at': time.time() - 3600,
        'session_duration': 600,
        'extended': False,
        'bot_alive': True,
        'last_activity': time.time(),
    }

    status = _get_session_status_impl(mock_session)
    assert status['no_expiry'] is True
    assert status['expires_in'] == 999999
    assert status['status'] == 'authenticated'
    assert 'Persistent Session' in status['message']

    ext = _extend_session_impl(mock_session)
    assert ext['success'] is True
    assert ext['no_expiry'] is True

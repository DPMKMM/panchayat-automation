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
    assert "Generated Time:" in p1_txt

    # Page 2 must be Portrait
    p2 = reader.pages[1]
    assert float(p2.mediabox.height) > float(p2.mediabox.width)
    p2_txt = p2.extract_text()
    assert "2. ATTENDANCE PENDING GPs" in p2_txt


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


def test_cutoff_time_and_sorting_options():
    import pandas as pd
    from dsr.pdf_generator import analyze_attendance

    raw_data = [
        {"District Name": "Khammam", "Mandal Name": "Mandal A", "Grampanchayat Name": "GP A1", "Panchayat Lgd": "101", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 08:45:00", "DSR Status": "Entered", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Mandal A", "Grampanchayat Name": "GP A2", "Panchayat Lgd": "102", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 09:15:00", "DSR Status": "Entered", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Mandal B", "Grampanchayat Name": "GP B1", "Panchayat Lgd": "103", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 08:30:00", "DSR Status": "Not Entered", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Mandal B", "Grampanchayat Name": "GP B2", "Panchayat Lgd": "104", "First Attendence Status": "", "Second Attendence Status": "", "First Attendence Datetime": "", "DSR Status": "", "Nature Of Reason": ""},
    ]
    df = pd.DataFrame(raw_data)

    # 1. Test default cutoff (09:00 AM) and default sort (before_9)
    rep1 = analyze_attendance(df, cutoff_time="09:00", sort_by="before_9")
    assert rep1.cutoff_label == "9 AM"
    assert rep1.totals["cutoff_time"] == "09:00"
    assert rep1.totals["sort_by"] == "before_9"

    # 2. Test custom cutoff time 09:30 AM
    rep2 = analyze_attendance(df, cutoff_time="09:30", sort_by="before_9")
    assert rep2.cutoff_label == "9:30 AM"
    # At 09:30 cutoff, GP A2 (09:15) is before cutoff, so Mandal A has 100% punctuality (2 out of 2)
    m_a = next(m for m in rep2.mandal_rows if m["mandal"] == "Mandal A")
    assert m_a["before_9"] == 2

    # 3. Test sorting options: attendance pending (highest pending first)
    rep3 = analyze_attendance(df, cutoff_time="09:00", sort_by="att_pending")
    # Mandal B has 1 pending, Mandal A has 0 pending -> Mandal B must be first
    assert rep3.mandal_rows[0]["mandal"] == "Mandal B"
    assert rep3.mandal_rows[0]["serial"] == 1
    assert rep3.mandal_rows[1]["serial"] == 2

    # 4. Test DSR sorting options: DSR pending
    rep4 = analyze_attendance(df, cutoff_time="09:00", sort_by="dsr_pending")
    # Mandal B has 1 DSR pending (GP B1 is present but DSR not entered), Mandal A has 0 DSR pending
    assert rep4.mandal_rows[0]["mandal"] == "Mandal B"
    assert rep4.mandal_rows[0]["serial"] == 1

    # 5. Test strict cutoff: 09:00 AM submission must NOT be included in before 9 AM
    raw_strict = [
        {"District Name": "Khammam", "Mandal Name": "Mandal C", "Grampanchayat Name": "GP C1", "Panchayat Lgd": "201", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 08:59:59", "DSR Status": "Entered", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Mandal C", "Grampanchayat Name": "GP C2", "Panchayat Lgd": "202", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 09:00:00", "DSR Status": "Entered", "Nature Of Reason": ""},
    ]
    df_strict = pd.DataFrame(raw_strict)
    rep_strict = analyze_attendance(df_strict, cutoff_time="09:00")
    # GP C1 (08:59:59) is < 09:00 -> before cutoff. GP C2 (09:00:00) is NOT < 09:00 -> after cutoff.
    m_c = rep_strict.mandal_rows[0]
    assert m_c["before_9"] == 1
    assert len(rep_strict.after_9_rows) == 1
    assert rep_strict.after_9_rows[0]["gp"] == "GP C2"


def test_download_filename_no_official():
    import re
    from dsr import service as automation_service
    from core.config import REPORTS_DIR

    sid = "test_no_official_sid"
    session = automation_service.get_or_create_session(sid)

    dummy_pdf = REPORTS_DIR / "Khammam_DSR_Report_08-Nov-2026_08-38-AM_09-00_before_9.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 test dummy content over 500 bytes " + b"0" * 600)

    session["latest_pdf_path"] = str(dummy_pdf)
    session["download_filename"] = "Khammam_PS_Attendance_and_DSR_Report_08-Nov-2026_08-38-AM.pdf"

    resp = client.get("/api/naresh/download", headers={"X-Session-ID": sid})
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "filename=" in cd
    assert "Official" not in cd
    assert "Khammam_PS_Attendance_and_DSR_Report_08-Nov-2026_08-38-AM.pdf" in cd

    # Test fallback when download_filename is not in session
    session.pop("download_filename", None)
    session["latest_pdf_path"] = str(dummy_pdf)
    resp2 = client.get("/api/naresh/download", headers={"X-Session-ID": sid})
    assert resp2.status_code == 200
    cd2 = resp2.headers.get("content-disposition", "")
    assert "Official" not in cd2
    assert re.search(r"Khammam_PS_Attendance_and_DSR_Report_08-Nov-2026_\d{2}-\d{2}-[A-Za-z]{2}\.pdf", cd2)


def test_dpoa3698_force_fresh_cache_bypass(tmp_path):
    import time
    from dsr import service as automation_service
    from dsr.service import _DSR_CACHE, _DSR_CACHE_LOCK

    sid_dpo = "sid_test_dpoa3698_fresh"
    session_dpo = automation_service.get_or_create_session(sid_dpo)
    session_dpo["status"] = "authenticated"
    session_dpo["user_id"] = "DPOA3698"
    session_dpo["district_name"] = "Khammam"

    cached_pdf = tmp_path / "cached_report.pdf"
    cached_pdf.write_bytes(b"%PDF-1.4 dummy " + b"0" * 600)

    cache_key = ("dsr_full", "02-Nov-2026", "Khammam", "09:00", "before_9")
    with _DSR_CACHE_LOCK:
        _DSR_CACHE[cache_key] = {
            "timestamp": time.time(),
            "latest_pdf_path": str(cached_pdf),
            "download_filename": "cached.pdf",
            "latest_report_date": "02-Nov-2026",
            "report_data": {"cached": True},
            "response": {"success": True, "cached": True},
        }

    # 1. Without force_fresh, DPOA3698 gets cached entry
    res1 = automation_service.generate_server_report(
        module="dsr_full", date_str="2026-11-02", session_id=sid_dpo, cutoff_time="09:00", sort_by="before_9", force_fresh=False
    )
    assert res1.get("cached") is True

    # 2. For non-DPOA3698 users, force_fresh=True does NOT bypass cache (SDC protection)
    sid_other = "sid_test_other_officer"
    session_other = automation_service.get_or_create_session(sid_other)
    session_other["status"] = "authenticated"
    session_other["user_id"] = "DLPO1234"
    session_other["district_name"] = "Khammam"
    res2 = automation_service.generate_server_report(
        module="dsr_full", date_str="2026-11-02", session_id=sid_other, cutoff_time="09:00", sort_by="before_9", force_fresh=True
    )
    assert res2.get("cached") is True





def test_services_hub_page():
    resp1 = client.get('/services')
    assert resp1.status_code == 200
    assert 'text/html' in resp1.headers['content-type']
    assert 'Services' in resp1.text
    assert 'Multi-Day Attendance' in resp1.text

    # /services-inspections-bal was removed as requested
    resp2 = client.get('/services-inspections-bal')
    assert resp2.status_code == 404

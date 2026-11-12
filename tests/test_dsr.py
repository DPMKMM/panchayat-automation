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

    # 1. Unauthenticated / non-admin calls must be rejected (401/403)
    resp = client.get("/api/system/sessions")
    assert resp.status_code == 401

    # 2. Regular officer DPOA3698 must have ZERO admin privileges on /api/system/sessions & /api/system/sync
    dpo_sid = "test_regular_dpoa3698"
    s = automation_service.get_or_create_session(dpo_sid)
    s["user_id"] = "DPOA3698"
    s["status"] = "authenticated"
    s["mode"] = "cloud_sync"

    resp_dpo = client.get("/api/system/sessions", headers={"X-Session-ID": dpo_sid})
    assert resp_dpo.status_code == 401
    resp_sync = client.post("/api/system/sync", headers={"X-Session-ID": dpo_sid})
    assert resp_sync.status_code == 401


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


def test_combined_abstract_dynamic_row_height_fills_page1(tmp_path):
    """Verify Page 1 abstract row height auto-expands to utilize page space without spilling to Page 2."""
    from datetime import date
    import pymupdf
    from dsr.pdf_generator import ReportData, generate_pdf

    for count in (20, 32):
        rows = [
            {
                "serial": i + 1, "mandal": f"Mandal {i + 1}", "total_gps": 25,
                "before_9": 22, "before_9_pct": 88.0, "attendance_submitted": 25,
                "attendance_pct": 100.0, "on_leave": 1, "meeting_training": 0, "pending": 0,
            }
            for i in range(count)
        ]
        dsr_rows = [
            {
                "serial": i + 1, "mandal": f"Mandal {i + 1}", "total_gps": 25,
                "present_ps": 24, "dsr_entered": 23, "dsr_pending": 1, "dsr_pct": 95.83,
            }
            for i in range(count)
        ]
        rpt = ReportData(
            district_name="Khammam",
            report_date=date(2026, 11, 11),
            source_row_count=count * 25,
            unique_gp_count=count * 25,
            missing_lgd_rows=0,
            duplicate_lgd_rows=0,
            conflicts=[],
            mandal_rows=rows,
            district_total={
                "total_gps": count * 25, "before_9": count * 22, "before_9_pct": 88.0,
                "attendance_submitted": count * 25, "attendance_pct": 100.0,
                "on_leave": count, "meeting_training": 0, "pending": 0,
            },
            pending_rows=[],
            leave_rows=[],
            meeting_training_rows=[],
            after_9_rows=[],
            dsr_mandal_rows=dsr_rows,
            dsr_district_total={
                "total_gps": count * 25, "present_ps": count * 24,
                "dsr_entered": count * 23, "dsr_pending": count, "dsr_pct": 95.83,
            },
            dsr_pending_rows=[],
            all_gp_rows=[],
        )
        pdf_out = tmp_path / f"abstract_{count}.pdf"
        generate_pdf(rpt, pdf_out)
        doc = pymupdf.open(str(pdf_out))
        try:
            assert "2. ATTENDANCE PENDING GPs" in doc[1].get_text()
            p1_h = doc[0].rect.height
            content_bottom = max(
                (d["rect"].y1 for d in doc[0].get_drawings() if d["rect"].y1 < p1_h - 25),
                default=0,
            )
            assert content_bottom / p1_h >= 0.88
        finally:
            doc.close()


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


def test_all_authenticated_sessions_no_10m_restriction():
    """Verify that ANY authenticated session has no 10-minute restriction and never auto-expires."""
    from dsr.service import _get_session_status_impl, _extend_session_impl
    import time

    mock_session = {
        'session_id': 'test_officer_mpo_sess',
        'user_id': 'MPOA1234',
        'status': 'authenticated',
        'mode': 'cloud_sync',
        'authenticated_at': time.time() - 7200,  # 2 hours ago (well beyond 10m / 600s)
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
    assert ext['expires_in'] == 999999


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
    """DPOA3698 is treated identically to other officers with zero exclusive cache-bypass admin privilege."""
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

    # Neither DPOA3698 nor any other officer receives an exclusive bypass
    res1 = automation_service.generate_server_report(
        module="dsr_full", date_str="2026-11-02", session_id=sid_dpo, cutoff_time="09:00", sort_by="before_9", force_fresh=True
    )
    assert res1.get("cached") is True

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
    html = resp1.text
    assert 'Services' in html
    assert 'Multi-Day Attendance' in html
    assert 'PS Attendance &amp; DSR Report' in html
    assert 'Thursday GP Bank Balance Report' in html
    assert 'Gram Panchayat Inspections' in html
    assert 'House Tax Demand Collection Balance' in html
    assert 'Monthly Activity Statement (MAS)' in html

    # All service-meta blocks and card action hyperlinks/buttons must be removed (informational cards only)
    for removed_text in (
        '<div class="service-meta">',
        'Daily Morning (8:00 AM',
        '1-Page Landscape PDF, Exception Tables',
        'Multi-Date Range Scraping',
        'Habitual Pendency Tracking &amp; Trend Charts',
        'Weekly Every Thursday',
        'Legal 2-Page PDF &amp; Filterable Excel',
        'DPO, DLPO, MPO Field Visits',
        'Interactive Table &amp; CSV Export',
        'Public / No Login Required',
        'PowerBI Visual Report, PDF, Excel',
        'Monthly Governance Review',
        'Zero Duplicate Login (Shared Session)',
        'Launch Attendance Robot',
        'Multi-Day Scope Details',
        'Launch Balance Robot',
        'Inspection Scope Details',
        'Open House Tax DCB',
        'Open MAS Report Workspace',
        '/?station=dsr',
        '/?station=balance',
        '/#tax-station',
        '/reports/mas?site=console',
    ):
        assert removed_text not in html, f'Unexpected leftover in /services: {removed_text}'

    # /services-inspections-bal was removed as requested
    resp2 = client.get('/services-inspections-bal')
    assert resp2.status_code == 404


def test_multiday_dsr_pdf_excel_and_endpoint():
    import io
    import openpyxl
    import pypdf

    def _make_day_xlsx(dt_prefix: str, third_status: str, third_dsr: str) -> bytes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([
            "District Name",
            "Panchayat LGD",
            "Mandal Name",
            "Panchayat Name",
            "First Attendence Status",
            "Second Attendence Status",
            "First Attendence Datetime",
            "DSR Status",
            "Panchayat Secretary Name",
            "Mobile Number",
        ])
        ws.append(["Khammam", "205101", "Bonakal", "Allinagaram", "Present", "Present", f"{dt_prefix} 08:40:00", "Entered", "Ramesh", "9876543210"])
        ws.append(["Khammam", "205102", "Bonakal", "Govindapuram", "Present", "Present", f"{dt_prefix} 09:20:00", "Not Entered", "Suresh", "9876543211"])
        ws.append(["Khammam", "205201", "Chinthakani", "Nagulavancha", third_status, third_status, f"{dt_prefix} 08:50:00" if third_status else "", third_dsr, "Padma", "9876543212"])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    day1_bytes = _make_day_xlsx("2026-11-08", "", "Not Entered")
    day2_bytes = _make_day_xlsx("2026-11-09", "Present", "Entered")

    page_res = client.get("/reports/ps-attendance")
    assert page_res.status_code == 200
    assert 'id="tab-btn-multiday"' in page_res.text
    assert 'id="multiday-form"' in page_res.text

    res = client.post(
        "/api/web/multi-day-reports",
        files=[
            ("files", ("day_08_Nov_2026.xlsx", day1_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ("files", ("day_09_Nov_2026.xlsx", day2_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ],
        data={"cutoff_time": "09:00"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "Completed"
    assert body["days_count"] == 2
    assert body["unique_gp_count"] == 3
    job_id = body["job_id"]

    pdf_res = client.get(f"/api/web/reports/{job_id}/download")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")
    assert "MultiDay_DSR_Report" in pdf_res.headers.get("content-disposition", "")
    assert "08-Nov-2026 to 09-Nov-2026" in body.get("date_range", "")
    reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
    assert len(reader.pages) >= 2
    full_pdf_txt = "\n".join(p.extract_text() for p in reader.pages)
    assert "MULTIPLE DAYS PS ATTENDANCE" in full_pdf_txt
    assert "Govindapuram" in full_pdf_txt

    xlsx_res = client.get(f"/api/web/reports/{job_id}/download-excel")
    assert xlsx_res.status_code == 200
    wb_out = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
    assert set(wb_out.sheetnames) >= {"Date Trend", "Mandal Consolidated", "Habitual Defaulters", "GP Day Matrix"}


def test_dsr_page_layout_individual_default_and_continuous(tmp_path):
    from datetime import date
    import io
    import openpyxl
    from pypdf import PdfReader
    from dsr.pdf_generator import ReportData, generate_pdf, generate_mandal_pdf

    # 1. Automated & Manual UI expose the PDF Page Layout selector defaulting to Individual Pages
    home_html = client.get("/").text
    assert 'id="auto-page-layout"' in home_html
    assert '<option value="individual" selected>' in home_html
    assert '<option value="continuous">' in home_html

    console_js = client.get("/static/js/console.js?v=18").text
    assert "auto-page-layout" in console_js
    assert "formData.append('page_layout', pageLayout)" in console_js

    manual_html = client.get("/reports/ps-attendance").text
    assert 'id="district-page-layout"' in manual_html
    assert 'id="mandal-page-layout"' in manual_html

    # 2. District PDF: Individual keeps 6 separate pages (Page 1 Mandal Abstract, Pages 2-6 individual);
    #    Continuous keeps Mandal Abstract on Page 1 and continues Sections 2-6 right after the previous table ends
    report = ReportData(
        district_name="KHAMMAM",
        report_date=date(2026, 11, 12),
        source_row_count=20,
        unique_gp_count=20,
        missing_lgd_rows=0,
        duplicate_lgd_rows=0,
        conflicts=[],
        mandal_rows=[{
            "serial": 1,
            "mandal": "BONAKAL",
            "total_gps": 20,
            "before_9": 15,
            "before_9_pct": 75.0,
            "submitted": 18,
            "attendance_pct": 90.0,
            "on_leave": 1,
            "meeting_training": 1,
            "pending": 2,
        }],
        district_total={
            "total_gps": 20,
            "before_9": 15,
            "before_9_pct": 75.0,
            "submitted": 18,
            "attendance_pct": 90.0,
            "on_leave": 1,
            "meeting_training": 1,
            "pending": 2,
        },
        dsr_mandal_rows=[{
            "serial": 1,
            "mandal": "BONAKAL",
            "total_gps": 20,
            "present_ps": 16,
            "dsr_entered": 15,
            "dsr_pending": 1,
            "dsr_pct": 93.75,
        }],
        dsr_district_total={
            "total_gps": 20,
            "present_ps": 16,
            "dsr_entered": 15,
            "dsr_pending": 1,
            "dsr_pct": 93.75,
        },
        pending_rows=[{"mandal": "BONAKAL", "gp": "GP A", "ps_name": "PS A", "nature_of_posting": "Regular", "mobile": "9876543210"}],
        dsr_pending_rows=[{"mandal": "BONAKAL", "gp": "GP B", "attendance_status": "Present", "timestamp": "08:30:00", "time_only": "08:30 AM"}],
        leave_rows=[{"mandal": "BONAKAL", "gp": "GP C", "ps_name": "PS C", "nature_of_posting": "Regular", "mobile": "9876543211", "status": "Leave"}],
        meeting_training_rows=[{"mandal": "BONAKAL", "gp": "GP D", "ps_name": "PS D", "nature_of_posting": "Regular", "mobile": "9876543212", "status": "Meeting"}],
        after_9_rows=[{"mandal": "BONAKAL", "gp": "GP E", "ps_name": "PS E", "nature_of_posting": "Regular", "mobile": "9876543213", "time_only": "09:15 AM", "status": "Present"}],
        all_gp_rows=[{"mandal": "BONAKAL", "gp": "GP A", "is_pending": True, "submitted": False, "on_leave": False, "meeting_training": False, "after_9": False, "dsr_eligible": False, "dsr_entered": False, "status": "Pending", "time_only": ""}],
    )

    indiv_pdf = tmp_path / "district_individual.pdf"
    cont_pdf = tmp_path / "district_continuous.pdf"
    generate_pdf(report, indiv_pdf)  # Default is individual
    generate_pdf(report, cont_pdf, page_layout="continuous")

    indiv_reader = PdfReader(str(indiv_pdf))
    cont_reader = PdfReader(str(cont_pdf))
    assert len(indiv_reader.pages) == 6
    assert "MANDAL-WISE ATTENDANCE & DSR ABSTRACT REPORT" in indiv_reader.pages[0].extract_text()
    assert len(cont_reader.pages) == 2
    assert "MANDAL-WISE ATTENDANCE & DSR ABSTRACT REPORT" in cont_reader.pages[0].extract_text()
    page2_text = cont_reader.pages[1].extract_text()
    for heading in (
        "2. ATTENDANCE PENDING GPs",
        "3. DSR PENDING GPs",
        "4. SECRETARIES REPORTED AS LEAVE",
        "5. SECRETARIES REPORTED AS TRAINING / MEETING",
        "6. GPs THAT SUBMITTED ATTENDANCE AFTER",
    ):
        assert heading in page2_text

    # 3. Mandal PDF also respects individual (2 pages) vs continuous (1 page)
    m_indiv = tmp_path / "mandal_individual.pdf"
    m_cont = tmp_path / "mandal_continuous.pdf"
    generate_mandal_pdf(report, m_indiv, mandal_name="BONAKAL")
    generate_mandal_pdf(report, m_cont, mandal_name="BONAKAL", page_layout="continuous")
    assert len(PdfReader(str(m_indiv)).pages) == 2
    assert len(PdfReader(str(m_cont)).pages) == 1

    # 4. Manual web upload endpoint /api/web/reports accepts page_layout=continuous and produces continuous PDF
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["District Name", "Panchayat LGD", "Mandal Name", "Panchayat Name", "First Attendence Status", "Second Attendence Status", "First Attendence Datetime", "DSR Status"])
    ws.append(["Khammam", "205101", "Bonakal", "Allinagaram", "Present", "Present", "2026-11-12 08:40:00", "Entered"])
    ws.append(["Khammam", "205102", "Bonakal", "Govindapuram", "Present", "Present", "2026-11-12 09:20:00", "Not Entered"])
    xbuf = io.BytesIO()
    wb.save(xbuf)

    up_res = client.post(
        "/api/web/reports",
        files={"file": ("raw_12_Nov.xlsx", xbuf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"report_mode": "district", "page_layout": "continuous"},
    )
    assert up_res.status_code == 200
    jid = up_res.json()["job_id"]
    dl_res = client.get(f"/api/web/reports/{jid}/download")
    assert dl_res.status_code == 200
    web_reader = PdfReader(io.BytesIO(dl_res.content))
    assert len(web_reader.pages) == 2
    assert "MANDAL-WISE ATTENDANCE & DSR ABSTRACT REPORT" in web_reader.pages[0].extract_text()
    assert "6. GPs THAT SUBMITTED ATTENDANCE AFTER" in web_reader.pages[1].extract_text()

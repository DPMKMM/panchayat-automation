"""Unit, Integration, and Playwright Tests for Automated Multiple Days DSR Module (Auto_Multi_DSR)."""

from __future__ import annotations

import io
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

os.environ["ENVIRONMENT"] = "development"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = ""

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl
from fastapi.testclient import TestClient
from pypdf import PdfReader

from Auto_Multi_DSR.holidays import (
    analyze_working_days,
    format_display_date,
    format_portal_date,
    is_second_saturday,
    is_sunday,
    parse_date_input,
)
from Auto_Multi_DSR import service as auto_multi_service
from app import app

client = TestClient(app)


def _make_epts_html_report(rows: list[dict[str, str]]) -> bytes:
    cols = [
        "District Name",
        "Mandal Name",
        "Panchayat Name",
        "Panchayat LGD",
        "First Attendence Status",
        "First Attendence Datetime",
        "DSR Entry Status",
        "DSR Submited Datetime",
    ]
    trs = []
    for r in rows:
        tds = "".join(f"<td>{r.get(c, '')}</td>" for c in cols)
        trs.append(f"<tr>{tds}</tr>")
    html = (
        "<html><body>"
        "<table><tr><td colspan='8'>GM-R 1.2.7 Attendance &amp; DSR Report</td></tr></table>"
        f"<table><thead><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
        "</body></html>"
    )
    return html.encode("utf-8")


def _console_login(test_client: TestClient, monkeypatch, suffix: str) -> dict:
    email = f"auto_multi_officer_{suffix}@gmail.com"
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": f"fb_am_{suffix}",
            "gmail": email,
            "name": f"Auto Multi Officer {suffix}",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    res = test_client.post(
        "/api/auth/firebase-login",
        headers={"Host": "reports.panchayatautomation.in"},
        json={"id_token": f"tok_am_{suffix}"},
    )
    assert res.status_code == 200
    return res.json()


def test_holiday_calculation_sundays_second_saturdays_and_public_holidays():
    """Verify exact holiday identification across calendar boundaries."""
    # 1. Sundays
    assert is_sunday(date(2026, 11, 1)) is True
    assert is_sunday(date(2026, 11, 8)) is True
    assert is_sunday(date(2026, 11, 7)) is False  # Saturday

    # 2. Second Saturdays: strictly Saturday falling on day 8 through 14
    # Nov 2026: 1st Sat = Nov 7, 2nd Sat = Nov 14, 3rd Sat = Nov 21
    assert is_second_saturday(date(2026, 11, 7)) is False   # 1st Saturday
    assert is_second_saturday(date(2026, 11, 14)) is True   # 2nd Saturday
    assert is_second_saturday(date(2026, 11, 21)) is False  # 3rd Saturday
    assert is_second_saturday(date(2026, 11, 28)) is False  # 4th Saturday

    # Aug 2026: 1st Sat = Aug 1, 2nd Sat = Aug 8
    assert is_second_saturday(date(2026, 8, 1)) is False
    assert is_second_saturday(date(2026, 8, 8)) is True
    assert is_second_saturday(date(2026, 8, 15)) is False

    # 3. Analyze working days range: 2026-11-06 (Fri) to 2026-11-16 (Mon) = 11 calendar days
    # In this range:
    # Nov 6 (Fri): Working
    # Nov 7 (Sat, 1st Sat): Working
    # Nov 8 (Sun): Excluded (Sunday)
    # Nov 9 (Mon): Working
    # Nov 10 (Tue): Working
    # Nov 11 (Wed): Excluded as Public Holiday
    # Nov 12 (Thu): Working
    # Nov 13 (Fri): Working
    # Nov 14 (Sat, 2nd Sat): Excluded (Second Saturday)
    # Nov 15 (Sun): Excluded (Sunday)
    # Nov 16 (Mon): Working
    analysis = analyze_working_days(
        start_date_raw="2026-11-06",
        end_date_raw="2026-11-16",
        public_holidays_raw=["2026-11-11"],
    )
    assert analysis.total_calendar_days == 11
    assert analysis.excluded_sundays == ["2026-11-08", "2026-11-15"]
    assert analysis.excluded_second_saturdays == ["2026-11-14"]
    assert analysis.excluded_public_holidays == ["2026-11-11"]
    assert analysis.working_days == [
        "2026-11-06",
        "2026-11-07",
        "2026-11-09",
        "2026-11-10",
        "2026-11-12",
        "2026-11-13",
        "2026-11-16",
    ]
    assert len(analysis.working_days) == 7

    # Check date formatting helpers
    assert format_portal_date(date(2026, 11, 6)) == "06-Nov-2026"
    assert format_display_date(date(2026, 11, 6)) == "06-11-2026"
    assert parse_date_input("06-11-2026") == date(2026, 11, 6)


def test_auto_multi_dsr_pipeline_execution_and_deliverables(monkeypatch, tmp_path):
    """End-to-end simulation of the background automated download and consolidation pipeline."""
    from dsr import service as automation_service

    monkeypatch.setattr("Auto_Multi_DSR.service.get_reports_dir", lambda: tmp_path)

    day1 = _make_epts_html_report([
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Allinagaram",
            "Panchayat LGD": "205101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "09-11-2026 08:35:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "09-11-2026 11:00:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Govindapuram",
            "Panchayat LGD": "205102",
            "First Attendence Status": "On Leave",
            "First Attendence Datetime": "09-11-2026 09:15:00",
            "DSR Entry Status": "Not Entered",
            "DSR Submited Datetime": "",
        },
    ])

    day2 = _make_epts_html_report([
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Allinagaram",
            "Panchayat LGD": "205101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "10-11-2026 08:45:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "10-11-2026 11:30:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Govindapuram",
            "Panchayat LGD": "205102",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "10-11-2026 08:50:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "10-11-2026 12:00:00",
        },
    ])

    download_calls = []

    def _mock_download(bot, target_date, downloads_dir=None, max_retries=2):
        t_str = str(target_date)
        download_calls.append(t_str)
        if "09" in t_str:
            return "09_11_2026_raw.xls", day1
        return "10_11_2026_raw.xls", day2

    monkeypatch.setattr("Auto_Multi_DSR.automation.download_daily_gmr127_raw", _mock_download)

    sid = "sid_auto_multi_test"
    sess = automation_service.get_or_create_session(sid)
    sess["authenticated"] = True
    sess["status"] = "authenticated"
    sess["user_id"] = "DPOA3698"
    sess["district_name"] = "Khammam"

    class _DummyBot:
        class _Page:
            def is_closed(self):
                return False
        page = _Page()

    sess["bot"] = _DummyBot()
    monkeypatch.setattr(automation_service, "_is_bot_alive", lambda b: True)
    monkeypatch.setattr(automation_service, "run_in_session_thread", lambda s, fn, *a, **kw: fn(*a, **kw))

    # Range: 2026-11-08 (Sun, auto-excluded) to 2026-11-10 (Tue)
    # Working days: 2026-11-09 (Mon) and 2026-11-10 (Tue)
    res = auto_multi_service.start_auto_multi_dsr_pipeline(
        session_id=sid,
        user_id="DPOA3698",
        district_name="Khammam",
        start_date="2026-11-08",
        end_date="2026-11-10",
        include_time_matrix=True,
    )
    assert res["success"] is True
    job_id = res["job_id"]
    assert res["total_working_days"] == 2

    # Wait for background thread completion
    for _ in range(40):
        status = auto_multi_service.get_job_status(job_id, sid)
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)

    assert status["status"] == "completed"
    assert status["completed_count"] == 2
    assert status["failed_count"] == 0
    assert download_calls == ["2026-11-09", "2026-11-10"]

    # Verify report data structure
    rep = status["report_data"]
    assert rep["summary"]["dist_name"] == "Khammam"
    assert rep["summary"]["total_gps"] == 2
    assert "Average Time" in rep["time_matrix_columns"]

    # Verify artifacts download
    pdf_fname, pdf_raw, pdf_mime = auto_multi_service.get_job_artifact(job_id, sid, "pdf", level="all")
    assert pdf_mime == "application/pdf"
    assert pdf_raw.startswith(b"%PDF")
    assert "_Auto_MultiDays_DSR_Full_Report_" in pdf_fname

    gp_fname, gp_raw, _ = auto_multi_service.get_job_artifact(job_id, sid, "pdf", level="gp")
    assert "_Auto_MultiDays_DSR_GP_Summary_" in gp_fname
    reader = PdfReader(io.BytesIO(gp_raw))
    gp_txt = "\n".join(p.extract_text() for p in reader.pages)
    assert "Gram Panchayat Level" in gp_txt
    assert "District Level — Date-Wise" not in gp_txt

    xl_fname, xl_raw, xl_mime = auto_multi_service.get_job_artifact(job_id, sid, "excel")
    assert "openxmlformats" in xl_mime
    wb = openpyxl.load_workbook(io.BytesIO(xl_raw))
    assert wb.sheetnames == ["District Level", "Mandal Level", "GP Level Summary", "Day-Wise Exact Time", "Master Data"]


def test_auto_multi_dsr_fastapi_endpoints_and_security(monkeypatch):
    """Verify /api/auto-multi-dsr/* authentication, validation, session isolation, and UI elements."""
    ts = int(time.time() * 1000)
    c = TestClient(app)
    _console_login(c, monkeypatch, f"api_{ts}")

    from dsr import service as automation_service
    sid = f"sid_auto_dsr_api_{ts}"
    sess = automation_service.get_or_create_session(sid)
    sess["authenticated"] = True
    sess["status"] = "authenticated"
    sess["user_id"] = "DPOA3698"
    sess["district_name"] = "Khammam"

    hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}

    # 1. Preview dates endpoint
    prev = c.post(
        "/api/auto-multi-dsr/preview-dates",
        headers=hdrs,
        json={"start_date": "2026-11-06", "end_date": "2026-11-15", "public_holidays": ["2026-11-10"]},
    )
    assert prev.status_code == 200
    pdata = prev.json()
    assert pdata["success"] is True
    assert pdata["date_analysis"]["total_calendar_days"] == 10
    assert pdata["date_analysis"]["excluded_sundays_count"] == 2
    assert pdata["date_analysis"]["excluded_second_saturdays_count"] == 1
    assert pdata["date_analysis"]["excluded_public_holidays_count"] == 1
    assert pdata["date_analysis"]["working_days_count"] == 6

    # Missing dates returns 400
    assert c.post("/api/auto-multi-dsr/preview-dates", headers=hdrs, json={"start_date": ""}).status_code == 400

    # 2. Unauthenticated client blocked from starting job (401)
    unauth = c.post("/api/auto-multi-dsr/start-job", headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": "unauth_sid"}, json={"start_date": "2026-11-09", "end_date": "2026-11-10"})
    assert unauth.status_code == 401

    # 3. Main dashboard HTML contains the new Automated Multi-Days DSR card and station
    main_page = c.get("/", headers={"Host": "reports.panchayatautomation.in"})
    assert main_page.status_code == 200
    assert 'id="card-console-auto-multi-dsr"' in main_page.text
    assert 'id="auto-multi-dsr-station"' in main_page.text
    assert 'id="btn-run-auto-multi-robot"' in main_page.text
    assert 'id="btn-auto-multi-dl-full-pdf"' in main_page.text
    assert 'id="btn-auto-multi-dl-dist-pdf"' in main_page.text
    assert 'id="btn-auto-multi-dl-mandal-pdf"' in main_page.text
    assert 'id="btn-auto-multi-dl-gp-pdf"' in main_page.text
    assert 'id="btn-auto-multi-dl-time-pdf"' in main_page.text
    assert 'openAutoMultiDsrStation' in main_page.text

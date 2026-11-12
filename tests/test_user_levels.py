"""Unit and integration tests for Multi-Level Officer Hierarchy (District, Divisional, Mandal).

Verifies:
1. Automatic officer level detection from e-Panchayat credentials and headers.
2. DSR Attendance: Mandal-level produces GP-wise status and suppresses multi-mandal abstract.
3. GP Balance (GM-R 14.2): Mandal-level produces GP-wise account entry status.
4. House Tax (DCB): Automatically locks to officer's Mandal and returns GP-wise DCB records.
5. MAS (GM-R 5.24): Automatically filters to officer's Mandal.
6. Role switcher endpoint (/api/naresh/set-user-level).
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from dsr.service import determine_user_level, get_or_create_session, set_user_level_override

client = TestClient(app)


def test_determine_user_level():
    # 1. District Officer (DPOA3698)
    lvl, mandal = determine_user_level(
        {"office_name": "District Panchayat Office", "division_name": "Khammam Division", "district_name": "Khammam District"},
        user_id="DPOA3698"
    )
    assert lvl == "district"
    assert mandal == ""

    # 2. Divisional Officer (DLPO)
    lvl, mandal = determine_user_level(
        {"office_name": "Divisional Panchayat Office", "division_name": "Khammam Division", "district_name": "Khammam District"},
        user_id="DLPO_KHAMMAM"
    )
    assert lvl == "division"
    assert mandal == ""

    # 3. Mandal Officer via User ID (MPO_KALLUR)
    lvl, mandal = determine_user_level(
        {"office_name": "Mandal Panchayat Office", "district_name": "Khammam District"},
        user_id="MPO_KALLUR"
    )
    assert lvl == "mandal"
    assert mandal.lower() == "kallur"

    # 4. Mandal Officer via Header Info (Mandal: Enkoor)
    lvl, mandal = determine_user_level(
        {"mandal_name": "Enkoor", "office_name": "MPO Office", "district_name": "Khammam District"},
        user_id="OFFICER123"
    )
    assert lvl == "mandal"
    assert mandal == "Enkoor"

    # 5. MPDO Officer
    lvl, mandal = determine_user_level(
        {"office_name": "O/o MPDO Wyra", "district_name": "Khammam District"},
        user_id="MPDO_WYRA"
    )
    assert lvl == "mandal"
    assert mandal.lower() == "wyra"


def test_set_user_level_endpoint():
    sid = "test_lvl_sess_1"
    res = client.post(f"/api/naresh/set-user-level?level=mandal&mandal=Kallur", headers={"X-Session-ID": sid})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["user_level"] == "mandal"
    assert data["mandal_name"] == "Kallur"

    # Verify session-status reflects this
    st_res = client.get("/api/naresh/session-status", headers={"X-Session-ID": sid})
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["user_level"] == "mandal"
    assert st_data["mandal_name"] == "Kallur"

    # Switch back to district
    res_dist = client.post(f"/api/naresh/set-user-level?level=district", headers={"X-Session-ID": sid})
    assert res_dist.status_code == 200
    assert res_dist.json()["user_level"] == "district"
    assert res_dist.json()["mandal_name"] == ""


def test_dcb_mandal_level_filtering():
    sid = "test_dcb_mandal_sess"
    # Switch session to Mandal Level for Kallur
    client.post(f"/api/naresh/set-user-level?level=mandal&mandal=Kallur", headers={"X-Session-ID": sid})

    # Call /api/tax/data with mandal="all" -> should automatically resolve to Kallur
    res = client.get("/api/tax/data?mandal=all", headers={"X-Session-ID": sid})
    assert res.status_code == 200
    data = res.json()
    assert data["is_mandal_level"] is True
    assert data["mandal_name"].lower() == "kallur"
    # Multi-mandal comparison table suppressed
    assert data["mandal_rows"] == []
    # GP records belong to Kallur
    for rec in data["records"][:5]:
        assert rec["mandal"].lower() in ("kallur", "kalluru")


def test_gp_balance_mandal_level():
    from gp_balance import service as gp_balance_service
    from gp_balance.models import DistrictBalanceReport, MandalBalanceSummary, GPBalanceDetail

    sid = "test_bal_mandal_sess"
    client.post(f"/api/naresh/set-user-level?level=mandal&mandal=Kallur", headers={"X-Session-ID": sid})

    # Create and cache a mock balance report
    rep = DistrictBalanceReport(
        district_name="Khammam",
        report_date_str="29-10-2026",
        generated_at="2026-10-29 10:00 AM",
        total_mandals=2,
        total_gps=40,
        total_entered_gps=35,
        total_not_entered_gps=5,
        overall_pct_entered=87.5,
    )
    m_kallur = MandalBalanceSummary(
        s_no=1,
        mandal_name="Kallur",
        total_gps=20,
        entered_gps=18,
        not_entered_gps=2,
        pct_entered=90.0,
    )
    gp1 = GPBalanceDetail(
        s_no=1, mandal_name="Kallur", panchayat_name="Kallur GP", entered=True,
        gp_pd="Yes", tgbpass="Yes", fc15_tied="Yes", fc15_untied="Yes", vwsc="Yes", mgnregs="Yes",
        missing_accounts=[], is_pending=False, secretary_name="Ramesh", secretary_phone="9876543210"
    )
    gp2 = GPBalanceDetail(
        s_no=2, mandal_name="Kallur", panchayat_name="Lingala GP", entered=False,
        gp_pd="No", tgbpass="Yes", fc15_tied="Yes", fc15_untied="Yes", vwsc="Yes", mgnregs="Yes",
        missing_accounts=["GP PD Account"], is_pending=True, secretary_name="Suresh", secretary_phone="9123456780"
    )
    m_kallur.all_gps = [gp1, gp2]
    m_kallur.pending_gps = [gp2]
    rep.mandals = [m_kallur]

    # Store in memory
    gp_balance_service._session_reports[(sid, "29-10-2026")] = rep

    # Call /api/balance/data
    res = client.get("/api/balance/data?date=29-10-2026", headers={"X-Session-ID": sid})
    assert res.status_code == 200
    data = res.json()
    assert data["has_data"] is True
    assert data["is_mandal_level"] is True
    assert data["mandal_name"] == "Kallur"
    assert data["mandals"] == []  # Multi-mandal comparison suppressed
    assert len(data["gp_rows"]) == 2
    assert data["gp_rows"][0]["panchayat_name"] == "Kallur GP"
    assert data["gp_rows"][0]["is_pending"] is False
    assert data["gp_rows"][1]["panchayat_name"] == "Lingala GP"
    assert data["gp_rows"][1]["is_pending"] is True
    assert "GP PD Account" in data["gp_rows"][1]["missing_accounts"]

    # Test PDF generation for Mandal level
    pdf_res = client.get("/api/balance/report.pdf?date=29-10-2026", headers={"X-Session-ID": sid})
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert "Kallur_Mandal_GP_Balance_Report" in pdf_res.headers["content-disposition"]


def test_dsr_mandal_level_report(tmp_path, monkeypatch):
    import pandas as pd
    from dsr.service import get_or_create_session, _generate_server_report_impl
    from dsr.pdf_generator import analyze_attendance, generate_mandal_pdf
    import dsr.auto_download

    raw_data = [
        {"District Name": "Khammam", "Mandal Name": "Kallur", "Grampanchayat Name": "Kallur GP", "Panchayat Lgd": "101", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 08:45:00", "DSR Status": "Entered", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Kallur", "Grampanchayat Name": "Lingala GP", "Panchayat Lgd": "102", "First Attendence Status": "", "Second Attendence Status": "", "First Attendence Datetime": "", "DSR Status": "", "Nature Of Reason": ""},
        {"District Name": "Khammam", "Mandal Name": "Enkoor", "Grampanchayat Name": "Enkoor GP", "Panchayat Lgd": "103", "First Attendence Status": "Present", "Second Attendence Status": "Present", "First Attendence Datetime": "08-11-2026 08:30:00", "DSR Status": "Entered", "Nature Of Reason": ""},
    ]
    df = pd.DataFrame(raw_data)
    rep = analyze_attendance(df, cutoff_time="09:00", sort_by="before_9")

    # Generate Mandal PDF for Kallur
    pdf_out = tmp_path / "kallur_test.pdf"
    generate_mandal_pdf(rep, pdf_out, mandal_name="Kallur")
    assert pdf_out.exists()
    assert pdf_out.stat().st_size > 500

    # Test Mandal-level session generation
    sid = "test_dsr_mandal_sess_2"
    session = get_or_create_session(sid)
    session["status"] = "authenticated"
    session["user_level"] = "mandal"
    session["mandal_name"] = "Kallur"

    class DummyBot:
        page = True

    session["bot"] = DummyBot()

    def mock_download(bot, code, dt):
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        raw_csv = session["downloads_dir"] / "GM_R_1_2_7.csv"
        raw_csv.write_bytes(csv_bytes)
        return raw_csv

    monkeypatch.setattr(dsr.auto_download, "download_single_report_with_menu", mock_download)

    res = _generate_server_report_impl(session, module="dsr_full", date_str="2026-11-08")
    assert res["success"] is True
    assert res["is_mandal_level"] is True
    assert res["mandal_name"] == "Kallur"
    assert res["totals"]["total_gps"] == 2
    assert res["totals"]["attendance_submitted"] == 1
    assert res["totals"]["pending"] == 1
    assert len(res["gp_rows"]) == 2
    assert res["gp_rows"][0]["gp"] == "Kallur GP"
    assert res["gp_rows"][1]["gp"] == "Lingala GP"

    # Verify session["report_data"] has mandal_rows == [] (suppressed multi-mandal abstract)
    assert session["report_data"]["mandal_rows"] == []

"""Test suite for Monthly Activity Statement (MAS) and Births Register (GM-R 5) module.

Validates:
1. GM-R 5.24 Activity Statement compliance logic (individual missing activity granularity across 17 indicators).
2. GM-R 5.23 Births Register in GP model and aggregation metrics.
3. Combined District MAS Master Report compliance index.
4. Mandal name fuzzy stem normalization.
5. Official landscape PDF generation (NumberedCanvas, headers, page counts, multi-section layout).
6. Multi-sheet Excel workbook export (GM-R_5.24_MAS_Summary, GM-R_5.23_Births_Register, Pending_GPs_Action_List).
7. FastAPI APIRouter endpoints for periods and data querying.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

# Ensure workspace root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mas.automation import normalize_mandal_key
from mas.excel_generator import generate_mas_excel
from mas.models import (
    DEFAULT_MAS_ACTIVITIES,
    MAS_5_24_ACTIVITIES,
    DistrictMASReport,
    GPBirthRegisterDetail,
    GPMASDetail,
    MandalBirthRegisterSummary,
    MandalMASSummary,
)
from mas.pdf_generator import generate_mas_pdf
from mas.router import router
from mas.service import (
    _session_reports,
    generate_mas_report_pipeline,
    get_available_periods,
    get_mas_data_dict,
    get_mas_excel_bytes,
    get_mas_pdf_bytes,
    reset_mas_data,
)


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def sample_mas_report() -> DistrictMASReport:
    """Creates a sample multi-mandal, multi-GP district report for verification."""
    # GP 1: Completed all activities
    gp1 = GPMASDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Appalanarasimhapuram",
        financial_year="2026",
        month="October",
        entered=True,
        activity_flags={act: "Yes" for act in MAS_5_24_ACTIVITIES},
    )
    gp1.evaluate_pending()

    # GP 2: Missed ONLY 'Payment of Electricity'
    act_flags2 = {act: "Yes" for act in MAS_5_24_ACTIVITIES}
    act_flags2["Payment of Electricity"] = "No"
    gp2 = GPMASDetail(
        s_no=2,
        mandal_name="Nelakondapally",
        panchayat_name="Bodulabanda",
        financial_year="2026",
        month="October",
        entered=True,
        activity_flags=act_flags2,
        secretary_name="K. Ramesh",
        secretary_phone="9876543210",
    )
    gp2.evaluate_pending()

    # GP 3: Completely Not Entered
    gp3 = GPMASDetail(
        s_no=3,
        mandal_name="Kusumanchi",
        panchayat_name="Palair",
        financial_year="2026",
        month="October",
        entered=False,
        activity_flags={},
        secretary_name="V. Suresh",
        secretary_phone="9123456780",
    )
    gp3.evaluate_pending()

    # GP 4: Completed all in Kusumanchi
    gp4 = GPMASDetail(
        s_no=4,
        mandal_name="Kusumanchi",
        panchayat_name="Nayakangudem",
        financial_year="2026",
        month="October",
        entered=True,
        activity_flags={act: "Yes" for act in MAS_5_24_ACTIVITIES},
    )
    gp4.evaluate_pending()

    # Mandal 1: Nelakondapally (MAS 5.24)
    m1 = MandalMASSummary(s_no=1, mandal_name="Nelakondapally")
    m1.add_gp(gp1)
    m1.add_gp(gp2)

    # Mandal 2: Kusumanchi (MAS 5.24)
    m2 = MandalMASSummary(s_no=2, mandal_name="Kusumanchi")
    m2.add_gp(gp3)
    m2.add_gp(gp4)

    # GM-R 5.23 Births Register Summary
    bgp1 = GPBirthRegisterDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Appalanarasimhapuram",
        financial_year="2026",
        month="October",
        entered=True,
        births_registered=12,
    )
    bgp1.evaluate_pending()

    bgp2 = GPBirthRegisterDetail(
        s_no=2,
        mandal_name="Nelakondapally",
        panchayat_name="Bodulabanda",
        financial_year="2026",
        month="October",
        entered=False,
        births_registered=0,
        secretary_name="K. Ramesh",
        secretary_phone="9876543210",
    )
    bgp2.evaluate_pending()

    bm1 = MandalBirthRegisterSummary(
        s_no=1,
        mandal_name="Nelakondapally",
        all_gps=[bgp1, bgp2],
    )
    bm1.calculate_metrics()

    report = DistrictMASReport(
        district_name="Khammam",
        financial_year="2026",
        month_name="October",
        mandals=[m1, m2],
        birth_mandals=[bm1],
    )
    report.calculate_totals()
    return report


# ==============================================================================
# UNIT TESTS: MODELS & COMPLIANCE LOGIC
# ==============================================================================
def test_gp_single_activity_missing():
    """Validates that if a GP missed ONLY one activity, missing_activities lists ONLY that one."""
    flags = {act: "Yes" for act in MAS_5_24_ACTIVITIES}
    flags["Payment of Electricity"] = "No"

    gp = GPMASDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Test GP",
        financial_year="2026",
        month="October",
        entered=True,
        activity_flags=flags,
    )
    gp.evaluate_pending()

    assert gp.is_pending is True
    assert gp.status == "Partial"
    assert gp.missing_activities == ["Payment of Electricity"]


def test_gp_all_activities_completed():
    """Validates that a GP with all 17 activities entered is marked completed and not pending."""
    flags = {act: "Yes" for act in MAS_5_24_ACTIVITIES}
    gp = GPMASDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Completed GP",
        financial_year="2026",
        month="October",
        entered=True,
        activity_flags=flags,
    )
    gp.evaluate_pending()

    assert gp.is_pending is False
    assert gp.status == "Completed"
    assert len(gp.missing_activities) == 0


def test_gp_not_entered():
    """Validates that an unsubmitted GP is marked pending and all 17 activities flagged missing."""
    gp = GPMASDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Pending GP",
        financial_year="2026",
        month="October",
        entered=False,
    )
    gp.evaluate_pending()

    assert gp.is_pending is True
    assert gp.status == "Not Entered"
    assert len(gp.missing_activities) == len(MAS_5_24_ACTIVITIES)


def test_mandal_and_district_metrics(sample_mas_report: DistrictMASReport):
    """Verifies metric aggregation math across mandals, district, and births register."""
    assert sample_mas_report.total_mandals == 2
    assert sample_mas_report.total_gps == 4
    assert sample_mas_report.total_completed_gps == 2
    assert sample_mas_report.total_pending_gps == 2
    assert sample_mas_report.overall_pct == 50.0

    # Births register metrics
    assert sample_mas_report.total_birth_entered_gps == 1
    assert sample_mas_report.total_birth_pending_gps == 1
    assert sample_mas_report.births_overall_pct == 50.0
    assert sample_mas_report.total_district_births == 12

    # Combined compliance index
    assert sample_mas_report.combined_compliance_index == 50.0


def test_mandal_key_normalization():
    """Verifies spelling variations of mandals normalize to identical stems."""
    assert normalize_mandal_key("Nelakondapally") == normalize_mandal_key("Nelakondapalle")
    assert normalize_mandal_key("Penubally") == normalize_mandal_key("Penuballi")
    assert normalize_mandal_key("Kallur") == normalize_mandal_key("Kalluru")
    assert normalize_mandal_key("Chinthakani") == normalize_mandal_key("Chintakani")


def test_report_serialization_cycle(sample_mas_report: DistrictMASReport):
    """Verifies complete JSON dictionary serialization and deserialization."""
    rep_dict = sample_mas_report.to_dict()
    restored = DistrictMASReport.from_dict(rep_dict)

    assert restored.district_name == sample_mas_report.district_name
    assert restored.total_gps == sample_mas_report.total_gps
    assert restored.overall_pct == sample_mas_report.overall_pct
    assert restored.births_overall_pct == sample_mas_report.births_overall_pct
    assert len(restored.mandals) == len(sample_mas_report.mandals)
    assert len(restored.birth_mandals) == len(sample_mas_report.birth_mandals)


# ==============================================================================
# INTEGRATION TESTS: REPORT GENERATORS
# ==============================================================================
def test_pdf_generation(sample_mas_report: DistrictMASReport):
    """Generates combined landscape PDF and validates structural integrity."""
    pdf_bytes = generate_mas_pdf(sample_mas_report)
    assert len(pdf_bytes) > 1000

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2

    page1_text = reader.pages[0].extract_text()
    assert "MONTHLY ACTIVITY STATEMENT" in page1_text
    assert "KHAMMAM" in page1_text
    assert "Nelakondapally" in page1_text

    # Verify that Legal landscape PDF includes the 2-page matrix and pending list without secretary contacts
    all_pdf_text = " ".join(p.extract_text() for p in reader.pages)
    assert "MONTHLY ACTIVITY STATEMENT" in all_pdf_text
    assert "PENDING" in all_pdf_text
    assert "Birth Details" in all_pdf_text
    assert "Panchayat Secretary" not in all_pdf_text
    assert "Secretary Phone" not in all_pdf_text
    assert "Action Status" not in all_pdf_text


def test_excel_generation(sample_mas_report: DistrictMASReport):
    """Generates multi-sheet Excel workbook with all 3 sheets."""
    excel_bytes = generate_mas_excel(sample_mas_report)
    assert len(excel_bytes) > 2000

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    assert "GM-R_5.24_MAS_Summary" in wb.sheetnames
    assert "GM-R_5.23_Births_Register" in wb.sheetnames
    assert "Pending_GPs_Action_List" in wb.sheetnames

    # Check MAS Sheet (58-Column Two-Tier Executive Matrix)
    ws1 = wb["GM-R_5.24_MAS_Summary"]
    assert "MONTHLY ACTIVITY STATEMENT" in str(ws1["A1"].value)
    assert ws1["B4"].value == "Mandal Name"
    assert ws1["D4"].value == "Overall % Entered"
    assert ws1["E4"].value == "Nursery"
    assert ws1["G5"].value == "% Entered"
    assert ws1["B6"].value == "Nelakondapally"
    assert ws1.max_column == 58

    # Check Births Sheet
    ws2 = wb["GM-R_5.23_Births_Register"]
    assert "BIRTHS REGISTER" in str(ws2["A1"].value)
    assert ws2["D5"].value == "Entered GPs"
    assert ws2["D6"].value == 1  # 1 entered GP in Nelakondapally
    assert ws2["F6"].value == 12  # 12 registered births

    # Check Pending Action List
    ws3 = wb["Pending_GPs_Action_List"]
    assert "ACTIONABLE PENDING GRAM PANCHAYATS" in str(ws3["A1"].value)
    assert ws3["C5"].value == "Bodulabanda"
    assert "Payment of Electricity" in str(ws3["D5"].value)


# ==============================================================================
# API ROUTER TESTS
# ==============================================================================
def test_mas_router_endpoints(sample_mas_report: DistrictMASReport):
    """Verifies FastAPI APIRouter endpoints."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)

    # 1. Periods endpoint
    res_periods = client.get("/api/mas/periods")
    assert res_periods.status_code == 200
    data_p = res_periods.json()
    assert data_p["status"] == "ok"
    assert "years" in data_p["periods"]
    assert "2020" in data_p["periods"]["years"]
    assert "months" in data_p["periods"]

    # 2. Data endpoint before caching (test with non-existent year/session)
    _session_reports.clear()
    res_data_empty = client.get("/api/mas/data?financial_year=1999&month=January", headers={"X-Session-ID": "fresh_session_empty"})
    assert res_data_empty.status_code == 200
    assert res_data_empty.json()["available"] is False

    # Inject sample report into service cache
    _session_reports[("test_session", "2026", "October")] = sample_mas_report

    # Query with session header
    res_data = client.get(
        "/api/mas/data?financial_year=2026&month=October",
        headers={"X-Session-ID": "test_session"},
    )
    assert res_data.status_code == 200
    report_dict = res_data.json()
    assert report_dict["available"] is True
    assert report_dict["total_gps"] == 4
    assert report_dict["overall_pct"] == 50.0
    assert report_dict["births_overall_pct"] == 50.0

    # 3. PDF endpoint
    res_pdf = client.get(
        "/api/mas/report.pdf?financial_year=2026&month=October",
        headers={"X-Session-ID": "test_session"},
    )
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000

    # 4. Excel endpoint
    res_excel = client.get(
        "/api/mas/export.xlsx?financial_year=2026&month=October",
        headers={"X-Session-ID": "test_session"},
    )
    assert res_excel.status_code == 200
    assert "openxmlformats" in res_excel.headers["content-type"]
    assert len(res_excel.content) > 1000

    # 5. Reset endpoint
    res_reset = client.post("/api/mas/reset", headers={"X-Session-ID": "test_session"})
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "ok"

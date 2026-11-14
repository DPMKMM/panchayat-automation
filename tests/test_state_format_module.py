"""
Unit and Integration Tests for State Format DSR Report Module (DSR_State_Format).
"""

from __future__ import annotations

import io
import os
import sys
from datetime import date, datetime
from pathlib import Path

os.environ["ENVIRONMENT"] = "development"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = ""

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import pandas as pd
from fastapi.testclient import TestClient
import openpyxl
from pypdf import PdfReader

from DSR_State_Format.consolidation.lookup_builder import (
    clean_lgd,
    clean_name,
    clean_mobile,
    is_regular_ps,
    build_secretary_lookup,
)
from DSR_State_Format.processing.data_enricher import (
    enrich_raw_data,
    parse_timestamp,
    standardize_status,
)
from DSR_State_Format.calculations.aggregator import (
    compute_mandal_metrics,
    StateFormatReport,
)
from DSR_State_Format.report_generation.pdf_generator import generate_state_format_pdf
from DSR_State_Format.report_generation.excel_generator import generate_state_format_excel
from DSR_State_Format import service as state_format_service
from dsr.service import get_or_create_session
from app import app

client = TestClient(app)


def _make_sample_directory_html(rows: list[dict[str, str]]) -> bytes:
    cols = [
        "S.No",
        "District Name",
        "Mandal Name",
        "Panchayat Name",
        "Panchayat LGD Code",
        "Panchayat Secretary Employee Id",
        "Panchayat Secretary Name",
        "Designation",
        "Nature of Posting",
        "Mobile Number",
    ]
    trs = []
    for r in rows:
        tds = "".join(f"<td>{r.get(c, '')}</td>" for c in cols)
        trs.append(f"<tr>{tds}</tr>")
    html = f"<table><thead><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    return html.encode("utf-8")


def _make_sample_raw_html(rows: list[dict[str, str]]) -> bytes:
    cols = [
        "District Name",
        "Mandal Name",
        "Panchayat Name",
        "Panchayat LGD",
        "First Attendence Status",
        "First Attendence Datetime",
        "Second Attendence Status",
        "Second Attendence Datetime",
        "DSR Entry Status",
        "DSR Submited Datetime",
    ]
    trs = []
    for r in rows:
        tds = "".join(f"<td>{r.get(c, '')}</td>" for c in cols)
        trs.append(f"<tr>{tds}</tr>")
    html = f"<table><thead><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    return html.encode("utf-8")


def test_lookup_builder_helpers():
    assert clean_lgd("207869") == "207869"
    assert clean_lgd(207869) == "207869"
    assert clean_lgd("  207869.0  ") == "207869"
    assert clean_lgd("") == ""

    assert is_regular_ps("Regular") is True
    assert is_regular_ps("REGULAR") is True
    assert is_regular_ps("Incharge") is False
    assert is_regular_ps("Full Additional Charge") is False
    assert is_regular_ps("Contract") is False
    assert is_regular_ps("") is False


def test_build_secretary_lookup():
    pres_rows = [
        {
            "Panchayat LGD Code": "1001",
            "Panchayat Secretary Name": "Ramesh Kumar",
            "Nature of Posting": "Regular",
            "Mobile Number": "9876543210",
        },
        {
            "Panchayat LGD Code": "1002",
            "Panchayat Secretary Name": "Suresh (FAC)",
            "Nature of Posting": "Incharge",
            "Mobile Number": "9876543211",
        },
    ]
    abs_rows = [
        {
            "Panchayat LGD Code": "1003",
            "Panchayat Secretary Name": "Naresh",
            "Nature of Posting": "Regular",
            "Mobile Number": "9876543212",
        }
    ]
    pres_bytes = _make_sample_directory_html(pres_rows)
    abs_bytes = _make_sample_directory_html(abs_rows)

    lookup = build_secretary_lookup(pres_bytes, "", abs_bytes, "")
    assert len(lookup) == 3
    assert lookup["1001"]["is_regular"] is True
    assert lookup["1001"]["ps_name"] == "Ramesh Kumar"
    assert lookup["1002"]["is_regular"] is False
    assert lookup["1003"]["is_regular"] is True


def test_timestamp_parsing():
    dt1 = parse_timestamp("12-Nov-2026 08:30:00")
    assert dt1 is not None
    assert dt1.hour == 8
    assert dt1.minute == 30

    dt2 = parse_timestamp("2026-11-12 14:15")
    assert dt2 is not None
    assert dt2.hour == 14
    assert dt2.minute == 15

    assert parse_timestamp("") is None
    assert parse_timestamp("-") is None


def test_standardize_status():
    assert standardize_status("Present") == "Present"
    assert standardize_status("Leave") == "Leave"
    assert standardize_status("On Leave") == "Leave"
    assert standardize_status("Meeting") == "Meeting"
    assert standardize_status("Training") == "Meeting"
    assert standardize_status("Absent") == "Not Reported"
    assert standardize_status("") == "Not Reported"


def test_compute_mandal_metrics_aggregation():
    # Setup test raw data across 2 Mandals
    # Mandal A: 2 Regular PS (1 reported 7 AM, 1 reported 9:30 AM), 1 Incharge PS (excluded from full_time)
    # Mandal B: 2 Regular PS (both reported 8 AM)
    lookup = {
        "101": {"lgd_code": "101", "emp_id": "EMP1", "ps_name": "Sec 1", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000001"},
        "102": {"lgd_code": "102", "emp_id": "EMP2", "ps_name": "Sec 2", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000002"},
        "103": {"lgd_code": "103", "emp_id": "EMP3", "ps_name": "Sec 3", "designation": "PS", "nature_of_posting": "Incharge", "is_regular": False, "mobile": "9000000003"},
        "201": {"lgd_code": "201", "emp_id": "EMP4", "ps_name": "Sec 4", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000004"},
        "202": {"lgd_code": "202", "emp_id": "EMP5", "ps_name": "Sec 5", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000005"},
    }

    raw_rows = [
        # Mandal A
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP A1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 07:15:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP A2",
            "Panchayat LGD": "102",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 09:30:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP A3",
            "Panchayat LGD": "103",  # Incharge
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 07:00:00",
        },
        # Mandal B
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal B",
            "Panchayat Name": "GP B1",
            "Panchayat LGD": "201",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 08:15:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal B",
            "Panchayat Name": "GP B2",
            "Panchayat LGD": "202",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 08:45:00",
        },
    ]

    raw_df = pd.DataFrame(raw_rows)
    enriched_df = enrich_raw_data(raw_df, lookup)
    report = compute_mandal_metrics(
        enriched_df,
        district_name="Khammam",
        report_date=date(2026, 11, 12),
        generated_at=datetime(2026, 11, 12, 19, 0),
    )

    assert report.district_name == "Khammam"
    assert len(report.mandal_rows) == 2

    # Mandal B should be ranked #1 because 2/2 = 100% reported before 9 AM
    assert report.mandal_rows[0]["mandal_name"] == "Mandal B"
    assert report.mandal_rows[0]["sl_no"] == 1
    assert report.mandal_rows[0]["tot_gps"] == 2
    assert report.mandal_rows[0]["full_time"] == 2
    assert report.mandal_rows[0]["b_6_9"] == 2
    assert report.mandal_rows[0]["pct_before_9"] == 100.0

    # Mandal A should be ranked #2 because 1/2 = 50% reported before 9 AM (Incharge excluded from full_time)
    assert report.mandal_rows[1]["mandal_name"] == "Mandal A"
    assert report.mandal_rows[1]["sl_no"] == 2
    assert report.mandal_rows[1]["tot_gps"] == 3
    assert report.mandal_rows[1]["full_time"] == 2
    assert report.mandal_rows[1]["b_6_9"] == 1
    assert report.mandal_rows[1]["b_9_10"] == 1
    assert report.mandal_rows[1]["pct_before_9"] == 50.0

    # District Totals
    assert report.total_row["tot_gps"] == 5
    assert report.total_row["full_time"] == 4
    assert report.total_row["b_6_9"] == 3
    assert report.total_row["b_9_10"] == 1
    assert report.total_row["attended_gp"] == 4

    # District Percentages (3/4 = 75.0%)
    assert report.total_row["pct_before_9"] == 75.0
    assert report.percentage_row["b_6_9"] == 75.0
    assert report.percentage_row["b_9_10"] == 25.0


def test_pdf_generation(tmp_path):
    lookup = {
        "101": {"lgd_code": "101", "emp_id": "EMP1", "ps_name": "Sec 1", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000001"},
    }
    raw_rows = [
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 08:30:00",
        }
    ]
    raw_df = pd.DataFrame(raw_rows)
    enriched_df = enrich_raw_data(raw_df, lookup)
    report = compute_mandal_metrics(
        enriched_df,
        district_name="Khammam",
        report_date=date(2026, 11, 12),
        generated_at=datetime(2026, 11, 12, 19, 0),
    )

    pdf_out = tmp_path / "test_report.pdf"
    res_path = generate_state_format_pdf(report, pdf_out)
    assert res_path.exists()
    assert res_path.stat().st_size > 0

    reader = PdfReader(str(res_path))
    assert len(reader.pages) == 1
    page = reader.pages[0]
    # Landscape orientation check: width > height
    assert page.mediabox.width > page.mediabox.height


def test_excel_generation(tmp_path):
    lookup = {
        "101": {"lgd_code": "101", "emp_id": "EMP1", "ps_name": "Sec 1", "designation": "PS", "nature_of_posting": "Regular", "is_regular": True, "mobile": "9000000001"},
    }
    raw_rows = [
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 08:30:00",
        }
    ]
    raw_df = pd.DataFrame(raw_rows)
    enriched_df = enrich_raw_data(raw_df, lookup)
    report = compute_mandal_metrics(
        enriched_df,
        district_name="Khammam",
        report_date=date(2026, 11, 12),
        generated_at=datetime(2026, 11, 12, 19, 0),
    )

    excel_out = tmp_path / "test_report.xlsx"
    res_path = generate_state_format_excel(report, excel_out)
    assert res_path.exists()

    wb = openpyxl.load_workbook(str(res_path))
    ws = wb.active
    assert ws.title == "PS Attendance State Format"
    assert ws.max_column == 14
    wb.close()


def test_process_and_generate_reports_service():
    session = get_or_create_session("test_session_sf_1")
    lookup_rows = [
        {
            "Panchayat LGD Code": "101",
            "Panchayat Secretary Name": "Sec 1",
            "Nature of Posting": "Regular",
            "Mobile Number": "9000000001",
        }
    ]
    raw_rows = [
        {
            "District Name": "Khammam",
            "Mandal Name": "Khammam Urban",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 07:30:00",
        }
    ]
    raw_bytes = _make_sample_raw_html(raw_rows)
    pres_bytes = _make_sample_directory_html(lookup_rows)

    res = state_format_service.process_and_generate_reports(
        raw_bytes=raw_bytes,
        raw_filename="Khammam_AttendenceStatusandDSRRawdata_12-Nov-2026.xls",
        presentees_bytes=pres_bytes,
        presentees_filename="presentees.xls",
        session=session,
    )

    assert res["success"] is True
    assert res["district"] == "Khammam"
    assert res["pdf_url"] == "/api/state-format/download-pdf"
    assert res["excel_url"] == "/api/state-format/download-excel"
    assert "state_format_pdf" in session
    assert "state_format_excel" in session
    assert Path(session["state_format_pdf"]).exists()
    assert Path(session["state_format_excel"]).exists()


def test_api_download_endpoints():
    session_id = "test_api_sf_sess"
    session = get_or_create_session(session_id)

    # Empty session should return 404
    resp_empty = client.get(
        "/api/state-format/download-pdf",
        headers={"X-Session-ID": session_id},
    )
    assert resp_empty.status_code == 404

    # Populate files via process_and_generate_reports
    raw_rows = [
        {
            "District Name": "Khammam",
            "Mandal Name": "Khammam Urban",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 07:30:00",
        }
    ]
    raw_bytes = _make_sample_raw_html(raw_rows)
    state_format_service.process_and_generate_reports(
        raw_bytes=raw_bytes,
        raw_filename="Khammam_AttendenceStatusandDSRRawdata_12-Nov-2026.xls",
        session=session,
    )

    # PDF download should return 200 with application/pdf
    resp_pdf = client.get(
        "/api/state-format/download-pdf",
        headers={"X-Session-ID": session_id},
    )
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF")

    # Excel download should return 200 with spreadsheet media type
    resp_excel = client.get(
        "/api/state-format/download-excel",
        headers={"X-Session-ID": session_id},
    )
    assert resp_excel.status_code == 200
    assert "spreadsheetml" in resp_excel.headers["content-type"]


def test_api_manual_upload():
    session_id = "test_upload_sf_sess"
    session = get_or_create_session(session_id)

    raw_rows = [
        {
            "District Name": "Khammam",
            "Mandal Name": "Khammam Urban",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "12-Nov-2026 07:30:00",
        }
    ]
    raw_bytes = _make_sample_raw_html(raw_rows)

    files = {
        "file": ("Khammam_AttendenceStatusandDSRRawdata_12-Nov-2026.xls", raw_bytes, "application/vnd.ms-excel"),
    }
    resp = client.post(
        "/api/state-format/upload",
        files=files,
        headers={"X-Session-ID": session_id},
    )
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert json_data["district"] == "Khammam"


def test_nat_type_safety_handling():
    """Verify that pd.NaT in datetime columns never raises 'NaTType does not support time'."""
    raw_df = pd.DataFrame([
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP 1",
            "Panchayat LGD": "101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": pd.Timestamp("2026-11-12 08:15:00"),
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP 2",
            "Panchayat LGD": "102",
            "First Attendence Status": "Leave",
            "First Attendence Datetime": pd.NaT,
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Mandal A",
            "Panchayat Name": "GP 3",
            "Panchayat LGD": "103",
            "First Attendence Status": "Not Reported",
            "First Attendence Datetime": None,
        },
    ])
    lookup = {
        "101": {"lgd_code": "101", "is_regular": True, "ps_name": "Sec 1"},
        "102": {"lgd_code": "102", "is_regular": True, "ps_name": "Sec 2"},
        "103": {"lgd_code": "103", "is_regular": True, "ps_name": "Sec 3"},
    }

    # Must complete without 'NaTType does not support time'
    enriched = enrich_raw_data(raw_df, lookup)
    assert len(enriched) == 3
    assert enriched.iloc[0]["reporting_time"] is not None
    assert enriched.iloc[1]["reporting_time"] is None
    assert enriched.iloc[2]["reporting_time"] is None

    report = compute_mandal_metrics(
        enriched,
        district_name="Khammam",
        report_date=date(2026, 11, 12),
        generated_at=datetime(2026, 11, 12, 19, 0),
    )
    assert len(report.mandal_rows) == 1
    assert report.total_row["full_time"] == 3
    assert report.total_row["b_6_9"] == 2  # Sec 1 (8:15 AM) + Sec 2 (Leave with unparsed/NaT time defaults to 6-9 AM)


def test_real_world_06_nov_dataset():
    """Verify processing of real-world 06-Nov-2026 3-report portal files."""
    fixture_dir = ROOT / "tests" / "fixtures" / "state_format_06_nov"
    raw_path = fixture_dir / "raw_dsr_06_nov.xls"
    pres_path = fixture_dir / "presentees_06_nov.xls"
    abs_path = fixture_dir / "absentees_06_nov.xls"

    if not raw_path.exists() or not pres_path.exists() or not abs_path.exists():
        pytest.skip("06-Nov-2026 fixtures not found")

    session = get_or_create_session("test_06_nov_fixture_session")
    res = state_format_service.process_and_generate_reports(
        raw_bytes=raw_path.read_bytes(),
        raw_filename=raw_path.name,
        presentees_bytes=pres_path.read_bytes(),
        presentees_filename=pres_path.name,
        absentees_bytes=abs_path.read_bytes(),
        absentees_filename=abs_path.name,
        session=session,
    )

    assert res["success"] is True
    assert res["district"] == "Khammam"
    assert res["date"] == "06-Nov-2026"

    totals = res["totals"]
    assert totals["tot_gps"] == 571
    assert totals["total_gps"] == 571
    assert totals["full_time"] == 505
    assert totals["full_time_working_ps"] == 505
    assert totals["b_6_9"] == 477
    assert totals["b_9_10"] == 27
    assert totals["b_after_12"] == 1
    assert totals["attended_gp"] == 486
    assert totals["mtg_trng"] == 4
    assert totals["leave"] == 15
    assert totals["not_reported"] == 0
    assert totals["pct_before_9"] == 94.46

    # Verify abstract sum rules
    assert totals["b_6_9"] + totals["b_9_10"] + totals["b_10_11"] + totals["b_11_12"] + totals["b_after_12"] + totals["not_reported"] == totals["full_time"]
    assert totals["attended_gp"] + totals["mtg_trng"] + totals["leave"] + totals["not_reported"] == totals["full_time"]

    # Verify mandals count
    mandals = res["mandals"]
    assert len(mandals) == 20
    assert mandals[0]["mandal_name"] == "Bonakal"
    assert mandals[0]["full_time"] == 17
    assert mandals[0]["pct_before_9"] == 100.0


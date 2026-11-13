"""Unit and integration tests for State Format Attendance & DSR Report module."""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import app
from dsr.state_format import (
    parse_state_format_data,
    generate_state_format_pdf,
    generate_state_format_excel,
    StateFormatReport,
    _classify_arrival_bucket,
)


SAMPLE_RAW_DSR = Path("dsr/downloads/session_bb833d53b268d8241dec88a7b533e0d7/Khammam_AttendenceStatusandDSRRawdata_07-Nov-2026.xls")


def test_classify_arrival_bucket():
    assert _classify_arrival_bucket("2026-11-07 07:30:00") == "6_9"
    assert _classify_arrival_bucket("2026-11-07 08:59:00") == "6_9"
    assert _classify_arrival_bucket("2026-11-07 09:00:00") == "9_10"
    assert _classify_arrival_bucket("2026-11-07 09:45:00") == "9_10"
    assert _classify_arrival_bucket("2026-11-07 10:15:00") == "10_11"
    assert _classify_arrival_bucket("2026-11-07 11:30:00") == "11_12"
    assert _classify_arrival_bucket("2026-11-07 12:00:00") == "after_12"
    assert _classify_arrival_bucket("2026-11-07 14:20:00") == "after_12"


@pytest.mark.skipif(not SAMPLE_RAW_DSR.exists(), reason="Sample raw DSR file not found")
def test_state_format_data_all_gps(tmp_path):
    raw_bytes = SAMPLE_RAW_DSR.read_bytes()
    report = parse_state_format_data(raw_bytes, SAMPLE_RAW_DSR.name, exclude_incharge=False)

    assert report.district_name == "Khammam"
    assert report.total_gps == 571
    assert report.total_working_ps == 508
    assert report.total_attended == 538
    assert report.overall_pct_before_9 > 0
    assert len(report.rows) == 20  # 20 mandals in Khammam

    # Ensure sorted descending by Col 10 (% of PS Reported before 9 AM)
    percentages = [r.pct_before_9 for r in report.rows]
    assert percentages == sorted(percentages, reverse=True)

    # Check Total Row
    tot = report.total_row
    assert tot.mandal_name == "Total"
    assert tot.total_gps == 571
    assert tot.full_time_working == 508
    assert tot.total_attended == 538
    assert tot.total_attended == (tot.b_6_9 + tot.b_9_10 + tot.b_10_11 + tot.b_11_12 + tot.b_after_12)
    assert tot.total_attended + tot.meeting_training + tot.on_leave + tot.not_reported == tot.total_gps

    # Generate PDF
    pdf_out = tmp_path / "test_state_format.pdf"
    generate_state_format_pdf(report, pdf_out)
    assert pdf_out.exists()
    assert pdf_out.stat().st_size > 1000

    # Generate Excel
    excel_out = tmp_path / "test_state_format.xlsx"
    generate_state_format_excel(report, excel_out)
    assert excel_out.exists()
    assert excel_out.stat().st_size > 1000


@pytest.mark.skipif(not SAMPLE_RAW_DSR.exists(), reason="Sample raw DSR file not found")
def test_state_format_data_exclude_incharge(tmp_path):
    raw_bytes = SAMPLE_RAW_DSR.read_bytes()
    report = parse_state_format_data(raw_bytes, SAMPLE_RAW_DSR.name, exclude_incharge=True)

    assert report.exclude_incharge is True
    assert report.total_gps == 508
    assert report.total_working_ps == 508
    assert report.total_attended == 486
    assert len(report.rows) == 20

    # Generate PDF
    pdf_out = tmp_path / "test_state_format_ex.pdf"
    generate_state_format_pdf(report, pdf_out)
    assert pdf_out.exists()
    assert pdf_out.stat().st_size > 1000


@pytest.mark.skipif(not SAMPLE_RAW_DSR.exists(), reason="Sample raw DSR file not found")
def test_manual_upload_state_format_endpoint():
    client = TestClient(app)
    raw_bytes = SAMPLE_RAW_DSR.read_bytes()
    
    response = client.post(
        "/api/web/state-format/upload",
        files={"file": (SAMPLE_RAW_DSR.name, io.BytesIO(raw_bytes), "application/vnd.ms-excel")},
        data={"exclude_incharge": "false"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["district_name"] == "Khammam"
    assert data["total_gps"] == 571
    assert len(data["rows"]) == 20
    assert "pdf_download_url" in data
    assert "excel_download_url" in data

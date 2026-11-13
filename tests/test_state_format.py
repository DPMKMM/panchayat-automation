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
    # Early punches before 6:00 AM must be considered in the Before 9 AM bucket
    assert _classify_arrival_bucket("2026-11-07 04:30:00") == "6_9"
    assert _classify_arrival_bucket("2026-11-07 05:15:00") == "6_9"
    assert _classify_arrival_bucket("2026-11-07 05:45:00") == "6_9"
    assert _classify_arrival_bucket("05:30:00") == "6_9"
    assert _classify_arrival_bucket("05:45 AM") == "6_9"
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
    # Arrival buckets (Cols 5-9) cover all reported secretaries (Attended GP + Meeting/Training + On Leave)
    assert tot.total_attended + tot.meeting_training + tot.on_leave == (tot.b_6_9 + tot.b_9_10 + tot.b_10_11 + tot.b_11_12 + tot.b_after_12)
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
    # Total No of GPs (Col 3) must NOT exclude incharge: it should be the total GP count (571 in Khammam)
    assert report.total_gps == 571
    assert report.total_working_ps == 508
    assert report.total_attended == 486
    assert len(report.rows) == 20

    # Total row checks
    tot = report.total_row
    assert tot.total_gps == 571
    assert tot.full_time_working == 508
    assert tot.total_attended == 486
    assert tot.total_attended + tot.meeting_training + tot.on_leave == (tot.b_6_9 + tot.b_9_10 + tot.b_10_11 + tot.b_11_12 + tot.b_after_12)
    assert tot.total_attended + tot.meeting_training + tot.on_leave + tot.not_reported == tot.full_time_working

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


def test_meeting_training_punctuality_formula(tmp_path):
    """Verify that Meeting/Training arrivals before 9 AM are credited in 6-9 AM bucket and 9 AM %."""
    import pandas as pd
    from dsr.state_format import parse_state_format_data

    # Create synthetic dataset resembling Thallada:
    # 27 GPs total: 21 Regular Full-Time, 6 Incharge
    # 6 Regular attended GP before 9 AM
    # 14 Regular attended Meeting at Mandal Level before 9 AM
    # 1 Regular attended Meeting at Mandal Level at 09:15 AM
    # 6 Incharge: 5 attended before 9 AM, 1 after 9 AM
    rows = []
    # 6 Regular GP present before 9 AM
    for i in range(1, 7):
        rows.append({
            "Panchayat LGD": str(200000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Regular",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "2026-11-13 08:30:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })
    # 14 Regular Meeting before 9 AM
    for i in range(7, 21):
        rows.append({
            "Panchayat LGD": str(200000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Regular",
            "First Attendence Status": "Meeting at Mandal Level",
            "First Attendence Datetime": "2026-11-13 08:45:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })
    # 1 Regular Meeting after 9 AM
    rows.append({
        "Panchayat LGD": "200021",
        "District Name": "Khammam",
        "Mandal Name": "Thallada",
        "Panchayat Name": "GP 21",
        "Nature of Posting": "Regular",
        "First Attendence Status": "Meeting at Mandal Level",
        "First Attendence Datetime": "2026-11-13 09:15:00",
        "Second Attendence Status": "",
        "Second Attendence Datetime": "",
    })
    # 6 Incharge GPs (5 before 9 AM, 1 after 9 AM)
    for i in range(22, 27):
        rows.append({
            "Panchayat LGD": str(200000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Incharge",
            "First Attendence Status": "Meeting at Mandal Level",
            "First Attendence Datetime": "2026-11-13 08:40:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })
    rows.append({
        "Panchayat LGD": "200027",
        "District Name": "Khammam",
        "Mandal Name": "Thallada",
        "Panchayat Name": "GP 27",
        "Nature of Posting": "Incharge",
        "First Attendence Status": "Present",
        "First Attendence Datetime": "2026-11-13 09:20:00",
        "Second Attendence Status": "",
        "Second Attendence Datetime": "",
    })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    raw_bytes = buf.getvalue()

    # 1. Test with Exclude Incharge (Regular Full-Time Only)
    rep_ex = parse_state_format_data(raw_bytes, "Thallada_Test.xlsx", exclude_incharge=True)
    th_row = rep_ex.rows[0]
    assert th_row.mandal_name == "Thallada"
    assert th_row.total_gps == 27
    assert th_row.full_time_working == 21
    # 6 GP present + 14 Meeting before 9 AM = 20
    assert th_row.b_6_9 == 20
    assert th_row.b_9_10 == 1
    # User formula: (6 AM - 9 AM) / No.of PS in which full time working * 100
    # 20 / 21 * 100 = 95.24% (~96%)
    assert th_row.pct_before_9 == 95.24
    # Col 11: strictly GP attended
    assert th_row.total_attended == 6
    # Col 12: reported to Meeting/Training
    assert th_row.meeting_training == 15
    # Balance: Col 11 (6) + Col 12 (15) == Col 4 (21)
    assert th_row.total_attended + th_row.meeting_training == th_row.full_time_working

    # 2. Test with All GPs (Include Incharge)
    rep_all = parse_state_format_data(raw_bytes, "Thallada_Test.xlsx", exclude_incharge=False)
    th_all = rep_all.rows[0]
    assert th_all.total_gps == 27
    assert th_all.full_time_working == 21
    # 20 regular + 5 incharge before 9 AM = 25 (out of 27 total, or if 26)
    assert th_all.b_6_9 == 25
    assert th_all.b_9_10 == 2
    # Total GPs denominator: 25 / 27 * 100 = 92.59%
    assert th_all.pct_before_9 == 92.59


def test_user_manual_report_leave_and_percentage_row(tmp_path):
    """Verify that Leave is credited before 9 AM, 14-col balancing holds, and percentage row is generated."""
    import pandas as pd
    from dsr.state_format import parse_state_format_data, generate_state_format_pdf, generate_state_format_excel

    # Thallada scenario:
    # 27 GPs total: 21 Regular, 6 Incharge
    # Among 21 Regular:
    # 19 Present before 9 AM
    # 2 On Leave before 9 AM (e.g. 06:25 AM, 06:58 AM)
    rows = []
    for i in range(1, 20):
        rows.append({
            "Panchayat LGD": str(990000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Regular",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "2026-11-12 08:35:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })
    # 2 on leave
    for i in range(20, 22):
        rows.append({
            "Panchayat LGD": str(990000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Regular",
            "First Attendence Status": "On Leave",
            "First Attendence Datetime": "2026-11-12 06:45:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })
    # 6 incharge
    for i in range(22, 28):
        rows.append({
            "Panchayat LGD": str(990000 + i),
            "District Name": "Khammam",
            "Mandal Name": "Thallada",
            "Panchayat Name": f"GP {i}",
            "Nature of Posting": "Incharge",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "2026-11-12 08:45:00",
            "Second Attendence Status": "",
            "Second Attendence Datetime": "",
        })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    raw_bytes = buf.getvalue()

    rep = parse_state_format_data(raw_bytes, "Thallada_12Nov.xlsx", ps_directory={}, exclude_incharge=True)
    r = rep.rows[0]

    assert r.total_gps == 27
    assert r.full_time_working == 21
    # Both 19 present and 2 on leave are credited before 9 AM -> 21
    assert r.b_6_9 == 21
    assert r.b_9_10 == 0
    assert r.pct_before_9 == 100.00
    assert r.total_attended == 19
    assert r.meeting_training == 0
    assert r.on_leave == 2
    assert r.not_reported == 0

    # Check Total & Percentage Row
    assert rep.total_row.b_6_9 == 21
    assert rep.percentage_row is not None
    assert rep.percentage_row["b_6_9"] == 100.00
    assert rep.percentage_row["total_attended"] == round(19 / 21 * 100, 2)
    assert rep.percentage_row["on_leave"] == round(2 / 21 * 100, 2)

    # Test PDF generation
    pdf_p = tmp_path / "manual_match.pdf"
    generate_state_format_pdf(rep, pdf_p)
    assert pdf_p.exists()
    assert pdf_p.stat().st_size > 1000

    # Test Excel generation
    xlsx_p = tmp_path / "manual_match.xlsx"
    generate_state_format_excel(rep, xlsx_p)
    assert xlsx_p.exists()
    assert xlsx_p.stat().st_size > 1000


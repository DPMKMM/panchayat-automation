"""Comprehensive tests for the Multi-Days DSR Manual Reports module (no graphs)."""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

os.environ["ENVIRONMENT"] = "development"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = ""

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import app
from multiday_dsr.processor import highlight_percentage, process_dsr
from multiday_dsr.reports import (
    generate_multiday_dsr_excel,
    generate_multiday_dsr_pdf,
)


def _make_epts_html_report(rows: list[dict[str, str]]) -> bytes:
    """Build a realistic EPTS HTML .xls export where table[0] is banner and table[1] has DSR rows."""
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


def test_process_dsr_logic_boundaries_and_color_bands():
    day1 = _make_epts_html_report([
        # < 09:00:00 -> Before 9 AM, Present, Entered
        {
            "District Name": "Peddapalli",
            "Mandal Name": "Julapalli",
            "Panchayat Name": "Julapalli GP",
            "Panchayat LGD": "201001",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "10-11-2026 08:45:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "10-11-2026 11:00:00",
        },
        # Exactly 09:00:00 -> After 9 AM (not < 09:00:00!)
        {
            "District Name": "Peddapalli",
            "Mandal Name": "Julapalli",
            "Panchayat Name": "Kuchirajpalli",
            "Panchayat LGD": "201002",
            "First Attendence Status": "On Leave",
            "First Attendence Datetime": "10-11-2026 09:00:00",
            "DSR Entry Status": "Not Entered",
            "DSR Submited Datetime": "",
        },
        # No timestamps at all -> still counted in gp_master denominator!
        {
            "District Name": "Peddapalli",
            "Mandal Name": "Manthani",
            "Panchayat Name": "Khammampalli",
            "Panchayat LGD": "202001",
            "First Attendence Status": "",
            "First Attendence Datetime": "",
            "DSR Entry Status": "Not Entered",
            "DSR Submited Datetime": "",
        },
    ])

    day2 = _make_epts_html_report([
        # Training, before 9 AM
        {
            "District Name": "Peddapalli",
            "Mandal Name": "Julapalli",
            "Panchayat Name": "Julapalli GP",
            "Panchayat LGD": "201001",
            "First Attendence Status": "Training - State",
            "First Attendence Datetime": "11-11-2026 08:30:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "11-11-2026 12:10:00",
        },
        # Meeting, fallback date from DSR Submited Datetime only (Attendance DT missing)
        {
            "District Name": "Peddapalli",
            "Mandal Name": "Manthani",
            "Panchayat Name": "Khammampalli",
            "Panchayat LGD": "202001",
            "First Attendence Status": "Meeting - Mandal",
            "First Attendence Datetime": "",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "11-11-2026 14:20:00",
        },
    ])

    res = process_dsr([("day1.xls", day1), ("day2.xls", day2)])
    assert res.dist_name == "Peddapalli"
    assert res.mandal_count == 2
    assert res.total_gps == 3
    assert res.total_reporting_days == 2
    assert res.start_date == "10-11-2026"
    assert res.end_date == "11-11-2026"

    # District level: 2 reporting days
    assert len(res.district) == 2
    d1 = res.district.iloc[0]
    assert d1["Date"] == "10-11-2026"
    assert int(d1["No. of GPs"]) == 3
    assert int(d1["Total Reported"]) == 2
    assert int(d1["Present"]) == 1
    assert int(d1["OnLeave"]) == 1
    assert int(d1["Not Reported"]) == 1
    assert int(d1["Before 9 AM"]) == 1
    assert int(d1["After 9 AM"]) == 1  # 09:00:00 belongs to After 9 AM
    assert float(d1["Before 9 AM %"]) == 50.0

    # Mandal level: 2 mandals x 2 dates = 4 rows (even Manthani on day1 with 0 reports)
    assert len(res.mandal) == 4
    manthani_day1 = res.mandal[(res.mandal["Mandal Name"] == "Manthani") & (res.mandal["Date"] == "10-11-2026")].iloc[0]
    assert int(manthani_day1["Total Reported"]) == 0
    assert int(manthani_day1["Not Reported"]) == 1

    # GP Summary: 3 unique GPs
    assert len(res.gp_summary) == 3
    j_gp = res.gp_summary[res.gp_summary["Panchayat Name"] == "Julapalli GP"].iloc[0]
    assert int(j_gp["No. of Days Reported"]) == 2
    assert float(j_gp["Before 9 AM %"]) == 100.0

    # Day-Wise Exact Attendance Time Matrix + Status Counts + Average Time & No. of Days Before 9 AM
    assert list(res.time_matrix.columns) == [
        "S.No",
        "Mandal Name",
        "Panchayat Name",
        "10-11-2026",
        "11-11-2026",
        "Present",
        "On Leave",
        "Not Marked Attendance",
        "Training / Meeting",
        "Average Time",
        "No. of Days Before 9 AM",
    ]
    tm_j = res.time_matrix[res.time_matrix["Panchayat Name"] == "Julapalli GP"].iloc[0]
    assert tm_j["10-11-2026"] == "08:45"
    assert tm_j["11-11-2026"] == "08:30"
    assert int(tm_j["Present"]) == 1
    assert int(tm_j["On Leave"]) == 0
    assert int(tm_j["Not Marked Attendance"]) == 0
    assert int(tm_j["Training / Meeting"]) == 1
    assert tm_j["Average Time"] == "08:37"
    assert int(tm_j["No. of Days Before 9 AM"]) == 2

    tm_k = res.time_matrix[res.time_matrix["Panchayat Name"] == "Kuchirajpalli"].iloc[0]
    assert tm_k["10-11-2026"] == "09:00"
    assert tm_k["11-11-2026"] == "-"
    assert int(tm_k["Present"]) == 0
    assert int(tm_k["On Leave"]) == 1
    assert int(tm_k["Not Marked Attendance"]) == 1
    assert int(tm_k["Training / Meeting"]) == 0
    assert tm_k["Average Time"] == "09:00"
    assert int(tm_k["No. of Days Before 9 AM"]) == 0  # 09:00:00 is >= 9 AM

    # Color threshold checks from highlight_percentage
    assert highlight_percentage(0)["bg"] == "#f8d7da"
    assert highlight_percentage(25)["bg"] == "#f5c6cb"
    assert highlight_percentage(60)["bg"] == "#fff3cd"
    assert highlight_percentage(80)["bg"] == "#ffeeba"
    assert highlight_percentage(95)["bg"] == "#c3e6cb"
    assert highlight_percentage(100)["bg"] == "#28a745"
    assert highlight_percentage(100)["fg"] == "#ffffff"


def test_multiday_dsr_exports_and_endpoints(tmp_path: Path):
    day1 = _make_epts_html_report([
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Allinagaram",
            "Panchayat LGD": "205101",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "10-11-2026 08:25:00",
            "DSR Entry Status": "Entered",
            "DSR Submited Datetime": "10-11-2026 11:15:00",
        },
        {
            "District Name": "Khammam",
            "Mandal Name": "Bonakal",
            "Panchayat Name": "Govindapuram",
            "Panchayat LGD": "205102",
            "First Attendence Status": "Present",
            "First Attendence Datetime": "10-11-2026 09:20:00",
            "DSR Entry Status": "Not Entered",
            "DSR Submited Datetime": "",
        },
    ])
    res = process_dsr([("bonakal.xls", day1)])

    pdf_path = tmp_path / "md.pdf"
    generate_multiday_dsr_pdf(res, pdf_path)
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 4
    first = reader.pages[0]
    assert float(first.mediabox.width) > float(first.mediabox.height)  # Landscape A4
    txt = "\n".join(p.extract_text() for p in reader.pages)
    assert "District Level" in txt
    assert "Mandal Level" in txt
    assert "Gram Panchayat Level" in txt
    assert "Average Time" in txt
    assert "08:25" in txt
    assert "08:25:00 AM" not in txt
    assert "Allinagaram" in txt

    xlsx_path = tmp_path / "md.xlsx"
    generate_multiday_dsr_excel(res, xlsx_path)
    wb = openpyxl.load_workbook(xlsx_path)
    assert wb.sheetnames == ["District Level", "Mandal Level", "GP Level Summary", "Day-Wise Exact Time", "Master Data"]

    # Individual single-level PDFs render only their requested report section
    gp_pdf_path = tmp_path / "md_gp.pdf"
    generate_multiday_dsr_pdf(res, gp_pdf_path, level="gp")
    gp_pdf_txt = "\n".join(p.extract_text() for p in PdfReader(str(gp_pdf_path)).pages)
    assert "Gram Panchayat Level" in gp_pdf_txt
    assert "District Level — Date-Wise" not in gp_pdf_txt

    # Live HTTP API & page route tests (CSV removed, Full + Per-Report PDFs + Excel present)
    client = TestClient(app)
    page = client.get("/reports/multi-day-dsr")
    assert page.status_code == 200
    assert "Multiple Days DSR" in page.text
    assert 'id="md-opt-time-matrix"' in page.text
    assert 'id="md-dl-pdf-district"' in page.text
    assert 'id="md-dl-pdf-mandal"' in page.text
    assert 'id="md-dl-pdf-gp"' in page.text
    assert 'id="md-dl-pdf-time"' in page.text
    assert "Download Active CSV" not in page.text

    resp = client.post(
        "/api/multiday-dsr/analyze",
        files=[("files", ("day1.xls", day1, "application/vnd.ms-excel"))],
        data={"include_time_matrix": "true"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["summary"]["dist_name"] == "Khammam"
    assert "Average Time" in body["time_matrix_columns"]
    assert "No. of Days Before 9 AM" in body["time_matrix_columns"]
    job_id = body["job_id"]

    ts_re = re.compile(r"_\d{2}-\d{2}-\d{4} \d{2}:\d{2} (?:AM|PM)\.(?:pdf|xlsx)\"")

    for lvl, expected_txt in (
        ("all", "District Level"),
        ("district", "District Level"),
        ("mandal", "Mandal Level"),
        ("gp", "Gram Panchayat Level"),
        ("time_matrix", "Average Time"),
    ):
        dl_p = client.get(f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level={lvl}")
        assert dl_p.status_code == 200 and dl_p.content.startswith(b"%PDF")
        assert ts_re.search(dl_p.headers.get("Content-Disposition", ""))
        lvl_txt = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(dl_p.content)).pages)
        assert expected_txt in lvl_txt

    dl_xlsx = client.get(f"/api/multiday-dsr/jobs/{job_id}/download-excel")
    assert dl_xlsx.status_code == 200 and dl_xlsx.content[:2] == b"PK"
    assert ts_re.search(dl_xlsx.headers.get("Content-Disposition", ""))

    # Removed CSV endpoint returns 404
    assert client.get(f"/api/multiday-dsr/jobs/{job_id}/download-csv?level=gp").status_code == 404

    # Toggle option off -> time_matrix omitted from Excel & JSON response
    resp_no_tm = client.post(
        "/api/multiday-dsr/analyze",
        files=[("files", ("day1.xls", day1, "application/vnd.ms-excel"))],
        data={"include_time_matrix": "false"},
    )
    assert resp_no_tm.status_code == 200
    assert resp_no_tm.json()["time_matrix_columns"] == []
    dl_xlsx_4 = client.get(f"/api/multiday-dsr/jobs/{resp_no_tm.json()['job_id']}/download-excel")
    wb4 = openpyxl.load_workbook(io.BytesIO(dl_xlsx_4.content))
    assert wb4.sheetnames == ["District Level", "Mandal Level", "GP Level Summary", "Master Data"]

    # Different client without job cookie is blocked (403)
    other_client = TestClient(app)
    blocked = other_client.get(f"/api/multiday-dsr/jobs/{job_id}/download-pdf")
    assert blocked.status_code == 403


def test_full_31_day_month_compact_layout(tmp_path: Path):
    """Full-month (31 days) dataset fits in just 2 horizontal PDF slices with HH:MM timestamps."""
    files = []
    for d in range(1, 32):
        dt = f"{d:02d}-10-2026"
        raw = _make_epts_html_report([
            {
                "District Name": "Khammam",
                "Mandal Name": "Bonakal",
                "Panchayat Name": "Allinagaram",
                "Panchayat LGD": "205101",
                "First Attendence Status": "Present",
                "First Attendence Datetime": f"{dt} 08:{10 + (d % 40):02d}:15",
                "DSR Entry Status": "Entered",
                "DSR Submited Datetime": f"{dt} 11:00:00",
            },
        ])
        files.append((f"day_{d:02d}.xls", raw))

    res = process_dsr(files)
    assert res.total_reporting_days == 31
    assert len(res.time_matrix.columns) == 3 + 31 + 6  # S.No, Mandal, GP + 31 dates + 6 summary cols

    pdf_path = tmp_path / "full_month.pdf"
    generate_multiday_dsr_pdf(res, pdf_path)
    pdf_txt = "\n".join(p.extract_text() for p in PdfReader(str(pdf_path)).pages)
    assert "(Part 1/2)" in pdf_txt and "(Part 2/2)" in pdf_txt
    assert "(Part 3/" not in pdf_txt

    xlsx_path = tmp_path / "full_month.xlsx"
    generate_multiday_dsr_excel(res, xlsx_path)
    wb = openpyxl.load_workbook(xlsx_path)
    assert "Day-Wise Exact Time" in wb.sheetnames

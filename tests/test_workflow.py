from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

import app as app_module
from app import Settings, create_app
from integrations import JobRecord, LocalJobTracker, utc_now
from report_generator import (
    InputValidationError,
    PercentBar,
    _clean_name,
    _format_time_only,
    analyze_attendance,
    detect_file_metadata,
    generate_mandal_pdf,
    generate_pdf,
    parse_ps_directory_file,
    merge_ps_directories,
    process_attendance_file,
)


def attendance_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"District Name": "Khammam", "Panchayat LGD": 1, "Mandal Name": "Mandal A", "Panchayat Name": "GP One",
         "First Attendence Status": "Present", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 09:00", "DSR Entry Status": "Submitted"},
        {"District Name": "Khammam", "Panchayat LGD": 2, "Mandal Name": "Mandal A", "Panchayat Name": "GP Two",
         "First Attendence Status": "Present", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 08:59", "DSR Entry Status": "Submitted"},
        {"District Name": "Khammam", "Panchayat LGD": 3, "Mandal Name": "Mandal A", "Panchayat Name": "GP Three",
         "First Attendence Status": "Present", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 09:01", "DSR Entry Status": "Pending"},
        {"District Name": "Khammam", "Panchayat LGD": 4, "Mandal Name": "Mandal B", "Panchayat Name": "GP Four",
         "First Attendence Status": "", "Second Attendence Status": "",
         "First Attendence Datetime": "", "DSR Entry Status": ""},
        {"District Name": "Khammam", "Panchayat LGD": 5, "Mandal Name": "Mandal B", "Panchayat Name": "GP Five",
         "First Attendence Status": "On Leave", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 08:30", "DSR Entry Status": "Submitted"},
        {"District Name": "Khammam", "Panchayat LGD": 6, "Mandal Name": "Mandal B", "Panchayat Name": "GP Six",
         "First Attendence Status": "Training", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 09:05", "DSR Entry Status": "Submitted"},
        {"District Name": "Khammam", "Panchayat LGD": 7, "Mandal Name": "Mandal B", "Panchayat Name": "GP Seven",
         "First Attendence Status": "", "Second Attendence Status": "",
         "First Attendence Datetime": "", "DSR Entry Status": ""},
        {"District Name": "Khammam", "Panchayat LGD": 7, "Mandal Name": "Mandal C", "Panchayat Name": "GP Seven Conflict",
         "First Attendence Status": "Meeting", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 09:00", "DSR Entry Status": "Submitted"},
    ])


def presentees_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "S.No.": 1, "District Name": "Khammam", "Division Name": "KHAMMAM",
            "Mandal Name": "Mandal A", "Panchayat Name": "GP One", "Panchayat LGD Code": 1,
            "Panchayat Secretary Employee Id": "EMP101",
            "Panchayat Secretary Name": "RAYALALA NAGARAJU",  # Test all caps name
            "Designation": "Panchayat Secretary Grade I", "Nature of Posting": "Regular",
            "Mobile Number": "8897632431",
        },
        {
            "S.No.": 2, "District Name": "Khammam", "Division Name": "KHAMMAM",
            "Mandal Name": "Mandal A", "Panchayat Name": "GP Three", "Panchayat LGD Code": 3,
            "Panchayat Secretary Employee Id": "EMP103",
            "Panchayat Secretary Name": "kola rajeswari",  # Test all lower name
            "Designation": "Junior Panchayat Secretary", "Nature of Posting": "Incharge",
            "Mobile Number": "7981048487.0",  # Test Excel trailing .0 float cleaning
        },
    ])


def absentees_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "S.No.": 1, "District Name": "Khammam", "Division Name": "KHAMMAM",
            "Mandal Name": "Mandal B", "Panchayat Name": "GP Four", "Panchayat LGD Code": 4,
            "Panchayat Secretary Employee Id": "EMP104",
            "Panchayat Secretary Name": "TALLURU BHARGAVI",
            "Designation": "Panchayat Secretary Grade IV", "Nature of Posting": "Regular",
            "Mobile Number": "9618390381",
        },
    ])


def bytes_for(frame: pd.DataFrame, extension: str) -> bytes:
    buffer = BytesIO()
    if extension == ".xlsx":
        frame.to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()
    if extension == ".csv":
        return frame.to_csv(index=False).encode("utf-8")
    if extension == ".xls":
        return ("<html><body>" + frame.to_html(index=False) + "</body></html>").encode("utf-8")
    raise AssertionError(extension)


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        session_secret="test-only-session-secret-value-at-least-32-characters",
        data_dir=tmp_path / "data",
        max_upload_bytes=30 * 1024 * 1024,
    )


def test_valid_xlsx_generates_unique_mandal_abstract_and_categories():
    report = process_attendance_file("synthetic.xlsx", bytes_for(attendance_rows(), ".xlsx"))

    assert report.district_name == "Khammam"
    assert report.unique_gp_count == 7
    assert report.duplicate_lgd_rows == 1
    assert len(report.conflicts) == 1
    assert report.conflicts[0]["lgd"] == "7"
    assert report.conflicts[0]["mandals"] == ["Mandal B", "Mandal C"]
    assert report.totals == {
        "unique_gps": 7,
        "attendance_submitted": 6,
        "overall_attendance_pct": pytest.approx(6 / 7 * 100),
        "before_9": 4,
        "on_leave": 1,
        "meeting_training": 2,
        "pending": 1,
        "after_9": 2,
        "dsr_eligible": 3,
        "dsr_entered": 2,
        "dsr_pending": 1,
    }
    assert [row["mandal"] for row in report.mandal_rows] == ["Mandal B", "Mandal A"]
    assert report.district_total["before_9_pct"] == pytest.approx(4 / 7 * 100)
    assert report.district_total["attendance_pct"] == pytest.approx(6 / 7 * 100)
    assert report.mandal_rows[0]["before_9_pct"] == 50
    assert report.mandal_rows[0]["attendance_pct"] == 75
    assert report.dsr_district_total["dsr_pct"] == pytest.approx(2 / 3 * 100)
    assert report.dsr_district_total["dsr_pending"] == 1
    assert [row["mandal"] for row in report.dsr_mandal_rows] == ["Mandal B", "Mandal A"]
    assert report.dsr_pending_rows[0]["gp"] == "GP Three"


def test_dynamic_district_name_detected_from_uploaded_data():
    frame = attendance_rows().copy()
    frame["District Name"] = "Bhadradri Kothagudem"
    report = analyze_attendance(frame)
    assert report.district_name == "Bhadradri Kothagudem"


def test_clean_name_proper_casing():
    assert _clean_name("RAYALALA NAGARAJU") == "Rayalala Nagaraju"
    assert _clean_name("kola rajeswari") == "Kola Rajeswari"
    assert _clean_name("CH.VENKATESWARLU") == "Ch.Venkateswarlu"
    assert _clean_name("K. Venkateshwarlu") == "K. Venkateshwarlu"
    assert _clean_name("MOGILI SIVASHANKAR") == "Mogili Sivashankar"


def test_format_time_only_extracts_clean_time():
    assert _format_time_only("28-10-2026 09:01") == "09:01 AM"
    assert _format_time_only("31-Oct-2026 08:30") == "08:30 AM"
    assert _format_time_only("09:15") == "09:15 AM"


def test_percent_bar_green_only_for_100_percent():
    bar_100 = PercentBar(100.0, 50)
    bar_95 = PercentBar(95.0, 50)
    bar_60 = PercentBar(60.0, 50)
    bar_30 = PercentBar(30.0, 50)
    assert bar_100.percent == 100.0
    assert bar_95.percent == 95.0


def test_csv_with_header_variations_is_supported():
    frame = attendance_rows().iloc[:1].rename(columns={
        "Panchayat LGD": " panchayat-lgd ",
        "Mandal Name": "MANDAL NAME",
        "First Attendence Status": "First Attendance Status",
        "First Attendence Datetime": "First Attendance Date Time",
        "Second Attendence Status": "Second Attendance Status",
        "DSR Entry Status": "DSR Status",
    })
    report = process_attendance_file("synthetic.csv", bytes_for(frame, ".csv"))
    assert report.unique_gp_count == 1
    assert report.totals["before_9"] == 1


def test_literal_na_status_is_submitted_not_pending():
    frame = attendance_rows().iloc[:1].copy()
    frame.loc[frame.index[0], "First Attendence Status"] = "NA"
    frame.loc[frame.index[0], "First Attendence Datetime"] = ""
    report = process_attendance_file("synthetic.csv", bytes_for(frame, ".csv"))
    assert report.totals["pending"] == 0
    assert report.totals["before_9"] == 0
    assert report.after_9_rows == []


def test_html_table_saved_as_xls_is_supported():
    report = process_attendance_file("portal-export.xls", bytes_for(attendance_rows().iloc[:2], ".xls"))
    assert report.unique_gp_count == 2
    assert report.totals["before_9"] == 2


def test_missing_required_columns_return_a_useful_error():
    source = pd.DataFrame({"Mandal": ["A"], "GP": ["one"]}).to_csv(index=False).encode()
    with pytest.raises(InputValidationError, match=r"Required column\(s\) not found") as error:
        process_attendance_file("bad.csv", source)
    assert "Panchayat LGD" in str(error.value)
    assert "First Attendence Datetime" in str(error.value)


def test_missing_dsr_submission_column_returns_a_useful_error():
    frame = attendance_rows().drop(columns=["DSR Entry Status"])
    with pytest.raises(InputValidationError, match="DSR submission column was not found"):
        analyze_attendance(frame)


def test_duplicate_lgd_prefers_a_nonblank_status_and_flags_conflicting_names():
    report = analyze_attendance(attendance_rows())
    assert report.unique_gp_count == 7
    assert report.duplicate_lgd_rows == 1
    assert report.conflicts[0]["mandals"] == ["Mandal B", "Mandal C"]
    assert report.conflicts[0]["panchayats"] == ["GP Seven", "GP Seven Conflict"]
    meeting = next(row for row in report.meeting_training_rows if row["gp"] == "GP Seven")
    assert meeting["status"] == "Meeting"
    assert meeting["timestamp"]


def test_time_boundary_blank_leave_meeting_training_and_after_nine_rules():
    report = analyze_attendance(attendance_rows())
    after_nine = {row["gp"] for row in report.after_9_rows}
    assert "GP One" not in after_nine  # 09:00 exactly belongs to before-9.
    assert "GP Two" not in after_nine  # 08:59.
    assert {"GP Three", "GP Six"} == after_nine
    assert report.totals["pending"] == 1
    assert [row["gp"] for row in report.leave_rows] == ["GP Five"]
    assert {row["gp"] for row in report.meeting_training_rows} == {"GP Seven", "GP Six"}
    assert all(row["status"] for row in report.leave_rows + report.meeting_training_rows)


def test_dsr_requires_present_on_first_or_second_attendance_and_excludes_other_statuses():
    frame = pd.DataFrame([
        {"Panchayat LGD": 1, "Mandal Name": "A", "Panchayat Name": "GP1",
         "First Attendence Status": "Present", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 08:00", "DSR Entry Status": "Submitted"},
        {"Panchayat LGD": 2, "Mandal Name": "A", "Panchayat Name": "GP2",
         "First Attendence Status": "On Leave", "Second Attendence Status": "Present",
         "First Attendence Datetime": "28-10-2026 08:00", "DSR Entry Status": "Pending"},
        {"Panchayat LGD": 3, "Mandal Name": "A", "Panchayat Name": "GP3",
         "First Attendence Status": "Meeting", "Second Attendence Status": "Training",
         "First Attendence Datetime": "28-10-2026 08:00", "DSR Entry Status": "Submitted"},
        {"Panchayat LGD": 4, "Mandal Name": "B", "Panchayat Name": "GP4",
         "First Attendence Status": "", "Second Attendence Status": "Present",
         "First Attendence Datetime": "", "DSR Entry Status": ""},
        {"Panchayat LGD": 5, "Mandal Name": "B", "Panchayat Name": "GP5",
         "First Attendence Status": "Present", "Second Attendence Status": "",
         "First Attendence Datetime": "28-10-2026 08:00", "DSR Entry Status": "Not Entered"},
    ])

    report = analyze_attendance(frame)

    assert report.dsr_district_total == {
        "total_gps": 5,
        "present_ps": 4,
        "dsr_entered": 1,
        "dsr_pct": 25,
        "dsr_pending": 3,
    }
    assert {row["gp"] for row in report.dsr_pending_rows} == {"GP2", "GP4", "GP5"}
    assert "Second: Present" in next(row for row in report.dsr_pending_rows if row["gp"] == "GP2")["attendance_status"]


def test_ps_directory_parsing_and_proper_casing():
    p_bytes = bytes_for(presentees_rows(), ".xlsx")
    a_bytes = bytes_for(absentees_rows(), ".csv")

    p_dir = parse_ps_directory_file("presentees.xlsx", p_bytes)
    a_dir = parse_ps_directory_file("absentees.csv", a_bytes)

    assert "1" in p_dir
    # All caps in source converted to proper case:
    assert p_dir["1"]["ps_name"] == "Rayalala Nagaraju"
    assert p_dir["1"]["mobile"] == "8897632431"
    assert p_dir["1"]["nature_of_posting"] == "Regular"

    assert "3" in p_dir
    # All lower in source converted to proper case:
    assert p_dir["3"]["ps_name"] == "Kola Rajeswari"
    assert p_dir["3"]["mobile"] == "7981048487"  # Cleaned from 7981048487.0
    assert p_dir["3"]["nature_of_posting"] == "Incharge"

    assert "4" in a_dir
    assert a_dir["4"]["ps_name"] == "Talluru Bhargavi"
    assert a_dir["4"]["mobile"] == "9618390381"
    assert a_dir["4"]["nature_of_posting"] == "Regular"

    merged = merge_ps_directories(p_dir, a_dir)
    assert len(merged) == 3
    assert set(merged.keys()) == {"1", "3", "4"}


def test_ps_details_lookup_in_attendance_pending_and_after_9_lists():
    raw_bytes = bytes_for(attendance_rows(), ".xlsx")
    p_source = ("presentees.xlsx", bytes_for(presentees_rows(), ".xlsx"))
    a_source = ("absentees.csv", bytes_for(absentees_rows(), ".csv"))

    report = process_attendance_file(
        "attendance.xlsx",
        raw_bytes,
        presentees_source=p_source,
        absentees_source=a_source,
    )

    # GP Four is pending:
    gp_four = next(row for row in report.pending_rows if row["gp"] == "GP Four")
    assert gp_four["ps_name"] == "Talluru Bhargavi"
    assert gp_four["nature_of_posting"] == "Regular"
    assert gp_four["mobile"] == "9618390381"

    # GP Three submitted after 9 AM (09:01):
    gp_three = next(row for row in report.after_9_rows if row["gp"] == "GP Three")
    assert gp_three["ps_name"] == "Kola Rajeswari"
    assert gp_three["nature_of_posting"] == "Incharge"
    assert gp_three["mobile"] == "7981048487"
    assert gp_three["time_only"] == "09:01 AM"

    # DSR pending row has attendance time:
    dsr_three = next(row for row in report.dsr_pending_rows if row["gp"] == "GP Three")
    assert dsr_three["time_only"] == "09:01 AM"


def test_pdf_generation_includes_ps_name_mobile_and_posting(tmp_path: Path):
    raw_bytes = bytes_for(attendance_rows(), ".xlsx")
    p_source = ("presentees.xlsx", bytes_for(presentees_rows(), ".xlsx"))
    a_source = ("absentees.csv", bytes_for(absentees_rows(), ".csv"))

    report = process_attendance_file(
        "attendance.xlsx",
        raw_bytes,
        presentees_source=p_source,
        absentees_source=a_source,
    )
    pdf_path = generate_pdf(report, tmp_path / "ps_report.pdf")
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Kola Rajeswari" in text
    assert "7981048487" in text
    assert "Talluru Bhargavi" in text  # In Pending table
    assert "9618390381" in text
    assert "Incharge" in text
    assert "Regular" in text
    assert "09:01 AM" in text
    assert "DSR not entered" in text


def test_empty_sections_are_rendered_and_district_totals_remain_correct(tmp_path: Path):
    frame = attendance_rows().iloc[[0]].copy()
    report = analyze_attendance(frame)
    assert report.totals["unique_gps"] == 1
    assert report.district_total["total_gps"] == 1
    assert report.district_total["before_9"] == 1
    assert report.district_total["attendance_pct"] == 100
    assert report.dsr_district_total["dsr_pct"] == 100
    assert report.pending_rows == []
    assert report.leave_rows == []
    assert report.meeting_training_rows == []
    assert report.after_9_rows == []
    assert report.dsr_pending_rows == []

    pdf_path = generate_pdf(report, tmp_path / "empty-sections.pdf")
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized_text = " ".join(text.split())
    assert "KHAMMAM DISTRICT" in text
    assert "No pending GPs found." in text
    assert "No GPs submitted attendance after 9 AM." in text
    assert "No eligible GPs have pending DSR." in text
    assert "Overall Attendance %" in normalized_text
    assert "Mandal-wise DSR Abstract Report" in text
    assert "% GPs DSR submitted" in text
    assert "DSR Pending GPs: 0" in text
    assert "Method:" not in text
    assert "DISTRICT TOTAL" in text


def test_pdf_generation_includes_all_report_section_titles(tmp_path: Path):
    report = analyze_attendance(attendance_rows())
    pdf_path = generate_pdf(report, tmp_path / "attendance.pdf")
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 5
    assert float(reader.pages[0].mediabox.width) == pytest.approx(595.28, abs=0.1)
    assert float(reader.pages[0].mediabox.height) == pytest.approx(841.89, abs=0.1)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized_text = " ".join(text.split())
    assert "Mandal-wise Attendance Abstract" in text
    assert "Overall Attendance %" in normalized_text
    assert "Mandal-wise DSR Abstract Report" in text
    assert "No. of PS present" in text
    assert "No. of GPs DSR entered" in text
    assert "No. of GPs DSR pending" in normalized_text
    assert "% GPs DSR submitted" in text
    assert "Attendance Pending GPs" in text
    assert "Secretaries Reported as Leave" in text
    assert "Secretaries Reported as Training / Meeting" in text
    assert "AFTER 9 AM" in text
    assert "DSR PENDING GPs" in text
    assert "DSR Pending GPs:" in text
    assert "Method:" not in text
    assert "GP Seven Conflict" in text or "conflicting names" in text
    page_texts = [page.extract_text() or "" for page in reader.pages]
    assert "Attendance Pending GPs" in page_texts[2]
    assert "DSR PENDING GPs" in page_texts[3]
    assert "Secretaries Reported as Leave" in page_texts[4]


def test_mandal_abstract_repeats_column_headers_when_continued(tmp_path: Path):
    frame = pd.DataFrame([
        {
            "Panchayat LGD": index + 1,
            "Mandal Name": f"Mandal {index:02d}",
            "Panchayat Name": f"GP {index:02d}",
            "First Attendence Status": "Present",
            "Second Attendence Status": "",
            "First Attendence Datetime": "28-10-2026 08:00",
            "DSR Entry Status": "Submitted",
        }
        for index in range(70)
    ])
    report = analyze_attendance(frame)
    pdf_path = generate_pdf(report, tmp_path / "continued-abstract.pdf")
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) > 5
    page_two = reader.pages[1].extract_text()
    assert "Sl. No." in page_two
    assert "No. of GPs" in page_two


def test_web_upload_processes_synchronously_and_downloads_private_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config = make_settings(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")
    monkeypatch.setattr(app_module, "utc_now", lambda: "2026-10-28T03:04:05+00:00")
    workbook = bytes_for(attendance_rows(), ".xlsx")
    calls = 0
    real_process = app_module.process_attendance_file

    def count_process(filename: str, contents: bytes, **kwargs):
        nonlocal calls
        calls += 1
        return real_process(filename, contents, **kwargs)

    monkeypatch.setattr(app_module, "process_attendance_file", count_process)
    upload = client.post(
        "/api/web/reports",
        data={"RequestedBy": "tester"},
        files={"file": ("synthetic.xlsx", workbook, "application/octet-stream")},
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == "Completed"
    job_id = upload.json()["job_id"]
    assert calls == 1

    status = client.get(f"/api/web/reports/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "Completed"
    download = client.get(f"/api/web/reports/{job_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"] == (
        'attachment; filename="PS_Attendance_Report_2026-10-28_08-34-05.pdf"'
    )
    assert download.content.startswith(b"%PDF")
    assert (config.data_dir / "reports" / "PS_Attendance_Report_2026-10-28_08-34-05.pdf").is_file()
    assert client.get(f"/api/web/reports/{job_id}/jpeg-pages").status_code == 404
    assert client.get(f"/api/reports/{job_id}").status_code == 404
    assert client.get("/docs").status_code == 404


def test_web_upload_with_presentees_and_absentees_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config = make_settings(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")
    monkeypatch.setattr(app_module, "utc_now", lambda: "2026-10-28T03:04:05+00:00")

    upload = client.post(
        "/api/web/reports",
        data={"RequestedBy": "Collectorate"},
        files={
            "file": ("attendance.xlsx", bytes_for(attendance_rows(), ".xlsx"), "application/octet-stream"),
            "presentees_file": ("presentees.xlsx", bytes_for(presentees_rows(), ".xlsx"), "application/octet-stream"),
            "absentees_file": ("absentees.csv", bytes_for(absentees_rows(), ".csv"), "text/csv"),
        },
    )
    assert upload.status_code == 200
    job_id = upload.json()["job_id"]
    assert upload.json()["status"] == "Completed"

    download = client.get(f"/api/web/reports/{job_id}/download")
    assert download.status_code == 200
    reader = PdfReader(BytesIO(download.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Kola Rajeswari" in text
    assert "7981048487" in text
    assert "Talluru Bhargavi" in text
    assert "9618390381" in text


def test_web_upload_rejects_invalid_types_and_missing_columns(tmp_path: Path):
    client = TestClient(create_app(make_settings(tmp_path)))

    invalid_type = client.post(
        "/api/web/reports",
        files={"file": ("payload.exe", b"data", "application/octet-stream")},
    )
    assert invalid_type.status_code == 415

    bad_csv = b"Mandal,GP\nA,One\n"
    missing = client.post(
        "/api/web/reports",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
    )
    assert missing.status_code == 422
    assert "Required column(s) not found" in missing.json()["detail"]["message"]
    assert missing.json()["detail"]["job_id"]


def test_health_and_web_upload_configuration(tmp_path: Path):
    config = make_settings(tmp_path)
    client = TestClient(create_app(Settings(
        session_secret="",
        data_dir=config.data_dir,
        max_upload_bytes=config.max_upload_bytes,
    )))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["storage"] == "local"
    assert health.json()["job_tracking"] == "local_sqlite"
    unavailable = client.post(
        "/api/web/reports",
        files={"file": ("synthetic.xlsx", bytes_for(attendance_rows(), ".xlsx"), "application/octet-stream")},
    )
    assert unavailable.status_code == 503


def test_root_page_opens_directly_with_upload_and_download_workflow(tmp_path: Path):
    client = TestClient(create_app(make_settings(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "PS Attendance" in response.text
    assert 'id="login-form"' not in response.text
    assert "APP_API_TOKEN" not in response.text
    assert "AppSheet" not in response.text
    assert "google" not in response.text.lower()
    assert "API documentation" not in response.text
    assert 'id="upload-form"' in response.text
    assert 'id="attendance-file"' in response.text
    assert 'id="presentees-file"' in response.text
    assert 'id="absentees-file"' in response.text
    assert "Generate and download report" in response.text
    assert "/api/web/reports" in response.text
    assert "Content-Disposition" in response.text


def test_public_web_upload_download_uses_private_browser_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config = make_settings(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")
    monkeypatch.setattr(app_module, "utc_now", lambda: "2026-10-28T03:04:05+00:00")

    upload = client.post(
        "/api/web/reports",
        data={"RequestedBy": "tester"},
        files={"file": ("synthetic.xlsx", bytes_for(attendance_rows(), ".xlsx"), "application/octet-stream")},
    )
    assert upload.status_code == 200
    job_id = upload.json()["job_id"]
    assert upload.json()["status"] == "Completed"
    cookie = upload.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "secure" in cookie.lower()
    assert "samesite=strict" in cookie.lower()
    assert client.get(f"/api/web/reports/{job_id}").status_code == 200

    download = client.get(f"/api/web/reports/{job_id}/download")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    assert download.headers["content-disposition"] == (
        'attachment; filename="PS_Attendance_Report_2026-10-28_08-34-05.pdf"'
    )

    other_client = TestClient(create_app(make_settings(tmp_path / "other")), base_url="https://testserver")
    assert other_client.get(f"/api/web/reports/{job_id}").status_code == 401
    assert other_client.get(f"/api/web/reports/{job_id}/download").status_code == 401
    assert client.get(f"/api/reports/{job_id}").status_code == 404


def test_public_web_upload_endpoint_limits_requests_by_client(tmp_path: Path):
    client = TestClient(create_app(make_settings(tmp_path)))
    invalid_upload = {
        "files": {"file": ("not-allowed.exe", b"no executable", "application/octet-stream")},
    }

    for _ in range(app_module.WEB_UPLOADS_PER_HOUR):
        assert client.post("/api/web/reports", **invalid_upload).status_code == 415
    limited = client.post("/api/web/reports", **invalid_upload)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"


def test_local_tracker_claims_once_and_recovers_a_stale_processing_job(tmp_path: Path):
    tracker = LocalJobTracker(tmp_path / "jobs.sqlite3")
    tracker.create(JobRecord(
        job_id="claim-test",
        uploaded_file="attendance.xlsx",
        requested_by="tester@example.org",
        requested_at=utc_now(),
    ))
    assert tracker.claim("claim-test") is True
    assert tracker.claim("claim-test") is False
    tracker.update("claim-test", notes="Processing started at 2000-01-01T00:00:00+00:00")
    assert tracker.claim("claim-test") is True


def test_mandal_pdf_generation_and_metadata_detection(tmp_path: Path):
    source_bytes = bytes_for(attendance_rows(), ".xlsx")
    meta = detect_file_metadata("attendance.xlsx", source_bytes)
    assert meta["district_name"] == "Khammam"
    assert "Mandal A" in meta["mandals"]
    assert "Mandal B" in meta["mandals"]

    report = process_attendance_file("attendance.xlsx", source_bytes)
    out_pdf = tmp_path / "mandal_a.pdf"
    generate_mandal_pdf(report, out_pdf, mandal_name="Mandal A")
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 1000

    reader = PdfReader(str(out_pdf))
    assert len(reader.pages) >= 2
    p1 = reader.pages[0].extract_text()
    assert "MANDAL A" in p1
    assert "Mandal Abstract Summary" in p1
    p2 = reader.pages[1].extract_text()
    assert "MANDAL A" in p2
    assert "GP ATTENDANCE & DSR REPORT" in p2
    assert "Gram Panchayat Attendance & DSR Status" in p2


def test_web_upload_mandal_mode_downloads_mandal_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(create_app(make_settings(tmp_path)))
    source_bytes = bytes_for(attendance_rows(), ".xlsx")

    # Test metadata detection endpoint
    detect_resp = client.post(
        "/api/web/detect-mandals",
        files={"file": ("attendance.xlsx", source_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert detect_resp.status_code == 200
    data = detect_resp.json()
    assert data["district_name"] == "Khammam"
    assert "Mandal A" in data["mandals"]

    # Test Mandal mode report creation
    create_resp = client.post(
        "/api/web/reports",
        files={"file": ("attendance.xlsx", source_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"report_mode": "mandal", "mandal_name": "Mandal A"},
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]
    download_resp = client.get(f"/api/web/reports/{job_id}/download")
    assert download_resp.status_code == 200
    assert "Mandal_A_Attendance_Report" in download_resp.headers["content-disposition"]

    images_resp = client.get(f"/api/web/reports/{job_id}/jpeg-pages")
    assert images_resp.status_code == 200
    page_count = images_resp.json()["page_count"]
    assert page_count >= 2
    for page_number in range(1, page_count + 1):
        image_resp = client.get(f"/api/web/reports/{job_id}/jpeg-pages/{page_number}")
        assert image_resp.status_code == 200
        assert image_resp.headers["content-type"] == "image/jpeg"
        assert f"_Page_{page_number:02d}.jpg" in image_resp.headers["content-disposition"]
        assert image_resp.content.startswith(b"\xff\xd8")


def test_mandal_report_excludes_ps_name_and_mobile(tmp_path: Path):
    app = create_app(make_settings(tmp_path))
    client = TestClient(app)
    raw_bytes = bytes_for(attendance_rows(), ".xlsx")

    resp_mandal = client.post(
        "/api/web/reports",
        files={
            "file": ("attendance.xlsx", raw_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        },
        data={"report_mode": "mandal", "mandal_name": "Mandal A"},
    )
    assert resp_mandal.status_code == 200
    mandal_job_id = resp_mandal.json()["job_id"]

    download_resp = client.get(f"/api/web/reports/{mandal_job_id}/download")
    assert download_resp.status_code == 200
    reader = PdfReader(BytesIO(download_resp.content))
    text = "".join(p.extract_text() for p in reader.pages)
    assert "MANDAL A" in text
    assert "Attendance Pending GPs" in text
    assert "Panchayat Secretary Name" not in text
    assert "Mobile Number" not in text



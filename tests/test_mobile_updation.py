"""Unit and integration tests for the Updation of Mobile Numbers to Assessments module."""

from __future__ import annotations

import io
import openpyxl
from fastapi.testclient import TestClient

from app import app
from mobile_updation.service import (
    clean_asmt_no,
    generate_lookup_excel_workbook,
    generate_lookup_pdf_report,
    parse_demand_register_bytes,
    parse_updated_report_bytes,
    perform_pending_lookup,
    process_pending_mobile_assessments,
)

client = TestClient(app)


def _create_mock_html_xls_demand_register() -> bytes:
    """Creates a sample HTML-disguised .xls string as exported by Telangana e-Panchayat."""
    html = """
    <html>
    <head><title>Demand Register</title></head>
    <body>
    <div>
    <table border="1">
      <tr>
        <th>SL.No</th><th>ASMTNo</th><th>Old ASMT</th><th>House No</th><th>Owner Name</th><th>Father Name</th><th>MobileNo</th>
      </tr>
      <tr>
        <td>1</td><td>101</td><td>--</td><td>1-10</td><td>RAMA RAO</td><td>VENKATA</td><td>9876543210</td>
      </tr>
      <tr>
        <td>2</td><td>102</td><td>--</td><td>1-11</td><td>SITA DEVI</td><td>RAMA</td><td>9876543211</td>
      </tr>
      <tr>
        <td>3</td><td>103.0</td><td>--</td><td>1-12</td><td>KRISHNA MURTHY</td><td>NARAYANA</td><td></td>
      </tr>
      <tr>
        <td>4</td><td>104</td><td>--</td><td>1-13</td><td>LAKSHMI BAI</td><td>GOPAL</td><td></td>
      </tr>
      <tr>
        <td>TOTAL</td><td>4</td><td></td><td></td><td></td><td></td><td></td>
      </tr>
    </table>
    </div>
    </body>
    </html>
    """
    return html.encode("utf-8")


def _create_mock_xlsx_demand_register() -> bytes:
    """Creates a standard .xlsx Demand Register."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Demand"
    ws.append(["SL.No", "ASMTNo", "Old ASMT", "House No", "Owner Name", "Father Name", "MobileNo"])
    ws.append([1, 201, "--", "2-1", "VENKATESHWARLU", "SUBBA RAO", "9988776655"])
    ws.append([2, 202, "--", "2-2", "ANASUYA", "VENKAT", ""])
    ws.append([3, 203, "--", "2-3", "SRINIVAS", "RAMAIAH", ""])
    ws.append(["TOTAL", 3, "", "", "", "", ""])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _create_mock_updated_report_xlsx(updated_asmts: list[str]) -> bytes:
    """Creates a sample Mobile Numbers Updated Report .xlsx as exported by e-Panchayat."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Updated Report"

    # Metadata rows (1-5)
    ws.append(["Panchayat Raj & Rural Employment, Government of Telangana"])
    ws.append(["District : Khammam | Mandal : Madhira | Gram Panchayat : Allinagaram"])
    ws.append(["Report Date: 15/11/2026"])
    ws.append([])
    ws.append([])

    # Table Header at row 6
    ws.append(["S.No.", "Assessment Number", "Owner Name", "House Number", "Mobile Number"])
    for idx, asmt in enumerate(updated_asmts, 1):
        ws.append([idx, asmt, f"Owner {asmt}", f"H-{asmt}", f"980000000{idx}"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_clean_asmt_no():
    assert clean_asmt_no("101") == "101"
    assert clean_asmt_no("101.0") == "101"
    assert clean_asmt_no(101) == "101"
    assert clean_asmt_no(" 502 ") == "502"
    assert clean_asmt_no(None) == ""


def test_parse_html_disguised_xls_demand():
    data = _create_mock_html_xls_demand_register()
    records = parse_demand_register_bytes(data, "DemandRegister.xls")
    assert len(records) == 4
    asmts = [r["assessment_number"] for r in records]
    assert asmts == ["101", "102", "103", "104"]
    assert records[0]["owner_name"] == "RAMA RAO"
    assert records[0]["house_number"] == "1-10"


def test_parse_standard_xlsx_demand():
    data = _create_mock_xlsx_demand_register()
    records = parse_demand_register_bytes(data, "RNPDR26-27.xlsx")
    assert len(records) == 3
    asmts = [r["assessment_number"] for r in records]
    assert asmts == ["201", "202", "203"]
    assert records[0]["owner_name"] == "VENKATESHWARLU"


def test_parse_updated_report_metadata_and_asmts():
    data = _create_mock_updated_report_xlsx(["101", "102"])
    meta, updated_set, mob_map = parse_updated_report_bytes(data)

    assert meta["district"].strip() == "Khammam"
    assert meta["mandal"].strip() == "Madhira"
    assert meta["gram_panchayat"].strip() == "Allinagaram"
    assert updated_set == {"101", "102"}
    assert "101" in mob_map


def test_perform_pending_lookup():
    demand_records = [
        {"sl_no": 1, "asmt_clean": "101", "assessment_number": "101", "house_number": "1-1", "owner_name": "A", "demand_mobile": ""},
        {"sl_no": 2, "asmt_clean": "102", "assessment_number": "102", "house_number": "1-2", "owner_name": "B", "demand_mobile": ""},
        {"sl_no": 3, "asmt_clean": "103", "assessment_number": "103", "house_number": "1-3", "owner_name": "C", "demand_mobile": ""},
    ]
    updated_set = {"101"}
    asmt_to_mob = {"101": "9876543210"}

    pending, full_recon = perform_pending_lookup(demand_records, updated_set, asmt_to_mob)
    assert len(pending) == 2
    assert [p["assessment_number"] for p in pending] == ["102", "103"]
    assert len(full_recon) == 3
    assert full_recon[0]["status"] == "Updated"
    assert full_recon[1]["status"] == "Pending"
    assert full_recon[2]["status"] == "Pending"


def test_generate_lookup_excel_workbook():
    meta = {"district": "Khammam", "mandal": "Madhira", "gram_panchayat": "Allinagaram"}
    pending = [
        {"sl_no": 1, "assessment_number": "103", "house_number": "1-3", "owner_name": "C", "remarks": "Pending"},
    ]
    full = [
        {"sl_no": 1, "assessment_number": "101", "house_number": "1-1", "owner_name": "A", "demand_mobile": "", "updated_mobile": "99999", "status": "Updated"},
        {"sl_no": 2, "assessment_number": "103", "house_number": "1-3", "owner_name": "C", "demand_mobile": "", "updated_mobile": "", "status": "Pending"},
    ]

    buf = generate_lookup_excel_workbook(meta, pending, full, total_demand=2, total_updated=1)
    assert buf is not None
    wb = openpyxl.load_workbook(buf, data_only=False)
    assert "Pending Assessments" in wb.sheetnames
    assert "Full Lookup Reconciliation" in wb.sheetnames

    ws1 = wb["Pending Assessments"]
    # Check formula in footer
    footer_row = ws1.max_row
    assert ws1.cell(row=footer_row, column=2).value == "=COUNTA(B6:B6)"


def test_generate_lookup_pdf_report():
    meta = {"district": "Khammam", "mandal": "Madhira", "gram_panchayat": "Allinagaram"}
    pending = [
        {"sl_no": 1, "assessment_number": "103", "house_number": "1-3", "owner_name": "C", "remarks": "Pending"},
    ]
    pdf_buf = generate_lookup_pdf_report(meta, pending, total_demand=2, total_updated=1)
    raw = pdf_buf.getvalue()
    assert raw.startswith(b"%PDF-")


def test_api_pending_mobile_assessments_flow():
    # 1. Test HTML Page
    page_res = client.get("/reports/mobile-updation")
    assert page_res.status_code == 200
    assert "Pending Mobile Number Assessments (Lookup)" in page_res.text
    assert "Upload Demand Register" in page_res.text

    # 2. Test Post API
    demand_bytes = _create_mock_html_xls_demand_register()
    updated_bytes = _create_mock_updated_report_xlsx(["101", "102"])

    files = {
        "demand_file": ("Demand_Register.xls", demand_bytes, "application/vnd.ms-excel"),
        "updated_file": ("Updated_Report.xlsx", updated_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }

    res = client.post("/api/manual-reports/pending-mobile-assessments", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_demand"] == 4
    assert data["total_updated"] == 2
    assert data["total_pending"] == 2
    assert len(data["preview"]) == 2
    assert data["metadata"]["district"] == "Khammam"
    assert data["metadata"]["gram_panchayat"] == "Allinagaram"

    token = data["token"]
    assert token

    # 3. Test Download Excel
    dl_excel = client.get(f"/api/manual-reports/pending-mobile-assessments/download-excel?token={token}")
    assert dl_excel.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in dl_excel.headers["content-type"]
    assert "filename=" in dl_excel.headers["content-disposition"]

    # 4. Test Download PDF
    dl_pdf = client.get(f"/api/manual-reports/pending-mobile-assessments/download-pdf?token={token}")
    assert dl_pdf.status_code == 200
    assert dl_pdf.headers["content-type"] == "application/pdf"
    assert dl_pdf.content.startswith(b"%PDF-")

    # 5. Test Invalid Token Format (400) and Non-Existent Token (404)
    dl_malformed = client.get("/api/manual-reports/pending-mobile-assessments/download-excel?token=invalid-token")
    assert dl_malformed.status_code == 400

    dl_not_found = client.get(f"/api/manual-reports/pending-mobile-assessments/download-excel?token={'a' * 32}")
    assert dl_not_found.status_code == 404


def test_updated_report_never_reads_column_a_sno():
    """
    Critical regression test: Ensures Column B ('Assessment Number') is selected,
    and Column A ('S.No.') is NEVER used as the assessment lookup key.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["District: Khammam | Mandal: Raghunadhapalem | Gram Panchayat: Raghunadha Palem"])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([])
    # Header row at row 7
    ws.append(["S.No.", "Assessment Number", "Owner Name", "House Number", "Old Mobile", "New Mobile Number"])
    # 5 rows where S.No is 1..5, but Assessment Numbers are 2313..2317
    ws.append(["1", "2313.0", "Owner A", "1-1", "9000000001", "9000000001"])
    ws.append(["2", "2314", "Owner B", "1-2", "9000000002", "9000000002"])
    ws.append(["3", "2315", "Owner C", "1-3", "9000000003", "9000000003"])
    ws.append(["4", "2316.0", "Owner D", "1-4", "9000000004", "9000000004"])
    ws.append(["5", "2317", "Owner E", "1-5", "9000000005", "9000000005"])

    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    meta, updated_set, mob_map = parse_updated_report_bytes(data)

    # Must contain Assessment Numbers (Column B), NOT S.No. 1..5 (Column A)
    assert "2313" in updated_set
    assert "2314" in updated_set
    assert "2315" in updated_set
    assert "2316" in updated_set
    assert "2317" in updated_set
    assert "1" not in updated_set
    assert "2" not in updated_set
    assert "3" not in updated_set
    assert "4" not in updated_set
    assert "5" not in updated_set


def test_kpi_calculations_and_reconciliation_exact():
    """
    Verifies KPI calculations:
    - DEMAND REGISTER TOTAL = len(demand) (e.g. 2254)
    - UPDATED ASSESSMENTS = DEMAND REGISTER TOTAL - PENDING ASSESSMENTS (e.g. 2218)
    - PENDING ASSESSMENTS = DEMAND REGISTER TOTAL - UPDATED ASSESSMENTS (e.g. 36)
    - SEEDING COVERAGE = (UPDATED ASSESSMENTS / DEMAND REGISTER TOTAL) * 100 (e.g. 98.4%)
    """
    demand_records = [
        {"sl_no": i, "asmt_clean": str(i), "assessment_number": str(i), "house_number": f"1-{i}", "owner_name": f"Owner {i}", "demand_mobile": ""}
        for i in range(1, 2255)  # 2254 total demand assessments
    ]
    # Simulate updated assessments missing exactly 36 records: 1241, 1243, 1292, 1438, 1454, 1482, and 30 records >= 2219
    missing_asmts = {"1241", "1243", "1292", "1438", "1454", "1482"} | {str(x) for x in range(2219, 2249)}
    assert len(missing_asmts) == 36

    updated_asmts = {str(i) for i in range(1, 2255) if str(i) not in missing_asmts}
    assert len(updated_asmts) == 2218

    pending, full = perform_pending_lookup(demand_records, updated_asmts, {})
    total_demand = len(demand_records)
    total_pending = len(pending)
    total_updated = total_demand - total_pending
    coverage_pct = round((total_updated / total_demand * 100), 1)

    assert total_demand == 2254
    assert total_updated == 2218
    assert total_pending == 36
    assert coverage_pct == 98.4
    assert [p["assessment_number"] for p in pending[:6]] == ["1241", "1243", "1292", "1438", "1454", "1482"]


def test_real_raghunadhapalem_files_if_available():
    """
    If real user files DPM DR RNP.xls and DMP RNP UPDATED.xlsx exist on host,
    verifies exact 36 pending count, 2254 demand, 2218 updated, 98.4% coverage,
    and pending sequence starting with 1241, 1243, 1292, 1438, 1454, 1482, 2313...
    """
    from pathlib import Path
    dr_path = Path(r"C:\Users\dpmkm\Downloads\DPM DR RNP.xls")
    up_path = Path(r"C:\Users\dpmkm\Downloads\DMP RNP UPDATED.xlsx")

    if not dr_path.exists() or not up_path.exists():
        return  # Skip if environment does not have downloads

    dr_bytes = dr_path.read_bytes()
    up_bytes = up_path.read_bytes()

    res = process_pending_mobile_assessments(dr_bytes, "DPM DR RNP.xls", up_bytes, "DMP RNP UPDATED.xlsx")
    assert res["success"] is True
    assert res["total_demand"] == 2254
    assert res["total_updated"] == 2218
    assert res["total_pending"] == 36
    assert res["coverage_pct"] == 98.4
    assert len(res["preview"]) == 36

    pending_asmts = [p["assessment_number"] for p in res["preview"]]
    assert pending_asmts[:7] == ["1241", "1243", "1292", "1438", "1454", "1482", "2313"]


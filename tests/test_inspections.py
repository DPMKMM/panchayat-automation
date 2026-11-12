"""Comprehensive tests for Gram Panchayat Inspections Module (GM-R 39.1)."""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

os.environ["ENVIRONMENT"] = "development"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = ""

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import create_app
from core import firebase_app, session_manager
from inspections.aggregator import consolidate_inspection_files
from inspections.automation import resolve_week_slice
from inspections.models import SUPPORTED_DESIGNATIONS, compute_designation_target, get_designation_spec
from inspections.reports import (
    generate_inspections_csv,
    generate_inspections_excel,
    generate_inspections_pdf,
)


def _make_week_xls_html(rows: list[dict[str, str]]) -> bytes:
    """Create a realistic EPTS GM-R 39.1 HTML-table .xls export."""
    trs = "".join(
        "<tr>"
        f"<td>{idx}</td>"
        f"<td>{r.get('district', 'Khammam')}</td>"
        f"<td>{r.get('division', 'Khammam Division')}</td>"
        f"<td>{r.get('mandal', 'Bonakal')}</td>"
        f"<td>{r.get('gp', 'Allinagaram')}</td>"
        f"<td>{r.get('designation', 'MPO')}</td>"
        f"<td>{r.get('officer', 'Officer A')}</td>"
        f"<td>{r.get('date', '04-11-2026')}</td>"
        f"<td>{r.get('status', 'Submitted')}</td>"
        "</tr>"
        for idx, r in enumerate(rows, start=1)
    )
    html = (
        "<html><body><table>"
        "<tr><td colspan='9'>GM-R 39.1 MPO, DLPO, DPO Inspection Data Entry Report</td></tr>"
        "<tr><th>Sl.No</th><th>District Name</th><th>Division Name</th><th>Mandal Name</th>"
        "<th>Gram Panchayat Name</th><th>Designation</th><th>Officer Name</th>"
        "<th>Inspection Date</th><th>Final Submit Status</th></tr>"
        f"{trs}"
        "<tr><td colspan='8'>Total</td><td></td></tr>"
        "</table></body></html>"
    )
    return html.encode("utf-8")


def _console_login(client: TestClient, monkeypatch, tag: str = "insp"):
    from portal import router as portal_router

    ts = int(time.time() * 1000)
    fake_user = lambda tok: {
        "firebase_uid": f"fb_{tag}_{ts}",
        "gmail": f"{tag}_{ts}@gmail.com",
        "name": f"Officer {tag}",
        "profile_picture": "",
    }
    monkeypatch.setattr(firebase_app, "verify_firebase_id_token", fake_user)
    monkeypatch.setattr(portal_router, "verify_firebase_id_token", fake_user)
    res = client.post(
        "/api/auth/firebase-login",
        headers={"Host": "autoreports.panchayatautomation.in"},
        json={"id_token": f"tok_{tag}_{ts}"},
    )
    assert res.status_code == 200
    return res.json()["token"]


def test_designation_specs_targets_and_grouping_levels():
    assert set(SUPPORTED_DESIGNATIONS) == {"MPO", "MPDO", "DLPO", "DPO", "CEO", "Deputy CEO"}

    assert get_designation_spec("MPO")["group_label"] == "Mandal"
    assert get_designation_spec("MPDO")["group_label"] == "Mandal"
    assert get_designation_spec("DLPO")["group_label"] == "Division"
    assert get_designation_spec("DPO")["group_label"] == "District"
    assert get_designation_spec("CEO")["group_label"] == "District"
    assert get_designation_spec("Deputy CEO")["group_label"] == "District"

    # MPO Weekly 4 across 3 weeks = 12
    t_mpo, desc_mpo = compute_designation_target(
        "MPO",
        week_labels=[
            "02-11-2026 to 07-11-2026",
            "09-11-2026 to 14-11-2026",
            "16-11-2026 to 21-11-2026",
        ],
    )
    assert t_mpo == 12
    assert "Weekly 4 x 3 Week(s) = 12" in desc_mpo

    # DLPO Monthly 10 (within 1 calendar month = 10; spanning 2 months = 20)
    t_dlpo_1m, _ = compute_designation_target(
        "DLPO",
        week_labels=["02-11-2026 to 07-11-2026", "09-11-2026 to 14-11-2026"],
    )
    assert t_dlpo_1m == 10
    t_dlpo_2m, _ = compute_designation_target(
        "DLPO",
        week_labels=["19-10-2026 to 24-10-2026", "02-11-2026 to 07-11-2026"],
    )
    assert t_dlpo_2m == 20

    # DPO Monthly 5
    t_dpo, _ = compute_designation_target("DPO", week_labels=["02-11-2026 to 07-11-2026"])
    assert t_dpo == 5


def test_strict_submitted_filter_consolidation_pdf_excel_and_csv(tmp_path):
    w1_bytes = _make_week_xls_html([
        {"mandal": "Bonakal", "division": "Madhira", "gp": "GP1", "status": "Submitted"},
        {"mandal": "Bonakal", "division": "Madhira", "gp": "GP2", "status": "Submitted"},
        {"mandal": "Bonakal", "division": "Madhira", "gp": "GP3", "status": "Pending"},
        {"mandal": "Wyra", "division": "Wyra Div", "gp": "GP4", "status": "Draft"},
    ])
    w2_bytes = _make_week_xls_html([
        {"mandal": "Bonakal", "division": "Madhira", "gp": "GP5", "status": "Submitted"},
        {"mandal": "Wyra", "division": "Wyra Div", "gp": "GP6", "status": "Submitted"},
        {"mandal": "Wyra", "division": "Wyra Div", "gp": "GP7", "status": "Submitted"},
    ])

    report = consolidate_inspection_files(
        week_files=[
            {"week_label": "02-11-2026 to 07-11-2026", "filename": "w1.xls", "raw_bytes": w1_bytes},
            {"week_label": "09-11-2026 to 14-11-2026", "filename": "w2.xls", "raw_bytes": w2_bytes},
        ],
        designation="MPO",
        weeks_selected=["02-11-2026 to 07-11-2026", "09-11-2026 to 14-11-2026"],
    )

    # 2 weeks * 4 weekly target = 8
    assert report.target_per_unit == 8
    assert report.group_label == "Mandal"
    assert report.raw_row_count == 7
    assert report.submitted_row_count == 5
    assert report.excluded_non_submitted_count == 2  # Pending + Draft excluded strictly

    by_unit = {r.unit_name: r for r in report.abstract_rows}
    assert by_unit["Bonakal"].completed == 3
    assert by_unit["Bonakal"].balance == 5
    assert by_unit["Bonakal"].pct_completed == 37.5
    assert by_unit["Wyra"].completed == 2
    assert by_unit["Wyra"].balance == 6
    assert by_unit["Wyra"].pct_completed == 25.0

    # Verify PDF follows exact format: Sl No, Mandal, Target, Completed, Balance, % Completed
    pdf_path = tmp_path / "inspections_mpo.pdf"
    generate_inspections_pdf(report, pdf_path)
    pdf_txt = "\n".join(p.extract_text() for p in PdfReader(str(pdf_path)).pages)
    assert "GRAM PANCHAYAT INSPECTIONS ABSTRACT REPORT (GM-R 39.1)" in pdf_txt
    for hdr in ("Sl No", "Mandal", "Target", "Completed", "Balance", "% Completed"):
        assert hdr in pdf_txt
    assert "Bonakal" in pdf_txt
    assert "Wyra" in pdf_txt

    # Verify Excel sheets & headers
    xlsx_path = tmp_path / "inspections_mpo.xlsx"
    generate_inspections_excel(report, xlsx_path)
    wb = openpyxl.load_workbook(xlsx_path)
    assert "Inspection Abstract" in wb.sheetnames
    assert "Submitted Inspections Data" in wb.sheetnames
    assert [wb["Inspection Abstract"].cell(row=4, column=c).value for c in range(1, 7)] == [
        "Sl No", "Mandal", "Target", "Completed", "Balance", "% Completed"
    ]

    # Verify CSV headers
    csv_txt = generate_inspections_csv(report).decode("utf-8-sig")
    assert "Sl No,Mandal,Target,Completed,Balance,% Completed" in csv_txt

    # Verify DLPO uses Division and Monthly target 10
    dlpo_report = consolidate_inspection_files(
        week_files=[
            {"week_label": "02-11-2026 to 07-11-2026", "filename": "w1.xls", "raw_bytes": w1_bytes},
        ],
        designation="DLPO",
    )
    assert dlpo_report.group_label == "Division"
    assert dlpo_report.target_per_unit == 10
    dlpo_units = {r.unit_name: r for r in dlpo_report.abstract_rows}
    assert dlpo_units["Madhira"].completed == 2
    assert dlpo_units["Wyra Div"].completed == 0


def test_resolve_week_slice_handles_asc_and_desc_orders():
    from inspections.automation import _classify_selects

    # Exact 3-select GM-R 39.1 layout from portal UI: Inspected by, District (skip!), Select Week (YYYY-MM-DD to YYYY-MM-DD)
    desig_sel, week_sel = _classify_selects([
        {"idx": 0, "id": "ddlInspectedBy", "name": "ddlInspectedBy", "options": [{"value": "MPO", "text": "MPO"}, {"value": "DLPO", "text": "DLPO"}, {"value": "DPO", "text": "DPO"}]},
        {"idx": 1, "id": "ddlDistrict", "name": "ddlDistrict", "options": [{"value": "0", "text": "--Select--"}, {"value": "19", "text": "Khammam"}]},
        {"idx": 2, "id": "ddlWeek", "name": "ddlWeek", "options": [{"value": "1", "text": "2026-11-09 to 2026-11-14"}, {"value": "2", "text": "2026-11-02 to 2026-11-07"}]},
    ])
    assert desig_sel is not None and desig_sel["id"] == "ddlInspectedBy"
    assert week_sel is not None and week_sel["id"] == "ddlWeek"

    weeks = [
        {"value": "w3", "text": "2026-11-16 to 2026-11-21"},
        {"value": "w2", "text": "2026-11-09 to 2026-11-14"},
        {"value": "w1", "text": "2026-11-02 to 2026-11-07"},
    ]
    sliced = resolve_week_slice(weeks, from_week="w1", to_week="w3")
    assert len(sliced) == 3
    assert [s["value"] for s in sliced] == ["w3", "w2", "w1"]


def test_inspections_api_rbac_session_isolation_live_and_upload(monkeypatch):
    from inspections import service as insp_service

    client = TestClient(create_app())

    # 1. Portal shell upgrades card from Upcoming to Live and wires GM-R 39.1 station
    shell_html = client.get("/").text
    assert 'id="card-console-gp-inspections"' in shell_html
    assert "openGpInspectionsStation()" in shell_html
    assert 'id="insp-designation"' in shell_html
    assert 'id="insp-from-week"' in shell_html
    assert 'id="insp-to-week"' in shell_html
    assert "KHAMMAM_INSPECTIONS_DATA" not in client.get("/static/js/console.js?v=20").text

    # 2. Unauthenticated requests blocked (401/403)
    assert client.get("/api/inspections/weeks").status_code in (401, 403)
    assert client.post("/api/inspections/generate", data={"designation": "MPO"}).status_code in (401, 403)
    assert client.get(
        "/api/inspections/download-pdf",
        headers={"Host": "autoreports.panchayatautomation.in"},
    ).status_code in (401, 403)
    assert client.post(
        "/api/inspections/upload-consolidate",
        headers={"Host": "autoreports.panchayatautomation.in"},
    ).status_code in (401, 403)

    # 3. Signed-in Console officer uploads weekly Excel files for consolidation & downloads PDF/Excel/CSV
    token = _console_login(client, monkeypatch, "insp_con")
    sid = "sess_insp_01"
    w1 = _make_week_xls_html([
        {"mandal": "Kalluru", "gp": "GP-1", "status": "Submitted"},
        {"mandal": "Kalluru", "gp": "GP-2", "status": "Not Submitted"},
    ])
    w2 = _make_week_xls_html([
        {"mandal": "Kalluru", "gp": "GP-3", "status": "Submitted"},
    ])

    up_res = client.post(
        "/api/inspections/upload-consolidate",
        headers={
            "Host": "autoreports.panchayatautomation.in",
            "Authorization": f"Bearer {token}",
            "X-Session-ID": sid,
        },
        files=[
            ("files", ("week1.xls", w1, "application/vnd.ms-excel")),
            ("files", ("week2.xls", w2, "application/vnd.ms-excel")),
        ],
        data={"designation": "MPO", "from_week": "02-11-2026 to 07-11-2026", "to_week": "09-11-2026 to 14-11-2026"},
    )
    assert up_res.status_code == 200
    body = up_res.json()
    assert body["designation"] == "MPO"
    assert body["group_label"] == "Mandal"
    assert body["totals"]["completed"] == 2
    assert body["totals"]["target"] == 8
    assert body["totals"]["balance"] == 6
    assert body["totals"]["excluded_non_submitted_count"] == 1

    # Different session must NOT see session A's inspection report
    other_data = client.get(
        "/api/inspections/data",
        headers={
            "Host": "autoreports.panchayatautomation.in",
            "Authorization": f"Bearer {token}",
            "X-Session-ID": "sess_insp_other",
        },
    )
    assert other_data.status_code == 200
    assert other_data.json()["generated"] is False

    # Same session downloads PDF, Excel, CSV
    pdf_dl = client.get(
        "/api/inspections/download-pdf",
        headers={"Host": "autoreports.panchayatautomation.in", "Authorization": f"Bearer {token}", "X-Session-ID": sid},
    )
    assert pdf_dl.status_code == 200 and pdf_dl.content.startswith(b"%PDF")

    xl_dl = client.get(
        "/api/inspections/download-excel",
        headers={"Host": "autoreports.panchayatautomation.in", "Authorization": f"Bearer {token}", "X-Session-ID": sid},
    )
    assert xl_dl.status_code == 200 and xl_dl.content[:2] == b"PK"

    csv_dl = client.get(
        "/api/inspections/download-csv",
        headers={"Host": "autoreports.panchayatautomation.in", "Authorization": f"Bearer {token}", "X-Session-ID": sid},
    )
    assert csv_dl.status_code == 200 and "Kalluru" in csv_dl.text

    # 4. Live Playwright automation endpoint (/api/inspections/generate & /weeks) executes cleanly with mocked session bot
    sess = session_manager.get_or_create_session(sid)
    sess["status"] = "authenticated"
    sess["mode"] = "live_portal"
    sess["district_name"] = "Khammam"
    sess["user_level"] = "district"

    class _MockBot:
        class _Page:
            def is_closed(self):
                return False
            url = "https://epanchayat.telangana.gov.in/deptLoginVerified"
        page = _Page()

    sess["bot"] = _MockBot()
    monkeypatch.setattr("dsr.service._is_bot_alive", lambda b: True)
    monkeypatch.setattr("dsr.service.run_in_session_thread", lambda s, fn, *a, **kw: fn(*a, **kw))
    monkeypatch.setattr(insp_service, "run_in_session_thread", lambda s, fn, *a, **kw: fn(*a, **kw))
    monkeypatch.setattr(
        insp_service,
        "fetch_inspection_metadata",
        lambda bot, designation=None: {
            "designations": list(SUPPORTED_DESIGNATIONS),
            "weeks": [{"value": "02-11-2026 to 07-11-2026", "text": "02-11-2026 to 07-11-2026"}],
            "selected_designation": designation or "MPO",
        },
    )
    monkeypatch.setattr(
        insp_service,
        "download_inspection_weeks",
        lambda bot, designation, from_week, to_week, downloads_dir: (
            [{"week_label": "02-11-2026 to 07-11-2026", "filename": "live.xls", "raw_bytes": w1, "status": "downloaded"}],
            ["02-11-2026 to 07-11-2026"],
        ),
    )

    wks_res = client.get(
        "/api/inspections/weeks?designation=DPO",
        headers={"Host": "autoreports.panchayatautomation.in", "Authorization": f"Bearer {token}", "X-Session-ID": sid},
    )
    assert wks_res.status_code == 200 and wks_res.json()["weeks"][0]["value"] == "02-11-2026 to 07-11-2026"

    gen_res = client.post(
        "/api/inspections/generate",
        headers={"Host": "autoreports.panchayatautomation.in", "Authorization": f"Bearer {token}", "X-Session-ID": sid},
        data={"designation": "DPO", "from_week": "02-11-2026 to 07-11-2026", "to_week": "02-11-2026 to 07-11-2026"},
    )
    assert gen_res.status_code == 200
    gdata = gen_res.json()
    assert gdata["designation"] == "DPO"
    assert gdata["group_label"] == "District"
    assert gdata["totals"]["target"] == 5
    assert gdata["totals"]["completed"] == 1
    assert gdata["totals"]["balance"] == 4


def test_playwright_gmr391_fetch_weeks_real_browser(monkeypatch):
    from playwright.sync_api import sync_playwright
    from inspections.automation import _clean_week_options, fetch_inspection_metadata

    # Verify _clean_week_options preserves date strings even when <option value=""> omits explicit value
    cleaned = _clean_week_options({
        "options": [
            {"value": "0", "text": "--Select--"},
            {"value": "", "text": "2026-11-09 to 2026-11-14"},
            {"value": "2026-11-02 to 2026-11-07", "text": "2026-11-02 to 2026-11-07"},
        ]
    })
    assert [w["text"] for w in cleaned] == ["2026-11-09 to 2026-11-14", "2026-11-02 to 2026-11-07"]

    report_html = """
    <html><body>
      <h2>MPO Inspection Data Entry Report</h2>
      <label>Inspected by :</label>
      <select id="ddlDesig" onchange="updateWeeks()">
        <option value="MPO" selected>MPO</option>
        <option value="DLPO">DLPO</option>
        <option value="DPO">DPO</option>
      </select>
      <label>District :</label>
      <select id="ddlDistrict"><option value="Khammam">Khammam</option></select>
      <label>Select Week:</label>
      <select id="ddlWeek">
        <option value="0">--Select--</option>
        <option value="2026-11-09 to 2026-11-14">2026-11-09 to 2026-11-14</option>
        <option value="2026-11-02 to 2026-11-07">2026-11-02 to 2026-11-07</option>
      </select>
      <script>
        function updateWeeks() {
          const d = document.getElementById('ddlDesig').value;
          const w = document.getElementById('ddlWeek');
          if (d === 'DLPO') {
            w.innerHTML = '<option value="0">--Select--</option><option value="2026-11-02 to 2026-11-07">2026-11-02 to 2026-11-07</option>';
          }
        }
      </script>
    </body></html>
    """
    menu_html = """
    <html><body>
      <input type="search" id="menuSearch" placeholder="Search" oninput="
        const q = this.value.toLowerCase();
        document.getElementById('card39').style.display = 'gm-r 39.'.includes(q) || !q ? 'block' : 'none';
      " />
      <div id="card39">
        <a href="javascript:void(0)" onclick="document.getElementById('layer39').style.display='block'">GM-R 39. MPO,DLPO,DPO Inspection Data Entry Report</a>
        <div id="layer39" style="display:none">
          <div>REPORTS LAYER</div>
          <a href="https://epanchayat.test/gmr391">GM-R 39.1 MPO,DLPO,DPO Inspection Data Entry Report</a>
        </div>
      </div>
    </body></html>
    """
    shell_html = """
    <html><body>
      <nav>
        <a href="https://epanchayat.test/menu" target="my-iframe">GP Monitoring</a>
        <a href="javascript:void(0)">GP Monitoring New</a>
      </nav>
      <iframe name="my-iframe" id="my-iframe" src="about:blank"></iframe>
    </body></html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def _handle_route(route):
            u = route.request.url
            if u.endswith("/shell"):
                route.fulfill(status=200, content_type="text/html", body=shell_html)
            elif u.endswith("/menu"):
                route.fulfill(status=200, content_type="text/html", body=menu_html)
            elif u.endswith("/gmr391"):
                route.fulfill(status=200, content_type="text/html", body=report_html)
            else:
                route.abort()

        page.route("https://epanchayat.test/**", _handle_route)
        page.goto("https://epanchayat.test/shell")
        monkeypatch.setattr(
            "inspections.automation._click_gp_monitoring_top_menu",
            lambda b: page.locator("xpath=//a[normalize-space(.)='GP Monitoring']").first.click(),
        )

        class _Bot:
            def __init__(self, pg):
                self.page = pg
            def select_menu(self, name):
                self.page.locator(f"xpath=//a[normalize-space(.)='{name}']").first.click()

        bot = _Bot(page)
        meta_mpo = fetch_inspection_metadata(bot, designation="MPO")
        assert [w["text"] for w in meta_mpo["weeks"]] == [
            "2026-11-09 to 2026-11-14",
            "2026-11-02 to 2026-11-07",
        ]

        meta_dlpo = fetch_inspection_metadata(bot, designation="DLPO")
        assert [w["text"] for w in meta_dlpo["weeks"]] == ["2026-11-02 to 2026-11-07"]
        assert meta_dlpo["selected_designation"] == "DLPO"
        browser.close()


def test_exact_26col_epts_html_banner_and_upload_consolidation(tmp_path):
    """Verify exact 26-column EPTS HTML .xls export (with 2-row colspan=26 banner) parses and consolidates cleanly."""
    from inspections.aggregator import consolidate_inspection_files

    epts_html_w1 = """<div style='border:1px;width:1000px;'>
    <table cellspacing='0' border='0px' width='1000px' cellpadding='0'>
      <tr><td colspan='26' align='center'>Telangana State </td></tr>
      <tr><td colspan='26' align='center'>Inspection Data Entry Report</td></tr>
    </table>
    <table Width='1000px' cellspacing="0" rules="all" border="1">
      <tr>
        <th>S.No</th><th>District Name</th><th>Division Name</th><th>Mandal Name</th>
        <th>Mandal LGD Code</th><th>Panchayat Name</th><th>Panchayat Id</th>
        <th>Attendence Date-Time</th><th>Inspection From Date</th><th>Inspection To Date</th>
        <th>Date of Inspection</th><th>Roads</th><th>Drains</th><th>Street Lights</th>
        <th>House Holds Responses</th><th>Cleanliness of Government Institutions</th>
        <th>Crematorium</th><th>Segregation</th><th>Nursery</th><th>Plantation</th>
        <th>Approvals &amp; Transactions</th><th>Financial Transactions</th>
        <th>Verification of Cheques</th><th>Administration &amp; Records</th>
        <th>Inspection Report</th><th>Final Submit Status</th>
      </tr>
      <tr>
        <td>1</td><td>Khammam</td><td>KHAMMAM</td><td>Bonakal</td><td>5057</td><td>Allapadu</td><td>202181</td>
        <td>&nbsp;</td><td>2026-11-02</td><td>2026-11-07</td><td>&nbsp;</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Submitted</td>
      </tr>
      <tr>
        <td>2</td><td>Khammam</td><td>KHAMMAM</td><td>Bonakal</td><td>5057</td><td>Janakipuram</td><td>202189</td>
        <td>05-Nov-2026 15:52</td><td>2026-11-02</td><td>2026-11-07</td><td>2026-11-05</td>
        <td>Entered</td><td>Entered</td><td>Entered</td><td>Entered</td><td>Entered</td>
        <td>Entered</td><td>Entered</td><td>Not Entered</td><td>Entered</td><td>Entered</td>
        <td>Entered</td><td>Entered</td><td>Not Entered</td><td>Entered</td><td>Submitted</td>
      </tr>
      <tr>
        <td>3</td><td>Khammam</td><td>KALLUR</td><td>Enkoor</td><td>5065</td><td>Repallewada</td><td>202329</td>
        <td>06-Nov-2026 10:07</td><td>2026-11-02</td><td>2026-11-07</td><td>2026-11-06</td>
        <td>Entered</td><td>Entered</td><td>Entered</td><td>Entered</td><td>Entered</td>
        <td>Entered</td><td>Entered</td><td>Not Entered</td><td>Entered</td><td>Entered</td>
        <td>Entered</td><td>Entered</td><td>Not Entered</td><td>Entered</td><td>Submitted</td>
      </tr>
      <tr>
        <td>4</td><td>Khammam</td><td>KHAMMAM</td><td>Kamepally</td><td>5070</td><td>Kamepalli</td><td>202389</td>
        <td>&nbsp;</td><td>2026-11-02</td><td>2026-11-07</td><td>&nbsp;</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td>
        <td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Entered</td><td>Not Submitted</td>
      </tr>
    </table></div>""".encode("utf-8")

    # Even with ONLY 1 data row in Week 2 (table shape 2x26 tied with banner table 2x26), banner must NOT win!
    epts_html_w2 = epts_html_w1.replace(b"2026-11-02", b"2026-11-09").replace(b"2026-11-07", b"2026-11-14")

    rep_mpo = consolidate_inspection_files(
        [
            {"week_label": "", "filename": "report1.xls", "raw_bytes": epts_html_w1},
            {"week_label": "", "filename": "report2.xls", "raw_bytes": epts_html_w2},
        ],
        designation="MPO",
    )
    assert rep_mpo.from_week == "2026-11-02 to 2026-11-07"
    assert rep_mpo.to_week == "2026-11-09 to 2026-11-14"
    assert rep_mpo.target_per_unit == 8  # Weekly 4 x 2 weeks
    by_m = {r.unit_name: r for r in rep_mpo.abstract_rows}
    assert by_m["Kamepally"].completed == 0 and by_m["Kamepally"].balance == 8
    assert by_m["Bonakal"].completed == 2 and by_m["Bonakal"].balance == 6
    assert by_m["Enkoor"].completed == 2 and by_m["Enkoor"].balance == 6
    assert rep_mpo.submitted_records[0].checklist_entered == "12/14 Entered"
    assert rep_mpo.submitted_records[0].inspection_date == "2026-11-05"

    # DLPO division grouping (Khammam vs Kallur divisions)
    rep_dlpo = consolidate_inspection_files(
        [{"week_label": "", "filename": "report1.xls", "raw_bytes": epts_html_w1}],
        designation="DLPO",
    )
    by_div = {r.unit_name: r for r in rep_dlpo.abstract_rows}
    assert set(by_div.keys()) == {"Khammam", "Kallur"}
    assert by_div["Khammam"].target == 10 and by_div["Khammam"].completed == 1
    assert by_div["Kallur"].target == 10 and by_div["Kallur"].completed == 1

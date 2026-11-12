"""Unit and API Integration Tests for MAS Consolidated Reporting (Zero Duplicate Login)."""

from __future__ import annotations

import ast
import io
import time
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import create_app
from core.branding import PLATFORM_NAME, TAGLINE
from mas import automation as mas_automation
from mas import service as mas_service
from mas.models import ALL_18_MODULES, MOD_NAMES_524
from mas.pdf_generator import (
    CLR_GREEN_TXT,
    CLR_RED_TXT,
    _completion_color,
    compute_mandal_abstract_table_layout,
    generate_mas_consolidated_pdf,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
app = create_app()
client = TestClient(app)


def _console_login(test_client: TestClient, monkeypatch, suffix: str) -> dict:
    email = f"mas_officer_{suffix}@gmail.com"
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": f"fb_mas_{suffix}",
            "gmail": email,
            "name": f"MAS Officer {suffix}",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    res = test_client.post(
        "/api/auth/firebase-login",
        headers={"Host": "reports.panchayatautomation.in"},
        json={"id_token": f"tok_mas_{suffix}"},
    )
    assert res.status_code == 200
    return res.json()


class _DummyPage:
    def is_closed(self) -> bool:
        return False


class _DummyBot:
    def __init__(self) -> None:
        self.page = _DummyPage()


def _build_synthetic_live_scrape(n_mandals: int = 2) -> tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Create realistic synthetic 17-module GM-R 5.24 + GM-R 5.23 data without external files."""
    mandals_524: List[Dict[str, Any]] = []
    births_523: Dict[str, Any] = {}

    for idx in range(1, n_mandals + 1):
        name = "Bonakal" if idx == 1 else ("Mudigonda" if idx == 2 else f"Mandal_{idx}")
        n_gps = 22
        mods: Dict[str, Dict[str, Any]] = {}
        total_not_entered = 0

        for m_name in MOD_NAMES_524:
            if idx == 1 and m_name == "Gram Sabha":
                ent, not_ent = 21, 1
            elif idx == 2 and m_name == "Payment of Electricity":
                # Only CC Charges pending in Mandal 2 so excluding CC Charges lifts it to 100%
                ent, not_ent = 20, 2
            else:
                ent, not_ent = n_gps, 0
            denom = ent + not_ent
            mods[m_name] = {
                "entered": ent,
                "not_entered": not_ent,
                "pct": round((ent / denom) * 100, 2) if denom > 0 else 100.0,
                "formatted_compact": f"{not_ent} / {ent}",
            }
            total_not_entered += not_ent

        mandals_524.append(
            {
                "sno": idx,
                "mandal_name": name,
                "ctl": f"ctl{idx + 1:02d}",
                "no_of_gps": n_gps,
                "has_pendency": total_not_entered > 0,
                "total_not_entered": total_not_entered,
                "modules": mods,
            }
        )
        births_523[name] = {
            "sno": idx,
            "ctl": f"ctl{idx + 1:02d}",
            "total_gps": n_gps,
            "registered_gps": n_gps,
            "balance_gps": 0,
            "births_as_per_register": 10,
            "births_entered": 10,
            "births_balance": 0,
            "pct": 100.0,
            "has_pendency": False,
        }

    # Build raw 34-value GP drilldown array for pending Mandal 1 (only Gram Sabha pending, MGNRE 0/0 N/A)
    values_bonakal_gp1: List[str] = []
    for mod_name in MOD_NAMES_524:
        if mod_name == "Gram Sabha":
            values_bonakal_gp1.extend(["0", "1"])  # Pending
        elif mod_name == "MGNRE Bank Balance":
            values_bonakal_gp1.extend(["0", "0"])  # N/A (must NOT trigger Pending)
        else:
            values_bonakal_gp1.extend(["1", "0"])  # Entered

    pending_gps_map = {
        "Bonakal": [{"sno": 1, "gpName": "Bonakal_GP_1", "values": values_bonakal_gp1}],
        "Mudigonda": [],
    }
    return mandals_524, births_523, pending_gps_map


def _install_mock_live_session(monkeypatch, tmp_path, suffix: str = "unit"):
    from dsr import service as automation_service

    monkeypatch.setattr("mas.automation.get_reports_dir", lambda: tmp_path)
    monkeypatch.setattr("mas.service.get_reports_dir", lambda: tmp_path)
    monkeypatch.setattr("mas.router.get_reports_dir", lambda: tmp_path)

    mandals_524, births_523, pending_gps_map = _build_synthetic_live_scrape(2)
    dummy_frame = object()

    monkeypatch.setattr(mas_automation, "_open_gmr_report_frame", lambda page, report_num="5.24": dummy_frame)
    monkeypatch.setattr(mas_automation, "_submit_month_year_and_wait_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(mas_automation, "scrape_mandal_abstract_524", lambda page, month, year: (mandals_524, dummy_frame))
    monkeypatch.setattr(
        mas_automation,
        "scrape_mandal_births_523",
        lambda page, month, year, include_gp_drilldown=True: (births_523, {}),
    )
    monkeypatch.setattr(
        mas_automation,
        "scrape_pending_gps_data",
        lambda frame, pending_mandals, month, year: {
            m["mandal_name"]: pending_gps_map.get(m["mandal_name"], []) for m in pending_mandals
        },
    )

    sid = f"sid_mas_live_{suffix}"
    sess = automation_service.get_or_create_session(sid)
    sess["authenticated"] = True
    sess["status"] = "authenticated"
    sess["user_id"] = "DPOA3698"
    sess["district_name"] = "Khammam"
    sess["bot"] = _DummyBot()
    return sid, automation_service, sess


def test_mas_no_duplicate_browser_or_login_in_source():
    """STRICT ZERO-DUPLICATE-LOGIN RULE: mas/ must never launch Playwright browsers or login flows."""
    mas_dir = ROOT_DIR / "mas"
    assert mas_dir.is_dir()

    forbidden_tokens = ("sync_playwright", "async_playwright", "launch_persistent_context", "start_server_login")
    for py_file in sorted(mas_dir.glob("*.py")):
        src = py_file.read_text(encoding="utf-8")
        ast.parse(src, filename=str(py_file))
        for tok in forbidden_tokens:
            assert tok not in src, f"Forbidden browser/login launch token '{tok}' found in {py_file.name}"

    assert (mas_dir / "xpaths.py").is_file()
    assert (mas_dir / "models.py").is_file()
    assert (mas_dir / "automation.py").is_file()
    assert (mas_dir / "pdf_generator.py").is_file()
    assert (mas_dir / "excel_generator.py").is_file()
    assert (mas_dir / "service.py").is_file()
    assert (mas_dir / "views.py").is_file()
    assert (mas_dir / "router.py").is_file()


def test_mas_18_modules_join_and_exclusion_math():
    """Verify 18-module catalog, CC Charges alias exclusion, and 17 vs 18 denominator calculation."""
    mods = mas_service.get_available_mas_modules()
    assert len(mods) == 18
    assert len(ALL_18_MODULES) == 18
    assert any(m["id"] == "Payment of Electricity" and m["is_cc_charges"] for m in mods)

    sample_gmr_524 = {
        "gram_panchayats": [
            {
                "Unique_Key": "BONAKAL_RAVIPADU",
                "Mandal": "Bonakal",
                "GP_SNo": 1,
                "Gram_Panchayat": "Ravipadu",
                "MAS_Nursery": "Completed",
                "MAS_Plantation": "Completed",
                "MAS_Vaikunta Dhamam": "Completed",
                "MAS_Dump Yard": "Completed",
                "MAS_Water Supply": "Completed",
                "MAS_GP Meeting": "Completed",
                "MAS_Gram Sabha": "Completed",
                "MAS_Record Maintenance": "Completed",
                "MAS_Approvals & Certificates": "Completed",
                "MAS_Deaths": "Completed",
                "MAS_Receipts": "Completed",
                "MAS_Expenditure": "Pending",
                "MAS_Cheque Details": "Completed",
                "MAS_Salary Details": "Completed",
                "MAS_VWSC & EGS Balance": "Completed",
                "MAS_MGNREGA Balance": "Completed",
                "MAS_Electricity Payment": "Pending",
            }
        ]
    }
    births_lookup = {
        "BONAKAL_RAVIPADU": {"births_data_entered": "Entered", "balance_gps_data_to_enter": 0, "balance_to_be_entered": 0}
    }

    # With CC Charges + Expenditure excluded -> 16 included -> 100% compliant
    joined, action_list, _ = mas_service.join_reports(
        sample_gmr_524, births_lookup, excluded_modules=["CC Charges", "Expenditure"]
    )
    assert len(joined) == 1
    assert joined[0]["Total_Activities"] == 16
    assert joined[0]["Activities_Completed"] == 16
    assert joined[0]["Completion_Rate"] == 100.0
    assert action_list == []

    # With zero exclusions -> 18 included -> 2 pending
    joined_all, action_all, _ = mas_service.join_reports(sample_gmr_524, births_lookup, excluded_modules=[])
    assert joined_all[0]["Total_Activities"] == 18
    assert joined_all[0]["Activities_Completed"] == 16
    assert len(action_all) == 1
    assert "Expenditure" in action_all[0]["Pending_Modules"]
    assert "Payment of Electricity" in action_all[0]["Pending_Modules"]


def test_mas_pdf_and_excel_branding_and_dynamic_layout(tmp_path):
    """Verify 1-page Page-1 dynamic fit for 20 & 35 mandals + canonical platform branding."""
    layout_20 = compute_mandal_abstract_table_layout(20)
    layout_35 = compute_mandal_abstract_table_layout(35)
    assert sum(layout_20["row_heights"]) <= 430.0
    assert sum(layout_35["row_heights"]) <= 430.0

    mandals_524, _, _ = _build_synthetic_live_scrape(20)
    abs_rows, tot_row, norm_excl = mas_service.build_full_18_module_abstract(
        [], excluded_modules=["CC Charges"], scraped_mandal_abstract=mandals_524
    )
    assert len(abs_rows) == 20
    assert norm_excl == ["Payment of Electricity"]
    assert tot_row["included_modules_count"] == 17

    pdf_out = tmp_path / "mas_test.pdf"
    generate_mas_consolidated_pdf(
        mandals_abstract=abs_rows,
        total_row=tot_row,
        pending_action_list=[],
        excluded_modules=norm_excl,
        output_path=pdf_out,
        month="October",
        year=2026,
        district_name="Khammam",
        include_gp_data=True,
    )
    reader = PdfReader(str(pdf_out))
    assert len(reader.pages) == 2
    full_txt = "\n".join(p.extract_text() for p in reader.pages)
    assert PLATFORM_NAME in full_txt
    assert "e-Panchayat Performance System" not in full_txt
    assert "Cell Legend" not in full_txt
    assert "Formula: Sum(Updated)" not in full_txt
    assert "Excluded from %:" not in full_txt
    assert _completion_color(100.0) == CLR_GREEN_TXT
    assert _completion_color(99.82) == CLR_RED_TXT

    mas_page = client.get("/reports/mas").text
    assert "const pctColor = hasPending ? '#dc2626' : '#059669';" in mas_page
    assert "const mandalColor = hasPending ? '#dc2626' : '#0f172a';" in mas_page
    assert "MAS_SHORT_HEADERS" in mas_page
    assert "Not / Upd" in mas_page


def test_mas_api_security_zero_duplicate_login_and_downloads(monkeypatch, tmp_path):
    """End-to-end API verification: Stage-1 + Stage-2 gates, zero duplicate login, downloads & isolation."""
    ts = int(time.time() * 1000)

    # 1. Console host without Firebase login -> 401
    anon = TestClient(app)
    for ep in ("/api/reports/mas-consolidated/modules", "/api/mas/modules"):
        assert anon.get(ep, headers={"Host": "reports.panchayatautomation.in"}).status_code == 401

    # 2. Portal-only login rejected with 403 on MAS endpoints
    portal_only = TestClient(app)
    monkeypatch.setattr(
        "portal.router.verify_firebase_id_token",
        lambda tok: {
            "firebase_uid": f"fb_p_{ts}",
            "gmail": f"p_{ts}@gmail.com",
            "name": "Portal User",
            "profile_picture": "",
            "sign_in_provider": "google.com",
            "email_verified": True,
        },
    )
    portal_only.post("/api/auth/firebase-login", headers={"Host": "panchayatautomation.in"}, json={"id_token": f"tok_p_{ts}"})
    assert portal_only.get("/api/reports/mas-consolidated/modules", headers={"Host": "reports.panchayatautomation.in"}).status_code == 403
    assert portal_only.post("/api/mas/generate", headers={"Host": "reports.panchayatautomation.in"}).status_code == 403

    # 3. Console Firebase login WITHOUT Stage-2 Dept Login -> 401 + X-Dept-Auth-Required: true
    c = TestClient(app)
    _console_login(c, monkeypatch, f"sec_{ts}")
    no_dept_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": f"nodept_{ts}"}
    for gen_ep in ("/api/reports/mas-consolidated/generate", "/api/mas/generate", "/api/MAS/generate"):
        r_unauth = c.post(gen_ep, headers=no_dept_hdrs)
        assert r_unauth.status_code == 401
        assert r_unauth.headers.get("X-Dept-Auth-Required") == "true"

    # 4. Pre-generation download -> 404 even when Dept session active
    sid, automation_service, _ = _install_mock_live_session(monkeypatch, tmp_path, str(ts))
    auth_hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}
    try:
        pre_dl = c.get("/api/reports/mas-consolidated/download/excel", headers=auth_hdrs)
        assert pre_dl.status_code == 404

        # 5. Live generation reuses existing session bot (Zero Duplicate Login)
        gen_resp = c.post(
            "/api/reports/mas-consolidated/generate",
            headers=auth_hdrs,
            json={"month": "October", "year": 2026, "excluded_modules": ["CC Charges"], "report_type": "abstract_and_gp"},
        )
        assert gen_resp.status_code == 200
        body = gen_resp.json()
        assert body["success"] is True
        assert body["status"] == "success"
        assert body["data_source"] == "live_two_stage_webscrape"
        assert body["included_modules_count"] == 17
        assert body["total_mandals"] == 2
        # Mudigonda becomes 100% compliant when CC Charges excluded
        mud = next(m for m in body["mandals"] if m["Mandal Name"] == "Mudigonda")
        assert mud["Overall % Entered"] == 100.0
        # MGNRE 0/0 N/A must NOT appear in Pending_Modules
        assert body["pending_gps_count"] == 1
        assert body["pending_action_list"][0]["Pending_Modules"] == "Gram Sabha"

        # Verify Step 2 alias /api/MAS/generate (form payload compatibility)
        alias_resp = c.post(
            "/api/MAS/generate",
            headers=auth_hdrs,
            data={"financial_year": "2026", "month": "October", "report_type": "abstract_only"},
        )
        assert alias_resp.status_code == 200
        assert alias_resp.json()["include_gp_data"] is False
        assert alias_resp.json()["pending_action_list"] == []

        # Re-run abstract_and_gp to produce full PDF + all deliverables and test downloads
        gen2 = c.post(
            "/api/mas/generate",
            headers=auth_hdrs,
            json={"month": "October", "year": 2026, "excluded_modules": [], "report_type": "abstract_and_gp"},
        )
        assert gen2.status_code == 200
        assert gen2.json()["included_modules_count"] == 18

        for ftype in ("excel", "pdf", "abstract_pdf", "compact_csv", "full_csv", "pending_csv", "json", "markdown"):
            dl = c.get(f"/api/reports/mas-consolidated/download/{ftype}", headers=auth_hdrs)
            assert dl.status_code == 200, f"Download failed for {ftype}"
            assert len(dl.content) > 0
            if ftype == "excel":
                wb = openpyxl.load_workbook(io.BytesIO(dl.content))
                assert wb.properties.creator == PLATFORM_NAME
                assert wb.properties.subject == TAGLINE
                assert "Mandal_Abstract" in wb.sheetnames
                assert "Methodology_And_Exclusions" in wb.sheetnames
                ws_abs = wb["Mandal_Abstract"]
                # Row 4 (Bonakal, has pending Gram Sabha -> < 100%) uses red text for Mandal Name & Overall %
                assert "B91C1C" in str(ws_abs["B4"].font.color.rgb)
                assert "B91C1C" in str(ws_abs["D4"].font.color.rgb)

        # Unrelated session cannot download sid's files
        other = c.get(
            "/api/reports/mas-consolidated/download/pdf",
            headers={"Host": "reports.panchayatautomation.in", "X-Session-ID": f"other_{ts}"},
        )
        assert other.status_code == 401
    finally:
        automation_service._sessions.pop(sid, None)


def test_mas_strict_live_expiry_and_error_handling(monkeypatch, tmp_path):
    """Verify upstream browser closure marks session expired (401) and scrape errors return 502."""
    from dsr import service as automation_service

    ts = int(time.time() * 1000)
    c = TestClient(app)
    _console_login(c, monkeypatch, f"err_{ts}")

    sid = f"sid_mas_exp_{ts}"
    sess = automation_service.get_or_create_session(sid)
    sess["authenticated"] = True
    sess["status"] = "authenticated"
    sess["mode"] = "cloud_sync"
    sess["user_id"] = "DPOA3698"
    sess["bot"] = None  # Missing Playwright browser in cloud_sync triggers PermissionError -> marks expired

    hdrs = {"Host": "reports.panchayatautomation.in", "X-Session-ID": sid}
    try:
        res_exp = c.post("/api/reports/mas-consolidated/generate", headers=hdrs, json={"month": "July", "year": 2026})
        assert res_exp.status_code == 401
        assert res_exp.headers.get("X-Dept-Auth-Required") == "true"
        assert sess["status"] == "expired"

        # Restore open bot in live_portal mode and simulate scrape runtime failure -> 502
        sess["authenticated"] = True
        sess["status"] = "authenticated"
        sess["mode"] = "live_portal"
        sess["bot"] = _DummyBot()

        def _boom(*args, **kwargs):
            raise RuntimeError("Upstream GM-R 5.24 table timeout")

        monkeypatch.setattr(mas_automation, "scrape_mandal_abstract_524", _boom)
        res_502 = c.post("/api/mas/generate", headers=hdrs, json={"month": "July", "year": 2026})
        assert res_502.status_code == 502
        assert "timeout" in res_502.json()["detail"].lower()
    finally:
        automation_service._sessions.pop(sid, None)


def test_mas_navigation_waits_for_iframe_and_expands_gmr5_accordion(monkeypatch):
    """Ensure MAS navigation recovers deptLoginVerified, waits for my-iframe, and expands GM-R 5 -> 5.24."""
    monkeypatch.setattr(mas_automation.time, "sleep", lambda *_: None)

    state = {
        "url": "https://epanchayat.telangana.gov.in/cs",
        "menu_loaded": False,
        "expanded": False,
        "report_loaded": False,
        "clicks": [],
    }

    class _MockLocator:
        def __init__(self, kind: str):
            self.kind = kind
            self.first = self

        def all(self):
            if self.kind in ("target_524", "gp_monitoring") and self.is_visible():
                return [self]
            return []

        def count(self) -> int:
            if self.kind == "gmr5" and state["menu_loaded"]:
                return 1
            if self.kind == "enlarge" and state["menu_loaded"]:
                return 1
            if self.kind == "target_524" and state["menu_loaded"]:
                return 1
            if self.kind == "ddl_month" and state["report_loaded"]:
                return 1
            return 0

        def is_visible(self, timeout: int = 0) -> bool:
            if self.kind == "gp_monitoring":
                return "deptloginverified" in state["url"].lower()
            if self.kind == "gmr5":
                return state["menu_loaded"] and not state["report_loaded"]
            if self.kind == "target_524":
                return state["menu_loaded"] and state["expanded"] and not state["report_loaded"]
            if self.kind == "ddl_month":
                return state["report_loaded"]
            return False

        def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
            if not self.is_visible():
                raise TimeoutError(f"Element {self.kind} not visible")

        def hover(self) -> None:
            state["clicks"].append(f"hover:{self.kind}")

        def scroll_into_view_if_needed(self) -> None:
            pass

        def click(self, timeout: int = 0) -> None:
            state["clicks"].append(f"click:{self.kind}")
            if self.kind == "gp_monitoring":
                state["menu_loaded"] = True
            elif self.kind == "gmr5":
                state["expanded"] = True
            elif self.kind == "target_524":
                state["report_loaded"] = True

    class _MockFrame:
        def __init__(self, name: str, url: str):
            self.name = name
            self.url = url

        def locator(self, selector: str):
            if "5.24" in selector or "Rpt_MAS_DataEntry" in selector:
                return _MockLocator("target_524")
            if "GM-R 5" in selector or "Monthly Activity" in selector:
                return _MockLocator("gmr5")
            if "Enlarge All" in selector:
                return _MockLocator("enlarge")
            if "ddlMonth" in selector:
                return _MockLocator("ddl_month")
            return _MockLocator("unknown")

    class _MockPage:
        def __init__(self):
            self.main_frame = _MockFrame("", "https://epanchayat.telangana.gov.in/deptLoginVerified")
            self.iframe = _MockFrame("my-iframe", "https://tgprepanchayat.telangana.gov.in/PSPerformance/DynamicReportsMenu2Array")
            self.frames = [self.main_frame, self.iframe]

        @property
        def url(self):
            return state["url"]

        def is_closed(self) -> bool:
            return False

        def goto(self, url: str, **kwargs) -> None:
            state["clicks"].append(f"goto:{url}")
            state["url"] = url

        def locator(self, selector: str):
            if "GP Monitoring" in selector:
                return _MockLocator("gp_monitoring")
            return _MockLocator("unknown")

    page = _MockPage()
    frame = mas_automation._open_gmr_report_frame(page, "5.24")
    assert frame is page.iframe
    assert "goto:https://epanchayat.telangana.gov.in/deptLoginVerified" in state["clicks"]
    assert "click:gp_monitoring" in state["clicks"]
    assert "click:gmr5" in state["clicks"]
    assert "click:target_524" in state["clicks"]
    assert state["report_loaded"] is True

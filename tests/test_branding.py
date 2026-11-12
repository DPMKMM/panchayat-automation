"""Verification suite for Official Branding, Identity, and Tagline consistency.

Covers:
- Centralized branding constants and host/route detection (core/branding.py)
- Both domains: panchayatautomation.in (apex) & reports.panchayatautomation.in (console)
- Google Login cards and Account Chooser modal consistency
- Dashboards, navigation headers, mobile nav drawer, profile view, loading & empty states
- Auxiliary pages (/services, /privacy-legal, /legal, /reports/ps-attendance, /reports/tax-dcb)
- Canonical two-line footer consistency across all web views
- Generated PDF & Excel reports preserving official government layouts while carrying canonical branding
"""

from __future__ import annotations

import io
from datetime import date
from types import SimpleNamespace

import openpyxl
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import app
from core.branding import (
    CONSOLE_NAME,
    GOV_SUBTITLE,
    PLATFORM_NAME,
    TAGLINE,
    WELCOME_MESSAGE,
    apply_openpyxl_branding,
    apply_portal_branding,
    apply_subpage_console_branding,
    get_branding_context,
    is_reports_console_request,
    render_canonical_footer_html,
)
from dsr.pdf_generator import ReportData, generate_mandal_pdf, generate_pdf as generate_dsr_pdf
from gp_balance.excel_generator import generate_balance_excel
from gp_balance.models import DistrictBalanceReport, GPBalanceDetail, MandalBalanceSummary
from gp_balance.pdf_generator import generate_balance_pdf

client = TestClient(app)

FORBIDDEN_LEGACY_BRAND_STRINGS = [
    "Automated Console",
    "e-Panchayat Console",
    "e-Panchayat-automation",
    "Panchayat Raj Analytics Reports",
    "Official MAS Portal",
    "ePanchayat Automation Portal",
    "DPM Khammam",
]


def _make_req(host: str = "panchayatautomation.in", path: str = "/", query: dict[str, str] | None = None):
    return SimpleNamespace(
        headers={"host": host},
        url=SimpleNamespace(path=path),
        query_params=query or {},
    )


def _assert_clean_legacy_branding(html: str) -> None:
    for term in FORBIDDEN_LEGACY_BRAND_STRINGS:
        assert term not in html, f"Found legacy branding term {term!r}"


def _assert_canonical_footer(html: str) -> None:
    assert PLATFORM_NAME in html
    assert TAGLINE in html
    assert "<footer" in html


# ---------------------------------------------------------------------------
# 1. Core Branding Module & Health Endpoint
# ---------------------------------------------------------------------------
def test_branding_constants_and_host_detection():
    assert PLATFORM_NAME == "e-Panchayat Automation"
    assert CONSOLE_NAME == "e-Panchayat Automation Console"
    assert WELCOME_MESSAGE == "Welcome to e-Panchayat Automation"
    assert TAGLINE == "Simplifying Panchayat Administration through Smart Reporting and Automation."

    assert is_reports_console_request(_make_req("panchayatautomation.in", "/")) is False
    assert is_reports_console_request(_make_req("panchayatautomation.in", "/manualreports")) is False
    assert is_reports_console_request(_make_req("www.panchayatautomation.in", "/services")) is False
    assert is_reports_console_request(_make_req("autoreports.panchayatautomation.in", "/")) is True
    assert is_reports_console_request(_make_req("www.autoreports.panchayatautomation.in", "/")) is True
    assert is_reports_console_request(_make_req("reports.panchayatautomation.in", "/")) is True
    assert is_reports_console_request(_make_req("www.reports.panchayatautomation.in", "/")) is True
    assert is_reports_console_request(_make_req("localhost:8050", "/reports")) is True
    assert is_reports_console_request(_make_req("localhost:8050", "/reports/tax-dcb")) is True
    assert is_reports_console_request(_make_req("localhost:8050", "/", {"site": "reports"})) is True

    ctx_apex = get_branding_context(_make_req("panchayatautomation.in", "/"))
    assert ctx_apex["is_reports_console"] is False
    assert ctx_apex["display_title"] == PLATFORM_NAME

    ctx_console = get_branding_context(_make_req("reports.panchayatautomation.in", "/"))
    assert ctx_console["is_reports_console"] is True
    assert ctx_console["display_title"] == CONSOLE_NAME
    assert ctx_console["page_title"] == f"{CONSOLE_NAME} | {PLATFORM_NAME}"

    footer_html = render_canonical_footer_html()
    assert PLATFORM_NAME in footer_html
    assert TAGLINE in footer_html
    assert GOV_SUBTITLE


def test_health_endpoint_includes_canonical_identity():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["platform"] == PLATFORM_NAME
    assert data["console"] == CONSOLE_NAME
    assert data["tagline"] == TAGLINE


# ---------------------------------------------------------------------------
# 2. Apex Homepage & Console Domain (Google Login + Dashboard UI Shell)
# ---------------------------------------------------------------------------
def test_apex_homepage_and_google_login_branding():
    for path in ("/", "/login", "/manualreports", "/tools", "/eptauto", "/naresh"):
        resp = client.get(path, headers={"Host": "panchayatautomation.in"})
        assert resp.status_code == 200
        html = resp.text

        assert '<title id="doc-page-title">e-Panchayat Automation</title>' in html
        assert WELCOME_MESSAGE in html
        assert TAGLINE in html
        assert "Sign in with Google" in html
        assert "google-account-chooser-modal" not in html
        assert "accounts.google.com/gsi/client" not in html
        assert "/static/js/firebase_auth.js" in html
        assert 'id="hero-console-chip" style="display:none;' in html
        assert 'id="login-console-badge" style="display:none;' in html
        assert '<header class="navbar"' not in html
        assert '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>' in html
        assert "gov-brand-subbadge" not in html
        assert 'id="hero-welcome-message"' not in html

        # Dashboard, profile, loading & empty states carry platform name
        assert "nav-officer-profile-bar" in html
        assert "openOfficerProfileView" in html
        assert "officer-profile-modal" in html
        assert 'id="dash-welcome-eyebrow"' in html
        assert 'id="dash-hero-title"' in html
        assert 'id="dash-tagline"' in html
        assert "progress-status-title" in html
        assert "e-Panchayat Automation is loading live mandal performance data..." in html
        assert "Loading active e-Panchayat Automation sessions..." in html
        assert "e-Panchayat Automation: No Gram Panchayats found" in html
        assert "Manual Reports" in html
        assert "Excel Studio" not in html
        assert "Excel Reporting Studio" not in html
        assert CONSOLE_NAME in html
        assert 'id="dash-hero-cross-link"' in html
        assert 'id="portal-cross-platform-card"' not in html
        assert html.index('id="dash-hero-cross-link"') < html.index('id="card-policy-module_dsr_excel"') < html.index('id="card-policy-module_dsr_multiday"')

        _assert_canonical_footer(html)
        _assert_clean_legacy_branding(html)


def test_reports_console_domain_and_routes_branding():
    requests = [
        ("/", {"Host": "autoreports.panchayatautomation.in"}),
        ("/", {"Host": "www.autoreports.panchayatautomation.in"}),
        ("/", {"Host": "reports.panchayatautomation.in"}),
        ("/", {"Host": "www.reports.panchayatautomation.in"}),
        ("/reports", {"Host": "panchayatautomation.in"}),
        ("/?site=reports", {"Host": "panchayatautomation.in"}),
    ]
    for url, hdrs in requests:
        resp = client.get(url, headers=hdrs)
        assert resp.status_code == 200
        html = resp.text

        assert f'<title id="doc-page-title">{CONSOLE_NAME} | {PLATFORM_NAME}</title>' in html
        assert f'<h1 class="gov-portal-main-brand" id="hero-platform-name">{CONSOLE_NAME}</h1>' in html
        assert WELCOME_MESSAGE in html
        assert TAGLINE in html
        assert "Sign in with Google" in html
        assert '<header class="navbar"' not in html
        assert 'id="hero-console-chip" style="display:inline-flex;' in html
        assert 'id="login-console-badge" style="display:inline-flex;' in html
        assert f"{CONSOLE_NAME} · Executive Report Modules" in html
        assert 'id="console-cross-platform-card"' not in html
        assert 'id="console-open-portal-link"' not in html
        assert html.index('id="dash-hero-cross-link"') < html.index('id="card-policy-module_dsr_automation"')

        _assert_canonical_footer(html)
        _assert_clean_legacy_branding(html)


def test_dedicated_manual_and_tools_subdomain_branding():
    manual_resp = client.get("/", headers={"Host": "www.manualreports.panchayatautomation.in"})
    assert manual_resp.status_code == 200
    manual_html = manual_resp.text
    assert f'<title id="doc-page-title">Manual Reports | {PLATFORM_NAME}</title>' in manual_html
    assert "e-Panchayat Manual Reports" in manual_html
    assert 'id="hero-console-chip" style="display:inline-flex;' in manual_html

    tools_resp = client.get("/", headers={"Host": "www.tools.panchayatautomation.in"})
    assert tools_resp.status_code == 200
    tools_html = tools_resp.text
    assert f'<title id="doc-page-title">Tools Studio | {PLATFORM_NAME}</title>' in tools_html
    assert "e-Panchayat Tools & Utilities Studio" in tools_html
    assert 'id="hero-console-chip" style="display:inline-flex;' in tools_html

    auto_resp = client.get("/autoreports", headers={"Host": "127.0.0.1:8050"})
    assert auto_resp.status_code == 200
    assert f'<title id="doc-page-title">{CONSOLE_NAME} | {PLATFORM_NAME}</title>' in auto_resp.text


# ---------------------------------------------------------------------------
# 3. Auxiliary Pages (/services, /privacy-legal, /reports/*)
# ---------------------------------------------------------------------------
def test_auxiliary_pages_branding_on_both_hosts():
    # Apex host: console pill hidden on /services & /privacy-legal
    for path in ("/services", "/privacy-legal", "/legal"):
        resp = client.get(path, headers={"Host": "panchayatautomation.in"})
        assert resp.status_code == 200
        html = resp.text
        assert PLATFORM_NAME in html
        assert WELCOME_MESSAGE in html
        assert TAGLINE in html
        assert 'id="subpage-console-pill" style="display:none;' in html
        _assert_canonical_footer(html)
        _assert_clean_legacy_branding(html)

    # Reports host & /reports/* routes: console pill visible
    for path in (
        "/services",
        "/privacy-legal",
        "/legal",
        "/reports/ps-attendance",
        "/reports/tax-dcb?district=Khammam",
        "/reports/mas",
        "/mas",
    ):
        resp = client.get(path, headers={"Host": "reports.panchayatautomation.in"})
        assert resp.status_code == 200
        html = resp.text
        assert PLATFORM_NAME in html
        assert CONSOLE_NAME in html
        assert TAGLINE in html
        assert 'id="subpage-console-pill" style="display:inline-flex;' in html
        _assert_canonical_footer(html)
        _assert_clean_legacy_branding(html)


def test_subpage_console_routes_activate_pill_even_on_localhost():
    for path in ("/reports/ps-attendance", "/reports/tax-dcb?district=Khammam", "/reports/mas", "/mas"):
        resp = client.get(path, headers={"Host": "127.0.0.1:8050"})
        assert resp.status_code == 200
        html = resp.text
        assert 'id="subpage-console-pill" style="display:inline-flex;' in html
        assert PLATFORM_NAME in html
        assert TAGLINE in html


# ---------------------------------------------------------------------------
# 4. Generated PDF & Excel Reports (Format-Preserving Branding)
# ---------------------------------------------------------------------------
def test_dsr_pdfs_carry_platform_branding_without_layout_change(tmp_path):
    report = ReportData(
        district_name="Khammam",
        report_date=date(2026, 11, 8),
        source_row_count=25,
        unique_gp_count=25,
        missing_lgd_rows=0,
        duplicate_lgd_rows=0,
        conflicts=[],
        mandal_rows=[{
            "serial": 1, "mandal": "Bonakal", "total_gps": 25,
            "before_9": 22, "before_9_pct": 88.0, "attendance_pct": 92.0,
            "on_leave": 1, "meeting_training": 1, "pending": 1,
        }],
        district_total={
            "total_gps": 25, "before_9": 22, "before_9_pct": 88.0, "attendance_pct": 92.0,
            "on_leave": 1, "meeting_training": 1, "pending": 1,
        },
        pending_rows=[{"serial": 1, "mandal": "Bonakal", "gp": "GP1", "ps_name": "PS1", "nature_of_posting": "Reg", "mobile": "9999999999"}],
        leave_rows=[],
        meeting_training_rows=[],
        after_9_rows=[],
        dsr_mandal_rows=[{
            "serial": 1, "mandal": "Bonakal", "total_gps": 25,
            "present_ps": 23, "dsr_entered": 21, "dsr_pending": 2, "dsr_pct": 91.3,
        }],
        dsr_district_total={
            "total_gps": 25, "present_ps": 23, "dsr_entered": 21, "dsr_pending": 2, "dsr_pct": 91.3,
        },
        dsr_pending_rows=[],
        all_gp_rows=[],
    )

    dist_pdf = tmp_path / "dsr_dist.pdf"
    generate_dsr_pdf(report, dist_pdf)
    reader_dist = PdfReader(str(dist_pdf))
    assert float(reader_dist.pages[0].mediabox.width) > float(reader_dist.pages[0].mediabox.height)
    assert PLATFORM_NAME in "\n".join(p.extract_text() for p in reader_dist.pages)

    mandal_pdf = tmp_path / "dsr_mandal.pdf"
    generate_mandal_pdf(report, mandal_pdf, mandal_name="Bonakal")
    reader_mandal = PdfReader(str(mandal_pdf))
    assert PLATFORM_NAME in "\n".join(p.extract_text() for p in reader_mandal.pages)


def test_gp_balance_pdf_and_excel_branding():
    gp = GPBalanceDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Appalanarasimhapuram",
        entered=True,
        gp_pd="Yes", tgbpass="Yes", fc15_tied="Yes", fc15_untied="Yes", vwsc="No", mgnregs="Yes",
    )
    gp.evaluate_pending()
    m = MandalBalanceSummary(
        s_no=1, mandal_name="Nelakondapally", total_gps=32, entered_gps=31, not_entered_gps=1,
        gp_pd_updated=32, tgbpass_updated=32, fc15_tied_updated=32, fc15_untied_updated=32, vwsc_updated=31, mgnregs_updated=32,
        pending_gps=[gp],
    )
    m.calculate_metrics()
    report = DistrictBalanceReport(
        district_name="Khammam",
        report_date_str="29-10-2026",
        generated_at="05-Nov-2026 05:00 PM",
        mandals=[m],
    )
    report.compute_totals()

    pdf_bytes = generate_balance_pdf(report)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert PLATFORM_NAME in "\n".join(p.extract_text() for p in reader.pages)

    excel_bytes = generate_balance_excel(report)
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    assert wb.properties.creator == PLATFORM_NAME
    assert wb.properties.subject == TAGLINE
    ws1 = wb["Mandal_Summary"]
    assert "Data Entry Status Report on Balances in GP Accounts" in str(ws1["A1"].value)
    assert ws1.oddFooter.left.text == PLATFORM_NAME
    assert ws1.oddFooter.center.text == TAGLINE


def test_dcb_pdfs_and_excel_branding():
    resp_pdf = client.get("/api/tax/report.pdf?district=Khammam&mandal=Bonakal")
    assert resp_pdf.status_code == 200
    reader = PdfReader(io.BytesIO(resp_pdf.content))
    assert len(reader.pages) == 1
    assert PLATFORM_NAME in reader.pages[0].extract_text()

    resp_pbi = client.get("/api/tax/powerbi-report.pdf?district=Khammam&mandal=Bonakal")
    assert resp_pbi.status_code == 200
    reader_pbi = PdfReader(io.BytesIO(resp_pbi.content))
    assert len(reader_pbi.pages) == 1
    pbi_txt = reader_pbi.pages[0].extract_text()
    assert CONSOLE_NAME in pbi_txt
    assert PLATFORM_NAME in pbi_txt

    resp_xlsx = client.get("/api/tax/download?district=Khammam&format=xlsx")
    assert resp_xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp_xlsx.content))
    assert wb.properties.creator == PLATFORM_NAME
    assert wb.properties.subject == TAGLINE
    assert wb.active.oddFooter.left.text == PLATFORM_NAME
    assert wb.active.oddFooter.center.text == TAGLINE


def test_apply_openpyxl_branding_helper():
    wb = openpyxl.Workbook()
    apply_openpyxl_branding(wb)
    assert wb.properties.creator == PLATFORM_NAME
    assert wb.properties.lastModifiedBy == PLATFORM_NAME
    assert wb.properties.subject == TAGLINE
    assert wb.active.oddFooter.left.text == PLATFORM_NAME
    assert wb.active.oddFooter.center.text == TAGLINE

"""Unit and regression tests for GP Balance Entry (GM-R 14.2) module.

Verifies:
1. Real Gram Panchayat names are strictly preserved; no dummy '<Mandal> GP-X' names.
2. Account evaluation granularity: if a GP missed ONLY 1 bank account, ONLY that 1 account is listed.
3. Mandal name fuzzy stem normalization (e.g. Nelakondapally vs Nelakondapalle).
4. PDF & Excel generators render exact GP names and specific missing accounts.
"""

import io
from pathlib import Path
import pytest
from pypdf import PdfReader
import openpyxl

import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
GP_DIR = ROOT_DIR / "GPBALNCE"
if str(GP_DIR) not in sys.path:
    sys.path.insert(0, str(GP_DIR))

from gp_balance.models import GPBalanceDetail, MandalBalanceSummary, DistrictBalanceReport
from gp_balance.automation import normalize_mandal_key, populate_pending_gps_from_directory
from gp_balance.pdf_generator import generate_balance_pdf
from gp_balance.excel_generator import generate_balance_excel


def test_mandal_normalization():
    """Verify spelling variations across GM-R 14.2 and directory match properly."""
    assert normalize_mandal_key("Nelakondapally") == normalize_mandal_key("Nelakondapalle")
    assert normalize_mandal_key("Penubally") == normalize_mandal_key("Penuballi")
    assert normalize_mandal_key("Kallur") == normalize_mandal_key("Kalluru")
    assert normalize_mandal_key("Chinthakani") == normalize_mandal_key("Chintakani")
    assert normalize_mandal_key("Kusumanchi") == normalize_mandal_key("Kusumanchi")


def test_gp_single_account_missing():
    """If a GP entered 5 accounts but missed only VWSC, missing_accounts must contain ONLY VWSC."""
    gp = GPBalanceDetail(
        s_no=1,
        mandal_name="Nelakondapally",
        panchayat_name="Appalanarasimhapuram",
        entered=True,
        gp_pd="Yes",
        tgbpass="Yes",
        fc15_tied="Yes",
        fc15_untied="Yes",
        vwsc="No",  # Only VWSC is missed!
        mgnregs="Yes",
    )
    gp.evaluate_pending()
    assert gp.is_pending is True
    assert len(gp.missing_accounts) == 1
    assert gp.missing_accounts == ["VWSC (SBM)"]


def test_gp_single_account_untied_missing():
    """If a GP entered 5 accounts but missed only 15th FC Untied, missing_accounts must contain ONLY that account."""
    gp = GPBalanceDetail(
        s_no=2,
        mandal_name="Penubally",
        panchayat_name="Bayyannagudem",
        entered=True,
        gp_pd="Yes",
        tgbpass="Yes",
        fc15_tied="Yes",
        fc15_untied="No",  # Only 15th FC Untied is missed!
        vwsc="Yes",
        mgnregs="Yes",
    )
    gp.evaluate_pending()
    assert gp.is_pending is True
    assert len(gp.missing_accounts) == 1
    assert gp.missing_accounts == ["15th FC Untied (e-Gram Swaraj)"]


def test_gp_all_accounts_entered():
    """If a GP entered all 6 accounts, it is NOT pending."""
    gp = GPBalanceDetail(
        s_no=3,
        mandal_name="Bonakal",
        panchayat_name="Allapadu",
        entered=True,
        gp_pd="Yes",
        tgbpass="Yes",
        fc15_tied="Yes",
        fc15_untied="Yes",
        vwsc="Yes",
        mgnregs="Yes",
    )
    gp.evaluate_pending()
    assert gp.is_pending is False
    assert len(gp.missing_accounts) == 0


def test_gp_all_accounts_missing():
    """If a GP missed all accounts (data not entered at all), all 6 accounts are listed."""
    gp = GPBalanceDetail(
        s_no=4,
        mandal_name="Chinthakani",
        panchayat_name="Chinamandava",
        entered=False,
        gp_pd="No",
        tgbpass="No",
        fc15_tied="No",
        fc15_untied="No",
        vwsc="No",
        mgnregs="No",
    )
    gp.evaluate_pending()
    assert gp.is_pending is True
    assert len(gp.missing_accounts) == 6


def test_no_synthetic_gp_names_in_fallback():
    """Verify that populate_pending_gps_from_directory NEVER synthesizes '<Mandal> GP-X' names."""
    m = MandalBalanceSummary(
        s_no=1,
        mandal_name="Nelakondapally",
        total_gps=32,
        entered_gps=30,
        not_entered_gps=2,
        vwsc_updated=30,  # 2 pending for VWSC
        gp_pd_updated=32,
        tgbpass_updated=32,
        fc15_tied_updated=32,
        fc15_untied_updated=32,
        mgnregs_updated=32,
    )
    m.calculate_metrics()
    assert m.vwsc_pending == 2
    assert m.gp_pd_pending == 0

    populate_pending_gps_from_directory([m], district_name="")
    # Every GP must have a real name, never "Nelakondapally GP-1"
    for gp in m.pending_gps:
        assert "GP-" not in gp.panchayat_name, f"Forbidden dummy name detected: {gp.panchayat_name}"
        # Since only vwsc_pending was 2, missing_accounts must ONLY be VWSC!
        assert gp.missing_accounts == ["VWSC (SBM)"]


def test_balance_pdf_and_excel_generation():
    """Verify PDF and Excel generation with exact GP names and specific missing accounts."""
    gp1 = GPBalanceDetail(
        s_no=1,
        mandal_name="Chinthakani",
        panchayat_name="Chinamandava",
        entered=False,
        gp_pd="No", tgbpass="No", fc15_tied="No", fc15_untied="No", vwsc="No", mgnregs="No",
    )
    gp1.evaluate_pending()

    gp2 = GPBalanceDetail(
        s_no=2,
        mandal_name="Nelakondapally",
        panchayat_name="Appalanarasimhapuram",
        entered=True,
        gp_pd="Yes", tgbpass="Yes", fc15_tied="Yes", fc15_untied="Yes", vwsc="No", mgnregs="Yes",
    )
    gp2.evaluate_pending()

    m1 = MandalBalanceSummary(
        s_no=1, mandal_name="Chinthakani", total_gps=26, entered_gps=25, not_entered_gps=1,
        gp_pd_updated=25, tgbpass_updated=25, fc15_tied_updated=25, fc15_untied_updated=25, vwsc_updated=25, mgnregs_updated=25,
        pending_gps=[gp1]
    )
    m1.calculate_metrics()

    m2 = MandalBalanceSummary(
        s_no=2, mandal_name="Nelakondapally", total_gps=32, entered_gps=31, not_entered_gps=1,
        gp_pd_updated=32, tgbpass_updated=32, fc15_tied_updated=32, fc15_untied_updated=32, vwsc_updated=31, mgnregs_updated=32,
        pending_gps=[gp2]
    )
    m2.calculate_metrics()

    report = DistrictBalanceReport(
        district_name="Test District",
        report_date_str="29-10-2026",
        generated_at="05-Nov-2026 05:00 PM",
        mandals=[m1, m2],
    )
    report.compute_totals()
    assert len(report.pending_gps_all) == 2

    # 1. Test PDF
    pdf_bytes = generate_balance_pdf(report)
    assert len(pdf_bytes) > 5_000
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2
    # Verify page 2 contains real GP names
    p2_text = reader.pages[1].extract_text()
    assert "Chinamandava" in p2_text
    assert "Appalanarasimhapuram" in p2_text
    assert "GP-1" not in p2_text
    assert "GP-2" not in p2_text

    # 2. Test Excel
    excel_bytes = generate_balance_excel(report)
    assert len(excel_bytes) > 5_000
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws2 = wb["Pending_GPs_Action_List"]
    found_gp1 = False
    found_gp2 = False
    for row in ws2.iter_rows(values_only=True):
        if "Chinamandava" in str(row):
            found_gp1 = True
        if "Appalanarasimhapuram" in str(row):
            found_gp2 = True
            # Row must list ONLY VWSC
            assert "VWSC (SBM)" in str(row)
    assert found_gp1 is True
    assert found_gp2 is True


def test_sathupally_partial_pending_shown_in_pdf():
    """Verify Sathupally case: not_entered_gps is 0 on portal, but 1 GP has 15th FC Untied and VWSC pending.
    Must be identified as pending and displayed in PDF with exact missed accounts.
    """
    m = MandalBalanceSummary(
        s_no=14,
        mandal_name="Sathupally",
        total_gps=21,
        entered_gps=21,
        not_entered_gps=0,  # Portal said 0
        gp_pd_updated=21,
        tgbpass_updated=21,
        fc15_tied_updated=21,
        fc15_untied_updated=20,  # 1 pending!
        vwsc_updated=20,         # 1 pending!
        mgnregs_updated=21,
    )
    m.calculate_metrics()
    assert m.has_pending is True
    assert m.fc15_untied_pending == 1
    assert m.vwsc_pending == 1

    # Test directory fallback if web drilldown didn't populate
    populate_pending_gps_from_directory([m], district_name="")
    assert len(m.pending_gps) == 1
    gp = m.pending_gps[0]
    assert gp.mandal_name == "Sathupally"
    assert "GP-" not in gp.panchayat_name
    assert "15th FC Untied (e-Gram Swaraj)" in gp.missing_accounts
    assert "VWSC (SBM)" in gp.missing_accounts

    # Test PDF generation includes Sathupally and its missing accounts
    report = DistrictBalanceReport(
        district_name="Test District",
        report_date_str="29-10-2026",
        generated_at="05-Nov-2026 05:25 PM",
        mandals=[m],
    )
    report.compute_totals()
    assert len(report.pending_gps_all) == 1

    pdf_bytes = generate_balance_pdf(report)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    p2_text = reader.pages[1].extract_text()
    assert "Sathupally" in p2_text
    assert "15th FC Untied (e-Gram Swaraj)" in p2_text
    assert "VWSC (SBM)" in p2_text

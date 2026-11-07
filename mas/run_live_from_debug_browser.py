"""Connects to user's interactive Chrome via CDP (Port 9222) and executes live MAS extraction.

Automates:
1. Connecting to the already authenticated e-Panchayat session.
2. Navigating to GP Monitoring -> GM-R 5.24 Data Entry Status Report.
3. Extracting available years and months from ASP.NET dropdowns.
4. Extracting Mandal Abstract and drilling down into each mandal for GP-level ground truth.
5. Navigating to GM-R 5.23 Report on Births Register in GP and drilling down.
6. Joining both datasets via make_lookup_key.
7. Generating the official 2-Page Executive Matrix + Single-Line Pending List PDF and 58-Column Excel.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from mas.automation import (
    MAS_XPATHS,
    extract_gmr5_23_births_abstract,
    extract_gmr5_23_gp_drilldown,
    extract_gmr5_24_gp_drilldown,
    extract_gmr5_24_mandal_abstract,
    fetch_available_gmr5_periods,
    get_content_iframe,
    navigate_to_gmr5_report,
    normalize_mandal_key,
    submit_gmr5_form,
    wait_for_aspnet_postback,
    wait_for_xpath_visible,
)
from mas.excel_generator import generate_mas_excel
from mas.models import (
    OFFICIAL_MAS_REPORT_ACTIVITIES,
    DistrictMASReport,
    GPBirthRegisterDetail,
    GPMASDetail,
    MandalBirthRegisterSummary,
    MandalMASSummary,
    _is_truthy,
    make_lookup_key,
)
from mas.pdf_generator import generate_mas_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mas_live")


class LiveBot:
    def __init__(self, page):
        self.page = page

    def select_menu(self, menu_name: str):
        xpath = f"//a[contains(text(), '{menu_name}') or contains(@title, '{menu_name}')]"
        loc = self.page.locator(f"xpath={xpath}").first
        loc.wait_for(state="visible", timeout=15000)
        loc.click()


def main():
    print("=" * 76, flush=True)
    print("  [*] CONNECTING TO LIVE CHROME ON PORT 9222...", flush=True)
    print("=" * 76, flush=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[+] Successfully connected to Chrome via CDP port 9222!", flush=True)
        except Exception as exc:
            print(f"[-] Could not connect to port 9222: {exc}", flush=True)
            print("[-] Please ensure Chrome was started using 'LOGIN_EPANCHAYAT.bat'.", flush=True)
            return

        contexts = browser.contexts
        if not contexts:
            print("[-] No browser context found.", flush=True)
            return

        context = contexts[0]
        # Find e-panchayat page
        target_page = None
        for pg in context.pages:
            if "epanchayat" in pg.url.lower():
                target_page = pg
                break

        if not target_page:
            target_page = context.pages[0] if context.pages else context.new_page()

        print(f"[+] Active Page URL: {target_page.url}", flush=True)
        bot = LiveBot(target_page)

        # 1. Navigate to GM-R 5.24 Data Entry Status Report
        print("\n[*] Navigating to GP Monitoring > GM-R 5.24 Data Entry Status Report...", flush=True)
        iframe_24 = navigate_to_gmr5_report(bot, report_code="5.24")

        # 2. Extract Available Periods
        periods = fetch_available_gmr5_periods(iframe_24)
        years = periods.get("years", ["2026"])
        months = periods.get("months", ["October"])
        target_year = years[-1] if years else "2026"
        target_month = months[-1] if months else "October"
        print(f"[*] Available reporting years: {years}", flush=True)
        print(f"[*] Available reporting months: {months}", flush=True)
        print(f"[+] Selecting target period: Year={target_year}, Month={target_month}", flush=True)

        submit_gmr5_form(iframe_24, year=target_year, month=target_month)
        time.sleep(3)

        # 3. Scrape Mandal Abstract
        print("[*] Scraping GM-R 5.24 Mandal Abstract...", flush=True)
        mandals = extract_gmr5_24_mandal_abstract(iframe_24)
        print(f"[+] Detected {len(mandals)} Mandals in GM-R 5.24 Mandal Abstract.", flush=True)

        # 4. Drilldown to GP level
        all_mas_gps: list[GPMASDetail] = []
        for m_idx, mandal in enumerate(mandals, start=1):
            print(f"  • [{m_idx}/{len(mandals)}] Drilling down into Mandal: {mandal.mandal_name} ...", flush=True)
            gps = extract_gmr5_24_gp_drilldown(
                iframe_24,
                mandal_name=mandal.mandal_name,
                year=target_year,
                month=target_month,
            )
            if gps:
                mandal.all_gps = gps
                mandal.total_gps = len(gps)
                all_mas_gps.extend(gps)
                print(f"    -> Extracted {len(gps)} Gram Panchayats.", flush=True)

        # 5. Navigate to GM-R 5.23 Births Register
        print("\n[*] Navigating to GM-R 5.23 Report on Births Register in GP...", flush=True)
        iframe_23 = navigate_to_gmr5_report(bot, report_code="5.23")
        submit_gmr5_form(iframe_23, year=target_year, month=target_month)
        time.sleep(3)

        birth_mandals = extract_gmr5_23_births_abstract(iframe_23)
        print(f"[+] Detected {len(birth_mandals)} Mandals in GM-R 5.23 Births Abstract.", flush=True)

        all_birth_gps: list[GPBirthRegisterDetail] = []
        for b_idx, b_mandal in enumerate(birth_mandals, start=1):
            print(f"  • [{b_idx}/{len(birth_mandals)}] Drilling down into Births for Mandal: {b_mandal.mandal_name} ...", flush=True)
            b_gps = extract_gmr5_23_gp_drilldown(
                iframe_23,
                mandal_name=b_mandal.mandal_name,
                year=target_year,
                month=target_month,
            )
            if b_gps:
                b_mandal.all_gps = b_gps
                all_birth_gps.extend(b_gps)
                print(f"    -> Extracted {len(b_gps)} Births GP records.", flush=True)

        # 6. Master Unique Key Lookup Join
        print("\n[*] Joining Births data via Unique Key Lookup: [MANDAL]::[GRAM_PANCHAYAT]...", flush=True)
        births_lookup: dict[str, GPBirthRegisterDetail] = {
            make_lookup_key(bgp.mandal_name, bgp.panchayat_name): bgp for bgp in all_birth_gps
        }

        for gp in all_mas_gps:
            u_key = make_lookup_key(gp.mandal_name, gp.panchayat_name)
            bgp = births_lookup.get(u_key)
            if not bgp:
                m_stem = normalize_mandal_key(gp.mandal_name)
                g_clean = re.sub(r"[^a-zA-Z0-9]", "", gp.panchayat_name).lower()
                for bk, bv in births_lookup.items():
                    bm_k, bg_k = bk.split("::", 1) if "::" in bk else (bk, "")
                    if normalize_mandal_key(bm_k) == m_stem and (
                        re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower() in g_clean or g_clean in re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower()
                    ):
                        bgp = bv
                        break

            if bgp and bgp.entered:
                gp.activity_flags["Birth details"] = "Yes"
                gp.remarks = f"Births Registered: {bgp.births_registered}"
            else:
                gp.activity_flags["Birth details"] = "No"

            gp.evaluate_pending(OFFICIAL_MAS_REPORT_ACTIVITIES)

        # 7. Re-aggregate master mandal abstract
        for mandal in mandals:
            if mandal.all_gps:
                mandal.total_gps = len(mandal.all_gps)
                mandal.activity_counts = {}
                for act in OFFICIAL_MAS_REPORT_ACTIVITIES:
                    mandal.activity_counts[act] = sum(1 for g in mandal.all_gps if _is_truthy(g.activity_flags.get(act)))
                mandal.completed_gps = sum(1 for g in mandal.all_gps if not g.is_pending)
                mandal.pending_gps_count = sum(1 for g in mandal.all_gps if g.is_pending)
                mandal.pending_gps = [g for g in mandal.all_gps if g.is_pending]
                mandal.calculate_metrics()

        # 8. Compile Master District Report
        dist_name = "Telangana District"
        try:
            header_txt = target_page.inner_text("body")
            m_dist = re.search(r"District\s*:\s*([A-Za-z\s]+)", header_txt)
            if m_dist:
                dist_name = m_dist.group(1).strip()
        except Exception:
            pass

        report = DistrictMASReport(
            district_name=dist_name,
            financial_year=target_year,
            month_name=target_month,
            mandals=mandals,
            birth_mandals=birth_mandals,
        )
        report.calculate_totals()

        print("\n" + "=" * 76, flush=True)
        print(f"  [+] LIVE MAS & BIRTHS EXTRACTION COMPLETE ({report.district_name.upper()})", flush=True)
        print("=" * 76, flush=True)
        print(f"  • Total Mandals: {report.total_mandals}", flush=True)
        print(f"  • Total Gram Panchayats: {report.total_gps}", flush=True)
        print(f"  • Completed MAS GPs: {report.total_completed_gps} ({report.overall_pct:.1f}%)", flush=True)
        print(f"  • Pending MAS GPs: {report.total_pending_gps}", flush=True)
        print(f"  • Births Entered GPs: {report.total_birth_entered_gps} ({report.births_overall_pct:.1f}%)", flush=True)
        print(f"  • Combined Compliance Index: {report.combined_compliance_index:.1f}%", flush=True)

        # 9. Output Deliverables
        clean_name = re.sub(r"[^a-zA-Z0-9]", "_", report.district_name).strip("_")
        ts_str = datetime.now().strftime("%Y%m%d_%H%M")
        pdf_path = REPORTS_DIR / f"{clean_name}_MAS_Report_{target_year}_{target_month}_{ts_str}.pdf"
        excel_path = REPORTS_DIR / f"{clean_name}_MAS_Report_{target_year}_{target_month}_{ts_str}.xlsx"

        print("\n[*] Generating Official 2-Page Executive Matrix + Single-Line Pending List PDF...", flush=True)
        pdf_bytes = generate_mas_pdf(report, target=pdf_path)
        print(f"[+] PDF successfully created: {pdf_path} ({len(pdf_bytes):,} bytes)", flush=True)

        print("[*] Generating Two-Tier 58-Column Formatted Excel Workbook...", flush=True)
        excel_bytes = generate_mas_excel(report, output_path=excel_path)
        print(f"[+] Excel successfully created: {excel_path} ({len(excel_bytes):,} bytes)", flush=True)

        print("\n" + "=" * 76, flush=True)
        print("  [SUCCESS] ALL DELIVERABLES SUCCESSFULLY GENERATED FROM LIVE PORTAL DATA!", flush=True)
        print("=" * 76, flush=True)
        print(f"  • PDF Report  : {pdf_path}", flush=True)
        print(f"  • Excel Report: {excel_path}", flush=True)
        print("=" * 76 + "\n", flush=True)


if __name__ == "__main__":
    main()

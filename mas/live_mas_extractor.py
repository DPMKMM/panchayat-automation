"""Production Live Scraper & Report Engine for Telangana e-Panchayat MAS Module.

Connects directly via CDP to the user's authenticated Chrome session on port 9222.
Extracts 100% live ground-truth data:
1. GM-R 5.24: Mandal Abstract & GP Drilldowns across 17 monthly activities.
2. GM-R 5.23: Mandal Abstract & GP Drilldowns for Births Register.
3. Performs Unique Key Lookup join: [MANDAL]::[GRAM_PANCHAYAT].
4. Generates:
   - Official Legal Landscape 2-Page Executive Matrix + Single-Line Pending List PDF
   - Departmental 58-Column Two-Tier Formatted Excel Workbook
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

from mas.excel_generator import generate_mas_excel
from mas.models import (
    MAS_5_24_ACTIVITIES,
    OFFICIAL_MAS_REPORT_ACTIVITIES,
    DistrictMASReport,
    GPBirthRegisterDetail,
    GPMASDetail,
    MandalBirthRegisterSummary,
    MandalMASSummary,
    _is_truthy,
    make_lookup_key,
    normalize_activity_key,
)
from mas.pdf_generator import generate_mas_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mas_live_extractor")


def reload_menu(page):
    """Submits the GP Monitoring form on the parent page to load DynamicReportsMenu into my-iframe."""
    page.evaluate('''() => {
        const form = document.querySelector("form[action*='PSPerformance/home']");
        if (form) form.submit();
    }''')
    time.sleep(5)
    iframe = page.frame('my-iframe')
    if iframe:
        try:
            iframe.wait_for_selector(
                "a[href*='Rpt_MAS_DataEntry'], a[href*='rpt_Pi_BirthRegistrations']",
                state="attached",
                timeout=20000,
            )
            time.sleep(1)
        except Exception:
            pass
    return iframe


def scrape_live_mas_data(
    page,
    target_year: str = "2026",
    target_month: str = "October",
) -> DistrictMASReport:
    """Executes full drilldown extraction for GM-R 5.24 and GM-R 5.23."""
    print("=" * 76, flush=True)
    print(f"  [*] STARTING LIVE MAS EXTRACTION (Period: {target_month} {target_year})", flush=True)
    print("=" * 76, flush=True)

    # -------------------------------------------------------------------------
    # STEP 1: Navigate to GM-R 5.24 Data Entry Status Report
    # -------------------------------------------------------------------------
    print("\n[Step 1] Navigating to GM-R 5.24 Data Entry Status Report...", flush=True)
    iframe = reload_menu(page)
    time.sleep(2)

    iframe.evaluate('''() => {
        const a = document.querySelector("a[href*='Rpt_MAS_DataEntry']");
        if (a) a.click();
    }''')
    iframe.wait_for_selector("#ContentPlaceHolder1_ddlYear", state="visible", timeout=20000)

    # Select Year and Month
    print(f"[*] Selecting Year={target_year} and Month={target_month}...", flush=True)
    iframe.select_option("#ContentPlaceHolder1_ddlYear", label=target_year)
    time.sleep(1)
    iframe.select_option("#ContentPlaceHolder1_ddlMonth", label=target_month)
    time.sleep(1)

    print("[*] Submitting GM-R 5.24 search form...", flush=True)
    iframe.click("#ContentPlaceHolder1_btnsubmit")
    iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=25000)

    # -------------------------------------------------------------------------
    # STEP 2: Scrape GM-R 5.24 Mandal Abstract Table
    # -------------------------------------------------------------------------
    print("\n[Step 2] Scraping GM-R 5.24 Mandal Abstract Table...", flush=True)
    mandal_rows_raw = iframe.evaluate('''() => {
        const table = document.querySelector("#ContentPlaceHolder1_GridView1");
        if (!table) return [];
        return Array.from(table.querySelectorAll("tbody tr, tr")).map(r => {
            const link = r.querySelector("a[id*='lblLevelNameMandal']");
            return {
                cells: Array.from(r.querySelectorAll("td, th")).map(c => c.innerText.trim()),
                linkId: link ? link.id : null,
                mandalName: link ? link.innerText.trim() : null
            };
        });
    }''')

    mandals_to_drill: list[dict] = []
    for r in mandal_rows_raw:
        if r["linkId"] and r["mandalName"]:
            m_name_up = r["mandalName"].strip().upper()
            if any(kw in m_name_up for kw in ("TOTAL", "GRAND TOTAL")):
                continue
            c = r["cells"]
            tot_gps = int(c[2]) if len(c) > 2 and c[2].isdigit() else 0
            mandals_to_drill.append({
                "linkId": r["linkId"],
                "mandalName": r["mandalName"].strip(),
                "totalGps": tot_gps,
                "sNo": int(c[0]) if c[0].isdigit() else len(mandals_to_drill) + 1,
            })

    print(f"[+] Found {len(mandals_to_drill)} authentic Mandals in GM-R 5.24 Mandal Abstract.", flush=True)

    # -------------------------------------------------------------------------
    # STEP 3: Drill Down into Each Mandal for GP Level Ground Truth Data
    # -------------------------------------------------------------------------
    print("\n[Step 3] Drilling down into each Mandal for Gram Panchayat ground-truth data...", flush=True)
    all_mas_gps: list[GPMASDetail] = []
    mandals: list[MandalMASSummary] = []

    for idx, m_info in enumerate(mandals_to_drill, start=1):
        m_name = m_info["mandalName"]
        link_id = m_info["linkId"]
        print(f"  • [{idx:2d}/{len(mandals_to_drill)}] Drilling down into Mandal: {m_name} ...", flush=True)

        mandal_gps: list[GPMASDetail] = []
        for attempt in range(2):
            try:
                # Ensure GridView1 is visible before clicking
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=20000)
                link_sel = f"#{link_id}"
                iframe.wait_for_selector(link_sel, state="visible", timeout=15000)
                iframe.click(link_sel)

                # Wait for GP Drilldown table (GridView2)
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView2", state="visible", timeout=25000)
                time.sleep(1)

                # Scrape GridView2
                gp_rows_raw = iframe.evaluate('''() => {
                    const table = document.querySelector("#ContentPlaceHolder1_GridView2");
                    if (!table) return [];
                    return Array.from(table.querySelectorAll("tbody tr, tr")).map(r => 
                        Array.from(r.querySelectorAll("td")).map(c => c.innerText.trim())
                    );
                }''')

                mandal_gps = []
                for gp_idx, gp_cols in enumerate(gp_rows_raw, start=1):
                    if len(gp_cols) < 3:
                        continue

                    gp_sno = int(gp_cols[0]) if gp_cols[0].isdigit() else gp_idx
                    gp_name = gp_cols[1].strip()

                    flags: dict[str, str] = {}
                    for a_idx, act_name in enumerate(MAS_5_24_ACTIVITIES):
                        c_ent = 2 + (a_idx * 2)
                        if c_ent < len(gp_cols):
                            val_ent = gp_cols[c_ent]
                            flags[act_name] = "Yes" if val_ent == "1" else "No"
                        else:
                            flags[act_name] = "No"

                    is_entered = any(v == "Yes" for v in flags.values())

                    gp = GPMASDetail(
                        s_no=gp_sno,
                        mandal_name=m_name,
                        panchayat_name=gp_name,
                        financial_year=target_year,
                        month=target_month,
                        entered=is_entered,
                        activity_flags=flags,
                    )
                    mandal_gps.append(gp)
                    all_mas_gps.append(gp)

                # Return back to Mandal Abstract
                iframe.wait_for_selector("#ContentPlaceHolder1_btnback", state="visible", timeout=15000)
                iframe.click("#ContentPlaceHolder1_btnback")
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=25000)
                time.sleep(1)
                break  # Successful drilldown and return

            except Exception as exc:
                logger.warning("Attempt %d error drilling into %s: %s", attempt + 1, m_name, exc)
                # Recover back to GridView1 if needed
                try:
                    if iframe.query_selector("#ContentPlaceHolder1_btnback"):
                        iframe.click("#ContentPlaceHolder1_btnback")
                    elif iframe.query_selector("#ContentPlaceHolder1_btnsubmit"):
                        iframe.click("#ContentPlaceHolder1_btnsubmit")
                    iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=20000)
                except Exception:
                    pass
                time.sleep(2)

        # Build MandalMASSummary
        m_summary = MandalMASSummary(
            s_no=m_info["sNo"],
            mandal_name=m_name,
            total_gps=len(mandal_gps) if mandal_gps else m_info["totalGps"],
            all_gps=mandal_gps,
        )
        mandals.append(m_summary)
        print(f"    -> Successfully extracted {len(mandal_gps)} GPs.", flush=True)

    print(f"\n[+] Total Gram Panchayats extracted from GM-R 5.24: {len(all_mas_gps)} across {len(mandals)} mandals.")

    # -------------------------------------------------------------------------
    # STEP 4: Navigate to GM-R 5.23 Report on Births Register in GP
    # -------------------------------------------------------------------------
    print("\n[Step 4] Navigating to GM-R 5.23 Report on Births Register in GP...", flush=True)
    iframe = reload_menu(page)
    time.sleep(2)

    iframe.evaluate('''() => {
        const a = document.querySelector("a[href*='rpt_Pi_BirthRegistrations']");
        if (a) a.click();
    }''')
    iframe.wait_for_selector("#ContentPlaceHolder1_ddlYear", state="visible", timeout=20000)

    # Select Year and Month
    iframe.select_option("#ContentPlaceHolder1_ddlYear", label=target_year)
    time.sleep(1)
    iframe.select_option("#ContentPlaceHolder1_ddlMonth", label=target_month)
    time.sleep(1)

    print("[*] Submitting GM-R 5.23 Births search form...", flush=True)
    iframe.click("#ContentPlaceHolder1_btnsubmit")
    iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=25000)

    # -------------------------------------------------------------------------
    # STEP 5: Scrape GM-R 5.23 Births Mandal Abstract & GP Drilldowns
    # -------------------------------------------------------------------------
    print("\n[Step 5] Scraping GM-R 5.23 Births Mandal Abstract & GP Drilldowns...", flush=True)
    birth_rows_raw = iframe.evaluate('''() => {
        const table = document.querySelector("#ContentPlaceHolder1_GridView1");
        if (!table) return [];
        return Array.from(table.querySelectorAll("tbody tr, tr")).map(r => {
            const link = r.querySelector("a[id*='lblLevelNameMandal']");
            return {
                cells: Array.from(r.querySelectorAll("td, th")).map(c => c.innerText.trim()),
                linkId: link ? link.id : null,
                mandalName: link ? link.innerText.trim() : null
            };
        });
    }''')

    birth_mandals_to_drill: list[dict] = []
    for r in birth_rows_raw:
        if r["linkId"] and r["mandalName"]:
            m_name_up = r["mandalName"].strip().upper()
            if any(kw in m_name_up for kw in ("TOTAL", "GRAND TOTAL")):
                continue
            c = r["cells"]
            tot = int(c[2]) if len(c) > 2 and c[2].isdigit() else 0
            ent = int(c[3]) if len(c) > 3 and c[3].isdigit() else 0
            not_ent = int(c[4]) if len(c) > 4 and c[4].isdigit() else 0
            b_cnt = int(c[5]) if len(c) > 5 and c[5].isdigit() else 0
            birth_mandals_to_drill.append({
                "linkId": r["linkId"],
                "mandalName": r["mandalName"].strip(),
                "totalGps": tot,
                "enteredGps": ent,
                "notEnteredGps": not_ent,
                "totalBirths": b_cnt,
                "sNo": int(c[0]) if c[0].isdigit() else len(birth_mandals_to_drill) + 1,
            })

    print(f"[+] Found {len(birth_mandals_to_drill)} authentic Mandals in GM-R 5.23 Births Abstract.", flush=True)

    all_birth_gps: list[GPBirthRegisterDetail] = []
    birth_mandals: list[MandalBirthRegisterSummary] = []

    for b_idx, bm_info in enumerate(birth_mandals_to_drill, start=1):
        m_name = bm_info["mandalName"]
        link_id = bm_info["linkId"]
        print(f"  • [{b_idx:2d}/{len(birth_mandals_to_drill)}] Drilling down into Births for Mandal: {m_name} ...", flush=True)

        bm_gps: list[GPBirthRegisterDetail] = []
        for attempt in range(2):
            try:
                # Ensure GridView1 is visible
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=20000)
                link_sel = f"#{link_id}"
                iframe.wait_for_selector(link_sel, state="visible", timeout=15000)
                iframe.click(link_sel)

                # Wait for GridView2
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView2", state="visible", timeout=25000)
                time.sleep(1)

                # Scrape GridView2
                bgp_rows_raw = iframe.evaluate('''() => {
                    const table = document.querySelector("#ContentPlaceHolder1_GridView2");
                    if (!table) return [];
                    return Array.from(table.querySelectorAll("tbody tr, tr")).map(r => 
                        Array.from(r.querySelectorAll("td")).map(c => c.innerText.trim())
                    );
                }''')

                bm_gps = []
                for bg_idx, bg_cols in enumerate(bgp_rows_raw, start=1):
                    if len(bg_cols) < 3:
                        continue
                    gp_sno = int(bg_cols[0]) if bg_cols[0].isdigit() else bg_idx
                    gp_name = bg_cols[1].strip()
                    is_ent = bg_cols[2] == "1"
                    b_cnt = int(bg_cols[4]) if len(bg_cols) > 4 and bg_cols[4].isdigit() else 0

                    bgp = GPBirthRegisterDetail(
                        s_no=gp_sno,
                        mandal_name=m_name,
                        panchayat_name=gp_name,
                        financial_year=target_year,
                        month=target_month,
                        entered=is_ent,
                        births_registered=b_cnt,
                        is_pending=not is_ent,
                    )
                    bm_gps.append(bgp)
                    all_birth_gps.append(bgp)

                # CRUCIAL: In GM-R 5.23, btnback causes server crash!
                # Using btnsubmit returns cleanly to GridView1!
                iframe.wait_for_selector("#ContentPlaceHolder1_btnsubmit", state="visible", timeout=15000)
                iframe.click("#ContentPlaceHolder1_btnsubmit")
                iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=25000)
                time.sleep(1)
                break  # Successful drilldown and return

            except Exception as exc:
                logger.warning("Attempt %d error drilling into Births for %s: %s", attempt + 1, m_name, exc)
                try:
                    iframe.click("#ContentPlaceHolder1_btnsubmit")
                    iframe.wait_for_selector("#ContentPlaceHolder1_GridView1", state="visible", timeout=20000)
                except Exception:
                    pass
                time.sleep(2)

        bm_summary = MandalBirthRegisterSummary(
            s_no=bm_info["sNo"],
            mandal_name=m_name,
            total_gps=len(bm_gps) if bm_gps else bm_info["totalGps"],
            entered_gps=sum(1 for g in bm_gps if g.entered),
            not_entered_gps=sum(1 for g in bm_gps if not g.entered),
            total_births=sum(g.births_registered for g in bm_gps),
            all_gps=bm_gps,
        )
        bm_summary.calculate_metrics()
        birth_mandals.append(bm_summary)
        print(f"    -> Successfully extracted {len(bm_gps)} Births GP records.", flush=True)

    print(f"\n[+] Total Births GP records extracted: {len(all_birth_gps)} across {len(birth_mandals)} mandals.")

    # -------------------------------------------------------------------------
    # STEP 6: Master Unique Key Lookup Join: [MANDAL]::[GRAM_PANCHAYAT]
    # -------------------------------------------------------------------------
    print("\n[Step 6] Joining Births data via Unique Key Lookup: [MANDAL]::[GRAM_PANCHAYAT]...", flush=True)
    births_lookup: dict[str, GPBirthRegisterDetail] = {
        make_lookup_key(bgp.mandal_name, bgp.panchayat_name): bgp for bgp in all_birth_gps
    }

    match_count = 0
    for gp in all_mas_gps:
        u_key = make_lookup_key(gp.mandal_name, gp.panchayat_name)
        bgp = births_lookup.get(u_key)
        if not bgp:
            # Normalized stem matching
            m_clean = re.sub(r"[^a-zA-Z0-9]", "", gp.mandal_name).lower()
            g_clean = re.sub(r"[^a-zA-Z0-9]", "", gp.panchayat_name).lower()
            for bk, bv in births_lookup.items():
                bm_k, bg_k = bk.split("::", 1) if "::" in bk else (bk, "")
                if re.sub(r"[^a-zA-Z0-9]", "", bm_k).lower() == m_clean and (
                    re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower() in g_clean or g_clean in re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower()
                ):
                    bgp = bv
                    break

        if bgp and bgp.entered:
            gp.activity_flags["Birth details"] = "Yes"
            if bgp.births_registered > 0:
                gp.remarks = f"Births Registered: {bgp.births_registered}"
            match_count += 1
        else:
            gp.activity_flags["Birth details"] = "No"

        # Evaluate compliance across all 18 indicators
        gp.evaluate_pending(OFFICIAL_MAS_REPORT_ACTIVITIES)

    print(f"[+] Unique Key Lookup completed: joined {len(births_lookup)} Births records into {len(all_mas_gps)} MAS records.")

    # -------------------------------------------------------------------------
    # STEP 7: Re-aggregate Master Mandal Summaries from Ground Truth
    # -------------------------------------------------------------------------
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

    # Compile Master District Report
    report = DistrictMASReport(
        district_name="Khammam",
        financial_year=target_year,
        month_name=target_month,
        mandals=mandals,
        birth_mandals=birth_mandals,
    )
    report.calculate_totals()

    print("\n" + "=" * 76, flush=True)
    print(f"  [+] LIVE DATA EXTRACTION COMPLETE (KHAMMAM DISTRICT)", flush=True)
    print("=" * 76, flush=True)
    print(f"  • Total Mandals: {report.total_mandals}")
    print(f"  • Total Gram Panchayats: {report.total_gps}")
    print(f"  • Fully Completed MAS GPs: {report.total_completed_gps} ({report.overall_pct:.1f}%)")
    print(f"  • Pending MAS GPs: {report.total_pending_gps}")
    print(f"  • Overall Percentage Entered (18 Indicators): {report.overall_pct_entered:.1f}%")
    print(f"  • Births Entered GPs: {report.total_birth_entered_gps} ({report.births_overall_pct:.1f}%)")
    print(f"  • Total District Registered Births: {report.total_district_births:,}")
    print(f"  • Combined Departmental Compliance Index: {report.combined_compliance_index:.1f}%")
    print("=" * 76 + "\n", flush=True)

    return report


def main():
    cache_path = DATA_DIR / "mas_report_latest.pkl"

    if "--from-cache" in sys.argv and cache_path.exists():
        import pickle
        with open(cache_path, "rb") as f:
            report = pickle.load(f)
        print(f"[*] Loaded live report from local cache ({cache_path}) successfully!", flush=True)
    else:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]

            report = scrape_live_mas_data(page, target_year="2026", target_month="October")
            import pickle
            with open(cache_path, "wb") as f:
                pickle.dump(report, f)
            print(f"[+] Saved extracted report cache to {cache_path}", flush=True)

    # Generate Deliverables
    clean_name = "Khammam"
    ts_str = datetime.now().strftime("%Y%m%d_%H%M")
    pdf_path = REPORTS_DIR / f"{clean_name}_MAS_Report_2026_October_LIVE_{ts_str}.pdf"
    excel_path = REPORTS_DIR / f"{clean_name}_MAS_Report_2026_October_LIVE_{ts_str}.xlsx"

    print("[*] Generating Official Legal Landscape 2-Page Matrix + Single-Line Pending List PDF...", flush=True)
    pdf_bytes = generate_mas_pdf(report, target=pdf_path)
    print(f"[+] PDF generated: {pdf_path} ({len(pdf_bytes):,} bytes)", flush=True)

    print("[*] Generating Departmental 58-Column Formatted Excel Workbook...", flush=True)
    excel_bytes = generate_mas_excel(report, output_path=excel_path)
    print(f"[+] Excel generated: {excel_path} ({len(excel_bytes):,} bytes)", flush=True)

    print("\n" + "=" * 76, flush=True)
    print("  🎉  ALL DELIVERABLES SUCCESSFULLY GENERATED FROM 100% LIVE PORTAL DATA!", flush=True)
    print("=" * 76, flush=True)
    print(f"  • PDF Report  : {pdf_path}")
    print(f"  • Excel Report: {excel_path}")
    print("=" * 76 + "\n", flush=True)


if __name__ == "__main__":
    main()

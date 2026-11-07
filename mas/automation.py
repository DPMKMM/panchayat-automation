"""Playwright Automation Engine for Telangana e-Panchayat Monthly Activity Statement (MAS).

Supports:
1. GM-R 5.24: Data Entry Status Report (Year from 2020 + Month -> Mandal Abstract -> GP Drilldown)
2. GM-R 5.23: Report on Births Register in GP

Strict ASP.NET XPath selection for all DOM elements (menus, accordion, dropdowns, buttons, tables).
Direct URL navigations (page.goto) are strictly prohibited — navigation is 100% DOM XPath driven
to preserve the authenticated ASP.NET session state and ViewState inside 'my-iframe'.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mas.models import (
    DEFAULT_MAS_ACTIVITIES,
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

logger = logging.getLogger("mas_automation")

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# DETERMINISTIC ASP.NET XPATH REGISTRY FOR GM-R 5 (MAS MODULE)
# ==============================================================================
MAS_XPATHS = {
    # 1. Content iframe detection
    "CONTENT_IFRAME": (
        "//iframe[@name='my-iframe' or contains(@src, 'PSPerformance') or "
        "contains(@src, 'DynamicReports') or contains(@id, 'my-iframe') or contains(@id, 'iframe')]"
    ),

    # 2. Top-level Menu
    "MENU_GP_MONITORING": "//a[contains(text(), 'GP Monitoring') or contains(@title, 'GP Monitoring')]",

    # 3. Accordion Management
    "BTN_ENLARGE_ALL": (
        "//a[contains(text(), 'Enlarge All') or contains(@title, 'Enlarge All')] | "
        "//input[@value='Enlarge All'] | //button[contains(text(), 'Enlarge All')] | "
        "//span[contains(text(), 'Enlarge All')]"
    ),

    # 4. GM-R 5 Category Accordion Header
    "ACCORDION_GMR_5": (
        "//a[contains(text(), 'GM-R 5') or contains(text(), 'Monthly Activity Statement Reports')] | "
        "//span[contains(text(), 'GM-R 5') or contains(text(), 'Monthly Activity Statement Reports')] | "
        "//div[contains(text(), 'GM-R 5') or contains(text(), 'Monthly Activity Statement Reports')]"
    ),

    # 5. Specific Report Links
    # GM-R 5.24 Data Entry Status Report
    "LINK_GMR_5_24": (
        "//a[contains(text(), '5.24') or contains(text(), 'Data Entry Status Report') or "
        "contains(text(), 'Data Entry Status')]"
    ),
    # GM-R 5.23 Report on Births Register in GP
    "LINK_GMR_5_23": (
        "//a[contains(text(), '5.23') or contains(text(), 'Births Register in GP') or "
        "contains(text(), 'Births Register')]"
    ),

    # 6. Form Controls (Exact Verified ASP.NET IDs: Year from 2020, Month)
    "SELECT_YEAR": (
        "//select[@id='ContentPlaceHolder1_ddlYear' or contains(@name, 'ddlYear') or "
        "contains(@id, 'ddlYear') or contains(@id, 'Year')]"
    ),
    "SELECT_MONTH": (
        "//select[@id='ContentPlaceHolder1_ddlMonth' or contains(@name, 'ddlMonth') or "
        "contains(@id, 'ddlMonth') or contains(@id, 'Month')]"
    ),
    "SELECT_DISTRICT": (
        "//select[contains(@name, 'ddlDistrict') or contains(@id, 'ddlDistrict') or "
        "contains(@name, 'District') or contains(@id, 'District')]"
    ),
    "SELECT_MANDAL": (
        "//select[contains(@name, 'ddlMandal') or contains(@id, 'ddlMandal') or "
        "contains(@name, 'Mandal') or contains(@id, 'Mandal')]"
    ),

    # 7. Action Buttons (Exact Verified ASP.NET Submit Button)
    "BTN_SUBMIT": (
        "//input[@id='ContentPlaceHolder1_btnsubmit' or @name='ctl00$ContentPlaceHolder1$btnsubmit'] | "
        "//input[@type='submit' and (contains(@value, 'Submit') or contains(@value, 'Get Report'))] | "
        "//button[contains(text(), 'Submit') or contains(text(), 'Get Report')]"
    ),
    "BTN_BACK": (
        "//button[contains(text(), 'Back')] | //input[@value='Back' or contains(@value, 'Back')] | "
        "//a[contains(text(), 'Back')]"
    ),
    "BTN_EXPORT_EXCEL": (
        "//input[contains(@value, 'Export') or contains(@value, 'Excel') or contains(@id, 'btnExport')] | "
        "//button[contains(text(), 'Export') or contains(text(), 'Excel')]"
    ),

    # 8. Tables and DataTables Controls (Exact Verified GridView Table ID: ContentPlaceHolder1_GridView1)
    "SELECT_ENTRIES_LENGTH": "//select[contains(@name, 'length') or contains(@name, 'entries')]",
    "TABLE_GRID": (
        "//table[@id='ContentPlaceHolder1_GridView1' or contains(@class, 'drillDownTable') or "
        "contains(@id, 'GridView') or contains(@class, 'dataTable') or contains(@class, 'table')]"
    ),
    "TABLE_BODY_ROWS": (
        "//table[@id='ContentPlaceHolder1_GridView1' or contains(@class, 'drillDownTable')]//tbody//tr | "
        "//table[@id='ContentPlaceHolder1_GridView1' or contains(@class, 'drillDownTable')]//tr[position()>1]"
    ),

    # 9. Loading / Progress Indicator
    "UPDATE_PROGRESS": (
        "//div[contains(@id, 'UpdateProgress') or contains(@class, 'spinner') or "
        "contains(@id, 'loading') or contains(@id, 'pnlLoading')]"
    ),
}


# ==============================================================================
# UTILITY FUNCTIONS & DOM HELPERS
# ==============================================================================
def normalize_mandal_key(name: str) -> str:
    """Normalizes mandal names across spelling variations (e.g. Nelakondapally vs Nelakondapalle)."""
    s = re.sub(r"[^a-zA-Z0-9]", "", str(name)).lower()
    s = s.replace("th", "t").replace("w", "v")
    for suffix in ("palle", "pally", "palli", "balle", "bally", "balli", "gudem", "kunta", "padu", "puram", "uru", "ur"):
        if s.endswith(suffix) and len(s) > len(suffix) + 2:
            s = s[: -len(suffix)]
            break
    s = re.sub(r"[yeiua]+$", "", s)
    return s


def get_content_iframe(page: Any) -> Any:
    """Locates the content iframe holding the ASP.NET performance / dynamic report view."""
    for f in page.frames:
        if f.name == "my-iframe" or "PSPerformance" in f.url or "DynamicReports" in f.url:
            return f
    try:
        frame_el = page.wait_for_selector(f"xpath={MAS_XPATHS['CONTENT_IFRAME']}", state="attached", timeout=5000)
        if frame_el:
            content_frame = frame_el.content_frame()
            if content_frame:
                return content_frame
    except Exception:
        pass

    if len(page.frames) > 2:
        return page.frames[2]
    return None


def wait_for_xpath_visible(container: Any, xpath: str, timeout: int = 30000) -> Any:
    """Enforces strict visibility wait for a specific XPath target."""
    loc = container.locator(f"xpath={xpath}").first
    loc.wait_for(state="visible", timeout=timeout)
    return loc


def wait_for_aspnet_postback(page_or_frame: Any, timeout: int = 15000) -> None:
    """Waits for ASP.NET postbacks and UpdateProgress indicators to settle."""
    try:
        page_or_frame.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass

    try:
        spinner = page_or_frame.locator(f"xpath={MAS_XPATHS['UPDATE_PROGRESS']}").first
        if spinner.is_visible(timeout=1000):
            spinner.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass


def expand_datatable_length(iframe: Any) -> None:
    """Expands DataTables page length to display all mandals/GPs without pagination."""
    try:
        iframe.evaluate(
            """() => {
                const lenSel = document.querySelector("select[name*='length' i], select[name*='entries' i]");
                if (lenSel) {
                    const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n));
                    if (vals.length > 0) {
                        const maxVal = Math.max(...vals);
                        lenSel.value = maxVal.toString();
                        lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                        if (window.$) window.$(lenSel).trigger('change');
                    }
                }
                if (window.$ && window.$.fn && window.$.fn.dataTable) {
                    try { window.$('table').DataTable().page.len(-1).draw(false); } catch(e) {}
                }
            }"""
        )
        time.sleep(1.5)
    except Exception:
        pass


# ==============================================================================
# NAVIGATION FOR GM-R 5 (MONTHLY ACTIVITY STATEMENT REPORTS)
# ==============================================================================
def navigate_to_gmr5_report(bot: Any, report_code: str = "5.24") -> Any:
    """Navigates specifically to GM-R 5 reports:
      - '5.24': GM-R 5.24 Data Entry Status Report
      - '5.23': GM-R 5.23 Report on Births Register in GP

    Follows: GP Monitoring -> Enlarge All -> GM-R 5 -> GM-R 5.24 / 5.23
    """
    page = bot.page
    logger.info("Navigating to GM-R %s report under GP Monitoring...", report_code)

    # 1. Select GP Monitoring
    if hasattr(bot, "select_menu"):
        bot.select_menu("GP Monitoring")
    else:
        menu_loc = wait_for_xpath_visible(page, MAS_XPATHS["MENU_GP_MONITORING"], timeout=15000)
        menu_loc.click()

    time.sleep(2.5)

    # 2. Locate content iframe
    iframe = get_content_iframe(page)
    if not iframe:
        time.sleep(2.0)
        iframe = get_content_iframe(page)
    if not iframe:
        raise RuntimeError("Could not locate 'my-iframe' content frame for GP Monitoring.")

    try:
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    # 3. Click Enlarge All
    try:
        enlarge_btn = iframe.locator(f"xpath={MAS_XPATHS['BTN_ENLARGE_ALL']}").first
        if enlarge_btn.is_visible(timeout=3000):
            enlarge_btn.click()
            time.sleep(1.0)
    except Exception as exc:
        logger.debug("Enlarge All button notice: %s", exc)

    # 4. Expand Accordion: GM-R 5. Monthly Activity Statement Reports
    try:
        gmr5_header = iframe.locator(f"xpath={MAS_XPATHS['ACCORDION_GMR_5']}").first
        if gmr5_header.is_visible(timeout=4000):
            gmr5_header.click()
            time.sleep(1.5)
    except Exception as exc:
        logger.warning("Notice on expanding GM-R 5 header: %s", exc)

    # 5. Click the requested report link (5.24 or 5.23)
    target_xpath = MAS_XPATHS["LINK_GMR_5_24"] if "24" in report_code else MAS_XPATHS["LINK_GMR_5_23"]
    report_link = wait_for_xpath_visible(iframe, target_xpath, timeout=12000)
    report_link.click()
    wait_for_aspnet_postback(iframe, timeout=15000)
    time.sleep(2.5)

    return iframe


def fetch_available_gmr5_periods(bot: Any, report_code: str = "5.24") -> dict[str, list[str]]:
    """Extracts available Years (2020 onwards) and Months from GM-R 5 report dropdowns."""
    iframe = navigate_to_gmr5_report(bot, report_code=report_code)

    periods: dict[str, list[str]] = {
        "years": [],
        "months": [],
    }

    # Extract Year dropdown options (displaying from 2020)
    try:
        years = iframe.evaluate(
            """() => {
                const sel = document.querySelector("select[id*='Year' i], select[name*='Year' i]");
                if (!sel) return [];
                return Array.from(sel.options)
                    .map(o => o.text.trim())
                    .filter(t => t && !t.includes('--Select--'));
            }"""
        )
        if years:
            periods["years"] = years
    except Exception as exc:
        logger.warning("Could not dynamically extract years: %s", exc)

    # Fallback year list: 2020 through current year + 1
    if not periods["years"]:
        current_year = datetime.now().year
        periods["years"] = [str(y) for y in range(2020, current_year + 1)]

    # Extract Month dropdown options
    try:
        months = iframe.evaluate(
            """() => {
                const sel = document.querySelector("select[id*='Month' i], select[name*='Month' i]");
                if (!sel) return [];
                return Array.from(sel.options)
                    .map(o => o.text.trim())
                    .filter(t => t && !t.includes('--Select--'));
            }"""
        )
        if months:
            periods["months"] = months
    except Exception as exc:
        logger.warning("Could not dynamically extract months: %s", exc)

    if not periods["months"]:
        periods["months"] = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

    return periods


# Backward-compatible alias
fetch_available_mas_periods = fetch_available_gmr5_periods


# ==============================================================================
# REPORT SUBMISSION & SCRAPING (GM-R 5.24 & GM-R 5.23)
# ==============================================================================
def submit_gmr5_form(iframe: Any, year: str = "", month: str = "") -> None:
    """Selects target Year (from 2020) and Month, then clicks Submit."""
    # 1. Year Selection
    if year:
        try:
            year_sel = wait_for_xpath_visible(iframe, MAS_XPATHS["SELECT_YEAR"], timeout=8000)
            year_sel.select_option(label=year)
            wait_for_aspnet_postback(iframe)
        except Exception as exc:
            logger.warning("Year selection notice for '%s': %s", year, exc)

    # 2. Month Selection
    if month:
        try:
            month_sel = wait_for_xpath_visible(iframe, MAS_XPATHS["SELECT_MONTH"], timeout=8000)
            month_sel.select_option(label=month)
            wait_for_aspnet_postback(iframe)
        except Exception as exc:
            logger.warning("Month selection notice for '%s': %s", month, exc)

    # 3. Submit
    btn = wait_for_xpath_visible(iframe, MAS_XPATHS["BTN_SUBMIT"], timeout=10000)
    btn.click()
    wait_for_aspnet_postback(iframe, timeout=20000)
    time.sleep(3.0)

    # Expand rows to show all mandals without pagination
    expand_datatable_length(iframe)


def extract_gmr5_24_mandal_abstract(iframe: Any, district_name: str = "") -> list[MandalMASSummary]:
    """Scrapes the Mandal Abstract grid for GM-R 5.24 Data Entry Status Report."""
    wait_for_xpath_visible(iframe, MAS_XPATHS["TABLE_GRID"], timeout=20000)

    # Extract all rows directly from browser context
    rows_data = iframe.evaluate(
        """() => {
            const table = document.querySelector("table[id*='GridView' i], table.dataTable, table.table");
            if (!table) return { headers: [], rows: [] };

            const headerCells = Array.from(table.querySelectorAll("thead th, tr:first-child th, tr:first-child td"));
            const headers = headerCells.map(c => c.innerText.trim());

            const bodyRows = Array.from(table.querySelectorAll("tbody tr, tr:not(:first-child)")).map(r => {
                const cells = Array.from(r.querySelectorAll("td, th")).map(c => c.innerText.trim());
                const link = r.querySelector("a");
                return {
                    cells: cells,
                    has_link: !!link,
                    link_text: link ? link.innerText.trim() : ""
                };
            });

            return { headers, rows: bodyRows };
        }"""
    )

    headers = rows_data.get("headers", [])
    raw_rows = rows_data.get("rows", [])
    logger.info("GM-R 5.24 extracted %d rows with headers: %s", len(raw_rows), headers)

    mandals: list[MandalMASSummary] = []
    idx = 1

    for item in raw_rows:
        row = item.get("cells", [])
        if not row or len(row) < 3:
            continue

        first_col = row[0].strip()
        second_col = row[1].strip() if len(row) > 1 else ""

        # Skip summary / total row to prevent double-counting
        if any(kw in first_col.upper() for kw in ("TOTAL", "GRAND TOTAL", "DISTRICT")) or any(
            kw in second_col.upper() for kw in ("TOTAL", "GRAND TOTAL", "DISTRICT")
        ):
            continue

        # Detect S.No and Mandal Name columns
        mandal_name = second_col if first_col.isdigit() else first_col
        if not mandal_name or mandal_name.isdigit():
            continue

        # Extract Total GPs (cell index 2)
        total_gps = 0
        if len(row) > 2:
            c2_clean = re.sub(r"[^0-9]", "", row[2])
            total_gps = int(c2_clean) if c2_clean else 0

        # Extract the 17 activity completed counts
        activity_counts: dict[str, int] = {}
        for act_idx, act_name in enumerate(MAS_5_24_ACTIVITIES):
            col_entered = 3 + (act_idx * 2)
            if col_entered < len(row):
                c_clean = re.sub(r"[^0-9]", "", row[col_entered])
                activity_counts[act_name] = int(c_clean) if c_clean else 0

        # Minimum completed across all required activities gives overall fully completed GPs count
        completed_gps = min(activity_counts.values()) if activity_counts else 0
        pending_gps = max(0, total_gps - completed_gps)

        m_summary = MandalMASSummary(
            s_no=idx,
            mandal_name=mandal_name,
            total_gps=total_gps,
            completed_gps=completed_gps,
            pending_gps_count=pending_gps,
            activity_counts=activity_counts,
        )
        m_summary.calculate_metrics()
        mandals.append(m_summary)
        idx += 1

    return mandals


def extract_gmr5_24_gp_drilldown(
    iframe: Any,
    mandal_name: str,
    year: str = "",
    month: str = "",
) -> list[GPMASDetail]:
    """Drills down into a specific Mandal by clicking its hyperlink, extracts GP records, then returns via Back."""
    logger.info("Drilling down into GM-R 5.24 GP details for Mandal: %s", mandal_name)
    gps: list[GPMASDetail] = []

    try:
        # Locate and click the Mandal hyperlink in the abstract table
        m_xpath = f"//table//tr[td[contains(text(), '{mandal_name}') or a[contains(text(), '{mandal_name}')]]]//a"
        m_link = iframe.locator(f"xpath={m_xpath}").first

        if m_link.is_visible(timeout=5000):
            m_link.click()
            wait_for_aspnet_postback(iframe)
            time.sleep(2.0)
            expand_datatable_length(iframe)

            # Scrape GP Drilldown Table with Headers and Exact Activity Flags
            gp_payload = iframe.evaluate(
                """() => {
                    const table = document.querySelector("table[id*='GridView' i], table.dataTable, table.table");
                    if (!table) return { headers: [], rows: [] };
                    const ths = Array.from(table.querySelectorAll("thead th, tr:first-child th, tr:first-child td"));
                    const headers = ths.map(h => h.innerText.trim());
                    const trs = Array.from(table.querySelectorAll("tbody tr, tr:not(:first-child)"));
                    const rows = trs.map(r => Array.from(r.querySelectorAll("td, th")).map(c => c.innerText.trim()));
                    return { headers, rows };
                }"""
            )

            headers = gp_payload.get("headers", [])
            gp_data = gp_payload.get("rows", [])

            for i, row in enumerate(gp_data, start=1):
                if len(row) < 2:
                    continue
                gp_name = row[1] if row[0].isdigit() else row[0]
                if not gp_name or gp_name.isdigit() or any(k in gp_name.upper() for k in ("TOTAL", "GRAND TOTAL")):
                    continue

                act_flags: dict[str, str] = {}
                for col_idx in range(2, len(row)):
                    h_name = headers[col_idx] if col_idx < len(headers) else ""
                    cell_val = row[col_idx]
                    if h_name:
                        act_key = normalize_activity_key(h_name)
                        act_flags[act_key] = "Yes" if _is_truthy(cell_val) else "No"
                    elif col_idx - 2 < len(MAS_5_24_ACTIVITIES):
                        act_key = MAS_5_24_ACTIVITIES[col_idx - 2]
                        act_flags[act_key] = "Yes" if _is_truthy(cell_val) else "No"

                entered = any(_is_truthy(v) for v in act_flags.values()) if act_flags else any(w in str(row).lower() for w in ("yes", "completed", "entered", "updated", "true"))

                gp = GPMASDetail(
                    s_no=i,
                    mandal_name=mandal_name,
                    panchayat_name=gp_name,
                    financial_year=year,
                    month=month,
                    entered=entered,
                    activity_flags=act_flags,
                )
                gp.evaluate_pending()
                gps.append(gp)

            # Return back to Mandal Abstract table
            try:
                back_btn = iframe.locator(f"xpath={MAS_XPATHS['BTN_BACK']}").first
                if back_btn.is_visible(timeout=3000):
                    back_btn.click()
                    wait_for_aspnet_postback(iframe)
                    time.sleep(2.0)
            except Exception:
                pass

    except Exception as exc:
        logger.warning("Drilldown extraction notice for mandal %s: %s", mandal_name, exc)

    return gps


# ==============================================================================
# GM-R 5.23: BIRTHS REGISTER REPORT EXTRACTION
# ==============================================================================
def extract_gmr5_23_births_abstract(iframe: Any, district_name: str = "") -> list[MandalBirthRegisterSummary]:
    """Scrapes the Mandal Abstract grid for GM-R 5.23 Report on Births Register in GP."""
    wait_for_xpath_visible(iframe, MAS_XPATHS["TABLE_GRID"], timeout=20000)

    rows_data = iframe.evaluate(
        """() => {
            const table = document.querySelector("table[id*='GridView' i], table.dataTable, table.table");
            if (!table) return [];
            const rows = Array.from(table.querySelectorAll("tbody tr, tr:not(:first-child)"));
            return rows.map(r => Array.from(r.querySelectorAll("td, th")).map(c => c.innerText.trim()));
        }"""
    )

    mandals: list[MandalBirthRegisterSummary] = []
    idx = 1
    for row in rows_data:
        if not row or len(row) < 3:
            continue
        first_col = row[0].strip()
        second_col = row[1].strip() if len(row) > 1 else ""

        if any(kw in first_col.upper() for kw in ("TOTAL", "GRAND TOTAL", "DISTRICT")) or any(
            kw in second_col.upper() for kw in ("TOTAL", "GRAND TOTAL", "DISTRICT")
        ):
            continue

        mandal_name = second_col if first_col.isdigit() else first_col
        if not mandal_name or mandal_name.isdigit():
            continue

        # Extract numeric columns safely
        numbers = []
        for cell in row[1:]:
            clean_num = re.sub(r"[^0-9]", "", cell)
            if clean_num:
                try:
                    numbers.append(int(clean_num))
                except ValueError:
                    pass

        total_gps = numbers[0] if len(numbers) >= 1 else 0
        entered_gps = numbers[1] if len(numbers) >= 2 else 0
        not_entered_gps = numbers[2] if len(numbers) >= 3 else max(0, total_gps - entered_gps)
        total_births = numbers[3] if len(numbers) >= 4 else 0

        m_summary = MandalBirthRegisterSummary(
            s_no=idx,
            mandal_name=mandal_name,
            total_gps=total_gps,
            entered_gps=entered_gps,
            not_entered_gps=not_entered_gps,
            total_births=total_births,
        )
        m_summary.calculate_metrics()
        mandals.append(m_summary)
        idx += 1

    return mandals


def extract_gmr5_23_gp_drilldown(
    iframe: Any,
    mandal_name: str,
    year: str = "",
    month: str = "",
) -> list[GPBirthRegisterDetail]:
    """Drills down into GM-R 5.23 Births Register for a specific Mandal."""
    logger.info("Drilling down into GM-R 5.23 Births GP details for Mandal: %s", mandal_name)
    gps: list[GPBirthRegisterDetail] = []

    try:
        m_xpath = f"//table//tr[td[contains(text(), '{mandal_name}') or a[contains(text(), '{mandal_name}')]]]//a"
        m_link = iframe.locator(f"xpath={m_xpath}").first

        if m_link.is_visible(timeout=5000):
            m_link.click()
            wait_for_aspnet_postback(iframe)
            time.sleep(2.0)
            expand_datatable_length(iframe)

            gp_data = iframe.evaluate(
                """() => {
                    const table = document.querySelector("table[id*='GridView' i], table.dataTable, table.table");
                    if (!table) return [];
                    const rows = Array.from(table.querySelectorAll("tbody tr, tr:not(:first-child)"));
                    return rows.map(r => Array.from(r.querySelectorAll("td")).map(c => c.innerText.trim()));
                }"""
            )

            for i, row in enumerate(gp_data, start=1):
                if len(row) < 2:
                    continue
                gp_name = row[1] if row[0].isdigit() else row[0]
                entered = any(w in str(row).lower() for w in ("yes", "completed", "entered", "updated", "true"))

                # Try extracting births count
                births_count = 0
                for cell in row[2:]:
                    c_clean = re.sub(r"[^0-9]", "", cell)
                    if c_clean and int(c_clean) > 0:
                        births_count = int(c_clean)
                        break

                gp = GPBirthRegisterDetail(
                    s_no=i,
                    mandal_name=mandal_name,
                    panchayat_name=gp_name,
                    financial_year=year,
                    month=month,
                    entered=entered,
                    births_registered=births_count,
                )
                gp.evaluate_pending()
                gps.append(gp)

            # Return back to Mandal Abstract
            try:
                back_btn = iframe.locator(f"xpath={MAS_XPATHS['BTN_BACK']}").first
                if back_btn.is_visible(timeout=3000):
                    back_btn.click()
                    wait_for_aspnet_postback(iframe)
                    time.sleep(2.0)
            except Exception:
                pass

    except Exception as exc:
        logger.warning("GM-R 5.23 drilldown extraction notice for %s: %s", mandal_name, exc)

    return gps


# ==============================================================================
# MASTER RUNNER FOR GM-R 5 (MAS MODULE)
# ==============================================================================
def run_mas_automation(
    bot: Any,
    financial_year: str = "",
    month: str = "",
    district_name: str = "",
    report_code: str = "combined",
) -> DistrictMASReport:
    """Executes live scrape on Telangana e-Panchayat portal for:
      - '5.24': GM-R 5.24 Data Entry Status Report
      - '5.23': GM-R 5.23 Report on Births Register in GP
      - 'combined': Complete Unified Final Report covering BOTH 5.24 and 5.23!
    """
    logger.info("Executing GM-R 5 MAS Automation: Code='%s' Year='%s' Month='%s'", report_code, financial_year, month)

    mandals: list[MandalMASSummary] = []
    birth_mandals: list[MandalBirthRegisterSummary] = []

    # 1. Scrape GM-R 5.24 (Data Entry Status Report)
    all_mas_gps: list[GPMASDetail] = []
    if report_code in ("5.24", "combined"):
        logger.info("[+] Scraping GM-R 5.24 Data Entry Status Report...")
        iframe_24 = navigate_to_gmr5_report(bot, report_code="5.24")
        submit_gmr5_form(iframe_24, year=financial_year, month=month)
        mandals = extract_gmr5_24_mandal_abstract(iframe_24, district_name=district_name)
        logger.info("Found %d mandals in GM-R 5.24 abstract. Beginning drilldown to GP level for each mandal...", len(mandals))

        # Drill down into each mandal to webscrape entire Gram Panchayat level data
        for mandal in mandals:
            mandal_gps = extract_gmr5_24_gp_drilldown(
                iframe_24,
                mandal_name=mandal.mandal_name,
                year=financial_year,
                month=month,
            )
            if mandal_gps:
                mandal.all_gps = mandal_gps
                mandal.total_gps = len(mandal_gps)
                all_mas_gps.extend(mandal_gps)

    # 2. Scrape GM-R 5.23 (Report on Births Register in GP)
    all_birth_gps: list[GPBirthRegisterDetail] = []
    if report_code in ("5.23", "combined"):
        logger.info("[+] Scraping GM-R 5.23 Report on Births Register in GP...")
        iframe_23 = navigate_to_gmr5_report(bot, report_code="5.23")
        submit_gmr5_form(iframe_23, year=financial_year, month=month)
        birth_mandals = extract_gmr5_23_births_abstract(iframe_23, district_name=district_name)
        logger.info("Found %d mandals in GM-R 5.23 Births abstract. Drilling down to GP level for each mandal...", len(birth_mandals))

        # Drill down into each mandal for Births register
        for b_mandal in birth_mandals:
            b_gps = extract_gmr5_23_gp_drilldown(
                iframe_23,
                mandal_name=b_mandal.mandal_name,
                year=financial_year,
                month=month,
            )
            if b_gps:
                b_mandal.all_gps = b_gps
                all_birth_gps.extend(b_gps)

    # 3. Master Lookup Function: Unique key = mandal_name + grampanchayat_name
    logger.info("Synthesizing master dataset using unique lookup key: [MANDAL]::[GRAM_PANCHAYAT]...")
    births_lookup: dict[str, GPBirthRegisterDetail] = {
        make_lookup_key(bgp.mandal_name, bgp.panchayat_name): bgp for bgp in all_birth_gps
    }

    # Join Births data into each GP record and re-evaluate compliance across all 18 indicators
    for gp in all_mas_gps:
        lookup_k = make_lookup_key(gp.mandal_name, gp.panchayat_name)
        bgp = births_lookup.get(lookup_k)
        if not bgp:
            m_stem = normalize_mandal_key(gp.mandal_name)
            g_stem = re.sub(r"[^a-zA-Z0-9]", "", gp.panchayat_name).lower()
            for bk, bv in births_lookup.items():
                bm_k, bg_k = bk.split("::", 1) if "::" in bk else (bk, "")
                if normalize_mandal_key(bm_k) == m_stem and (
                    re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower() in g_stem or g_stem in re.sub(r"[^a-zA-Z0-9]", "", bg_k).lower()
                ):
                    bgp = bv
                    break

        if bgp and bgp.entered:
            gp.activity_flags["Birth details"] = "Yes"
            gp.remarks = f"Births Registered: {bgp.births_registered}"
        else:
            gp.activity_flags["Birth details"] = "No"

        gp.evaluate_pending(OFFICIAL_MAS_REPORT_ACTIVITIES)

    # 4. Prepare Mandal Abstract from ground-truth GP dataset
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

    report = DistrictMASReport(
        district_name=district_name or "Telangana District",
        financial_year=financial_year or "2026",
        month_name=month or "October",
        mandals=mandals,
        birth_mandals=birth_mandals,
    )
    report.calculate_totals()
    return report

"""Live two-stage Playwright scraper for GM-R 5.24 & GM-R 5.23 inside the shared EPTS session.

STRICT ZERO-DUPLICATE-LOGIN RULE:
This module NEVER launches a Playwright browser or asks for OTP. It operates
exclusively on the already-authenticated ``page`` (``bot.page``) owned by
``dsr.service`` / ``core.session_manager``.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_reports_dir
from mas.models import (
    ALL_18_LABELS,
    CANONICAL_18_MODULES,
    MANDALS_20,
    MOD_NAMES_524,
    clean_district_name,
    district_slug,
    get_month_number,
    is_module_excluded,
    is_summary_row_name,
    make_unique_key,
)
from mas.xpaths import XPATH_REGISTRY

logger = logging.getLogger(__name__)


def get_gmr_524_cache_path(month: str, year: int, district_name: str = "Khammam") -> Path:
    return get_reports_dir() / f"{district_slug(district_name)}_MAS_{month.capitalize()}_{year}_Consolidated_Data.json"


def get_gmr_523_cache_path(month: str, year: int, district_name: str = "Khammam") -> Path:
    return get_reports_dir() / f"{district_slug(district_name)}_Births_{month.capitalize()}_{year}_Lookup.json"


def _assert_session_not_redirected(page) -> None:
    """Detect EPTS upstream login redirects or closed pages and raise PermissionError."""
    if page is None or (hasattr(page, "is_closed") and page.is_closed()):
        raise PermissionError("e-Panchayat browser session is closed or inactive. Please log in once from the Console header.")
    try:
        cur_url = str(getattr(page, "url", "") or "").lower()
    except Exception:
        cur_url = ""
    if "login.aspx" in cur_url or "default.aspx" in cur_url and "psperformance" not in cur_url and "dashboard" not in cur_url:
        raise PermissionError("e-Panchayat portal redirected to Login. Your Department Login session expired; please re-authenticate once.")


def _find_psperformance_frame(page):
    """Locate the Playwright Frame hosting tgprepanchayat/PSPerformance inside my-iframe."""
    _assert_session_not_redirected(page)
    for frame in getattr(page, "frames", []) or []:
        if frame == getattr(page, "main_frame", None):
            continue
        f_name = (getattr(frame, "name", "") or "").lower()
        f_url = (getattr(frame, "url", "") or "").lower()
        if (
            f_name == "my-iframe"
            or "tgprepanchayat" in f_url
            or "psperformance" in f_url
            or "dynamicreports" in f_url
            or "gmr" in f_url
            or "gm-r" in f_url
        ):
            return frame
    try:
        handle = page.locator("iframe[name='my-iframe'], iframe#my-iframe").first.element_handle(timeout=1500)
        if handle:
            cf = handle.content_frame()
            if cf and (getattr(cf, "url", "") or "").lower() != "about:blank":
                return cf
    except Exception:
        pass
    return None


def _find_first_visible(scope, xpath_expr: str):
    """Return the first currently visible match for an XPath selector within `scope`."""
    try:
        matches = scope.locator(f"xpath={xpath_expr}").all()
        for loc in matches:
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                continue
    except Exception:
        pass
    return None


def _find_visible_gp_monitoring_link(page):
    """Find the exact 'GP Monitoring' top navigation trigger without matching 'GP Monitoring New'."""
    selectors = (
        "xpath=//a[normalize-space(.)='GP Monitoring'] | //input[@value='GP Monitoring']",
        XPATH_REGISTRY["gp_monitoring_menu"],
    )
    for sel in selectors:
        vis = _find_first_visible(page, sel.replace("xpath=", "", 1))
        if vis is not None:
            return vis
    return page.locator("xpath=//a[normalize-space(.)='GP Monitoring'] | //input[@value='GP Monitoring']").first


def _click_gp_monitoring_menu(page) -> None:
    """Ensure dashboard URL is active and click the top-level GP Monitoring trigger."""
    cur_url = str(getattr(page, "url", "") or "").lower()
    if "deptloginverified" not in cur_url:
        logger.info("[*] Navigating to authenticated dashboard deptLoginVerified before opening MAS...")
        page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)
        _assert_session_not_redirected(page)
        if "deptloginverified" not in str(getattr(page, "url", "") or "").lower():
            raise PermissionError(
                "Departmental portal session expired or not logged in. Please log in once from the Console header."
            )

    gp_menu = _find_visible_gp_monitoring_link(page)
    try:
        gp_menu.wait_for(state="visible", timeout=12000)
    except Exception:
        logger.info("[*] Reloading deptLoginVerified so top 'GP Monitoring' menu is visible...")
        page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)
        _assert_session_not_redirected(page)
        gp_menu = _find_visible_gp_monitoring_link(page)
        gp_menu.wait_for(state="visible", timeout=12000)

    try:
        gp_menu.hover()
        time.sleep(0.25)
    except Exception:
        pass
    gp_menu.click()


def _open_gmr_report_frame(page, report_num: str = "5.24"):
    """Navigate authenticated page -> GP Monitoring -> my-iframe -> GM-R 5 -> 5.24 or 5.23."""
    _assert_session_not_redirected(page)
    logger.info("[*] Navigating to GP Monitoring -> GM-R %s in shared EPTS Playwright session...", report_num)

    _click_gp_monitoring_menu(page)

    target_xpath = XPATH_REGISTRY["gmr_524_link"] if "5.24" in str(report_num) else XPATH_REGISTRY["gmr_523_link"]

    frame = None
    menu_ready = False
    deadline = time.time() + 25.0
    while time.time() < deadline:
        frame = _find_psperformance_frame(page)
        if frame:
            try:
                if (
                    frame.locator(XPATH_REGISTRY["gmr5_accordion"]).count() > 0
                    or frame.locator("text='Enlarge All'").count() > 0
                    or frame.locator(f"xpath={target_xpath}").count() > 0
                ):
                    menu_ready = True
                    break
            except Exception:
                pass
        time.sleep(0.4)

    if not frame or not menu_ready:
        _assert_session_not_redirected(page)
        frame_urls = [getattr(f, "url", "") for f in (getattr(page, "frames", []) or [])]
        raise RuntimeError(
            f"Could not load GP Monitoring reports menu inside portal iframe (my-iframe) for GM-R {report_num}. "
            f"Active URL={getattr(page, 'url', '')}, Frames={frame_urls}"
        )

    # Expand report folder if 5.24/5.23 link is still collapsed inside GM-R 5
    target_link = _find_first_visible(frame, target_xpath)
    if target_link is None:
        try:
            gmr5 = frame.locator(f"xpath={XPATH_REGISTRY['gmr5_accordion']}").first
            gmr5.wait_for(state="visible", timeout=10000)
            try:
                gmr5.scroll_into_view_if_needed()
            except Exception:
                pass
            gmr5.click()
            time.sleep(1.0)
            target_link = _find_first_visible(frame, target_xpath)
        except Exception as exc:
            logger.debug("GM-R 5 accordion click notice: %s", exc)

    if target_link is None:
        # Mirror DSR & GP Balance: try 'Enlarge All' when accordion item stays collapsed
        try:
            enlarge_btn = frame.locator("text='Enlarge All'").first
            if enlarge_btn.is_visible(timeout=2500):
                enlarge_btn.click()
                time.sleep(1.2)
                target_link = _find_first_visible(frame, target_xpath)
        except Exception as exc:
            logger.debug("Enlarge All click notice: %s", exc)

    if target_link is None:
        target_link = frame.locator(f"xpath={target_xpath}").first
        target_link.wait_for(state="visible", timeout=12000)

    try:
        target_link.scroll_into_view_if_needed()
    except Exception:
        pass
    target_link.click()

    deadline_ddl = time.time() + 25.0
    last_exc = None
    while time.time() < deadline_ddl:
        frame = _find_psperformance_frame(page) or frame
        try:
            ddl = frame.locator(f"xpath={XPATH_REGISTRY['ddl_month']}").first
            if ddl.is_visible():
                time.sleep(0.3)
                return frame
        except Exception as exc:
            last_exc = exc
        time.sleep(0.3)

    _assert_session_not_redirected(page)
    raise TimeoutError(
        f"Timed out waiting for Month dropdown inside GM-R {report_num} iframe (url={getattr(frame, 'url', '')}, err={last_exc})"
    )


def _submit_month_year_and_wait_table(frame, month_num: int, year: int, report_label: str = "GM-R 5.24") -> None:
    """Validate available Month/Year dropdowns inside frame, click Submit, and wait for GridView1."""
    logger.info("[*] Selecting Month=%d, Year=%d in %s...", month_num, year, report_label)

    try:
        dropdown_info = frame.evaluate(
            """() => {
                const getOpts = (sel) => {
                    const el = document.getElementById(sel) || document.querySelector(`select[id*='${sel.replace('ContentPlaceHolder1_', '')}']`);
                    return el ? Array.from(el.options).map(o => ({ value: String(o.value), text: (o.text || '').trim() })) : [];
                };
                return {
                    months: getOpts('ContentPlaceHolder1_ddlMonth'),
                    years: getOpts('ContentPlaceHolder1_ddlYear'),
                };
            }"""
        )
    except Exception:
        dropdown_info = None

    if isinstance(dropdown_info, dict):
        avail_years = [
            o["value"] for o in dropdown_info.get("years", [])
            if str(o.get("value", "")).strip() not in ("", "0")
            and "select" not in str(o.get("text", "")).lower()
        ]
        avail_year_texts = [
            o["text"] for o in dropdown_info.get("years", [])
            if str(o.get("value", "")).strip() not in ("", "0")
            and "select" not in str(o.get("text", "")).lower()
        ]
        if avail_years and str(year) not in avail_years and str(year) not in avail_year_texts:
            raise ValueError(
                f"Year {year} is not available in the e-Panchayat portal {report_label} dropdown "
                f"(available: {', '.join(avail_years)})."
            )

        avail_months = [
            o for o in dropdown_info.get("months", [])
            if str(o.get("value", "")).strip() not in ("", "0")
            and "select" not in str(o.get("text", "")).lower()
        ]
        month_names_chk = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        target_name_chk = month_names_chk[month_num] if 1 <= month_num <= 12 else ""
        if avail_months and not any(
            str(o.get("value", "")).strip() in (str(month_num), f"{month_num:02d}")
            or (target_name_chk and str(o.get("text", "")).strip().lower().startswith(target_name_chk.lower()[:3]))
            for o in avail_months
        ):
            avail_m_labels = [o.get("text") or o.get("value") for o in avail_months]
            raise ValueError(
                f"Month {target_name_chk or month_num} {year} is not yet available in portal {report_label} dropdown "
                f"(available: {', '.join(avail_m_labels)})."
            )

    yr_select = frame.locator(XPATH_REGISTRY["ddl_year"]).first
    mo_select = frame.locator(XPATH_REGISTRY["ddl_month"]).first

    try:
        yr_select.select_option(str(year))
    except Exception:
        yr_select.select_option(label=str(year))
    time.sleep(0.5)

    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    target_name = month_names[month_num] if 1 <= month_num <= 12 else "July"
    month_selected = False
    for opt in mo_select.locator("option").all():
        val = (opt.get_attribute("value") or "").strip()
        txt = (opt.inner_text() or "").strip()
        if (
            val == str(month_num)
            or val == f"{month_num:02d}"
            or txt.lower().startswith(target_name.lower()[:3])
        ):
            mo_select.select_option(value=val)
            month_selected = True
            break

    if not month_selected:
        mo_select.select_option(str(month_num))

    time.sleep(0.4)
    submit_btn = frame.locator(XPATH_REGISTRY["btn_submit"]).first
    submit_btn.wait_for(state="visible", timeout=10000)
    submit_btn.click()

    table_loc = frame.locator(XPATH_REGISTRY["gridview1"]).first
    table_loc.wait_for(state="visible", timeout=30000)
    time.sleep(0.8)

    try:
        frame.evaluate(
            """() => {
                const tbl = document.getElementById('ContentPlaceHolder1_GridView1');
                if (tbl && window.jQuery && window.jQuery.fn && window.jQuery.fn.DataTable && window.jQuery.fn.DataTable.isDataTable(tbl)) {
                    window.jQuery(tbl).DataTable().page.len(-1).draw();
                }
            }"""
        )
        time.sleep(0.3)
    except Exception:
        pass


def scrape_mandal_abstract_524(page, month: str, year: int) -> Tuple[List[Dict[str, Any]], Any]:
    """Scrapes the Mandal Abstract Table directly from GM-R 5.24 inside my-iframe."""
    month_num = get_month_number(month)
    logger.info("[*] [Stage 1A] Opening GM-R 5.24 inside GP Monitoring for %s %s...", month, year)

    frame = _open_gmr_report_frame(page, "5.24")
    _submit_month_year_and_wait_table(frame, month_num, year, "GM-R 5.24")

    js_parse_mandals = """
    (modNames) => {
        const table = document.getElementById("ContentPlaceHolder1_GridView1");
        if (!table) return null;
        const rows = Array.from(table.querySelectorAll("tr"));
        const mandals = [];

        for (let i = 0; i < rows.length; i++) {
            const cells = Array.from(rows[i].querySelectorAll("td")).map(c => c.innerText.trim());
            if (cells.length < 37) continue;

            const sno = parseInt(cells[0], 10);
            if (isNaN(sno)) continue;

            const mandalLink = rows[i].querySelector("a");
            const mandalName = (cells[1] || "").trim();
            if (!mandalName || /^(?:grand\\s+|district\\s+|mandal\\s+|sub[\\s-]*)?total$/i.test(mandalName)) continue;
            const hrefStr = mandalLink ? (mandalLink.getAttribute("href") || "") : "";
            const idStr = mandalLink ? (mandalLink.id || "") : "";
            const ctlMatch = hrefStr.match(/\\$(ctl\\d+)\\$/i) || idStr.match(/GridView1_(ctl\\d+)_/i);
            const ctl = ctlMatch ? ctlMatch[1] : `ctl${String(sno + 1).padStart(2, '0')}`;

            const noOfGps = parseInt(cells[2], 10) || 0;
            const modules = {};

            // GM-R 5.24 has 2 columns per module: Entered, Not Entered (3 + 17*2 = 37 cols)
            let colIdx = 3;
            let mTotalNotEntered = 0;
            modNames.forEach(mod => {
                const ent = parseInt(cells[colIdx], 10) || 0;
                const notEnt = parseInt(cells[colIdx + 1], 10) || 0;
                const denom = ent + notEnt;
                const pct = denom > 0 ? Math.round((ent / denom) * 10000) / 100 : 100.0;
                modules[mod] = {
                    entered: ent,
                    not_entered: notEnt,
                    pct: pct,
                    formatted_compact: `${notEnt} / ${ent}`
                };
                mTotalNotEntered += notEnt;
                colIdx += 2;
            });

            mandals.push({
                sno: sno,
                mandal_name: mandalName,
                ctl: ctl,
                no_of_gps: noOfGps,
                has_pendency: (mTotalNotEntered > 0),
                total_not_entered: mTotalNotEntered,
                modules: modules
            });
        }
        return mandals;
    }
    """
    mandals = frame.evaluate(js_parse_mandals, MOD_NAMES_524)
    if not mandals:
        raise RuntimeError(f"GM-R 5.24 returned 0 mandal rows for {month} {year}.")
    logger.info("[+] [Stage 1A] Live scraped %d Mandals from GM-R 5.24.", len(mandals))
    return mandals, frame


def scrape_pending_gps_data(
    frame,
    pending_mandals: List[Dict[str, Any]],
    month: str,
    year: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Dispatches ASP.NET __doPostBack via fetch inside frame_524 for pending mandals only."""
    if not pending_mandals:
        logger.info("[*] [Stage 3A] No pending mandals found in GM-R 5.24. Skipping GP drill-down.")
        return {}

    logger.info(
        "[*] [Stage 3A] Drilling down %d pending mandal(s) in GM-R 5.24: %s",
        len(pending_mandals),
        [p["mandal_name"] for p in pending_mandals],
    )

    js_script = """
    async (mandals) => {
        const form = document.forms[0];
        const url = document.location.href;
        const results = {};
        const parser = new DOMParser();

        for (const m of mandals) {
            const formData = new FormData(form);
            formData.set('__EVENTTARGET', `ctl00$ContentPlaceHolder1$GridView1$${m.ctl}$lblLevelNameMandal`);
            formData.set('__EVENTARGUMENT', '');

            try {
                const resp = await fetch(url, { method: 'POST', body: formData });
                const html = await resp.text();
                const subDoc = parser.parseFromString(html, 'text/html');
                const table = (
                    subDoc.getElementById('ContentPlaceHolder1_GridView2')
                    || subDoc.getElementById('ContentPlaceHolder1_GridView1')
                    || subDoc.querySelector('table')
                );
                const rows = table ? Array.from(table.querySelectorAll('tr')) : [];
                const gpRows = [];

                rows.forEach(r => {
                    const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
                    const gpName = (cells[1] || '').trim();
                    if (
                        cells.length >= 36
                        && /^\\d+$/.test(cells[0])
                        && gpName
                        && !/^(?:grand\\s+|district\\s+|mandal\\s+|sub[\\s-]*)?total$/i.test(gpName)
                    ) {
                        gpRows.push({
                            sno: parseInt(cells[0], 10),
                            gpName: gpName,
                            values: cells.slice(2)
                        });
                    }
                });
                results[m.mandal_name] = gpRows;
            } catch (err) {
                results[m.mandal_name] = [];
            }
        }
        return results;
    }
    """
    try:
        raw_gps_by_mandal = frame.evaluate(
            js_script,
            [{"ctl": p["ctl"], "mandal_name": p["mandal_name"]} for p in pending_mandals],
        )
        logger.info("[+] [Stage 3A] Live scraped GP drill-down rows for %d mandal(s).", len(raw_gps_by_mandal or {}))
        return raw_gps_by_mandal or {}
    except Exception as exc:
        logger.warning("[-] [Stage 3A] Failed during GP drill-down in GM-R 5.24: %s", exc)
        return {}


def scrape_mandal_births_523(
    page,
    month: str,
    year: int,
    include_gp_drilldown: bool = True,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Scrapes Mandal Births Summary (#GridView1) and optionally pending GP rows (#GridView2) from GM-R 5.23."""
    month_num = get_month_number(month)
    logger.info("[*] [Stage 1B] Opening GM-R 5.23 inside GP Monitoring for %s %s...", month, year)

    frame = _open_gmr_report_frame(page, "5.23")
    _submit_month_year_and_wait_table(frame, month_num, year, "GM-R 5.23")

    js_parse_births = """
    () => {
        const table = document.getElementById("ContentPlaceHolder1_GridView1");
        if (!table) return null;
        const rows = Array.from(table.querySelectorAll("tr"));
        const birthsMap = {};

        for (let i = 0; i < rows.length; i++) {
            const cells = Array.from(rows[i].querySelectorAll("td")).map(c => c.innerText.trim());
            if (cells.length < 5) continue;
            const sno = parseInt(cells[0], 10);
            if (isNaN(sno)) continue;

            const mandalLink = rows[i].querySelector("a");
            const mandalName = (cells[1] || "").trim();
            if (!mandalName || /^(?:grand\\s+|district\\s+|mandal\\s+|sub[\\s-]*)?total$/i.test(mandalName)) continue;
            const hrefStr = mandalLink ? (mandalLink.getAttribute("href") || "") : "";
            const idStr = mandalLink ? (mandalLink.id || "") : "";
            const ctlMatch = hrefStr.match(/\\$(ctl\\d+)\\$/i) || idStr.match(/GridView1_(ctl\\d+)_/i);
            const ctl = ctlMatch ? ctlMatch[1] : `ctl${String(sno + 1).padStart(2, '0')}`;

            const totalGps = parseInt(cells[2], 10) || 0;
            const registeredGps = parseInt(cells[3], 10) || 0;
            const balanceGps = parseInt(cells[4], 10) || 0;
            const birthsReg = cells.length > 5 ? (parseInt(cells[5], 10) || 0) : 0;
            const birthsEnt = cells.length > 6 ? (parseInt(cells[6], 10) || 0) : 0;
            const birthsBal = cells.length > 7 ? (parseInt(cells[7], 10) || 0) : 0;
            const denom = registeredGps + balanceGps;
            const pct = denom > 0 ? Math.round((registeredGps / denom) * 10000) / 100 : 100.0;

            birthsMap[mandalName] = {
                sno: sno,
                ctl: ctl,
                total_gps: totalGps,
                registered_gps: registeredGps,
                balance_gps: balanceGps,
                births_as_per_register: birthsReg,
                births_entered: birthsEnt,
                births_balance: birthsBal,
                pct: pct,
                has_pendency: (balanceGps > 0)
            };
        }
        return birthsMap;
    }
    """
    births_map = frame.evaluate(js_parse_births) or {}
    logger.info("[+] [Stage 1B] Live scraped %d Mandal Birth rows from GM-R 5.23.", len(births_map))

    mandals_to_drill = [
        {"ctl": v["ctl"], "mandal_name": m_name}
        for m_name, v in births_map.items()
        if v.get("balance_gps", 0) > 0 or v.get("births_balance", 0) > 0
    ]
    births_gp_lookup: Dict[str, Dict[str, Any]] = {}

    if include_gp_drilldown and mandals_to_drill:
        logger.info("[*] [Stage 3B] Drilling down %d mandal(s) in GM-R 5.23...", len(mandals_to_drill))
        js_drill_523 = """
        async (mandals) => {
            const form = document.forms[0];
            const url = document.location.href;
            const results = [];
            const parser = new DOMParser();

            for (const m of mandals) {
                const formData = new FormData(form);
                formData.set('__EVENTTARGET', `ctl00$ContentPlaceHolder1$GridView1$${m.ctl}$lblLevelNameMandal`);
                formData.set('__EVENTARGUMENT', '');
                try {
                    const resp = await fetch(url, { method: 'POST', body: formData });
                    const html = await resp.text();
                    const subDoc = parser.parseFromString(html, 'text/html');
                    const table = subDoc.getElementById('ContentPlaceHolder1_GridView2');
                    if (!table) continue;
                    const rows = Array.from(table.querySelectorAll('tr'));
                    for (let i = 1; i < rows.length; i++) {
                        const cells = Array.from(rows[i].querySelectorAll('td')).map(c => c.innerText.trim());
                        const gpName = (cells[1] || '').trim();
                        if (
                            cells.length >= 7
                            && /^\\d+$/.test(cells[0])
                            && gpName
                            && !/^(?:grand\\s+|district\\s+|mandal\\s+|sub[\\s-]*)?total$/i.test(gpName)
                        ) {
                            results.push({
                                mandal: m.mandal_name,
                                gpName: gpName,
                                gpsEnteredData: cells[2],
                                balanceGpsDataToEnter: cells[3],
                                birthsAsPerRegister: cells[4],
                                birthsEntered: cells[5],
                                balanceToBeEntered: cells[6]
                            });
                        }
                    }
                } catch (e) {}
            }
            return results;
        }
        """
        gp_rows_523 = frame.evaluate(js_drill_523, mandals_to_drill) or []
        for g in gp_rows_523:
            m_name = g.get("mandal", "")
            gp_name = g.get("gpName", "")
            if is_summary_row_name(gp_name):
                continue
            ukey = make_unique_key(m_name, gp_name)
            bal_gps = int(g.get("balanceGpsDataToEnter") or 0)
            bal_births = int(g.get("balanceToBeEntered") or 0)
            status = "Pending" if bal_gps > 0 else "Entered"
            births_gp_lookup[ukey] = {
                "mandal_523": m_name,
                "gp_523": gp_name,
                "births_data_entered": status,
                "balance_gps_data_to_enter": bal_gps,
                "balance_to_be_entered": bal_births,
            }
        logger.info("[+] [Stage 3B] Scraped %d GP Birth rows across pending mandals.", len(births_gp_lookup))

    return births_map, births_gp_lookup


def find_mandal_pendency(
    mandals_524: List[Dict[str, Any]],
    births_523: Optional[Dict[str, Dict[str, Any]]] = None,
    excluded_modules: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge 17 MAS modules (GM-R 5.24) and Birth Details (GM-R 5.23) into full 18-module abstract."""
    if excluded_modules is None:
        excluded_modules = ["Payment of Electricity", "Expenditure", "Cheque Details"]
    clean_excluded = {x.strip().lower() for x in excluded_modules}

    full_abstract: List[Dict[str, Any]] = []
    pending_mandals: List[Dict[str, Any]] = []

    for m in mandals_524:
        m_name = m["mandal_name"]
        m_ctl = m.get("ctl", "ctl02")
        no_gps = m["no_of_gps"]
        mods = copy.deepcopy(m.get("modules", {}))

        if births_523 and m_name in births_523:
            b_info = births_523[m_name]
            b_ent = b_info["registered_gps"]
            b_not = b_info["balance_gps"]
            b_pct = b_info["pct"]
            mods["Birth Details"] = {
                "entered": b_ent,
                "not_entered": b_not,
                "pct": b_pct,
                "formatted_compact": f"{b_not} / {b_ent}",
            }
        elif "Birth Details" not in mods:
            mods["Birth Details"] = {
                "entered": no_gps,
                "not_entered": 0,
                "pct": 100.0,
                "formatted_compact": f"0 / {no_gps}",
            }

        pending_in_mandal: List[str] = []
        tot_entered_included = 0
        tot_possible_included = 0

        for label in ALL_18_LABELS:
            is_excl = is_module_excluded(label, clean_excluded)

            m_mod_data = None
            if label in mods:
                m_mod_data = mods[label]
            else:
                for k, v in mods.items():
                    if (
                        k.lower() == label.lower()
                        or (label == "Recipts" and k.lower() == "receipts")
                        or (label == "Receipts" and k.lower() == "recipts")
                    ):
                        m_mod_data = v
                        break

            if m_mod_data is None:
                m_mod_data = {"entered": no_gps, "not_entered": 0, "pct": 100.0}

            m_mod_data["formatted_compact"] = f"{m_mod_data['not_entered']} / {m_mod_data['entered']}"
            m_mod_data["is_excluded"] = is_excl
            mods[label] = m_mod_data
            if label == "Recipts":
                mods["Receipts"] = m_mod_data
            elif label == "Receipts":
                mods["Recipts"] = m_mod_data

            if not is_excl:
                tot_entered_included += m_mod_data["entered"]
                mod_total = m_mod_data["entered"] + m_mod_data["not_entered"]
                tot_possible_included += mod_total
                if m_mod_data["not_entered"] > 0:
                    pending_in_mandal.append(label)

        has_pendency = len(pending_in_mandal) > 0
        overall_pct = round((tot_entered_included / tot_possible_included * 100), 2) if tot_possible_included > 0 else 100.0

        m_record = {
            "sno": m.get("sno", len(full_abstract) + 1),
            "mandal_name": m_name,
            "ctl": m_ctl,
            "no_of_gps": no_gps,
            "overall_pct": overall_pct,
            "has_pendency": has_pendency,
            "pending_modules": pending_in_mandal,
            "pending_modules_count": len(pending_in_mandal),
            "modules": mods,
        }
        full_abstract.append(m_record)
        if has_pendency:
            pending_mandals.append(m_record)

    logger.info(
        "[+] [Stage 2] Pendency Analysis Complete: %d Pending Mandal(s): %s. %d Mandal(s) 100%% Compliant.",
        len(pending_mandals),
        [p["mandal_name"] for p in pending_mandals],
        len(full_abstract) - len(pending_mandals),
    )
    return full_abstract, pending_mandals


def get_master_gp_registry(district_name: str = "Khammam") -> Dict[str, List[str]]:
    """Retrieve fallback GP directory grouped by Mandal for 100%-compliant mandals."""
    if clean_district_name(district_name).lower() != "khammam":
        return {}
    july_path = get_reports_dir() / "Khammam_MAS_July_2026_Consolidated_Data.json"
    if july_path.exists():
        try:
            d = json.loads(july_path.read_text(encoding="utf-8"))
            mapping: Dict[str, List[str]] = {}
            for g in d.get("gram_panchayats", []):
                mapping.setdefault(g["Mandal"], []).append(g["Gram_Panchayat"])
            return mapping
        except Exception:
            pass
    return {m["name"]: [] for m in MANDALS_20}


def assemble_full_gp_list_and_action_list(
    mandal_abstract: List[Dict[str, Any]],
    pending_gps_by_mandal: Dict[str, List[Dict[str, Any]]],
    births_lookup: Optional[Dict[str, Any]] = None,
    excluded_modules: Optional[List[str]] = None,
    district_name: str = "Khammam",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Combine 100%-compliant mandals and pending mandal live-scraped GP records."""
    if excluded_modules is None:
        excluded_modules = ["Payment of Electricity", "Expenditure", "Cheque Details"]
    clean_excluded = {x.strip().lower() for x in excluded_modules}

    gp_registry = get_master_gp_registry(district_name=district_name)
    all_gps: List[Dict[str, Any]] = []
    pending_action_list: List[Dict[str, Any]] = []

    n_included = len([m for m in CANONICAL_18_MODULES if not is_module_excluded(m[0], clean_excluded)]) or 18

    for m_info in mandal_abstract:
        m_name = m_info["mandal_name"]
        m_no_gps = int(m_info.get("no_of_gps") or 0)
        gp_names = gp_registry.get(m_name, [])
        if len(gp_names) != m_no_gps and m_no_gps > 0:
            gp_names = gp_names[:m_no_gps] + [f"{m_name} GP {k}" for k in range(len(gp_names) + 1, m_no_gps + 1)]

        has_pendency = m_info.get("has_pendency", False)
        raw_scraped_pending = pending_gps_by_mandal.get(m_name, [])
        scraped_pending = []
        seen_mandal_ukeys = set()
        for item in raw_scraped_pending:
            gname = (item.get("gpName") or "").strip()
            if is_summary_row_name(gname):
                continue
            uk = make_unique_key(m_name, gname)
            if uk in seen_mandal_ukeys:
                continue
            seen_mandal_ukeys.add(uk)
            scraped_pending.append(item)
        if m_no_gps > 0 and len(scraped_pending) > m_no_gps:
            logger.warning(
                "[-] Mandal %s scraped %d GP rows vs %d expected in 5.24; capping to %d.",
                m_name, len(scraped_pending), m_no_gps, m_no_gps,
            )
            scraped_pending = scraped_pending[:m_no_gps]

        if scraped_pending:
            for item in scraped_pending:
                gp_name = (item.get("gpName") or "").strip()
                raw_vals = item.get("values", [])
                ukey = make_unique_key(m_name, gp_name)

                b_status = "Entered"
                if births_lookup and ukey in births_lookup:
                    b_status = births_lookup[ukey].get("births_data_entered", "Entered")

                rec: Dict[str, Any] = {
                    "Unique_Key": ukey,
                    "Mandal": m_name,
                    "GP_SNo": item.get("sno", len(all_gps) + 1),
                    "Gram_Panchayat": gp_name,
                    "Births_Data_Entered": b_status,
                }
                pending_mods = []
                for idx, (state_label, mod_524, mas_col) in enumerate(CANONICAL_18_MODULES[:17]):
                    not_ent_val = int(raw_vals[idx * 2 + 1]) if len(raw_vals) > idx * 2 + 1 and str(raw_vals[idx * 2 + 1]).isdigit() else 0
                    status = "Pending" if not_ent_val > 0 else "Completed"
                    rec[state_label] = status
                    rec[mod_524] = status
                    rec[mas_col] = status
                    if status == "Pending" and not is_module_excluded(state_label, clean_excluded):
                        pending_mods.append(state_label)

                rec["Birth Details"] = b_status
                rec["Births_Data_Entered"] = b_status
                if b_status == "Pending" and not is_module_excluded("Birth Details", clean_excluded):
                    pending_mods.append("Birth Details")

                rec["Activities_Completed"] = n_included - len(pending_mods)
                rec["Total_Activities"] = n_included
                rec["Completion_Rate"] = round(((n_included - len(pending_mods)) / n_included) * 100, 2)
                rec["Compliance_Status"] = "Compliant" if len(pending_mods) == 0 else "Action Required"
                all_gps.append(rec)

                if pending_mods:
                    pending_action_list.append({
                        "S No": len(pending_action_list) + 1,
                        "Mandal": m_name,
                        "Gram_Panchayat": gp_name,
                        "Pending_Count": len(pending_mods),
                        "Pending_Modules": ", ".join(pending_mods),
                        "Completed_Count": n_included - len(pending_mods),
                        "Total_Activities": n_included,
                        "Completion_Rate": f"{rec['Completion_Rate']}%",
                        "Action_Required": "Immediate follow-up by MPO / PS",
                    })
        else:
            m_mods = m_info.get("modules", {})
            b_mod = m_mods.get("Birth Details", {})
            b_not = int(b_mod.get("not_entered", 0) or 0)
            b_ent = int(b_mod.get("entered", len(gp_names)) or 0)

            for idx, gp_name in enumerate(gp_names, 1):
                ukey = make_unique_key(m_name, gp_name)
                b_st = "Entered"
                if births_lookup and ukey in births_lookup:
                    b_st = births_lookup[ukey].get("births_data_entered", "Entered")
                elif b_not > 0 and idx > b_ent:
                    b_st = "Pending"

                rec = {
                    "Unique_Key": ukey,
                    "Mandal": m_name,
                    "GP_SNo": idx,
                    "Gram_Panchayat": gp_name,
                    "Births_Data_Entered": b_st,
                }
                pending_mods = []
                for state_label, mod_524, mas_col in CANONICAL_18_MODULES[:17]:
                    if not has_pendency:
                        status = "Completed"
                    else:
                        m_mod_data = m_mods.get(state_label)
                        if not m_mod_data:
                            for k, v in m_mods.items():
                                if k.lower() == state_label.lower() or k.lower() == mod_524.lower():
                                    m_mod_data = v
                                    break
                        not_ent = int(m_mod_data.get("not_entered", 0) or 0) if m_mod_data else 0
                        ent_count = int(m_mod_data.get("entered", len(gp_names)) or 0) if m_mod_data else len(gp_names)
                        status = "Completed" if not_ent == 0 else ("Completed" if idx <= ent_count else "Pending")
                    rec[state_label] = status
                    rec[mod_524] = status
                    rec[mas_col] = status
                    if status == "Pending" and not is_module_excluded(state_label, clean_excluded):
                        pending_mods.append(state_label)

                rec["Birth Details"] = b_st
                rec["Births_Data_Entered"] = b_st
                if b_st == "Pending" and not is_module_excluded("Birth Details", clean_excluded):
                    pending_mods.append("Birth Details")

                rec["Activities_Completed"] = n_included - len(pending_mods)
                rec["Total_Activities"] = n_included
                rec["Completion_Rate"] = round(((n_included - len(pending_mods)) / n_included) * 100, 2)
                rec["Compliance_Status"] = "Compliant" if len(pending_mods) == 0 else "Action Required"
                all_gps.append(rec)

                if pending_mods:
                    pending_action_list.append({
                        "S No": len(pending_action_list) + 1,
                        "Mandal": m_name,
                        "Gram_Panchayat": gp_name,
                        "Pending_Count": len(pending_mods),
                        "Pending_Modules": ", ".join(pending_mods),
                        "Completed_Count": n_included - len(pending_mods),
                        "Total_Activities": n_included,
                        "Completion_Rate": f"{rec['Completion_Rate']}%",
                        "Action_Required": "Immediate follow-up by MPO / PS",
                    })

    return all_gps, pending_action_list


def _generate_district_master_from_live(
    mandal_abstract: List[Dict[str, Any]],
    births_map: Dict[str, Dict[str, Any]],
    all_gps: List[Dict[str, Any]],
    pending_action_list: List[Dict[str, Any]],
    month: str,
    year: int,
    district_name: str = "Khammam",
) -> Dict[str, Any]:
    return {
        "district": clean_district_name(district_name),
        "month": month.capitalize(),
        "year": year,
        "total_mandals": len(mandal_abstract),
        "total_gps": len(all_gps),
        "pending_gps_count": len(pending_action_list),
        "mandal_abstract": mandal_abstract,
        "births_523": births_map,
        "gram_panchayats": all_gps,
        "pending_action_list": pending_action_list,
    }


def _load_or_build_local_data(
    month: str,
    year: int,
    excluded_modules: Optional[List[str]] = None,
    district_name: str = "Khammam",
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], str]:
    """Load cached GM-R 5.24 + GM-R 5.23 JSON files if present when non-strict fallback is allowed."""
    p524 = get_gmr_524_cache_path(month, year, district_name=district_name)
    p523 = get_gmr_523_cache_path(month, year, district_name=district_name)

    if p524.exists() and p523.exists():
        d524 = json.loads(p524.read_text(encoding="utf-8"))
        d523 = json.loads(p523.read_text(encoding="utf-8"))

        clean_excluded = {x.strip().lower() for x in (excluded_modules or [])}
        all_gps = []
        pending_action_list = []

        if "mandal_abstract" in d524 and "gram_panchayats" in d524:
            mandal_abs = d524["mandal_abstract"]
            all_gps = d524["gram_panchayats"]
            if excluded_modules is not None:
                n_included = len([m for m in CANONICAL_18_MODULES if not is_module_excluded(m[0], clean_excluded)]) or 18
                recalculated = []
                for g in all_gps:
                    pend = [
                        st for st, _, _ in CANONICAL_18_MODULES
                        if not is_module_excluded(st, clean_excluded)
                        and g.get(st, "Completed") == "Pending"
                    ]
                    if pend:
                        recalculated.append({
                            "S No": len(recalculated) + 1,
                            "Mandal": g["Mandal"],
                            "Gram_Panchayat": g["Gram_Panchayat"],
                            "Pending_Count": len(pend),
                            "Pending_Modules": ", ".join(pend),
                            "Completed_Count": n_included - len(pend),
                            "Total_Activities": n_included,
                            "Completion_Rate": f"{round(((n_included - len(pend)) / n_included) * 100, 2)}%",
                            "Action_Required": "Immediate follow-up by MPO / PS",
                        })
                pending_action_list = recalculated
            else:
                pending_action_list = d524.get("pending_action_list", [])
            return mandal_abs, d523.get("births_map", {}), all_gps, d523.get("lookup", {}), "cached_consolidated"

    raise FileNotFoundError(
        f"No live session or cached MAS report files found for {clean_district_name(district_name)} ({month} {year})."
    )


def get_or_create_monthly_data(
    month: str,
    year: int,
    page=None,
    excluded_modules: Optional[List[str]] = None,
    force_refresh: bool = False,
    strict_live: bool = False,
    district_name: str = "Khammam",
    include_gp_data: bool = True,
) -> Dict[str, Any]:
    """Two-stage live pipeline using the shared authenticated EPTS page.

    When ``strict_live=True``, requires an open, authenticated ``page`` (never
    serves stale disk files) and raises ``PermissionError`` when the session or
    page is unavailable or expired.
    """
    clean_dist = clean_district_name(district_name)
    if excluded_modules is None:
        excluded_modules = ["Payment of Electricity", "Expenditure", "Cheque Details"]

    p524 = get_gmr_524_cache_path(month, year, district_name=clean_dist)
    p523 = get_gmr_523_cache_path(month, year, district_name=clean_dist)

    if strict_live and (page is None or (hasattr(page, "is_closed") and page.is_closed())):
        raise PermissionError(
            "Department Login & OTP session browser is not active. Please log in once from the Console header."
        )

    if not strict_live and not force_refresh and p524.exists() and p523.exists():
        try:
            mandal_abs, births_map, all_gps, births_lookup, _ = _load_or_build_local_data(
                month, year, excluded_modules, district_name=clean_dist
            )
            full_abs, pending_mandals = find_mandal_pendency(mandal_abs, births_map, excluded_modules)
            if not all_gps:
                all_gps, pending_action = assemble_full_gp_list_and_action_list(
                    full_abs, {}, births_lookup, excluded_modules, district_name=clean_dist
                )
            else:
                all_gps, pending_action = assemble_full_gp_list_and_action_list(
                    full_abs, {}, births_lookup, excluded_modules, district_name=clean_dist
                )
            return {
                "mandal_abstract": full_abs,
                "pending_mandals": pending_mandals,
                "births_map": births_map,
                "births_lookup": births_lookup,
                "all_gps": all_gps,
                "pending_action_list": pending_action,
                "data_source": "cached",
                "include_gp_data": include_gp_data,
                "district": clean_dist,
            }
        except Exception as exc:
            logger.warning("Failed loading cached data cleanly, falling back to live if page open: %s", exc)

    if page is not None:
        try:
            mandals_524, frame_524 = scrape_mandal_abstract_524(page, month, year)
            births_523, births_gp_lookup = scrape_mandal_births_523(
                page, month, year, include_gp_drilldown=include_gp_data
            )
            full_abstract, pending_mandals = find_mandal_pendency(mandals_524, births_523, excluded_modules)

            if include_gp_data:
                if pending_mandals:
                    frame_524 = _open_gmr_report_frame(page, "5.24")
                    _submit_month_year_and_wait_table(frame_524, get_month_number(month), year, "GM-R 5.24")
                    pending_gps_by_mandal = scrape_pending_gps_data(frame_524, pending_mandals, month, year)
                else:
                    pending_gps_by_mandal = {}
            else:
                logger.info(
                    "[*] Report type 'abstract_only': skipping GP-wise drill-down across %d pending mandal(s).",
                    len(pending_mandals),
                )
                pending_gps_by_mandal = {}

            all_gps, pending_action_list = assemble_full_gp_list_and_action_list(
                full_abstract,
                pending_gps_by_mandal,
                births_gp_lookup,
                excluded_modules,
                district_name=clean_dist,
            )

            master_524 = _generate_district_master_from_live(
                full_abstract, births_523, all_gps, pending_action_list, month, year, district_name=clean_dist
            )
            p524.parent.mkdir(parents=True, exist_ok=True)
            p524.write_text(json.dumps(master_524, indent=2), encoding="utf-8")
            p523.write_text(
                json.dumps({"births_map": births_523, "lookup": births_gp_lookup}, indent=2),
                encoding="utf-8",
            )

            return {
                "mandal_abstract": full_abstract,
                "pending_mandals": pending_mandals,
                "births_map": births_523,
                "births_lookup": births_gp_lookup,
                "all_gps": all_gps,
                "pending_action_list": pending_action_list,
                "data_source": "live_two_stage_webscrape",
                "include_gp_data": include_gp_data,
                "district": clean_dist,
            }
        except PermissionError:
            raise
        except Exception as exc:
            logger.exception("[-] Live two-stage scrape failed: %s", exc)
            if strict_live:
                raise RuntimeError(
                    f"Live webscrape failed while fetching {month} {year} from EPTS portal: {exc}"
                ) from exc

    if strict_live:
        raise PermissionError("Live EPTS session is required. Cached disk fallback is disabled in live mode.")

    mandal_abs, births_map, all_gps, births_lookup, _ = _load_or_build_local_data(
        month, year, excluded_modules, district_name=clean_dist
    )
    full_abs, pending_mandals = find_mandal_pendency(mandal_abs, births_map, excluded_modules)
    return {
        "mandal_abstract": full_abs,
        "pending_mandals": pending_mandals,
        "births_map": births_map,
        "births_lookup": births_lookup,
        "all_gps": all_gps,
        "pending_action_list": [],
        "data_source": "local_fallback",
        "include_gp_data": include_gp_data,
        "district": clean_dist,
    }

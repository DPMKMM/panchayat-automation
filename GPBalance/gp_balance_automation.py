"""Playwright Automation Pipeline for GP Balance Entry Report (GM-R 14.2).

Performs exact sequence:
  1. GP Monitoring Menu Selection
  2. Enlarge All & Expand 'GM-R 14. Reports on Balances of GP Account'
  3. Click 'GM-R 14.2 Report on Data Entered GPs'
  4. Detect Thursday dates dropdown
  5. Select target Thursday date and click Submit
  6. Extract Mandal-wise Abstract with % Data Entered
  7. Drill-down into Mandals with pending data (ignoring PMAGY)
  8. Return DistrictBalanceReport with matched Secretary details
"""

import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

from .gp_balance_models import (
    ACTIVE_ACCOUNTS,
    DistrictBalanceReport,
    GPBalanceDetail,
    MandalBalanceSummary,
)

logger = logging.getLogger("gp_balance_automation")

def get_my_iframe(page):
    """Returns the content iframe named 'my-iframe' or holding PSPerformance/DynamicReports."""
    for f in page.frames:
        if f.name == "my-iframe" or "PSPerformance" in f.url or "DynamicReports" in f.url:
            return f
    if len(page.frames) > 2:
        return page.frames[2]
    return None


def fetch_available_thursday_dates(bot) -> list[str]:
    """Navigates to GM-R 14.2 and extracts the available Thursday dates from the dropdown."""
    page = bot.page
    bot.select_menu("GP Monitoring")
    time.sleep(2.5)

    iframe = get_my_iframe(page)
    if not iframe:
        time.sleep(2)
        iframe = get_my_iframe(page)
    if not iframe:
        raise RuntimeError("Could not locate 'my-iframe' after selecting GP Monitoring.")

    try:
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    # Click Enlarge All
    try:
        enlarge_btn = iframe.locator("text='Enlarge All'").first
        if enlarge_btn.is_visible(timeout=3000):
            enlarge_btn.click()
            time.sleep(1)
    except Exception:
        pass

    # Expand GM-R 14
    try:
        gmr14_header = iframe.locator("text*='Reports on Balances'").first
        if gmr14_header.is_visible(timeout=3000):
            gmr14_header.click()
            time.sleep(1.5)
    except Exception:
        pass

    # Click GM-R 14.2
    link_14_2 = iframe.locator("a:has-text('14.2'), a:has-text('Report on Data Entered GPs')").first
    link_14_2.wait_for(state="visible", timeout=10000)
    link_14_2.click()
    time.sleep(2.5)

    # Extract select options
    dates = iframe.evaluate("""() => {
        const sel = document.querySelector("select");
        if (!sel) return [];
        return Array.from(sel.options)
            .map(o => o.text.trim())
            .filter(t => t && t !== '--Select--' && t.match(/\\d{2}-\\d{2}-\\d{4}/));
    }""")
    return dates


def run_balance_automation(bot, target_date: str = "") -> DistrictBalanceReport:
    """Executes the full automated scraping pipeline for GM-R 14.2."""
    page = bot.page
    district_name = "Khammam"

    # Automatically dismiss alert dialogs
    def on_dialog(dialog):
        print(f"[!] Balance Alert dialog: {dialog.message} - accepting...", flush=True)
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", on_dialog)

    # 1. Select GP Monitoring
    print("[*] Navigating to GP Monitoring -> GM-R 14.2...", flush=True)
    bot.select_menu("GP Monitoring")
    time.sleep(2.5)

    iframe = get_my_iframe(page)
    if not iframe:
        time.sleep(2)
        iframe = get_my_iframe(page)
    if not iframe:
        raise RuntimeError("Could not locate 'my-iframe' in portal.")

    try:
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    # 2. Click Enlarge All
    try:
        enlarge_btn = iframe.locator("text='Enlarge All'").first
        if enlarge_btn.is_visible(timeout=3000):
            enlarge_btn.click()
            time.sleep(1)
    except Exception:
        pass

    # 3. Expand GM-R 14
    try:
        gmr14_header = iframe.locator("text*='Reports on Balances'").first
        if gmr14_header.is_visible(timeout=3000):
            gmr14_header.click()
            time.sleep(1.5)
    except Exception:
        pass

    # 4. Click GM-R 14.2
    link_14_2 = iframe.locator("a:has-text('14.2'), a:has-text('Report on Data Entered GPs')").first
    link_14_2.wait_for(state="visible", timeout=12000)
    link_14_2.click()
    time.sleep(3)

    # 5. Handle Thursday Date Selection
    available_dates = iframe.evaluate("""() => {
        const sel = document.querySelector("select");
        if (!sel) return [];
        return Array.from(sel.options)
            .map(o => ({ value: o.value, text: o.text.trim() }))
            .filter(o => o.text && o.text !== '--Select--');
    }""")

    selected_date_text = ""
    if available_dates:
        # Match target_date or pick latest (first option)
        chosen_opt = available_dates[0]
        if target_date:
            for opt in available_dates:
                if target_date.strip() in opt["text"]:
                    chosen_opt = opt
                    break

        selected_date_text = chosen_opt["text"]
        val = chosen_opt["value"]
        print(f"[+] Selecting Thursday Balance Date: {selected_date_text} (value={val})", flush=True)

        iframe.evaluate(f"""() => {{
            const sel = document.querySelector("select");
            if (sel) {{
                sel.value = "{val}";
                sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""")
        time.sleep(1)
    else:
        selected_date_text = target_date or datetime.now().strftime("%d-%m-%Y")

    # 6. Click Submit
    print("[*] Clicking 'Submit' button...", flush=True)
    submit_btn = iframe.locator("button:has-text('Submit'), input[value='Submit'], input[type='submit']").first
    submit_btn.wait_for(state="visible", timeout=10000)
    submit_btn.click()
    time.sleep(4)

    # 7. Ensure table entries dropdown shows all (select 32 or 50 or 100)
    try:
        iframe.evaluate("""() => {
            const lenSel = document.querySelector("select[name*='length' i], select[name*='entries' i]");
            if (lenSel) {
                // Find highest value
                const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n));
                const maxVal = Math.max(...vals);
                lenSel.value = maxVal.toString();
                lenSel.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }
        }""")
        time.sleep(2)
    except Exception:
        pass

    # 8. Scrape Mandal Summary Table
    print("[*] Extracting Mandal Summary Table from page DOM...", flush=True)
    mandal_rows_raw = iframe.evaluate("""() => {
        const rows = document.querySelectorAll("table tbody tr");
        const results = [];
        for (const r of rows) {
            const cells = Array.from(r.querySelectorAll("td")).map(td => td.innerText.trim());
            if (cells.length >= 10 && cells[0].match(/^\\d+$/)) {
                const name = cells[1].trim();
                // STRICTLY skip the summary row (TOTAL / GRAND TOTAL / DISTRICT TOTAL) to avoid double-counting!
                if (name.toUpperCase().includes("TOTAL") || name.toUpperCase().includes("DISTRICT")) {
                    continue;
                }
                const mandalLink = r.querySelector("a");
                results.push({
                    s_no: results.length + 1,
                    mandal_name: name,
                    has_link: !!mandalLink,
                    total_gps: parseInt(cells[2]) || 0,
                    entered_gps: parseInt(cells[3]) || 0,
                    not_entered_gps: parseInt(cells[4]) || 0,
                    gp_pd: parseInt(cells[5]) || 0,
                    tgbpass: parseInt(cells[6]) || 0,
                    fc15_tied: parseInt(cells[7]) || 0,
                    fc15_untied: parseInt(cells[8]) || 0,
                    pmagy: parseInt(cells[9]) || 0, // Ignored
                    vwsc: parseInt(cells[10]) || 0,
                    mgnregs: parseInt(cells[11]) || 0,
                });
            }
        }
        return results;
    }""")

    mandals_list: list[MandalBalanceSummary] = []
    for r in mandal_rows_raw:
        m_name = r["mandal_name"].strip()
        # Extra safety check against TOTAL / summary row
        if "TOTAL" in m_name.upper() or "DISTRICT" in m_name.upper():
            continue

        m = MandalBalanceSummary(
            s_no=len(mandals_list) + 1,
            mandal_name=m_name,
            total_gps=r["total_gps"],
            entered_gps=r["entered_gps"],
            not_entered_gps=r["not_entered_gps"],
            gp_pd_updated=r["gp_pd"],
            tgbpass_updated=r["tgbpass"],
            fc15_tied_updated=r["fc15_tied"],
            fc15_untied_updated=r["fc15_untied"],
            vwsc_updated=r["vwsc"],
            mgnregs_updated=r["mgnregs"],
        )
        m.calculate_metrics()
        mandals_list.append(m)

    # 9. Drill Down for Mandals with Pending Entries
    pending_mandals = [m for m in mandals_list if m.has_pending]
    print(f"[*] Found {len(pending_mandals)} Mandal(s) with pending balance entries to drill down: {[m.mandal_name for m in pending_mandals]}", flush=True)

    for m in pending_mandals:
        # Extra safety check: never drill down into TOTAL
        if "TOTAL" in m.mandal_name.strip().upper() or "DISTRICT" in m.mandal_name.strip().upper():
            continue

        try:
            print(f"[*] Drilling down into Mandal: {m.mandal_name} ...", flush=True)

            # Ensure entries dropdown shows maximum entries so all rows are rendered
            try:
                iframe.evaluate("""() => {
                    const lenSel = document.querySelector("select[name*='length' i], select[name*='entries' i]");
                    if (lenSel) {
                        const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n));
                        if (vals.length > 0) {
                            const maxVal = Math.max(...vals);
                            if (lenSel.value !== maxVal.toString()) {
                                lenSel.value = maxVal.toString();
                                lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                    }
                }""")
                time.sleep(0.8)
            except Exception:
                pass

            # Click link for this mandal directly via DOM
            clicked = iframe.evaluate("""(targetMandal) => {
                const rows = document.querySelectorAll("table tbody tr");
                for (const r of rows) {
                    const cells = r.querySelectorAll("td");
                    if (cells.length >= 2) {
                        const name = cells[1].innerText.trim();
                        if (name.toLowerCase() === targetMandal.toLowerCase()) {
                            const link = r.querySelector("a");
                            if (link) {
                                link.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }""", m.mandal_name)

            if not clicked:
                mandal_link = iframe.locator(f"a:has-text('{m.mandal_name}')").first
                if mandal_link.is_visible(timeout=2000):
                    mandal_link.click()
                    clicked = True

            if clicked:
                time.sleep(2.5)

                # Ensure GP table displays all entries
                try:
                    iframe.evaluate("""() => {
                        const lenSel = document.querySelector("select[name*='length' i], select[name*='entries' i]");
                        if (lenSel) {
                            const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n));
                            if (vals.length > 0) {
                                lenSel.value = Math.max(...vals).toString();
                                lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                    }""")
                    time.sleep(1)
                except Exception:
                    pass

                # Scrape GP details
                gp_rows_raw = iframe.evaluate("""() => {
                    const rows = document.querySelectorAll("table tbody tr");
                    const gps = [];
                    for (const r of rows) {
                        const cells = Array.from(r.querySelectorAll("td")).map(td => td.innerText.trim());
                        if (cells.length >= 9 && cells[0].match(/^\\d+$/)) {
                            gps.push({
                                s_no: parseInt(cells[0]) || 0,
                                panchayat_name: cells[1],
                                entered: cells[2] === "1",
                                gp_pd: cells[4],
                                tgbpass: cells[5],
                                fc15_tied: cells[6],
                                fc15_untied: cells[7],
                                pmagy: cells[8], // Ignored
                                vwsc: cells[9],
                                mgnregs: cells[10]
                            });
                        }
                    }
                    return gps;
                }""")

                m.pending_gps = []
                for gp_raw in gp_rows_raw:
                    gp = GPBalanceDetail(
                        s_no=gp_raw["s_no"],
                        mandal_name=m.mandal_name,
                        panchayat_name=gp_raw["panchayat_name"],
                        entered=gp_raw["entered"],
                        gp_pd=gp_raw["gp_pd"],
                        tgbpass=gp_raw["tgbpass"],
                        fc15_tied=gp_raw["fc15_tied"],
                        fc15_untied=gp_raw["fc15_untied"],
                        vwsc=gp_raw["vwsc"],
                        mgnregs=gp_raw["mgnregs"],
                    )
                    gp.evaluate_pending()
                    if gp.is_pending:
                        m.pending_gps.append(gp)

                print(f"[+] Mandal {m.mandal_name}: Identified {len(m.pending_gps)} pending GP(s).", flush=True)

                # Click Back button
                iframe.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll("button, input[value='Back'], a"));
                    const b = btns.find(el => (el.innerText || el.value || "").trim().toLowerCase() === "back");
                    if (b) b.click();
                }""")
                time.sleep(2)

        except Exception as drill_err:
            logger.warning("Error drilling down into %s: %s", m.mandal_name, drill_err)
            try:
                iframe.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll("button, input[value='Back'], a"));
                    const b = btns.find(el => (el.innerText || el.value || "").trim().toLowerCase() === "back");
                    if (b) b.click();
                }""")
                time.sleep(2)
            except Exception:
                pass

    # Ensure all mandals with pending GPs have concrete GP records populated
    validate_pending_gps_from_portal(mandals_list)

    # Enrich the live scrape from the current online directory where it exposes
    # secretary fields. The DCB feed does not always contain those fields.
    match_secretary_details(mandals_list, district_name=district_name)

    # Detect district name dynamically from portal text / header
    try:
        header_text = iframe.evaluate("""() => {
            const el = document.body;
            return el ? el.innerText : "";
        }""")
        import re
        dist_match = re.search(r"[-—–:]\s*([A-Za-z\s]+?)\s+DISTRICT", header_text, re.IGNORECASE)
        if dist_match:
            candidate = dist_match.group(1).strip().title()
            if candidate and len(candidate) > 2:
                district_name = candidate
    except Exception:
        pass

    report = DistrictBalanceReport(
        district_name=district_name,
        report_date_str=selected_date_text,
        generated_at=datetime.now().strftime("%d-%b-%Y %I:%M %p"),
        mandals=mandals_list,
    )
    report.compute_totals()
    return report


def validate_pending_gps_from_portal(mandals: list[MandalBalanceSummary]) -> None:
    """Reject incomplete live drill-downs instead of inventing pending GP rows."""
    for m in mandals:
        if m.has_pending and not m.pending_gps:
            raise RuntimeError(
                f"The live portal reports pending balance entries in {m.mandal_name}, "
                "but its drill-down returned no GP names. "
                "Refresh the portal session and retry the report."
            )
        if m.not_entered_gps > len(m.pending_gps):
            raise RuntimeError(
                f"The live portal reports {m.not_entered_gps} GPs without balance entries in "
                f"{m.mandal_name}, but its drill-down returned only {len(m.pending_gps)} pending GP rows. "
                "Refresh the portal session and retry the report."
            )


def _normalized_lookup(value: Any) -> str:
    text = _cell_text(value).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def _live_tax_directory() -> Any:
    """Load the current DCB directory from the portal without writing its XLS response to disk."""
    try:
        from DCB import tax_service
        return tax_service.get_df()
    except Exception as exc:
        logger.info("Online tax directory unavailable for secretary enrichment: %s", exc)
        return None


def match_secretary_details(mandals: list[MandalBalanceSummary], district_name: str = "") -> None:
    """Enrich scraped pending GPs from optional secretary columns in the live DCB feed."""
    df = _live_tax_directory()
    if df is None or df.empty:
        return

    columns = {re.sub(r"[^a-z0-9]", "", str(col).lower()): col for col in df.columns}
    district_col = columns.get("district")
    mandal_col = columns.get("mandal")
    gp_col = columns.get("panchayat") or next((col for key, col in columns.items() if key in {"gp", "gpname", "gram panchayat"}), None)
    name_col = next((col for key, col in columns.items() if ("secretary" in key and "name" in key) or key in {"psname", "panchayatsecretary"}), None)
    phone_col = next((col for key, col in columns.items() if "phone" in key or "mobile" in key), None)
    if not mandal_col or not gp_col or not (name_col or phone_col):
        return

    district_key = _normalized_lookup(district_name)
    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for _, row in df.iterrows():
        if district_col and district_key and _normalized_lookup(row.get(district_col)) != district_key:
            continue
        mandal_key = _normalized_lookup(row.get(mandal_col))
        gp_key = _normalized_lookup(row.get(gp_col))
        if not mandal_key or not gp_key:
            continue
        name = _cell_text(row.get(name_col, "")) if name_col else ""
        phone = _cell_text(row.get(phone_col, "")) if phone_col else ""
        lookup[(mandal_key, gp_key)] = (name, phone)

    for mandal in mandals:
        for gp in mandal.pending_gps:
            details = lookup.get((_normalized_lookup(gp.mandal_name), _normalized_lookup(gp.panchayat_name)))
            if details:
                gp.secretary_name, gp.secretary_phone = details

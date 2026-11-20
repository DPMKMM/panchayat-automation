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
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from gp_balance.models import (
        ACTIVE_ACCOUNTS,
        DistrictBalanceReport,
        GPBalanceDetail,
        MandalBalanceSummary,
    )
except (ImportError, ModuleNotFoundError):
    from gp_balance_models import (
        ACTIVE_ACCOUNTS,
        DistrictBalanceReport,
        GPBalanceDetail,
        MandalBalanceSummary,
    )

logger = logging.getLogger("gp_balance_automation")

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize_mandal_key(name: str) -> str:
    """Normalizes mandal names across spelling variations (e.g. Nelakondapally vs Nelakondapalle, Penubally vs Penuballi, Yerrupalem vs Yerrupalam)."""
    s = re.sub(r'[^a-zA-Z0-9]', '', str(name)).lower()
    s = s.replace('th', 't').replace('w', 'v')
    for suffix in ('palle', 'pally', 'palli', 'balle', 'bally', 'balli', 'gudem', 'kunta', 'padu', 'puram', 'palem', 'palam', 'patnam', 'peta', 'pet', 'uru', 'ur'):
        if s.endswith(suffix) and len(s) > len(suffix) + 2:
            s = s[:-len(suffix)]
            break
    s = re.sub(r'[yeiua]+$', '', s)
    return s


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
        gmr14_header = iframe.locator("xpath=//*[contains(text(), 'Reports on Balances')] | text=Reports on Balances").first
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

    # Extract select options (scan all selects inside frame for date values)
    dates = iframe.evaluate("""() => {
        const sels = Array.from(document.querySelectorAll("select"));
        for (const sel of sels) {
            const opts = Array.from(sel.options)
                .map(o => (o.text || '').trim())
                .filter(t => t && t !== '--Select--' && t.match(/\\d{2}[-/]\\d{2}[-/]\\d{4}/));
            if (opts.length > 0) return opts;
        }
        return [];
    }""")
    return dates


def run_balance_automation(bot, target_date: str = "", include_pmagy: bool = False) -> DistrictBalanceReport:
    """Executes the full automated scraping pipeline for GM-R 14.2."""
    page = bot.page

    # Automatically dismiss alert dialogs without leaking listeners across modules
    def on_dialog(dialog):
        print(f"[!] Balance Alert dialog: {dialog.message} - accepting...", flush=True)
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", on_dialog)
    try:
        return _scrape_balance_report(bot, page, target_date=target_date, include_pmagy=include_pmagy)
    finally:
        try:
            page.remove_listener("dialog", on_dialog)
        except Exception:
            pass


def _scrape_balance_report(bot, page, target_date: str = "", include_pmagy: bool = False) -> DistrictBalanceReport:
    district_name = "District"
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
        gmr14_header = iframe.locator("xpath=//*[contains(text(), 'Reports on Balances')] | text=Reports on Balances").first
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
    target_date_val = ""
    if available_dates:
        # Match target_date or pick latest (first option)
        chosen_opt = available_dates[0]
        if target_date:
            for opt in available_dates:
                if target_date.strip() in opt["text"]:
                    chosen_opt = opt
                    break

        selected_date_text = chosen_opt["text"]
        target_date_val = chosen_opt["value"]
        val = target_date_val
        print(f"[+] Selecting Thursday Balance Date: {selected_date_text} (value={target_date_val})", flush=True)

        iframe.evaluate(f"""() => {{
            const sel = document.querySelector("select");
            if (sel) {{
                sel.value = "{target_date_val}";
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

    # 7. Ensure table entries dropdown shows all (select 32, 50, 100 or -1 All)
    try:
        iframe.evaluate("""() => {
            const lenSel = document.querySelector(".dataTables_length select, select[name*='length' i], select[name*='entries' i]");
            if (lenSel) {
                const allOpt = Array.from(lenSel.options).find(o => o.value === "-1" || (o.innerText || '').toLowerCase().includes("all"));
                if (allOpt) {
                    lenSel.value = allOpt.value;
                } else {
                    const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n) && n > 0);
                    if (vals.length > 0) {
                        lenSel.value = Math.max(...vals).toString();
                    }
                }
                lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                if (window.$) window.$(lenSel).trigger('change');
            }
            if (window.$ && window.$.fn && window.$.fn.dataTable) {
                try { window.$('table').DataTable().page.len(-1).draw(false); } catch(e) {}
            }
        }""")
        time.sleep(2)
    except Exception as e_len:
        logger.debug("Length expand error: %s", e_len)

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
            pmagy_updated=r["pmagy"],
            vwsc_updated=r["vwsc"],
            mgnregs_updated=r["mgnregs"],
        )
        m.calculate_metrics(include_pmagy=include_pmagy)
        mandals_list.append(m)

    # Dynamic District Detection (works for all 33 districts across Telangana without hardcoding)
    try:
        page_text = page.evaluate("""() => {
            return (document.body ? document.body.innerText : '') + ' ' + (document.title || '');
        }""")
        dist_match = re.search(r"(?:DISTRICT\s+PANCHAYAT\s+OFFICE|COLLECTORATE|ZPP|DPO)[,\s\-–—:]+([A-Za-z\s]+?)(?:\s+DISTRICT|\b)", page_text, re.IGNORECASE)
        if not dist_match:
            dist_match = re.search(r"[-—–:]\s*([A-Za-z\s]+?)\s+DISTRICT", page_text, re.IGNORECASE)
        if dist_match:
            candidate = dist_match.group(1).strip().title()
            if candidate and len(candidate) > 2 and candidate.lower() != "district":
                district_name = candidate
    except Exception as exc:
        logger.debug("Page header district match note: %s", exc)

    if not district_name or district_name.lower() == "district":
        try:
            import sys
            if str(ROOT_DIR) not in sys.path:
                sys.path.insert(0, str(ROOT_DIR))
            try:
                from dcb import service as tax_service
            except (ImportError, ModuleNotFoundError):
                import tax_service
            df = tax_service.get_df()
            m_names = [m.mandal_name for m in mandals_list if m.mandal_name]
            norm_keys = [normalize_mandal_key(m) for m in m_names]
            df_matches = df[df["mandal"].apply(normalize_mandal_key).isin(norm_keys)]
            if not df_matches.empty:
                top_dist = df_matches["district"].mode()
                if not top_dist.empty:
                    district_name = str(top_dist.iloc[0]).strip().title()
        except Exception as exc:
            logger.debug("Mandal lookup district detection note: %s", exc)

    print(f"[*] Dynamically detected District Name: {district_name}", flush=True)

    # 9. Drill Down for Mandals with Pending Entries
    pending_mandals = [m for m in mandals_list if m.has_pending]
    print(f"[*] Found {len(pending_mandals)} Mandal(s) with pending balance entries to drill down: {[m.mandal_name for m in pending_mandals]}", flush=True)

    for m in pending_mandals:
        if "TOTAL" in m.mandal_name.strip().upper() or "DISTRICT" in m.mandal_name.strip().upper():
            continue

        try:
            print(f"[*] Drilling down into Mandal: {m.mandal_name} ...", flush=True)

            # Ensure entries dropdown shows maximum entries so all mandal rows are rendered
            try:
                iframe.evaluate("""() => {
                    const lenSel = document.querySelector(".dataTables_length select, select[name*='length' i], select[name*='entries' i]");
                    if (lenSel) {
                        const allOpt = Array.from(lenSel.options).find(o => o.value === "-1" || (o.innerText || '').toLowerCase().includes("all"));
                        if (allOpt) {
                            lenSel.value = allOpt.value;
                        } else {
                            const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n) && n > 0);
                            if (vals.length > 0) {
                                lenSel.value = Math.max(...vals).toString();
                            }
                        }
                        lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                        if (window.$) window.$(lenSel).trigger('change');
                    }
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).page.len(-1).draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().page.len(-1).draw(false);
                            }
                        } catch(e) {}
                    }
                }""")
                time.sleep(0.4)
            except Exception:
                pass

            # Ensure search box is clear on Mandal Abstract table
            try:
                iframe.evaluate("""() => {
                    const inps = document.querySelectorAll("input[type='search'], .dataTables_filter input");
                    for (const inp of inps) {
                        inp.value = "";
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).search('').draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().search('').draw(false);
                            }
                        } catch(e) {}
                    }
                }""")
                search_box = iframe.locator("input[type='search'], .dataTables_filter input").first
                if search_box.is_visible(timeout=600):
                    search_box.fill("")
                time.sleep(0.3)
            except Exception:
                pass

            clicked = False

            # Strategy 1: Direct DOM match across currently rendered rows
            try:
                click_info = iframe.evaluate("""(targetMandal) => {
                    function clean(s) { return (s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
                    function stem(s) {
                        let c = clean(s).replace('th', 't').replace('w', 'v');
                        for (const suf of ['palle', 'pally', 'palli', 'balle', 'bally', 'balli', 'gudem', 'kunta', 'padu', 'puram', 'palem', 'palam', 'patnam', 'peta', 'pet', 'uru', 'ur']) {
                            if (c.endsWith(suf) && c.length > suf.length + 2) {
                                c = c.slice(0, -suf.length);
                                break;
                            }
                        }
                        return c.replace(/[yeiua]+$/, '');
                    }
                    const cleanTarget = clean(targetMandal);
                    const targetStem = stem(targetMandal);
                    const rows = Array.from(document.querySelectorAll("table tbody tr"));
                    for (const r of rows) {
                        const cells = Array.from(r.querySelectorAll("td"));
                        if (cells.length >= 2) {
                            const name = (cells[1].innerText || '').trim();
                            const cName = clean(name);
                            if (cName === cleanTarget || cName.includes(cleanTarget) || cleanTarget.includes(cName) || (stem(name) === targetStem && targetStem.length >= 3)) {
                                const link = cells[1].querySelector("a") || r.querySelector("a");
                                if (link) {
                                    link.click();
                                    return { success: true, method: "direct_row", name: name };
                                }
                            }
                        }
                    }
                    return { success: false, rowCount: rows.length };
                }""", m.mandal_name)
                if isinstance(click_info, dict) and click_info.get("success"):
                    clicked = True
                    print(f"[+] Mandal {m.mandal_name}: Clicked link via direct DOM row match ({click_info.get('name')})", flush=True)
            except Exception as e_click1:
                logger.debug("Strategy 1 click note for %s: %s", m.mandal_name, e_click1)

            # Strategy 2: DataTables Search & Filter if not clicked via Strategy 1
            if not clicked:
                try:
                    click_info = iframe.evaluate("""(targetMandal) => {
                        if (window.$ && window.$.fn && window.$.fn.dataTable) {
                            try {
                                if (window.$.fn.dataTable.tables) {
                                    window.$.fn.dataTable.tables({ api: true }).search(targetMandal).draw();
                                } else {
                                    window.$('table.dataTable, table').DataTable().search(targetMandal).draw();
                                }
                            } catch(e) {}
                        }
                        const inps = document.querySelectorAll("input[type='search'], .dataTables_filter input");
                        for (const inp of inps) {
                            inp.value = targetMandal;
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        const rows = Array.from(document.querySelectorAll("table tbody tr"));
                        if (rows.length > 0) {
                            for (const r of rows) {
                                const link = r.querySelector("a");
                                if (link) {
                                    link.click();
                                    return { success: true, method: "search_filter" };
                                }
                            }
                        }
                        return { success: false };
                    }""", m.mandal_name)
                    if isinstance(click_info, dict) and click_info.get("success"):
                        clicked = True
                        print(f"[+] Mandal {m.mandal_name}: Clicked link via DataTables search filter", flush=True)
                except Exception as e_click2:
                    logger.debug("Strategy 2 click note for %s: %s", m.mandal_name, e_click2)

            # Strategy 3: Playwright locator fallback
            if not clicked:
                try:
                    m_link = iframe.locator(f"table tbody tr a:has-text('{m.mandal_name}')").first
                    if m_link.is_visible(timeout=3000):
                        m_link.click()
                        clicked = True
                        print(f"[+] Mandal {m.mandal_name}: Clicked link via Playwright locator", flush=True)
                except Exception:
                    pass

            if not clicked:
                print(f"[-] Mandal {m.mandal_name}: Link NOT found across all strategies! Skipping.", flush=True)
                continue

            # Wait for GP Drilldown Table to load (confirmed by presence of Back button or Panchayat header)
            gp_table_loaded = False
            for _ in range(30):
                time.sleep(0.5)
                gp_table_loaded = iframe.evaluate("""() => {
                    const hasBack = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], a"))
                        .some(el => {
                            const txt = (el.value || el.innerText || el.textContent || '').trim().toLowerCase();
                            return txt === 'back' || txt.includes('back');
                        });
                    const hasGpHdr = Array.from(document.querySelectorAll("table thead th"))
                        .some(th => {
                            const t = (th.innerText || '').toLowerCase();
                            return t.includes("panchayat") || t.includes("gram panchayat");
                        });
                    const text = document.body ? document.body.innerText : '';
                    const hasGpIndicators = text.includes("Mandal:") || text.includes("Panchayat Name");
                    const hasRows = document.querySelectorAll("table tbody tr").length > 0;
                    return (hasBack || hasGpHdr || hasGpIndicators) && hasRows;
                }""")
                if gp_table_loaded:
                    break

            if not gp_table_loaded:
                print(f"[-] Mandal {m.mandal_name}: GP drilldown table did not load after clicking link. Skipping.", flush=True)
                continue

            # Clear any lingering search filter in GP table so all GPs load
            try:
                iframe.evaluate("""() => {
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).search('').page.len(-1).draw();
                            } else {
                                window.$('table.dataTable, table').DataTable().search('').page.len(-1).draw();
                            }
                        } catch(e) {}
                    }
                    const inps = document.querySelectorAll("input[type='search'], .dataTables_filter input");
                    for (const inp of inps) {
                        inp.value = "";
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""")
                time.sleep(0.4)
            except Exception:
                pass

            # Ensure GP table displays all entries (set length selector to highest)
            try:
                iframe.evaluate("""() => {
                    const lenSel = document.querySelector(".dataTables_length select, select[name*='length' i], select[name*='entries' i]");
                    if (lenSel) {
                        const allOpt = Array.from(lenSel.options).find(o => o.value === "-1" || (o.innerText || '').toLowerCase().includes("all"));
                        if (allOpt) {
                            lenSel.value = allOpt.value;
                        } else {
                            const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n) && n > 0);
                            if (vals.length > 0) {
                                lenSel.value = Math.max(...vals).toString();
                            }
                        }
                        lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                        if (window.$) window.$(lenSel).trigger('change');
                    }
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).page.len(-1).draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().page.len(-1).draw(false);
                            }
                        } catch(e) {}
                    }
                }""")
                time.sleep(0.8)
            except Exception:
                pass

            # Step E: Scrape all GP rows directly from GP table DOM
            gp_rows_raw = iframe.evaluate("""() => {
                const rows = document.querySelectorAll("table tbody tr");
                const gps = [];
                for (const r of rows) {
                    const cells = Array.from(r.querySelectorAll("td")).map(td => td.innerText.trim());
                    if (cells.length >= 10 && cells[0].match(/^\\d+$/)) {
                        const sNo = parseInt(cells[0]) || 0;
                        const gpName = cells[1];
                        if (!gpName || gpName.toUpperCase().includes("TOTAL")) continue;

                        const enteredVal = cells[2];
                        const notEnteredVal = cells[3];
                        const isEntered = (enteredVal === "1" || enteredVal.toLowerCase() === "yes") && notEnteredVal !== "1";

                        gps.push({
                            s_no: sNo,
                            panchayat_name: gpName,
                            entered: isEntered,
                            not_entered: !isEntered,
                            gp_pd: cells[4],
                            tgbpass: cells[5],
                            fc15_tied: cells[6],
                            fc15_untied: cells[7],
                            pmagy: cells[8], // Ignored by default
                            vwsc: cells[9],
                            mgnregs: cells[10]
                        });
                    }
                }
                return gps;
            }""")

            m.pending_gps = []
            m.all_gps = []
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
                    pmagy=gp_raw.get("pmagy", "Yes"),
                    vwsc=gp_raw["vwsc"],
                    mgnregs=gp_raw["mgnregs"],
                )
                gp.evaluate_pending(include_pmagy=include_pmagy)
                m.all_gps.append(gp)
                if gp.is_pending:
                    m.pending_gps.append(gp)

            print(f"[+] Mandal {m.mandal_name}: Scraped {len(gp_rows_raw)} total GPs. Found {len(m.pending_gps)} pending GP(s): {[g.panchayat_name for g in m.pending_gps]}", flush=True)

            # Step F: Return to Mandal Abstract table
            # Verify we are on Mandal Abstract table (Header has Mandal & Total GPs, no GP Name col, and rows present)
            is_mandal_table_js = """() => {
                const ths = Array.from(document.querySelectorAll("table thead th"))
                    .map(th => (th.innerText || th.textContent || '').trim().toLowerCase());
                if (ths.length < 5) return false;
                const hasMandal = ths.some(t => t === 'mandal' || t.includes('mandal name') || t === 'mandal name');
                const hasTotalGps = ths.some(t => t.includes('total gp') || t.includes('total gps'));
                const hasGpCol = ths.some(t => t.includes('panchayat') || t.includes('gp name'));
                const rowCount = document.querySelectorAll("table tbody tr").length;
                return hasMandal && hasTotalGps && !hasGpCol && rowCount > 0;
            }"""

            back_clicked = False
            try:
                back_btn = iframe.locator("button:has-text('Back'), input[value*='Back' i], a:has-text('Back')").first
                if back_btn.is_visible(timeout=1500):
                    back_btn.click()
                    back_clicked = True
            except Exception:
                pass

            if not back_clicked:
                try:
                    back_clicked = iframe.evaluate(r"""() => {
                        const btns = Array.from(document.querySelectorAll("button, input[value*='Back' i], a, input[type='button'], input[type='submit']"));
                        const b = btns.find(el => {
                            const val = (el.value || '').trim().toLowerCase();
                            const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                            return /^(?:<|<<|←)?\s*back\s*$/i.test(val) || /^(?:<|<<|←)?\s*back\s*$/i.test(txt);
                        });
                        if (b) {
                            b.click();
                            return true;
                        }
                        if (window.history && window.history.length > 1) {
                            window.history.back();
                            return true;
                        }
                        return false;
                    }""")
                except Exception:
                    pass

            # Confirm Mandal Abstract table is restored
            restored = False
            for _ in range(16):
                time.sleep(0.5)
                try:
                    if iframe.evaluate(is_mandal_table_js):
                        restored = True
                        break
                except Exception:
                    pass

            if restored:
                print(f"[*] Mandal Abstract table restored successfully after {m.mandal_name}.", flush=True)
            else:
                print(f"[!] Mandal Abstract table not restored via Back for {m.mandal_name}. Using Date Selection + Submit reload fallback...", flush=True)
                try:
                    if target_date_val:
                        iframe.evaluate(f"""() => {{
                            const sel = document.querySelector("select");
                            if (sel) {{
                                sel.value = "{target_date_val}";
                                sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                if (window.$) window.$(sel).trigger('change');
                            }}
                        }}""")
                        time.sleep(0.8)

                    submit_btn = iframe.locator("button:has-text('Submit'), input[value='Submit'], input[type='submit']").first
                    if submit_btn.is_visible(timeout=3000):
                        submit_btn.click()
                        time.sleep(3)
                        for _ in range(16):
                            time.sleep(0.5)
                            if iframe.evaluate(is_mandal_table_js):
                                restored = True
                                break
                except Exception as e_sub:
                    logger.debug("Submit reload fallback note: %s", e_sub)

            # Clear search input on restored Mandal table and re-expand page length to max
            try:
                iframe.evaluate("""() => {
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).search('').draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().search('').draw(false);
                            }
                        } catch(e) {}
                    }
                    const inps = document.querySelectorAll("input[type='search'], .dataTables_filter input");
                    for (const inp of inps) {
                        inp.value = "";
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    const lenSel = document.querySelector(".dataTables_length select, select[name*='length' i], select[name*='entries' i]");
                    if (lenSel) {
                        const allOpt = Array.from(lenSel.options).find(o => o.value === "-1" || (o.innerText || '').toLowerCase().includes("all"));
                        if (allOpt) {
                            lenSel.value = allOpt.value;
                        } else {
                            const vals = Array.from(lenSel.options).map(o => parseInt(o.value)).filter(n => !isNaN(n) && n > 0);
                            if (vals.length > 0) {
                                lenSel.value = Math.max(...vals).toString();
                            }
                        }
                        lenSel.dispatchEvent(new Event('change', { bubbles: true }));
                        if (window.$) window.$(lenSel).trigger('change');
                    }
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).page.len(-1).draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().page.len(-1).draw(false);
                            }
                        } catch(e) {}
                    }
                }""")
                search_box = iframe.locator("input[type='search'], .dataTables_filter input").first
                if search_box.is_visible(timeout=600):
                    search_box.fill("")
                time.sleep(0.3)
            except Exception:
                pass

        except Exception as drill_err:
            logger.warning("Error drilling down into %s: %s", m.mandal_name, drill_err)
            try:
                iframe.evaluate(r"""() => {
                    const btns = Array.from(document.querySelectorAll("button, input[value*='Back' i], a, input[type='button'], input[type='submit']"));
                    const b = btns.find(el => {
                        const val = (el.value || '').trim().toLowerCase();
                        const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                        return /^(?:<|<<|←)?\s*back\s*$/i.test(val) || /^(?:<|<<|←)?\s*back\s*$/i.test(txt);
                    });
                    if (b) b.click();
                    else if (window.history && window.history.length > 1) window.history.back();
                }""")
                time.sleep(1.5)

                if not iframe.evaluate(is_mandal_table_js) and target_date_val:
                    iframe.evaluate(f"""() => {{
                        const sel = document.querySelector("select");
                        if (sel) {{
                            sel.value = "{target_date_val}";
                            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            if (window.$) window.$(sel).trigger('change');
                        }}
                    }}""")
                    time.sleep(0.8)
                    sub = iframe.locator("button:has-text('Submit'), input[value='Submit'], input[type='submit']").first
                    if sub.is_visible(timeout=3000):
                        sub.click()
                        time.sleep(3)

                # Clear lingering search filter on recovery
                iframe.evaluate("""() => {
                    const inps = document.querySelectorAll("input[type='search'], .dataTables_filter input");
                    for (const inp of inps) {
                        inp.value = "";
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (window.$ && window.$.fn && window.$.fn.dataTable) {
                        try {
                            if (window.$.fn.dataTable.tables) {
                                window.$.fn.dataTable.tables({ api: true }).search('').page.len(-1).draw(false);
                            } else {
                                window.$('table.dataTable, table').DataTable().search('').page.len(-1).draw(false);
                            }
                        } catch(e) {}
                    }
                }""")
            except Exception:
                pass

    total_scraped_pending = sum(len(m.pending_gps) for m in mandals_list)
    print(f"[✓] DRILLDOWN FINISHED: Scraped {total_scraped_pending} pending GP(s) across all {len(pending_mandals)} mandals.", flush=True)

    # 10. Enrich Secretary Details using in-memory live portal data
    match_secretary_details(mandals_list)

    report = DistrictBalanceReport(
        district_name=district_name,
        report_date_str=selected_date_text,
        generated_at=datetime.now().strftime("%d-%b-%Y %I:%M %p"),
        mandals=mandals_list,
        include_pmagy=include_pmagy,
    )
    report.compute_totals()
    return report


def populate_pending_gps_from_directory(mandals: list[MandalBalanceSummary], district_name: str = "", include_pmagy: bool = False) -> None:
    """Strictly enforces live portal scraping only.
    Offline DCB list is NEVER used to synthesize pending GP names.
    Any pending GPs must originate directly from live portal scraping.
    """
    for m in mandals:
        if m.all_gps:
            m.pending_gps = [g for g in m.all_gps if g.is_pending]
            m.has_pending = len(m.pending_gps) > 0

def match_secretary_details(mandals: list[MandalBalanceSummary]) -> None:
    """Enriches pending GP records with secretary details if present in in-memory live portal data."""
    try:
        import sys
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        try:
            from dcb import service as tax_service
        except (ImportError, ModuleNotFoundError):
            import tax_service
        df = tax_service.get_df()
        sec_name_col = next((c for c in df.columns if "secretary" in c.lower() or "ps_name" in c.lower()), None)
        sec_phone_col = next((c for c in df.columns if "mobile" in c.lower() or "phone" in c.lower()), None)
        if not sec_name_col and not sec_phone_col:
            return

        lookup = {}
        for _, row in df.iterrows():
            m_key = normalize_mandal_key(str(row.get("mandal", "")))
            gp_key = re.sub(r'[^a-zA-Z0-9]', '', str(row.get("panchayat", ""))).lower()
            n_val = str(row.get(sec_name_col, "")).strip() if sec_name_col else ""
            p_val = str(row.get(sec_phone_col, "")).strip() if sec_phone_col else ""
            if m_key and gp_key:
                lookup[(m_key, gp_key)] = (n_val, p_val)

        for m in mandals:
            m_key = normalize_mandal_key(m.mandal_name)
            target_list = list(m.pending_gps)
            for g in (m.all_gps or []):
                if g not in target_list:
                    target_list.append(g)
            for gp in target_list:
                gp_key = re.sub(r'[^a-zA-Z0-9]', '', str(gp.panchayat_name)).lower()
                sec = lookup.get((m_key, gp_key))
                if not sec:
                    for (mk, gk), v in lookup.items():
                        if mk == m_key and (gk in gp_key or gp_key in gk):
                            sec = v
                            break
                if sec:
                    if sec[0]: gp.secretary_name = sec[0]
                    if sec[1]: gp.secretary_phone = sec[1]
    except Exception as exc:
        logger.debug("Secretary matching note: %s", exc)

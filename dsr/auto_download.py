"""
Exact Automated Pipeline for e-Panchayat DSR Report
Downloads in sequence:
  1. GM-R 1.2.7 DSR Raw Data Report -> Saved as-is with original filename
  2. Select GP Monitoring -> GM-R 1.2.11 Report on Presenties Data -> Saved as-is with original filename
  3. Select GP Monitoring -> GM-R 1.2.10 Report on Absentees Data -> Saved as-is with original filename
And prepares report using newly downloaded files ONLY (no saved/bundled files, no renaming).
"""

import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

try:
    from dsr.automation import EPTSAutomation, BASE_DIR, DEBUG_DIR, DOWNLOADS_DIR, OTP_FILE
except (ImportError, ModuleNotFoundError):
    from epts_automation import EPTSAutomation, BASE_DIR, DOWNLOADS_DIR, OTP_FILE
    DEBUG_DIR = DOWNLOADS_DIR.parent / "debug"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_SCREENSHOT = DEBUG_DIR / "enlarged_reports.png"
MENU_URL = "https://tgprepanchayat.telangana.gov.in/PSPerformance/DynamicReportsMenu2Array"


def get_my_iframe(page):
    """Returns the content iframe named 'my-iframe' or holding PSPerformance."""
    for f in page.frames:
        if f.name == "my-iframe" or "PSPerformance" in f.url:
            return f
    if len(page.frames) > 2:
        return page.frames[2]
    return None


def find_form_frame(page, preferred_frame=None):
    """Resolves the active frame holding the report form (Select Date or Download button)."""
    check_frames = []
    if preferred_frame and preferred_frame in page.frames:
        check_frames.append(preferred_frame)
    primary = get_my_iframe(page)
    if primary and primary not in check_frames:
        check_frames.append(primary)
    for f in page.frames:
        if f not in check_frames:
            check_frames.append(f)

    for f in check_frames:
        try:
            if f.locator("text='Select Date', input[value*='Download' i], button:has-text('Download')").first.is_visible(timeout=500):
                return f
        except Exception:
            continue

    return preferred_frame or primary or (page.frames[0] if page.frames else None)


def format_portal_date(date_val: str) -> str:
    """Formats date to DD-MMM-YYYY (e.g. 30-Oct-2026 or 02-Nov-2026) required by portal."""
    if not date_val:
        return datetime.now().strftime("%d-%b-%Y")
    clean = date_val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(clean, fmt).strftime("%d-%b-%Y")
        except Exception:
            continue
    return clean


def download_single_report_with_menu(bot, code: str, target_date: str) -> Path:
    """
    Downloads a single report from e-Panchayat portal:
    1. Selects 'GP Monitoring' from the top navigation to load/reset the reports iframe.
    2. Waits for 'my-iframe' to load.
    3. Clicks 'Enlarge All' and expands 'DSR REPORTS'.
    4. Clicks the report link matching `code` (e.g. 1.2.7, 1.2.11, 1.2.10).
    5. Sets the date filter in DD-MMM-YYYY format.
    6. Clicks Download and saves the file with its ORIGINAL portal filename (NO renaming).
    """
    page = bot.page
    date_formatted = format_portal_date(target_date)

    portal_dialog_messages: list[str] = []

    # Automatically dismiss any alert dialogs from portal so they don't block
    def on_dialog(dialog):
        msg = (dialog.message or "").strip()
        print(f"[!] Portal alert dialog: '{msg}' - accepting...", flush=True)
        portal_dialog_messages.append(msg)
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", on_dialog)
    try:
        print(f"\n[*] Re-selecting 'GP Monitoring' from top menu for report {code}...", flush=True)
        bot.select_menu("GP Monitoring")
        time.sleep(2.5)

        iframe = get_my_iframe(page)
        if not iframe:
            time.sleep(2)
            iframe = get_my_iframe(page)
        if not iframe:
            raise RuntimeError(f"Could not locate 'my-iframe' after selecting GP Monitoring for {code}.")

        try:
            iframe.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass

        # Click 'Enlarge All' to expand all folders
        print("[*] Clicking 'Enlarge All'...", flush=True)
        try:
            enlarge_btn = iframe.locator("text='Enlarge All'").first
            if enlarge_btn.is_visible(timeout=3000):
                enlarge_btn.click()
                time.sleep(1)
        except Exception as e:
            print(f"[-] Note on Enlarge All: {e}", flush=True)

        # Expand 'DSR REPORTS' section
        print("[*] Expanding 'DSR REPORTS'...", flush=True)
        try:
            dsr_header = iframe.locator("text='DSR REPORTS'").first
            if dsr_header.is_visible(timeout=3000):
                dsr_header.click()
                time.sleep(1.5)
        except Exception as e:
            print(f"[-] Note on DSR REPORTS: {e}", flush=True)

        # Locate report link matching code
        print(f"[*] Locating link for {code}...", flush=True)
        selectors = [f"a:has-text('{code}')"]
        if "1.2.7" in code:
            selectors.append("a:has-text('Raw Data')")
        elif "1.2.11" in code:
            selectors.extend(["a:has-text('Presenties')", "a:has-text('Presentees')"])
        elif "1.2.10" in code:
            selectors.append("a:has-text('Absentees')")

        link = None
        for sel in selectors:
            cand = iframe.locator(sel).first
            try:
                if cand.is_visible(timeout=2000):
                    link = cand
                    break
            except Exception:
                pass

        if not link:
            link = iframe.locator(selectors[0]).first
            link.wait_for(state="visible", timeout=12000)

        print(f"[+] Found link for {code}. Clicking...", flush=True)
        link.click()
        time.sleep(2.0)

        # Re-resolve fresh iframe handle after report link navigation
        iframe = get_my_iframe(page) or iframe

        # Locate download button selectors
        dl_selectors = [
            "input[value='Download']",
            "input[value='Download Excel']",
            "input[value*='Download' i]",
            "button:has-text('Download')",
            "button:has-text('Download Excel')",
            "input[id*='btnExport' i]",
            "input[id*='btnDownload' i]",
            "input[name*='btnDownload' i]",
            "input[name*='btnExport' i]",
            "input[value*='Excel' i]",
            "button:has-text('Excel')",
            "input[type='submit']",
            "button[type='submit']",
        ]

        print(f"[*] Waiting for report form ({code}) to load in portal iframe...", flush=True)
        # Check active form frame
        iframe = find_form_frame(page, preferred_frame=iframe)
        dl_loc = iframe.locator(", ".join(dl_selectors))
        txt_loc = iframe.locator("text='Select Date'")
        report_form_indicator = dl_loc.or_(txt_loc)
        try:
            report_form_indicator.first.wait_for(state="visible", timeout=25000)
            print(f"[+] Report form for {code} is visible and ready.", flush=True)
        except Exception as wait_err:
            print(f"[-] Note waiting for report form on {code}: {wait_err}", flush=True)
            time.sleep(2.0)

        # Re-resolve fresh frame
        iframe = find_form_frame(page, preferred_frame=iframe)

        # Screenshot initial view
        if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
            ss_path = DEBUG_DIR / f"page_{code.replace('.', '_')}.png"
            try:
                page.screenshot(path=str(ss_path))
                print(f"[+] Saved view screenshot to {ss_path}", flush=True)
            except Exception:
                pass

        # Set Date filter in iframe (using DD-MMM-YYYY e.g. 30-Oct-2026 or 09-Nov-2026)
        print(f"[*] Setting date to {date_formatted} in iframe for {code}...", flush=True)

        # 1. Comprehensive DOM evaluation & jQuery UI datepicker (STRICTLY NON-BUTTON INPUTS ONLY)
        try:
            iframe.evaluate(f"""(dt) => {{
                function isEditableDateInput(el) {{
                    if (!el || el.tagName !== 'INPUT') return false;
                    const type = (el.getAttribute('type') || el.type || 'text').toLowerCase();
                    if (['button', 'submit', 'reset', 'image', 'hidden', 'checkbox', 'radio', 'file'].includes(type)) {{
                        return false;
                    }}
                    const val = (el.value || '').trim().toLowerCase();
                    if (['download', 'excel', 'export', 'submit', 'search', 'cancel', 'back'].some(w => val.includes(w))) {{
                        return false;
                    }}
                    const id = (el.id || '').toLowerCase();
                    const name = (el.name || '').toLowerCase();
                    if (['download', 'btnexport', 'btndownload', 'btnsubmit'].some(w => id.includes(w) || name.includes(w))) {{
                        return false;
                    }}
                    return true;
                }}

                const candidates = [];
                const attrInputs = document.querySelectorAll(
                    "input[id*='Date' i], input[name*='Date' i], input.hasDatepicker, input[type='text'], input:not([type])"
                );
                for (const inp of attrInputs) {{
                    if (isEditableDateInput(inp) && inp.offsetParent !== null && !candidates.includes(inp)) {{
                        candidates.push(inp);
                    }}
                }}

                const allLabels = Array.from(document.querySelectorAll('label, td, span, div, b, strong, th'))
                    .filter(el => el.textContent && el.textContent.toLowerCase().includes('select date'));
                for (const lbl of allLabels) {{
                    let parent = lbl.parentElement;
                    for (let step = 0; step < 3 && parent; step++) {{
                        const inps = parent.querySelectorAll('input');
                        for (const inp of inps) {{
                            if (isEditableDateInput(inp) && inp.offsetParent !== null && !candidates.includes(inp)) {{
                                candidates.push(inp);
                            }}
                        }}
                        parent = parent.parentElement;
                    }}
                }}

                for (const inp of candidates) {{
                    inp.removeAttribute('readonly');
                    inp.removeAttribute('disabled');
                    inp.value = dt;
                    if (window.jQuery && window.jQuery(inp).datepicker) {{
                        try {{ window.jQuery(inp).datepicker('setDate', dt); }} catch(e) {{}}
                    }}
                    inp.dispatchEvent(new Event('focus', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}

                for (const f of document.forms) {{
                    f.removeAttribute('target');
                }}
            }}""", date_formatted)
        except Exception as e:
            print(f"[-] Note on DOM date evaluation for {code}: {e}", flush=True)

        # 2. Playwright locator typing/filling (STRICTLY NON-BUTTON INPUTS)
        date_selectors = [
            "xpath=//*[contains(text(), 'Select Date')]/following::input[not(@type='button') and not(@type='submit') and not(@type='hidden')][1]",
            "input[id*='Date' i]:not([type='button']):not([type='submit'])",
            "input[name*='Date' i]:not([type='button']):not([type='submit'])",
            "input.hasDatepicker:not([type='button']):not([type='submit'])",
            "input[type='text']:not([id*='btn' i])",
        ]
        for sel in date_selectors:
            cand = iframe.locator(sel).first
            try:
                if cand.is_visible(timeout=2000):
                    cand.evaluate("el => { el.removeAttribute('readonly'); el.removeAttribute('disabled'); }")
                    cand.click()
                    cand.fill("")
                    cand.fill(date_formatted)
                    cand.press("Tab")
                    time.sleep(0.2)
                    break
            except Exception:
                continue

        # 3. Verification & retry loop (STRICTLY NON-BUTTON INPUTS)
        target_clean = date_formatted.strip()
        for attempt in range(1, 4):
            current_val = ""
            try:
                current_val = iframe.evaluate("""() => {
                    function isEditableDateInput(el) {
                        if (!el || el.tagName !== 'INPUT') return false;
                        const type = (el.getAttribute('type') || el.type || 'text').toLowerCase();
                        if (['button', 'submit', 'reset', 'image', 'hidden', 'checkbox', 'radio', 'file'].includes(type)) return false;
                        const val = (el.value || '').trim().toLowerCase();
                        if (['download', 'excel', 'export', 'submit'].some(w => val.includes(w))) return false;
                        return true;
                    }
                    const inps = document.querySelectorAll(
                        "input[id*='Date' i], input[name*='Date' i], input.hasDatepicker, input[type='text'], input:not([type])"
                    );
                    for (const inp of inps) {
                        if (isEditableDateInput(inp) && inp.offsetParent !== null && inp.value) {
                            return inp.value.trim();
                        }
                    }
                    return '';
                }""")
            except Exception:
                current_val = ""

            print(f"[*] Verified date input in iframe for {code}: '{current_val}' (target: '{target_clean}')", flush=True)
            if current_val and (current_val.lower().replace("-", " ") == target_clean.lower().replace("-", " ") or current_val == target_clean):
                print(f"[+] Date filter strictly verified and applied as '{current_val}' for {code}.", flush=True)
                break
            else:
                print(f"[!] Date mismatch on attempt {attempt} for {code} (current='{current_val}', target='{target_clean}'). Forcing update...", flush=True)
                try:
                    iframe.evaluate(f"""(dt) => {{
                        function isEditableDateInput(el) {{
                            if (!el || el.tagName !== 'INPUT') return false;
                            const type = (el.getAttribute('type') || el.type || 'text').toLowerCase();
                            if (['button', 'submit', 'reset', 'image', 'hidden', 'checkbox', 'radio', 'file'].includes(type)) return false;
                            const val = (el.value || '').trim().toLowerCase();
                            if (['download', 'excel', 'export', 'submit'].some(w => val.includes(w))) return false;
                            return true;
                        }}
                        const inps = document.querySelectorAll("input[type='text'], input.hasDatepicker, input:not([type])");
                        for (const inp of inps) {{
                            if (isEditableDateInput(inp) && inp.offsetParent !== null) {{
                                inp.removeAttribute('readonly');
                                inp.removeAttribute('disabled');
                                inp.value = dt;
                                if (window.jQuery && window.jQuery(inp).datepicker) {{
                                    try {{ window.jQuery(inp).datepicker('setDate', dt); }} catch(e) {{}}
                                }}
                                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            }}
                        }}
                    }}""", target_clean)
                except Exception:
                    pass
                time.sleep(0.5)

        time.sleep(0.5)

        # Close any active jQuery UI datepicker popups that might obscure elements
        try:
            iframe.evaluate("""() => {
                if (window.jQuery && window.jQuery.datepicker) {
                    try { window.jQuery.datepicker._hideDatepicker(); } catch(e){}
                }
                document.querySelectorAll('.ui-datepicker').forEach(el => el.style.display = 'none');
            }""")
        except Exception:
            pass

        # Save verification screenshot showing date filled in
        if os.getenv("EPTS_SAVE_DEBUG_SCREENSHOTS") == "1":
            after_date_ss = DEBUG_DIR / f"after_date_{code.replace('.', '_')}.png"
            try:
                page.screenshot(path=str(after_date_ss))
                print(f"[+] Saved date verification screenshot to {after_date_ss}", flush=True)
            except Exception:
                pass

        # Locate and click Download button
        print(f"[*] Waiting for download button for {code}...", flush=True)
        iframe = find_form_frame(page, preferred_frame=iframe)

        dl_btn = None
        for sel in dl_selectors:
            cand = iframe.locator(sel).first
            try:
                if cand.is_visible(timeout=1500):
                    dl_btn = cand
                    break
            except Exception:
                continue

        # If not found yet in current frame, search across all frames
        if not dl_btn:
            for f in page.frames:
                for sel in dl_selectors[:5]:
                    cand = f.locator(sel).first
                    try:
                        if cand.is_visible(timeout=1000):
                            dl_btn = cand
                            iframe = f
                            break
                    except Exception:
                        continue
                if dl_btn:
                    break

        if not dl_btn:
            dl_btn = iframe.locator(", ".join(dl_selectors)).first
            try:
                dl_btn.wait_for(state="visible", timeout=25000)
            except Exception as wait_err:
                try:
                    err_ss = DEBUG_DIR / f"error_dl_{code.replace('.', '_')}.png"
                    page.screenshot(path=str(err_ss))
                    print(f"[-] Saved error screenshot to {err_ss}", flush=True)
                except Exception:
                    pass
                raise wait_err

        print(f"[*] Triggering download for {code}...", flush=True)
        portal_dialog_messages.clear()

        try:
            with page.expect_download(timeout=35000) as dl_info:
                try:
                    dl_btn.click(timeout=5000)
                except Exception:
                    dl_btn.click(force=True)

            download = dl_info.value
            portal_filename = download.suggested_filename
            target_dir = getattr(bot, "downloads_dir", DOWNLOADS_DIR)
            dest = target_dir / portal_filename
            download.save_as(str(dest))
            print(f"[SUCCESS] Downloaded file as-is from portal: {portal_filename} ({dest.stat().st_size:,} bytes)", flush=True)
            return dest
        except Exception as exc:
            for m in portal_dialog_messages:
                if "no data found" in m.lower():
                    print(f"[-] Portal alert '{m}' received for {code}.", flush=True)
                    if "1.2.7" in code:
                        raise FileNotFoundError(
                            f"e-Panchayat portal returned no DSR attendance records for date '{date_formatted}' ({m})."
                        ) from exc
                    return None
            # For absentees and presentees, lack of a download is normal if 0 records match
            if "1.2.10" in code or "1.2.11" in code:
                print(f"[-] Optional report {code} download note: {exc}. Proceeding without it.", flush=True)
                return None
            raise
    finally:
        try:
            page.remove_listener("dialog", on_dialog)
        except Exception:
            pass


# Backward compatibility alias
def download_single_report(page, iframe, code, key, today_str):
    dest = DOWNLOADS_DIR / f"{key}.xls"
    return dest


def run_pipeline(target_date: str = ""):
    print("=" * 65, flush=True)
    print("  e-Panchayat Automation - DSR Report Generation Pipeline", flush=True)
    print("=" * 65, flush=True)

    date_str = target_date.strip() if target_date else datetime.now().strftime("%Y-%m-%d")
    date_formatted = format_portal_date(date_str)
    print(f"[*] Target Report Date: {date_formatted} ({date_str})", flush=True)

    # REMOVE OLD SAVED FILES - only newly downloaded files must be used
    print("[*] Cleaning up old downloads...", flush=True)
    for old_f in DOWNLOADS_DIR.iterdir():
        if old_f.is_file():
            try:
                old_f.unlink()
            except Exception:
                pass

    app = EPTSAutomation(headless=False)
    try:
        app.ensure_logged_in()

        downloaded_paths = {}

        # Step 1: Select GP Monitoring -> Download GM-R 1.2.7 (DSR Raw Data Report)
        print("\n" + "=" * 50, flush=True)
        print("[*] STEP 1: GP Monitoring -> GM-R 1.2.7 DSR Raw Data Report", flush=True)
        print("=" * 50, flush=True)
        try:
            p1 = download_single_report_with_menu(app, "1.2.7", date_formatted)
            downloaded_paths["raw_dsr"] = p1
        except Exception as e:
            print(f"[ERROR] Failed downloading GM-R 1.2.7: {e}", flush=True)
            raise RuntimeError(f"Failed to download GM-R 1.2.7 DSR Raw Data from portal: {e}")

        # Step 2: Select GP Monitoring -> Download GM-R 1.2.11 (Presentees Report)
        print("\n" + "=" * 50, flush=True)
        print("[*] STEP 2: Re-select GP Monitoring -> GM-R 1.2.11 Presentees Report", flush=True)
        print("=" * 50, flush=True)
        try:
            p2 = download_single_report_with_menu(app, "1.2.11", date_formatted)
            downloaded_paths["presentees"] = p2
        except Exception as e:
            print(f"[WARNING] Could not download GM-R 1.2.11: {e}", flush=True)

        # Step 3: Select GP Monitoring -> Download GM-R 1.2.10 (Absentees Report)
        print("\n" + "=" * 50, flush=True)
        print("[*] STEP 3: Re-select GP Monitoring -> GM-R 1.2.10 Absentees Report", flush=True)
        print("=" * 50, flush=True)
        try:
            p3 = download_single_report_with_menu(app, "1.2.10", date_formatted)
            downloaded_paths["absentees"] = p3
        except Exception as e:
            print(f"[WARNING] Could not download GM-R 1.2.10: {e}", flush=True)

        print("\n" + "=" * 55, flush=True)
        print("[+] Download Summary (Original Filenames Preserved):", flush=True)
        for k, v in downloaded_paths.items():
            if v and v.exists():
                print(f"    - {k}: {v.name} ({v.stat().st_size:,} bytes)", flush=True)

        # Step 4: Prepare Report Using ONLY Newly Downloaded Files
        raw_dsr_path = downloaded_paths.get("raw_dsr")
        if not raw_dsr_path or not raw_dsr_path.exists():
            raise FileNotFoundError("DSR Raw Data file was not downloaded. Aborting report preparation.")

        print("\n" + "=" * 55, flush=True)
        print(f"[*] Preparing Official 7-Section Report from newly downloaded file: {raw_dsr_path.name} ...", flush=True)
        sys.path.insert(0, str(BASE_DIR.parent.resolve()))
        from report_generator import process_attendance_file, generate_pdf

        p_path = downloaded_paths.get("presentees")
        presentees_source = (p_path.name, p_path.read_bytes()) if p_path and p_path.exists() and p_path.stat().st_size > 0 else None

        a_path = downloaded_paths.get("absentees")
        absentees_source = (a_path.name, a_path.read_bytes()) if a_path and a_path.exists() and a_path.stat().st_size > 0 else None

        report = process_attendance_file(
            raw_dsr_path.name,
            raw_dsr_path.read_bytes(),
            presentees_source=presentees_source,
            absentees_source=absentees_source,
        )

        try:
            from core.config import get_reports_dir
            reports_dir = get_reports_dir()
        except Exception:
            reports_dir = BASE_DIR.parent / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_pdf = reports_dir / f"{report.district_name.replace(' ', '_')}_Official_DSR_Report_{date_formatted}.pdf"
        generate_pdf(report, output_pdf)

        cached_pdf = DOWNLOADS_DIR / f"Official_DSR_Report_{date_formatted}.pdf"
        cached_pdf.write_bytes(output_pdf.read_bytes())

        print(f"\n[SUCCESS] Final Official 7-Section DSR Attendance PDF Generated:")
        print(f"--> {output_pdf} (Size: {output_pdf.stat().st_size:,} bytes)")
        print(f"District: {report.district_name} | Total GPs: {report.unique_gp_count}")
        print(f"Attendance Submitted: {report.totals.get('attendance_submitted')}")
        print(f"DSR Entered: {report.totals.get('dsr_entered')}")
        return output_pdf

    except Exception as e:
        print(f"\n[ERROR] Pipeline encountered an error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("[*] Closing browser session...", flush=True)
        app.close()
        print("[+] Done.", flush=True)


if __name__ == "__main__":
    run_pipeline()

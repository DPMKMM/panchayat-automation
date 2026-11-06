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
    from dsr.automation import EPTSAutomation, BASE_DIR, DOWNLOADS_DIR, OTP_FILE
except (ImportError, ModuleNotFoundError):
    from epts_automation import EPTSAutomation, BASE_DIR, DOWNLOADS_DIR, OTP_FILE

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_SCREENSHOT = BASE_DIR / "enlarged_reports.png"
MENU_URL = "https://tgprepanchayat.telangana.gov.in/PSPerformance/DynamicReportsMenu2Array"


def get_my_iframe(page):
    """Returns the content iframe named 'my-iframe' or holding PSPerformance."""
    for f in page.frames:
        if f.name == "my-iframe" or "PSPerformance" in f.url:
            return f
    if len(page.frames) > 2:
        return page.frames[2]
    return None


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
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
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
    time.sleep(3)

    # Screenshot initial view
    ss_path = BASE_DIR / f"page_{code.replace('.', '_')}.png"
    try:
        page.screenshot(path=str(ss_path))
        print(f"[+] Saved view screenshot to {ss_path}", flush=True)
    except Exception:
        pass

    # Set Date filter in iframe (using DD-MMM-YYYY e.g. 30-Oct-2026 or 02-Nov-2026)
    print(f"[*] Setting date to {date_formatted} in iframe...", flush=True)
    iframe.evaluate(f"""() => {{
        const inputs = document.querySelectorAll("input[type='text'], input[name*='Date' i], input[id*='Date' i]");
        for (const inp of inputs) {{
            inp.removeAttribute('readonly');
            inp.value = '{date_formatted}';
            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
            inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
        }}
        // Remove target="_blank" from form so download stays in current page
        for (const f of document.forms) {{
            f.removeAttribute('target');
        }}
    }}""")
    time.sleep(0.5)

    # Also fill via Playwright locator to trigger any ASP.NET calendar handlers
    try:
        txt_loc = iframe.locator("input[type='text']:visible").first
        if txt_loc.is_visible(timeout=2000):
            txt_loc.evaluate("el => el.removeAttribute('readonly')")
            txt_loc.fill(date_formatted)
            txt_loc.press("Tab")
            time.sleep(0.5)
    except Exception as e:
        print(f"[-] Note on fill: {e}", flush=True)

    # Save verification screenshot showing date filled in
    after_date_ss = BASE_DIR / f"after_date_{code.replace('.', '_')}.png"
    try:
        page.screenshot(path=str(after_date_ss))
        print(f"[+] Saved date verification screenshot to {after_date_ss}", flush=True)
    except Exception:
        pass

    # Locate and click Download button
    print(f"[*] Waiting for download button for {code}...", flush=True)
    dl_selectors = [
        "input[value='Download']",
        "input[value='Download Excel']",
        "input[value*='Download' i]",
        "button:has-text('Download')",
        "button:has-text('Download Excel')",
        "input[id*='btnExport' i]",
        "input[id*='btnDownload' i]",
    ]
    dl_btn = iframe.locator(", ".join(dl_selectors)).first
    dl_btn.wait_for(state="visible", timeout=15000)

    print(f"[*] Triggering download for {code}...", flush=True)
    portal_dialog_messages.clear()

    try:
        with page.expect_download(timeout=15000) as dl_info:
            dl_btn.click()
            # If an alert appeared immediately (like 'Sorry! No Data Found..'), check dialog list
            time.sleep(1)
            for m in portal_dialog_messages:
                if "no data found" in m.lower():
                    print(f"[-] Portal dialog: '{m}' for {code}. No records found.", flush=True)
                    return None

        download = dl_info.value
        # USE THE ORIGINAL SUGGESTED FILENAME AS-IS WITHOUT RENAMING
        portal_filename = download.suggested_filename
        target_dir = getattr(bot, "downloads_dir", DOWNLOADS_DIR)
        dest = target_dir / portal_filename
        download.save_as(str(dest))
        print(f"[SUCCESS] Downloaded file as-is from portal: {portal_filename} ({dest.stat().st_size:,} bytes)", flush=True)
        return dest
    except Exception as exc:
        for m in portal_dialog_messages:
            if "no data found" in m.lower():
                print(f"[-] Portal alert '{m}' received for {code}. No records exist.", flush=True)
                return None
        # For absentees and presentees, lack of a download is normal if 0 records match
        if "1.2.10" in code or "1.2.11" in code:
            print(f"[-] Optional report {code} download note: {exc}. Proceeding without it.", flush=True)
            return None
        raise


# Backward compatibility alias
def download_single_report(page, iframe, code, key, today_str):
    dest = DOWNLOADS_DIR / f"{key}.xls"
    return dest


def run_pipeline(target_date: str = ""):
    print("=" * 65, flush=True)
    print("  e-Panchayat Automated DSR Report Generation Pipeline", flush=True)
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

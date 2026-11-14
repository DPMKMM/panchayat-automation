"""Shared-session Playwright scraper for Automated Multiple Days DSR (GM-R 1.2.7).

STRICT ZERO-DUPLICATE-LOGIN CONTRACT:
This module operates exclusively on the already-authenticated Playwright Page
(bot.page) managed centrally by dsr.service / core.session_manager. It never launches
a new browser, never asks for duplicate credentials or OTP, and downloads ONLY the
daily GM-R 1.2.7 Raw Data report (omitting Presentees 1.2.11 and Absentees 1.2.10).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

from Auto_Multi_DSR.holidays import format_display_date, format_portal_date, parse_date_input
from core.config import get_downloads_dir

logger = logging.getLogger("auto_multi_dsr_automation")


def _assert_page_active(page: Any) -> None:
    if page is None or (hasattr(page, "is_closed") and page.is_closed()):
        raise PermissionError(
            "e-Panchayat browser session is closed or inactive. Please complete Departmental Login first."
        )
    cur_url = str(getattr(page, "url", "") or "").lower()
    if "login.aspx" in cur_url or ("default.aspx" in cur_url and "psperformance" not in cur_url and "dashboard" not in cur_url):
        raise PermissionError(
            "e-Panchayat portal session expired and redirected to Login. Please re-authenticate once from Console."
        )


def _get_my_iframe(page: Any):
    """Find the content iframe hosting PSPerformance reports inside EPTS dashboard."""
    _assert_page_active(page)
    for f in getattr(page, "frames", []) or []:
        f_name = (getattr(f, "name", "") or "").lower()
        f_url = (getattr(f, "url", "") or "").lower()
        if f_name == "my-iframe" or "psperformance" in f_url or "dynamicreports" in f_url:
            return f
    try:
        handle = page.locator("iframe[name='my-iframe'], iframe#my-iframe").first.element_handle(timeout=1500)
        if handle:
            cf = handle.content_frame()
            if cf and (getattr(cf, "url", "") or "").lower() != "about:blank":
                return cf
    except Exception:
        pass
    frames = getattr(page, "frames", []) or []
    if len(frames) > 2:
        return frames[2]
    return None


def download_daily_gmr127_raw(
    bot: Any,
    target_date: str | date,
    downloads_dir: Path | None = None,
    max_retries: int = 2,
) -> tuple[str, bytes]:
    """Download daily GM-R 1.2.7 DSR Raw Data report for a single working date from portal.

    Returns:
        (filename, raw_bytes)
    Raises:
        RuntimeError or FileNotFoundError if download fails after retries.
    """
    d_obj = parse_date_input(target_date)
    date_formatted = format_portal_date(d_obj)  # e.g. 02-Nov-2026
    disp_date = format_display_date(d_obj)      # e.g. 02-11-2026
    target_dir = downloads_dir or getattr(bot, "downloads_dir", None) or get_downloads_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    page = getattr(bot, "page", None)
    _assert_page_active(page)

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        dialog_messages: list[str] = []

        def on_dialog(dialog):
            msg = (dialog.message or "").strip()
            logger.info("[Auto-Multi-DSR] Portal alert on %s (attempt %d): '%s' - accepting", disp_date, attempt, msg)
            dialog_messages.append(msg)
            try:
                dialog.accept()
            except Exception:
                pass

        page.on("dialog", on_dialog)
        try:
            logger.info("[*] [Attempt %d/%d] Preparing GM-R 1.2.7 for date %s (%s)...", attempt, max_retries, disp_date, date_formatted)

            dl_selectors = [
                "input[value='Download']",
                "input[value='Download Excel']",
                "input[value*='Download' i]",
                "button:has-text('Download')",
                "button:has-text('Download Excel')",
                "input[id*='btnExport' i]",
                "input[id*='btnDownload' i]",
            ]

            iframe = _get_my_iframe(page)

            # Check if iframe is already loaded directly on GM-R 1.2.7 report form
            already_on_form = False
            if iframe:
                try:
                    cand_btn = iframe.locator(", ".join(dl_selectors)).first
                    cand_txt = iframe.locator("input[type='text'], input[name*='Date' i], input[id*='Date' i]").first
                    if cand_btn.is_visible(timeout=1000) and cand_txt.is_visible(timeout=1000):
                        already_on_form = True
                        logger.info("[*] Iframe is already on GM-R 1.2.7 report form. Reusing form for %s.", disp_date)
                except Exception:
                    already_on_form = False

            if not already_on_form:
                logger.info("[*] Navigating menu to GM-R 1.2.7 for date %s...", disp_date)
                if hasattr(bot, "select_menu"):
                    bot.select_menu("GP Monitoring")
                else:
                    menu_loc = page.locator("//a[normalize-space(.)='GP Monitoring'] | //input[@value='GP Monitoring']").first
                    menu_loc.click()
                time.sleep(2.0)

                iframe = _get_my_iframe(page)
                if not iframe:
                    time.sleep(1.8)
                    iframe = _get_my_iframe(page)
                if not iframe:
                    raise RuntimeError("Could not locate 'my-iframe' in portal after clicking GP Monitoring.")

                try:
                    iframe.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass

                # Click 'Enlarge All'
                try:
                    enlarge_btn = iframe.locator("text='Enlarge All'").first
                    if enlarge_btn.is_visible(timeout=2500):
                        enlarge_btn.click()
                        time.sleep(1.0)
                except Exception as e:
                    logger.debug("Enlarge All note: %s", e)

                # Expand 'DSR REPORTS' section
                try:
                    dsr_header = iframe.locator("text='DSR REPORTS'").first
                    if dsr_header.is_visible(timeout=2500):
                        dsr_header.click()
                        time.sleep(1.2)
                except Exception as e:
                    logger.debug("DSR REPORTS click note: %s", e)

                # Locate GM-R 1.2.7 link (Raw Data)
                selectors = [
                    "a:has-text('1.2.7')",
                    "a:has-text('Raw Data')",
                    "//a[contains(., '1.2.7') or contains(., 'Raw Data')]",
                ]
                link = None
                for sel in selectors:
                    cand = iframe.locator(sel).first
                    try:
                        if cand.is_visible(timeout=1500):
                            link = cand
                            break
                    except Exception:
                        pass

                if not link:
                    link = iframe.locator("a:has-text('1.2.7')").first
                    link.wait_for(state="visible", timeout=10000)

                link.click()
                time.sleep(1.5)

            # Ensure date input is visible and ready
            txt_loc = iframe.locator("input[type='text'], input[name*='Date' i], input[id*='Date' i]").first
            try:
                txt_loc.wait_for(state="visible", timeout=8000)
            except Exception:
                pass

            # Fill Date filter in iframe with DD-MMM-YYYY
            iframe.evaluate(
                f"""(dt) => {{
                    const inputs = document.querySelectorAll("input[type='text'], input[name*='Date' i], input[id*='Date' i]");
                    for (const inp of inputs) {{
                        inp.removeAttribute('readonly');
                        inp.value = dt;
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    }}
                    for (const f of document.forms) {{
                        f.removeAttribute('target');
                    }}
                }}""",
                date_formatted,
            )
            time.sleep(0.3)

            # Also fill via Playwright locator to trigger ASP.NET handlers
            try:
                if txt_loc.is_visible(timeout=1500):
                    txt_loc.evaluate("el => el.removeAttribute('readonly')")
                    txt_loc.fill(date_formatted)
                    txt_loc.press("Tab")
                    time.sleep(0.3)
            except Exception:
                pass

            # Locate and click Download button
            dl_btn = iframe.locator(", ".join(dl_selectors)).first
            dl_btn.wait_for(state="visible", timeout=15000)

            dialog_messages.clear()
            with page.expect_download(timeout=22000) as dl_info:
                dl_btn.click()

            download = dl_info.value
            portal_fname = download.suggested_filename or f"{disp_date}_GMR_127_RawData.xls"
            dest = target_dir / f"auto_multi_{disp_date}_{portal_fname}"
            download.save_as(str(dest))
            raw_bytes = dest.read_bytes()

            if len(raw_bytes) < 100:
                raise ValueError(f"Downloaded file for {disp_date} is empty ({len(raw_bytes)} bytes).")

            logger.info("[+] [SUCCESS] Downloaded %s for %s (%d bytes)", portal_fname, disp_date, len(raw_bytes))
            return portal_fname, raw_bytes

        except Exception as exc:
            last_error = exc
            for m in dialog_messages:
                m_low = m.lower()
                if "no data" in m_low or "no record" in m_low or "not found" in m_low or "no detail" in m_low:
                    raise FileNotFoundError(
                        f"e-Panchayat portal returned no DSR attendance records for date '{disp_date}' ({m})."
                    ) from exc
            logger.warning("[-] Download failed for date %s (attempt %d/%d): %s", disp_date, attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2.0)
        finally:
            try:
                page.remove_listener("dialog", on_dialog)
            except Exception:
                pass

    raise RuntimeError(
        f"Failed to download GM-R 1.2.7 DSR Raw Data for date '{disp_date}' after {max_retries} attempts: {last_error}"
    )

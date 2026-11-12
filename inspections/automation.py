"""Shared-session Playwright automation for GM-R 39.1 MPO/DLPO/DPO Inspection Data Entry Report.

Zero-Duplicate-Login Contract:
Operates strictly on the active authenticated Playwright Page (`bot.page`) managed
by `dsr.service` / `core.session_manager`. Never spawns a duplicate browser or OTP prompt.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from inspections.models import SUPPORTED_DESIGNATIONS, get_designation_spec

logger = logging.getLogger("inspections_automation")


def _assert_session_active(page) -> None:
    """Ensure shared EPTS Playwright page is open and not redirected to Login."""
    if page is None or (hasattr(page, "is_closed") and page.is_closed()):
        raise PermissionError(
            "e-Panchayat browser session is closed or inactive. Please complete Departmental Login first."
        )
    try:
        cur_url = str(getattr(page, "url", "") or "").lower()
    except Exception:
        cur_url = ""
    if "login.aspx" in cur_url or ("default.aspx" in cur_url and "psperformance" not in cur_url and "dashboard" not in cur_url):
        raise PermissionError(
            "e-Panchayat portal session expired and redirected to Login. Please re-authenticate once."
        )


def _get_my_iframe(page):
    """Locate the `my-iframe` frame hosting PSPerformance / DynamicReports inside EPTS dashboard."""
    _assert_session_active(page)
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
            or "inspection" in f_url
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


def _find_visible(scope, selector: str):
    try:
        for loc in scope.locator(selector).all():
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                continue
    except Exception:
        pass
    return None


def _inspect_selects(iframe) -> dict[str, Any]:
    """Inspect visible <select> elements inside GM-R 39.1 frame and classify Designation vs Week."""
    return iframe.evaluate(
        """() => {
            const selects = Array.from(document.querySelectorAll('select'));
            const result = [];
            selects.forEach((el, idx) => {
                const style = window.getComputedStyle(el);
                if (style && (style.display === 'none' || style.visibility === 'hidden')) return;
                const opts = Array.from(el.options).map(o => ({
                    value: String(o.value || '').trim(),
                    text: String(o.text || '').trim()
                }));
                result.push({
                    idx: idx,
                    id: el.id || '',
                    name: el.name || '',
                    options: opts
                });
            });
            return result;
        }"""
    )


def _classify_selects(select_infos: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Identify Inspected-by Designation dropdown and Select-Week dropdown (skipping District dropdown)."""
    desig_sel = None
    week_sel = None

    for info in select_infos:
        id_name = f"{info.get('id', '')} {info.get('name', '')}".lower()
        opt_texts = " | ".join(o.get("text", "") for o in info.get("options", [])).lower()

        if desig_sel is None and (
            "desig" in id_name
            or "inspect" in id_name
            or ("mpo" in opt_texts and ("dlpo" in opt_texts or "dpo" in opt_texts or "mpdo" in opt_texts))
        ):
            desig_sel = info
            continue

        if "dist" in id_name and "week" not in id_name:
            continue

        has_week_dates = any(
            re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", o.get("text", ""))
            or re.search(r"\d{2}[-/][A-Za-z0-9]{2,3}[-/]\d{4}", o.get("text", ""))
            or " to " in o.get("text", "").lower()
            for o in info.get("options", [])
        )
        if week_sel is None and ("week" in id_name or "period" in id_name or has_week_dates):
            week_sel = info

    # Fallback: skip designation & district selects
    if not week_sel:
        for info in select_infos:
            id_name = f"{info.get('id', '')} {info.get('name', '')}".lower()
            if info is not desig_sel and "dist" not in id_name and len(info.get("options", [])) > 1:
                week_sel = info
                break
    return desig_sel, week_sel


def _locator_for_select(iframe, sel_info: dict[str, Any]):
    sel_id = sel_info.get("id")
    if sel_id:
        return iframe.locator(f"#{sel_id}").first
    sel_name = sel_info.get("name")
    if sel_name:
        return iframe.locator(f"select[name='{sel_name}']").first
    return iframe.locator("select:visible").nth(int(sel_info.get("idx", 0)))


def _open_gmr391_frame(bot):
    """Navigate authenticated session: GP Monitoring -> GM-R 39 -> GM-R 39.1."""
    page = bot.page
    _assert_session_active(page)
    logger.info("[*] Navigating GP Monitoring -> GM-R 39 -> GM-R 39.1 inside shared session...")

    bot.select_menu("GP Monitoring")
    time.sleep(2.0)

    iframe = None
    deadline = time.time() + 20.0
    while time.time() < deadline:
        iframe = _get_my_iframe(page)
        if iframe:
            try:
                if iframe.locator("text='Enlarge All'").count() > 0 or iframe.locator("a").count() > 3:
                    break
            except Exception:
                pass
        time.sleep(0.4)

    if not iframe:
        _assert_session_active(page)
        raise RuntimeError("Could not locate 'my-iframe' after selecting GP Monitoring for GM-R 39.1.")

    try:
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    # If search input exists inside the menu frame, try searching GM-R 39
    try:
        search_box = _find_visible(
            iframe,
            "input[type='search'], input[placeholder*='Search' i], input[id*='search' i]",
        )
        if search_box is not None:
            search_box.fill("39.1")
            time.sleep(0.6)
    except Exception:
        pass

    # Look for GM-R 39.1 link directly or after clicking Enlarge All / GM-R 39 header
    target_selectors = (
        "a:has-text('39.1')",
        "a:has-text('GM-R 39.1')",
        "a:has-text('MPO,DLPO,DPO Inspection Data Entry')",
        "a:has-text('MPO, DLPO, DPO Inspection Data Entry')",
    )

    def _find_391():
        for sel in target_selectors:
            vis = _find_visible(iframe, sel)
            if vis is not None:
                return vis
        return None

    link = _find_391()
    if link is None:
        try:
            enlarge = _find_visible(iframe, "text='Enlarge All'")
            if enlarge is not None:
                enlarge.click()
                time.sleep(1.0)
                link = _find_391()
        except Exception:
            pass

    if link is None:
        for hdr_sel in ("text*='GM-R 39'", "text*='Inspection Data Entry Report'"):
            try:
                hdr = _find_visible(iframe, hdr_sel)
                if hdr is not None:
                    hdr.click()
                    time.sleep(1.0)
                    link = _find_391()
                    if link is not None:
                        break
            except Exception:
                continue

    if link is None:
        link = iframe.locator("a:has-text('39.1')").first
        link.wait_for(state="visible", timeout=12000)

    try:
        link.scroll_into_view_if_needed()
    except Exception:
        pass
    link.click()

    # Wait for Designation & Week <select> elements to render inside GM-R 39.1 iframe
    ddl_deadline = time.time() + 20.0
    while time.time() < ddl_deadline:
        iframe = _get_my_iframe(page) or iframe
        try:
            infos = _inspect_selects(iframe)
            desig_sel, week_sel = _classify_selects(infos)
            if desig_sel is not None or week_sel is not None:
                time.sleep(0.4)
                return iframe
        except Exception:
            pass
        time.sleep(0.4)

    _assert_session_active(page)
    raise TimeoutError("Timed out waiting for Designation / Week dropdowns inside GM-R 39.1 iframe.")


def _select_designation(iframe, desig_info: dict[str, Any], target_designation: str) -> None:
    """Select the requested Officer Designation in GM-R 39.1 dropdown."""
    spec = get_designation_spec(target_designation)
    canon = spec["designation"]
    loc = _locator_for_select(iframe, desig_info)

    chosen_val = None
    for opt in desig_info.get("options", []):
        txt = opt.get("text", "").strip()
        val = opt.get("value", "").strip()
        if not val or val == "0" or "select" in txt.lower():
            continue
        if txt.casefold() == canon.casefold() or val.casefold() == canon.casefold():
            chosen_val = val
            break
    if chosen_val is None:
        for opt in desig_info.get("options", []):
            txt = opt.get("text", "").strip()
            val = opt.get("value", "").strip()
            if not val or val == "0" or "select" in txt.lower():
                continue
            # Avoid matching 'CEO' against 'Deputy CEO'
            if canon == "CEO" and "deputy" in txt.lower():
                continue
            if canon.lower() in txt.lower():
                chosen_val = val
                break

    if chosen_val is None:
        loc.select_option(label=canon)
    else:
        loc.select_option(value=chosen_val)
    time.sleep(1.5)


def _clean_week_options(week_info: dict[str, Any] | None) -> list[dict[str, str]]:
    if not week_info:
        return []
    cleaned: list[dict[str, str]] = []
    for opt in week_info.get("options", []):
        val = str(opt.get("value", "")).strip()
        txt = str(opt.get("text", "")).strip()
        if not txt or val in ("", "0", "-1") or "select" in txt.lower():
            continue
        cleaned.append({"value": val or txt, "text": txt})
    return cleaned


def resolve_week_slice(
    available_weeks: list[dict[str, str]],
    from_week: str = "",
    to_week: str = "",
) -> list[dict[str, str]]:
    """Return inclusive slice of week items matching From Week .. To Week regardless of sort order."""
    if not available_weeks:
        return []

    def _find_idx(target: str) -> int | None:
        clean = str(target or "").strip().casefold()
        if not clean:
            return None
        for idx, item in enumerate(available_weeks):
            if item["value"].casefold() == clean or item["text"].casefold() == clean:
                return idx
        for idx, item in enumerate(available_weeks):
            if clean in item["text"].casefold():
                return idx
        return None

    i1 = _find_idx(from_week)
    i2 = _find_idx(to_week)
    if i1 is None and i2 is None:
        return [available_weeks[0]]
    if i1 is None:
        return [available_weeks[i2]]  # type: ignore[index]
    if i2 is None:
        return [available_weeks[i1]]
    lo, hi = min(i1, i2), max(i1, i2)
    return available_weeks[lo:hi + 1]


def fetch_inspection_metadata(bot, designation: str | None = None) -> dict[str, Any]:
    """Open GM-R 39.1 inside shared session and extract live Designations & Week options."""
    iframe = _open_gmr391_frame(bot)
    infos = _inspect_selects(iframe)
    desig_info, week_info = _classify_selects(infos)

    if designation and desig_info is not None:
        _select_designation(iframe, desig_info, designation)
        iframe = _get_my_iframe(bot.page) or iframe
        infos = _inspect_selects(iframe)
        desig_info, week_info = _classify_selects(infos)

    portal_desigs = []
    if desig_info:
        for opt in desig_info.get("options", []):
            txt = str(opt.get("text", "")).strip()
            val = str(opt.get("value", "")).strip()
            if txt and val not in ("", "0") and "select" not in txt.lower():
                portal_desigs.append({"value": val, "text": txt})

    weeks = _clean_week_options(week_info)
    return {
        "designations": list(SUPPORTED_DESIGNATIONS),
        "portal_designations": portal_desigs,
        "weeks": weeks,
        "selected_designation": get_designation_spec(designation or "MPO")["designation"],
    }


def _find_excel_icon_locator(iframe):
    """Locate the Excel icon/image button next to Submit / CompleteReport inside GM-R 39.1."""
    excel_selectors = (
        "input[type='image'][src*='excel' i]",
        "input[type='image'][src*='xls' i]",
        "input[type='image'][id*='excel' i]",
        "input[type='image'][id*='xls' i]",
        "input[type='image'][title*='Excel' i]",
        "input[src*='excel' i]",
        "a:has(img[src*='excel' i])",
        "img[src*='excel' i]",
        "a:has(img[src*='xls' i])",
        "img[src*='xls' i]",
        "a[title*='Excel' i]",
        "input[title*='Excel' i]",
        "button[title*='Excel' i]",
        "input[value*='Excel' i]",
        "button:has-text('Excel')",
        "a[id*='Excel' i]",
        "input[id*='Excel' i]",
        "[onclick*='Excel' i]",
        "input[type='image'][src*='xl' i]",
        "a:has(img[src*='xl' i])",
        "input[type='image'][id*='Export' i]",
        "a[id*='Export' i]",
        "input[type='image']",
    )
    for sel in excel_selectors:
        vis = _find_visible(iframe, sel)
        if vis is not None:
            return vis
    # Structural DOM fallback: clickable image/anchor directly adjacent to Submit or CompleteReport button
    try:
        idx = iframe.evaluate(
            """() => {
                const btns = Array.from(document.querySelectorAll("input, button, a, img"));
                for (let i = 0; i < btns.length; i++) {
                    const txt = ((btns[i].value || btns[i].innerText || btns[i].title || '') + '').trim().toLowerCase();
                    if (txt.includes('completereport') || txt.includes('complete report')) {
                        for (let j = i - 1; j >= Math.max(0, i - 4); j--) {
                            const tag = btns[j].tagName.toLowerCase();
                            const t = (btns[j].type || '').toLowerCase();
                            if (tag === 'img' || t === 'image' || tag === 'a') {
                                btns[j].setAttribute('data-epts-excel-icon', '1');
                                return true;
                            }
                        }
                    }
                }
                return false;
            }"""
        )
        if idx:
            cand = iframe.locator("[data-epts-excel-icon='1']").first
            if cand.is_visible():
                return cand
    except Exception:
        pass
    return None


def download_inspection_weeks(
    bot,
    designation: str,
    from_week: str,
    to_week: str,
    downloads_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Iterate selected weeks in GM-R 39.1, click Submit / Excel icon, and save weekly files."""
    page = bot.page
    spec = get_designation_spec(designation)
    canon_desig = spec["designation"]

    insp_dir = Path(downloads_dir) / "inspections_tmp"
    insp_dir.mkdir(parents=True, exist_ok=True)
    for old in insp_dir.iterdir():
        if old.is_file():
            try:
                old.unlink()
            except Exception:
                pass

    portal_dialogs: list[str] = []

    def _on_dialog(dialog):
        msg = (dialog.message or "").strip()
        portal_dialogs.append(msg)
        logger.info("[*] Portal alert in GM-R 39.1: %s", msg)
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", _on_dialog)
    downloaded_items: list[dict[str, Any]] = []

    try:
        iframe = _open_gmr391_frame(bot)
        infos = _inspect_selects(iframe)
        desig_info, week_info = _classify_selects(infos)

        if desig_info is not None:
            _select_designation(iframe, desig_info, canon_desig)
            iframe = _get_my_iframe(page) or iframe
            infos = _inspect_selects(iframe)
            desig_info, week_info = _classify_selects(infos)

        available_weeks = _clean_week_options(week_info)
        if not available_weeks:
            raise FileNotFoundError(
                f"No weekly date ranges found in portal GM-R 39.1 for designation {canon_desig}."
            )

        selected_weeks = resolve_week_slice(available_weeks, from_week=from_week, to_week=to_week)
        week_labels = [w["text"] for w in selected_weeks]

        for idx, wk in enumerate(selected_weeks, start=1):
            portal_dialogs.clear()
            iframe = _get_my_iframe(page) or iframe
            infos = _inspect_selects(iframe)
            _, cur_week_info = _classify_selects(infos)
            if cur_week_info is None:
                raise RuntimeError(f"Week dropdown disappeared in GM-R 39.1 on week '{wk['text']}'.")

            week_loc = _locator_for_select(iframe, cur_week_info)
            try:
                week_loc.select_option(value=wk["value"])
            except Exception:
                week_loc.select_option(label=wk["text"])
            time.sleep(0.8)

            iframe = _get_my_iframe(page) or iframe
            excel_loc = _find_excel_icon_locator(iframe)

            # If Excel icon is already visible on the filter bar (standard GM-R 39.1 layout),
            # try downloading directly on week selection first; if no download fires, click Submit then Excel.
            did_download = False
            if excel_loc is not None:
                try:
                    iframe.evaluate("() => { for (const f of document.forms) f.removeAttribute('target'); }")
                except Exception:
                    pass
                try:
                    with page.expect_download(timeout=12000) as dl_info:
                        excel_loc.click()
                    dl = dl_info.value
                    suggested = dl.suggested_filename or f"GMR39_1_{canon_desig}_week_{idx:02d}.xls"
                    dest = insp_dir / f"w{idx:02d}_{suggested}"
                    dl.save_as(str(dest))
                    raw_bytes = dest.read_bytes()
                    downloaded_items.append({
                        "week_label": wk["text"],
                        "filename": suggested,
                        "raw_bytes": raw_bytes,
                        "status": "downloaded" if raw_bytes else "no_data",
                    })
                    did_download = True
                except Exception:
                    if any("no data" in m.lower() or "no record" in m.lower() for m in portal_dialogs):
                        downloaded_items.append({
                            "week_label": wk["text"],
                            "filename": "",
                            "raw_bytes": b"",
                            "status": "no_data",
                        })
                        continue

            if did_download:
                continue

            # Fallback path: click Submit first, then click Excel icon
            try:
                submit_btn = _find_visible(
                    iframe,
                    "input[value*='Submit' i], button:has-text('Submit'), input[id*='Submit' i], input[id*='btnGet' i]",
                )
                if submit_btn is not None:
                    submit_btn.click()
                    time.sleep(1.8)
            except Exception as exc:
                logger.debug("Submit click note on week %s: %s", wk["text"], exc)

            iframe = _get_my_iframe(page) or iframe
            excel_loc = None
            xl_deadline = time.time() + 12.0
            while time.time() < xl_deadline:
                if any("no data" in m.lower() or "no record" in m.lower() for m in portal_dialogs):
                    break
                excel_loc = _find_excel_icon_locator(iframe)
                if excel_loc is not None:
                    break
                time.sleep(0.4)

            if excel_loc is None:
                downloaded_items.append({
                    "week_label": wk["text"],
                    "filename": "",
                    "raw_bytes": b"",
                    "status": "no_data",
                })
                continue

            try:
                iframe.evaluate("() => { for (const f of document.forms) f.removeAttribute('target'); }")
            except Exception:
                pass

            try:
                with page.expect_download(timeout=20000) as dl_info:
                    excel_loc.click()
                dl = dl_info.value
                suggested = dl.suggested_filename or f"GMR39_1_{canon_desig}_week_{idx:02d}.xls"
                dest = insp_dir / f"w{idx:02d}_{suggested}"
                dl.save_as(str(dest))
                raw_bytes = dest.read_bytes()
                downloaded_items.append({
                    "week_label": wk["text"],
                    "filename": suggested,
                    "raw_bytes": raw_bytes,
                    "status": "downloaded" if raw_bytes else "no_data",
                })
            except Exception as exc:
                if any("no data" in m.lower() or "no record" in m.lower() for m in portal_dialogs):
                    downloaded_items.append({
                        "week_label": wk["text"],
                        "filename": "",
                        "raw_bytes": b"",
                        "status": "no_data",
                    })
                    continue
                raise RuntimeError(f"Failed downloading Excel for week '{wk['text']}': {exc}") from exc

        return downloaded_items, week_labels
    finally:
        try:
            page.remove_listener("dialog", _on_dialog)
        except Exception:
            pass

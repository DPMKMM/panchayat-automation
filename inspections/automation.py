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

from inspections.models import (
    SUPPORTED_DESIGNATIONS,
    assign_week_to_month,
    extract_week_dates,
    format_month_key_label,
    get_designation_spec,
    parse_month_key,
)

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


def _get_all_candidate_frames(page) -> list[Any]:
    """Return non-main frames ordered with my-iframe / PSPerformance frames first."""
    _assert_session_active(page)
    main_f = getattr(page, "main_frame", None)
    preferred: list[Any] = []
    others: list[Any] = []

    pages_to_scan = [page]
    try:
        ctx = getattr(page, "context", None)
        for p in (getattr(ctx, "pages", []) or []):
            if p not in pages_to_scan and not (hasattr(p, "is_closed") and p.is_closed()):
                pages_to_scan.append(p)
    except Exception:
        pass

    for pg in pages_to_scan:
        if pg != page:
            mf = getattr(pg, "main_frame", None)
            if mf is not None:
                others.append(mf)
        for frame in getattr(pg, "frames", []) or []:
            if frame == main_f:
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
                preferred.append(frame)
            else:
                others.append(frame)

    try:
        handle = page.locator("iframe[name='my-iframe'], iframe#my-iframe").first.element_handle(timeout=1000)
        if handle:
            cf = handle.content_frame()
            if cf and cf not in preferred and (getattr(cf, "url", "") or "").lower() != "about:blank":
                preferred.insert(0, cf)
    except Exception:
        pass
    return preferred + others


def _get_my_iframe(page):
    """Locate the `my-iframe` frame hosting PSPerformance / DynamicReports inside EPTS dashboard."""
    frames = _get_all_candidate_frames(page)
    return frames[0] if frames else None


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


def _inspect_selects(iframe) -> list[dict[str, Any]]:
    """Inspect <select> elements inside GM-R 39.1 frame (visible first, falling back to non-hidden if Select2/Chosen used)."""
    return iframe.evaluate(
        """() => {
            const selects = Array.from(document.querySelectorAll('select'));
            const visible = [];
            const allNonEmpty = [];
            selects.forEach((el, idx) => {
                const style = window.getComputedStyle(el);
                const opts = Array.from(el.options).map(o => ({
                    value: String(o.value || '').trim(),
                    text: String(o.text || '').trim()
                }));
                const item = {
                    idx: idx,
                    id: el.id || '',
                    name: el.name || '',
                    selectedValue: String(el.value || '').trim(),
                    options: opts
                };
                if (opts.length > 0) allNonEmpty.push(item);
                if (style && style.display !== 'none' && style.visibility !== 'hidden') {
                    visible.push(item);
                }
            });
            return visible.length > 0 ? visible : allNonEmpty;
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
    return iframe.locator("select").nth(int(sel_info.get("idx", 0)))


def _find_frame_with_gmr_menu(page):
    """Return the child frame currently rendering the DynamicReports GM-R menu."""
    for f in _get_all_candidate_frames(page):
        try:
            if (
                f.locator("text='Enlarge All'").count() > 0
                or f.locator("a:has-text('GM-R')").count() > 0
                or f.locator("xpath=//*[contains(., 'GM-R 39')]").count() > 0
                or f.locator("a:has-text('39.1')").count() > 0
            ):
                return f
        except Exception:
            continue
    return None


def _find_frame_with_gmr391_selects(page, fallback_frame=None):
    """Scan all frames/pages for GM-R 39.1 Designation/Week <select> controls."""
    candidates = _get_all_candidate_frames(page)
    if fallback_frame is not None and fallback_frame not in candidates:
        candidates.append(fallback_frame)
    for f in candidates:
        try:
            infos = _inspect_selects(f)
            if not infos:
                continue
            desig_sel, week_sel = _classify_selects(infos)
            if desig_sel is not None or week_sel is not None:
                return f, infos, desig_sel, week_sel
        except Exception:
            continue
    return fallback_frame, [], None, None


def _click_gp_monitoring_top_menu(bot) -> None:
    """Ensure EPTS dashboard is open and click the exact 'GP Monitoring' top menu item."""
    page = bot.page
    _assert_session_active(page)
    cur_url = str(getattr(page, "url", "") or "").lower()
    if "deptloginverified" not in cur_url:
        try:
            page.goto("https://epanchayat.telangana.gov.in/deptLoginVerified", wait_until="domcontentloaded", timeout=25000)
            time.sleep(1.0)
            _assert_session_active(page)
        except PermissionError:
            raise
        except Exception:
            pass

    gp_selectors = (
        "xpath=//a[normalize-space(.)='GP Monitoring'] | //input[@value='GP Monitoring']",
        "text='GP Monitoring'",
        "a:has-text('GP Monitoring')",
    )
    gp_loc = None
    for sel in gp_selectors:
        gp_loc = _find_visible(page, sel)
        if gp_loc is not None:
            break

    if gp_loc is not None:
        try:
            gp_loc.hover()
            time.sleep(0.25)
        except Exception:
            pass
        gp_loc.click()
        return

    bot.select_menu("GP Monitoring")


def _open_gmr391_frame(bot):
    """Navigate authenticated session: GP Monitoring -> GM-R 39 -> GM-R 39.1."""
    page = bot.page
    _assert_session_active(page)
    logger.info("[*] Navigating GP Monitoring -> GM-R 39 -> GM-R 39.1 inside shared session...")

    _click_gp_monitoring_top_menu(bot)
    time.sleep(2.0)

    iframe = None
    deadline = time.time() + 25.0
    while time.time() < deadline:
        iframe = _find_frame_with_gmr_menu(page)
        if iframe is not None:
            break
        # Fallback if a mock/test frame exposes generic links
        cand = _get_my_iframe(page)
        if cand is not None:
            try:
                if cand.locator("a").count() > 3:
                    iframe = cand
                    break
            except Exception:
                pass
        time.sleep(0.4)

    if not iframe:
        _assert_session_active(page)
        raise RuntimeError("Could not locate 'my-iframe' menu after selecting GP Monitoring for GM-R 39.1.")

    try:
        iframe.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    target_selectors = (
        "a:has-text('GM-R 39.1')",
        "a:has-text('39.1')",
        "xpath=//*[self::a or self::button or self::span or @onclick][contains(text(), '39.1')]",
    )

    def _find_391(scope):
        for sel in target_selectors:
            vis = _find_visible(scope, sel)
            if vis is not None:
                return vis
        return None

    link = _find_391(iframe)
    if link is None:
        try:
            enlarge = _find_visible(
                iframe,
                "text='Enlarge All', a:has-text('Enlarge All'), button:has-text('Enlarge All'), input[value*='Enlarge' i]",
            )
            if enlarge is not None:
                try:
                    enlarge.scroll_into_view_if_needed()
                except Exception:
                    pass
                enlarge.click()
                time.sleep(1.2)
                link = _find_391(iframe)
        except Exception:
            pass

    if link is None:
        # Valid Playwright leaf-text selectors only (avoid outer container wrappers & unsupported `text*=`)
        header_selectors = (
            "a:has-text('GM-R 39.')",
            "button:has-text('GM-R 39.')",
            "text=GM-R 39.",
            "xpath=//*[contains(text(), 'GM-R 39') and not(contains(text(), '39.1'))]",
            "xpath=//*[contains(text(), 'Inspection Data Entry Report') and not(contains(text(), '39.1'))]",
        )
        for hdr_sel in header_selectors:
            try:
                hdr = _find_visible(iframe, hdr_sel)
                if hdr is not None:
                    try:
                        hdr.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    hdr.click()
                    time.sleep(1.2)
                    link = _find_391(iframe)
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

    # Wait for Designation & Week <select> elements to render inside GM-R 39.1 frame
    ddl_deadline = time.time() + 25.0
    while time.time() < ddl_deadline:
        target_frame, _infos, desig_sel, week_sel = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
        if desig_sel is not None or week_sel is not None:
            time.sleep(0.4)
            return target_frame
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
        if not txt or "select" in txt.lower() or val in ("0", "-1"):
            continue
        if txt.casefold() == canon.casefold() or val.casefold() == canon.casefold():
            chosen_val = val
            break
    if chosen_val is None:
        for opt in desig_info.get("options", []):
            txt = opt.get("text", "").strip()
            val = opt.get("value", "").strip()
            if not txt or "select" in txt.lower() or val in ("0", "-1"):
                continue
            # Avoid matching 'CEO' against 'Deputy CEO'
            if canon == "CEO" and "deputy" in txt.lower():
                continue
            if canon.lower() in txt.lower():
                chosen_val = val
                break

    cur_selected = str(desig_info.get("selectedValue") or "").strip()
    if chosen_val is not None and cur_selected and cur_selected.casefold() == chosen_val.casefold():
        return

    if chosen_val is None:
        loc.select_option(label=canon)
    elif chosen_val == "":
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
        if not txt or "select" in txt.lower():
            continue
        looks_like_date = bool(
            re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", txt)
            or re.search(r"\d{2}[-/][A-Za-z0-9]{2,3}[-/]\d{4}", txt)
            or " to " in txt.lower()
        )
        if not looks_like_date and val in ("", "0", "-1"):
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


def group_available_weeks_by_month(available_weeks: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Group portal weekly items by calendar month using strict Monday-start week allocation."""
    by_ym: dict[tuple[int, int], list[dict[str, str]]] = {}
    for item in available_weeks or []:
        ym = assign_week_to_month(item.get("text") or item.get("value") or "")
        if ym is not None:
            by_ym.setdefault(ym, []).append(item)

    grouped: list[dict[str, Any]] = []
    for ym in sorted(by_ym.keys()):
        items = sorted(
            by_ym[ym],
            key=lambda w: (extract_week_dates(w.get("text") or "")[0] or 0, w.get("text") or ""),
        )
        grouped.append({
            "key": f"{ym[0]:04d}-{ym[1]:02d}",
            "label": format_month_key_label(ym),
            "year": ym[0],
            "month": ym[1],
            "week_count": len(items),
            "from_week": items[0]["text"],
            "to_week": items[-1]["text"],
            "weeks": items,
        })
    return grouped


def resolve_month_week_slice(
    available_weeks: list[dict[str, str]],
    from_month: str = "",
    to_month: str = "",
) -> list[dict[str, str]]:
    """Return all available weeks whose Monday falls within [from_month .. to_month] chronologically."""
    if not available_weeks:
        return []
    m1 = parse_month_key(from_month)
    m2 = parse_month_key(to_month or from_month)
    if m1 is None and m2 is None:
        return resolve_week_slice(available_weeks)
    if m1 is None:
        m1 = m2
    if m2 is None:
        m2 = m1
    lo_m, hi_m = min(m1, m2), max(m1, m2)  # type: ignore[type-var]

    matched: list[tuple[Any, dict[str, str]]] = []
    for item in available_weeks:
        txt = item.get("text") or item.get("value") or ""
        ym = assign_week_to_month(txt)
        if ym is not None and lo_m <= ym <= hi_m:
            s_dt, _ = extract_week_dates(txt)
            matched.append((s_dt, item))

    matched.sort(key=lambda pair: (pair[0] or 0, pair[1].get("text") or ""))
    return [pair[1] for pair in matched]


def fetch_inspection_metadata(bot, designation: str | None = None) -> dict[str, Any]:
    """Open GM-R 39.1 inside shared session and extract live Designations, Weeks & Monday-grouped Months."""
    page = bot.page

    def _on_dialog(dialog):
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", _on_dialog)
    try:
        iframe = _open_gmr391_frame(bot)
        iframe, infos, desig_info, week_info = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
        weeks = _clean_week_options(week_info)

        if (designation or not weeks) and desig_info is not None:
            _select_designation(iframe, desig_info, designation or "MPO")
            wait_end = time.time() + 8.0
            while time.time() < wait_end:
                iframe, infos, desig_info, week_info = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
                weeks = _clean_week_options(week_info)
                if weeks:
                    break
                time.sleep(0.4)

        portal_desigs = []
        if desig_info:
            for opt in desig_info.get("options", []):
                txt = str(opt.get("text", "")).strip()
                val = str(opt.get("value", "")).strip()
                if txt and val not in ("0", "-1") and "select" not in txt.lower():
                    portal_desigs.append({"value": val or txt, "text": txt})

        return {
            "designations": list(SUPPORTED_DESIGNATIONS),
            "portal_designations": portal_desigs,
            "weeks": weeks,
            "months": group_available_weeks_by_month(weeks),
            "selected_designation": get_designation_spec(designation or "MPO")["designation"],
        }
    finally:
        try:
            page.remove_listener("dialog", _on_dialog)
        except Exception:
            pass


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
    )
    for sel in excel_selectors:
        vis = _find_visible(iframe, sel)
        if vis is not None:
            return vis
    # Structural DOM match: clickable image/anchor immediately adjacent to Submit / CompleteReport
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
                for (let i = 0; i < btns.length; i++) {
                    const txt = ((btns[i].value || btns[i].innerText || btns[i].title || '') + '').trim().toLowerCase();
                    if (txt === 'submit' || txt.includes('submit')) {
                        for (let j = i + 1; j <= Math.min(btns.length - 1, i + 4); j++) {
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
    return _find_visible(iframe, "input[type='image']")


def _ensure_district_selected_if_needed(iframe, infos: list[dict[str, Any]]) -> None:
    """Log active selects and ensure District dropdown is not accidentally left at '--Select--' if valid options exist."""
    for info in infos:
        id_name = f"{info.get('id', '')} {info.get('name', '')}".lower()
        if "dist" in id_name and "week" not in id_name:
            cur_val = str(info.get("selectedValue") or "").strip()
            opts = info.get("options", [])
            if (not cur_val or cur_val in ("0", "-1")) and len(opts) > 1:
                for opt in opts:
                    ov = str(opt.get("value") or "").strip()
                    ot = str(opt.get("text") or "").strip()
                    if ov and ov not in ("0", "-1") and "select" not in ot.lower():
                        try:
                            _locator_for_select(iframe, info).select_option(value=ov)
                            time.sleep(0.8)
                        except Exception:
                            pass
                        break


def download_inspection_weeks(
    bot,
    designation: str,
    from_week: str,
    to_week: str,
    downloads_dir: Path,
    from_month: str = "",
    to_month: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Iterate selected weeks in GM-R 39.1, click Submit then Excel icon, and save weekly files."""
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
        iframe, infos, desig_info, week_info = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
        _ensure_district_selected_if_needed(iframe, infos)

        if desig_info is not None:
            logger.info("[*] Selecting Officer Designation = %s in GM-R 39.1...", canon_desig)
            _select_designation(iframe, desig_info, canon_desig)
            wait_end = time.time() + 8.0
            while time.time() < wait_end:
                iframe, infos, desig_info, week_info = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
                if _clean_week_options(week_info):
                    break
                time.sleep(0.4)

        available_weeks = _clean_week_options(week_info)
        if not available_weeks:
            raise FileNotFoundError(
                f"No weekly date ranges found in portal GM-R 39.1 for designation {canon_desig}."
            )

        if from_month.strip():
            selected_weeks = resolve_month_week_slice(available_weeks, from_month=from_month, to_month=to_month)
            if not selected_weeks:
                raise FileNotFoundError(
                    f"No portal weeks found whose Monday start date falls in '{from_month}'"
                    + (f" to '{to_month}'." if to_month and to_month != from_month else ".")
                )
        else:
            selected_weeks = resolve_week_slice(available_weeks, from_week=from_week, to_week=to_week)
        week_labels = [w["text"] for w in selected_weeks]
        logger.info("[*] GM-R 39.1 Selected Weeks (%d): %s", len(selected_weeks), week_labels)

        for idx, wk in enumerate(selected_weeks, start=1):
            portal_dialogs.clear()
            iframe, infos, _, cur_week_info = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
            if cur_week_info is None:
                raise RuntimeError(f"Week dropdown disappeared in GM-R 39.1 on week '{wk['text']}'.")

            logger.info("[*] [%d/%d] Selecting Week '%s' (value=%s)...", idx, len(selected_weeks), wk["text"], wk["value"])
            week_loc = _locator_for_select(iframe, cur_week_info)
            try:
                week_loc.select_option(value=wk["value"])
            except Exception:
                week_loc.select_option(label=wk["text"])
            time.sleep(1.0)

            iframe, _, _, _ = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)

            # Always click [Submit] FIRST so EPTS loads/binds the week's inspection dataset before exporting to Excel.
            try:
                submit_btn = _find_visible(
                    iframe,
                    "input[value*='Submit' i], button:has-text('Submit'), input[id*='Submit' i], input[id*='btnSubmit' i], input[id*='btnGet' i]",
                )
                if submit_btn is not None:
                    logger.info("[*] [%d/%d] Clicking Submit for week '%s'...", idx, len(selected_weeks), wk["text"])
                    submit_btn.click()
                    time.sleep(2.0)
            except Exception as exc:
                logger.info("Submit click notice on week %s: %s", wk["text"], exc)

            if any("no data" in m.lower() or "no record" in m.lower() for m in portal_dialogs):
                downloaded_items.append({
                    "week_label": wk["text"],
                    "filename": "",
                    "raw_bytes": b"",
                    "status": f"no_data ({'; '.join(portal_dialogs)})",
                })
                continue

            iframe, _, _, _ = _find_frame_with_gmr391_selects(page, fallback_frame=iframe)
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
                    "status": "no_data (excel icon not visible)" if not portal_dialogs else f"no_data ({'; '.join(portal_dialogs)})",
                })
                continue

            try:
                iframe.evaluate(
                    "() => { for (const f of document.forms) f.removeAttribute('target'); "
                    "for (const a of document.querySelectorAll('a[target]')) a.removeAttribute('target'); }"
                )
            except Exception:
                pass

            try:
                logger.info("[*] [%d/%d] Clicking Excel export icon for week '%s'...", idx, len(selected_weeks), wk["text"])
                with page.expect_download(timeout=20000) as dl_info:
                    excel_loc.click()
                dl = dl_info.value
                suggested = dl.suggested_filename or f"GMR39_1_{canon_desig}_week_{idx:02d}.xls"
                dest = insp_dir / f"w{idx:02d}_{suggested}"
                dl.save_as(str(dest))
                raw_bytes = dest.read_bytes()
                logger.info("[+] [%d/%d] Downloaded '%s' (%d bytes) for week '%s'", idx, len(selected_weeks), suggested, len(raw_bytes), wk["text"])
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
                        "status": f"no_data ({'; '.join(portal_dialogs)})",
                    })
                    continue
                raise RuntimeError(f"Failed downloading Excel for week '{wk['text']}': {exc}") from exc

        return downloaded_items, week_labels
    finally:
        try:
            page.remove_listener("dialog", _on_dialog)
        except Exception:
            pass

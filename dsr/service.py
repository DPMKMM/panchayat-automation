"""DSR & Consolidated Departmental Report Generation Service.

Report generation pipelines execute inside the caller's isolated Playwright session
owned by `core.session_manager`. All session lifecycle symbols are re-exported
from `core.session_manager` for full backward compatibility.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import (
    DOWNLOADS_DIR,
    PROFILES_DIR,
    REPORTS_DIR,
    SESSIONS_DIR,
    SESSION_DEFAULT_DURATION,
    SESSION_EXTENSION_DURATION,
    SESSION_MAX_DURATION,
    get_reports_dir,
)
from core.session_manager import (  # noqa: F401 - compatibility re-exports
    _DSR_CACHE,
    _DSR_CACHE_LOCK,
    _DSR_CACHE_TTL_SECONDS,
    _ActiveSessionProxy,
    _active_session,
    _background_keepalive_loop,
    _clear_session_state,
    _expire_session_impl,
    _extend_session_impl,
    _get_session_status_impl,
    _keepalive_ping,
    _load_session_state,
    _logout_server_session_impl,
    _sanitize_session_id,
    _save_session_state,
    _sessions,
    _sessions_lock,
    _start_server_login_impl,
    _verify_server_otp_impl,
    check_epts_reachability,
    determine_user_level,
    ensure_keepalive_running,
    extend_session,
    extract_epanchayat_header_info,
    get_all_active_sessions_summary,
    get_login_progress,
    get_or_create_session,
    get_session_status,
    is_authenticated,
    logout_server_session,
    run_in_bot_thread,
    run_in_session_thread,
    set_user_level_override,
    start_server_login,
    verify_server_otp,
)

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
PROFILES_BASE = PROFILES_DIR
SESSIONS_STATE_DIR = SESSIONS_DIR

logger = logging.getLogger("epts_automation_service")


def set_custom_user_level(
    level: str = "district",
    district: str = "Khammam",
    mandal: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    """Compatibility helper updating the target session's hierarchy level cleanly."""
    res = set_user_level_override(session_id=session_id, user_level=level, mandal_name=mandal)
    sess = get_or_create_session(session_id)
    if district:
        sess["district_name"] = district
    return res


def generate_server_report(
    module: str = "dsr_full",
    date_str: str = "",
    session_id: str = "",
    cutoff_time: str = "09:00",
    sort_by: str = "before_9",
    force_fresh: bool = False,
    include_pmagy: bool = False,
) -> dict[str, Any]:
    """Generate report for this specific user session in its isolated browser and directory."""
    session = get_or_create_session(session_id)
    with session["lock"]:
        return run_in_session_thread(
            session,
            _generate_server_report_impl,
            session,
            module,
            date_str,
            cutoff_time,
            sort_by,
            force_fresh,
            include_pmagy,
        )


def _generate_server_report_impl(
    session: dict[str, Any],
    module: str = "dsr_full",
    date_str: str = "",
    cutoff_time: str = "09:00",
    sort_by: str = "before_9",
    force_fresh: bool = False,
    include_pmagy: bool = False,
) -> dict[str, Any]:
    is_auth = session.get("status") == "authenticated"
    if not is_auth:
        raise PermissionError(
            "e-Panchayat session is not logged in. Please complete Login & OTP verification first before generating reports."
        )

    bot = session.get("bot")
    user_id = session.get("user_id") or "Officer"
    sid = session["session_id"]
    req_date = date_str.strip() if date_str else datetime.now().strftime("%Y-%m-%d")
    reports_dir = get_reports_dir()

    # Module: GP Balance Entry (GM-R 14.2)
    if module == "gp_balance":
        sys.path.insert(0, str((ROOT_DIR / "GPBALNCE").resolve()))
        try:
            from gp_balance import service as gp_balance_service
        except (ImportError, ModuleNotFoundError):
            import gp_balance_service
        report = gp_balance_service.generate_balance_report_pipeline(
            bot=bot,
            date_str=date_str,
            session_id=sid,
            include_pmagy=bool(include_pmagy),
        )
        pmagy_q = f"&include_pmagy={'1' if report.include_pmagy else '0'}"
        clean_date = report.report_date_str.replace("/", "-")
        user_level = session.get("user_level", "district")
        is_mandal_level = (user_level == "mandal") or bool(session.get("mandal_name"))
        target_mandal = (session.get("mandal_name") or "").strip()

        if is_mandal_level:
            if not target_mandal and report.mandals:
                target_mandal = report.mandals[0].mandal_name
            clean_mandal = (target_mandal or "Mandal").replace(" ", "_")
            pdf_path = reports_dir / f"{clean_mandal}_Mandal_GP_Balance_Report_{clean_date}.pdf"
            gp_balance_service.generate_mandal_balance_pdf_file(report, pdf_path, mandal_name=target_mandal)
            session["latest_pdf_path"] = str(pdf_path)
            session["latest_report_date"] = report.report_date_str
            m_obj = next((m for m in report.mandals if m.mandal_name.strip().casefold() == target_mandal.strip().casefold()), None)
            tot_gps = m_obj.total_gps if m_obj else 0
            ent_gps = m_obj.entered_gps if m_obj else 0
            pend_gps = m_obj.not_entered_gps if m_obj else 0
            pct_ent = m_obj.pct_entered if m_obj else 0.0
            return {
                "success": True,
                "module": "gp_balance",
                "is_mandal_level": True,
                "user_level": "mandal",
                "mandal_name": target_mandal,
                "district_name": report.district_name,
                "report_date": report.report_date_str,
                "totals": {
                    "total_mandals": 1,
                    "total_gps": tot_gps,
                    "total_entered_gps": ent_gps,
                    "total_not_entered_gps": pend_gps,
                    "overall_pct_entered": pct_ent,
                },
                "include_pmagy": bool(report.include_pmagy),
                "message": f"Gram Panchayat Balance Entry Report compiled successfully for {target_mandal} Mandal ({report.report_date_str})! {ent_gps}/{tot_gps} GPs completed ({pct_ent:.1f}%).",
                "pdf_url": f"/api/balance/report.pdf?date={clean_date}&mandal={target_mandal}{pmagy_q}",
                "excel_url": f"/api/balance/download-excel?date={clean_date}&mandal={target_mandal}{pmagy_q}",
            }
        else:
            safe_dist = (report.district_name or "Official").strip().replace(" ", "_")
            pdf_path = reports_dir / f"{safe_dist}_GP_Balance_Entry_Report_{clean_date}.pdf"
            session["latest_pdf_path"] = str(pdf_path)
            session["latest_report_date"] = report.report_date_str
            return {
                "success": True,
                "module": "gp_balance",
                "is_mandal_level": False,
                "user_level": user_level,
                "district_name": report.district_name,
                "report_date": report.report_date_str,
                "include_pmagy": bool(report.include_pmagy),
                "totals": {
                    "total_mandals": report.total_mandals,
                    "total_gps": report.total_gps,
                    "total_entered_gps": report.total_entered_gps,
                    "total_not_entered_gps": report.total_not_entered_gps,
                    "overall_pct_entered": report.overall_pct_entered,
                },
                "message": f"GP Balance Entry Report compiled successfully for {report.report_date_str}! {report.total_entered_gps}/{report.total_gps} GPs completed ({report.overall_pct_entered:.1f}%).",
                "pdf_url": f"/api/balance/report.pdf?date={clean_date}{pmagy_q}",
                "excel_url": f"/api/balance/download-excel?date={clean_date}{pmagy_q}",
            }

    # Module: DSR Attendance Report
    try:
        from dsr.auto_download import download_single_report_with_menu, format_portal_date
    except (ImportError, ModuleNotFoundError):
        from dsr_auto_download import download_single_report_with_menu, format_portal_date
    portal_date_fmt = format_portal_date(req_date)
    dl_dir = session["downloads_dir"]

    dist_name = session.get("district_name", "Khammam")
    user_level = session.get("user_level", "district")
    target_mandal_raw = (session.get("mandal_name") or "").strip()
    is_mandal_level = (user_level == "mandal") or bool(target_mandal_raw)
    target_mandal_norm = re.sub(r"[^a-zA-Z0-9]", "", target_mandal_raw).lower() if is_mandal_level else ""
    cache_level = "mandal" if is_mandal_level else user_level

    cache_key = (module, portal_date_fmt, dist_name, cutoff_time, sort_by, cache_level, target_mandal_norm)
    legacy_district_key = (module, portal_date_fmt, dist_name, cutoff_time, sort_by)

    with _DSR_CACHE_LOCK:
        cached_entry = _DSR_CACHE.get(cache_key)
        if not cached_entry and cache_level == "district" and not target_mandal_norm:
            cached_entry = _DSR_CACHE.get(legacy_district_key)
        if cached_entry:
            age = time.time() - cached_entry["timestamp"]
            if age < _DSR_CACHE_TTL_SECONDS and Path(cached_entry["latest_pdf_path"]).exists():
                logger.info(
                    "[%s] Serving cached DSR report (age: %.1fs < %.0fs TTL). Zero portal load.",
                    sid[:6], age, _DSR_CACHE_TTL_SECONDS,
                )
                session["latest_pdf_path"] = cached_entry["latest_pdf_path"]
                session["download_filename"] = cached_entry.get("download_filename", "")
                session["latest_report_date"] = cached_entry["latest_report_date"]
                session["report_data"] = cached_entry["report_data"]
                return cached_entry["response"]

    # Clean old downloads in this session's isolated folder
    if dl_dir.exists():
        for old_f in dl_dir.iterdir():
            if old_f.is_file():
                try:
                    old_f.unlink()
                except Exception:
                    pass

    downloaded_files: dict[str, Path] = {}

    if (bot is None or getattr(bot, "page", None) is None) and session.get("status") == "authenticated":
        try:
            try:
                from dsr.automation import EPTSAutomation
            except (ImportError, ModuleNotFoundError):
                from epts_automation import EPTSAutomation
            cand_bot = EPTSAutomation(headless=True, profile_dir=session["profile_dir"], downloads_dir=session["downloads_dir"])
            cand_bot.start_browser()
            if cand_bot.is_logged_in():
                bot = cand_bot
                session["bot"] = cand_bot
                session["mode"] = "live_portal"
                logger.info("Re-attached persistent browser automation session for Officer %s (%s)", user_id, sid)
        except Exception as e:
            logger.warning("Could not re-attach browser for session %s: %s", sid, e)

    if bot and bot.page and session.get("status") == "authenticated":
        try:
            logger.info("[%s] Step 1: Downloading GM-R 1.2.7 DSR Raw Data...", sid[:6])
            try:
                p1 = download_single_report_with_menu(bot, "1.2.7", portal_date_fmt)
                if p1 and p1.exists() and p1.stat().st_size > 0:
                    downloaded_files["raw_dsr"] = p1
            except Exception as e:
                logger.error("Download GM-R 1.2.7 error: %s", e)
                raise RuntimeError(f"Failed to download GM-R 1.2.7 DSR Raw Data from e-Panchayat: {e}")

            if module in ("dsr_full", "dsr_presentees"):
                logger.info("[%s] Step 2: Downloading GM-R 1.2.11 Presentees Report...", sid[:6])
                try:
                    p2 = download_single_report_with_menu(bot, "1.2.11", portal_date_fmt)
                    if p2 and p2.exists() and p2.stat().st_size > 0:
                        downloaded_files["presentees"] = p2
                except Exception as e:
                    logger.warning("Could not download GM-R 1.2.11: %s", e)

            if module in ("dsr_full", "dsr_absentees"):
                logger.info("[%s] Step 3: Downloading GM-R 1.2.10 Absentees Report...", sid[:6])
                try:
                    p3 = download_single_report_with_menu(bot, "1.2.10", portal_date_fmt)
                    if p3 and p3.exists() and p3.stat().st_size > 0:
                        downloaded_files["absentees"] = p3
                except Exception as e:
                    logger.warning("Could not download GM-R 1.2.10: %s", e)

        except Exception as exc:
            logger.error("[%s] Live download pipeline error: %s", sid[:6], exc)
            raise

    raw_path = downloaded_files.get("raw_dsr")
    if not raw_path or not raw_path.exists():
        recent_files = [f for f in dl_dir.iterdir() if f.is_file() and f.suffix.lower() in (".xls", ".xlsx", ".csv")]
        if recent_files:
            raw_path = recent_files[0]
        else:
            raise RuntimeError(
                f"No fresh DSR attendance report was downloaded from e-Panchayat portal for date '{portal_date_fmt}'. "
                "Please ensure your e-Panchayat session is logged in and active."
            )

    try:
        from dsr.pdf_generator import process_attendance_file, generate_pdf
    except (ImportError, ModuleNotFoundError):
        from report_generator import process_attendance_file, generate_pdf

    p_file = downloaded_files.get("presentees")
    presentees_data = (p_file.name, p_file.read_bytes()) if p_file and p_file.exists() and p_file.stat().st_size > 0 else None

    a_file = downloaded_files.get("absentees")
    absentees_data = (a_file.name, a_file.read_bytes()) if a_file and a_file.exists() and a_file.stat().st_size > 0 else None

    report = process_attendance_file(
        raw_path.name,
        raw_path.read_bytes(),
        presentees_source=presentees_data,
        absentees_source=absentees_data,
        cutoff_time=cutoff_time,
        sort_by=sort_by,
    )

    now = datetime.now()
    gen_time_label = now.strftime("%I:%M %p")
    gen_time_file = now.strftime("%I-%M-%p")

    report.generated_at = now
    report.generated_time_str = gen_time_label

    if is_mandal_level:
        target_mandal = target_mandal_raw
        if not target_mandal:
            if report.mandal_rows:
                target_mandal = report.mandal_rows[0].get("mandal", "")
            elif report.all_gp_rows:
                target_mandal = report.all_gp_rows[0].get("mandal", "")
            target_mandal = target_mandal or "Mandal"

        clean_mandal = target_mandal.replace(" ", "_")
        clean_download_name = f"{clean_mandal}_Mandal_GP_Attendance_and_DSR_Report_{portal_date_fmt}_{gen_time_file}.pdf"
        target_pdf = reports_dir / f"{clean_mandal}_Mandal_DSR_Report_{portal_date_fmt}_{gen_time_file}_{cutoff_time.replace(':', '-')}_{sort_by}.pdf"
        try:
            from dsr.pdf_generator import generate_mandal_pdf
        except (ImportError, ModuleNotFoundError):
            from report_generator import generate_mandal_pdf
        generate_mandal_pdf(report, target_pdf, mandal_name=target_mandal)

        mandal_gps = [
            r for r in (report.all_gp_rows or [])
            if r.get("mandal", "").strip().casefold() == target_mandal.strip().casefold()
        ]
        if not mandal_gps and report.all_gp_rows:
            mandal_gps = report.all_gp_rows

        tot_gps = len(mandal_gps)
        sub_cnt = sum(1 for g in mandal_gps if g.get("submitted"))
        b9_cnt = sum(1 for g in mandal_gps if g.get("before_9"))
        leave_cnt = sum(1 for g in mandal_gps if g.get("on_leave") or g.get("meeting_training"))
        pend_cnt = sum(1 for g in mandal_gps if g.get("is_pending"))
        dsr_cnt = sum(1 for g in mandal_gps if g.get("dsr_entered"))
        dsr_elig = sum(1 for g in mandal_gps if g.get("dsr_eligible"))
        pct = round((sub_cnt / tot_gps * 100), 1) if tot_gps > 0 else 0.0

        mandal_totals = {
            "unique_gps": tot_gps,
            "total_gps": tot_gps,
            "attendance_submitted": sub_cnt,
            "before_9": b9_cnt,
            "on_leave": leave_cnt,
            "pending": pend_cnt,
            "dsr_entered": dsr_cnt,
            "dsr_eligible": dsr_elig,
            "cutoff_label": report.cutoff_label,
            "sort_by": sort_by,
            "overall_attendance_pct": pct,
        }

        cached_pdf = dl_dir / clean_download_name
        try:
            cached_pdf.write_bytes(target_pdf.read_bytes())
        except Exception:
            pass

        session["latest_pdf_path"] = str(target_pdf)
        session["download_filename"] = clean_download_name
        session["latest_report_date"] = f"{report.report_date:%d-%b-%Y}"
        session["report_data"] = {
            "district_name": report.district_name,
            "mandal_name": target_mandal,
            "is_mandal_level": True,
            "user_level": "mandal",
            "report_date": f"{report.report_date:%d-%b-%Y}",
            "generated_time": gen_time_label,
            "generated_timestamp": gen_time_file,
            "download_filename": clean_download_name,
            "totals": mandal_totals,
            "gp_rows": mandal_gps,
            "mandal_rows": [],
            "generated": True,
        }

        res_payload = {
            "success": True,
            "step": "completed",
            "user_id": user_id,
            "user_level": "mandal",
            "is_mandal_level": True,
            "district_name": report.district_name,
            "mandal_name": target_mandal,
            "report_date": f"{report.report_date:%d-%b-%Y}",
            "generated_time": gen_time_label,
            "generated_timestamp": gen_time_file,
            "download_filename": clean_download_name,
            "message": f"Gram Panchayat Attendance & DSR Report for {target_mandal} Mandal ({portal_date_fmt}) prepared successfully at {gen_time_label}!",
            "pdf_url": "/api/naresh/view",
            "download_url": "/api/naresh/download",
            "totals": mandal_totals,
            "gp_rows": mandal_gps,
        }
    else:
        clean_dist = report.district_name.replace(" ", "_")
        clean_download_name = f"{clean_dist}_PS_Attendance_and_DSR_Report_{portal_date_fmt}_{gen_time_file}.pdf"
        target_pdf = reports_dir / f"{clean_dist}_DSR_Report_{portal_date_fmt}_{gen_time_file}_{cutoff_time.replace(':', '-')}_{sort_by}.pdf"
        generate_pdf(report, target_pdf)

        cached_pdf = dl_dir / clean_download_name
        try:
            cached_pdf.write_bytes(target_pdf.read_bytes())
        except Exception:
            pass

        session["latest_pdf_path"] = str(target_pdf)
        session["download_filename"] = clean_download_name
        session["latest_report_date"] = f"{report.report_date:%d-%b-%Y}"
        session["report_data"] = {
            "district_name": report.district_name,
            "is_mandal_level": False,
            "user_level": user_level,
            "report_date": f"{report.report_date:%d-%b-%Y}",
            "generated_time": gen_time_label,
            "generated_timestamp": gen_time_file,
            "download_filename": clean_download_name,
            "totals": report.totals,
            "mandal_rows": report.mandal_rows,
            "all_gp_rows": report.all_gp_rows,
            "generated": True,
        }

        res_payload = {
            "success": True,
            "step": "completed",
            "user_id": user_id,
            "user_level": user_level,
            "is_mandal_level": False,
            "district_name": report.district_name,
            "report_date": f"{report.report_date:%d-%b-%Y}",
            "generated_time": gen_time_label,
            "generated_timestamp": gen_time_file,
            "download_filename": clean_download_name,
            "message": f"Attendance & DSR Report for {report.district_name} ({portal_date_fmt}) prepared successfully at {gen_time_label}!",
            "pdf_url": "/api/naresh/view",
            "download_url": "/api/naresh/download",
            "totals": report.totals,
        }

    with _DSR_CACHE_LOCK:
        _DSR_CACHE[cache_key] = {
            "timestamp": time.time(),
            "latest_pdf_path": str(target_pdf),
            "download_filename": clean_download_name,
            "latest_report_date": f"{report.report_date:%d-%b-%Y}",
            "report_data": session["report_data"],
            "response": res_payload,
        }

    return res_payload

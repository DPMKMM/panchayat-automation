"""High-level service interface for GP Balance Entry Report Module."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

try:
    from gp_balance.models import DistrictBalanceReport
    from gp_balance.excel_generator import generate_balance_excel
    from gp_balance.pdf_generator import generate_balance_pdf
    from gp_balance.automation import fetch_available_thursday_dates, run_balance_automation
except (ImportError, ModuleNotFoundError):
    from gp_balance_models import DistrictBalanceReport
    from gp_balance_excel_generator import generate_balance_excel
    from gp_balance_pdf_generator import generate_balance_pdf
    from gp_balance_automation import fetch_available_thursday_dates, run_balance_automation

logger = logging.getLogger("gp_balance_service")

from core.config import get_reports_dir
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
REPORTS_DIR = get_reports_dir()

# Cache active reports in memory keyed by (session_id, date_str)
_session_reports: dict[tuple[str, str], DistrictBalanceReport] = {}


def reset_balance_data(session_id: str = "") -> None:
    """Wipes in-memory session cache without deleting persisted reports on disk."""
    global _session_reports
    clean_sid = (session_id or "").strip()
    if clean_sid:
        keys_to_del = [k for k in list(_session_reports.keys()) if k[0] == clean_sid]
        for k in keys_to_del:
            _session_reports.pop(k, None)
    else:
        _session_reports.clear()


def get_latest_balance_report(force_date: str = "", session_id: str = "") -> Optional[DistrictBalanceReport]:
    """Returns active report ONLY if explicitly generated via 'Run Balance Robot' during this server session."""
    global _session_reports
    clean_date = (force_date or "").strip()
    clean_sid = (session_id or "default").strip()

    if clean_date and (clean_sid, clean_date) in _session_reports:
        rep = _session_reports[(clean_sid, clean_date)]
        if not any(m.mandal_name.strip().upper() in ("TOTAL", "GRAND TOTAL") for m in rep.mandals):
            return rep

    session_reps = [
        r for k, r in _session_reports.items()
        if (isinstance(k, tuple) and len(k) == 2 and k[0] == clean_sid) or k == clean_sid
    ]
    if session_reps:
        return session_reps[-1]

    return None


def _resolve_report_view(report: DistrictBalanceReport, include_pmagy: Optional[bool] = None) -> DistrictBalanceReport:
    """Return a view of report matching requested include_pmagy without mutating the cached base report."""
    if include_pmagy is None or bool(include_pmagy) == bool(report.include_pmagy):
        return report
    view = report.clone_with_pmagy_option(bool(include_pmagy))
    if bool(include_pmagy):
        try:
            from gp_balance.automation import match_secretary_details, populate_pending_gps_from_directory
        except (ImportError, ModuleNotFoundError):
            from gp_balance_automation import match_secretary_details, populate_pending_gps_from_directory
        populate_pending_gps_from_directory(view.mandals, district_name=view.district_name, include_pmagy=True)
        match_secretary_details(view.mandals)
        view.compute_totals()
    return view


def generate_balance_report_pipeline(
    bot: Any = None,
    date_str: str = "",
    session_id: str = "",
    include_pmagy: bool = False,
) -> DistrictBalanceReport:
    """Executes live portal scrape when officer clicks 'Run Balance Robot'."""
    global _session_reports
    report: Optional[DistrictBalanceReport] = None
    clean_sid = (session_id or "default").strip()

    if bot and getattr(bot, "page", None):
        logger.info(
            "[%s] Executing live portal scraping for GP Balance on date: %s (include_pmagy=%s)",
            clean_sid[:6],
            date_str,
            include_pmagy,
        )
        report = run_balance_automation(bot, target_date=date_str, include_pmagy=bool(include_pmagy))
    else:
        try:
            from core.session_manager import ensure_active_bot, get_or_create_session
            sess = get_or_create_session(clean_sid)
            restored = ensure_active_bot(sess)
            if restored and getattr(restored, "page", None):
                report = run_balance_automation(restored, target_date=date_str, include_pmagy=bool(include_pmagy))
        except Exception:
            restored = None
        if report is None:
            raise PermissionError("e-Panchayat browser session is not active. Please log in with your credentials and OTP first.")

    # Cache report specifically under the requested date and session
    target_key = (date_str or report.report_date_str).strip()
    _session_reports[(clean_sid, target_key)] = report
    _session_reports[(clean_sid, report.report_date_str.strip())] = report

    # Export fresh Excel and PDF files to reports folder
    clean_date = report.report_date_str.replace("/", "-")
    safe_dist = get_balance_filename_prefix(report)
    excel_path = REPORTS_DIR / f"{safe_dist}_GP_Balance_Report_{clean_date}_{clean_sid[:6]}.xlsx"
    pdf_path = REPORTS_DIR / f"{safe_dist}_GP_Balance_Report_{clean_date}_{clean_sid[:6]}.pdf"

    generate_balance_excel(report, output_path=excel_path)
    generate_balance_pdf(report, target=pdf_path)

    # Save to local module data dir
    local_data = BASE_DIR / "data"
    local_data.mkdir(parents=True, exist_ok=True)
    try:
        generate_balance_excel(report, output_path=local_data / f"{safe_dist}_GP_Balance_{clean_date}.xlsx")
        generate_balance_pdf(report, target=local_data / f"{safe_dist}_GP_Balance_{clean_date}.pdf")
    except Exception:
        pass

    return report


def get_balance_filename_prefix(report: DistrictBalanceReport) -> str:
    clean_dist = (report.district_name or "").strip().title().replace(" ", "_")
    if clean_dist.endswith("_District"):
        clean_dist = clean_dist[:-9].strip()
    if not clean_dist or clean_dist.lower() == "district":
        return "District"
    return clean_dist


def _format_balance_download_ts(report: DistrictBalanceReport) -> str:
    from datetime import datetime
    raw_gen = getattr(report, "generated_at", "")
    if raw_gen:
        for fmt in (
            "%d-%b-%Y %I:%M %p",
            "%d-%B-%Y %I:%M %p",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d-%m-%Y %H:%M",
            "%Y-%m-%d %H:%M",
        ):
            try:
                return datetime.strptime(raw_gen.strip(), fmt).strftime("%d-%m-%Y %I:%M %p")
            except Exception:
                pass
    return datetime.now().strftime("%d-%m-%Y %I:%M %p")


def get_balance_excel_bytes(date_str: str = "", session_id: str = "", include_pmagy: Optional[bool] = None) -> tuple[str, bytes]:
    report = get_latest_balance_report(force_date=date_str, session_id=session_id)
    if report is not None:
        view = _resolve_report_view(report, include_pmagy)
        ts_download = _format_balance_download_ts(view)
        safe_dist = get_balance_filename_prefix(view)
        filename = f"{safe_dist}_GP_Balance_Report_{ts_download}.xlsx"
        data = generate_balance_excel(view)
        return filename, data

    # Disk Fallback: Check if file was already generated and saved in REPORTS_DIR
    reports_dir = get_reports_dir()
    clean_date = (date_str or "").strip().replace("/", "-")
    short_sid = (session_id[:6] if len(session_id) >= 6 else session_id) if session_id and session_id != "default" else ""
    patterns = []
    if clean_date and short_sid:
        patterns.append(f"*GP_Balance_Report_{clean_date}_{short_sid}.xlsx")
    if short_sid:
        patterns.append(f"*GP_Balance_Report*_{short_sid}.xlsx")

    for pat in patterns:
        matches = sorted(reports_dir.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError(f"No balance report generated yet for date {date_str or 'selected'}. Please click 'Run Balance Robot' first.")


def generate_mandal_balance_pdf_file(report: DistrictBalanceReport, output_path: Union[str, Path], mandal_name: str) -> Path:
    from gp_balance.pdf_generator import generate_mandal_balance_pdf
    pdf_bytes = generate_mandal_balance_pdf(report, mandal_name=mandal_name)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf_bytes)
    return out


def get_balance_pdf_bytes(date_str: str = "", session_id: str = "", mandal: str = "", include_pmagy: Optional[bool] = None) -> tuple[str, bytes]:
    report = get_latest_balance_report(force_date=date_str, session_id=session_id)

    # Check session user level and mandal
    mandal_name = (mandal or "").strip()
    try:
        from dsr.service import get_or_create_session
        sess = get_or_create_session(session_id)
        if not mandal_name and sess.get("user_level") == "mandal" and sess.get("mandal_name"):
            mandal_name = sess.get("mandal_name", "").strip()
    except Exception:
        pass

    if report is not None:
        view = _resolve_report_view(report, include_pmagy)
        ts_download = _format_balance_download_ts(view)
        if mandal_name:
            clean_mandal = mandal_name.replace(" ", "_")
            filename = f"{clean_mandal}_Mandal_GP_Balance_Report_{ts_download}.pdf"
            data = generate_balance_pdf(view, mandal_name=mandal_name)
            return filename, data
        else:
            safe_dist = get_balance_filename_prefix(view)
            filename = f"{safe_dist}_GP_Balance_Report_{ts_download}.pdf"
            data = generate_balance_pdf(view)
            return filename, data

    # Disk Fallback: Check if file was already generated and saved in REPORTS_DIR
    reports_dir = get_reports_dir()
    clean_date = (date_str or "").strip().replace("/", "-")
    short_sid = (session_id[:6] if len(session_id) >= 6 else session_id) if session_id and session_id != "default" else ""
    patterns = []
    if clean_date and short_sid:
        patterns.append(f"*GP_Balance_Report_{clean_date}_{short_sid}.pdf")
    if short_sid:
        patterns.append(f"*GP_Balance_Report*_{short_sid}.pdf")

    for pat in patterns:
        matches = sorted(reports_dir.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError(f"No balance report generated yet for date {date_str or 'selected'}. Please click 'Run Balance Robot' first.")


def get_balance_data_dict(date_str: str = "", session_id: str = "", mandal: str = "", include_pmagy: Optional[bool] = None) -> dict[str, Any]:
    base_report = get_latest_balance_report(force_date=date_str, session_id=session_id)
    if base_report is None:
        return {
            "success": True,
            "has_data": False,
            "include_pmagy": bool(include_pmagy) if include_pmagy is not None else False,
            "message": "No balance report generated yet for this session. Please select Thursday date and click 'Run Balance Robot'."
        }
    report = _resolve_report_view(base_report, include_pmagy)

    # Determine user level and mandal
    mandal_name = (mandal or "").strip()
    user_level = "district"
    try:
        from dsr.service import get_or_create_session
        sess = get_or_create_session(session_id)
        user_level = sess.get("user_level", "district")
        if not mandal_name and user_level == "mandal" and sess.get("mandal_name"):
            mandal_name = sess.get("mandal_name", "").strip()
    except Exception:
        pass

    is_mandal_level = (user_level == "mandal") or bool(mandal_name)
    if is_mandal_level:
        target_m = None
        if mandal_name:
            for m in report.mandals:
                if m.mandal_name.strip().casefold() == mandal_name.strip().casefold():
                    target_m = m
                    break
        if not target_m and report.mandals:
            target_m = report.mandals[0]
            mandal_name = target_m.mandal_name

        m_gps_data = []
        gps_source = target_m.all_gps if target_m and target_m.all_gps else (target_m.pending_gps if target_m else [])
        for idx, gp in enumerate(gps_source, start=1):
            m_gps_data.append({
                "s_no": idx,
                "mandal_name": gp.mandal_name,
                "panchayat_name": gp.panchayat_name,
                "entered": gp.entered,
                "is_pending": gp.is_pending,
                "gp_pd": gp.gp_pd,
                "tgbpass": gp.tgbpass,
                "fc15_tied": gp.fc15_tied,
                "fc15_untied": gp.fc15_untied,
                "pmagy": gp.pmagy,
                "vwsc": gp.vwsc,
                "mgnregs": gp.mgnregs,
                "missing_accounts": gp.missing_accounts,
                "secretary_name": gp.secretary_name,
                "secretary_phone": gp.secretary_phone,
            })

        m_pending_data = []
        if target_m:
            for idx, gp in enumerate(target_m.pending_gps, start=1):
                m_pending_data.append({
                    "s_no": idx,
                    "mandal_name": gp.mandal_name,
                    "panchayat_name": gp.panchayat_name,
                    "missing_accounts": gp.missing_accounts,
                    "secretary_name": gp.secretary_name,
                    "secretary_phone": gp.secretary_phone,
                })

        return {
            "success": True,
            "has_data": True,
            "is_mandal_level": True,
            "user_level": "mandal",
            "mandal_name": mandal_name,
            "district_name": report.district_name,
            "report_date_str": report.report_date_str,
            "generated_at": report.generated_at,
            "include_pmagy": bool(report.include_pmagy),
            "scraped_with_pmagy": bool(base_report.include_pmagy),
            "totals": {
                "total_mandals": 1,
                "total_gps": target_m.total_gps if target_m else 0,
                "total_entered_gps": target_m.entered_gps if target_m else 0,
                "total_not_entered_gps": target_m.not_entered_gps if target_m else 0,
                "overall_pct_entered": target_m.pct_entered if target_m else 0.0,
                "total_gp_pd_pending": target_m.gp_pd_pending if target_m else 0,
                "total_tgbpass_pending": target_m.tgbpass_pending if target_m else 0,
                "total_fc15_tied_pending": target_m.fc15_tied_pending if target_m else 0,
                "total_fc15_untied_pending": target_m.fc15_untied_pending if target_m else 0,
                "total_pmagy_pending": target_m.pmagy_pending if (target_m and report.include_pmagy) else 0,
                "total_vwsc_pending": target_m.vwsc_pending if target_m else 0,
                "total_mgnregs_pending": target_m.mgnregs_pending if target_m else 0,
            },
            "mandals": [],  # Multi-mandal comparison table suppressed for mandal-level officers
            "gp_rows": m_gps_data,
            "pending_gps": m_pending_data,
        }

    mandals_data = []
    for m in report.mandals:
        mandals_data.append({
            "s_no": m.s_no,
            "mandal_name": m.mandal_name,
            "total_gps": m.total_gps,
            "entered_gps": m.entered_gps,
            "not_entered_gps": m.not_entered_gps,
            "pct_entered": m.pct_entered,
            "gp_pd_updated": m.gp_pd_updated,
            "gp_pd_pending": m.gp_pd_pending,
            "tgbpass_updated": m.tgbpass_updated,
            "tgbpass_pending": m.tgbpass_pending,
            "fc15_tied_updated": m.fc15_tied_updated,
            "fc15_tied_pending": m.fc15_tied_pending,
            "fc15_untied_updated": m.fc15_untied_updated,
            "fc15_untied_pending": m.fc15_untied_pending,
            "pmagy_updated": m.pmagy_updated,
            "pmagy_pending": m.pmagy_pending,
            "vwsc_updated": m.vwsc_updated,
            "vwsc_pending": m.vwsc_pending,
            "mgnregs_updated": m.mgnregs_updated,
            "mgnregs_pending": m.mgnregs_pending,
            "has_pending": m.has_pending,
            "pending_count": len(m.pending_gps),
        })

    pending_gps_data = []
    for gp in report.pending_gps_all:
        pending_gps_data.append({
            "s_no": gp.s_no,
            "mandal_name": gp.mandal_name,
            "panchayat_name": gp.panchayat_name,
            "missing_accounts": gp.missing_accounts,
            "secretary_name": gp.secretary_name,
            "secretary_phone": gp.secretary_phone,
        })

    return {
        "success": True,
        "has_data": True,
        "district_name": report.district_name,
        "report_date_str": report.report_date_str,
        "generated_at": report.generated_at,
        "include_pmagy": bool(report.include_pmagy),
        "scraped_with_pmagy": bool(base_report.include_pmagy),
        "totals": {
            "total_mandals": report.total_mandals,
            "total_gps": report.total_gps,
            "total_entered_gps": report.total_entered_gps,
            "total_not_entered_gps": report.total_not_entered_gps,
            "overall_pct_entered": report.overall_pct_entered,
            "total_gp_pd_pending": report.total_gp_pd_pending,
            "total_tgbpass_pending": report.total_tgbpass_pending,
            "total_fc15_tied_pending": report.total_fc15_tied_pending,
            "total_fc15_untied_pending": report.total_fc15_untied_pending,
            "total_pmagy_pending": report.total_pmagy_pending if report.include_pmagy else 0,
            "total_vwsc_pending": report.total_vwsc_pending,
            "total_mgnregs_pending": report.total_mgnregs_pending,
        },
        "mandals": mandals_data,
        "pending_gps": pending_gps_data,
    }


_session_portal_dates: dict[str, list[str]] = {}


def get_portal_dates(bot: Any = None, session_id: str = "") -> dict[str, Any]:
    """Return available Thursday dates scraped from e-Panchayat portal for this session,
    or dynamically computed Thursdays up to today."""
    from datetime import datetime, timedelta
    clean_sid = (session_id or "default").strip()

    # 1. If bot is provided and active, scrape dates directly from portal
    if bot and getattr(bot, "page", None):
        try:
            live_dates = fetch_available_thursday_dates(bot)
            if live_dates:
                _session_portal_dates[clean_sid] = live_dates
                return {
                    "success": True,
                    "is_live": True,
                    "dates": live_dates,
                    "message": f"Successfully retrieved {len(live_dates)} dates live from e-Panchayat portal."
                }
        except Exception as exc:
            logger.warning("Live portal dates fetch error: %s", exc)

    cached_for_sid = _session_portal_dates.get(clean_sid)
    if cached_for_sid:
        return {
            "success": True,
            "is_live": True,
            "dates": cached_for_sid,
            "message": f"Retrieved {len(cached_for_sid)} dates from active session cache."
        }

    # 2. Dynamic Thursday dates (past 12 Thursdays from today)
    today = datetime.now()
    days_back = (today.weekday() - 3) % 7
    latest_thursday = today - timedelta(days=days_back)
    computed_dates = []
    for i in range(12):
        t_date = latest_thursday - timedelta(weeks=i)
        computed_dates.append(t_date.strftime("%d-%m-%Y"))

    return {
        "success": True,
        "is_live": False,
        "dates": computed_dates,
        "message": "Dynamic Thursday dates (Login to e-Panchayat to sync live portal dates)."
    }

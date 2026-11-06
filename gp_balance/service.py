"""High-level service interface for GP Balance Entry Report Module."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
REPORTS_DIR = ROOT_DIR / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

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

    session_reps = [r for (s, d), r in _session_reports.items() if s == clean_sid]
    if session_reps:
        return session_reps[-1]

    if clean_sid != "default":
        default_reps = [r for (s, d), r in _session_reports.items() if s == "default"]
        if default_reps:
            return default_reps[-1]

    return None


def generate_balance_report_pipeline(bot: Any = None, date_str: str = "", session_id: str = "") -> DistrictBalanceReport:
    """Executes live portal scrape when officer clicks 'Run Balance Robot'."""
    global _session_reports
    report: Optional[DistrictBalanceReport] = None
    clean_sid = (session_id or "default").strip()

    if bot and getattr(bot, "page", None):
        logger.info("[%s] Executing live portal scraping for GP Balance on date: %s", clean_sid[:6], date_str)
        report = run_balance_automation(bot, target_date=date_str)
    else:
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


def get_balance_excel_bytes(date_str: str = "", session_id: str = "") -> tuple[str, bytes]:
    report = get_latest_balance_report(force_date=date_str, session_id=session_id)
    if report is not None:
        clean_date = report.report_date_str.replace("/", "-")
        safe_dist = get_balance_filename_prefix(report)
        filename = f"{safe_dist}_GP_Balance_Report_{clean_date}.xlsx"
        data = generate_balance_excel(report)
        return filename, data

    # Disk Fallback: Check if file was already generated and saved in REPORTS_DIR
    clean_date = (date_str or "").strip().replace("/", "-")
    short_sid = (session_id[:6] if len(session_id) >= 6 else session_id) if session_id and session_id != "default" else ""
    patterns = []
    if clean_date and short_sid:
        patterns.append(f"*GP_Balance_Report_{clean_date}_{short_sid}.xlsx")
    if clean_date:
        patterns.append(f"*GP_Balance_Report_{clean_date}*.xlsx")
    if short_sid:
        patterns.append(f"*GP_Balance_Report*_{short_sid}.xlsx")
    patterns.append("*GP_Balance_Report*.xlsx")

    for pat in patterns:
        matches = sorted(REPORTS_DIR.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError(f"No balance report generated yet for date {date_str or 'selected'}. Please click 'Run Balance Robot' first.")


def get_balance_pdf_bytes(date_str: str = "", session_id: str = "") -> tuple[str, bytes]:
    report = get_latest_balance_report(force_date=date_str, session_id=session_id)
    if report is not None:
        clean_date = report.report_date_str.replace("/", "-")
        safe_dist = get_balance_filename_prefix(report)
        filename = f"{safe_dist}_GP_Balance_Report_{clean_date}.pdf"
        data = generate_balance_pdf(report)
        return filename, data

    # Disk Fallback: Check if file was already generated and saved in REPORTS_DIR
    clean_date = (date_str or "").strip().replace("/", "-")
    short_sid = (session_id[:6] if len(session_id) >= 6 else session_id) if session_id and session_id != "default" else ""
    patterns = []
    if clean_date and short_sid:
        patterns.append(f"*GP_Balance_Report_{clean_date}_{short_sid}.pdf")
    if clean_date:
        patterns.append(f"*GP_Balance_Report_{clean_date}*.pdf")
    if short_sid:
        patterns.append(f"*GP_Balance_Report*_{short_sid}.pdf")
    patterns.append("*GP_Balance_Report*.pdf")

    for pat in patterns:
        matches = sorted(REPORTS_DIR.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError(f"No balance report generated yet for date {date_str or 'selected'}. Please click 'Run Balance Robot' first.")


def get_balance_data_dict(date_str: str = "", session_id: str = "") -> dict[str, Any]:
    report = get_latest_balance_report(force_date=date_str, session_id=session_id)
    if report is None:
        return {
            "success": True,
            "has_data": False,
            "message": "No balance report generated yet for this session. Please select Thursday date and click 'Run Balance Robot'."
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
            "total_vwsc_pending": report.total_vwsc_pending,
            "total_mgnregs_pending": report.total_mgnregs_pending,
        },
        "mandals": mandals_data,
        "pending_gps": pending_gps_data,
    }


_cached_portal_dates: list[str] = []


def get_portal_dates(bot: Any = None) -> dict[str, Any]:
    """Returns available Thursday dates scraped from epanchayat portal if logged in,
    or dynamically computed Thursdays up to today."""
    global _cached_portal_dates
    from datetime import datetime, timedelta

    # 1. If bot is provided and active, scrape dates directly from portal
    if bot and getattr(bot, "page", None):
        try:
            live_dates = fetch_available_thursday_dates(bot)
            if live_dates:
                _cached_portal_dates = live_dates
                return {
                    "success": True,
                    "is_live": True,
                    "dates": live_dates,
                    "message": f"Successfully retrieved {len(live_dates)} dates live from e-Panchayat portal."
                }
        except Exception as exc:
            logger.warning("Live portal dates fetch error: %s", exc)

    if _cached_portal_dates:
        return {
            "success": True,
            "is_live": True,
            "dates": _cached_portal_dates,
            "message": f"Retrieved {len(_cached_portal_dates)} dates from active session cache."
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

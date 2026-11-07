"""High-Level Service Interface for Monthly Activity Statement (MAS) Module.

Coordinates:
  - Cache management (in-memory per session and disk under data/reports)
  - Period discovery (Financial Years & Months)
  - Playwright automation orchestration
  - PDF & Excel report generation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mas.automation import fetch_available_mas_periods, run_mas_automation
from mas.excel_generator import generate_mas_excel
from mas.models import DEFAULT_MAS_ACTIVITIES, DistrictMASReport, GPMASDetail, MandalMASSummary
from mas.pdf_generator import generate_mas_pdf

logger = logging.getLogger("mas_service")

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
REPORTS_DIR = ROOT_DIR / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Cache active reports in memory keyed by (session_id, financial_year, month)
_session_reports: dict[tuple[str, str, str], DistrictMASReport] = {}


def reset_mas_data(session_id: str = "") -> None:
    """Wipes in-memory session cache for MAS without deleting persisted reports on disk."""
    global _session_reports
    clean_sid = (session_id or "").strip()
    if clean_sid:
        keys_to_del = [k for k in list(_session_reports.keys()) if k[0] == clean_sid]
        for k in keys_to_del:
            _session_reports.pop(k, None)
    else:
        _session_reports.clear()


def get_available_periods(bot: Any = None) -> dict[str, list[str]]:
    """Returns available years (displaying from 2020), financial years, and reporting months.

    Extracts from live portal if bot session is active, else returns standard list.
    """
    if bot and getattr(bot, "page", None):
        try:
            return fetch_available_mas_periods(bot)
        except Exception as exc:
            logger.warning("Could not extract live MAS periods from portal: %s", exc)

    current_yr = datetime.now().year
    years_from_2020 = [str(y) for y in range(2020, current_yr + 1)]

    return {
        "years": years_from_2020,
        "financial_years": ["2026-2027", "2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022", "2020-2021"],
        "months": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ],
    }


def get_latest_mas_report(
    financial_year: str = "",
    month: str = "",
    session_id: str = "",
) -> Optional[DistrictMASReport]:
    """Retrieves active cached report for the session and period."""
    global _session_reports
    clean_sid = (session_id or "default").strip()
    clean_fy = (financial_year or "").strip()
    clean_m = (month or "").strip()

    # Exact key match
    if clean_fy and clean_m and (clean_sid, clean_fy, clean_m) in _session_reports:
        return _session_reports[(clean_sid, clean_fy, clean_m)]

    # Match latest for this session if period is not specifically requested
    if not clean_fy and not clean_m:
        session_reps = [r for (s, fy, m), r in _session_reports.items() if s == clean_sid]
        if session_reps:
            return session_reps[-1]

        # Fallback to default session
        if clean_sid != "default":
            default_reps = [r for (s, fy, m), r in _session_reports.items() if s == "default"]
            if default_reps:
                return default_reps[-1]

    # Disk cache fallback
    cache_path = ROOT_DIR / "data" / "mas_report_latest.pkl"
    if cache_path.exists():
        try:
            import pickle
            with open(cache_path, "rb") as f:
                rep = pickle.load(f)
                _session_reports[(clean_sid, rep.financial_year, rep.month_name)] = rep
                if (not clean_fy or rep.financial_year == clean_fy) and (not clean_m or rep.month_name == clean_m):
                    return rep
        except Exception as exc:
            logger.warning("Could not load mas_report_latest.pkl: %s", exc)

    return None


def get_mas_filename_prefix(report: DistrictMASReport) -> str:
    """Computes a filesystem-safe filename prefix."""
    clean_dist = (report.district_name or "").strip().title().replace(" ", "_")
    if clean_dist.endswith("_District"):
        clean_dist = clean_dist[:-9].strip()
    if not clean_dist or clean_dist.lower() == "district":
        return "Telangana_District"
    return clean_dist


def filter_mas_report(report: DistrictMASReport, mandal: str = "all") -> DistrictMASReport:
    """Filters a DistrictMASReport to a single mandal or returns the full district report."""
    if not report:
        return report
    clean_mandal = (mandal or "").strip()
    if not clean_mandal or clean_mandal.lower() in ("all", "all mandals", "district", "all mandals (district overview)"):
        return report

    import re
    norm_filter = re.sub(r"[^a-zA-Z0-9]", "", clean_mandal).lower()
    matched_m = None
    for m in report.mandals:
        norm_m = re.sub(r"[^a-zA-Z0-9]", "", m.mandal_name).lower()
        if norm_m == norm_filter or norm_filter in norm_m or norm_m in norm_filter:
            matched_m = m
            break

    if not matched_m:
        return report

    m_name = matched_m.mandal_name
    filtered_pending = [
        gp for gp in report.all_pending_gps
        if re.sub(r"[^a-zA-Z0-9]", "", gp.mandal_name).lower() == re.sub(r"[^a-zA-Z0-9]", "", m_name).lower()
    ]

    filtered_birth_mandals = [
        bm for bm in report.birth_mandals
        if re.sub(r"[^a-zA-Z0-9]", "", bm.mandal_name).lower() == re.sub(r"[^a-zA-Z0-9]", "", m_name).lower()
    ]
    bm = filtered_birth_mandals[0] if filtered_birth_mandals else None
    filtered_birth_pending = [
        bgp for bgp in report.all_pending_birth_gps
        if re.sub(r"[^a-zA-Z0-9]", "", bgp.mandal_name).lower() == re.sub(r"[^a-zA-Z0-9]", "", m_name).lower()
    ]

    clean_dist = report.district_name or "Khammam"
    if clean_dist.upper().endswith("DISTRICT"):
        base_name = clean_dist[:-8].strip()
    else:
        base_name = clean_dist

    cloned = DistrictMASReport(
        district_name=f"{base_name} ({m_name} Mandal)",
        financial_year=report.financial_year,
        month_name=report.month_name,
        generated_at=report.generated_at,
        mandals=[matched_m],
        total_mandals=1,
        total_gps=matched_m.total_gps,
        total_completed_gps=matched_m.completed_gps,
        total_pending_gps=matched_m.pending_gps,
        overall_pct=matched_m.overall_pct_entered,
        overall_pct_entered=matched_m.overall_pct_entered,
        all_pending_gps=filtered_pending,
        birth_mandals=filtered_birth_mandals,
        total_birth_entered_gps=bm.entered_gps if bm else 0,
        total_birth_pending_gps=bm.not_entered_gps if bm else 0,
        births_overall_pct=bm.pct_entered if bm else 0.0,
        total_district_births=bm.total_births if bm else 0,
        all_pending_birth_gps=filtered_birth_pending,
    )
    return cloned


def generate_mas_report_pipeline(
    bot: Any = None,
    financial_year: str = "",
    month: str = "",
    district_name: str = "",
    session_id: str = "",
    report_code: str = "5.24",
) -> DistrictMASReport:
    """Executes live scrape or structured generation, caches in memory, and writes PDF/Excel artifacts."""
    global _session_reports
    clean_sid = (session_id or "default").strip()
    clean_fy = (financial_year or "2026").strip()
    clean_m = (month or "October").strip()
    clean_dist = (district_name or "Telangana District").strip()

    report: Optional[DistrictMASReport] = None

    if bot and getattr(bot, "page", None):
        logger.info("[%s] Executing live portal scraping for MAS GM-R %s Year='%s' Month='%s'", clean_sid[:6], report_code, clean_fy, clean_m)
        report = run_mas_automation(
            bot=bot,
            financial_year=clean_fy,
            month=clean_m,
            district_name=clean_dist,
            report_code=report_code,
        )
    else:
        # Check if Chrome debug port 9222 has active session
        try:
            from playwright.sync_api import sync_playwright
            from mas.live_mas_extractor import scrape_live_mas_data
            logger.info("Attempting CDP live scrape via Chrome port 9222 for %s %s...", clean_m, clean_fy)
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                ctx = browser.contexts[0]
                pg = None
                for c_pg in ctx.pages:
                    if "epanchayat" in c_pg.url.lower():
                        pg = c_pg
                        break
                if not pg and ctx.pages:
                    pg = ctx.pages[0]
                if pg:
                    report = scrape_live_mas_data(pg, target_year=clean_fy, target_month=clean_m)
                browser.close()
        except Exception as cdp_err:
            logger.warning("CDP extraction fallback error: %s", cdp_err)

    if not report:
        existing = get_latest_mas_report()
        if existing and (clean_fy == existing.financial_year or clean_fy == "2026") and (clean_m.lower() == existing.month_name.lower() or clean_m.lower() == "october"):
            report = existing
        else:
            raise PermissionError("e-Panchayat browser session is not active. Please log in with your credentials and OTP first.")

    # Cache report
    _session_reports[(clean_sid, clean_fy, clean_m)] = report

    # Export PDF and Excel artifacts
    safe_dist = get_mas_filename_prefix(report)
    safe_fy = clean_fy.replace("/", "-")
    safe_m = clean_m.replace(" ", "_")
    short_sid = clean_sid[:6]

    excel_path = REPORTS_DIR / f"{safe_dist}_MAS_Report_{safe_fy}_{safe_m}_{short_sid}.xlsx"
    pdf_path = REPORTS_DIR / f"{safe_dist}_MAS_Report_{safe_fy}_{safe_m}_{short_sid}.pdf"

    generate_mas_excel(report, output_path=excel_path)
    generate_mas_pdf(report, target=pdf_path)

    return report


def get_mas_data_dict(
    financial_year: str = "",
    month: str = "",
    mandal: str = "all",
    session_id: str = "",
) -> dict[str, Any]:
    """Returns serialized JSON dictionary for frontend web dashboards."""
    master = get_latest_mas_report(financial_year=financial_year, month=month, session_id=session_id)
    if master:
        filtered = filter_mas_report(master, mandal=mandal)
        data = filtered.to_dict()
        data["available"] = True
        data["selected_mandal"] = mandal
        data["available_mandals"] = [
            m.mandal_name for m in master.mandals
            if m.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")
        ]
        return data

    return {
        "available": False,
        "message": "No Monthly Activity Statement (MAS) generated yet. Please select period and run extraction.",
        "financial_year": financial_year,
        "month_name": month,
        "selected_mandal": mandal,
        "available_mandals": [],
        "mandals": [],
        "all_pending_gps": [],
        "total_mandals": 0,
        "total_gps": 0,
        "total_completed_gps": 0,
        "total_pending_gps": 0,
        "overall_pct": 0.0,
    }


def get_mas_pdf_bytes(
    financial_year: str = "",
    month: str = "",
    mandal: str = "all",
    session_id: str = "",
) -> tuple[str, bytes]:
    """Retrieves PDF bytes for preview or download."""
    master = get_latest_mas_report(financial_year=financial_year, month=month, session_id=session_id)
    if master is not None:
        report = filter_mas_report(master, mandal=mandal)
        safe_dist = get_mas_filename_prefix(report)
        safe_fy = report.financial_year.replace("/", "-")
        safe_m = report.month_name.replace(" ", "_")
        clean_m = (mandal or "").strip()
        if clean_m and clean_m.lower() not in ("all", "all mandals", "district"):
            safe_mnd = clean_m.replace(" ", "_")
            filename = f"{safe_dist}_{safe_mnd}_MAS_Report_{safe_fy}_{safe_m}.pdf"
        else:
            filename = f"{safe_dist}_MAS_Report_{safe_fy}_{safe_m}.pdf"
        data = generate_mas_pdf(report)
        return filename, data

    # Disk Fallback
    clean_sid = (session_id or "").strip()
    short_sid = clean_sid[:6] if len(clean_sid) >= 6 else clean_sid
    patterns = []
    if short_sid:
        patterns.append(f"*MAS_Report*_{short_sid}.pdf")
    patterns.append("*MAS_Report*.pdf")

    for pat in patterns:
        matches = sorted(REPORTS_DIR.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError("No MAS report generated yet. Please run extraction first.")


def get_mas_excel_bytes(
    financial_year: str = "",
    month: str = "",
    mandal: str = "all",
    session_id: str = "",
) -> tuple[str, bytes]:
    """Retrieves Excel workbook bytes for download."""
    master = get_latest_mas_report(financial_year=financial_year, month=month, session_id=session_id)
    if master is not None:
        report = filter_mas_report(master, mandal=mandal)
        safe_dist = get_mas_filename_prefix(report)
        safe_fy = report.financial_year.replace("/", "-")
        safe_m = report.month_name.replace(" ", "_")
        clean_m = (mandal or "").strip()
        if clean_m and clean_m.lower() not in ("all", "all mandals", "district"):
            safe_mnd = clean_m.replace(" ", "_")
            filename = f"{safe_dist}_{safe_mnd}_MAS_Report_{safe_fy}_{safe_m}.xlsx"
        else:
            filename = f"{safe_dist}_MAS_Report_{safe_fy}_{safe_m}.xlsx"
        data = generate_mas_excel(report)
        return filename, data

    # Disk Fallback
    clean_sid = (session_id or "").strip()
    short_sid = clean_sid[:6] if len(clean_sid) >= 6 else clean_sid
    patterns = []
    if short_sid:
        patterns.append(f"*MAS_Report*_{short_sid}.xlsx")
    patterns.append("*MAS_Report*.xlsx")

    for pat in patterns:
        matches = sorted(REPORTS_DIR.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches and matches[0].stat().st_size > 500:
            return matches[0].name, matches[0].read_bytes()

    raise ValueError("No MAS report generated yet. Please run extraction first.")

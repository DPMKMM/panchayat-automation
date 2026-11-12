"""Session-isolated service layer for Gram Panchayat Inspections (GM-R 39.1)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from threading import Lock
from typing import Any

from core.config import get_reports_dir
from core.session_manager import get_or_create_session, run_in_session_thread
from inspections.aggregator import consolidate_inspection_files
from inspections.automation import download_inspection_weeks, fetch_inspection_metadata
from inspections.models import (
    DESIGNATION_SPECS,
    SUPPORTED_DESIGNATIONS,
    InspectionReport,
    format_month_range_from_weeks,
    get_designation_spec,
)
from inspections.reports import (
    generate_inspections_csv,
    generate_inspections_excel,
    generate_inspections_pdf,
    generate_monthwise_inspections_csv,
    generate_monthwise_inspections_excel,
    generate_monthwise_inspections_pdf,
)

logger = logging.getLogger("inspections_service")

_SESSION_STORE_LOCK = Lock()
_SESSION_REPORTS: dict[str, dict[str, Any]] = {}


def serialize_inspection_report(report: InspectionReport) -> dict[str, Any]:
    """Serialize consolidated InspectionReport for JSON responses & frontend rendering."""
    records_by_unit: dict[str, list[dict[str, str]]] = {}
    for rec in report.submitted_records:
        key = rec.unit_name.casefold()
        records_by_unit.setdefault(key, []).append({
            "week": rec.week_label,
            "designation": rec.designation,
            "district": rec.district_name,
            "division": rec.division_name,
            "mandal": rec.mandal_name,
            "gp_name": rec.gp_name,
            "officer_name": rec.officer_name,
            "inspection_date": rec.inspection_date,
            "final_submit_status": rec.final_submit_status,
        })

    rows_payload = []
    for row in report.abstract_rows:
        rows_payload.append({
            "sl_no": row.serial,
            "unit_name": row.unit_name,
            "target": row.target,
            "completed": row.completed,
            "balance": row.balance,
            "pct_completed": row.pct_completed,
            "details": records_by_unit.get(row.unit_name.casefold(), []),
        })

    monthly_payload = []
    for sec in report.monthly_sections or []:
        m_rows = []
        for r in sec.abstract_rows:
            m_recs = [
                d for d in records_by_unit.get(r.unit_name.casefold(), [])
                if d.get("week") in sec.weeks_included
            ]
            m_rows.append({
                "sl_no": r.serial,
                "unit_name": r.unit_name,
                "target": r.target,
                "completed": r.completed,
                "balance": r.balance,
                "pct_completed": r.pct_completed,
                "details": m_recs,
            })
        monthly_payload.append({
            "year": sec.year,
            "month": sec.month,
            "month_key": sec.month_key,
            "month_label": sec.month_label,
            "weeks_included": sec.weeks_included,
            "week_count": sec.week_count,
            "target_per_unit": sec.target_per_unit,
            "target_rule_desc": sec.target_rule_desc,
            "totals": {
                "units_count": len(sec.abstract_rows),
                "target": sec.total_target,
                "completed": sec.total_completed,
                "balance": sec.total_balance,
                "pct_completed": sec.total_pct_completed,
                "raw_row_count": sec.raw_row_count,
                "submitted_row_count": sec.submitted_row_count,
                "excluded_non_submitted_count": sec.excluded_non_submitted_count,
            },
            "rows": m_rows,
        })

    return {
        "success": True,
        "module": "gp_inspections",
        "designation": report.designation,
        "designation_title": report.designation_title,
        "group_level": report.group_level,
        "group_label": report.group_label,
        "district_name": report.district_name,
        "from_week": report.from_week,
        "to_week": report.to_week,
        "month_period": format_month_range_from_weeks(report.from_week, report.to_week),
        "weeks_selected": report.weeks_selected,
        "weeks_count": len(report.weeks_selected),
        "target_per_unit": report.target_per_unit,
        "target_rule_desc": report.target_rule_desc,
        "generated_at": report.generated_time_str,
        "totals": {
            "units_count": len(report.abstract_rows),
            "target": report.total_target,
            "completed": report.total_completed,
            "balance": report.total_balance,
            "pct_completed": report.total_pct_completed,
            "raw_row_count": report.raw_row_count,
            "submitted_row_count": report.submitted_row_count,
            "excluded_non_submitted_count": report.excluded_non_submitted_count,
        },
        "rows": rows_payload,
        "monthly_sections": monthly_payload,
        "week_logs": report.week_download_logs,
        "pdf_url": "/api/inspections/report.pdf",
        "download_pdf_url": "/api/inspections/download-pdf",
        "excel_url": "/api/inspections/download-excel",
        "csv_url": "/api/inspections/download-csv",
        "monthwise_pdf_url": "/api/inspections/download-monthwise-pdf",
        "monthwise_excel_url": "/api/inspections/download-monthwise-excel",
        "monthwise_csv_url": "/api/inspections/download-monthwise-csv",
    }


def _persist_artifacts_for_session(session_id: str, report: InspectionReport) -> dict[str, Any]:
    """Generate consolidated and Month-Wise PDF/Excel/CSV files and store metadata in session memory."""
    reports_dir = get_reports_dir()
    safe_sid = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)[:12] or "sess"
    safe_dist = re.sub(r"[^A-Za-z0-9_-]", "_", report.district_name or "District")
    safe_desig = re.sub(r"[^A-Za-z0-9_-]", "_", report.designation)
    ts = report.generated_at.strftime("%Y%m%d_%H%M%S")

    pdf_name = f"{safe_dist}_{safe_desig}_GP_Inspections_Abstract_{ts}.pdf"
    xlsx_name = f"{safe_dist}_{safe_desig}_GP_Inspections_Consolidated_{ts}.xlsx"
    mw_pdf_name = f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts}.pdf"
    mw_xlsx_name = f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts}.xlsx"

    pdf_path = reports_dir / f"{safe_sid}_{pdf_name}"
    xlsx_path = reports_dir / f"{safe_sid}_{xlsx_name}"
    mw_pdf_path = reports_dir / f"{safe_sid}_{mw_pdf_name}"
    mw_xlsx_path = reports_dir / f"{safe_sid}_{mw_xlsx_name}"

    generate_inspections_pdf(report, pdf_path)
    generate_inspections_excel(report, xlsx_path)
    csv_bytes = generate_inspections_csv(report)
    generate_monthwise_inspections_pdf(report, mw_pdf_path)
    generate_monthwise_inspections_excel(report, mw_xlsx_path)
    mw_csv_bytes = generate_monthwise_inspections_csv(report)

    payload = serialize_inspection_report(report)
    with _SESSION_STORE_LOCK:
        _SESSION_REPORTS[session_id] = {
            "report": report,
            "payload": payload,
            "pdf_path": str(pdf_path),
            "pdf_filename": pdf_name,
            "xlsx_path": str(xlsx_path),
            "xlsx_filename": xlsx_name,
            "csv_bytes": csv_bytes,
            "csv_filename": f"{safe_dist}_{safe_desig}_GP_Inspections_Abstract_{ts}.csv",
            "mw_pdf_path": str(mw_pdf_path),
            "mw_pdf_filename": mw_pdf_name,
            "mw_xlsx_path": str(mw_xlsx_path),
            "mw_xlsx_filename": mw_xlsx_name,
            "mw_csv_bytes": mw_csv_bytes,
            "mw_csv_filename": f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts}.csv",
        }
    return payload


def get_specs_payload() -> dict[str, Any]:
    return {
        "success": True,
        "designations": list(SUPPORTED_DESIGNATIONS),
        "specs": DESIGNATION_SPECS,
    }


def get_live_weeks_for_session(session_id: str, designation: str | None = None) -> dict[str, Any]:
    """Scrape available From-To weekly options from GM-R 39.1 on the session's Playwright thread."""
    from dsr import service as automation_service

    session = get_or_create_session(session_id)
    with session["lock"]:
        def _task():
            bot = session.get("bot")
            if not automation_service._is_bot_alive(bot):
                bot = automation_service.ensure_active_bot(session)
            if not automation_service._is_bot_alive(bot):
                raise PermissionError(
                    "e-Panchayat browser session is not active. Please complete Departmental Login first."
                )
            return fetch_inspection_metadata(bot, designation=designation)

        return run_in_session_thread(session, _task)


def generate_live_inspection_report(
    session_id: str,
    designation: str = "MPO",
    from_week: str = "",
    to_week: str = "",
    from_month: str = "",
    to_month: str = "",
    target_override: int | None = None,
) -> dict[str, Any]:
    """Download each selected week (by week range or Monday-month range) from GM-R 39.1 and consolidate."""
    from dsr import service as automation_service

    spec = get_designation_spec(designation)
    canon_desig = spec["designation"]
    session = get_or_create_session(session_id)

    with session["lock"]:
        def _task():
            bot = session.get("bot")
            if not automation_service._is_bot_alive(bot):
                bot = automation_service.ensure_active_bot(session)
            if not automation_service._is_bot_alive(bot):
                raise PermissionError(
                    "e-Panchayat browser session is not active. Please complete Departmental Login first."
                )

            dl_kwargs: dict[str, Any] = {
                "bot": bot,
                "designation": canon_desig,
                "from_week": from_week,
                "to_week": to_week,
                "downloads_dir": session["downloads_dir"],
            }
            if from_month.strip():
                dl_kwargs["from_month"] = from_month
                dl_kwargs["to_month"] = to_month
            week_files, week_labels = download_inspection_weeks(**dl_kwargs)
            dist_name = str(session.get("district_name") or "").strip()
            user_level = str(session.get("user_level") or "district").strip().lower()
            mandal_name = str(session.get("mandal_name") or "").strip()

            report = consolidate_inspection_files(
                week_files=week_files,
                designation=canon_desig,
                weeks_selected=week_labels,
                district_name=dist_name,
                target_override=target_override,
            )

            # Restrict to officer's own mandal if logged in as a single Mandal officer
            if user_level == "mandal" and mandal_name and spec["group_level"] == "mandal":
                filtered_rows = [
                    r for r in report.abstract_rows if r.unit_name.casefold() == mandal_name.casefold()
                ]
                if filtered_rows:
                    for idx, r in enumerate(filtered_rows, start=1):
                        r.serial = idx
                    report.abstract_rows = filtered_rows
                    report.total_target = sum(r.target for r in filtered_rows)
                    report.total_completed = sum(r.completed for r in filtered_rows)
                    report.total_balance = sum(r.balance for r in filtered_rows)
                    report.total_pct_completed = (
                        round((report.total_completed / report.total_target) * 100.0, 2)
                        if report.total_target > 0
                        else 0.0
                    )

            return _persist_artifacts_for_session(session_id, report)

        return run_in_session_thread(session, _task)


def consolidate_uploaded_inspection_files(
    session_id: str,
    files_payload: list[tuple[str, bytes]],
    designation: str = "MPO",
    from_week: str = "",
    to_week: str = "",
    district_name: str = "",
    target_override: int | None = None,
) -> dict[str, Any]:
    """Consolidate manually uploaded GM-R 39.1 weekly Excel files into the same abstract + PDF + Excel."""
    if not files_payload:
        raise ValueError("Please upload at least one GM-R 39.1 Excel file.")

    week_files = []
    for idx, (fname, raw) in enumerate(files_payload, start=1):
        lbl = ""
        if idx == 1 and from_week.strip():
            lbl = from_week.strip()
        elif idx == len(files_payload) and len(files_payload) > 1 and to_week.strip():
            lbl = to_week.strip()
        week_files.append({
            "week_label": lbl,
            "filename": fname,
            "raw_bytes": raw,
            "status": "uploaded",
        })

    explicit_weeks = [w for w in (from_week.strip(), to_week.strip()) if w]
    report = consolidate_inspection_files(
        week_files=week_files,
        designation=designation,
        weeks_selected=explicit_weeks or None,
        district_name=district_name,
        target_override=target_override,
    )
    return _persist_artifacts_for_session(session_id, report)


def get_session_inspection_payload(session_id: str) -> dict[str, Any] | None:
    with _SESSION_STORE_LOCK:
        entry = _SESSION_REPORTS.get(session_id)
        return entry["payload"] if entry else None


def get_session_download_artifact(session_id: str, kind: str) -> tuple[str, bytes, str]:
    """Return (filename, bytes, media_type) for pdf | excel | csv generated in this session."""
    with _SESSION_STORE_LOCK:
        entry = _SESSION_REPORTS.get(session_id)
    if not entry:
        raise FileNotFoundError("No inspection report has been generated in this session yet.")

    if kind == "pdf":
        p = Path(entry["pdf_path"])
        if not p.exists():
            raise FileNotFoundError("Generated inspection PDF file is no longer available.")
        return entry["pdf_filename"], p.read_bytes(), "application/pdf"
    if kind == "excel":
        p = Path(entry["xlsx_path"])
        if not p.exists():
            raise FileNotFoundError("Generated inspection Excel file is no longer available.")
        return (
            entry["xlsx_filename"],
            p.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if kind == "csv":
        return entry["csv_filename"], entry["csv_bytes"], "text/csv; charset=utf-8"
    if kind == "monthwise-pdf":
        p = Path(entry["mw_pdf_path"])
        if not p.exists():
            raise FileNotFoundError("Generated Month-Wise inspection PDF is no longer available.")
        return entry["mw_pdf_filename"], p.read_bytes(), "application/pdf"
    if kind == "monthwise-excel":
        p = Path(entry["mw_xlsx_path"])
        if not p.exists():
            raise FileNotFoundError("Generated Month-Wise inspection Excel is no longer available.")
        return (
            entry["mw_xlsx_filename"],
            p.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if kind == "monthwise-csv":
        return entry["mw_csv_filename"], entry["mw_csv_bytes"], "text/csv; charset=utf-8"
    raise ValueError(f"Unsupported artifact kind: {kind}")

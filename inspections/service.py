"""Session-isolated service layer for Gram Panchayat Inspections (GM-R 39.1)."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Optional

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
    generate_pending_gps_csv,
    generate_total_gps_csv,
)

logger = logging.getLogger("inspections_service")

_SESSION_STORE_LOCK = Lock()
_SESSION_REPORTS: dict[str, dict[str, Any]] = {}

_INSP_PROGRESS_LOCK = Lock()
_INSP_PROGRESS_MAP: dict[str, dict[str, Any]] = {}


def set_inspection_progress(
    session_id: str,
    *,
    status: str,
    current_week: str = "",
    current_index: int = 0,
    total_weeks: int = 0,
    designation: str = "",
    detail: str = "",
) -> None:
    sid = str(session_id or "").strip()
    if not sid:
        return
    with _INSP_PROGRESS_LOCK:
        _INSP_PROGRESS_MAP[sid] = {
            "status": status,
            "current_week": current_week,
            "current_index": current_index,
            "total_weeks": total_weeks,
            "designation": designation,
            "detail": detail,
            "updated_at": time.time(),
        }


def get_inspection_progress(session_id: str) -> dict[str, Any]:
    sid = str(session_id or "").strip()
    with _INSP_PROGRESS_LOCK:
        info = _INSP_PROGRESS_MAP.get(sid)
        if not info:
            return {
                "active": False,
                "status": "idle",
                "current_week": "",
                "current_index": 0,
                "total_weeks": 0,
                "detail": "",
            }
        return {"active": True, **info}


def clear_inspection_progress(session_id: str) -> None:
    sid = str(session_id or "").strip()
    with _INSP_PROGRESS_LOCK:
        _INSP_PROGRESS_MAP.pop(sid, None)


def _insp_rec_to_dict(rec: InspectionRecord) -> dict[str, Any]:
    return {
        "week": rec.week_label,
        "designation": rec.designation,
        "district": rec.district_name,
        "division": rec.division_name,
        "mandal": rec.mandal_name,
        "gp_name": rec.gp_name,
        "officer_name": rec.officer_name,
        "inspection_date": rec.inspection_date,
        "attendance_datetime": rec.attendance_datetime,
        "attendance_status": rec.attendance_status,
        "final_submit_status": rec.final_submit_status,
        "is_submitted": rec.is_submitted,
        "month_key": rec.month_key,
        "month_label": rec.month_label,
    }


def serialize_inspection_report(report: InspectionReport) -> dict[str, Any]:
    """Serialize consolidated InspectionReport for JSON responses & frontend rendering."""
    records_by_unit: dict[str, list[dict[str, Any]]] = {}
    pending_by_unit: dict[str, list[dict[str, Any]]] = {}
    all_by_unit: dict[str, list[dict[str, Any]]] = {}

    for rec in report.all_records:
        key = rec.unit_name.casefold()
        d = _insp_rec_to_dict(rec)
        all_by_unit.setdefault(key, []).append(d)
        if rec.is_submitted:
            records_by_unit.setdefault(key, []).append(d)
        else:
            pending_by_unit.setdefault(key, []).append(d)

    rows_payload = []
    for row in report.abstract_rows:
        key = row.unit_name.casefold()
        rows_payload.append({
            "sl_no": row.serial,
            "unit_name": row.unit_name,
            "target": row.target,
            "completed": row.completed,
            "balance": row.balance,
            "pct_completed": row.pct_completed,
            "details": records_by_unit.get(key, []),
            "pending_details": pending_by_unit.get(key, []),
            "all_details": all_by_unit.get(key, []),
        })

    monthly_payload = []
    for sec in report.monthly_sections or []:
        m_rows = []
        sec_recs_by_unit: dict[str, list[dict[str, Any]]] = {}
        sec_pending_by_unit: dict[str, list[dict[str, Any]]] = {}
        sec_all_by_unit: dict[str, list[dict[str, Any]]] = {}

        src_all = sec.all_records or [
            r for r in report.all_records
            if (r.month_key and r.month_key == sec.month_key) or r.week_label in sec.weeks_included
        ]
        for rec in src_all:
            k = rec.unit_name.casefold()
            d = _insp_rec_to_dict(rec)
            sec_all_by_unit.setdefault(k, []).append(d)
            if rec.is_submitted:
                sec_recs_by_unit.setdefault(k, []).append(d)
            else:
                sec_pending_by_unit.setdefault(k, []).append(d)

        for r in sec.abstract_rows:
            k = r.unit_name.casefold()
            m_rows.append({
                "sl_no": r.serial,
                "unit_name": r.unit_name,
                "target": r.target,
                "completed": r.completed,
                "balance": r.balance,
                "pct_completed": r.pct_completed,
                "details": sec_recs_by_unit.get(k, []),
                "pending_details": sec_pending_by_unit.get(k, []),
                "all_details": sec_all_by_unit.get(k, []),
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
            "counting_mode": sec.counting_mode,
            "totals": {
                "units_count": len(sec.abstract_rows),
                "target": sec.total_target,
                "completed": sec.total_completed,
                "balance": sec.total_balance,
                "pct_completed": sec.total_pct_completed,
                "raw_row_count": sec.raw_row_count,
                "submitted_row_count": sec.submitted_row_count,
                "pending_row_count": sec.pending_row_count,
                "excluded_non_submitted_count": sec.excluded_non_submitted_count,
            },
            "rows": m_rows,
            "submitted_records": [_insp_rec_to_dict(r) for r in sec.submitted_records],
            "pending_records": [_insp_rec_to_dict(r) for r in sec.pending_records],
            "all_records": [_insp_rec_to_dict(r) for r in sec.all_records],
        })

    pending_count = report.pending_row_count if getattr(report, "pending_row_count", 0) > 0 else len(report.pending_records)
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
        "counting_mode": report.counting_mode,
        "counting_mode_label": report.counting_mode_label,
        "generated_at": report.generated_time_str,
        "totals": {
            "units_count": len(report.abstract_rows),
            "target": report.total_target,
            "completed": report.total_completed,
            "balance": report.total_balance,
            "pct_completed": report.total_pct_completed,
            "raw_row_count": report.raw_row_count,
            "submitted_row_count": report.submitted_row_count,
            "pending_row_count": pending_count,
            "excluded_non_submitted_count": report.excluded_non_submitted_count,
        },
        "rows": rows_payload,
        "submitted_records": [_insp_rec_to_dict(r) for r in report.submitted_records],
        "pending_records": [_insp_rec_to_dict(r) for r in report.pending_records],
        "all_records": [_insp_rec_to_dict(r) for r in report.all_records],
        "monthly_sections": monthly_payload,
        "week_logs": report.week_download_logs,
        "pdf_url": "/api/inspections/report.pdf",
        "download_pdf_url": "/api/inspections/download-pdf",
        "excel_url": "/api/inspections/download-excel",
        "csv_url": "/api/inspections/download-csv",
        "monthwise_pdf_url": "/api/inspections/download-monthwise-pdf",
        "monthwise_excel_url": "/api/inspections/download-monthwise-excel",
        "monthwise_csv_url": "/api/inspections/download-monthwise-csv",
        "pending_csv_url": "/api/inspections/download-pending-csv",
        "total_csv_url": "/api/inspections/download-total-csv",
    }


def _persist_artifacts_for_session(session_id: str, report: InspectionReport) -> dict[str, Any]:
    """Generate consolidated and Month-Wise PDF/Excel/CSV files and store metadata in session memory."""
    reports_dir = get_reports_dir()
    safe_sid = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)[:12] or "sess"
    safe_dist = re.sub(r"[^A-Za-z0-9_-]", "_", report.district_name or "District")
    safe_desig = re.sub(r"[^A-Za-z0-9_-]", "_", report.designation)
    ts_download = report.generated_at.strftime("%d-%m-%Y %I:%M %p")
    ts_disk = report.generated_at.strftime("%d-%m-%Y_%I-%M_%p")

    pdf_name = f"{safe_dist}_{safe_desig}_GP_Inspections_Abstract_{ts_download}.pdf"
    xlsx_name = f"{safe_dist}_{safe_desig}_GP_Inspections_Consolidated_{ts_download}.xlsx"
    csv_name = f"{safe_dist}_{safe_desig}_GP_Inspections_Abstract_{ts_download}.csv"
    pending_csv_name = f"{safe_dist}_{safe_desig}_Pending_GPs_Data_{ts_download}.csv"
    total_csv_name = f"{safe_dist}_{safe_desig}_Total_GPs_Inspection_Status_{ts_download}.csv"
    mw_pdf_name = f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts_download}.pdf"
    mw_xlsx_name = f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts_download}.xlsx"
    mw_csv_name = f"{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts_download}.csv"

    pdf_path = reports_dir / f"{safe_sid}_{safe_dist}_{safe_desig}_GP_Inspections_Abstract_{ts_disk}.pdf"
    xlsx_path = reports_dir / f"{safe_sid}_{safe_dist}_{safe_desig}_GP_Inspections_Consolidated_{ts_disk}.xlsx"
    mw_pdf_path = reports_dir / f"{safe_sid}_{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts_disk}.pdf"
    mw_xlsx_path = reports_dir / f"{safe_sid}_{safe_dist}_{safe_desig}_GP_Inspections_MonthWise_{ts_disk}.xlsx"

    generate_inspections_pdf(report, pdf_path)
    generate_inspections_excel(report, xlsx_path)
    csv_bytes = generate_inspections_csv(report)
    pending_csv_bytes = generate_pending_gps_csv(report)
    total_csv_bytes = generate_total_gps_csv(report)
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
            "csv_filename": csv_name,
            "pending_csv_bytes": pending_csv_bytes,
            "pending_csv_filename": pending_csv_name,
            "total_csv_bytes": total_csv_bytes,
            "total_csv_filename": total_csv_name,
            "mw_pdf_path": str(mw_pdf_path),
            "mw_pdf_filename": mw_pdf_name,
            "mw_xlsx_path": str(mw_xlsx_path),
            "mw_xlsx_filename": mw_xlsx_name,
            "mw_csv_bytes": mw_csv_bytes,
            "mw_csv_filename": mw_csv_name,
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
    counting_mode: str = "attendance",
) -> dict[str, Any]:
    """Download each selected week (by week range or Monday-month range) from GM-R 39.1 and consolidate."""
    from dsr import service as automation_service

    spec = get_designation_spec(designation)
    canon_desig = spec["designation"]
    session = get_or_create_session(session_id)

    set_inspection_progress(
        session_id,
        status="starting",
        current_week=from_week or "Initializing",
        current_index=0,
        total_weeks=1,
        designation=canon_desig,
        detail="Initializing GM-R 39.1 inspection robot...",
    )

    with session["lock"]:
        def _task():
            bot = session.get("bot")
            if not automation_service._is_bot_alive(bot):
                bot = automation_service.ensure_active_bot(session)
            if not automation_service._is_bot_alive(bot):
                raise PermissionError(
                    "e-Panchayat browser session is not active. Please complete Departmental Login first."
                )

            def _progress_cb(wk_label: str, cur_idx: int, tot_wks: int) -> None:
                set_inspection_progress(
                    session_id,
                    status="processing",
                    current_week=wk_label,
                    current_index=cur_idx,
                    total_weeks=tot_wks,
                    designation=canon_desig,
                    detail=f"Processing Week {cur_idx} of {tot_wks}: {wk_label}",
                )

            dl_kwargs: dict[str, Any] = {
                "bot": bot,
                "designation": canon_desig,
                "from_week": from_week,
                "to_week": to_week,
                "downloads_dir": session["downloads_dir"],
                "counting_mode": counting_mode,
                "on_progress": _progress_cb,
            }
            if from_month.strip():
                dl_kwargs["from_month"] = from_month
                dl_kwargs["to_month"] = to_month
            week_files, week_labels = download_inspection_weeks(**dl_kwargs)

            set_inspection_progress(
                session_id,
                status="consolidating",
                current_week=f"All {len(week_labels)} week(s)",
                current_index=len(week_labels),
                total_weeks=len(week_labels),
                designation=canon_desig,
                detail=f"Consolidating submitted inspection records across {len(week_labels)} week(s)...",
            )

            dist_name = str(session.get("district_name") or "").strip()
            user_level = str(session.get("user_level") or "district").strip().lower()
            mandal_name = str(session.get("mandal_name") or "").strip()

            report = consolidate_inspection_files(
                week_files=week_files,
                designation=canon_desig,
                weeks_selected=week_labels,
                district_name=dist_name,
                target_override=target_override,
                counting_mode=counting_mode,
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

            res = _persist_artifacts_for_session(session_id, report)
            set_inspection_progress(
                session_id,
                status="completed",
                current_week=f"Completed {len(week_labels)} week(s)",
                current_index=len(week_labels),
                total_weeks=len(week_labels),
                designation=canon_desig,
                detail=f"Successfully consolidated {len(week_labels)} week(s).",
            )
            return res

        try:
            return run_in_session_thread(session, _task)
        except Exception as exc:
            set_inspection_progress(
                session_id,
                status="error",
                current_week="",
                current_index=0,
                total_weeks=0,
                designation=canon_desig,
                detail=str(exc),
            )
            raise


def consolidate_uploaded_inspection_files(
    session_id: str,
    files_payload: list[tuple[str, bytes]],
    designation: str = "MPO",
    from_week: str = "",
    to_week: str = "",
    district_name: str = "",
    target_override: int | None = None,
    counting_mode: str = "attendance",
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
        counting_mode=counting_mode,
    )
    return _persist_artifacts_for_session(session_id, report)


def clear_session_inspections(session_id: str) -> None:
    """Wipe any cached inspection report for this session."""
    with _SESSION_STORE_LOCK:
        _SESSION_REPORTS.pop(session_id, None)


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
    if kind == "pending-csv":
        return entry["pending_csv_filename"], entry["pending_csv_bytes"], "text/csv; charset=utf-8"
    if kind == "total-csv":
        return entry["total_csv_filename"], entry["total_csv_bytes"], "text/csv; charset=utf-8"
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

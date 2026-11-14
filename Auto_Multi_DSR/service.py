"""Service layer and background orchestration for Automated Multiple Days DSR reporting."""

from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd

from Auto_Multi_DSR import automation as auto_scraper
from Auto_Multi_DSR.holidays import (
    analyze_working_days,
    format_display_date,
    format_portal_date,
    parse_date_input,
)
from Auto_Multi_DSR.models import AutoMultiDsrJobRecord, DateAnalysis, DownloadDayStatus
from core.config import get_reports_dir
from dsr import service as automation_service
from multiday_dsr.processor import MultiDayDsrResult, highlight_percentage, process_dsr
from multiday_dsr.reports import generate_multiday_dsr_excel, generate_multiday_dsr_pdf
from multiday_dsr.service import _df_to_records

logger = logging.getLogger("auto_multi_dsr_service")

_LOCK = threading.Lock()
_JOBS: dict[str, AutoMultiDsrJobRecord] = {}
_ACTIVE_JOB_BY_SESSION: dict[str, str] = {}


def preview_date_range(
    start_date: str,
    end_date: str,
    public_holidays: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Calculate working days, automatically excluding Sundays, Second Saturdays,

    and any user-specified public holidays.
    """
    analysis = analyze_working_days(start_date, end_date, public_holidays)
    return {
        "success": True,
        "date_analysis": analysis.to_dict(),
    }


def start_auto_multi_dsr_pipeline(
    session_id: str,
    user_id: str,
    district_name: str,
    start_date: str,
    end_date: str,
    public_holidays: Iterable[str] | None = None,
    include_time_matrix: bool = True,
) -> dict[str, Any]:
    """Initialize an automated multi-days download job and launch background runner."""
    analysis = analyze_working_days(start_date, end_date, public_holidays)
    if not analysis.working_days:
        raise ValueError(
            f"No working days found between {start_date} and {end_date} after excluding "
            f"{len(analysis.excluded_sundays)} Sunday(s), "
            f"{len(analysis.excluded_second_saturdays)} Second Saturday(s), and "
            f"{len(analysis.excluded_public_holidays)} Public Holiday(s)."
        )

    job_id = uuid4().hex
    job = AutoMultiDsrJobRecord(
        job_id=job_id,
        session_id=session_id,
        district_name=district_name or "District",
        user_id=user_id or "Officer",
        start_date=analysis.start_date,
        end_date=analysis.end_date,
        date_analysis=analysis,
        status="queued",
        started_at=time.time(),
    )

    with _LOCK:
        _JOBS[job_id] = job
        _ACTIVE_JOB_BY_SESSION[session_id] = job_id

    # Launch worker in background thread attached to session Playwright runner
    thread = threading.Thread(
        target=_execute_job_thread,
        args=(job_id, session_id, include_time_matrix),
        name=f"auto-multi-dsr-{job_id[:8]}",
        daemon=True,
    )
    thread.start()

    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "total_working_days": len(analysis.working_days),
        "working_days": analysis.working_days,
        "date_analysis": analysis.to_dict(),
    }


def _execute_job_thread(job_id: str, session_id: str, include_time_matrix: bool) -> None:
    """Thread worker iterating each working day via the active Playwright session."""
    session = automation_service.get_or_create_session(session_id)
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.status = "running"

    reports_dir = get_reports_dir()
    downloaded_files: list[tuple[str, bytes]] = []

    def _run_in_bot_page():
        active_bot = session.get("bot")
        if not automation_service._is_bot_alive(active_bot):
            active_bot = automation_service.ensure_active_bot(session)

        working_days = job.date_analysis.working_days
        total_w = len(working_days)

        for idx, w_iso in enumerate(working_days, start=1):
            session["last_activity"] = time.time()
            disp = format_display_date(parse_date_input(w_iso))
            portal_str = format_portal_date(parse_date_input(w_iso))

            with _LOCK:
                job.current_date = disp
                job.progress_pct = int(((idx - 1) / total_w) * 80)

            day_status = DownloadDayStatus(
                date_str=w_iso,
                display_date=disp,
                portal_date=portal_str,
                status="downloading",
            )

            try:
                fname, raw = auto_scraper.download_daily_gmr127_raw(
                    active_bot,
                    target_date=w_iso,
                    downloads_dir=reports_dir,
                    max_retries=2,
                )
                day_status.status = "success"
                day_status.filename = fname
                day_status.file_size = len(raw)
                day_status.attempts = 1
                downloaded_files.append((fname, raw))

                with _LOCK:
                    job.successful_dates.append(w_iso)
                    job.download_logs.append(day_status.to_log_dict())

            except Exception as exc:
                logger.warning("[Auto-Multi-DSR] Error downloading date %s: %s", disp, exc)
                day_status.status = "failed"
                day_status.error = str(exc)
                day_status.attempts = 2

                with _LOCK:
                    job.failed_dates.append(w_iso)
                    job.download_logs.append(day_status.to_log_dict())

            with _LOCK:
                job.progress_pct = int((idx / total_w) * 80)

    sess_lock = session.get("lock")
    try:
        if sess_lock:
            with sess_lock:
                automation_service.run_in_session_thread(session, _run_in_bot_page)
        else:
            automation_service.run_in_session_thread(session, _run_in_bot_page)

        if not downloaded_files:
            raise RuntimeError(
                f"No daily GM-R 1.2.7 raw reports could be downloaded across {len(job.date_analysis.working_days)} "
                f"working day(s). Errors: {', '.join(log.get('error', '') for log in job.download_logs if log.get('error'))}"
            )

        with _LOCK:
            job.current_date = "Consolidating downloaded reports..."
            job.progress_pct = 85

        # Consolidate via existing proven multiday processor
        result: MultiDayDsrResult = process_dsr(downloaded_files)

        safe_dist = re.sub(r"[^A-Za-z0-9_-]", "_", result.dist_name or job.district_name or "District").strip("_") or "District"
        ts_download = result.generated_at.strftime("%d-%m-%Y %I:%M %p")
        ts_disk = result.generated_at.strftime("%d-%m-%Y_%I-%M_%p")

        pdf_filenames = {
            "all": f"{safe_dist}_Auto_MultiDays_DSR_Full_Report_{ts_download}.pdf",
            "district": f"{safe_dist}_Auto_MultiDays_DSR_District_{ts_download}.pdf",
            "mandal": f"{safe_dist}_Auto_MultiDays_DSR_Mandal_{ts_download}.pdf",
            "gp": f"{safe_dist}_Auto_MultiDays_DSR_GP_Summary_{ts_download}.pdf",
            "time_matrix": f"{safe_dist}_Auto_MultiDays_DSR_Exact_Time_{ts_download}.pdf",
        }
        excel_filename = f"{safe_dist}_Auto_MultiDays_DSR_Report_{ts_download}.xlsx"

        pdf_paths = {
            lvl: reports_dir / f"{job_id[:10]}_{safe_dist}_AutoMulti_{lvl}_{ts_disk}.pdf"
            for lvl in pdf_filenames
        }
        excel_path = reports_dir / f"{job_id[:10]}_{safe_dist}_AutoMulti_{ts_disk}.xlsx"

        # Generate deliverables
        for lvl, p_path in pdf_paths.items():
            generate_multiday_dsr_pdf(result, p_path, include_time_matrix=include_time_matrix, level=lvl)
        generate_multiday_dsr_excel(result, excel_path, include_time_matrix=include_time_matrix)

        dist_rows = _df_to_records(result.district)
        mandal_rows = _df_to_records(result.mandal)
        gp_rows = _df_to_records(result.gp_summary)
        tm_rows = _df_to_records(result.time_matrix, include_time_styles=True) if include_time_matrix else []

        tot_reported = int(result.district["Total Reported"].sum()) if not result.district.empty else 0
        tot_before9 = int(result.district["Before 9 AM"].sum()) if not result.district.empty else 0
        overall_before9_pct = round((tot_before9 / tot_reported) * 100, 2) if tot_reported > 0 else 0.0

        report_payload = {
            "summary": {
                "dist_name": result.dist_name,
                "mandal_name": result.mandal_name,
                "mandal_count": result.mandal_count,
                "total_gps": result.total_gps,
                "total_reporting_days": result.total_reporting_days,
                "working_days_downloaded": len(job.successful_dates),
                "working_days_failed": len(job.failed_dates),
                "start_date": result.start_date,
                "end_date": result.end_date,
                "raw_row_count": len(result.master_data),
                "overall_before9_pct": overall_before9_pct,
                "generated_on": ts_download,
            },
            "district_columns": list(result.district.columns),
            "mandal_columns": list(result.mandal.columns),
            "gp_columns": list(result.gp_summary.columns),
            "time_matrix_columns": list(result.time_matrix.columns) if include_time_matrix else [],
            "district_rows": dist_rows,
            "mandal_rows": mandal_rows,
            "gp_rows": gp_rows,
            "time_matrix_rows": tm_rows,
            "download_filenames": {
                "pdf": pdf_filenames["all"],
                "pdf_district": pdf_filenames["district"],
                "pdf_mandal": pdf_filenames["mandal"],
                "pdf_gp": pdf_filenames["gp"],
                "pdf_time_matrix": pdf_filenames["time_matrix"],
                "excel": excel_filename,
            },
        }

        with _LOCK:
            job.status = "completed"
            job.progress_pct = 100
            job.current_date = "Completed"
            job.report_data = report_payload
            job.pdf_filenames = pdf_filenames
            job.pdf_paths = {k: str(v) for k, v in pdf_paths.items()}
            job.excel_filename = excel_filename
            job.excel_path = str(excel_path)
            job.result = result
            job.completed_at = time.time()

        # Cache in session storage for direct instant reload
        session["auto_multi_dsr_payload"] = report_payload
        session["auto_multi_dsr_result"] = result
        session["auto_multi_dsr_job_id"] = job_id

    except PermissionError as exc:
        logger.exception("[Auto-Multi-DSR] Session authentication error: %s", exc)
        with _LOCK:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = time.time()
    except Exception as exc:
        logger.exception("[Auto-Multi-DSR] Pipeline failed for job %s: %s", job_id, exc)
        with _LOCK:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = time.time()


def get_job_status(job_id: str, session_id: str) -> dict[str, Any]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise FileNotFoundError(f"Auto-Multi-DSR job '{job_id}' not found or expired.")
        if job.session_id != session_id:
            raise PermissionError("Access forbidden to another session's reporting job.")
        return job.to_public_dict()


def clear_session_jobs(session_id: str) -> None:
    """Wipe any active or completed jobs for this session."""
    with _LOCK:
        job_id = _ACTIVE_JOB_BY_SESSION.pop(session_id, None)
        if job_id:
            _JOBS.pop(job_id, None)


def get_session_active_job(session_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job_id = _ACTIVE_JOB_BY_SESSION.get(session_id)
        if not job_id:
            return None
        job = _JOBS.get(job_id)
        return job.to_public_dict() if job else None


def get_job_artifact(job_id: str, session_id: str, kind: str, level: str = "all") -> tuple[str, bytes, str]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise FileNotFoundError(f"Auto-Multi-DSR job '{job_id}' not found or expired.")
        if job.session_id != session_id:
            raise PermissionError("Access forbidden to another session's reporting artifact.")
        if job.status != "completed":
            raise RuntimeError(f"Report generation is currently '{job.status}'. Please wait for completion.")

    if kind == "pdf":
        lvl = (level or "all").strip().lower()
        if lvl in ("exact_time", "time"):
            lvl = "time_matrix"
        if lvl not in job.pdf_paths:
            lvl = "all"
        p = Path(job.pdf_paths[lvl])
        if not p.exists():
            # Generate on demand
            res = job.result
            if not res:
                session = automation_service.get_or_create_session(session_id)
                res = session.get("auto_multi_dsr_result")
            if not res:
                raise FileNotFoundError(f"PDF file for level '{lvl}' is no longer available on disk.")
            generate_multiday_dsr_pdf(res, p, include_time_matrix=True, level=lvl)
        return job.pdf_filenames[lvl], p.read_bytes(), "application/pdf"

    if kind == "excel":
        p = Path(job.excel_path)
        if not p.exists():
            raise FileNotFoundError("Generated Excel workbook is no longer available on disk.")
        return (
            job.excel_filename,
            p.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    raise ValueError(f"Unsupported artifact kind: '{kind}'. Expected 'pdf' or 'excel'.")

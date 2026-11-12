"""FastAPI Router for Automated Multiple Days DSR & PS Attendance Reporting."""

from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from Auto_Multi_DSR import service as auto_multi_service
from core.dependencies import enforce_console_api_access, enforce_department_api_access

router = APIRouter(prefix="/api/auto-multi-dsr", tags=["Automated Multiple Days DSR"])


class DatePreviewRequest(BaseModel):
    start_date: str
    end_date: str
    public_holidays: Optional[List[str]] = None


class StartJobRequest(BaseModel):
    start_date: str
    end_date: str
    public_holidays: Optional[List[str]] = None
    include_time_matrix: bool = True


async def _parse_preview_body(request: Request) -> tuple[str, str, list[str]]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        raw = await request.body()
        if raw and raw.strip():
            d = json.loads(raw.decode("utf-8"))
            if isinstance(d, dict):
                return (
                    str(d.get("start_date") or "").strip(),
                    str(d.get("end_date") or "").strip(),
                    list(d.get("public_holidays") or []),
                )
    form = await request.form()
    ph_raw = form.get("public_holidays") or ""
    ph_list = [s.strip() for s in str(ph_raw).split(",") if s.strip()] if ph_raw else []
    return (
        str(form.get("start_date") or "").strip(),
        str(form.get("end_date") or "").strip(),
        ph_list,
    )


async def _parse_start_job_body(request: Request) -> tuple[str, str, list[str], bool]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        raw = await request.body()
        if raw and raw.strip():
            d = json.loads(raw.decode("utf-8"))
            if isinstance(d, dict):
                return (
                    str(d.get("start_date") or "").strip(),
                    str(d.get("end_date") or "").strip(),
                    list(d.get("public_holidays") or []),
                    bool(d.get("include_time_matrix", True)),
                )
    form = await request.form()
    ph_raw = form.get("public_holidays") or ""
    ph_list = [s.strip() for s in str(ph_raw).split(",") if s.strip()] if ph_raw else []
    inc_tm = str(form.get("include_time_matrix", "true")).lower() in ("true", "1", "yes")
    return (
        str(form.get("start_date") or "").strip(),
        str(form.get("end_date") or "").strip(),
        ph_list,
        inc_tm,
    )


@router.post("/preview-dates", include_in_schema=False)
async def preview_dates_api(request: Request) -> dict[str, Any]:
    """Calculate working days, automatically excluding Sundays, Second Saturdays,

    and user-specified public holidays.
    """
    enforce_console_api_access(request)
    start_date, end_date, public_holidays = await _parse_preview_body(request)
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Please provide both start_date and end_date.")
    try:
        return auto_multi_service.preview_date_range(start_date, end_date, public_holidays)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start-job", include_in_schema=False)
async def start_job_api(request: Request) -> dict[str, Any]:
    """Initiate the Automated Multi-Days DSR download and consolidation pipeline."""
    console_user, sid = enforce_department_api_access(request, always_require=True)
    start_date, end_date, public_holidays, include_time_matrix = await _parse_start_job_body(request)
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Please select both Start Date and End Date.")

    from dsr import service as automation_service
    session = automation_service.get_or_create_session(sid)
    district = session.get("district_name") or (console_user.get("district") if console_user else "") or "District"
    uid = session.get("user_id") or (console_user.get("user_id") if console_user else "") or "Officer"

    try:
        return auto_multi_service.start_auto_multi_dsr_pipeline(
            session_id=sid,
            user_id=uid,
            district_name=district,
            start_date=start_date,
            end_date=end_date,
            public_holidays=public_holidays,
            include_time_matrix=include_time_matrix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", include_in_schema=False)
def get_job_progress_api(request: Request, job_id: str) -> dict[str, Any]:
    """Poll live progress, status, date download logs, or final report payload."""
    _, sid = enforce_department_api_access(request, always_require=True)
    try:
        return auto_multi_service.get_job_status(job_id, sid)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/session-job", include_in_schema=False)
def get_session_job_api(request: Request) -> dict[str, Any]:
    """Retrieve existing or active job for this department session."""
    _, sid = enforce_department_api_access(request, always_require=True)
    job_data = auto_multi_service.get_session_active_job(sid)
    if not job_data:
        return {"success": False, "job": None}
    return {"success": True, "job": job_data}


def _download_artifact_response(request: Request, job_id: str, kind: str, level: str = "all") -> Response:
    _, sid = enforce_department_api_access(request, always_require=True)
    try:
        fname, raw, mime = auto_multi_service.get_job_artifact(job_id, sid, kind, level=level)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=raw,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/jobs/{job_id}/download-pdf", include_in_schema=False)
def download_pdf_api(job_id: str, request: Request, level: str = "all") -> Response:
    return _download_artifact_response(request, job_id, "pdf", level=level)


@router.get("/jobs/{job_id}/download-excel", include_in_schema=False)
def download_excel_api(job_id: str, request: Request) -> Response:
    return _download_artifact_response(request, job_id, "excel")

"""FastAPI Router for GP Balance Entry Report (GM-R 14.2) endpoints."""

from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import APIRouter, Form, HTTPException, Request, Response

from core.firebase_store import log_usage
from core.dependencies import enforce_console_api_access, enforce_department_api_access, extract_epts_session_id
from gp_balance import service as gp_balance_service

logger = logging.getLogger("gp_balance_router")
router = APIRouter(tags=["GP Balance Entry (GM-R 14.2)"])

_get_sid = extract_epts_session_id


@router.get("/api/balance/portal-dates", include_in_schema=False)
@router.get("/api/balance/dates", include_in_schema=False)
def get_balance_portal_dates(request: Request) -> dict[str, Any]:
    """Returns available Thursday dates scraped from e-Panchayat GM-R 14.2 on the session Playwright thread."""
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        from dsr import service as automation_service
        from core.session_manager import run_in_session_thread

        session = automation_service.get_or_create_session(sid)
        if automation_service.is_authenticated(session_id=sid):
            with session["lock"]:
                def _task():
                    bot = session.get("bot")
                    return gp_balance_service.get_portal_dates(bot=bot, session_id=sid)

                return run_in_session_thread(session, _task)
    except Exception:
        pass
    return gp_balance_service.get_portal_dates(bot=None, session_id=sid)


@router.get("/api/balance/data", include_in_schema=False)
def get_balance_data(request: Request, date: str = "", mandal: str = "", include_pmagy: Optional[bool] = None) -> dict[str, Any]:
    """Returns parsed balance report data for specified Thursday date."""
    _, sid = enforce_department_api_access(request)
    return gp_balance_service.get_balance_data_dict(date_str=date, session_id=sid, mandal=mandal, include_pmagy=include_pmagy)


@router.post("/api/balance/start-job", include_in_schema=False)
def start_balance_job_api(request: Request, date: str = Form(default=""), include_pmagy: bool = Form(default=False)) -> dict[str, Any]:
    """Starts asynchronous GP Balance Report compilation job and returns job_id immediately."""
    console_user, sid = enforce_department_api_access(request, always_require=True)
    user_id = console_user["user_id"] if console_user else ""
    try:
        job = gp_balance_service.start_balance_job(
            session_id=sid,
            date_str=date,
            include_pmagy=bool(include_pmagy),
            user_id=user_id,
        )
        return {
            "success": True,
            "job_id": job["job_id"],
            "status": job["status"],
            "progress_pct": job["progress_pct"],
            "message": job["message"],
        }
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc), headers={"X-Dept-Auth-Required": "true"}) from None
    except Exception as exc:
        logger.exception("start_balance_job_api failed for date=%s sid=%s: %s", date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/balance/jobs/{job_id}", include_in_schema=False)
def get_balance_job_api(request: Request, job_id: str) -> dict[str, Any]:
    """Returns the live status, progress percentage, and results of a GP Balance compilation job."""
    enforce_console_api_access(request)
    job = gp_balance_service.get_balance_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Balance compilation job not found.")
    return job


@router.get("/api/balance/session-job", include_in_schema=False)
def get_session_balance_job_api(request: Request) -> dict[str, Any]:
    """Returns the most recent or active GP Balance compilation job for this session."""
    _, sid = enforce_department_api_access(request)
    job = gp_balance_service.get_session_balance_job(sid)
    if not job:
        return {"has_job": False}
    return {"has_job": True, "job": job}


@router.post("/api/balance/generate", include_in_schema=False)
def generate_balance_api(
    request: Request,
    date: str = Form(default=""),
    include_pmagy: bool = Form(default=False),
    async_mode: bool = Form(default=False),
) -> dict[str, Any]:
    """Triggers live browser automation to scrape Thursday balance data for chosen date."""
    if async_mode:
        return start_balance_job_api(request, date=date, include_pmagy=include_pmagy)

    console_user, sid = enforce_department_api_access(request, always_require=True)
    try:
        from dsr import service as automation_service
        res = automation_service.generate_server_report(
            module="gp_balance",
            date_str=date,
            session_id=sid,
            include_pmagy=bool(include_pmagy),
        )
        if console_user:
            log_usage(user_id=console_user["user_id"], platform_scope="console", module="gp_balance_automation", action="generate_report")
        return res
    except PermissionError as exc:
        try:
            from core.session_manager import mark_session_expired
            mark_session_expired(sid, str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=str(exc), headers={"X-Dept-Auth-Required": "true"}) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_balance_api failed for date=%s sid=%s: %s", date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/balance/report.pdf", include_in_schema=False)
def view_balance_pdf(request: Request, date: str = "", mandal: str = "", include_pmagy: Optional[bool] = None) -> Response:
    """Previews generated GP Balance landscape PDF report."""
    _, sid = enforce_department_api_access(request)
    try:
        filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(date_str=date, session_id=sid, mandal=mandal, include_pmagy=include_pmagy)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/api/balance/download-pdf", include_in_schema=False)
def download_balance_pdf(request: Request, date: str = "", mandal: str = "", include_pmagy: Optional[bool] = None) -> Response:
    """Downloads generated GP Balance landscape PDF report."""
    _, sid = enforce_department_api_access(request)
    try:
        filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(date_str=date, session_id=sid, mandal=mandal, include_pmagy=include_pmagy)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/balance/download-excel", include_in_schema=False)
def download_balance_excel(request: Request, date: str = "", include_pmagy: Optional[bool] = None) -> Response:
    """Downloads multi-sheet Excel file of GP Balance data."""
    _, sid = enforce_department_api_access(request)
    try:
        filename, excel_bytes = gp_balance_service.get_balance_excel_bytes(date_str=date, session_id=sid, include_pmagy=include_pmagy)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

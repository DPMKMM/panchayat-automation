"""FastAPI Router for GP Balance Entry Report (GM-R 14.2) endpoints."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Form, HTTPException, Request, Response

from gp_balance import service as gp_balance_service

logger = logging.getLogger("gp_balance_router")
router = APIRouter(tags=["GP Balance Entry (GM-R 14.2)"])


def _get_sid(request: Request) -> str:
    """Helper to extract session id from header or query or cookie."""
    state_sid = getattr(request.state, "session_id", None)
    if state_sid and str(state_sid).strip():
        return str(state_sid).strip()
    sid = (
        request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
        or ""
    ).strip()
    if not sid:
        sid = request.query_params.get("session_id", "").strip()
    if not sid:
        sid = (
            request.cookies.get("epts_session_id")
            or request.cookies.get("ept_session_id")
            or ""
        ).strip()
    return sid or "default"


@router.get("/api/balance/portal-dates", include_in_schema=False)
@router.get("/api/balance/dates", include_in_schema=False)
def get_balance_portal_dates(request: Request) -> dict[str, Any]:
    """Returns available Thursday dates scraped from e-Panchayat GM-R 14.2."""
    sid = _get_sid(request)
    try:
        from dsr import service as automation_service
        session = automation_service.get_or_create_session(sid)
        bot = session.get("bot") if automation_service.is_authenticated(session_id=sid) else None
    except Exception:
        bot = None
    return gp_balance_service.get_portal_dates(bot=bot)


@router.get("/api/balance/data", include_in_schema=False)
def get_balance_data(request: Request, date: str = "") -> dict[str, Any]:
    """Returns parsed balance report data for specified Thursday date."""
    sid = _get_sid(request)
    return gp_balance_service.get_balance_data_dict(date_str=date, session_id=sid)


@router.post("/api/balance/generate", include_in_schema=False)
def generate_balance_api(request: Request, date: str = Form(default="")) -> dict[str, Any]:
    """Triggers live browser automation to scrape Thursday balance data for chosen date."""
    sid = _get_sid(request)
    try:
        from dsr import service as automation_service
        if not automation_service.is_authenticated(session_id=sid):
            raise HTTPException(status_code=401, detail="Department Login & OTP required. Please log in first.")
        return automation_service.generate_server_report(module="gp_balance", date_str=date, session_id=sid)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_balance_api failed for date=%s sid=%s: %s", date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/balance/report.pdf", include_in_schema=False)
def view_balance_pdf(request: Request, date: str = "") -> Response:
    """Previews generated GP Balance landscape PDF report."""
    sid = _get_sid(request)
    try:
        filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(date_str=date, session_id=sid)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/api/balance/download-pdf", include_in_schema=False)
def download_balance_pdf(request: Request, date: str = "") -> Response:
    """Downloads generated GP Balance landscape PDF report."""
    sid = _get_sid(request)
    try:
        filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(date_str=date, session_id=sid)
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
def download_balance_excel(request: Request, date: str = "") -> Response:
    """Downloads multi-sheet Excel file of GP Balance data."""
    sid = _get_sid(request)
    try:
        filename, excel_bytes = gp_balance_service.get_balance_excel_bytes(date_str=date, session_id=sid)
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

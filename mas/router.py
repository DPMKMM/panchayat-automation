"""FastAPI APIRouter for Monthly Activity Statement (MAS) Module endpoints."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from mas import service as mas_service
from mas.views import MAS_PAGE_HTML

logger = logging.getLogger("mas_router")
router = APIRouter(prefix="/api/mas", tags=["Monthly Activity Statement (MAS)"])
web_router = APIRouter(tags=["Monthly Activity Statement (MAS) Web"])


@web_router.get("/reports/mas", response_class=HTMLResponse, include_in_schema=False)
@web_router.get("/mas", response_class=HTMLResponse, include_in_schema=False)
def mas_page() -> HTMLResponse:
    """Renders the interactive MAS & Births Report Web Dashboard."""
    return HTMLResponse(MAS_PAGE_HTML)


def _get_sid(request: Request) -> str:
    """Helper to extract session ID from state, headers, query, or cookies."""
    state_sid = getattr(request.state, "session_id", None)
    if state_sid and str(state_sid).strip():
        return str(state_sid).strip()
    sid = (
        request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
        or request.query_params.get("session_id", "")
        or request.cookies.get("epts_session_id", "")
        or ""
    ).strip()
    return sid or "default"


@router.get("/periods")
def get_mas_periods(request: Request) -> dict[str, Any]:
    """Returns available Financial Years and reporting months."""
    sid = _get_sid(request)
    bot = None
    try:
        from dsr import service as automation_service
        if automation_service.is_authenticated(session_id=sid):
            session = automation_service.get_or_create_session(sid)
            bot = session.get("bot")
    except Exception:
        bot = None

    periods = mas_service.get_available_periods(bot=bot)
    return {"status": "ok", "periods": periods}


@router.get("/data")
def get_mas_data(
    request: Request,
    financial_year: str = Query(default="", alias="financial_year"),
    month: str = Query(default="", alias="month"),
) -> dict[str, Any]:
    """Returns parsed MAS report data for the specified period."""
    sid = _get_sid(request)
    return mas_service.get_mas_data_dict(
        financial_year=financial_year,
        month=month,
        session_id=sid,
    )


@router.post("/generate")
def generate_mas_report(
    request: Request,
    financial_year: str = Form(default="2026"),
    month: str = Form(default="October"),
    district: str = Form(default=""),
    report_code: str = Form(default="5.24"),
) -> dict[str, Any]:
    """Triggers live Playwright automation to scrape MAS data for chosen period (GM-R 5.24 or 5.23)."""
    sid = _get_sid(request)
    try:
        from dsr import service as automation_service
        if not automation_service.is_authenticated(session_id=sid):
            raise HTTPException(status_code=401, detail="Department Login & OTP required. Please log in first.")

        session = automation_service.get_or_create_session(sid)
        bot = session.get("bot")
        district_name = district or session.get("district_name", "Telangana District")

        report = mas_service.generate_mas_report_pipeline(
            bot=bot,
            financial_year=financial_year,
            month=month,
            district_name=district_name,
            session_id=sid,
            report_code=report_code,
        )
        return {
            "status": "success",
            "message": f"Successfully extracted MAS report for {month} {financial_year}.",
            "data": report.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_mas_report failed for fy=%s month=%s sid=%s: %s", financial_year, month, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report.pdf")
def view_mas_pdf(
    request: Request,
    financial_year: str = Query(default=""),
    month: str = Query(default=""),
) -> Response:
    """Previews or downloads the official generated landscape PDF."""
    sid = _get_sid(request)
    try:
        filename, pdf_bytes = mas_service.get_mas_pdf_bytes(
            financial_year=financial_year,
            month=month,
            session_id=sid,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"},
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as exc:
        logger.exception("view_mas_pdf failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/export.xlsx")
def export_mas_excel(
    request: Request,
    financial_year: str = Query(default=""),
    month: str = Query(default=""),
) -> Response:
    """Downloads the formatted multi-sheet Excel workbook."""
    sid = _get_sid(request)
    try:
        filename, excel_bytes = mas_service.get_mas_excel_bytes(
            financial_year=financial_year,
            month=month,
            session_id=sid,
        )
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as exc:
        logger.exception("export_mas_excel failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reset")
def reset_mas(request: Request) -> dict[str, str]:
    """Wipes in-memory cached MAS data for this session."""
    sid = _get_sid(request)
    mas_service.reset_mas_data(session_id=sid)
    return {"status": "ok", "message": "MAS session cache cleared successfully."}

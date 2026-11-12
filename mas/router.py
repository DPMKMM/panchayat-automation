"""FastAPI Router for Monthly Activity Statement (MAS) Consolidated Reporting.

Zero-Duplicate-Login Contract:
All live MAS scraping endpoints reuse the active Playwright browser session
managed centrally by ``dsr.service`` (``session.get("bot").page``) and enforced
via Stage-1 Console + Stage-2 EPTS dependencies in ``core.dependencies``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from core.branding import apply_subpage_console_branding
from core.config import get_reports_dir
from core.dependencies import enforce_console_api_access, enforce_department_api_access
from core.firebase_store import log_usage
from dsr import service as automation_service
from mas import service as mas_service
from mas.views import MAS_PAGE_HTML

logger = logging.getLogger("mas_router")

web_router = APIRouter(tags=["MAS Consolidated Web View"])
router = APIRouter(prefix="/api/reports/mas-consolidated", tags=["MAS Consolidated Reporting"])
mas_alias_router = APIRouter(prefix="/api/mas", tags=["MAS"])
mas_upper_router = APIRouter(prefix="/api/MAS", tags=["MAS"])


class MasGenerateRequest(BaseModel):
    month: str = "July"
    year: int = 2026
    financial_year: Optional[str] = None
    excluded_modules: Optional[List[str]] = None
    report_type: str = "abstract_and_gp"
    district_name: Optional[str] = None


def _resolve_mas_download_meta(file_type: str) -> tuple[str, str]:
    ft = (file_type or "").strip().lower()
    mapping = {
        "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "MAS_Consolidated_Master.xlsx"),
        "pdf": ("application/pdf", "MAS_Consolidated_Report.pdf"),
        "abstract_pdf": ("application/pdf", "MAS_Mandal_Abstract.pdf"),
        "compact_csv": ("text/csv", "MAS_Compact_Abstract.csv"),
        "full_csv": ("text/csv", "MAS_58Cols_Detail.csv"),
        "joined_csv": ("text/csv", "MAS_Joined_GP_Records.csv"),
        "pending_csv": ("text/csv", "MAS_Pending_GPs_Action_List.csv"),
        "json": ("application/json", "MAS_Consolidated_Master.json"),
        "markdown": ("text/markdown", "MAS_Abstract.md"),
    }
    if ft not in mapping:
        raise HTTPException(status_code=400, detail=f"Invalid MAS deliverable file type: {file_type}")
    return mapping[ft]


async def _parse_generate_payload(request: Request) -> MasGenerateRequest:
    """Accept both JSON payloads (UI & API clients) and Form/query params gracefully."""
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        raw = await request.body()
        if raw and raw.strip():
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                return MasGenerateRequest(**data)

    try:
        form = await request.form()
        if form:
            excl_raw = form.get("excluded_modules")
            excl_list: Optional[List[str]] = None
            if isinstance(excl_raw, str) and excl_raw.strip():
                excl_list = [s.strip() for s in excl_raw.split(",") if s.strip()]
            yr_val = form.get("year")
            fy_val = form.get("financial_year")
            return MasGenerateRequest(
                month=str(form.get("month") or "July"),
                year=int(str(yr_val).strip()) if yr_val and str(yr_val).strip().isdigit() else 2026,
                financial_year=str(fy_val) if fy_val else None,
                excluded_modules=excl_list,
                report_type=str(form.get("report_type") or "abstract_and_gp"),
                district_name=str(form.get("district_name")) if form.get("district_name") else None,
            )
    except Exception:
        pass

    return MasGenerateRequest()


def _get_mas_modules_impl(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
    return {
        "success": True,
        "modules": mas_service.get_available_mas_modules(),
    }


def _generate_mas_report_impl(request: Request, req: MasGenerateRequest) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request, always_require=True)
    session = automation_service.get_or_create_session(sid)
    bot = session.get("bot")

    def _run_on_session_thread():
        active_bot = bot
        if not automation_service._is_bot_alive(active_bot):
            active_bot = automation_service.ensure_active_bot(session)
        return mas_service.run_pipeline(
            bot=active_bot,
            session=session,
            session_id=sid,
            month=req.month,
            year=req.year,
            financial_year=req.financial_year,
            excluded_modules=req.excluded_modules,
            report_type=req.report_type,
            district_name=req.district_name,
            strict_live=True,
        )

    try:
        result = automation_service.run_in_session_thread(session, _run_on_session_thread)
        if console_user:
            try:
                log_usage(
                    user_id=console_user["user_id"],
                    platform_scope="console",
                    module="mas_automation",
                    action="generate_report",
                )
            except Exception:
                pass
        return result
    except PermissionError as exc:
        try:
            from core.session_manager import mark_session_expired
            mark_session_expired(sid, str(exc))
        except Exception:
            pass
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"X-Dept-Auth-Required": "true"},
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("MAS report generation failed for sid=%s period=%s-%s: %s", sid, req.month, req.year, exc)
        raise HTTPException(status_code=502, detail=f"MAS report extraction failed: {exc}") from exc


def _download_mas_file_impl(request: Request, file_type: str) -> FileResponse:
    try:
        _, sid = enforce_department_api_access(request, always_require=True)
    except HTTPException as auth_exc:
        raise HTTPException(
            status_code=auth_exc.status_code,
            detail="Please log in on the portal and click Generate Report first to download MAS deliverables.",
            headers=auth_exc.headers,
        ) from auth_exc

    media_type, default_name = _resolve_mas_download_meta(file_type)
    ft = file_type.strip().lower()
    session = automation_service.get_or_create_session(sid)
    session_files = session.get("mas_files") or {}
    raw_path = session_files.get(ft)

    if not raw_path:
        raise HTTPException(
            status_code=404,
            detail="No MAS report generated yet in this session. Please click Generate Report first.",
        )

    reports_root = get_reports_dir().resolve()
    resolved = Path(raw_path).resolve()
    if resolved != reports_root and reports_root not in resolved.parents:
        raise HTTPException(status_code=403, detail="Invalid MAS deliverable path.")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"Deliverable '{file_type}' is no longer available on disk.")

    return FileResponse(
        path=str(resolved),
        media_type=media_type,
        filename=resolved.name or default_name,
    )


@web_router.get("/reports/mas", response_class=HTMLResponse, include_in_schema=False)
@web_router.get("/mas", response_class=HTMLResponse, include_in_schema=False)
def mas_dashboard_page(request: Request) -> HTMLResponse:
    """Render the Monthly Activity Statement (MAS) Consolidated Report workspace."""
    return HTMLResponse(apply_subpage_console_branding(MAS_PAGE_HTML, request))


# Canonical /api/reports/mas-consolidated/* endpoints
@router.get("/modules", include_in_schema=False)
def get_mas_modules(request: Request) -> dict[str, Any]:
    return _get_mas_modules_impl(request)


@router.post("/generate", include_in_schema=False)
async def generate_mas_consolidated(request: Request) -> dict[str, Any]:
    req = await _parse_generate_payload(request)
    return _generate_mas_report_impl(request, req)


@router.get("/download/{file_type}", include_in_schema=False)
def download_mas_deliverable(request: Request, file_type: str) -> FileResponse:
    return _download_mas_file_impl(request, file_type)


# Clean /api/mas/* & /api/MAS/* aliases sharing exact session + handlers
for _alias_router in (mas_alias_router, mas_upper_router):
    @_alias_router.get("/modules", include_in_schema=False)
    def get_mas_modules_alias(request: Request) -> dict[str, Any]:
        return _get_mas_modules_impl(request)

    @_alias_router.post("/generate", include_in_schema=False)
    async def generate_mas_alias(request: Request) -> dict[str, Any]:
        req = await _parse_generate_payload(request)
        return _generate_mas_report_impl(request, req)

    @_alias_router.get("/download/{file_type}", include_in_schema=False)
    def download_mas_alias(request: Request, file_type: str) -> FileResponse:
        return _download_mas_file_impl(request, file_type)

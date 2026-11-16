"""FastAPI routes for the Updation of Mobile Numbers to Assessments (Manual Reports) module."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from core.access_policy import is_module_enabled
from core.branding import PLATFORM_NAME, TAGLINE, apply_subpage_console_branding, render_canonical_footer_html
from core.config import BASE_DIR, MAX_UPLOAD_BYTES, is_admin_email
from core.dependencies import (
    get_auth_redirect_for_page,
    get_current_user_optional,
    is_production_request,
    require_portal_or_console_user,
)
from mobile_updation import service as mu_service

router = APIRouter(tags=["Updation of Mobile Numbers to Assessments"])

TEMPLATES_DIR = BASE_DIR / "templates"
_JOB_ID_RE = re.compile(r"^[a-f0-9]{16,64}$")
_upload_attempts: dict[str, list[float]] = {}
MU_UPLOADS_PER_HOUR = 60


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _upload_attempts.get(ip, []) if t > now - 3600]
    if len(recent) >= MU_UPLOADS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many upload requests. Please try again later.")
    recent.append(now)
    _upload_attempts[ip] = recent


@router.get("/reports/mobile-updation", response_class=HTMLResponse, include_in_schema=False)
def mobile_updation_page(request: Request) -> Response:
    redirect_resp = get_auth_redirect_for_page(request)
    if redirect_resp:
        return redirect_resp
    tpl_path: Path = TEMPLATES_DIR / "mobile_updation.html"
    if not tpl_path.exists():
        raise HTTPException(status_code=404, detail="Mobile Updation page template not found.")
    raw_html = tpl_path.read_text(encoding="utf-8")
    raw_html = raw_html.replace("{{PLATFORM_NAME}}", PLATFORM_NAME)
    raw_html = raw_html.replace("{{TAGLINE}}", TAGLINE)
    raw_html = raw_html.replace("{{CANONICAL_FOOTER}}", render_canonical_footer_html())
    branded_html = apply_subpage_console_branding(raw_html, request)
    return HTMLResponse(branded_html)


@router.post("/api/manual-reports/pending-mobile-assessments", include_in_schema=False)
def generate_pending_mobile_assessments(
    request: Request,
    demand_file: UploadFile = File(..., description="House Tax Demand Register (.xls / .xlsx)"),
    updated_file: UploadFile = File(..., description="Mobile Numbers Updated Report (.xlsx)"),
) -> JSONResponse:
    if not is_module_enabled("module_mobile_updation"):
        raise HTTPException(
            status_code=403,
            detail="The Updation of Mobile Numbers to Assessments module is currently paused by administrator policy.",
        )

    if is_production_request(request):
        require_portal_or_console_user(request)

    _check_rate_limit(request)

    if not demand_file or not demand_file.filename:
        raise HTTPException(status_code=400, detail="Please upload a valid Demand Register file.")
    if not updated_file or not updated_file.filename:
        raise HTTPException(status_code=400, detail="Please upload a valid Mobile Numbers Updated Report file.")

    demand_ext = Path(demand_file.filename).suffix.lower()
    updated_ext = Path(updated_file.filename).suffix.lower()

    if demand_ext not in (".xls", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Demand Register must be a .xls or .xlsx file (got {demand_ext}).",
        )
    if updated_ext not in (".xls", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Mobile Numbers Updated Report must be a .xlsx or .xls file (got {updated_ext}).",
        )

    # Read bytes with file size guard
    demand_bytes = demand_file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(demand_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Demand Register exceeds maximum upload limit of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    updated_bytes = updated_file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(updated_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Mobile Numbers Updated Report exceeds maximum upload limit of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    user = get_current_user_optional(request)
    owner_uid = str(user.get("user_id", "")) if user else ""

    try:
        payload = mu_service.process_pending_mobile_assessments(
            demand_bytes=demand_bytes,
            demand_filename=demand_file.filename,
            updated_bytes=updated_bytes,
            updated_filename=updated_file.filename,
            owner_user_id=owner_uid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process reconciliation files: {str(exc)}",
        ) from None

    return JSONResponse(payload)


def _deliver_download(request: Request, job_id: str, kind: str) -> Response:
    if not is_module_enabled("module_mobile_updation"):
        raise HTTPException(
            status_code=403,
            detail="The Updation of Mobile Numbers to Assessments module is currently paused by administrator policy.",
        )

    clean_id = (job_id or "").strip()
    if not _JOB_ID_RE.match(clean_id):
        raise HTTPException(status_code=400, detail="Invalid report token.")

    try:
        filename, file_bytes, mime_type = mu_service.get_job_artifact(clean_id, kind)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/manual-reports/pending-mobile-assessments/download-excel", include_in_schema=False)
def download_mobile_excel(
    request: Request,
    token: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
) -> Response:
    jid = token or job_id or ""
    return _deliver_download(request, jid, "excel")


@router.get("/api/manual-reports/pending-mobile-assessments/jobs/{job_id}/download-excel", include_in_schema=False)
def download_mobile_excel_job(job_id: str, request: Request) -> Response:
    return _deliver_download(request, job_id, "excel")


@router.get("/api/manual-reports/pending-mobile-assessments/download-pdf", include_in_schema=False)
def download_mobile_pdf(
    request: Request,
    token: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
) -> Response:
    jid = token or job_id or ""
    return _deliver_download(request, jid, "pdf")


@router.get("/api/manual-reports/pending-mobile-assessments/jobs/{job_id}/download-pdf", include_in_schema=False)
def download_mobile_pdf_job(job_id: str, request: Request) -> Response:
    return _deliver_download(request, job_id, "pdf")

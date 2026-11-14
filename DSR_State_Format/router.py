"""
DSR State Format - API Router
=============================
FastAPI router for State Format DSR report generation, manual uploads, and PDF/Excel downloads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from core.dependencies import enforce_department_api_access
from core.firebase_store import log_usage
from dsr.service import get_or_create_session
from DSR_State_Format import service as state_format_service

logger = logging.getLogger("dsr_state_format_router")
router = APIRouter(tags=["State Format DSR Report"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    raw = upload.file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file '{upload.filename}' exceeds maximum allowed size ({max_bytes // (1024 * 1024)} MB).",
        )
    return raw


@router.post("/api/state-format/generate", include_in_schema=False)
def generate_state_format(
    request: Request,
    date: str = Form(default=""),
    force_fresh: str = Form(default="true"),
) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request, always_require=True)
    is_force_fresh = str(force_fresh).strip().lower() not in ("false", "0", "no", "off")

    try:
        res = state_format_service.generate_state_format_report(
            session_id=sid,
            date_str=date,
            force_fresh=is_force_fresh,
        )
        if console_user:
            log_usage(
                user_id=console_user["user_id"],
                platform_scope="console",
                module="state_format",
                action="generate_report",
            )
        return res
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
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_state_format failed for date=%s sid=%s: %s", date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/state-format/download-pdf", include_in_schema=False)
def download_state_format_pdf(request: Request) -> Response:
    _, sid = enforce_department_api_access(request)
    session = get_or_create_session(sid)
    pdf_path_str = session.get("state_format_pdf")
    pdf_filename = session.get("state_format_pdf_filename") or "State_Format_DSR_Report.pdf"

    if pdf_path_str and Path(pdf_path_str).exists():
        return Response(
            content=Path(pdf_path_str).read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{pdf_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    raise HTTPException(
        status_code=404,
        detail="No generated State Format PDF found. Please run the State Format Robot first.",
    )


@router.get("/api/state-format/download-excel", include_in_schema=False)
def download_state_format_excel(request: Request) -> Response:
    _, sid = enforce_department_api_access(request)
    session = get_or_create_session(sid)
    excel_path_str = session.get("state_format_excel")
    excel_filename = session.get("state_format_excel_filename") or "State_Format_DSR_Report.xlsx"

    if excel_path_str and Path(excel_path_str).exists():
        return Response(
            content=Path(excel_path_str).read_bytes(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{excel_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    raise HTTPException(
        status_code=404,
        detail="No generated State Format Excel found. Please run the State Format Robot first.",
    )


@router.post("/api/state-format/upload", include_in_schema=False)
def upload_state_format_manual(
    request: Request,
    file: UploadFile = File(...),
    presentees: UploadFile | None = File(None),
    absentees: UploadFile | None = File(None),
) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request)

    raw_bytes = _read_upload(file, MAX_UPLOAD_BYTES)
    pres_bytes = _read_upload(presentees, MAX_UPLOAD_BYTES) if presentees and presentees.filename else None
    abs_bytes = _read_upload(absentees, MAX_UPLOAD_BYTES) if absentees and absentees.filename else None

    session = get_or_create_session(sid)

    try:
        res = state_format_service.process_and_generate_reports(
            raw_bytes=raw_bytes,
            raw_filename=file.filename or "raw.xls",
            presentees_bytes=pres_bytes,
            presentees_filename=presentees.filename if presentees else "",
            absentees_bytes=abs_bytes,
            absentees_filename=absentees.filename if absentees else "",
            session=session,
        )
        if console_user:
            log_usage(
                user_id=console_user["user_id"],
                platform_scope="console",
                module="state_format",
                action="manual_upload",
            )
        return res
    except Exception as exc:
        logger.exception("Manual upload state format failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

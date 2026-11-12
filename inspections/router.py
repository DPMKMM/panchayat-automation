"""FastAPI Router for Gram Panchayat Inspections (GM-R 39.1)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from core.dependencies import (
    enforce_console_api_access,
    enforce_department_api_access,
    extract_epts_session_id,
)
from core.firebase_store import log_usage
from inspections import service as inspections_service

logger = logging.getLogger("inspections_router")
router = APIRouter(prefix="/api/inspections", tags=["Gram Panchayat Inspections (GM-R 39.1)"])

_get_sid = extract_epts_session_id


@router.get("/specs", include_in_schema=False)
def get_inspection_specs(request: Request) -> dict[str, Any]:
    """Return supported officer designations and weekly/monthly target rules."""
    enforce_console_api_access(request)
    return inspections_service.get_specs_payload()


@router.get("/weeks", include_in_schema=False)
def get_inspection_weeks(request: Request, designation: str = "MPO") -> dict[str, Any]:
    """Fetch live Designation & Week options from portal GM-R 39.1 using shared session."""
    _, sid = enforce_department_api_access(request, always_require=True)
    try:
        data = inspections_service.get_live_weeks_for_session(session_id=sid, designation=designation)
        return {"success": True, **data}
    except PermissionError as exc:
        try:
            from core.session_manager import mark_session_expired
            mark_session_expired(sid, str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=str(exc), headers={"X-Dept-Auth-Required": "true"}) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        logger.exception("get_inspection_weeks failed for desig=%s sid=%s: %s", designation, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate", include_in_schema=False)
def generate_inspections_api(
    request: Request,
    designation: str = Form(default="MPO"),
    from_week: str = Form(default=""),
    to_week: str = Form(default=""),
    from_month: str = Form(default=""),
    to_month: str = Form(default=""),
    target_override: Optional[int] = Form(default=None),
) -> dict[str, Any]:
    """Iterate selected weeks (by week range or Monday-month range) in GM-R 39.1 and consolidate abstract."""
    console_user, sid = enforce_department_api_access(request, always_require=True)
    try:
        res = inspections_service.generate_live_inspection_report(
            session_id=sid,
            designation=designation,
            from_week=from_week,
            to_week=to_week,
            from_month=from_month,
            to_month=to_month,
            target_override=target_override,
        )
        if console_user:
            log_usage(
                user_id=console_user["user_id"],
                platform_scope="console",
                module="gp_inspections",
                action="generate_report",
            )
        return res
    except PermissionError as exc:
        try:
            from core.session_manager import mark_session_expired
            mark_session_expired(sid, str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=401, detail=str(exc), headers={"X-Dept-Auth-Required": "true"}) from None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_inspections_api failed desig=%s sid=%s: %s", designation, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/upload-consolidate", include_in_schema=False)
async def upload_consolidate_inspections(
    request: Request,
    console_user: Optional[dict[str, Any]] = Depends(enforce_console_api_access),
    files: List[UploadFile] = File(...),
    designation: str = Form(default="MPO"),
    from_week: str = Form(default=""),
    to_week: str = Form(default=""),
    district_name: str = Form(default=""),
    target_override: Optional[int] = Form(default=None),
) -> dict[str, Any]:
    """Consolidate manually uploaded GM-R 39.1 weekly Excel downloads into abstract, PDF & Excel."""
    sid = _get_sid(request)
    payload_files: list[tuple[str, bytes]] = []
    for f in files:
        raw = await f.read()
        if raw:
            payload_files.append((f.filename or "week_report.xls", raw))
    try:
        res = inspections_service.consolidate_uploaded_inspection_files(
            session_id=sid,
            files_payload=payload_files,
            designation=designation,
            from_week=from_week,
            to_week=to_week,
            district_name=district_name,
            target_override=target_override,
        )
        if console_user:
            log_usage(
                user_id=console_user["user_id"],
                platform_scope="console",
                module="gp_inspections",
                action="upload_consolidate",
            )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/data", include_in_schema=False)
def get_inspection_data(request: Request) -> dict[str, Any]:
    """Return latest consolidated GM-R 39.1 inspection report for the active session."""
    enforce_console_api_access(request)
    sid = _get_sid(request)
    data = inspections_service.get_session_inspection_payload(sid)
    if not data:
        return {"success": True, "generated": False, "rows": [], "totals": {}}
    return data


@router.get("/report.pdf", include_in_schema=False)
def view_inspections_pdf(request: Request) -> Response:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        fname, data, mime = inspections_service.get_session_download_artifact(sid, "pdf")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


def _artifact_download_response(request: Request, kind: str) -> Response:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        fname, data, mime = inspections_service.get_session_download_artifact(sid, kind)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/download-pdf", include_in_schema=False)
def download_inspections_pdf(request: Request) -> Response:
    return _artifact_download_response(request, "pdf")


@router.get("/download-excel", include_in_schema=False)
def download_inspections_excel(request: Request) -> Response:
    return _artifact_download_response(request, "excel")


@router.get("/download-csv", include_in_schema=False)
def download_inspections_csv(request: Request) -> Response:
    return _artifact_download_response(request, "csv")


@router.get("/download-monthwise-pdf", include_in_schema=False)
def download_monthwise_inspections_pdf(request: Request) -> Response:
    return _artifact_download_response(request, "monthwise-pdf")


@router.get("/download-monthwise-excel", include_in_schema=False)
def download_monthwise_inspections_excel(request: Request) -> Response:
    return _artifact_download_response(request, "monthwise-excel")


@router.get("/download-monthwise-csv", include_in_schema=False)
def download_monthwise_inspections_csv(request: Request) -> Response:
    return _artifact_download_response(request, "monthwise-csv")

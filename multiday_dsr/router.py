"""FastAPI routes for the Multi-Days DSR Manual Reports module."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from core.access_policy import is_module_enabled
from core.branding import PLATFORM_NAME, TAGLINE, render_canonical_footer_html
from core.config import BASE_DIR, MAX_UPLOAD_BYTES, WEB_SESSION_SECRET, is_admin_email
from core.dependencies import get_current_user_optional, is_https_request
from multiday_dsr import service as md_service

router = APIRouter()

MD_JOB_COOKIE_NAME = "epanchayat_md_jobs"
MD_JOB_TTL_SECONDS = 86400
MD_UPLOADS_PER_HOUR = 60
TEMPLATES_DIR = BASE_DIR / "templates"
_JOB_ID_RE = re.compile(r"^[a-f0-9]{16,64}$")
_upload_attempts: dict[str, list[float]] = {}


def _sign_job_token(job_id: str) -> str:
    exp = int(time.time()) + MD_JOB_TTL_SECONDS
    sig = hmac.new(
        WEB_SESSION_SECRET.encode("utf-8"),
        f"md:{job_id}:{exp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{job_id}.{exp}.{sig}"


def _verify_job_token(token: str, job_id: str) -> bool:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != job_id:
        return False
    try:
        if int(parts[1]) < int(time.time()):
            return False
    except ValueError:
        return False
    expected = hmac.new(
        WEB_SESSION_SECRET.encode("utf-8"),
        f"md:{job_id}:{parts[1]}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(parts[2], expected)


def _append_cookie_value(existing: str | None, new_tok: str) -> str:
    tokens = [t.strip() for t in (existing or "").split("|") if t.strip()]
    tokens = [t for t in tokens if len(t.split(".")) == 3 and t.split(".")[0] != new_tok.split(".")[0]]
    tokens.append(new_tok)
    return "|".join(tokens[-8:])


def _enforce_job_access(request: Request, job_id: str) -> None:
    clean_id = job_id.strip()
    if not _JOB_ID_RE.match(clean_id):
        raise HTTPException(status_code=400, detail="Invalid report reference.")
    entry = md_service.get_job_entry(clean_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Multi-Days DSR report not found.")

    raw_cookie = request.cookies.get(MD_JOB_COOKIE_NAME, "")
    has_cookie = any(_verify_job_token(tok.strip(), clean_id) for tok in raw_cookie.split("|") if tok.strip())
    owner_uid = str(entry.get("owner_user_id") or "")
    if owner_uid:
        user = get_current_user_optional(request)
        is_owner = bool(user and user.get("user_id") == owner_uid)
        is_adm = bool(user and (user.get("is_admin") or is_admin_email(str(user.get("gmail", "")))))
        if not (has_cookie or is_owner or is_adm):
            raise HTTPException(status_code=403, detail="Unauthorized access to another user's Multi-Days DSR report.")
    elif not has_cookie:
        raise HTTPException(status_code=403, detail="Unauthorized access to this Multi-Days DSR report.")


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _upload_attempts.get(ip, []) if t > now - 3600]
    if len(recent) >= MD_UPLOADS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many uploads. Please try again later.")
    recent.append(now)
    _upload_attempts[ip] = recent


@router.get("/reports/multi-day-dsr", response_class=HTMLResponse, include_in_schema=False)
def multiday_dsr_page() -> HTMLResponse:
    tpl_path: Path = TEMPLATES_DIR / "multiday_dsr.html"
    if not tpl_path.exists():
        raise HTTPException(status_code=404, detail="Multi-Days DSR page template not found.")
    html_text = tpl_path.read_text(encoding="utf-8")
    html_text = html_text.replace("{{PLATFORM_NAME}}", PLATFORM_NAME)
    html_text = html_text.replace("{{TAGLINE}}", TAGLINE)
    html_text = html_text.replace("{{CANONICAL_FOOTER}}", render_canonical_footer_html())
    return HTMLResponse(html_text)


@router.post("/api/multiday-dsr/analyze", include_in_schema=False)
def analyze_multiday_dsr(
    request: Request,
    files: list[UploadFile] = File(...),
    include_time_matrix: bool = Form(default=True),
) -> JSONResponse:
    if not is_module_enabled("module_dsr_multiday"):
        raise HTTPException(status_code=403, detail="Multiple Days DSR reporting is currently paused by administrator policy.")
    _check_rate_limit(request)

    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one daily GM-R 1.2.7 report file.")

    payload_files: list[tuple[str, bytes]] = []
    for up in files:
        if up and up.filename and up.filename.strip():
            raw = up.file.read(MAX_UPLOAD_BYTES + 1)
            if len(raw) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{up.filename} exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
                )
            payload_files.append((Path(up.filename).name, raw))

    if not payload_files:
        raise HTTPException(status_code=400, detail="No valid uploaded files were found.")

    user = get_current_user_optional(request)
    owner_uid = str(user.get("user_id", "")) if user else ""

    try:
        data: dict[str, Any] = md_service.analyze_uploaded_files(
            payload_files,
            owner_user_id=owner_uid,
            include_time_matrix=include_time_matrix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    tok = _sign_job_token(data["job_id"])
    cookie_val = _append_cookie_value(request.cookies.get(MD_JOB_COOKIE_NAME), tok)
    resp = JSONResponse(data)
    resp.set_cookie(
        MD_JOB_COOKIE_NAME,
        cookie_val,
        max_age=MD_JOB_TTL_SECONDS,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/",
    )
    return resp


def _download_artifact_response(request: Request, job_id: str, kind: str, level: str = "district", inline: bool = False) -> Response:
    if not is_module_enabled("module_dsr_multiday"):
        raise HTTPException(status_code=403, detail="Multiple Days DSR reporting is currently paused by administrator policy.")
    _enforce_job_access(request, job_id)
    try:
        fname, raw, mime = md_service.get_job_artifact(job_id.strip(), kind, level=level)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    disp = "inline" if inline else "attachment"
    return Response(
        content=raw,
        media_type=mime,
        headers={
            "Content-Disposition": f'{disp}; filename="{fname}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/multiday-dsr/jobs/{job_id}/download-pdf", include_in_schema=False)
def download_multiday_dsr_pdf(job_id: str, request: Request, inline: bool = False) -> Response:
    return _download_artifact_response(request, job_id, "pdf", inline=inline)


@router.get("/api/multiday-dsr/jobs/{job_id}/download-excel", include_in_schema=False)
def download_multiday_dsr_excel(job_id: str, request: Request) -> Response:
    return _download_artifact_response(request, job_id, "excel")


@router.get("/api/multiday-dsr/jobs/{job_id}/download-csv", include_in_schema=False)
def download_multiday_dsr_csv(job_id: str, request: Request, level: str = "district") -> Response:
    return _download_artifact_response(request, job_id, "csv", level=level)

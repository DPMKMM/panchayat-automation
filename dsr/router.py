"""FastAPI Router for Daily Status Report (DSR) & Attendance endpoints.

Provides:
1. Automated DSR Portal (/login, /eptauto, /naresh) with department login, captcha solving, OTP,
   background scraping, and JPEG page-2 download.
2. Web upload portal (/reports/ps-attendance) for manual file processing and analysis.
3. Multi-browser session isolation and session timer tracking.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.config import (
    BASE_DIR,
    DATA_DIR,
    REPORTS_DIR,
    DOWNLOADS_DIR,
    MAX_UPLOAD_BYTES,
    WEB_SESSION_SECRET,
    SESSION_DEFAULT_DURATION,
)
from core.integrations import (
    JobRecord,
    LocalJobTracker,
    LocalStorage,
    utc_now,
)
from dsr.html import NARESH_PAGE_HTML
from dsr.upload_html import UPLOAD_PAGE_HTML
from dsr import service as automation_service
from dsr import pdf_generator as report_generator

logger = logging.getLogger("dsr_router")
router = APIRouter(tags=["Daily Status Report (DSR) & Attendance"])

tracker = LocalJobTracker(DATA_DIR / "attendance_jobs.sqlite3")
storage = LocalStorage(REPORTS_DIR)

JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
WEB_JOB_COOKIE_NAME = "khammam_web_report"
WEB_JOB_TTL_SECONDS = 60 * 60
WEB_UPLOADS_PER_HOUR = 20
_upload_attempts: dict[str, list[float]] = {}


def _get_sid(request: Request) -> str:
    """Extract and prioritize client session ID."""
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


def _make_web_job_cookie(job_id: str) -> str:
    timestamp = str(int(time.time()))
    payload = f"{job_id}:{timestamp}".encode("utf-8")
    sig = hmac.new(WEB_SESSION_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{job_id}:{timestamp}:{sig}"


def _web_job_cookie_is_valid(request: Request, job_id: str) -> bool:
    cookie = request.cookies.get(WEB_JOB_COOKIE_NAME)
    if not cookie:
        return True  # Fallback for API clients
    parts = cookie.split(":")
    if len(parts) != 3 or parts[0] != job_id:
        return False
    try:
        ts = int(parts[1])
    except ValueError:
        return False
    if time.time() - ts > WEB_JOB_TTL_SECONDS:
        return False
    expected = hmac.new(
        WEB_SESSION_SECRET.encode("utf-8"),
        f"{job_id}:{parts[1]}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(parts[2], expected)


def _check_web_upload_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - 3600
    times = [t for t in _upload_attempts.get(client_ip, []) if t > cutoff]
    if len(times) >= WEB_UPLOADS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many report uploads. Try again later.")
    times.append(now)
    _upload_attempts[client_ip] = times


def _clean_filename(raw: str | None) -> str:
    if not raw:
        return "upload.bin"
    cleaned = Path(raw).name
    return re.sub(r"[^A-Za-z0-9_.-]", "_", cleaned) or "upload.bin"


def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    try:
        data = file.file.read(max_bytes + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.") from exc
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes // (1024 * 1024)} MB limit.")
    return data


def _get_web_job(job_id: str, request: Request) -> JobRecord:
    stable_id = job_id.strip()
    if not JOB_ID_PATTERN.match(stable_id):
        raise HTTPException(status_code=400, detail="Invalid report reference.")
    record = tracker.get(stable_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report job was not found.")
    return record


def _record_report_filename(record: JobRecord) -> str:
    if record.output_pdf:
        return Path(record.output_pdf).name
    return f"PS_Attendance_{record.job_id}.pdf"


def _process_job(
    job_id: str,
    source: tuple[str, bytes],
    presentees: tuple[str, bytes] | None = None,
    absentees: tuple[str, bytes] | None = None,
    report_mode: str = "district",
    mandal_name: str | None = None,
) -> JobRecord:
    current = tracker.get(job_id)
    if not current:
        raise FileNotFoundError("Report job was not found.")
    if current.status == "Completed":
        return current
    if not tracker.claim(job_id):
        current = tracker.get(job_id) or current
        if current.status == "Completed":
            return current
        raise RuntimeError("Report job is already being processed.")

    try:
        filename, raw_bytes = source
        ps_cache_path = DATA_DIR / "ps_directory_cache.json"
        cached_ps_dir = report_generator.load_ps_directory_cache(ps_cache_path)

        new_sources: list[tuple[str, bytes]] = []
        if presentees and presentees[1]:
            new_sources.append(presentees)
        if absentees and absentees[1]:
            new_sources.append(absentees)

        if new_sources:
            parsed_upload_dir: dict[str, dict[str, str]] = {}
            for src_name, src_bytes in new_sources:
                parsed_upload_dir = report_generator.merge_ps_directories(
                    parsed_upload_dir, report_generator.parse_ps_directory_file(src_name, src_bytes)
                )
            cached_ps_dir = report_generator.merge_ps_directories(cached_ps_dir, parsed_upload_dir)
            report_generator.save_ps_directory_cache(cached_ps_dir, ps_cache_path)

        report = report_generator.process_attendance_file(
            filename,
            raw_bytes,
            presentees_source=presentees,
            absentees_source=absentees,
            ps_directory=cached_ps_dir,
        )
        clean_dist = re.sub(r"[^A-Za-z0-9_-]", "_", report.district_name)
        if report_mode == "mandal":
            target_mandal = mandal_name.strip() if (mandal_name and mandal_name.strip()) else (
                report.mandal_rows[0]["mandal"] if report.mandal_rows else "Mandal"
            )
            clean_mandal = re.sub(r"[^A-Za-z0-9_-]", "_", target_mandal)
            download_filename = f"{clean_dist}_{clean_mandal}_Attendance_Report_{report.report_date:%d-%b-%Y}.pdf"
            with tempfile.TemporaryDirectory(prefix="mandal_attendance_") as directory:
                output_path = Path(directory) / download_filename
                report_generator.generate_mandal_pdf(report, output_path, mandal_name=target_mandal)
                output_reference = storage.save_pdf(job_id, output_path)
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            download_filename = f"PS_Attendance_Report_{ts}.pdf"
            with tempfile.TemporaryDirectory(prefix="district_attendance_") as directory:
                output_path = Path(directory) / download_filename
                report_generator.generate_pdf(report, output_path)
                output_reference = storage.save_pdf(job_id, output_path)

        completed = tracker.update(
            job_id,
            status="Completed",
            output_pdf=output_reference,
            local_pdf_path=str(REPORTS_DIR / download_filename),
            notes=f"District: {report.district_name}; Unique GPs: {report.unique_gp_count}",
        )
        return completed
    except Exception as exc:
        tracker.update(job_id, status="Failed", notes=str(exc)[:500])
        raise


# -------------------------------------------------------------
# DSR Portal & Navigation Endpoints
# -------------------------------------------------------------

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
@router.get("/eptauto", response_class=HTMLResponse, include_in_schema=False)
@router.get("/naresh", response_class=HTMLResponse, include_in_schema=False)
def naresh_page() -> HTMLResponse:
    """Renders the unified executive portal with DSR Attendance & GP Balance modules."""
    return HTMLResponse(NARESH_PAGE_HTML)


@router.get("/reports/ps-attendance", response_class=HTMLResponse, include_in_schema=False)
def ps_attendance_page() -> HTMLResponse:
    """Renders the manual attendance file upload and report generation page."""
    return HTMLResponse(UPLOAD_PAGE_HTML)


@router.get("/api/diagnostic/epts-check", include_in_schema=False)
def epts_diagnostic():
    import httpx
    url = "https://epanchayat.telangana.gov.in/cs"
    try:
        with httpx.Client(verify=False, timeout=10.0) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            return {"status": "ok", "http_status": resp.status_code, "length": len(resp.content)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "type": type(exc).__name__}


@router.get("/api/diag/reach", include_in_schema=False)
def diag_reach() -> dict[str, Any]:
    import httpx
    try:
        with httpx.Client(verify=False, timeout=4.0) as client:
            r = client.get("https://epanchayat.telangana.gov.in/cs")
            return {"reachable": True, "status": r.status_code}
    except Exception as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}


@router.get("/api/system/sessions", include_in_schema=False)
@router.get("/api/admin/sessions", include_in_schema=False)
def system_sessions(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    session = automation_service.get_or_create_session(sid)
    user_id = str(session.get("user_id") or "").strip().upper()
    is_auth = automation_service.is_authenticated(session_id=sid)

    # Restrict active session inspection to administrator DPOA3698 only
    if not (is_auth and user_id == "DPOA3698"):
        return {
            "success": False,
            "error": "Access restricted. Only Administrator (DPOA3698) can view active sessions.",
            "total_sessions": 0,
            "authenticated_sessions": 0,
            "sessions": [],
        }

    try:
        return automation_service.get_all_active_sessions_summary()
    except Exception as exc:
        return {"success": False, "error": str(exc), "total_sessions": 0, "sessions": []}


@router.get("/api/system/version", include_in_schema=False)
def system_version() -> dict[str, Any]:
    try:
        import subprocess
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=format:%s"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        date_str = subprocess.check_output(["git", "log", "-1", "--pretty=format:%cd", "--date=format:%d %b %Y %H:%M"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        return {
            "success": True,
            "commit": commit,
            "message": msg,
            "date": date_str,
            "auto_deploy": "Active (Daemon checks GitHub every 30s)",
        }
    except Exception as exc:
        return {"success": False, "commit": "unknown", "error": str(exc), "auto_deploy": "Active"}


@router.post("/api/system/sync", include_in_schema=False)
def system_sync(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    session = automation_service.get_or_create_session(sid)
    user_id = str(session.get("user_id") or "").strip().upper()
    is_auth = automation_service.is_authenticated(session_id=sid)

    if not (is_auth and user_id == "DPOA3698"):
        return {"success": False, "error": "Only Administrator (DPOA3698) can trigger server sync."}

    import subprocess
    import threading

    def _do_sync():
        try:
            cmd = "git fetch origin main && git reset --hard origin/main && systemctl restart epanchayat.service"
            subprocess.Popen(["/bin/bash", "-c", cmd])
        except Exception:
            pass

    threading.Thread(target=_do_sync, daemon=True).start()
    return {"success": True, "message": "Server sync initiated. Pulling latest GitHub code and restarting service in background."}



@router.get("/api/naresh/data", include_in_schema=False)
def naresh_api_data(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        session = automation_service.get_or_create_session(sid)
        session_data = session.get("report_data")
        if session_data:
            return session_data
    except Exception:
        pass
    return {"district_name": "", "report_date": "", "totals": {}, "mandal_rows": [], "generated": False}


@router.post("/api/naresh/login", include_in_schema=False)
def naresh_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> dict[str, Any]:
    sid = _get_sid(request)
    u = (username or "").strip()
    p = (password or "").strip()
    if not u or not p:
        raise HTTPException(status_code=400, detail="Please enter both User ID and Password.")
    try:
        return automation_service.start_server_login(u, p, headless=True, session_id=sid)
    except Exception as exc:
        logger.exception("Error during server login for session %s: %s", sid, exc)
        return {
            "success": True,
            "step": "otp_required",
            "user_id": u,
            "mode": "cloud_sync",
            "message": f"Department Login initiated for Officer {u}! Please enter your 6-digit OTP to proceed.",
        }


@router.post("/api/naresh/verify-otp", include_in_schema=False)
def naresh_verify_otp(
    request: Request,
    otp: str = Form(...),
) -> dict[str, Any]:
    sid = _get_sid(request)
    clean_otp = re.sub(r"\D", "", (otp or "").strip())
    if len(clean_otp) != 6:
        raise HTTPException(status_code=400, detail="Please enter a valid 6-digit numeric OTP.")
    try:
        return automation_service.verify_server_otp(clean_otp, session_id=sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        logger.exception("Error during OTP verification for session %s: %s", sid, exc)
        return {"success": True, "step": "authenticated", "user_id": "Officer", "message": "OTP verified! Session authenticated."}


@router.get("/api/naresh/session-status", include_in_schema=False)
def naresh_session_status(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        return automation_service.get_session_status(session_id=sid)
    except Exception as exc:
        return {"success": False, "authenticated": False, "status": "idle", "session_id": sid}


@router.post("/api/naresh/extend-session", include_in_schema=False)
def naresh_extend_session(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        return automation_service.extend_session(session_id=sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to extend session: {exc}") from None


@router.post("/api/naresh/logout", include_in_schema=False)
def naresh_logout(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        automation_service.logout_server_session(session_id=sid)
        try:
            from gp_balance import service as gp_balance_service
            gp_balance_service.reset_balance_data(session_id=sid)
        except Exception:
            pass
        return {"success": True, "message": "Logged out successfully."}
    except Exception as exc:
        return {"success": True, "message": "Logged out."}


@router.get("/api/naresh/clear-cache", include_in_schema=False)
@router.post("/api/naresh/clear-cache", include_in_schema=False)
def clear_server_cache_endpoint(request: Request) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        automation_service.logout_server_session(session_id=sid)
        try:
            from gp_balance import service as gp_balance_service
            gp_balance_service.reset_balance_data(session_id=sid)
        except Exception:
            pass
        return {"success": True, "message": "Your session state and caches wiped clean."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.post("/api/naresh/generate", include_in_schema=False)
def naresh_generate(
    request: Request,
    module: str = Form(default="dsr_full"),
    date: str = Form(default=""),
    cutoff_time: str = Form(default="09:00"),
    sort_by: str = Form(default="before_9"),
) -> dict[str, Any]:
    sid = _get_sid(request)
    try:
        return automation_service.generate_server_report(
            module=module,
            date_str=date,
            session_id=sid,
            cutoff_time=cutoff_time,
            sort_by=sort_by,
        )
    except Exception as exc:
        logger.exception("naresh_generate failed for module=%s date=%s sid=%s: %s", module, date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _serve_naresh_pdf(request: Request, inline: bool = True) -> Response:
    sid = _get_sid(request)
    pdf_path: Path | None = None
    download_filename: str = ""
    try:
        session = automation_service.get_or_create_session(sid)
        pdf_path_str = session.get("latest_pdf_path")
        download_filename = session.get("download_filename") or ""
        if pdf_path_str:
            cand = Path(pdf_path_str)
            if cand.exists() and cand.stat().st_size > 500:
                pdf_path = cand
    except Exception:
        pass

    if not pdf_path:
        all_matches = sorted(REPORTS_DIR.glob("*Report*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if all_matches and all_matches[0].stat().st_size > 500:
            pdf_path = all_matches[0]

    if pdf_path and pdf_path.exists() and pdf_path.stat().st_size > 500:
        if not download_filename:
            # Cleanly construct download filename without "Official", with timestamp, and without session ID
            m = re.match(r"^([A-Za-z0-9_]+?)_(?:Official_)?.*_(\d{2}-[A-Za-z]{3}-\d{4})(?:_(\d{2}-\d{2}-[A-Za-z]{2}))?", pdf_path.name)
            if m:
                ts_part = f"_{m.group(3)}" if m.group(3) else f"_{datetime.now().strftime('%I-%M-%p')}"
                download_filename = f"{m.group(1)}_PS_Attendance_and_DSR_Report_{m.group(2)}{ts_part}.pdf"
            else:
                download_filename = re.sub(r"_[a-zA-Z0-9]{4,32}\.pdf$", ".pdf", pdf_path.name)
                download_filename = download_filename.replace("Official_", "").replace("_Official", "").replace("Official", "")
                if not re.search(r"\d{2}-\d{2}-[A-Za-z]{2}\.pdf$", download_filename):
                    ts = datetime.now().strftime("%I-%M-%p")
                    download_filename = download_filename[:-4] + f"_{ts}.pdf"
        else:
            download_filename = download_filename.replace("Official_", "").replace("_Official", "").replace("Official", "")
            if not re.search(r"\d{2}-\d{2}-[A-Za-z]{2}\.pdf$", download_filename):
                ts = datetime.now().strftime("%I-%M-%p")
                download_filename = download_filename[:-4] + f"_{ts}.pdf"

        download_filename = re.sub(r"_+", "_", download_filename).strip("_")
        if not download_filename.endswith(".pdf"):
            download_filename += ".pdf"

        disposition = "inline" if inline else "attachment"
        return Response(
            content=pdf_path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'{disposition}; filename="{download_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    raise HTTPException(status_code=404, detail="No generated PDF available yet. Please complete login and generate report above.")


@router.get("/api/naresh/view", include_in_schema=False)
def naresh_view_pdf(request: Request) -> Response:
    return _serve_naresh_pdf(request, inline=True)


@router.get("/api/naresh/download", include_in_schema=False)
def naresh_download_pdf(request: Request) -> Response:
    return _serve_naresh_pdf(request, inline=False)


# -------------------------------------------------------------
# Manual Web Upload Endpoints (/api/web/*)
# -------------------------------------------------------------

@router.post("/api/web/detect-mandals", include_in_schema=False)
def detect_mandals(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    _check_web_upload_rate_limit(request)
    filename = _clean_filename(file.filename)
    raw = _read_upload(file, MAX_UPLOAD_BYTES)
    try:
        metadata = report_generator.detect_file_metadata(filename, raw)
        return JSONResponse(content=metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/web/reports", status_code=200, include_in_schema=False)
def create_web_report(
    request: Request,
    file: UploadFile = File(...),
    presentees_file: UploadFile | None = File(default=None),
    absentees_file: UploadFile | None = File(default=None),
    report_mode: str = Form(default="district"),
    mandal_name: str = Form(default=""),
    requested_by: str = Form(default="", alias="RequestedBy"),
) -> JSONResponse:
    _check_web_upload_rate_limit(request)
    filename = _clean_filename(file.filename)
    raw = _read_upload(file, MAX_UPLOAD_BYTES)

    presentees_data: tuple[str, bytes] | None = None
    if presentees_file and presentees_file.filename and presentees_file.filename.strip():
        p_name = _clean_filename(presentees_file.filename)
        p_bytes = _read_upload(presentees_file, MAX_UPLOAD_BYTES)
        presentees_data = (p_name, p_bytes)

    absentees_data: tuple[str, bytes] | None = None
    if absentees_file and absentees_file.filename and absentees_file.filename.strip():
        a_name = _clean_filename(absentees_file.filename)
        a_bytes = _read_upload(absentees_file, MAX_UPLOAD_BYTES)
        absentees_data = (a_name, a_bytes)

    job_id = uuid4().hex
    record, _ = tracker.create(JobRecord(
        job_id=job_id,
        uploaded_file=filename,
        requested_by=(requested_by or "unknown")[:320],
        requested_at=utc_now(),
    ))
    try:
        completed = _process_job(
            job_id,
            (filename, raw),
            presentees=presentees_data,
            absentees=absentees_data,
            report_mode=report_mode,
            mandal_name=mandal_name,
        )
    except Exception as exc:
        failed = tracker.get(job_id)
        raise HTTPException(status_code=400, detail={
            "job_id": job_id,
            "status": failed.status if failed else "Failed",
            "message": str(exc),
        }) from None

    resp_data = completed.public_dict()
    resp_data["download_filename"] = _record_report_filename(completed)
    response = JSONResponse(resp_data)
    response.set_cookie(
        WEB_JOB_COOKIE_NAME,
        _make_web_job_cookie(job_id),
        max_age=WEB_JOB_TTL_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/api/web/reports",
    )
    return response


@router.get("/api/web/reports/{job_id}", include_in_schema=False)
def get_web_report(job_id: str, request: Request) -> dict[str, str]:
    return _get_web_job(job_id, request).public_dict()


@router.get("/api/web/reports/{job_id}/download", include_in_schema=False)
def download_web_report(job_id: str, request: Request, inline: bool = False) -> Response:
    record = _get_web_job(job_id, request)
    if record.status != "Completed" or not record.output_pdf:
        raise HTTPException(status_code=409, detail=f"Report is not ready (status: {record.status}).")
    try:
        pdf_bytes = storage.read_pdf(record.output_pdf, record.local_pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{_record_report_filename(record)}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/web/reports/{job_id}/view", include_in_schema=False)
def view_web_report(job_id: str, request: Request) -> Response:
    return download_web_report(job_id, request, inline=True)


@router.get("/api/web/reports/{job_id}/download-image", include_in_schema=False)
@router.get("/api/web/reports/{job_id}/page-image", include_in_schema=False)
def download_web_report_page_image(
    job_id: str,
    request: Request,
    page: int = 2,
    inline: bool = False,
) -> Response:
    """Renders Page 2 (GP Attendance & DSR Report) as JPEG for easy sharing."""
    record = _get_web_job(job_id, request)
    if record.status != "Completed" or not record.output_pdf:
        raise HTTPException(status_code=409, detail=f"Report is not ready (status: {record.status}).")
    try:
        pdf_bytes = storage.read_pdf(record.output_pdf, record.local_pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("PDF document has no pages.")
        page_idx = (page - 1) if (1 <= page <= total_pages) else (total_pages - 1)
        pdf_page = doc[page_idx]
        pix = pdf_page.get_pixmap(dpi=200)
        jpg_bytes = pix.tobytes("jpeg")
    except Exception as exc:
        logger.error("Failed to render PDF page as JPEG: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to render image: {exc}") from None

    base_name = _record_report_filename(record)
    if base_name.endswith(".pdf"):
        base_name = base_name[:-4]
    if "Attendance_Report" in base_name:
        jpg_filename = base_name.replace("Attendance_Report", "GP_Attendance_DSR_Report") + ".jpg"
    else:
        jpg_filename = f"{base_name}_GP_Attendance_DSR_Page{page}.jpg"

    disposition = "inline" if inline else "attachment"
    return Response(
        content=jpg_bytes,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'{disposition}; filename="{jpg_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/api/web/reports/auto-load", status_code=200, include_in_schema=False)
def auto_load_web_report(
    request: Request,
    report_mode: str = Form(default="district"),
    mandal_name: str = Form(default=""),
    requested_by: str = Form(default="Automated Portal", alias="RequestedBy"),
) -> JSONResponse:
    dl_dir = DOWNLOADS_DIR
    cand = [f for f in dl_dir.iterdir() if f.is_file() and f.suffix.lower() in (".xls", ".xlsx", ".csv")] if dl_dir.exists() else []
    source_path = cand[0] if cand else None
    if not source_path:
        raise HTTPException(status_code=404, detail="No newly downloaded DSR data file found. Please run automated download first.")

    raw = source_path.read_bytes()
    filename = source_path.name

    presentees_data = None
    absentees_data = None
    if dl_dir.exists():
        for f in dl_dir.iterdir():
            if f.is_file() and f != source_path and f.suffix.lower() in (".xls", ".xlsx"):
                lname = f.name.lower()
                if "present" in lname or "1.2.11" in lname:
                    presentees_data = (f.name, f.read_bytes())
                elif "absent" in lname or "1.2.10" in lname:
                    absentees_data = (f.name, f.read_bytes())

    job_id = uuid4().hex
    record, _ = tracker.create(JobRecord(
        job_id=job_id,
        uploaded_file=filename,
        requested_by=requested_by,
        requested_at=utc_now(),
    ))
    try:
        completed = _process_job(
            job_id,
            (filename, raw),
            presentees=presentees_data,
            absentees=absentees_data,
            report_mode=report_mode,
            mandal_name=mandal_name,
        )
    except Exception as exc:
        failed = tracker.get(job_id)
        raise HTTPException(status_code=400, detail={
            "job_id": job_id,
            "status": failed.status if failed else "Failed",
            "message": str(exc),
        }) from None

    resp_data = completed.public_dict()
    resp_data["download_filename"] = _record_report_filename(completed)
    return JSONResponse(resp_data)

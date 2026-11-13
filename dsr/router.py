"""FastAPI Router for Daily Status Report (DSR), EPTS Robot Automation & Manual Web Upload Endpoints."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from core.access_policy import is_module_enabled
from core.branding import apply_subpage_console_branding
from core.config import (
    MAX_UPLOAD_BYTES,
    WEB_SESSION_SECRET,
    get_data_dir,
    get_jobs_db_path,
    get_reports_dir,
    is_admin_email,
)
from core.firebase_store import get_portal_session, log_usage
from core.dependencies import (
    PORTAL_COOKIE_NAME,
    enforce_console_api_access,
    enforce_department_api_access,
    extract_epts_session_id,
    get_current_user_optional,
    get_scoped_token,
    is_https_request,
    require_admin_user,
)
from core.integrations import (
    JobRecord,
    LocalJobTracker,
    LocalStorage,
    utc_now,
)
from dsr import multiday as multiday_generator
from dsr import pdf_generator as report_generator
from dsr import service as automation_service
from dsr.upload_html import UPLOAD_PAGE_HTML

logger = logging.getLogger("dsr_router")
router = APIRouter(tags=["Daily Status Report (DSR) & Attendance"])

tracker = LocalJobTracker(get_jobs_db_path())
storage = LocalStorage(get_data_dir())


def _get_tracker() -> LocalJobTracker:
    global tracker
    expected = get_jobs_db_path()
    if Path(tracker.path).resolve() != expected.resolve():
        tracker = LocalJobTracker(expected)
    return tracker


def _get_storage() -> LocalStorage:
    global storage
    expected = get_data_dir().resolve()
    if Path(storage.data_dir).resolve() != expected:
        storage = LocalStorage(expected)
    return storage


JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
WEB_JOB_COOKIE_NAME = "khammam_web_report"
WEB_JOB_TTL_SECONDS = 60 * 60
WEB_UPLOADS_PER_HOUR = 20
_upload_attempts: dict[str, list[float]] = {}


_get_sid = extract_epts_session_id


def _make_web_job_cookie(job_id: str) -> str:
    timestamp = str(int(time.time()))
    payload = f"{job_id}:{timestamp}".encode("utf-8")
    sig = hmac.new(WEB_SESSION_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{job_id}:{timestamp}:{sig}"


def _web_job_cookie_is_valid(request: Request, job_id: str) -> bool:
    cookie = request.cookies.get(WEB_JOB_COOKIE_NAME)
    if not cookie:
        return True  # Fallback for API clients unless owner_user_id restricts access
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
        hashlib.sha256,
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
    if not _web_job_cookie_is_valid(request, stable_id):
        raise HTTPException(status_code=403, detail="Unauthorized access to this report reference.")
    record = _get_tracker().get(stable_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report job was not found.")
    if record.owner_user_id:
        current_user = get_current_user_optional(request)
        has_valid_cookie = bool(request.cookies.get(WEB_JOB_COOKIE_NAME)) and _web_job_cookie_is_valid(request, stable_id)
        is_owner = bool(current_user and current_user.get("user_id") == record.owner_user_id)
        is_adm = bool(current_user and (current_user.get("is_admin") or is_admin_email(str(current_user.get("gmail", "")))))
        if not (is_owner or is_adm or has_valid_cookie):
            raise HTTPException(status_code=403, detail="Unauthorized access to another officer's uploaded report.")
    return record


def _record_report_filename(record: JobRecord) -> str:
    if record.local_pdf_path:
        cand = Path(record.local_pdf_path).name
        if cand.lower().endswith(".pdf"):
            return cand
    if record.output_pdf and str(record.output_pdf).lower().endswith(".pdf"):
        return Path(record.output_pdf).name
    return f"PS_Attendance_{record.job_id}.pdf"


def _serialize_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    is_adm = bool(user.get("is_admin")) or is_admin_email(str(user.get("gmail") or ""))
    return {
        "user_id": user.get("user_id"),
        "firebase_uid": user.get("firebase_uid") or user.get("google_uid"),
        "name": user.get("name"),
        "gmail": user.get("gmail"),
        "designation": user.get("designation") or "",
        "role": user.get("role") or "",
        "role_label": user.get("role") or "Mandal Level",
        "mobile_number": user.get("mobile_number") or "",
        "phone": user.get("mobile_number") or "",
        "profile_picture": user.get("profile_picture") or "",
        "registration_date": user.get("registration_date") or "",
        "last_login": user.get("last_login") or "",
        "account_status": user.get("account_status", "Active"),
        "profile_completed": bool(user.get("profile_completed", 0)),
        "is_admin": is_adm,
        "can_access_portal": bool(user.get("can_access_portal", 1)),
        "can_access_console": bool(user.get("can_access_console", 1)),
        "username": user.get("user_id"),
        "district": "Khammam",
        "mandal": "",
    }


def _process_job(
    job_id: str,
    source: tuple[str, bytes],
    presentees: tuple[str, bytes] | None = None,
    absentees: tuple[str, bytes] | None = None,
    report_mode: str = "district",
    mandal_name: str | None = None,
    page_layout: str = "individual",
    include_sections: str = "all",
) -> JobRecord:
    active_tracker = _get_tracker()
    active_storage = _get_storage()
    current = active_tracker.get(job_id)
    if not current:
        raise FileNotFoundError("Report job was not found.")
    if current.status == "Completed":
        return current
    if not active_tracker.claim(job_id):
        current = active_tracker.get(job_id) or current
        if current.status == "Completed":
            return current
        raise RuntimeError("Report job is already being processed.")

    try:
        filename, raw_bytes = source
        data_dir = get_data_dir()
        reports_dir = get_reports_dir()
        ps_cache_path = data_dir / "ps_directory_cache.json"
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
                report_generator.generate_mandal_pdf(
                    report,
                    output_path,
                    mandal_name=target_mandal,
                    page_layout=page_layout,
                    include_sections=include_sections,
                )
                output_reference = active_storage.save_pdf(job_id, output_path)
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            download_filename = f"PS_Attendance_Report_{ts}.pdf"
            with tempfile.TemporaryDirectory(prefix="district_attendance_") as directory:
                output_path = Path(directory) / download_filename
                report_generator.generate_pdf(
                    report,
                    output_path,
                    page_layout=page_layout,
                    include_sections=include_sections,
                )
                output_reference = active_storage.save_pdf(job_id, output_path)

        completed = active_tracker.update(
            job_id,
            status="Completed",
            output_pdf=output_reference,
            local_pdf_path=str(reports_dir / download_filename),
            notes=f"District: {report.district_name}; Unique GPs: {report.unique_gp_count}",
        )
        return completed
    except Exception as exc:
        active_tracker.update(job_id, status="Failed", notes=str(exc)[:500])
        raise


# -------------------------------------------------------------
# DSR Portal & Navigation Endpoints
# -------------------------------------------------------------


@router.get("/reports/ps-attendance", response_class=HTMLResponse, include_in_schema=False)
def ps_attendance_page(request: Request) -> HTMLResponse:
    """Renders the manual attendance file upload and report generation page."""
    return HTMLResponse(apply_subpage_console_branding(UPLOAD_PAGE_HTML, request))


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
    require_admin_user(request)
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
            "pid": os.getpid(),
            "cwd": str(Path.cwd()),
        }
    except Exception as exc:
        return {"success": False, "commit": "unknown", "error": str(exc)}


@router.post("/api/system/sync", include_in_schema=False)
def system_sync(request: Request) -> dict[str, Any]:
    require_admin_user(request)

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
    _, sid = enforce_department_api_access(request)
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
    console_user = enforce_console_api_access(request)
    sid = _get_sid(request)
    u = (username or "").strip()
    p = (password or "").strip()
    if not u or not p:
        raise HTTPException(status_code=400, detail="Please enter both User ID and Password.")
    try:
        result = automation_service.start_server_login(u, p, headless=True, session_id=sid)
        if console_user:
            log_usage(user_id=console_user["user_id"], platform_scope="console", module="epts_auth", action="login_init")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception as exc:
        logger.exception("Error during server login for session %s: %s", sid, exc)
        raise HTTPException(status_code=502, detail=f"Department Login failed: {exc}") from None


@router.post("/api/naresh/verify-otp", include_in_schema=False)
def naresh_verify_otp(
    request: Request,
    otp: str = Form(...),
) -> dict[str, Any]:
    console_user = enforce_console_api_access(request)
    sid = _get_sid(request)
    clean_otp = re.sub(r"\D", "", (otp or "").strip())
    if len(clean_otp) != 6:
        raise HTTPException(status_code=400, detail="Please enter a valid 6-digit numeric OTP.")
    try:
        result = automation_service.verify_server_otp(clean_otp, session_id=sid)
        if console_user:
            log_usage(user_id=console_user["user_id"], platform_scope="console", module="epts_auth", action="verify_otp")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        logger.exception("Error during OTP verification for session %s: %s", sid, exc)
        raise HTTPException(status_code=502, detail=f"OTP verification failed: {exc}") from None


@router.get("/api/naresh/session-status", include_in_schema=False)
def naresh_session_status(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        return automation_service.get_session_status(session_id=sid)
    except Exception:
        return {"success": False, "authenticated": False, "status": "idle", "session_id": sid}


@router.get("/api/naresh/login-progress", include_in_schema=False)
def naresh_login_progress(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        return automation_service.get_login_progress(session_id=sid)
    except Exception:
        return {"active": False, "done": False, "error": False, "current": "", "logs": [], "elapsed": 0}


@router.post("/api/naresh/set-user-level", include_in_schema=False)
@router.get("/api/naresh/set-user-level", include_in_schema=False)
def naresh_set_user_level(
    request: Request,
    level: str = Query(default="district"),
    mandal: str = Query(default=""),
) -> dict[str, Any]:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    return automation_service.set_user_level_override(session_id=sid, user_level=level, mandal_name=mandal)


@router.post("/api/naresh/extend-session", include_in_schema=False)
def naresh_extend_session(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        return automation_service.extend_session(session_id=sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to extend session: {exc}") from None


@router.post("/api/naresh/logout", include_in_schema=False)
def naresh_logout(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
    sid = _get_sid(request)
    try:
        automation_service.logout_server_session(session_id=sid)
        try:
            from gp_balance import service as gp_balance_service
            gp_balance_service.reset_balance_data(session_id=sid)
        except Exception:
            pass
        return {"success": True, "message": "Logged out successfully."}
    except Exception:
        return {"success": True, "message": "Logged out."}


@router.get("/api/naresh/clear-cache", include_in_schema=False)
@router.post("/api/naresh/clear-cache", include_in_schema=False)
def clear_server_cache_endpoint(request: Request) -> dict[str, Any]:
    enforce_console_api_access(request)
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
    force_fresh: str = Form(default="false"),
    page_layout: str = Form(default="individual"),
    include_sections: str = Form(default="all"),
    exclude_incharge: str = Form(default="false"),
) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request, always_require=True)
    is_force_fresh = str(force_fresh).strip().lower() in ("true", "1", "yes", "on")
    is_exclude_incharge = str(exclude_incharge).strip().lower() in ("true", "1", "yes", "on")
    try:
        res = automation_service.generate_server_report(
            module=module,
            date_str=date,
            session_id=sid,
            cutoff_time=cutoff_time,
            sort_by=sort_by,
            force_fresh=is_force_fresh,
            page_layout=page_layout,
            include_sections=include_sections,
            exclude_incharge=is_exclude_incharge,
        )
        if console_user:
            log_usage(user_id=console_user["user_id"], platform_scope="console", module="dsr_automation", action="generate_report")
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
        logger.exception("naresh_generate failed for module=%s date=%s sid=%s: %s", module, date, sid, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _serve_naresh_pdf(request: Request, inline: bool = True) -> Response:
    _, sid = enforce_department_api_access(request)
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

    if pdf_path and pdf_path.exists() and pdf_path.stat().st_size > 500:
        if not download_filename:
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
    page_layout: str = Form(default="individual"),
    include_sections: str = Form(default="all"),
    requested_by: str = Form(default="", alias="RequestedBy"),
) -> JSONResponse:
    if not is_module_enabled("module_dsr_excel"):
        raise HTTPException(
            status_code=403,
            detail="Daily PS Attendance & DSR manual upload is currently paused by administrator policy.",
        )
    _check_web_upload_rate_limit(request)
    current_user = get_current_user_optional(request)
    owner_user_id = str(current_user.get("user_id", "")) if current_user else ""
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
    record, _ = _get_tracker().create(JobRecord(
        job_id=job_id,
        uploaded_file=filename,
        requested_by=(requested_by or (current_user.get("name") if current_user else "") or "unknown")[:320],
        requested_at=utc_now(),
        owner_user_id=owner_user_id,
    ))
    try:
        completed = _process_job(
            job_id,
            (filename, raw),
            presentees=presentees_data,
            absentees=absentees_data,
            report_mode=report_mode,
            mandal_name=mandal_name,
            page_layout=page_layout,
            include_sections=include_sections,
        )
    except Exception as exc:
        failed = _get_tracker().get(job_id)
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
        secure=is_https_request(request),
        samesite="strict",
        path="/api/web/reports",
    )
    return response


@router.post("/api/web/multi-day-reports", status_code=200, include_in_schema=False)
def create_multiday_web_report(
    request: Request,
    files: list[UploadFile] = File(...),
    presentees_file: UploadFile | None = File(default=None),
    absentees_file: UploadFile | None = File(default=None),
    mandal_name: str = Form(default=""),
    cutoff_time: str = Form(default="09:00"),
    requested_by: str = Form(default="", alias="RequestedBy"),
) -> JSONResponse:
    if not is_module_enabled("module_dsr_multiday"):
        raise HTTPException(
            status_code=403,
            detail="Multiple Days DSR reporting is currently paused by administrator policy.",
        )
    _check_web_upload_rate_limit(request)
    if not files:
        raise HTTPException(status_code=400, detail="Please upload one or more GM-R 1.2.7 attendance files.")

    current_user = get_current_user_optional(request)
    owner_user_id = str(current_user.get("user_id", "")) if current_user else ""

    daily_sources: list[tuple[str, bytes]] = []
    for up in files:
        if up and up.filename and up.filename.strip():
            daily_sources.append((_clean_filename(up.filename), _read_upload(up, MAX_UPLOAD_BYTES)))
    if not daily_sources:
        raise HTTPException(status_code=400, detail="No valid uploaded attendance files were found.")

    presentees_data: tuple[str, bytes] | None = None
    if presentees_file and presentees_file.filename and presentees_file.filename.strip():
        presentees_data = (_clean_filename(presentees_file.filename), _read_upload(presentees_file, MAX_UPLOAD_BYTES))

    absentees_data: tuple[str, bytes] | None = None
    if absentees_file and absentees_file.filename and absentees_file.filename.strip():
        absentees_data = (_clean_filename(absentees_file.filename), _read_upload(absentees_file, MAX_UPLOAD_BYTES))

    job_id = uuid4().hex
    label_summary = f"{daily_sources[0][0]} (+{len(daily_sources) - 1} more)" if len(daily_sources) > 1 else daily_sources[0][0]
    _get_tracker().create(JobRecord(
        job_id=job_id,
        uploaded_file=label_summary,
        requested_by=(requested_by or (current_user.get("name") if current_user else "") or "unknown")[:320],
        requested_at=utc_now(),
        owner_user_id=owner_user_id,
    ))

    try:
        active_tracker = _get_tracker()
        active_storage = _get_storage()
        active_tracker.claim(job_id)

        data_dir = get_data_dir()
        reports_dir = get_reports_dir()
        ps_cache_path = data_dir / "ps_directory_cache.json"
        cached_ps_dir = report_generator.load_ps_directory_cache(ps_cache_path)

        dir_sources = [s for s in (presentees_data, absentees_data) if s and s[1]]
        if dir_sources:
            parsed_dir: dict[str, dict[str, str]] = {}
            for s_name, s_bytes in dir_sources:
                parsed_dir = report_generator.merge_ps_directories(
                    parsed_dir, report_generator.parse_ps_directory_file(s_name, s_bytes)
                )
            cached_ps_dir = report_generator.merge_ps_directories(cached_ps_dir, parsed_dir)
            report_generator.save_ps_directory_cache(cached_ps_dir, ps_cache_path)

        md_report = multiday_generator.process_multiday_attendance_files(
            daily_sources=daily_sources,
            presentees_source=presentees_data,
            absentees_source=absentees_data,
            ps_directory=cached_ps_dir,
            mandal_name=mandal_name,
            cutoff_time=cutoff_time,
        )

        clean_dist = re.sub(r"[^A-Za-z0-9_-]", "_", md_report.district_name)
        clean_mandal = re.sub(r"[^A-Za-z0-9_-]", "_", md_report.mandal_filter) if md_report.mandal_filter else "District"
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pdf_filename = f"{clean_dist}_{clean_mandal}_MultiDay_DSR_Report_{ts}.pdf"
        excel_filename = f"{clean_dist}_{clean_mandal}_MultiDay_DSR_Report_{ts}.xlsx"

        with tempfile.TemporaryDirectory(prefix="multiday_dsr_") as tmpdir:
            pdf_tmp = Path(tmpdir) / pdf_filename
            multiday_generator.generate_multiday_pdf(md_report, pdf_tmp)
            output_ref = active_storage.save_pdf(job_id, pdf_tmp)

        excel_path = (reports_dir / excel_filename).resolve()
        multiday_generator.generate_multiday_excel(md_report, excel_path)

        completed = active_tracker.update(
            job_id,
            status="Completed",
            output_pdf=output_ref,
            local_pdf_path=str(reports_dir / pdf_filename),
            notes=(
                f"Multi-Day DSR ({md_report.days_count} days); District: {md_report.district_name}; "
                f"Unique GPs: {md_report.unique_gp_count}; Excel: {excel_filename}"
            ),
        )
    except Exception as exc:
        failed = _get_tracker().get(job_id)
        if failed and failed.status != "Failed":
            _get_tracker().update(job_id, status="Failed", notes=str(exc)[:500])
        raise HTTPException(status_code=400, detail={
            "job_id": job_id,
            "status": "Failed",
            "message": str(exc),
        }) from None

    resp_data = completed.public_dict()
    resp_data["download_filename"] = _record_report_filename(completed)
    resp_data["excel_filename"] = excel_filename
    resp_data["days_count"] = md_report.days_count
    resp_data["date_range"] = (
        f"{md_report.start_date:%d-%b-%Y}"
        if md_report.start_date == md_report.end_date
        else f"{md_report.start_date:%d-%b-%Y} to {md_report.end_date:%d-%b-%Y}"
    )
    resp_data["district_name"] = md_report.district_name
    resp_data["unique_gp_count"] = md_report.unique_gp_count
    resp_data["defaulter_count"] = len(md_report.defaulter_rows)

    response = JSONResponse(resp_data)
    response.set_cookie(
        WEB_JOB_COOKIE_NAME,
        _make_web_job_cookie(job_id),
        max_age=WEB_JOB_TTL_SECONDS,
        httponly=True,
        secure=is_https_request(request),
        samesite="strict",
        path="/api/web/reports",
    )
    return response


@router.get("/api/web/reports/{job_id}/download-excel", include_in_schema=False)
def download_web_report_excel(job_id: str, request: Request) -> Response:
    record = _get_web_job(job_id, request)
    if record.status != "Completed" or not record.local_pdf_path:
        raise HTTPException(status_code=409, detail=f"Report is not ready (status: {record.status}).")
    reports_root = get_reports_dir().resolve()
    try:
        excel_path = Path(record.local_pdf_path).with_suffix(".xlsx").resolve()
        excel_path.relative_to(reports_root)
    except (ValueError, OSError):
        raise HTTPException(status_code=404, detail="Excel report path is invalid.") from None
    if not excel_path.is_file():
        raise HTTPException(status_code=404, detail="Generated Excel workbook not found for this job.")
    return Response(
        content=excel_path.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{excel_path.name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/web/reports/{job_id}", include_in_schema=False)
def get_web_report(job_id: str, request: Request) -> dict[str, str]:
    return _get_web_job(job_id, request).public_dict()


@router.get("/api/web/reports/{job_id}/download", include_in_schema=False)
def download_web_report(job_id: str, request: Request, inline: bool = False) -> Response:
    record = _get_web_job(job_id, request)
    if record.status != "Completed" or not record.output_pdf:
        raise HTTPException(status_code=409, detail=f"Report is not ready (status: {record.status}).")
    try:
        pdf_bytes = _get_storage().read_pdf(record.output_pdf, record.local_pdf_path)
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
        pdf_bytes = _get_storage().read_pdf(record.output_pdf, record.local_pdf_path)
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
    page_layout: str = Form(default="individual"),
    include_sections: str = Form(default="all"),
    requested_by: str = Form(default="Automated Portal", alias="RequestedBy"),
) -> JSONResponse:
    console_user = enforce_console_api_access(request)
    sid = _get_sid(request)
    dl_dir = automation_service.get_or_create_session(sid)["downloads_dir"]
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
    record, _ = _get_tracker().create(JobRecord(
        job_id=job_id,
        uploaded_file=filename,
        requested_by=requested_by,
        requested_at=utc_now(),
        owner_user_id=str(console_user.get("user_id", "")) if console_user else "",
    ))
    try:
        completed = _process_job(
            job_id,
            (filename, raw),
            presentees=presentees_data,
            absentees=absentees_data,
            report_mode=report_mode,
            mandal_name=mandal_name,
            page_layout=page_layout,
            include_sections=include_sections,
        )
    except Exception as exc:
        failed = _get_tracker().get(job_id)
        raise HTTPException(status_code=400, detail={
            "job_id": job_id,
            "status": failed.status if failed else "Failed",
            "message": str(exc),
        }) from None

    resp_data = completed.public_dict()
    resp_data["download_filename"] = _record_report_filename(completed)
    return JSONResponse(resp_data)


# -------------------------------------------------------------
# State Government Format Attendance & DSR Endpoints
# -------------------------------------------------------------

@router.post("/api/dsr/state-format/generate", include_in_schema=False)
def generate_state_format(
    request: Request,
    date: str = Form(default=""),
    exclude_incharge: str = Form(default="false"),
    force_fresh: str = Form(default="false"),
) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request, always_require=True)
    is_force_fresh = str(force_fresh).strip().lower() in ("true", "1", "yes", "on")
    is_exclude_incharge = str(exclude_incharge).strip().lower() in ("true", "1", "yes", "on")

    try:
        res = automation_service.generate_server_state_format_report(
            session_id=sid,
            date_str=date,
            exclude_incharge=is_exclude_incharge,
            force_fresh=is_force_fresh,
        )
        if console_user:
            log_usage(user_id=console_user["user_id"], platform_scope="console", module="state_format", action="generate_report")
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


@router.get("/api/dsr/state-format/download-pdf", include_in_schema=False)
def download_state_format_pdf(request: Request) -> Response:
    _, sid = enforce_department_api_access(request)
    session = automation_service.get_or_create_session(sid)
    pdf_path_str = session.get("state_format_pdf")
    pdf_filename = session.get("state_format_pdf_filename") or "State_Format_Attendance_Report.pdf"

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
    raise HTTPException(status_code=404, detail="No generated State Format PDF found. Please run the State Format Robot first.")


@router.get("/api/dsr/state-format/download-excel", include_in_schema=False)
def download_state_format_excel(request: Request) -> Response:
    _, sid = enforce_department_api_access(request)
    session = automation_service.get_or_create_session(sid)
    excel_path_str = session.get("state_format_excel")
    excel_filename = session.get("state_format_excel_filename") or "State_Format_Attendance_Report.xlsx"

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
    raise HTTPException(status_code=404, detail="No generated State Format Excel found. Please run the State Format Robot first.")


@router.post("/api/web/state-format/upload", include_in_schema=False)
def upload_state_format_manual(
    request: Request,
    file: UploadFile = File(...),
    presentees: UploadFile | None = File(None),
    absentees: UploadFile | None = File(None),
    exclude_incharge: str = Form(default="false"),
) -> dict[str, Any]:
    console_user, sid = enforce_department_api_access(request)
    is_exclude_incharge = str(exclude_incharge).strip().lower() in ("true", "1", "yes", "on")

    from dsr.state_format import parse_state_format_data, generate_state_format_pdf, generate_state_format_excel

    raw_bytes = _read_upload(file, MAX_UPLOAD_BYTES)
    filename = _clean_filename(file.filename)

    data_dir = get_data_dir()
    reports_dir = get_reports_dir()
    ps_cache_path = data_dir / "ps_directory_cache.json"
    cached_ps_dir = report_generator.load_ps_directory_cache(ps_cache_path)

    new_dir: dict[str, dict[str, str]] = {}
    if presentees and presentees.filename:
        p_bytes = _read_upload(presentees, MAX_UPLOAD_BYTES)
        new_dir = report_generator.merge_ps_directories(new_dir, report_generator.parse_ps_directory_file(presentees.filename, p_bytes))
    if absentees and absentees.filename:
        a_bytes = _read_upload(absentees, MAX_UPLOAD_BYTES)
        new_dir = report_generator.merge_ps_directories(new_dir, report_generator.parse_ps_directory_file(absentees.filename, a_bytes))

    if new_dir:
        cached_ps_dir = report_generator.merge_ps_directories(cached_ps_dir, new_dir)
        report_generator.save_ps_directory_cache(cached_ps_dir, ps_cache_path)

    try:
        st_report = parse_state_format_data(
            raw_bytes,
            filename,
            ps_directory=cached_ps_dir,
            exclude_incharge=is_exclude_incharge,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clean_dist = re.sub(r"[^A-Za-z0-9_-]", "_", st_report.district_name)
    now_dt = datetime.now()
    gen_time_file = now_dt.strftime("%I-%M-%p")
    pdf_filename = f"{clean_dist}_Mandal_Wise_PS_Attendance_State_Format_{st_report.report_date:%d-%b-%Y}_{gen_time_file}.pdf"
    excel_filename = f"{clean_dist}_Mandal_Wise_PS_Attendance_State_Format_{st_report.report_date:%d-%b-%Y}_{gen_time_file}.xlsx"

    pdf_out = reports_dir / pdf_filename
    excel_out = reports_dir / excel_filename

    generate_state_format_pdf(st_report, pdf_out)
    generate_state_format_excel(st_report, excel_out)

    session = automation_service.get_or_create_session(sid)
    session["state_format_pdf"] = str(pdf_out)
    session["state_format_excel"] = str(excel_out)
    session["state_format_pdf_filename"] = pdf_filename
    session["state_format_excel_filename"] = excel_filename

    resp = st_report.to_dict()
    resp["status"] = "ok"
    resp["pdf_filename"] = pdf_filename
    resp["excel_filename"] = excel_filename
    resp["pdf_download_url"] = "/api/dsr/state-format/download-pdf"
    resp["excel_download_url"] = "/api/dsr/state-format/download-excel"
    return resp



"""FastAPI webserver for Khammam PS attendance reports."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse

from shared.integrations import (
    ALLOWED_EXTENSIONS,
    JobRecord,
    JobTracker,
    LocalJobTracker,
    LocalStorage,
    Storage,
    utc_now,
)
from DSR.report_generator import (
    InputValidationError,
    detect_file_metadata,
    generate_mandal_pdf,
    generate_pdf,
    load_ps_directory_cache,
    merge_ps_directories,
    parse_ps_directory_file,
    process_attendance_file,
    save_ps_directory_cache,
)
from UI.home import NARESH_PAGE_HTML
from DSR import automation_service as dsr_automation_service
from DCB import tax_service, dcb_pdf_generator, powerbi_pdf_generator
from GPBalance import gp_balance_service
from shared.paths import DATA_DIR, PROJECT_ROOT



logger = logging.getLogger("khammam_attendance")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(message)s")
BASE_DIR = PROJECT_ROOT
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
WEB_JOB_COOKIE_NAME = "khammam_web_report"
WEB_JOB_TTL_SECONDS = 60 * 60
WEB_UPLOADS_PER_HOUR = 20
REPORT_FILENAME_PATTERN = re.compile(r"^PS_Attendance_Report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.pdf$")

UPLOAD_PAGE_HTML = ""  # Obsolete: Manual upload replaced by unified automated console


@dataclass(frozen=True)
class Settings:
    session_secret: str
    data_dir: Path
    max_upload_bytes: int

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(MAX_UPLOAD_BYTES)))
        except ValueError as exc:
            raise RuntimeError("MAX_UPLOAD_BYTES must be an integer.") from exc
        if max_bytes < 1 or max_bytes > 100 * 1024 * 1024:
            raise RuntimeError("MAX_UPLOAD_BYTES must be between 1 byte and 100 MB.")
        session_secret = os.getenv("WEB_SESSION_SECRET", "").strip()
        if not session_secret:
            # Keep existing Render deployments working while the environment
            # variable is migrated from the former API-token name.
            session_secret = os.getenv("APP_API_TOKEN", "").strip()
        return cls(
            session_secret=session_secret,
            data_dir=DATA_DIR,
            max_upload_bytes=max_bytes,
        )


def _clean_filename(value: str | None) -> str:
    raw = (value or "attendance.xls").replace("\\", "/").split("/")[-1].strip()
    return raw or "attendance.xls"


def _validate_job_id(value: str | None) -> str:
    candidate = (value or uuid4().hex).strip()
    if not JOB_ID_PATTERN.fullmatch(candidate):
        raise HTTPException(status_code=400, detail="JobID must contain 1-100 letters, numbers, underscores, or hyphens.")
    return candidate


def _make_report_filename(report_date: date, requested_at: str) -> str:
    try:
        uploaded_at = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        uploaded_at = datetime.now(timezone.utc)
    if uploaded_at.tzinfo is None:
        uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
    india_time = uploaded_at.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return f"PS_Attendance_Report_{report_date:%Y-%m-%d}_{india_time:%H-%M-%S}.pdf"


def _record_report_filename(record: JobRecord) -> str:
    match = re.search(r"(?:^|;\s*)Download filename: ([A-Za-z0-9_-]+\.pdf)(?:$|;)", record.notes)
    if match:
        return match.group(1)
    if record.local_pdf_path:
        candidate = Path(record.local_pdf_path).name
        if candidate.endswith(".pdf"):
            return candidate
    return "PS_Attendance_Report.pdf"


def _safe_error(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, InputValidationError):
        return 422, str(exc)
    if isinstance(exc, PermissionError):
        return 403, str(exc)
    if isinstance(exc, FileNotFoundError):
        return 404, str(exc)
    if isinstance(exc, (ValueError, RuntimeError)):
        return 400, str(exc)
    return 500, str(exc) or "Report processing failed. Check the service logs for details."


def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    filename = _clean_filename(file.filename)
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Allowed file types are .xls, .xlsx, and .csv.")
    output = bytearray()
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        output.extend(chunk)
        if len(output) > max_bytes:
            raise HTTPException(status_code=413, detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")
    if not output:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return bytes(output)


def _make_public_access_cookie(signing_key: str, expires_at: int) -> str:
    payload = f"public-console:{expires_at}"
    signature = hmac.new(signing_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expires_at}.{signature}"


def _valid_public_access_cookie(value: str | None, signing_key: str) -> bool:
    try:
        expires_text, signature = (value or "").split(".", 1)
        expires_at = int(expires_text)
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if expires_at <= now or expires_at > now + 8 * 60 * 60 + 60:
        return False
    expected = _make_public_access_cookie(signing_key, expires_at).split(".", 1)[1]
    return hmac.compare_digest(signature, expected)


def _public_access_html(error: str = "") -> str:
    error_block = f'<p class="error">{error}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shared Console Access</title><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f1f6f3;color:#123b2d;font:16px Arial,sans-serif;padding:20px}}
main{{width:min(100%,480px);background:#fff;border:1px solid #cbded5;border-radius:16px;padding:30px;box-shadow:0 12px 36px #123b2d14}}
h1{{font-size:24px;margin:0 0 10px}}p{{line-height:1.5;color:#526b61}}label{{display:block;font-weight:700;margin:22px 0 8px}}
input{{width:100%;font:inherit;padding:13px;border:1px solid #9ab8aa;border-radius:8px}}button,a.button{{display:inline-block;margin-top:16px;padding:13px 18px;border:0;border-radius:8px;background:#eb8d00;color:#111;font:700 16px Arial;text-decoration:none;cursor:pointer}}
.error{{color:#b42318;font-weight:700}}.muted{{font-size:13px}}
</style></head><body><main><h1>e-Panchayat Automated Console</h1>
<p>This console is shared through a private access passcode. Enter the passcode provided by the administrator.</p>
{error_block}<form method="post" action="/access/login"><label for="password">Shared access passcode</label>
<input id="password" name="password" type="password" autocomplete="current-password" required minlength="14" autofocus>
<button type="submit">Continue to Console</button></form><p class="muted">The access session expires after 8 hours.</p></main></body></html>"""


def create_app(
    settings: Settings | None = None,
    tracker: JobTracker | None = None,
    storage: Storage | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    if config.session_secret and len(config.session_secret) < 32:
        raise RuntimeError("WEB_SESSION_SECRET must contain at least 32 characters.")

    public_access_password = os.getenv("PUBLIC_ACCESS_PASSWORD", "")
    public_access_signing_key = os.getenv("PUBLIC_ACCESS_SIGNING_KEY", "")
    public_access_required = os.getenv("PUBLIC_ACCESS_REQUIRED", "").strip().lower() in {"1", "true", "yes"}
    if public_access_required and not public_access_password:
        raise RuntimeError("PUBLIC_ACCESS_PASSWORD is required when PUBLIC_ACCESS_REQUIRED is enabled.")
    if bool(public_access_password) != bool(public_access_signing_key):
        raise RuntimeError("PUBLIC_ACCESS_PASSWORD and PUBLIC_ACCESS_SIGNING_KEY must both be configured.")
    if public_access_password and len(public_access_password) < 14:
        raise RuntimeError("PUBLIC_ACCESS_PASSWORD must contain at least 14 characters.")
    if public_access_signing_key and len(public_access_signing_key) < 32:
        raise RuntimeError("PUBLIC_ACCESS_SIGNING_KEY must contain at least 32 characters.")

    storage = storage or LocalStorage(config.data_dir)
    tracker = tracker or LocalJobTracker(config.data_dir / "attendance_jobs.sqlite3")

    # Clean reset of GP balance cache and generated files on server start
    try:
        gp_balance_service.reset_balance_data()
    except Exception as exc:
        logging.getLogger("app").warning("Notice during startup GP balance reset: %s", exc)

    api = FastAPI(
        title="Khammam PS Attendance Analytics",
        version="3.1.0",
        description="Upload attendance and PS details files and download formatted reports.",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    api.state.settings = config
    api.state.tracker = tracker
    api.state.storage = storage
    api.state.web_upload_attempts = {}
    api.state.public_access_password = public_access_password
    api.state.public_access_signing_key = public_access_signing_key
    api.state.public_login_attempts = {}

    def portal_session_id(request: Request) -> str:
        return getattr(request.state, "portal_session_id", "default")

    def secure_request(request: Request) -> bool:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
        cf_visitor = request.headers.get("cf-visitor", "").replace(" ", "").lower()
        return request.url.scheme == "https" or forwarded_proto == "https" or '"scheme":"https"' in cf_visitor

    @api.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home() -> HTMLResponse:
        return HTMLResponse(NARESH_PAGE_HTML)

    @api.get("/reports/ps-attendance", include_in_schema=False)
    def ps_attendance_page() -> RedirectResponse:
        return RedirectResponse(url="/", status_code=302)

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "PS Attendance Analytics",
            "storage": "SQLite SQL database",
            "remote_access_enabled": bool(api.state.public_access_password),
        }

    # -------------------------------------------------------------
    # Automated DSR Portal Endpoints (/login, /eptauto & /naresh)
    # -------------------------------------------------------------
    @api.get("/login", response_class=HTMLResponse, include_in_schema=False)
    @api.get("/eptauto", response_class=HTMLResponse, include_in_schema=False)
    @api.get("/naresh", response_class=HTMLResponse, include_in_schema=False)
    def naresh_page() -> HTMLResponse:
        return HTMLResponse(NARESH_PAGE_HTML)

    @api.get("/api/diagnostic/epts-check", include_in_schema=False)
    def epts_diagnostic():
        import httpx
        url = "https://epanchayat.telangana.gov.in/cs"
        try:
            with httpx.Client(verify=False, timeout=10.0) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                return {
                    "status": "ok",
                    "http_status": resp.status_code,
                    "length": len(resp.content),
                    "url": str(resp.url),
                }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "type": type(exc).__name__,
            }

    @api.get("/api/naresh/data", include_in_schema=False)
    def naresh_api_data(request: Request) -> dict[str, Any]:
        # Return report data only for this browser's e-Panchayat session.
        try:
            session_data = dsr_automation_service.get_report_data(portal_session_id(request))
            if session_data:
                return session_data
        except Exception:
            pass

        # If no fresh report has been generated yet in this session, return empty state
        return {
            "district_name": "",
            "report_date": "",
            "totals": {},
            "mandal_rows": [],
            "generated": False,
        }

    @api.get("/api/diag/reach", include_in_schema=False)
    def diag_reach() -> dict[str, Any]:
        import httpx
        try:
            with httpx.Client(verify=False, timeout=4.0) as client:
                r = client.get("https://epanchayat.telangana.gov.in/cs")
                return {"reachable": True, "status": r.status_code}
        except Exception as exc:
            return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}

    @api.post("/api/naresh/login", include_in_schema=False)
    def naresh_login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> dict[str, Any]:
        u = username.strip() if username else ""
        p = password.strip() if password else ""
        if not u or not p:
            raise HTTPException(status_code=400, detail="Please enter both User ID and Password.")

        try:
            return dsr_automation_service.start_server_login(u, p, headless=True, session_id=portal_session_id(request))
        except Exception as exc:
            logger.exception("Error during server login: %s", exc)
            detail = "Live e-Panchayat login failed. Check portal connectivity and browser automation dependencies."
            if "captcha image is not visible" in str(exc).lower():
                detail = (
                    "e-Panchayat opened the login form, but its CAPTCHA image was not visible to the automation. "
                    "Please retry; if it continues, the portal may not be serving a usable CAPTCHA challenge."
                )
            elif "page.goto: timeout" in str(exc).lower():
                detail = (
                    "The e-Panchayat login page did not finish opening through the regional connection. "
                    "No OTP was generated. Please retry shortly."
                )
            raise HTTPException(
                status_code=502,
                detail=detail,
            ) from None

    @api.post("/api/naresh/verify-otp", include_in_schema=False)
    def naresh_verify_otp(
        request: Request,
        otp: str = Form(...),
    ) -> dict[str, Any]:
        clean_otp = re.sub(r"\D", "", otp.strip() if otp else "")
        if len(clean_otp) != 6:
            raise HTTPException(status_code=400, detail="Please enter a valid 6-digit numeric OTP.")

        try:
            return dsr_automation_service.verify_server_otp(clean_otp, session_id=portal_session_id(request))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except Exception as exc:
            logger.exception("Error during OTP verification: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Live e-Panchayat OTP verification failed. The portal did not confirm authentication.",
            ) from None

    @api.get("/api/naresh/session-status", include_in_schema=False)
    def naresh_session_status(request: Request) -> dict[str, Any]:
        try:
            return dsr_automation_service.get_session_status(portal_session_id(request))
        except Exception as exc:
            logger.warning("Error fetching session status: %s", exc)
            return {"success": False, "authenticated": False, "status": "idle"}

    @api.post("/api/naresh/logout", include_in_schema=False)
    def naresh_logout(request: Request) -> dict[str, Any]:
        try:
            return dsr_automation_service.logout_server_session(portal_session_id(request))
        except Exception as exc:
            logger.exception("Error during e-Panchayat logout: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="The background portal session could not be stopped cleanly.",
            ) from None

    @api.post("/api/naresh/generate", include_in_schema=False)
    def naresh_generate(
        request: Request,
        module: str = Form(default="dsr_full"),
        date: str = Form(default=""),
    ) -> dict[str, Any]:
        try:
            return dsr_automation_service.generate_server_report(
                module=module,
                date_str=date,
                session_id=portal_session_id(request),
            )
        except Exception as exc:
            logger.exception("naresh_generate failed for module=%s date=%s", module, date)
            status_code, safe_message = _safe_error(exc)
            raise HTTPException(status_code=status_code, detail=safe_message) from None

    @api.get("/api/naresh/progress", include_in_schema=False)
    def naresh_progress(request: Request) -> dict[str, Any]:
        try:
            return dsr_automation_service.get_generation_progress(portal_session_id(request))
        except Exception as exc:
            logger.warning("Error fetching report progress: %s", exc)
            return {
                "active": False,
                "status": "error",
                "percent": 0,
                "step": 0,
                "stage": "error",
                "message": "Report progress is temporarily unavailable.",
            }

    def _serve_naresh_pdf(session_id: str, inline: bool = True) -> Response:
        # Resolve only this browser session's generated PDF.
        try:
            pdf_path_str = dsr_automation_service.get_latest_pdf_path(session_id)
            if pdf_path_str:
                pdf_path = Path(pdf_path_str)
                if pdf_path.exists() and pdf_path.stat().st_size > 500:
                    disposition = "inline" if inline else "attachment"
                    return Response(
                        content=pdf_path.read_bytes(),
                        media_type="application/pdf",
                        headers={
                            "Content-Disposition": f'{disposition}; filename="{pdf_path.name}"',
                            "Access-Control-Expose-Headers": "Content-Disposition",
                        },
                    )
        except Exception:
            pass

        raise HTTPException(
            status_code=404,
            detail="No generated PDF available yet. Please complete login and generate report above."
        )

    @api.get("/api/naresh/view", include_in_schema=False)
    def naresh_view_pdf(request: Request) -> Response:
        return _serve_naresh_pdf(portal_session_id(request), inline=True)

    @api.get("/api/naresh/download", include_in_schema=False)
    def naresh_download_pdf(request: Request) -> Response:
        return _serve_naresh_pdf(portal_session_id(request), inline=False)

    # -------------------------------------------------------------
    # GP Balance Entry (GM-R 14.2) Report Endpoints
    # -------------------------------------------------------------
    @api.get("/api/balance/dates", include_in_schema=False)
    def get_balance_dates(request: Request) -> dict[str, list[str]]:
        try:
            if not dsr_automation_service.is_authenticated(portal_session_id(request)):
                raise HTTPException(status_code=401, detail="Department Login & OTP required.")
            return {"dates": dsr_automation_service.get_available_balance_dates(portal_session_id(request))}
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None
        except Exception as exc:
            logger.exception("get_balance_dates failed")
            raise HTTPException(status_code=502, detail="Could not load dates from the live e-Panchayat portal.") from None

    @api.get("/api/balance/data", include_in_schema=False)
    def get_balance_data(request: Request, date: str = "") -> dict[str, Any]:
        return gp_balance_service.get_balance_data_dict(date_str=date, session_id=portal_session_id(request))

    @api.post("/api/balance/generate", include_in_schema=False)
    def generate_balance_api(request: Request, date: str = Form(default="")) -> dict[str, Any]:
        try:
            if not dsr_automation_service.is_authenticated(portal_session_id(request)):
                raise HTTPException(status_code=401, detail="Department Login & OTP required. Please log in first.")
            return dsr_automation_service.generate_server_report(
                module="gp_balance", date_str=date, session_id=portal_session_id(request)
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("generate_balance_api failed for date=%s", date)
            status_code, safe_message = _safe_error(exc)
            raise HTTPException(status_code=status_code, detail=safe_message) from None

    @api.get("/api/balance/report.pdf", include_in_schema=False)
    def view_balance_pdf(request: Request, date: str = "") -> Response:
        try:
            filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(
                date_str=date, session_id=portal_session_id(request)
            )
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @api.get("/api/balance/download-pdf", include_in_schema=False)
    def download_balance_pdf(request: Request, date: str = "") -> Response:
        try:
            filename, pdf_bytes = gp_balance_service.get_balance_pdf_bytes(
                date_str=date, session_id=portal_session_id(request)
            )
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

    @api.get("/api/balance/download-excel", include_in_schema=False)
    def download_balance_excel(request: Request, date: str = "") -> Response:
        try:
            filename, excel_bytes = gp_balance_service.get_balance_excel_bytes(
                date_str=date, session_id=portal_session_id(request)
            )
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

    # -------------------------------------------------------------
    # House Tax DCB Consolidation & PDF Report Endpoints
    # -------------------------------------------------------------
    @api.get("/reports/tax-dcb", include_in_schema=False)
    def tax_dcb_page(district: str = "Khammam") -> RedirectResponse:
        return RedirectResponse(url=f"/?station=tax-dcb&district={district}", status_code=302)

    @api.get("/api/tax/districts")
    def get_tax_districts() -> list[dict[str, Any]]:
        return tax_service.get_districts_list()

    @api.get("/api/tax/mandals")
    def get_tax_mandals(district: str = "Khammam") -> list[str]:
        return tax_service.get_mandals_for_district(district)

    @api.get("/api/tax/data")
    def get_tax_data(district: str = "Khammam", mandal: str = "all") -> dict[str, Any]:
        return tax_service.get_filtered_data(district, mandal)

    @api.get("/api/tax/report.pdf")
    def view_tax_pdf(district: str = "Khammam", mandal: str = "all") -> Response:
        filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, mandal)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @api.get("/api/tax/download-pdf")
    def download_tax_pdf(district: str = "Khammam", mandal: str = "all") -> Response:
        filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, mandal)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    @api.get("/api/tax/powerbi-report.pdf")
    def download_powerbi_pdf(district: str = "Khammam", mandal: str = "all", force: bool = False) -> Response:
        filename, pdf_bytes = powerbi_pdf_generator.get_or_generate_powerbi_pdf(district, mandal, force_regenerate=force)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    @api.get("/api/tax/download")
    def download_tax_data(district: str = "Khammam", format: str = "xlsx") -> Response:
        safe_dist = district.strip().replace(" ", "_")
        if format.lower() == "csv":
            csv_bytes = tax_service.generate_consolidated_csv(district)
            return Response(
                content=csv_bytes,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_dist}_House_Tax_DCB.csv"',
                    "Access-Control-Expose-Headers": "Content-Disposition",
                },
            )
        excel_bytes = tax_service.generate_consolidated_excel(district)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_dist}_House_Tax_DCB.xlsx"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    @api.post("/api/tax/refresh")
    def refresh_tax_data() -> dict[str, Any]:
        df = tax_service.get_df(force_reload=True)
        return {"status": "ok", "total_gps": len(df), "message": "Fresh DCB data successfully downloaded."}

    @api.get("/access", response_class=HTMLResponse, include_in_schema=False)
    def public_access_page(request: Request) -> HTMLResponse:
        if _valid_public_access_cookie(
            request.cookies.get("remote_console_access"), api.state.public_access_signing_key
        ):
            return HTMLResponse("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shared Console Access</title><body style="font:16px Arial,sans-serif;max-width:520px;margin:12vh auto;padding:24px;color:#123b2d">
<h1>Access session active</h1><p>You are signed in to the shared console.</p><p><a href="/">Open the e-Panchayat Automated Console</a></p>
<form method="post" action="/access/logout"><button type="submit">Sign out of this device</button></form></body></html>""")
        response = HTMLResponse(_public_access_html())
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.post("/access/login", include_in_schema=False)
    async def public_access_login(request: Request) -> Response:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Submit the access passcode using the login form.")

        client_ip = request.headers.get("cf-connecting-ip", "").strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        attempt_started, attempts = api.state.public_login_attempts.get(client_ip, (now, 0))
        if now - attempt_started >= 10 * 60:
            attempt_started, attempts = now, 0
        if attempts >= 8:
            response = HTMLResponse(_public_access_html("Too many attempts. Wait 10 minutes and try again."), status_code=429)
            response.headers["Cache-Control"] = "no-store"
            return response

        from urllib.parse import parse_qs
        try:
            submitted = parse_qs((await request.body()).decode("utf-8", errors="strict")).get("password", [""])[0]
        except (UnicodeDecodeError, ValueError):
            submitted = ""
        if not hmac.compare_digest(submitted, api.state.public_access_password):
            api.state.public_login_attempts[client_ip] = (attempt_started, attempts + 1)
            response = HTMLResponse(_public_access_html("The access passcode was not accepted."), status_code=401)
            response.headers["Cache-Control"] = "no-store"
            return response

        api.state.public_login_attempts.pop(client_ip, None)
        expires_at = int(time.time()) + 8 * 60 * 60
        cookie_value = _make_public_access_cookie(api.state.public_access_signing_key, expires_at)
        if "application/json" in request.headers.get("accept", ""):
            response = JSONResponse({"authenticated": True})
        else:
            response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            "remote_console_access",
            cookie_value,
            max_age=8 * 60 * 60,
            httponly=True,
            secure=secure_request(request),
            samesite="strict",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.post("/access/logout", include_in_schema=False)
    def public_access_logout() -> RedirectResponse:
        response = RedirectResponse(url="/access", status_code=303)
        response.delete_cookie("remote_console_access", path="/", secure=True, httponly=True, samesite="strict")
        return response

    @api.middleware("http")
    async def enforce_public_access(request: Request, call_next):
        existing_session_id = request.cookies.get("portal_client_session", "")
        valid_session_cookie = bool(re.fullmatch(r"[a-f0-9]{32}", existing_session_id))
        session_id = existing_session_id if valid_session_cookie else uuid4().hex
        request.state.portal_session_id = session_id

        if request.url.path == "/health":
            response = await call_next(request)
        elif not api.state.public_access_password:
            response = await call_next(request)
        elif request.url.path == "/access" and request.method == "GET":
            response = await call_next(request)
        elif request.url.path in {"/access/login", "/access/logout"} and request.method == "POST":
            response = await call_next(request)
        elif _valid_public_access_cookie(
            request.cookies.get("remote_console_access"), api.state.public_access_signing_key
        ):
            response = await call_next(request)
        elif request.url.path.startswith("/api/") or "text/html" not in request.headers.get("accept", ""):
            response = JSONResponse({"detail": "Shared console access passcode required."}, status_code=401)
        else:
            response = RedirectResponse(url="/access", status_code=303)

        if request.url.path != "/health" and not valid_session_cookie:
            response.set_cookie(
                "portal_client_session",
                session_id,
                max_age=12 * 60 * 60,
                httponly=True,
                secure=secure_request(request),
                samesite="strict",
                path="/",
            )
        return response

    return api
app = create_app()

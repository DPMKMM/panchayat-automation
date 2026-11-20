"""e-Panchayat Automation & e-Panchayat Automation Console Portal.

Unified backend server cleanly mounting modular sub-applications:
- Portal Module: Dual-domain Homepage, Firebase Auth (Google Sign-In), Cloud Firestore Profiles & Admin Dashboard
- DSR Module: Daily Status Report & Attendance Automation + Manual DSR Excel Upload
- DCB Module: House Tax Demand Collection Balance Analytics (100% Live Web Scraped)
- GP Balance Module: Thursday Gram Panchayat Bank/Cash Balance Tracking
- MAS Module: Monthly Activity Statement 18-Indicator Executive Matrix (GM-R 5.24 + GM-R 5.23 Births)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import re
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.branding import CONSOLE_NAME, PLATFORM_NAME, TAGLINE
from core.config import BASE_DIR, LOG_LEVEL
from core.dependencies import auth_cookie_domain, resolve_sso_session
from core.firebase_store import log_usage, record_dsc_telemetry
from dcb.router import router as dcb_router
from dsr import service as automation_service
from dsr.router import router as dsr_router
from DSR_State_Format.router import router as state_format_router
from gp_balance.router import router as gp_balance_router
from inspections.router import router as inspections_router
from mas.router import mas_alias_router, mas_upper_router, router as mas_router, web_router as mas_web_router
from multiday_dsr.router import router as multiday_dsr_router
from mobile_updation.router import router as mobile_updation_router
from Auto_Multi_DSR.router import router as auto_multi_dsr_router
from portal.admin_router import router as admin_router
from portal.billing_router import router as billing_router
from portal.router import router as portal_router
from tools.excel.router import router as tools_excel_router
from tools.pdf.router import router as tools_pdf_router


def _resolve_tracked_tool_event(method: str, path: str) -> tuple[str, str, str] | None:
    """Map successful report/tool API endpoints to structured (scope, module, action) telemetry."""
    m = method.upper()
    p = path.lower()
    if m == "POST" and p.startswith("/api/tools/pdf/"):
        slug = p[len("/api/tools/pdf/"):].strip("/")
        if slug and "/" not in slug and slug != "health":
            return "tools", f"pdf:{slug}", "execute"
    if m == "POST" and (p.startswith("/api/tools/excel/execute") or p.startswith("/api/tools/excel/viewer/")):
        return "tools", "excel_studio", "execute"
    if m == "GET" and p.startswith("/api/tools/excel/download/"):
        return "tools", "excel_studio", "download"
    if m == "POST" and p == "/api/web/reports":
        return "portal", "dsr_manual", "generate"
    if m == "GET" and (p.startswith("/api/web/reports/") and any(k in p for k in ("download", "download-excel", "download-image"))):
        return "portal", "dsr_manual", "download"
    if m == "POST" and p in ("/api/web/multi-day-reports", "/api/multiday-dsr/analyze"):
        return "portal", "dsr_multiday", "generate"
    if m == "GET" and (p.startswith("/api/multiday-dsr/jobs/") and any(k in p for k in ("download-pdf", "download-excel"))):
        return "portal", "dsr_multiday", "download"
    if m == "POST" and p == "/api/manual-reports/pending-mobile-assessments":
        return "portal", "mobile_updation", "generate"
    if m == "GET" and p.startswith("/api/manual-reports/pending-mobile-assessments") and "download" in p:
        return "portal", "mobile_updation", "download"
    if p in ("/api/tax/report.pdf", "/api/tax/download-pdf", "/api/tax/powerbi-report.pdf", "/api/tax/download") and m == "GET":
        return "portal", "dcb_live", p.rsplit("/", 1)[-1]
    if p == "/api/tax/refresh" and m == "POST":
        return "portal", "dcb_live", "refresh"
    if p in ("/api/balance/generate", "/api/balance/download-pdf", "/api/balance/download-excel"):
        return "console", "gp_balance", p.rsplit("/", 1)[-1]
    if m == "POST" and p in ("/api/reports/mas-consolidated/generate", "/api/mas/generate"):
        return "console", "mas_consolidated", "generate"
    if m == "POST" and p in ("/api/inspections/generate", "/api/inspections/upload-consolidate"):
        return "console", "gp_inspections", "generate"
    if m == "POST" and p == "/api/auto-multi-dsr/start-job":
        return "console", "auto_multi_dsr", "generate"
    if m == "GET" and (p.startswith("/api/auto-multi-dsr/jobs/") and any(k in p for k in ("download-pdf", "download-excel"))):
        return "console", "auto_multi_dsr", "download"
    return None

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("epanchayat_app")


def create_app() -> FastAPI:
    # Start session keepalive loop
    try:
        automation_service.ensure_keepalive_running()
    except Exception as exc:
        logger.warning("Notice on keepalive init: %s", exc)

    # Security Patch 4: Hide Swagger OpenAPI Docs in production to prevent schema scraping
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
    enable_docs = os.getenv("ENABLE_DOCS", "false" if is_production else "true").lower() in ("true", "1")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            from core.firebase_store import seed_admin_user
            seed_admin_user()
        except Exception as exc:
            logger.warning("Could not auto-seed admin user on startup: %s", exc)
        yield

    app = FastAPI(
        title=f"{PLATFORM_NAME} · {CONSOLE_NAME}",
        version="4.0.0",
        description=f"{TAGLINE} Unified portal for Attendance/DSR, House Tax DCB, and GP Thursday Balance Tracking.",
        docs_url="/api/docs" if enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if enable_docs else None,
        lifespan=lifespan,
    )

    # Security Patch 2: Restrict CORS to authorized production and local domains
    allowed_origins = [
        "https://panchayatautomation.in",
        "https://www.panchayatautomation.in",
        "https://autoreports.panchayatautomation.in",
        "https://www.autoreports.panchayatautomation.in",
        "https://manualreports.panchayatautomation.in",
        "https://www.manualreports.panchayatautomation.in",
        "https://tools.panchayatautomation.in",
        "https://www.tools.panchayatautomation.in",
        "https://softwares.panchayatautomation.in",
        "https://www.softwares.panchayatautomation.in",
        "https://admin.panchayatautomation.in",
        "https://www.admin.panchayatautomation.in",
        "https://reports.panchayatautomation.in",
        "https://www.reports.panchayatautomation.in",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8050",
        "http://localhost:8050",
        "http://testserver",
    ]
    custom_origin = os.getenv("CUSTOM_DOMAIN", "").strip()
    if custom_origin and f"https://{custom_origin}" not in allowed_origins:
        allowed_origins.append(f"https://{custom_origin}")
        allowed_origins.append(f"https://www.{custom_origin}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https?://([a-zA-Z0-9_-]+\.)*panchayatautomation\.in(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def session_cookie_middleware(request: Request, call_next):
        # 1. Header takes strict priority over cookie (prevents proxy / Cloudflare cookie poisoning)
        sid = (
            request.headers.get("X-Session-ID")
            or request.headers.get("x-session-id")
            or request.query_params.get("session_id")
            or request.cookies.get("epts_session_id")
            or ""
        ).strip()

        is_new = False
        if not sid or not re.match(r"^[a-zA-Z0-9_\-]{8,64}$", sid):
            sid = secrets.token_hex(16)
            is_new = True

        request.state.session_id = sid

        # Security Patch 4: Block /docs, /redoc, and /openapi.json when enable_docs is disabled
        path_low = request.url.path.lower()
        if not enable_docs and path_low in ("/docs", "/redoc", "/openapi.json", "/api/docs", "/api/redoc", "/api/openapi.json"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # Security Patch 5: Strictly require authenticated user session for all automation & report endpoints in production
        if is_production:
            tracked_event = _resolve_tracked_tool_event(request.method, request.url.path)
            if tracked_event:
                user, _ = resolve_sso_session(request)
                if user is None:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required. Please sign in with an active account to access automation and reports."},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

        response = await call_next(request)

        if response.status_code < 400:
            tracked = _resolve_tracked_tool_event(request.method, request.url.path)
            if tracked:
                t_scope, t_mod, t_act = tracked
                try:
                    t_user, _ = resolve_sso_session(request)
                except Exception:
                    t_user = None
                log_usage(
                    user_id=str((t_user or {}).get("user_id") or "guest"),
                    gmail=str((t_user or {}).get("gmail") or ""),
                    user_name=str((t_user or {}).get("name") or ""),
                    designation=str((t_user or {}).get("designation") or ""),
                    platform_scope=t_scope,
                    module=t_mod,
                    action=t_act,
                )

        # Security Patch 1: Comprehensive Anti-Clickjacking, Anti-Sniffing & Security Headers
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Strict anti-caching headers for dynamic governance reports
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Session-ID"] = sid

        is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Security Patch 3: Keep HttpOnly epts_session_id cookie synchronized across page & asset requests
        handler_set_epts = False
        try:
            raw_cookies = response.headers.getlist("set-cookie") if hasattr(response.headers, "getlist") else []
            if not raw_cookies:
                raw_cookies = [v for k, v in getattr(response, "raw_headers", []) if k.lower() == b"set-cookie"]
                raw_cookies = [c.decode("latin1", "ignore") if isinstance(c, bytes) else str(c) for c in raw_cookies]
            for c in raw_cookies:
                if "epts_session_id=" in c:
                    handler_set_epts = True
                    break
        except Exception:
            handler_set_epts = False

        cookie_sid = (request.cookies.get("epts_session_id") or "").strip()
        if not handler_set_epts and not request.url.path.startswith("/static/") and (is_new or not cookie_sid or cookie_sid != sid):
            response.set_cookie(
                key="epts_session_id",
                value=sid,
                max_age=86400 * 30,
                httponly=True,
                secure=is_https,
                samesite="lax",
                path="/",
                domain=auth_cookie_domain(request),
            )
        return response

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        commit_hash = "unknown"
        try:
            import subprocess
            commit_hash = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(Path(__file__).resolve().parent),
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )
        except Exception:
            pass
        return {
            "status": "ok",
            "platform": PLATFORM_NAME,
            "console": CONSOLE_NAME,
            "tagline": TAGLINE,
            "modules": "DSR, DCB, GP_BALANCE, MAS, TOOLS, SOFTWARES",
            "version": "4.0.0",
            "commit": commit_hash,
        }

    # Mount modular application routers
    app.include_router(portal_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(dsr_router)
    app.include_router(state_format_router)
    app.include_router(dcb_router)
    app.include_router(gp_balance_router)
    app.include_router(inspections_router)
    app.include_router(multiday_dsr_router)
    app.include_router(mobile_updation_router)
    app.include_router(auto_multi_dsr_router)
    app.include_router(mas_web_router)
    app.include_router(mas_router)
    app.include_router(mas_alias_router)
    app.include_router(mas_upper_router)
    app.include_router(tools_excel_router)
    app.include_router(tools_pdf_router)

    # High-speed static software package downloads & release CDN fallback
    RELEASE_CDN_FALLBACK: dict[str, str] = {
        "jdk-8u351-windows-x32bit.zip": "https://github.com/DPMKMM/panchayat-automation/releases/download/softwares-v1/jdk-8u351-windows-x32bit.zip",
        "jdk-8u191-windows-x64.zip": "https://github.com/DPMKMM/panchayat-automation/releases/download/softwares-v1/jdk-8u191-windows-x64.zip",
        "Office_ProPlus_2010w_SP2_W32_English_August_2016.iso": "https://github.com/DPMKMM/panchayat-automation/releases/download/softwares-v1/Office_ProPlus_2010w_SP2_W32_English_August_2016.iso",
        "AdbeRdr11007_en_US.zip": "https://github.com/DPMKMM/panchayat-automation/releases/download/softwares-v1/AdbeRdr11007_en_US.zip",
        "DSC.Signer.Bundle.Softwares.exe": "https://github.com/DPMKMM/panchayat-automation/releases/download/sofotware_bundle/DSC.Signer.Bundle.Softwares.exe",
        "DSC.Signer.Bundle.Softwares.Offline.exe": "https://github.com/DPMKMM/panchayat-automation/releases/download/sofotware_bundle/DSC.Signer.Bundle.Softwares.Offline.exe",
    }

    @app.api_route("/download/{file_name}", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/static/softwares/{file_name}", methods=["GET", "HEAD"], include_in_schema=False)
    def static_software_package_download(file_name: str):
        local_file = BASE_DIR / "static" / "softwares" / file_name
        if local_file.is_file():
            return FileResponse(
                path=str(local_file),
                filename=file_name,
                media_type="application/octet-stream",
            )
        lookup_name = file_name if file_name in RELEASE_CDN_FALLBACK else file_name.replace(" ", ".")
        if lookup_name in RELEASE_CDN_FALLBACK:
            target_url = RELEASE_CDN_FALLBACK[lookup_name]
            try:
                import urllib.request
                from starlette.responses import StreamingResponse

                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "PanchayatAutomation-Proxy/1.0"},
                )
                upstream = urllib.request.urlopen(req, timeout=30)
                content_len = upstream.headers.get("Content-Length")
                headers = {"Content-Disposition": f'attachment; filename="{file_name}"'}
                if content_len:
                    headers["Content-Length"] = content_len

                def stream_chunks():
                    try:
                        while True:
                            chunk = upstream.read(65536)
                            if not chunk:
                                break
                            yield chunk
                    finally:
                        upstream.close()

                return StreamingResponse(
                    stream_chunks(),
                    media_type="application/octet-stream",
                    headers=headers,
                )
            except Exception:
                return RedirectResponse(target_url, status_code=307)
        raise HTTPException(status_code=404, detail="Software file not found.")

    @app.post("/api/ubd/telemetry", include_in_schema=False)
    async def ubd_telemetry_webhook(request: Request):
        """Receive silent background heartbeat & installation receipts from DSC Signer desktop app."""
        payload: dict[str, Any] = {}
        try:
            payload = await request.json()
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        record = record_dsc_telemetry(payload, client_ip=client_ip)
        return {"success": True, "system_id": record.get("system_id")}

    @app.get("/version.json", include_in_schema=False)
    @app.get("/api/version.json", include_in_schema=False)
    def dsc_bundle_version_manifest():
        v_file = BASE_DIR / "version.json"
        if v_file.is_file():
            return FileResponse(
                path=str(v_file),
                media_type="application/json",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return {"version": "1.0.1", "status": "latest"}

    # Progressive Web App (PWA) Manifest & Service Worker Endpoints
    @app.get("/manifest.json", include_in_schema=False)
    def web_manifest():
        manifest_file = BASE_DIR / "static" / "manifest.json"
        if manifest_file.is_file():
            return FileResponse(
                path=str(manifest_file),
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        raise HTTPException(status_code=404, detail="Manifest not found.")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        sw_file = BASE_DIR / "static" / "sw.js"
        if sw_file.is_file():
            return FileResponse(
                path=str(sw_file),
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Service-Worker-Allowed": "/",
                },
            )
        raise HTTPException(status_code=404, detail="Service worker not found.")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        fav_file = BASE_DIR / "static" / "favicon.ico"
        if fav_file.is_file():
            return FileResponse(path=str(fav_file), media_type="image/x-icon")
        fav_icon_file = BASE_DIR / "static" / "icons" / "favicon.ico"
        if fav_icon_file.is_file():
            return FileResponse(path=str(fav_icon_file), media_type="image/x-icon")
        raise HTTPException(status_code=404, detail="Favicon not found.")

    # Mount static files directory
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8050"))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)

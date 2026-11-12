"""e-Panchayat Automation & e-Panchayat Automation Console Portal.

Unified backend server cleanly mounting modular sub-applications:
- Portal Module: Dual-domain Homepage, Firebase Auth (Google Sign-In), Cloud Firestore Profiles & Admin Dashboard
- DSR Module: Daily Status Report & Attendance Automation + Manual DSR Excel Upload
- DCB Module: House Tax Demand Collection Balance Analytics (100% Live Web Scraped)
- GP Balance Module: Thursday Gram Panchayat Bank/Cash Balance Tracking
- MAS Module: Monthly Activity Statement 18-Indicator Executive Matrix (GM-R 5.24 + GM-R 5.23 Births)
"""

from __future__ import annotations

import logging
import os
import re
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.branding import CONSOLE_NAME, PLATFORM_NAME, TAGLINE
from core.config import BASE_DIR, LOG_LEVEL
from core.dependencies import auth_cookie_domain, resolve_sso_session
from core.firebase_store import log_usage
from dcb.router import router as dcb_router
from dsr import service as automation_service
from dsr.router import router as dsr_router
from gp_balance.router import router as gp_balance_router
from inspections.router import router as inspections_router
from mas.router import mas_alias_router, mas_upper_router, router as mas_router, web_router as mas_web_router
from multiday_dsr.router import router as multiday_dsr_router
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
    if m == "POST" and p == "/api/web/reports":
        return "portal", "dsr_manual", "generate"
    if m == "POST" and p in ("/api/web/multi-day-reports", "/api/multiday-dsr/analyze"):
        return "portal", "dsr_multiday", "generate"
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

    app = FastAPI(
        title=f"{PLATFORM_NAME} · {CONSOLE_NAME}",
        version="4.0.0",
        description=f"{TAGLINE} Unified portal for Attendance/DSR, House Tax DCB, and GP Thursday Balance Tracking.",
        docs_url="/api/docs" if enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if enable_docs else None,
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
        cookie_sid = (request.cookies.get("epts_session_id") or "").strip()
        if not request.url.path.startswith("/static/") and (is_new or not cookie_sid or cookie_sid != sid):
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
        return {
            "status": "ok",
            "platform": PLATFORM_NAME,
            "console": CONSOLE_NAME,
            "tagline": TAGLINE,
            "modules": "DSR, DCB, GP_BALANCE, MAS, TOOLS",
            "version": "4.0.0",
        }

    # Mount modular application routers
    app.include_router(portal_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(dsr_router)
    app.include_router(dcb_router)
    app.include_router(gp_balance_router)
    app.include_router(inspections_router)
    app.include_router(multiday_dsr_router)
    app.include_router(auto_multi_dsr_router)
    app.include_router(mas_web_router)
    app.include_router(mas_router)
    app.include_router(mas_alias_router)
    app.include_router(mas_upper_router)
    app.include_router(tools_excel_router)
    app.include_router(tools_pdf_router)

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

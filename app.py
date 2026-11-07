"""Telangana ePanchayat Automation & Analytics Portal.

Unified backend server cleanly mounting modular sub-applications:
- DSR Module: Daily Status Report & Attendance Automation
- DCB Module: House Tax Demand Collection Balance Analytics (100% Live Web Scraped)
- GP Balance Module: Thursday Gram Panchayat Bank/Cash Balance Tracking
"""

from __future__ import annotations

import logging
import re
import secrets
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import BASE_DIR, LOG_LEVEL
from dsr.router import router as dsr_router
from dcb.router import router as dcb_router
from gp_balance.router import router as gp_balance_router
from mas.router import router as mas_router, web_router as mas_web_router
from dsr import service as automation_service

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("epanchayat_app")


def create_app() -> FastAPI:
    # Start session keepalive loop
    try:
        automation_service.ensure_keepalive_running()
    except Exception as exc:
        logger.warning("Notice on keepalive init: %s", exc)

    app = FastAPI(
        title="Telangana ePanchayat Automation & Executive Analytics",
        version="4.0.0",
        description="Unified portal for Attendance/DSR, House Tax DCB, and GP Thursday Balance Tracking.",
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def session_cookie_middleware(request: Request, call_next):
        # 1. Header takes strict priority over cookie (prevents proxy / Cloudflare cookie poisoning)
        sid = (
            request.headers.get("X-Session-ID")
            or request.headers.get("x-session-id")
            or request.cookies.get("epts_session_id")
            or request.query_params.get("session_id")
            or ""
        ).strip()

        is_new = False
        if not sid or not re.match(r"^[a-zA-Z0-9_\-]{8,64}$", sid):
            sid = secrets.token_hex(16)
            is_new = True

        request.state.session_id = sid
        response = await call_next(request)

        # 2. Strict anti-caching headers for ALL endpoints
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Session-ID"] = sid

        if is_new or not request.cookies.get("epts_session_id"):
            response.set_cookie(
                key="epts_session_id",
                value=sid,
                max_age=86400 * 30,
                httponly=False,
                samesite="lax",
                path="/",
            )
        return response

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "platform": "Telangana ePanchayat Automation",
            "modules": "DSR, DCB, GP_BALANCE, MAS",
            "version": "4.0.0",
        }

    # Mount modular application routers
    app.include_router(dsr_router)
    app.include_router(dcb_router)
    app.include_router(gp_balance_router)
    app.include_router(mas_router)
    app.include_router(mas_web_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

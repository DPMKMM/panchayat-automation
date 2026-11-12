"""Platform 1 & Dual-Domain Identity Router (Homepage, Firebase Auth, Firestore Profile & Feedback)."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from core.access_policy import can_user_access_automated_reports, get_access_policy, is_platform_enabled
from core.branding import WELCOME_MESSAGE, apply_portal_branding, apply_subpage_console_branding
from core.config import REVOKED_ADMIN_EMAILS, get_firebase_web_config, is_admin_email
from core.dependencies import (
    clear_auth_cookie,
    enforce_console_api_access,
    extract_all_auth_tokens,
    extract_epts_session_id,
    get_current_user_optional,
    resolve_platform_scope,
    resolve_sso_session,
    set_auth_cookie,
    sync_sso_cookie_if_needed,
)
from core.firebase_app import get_firebase_runtime_status, verify_firebase_id_token
from core.firebase_store import (
    authenticate_or_register_firebase_user,
    create_portal_session,
    get_portal_session,
    log_usage,
    register_user_profile,
    revoke_portal_session,
    save_feedback,
)
from core.templating import load_portal_shell_html
from dsr import service as automation_service

logger = logging.getLogger("portal_router")
router = APIRouter(tags=["Dual-Domain Portal & Authentication"])

_get_sid = extract_epts_session_id


def serialize_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    clean_gmail = str(user.get("gmail") or "").strip().lower()
    is_adm = (
        clean_gmail not in REVOKED_ADMIN_EMAILS
        and (bool(user.get("is_admin")) or is_admin_email(clean_gmail))
    )
    return {
        "user_id": user.get("user_id"),
        "firebase_uid": user.get("firebase_uid") or user.get("google_uid") or "",
        "name": user.get("name"),
        "gmail": user.get("gmail"),
        "email": user.get("gmail"),
        "designation": user.get("designation") or "",
        "role": user.get("role") or "",
        "role_label": user.get("role") or "Mandal Level",
        "mobile_number": user.get("mobile_number") or "",
        "phone": user.get("mobile_number") or "",
        "profile_picture": user.get("profile_picture") or "",
        "registration_date": user.get("registration_date") or "",
        "last_login": user.get("last_login") or "",
        "account_status": user.get("account_status", "Active"),
        "profile_completed": bool(user.get("profile_completed", False)),
        "is_admin": is_adm,
        "can_access_portal": bool(user.get("can_access_portal", True)),
        "can_access_console": bool(user.get("can_access_console", True)),
        "can_access_automated": can_user_access_automated_reports(user),
        "has_automated_subscription": bool(user.get("has_automated_subscription", False)),
        "subscription_status": str(user.get("subscription_status") or "free_preview"),
        "subscription_plan_id": str(user.get("subscription_plan_id") or ""),
        "subscription_plan_name": str(user.get("subscription_plan_name") or ""),
        "subscription_expires_at": str(user.get("subscription_expires_at") or ""),
        "username": user.get("user_id"),
        "district": "Khammam",
        "mandal": "",
    }


def _firebase_client_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "firebase_config": get_firebase_web_config(),
        "firebase_runtime": get_firebase_runtime_status(),
    }
    auth_emu = (os.getenv("FIREBASE_AUTH_EMULATOR_HOST") or "").strip()
    if auth_emu:
        payload["auth_emulator_host"] = auth_emu
    return payload


# ---------------------------------------------------------------------------
# Web Shell & Informational Routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
@router.get("/autoreports", response_class=HTMLResponse, include_in_schema=False)
@router.get("/manualreports", response_class=HTMLResponse, include_in_schema=False)
@router.get("/tools", response_class=HTMLResponse, include_in_schema=False)
@router.get("/eptauto", response_class=HTMLResponse, include_in_schema=False)
@router.get("/naresh", response_class=HTMLResponse, include_in_schema=False)
@router.get("/reports", response_class=HTMLResponse, include_in_schema=False)
def portal_home_page(request: Request) -> HTMLResponse:
    """Render web shell branded for the active host and upgrade active sessions to SSO cookie."""
    resp = HTMLResponse(apply_portal_branding(load_portal_shell_html(), request))
    user, tok = resolve_sso_session(request)
    sync_sso_cookie_if_needed(request, resp, user, tok)
    return resp


@router.get("/services", response_class=HTMLResponse, tags=["Services"])
def services_hub_page(request: Request) -> HTMLResponse:
    from dsr.services_html import get_services_page_html
    return HTMLResponse(apply_subpage_console_branding(get_services_page_html(), request))


@router.get("/privacy-legal", response_class=HTMLResponse, tags=["Legal"])
@router.get("/legal", response_class=HTMLResponse, tags=["Legal"])
def privacy_legal_page(request: Request) -> HTMLResponse:
    from dsr.legal_html import get_privacy_legal_html
    return HTMLResponse(apply_subpage_console_branding(get_privacy_legal_html(), request))


@router.post("/api/feedback", include_in_schema=False)
async def api_submit_feedback(request: Request):
    data: dict[str, Any] = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        pass

    message = str(data.get("message") or "").strip()
    if not message:
        return JSONResponse({"success": False, "message": "Feedback message cannot be empty."}, status_code=400)

    session_user = (
        get_current_user_optional(request)
        or get_current_user_optional(request, app_scope="console")
        or get_current_user_optional(request, app_scope="portal")
    )

    name = str(data.get("name") or (session_user.get("name") if session_user else "")).strip()
    email = str(data.get("email") or (session_user.get("gmail") if session_user else "")).strip().lower()
    designation = str(data.get("designation") or (session_user.get("designation") if session_user else "")).strip()
    role = str(data.get("role") or (session_user.get("role") if session_user else "")).strip()
    rating_val = int(data.get("rating") or 5)
    category = str(data.get("category") or "General Feedback").strip()

    try:
        record = save_feedback(
            message=message,
            name=name,
            email=email,
            designation=designation,
            role=role,
            rating=rating_val,
            category=category,
            user_id=str(session_user.get("user_id") if session_user else ""),
            app_scope=resolve_platform_scope(request),
        )
        return {
            "success": True,
            "message": "Thank you! Your feedback has been submitted successfully.",
            "record": record,
        }
    except Exception as exc:
        logger.error("Failed to save feedback: %s", exc)
        return JSONResponse({"success": False, "message": f"Failed to save feedback: {exc}"}, status_code=500)


# ---------------------------------------------------------------------------
# Dual-Domain Firebase Authentication & Independent Scoped Sessions
# ---------------------------------------------------------------------------

@router.get("/api/auth/firebase-config", include_in_schema=False)
def api_firebase_config() -> dict[str, Any]:
    """Return public Firebase Web SDK configuration for modular client sign-in."""
    return {"success": True, **_firebase_client_payload()}


@router.post("/api/auth/firebase-login", include_in_schema=False)
async def api_firebase_login(request: Request, response: Response):
    """Verify a Firebase ID Token, upsert user in Cloud Firestore, and issue a scoped session."""
    scope = resolve_platform_scope(request)
    if not is_platform_enabled(scope):
        return JSONResponse(
            {"success": False, "message": "This platform is temporarily unavailable under administrator policy."},
            status_code=403,
        )

    data: dict[str, Any] = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        pass

    auth_header = str(request.headers.get("Authorization") or "").strip()
    bearer_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    id_token = str(data.get("id_token") or data.get("idToken") or bearer_token or "").strip()

    if not id_token:
        return JSONResponse(
            {"success": False, "message": "Firebase ID token is required. Please sign in with Google."},
            status_code=400,
        )

    try:
        claims = verify_firebase_id_token(id_token)
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=401)

    try:
        user_record, is_new = authenticate_or_register_firebase_user(
            firebase_uid=claims["firebase_uid"],
            gmail=claims["gmail"],
            name=claims["name"],
            profile_picture=claims["profile_picture"],
            platform_scope=scope,
        )
    except PermissionError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=403)

    user_agent = str(request.headers.get("user-agent") or "").strip()
    client_ip = str(request.client.host if request.client else "").strip()
    token = create_portal_session(
        user_id=str(user_record["user_id"]),
        app_scope=scope,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    set_auth_cookie(response, token, scope, request)
    log_usage(
        user_id=str(user_record["user_id"]),
        gmail=str(user_record.get("gmail") or ""),
        platform_scope=scope,
        module="auth",
        action="firebase_login",
    )

    return {
        "success": True,
        "token": token,
        "platform_scope": scope,
        "user": serialize_user_payload(user_record),
        "is_first_time": is_new,
        "profile_completed": bool(user_record.get("profile_completed", False)),
        "message": f"{WELCOME_MESSAGE}, {user_record.get('name', 'Officer')}!",
    }


@router.post("/api/auth/logout", include_in_schema=False)
@router.post("/api/auth/portal-logout", include_in_schema=False)
@router.get("/api/auth/portal-logout", include_in_schema=False)
def api_portal_logout(request: Request, response: Response):
    scope = resolve_platform_scope(request)
    for tok in extract_all_auth_tokens(request, scope):
        revoke_portal_session(tok)
    clear_auth_cookie(response, scope, request)

    browser_closed = False
    sid = extract_epts_session_id(request)
    has_console_bot = bool(sid and sid in getattr(automation_service, "_sessions", {}))
    if scope == "console" or has_console_bot:
        try:
            automation_service.logout_server_session(session_id=sid)
            browser_closed = True
        except Exception:
            pass
        try:
            from gp_balance import service as gp_balance_service
            gp_balance_service.reset_balance_data(session_id=sid)
        except Exception:
            pass

    return {
        "success": True,
        "platform_scope": scope,
        "browser_closed": browser_closed,
        "message": "Logged out and closed Automation Console browser." if browser_closed else "Logged out successfully.",
    }


@router.get("/api/auth/portal-status", include_in_schema=False)
@router.get("/api/auth/me", include_in_schema=False)
def api_portal_status(request: Request, response: Response):
    scope = resolve_platform_scope(request)
    user, tok = resolve_sso_session(request, scope)
    if user is not None and scope == "portal" and not user.get("can_access_portal", True):
        user = None
    if user is not None:
        sync_sso_cookie_if_needed(request, response, user, tok)
    policy = get_access_policy()["flags"]
    epts_sid = str(getattr(request.state, "session_id", "") or "").strip()
    base_payload = {
        "authenticated": bool(user),
        "platform_scope": scope,
        "epts_session_id": epts_sid,
        "access_policy": policy,
        **_firebase_client_payload(),
    }
    if user:
        payload = serialize_user_payload(user)
        return {
            **base_payload,
            "user": payload,
            "profile_completed": payload["profile_completed"],
        }
    return {
        **base_payload,
        "user": None,
        "profile_completed": False,
    }


@router.get("/api/auth/department-status", include_in_schema=False)
def api_department_status(request: Request) -> dict[str, Any]:
    """Centralized Stage-2 Department Login verification endpoint across all Console modules."""
    enforce_console_api_access(request)
    sid = extract_epts_session_id(request)
    try:
        st = automation_service.get_session_status(session_id=sid)
    except Exception:
        st = {"success": False, "authenticated": False, "expired": False, "status": "idle", "session_id": sid}
    is_auth = bool(st.get("authenticated"))
    st["department_authenticated"] = is_auth
    st["active"] = is_auth
    return st


@router.post("/api/auth/register-profile", include_in_schema=False)
@router.post("/api/auth/complete-profile", include_in_schema=False)
async def api_register_profile(request: Request, response: Response):
    scope = resolve_platform_scope(request)
    session_user, token = resolve_sso_session(request, scope)
    if not session_user or not token:
        return {"success": False, "message": "Portal authentication is required to complete profile registration."}

    data: dict[str, Any] = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        pass

    user_id = str(session_user["user_id"]).strip()
    name = str(data.get("name", "")).strip()
    designation = str(data.get("designation", "")).strip()
    role = str(data.get("role", "")).strip()
    mobile_number = str(data.get("mobile_number") or data.get("phone") or "").strip()

    ok, msg, updated_user = register_user_profile(
        user_id=user_id,
        name=name,
        designation=designation,
        role=role,
        mobile_number=mobile_number,
    )
    if not ok or not updated_user:
        return {"success": False, "message": msg}

    set_auth_cookie(response, token, scope, request)
    log_usage(
        user_id=user_id,
        gmail=str(updated_user.get("gmail") or ""),
        platform_scope=scope,
        module="profile",
        action="update_profile",
    )

    try:
        level_map = {
            "District Level": "district",
            "Division Level": "division",
            "Mandal Level": "mandal",
        }
        lvl = level_map.get(updated_user.get("role"), "mandal")
        automation_service.set_custom_user_level(
            level=lvl,
            district="Khammam",
            mandal="",
            session_id=_get_sid(request),
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": msg,
        "token": token,
        "platform_scope": scope,
        "user": serialize_user_payload(updated_user),
    }

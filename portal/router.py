"""Platform 1 & Dual-Domain Identity Router (Homepage, Firebase Auth, Firestore Profile & Feedback)."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.access_policy import can_user_access_automated_reports, get_access_policy, is_platform_enabled
from core.branding import WELCOME_MESSAGE, apply_portal_branding, apply_subpage_console_branding
from core.config import REVOKED_ADMIN_EMAILS, get_firebase_web_config, is_admin_email
from core.dependencies import (
    auth_cookie_domain,
    clear_auth_cookie,
    enforce_console_api_access,
    extract_all_auth_tokens,
    extract_epts_session_id,
    get_current_user_optional,
    is_https_request,
    resolve_platform_scope,
    resolve_sso_session,
    set_auth_cookie,
    sync_sso_cookie_if_needed,
)
from core.firebase_app import get_firebase_runtime_status, verify_firebase_id_token
from core.firebase_store import (
    authenticate_email_password_user,
    authenticate_or_register_firebase_user,
    create_portal_session,
    get_portal_session,
    get_recent_feedback,
    log_usage,
    register_email_password_user,
    register_user_profile,
    revoke_portal_session,
    save_feedback,
    update_feedback_reply,
    update_user_admin,
    update_user_profile_details,
)
from core.templating import load_portal_shell_html
from dsr import service as automation_service

logger = logging.getLogger("portal_router")
router = APIRouter(tags=["Dual-Domain Portal & Authentication"])

_get_sid = extract_epts_session_id


def serialize_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    clean_gmail = str(user.get("gmail") or user.get("email") or "").strip().lower()
    is_adm = (
        clean_gmail not in REVOKED_ADMIN_EMAILS
        and (bool(user.get("is_admin")) or is_admin_email(clean_gmail))
    )
    desig = str(user.get("designation") or "").strip()
    desig_other = str(user.get("designation_other") or "").strip()
    effective_desig = desig_other if (desig == "OTHER" and desig_other) else (desig or "CITIZEN" if desig == "CITIZEN" else "OFFICER")
    name = str(user.get("name") or "").strip()
    surname = str(user.get("surname") or "").strip()
    display_name = str(user.get("display_name") or user.get("username") or name or "Officer").strip()

    return {
        "user_id": user.get("user_id"),
        "firebase_uid": user.get("firebase_uid") or user.get("google_uid") or "",
        "name": name,
        "surname": surname,
        "display_name": display_name,
        "username": str(user.get("username") or display_name or user.get("user_id") or "").strip(),
        "gender": str(user.get("gender") or "").strip(),
        "state": str(user.get("state") or "Telangana").strip(),
        "district": str(user.get("district") or "").strip(),
        "mandal": str(user.get("mandal") or "").strip(),
        "village_gp": str(user.get("village_gp") or user.get("village") or "").strip(),
        "village": str(user.get("village_gp") or user.get("village") or "").strip(),
        "gmail": clean_gmail,
        "email": clean_gmail,
        "designation": desig,
        "designation_other": desig_other,
        "effective_designation": effective_desig,
        "role": user.get("role") or "",
        "role_label": user.get("role") or ("Citizen" if desig == "CITIZEN" else "Mandal Level"),
        "mobile_number": user.get("mobile_number") or "",
        "phone": user.get("mobile_number") or "",
        "auth_provider": user.get("auth_provider") or "email",
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

@router.get("/admin", include_in_schema=False)
def portal_admin_page(request: Request) -> Response:
    """Admin access is strictly separated onto https://admin.panchayatautomation.in."""
    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    if host == "panchayatautomation.in" or (host.endswith(".panchayatautomation.in") and not host.startswith("admin.")):
        return RedirectResponse("https://admin.panchayatautomation.in/", status_code=307)
    return portal_home_page(request)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
@router.get("/autoreports", response_class=HTMLResponse, include_in_schema=False)
@router.get("/manualreports", response_class=HTMLResponse, include_in_schema=False)
@router.get("/tools", response_class=HTMLResponse, include_in_schema=False)
@router.get("/softwares", response_class=HTMLResponse, include_in_schema=False)
@router.get("/software", response_class=HTMLResponse, include_in_schema=False)
@router.get("/eptauto", response_class=HTMLResponse, include_in_schema=False)
@router.get("/naresh", response_class=HTMLResponse, include_in_schema=False)
@router.get("/reports", response_class=HTMLResponse, include_in_schema=False)
def portal_home_page(request: Request) -> HTMLResponse:
    """Render web shell branded for the active host and upgrade active sessions to SSO cookie."""
    html = apply_portal_branding(load_portal_shell_html(), request)
    user = None
    tok = ""
    try:
        user, tok = resolve_sso_session(request)
    except Exception as exc:
        logger.warning("SSO session resolution error (non-fatal): %s", exc)

    if user is not None:
        html = html.replace(
            '<body class="state-home-login">',
            '<body class="state-logged-in state-auth-resolving">',
            1,
        ).replace(
            '<header id="site-top-ribbon" class="site-top-ribbon" style="display:none;">',
            '<header id="site-top-ribbon" class="site-top-ribbon" style="display:block;">',
            1,
        ).replace(
            '<div id="portal-hero-card" class="gov-login-wrapper" style="margin-bottom: 24px;">',
            '<div id="portal-hero-card" class="gov-login-wrapper" style="display:none; margin-bottom: 24px;">',
            1,
        )
    resp = HTMLResponse(html)
    try:
        sync_sso_cookie_if_needed(request, resp, user, tok)
    except Exception as exc:
        logger.warning("SSO cookie sync error (non-fatal): %s", exc)
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


@router.post("/api/softwares/track-download", include_in_schema=False)
async def api_track_software_download(request: Request):
    """Record software package download telemetry for officer audit logs."""
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
    item_id = str(data.get("item_id") or request.query_params.get("id") or "general").strip()
    item_title = str(data.get("item_title") or request.query_params.get("title") or item_id).strip()
    filename = str(data.get("filename") or request.query_params.get("filename") or "").strip()

    user = None
    try:
        user, _ = resolve_sso_session(request)
    except Exception:
        user = None

    log_usage(
        user_id=str((user or {}).get("user_id") or "guest"),
        gmail=str((user or {}).get("gmail") or ""),
        user_name=str((user or {}).get("name") or ""),
        designation=str((user or {}).get("designation") or ""),
        platform_scope="portal",
        module="softwares",
        action="download",
        tool_id=f"softwares:{item_id}",
        tool_name=f"Download {item_title}",
        category="Softwares & Drivers",
        details=f"File: {filename}" if filename else f"Package: {item_id}",
    )
    return {"success": True, "tracked": True}


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


@router.get("/api/feedback", include_in_schema=False)
def api_get_public_feedback(limit: int = 100) -> dict[str, Any]:
    """Return public community feedback & suggestions submissions visible to everyone."""
    rows = get_recent_feedback(limit=max(1, min(200, int(limit))))
    public_rows = []
    for r in rows:
        public_rows.append({
            "feedback_id": str(r.get("feedback_id") or r.get("id") or ""),
            "id": str(r.get("feedback_id") or r.get("id") or ""),
            "name": str(r.get("name") or "Officer"),
            "designation": str(r.get("designation") or ""),
            "category": str(r.get("category") or "General Feedback"),
            "message": str(r.get("message") or ""),
            "rating": int(r.get("rating") or 5),
            "created_at": str(r.get("created_at") or ""),
            "admin_reply": str(r.get("admin_reply") or ""),
            "admin_replied_at": str(r.get("admin_replied_at") or ""),
            "admin_name": str(r.get("admin_name") or ""),
            "status": str(r.get("status") or ("replied" if r.get("admin_reply") else "open")),
        })
    return {"success": True, "feedback": public_rows, "count": len(public_rows)}


@router.post("/api/feedback/{feedback_id}/reply", include_in_schema=False)
async def api_post_feedback_reply(feedback_id: str, request: Request):
    """Directly post an official administrator reply to a feedback or suggestion."""
    session_user = (
        get_current_user_optional(request)
        or get_current_user_optional(request, app_scope="console")
        or get_current_user_optional(request, app_scope="portal")
    )
    if not session_user or not session_user.get("is_admin"):
        return JSONResponse(
            {"success": False, "message": "Only platform administrators can post official replies."},
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

    reply_text = str(data.get("reply") or data.get("admin_reply") or "").strip()
    if not reply_text:
        return JSONResponse(
            {"success": False, "message": "Reply message cannot be empty."},
            status_code=400,
        )

    admin_name = str(session_user.get("name") or "Administrator").strip()
    admin_uid = str(session_user.get("user_id") or "")

    try:
        record = update_feedback_reply(
            feedback_id=feedback_id,
            admin_reply=reply_text,
            admin_name=admin_name,
            admin_user_id=admin_uid,
        )
        return {
            "success": True,
            "message": "Admin reply published successfully.",
            "record": record,
        }
    except Exception as exc:
        logger.error("Failed to post feedback reply: %s", exc)
        return JSONResponse(
            {"success": False, "message": f"Failed to post reply: {exc}"},
            status_code=500,
        )


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

    import secrets
    user_sid = f"sid_{user_record['user_id']}_{secrets.token_hex(8)}"
    response.set_cookie(
        key="epts_session_id",
        value=user_sid,
        httponly=False,
        samesite="lax",
        secure=is_https_request(request),
        domain=auth_cookie_domain(request),
        path="/",
    )
    try:
        automation_service.get_or_create_session(user_sid, owner_user_id=str(user_record["user_id"]))
    except Exception:
        pass

    return {
        "success": True,
        "token": token,
        "epts_session_id": user_sid,
        "platform_scope": scope,
        "user": serialize_user_payload(user_record),
        "is_first_time": is_new,
        "profile_completed": bool(user_record.get("profile_completed", False)),
        "message": f"{WELCOME_MESSAGE}, {user_record.get('name', 'Officer')}!",
    }


@router.post("/api/auth/register", include_in_schema=False)
async def api_auth_register(request: Request, response: Response):
    """Register a new officer or citizen account with email, password, and profile fields."""
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

    email = str(data.get("email") or data.get("gmail") or "").strip().lower()
    password = str(data.get("password") or "")
    full_name = str(data.get("full_name") or data.get("name") or "").strip()
    surname = str(data.get("surname") or "").strip()
    name = str(data.get("name") or full_name).strip()
    display_name = str(data.get("display_name") or data.get("username") or full_name or name).strip()
    gender = str(data.get("gender") or "").strip()
    mobile_number = str(data.get("mobile_number") or data.get("phone") or "").strip()
    state = str(data.get("state") or "").strip()
    district = str(data.get("district") or "").strip()
    mandal = str(data.get("mandal") or "").strip()
    village_gp = str(data.get("village_gp") or data.get("gram_panchayat") or data.get("village") or "").strip()
    designation = str(data.get("designation") or "CITIZEN").strip().upper()
    designation_other = str(data.get("designation_other") or "").strip()

    try:
        user_record = register_email_password_user(
            email=email,
            password=password,
            full_name=full_name,
            surname=surname,
            name=name,
            display_name=display_name,
            gender=gender,
            mobile_number=mobile_number,
            state=state,
            district=district,
            mandal=mandal,
            village_gp=village_gp,
            designation=designation,
            designation_other=designation_other,
        )
    except (ValueError, PermissionError) as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        return JSONResponse({"success": False, "message": f"Registration failed: {exc}"}, status_code=500)

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
        action="email_register",
    )

    import secrets
    user_sid = f"sid_{user_record['user_id']}_{secrets.token_hex(8)}"
    response.set_cookie(
        key="epts_session_id",
        value=user_sid,
        httponly=False,
        samesite="lax",
        secure=is_https_request(request),
        domain=auth_cookie_domain(request),
        path="/",
    )
    try:
        automation_service.get_or_create_session(user_sid, owner_user_id=str(user_record["user_id"]))
    except Exception:
        pass

    return {
        "success": True,
        "token": token,
        "epts_session_id": user_sid,
        "platform_scope": scope,
        "user": serialize_user_payload(user_record),
        "message": f"Account registered successfully! Welcome to Panchayat Automation, {user_record.get('name', 'Officer')}!",
    }


@router.post("/api/auth/email-login", include_in_schema=False)
@router.post("/api/auth/login", include_in_schema=False)
async def api_auth_email_login(request: Request, response: Response):
    """Authenticate via registered email address and password."""
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

    email = str(data.get("email") or data.get("gmail") or "").strip().lower()
    password = str(data.get("password") or "")

    try:
        user_record = authenticate_email_password_user(
            email=email,
            password=password,
            platform_scope=scope,
        )
    except PermissionError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=403)
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        logger.error("Email login error: %s", exc)
        return JSONResponse({"success": False, "message": f"Sign-in failed: {exc}"}, status_code=500)

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
        action="email_login",
    )

    import secrets
    user_sid = f"sid_{user_record['user_id']}_{secrets.token_hex(8)}"
    response.set_cookie(
        key="epts_session_id",
        value=user_sid,
        httponly=False,
        samesite="lax",
        secure=is_https_request(request),
        domain=auth_cookie_domain(request),
        path="/",
    )
    try:
        automation_service.get_or_create_session(user_sid, owner_user_id=str(user_record["user_id"]))
    except Exception:
        pass

    return {
        "success": True,
        "token": token,
        "epts_session_id": user_sid,
        "platform_scope": scope,
        "user": serialize_user_payload(user_record),
        "message": f"{WELCOME_MESSAGE}, {user_record.get('name', 'Officer')}!",
    }


@router.post("/api/auth/update-profile", include_in_schema=False)
async def api_auth_update_profile(request: Request, response: Response):
    """Update profile details for currently logged-in user."""
    scope = resolve_platform_scope(request)
    session_user, token = resolve_sso_session(request, scope)
    if not session_user or not token:
        return JSONResponse({"success": False, "message": "Sign-in required to edit your profile."}, status_code=401)

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
    full_name = str(data.get("full_name") or data.get("name") or "").strip()
    name = str(data.get("name") or full_name).strip()
    try:
        updated = update_user_profile_details(
            user_id=user_id,
            full_name=full_name,
            surname=str(data.get("surname") or "").strip(),
            name=name,
            display_name=str(data.get("display_name") or data.get("username") or full_name or name).strip(),
            gender=str(data.get("gender") or "").strip(),
            mobile_number=str(data.get("mobile_number") or data.get("phone") or "").strip(),
            state=str(data.get("state") or "").strip(),
            district=str(data.get("district") or "").strip(),
            mandal=str(data.get("mandal") or "").strip(),
            village_gp=str(data.get("village_gp") or data.get("gram_panchayat") or data.get("village") or "").strip(),
            designation=str(data.get("designation") or "").strip(),
            designation_other=str(data.get("designation_other") or "").strip(),
        )
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        logger.error("Profile update error: %s", exc)
        return JSONResponse({"success": False, "message": f"Could not update profile: {exc}"}, status_code=500)

    log_usage(
        user_id=user_id,
        gmail=str(updated.get("gmail") or ""),
        platform_scope=scope,
        module="profile",
        action="update_profile_full",
    )

    return {
        "success": True,
        "message": "Profile updated successfully!",
        "user": serialize_user_payload(updated),
    }


@router.post("/api/auth/logout", include_in_schema=False)
@router.post("/api/auth/portal-logout", include_in_schema=False)
@router.get("/api/auth/portal-logout", include_in_schema=False)
def api_portal_logout(request: Request, response: Response):
    scope = resolve_platform_scope(request)
    for tok in extract_all_auth_tokens(request, scope):
        revoke_portal_session(tok)
    clear_auth_cookie(response, scope, request)

    dom = auth_cookie_domain(request)
    response.delete_cookie("epts_session_id", domain=dom, path="/")
    response.delete_cookie("epts_session_id", path="/")
    response.delete_cookie("ept_session_id", domain=dom, path="/")
    response.delete_cookie("ept_session_id", path="/")

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
        try:
            from inspections.service import clear_session_inspections
            clear_session_inspections(session_id=sid)
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
    try:
        scope = resolve_platform_scope(request)
        user, tok = resolve_sso_session(request, scope)
        if user is not None and scope == "portal" and not user.get("can_access_portal", True):
            user = None
        if user is not None:
            sync_sso_cookie_if_needed(request, response, user, tok)
        policy = get_access_policy()["flags"]
        c_uid = str(user.get("user_id") if user else "").strip()
        epts_sid = str(getattr(request.state, "session_id", "") or "").strip()
        if not epts_sid and user:
            epts_sid = extract_epts_session_id(request, user_id=c_uid)
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
    except Exception as exc:
        logger.error("Error in api_portal_status (resilient fallback): %s", exc)
        return {
            "authenticated": False,
            "platform_scope": "portal",
            "epts_session_id": "",
            "access_policy": get_access_policy()["flags"],
            **_firebase_client_payload(),
            "user": None,
            "profile_completed": False,
        }


@router.get("/api/auth/department-status", include_in_schema=False)
def api_department_status(request: Request) -> dict[str, Any]:
    """Centralized Stage-2 Department Login verification endpoint across all Console modules."""
    console_user = enforce_console_api_access(request)
    c_uid = str(console_user["user_id"]) if console_user else ""
    sid = extract_epts_session_id(request, user_id=c_uid)
    try:
        st = automation_service.get_session_status(session_id=sid, owner_user_id=c_uid)
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


@router.post("/api/auth/update-designation", include_in_schema=False)
async def api_update_designation(request: Request, response: Response):
    scope = resolve_platform_scope(request)
    session_user, token = resolve_sso_session(request, scope)
    if not session_user or not token:
        return JSONResponse({"success": False, "message": "Portal authentication is required to change designation."}, status_code=401)

    data: dict[str, Any] = {}
    try:
        data = await request.json()
    except Exception:
        pass
    new_desig = str(data.get("designation") or "").strip().upper()
    user_id = str(session_user["user_id"]).strip()

    ok, msg, updated = update_user_admin(user_id, updates_dict={"designation": new_desig})
    if not ok or not updated:
        return JSONResponse({"success": False, "message": msg or "Failed to update designation."}, status_code=400)

    log_usage(
        user_id=user_id,
        gmail=str(updated.get("gmail") or ""),
        platform_scope=scope,
        module="profile",
        action="update_designation",
    )
    return {
        "success": True,
        "message": f"Designation updated to {new_desig} successfully.",
        "designation": new_desig,
        "user": serialize_user_payload(updated),
    }

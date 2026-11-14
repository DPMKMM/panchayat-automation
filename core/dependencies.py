"""Shared FastAPI dependencies, dual-domain scope resolution, and HttpOnly cookie helpers."""

from __future__ import annotations

import os
from typing import Any, Literal, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException, Request, Response

from core.access_policy import can_user_access_automated_reports
from core.config import REVOKED_ADMIN_EMAILS, is_admin_email
from core.firebase_store import SESSION_TTL_SECONDS, get_portal_session

PORTAL_COOKIE_NAME = "portal_token"
CONSOLE_COOKIE_NAME = "console_token"
SSO_COOKIE_NAME = "epanchayat_sso"

ScopeType = Literal["portal", "console"]


def is_https_request(request: Request) -> bool:
    proto = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
    return request.url.scheme == "https" or proto == "https"


def auth_cookie_domain(request: Optional[Request]) -> Optional[str]:
    """Share SSO cookies across *.panchayatautomation.in on live HTTPS requests.

    Keeps host-only cookies on localhost, HTTP dev servers, and default TestClient
    requests so local sessions and HTTP unit tests retain their cookie jars.
    """
    if request is None or not is_https_request(request):
        return None
    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    if host == "panchayatautomation.in" or host.endswith(".panchayatautomation.in"):
        return ".panchayatautomation.in"
    return None


def _referer_implies_console(request: Request) -> Optional[ScopeType]:
    ref = str(request.headers.get("referer") or "").strip()
    if not ref:
        return None
    try:
        parsed = urlparse(ref)
        ref_host = (parsed.hostname or "").lower()
        if (
            ref_host.startswith("autoreports.")
            or ref_host.startswith("www.autoreports.")
            or ref_host.startswith("reports.")
            or ref_host.startswith("www.reports.")
        ):
            return "console"
        qs = parse_qs(parsed.query)
        site_vals = [v.strip().lower() for v in qs.get("site", [])]
        if any(v in ("reports", "console") for v in site_vals):
            return "console"
        if any(v == "portal" for v in site_vals):
            return "portal"
    except Exception:
        pass
    return None


def resolve_platform_scope(request: Request, explicit_scope: str = "") -> ScopeType:
    """Determine whether the request targets Platform 1 ('portal') or Platform 2 ('console')."""
    exp = str(explicit_scope or "").strip().lower()
    if exp in ("reports", "console"):
        return "console"
    if exp == "portal":
        return "portal"

    header_scope = str(request.headers.get("X-Platform-Scope") or "").strip().lower()
    if header_scope in ("reports", "console"):
        return "console"
    if header_scope == "portal":
        return "portal"

    query_site = str(request.query_params.get("site") or "").strip().lower()
    if query_site in ("reports", "console"):
        return "console"
    if query_site == "portal":
        return "portal"

    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    if (
        host.startswith("autoreports.")
        or host.startswith("www.autoreports.")
        or host.startswith("reports.")
        or host.startswith("www.reports.")
    ):
        return "console"

    ref_scope = _referer_implies_console(request)
    if ref_scope is not None:
        return ref_scope

    path = (request.url.path or "").strip().lower()
    if (
        path.startswith("/api/naresh/")
        or path.startswith("/api/balance/")
        or path.startswith("/api/mas/")
        or path.startswith("/api/reports/mas-consolidated/")
    ):
        return "console"

    return "portal"


def cookie_name_for_scope(scope: ScopeType) -> str:
    return CONSOLE_COOKIE_NAME if scope == "console" else PORTAL_COOKIE_NAME


def set_sso_cookie(response: Response, token: str, request: Request) -> None:
    """Issue shared HttpOnly SameSite=Lax SSO cookie across .panchayatautomation.in on HTTPS prod."""
    response.set_cookie(
        key=SSO_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/",
        domain=auth_cookie_domain(request),
    )


def set_auth_cookie(response: Response, token: str, app_scope: ScopeType, request: Request) -> None:
    """Issue scoped cookie and shared SSO cookie so one Firebase login works across subdomains."""
    cookie_domain = auth_cookie_domain(request)
    response.set_cookie(
        key=cookie_name_for_scope(app_scope),
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/",
        domain=cookie_domain,
    )
    set_sso_cookie(response, token, request)


def clear_auth_cookie(
    response: Response,
    app_scope: Optional[ScopeType] = None,
    request: Optional[Request] = None,
) -> None:
    """Clear SSO and scoped cookies across both host-only and parent subdomain scopes."""
    cookie_domain = auth_cookie_domain(request)
    for name in (SSO_COOKIE_NAME, PORTAL_COOKIE_NAME, CONSOLE_COOKIE_NAME):
        response.delete_cookie(key=name, path="/")
        if cookie_domain:
            response.delete_cookie(key=name, path="/", domain=cookie_domain)


def _extract_header_token(request: Request, app_scope: ScopeType) -> str:
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        tok = auth_header[7:].strip()
        if tok:
            return tok
    primary_hdr = "X-Console-Token" if app_scope == "console" else "X-Portal-Token"
    fallback_hdr = "X-Portal-Token" if app_scope == "console" else "X-Console-Token"
    return str(request.headers.get(primary_hdr) or request.headers.get(fallback_hdr) or "").strip()


def extract_all_auth_tokens(request: Request, app_scope: Optional[ScopeType] = None) -> list[str]:
    """Return deduplicated non-empty tokens from request headers, SSO cookie, and scoped cookies."""
    scope = app_scope or resolve_platform_scope(request)
    primary_cookie = cookie_name_for_scope(scope)
    secondary_cookie = PORTAL_COOKIE_NAME if primary_cookie == CONSOLE_COOKIE_NAME else CONSOLE_COOKIE_NAME
    candidates = [
        _extract_header_token(request, scope),
        str(request.cookies.get(SSO_COOKIE_NAME) or "").strip(),
        str(request.cookies.get(primary_cookie) or "").strip(),
        str(request.cookies.get(secondary_cookie) or "").strip(),
    ]
    seen: list[str] = []
    for tok in candidates:
        if tok and tok not in seen:
            seen.append(tok)
    return seen


def get_scoped_token(request: Request, app_scope: ScopeType) -> str:
    """Extract highest-priority auth token across explicit headers, SSO cookie, and scoped cookies."""
    tokens = extract_all_auth_tokens(request, app_scope)
    return tokens[0] if tokens else ""


def resolve_sso_session(
    request: Request,
    app_scope: Optional[ScopeType] = None,
) -> tuple[Optional[dict[str, Any]], str]:
    """Validate active Firebase SSO or scoped session token cleanly across subdomains."""
    scope = app_scope or resolve_platform_scope(request)
    tok = get_scoped_token(request, scope)
    if not tok:
        return None, ""
    return get_portal_session(tok, app_scope=None), tok


def sync_sso_cookie_if_needed(
    request: Request,
    response: Response,
    user: Optional[dict[str, Any]],
    token: str,
) -> None:
    """Promote an active session to the shared .panchayatautomation.in SSO cookie when missing."""
    if not user or not token:
        return
    current_sso = str(request.cookies.get(SSO_COOKIE_NAME) or "").strip()
    if current_sso != token:
        set_sso_cookie(response, token, request)


def get_current_user_optional(request: Request, app_scope: Optional[ScopeType] = None) -> Optional[dict[str, Any]]:
    """Return authenticated user dict via SSO/scoped session if valid and permitted, else None."""
    scope: ScopeType = app_scope or resolve_platform_scope(request)
    user, _ = resolve_sso_session(request, scope)
    if user is None:
        return None
    if scope == "portal" and not user.get("can_access_portal", True):
        return None
    return user


def require_platform_user(request: Request, app_scope: Optional[ScopeType] = None) -> dict[str, Any]:
    """Require an active authenticated Google SSO user for the given platform scope."""
    scope: ScopeType = app_scope or resolve_platform_scope(request)
    user, tok = resolve_sso_session(request, scope)
    if not tok or user is None:
        raise HTTPException(
            status_code=401,
            detail=f"Google Sign-In required to access {'e-Panchayat Automation Console' if scope == 'console' else 'e-Panchayat Automation'}.",
        )
    if scope == "portal" and not user.get("can_access_portal", True):
        raise HTTPException(status_code=403, detail="Access to e-Panchayat Automation is restricted for your account.")
    if scope == "console" and not can_user_access_automated_reports(user):
        raise HTTPException(
            status_code=403,
            detail="Automated Reports access is disabled or requires an active subscription.",
        )
    return user


def require_portal_or_console_user(request: Request) -> dict[str, Any]:
    """Accept an authenticated SSO user permitted on the active platform scope."""
    scope = resolve_platform_scope(request)
    user = get_current_user_optional(request, app_scope=scope)
    if user is not None:
        return user
    raise HTTPException(status_code=401, detail="Authentication required. Please sign in with Google.")


def _is_disallowed_admin_host(request: Request) -> bool:
    """Return True when a public user portal host tries to invoke /api/admin/* endpoints."""
    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    if not host:
        return False
    if host.startswith("admin.") or host.startswith("www.admin."):
        return False
    # Block admin APIs on user-facing production domains; allow testserver/localhost for tests & local dev
    if host == "panchayatautomation.in" or host.endswith(".panchayatautomation.in"):
        return True
    return False


def require_admin_user(request: Request) -> dict[str, Any]:
    """Strict dependency requiring an active Administrator Google user on admin.panchayatautomation.in."""
    if _is_disallowed_admin_host(request):
        raise HTTPException(
            status_code=403,
            detail="Administrator access is separated onto https://admin.panchayatautomation.in.",
        )

    scope = resolve_platform_scope(request)
    user, tok = resolve_sso_session(request, scope)
    if not tok or user is None:
        raise HTTPException(status_code=401, detail="Administrator sign-in required.")

    clean_gmail = str(user.get("gmail") or "").strip().lower()
    is_adm = (
        clean_gmail not in REVOKED_ADMIN_EMAILS
        and (bool(user.get("is_admin")) or is_admin_email(clean_gmail))
    )
    if not is_adm:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return user


def _is_explicit_console_request(request: Request) -> bool:
    """Return True when the request explicitly targets Console via env, host, header, query, or referer."""
    is_prod = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    query_site = str(request.query_params.get("site") or "").strip().lower()
    header_scope = str(request.headers.get("X-Platform-Scope") or "").strip().lower()
    ref_scope = _referer_implies_console(request)
    return bool(
        is_prod
        or host.startswith("autoreports.")
        or host.startswith("www.autoreports.")
        or host.startswith("reports.")
        or host.startswith("www.reports.")
        or query_site in ("reports", "console")
        or header_scope in ("reports", "console")
        or ref_scope == "console"
    )


def _is_reports_subdomain(request: Request) -> bool:
    raw_host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    return (
        host.startswith("autoreports.")
        or host.startswith("www.autoreports.")
        or host.startswith("reports.")
        or host.startswith("www.reports.")
    )


def enforce_console_api_access(request: Request) -> Optional[dict[str, Any]]:
    """Enforce Stage-1 Firebase SSO + policy/account permissions on Console/Automation APIs."""
    user, tok = resolve_sso_session(request, "console")
    if tok:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Console session expired or invalid. Please sign in with Google.",
            )
        if not can_user_access_automated_reports(user):
            raise HTTPException(
                status_code=403,
                detail="An active subscription or Console permission is required to access Automated Reports Console.",
            )
        return user

    if _is_explicit_console_request(request):
        raise HTTPException(
            status_code=401,
            detail="Google authentication required for e-Panchayat Automation Console.",
        )
    return None


def extract_epts_session_id(request: Request, user_id: str = "") -> str:
    """Resolve canonical Stage-2 EPTS session ID across state, headers, query params, and cookies.

    If no explicit session ID is sent by an authenticated Google console user, scopes the session
    strictly to that user's ID to prevent cross-user collisions on a shared 'default' session.
    """
    state_sid = getattr(request.state, "session_id", None)
    if state_sid and str(state_sid).strip():
        return str(state_sid).strip()
    sid = (
        request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
        or request.headers.get("X-EPTS-Session-ID")
        or request.headers.get("x-epts-session-id")
        or request.query_params.get("session_id", "")
        or request.cookies.get("epts_session_id")
        or request.cookies.get("ept_session_id")
        or ""
    ).strip()
    if sid and sid != "default":
        return sid
    clean_uid = str(user_id or "").strip()
    if clean_uid:
        return f"user_{clean_uid}"
    return sid or "default"


def enforce_department_api_access(
    request: Request,
    *,
    always_require: bool = False,
) -> tuple[Optional[dict[str, Any]], str]:
    """Centralized Stage-1 Console Google + Stage-2 EPTS Department Login verifier.

    Args:
        request: Incoming FastAPI request.
        always_require: Enforce active Department Login even when invoked outside
            explicit Console scope (used for report generation endpoints).
    Returns:
        Tuple of `(console_user_or_none, resolved_session_id)`.
    """
    console_user = enforce_console_api_access(request)
    c_uid = str(console_user["user_id"]) if console_user else ""
    sid = extract_epts_session_id(request, user_id=c_uid)
    requires_dept = bool(always_require or console_user is not None or _is_explicit_console_request(request))
    if requires_dept:
        from core.session_manager import get_or_create_session, is_authenticated

        sess = get_or_create_session(sid, owner_user_id=c_uid)
        if not is_authenticated(session_id=sid):
            is_expired = sess.get("status") == "expired"
            detail = (
                "Department Login session has expired. Please complete Department Login again."
                if is_expired
                else "Department Login & OTP required. Please complete Department Login first."
            )
            raise HTTPException(
                status_code=401,
                detail=detail,
                headers={"X-Dept-Auth-Required": "true"},
            )
    return console_user, sid

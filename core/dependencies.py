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

ScopeType = Literal["portal", "console"]


def is_https_request(request: Request) -> bool:
    proto = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
    return request.url.scheme == "https" or proto == "https"


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


def set_auth_cookie(response: Response, token: str, app_scope: ScopeType, request: Request) -> None:
    """Issue host-only HttpOnly SameSite=Lax cookie scoped exclusively to portal or console."""
    response.set_cookie(
        key=cookie_name_for_scope(app_scope),
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response, app_scope: ScopeType) -> None:
    response.delete_cookie(key=cookie_name_for_scope(app_scope), path="/")


def get_scoped_token(request: Request, app_scope: ScopeType) -> str:
    """Extract auth token strictly matching app_scope without cross-platform cookie fallback."""
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        tok = auth_header[7:].strip()
        if tok:
            return tok

    if app_scope == "console":
        hdr = (request.headers.get("X-Console-Token") or request.headers.get("X-Portal-Token") or "").strip()
        if hdr:
            return hdr
        return str(request.cookies.get(CONSOLE_COOKIE_NAME) or "").strip()

    hdr = (request.headers.get("X-Portal-Token") or "").strip()
    if hdr:
        return hdr
    return str(request.cookies.get(PORTAL_COOKIE_NAME) or "").strip()


def get_current_user_optional(request: Request, app_scope: Optional[ScopeType] = None) -> Optional[dict[str, Any]]:
    """Return authenticated user dict for the resolved scope if valid, else None."""
    scope: ScopeType = app_scope or resolve_platform_scope(request)
    token = get_scoped_token(request, scope)
    if not token:
        return None
    return get_portal_session(token, app_scope=scope)


def require_platform_user(request: Request, app_scope: Optional[ScopeType] = None) -> dict[str, Any]:
    """Require an active authenticated Google user for the given platform scope."""
    scope: ScopeType = app_scope or resolve_platform_scope(request)
    token = get_scoped_token(request, scope)
    if not token:
        raise HTTPException(
            status_code=401,
            detail=f"Google Sign-In required to access {'e-Panchayat Automation Console' if scope == 'console' else 'e-Panchayat Automation'}.",
        )
    # Check whether caller presented a token belonging to the wrong scope
    user = get_portal_session(token, app_scope=scope)
    if user is None:
        other_scope: ScopeType = "portal" if scope == "console" else "console"
        if get_portal_session(token, app_scope=other_scope) is not None:
            raise HTTPException(
                status_code=403,
                detail=f"Session belongs to '{other_scope}' platform and cannot access '{scope}'. Please sign in again on this domain.",
            )
        raise HTTPException(status_code=401, detail="Session invalid, expired, or account disabled.")
    return user


def require_portal_or_console_user(request: Request) -> dict[str, Any]:
    """Accept an authenticated user whose token matches the active platform scope."""
    scope = resolve_platform_scope(request)
    user = get_current_user_optional(request, app_scope=scope)
    if user is not None:
        return user
    # Allow console user accessing shared utilities only via console token when on console scope,
    # never allowing cross-cookie fallback blindly.
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
    token = get_scoped_token(request, scope)
    if not token:
        # Check explicit header tokens on either scope if provided by API admin clients
        for cand_scope in ("portal", "console"):
            cand_tok = get_scoped_token(request, cand_scope)  # type: ignore[arg-type]
            if cand_tok:
                cand_user = get_portal_session(cand_tok, app_scope=cand_scope)
                if cand_user:
                    user = cand_user
                    break
        else:
            raise HTTPException(status_code=401, detail="Administrator sign-in required.")
    else:
        user = get_portal_session(token, app_scope=scope)
        if not user:
            raise HTTPException(status_code=401, detail="Valid administrator session required.")

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
    """Enforce Firebase Google auth on Console/Automation APIs across unified Home & Console.

    Strict host isolation:
    - On ``reports.*`` subdomains, ONLY ``console_token`` is accepted (a ``portal_token``
      cookie/token is rejected with 403).
    - On unified Home hosts (apex domain / localhost), a valid ``console_token`` OR a
      valid ``portal_token`` (with ``can_access_console`` enabled) is accepted.
    - Synthetic dev/unit-test calls without explicit Console/Auth headers stay compatible.
    """
    is_reports_host = _is_reports_subdomain(request)
    console_tok = get_scoped_token(request, "console")
    if console_tok:
        user = get_portal_session(console_tok, app_scope="console")
        if user:
            if not can_user_access_automated_reports(user):
                raise HTTPException(
                    status_code=403,
                    detail="An active subscription is required to access Automated Reports Console.",
                )
            return user
        portal_user = get_portal_session(console_tok, app_scope="portal")
        if portal_user is not None:
            if not is_reports_host and can_user_access_automated_reports(portal_user):
                return portal_user
            raise HTTPException(
                status_code=403,
                detail="Platform 1 session cannot access e-Panchayat Automation Console endpoints. Sign in on Console.",
            )
        raise HTTPException(status_code=401, detail="Console session expired or invalid. Please sign in with Google.")

    # Check Platform 1 portal_token cookie / header
    portal_tok = get_scoped_token(request, "portal")
    if portal_tok:
        portal_user = get_portal_session(portal_tok, app_scope="portal")
        if portal_user is not None:
            if is_reports_host:
                raise HTTPException(
                    status_code=403,
                    detail="e-Panchayat Automation Console requires an independent Google Sign-In on Console.",
                )
            if not can_user_access_automated_reports(portal_user):
                raise HTTPException(
                    status_code=403,
                    detail="Automated Reports access is disabled or requires an active subscription.",
                )
            return portal_user

    if _is_explicit_console_request(request):
        raise HTTPException(
            status_code=401,
            detail="Google authentication required for e-Panchayat Automation Console.",
        )
    return None


def extract_epts_session_id(request: Request) -> str:
    """Resolve canonical Stage-2 EPTS session ID across state, headers, query params, and cookies."""
    state_sid = getattr(request.state, "session_id", None)
    if state_sid and str(state_sid).strip():
        return str(state_sid).strip()
    sid = (
        request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
        or request.query_params.get("session_id", "")
        or request.cookies.get("epts_session_id")
        or request.cookies.get("ept_session_id")
        or ""
    ).strip()
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
    sid = extract_epts_session_id(request)
    requires_dept = bool(always_require or console_user is not None or _is_explicit_console_request(request))
    if requires_dept:
        from core.session_manager import get_or_create_session, is_authenticated

        if not is_authenticated(session_id=sid):
            sess = get_or_create_session(sid)
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

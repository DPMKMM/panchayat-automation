"""Administrator Governance Dashboard API Router."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from core.access_policy import DEFAULT_POLICY, get_access_policy, update_access_policy
from core.config import ENVIRONMENT, TEMP_RETENTION_HOURS
from core.firebase_app import get_firebase_runtime_status
from core.firebase_store import (
    get_recent_feedback,
    get_usage_stats,
    get_user_by_id,
    list_users,
    log_usage,
    update_user_admin,
)
from core.dependencies import require_admin_user, resolve_platform_scope
from portal.router import serialize_user_payload

logger = logging.getLogger("admin_router")
router = APIRouter(
    prefix="/api/admin",
    tags=["Administrator Dashboard"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/overview", include_in_schema=False)
def admin_overview(admin_user: dict[str, Any] = Depends(require_admin_user)) -> dict[str, Any]:
    stats = get_usage_stats(days=30)
    policy = get_access_policy()
    return {
        "success": True,
        "admin": serialize_user_payload(admin_user),
        "stats": stats,
        "access_policy": policy,
        "firebase": get_firebase_runtime_status(),
        "environment": os.getenv("ENVIRONMENT", ENVIRONMENT).strip().lower() or "development",
        "temp_retention_hours": float(os.getenv("TEMP_RETENTION_HOURS", str(TEMP_RETENTION_HOURS))),
    }


@router.get("/users", include_in_schema=False)
def admin_list_users(
    search: str = Query(default=""),
    designation: str = Query(default=""),
    role: str = Query(default=""),
    account_status: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows, total = list_users(
        search=search,
        designation=designation,
        role=role,
        account_status=account_status,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "users": [serialize_user_payload(u) for u in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/users/{user_id}", include_in_schema=False)
@router.post("/users/{user_id}", include_in_schema=False)
async def admin_update_user(
    user_id: str,
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
):
    data: dict[str, Any] = {}
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    clean_target_id = str(user_id or "").strip()
    target_existing = get_user_by_id(clean_target_id)
    if not target_existing:
        raise HTTPException(status_code=404, detail=f"User '{clean_target_id}' not found.")

    allowed_fields = {
        "name",
        "designation",
        "role",
        "mobile_number",
        "account_status",
        "can_access_portal",
        "can_access_console",
        "is_admin",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="No recognized user fields were provided for update.")

    # Guard against accidental administrator self-lockout
    if clean_target_id == str(admin_user.get("user_id") or "").strip():
        if "account_status" in updates and str(updates["account_status"]).strip().lower() != "active":
            raise HTTPException(status_code=400, detail="Administrators cannot disable their own account.")
        if "is_admin" in updates and updates["is_admin"] is False:
            raise HTTPException(status_code=400, detail="Administrators cannot revoke their own admin privileges.")

        eff_portal = (
            bool(updates["can_access_portal"])
            if "can_access_portal" in updates
            else bool(target_existing.get("can_access_portal", 1))
        )
        eff_console = (
            bool(updates["can_access_console"])
            if "can_access_console" in updates
            else bool(target_existing.get("can_access_console", 1))
        )
        if not eff_portal and not eff_console:
            raise HTTPException(
                status_code=400,
                detail="Administrators cannot disable both Platform 1 and Console access for their own account.",
            )

    ok, msg, updated = update_user_admin(clean_target_id, updates)
    if not ok or not updated:
        raise HTTPException(status_code=400, detail=msg)

    scope = resolve_platform_scope(request)
    log_usage(
        user_id=str(admin_user["user_id"]),
        platform_scope=scope,
        module="admin",
        action="update_user",
        details=f"target={clean_target_id}; keys={','.join(sorted(updates.keys()))}",
    )
    return {
        "success": True,
        "message": msg,
        "user": serialize_user_payload(updated),
    }


@router.get("/policy", include_in_schema=False)
def admin_get_policy() -> dict[str, Any]:
    return {"success": True, **get_access_policy()}


@router.post("/policy", include_in_schema=False)
@router.patch("/policy", include_in_schema=False)
async def admin_update_policy(
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
):
    data: dict[str, Any] = {}
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    raw_flags = data.get("flags") if isinstance(data.get("flags"), dict) else data
    updates = {k: v for k, v in raw_flags.items() if k in DEFAULT_POLICY}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid policy keys supplied.")

    try:
        updated_policy = update_access_policy(updates, updated_by=str(admin_user["user_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    scope = resolve_platform_scope(request)
    log_usage(
        user_id=str(admin_user["user_id"]),
        platform_scope=scope,
        module="admin",
        action="update_policy",
        details=",".join(f"{k}={v}" for k, v in sorted(updates.items())),
    )
    return {
        "success": True,
        "message": "Platform access policy updated.",
        **updated_policy,
    }


@router.get("/feedback", include_in_schema=False)
def admin_feedback(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    rows = get_recent_feedback(limit=limit)
    return {"success": True, "feedback": rows, "count": len(rows)}


@router.get("/stats", include_in_schema=False)
def admin_stats(days: int = Query(default=30, ge=1, le=365)) -> dict[str, Any]:
    return {"success": True, "days": days, "stats": get_usage_stats(days=days)}

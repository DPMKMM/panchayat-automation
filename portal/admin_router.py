"""Administrator Governance Dashboard API Router."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from core.access_policy import DEFAULT_POLICY, get_access_policy, update_access_policy
from core.billing import get_razorpay_status
from core.config import ENVIRONMENT, TEMP_RETENTION_HOURS
from core.firebase_app import get_firebase_runtime_status
from core.firebase_store import (
    get_recent_feedback,
    get_tool_usage_analytics,
    get_usage_stats,
    get_user_by_id,
    grant_or_activate_subscription,
    list_payments,
    list_subscription_plans,
    list_subscriptions,
    list_users,
    log_usage,
    revoke_user_subscription,
    update_user_admin,
    upsert_subscription_plan,
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
        "razorpay": get_razorpay_status(),
        "plans": list_subscription_plans(include_inactive=True),
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
        "has_automated_subscription",
        "subscription_status",
        "subscription_plan_id",
        "subscription_plan_name",
        "subscription_expires_at",
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


@router.get("/tool-usage", include_in_schema=False)
def admin_tool_usage(days: int = Query(default=30, ge=1, le=365)) -> dict[str, Any]:
    analytics = get_tool_usage_analytics(days=days)
    analytics.pop("active_uids_24h", None)
    analytics.pop("active_uids_7d", None)
    return {"success": True, **analytics}


@router.get("/subscriptions", include_in_schema=False)
def admin_subscriptions_overview() -> dict[str, Any]:
    plans = list_subscription_plans(include_inactive=True)
    subs = list_subscriptions(limit=200)
    payments = list_payments(limit=200)
    policy = get_access_policy()
    users, total_users = list_users(limit=5000)
    subscribed_users = sum(
        1 for u in users if bool(u.get("has_automated_subscription")) or u.get("subscription_status") == "active"
    )
    captured = [p for p in payments if p.get("status") == "captured"]
    total_revenue_inr = round(sum(float(p.get("amount_inr") or 0.0) for p in captured), 2)
    return {
        "success": True,
        "plans": plans,
        "subscriptions": subs,
        "payments": payments,
        "razorpay": get_razorpay_status(),
        "subscription_required": bool(policy["flags"].get("automated_subscription_required", False)),
        "summary": {
            "total_users": total_users,
            "subscribed_users": subscribed_users,
            "total_subscriptions": len(subs),
            "captured_payments": len(captured),
            "total_revenue_inr": total_revenue_inr,
        },
    }


@router.post("/subscriptions/grant", include_in_schema=False)
async def admin_grant_subscription(
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    user_id = str(data.get("user_id") or "").strip()
    plan_id = str(data.get("plan_id") or "plan_monthly").strip()
    duration_raw = data.get("duration_days")
    amount_raw = data.get("amount_inr")
    notes = str(data.get("notes") or "").strip()
    record_payment = bool(data.get("record_payment", False))
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")

    try:
        sub = grant_or_activate_subscription(
            user_id=user_id,
            plan_id=plan_id,
            duration_days=int(duration_raw) if duration_raw else None,
            amount_inr=float(amount_raw) if amount_raw not in (None, "") else None,
            provider="admin_grant",
            granted_by=str(admin_user.get("gmail") or admin_user["user_id"]),
            notes=notes or "Granted by Administrator",
            record_payment=record_payment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_usage(
        user_id=str(admin_user["user_id"]),
        gmail=str(admin_user.get("gmail") or ""),
        platform_scope=resolve_platform_scope(request),
        module="billing",
        action="grant_subscription",
        details=f"target={user_id}; plan={sub['plan_id']}",
    )
    return {"success": True, "message": "Subscription activated for officer.", "subscription": sub}


@router.post("/subscriptions/{user_id}/revoke", include_in_schema=False)
def admin_revoke_subscription(
    user_id: str,
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        updated = revoke_user_subscription(
            user_id=str(user_id).strip(),
            actor=str(admin_user.get("gmail") or admin_user["user_id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    log_usage(
        user_id=str(admin_user["user_id"]),
        gmail=str(admin_user.get("gmail") or ""),
        platform_scope=resolve_platform_scope(request),
        module="billing",
        action="revoke_subscription",
        details=f"target={user_id}",
    )
    return {"success": True, "message": "Subscription cancelled for officer.", "user": serialize_user_payload(updated)}


@router.post("/plans", include_in_schema=False)
async def admin_upsert_plan(
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    try:
        plan = upsert_subscription_plan(
            plan_id=str(data.get("plan_id") or "").strip(),
            name=str(data.get("name") or "").strip(),
            amount_inr=float(data.get("amount_inr") or 0),
            duration_days=int(data.get("duration_days") or 30),
            description=str(data.get("description") or "").strip(),
            code=str(data.get("code") or "").strip(),
            razorpay_plan_id=str(data.get("razorpay_plan_id") or "").strip(),
            features=data.get("features") if isinstance(data.get("features"), list) else [],
            is_active=bool(data.get("is_active", True)),
            sort_order=int(data.get("sort_order") or 10),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_usage(
        user_id=str(admin_user["user_id"]),
        gmail=str(admin_user.get("gmail") or ""),
        platform_scope=resolve_platform_scope(request),
        module="billing",
        action="upsert_plan",
        details=f"plan={plan['plan_id']}; inr={plan['amount_inr']}",
    )
    return {"success": True, "message": "Subscription plan saved.", "plan": plan}

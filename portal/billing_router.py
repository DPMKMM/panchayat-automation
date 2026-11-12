"""User Subscription & Razorpay-Ready Billing API Router."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from core.access_policy import get_access_policy
from core.billing import (
    complete_razorpay_checkout,
    create_razorpay_order,
    get_razorpay_status,
    verify_razorpay_webhook_signature,
)
from core.dependencies import require_portal_or_console_user
from core.firebase_store import (
    capture_razorpay_payment,
    get_user_billing_summary,
    list_subscription_plans,
    log_usage,
)
from portal.router import serialize_user_payload

logger = logging.getLogger("billing_router")
router = APIRouter(prefix="/api/billing", tags=["Subscriptions & Razorpay Billing"])


@router.get("/plans", include_in_schema=False)
def billing_plans() -> dict[str, Any]:
    """Return active subscription plans and Razorpay readiness state."""
    policy = get_access_policy()
    return {
        "success": True,
        "plans": list_subscription_plans(include_inactive=False),
        "razorpay": get_razorpay_status(),
        "subscription_required": bool(policy["flags"].get("automated_subscription_required", False)),
    }


@router.get("/status", include_in_schema=False)
def billing_status(user: dict[str, Any] = Depends(require_portal_or_console_user)) -> dict[str, Any]:
    """Return the signed-in officer's current subscription status, ledger history, and available plans."""
    summary = get_user_billing_summary(str(user["user_id"]))
    policy = get_access_policy()
    return {
        "success": True,
        "user": serialize_user_payload(user),
        "subscription_required": bool(policy["flags"].get("automated_subscription_required", False)),
        "razorpay": get_razorpay_status(),
        "plans": list_subscription_plans(include_inactive=False),
        **summary,
    }


@router.post("/razorpay/create-order", include_in_schema=False)
async def billing_create_razorpay_order(
    request: Request,
    user: dict[str, Any] = Depends(require_portal_or_console_user),
) -> dict[str, Any]:
    """Initiate a Razorpay payment order for the selected subscription plan."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    plan_id = str(data.get("plan_id") or "plan_monthly").strip()
    try:
        order = create_razorpay_order(user, plan_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_usage(
        user_id=str(user["user_id"]),
        gmail=str(user.get("gmail") or ""),
        user_name=str(user.get("name") or ""),
        designation=str(user.get("designation") or ""),
        platform_scope="portal",
        module="billing",
        action="create_razorpay_order",
        details=f"plan={plan_id}; order={order['order_id']}",
    )
    return {"success": True, **order}


@router.post("/razorpay/verify", include_in_schema=False)
async def billing_verify_razorpay_payment(
    request: Request,
    user: dict[str, Any] = Depends(require_portal_or_console_user),
) -> dict[str, Any]:
    """Verify Razorpay Checkout payment signature and activate officer subscription."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body.")

    order_id = str(data.get("razorpay_order_id") or "").strip()
    payment_id = str(data.get("razorpay_payment_id") or "").strip()
    signature = str(data.get("razorpay_signature") or "").strip()
    plan_id = str(data.get("plan_id") or "plan_monthly").strip()
    method = str(data.get("method") or "razorpay").strip()
    if not order_id or not payment_id or not signature:
        raise HTTPException(status_code=400, detail="razorpay_order_id, razorpay_payment_id, and razorpay_signature are required.")

    try:
        result = complete_razorpay_checkout(
            user_id=str(user["user_id"]),
            plan_id=plan_id,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
            method=method,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_usage(
        user_id=str(user["user_id"]),
        gmail=str(user.get("gmail") or ""),
        user_name=str(user.get("name") or ""),
        designation=str(user.get("designation") or ""),
        platform_scope="portal",
        module="billing",
        action="payment_verified",
        details=f"plan={plan_id}; pay={payment_id}",
    )
    return {"success": True, "message": "Subscription activated successfully.", **result}


@router.post("/razorpay/webhook", include_in_schema=False)
async def billing_razorpay_webhook(request: Request) -> dict[str, Any]:
    """Handle verified server-to-server Razorpay webhooks (payment.captured / order.paid)."""
    raw_body = await request.body()
    sig_header = request.headers.get("X-Razorpay-Signature", "")
    try:
        valid = verify_razorpay_webhook_signature(raw_body, sig_header)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature.")

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed webhook JSON.")

    ev_name = str(event.get("event") or "").strip().lower()
    payment_entity = (((event.get("payload") or {}).get("payment") or {}).get("entity") or {})
    notes = payment_entity.get("notes") or {}

    if ev_name in ("payment.captured", "order.paid") and payment_entity:
        uid = str(notes.get("user_id") or "").strip()
        pid = str(notes.get("plan_id") or "plan_monthly").strip()
        r_order_id = str(payment_entity.get("order_id") or "").strip()
        r_pay_id = str(payment_entity.get("id") or "").strip()
        method = str(payment_entity.get("method") or "razorpay").strip()
        if uid and r_pay_id:
            capture_razorpay_payment(
                user_id=uid,
                plan_id=pid,
                razorpay_order_id=r_order_id,
                razorpay_payment_id=r_pay_id,
                method=method,
            )

    return {"success": True, "event": ev_name}

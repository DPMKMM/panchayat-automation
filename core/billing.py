"""Razorpay Payment Gateway & Subscription Verification Helpers.

Reads RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_WEBHOOK_SECRET strictly from environment variables.
When credentials are not yet configured, billing readiness endpoints remain informative without failing startup.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

from core.firebase_store import (
    capture_razorpay_payment,
    get_subscription_plan,
    record_payment_order,
)


def _razorpay_credentials() -> tuple[str, str, str]:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    return key_id, key_secret, webhook_secret


def get_razorpay_status() -> dict[str, Any]:
    """Return safe public Razorpay configuration status (never exposing secret values)."""
    key_id, key_secret, webhook_secret = _razorpay_credentials()
    configured = bool(key_id and key_secret)
    if not configured:
        mode = "unconfigured"
    elif key_id.startswith("rzp_live_"):
        mode = "live"
    else:
        mode = "test"
    masked_key = f"{key_id[:12]}..." if len(key_id) > 12 else ("configured" if key_id else "")
    return {
        "configured": configured,
        "mode": mode,
        "key_id_preview": masked_key,
        "webhook_configured": bool(webhook_secret),
    }


def get_public_razorpay_key_id() -> str:
    """Return Razorpay public Key ID for client checkout (safe public identifier)."""
    key_id, key_secret, _ = _razorpay_credentials()
    if not (key_id and key_secret):
        return ""
    return key_id


def create_razorpay_order(user: dict[str, Any], plan_id: str) -> dict[str, Any]:
    """Create a Razorpay Checkout order for a subscription plan and log the initiated payment."""
    key_id, key_secret, _ = _razorpay_credentials()
    if not (key_id and key_secret):
        raise RuntimeError(
            "Razorpay is not connected yet. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to enable payments."
        )

    plan = get_subscription_plan(plan_id)
    if not plan or not bool(plan.get("is_active", True)):
        raise ValueError("Selected subscription plan is unavailable.")

    amount_paise = int(plan.get("amount_paise") or round(float(plan.get("amount_inr") or 0) * 100))
    if amount_paise <= 0:
        raise ValueError("Paid checkout requires a plan amount greater than 0 INR.")

    payload = {
        "amount": amount_paise,
        "currency": str(plan.get("currency") or "INR"),
        "receipt": f"rcpt_{user['user_id'][:12]}_{plan['code']}"[:40],
        "notes": {
            "user_id": str(user["user_id"]),
            "gmail": str(user.get("gmail") or ""),
            "plan_id": str(plan["plan_id"]),
        },
    }

    resp = httpx.post(
        "https://api.razorpay.com/v1/orders",
        auth=(key_id, key_secret),
        json=payload,
        timeout=20.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Razorpay order creation failed ({resp.status_code}): {resp.text[:240]}")

    order = resp.json()
    order_id = str(order.get("id") or "").strip()
    if not order_id:
        raise RuntimeError("Razorpay returned an empty order id.")

    record_payment_order(
        user_id=str(user["user_id"]),
        plan=plan,
        razorpay_order_id=order_id,
        notes=f"Checkout initiated for {plan['name']}",
    )
    return {
        "order_id": order_id,
        "amount_paise": amount_paise,
        "amount_inr": float(plan.get("amount_inr") or 0.0),
        "currency": str(plan.get("currency") or "INR"),
        "key_id": key_id,
        "plan": plan,
    }


def verify_razorpay_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """Verify Razorpay Checkout HMAC-SHA256 payment signature in constant time."""
    _, key_secret, _ = _razorpay_credentials()
    if not key_secret:
        raise RuntimeError("RAZORPAY_KEY_SECRET is not configured.")
    body = f"{str(razorpay_order_id).strip()}|{str(razorpay_payment_id).strip()}".encode("utf-8")
    expected = hmac.new(key_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(razorpay_signature or "").strip())


def verify_razorpay_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify incoming Razorpay Webhook X-Razorpay-Signature in constant time."""
    _, _, webhook_secret = _razorpay_credentials()
    if not webhook_secret:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET is not configured.")
    expected = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature_header or "").strip())


def complete_razorpay_checkout(
    *,
    user_id: str,
    plan_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    method: str = "razorpay",
) -> dict[str, Any]:
    """Validate Razorpay payment signature, capture transaction ledger, and activate subscription."""
    if not verify_razorpay_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        raise PermissionError("Invalid Razorpay payment signature.")
    return capture_razorpay_payment(
        user_id=user_id,
        plan_id=plan_id,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        method=method,
    )

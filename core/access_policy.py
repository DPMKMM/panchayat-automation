"""Platform Access Policy & Feature Availability Controller.

Launch Policy:
All reporting and departmental automation features across panchayatautomation.in
and reports.panchayatautomation.in are completely free and enabled by default.
This module provides explicit administrator-managed availability toggles without
any commercial billing, payment, subscription, or timed expiration logic.
"""

from __future__ import annotations

from typing import Any

from core.firebase_store import get_all_policy_entries, set_policy_entry

DEFAULT_POLICY: dict[str, bool] = {
    "free_launch_mode": True,
    "portal_enabled": True,
    "console_enabled": True,
    "module_dsr_excel": True,
    "module_dsr_multiday": True,
    "module_dcb_live": True,
    "module_dsr_automation": True,
    "module_gp_balance_automation": True,
    "module_mas_automation": True,
    "automated_subscription_required": False,
}

POLICY_DESCRIPTIONS: dict[str, str] = {
    "free_launch_mode": "Open free access across all available reporting and automation features",
    "portal_enabled": "Platform 1 (panchayatautomation.in) Free Reporting & Analytics availability",
    "console_enabled": "Platform 2 (reports.panchayatautomation.in) e-Panchayat Automation Console availability",
    "module_dsr_excel": "Manual Reports: Daily PS Attendance & DSR Excel Upload",
    "module_dsr_multiday": "Manual Reports: Multiple Days DSR & Attendance Consolidation",
    "module_dcb_live": "Live House Tax DCB Analytics",
    "module_dsr_automation": "Console Automation: Daily PS Attendance & DSR Robot",
    "module_gp_balance_automation": "Console Automation: Thursday GP Balance Robot",
    "module_mas_automation": "Console Automation: Monthly Activity Statement (MAS) Robot",
    "automated_subscription_required": "Require active subscription for Automated Reports Console (currently open without subscription)",
}


def _parse_bool(raw: Any, default: bool = True) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes", "on", "enabled"):
        return True
    if s in ("false", "0", "no", "off", "disabled"):
        return False
    return default


def get_access_policy() -> dict[str, Any]:
    """Return merged effective platform/module availability policy."""
    stored = get_all_policy_entries()
    flags: dict[str, bool] = {}
    meta: dict[str, dict[str, str]] = {}
    for key, default_val in DEFAULT_POLICY.items():
        entry = stored.get(key)
        flags[key] = _parse_bool(entry["value"], default_val) if entry else default_val
        meta[key] = {
            "description": POLICY_DESCRIPTIONS.get(key, key),
            "updated_at": entry.get("updated_at", "") if entry else "",
            "updated_by": entry.get("updated_by", "") if entry else "",
        }
    return {
        "flags": flags,
        "descriptions": POLICY_DESCRIPTIONS,
        "meta": meta,
        **flags,
    }


def is_module_enabled(module_key: str) -> bool:
    """Return True unless explicitly disabled by an administrator."""
    policy = get_access_policy()["flags"]
    if not policy.get(module_key, True):
        return False
    return True


def is_platform_enabled(scope: str) -> bool:
    policy = get_access_policy()["flags"]
    if str(scope).strip().lower() == "console":
        return bool(policy.get("console_enabled", True))
    return bool(policy.get("portal_enabled", True))


def can_user_access_automated_reports(user: dict[str, Any] | None) -> bool:
    """Return whether user can open Automated Reports Console.

    During the current rollout (`automated_subscription_required == False`), any
    officer with ``can_access_console=True`` can use Automated Reports without a
    subscription. When ``automated_subscription_required`` is turned on later, an
    active subscription (``has_automated_subscription`` or ``subscription_status=='active'``)
    is required.
    """
    if not user or not bool(user.get("can_access_console", True)):
        return False
    policy = get_access_policy()["flags"]
    if not policy.get("console_enabled", True):
        return False
    if not policy.get("automated_subscription_required", False):
        return True
    return bool(
        user.get("has_automated_subscription")
        or str(user.get("subscription_status") or "").strip().lower() == "active"
    )


def update_access_policy(updates: dict[str, Any], updated_by: str = "") -> dict[str, Any]:
    """Persist boolean updates for recognized policy keys."""
    for key, value in updates.items():
        if key not in DEFAULT_POLICY:
            raise ValueError(f"Unsupported policy setting: {key}")
        normalized = "true" if _parse_bool(value, True) else "false"
        set_policy_entry(key=key, value=normalized, updated_by=updated_by)
    return get_access_policy()

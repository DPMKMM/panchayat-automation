"""Platform Access Policy & Feature Availability Controller.

Launch Policy:
All reporting and departmental automation features across panchayatautomation.in
and reports.panchayatautomation.in are completely free and enabled by default.
This module provides explicit administrator-managed availability toggles and
Hide/View module visibility controls for the officer workspace.
"""

from __future__ import annotations

from typing import Any

from core.firebase_store import get_all_policy_entries, set_policy_entry

# Master catalog of all modules available on the platform
MODULE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "module_state_format",
        "name": "State Format DSR Report",
        "icon": "🏛️",
        "category": "Automated Reports Robots",
        "description": "Official State Government 14-column mandal-wise attendance matrix with hourly arrival time buckets, % before 9 AM, full-time working PS evaluation, Landscape PDF & Excel downloads.",
        "card_selector": "#card-policy-module_state_format",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_dsr_automation",
        "name": "PS Attendance & DSR Report Robot",
        "icon": "⚡",
        "category": "Automated Reports Robots",
        "description": "Automatic downloading of GM-R 1.2.7 DSR raw data, 1.2.11 Presentees, and 1.2.10 Absentees reports with matched secretary details and official combined Landscape District PDF compilation.",
        "card_selector": "#card-policy-module_dsr_automation",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_gp_balance_automation",
        "name": "Thursday GP Balance Entry Robot",
        "icon": "🏦",
        "category": "Automated Reports Robots",
        "description": "Automated Thursday bank balance entry tracking (GM-R 14.2), calculating % Data Entered, account-wise pending tracking, and drill-down actionable list.",
        "card_selector": "#card-policy-module_gp_balance_automation",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_mas_automation",
        "name": "Monthly Activity Statement (MAS) Robot",
        "icon": "📑",
        "category": "Automated Reports Robots",
        "description": "Official 18-Indicator Executive Matrix (GM-R 5.24 & GM-R 5.23 Births Register) with Legal Landscape PDF and 5-Sheet Styled Excel export via single active EPTS session.",
        "card_selector": "#card-policy-module_mas_automation",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_gp_inspections",
        "name": "Gram Panchayat Weekly Inspections",
        "icon": "🔍",
        "category": "Automated Reports Robots",
        "description": "Automated GM-R 39.1 weekly inspection consolidation across MPO, MPDO, DLPO, DPO, CEO & Deputy CEO designations with Submitted-only filtering, Targets, Balance, PDF & Excel reports.",
        "card_selector": "#card-console-gp-inspections",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_auto_multi_dsr",
        "name": "Automated Multi-Days DSR Robot",
        "icon": "📅",
        "category": "Automated Reports Robots",
        "description": "Automated date-range extraction of daily GM-R 1.2.7 raw data with automatic Sunday and Second Saturday exclusion, custom public holiday filtering, and complete multi-day consolidation into PDF & Excel.",
        "card_selector": "#card-console-auto-multi-dsr",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_dsr_excel",
        "name": "Daily PS Attendance & DSR (Manual Upload)",
        "icon": "📊",
        "category": "Manual Offline Reports",
        "description": "Upload GM-R 1.2.7 DSR spreadsheet along with optional Presentees & Absentees directories to generate 6-Section Landscape District or 2-Page Mandal PDF reports without portal login.",
        "card_selector": "#card-policy-module_dsr_excel",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_dsr_multiday",
        "name": "Multi-Day DSR Consolidation (Manual Upload)",
        "icon": "📅",
        "category": "Manual Offline Reports",
        "description": "Upload multiple daily GM-R 1.2.7 reports to generate District Date-Wise, Mandal Date-Wise & GP Period Summaries with Before 9 AM % highlighting, PDF & Multi-Sheet Excel.",
        "card_selector": "#card-policy-module_dsr_multiday",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_dcb_live",
        "name": "Live House Tax DCB Analytics",
        "icon": "🏛️",
        "category": "Live Revenue Analytics",
        "description": "Real-time statewide Demand, Collection, and Balance (DCB) analytics across 31+ Districts and Mandals with interactive KPIs, PDF, Power BI Visual PDF & Excel exports.",
        "card_selector": "#card-policy-module_dcb_live",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_excel_studio",
        "name": "Excel & Data Studio (70+ Tools)",
        "icon": "📊",
        "category": "Utility Studios",
        "description": "Self-hosted spreadsheet suite: convert, merge, compare, clean, normalize dates, export Bank/QuickBooks formats, and interactive in-browser grid editor.",
        "card_selector": "#card-tool-excel",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_pdf_studio",
        "name": "All-in-One PDF Studio (14 Tools)",
        "icon": "📄",
        "category": "Utility Studios",
        "description": "Merge, split, compress, rotate, organize, convert, watermark, password-protect, and searchable RapidOCR for official government PDF documents.",
        "card_selector": "#card-tool-pdf",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_citizen_services",
        "name": "Citizen Services Monitoring",
        "icon": "👥",
        "category": "Upcoming Services",
        "description": "Real-time monitoring of citizen application delivery, birth/death certificates, and NOC timelines across Mandals.",
        "card_selector": "#card-policy-module_citizen_services",
        "default_enabled": True,
        "default_visible": True,
    },
    {
        "id": "module_trade_licences",
        "name": "Trade Licences Automation",
        "icon": "🏷️",
        "category": "Upcoming Services",
        "description": "Gram Panchayat business and trade licence issuance tracking, fee collection, and expiry renewal automation.",
        "card_selector": "#card-policy-module_trade_licences",
        "default_enabled": True,
        "default_visible": True,
    },
]

DEFAULT_POLICY: dict[str, bool] = {
    # Platform Availability Toggles
    "free_launch_mode": True,
    "portal_enabled": True,
    "console_enabled": True,
    "automated_subscription_required": False,

    # Module Availability Toggles (Enabled / Paused)
    "module_dsr_excel": True,
    "module_dsr_multiday": True,
    "module_dcb_live": True,
    "module_dsr_automation": True,
    "module_state_format": True,
    "module_gp_balance_automation": True,
    "module_mas_automation": True,
    "module_gp_inspections": True,
    "module_auto_multi_dsr": True,
    "module_excel_studio": True,
    "module_pdf_studio": True,
    "module_citizen_services": True,
    "module_trade_licences": True,

    # Module Visibility Toggles (Hide / View)
    "visible_module_dsr_excel": True,
    "visible_module_dsr_multiday": True,
    "visible_module_dcb_live": True,
    "visible_module_dsr_automation": True,
    "visible_module_state_format": True,
    "visible_module_gp_balance_automation": True,
    "visible_module_mas_automation": True,
    "visible_module_gp_inspections": True,
    "visible_module_auto_multi_dsr": True,
    "visible_module_excel_studio": True,
    "visible_module_pdf_studio": True,
    "visible_module_citizen_services": True,
    "visible_module_trade_licences": True,
}

POLICY_DESCRIPTIONS: dict[str, str] = {
    "free_launch_mode": "Open free access across all available reporting and automation features",
    "portal_enabled": "Platform 1 (panchayatautomation.in) Free Reporting & Analytics availability",
    "console_enabled": "Platform 2 (reports.panchayatautomation.in) e-Panchayat Automation Console availability",
    "automated_subscription_required": "Require active subscription for Automated Reports Console (currently open without subscription)",

    "module_dsr_excel": "Manual Reports: Daily PS Attendance & DSR Excel Upload",
    "module_dsr_multiday": "Manual Reports: Multiple Days DSR & Attendance Consolidation",
    "module_dcb_live": "Live House Tax DCB Analytics",
    "module_dsr_automation": "Console Automation: Daily PS Attendance & DSR Robot",
    "module_state_format": "Console Automation: State Format DSR Report (14-Column Matrix)",
    "module_gp_balance_automation": "Console Automation: Thursday GP Balance Robot",
    "module_mas_automation": "Console Automation: Monthly Activity Statement (MAS) Robot",
    "module_gp_inspections": "Console Automation: Gram Panchayat Weekly Inspections",
    "module_auto_multi_dsr": "Console Automation: Automated Multiple Days DSR & PS Attendance Robot",
    "module_excel_studio": "Utility Studio: Excel & Data Studio (70+ Tools)",
    "module_pdf_studio": "Utility Studio: All-in-One PDF Studio (14 Tools)",
    "module_citizen_services": "Upcoming Services: Citizen Applications & Certificates Monitoring",
    "module_trade_licences": "Upcoming Services: Trade Licences Issuance & Renewals Tracking",

    "visible_module_dsr_excel": "Display Visibility: Daily PS Attendance & DSR (Manual)",
    "visible_module_dsr_multiday": "Display Visibility: Multi-Day DSR (Manual)",
    "visible_module_dcb_live": "Display Visibility: Live House Tax DCB Analytics",
    "visible_module_dsr_automation": "Display Visibility: PS Attendance & DSR Robot",
    "visible_module_state_format": "Display Visibility: State Format DSR Report Robot",
    "visible_module_gp_balance_automation": "Display Visibility: Thursday GP Balance Robot",
    "visible_module_mas_automation": "Display Visibility: Monthly Activity Statement (MAS) Robot",
    "visible_module_gp_inspections": "Display Visibility: GP Weekly Inspections Robot",
    "visible_module_auto_multi_dsr": "Display Visibility: Automated Multi-Days DSR Robot",
    "visible_module_excel_studio": "Display Visibility: Excel & Data Studio",
    "visible_module_pdf_studio": "Display Visibility: All-in-One PDF Studio",
    "visible_module_citizen_services": "Display Visibility: Citizen Services",
    "visible_module_trade_licences": "Display Visibility: Trade Licences",
}


def _parse_bool(raw: Any, default: bool = True) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes", "on", "enabled", "view", "visible"):
        return True
    if s in ("false", "0", "no", "off", "disabled", "hide", "hidden"):
        return False
    return default


def get_access_policy() -> dict[str, Any]:
    """Return merged effective platform/module availability and visibility policy."""
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

    # Build enriched modules catalog with live flags
    modules: list[dict[str, Any]] = []
    for mod in MODULE_CATALOG:
        mod_id = mod["id"]
        vis_key = f"visible_{mod_id}"
        is_enabled = flags.get(mod_id, mod.get("default_enabled", True))
        is_visible = flags.get(vis_key, mod.get("default_visible", True))
        modules.append({
            **mod,
            "enabled": is_enabled,
            "visible": is_visible,
            "visibility_key": vis_key,
        })

    return {
        "flags": flags,
        "descriptions": POLICY_DESCRIPTIONS,
        "meta": meta,
        "modules_catalog": modules,
        **flags,
    }


def is_module_enabled(module_key: str) -> bool:
    """Return True unless explicitly disabled by an administrator."""
    policy = get_access_policy()["flags"]
    return bool(policy.get(module_key, True))


def is_module_visible(module_key: str) -> bool:
    """Return True unless explicitly hidden by an administrator."""
    policy = get_access_policy()["flags"]
    vis_key = f"visible_{module_key}"
    if vis_key in policy:
        return bool(policy.get(vis_key, True))
    return bool(policy.get(module_key, True))


def is_platform_enabled(scope: str) -> bool:
    policy = get_access_policy()["flags"]
    if str(scope).strip().lower() == "console":
        return bool(policy.get("console_enabled", True))
    return bool(policy.get("portal_enabled", True))


def can_user_access_automated_reports(user: dict[str, Any] | None) -> bool:
    """Return whether user can open Automated Reports Console."""
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

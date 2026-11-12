"""Centralized branding, identity, and tagline definitions for e-Panchayat Automation."""

from __future__ import annotations

from typing import Any

PLATFORM_NAME = "e-Panchayat Automation"
CONSOLE_NAME = "e-Panchayat Automation Console"
WELCOME_MESSAGE = "Welcome to e-Panchayat Automation"
TAGLINE = "Simplifying Panchayat Administration through Smart Reporting and Automation."
GOV_SUBTITLE = "Independent Panchayat Administration & Reporting Companion"


MANUAL_SECTION_NAME = "e-Panchayat Manual Reports"
TOOLS_SECTION_NAME = "e-Panchayat Tools & Utilities Studio"
ADMIN_SECTION_NAME = "e-Panchayat Admin Control Center"


def _request_host_and_path(request: Any = None) -> tuple[str, str]:
    if request is None:
        return "", ""
    headers = getattr(request, "headers", None) or {}
    raw_host = str(headers.get("x-forwarded-host") or headers.get("host") or "").strip().lower()
    host = raw_host.split(":")[0]
    url = getattr(request, "url", None)
    path = (getattr(url, "path", "") or "").strip().lower()
    return host, path


def is_admin_host_request(request: Any = None) -> bool:
    """Return True when the request targets the dedicated admin portal host (admin.panchayatautomation.in)."""
    host, _ = _request_host_and_path(request)
    return host.startswith("admin.") or host.startswith("www.admin.")


def is_manual_host_request(request: Any = None) -> bool:
    """Return True when the request targets manualreports subdomain."""
    host, _ = _request_host_and_path(request)
    return host.startswith("manualreports.") or host.startswith("www.manualreports.")


def is_tools_host_request(request: Any = None) -> bool:
    """Return True when the request targets tools subdomain."""
    host, _ = _request_host_and_path(request)
    return host.startswith("tools.") or host.startswith("www.tools.")


def is_reports_console_request(request: Any = None) -> bool:
    """Return True when the request targets autoreports/reports subdomain or console routes."""
    if request is None:
        return False

    host, path = _request_host_and_path(request)
    if (
        host.startswith("autoreports.")
        or host.startswith("www.autoreports.")
        or host.startswith("reports.")
        or host.startswith("www.reports.")
    ):
        return True

    if path.startswith("/reports") or path in ("/mas", "/autoreports"):
        return True

    query_params = getattr(request, "query_params", None)
    if query_params is not None:
        site_mode = str(query_params.get("site") or "").strip().lower()
        if site_mode in ("reports", "console"):
            return True

    return False


def _replace_pairs(html: str, pairs: tuple[tuple[str, str], ...]) -> str:
    rendered = html
    for old, new in pairs:
        rendered = rendered.replace(old, new)
    return rendered


def get_branding_context(request: Any = None) -> dict[str, Any]:
    """Build host- and route-aware branding metadata while preserving unified identity."""
    is_console = is_reports_console_request(request)
    return {
        "platform_name": PLATFORM_NAME,
        "console_name": CONSOLE_NAME,
        "welcome_message": WELCOME_MESSAGE,
        "tagline": TAGLINE,
        "gov_subtitle": GOV_SUBTITLE,
        "is_reports_console": is_console,
        "display_title": CONSOLE_NAME if is_console else PLATFORM_NAME,
        "page_title": f"{CONSOLE_NAME} | {PLATFORM_NAME}" if is_console else PLATFORM_NAME,
        "login_prompt": (
            f"Sign in with your Google account to access the {CONSOLE_NAME}."
            if is_console
            else f"Sign in with your Google account to access {PLATFORM_NAME}."
        ),
    }


def apply_portal_branding(html: str, request: Any = None) -> str:
    """Adapt apex vs dedicated section subdomain labels in the portal shell server-side."""
    if not html:
        return html

    if is_reports_console_request(request):
        return _replace_pairs(
            html,
            (
                (
                    '<title id="doc-page-title">e-Panchayat Automation</title>',
                    f'<title id="doc-page-title">{CONSOLE_NAME} | {PLATFORM_NAME}</title>',
                ),
                (
                    '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>',
                    f'<h1 class="gov-portal-main-brand" id="hero-platform-name">{CONSOLE_NAME}</h1>',
                ),
                (
                    '<span id="hero-console-chip" style="display:none;',
                    '<span id="hero-console-chip" style="display:inline-flex;',
                ),
                (
                    '<div id="login-console-badge" style="display:none;',
                    '<div id="login-console-badge" style="display:inline-flex;',
                ),
                (
                    'id="login-panel-subtitle">Sign in with your Google account to access e-Panchayat Automation<',
                    f'id="login-panel-subtitle">Sign in with your Google account to access the {CONSOLE_NAME}<',
                ),
                (
                    '<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">e-Panchayat Automation · Executive Report Modules</h1>',
                    f'<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">{CONSOLE_NAME} · Executive Report Modules</h1>',
                ),
            ),
        )

    if is_manual_host_request(request):
        return _replace_pairs(
            html,
            (
                (
                    '<title id="doc-page-title">e-Panchayat Automation</title>',
                    f'<title id="doc-page-title">Manual Reports | {PLATFORM_NAME}</title>',
                ),
                (
                    '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>',
                    f'<h1 class="gov-portal-main-brand" id="hero-platform-name">{MANUAL_SECTION_NAME}</h1>',
                ),
                (
                    '<span id="hero-console-chip" style="display:none;',
                    '<span id="hero-console-chip" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</span>',
                    '>Manual Reports Studio</span>',
                ),
                (
                    '<div id="login-console-badge" style="display:none;',
                    '<div id="login-console-badge" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</div>',
                    '>Manual Reports Studio</div>',
                ),
                (
                    'id="login-panel-subtitle">Sign in with your Google account to access e-Panchayat Automation<',
                    f'id="login-panel-subtitle">Sign in with your Google account to access {MANUAL_SECTION_NAME}<',
                ),
                (
                    '<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">e-Panchayat Automation · Executive Report Modules</h1>',
                    f'<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">{PLATFORM_NAME} · Manual Reporting Workspace</h1>',
                ),
            ),
        )

    if is_admin_host_request(request):
        return _replace_pairs(
            html,
            (
                (
                    '<title id="doc-page-title">e-Panchayat Automation</title>',
                    f'<title id="doc-page-title">Admin Control Center | {PLATFORM_NAME}</title>',
                ),
                (
                    '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>',
                    f'<h1 class="gov-portal-main-brand" id="hero-platform-name">{ADMIN_SECTION_NAME}</h1>',
                ),
                (
                    '<span id="hero-console-chip" style="display:none;',
                    '<span id="hero-console-chip" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</span>',
                    '>Administrator Command Center</span>',
                ),
                (
                    '<div id="login-console-badge" style="display:none;',
                    '<div id="login-console-badge" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</div>',
                    '>Admin Host</div>',
                ),
                (
                    'id="login-panel-subtitle">Sign in with your Google account to access e-Panchayat Automation<',
                    f'id="login-panel-subtitle">Sign in with your Administrator Google account to open {ADMIN_SECTION_NAME}<',
                ),
                (
                    '<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">e-Panchayat Automation · Executive Report Modules</h1>',
                    f'<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">{ADMIN_SECTION_NAME}</h1>',
                ),
            ),
        )

    if is_tools_host_request(request):
        return _replace_pairs(
            html,
            (
                (
                    '<title id="doc-page-title">e-Panchayat Automation</title>',
                    f'<title id="doc-page-title">Tools Studio | {PLATFORM_NAME}</title>',
                ),
                (
                    '<h1 class="gov-portal-main-brand" id="hero-platform-name">Welcome to e-Panchayat Automation</h1>',
                    f'<h1 class="gov-portal-main-brand" id="hero-platform-name">{TOOLS_SECTION_NAME}</h1>',
                ),
                (
                    '<span id="hero-console-chip" style="display:none;',
                    '<span id="hero-console-chip" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</span>',
                    '>Tools &amp; Utilities Studio</span>',
                ),
                (
                    '<div id="login-console-badge" style="display:none;',
                    '<div id="login-console-badge" style="display:inline-flex;',
                ),
                (
                    '>e-Panchayat Automation Console</div>',
                    '>Tools Studio</div>',
                ),
                (
                    'id="login-panel-subtitle">Sign in with your Google account to access e-Panchayat Automation<',
                    f'id="login-panel-subtitle">Sign in with your Google account to access {TOOLS_SECTION_NAME}<',
                ),
                (
                    '<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">e-Panchayat Automation · Executive Report Modules</h1>',
                    f'<h1 class="hero-title" id="dash-hero-title" style="margin-bottom:6px;">{PLATFORM_NAME} · Tools &amp; Utility Studios</h1>',
                ),
            ),
        )

    return html


def apply_subpage_console_branding(html: str, request: Any = None) -> str:
    """Adapt auxiliary pages (/services, /privacy-legal) when served under reports console hosts."""
    if not html or not is_reports_console_request(request):
        return html
    return html.replace(
        '<span id="subpage-console-pill" style="display:none;',
        '<span id="subpage-console-pill" style="display:inline-flex;',
    )


def render_canonical_footer_html(extra_style: str = "") -> str:
    """Return the unified two-line footer used across both domains and every web page."""
    style_attr = f' style="{extra_style}"' if extra_style else ""
    return (
        f"<footer{style_attr}>\n"
        '    <div style="max-width:1200px; margin:0 auto; padding:6px 10px; text-align:center; line-height:1.55;">\n'
        f'      <strong style="display:block; font-size:0.95rem; font-weight:800;">{PLATFORM_NAME}</strong>\n'
        f'      <div style="font-size:0.84rem; margin-top:2px;">{TAGLINE}</div>\n'
        "    </div>\n"
        "  </footer>"
    )


def apply_openpyxl_branding(workbook: Any) -> None:
    """Attach canonical metadata and non-intrusive print footers to an openpyxl Workbook."""
    if workbook is None:
        return
    try:
        workbook.properties.creator = PLATFORM_NAME
        workbook.properties.lastModifiedBy = PLATFORM_NAME
        workbook.properties.subject = TAGLINE
    except Exception:
        pass

    for ws in getattr(workbook, "worksheets", []):
        try:
            ws.oddFooter.left.text = PLATFORM_NAME
            ws.oddFooter.left.size = 8
            ws.oddFooter.center.text = TAGLINE
            ws.oddFooter.center.size = 8
            ws.oddFooter.right.text = "Page &P of &N"
            ws.oddFooter.right.size = 8
        except Exception:
            pass

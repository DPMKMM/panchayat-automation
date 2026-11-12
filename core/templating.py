"""HTML template loading utilities for e-Panchayat Automation & Console."""

from __future__ import annotations

from pathlib import Path

from core.config import BASE_DIR

TEMPLATES_DIR = BASE_DIR / "templates"
PORTAL_SHELL_PATH = TEMPLATES_DIR / "portal_shell.html"


def load_portal_shell_html() -> str:
    """Load the shared dual-domain HTML shell from templates/portal_shell.html."""
    if PORTAL_SHELL_PATH.exists():
        return PORTAL_SHELL_PATH.read_text(encoding="utf-8")
    from dsr import html as dsr_html
    return dsr_html.NARESH_PAGE_HTML

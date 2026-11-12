"""HTML template shim loading the unified dual-domain portal shell."""

from __future__ import annotations

from pathlib import Path

_PORTAL_SHELL_PATH = Path(__file__).resolve().parent.parent / "templates" / "portal_shell.html"


def get_naresh_page_html() -> str:
    """Return the shared dual-domain HTML shell from templates/portal_shell.html."""
    if _PORTAL_SHELL_PATH.exists():
        return _PORTAL_SHELL_PATH.read_text(encoding="utf-8")
    return "<!doctype html><html lang='en'><body><h1>e-Panchayat Automation</h1></body></html>"


NARESH_PAGE_HTML: str = get_naresh_page_html()

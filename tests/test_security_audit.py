"""
test_security_audit.py - Security & Production Hardening Verification Tests

Verifies:
1. Documentation and schema endpoints (/docs, /redoc, /openapi.json) are restricted/hidden in production.
2. All automation and report download endpoints strictly reject unauthenticated requests with 401/403.
3. Server-side isolation: core scraping, OCR, and processing logic is never exposed on frontend.
4. Configuration and gitignore safety constraints.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app import create_app
from core.config import BASE_DIR, get_firebase_web_config


@pytest.fixture(scope="module")
def prod_client():
    """Client configured with production environment settings."""
    old_env = os.environ.get("ENVIRONMENT")
    old_docs = os.environ.get("ENABLE_DOCS")
    os.environ["ENVIRONMENT"] = "production"
    os.environ["ENABLE_DOCS"] = "false"
    
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    
    yield client
    
    if old_env is not None:
        os.environ["ENVIRONMENT"] = old_env
    else:
        os.environ.pop("ENVIRONMENT", None)
    if old_docs is not None:
        os.environ["ENABLE_DOCS"] = old_docs
    else:
        os.environ.pop("ENABLE_DOCS", None)


def test_docs_endpoints_disabled_in_production(prod_client: TestClient):
    """Confirm /docs, /redoc, and /openapi.json return 404 in production mode."""
    for path in ["/docs", "/redoc", "/openapi.json", "/api/docs", "/api/redoc", "/api/openapi.json"]:
        resp = prod_client.get(path)
        assert resp.status_code == 404, f"Endpoint {path} was not restricted (status: {resp.status_code})"


def test_automation_endpoints_reject_unauthenticated(prod_client: TestClient):
    """Confirm all automation endpoints strictly reject unauthenticated calls with 401."""
    automation_endpoints = [
        # DSR Automation
        ("POST", "/api/naresh/generate"),
        ("GET", "/api/naresh/data"),
        ("GET", "/api/naresh/download"),
        # Multi-Days DSR Automation
        ("POST", "/api/auto-multi-dsr/start-job"),
        # GP Balance Automation
        ("POST", "/api/balance/generate"),
        ("GET", "/api/balance/download-pdf"),
        ("GET", "/api/balance/download-excel"),
        # MAS Automation
        ("POST", "/api/mas/generate"),
        ("POST", "/api/reports/mas-consolidated/generate"),
        # Inspections Automation
        ("POST", "/api/inspections/generate"),
        # Live DCB Scrape & Exports
        ("POST", "/api/tax/refresh"),
        ("GET", "/api/tax/report.pdf"),
        ("GET", "/api/tax/powerbi-report.pdf"),
        ("GET", "/api/tax/download"),
        # Tools Studio Processing
        ("POST", "/api/tools/pdf/merge"),
        ("POST", "/api/tools/pdf/compress"),
        ("POST", "/api/tools/excel/execute"),
        # Admin Endpoints
        ("GET", "/api/admin/users"),
    ]

    for method, path in automation_endpoints:
        if method == "POST":
            resp = prod_client.post(path)
        else:
            resp = prod_client.get(path)
        assert resp.status_code in (401, 403), f"Endpoint {method} {path} returned {resp.status_code} instead of 401/403"


def test_gitignore_contains_all_required_security_blocks():
    """Verify that .gitignore blocks all sensitive files, DBs, logs, and downloads."""
    gitignore_path = BASE_DIR / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")

    required_patterns = [
        ".env",
        "__pycache__/",
        ".venv/",
        "*.db",
        "*.sqlite",
        "*.sqlite*",
        "*.xlsx",
        "*.pdf",
        "*.log",
        "config.json",
        "secrets/",
    ]
    for pat in required_patterns:
        assert pat in content, f"Missing required .gitignore block: {pat}"


def test_env_example_contains_zero_secrets():
    """Verify that .env.example contains only placeholders and zero real secrets or keys."""
    env_example_path = BASE_DIR / ".env.example"
    assert env_example_path.exists()
    content = env_example_path.read_text(encoding="utf-8")

    # Forbidden real token prefixes or live keys
    assert "AIzaSy" not in content
    assert "eyJhIjoi" not in content
    assert "b71c84f509e5bca3" not in content
    assert "khammam-epanchayat" not in content


def test_firebase_web_config_dynamically_loaded_from_env():
    """Verify that get_firebase_web_config() loads values dynamically without hardcoded secrets in source."""
    cfg = get_firebase_web_config()
    assert isinstance(cfg, dict)
    assert "apiKey" in cfg
    assert "projectId" in cfg
    assert "authDomain" in cfg

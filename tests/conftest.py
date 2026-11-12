"""Pytest session isolation configuration.

Ensures every test run uses an isolated temporary DATA_DIR and in-memory
Cloud Firestore test store instead of mutating live production files or databases.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_PYTEST_TMP_DIR: Path | None = None


def pytest_configure(config) -> None:
    global _PYTEST_TMP_DIR
    _PYTEST_TMP_DIR = Path(tempfile.mkdtemp(prefix="epanchayat_pytest_")).resolve()

    os.environ["ENVIRONMENT"] = "development"
    os.environ["USE_INMEMORY_FIRESTORE_FOR_TESTS"] = "1"
    os.environ["ALLOW_CLOUD_SYNC_FALLBACK"] = "true"
    os.environ["DATA_DIR"] = str(_PYTEST_TMP_DIR)
    os.environ["ATTENDANCE_JOBS_DB_PATH"] = str(_PYTEST_TMP_DIR / "attendance_jobs.sqlite3")
    os.environ.setdefault("ADMIN_EMAILS", "admin.epanchayat@gmail.com")


def pytest_sessionfinish(session, exitstatus) -> None:
    global _PYTEST_TMP_DIR
    if _PYTEST_TMP_DIR and _PYTEST_TMP_DIR.exists():
        shutil.rmtree(_PYTEST_TMP_DIR, ignore_errors=True)
        _PYTEST_TMP_DIR = None

"""Shared project and runtime data paths."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_configured_data_dir = os.getenv("DATA_DIR", "").strip()
if _configured_data_dir:
    DATA_DIR = Path(_configured_data_dir).expanduser()
    if not DATA_DIR.is_absolute():
        DATA_DIR = PROJECT_ROOT / DATA_DIR
else:
    DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR = DATA_DIR.resolve()

REPORTS_DIR = DATA_DIR / "reports"
DSR_DATA_DIR = DATA_DIR / "DSR"
GP_BALANCE_DATA_DIR = DATA_DIR / "GPBalance"

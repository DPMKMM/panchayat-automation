"""Canonical data structures, module catalogs, and normalization helpers for MAS."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Ordered 18 MAS indicators combining GM-R 5.24 (17 indicators) + GM-R 5.23 (Birth Details)
ALL_18_MODULES: List[Tuple[str, str]] = [
    ("Nursery", "MAS_Nursery"),
    ("Plantation", "MAS_Plantation"),
    ("Vaikunta Dhamam", "MAS_Vaikunta Dhamam"),
    ("Dump Yard", "MAS_Dump Yard"),
    ("Water Supply", "MAS_Water Supply"),
    ("GP Meetings", "MAS_GP Meeting"),
    ("Gram Sabha", "MAS_Gram Sabha"),
    ("Record Maintenance", "MAS_Record Maintenance"),
    ("Approvals and Certificates", "MAS_Approvals & Certificates"),
    ("Deaths", "MAS_Deaths"),
    ("Recipts", "MAS_Receipts"),
    ("Expenditure", "MAS_Expenditure"),
    ("Cheque Details", "MAS_Cheque Details"),
    ("Salary Details", "MAS_Salary Details"),
    ("VWSC Bank Balance", "MAS_VWSC & EGS Balance"),
    ("MGNRE Bank Balance", "MAS_MGNREGA Balance"),
    ("Payment of Electricity", "MAS_Electricity Payment"),
    ("Birth Details", "Births_Data_Entered"),
]

# Official 17 modules inside GM-R 5.24 Table Headers (columns 3..36)
MOD_NAMES_524: List[str] = [
    "Nursery",
    "Plantation",
    "Vaikunta Dhamam",
    "Dump Yard",
    "Water Supply",
    "GP Meetings",
    "Gram Sabha",
    "Record Maintenance",
    "Approvals and Certificates",
    "Deaths",
    "Recipts",
    "Expenditure",
    "Cheque Details",
    "Salary Details",
    "VWSC Bank Balance",
    "MGNRE Bank Balance",
    "Payment of Electricity",
]

# Full 18-module mapping across GM-R 5.24 label, short name, and consolidated GP record column
CANONICAL_18_MODULES: List[Tuple[str, str, str]] = [
    ("Nursery", "Nursery", "MAS_Nursery"),
    ("Plantation", "Plantation", "MAS_Plantation"),
    ("Vaikunta Dhamam", "Vaikunta Dhamam", "MAS_Vaikunta Dhamam"),
    ("Dump Yard", "Dump Yard", "MAS_Dump Yard"),
    ("Water Supply", "Water Supply", "MAS_Water Supply"),
    ("GP Meetings", "GP Meeting", "MAS_GP Meeting"),
    ("Gram Sabha", "Gram Sabha", "MAS_Gram Sabha"),
    ("Record Maintenance", "Record Maintenance", "MAS_Record Maintenance"),
    ("Approvals and Certificates", "Approvals & Certificates", "MAS_Approvals & Certificates"),
    ("Deaths", "Deaths", "MAS_Deaths"),
    ("Recipts", "Receipts", "MAS_Receipts"),
    ("Expenditure", "Expenditure", "MAS_Expenditure"),
    ("Cheque Details", "Cheque Details", "MAS_Cheque Details"),
    ("Salary Details", "Salary Details", "MAS_Salary Details"),
    ("VWSC Bank Balance", "VWSC & EGS Balance", "MAS_VWSC & EGS Balance"),
    ("MGNRE Bank Balance", "MGNREGA Balance", "MAS_MGNREGA Balance"),
    ("Payment of Electricity", "Electricity Payment", "MAS_Electricity Payment"),
    ("Birth Details", "Birth Details", "Births_Data_Entered"),
]

ALL_18_LABELS: List[str] = [label for label, _ in ALL_18_MODULES]

MODULE_ALIASES: Dict[str, str] = {
    "receipts": "Recipts",
    "recipts": "Recipts",
    "cc charges": "Payment of Electricity",
    "electricity payment": "Payment of Electricity",
    "electricity": "Payment of Electricity",
    "payment of electricity": "Payment of Electricity",
    "gp meeting": "GP Meetings",
    "gp meetings": "GP Meetings",
    "approvals & certificates": "Approvals and Certificates",
    "approvals and certificates": "Approvals and Certificates",
    "vwsc & egs balance": "VWSC Bank Balance",
    "vwsc bank balance": "VWSC Bank Balance",
    "mgnrega balance": "MGNRE Bank Balance",
    "mgnre bank balance": "MGNRE Bank Balance",
    "births": "Birth Details",
    "birth details": "Birth Details",
}

HIGHLIGHTED_EXCLUDE_CANDIDATES: Set[str] = {
    "Payment of Electricity",
    "Expenditure",
    "Cheque Details",
}

MANDALS_20: List[Dict[str, str]] = [
    {"ctl": "ctl02", "name": "Bonakal"},
    {"ctl": "ctl03", "name": "Chinthakani"},
    {"ctl": "ctl04", "name": "Enkoor"},
    {"ctl": "ctl05", "name": "Kalloor"},
    {"ctl": "ctl06", "name": "Kamepally"},
    {"ctl": "ctl07", "name": "Khammam_rural"},
    {"ctl": "ctl08", "name": "Konijerla"},
    {"ctl": "ctl09", "name": "Kusumanchi"},
    {"ctl": "ctl10", "name": "Madhira"},
    {"ctl": "ctl11", "name": "Mudigonda"},
    {"ctl": "ctl12", "name": "Nelakondapally"},
    {"ctl": "ctl13", "name": "Penuballi"},
    {"ctl": "ctl14", "name": "Raghunathapalem"},
    {"ctl": "ctl15", "name": "Sathupally"},
    {"ctl": "ctl16", "name": "Singareni"},
    {"ctl": "ctl17", "name": "Thallada"},
    {"ctl": "ctl18", "name": "Tirumalayapalem"},
    {"ctl": "ctl19", "name": "Vemsoor"},
    {"ctl": "ctl20", "name": "Wyra"},
    {"ctl": "ctl21", "name": "Yerrupalem"},
]

MONTH_NUM_MAP: Dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_SUMMARY_ROW_RE = re.compile(
    r"^(?:grand\s+|district\s+|mandal\s+|sub[\s-]*)?total$",
    re.IGNORECASE,
)


def normalize_module_name(name: str) -> str:
    """Resolve user/API alias strings into the canonical 18-module label."""
    low = (name or "").strip().lower()
    if low in MODULE_ALIASES:
        return MODULE_ALIASES[low]
    for label, _ in ALL_18_MODULES:
        if label.lower() == low:
            return label
    return name


def is_module_excluded(label: str, excluded_lower: Set[str]) -> bool:
    """Check whether a module label is covered by the exclusion set (including CC Charges/Electricity aliases)."""
    low = (label or "").strip().lower()
    if not excluded_lower:
        return False
    return (
        low in excluded_lower
        or ("electricity" in low and any("elect" in c or "cc" in c for c in excluded_lower))
        or ("cc charges" in low and any("cc" in c or "elect" in c for c in excluded_lower))
        or ("cheque" in low and any("cheque" in c for c in excluded_lower))
        or ("expenditure" in low and any("expend" in c for c in excluded_lower))
    )


def resolve_excluded_set(excluded_modules: Optional[List[str]]) -> Set[str]:
    """Normalize a list of excluded module names/aliases into canonical 18-module labels."""
    if not excluded_modules:
        return set()
    normalized_excluded: Set[str] = set()
    for ex in excluded_modules:
        target = normalize_module_name(ex).lower()
        for label, _ in ALL_18_MODULES:
            if (
                label.lower() == target
                or normalize_module_name(label).lower() == target
                or (target and target in label.lower())
                or ("electricity" in target and "electricity" in label.lower())
                or ("cc charges" in target and "electricity" in label.lower())
            ):
                normalized_excluded.add(label)
    return normalized_excluded


def clean_key(val: Any) -> str:
    """Strip non-alphanumeric chars and uppercase for resilient Mandal/GP composite keys."""
    if not val:
        return ""
    return re.sub(r"[^a-zA-Z0-9]", "", str(val)).upper()


def make_unique_key(mandal: str, gp: str) -> str:
    """Build composite unique identifier ``MANDAL_GP``."""
    return f"{clean_key(mandal)}_{clean_key(gp)}"


def is_summary_row_name(name: str) -> bool:
    """Return True for empty rows or summary/total footer rows."""
    clean = (name or "").strip()
    return (not clean) or bool(_SUMMARY_ROW_RE.match(clean))


def clean_district_name(district_name: str = "Khammam") -> str:
    """Normalize display district name without trailing 'District' suffix."""
    txt = re.sub(r"\s+", " ", (district_name or "")).strip()
    txt = re.sub(r"\s*\bdistrict\b$", "", txt, flags=re.IGNORECASE).strip()
    return txt or "Khammam"


def district_slug(district_name: str = "Khammam") -> str:
    """Return filesystem-safe district slug."""
    return re.sub(r"[^A-Za-z0-9]+", "_", clean_district_name(district_name)).strip("_") or "District"


def normalize_district_and_slug(district_name: str = "Khammam") -> Tuple[str, str]:
    """Return ``(clean_display_name, filesystem_slug)`` pair."""
    txt = clean_district_name(district_name)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_") or "District"
    return txt, slug


def get_month_number(month_name: str) -> int:
    """Convert month name or abbreviation to 1..12 (defaults to 7/July)."""
    clean = (month_name or "").strip().lower()
    if clean.isdigit():
        num = int(clean)
        if 1 <= num <= 12:
            return num
    return MONTH_NUM_MAP.get(clean, 7)


def build_module_options() -> List[Dict[str, Any]]:
    """Build UI filter chip metadata for all 18 MAS indicators."""
    return [
        {
            "id": label,
            "label": label,
            "col": col,
            "default_excluded": False,
            "is_cc_charges": label == "Payment of Electricity",
            "is_highlighted": label in HIGHLIGHTED_EXCLUDE_CANDIDATES,
        }
        for label, col in ALL_18_MODULES
    ]

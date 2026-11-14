"""
DSR State Format - Consolidation & Secretary Lookup Directory Builder
====================================================================
Merges GM-R 1.2.11 (Presentees) and GM-R 1.2.10 (Absentees) datasets using
Panchayat LGD Code as primary key. Identifies Regular vs Incharge vs Full Additional Charge.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any
import pandas as pd


def clean_lgd(value: Any) -> str:
    """Normalize Panchayat LGD Code to a clean string without trailing .0."""
    if pd.isna(value) or value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Strip .0 if parsed as float from Excel
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def clean_string(value: Any) -> str:
    """Clean arbitrary string, title-casing and stripping whitespace."""
    if pd.isna(value) or value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def clean_name(value: Any) -> str:
    """Clean and title-case secretary or panchayat names."""
    cleaned = clean_string(value)
    if not cleaned:
        return ""
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), cleaned)


def clean_mobile(value: Any) -> str:
    """Normalize 10-digit mobile number."""
    if pd.isna(value) or value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "0", "0.0", "na", "-", "."}:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    cleaned = re.sub(r"[^\d+]", "", text)
    return cleaned or text


def is_regular_ps(nature_of_posting: str) -> bool:
    """
    Returns True if nature of posting is strictly Regular (full-time working PS),
    excluding Incharge and Full Additional Charge.
    """
    cleaned = (nature_of_posting or "").strip().lower()
    if not cleaned:
        return False
    if "incharge" in cleaned or "additional" in cleaned:
        return False
    return "regular" in cleaned


def _canonicalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Map common variation of column names in Presentees/Absentees to standard schema."""
    out = df.copy()
    col_map = {}
    for col in out.columns:
        norm = re.sub(r"[^a-zA-Z0-9]", "", str(col).lower())
        if norm in ("panchayatlgdcode", "panchayatlgd", "lgdcode", "lgd"):
            col_map[col] = "Panchayat LGD Code"
        elif norm in ("panchayatsecretaryname", "psname", "secretaryname", "name"):
            col_map[col] = "Panchayat Secretary Name"
        elif norm in ("mobilenumber", "mobileno", "phone", "contact"):
            col_map[col] = "Mobile Number"
        elif norm in ("natureofposting", "postingnature", "nature"):
            col_map[col] = "Nature of Posting"
        elif norm in ("panchayatsecretaryemployeeid", "employeeid", "empid", "psid"):
            col_map[col] = "Panchayat Secretary Employee Id"
        elif norm in ("designation", "desg"):
            col_map[col] = "Designation"
        elif norm in ("mandalname", "mandal"):
            col_map[col] = "Mandal Name"
        elif norm in ("panchayatname", "gpname", "panchayat"):
            col_map[col] = "Panchayat Name"
    if col_map:
        out = out.rename(columns=col_map)
    return out


def parse_directory_bytes(raw_bytes: bytes, filename: str = "") -> list[dict[str, Any]]:
    """Parse Excel/HTML bytes from Presentees or Absentees file into records."""
    if not raw_bytes:
        return []

    prefix = raw_bytes[:8192].lstrip().lower()
    looks_html = (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or (b"<table" in prefix and (b"<tr" in prefix or b"<th" in prefix))
    )

    frames: list[pd.DataFrame] = []
    if looks_html:
        try:
            frames = pd.read_html(io.BytesIO(raw_bytes))
        except Exception:
            pass
    elif filename.lower().endswith(".csv"):
        for enc in ("utf-8-sig", "cp1252", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, keep_default_na=False)
                frames.append(df)
                break
            except Exception:
                continue
    else:  # .xls / .xlsx
        try:
            sheets = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=None)
            if isinstance(sheets, dict):
                frames.extend(sheets.values())
            elif isinstance(sheets, pd.DataFrame):
                frames.append(sheets)
        except Exception:
            try:
                frames = pd.read_html(io.BytesIO(raw_bytes))
            except Exception:
                pass

    records: list[dict[str, Any]] = []
    for candidate in frames:
        if candidate is None or candidate.empty:
            continue
        c_df = candidate.copy()
        c_df.columns = [str(col).replace("\n", " ").strip() for col in c_df.columns]
        standardized = _canonicalize_df(c_df)

        if "Panchayat LGD Code" not in standardized.columns:
            # Check if headers are inside the first few rows (ASP.NET header offset)
            for row_idx in range(min(len(c_df), 15)):
                sub = c_df.iloc[row_idx + 1:].copy()
                sub.columns = [str(val).replace("\n", " ").strip() for val in c_df.iloc[row_idx].tolist()]
                test_std = _canonicalize_df(sub)
                if "Panchayat LGD Code" in test_std.columns:
                    standardized = test_std
                    break

        if "Panchayat LGD Code" not in standardized.columns:
            continue

        for _, row in standardized.iterrows():
            lgd = clean_lgd(row.get("Panchayat LGD Code"))
            if not lgd:
                continue
            name = clean_name(row.get("Panchayat Secretary Name", ""))
            mobile = clean_mobile(row.get("Mobile Number", ""))
            posting = clean_string(row.get("Nature of Posting", ""))
            emp_id = clean_string(row.get("Panchayat Secretary Employee Id", ""))
            designation = clean_string(row.get("Designation", ""))
            mandal = clean_name(row.get("Mandal Name", ""))
            gp_name = clean_name(row.get("Panchayat Name", ""))

            records.append({
                "lgd_code": lgd,
                "ps_name": name,
                "mobile": mobile,
                "nature_of_posting": posting,
                "is_regular": is_regular_ps(posting),
                "emp_id": emp_id,
                "designation": designation,
                "mandal_name": mandal,
                "gp_name": gp_name,
            })

    return records


def build_secretary_lookup(
    presentees_bytes: bytes | None = None,
    presentees_filename: str = "",
    absentees_bytes: bytes | None = None,
    absentees_filename: str = "",
) -> dict[str, dict[str, Any]]:
    """
    Consolidates Presentees and Absentees data into a unified dictionary keyed by Panchayat LGD Code.
    Ensures zero duplicate keys and resolves any record conflicts.
    """
    lookup: dict[str, dict[str, Any]] = {}

    all_records: list[dict[str, Any]] = []
    if presentees_bytes:
        all_records.extend(parse_directory_bytes(presentees_bytes, presentees_filename))
    if absentees_bytes:
        all_records.extend(parse_directory_bytes(absentees_bytes, absentees_filename))

    for rec in all_records:
        lgd = rec["lgd_code"]
        if not lgd:
            continue
        existing = lookup.get(lgd)
        if not existing:
            lookup[lgd] = rec
        else:
            # Merge fields if missing
            for field in ("ps_name", "mobile", "nature_of_posting", "emp_id", "designation", "mandal_name", "gp_name"):
                if not existing.get(field) and rec.get(field):
                    existing[field] = rec[field]
            existing["is_regular"] = is_regular_ps(existing.get("nature_of_posting", ""))

    return lookup

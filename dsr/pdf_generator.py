"""Attendance data validation, analysis, and A4 PDF report generation.

This module is deliberately safe to import.  The command-line entry point at
the bottom is only invoked when this file is executed as a script.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REQUIRED_COLUMNS = {
    "Panchayat LGD": {
        "panchayatlgd", "panchayatlgdcode", "lgd", "lgdcode",
    },
    "Mandal Name": {"mandalname", "mandal"},
    "Panchayat Name": {
        "panchayatname", "grampanchayat", "grampanchayatname", "gramapanchayatname",
    },
    "First Attendence Status": {
        "firstattendencestatus", "firstattendancestatus", "attendencestatus",
        "attendancestatus", "attendance", "status",
    },
    "Second Attendence Status": {
        "secondattendencestatus", "secondattendancestatus", "secondattendance",
        "secondattendence", "secondstatus", "secondattendance1status",
        "2ndattendencestatus", "2ndattendancestatus", "attendance2status",
    },
    "First Attendence Datetime": {
        "firstattendencedatetime", "firstattendancedatetime", "attendencedatetime",
        "attendancedatetime", "attendancedateandtime", "attendancetime",
    },
}

OPTIONAL_COLUMN_ALIASES = {
    "District Name": {
        "districtname", "district", "district_name", "distname", "dist",
    },
    "DSR Status": {
        "dsr", "dsrstatus", "dsrsubmitted", "dsrsubmissionstatus", "dsrsubmittedstatus",
        "dsrentrystatus", "dsrreportstatus", "dsrreportentered", "dsrentered",
        "dsrentry", "dailystatusreport", "dailystatusreportstatus",
        "dailystatusreportsubmitted", "dailystatusreportentrystatus",
    },
    "DSR Datetime": {
        "dsrdate", "dsrdatetime", "dsrsubmitteddate", "dsrsubmitteddatetime",
        "dsrsubmissiondate", "dsrsubmissiondatetime", "dsrentrydate", "dsrentrydatetime",
        "dsrreportdate", "dsrreportdatetime", "dsrentereddate", "dsrentereddatetime",
        "dailystatusreportdate", "dailystatusreportdatetime",
    },
    "Panchayat Secretary Name": {
        "panchayatsecretaryname", "secretaryname", "psname", "panchayatsecretary",
        "secname", "employeename", "name", "nameofps", "nameofpanchayatsecretary",
    },
    "Mobile Number": {
        "mobilenumber", "mobile", "phonenumber", "phone", "contactnumber",
        "contactno", "cellnumber", "cell", "mobileno", "phoneno", "contact",
    },
    "Nature of Posting": {
        "natureofposting", "natureofpost", "postingnature", "natureofpostings",
        "regularorinchage", "regularorincharge", "regularincharge", "posting",
        "postnature", "nature", "typeofposting",
    },
    "Panchayat Secretary Employee Id": {
        "panchayatsecretaryemployeeid", "psemployeeid", "secretaryemployeeid",
        "employeeid", "empid", "psempid",
    },
    "Designation": {
        "designation", "designationname", "post", "role",
    },
}

PS_DIRECTORY_COLUMN_ALIASES = {
    "Panchayat LGD Code": {
        "panchayatlgdcode", "panchayatlgd", "lgdcode", "lgd", "gplgdcode", "gplgd",
        "panchayatcode", "gpcode", "panchayatlgdno",
    },
    "Panchayat Secretary Name": {
        "panchayatsecretaryname", "secretaryname", "psname", "panchayatsecretary",
        "secname", "employeename", "name", "nameofps", "nameofpanchayatsecretary",
    },
    "Mobile Number": {
        "mobilenumber", "mobile", "phonenumber", "phone", "contactnumber",
        "contactno", "cellnumber", "cell", "mobileno", "phoneno", "contact",
    },
    "Nature of Posting": {
        "natureofposting", "natureofpost", "postingnature", "natureofpostings",
        "regularorinchage", "regularorincharge", "regularincharge", "posting",
        "postnature", "nature", "typeofposting",
    },
    "Panchayat Secretary Employee Id": {
        "panchayatsecretaryemployeeid", "psemployeeid", "secretaryemployeeid",
        "employeeid", "empid", "psempid",
    },
    "Designation": {
        "designation", "designationname", "post", "role",
    },
    "Mandal Name": {
        "mandalname", "mandal",
    },
    "Panchayat Name": {
        "panchayatname", "grampanchayat", "grampanchayatname", "gpname", "panchayat",
    },
    "District Name": {
        "districtname", "district", "district_name", "distname", "dist",
    },
}


class InputValidationError(ValueError):
    """A safe, user-facing validation error for an uploaded attendance file."""


@dataclass
class ReportData:
    district_name: str
    report_date: date
    source_row_count: int
    unique_gp_count: int
    missing_lgd_rows: int
    duplicate_lgd_rows: int
    conflicts: list[dict[str, Any]]
    mandal_rows: list[dict[str, Any]]
    district_total: dict[str, Any]
    pending_rows: list[dict[str, Any]]
    leave_rows: list[dict[str, Any]]
    meeting_training_rows: list[dict[str, Any]]
    after_9_rows: list[dict[str, Any]]
    dsr_mandal_rows: list[dict[str, Any]]
    dsr_district_total: dict[str, Any]
    dsr_pending_rows: list[dict[str, Any]]
    all_gp_rows: list[dict[str, Any]] | None = None

    @property
    def totals(self) -> dict[str, Any]:
        return {
            "unique_gps": self.unique_gp_count,
            "attendance_submitted": int(self.district_total["attendance_submitted"]),
            "overall_attendance_pct": float(self.district_total["attendance_pct"]),
            "before_9": int(self.district_total["before_9"]),
            "on_leave": int(self.district_total["on_leave"]),
            "meeting_training": int(self.district_total["meeting_training"]),
            "pending": int(self.district_total["pending"]),
            "after_9": len(self.after_9_rows),
            "dsr_eligible": int(self.dsr_district_total["present_ps"]),
            "dsr_entered": int(self.dsr_district_total["dsr_entered"]),
            "dsr_pending": int(self.dsr_district_total["dsr_pending"]),
        }


def normalize_column_name(value: Any) -> str:
    """Normalize punctuation, case, and whitespace for tolerant header matching."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _canonicalize_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    aliases = {
        alias: canonical
        for canonical, names in {**REQUIRED_COLUMNS, **OPTIONAL_COLUMN_ALIASES}.items()
        for alias in names
    }
    rename: dict[Any, str] = {}
    found: set[str] = set()
    for column in frame.columns:
        canonical = aliases.get(normalize_column_name(column))
        if canonical and canonical not in found:
            rename[column] = canonical
            found.add(canonical)
    return frame.rename(columns=rename), [name for name in REQUIRED_COLUMNS if name not in found]


def _canonicalize_ps_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    aliases = {
        alias: canonical
        for canonical, names in PS_DIRECTORY_COLUMN_ALIASES.items()
        for alias in names
    }
    rename: dict[Any, str] = {}
    found: set[str] = set()
    for column in frame.columns:
        canonical = aliases.get(normalize_column_name(column))
        if canonical and canonical not in found:
            rename[column] = canonical
            found.add(canonical)
    return frame.rename(columns=rename)


def _clean_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _clean_name(value: Any) -> str:
    """Format names in proper Title Case while respecting initials, abbreviations, and punctuation."""
    cleaned = _clean_string(value)
    if not cleaned or cleaned.lower() in {"nan", "none", "null", "na", "-", "."}:
        return ""
    # Capitalize every contiguous sequence of letters (e.g. MALLARAPU -> Mallarapu, (INCHARGE) -> (Incharge))
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), cleaned)


def _clean_lgd(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Excel numeric cells are often represented as e.g. "12345.0".
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _clean_mobile(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "0", "0.0", "na", "-", "."}:
        return ""
    # Strip trailing decimal from Excel float representation e.g. "9876543210.0"
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    cleaned = re.sub(r"[^\d+]", "", text)
    return cleaned or text


def parse_ps_directory_file(filename: str, raw_bytes: bytes) -> dict[str, dict[str, str]]:
    """Parse an Excel, CSV, or HTML table containing PS details (Presentees / Absentees).
    
    Extracts mapping of Panchayat LGD -> {ps_name, mobile, nature_of_posting, emp_id, designation}.
    """
    if not raw_bytes:
        return {}
    extension = Path(filename).suffix.lower()
    prefix = raw_bytes[:8192].lstrip().lower()
    looks_html = (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or (b"<table" in prefix and (b"<tr" in prefix or b"<th" in prefix))
    )

    frames: list[pd.DataFrame] = []
    if looks_html:
        try:
            tables = pd.read_html(io.BytesIO(raw_bytes))
            frames.extend(tables)
        except Exception:
            pass
    elif extension == ".csv":
        for enc in ("utf-8-sig", "cp1252", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(raw_bytes), sep=None, engine="python", encoding=enc, keep_default_na=False)
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
                tables = pd.read_html(io.BytesIO(raw_bytes))
                frames.extend(tables)
            except Exception:
                pass

    directory: dict[str, dict[str, str]] = {}
    for candidate in frames:
        if candidate is None or candidate.empty:
            continue
        frame = candidate.copy()
        frame.columns = [str(col).replace("\n", " ").strip() for col in frame.columns]
        standardized = _canonicalize_ps_columns(frame)
        if "Panchayat LGD Code" not in standardized.columns:
            for row_idx in range(min(len(frame), 15)):
                candidate_sub = frame.iloc[row_idx + 1:].copy()
                candidate_sub.columns = [str(val).replace("\n", " ").strip() for val in frame.iloc[row_idx].tolist()]
                test_std = _canonicalize_ps_columns(candidate_sub)
                if "Panchayat LGD Code" in test_std.columns:
                    standardized = test_std
                    break

        if "Panchayat LGD Code" not in standardized.columns:
            continue

        for _, row in standardized.iterrows():
            lgd = _clean_lgd(row.get("Panchayat LGD Code"))
            if not lgd:
                continue
            name = _clean_name(row.get("Panchayat Secretary Name", ""))
            mobile = _clean_mobile(row.get("Mobile Number", ""))
            posting = _clean_name(row.get("Nature of Posting", ""))
            emp_id = _clean_string(row.get("Panchayat Secretary Employee Id", ""))
            designation = _clean_name(row.get("Designation", ""))

            existing = directory.get(lgd, {})
            directory[lgd] = {
                "ps_name": name or existing.get("ps_name", ""),
                "mobile": mobile or existing.get("mobile", ""),
                "nature_of_posting": posting or existing.get("nature_of_posting", ""),
                "emp_id": emp_id or existing.get("emp_id", ""),
                "designation": designation or existing.get("designation", ""),
            }

    return directory


def merge_ps_directories(*directories: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Merge multiple PS directories (e.g. Presentees and Absentees), prioritizing non-empty values."""
    merged: dict[str, dict[str, str]] = {}
    for d in directories:
        if not d:
            continue
        for lgd, info in d.items():
            if lgd not in merged:
                merged[lgd] = dict(info)
            else:
                existing = merged[lgd]
                merged[lgd] = {
                    "ps_name": info.get("ps_name") or existing.get("ps_name", ""),
                    "mobile": info.get("mobile") or existing.get("mobile", ""),
                    "nature_of_posting": info.get("nature_of_posting") or existing.get("nature_of_posting", ""),
                    "emp_id": info.get("emp_id") or existing.get("emp_id", ""),
                    "designation": info.get("designation") or existing.get("designation", ""),
                }
    return merged


def save_ps_directory_cache(directory: dict[str, dict[str, str]], cache_path: str | Path) -> None:
    """Save the merged PS directory (Presentees/Absentees) to disk as JSON."""
    if not directory:
        return
    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(directory, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to save PS directory cache to %s: %s", p, exc)


def load_ps_directory_cache(cache_path: str | Path) -> dict[str, dict[str, str]]:
    """Load the cached PS directory (Presentees/Absentees) from disk as JSON."""
    p = Path(cache_path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to load PS directory cache from %s: %s", p, exc)
    return {}


def _read_html_table(raw: bytes) -> pd.DataFrame:
    try:
        tables = pd.read_html(io.BytesIO(raw))
    except Exception as exc:
        raise InputValidationError("The uploaded HTML file does not contain a readable table.") from exc
    if not tables:
        raise InputValidationError("No tables were found in the uploaded HTML file.")
    for candidate in tables:
        standardized, missing = _canonicalize_columns(candidate.copy())
        if not missing:
            return standardized

    # Some portal exports put a title row above the actual column headings.
    for candidate in tables:
        frame = candidate.copy()
        for row_index in range(min(len(frame), 20)):
            values = frame.iloc[row_index].tolist()
            tentative = frame.iloc[row_index + 1 :].copy()
            tentative.columns = values
            standardized, missing = _canonicalize_columns(tentative)
            if not missing:
                return standardized
    largest = max(tables, key=lambda table: table.shape[1])
    return largest.copy()


def read_source_file(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    """Read CSV, XLS/XLSX, or an HTML table (even when saved with .xls, .html, .htm, .txt, or web extension)."""
    if not raw_bytes:
        raise InputValidationError("The uploaded file is empty.")

    prefix = raw_bytes[:8192].lstrip().lower()
    looks_html = (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or (b"<table" in prefix and (b"<tr" in prefix or b"<th" in prefix))
        or b"xmlns:x=\"urn:schemas-microsoft-com:office:excel\"" in prefix
        or b"xmlns:o=\"urn:schemas-microsoft-com:office:office\"" in prefix
        or b"<body" in prefix
    )
    if looks_html:
        frame = _read_html_table(raw_bytes)
    else:
        # Check for Excel signatures or try Excel
        is_xlsx_zip = raw_bytes.startswith(b"PK\x03\x04")
        is_ole_xls = raw_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        extension = Path(filename).suffix.lower()

        frame = None
        if is_xlsx_zip or is_ole_xls or extension in {".xls", ".xlsx"}:
            try:
                frame = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=0)
            except Exception:
                try:
                    frame = _read_html_table(raw_bytes)
                except Exception:
                    frame = None

        if frame is None:
            # Try CSV / delimiter
            for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
                try:
                    frame = pd.read_csv(
                        io.BytesIO(raw_bytes), sep=None, engine="python", encoding=enc, keep_default_na=False,
                    )
                    break
                except Exception:
                    continue

        if frame is None:
            # Fallback to Excel then HTML
            try:
                frame = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=0)
            except Exception:
                try:
                    frame = _read_html_table(raw_bytes)
                except Exception as exc:
                    raise InputValidationError(
                        "Could not parse the uploaded file. Please ensure it is a valid attendance file (Excel, CSV, or portal web export table)."
                    ) from exc

    frame.columns = [str(column).replace("\n", " ").strip() for column in frame.columns]
    frame, missing = _canonicalize_columns(frame)
    if missing:
        detected = ", ".join(str(column) for column in frame.columns[:40]) or "(none)"
        raise InputValidationError(
            "Required column(s) not found: " + ", ".join(missing) + ". Detected columns: " + detected
        )
    return frame


def _is_present_status(value: Any) -> bool:
    normalized = normalize_column_name(_clean_string(value))
    return bool(normalized) and normalized.startswith("present") and "notpresent" not in normalized


def _is_dsr_entered(value: Any, is_datetime: bool = False) -> bool:
    text = _clean_string(value)
    normalized = normalize_column_name(text)
    if not normalized or normalized in {"na", "nan", "none", "null", "no", "n", "false", "0", "nodsr"}:
        return False
    if any(token in normalized for token in (
        "pending", "notentered", "notentry", "noentry", "notsubmitted", "notreported", "notdone", "skipped",
        "notavailable", "notapplicable", "notrequired", "noteligible", "missing",
    )):
        return False
    if is_datetime:
        return not pd.isna(_parse_timestamp(value)) or bool(text)
    return True


def _parse_timestamp(value: Any) -> Any:
    if pd.isna(value) or value == "":
        return pd.NaT
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    if isinstance(value, time):
        return pd.Timestamp(datetime.combine(date.today(), value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Excel stores a time-only cell as a fraction of a day.
        if 0 <= float(value) < 1:
            seconds = round(float(value) * 24 * 60 * 60)
            return pd.Timestamp(datetime.combine(date.today(), time.min)) + pd.Timedelta(seconds=seconds)
        # Also accept Excel serial dates found in CSV exports.
        if 10000 <= float(value) <= 100000:
            return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(value, errors="coerce", dayfirst=True)


def _format_timestamp(value: Any) -> str:
    if pd.isna(value) or value == "":
        return ""
    try:
        stamp = pd.Timestamp(value)
        return stamp.strftime("%d-%m-%Y %I:%M %p")
    except (TypeError, ValueError, OverflowError):
        return _clean_string(value)


def _format_time_only(value: Any) -> str:
    """Format timestamp extracting strictly only the time e.g. '09:15 AM'."""
    if pd.isna(value) or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%I:%M %p")
    if isinstance(value, time):
        return value.strftime("%I:%M %p")
    text = str(value).strip()
    if not text:
        return ""
    try:
        stamp = pd.Timestamp(value)
        return stamp.strftime("%I:%M %p")
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)", text)
    if match:
        raw_time = match.group(1).strip()
        try:
            parsed_time = pd.to_datetime(raw_time, errors="coerce")
            if not pd.isna(parsed_time):
                return parsed_time.strftime("%I:%M %p")
        except Exception:
            pass
        return raw_time
    return text


def _report_date(filename: str, timestamps: pd.Series) -> date:
    valid = timestamps.dropna()
    if not valid.empty:
        try:
            return valid.dt.date.mode().iloc[0]
        except (AttributeError, TypeError):
            pass
    match = re.search(r"(\d{1,2})[-_ ]([A-Za-z]{3})[-_ ](\d{4})", filename)
    if match:
        try:
            return datetime.strptime(match.group(0).replace("_", "-"), "%d-%b-%Y").date()
        except ValueError:
            pass
    return date.today()


def analyze_attendance(
    frame: pd.DataFrame,
    filename: str = "attendance.xlsx",
    ps_directory: dict[str, dict[str, str]] | None = None,
) -> ReportData:
    """Validate and aggregate one unique record per nonblank Panchayat LGD."""
    frame, missing = _canonicalize_columns(frame.copy())
    if missing:
        raise InputValidationError("Required column(s) not found: " + ", ".join(missing))
    dsr_columns = [column for column in ("DSR Status", "DSR Datetime") if column in frame.columns]
    if not dsr_columns:
        raise InputValidationError(
            "A DSR submission column was not found. Include a DSR status or submission date/time "
            "column (for example, DSR Entry Status or DSR Date)."
        )

    # Detect district name dynamically from the uploaded data
    district_name = "Khammam"
    if "District Name" in frame.columns:
        dist_series = frame["District Name"].dropna().map(_clean_string)
        dist_series = dist_series[dist_series != ""]
        if not dist_series.empty:
            detected_dist = dist_series.mode().iloc[0]
            if detected_dist:
                district_name = _clean_name(detected_dist)

    frame["Panchayat LGD"] = frame["Panchayat LGD"].map(_clean_lgd)
    frame["Mandal Name"] = frame["Mandal Name"].map(_clean_string)
    frame["Panchayat Name"] = frame["Panchayat Name"].map(_clean_string)
    frame["First Attendence Status"] = frame["First Attendence Status"].map(_clean_string)
    frame["Second Attendence Status"] = frame["Second Attendence Status"].map(_clean_string)
    for column in dsr_columns:
        frame[column] = frame[column].map(_clean_string)
    frame["_timestamp"] = frame["First Attendence Datetime"].map(_parse_timestamp)

    valid = frame.loc[frame["Panchayat LGD"].ne("")].copy()
    if valid.empty:
        raise InputValidationError("No nonblank Panchayat LGD codes were found; no GP records can be reported.")

    unique_rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    duplicate_count = 0
    directory = ps_directory or {}

    for lgd, group in valid.groupby("Panchayat LGD", sort=False, dropna=False):
        duplicate_count += max(0, len(group) - 1)
        def distinct_names(column: str) -> list[str]:
            found: dict[str, str] = {}
            for value in group[column]:
                if value and value.casefold() not in found:
                    found[value.casefold()] = value
            return list(found.values())

        mandals = distinct_names("Mandal Name")
        panchayats = distinct_names("Panchayat Name")
        if len(mandals) > 1 or len(panchayats) > 1:
            conflicts.append({"lgd": str(lgd), "mandals": mandals, "panchayats": panchayats})

        submitted = group.loc[group["First Attendence Status"].ne("")]
        chosen = submitted.iloc[0] if not submitted.empty else group.iloc[0]
        first_attendance = next(
            (value for value in group["First Attendence Status"] if value), ""
        )
        second_attendance = next(
            (value for value in group["Second Attendence Status"] if value), ""
        )
        present = any(
            _is_present_status(first) or _is_present_status(second)
            for first, second in zip(group["First Attendence Status"], group["Second Attendence Status"])
        )
        dsr_entered = any(
            _is_dsr_entered(row[column], is_datetime=(column == "DSR Datetime"))
            for _, row in group.iterrows()
            for column in dsr_columns
        )
        attendance_status = "; ".join(
            f"{label}: {value}" for label, value in (
                ("First", first_attendance), ("Second", second_attendance),
            ) if value
        ) or "No attendance status"

        ps_info = directory.get(str(lgd), {})
        ps_name = _clean_name(ps_info.get("ps_name", "")) or _clean_name(chosen.get("Panchayat Secretary Name", ""))
        mobile = ps_info.get("mobile", "") or _clean_mobile(chosen.get("Mobile Number", ""))
        nature_of_posting = _clean_name(ps_info.get("nature_of_posting", "")) or _clean_name(chosen.get("Nature of Posting", ""))
        emp_id = _clean_string(ps_info.get("emp_id", "")) or _clean_string(chosen.get("Panchayat Secretary Employee Id", ""))
        designation = _clean_name(ps_info.get("designation", "")) or _clean_name(chosen.get("Designation", ""))

        unique_rows.append({
            "lgd": str(lgd),
            "mandal": mandals[0] if mandals else "(Unspecified)",
            "gp": panchayats[0] if panchayats else "(Unnamed GP)",
            "status": chosen["First Attendence Status"],
            "timestamp": chosen["First Attendence Datetime"],
            "parsed_timestamp": chosen["_timestamp"],
            "first_attendance": first_attendance,
            "second_attendance": second_attendance,
            "dsr_eligible": present,
            "dsr_entered": present and dsr_entered,
            "dsr_attendance_status": attendance_status,
            "ps_name": ps_name,
            "mobile": mobile,
            "nature_of_posting": nature_of_posting,
            "emp_id": emp_id,
            "designation": designation,
        })

    records = pd.DataFrame(unique_rows)
    records["submitted"] = records["status"].ne("")
    cutoff = time(9, 0)

    def is_before_9(stamp: Any) -> bool:
        if pd.isna(stamp):
            return False
        return stamp.time() <= cutoff

    records["before_9"] = records["submitted"] & records["parsed_timestamp"].map(is_before_9)
    records["after_9"] = records["submitted"] & records["parsed_timestamp"].map(
        lambda value: (not pd.isna(value)) and value.time() > cutoff
    )
    records["pending"] = ~records["submitted"]
    status_lower = records["status"].str.casefold()
    records["on_leave"] = status_lower.str.contains("leave", regex=False)
    records["meeting_training"] = (
        status_lower.str.contains("meeting", regex=False)
        | status_lower.str.contains("training", regex=False)
    )
    records["timestamp_text"] = records["timestamp"].map(_format_timestamp)

    mandal_rows: list[dict[str, Any]] = []
    for mandal, group in records.groupby("mandal", sort=False):
        total = len(group)
        before = int(group["before_9"].sum())
        mandal_rows.append({
            "mandal": mandal,
            "total_gps": total,
            "attendance_submitted": int(group["submitted"].sum()),
            "attendance_pct": (int(group["submitted"].sum()) / total * 100) if total else 0.0,
            "before_9": before,
            "before_9_pct": (before / total * 100) if total else 0.0,
            "on_leave": int(group["on_leave"].sum()),
            "meeting_training": int(group["meeting_training"].sum()),
            "pending": int(group["pending"].sum()),
        })
    mandal_rows.sort(key=lambda item: (item["before_9_pct"], item["mandal"].casefold()))
    for index, item in enumerate(mandal_rows, start=1):
        item["serial"] = index

    district_gps = len(records)
    district_before = int(records["before_9"].sum())
    district_total = {
        "total_gps": district_gps,
        "attendance_submitted": int(records["submitted"].sum()),
        "attendance_pct": int(records["submitted"].sum()) / district_gps * 100 if district_gps else 0.0,
        "before_9": district_before,
        "before_9_pct": district_before / district_gps * 100 if district_gps else 0.0,
        "on_leave": int(records["on_leave"].sum()),
        "meeting_training": int(records["meeting_training"].sum()),
        "pending": int(records["pending"].sum()),
    }

    dsr_mandal_rows: list[dict[str, Any]] = []
    for mandal, group in records.groupby("mandal", sort=False):
        present_ps = int(group["dsr_eligible"].sum())
        dsr_entered = int(group["dsr_entered"].sum())
        dsr_mandal_rows.append({
            "mandal": mandal,
            "total_gps": len(group),
            "present_ps": present_ps,
            "dsr_entered": dsr_entered,
            "dsr_pct": dsr_entered / present_ps * 100 if present_ps else 0.0,
            "dsr_pending": int((group["dsr_eligible"] & ~group["dsr_entered"]).sum()),
        })
    dsr_mandal_rows.sort(
        key=lambda item: (item["dsr_pct"], -item["dsr_pending"], item["mandal"].casefold())
    )
    for index, item in enumerate(dsr_mandal_rows, start=1):
        item["serial"] = index

    dsr_present_ps = int(records["dsr_eligible"].sum())
    dsr_entered_total = int(records["dsr_entered"].sum())
    dsr_district_total = {
        "total_gps": district_gps,
        "present_ps": dsr_present_ps,
        "dsr_entered": dsr_entered_total,
        "dsr_pct": dsr_entered_total / dsr_present_ps * 100 if dsr_present_ps else 0.0,
        "dsr_pending": int((records["dsr_eligible"] & ~records["dsr_entered"]).sum()),
    }

    def make_rows(mask: pd.Series) -> list[dict[str, Any]]:
        selected = records.loc[mask].sort_values(["mandal", "gp"], key=lambda column: column.str.casefold(), kind="stable")
        return [
            {
                "serial": index,
                "lgd": row.lgd,
                "mandal": row.mandal,
                "gp": row.gp,
                "status": row.status,
                "timestamp": row.timestamp_text,
                "time_only": _format_time_only(row.timestamp),
                "ps_name": _clean_name(row.ps_name),
                "mobile": row.mobile,
                "nature_of_posting": row.nature_of_posting,
                "emp_id": row.emp_id,
                "designation": row.designation,
            }
            for index, row in enumerate(selected.itertuples(index=False), start=1)
        ]

    pending_rows = make_rows(records["pending"])
    leave_rows = make_rows(records["on_leave"])
    meeting_training_rows = make_rows(records["meeting_training"])
    after_9_rows = make_rows(records["after_9"])
    dsr_pending_records = records.loc[records["dsr_eligible"] & ~records["dsr_entered"]]
    dsr_pending_records = dsr_pending_records.sort_values(
        ["mandal", "gp"], key=lambda column: column.str.casefold(), kind="stable"
    )
    dsr_pending_rows = [
        {
            "serial": index,
            "lgd": row.lgd,
            "mandal": row.mandal,
            "gp": row.gp,
            "attendance_status": row.dsr_attendance_status,
            "dsr_status": "DSR not entered",
            "timestamp": row.timestamp_text,
            "time_only": _format_time_only(row.timestamp),
            "ps_name": _clean_name(row.ps_name),
            "mobile": row.mobile,
            "nature_of_posting": row.nature_of_posting,
            "emp_id": row.emp_id,
            "designation": row.designation,
        }
        for index, row in enumerate(dsr_pending_records.itertuples(index=False), start=1)
    ]
    # Full list of all Gram Panchayats with normalized attendance & DSR indicators
    all_sorted = records.sort_values(
        ["mandal", "gp"], key=lambda col: col.str.casefold(), kind="stable"
    )
    all_gp_rows = [
        {
            "serial": index,
            "lgd": row.lgd,
            "mandal": row.mandal,
            "gp": row.gp,
            "status": row.status if row.submitted else "Attendance Pending",
            "is_pending": bool(row.pending),
            "submitted": bool(row.submitted),
            "before_9": bool(row.before_9),
            "after_9": bool(row.after_9),
            "on_leave": bool(row.on_leave),
            "meeting_training": bool(row.meeting_training),
            "timestamp": row.timestamp_text,
            "time_only": _format_time_only(row.timestamp),
            "dsr_eligible": bool(row.dsr_eligible),
            "dsr_entered": bool(row.dsr_entered),
            "dsr_status": "Entered" if row.dsr_entered else ("DSR not entered" if row.dsr_eligible else "-"),
            "ps_name": _clean_name(row.ps_name),
            "mobile": row.mobile,
            "nature_of_posting": row.nature_of_posting,
            "emp_id": row.emp_id,
            "designation": row.designation,
        }
        for index, row in enumerate(all_sorted.itertuples(index=False), start=1)
    ]

    # Use all available recorded dates to infer the report date.
    report_date = _report_date(filename, valid["_timestamp"])
    return ReportData(
        district_name=district_name,
        report_date=report_date,
        source_row_count=len(frame),
        unique_gp_count=district_gps,
        missing_lgd_rows=len(frame) - len(valid),
        duplicate_lgd_rows=duplicate_count,
        conflicts=conflicts,
        mandal_rows=mandal_rows,
        district_total=district_total,
        pending_rows=pending_rows,
        leave_rows=leave_rows,
        meeting_training_rows=meeting_training_rows,
        after_9_rows=after_9_rows,
        dsr_mandal_rows=dsr_mandal_rows,
        dsr_district_total=dsr_district_total,
        dsr_pending_rows=dsr_pending_rows,
        all_gp_rows=all_gp_rows,
    )


def process_attendance_file(
    filename: str,
    raw_bytes: bytes,
    presentees_source: tuple[str, bytes] | None = None,
    absentees_source: tuple[str, bytes] | None = None,
    ps_directory: dict[str, dict[str, str]] | None = None,
) -> ReportData:
    """Read and analyze an uploaded file, merging optional Presentees/Absentees PS details."""
    sources: list[tuple[str, bytes]] = []
    if presentees_source and presentees_source[1]:
        sources.append(presentees_source)
    if absentees_source and absentees_source[1]:
        sources.append(absentees_source)

    parsed_dir: dict[str, dict[str, str]] = {}
    for src_name, src_bytes in sources:
        parsed_dir = merge_ps_directories(parsed_dir, parse_ps_directory_file(src_name, src_bytes))

    combined_dir = merge_ps_directories(parsed_dir, ps_directory or {})
    return analyze_attendance(
        read_source_file(filename, raw_bytes),
        filename,
        ps_directory=combined_dir,
    )


class PercentBar(Flowable):
    """A small data bar and label that are clipped to their table cell width."""

    def __init__(self, percent: float, width: float, height: float = 22):
        super().__init__()
        self.percent = max(0.0, min(100.0, float(percent)))
        self.width = width
        self.height = height

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = min(self.width, max(1, avail_width))
        return self.width, self.height

    def draw(self) -> None:
        self.canv.saveState()
        self.canv.setFont("Helvetica-Bold", 6.5)
        self.canv.setFillColor(HexColor("#1F2937"))
        self.canv.drawCentredString(self.width / 2, self.height - 8, f"{self.percent:.2f}%")
        y, height = 3, 4
        self.canv.setFillColor(HexColor("#E8EDF3"))
        self.canv.roundRect(0, y, self.width, height, 2, fill=1, stroke=0)
        fill_width = min(self.width, self.width * self.percent / 100)
        if fill_width > 0:
            # Green ONLY if attendance is 100.0%; distinct amber/orange/red for < 100%
            if round(self.percent, 2) >= 100.0:
                color = "#28A745"  # Green ONLY for 100%
            elif self.percent >= 75.0:
                color = "#E69500"  # Rich Amber for 75% - 99.99% (unmistakably not green)
            elif self.percent >= 50.0:
                color = "#E65100"  # Orange for 50% - 74.99%
            else:
                color = "#D9534F"  # Red for < 50%
            self.canv.setFillColor(HexColor(color))
            self.canv.roundRect(0, y, fill_width, height, 2, fill=1, stroke=0)
        self.canv.restoreState()


def generate_pdf(report: ReportData, output_path: str | Path) -> Path:
    """Create a professional, printable A4 portrait report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    page_width, _ = A4
    margin = 12 * mm
    available_width = page_width - 2 * margin
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=15, leading=18, alignment=TA_CENTER, textColor=HexColor("#17365D"), spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=HexColor("#444444"), spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=HexColor("#17365D"), spaceBefore=2, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="CellLeft", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=8.4,
        alignment=TA_LEFT, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="CellCenter", parent=styles["CellLeft"], alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5,
        leading=7.5, alignment=TA_CENTER, textColor=colors.white, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="TableHeaderLeft", parent=styles["TableHeader"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="Note", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=9,
        textColor=HexColor("#444444"),
    ))

    def safe(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def make_table(
        headers: list[str], rows: list[list[Any]], widths: list[float], left_columns: tuple[int, ...] = (),
        total_row: bool = False,
    ) -> Table:
        data: list[list[Any]] = [[
            Paragraph(
                safe(value).replace("\n", "<br/>"),
                styles["TableHeaderLeft"] if column_index in left_columns else styles["TableHeader"],
            )
            for column_index, value in enumerate(headers)
        ]]
        for row in rows:
            formatted = []
            for column_index, value in enumerate(row):
                if isinstance(value, Flowable):
                    formatted.append(value)
                else:
                    cell_style = styles["CellLeft"] if column_index in left_columns else styles["CellCenter"]
                    text_val = "" if value is None else str(value)
                    if "<font" in text_val or "<b>" in text_val or "<br/>" in text_val:
                        formatted.append(Paragraph(text_val, cell_style))
                    else:
                        formatted.append(Paragraph(safe(text_val), cell_style))
            data.append(formatted)
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
        commands: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F4E78")),
            ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#A6A6A6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#EAF2F8")]),
        ]
        for column_index in left_columns:
            commands.append(("ALIGN", (column_index, 1), (column_index, -1), "LEFT"))
        if total_row:
            commands.extend([
                ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D9EAF7")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, HexColor("#1F4E78")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ])
        table.setStyle(TableStyle(commands))
        return table

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(HexColor("#B7C9D6"))
        canvas.line(margin, 10 * mm, width - margin, 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawString(margin, 6 * mm, f"{report.district_name.title()} District | PS Attendance Report | {report.report_date:%d-%m-%Y}")
        canvas.drawRightString(width - margin, 6 * mm, f"Page {document.page}")
        canvas.restoreState()

    story: list[Any] = []
    story.extend([
        Paragraph(f"{report.district_name.upper()} DISTRICT", styles["ReportTitle"]),
        Paragraph("PANCHAYAT SECRETARY ATTENDANCE REPORT", styles["ReportTitle"]),
        Paragraph(f"Report Date: {report.report_date:%d-%m-%Y} | Unique GPs: {report.unique_gp_count:,}", styles["ReportSubtitle"]),
        Paragraph("1. Mandal-wise Attendance Abstract", styles["SectionTitle"]),
    ])

    abstract_headers = [
        "Sl. No.", "Mandal", "No. of GPs",
        "No. of GPs submitted\nattendance before 9 AM",
        "Attendance %\nbefore 9 AM", "Overall\nAttendance %", "No. of PS\non leave",
        "No. of PS in\ntraining/meeting", "No. of GPs with\nattendance pending",
    ]
    widths = [11 * mm, 24 * mm, 12 * mm, 28 * mm, 22 * mm, 22 * mm, 14 * mm, 27 * mm, 26 * mm]
    # Keep all eight columns inside the printable A4 width even if margins change.
    scale = min(1.0, available_width / sum(widths))
    widths = [width * scale for width in widths]
    abstract_rows: list[list[Any]] = []
    for item in report.mandal_rows:
        pending_val = item["pending"]
        pending_display = f'<font color="#C00000"><b>{pending_val}</b></font>' if pending_val > 0 else str(pending_val)
        abstract_rows.append([
            item["serial"], item["mandal"], item["total_gps"], item["before_9"],
            PercentBar(item["before_9_pct"], widths[4] - 5),
            PercentBar(item["attendance_pct"], widths[5] - 5), item["on_leave"],
            item["meeting_training"], pending_display,
        ])
    total = report.district_total
    total_pending = total["pending"]
    total_pending_display = f'<font color="#C00000"><b>{total_pending}</b></font>' if total_pending > 0 else str(total_pending)
    abstract_rows.append([
        "", "DISTRICT TOTAL", total["total_gps"], total["before_9"],
        PercentBar(total["before_9_pct"], widths[4] - 5),
        PercentBar(total["attendance_pct"], widths[5] - 5), total["on_leave"],
        total["meeting_training"], total_pending_display,
    ])
    story.append(make_table(abstract_headers, abstract_rows, widths, left_columns=(1,), total_row=True))
    story.append(Spacer(1, 6))
    if report.duplicate_lgd_rows:
        story.append(Paragraph(
            f"Validation: Excluded {report.duplicate_lgd_rows} duplicate LGD row(s).", styles["Note"],
        ))
    if report.missing_lgd_rows:
        story.append(Paragraph(
            f"Validation: Excluded {report.missing_lgd_rows} source row(s) without a Panchayat LGD code.",
            styles["Note"],
        ))
    if report.conflicts:
        details = "; ".join(
            f"{item['lgd']} (Mandal: {', '.join(item['mandals']) or '-'}; GP: {', '.join(item['panchayats']) or '-'})"
            for item in report.conflicts[:8]
        )
        suffix = f"; and {len(report.conflicts) - 8} more" if len(report.conflicts) > 8 else ""
        story.append(Paragraph(
            f"Validation warning: {len(report.conflicts)} LGD code(s) have conflicting names: {safe(details + suffix)}.",
            styles["Note"],
        ))

    story.append(PageBreak())
    story.append(Paragraph("2. Mandal-wise DSR Abstract Report", styles["SectionTitle"]))
    dsr_headers = [
        "Sl. No.", "Mandal", "Total No. of GPs", "No. of PS present",
        "No. of GPs DSR entered", "No. of GPs DSR pending", "% GPs DSR submitted",
    ]
    dsr_widths = [10 * mm, 38 * mm, 27 * mm, 27 * mm, 29 * mm, 27 * mm, available_width - 158 * mm]
    dsr_rows: list[list[Any]] = []
    for item in report.dsr_mandal_rows:
        dsr_pending_display = f'<font color="#C00000"><b>{item["dsr_pending"]}</b></font>' if item["dsr_pending"] > 0 else str(item["dsr_pending"])
        dsr_rows.append([
            item["serial"], item["mandal"], item["total_gps"], item["present_ps"],
            item["dsr_entered"], dsr_pending_display,
            PercentBar(item["dsr_pct"], dsr_widths[6] - 5),
        ])
    dsr_total = report.dsr_district_total
    total_dsr_pending_display = f'<font color="#C00000"><b>{dsr_total["dsr_pending"]}</b></font>' if dsr_total["dsr_pending"] > 0 else str(dsr_total["dsr_pending"])
    dsr_rows.append([
        "", "DISTRICT TOTAL", dsr_total["total_gps"], dsr_total["present_ps"],
        dsr_total["dsr_entered"], total_dsr_pending_display,
        PercentBar(dsr_total["dsr_pct"], dsr_widths[6] - 5),
    ])
    story.append(make_table(dsr_headers, dsr_rows, dsr_widths, left_columns=(1,), total_row=True))

    # 3. Attendance Pending GPs (with PS Name, Nature of Posting, Mobile Number)
    story.append(PageBreak())
    story.append(Paragraph("3. Attendance Pending GPs", styles["SectionTitle"]))
    story.append(Paragraph(f"Total pending GPs: {len(report.pending_rows):,}", styles["ReportSubtitle"]))
    pending_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat",
        "Panchayat Secretary Name", "Nature of\nPosting", "Mobile Number",
    ]
    pending_widths = [10 * mm, 28 * mm, 36 * mm, 44 * mm, 34 * mm, available_width - 152 * mm]
    pending_table_rows: list[list[Any]] = [
        [
            item["serial"],
            item["mandal"],
            item["gp"],
            _clean_name(item.get("ps_name")) or "-",
            item.get("nature_of_posting") or "-",
            item.get("mobile") or "-",
        ]
        for item in report.pending_rows
    ]
    if not pending_table_rows:
        pending_table_rows = [["-", "-", "No pending GPs found.", "-", "-", "-"]]
    pending_table = make_table(
        pending_headers, pending_table_rows, pending_widths, left_columns=(1, 2, 3, 4),
    )
    if not report.pending_rows:
        pending_table.setStyle(TableStyle([
            ("SPAN", (2, 1), (-1, 1)), ("ALIGN", (2, 1), (-1, 1), "LEFT"),
        ]))
    story.append(pending_table)

    # 4. DSR PENDING GPs (with Attendance Time and 'DSR not entered' in RED)
    story.append(PageBreak())
    story.append(Paragraph("4. DSR PENDING GPs", styles["SectionTitle"]))
    story.append(Paragraph(
        f"DSR Pending GPs: {len(report.dsr_pending_rows):,}",
        styles["ReportSubtitle"],
    ))
    dsr_pending_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat", "Attendance Status", "Attendance Time", "DSR Status",
    ]
    dsr_pending_widths = [10 * mm, 32 * mm, 38 * mm, 42 * mm, 32 * mm, available_width - 154 * mm]
    dsr_pending_table_rows: list[list[Any]] = []
    for item in report.dsr_pending_rows:
        raw_time = item.get("time_only") or _format_time_only(item.get("timestamp")) or "-"
        dsr_status_display = '<font color="#C00000"><b>DSR not entered</b></font>'
        dsr_pending_table_rows.append([
            item["serial"],
            item["mandal"],
            item["gp"],
            item["attendance_status"],
            raw_time,
            dsr_status_display,
        ])
    if not dsr_pending_table_rows:
        dsr_pending_table_rows = [["-", "-", "No eligible GPs have pending DSR.", "-", "-", "-"]]
    dsr_pending_table = make_table(
        dsr_pending_headers, dsr_pending_table_rows, dsr_pending_widths,
        left_columns=(1, 2, 3),
    )
    if not report.dsr_pending_rows:
        dsr_pending_table.setStyle(TableStyle([
            ("SPAN", (2, 1), (-1, 1)), ("ALIGN", (2, 1), (-1, 1), "LEFT"),
        ]))
    story.append(dsr_pending_table)

    def append_contact_list_section(title: str, total_label: str, rows: list[dict[str, Any]]) -> None:
        story.append(PageBreak())
        story.append(Paragraph(title, styles["SectionTitle"]))
        story.append(Paragraph(f"{total_label}: {len(rows):,}", styles["ReportSubtitle"]))
        headers = [
            "Sl. No.", "Mandal", "Gram Panchayat",
            "Panchayat Secretary Name", "Nature of\nPosting", "Mobile Number", "Status",
        ]
        col_widths = [
            10 * mm, 26 * mm, 32 * mm, 40 * mm, 26 * mm, 28 * mm, available_width - 162 * mm,
        ]
        table_rows: list[list[Any]] = [
            [
                item["serial"],
                item["mandal"],
                item["gp"],
                _clean_name(item.get("ps_name")) or "-",
                item.get("nature_of_posting") or "-",
                item.get("mobile") or "-",
                item["status"] or "-",
            ]
            for item in rows
        ]
        if not table_rows:
            table_rows = [["-", "-", "No records found for this section.", "-", "-", "-", "-"]]
        table = make_table(headers, table_rows, col_widths, left_columns=(1, 2, 3, 4))
        if not rows:
            table.setStyle(TableStyle([("SPAN", (2, 1), (-1, 1)), ("ALIGN", (2, 1), (-1, 1), "LEFT")]))
        story.append(table)

    append_contact_list_section("5. Secretaries Reported as Leave", "Total Secretaries on leave", report.leave_rows)
    append_contact_list_section(
        "6. Secretaries Reported as Training / Meeting", "Total training/meeting records", report.meeting_training_rows,
    )

    # 7. GPs THAT SUBMITTED ATTENDANCE AFTER 9 AM (with PS Name, Nature of Posting, Mobile Number, Time in Red)
    story.append(PageBreak())
    story.append(Paragraph("7. GPs THAT SUBMITTED ATTENDANCE AFTER 9 AM", styles["SectionTitle"]))
    story.append(Paragraph(f"Total GPs after 9 AM: {len(report.after_9_rows):,}", styles["ReportSubtitle"]))
    after_9_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat",
        "Panchayat Secretary Name", "Nature of\nPosting", "Mobile Number",
        "Attendance\nTime", "Attendance\nStatus",
    ]
    after_9_widths = [
        9 * mm, 24 * mm, 28 * mm, 36 * mm, 22 * mm, 25 * mm, 24 * mm, available_width - 168 * mm,
    ]
    after_9_table_rows: list[list[Any]] = []
    for item in report.after_9_rows:
        raw_time = item.get("time_only") or _format_time_only(item.get("timestamp")) or "-"
        time_display = f'<font color="#C00000"><b>{raw_time}</b></font>' if raw_time != "-" else "-"
        after_9_table_rows.append([
            item["serial"],
            item["mandal"],
            item["gp"],
            _clean_name(item.get("ps_name")) or "-",
            item.get("nature_of_posting") or "-",
            item.get("mobile") or "-",
            time_display,
            item["status"] or "Present",
        ])
    if not after_9_table_rows:
        after_9_table_rows = [["-", "-", "No GPs submitted attendance after 9 AM.", "-", "-", "-", "-", "-"]]
    after_9_table = make_table(
        after_9_headers, after_9_table_rows, after_9_widths, left_columns=(1, 2, 3, 4),
    )
    if not report.after_9_rows:
        after_9_table.setStyle(TableStyle([
            ("SPAN", (2, 1), (-1, 1)), ("ALIGN", (2, 1), (-1, 1), "LEFT"),
        ]))
    story.append(after_9_table)

    doc = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=margin, leftMargin=margin,
        topMargin=13 * mm, bottomMargin=14 * mm,
        title=f"{report.district_name.title()} District PS Attendance Report",
        author=f"{report.district_name.title()} District",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


def detect_file_metadata(filename: str, raw_bytes: bytes) -> dict[str, Any]:
    """Inspect uploaded raw data file and extract district name and available mandals."""
    frame = read_source_file(filename, raw_bytes)
    district_name = "District"
    if "District Name" in frame.columns:
        s = frame["District Name"].dropna().map(_clean_string)
        s = s[s != ""]
        if not s.empty:
            district_name = _clean_name(s.mode().iloc[0]) or "District"

    mandals: list[str] = []
    if "Mandal Name" in frame.columns:
        raw_mandals = sorted(set(frame["Mandal Name"].dropna().map(_clean_string)))
        mandals = [_clean_name(m) for m in raw_mandals if m]

    return {
        "district_name": district_name,
        "mandals": mandals,
        "mandal_name": mandals[0] if len(mandals) == 1 else (", ".join(mandals) if mandals else ""),
        "total_records": len(frame),
    }


def generate_mandal_pdf(report: ReportData, output_path: str | Path, mandal_name: str | None = None) -> Path:
    """Create a focused 2-page Mandal GP Attendance & DSR report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    all_gps = report.all_gp_rows or []

    # Pick target mandal (if specified, filter by it; otherwise take the first mandal available)
    target_mandal = None
    if mandal_name and mandal_name.strip():
        req_name = mandal_name.strip().casefold()
        for r in all_gps:
            if r["mandal"].casefold() == req_name:
                target_mandal = r["mandal"]
                break
    if not target_mandal and report.mandal_rows:
        target_mandal = report.mandal_rows[0]["mandal"]
    if not target_mandal and all_gps:
        target_mandal = all_gps[0]["mandal"]
    if not target_mandal:
        target_mandal = "Mandal"

    mandal_gps = [r for r in all_gps if r["mandal"].casefold() == target_mandal.casefold()]
    if not mandal_gps:
        mandal_gps = all_gps

    page_width, _ = A4
    margin = 12 * mm
    available_width = page_width - 2 * margin
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MandalReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=14, leading=17, alignment=TA_CENTER, textColor=HexColor("#17365D"), spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="MandalReportSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=HexColor("#444444"), spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="MandalSectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=13, textColor=HexColor("#17365D"), spaceBefore=3, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="MandalCellLeft", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=8.4,
        alignment=TA_LEFT, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="MandalCellCenter", parent=styles["MandalCellLeft"], alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="MandalTableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.8,
        leading=8, alignment=TA_CENTER, textColor=colors.white, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="MandalTableHeaderLeft", parent=styles["MandalTableHeader"], alignment=TA_LEFT,
    ))

    def safe(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def make_table(
        headers: list[str], rows: list[list[Any]], widths: list[float], left_columns: tuple[int, ...] = (),
        total_row: bool = False,
    ) -> Table:
        data: list[list[Any]] = [[
            Paragraph(
                safe(value).replace("\n", "<br/>"),
                styles["MandalTableHeaderLeft"] if column_index in left_columns else styles["MandalTableHeader"],
            )
            for column_index, value in enumerate(headers)
        ]]
        for row in rows:
            formatted = []
            for column_index, value in enumerate(row):
                if isinstance(value, Flowable):
                    formatted.append(value)
                else:
                    cell_style = styles["MandalCellLeft"] if column_index in left_columns else styles["MandalCellCenter"]
                    text_val = "" if value is None else str(value)
                    if "<font" in text_val or "<b>" in text_val or "<br/>" in text_val:
                        formatted.append(Paragraph(text_val, cell_style))
                    else:
                        formatted.append(Paragraph(safe(text_val), cell_style))
            data.append(formatted)
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
        commands: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F4E78")),
            ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#A6A6A6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#EAF2F8")]),
        ]
        for column_index in left_columns:
            commands.append(("ALIGN", (column_index, 1), (column_index, -1), "LEFT"))
        if total_row:
            commands.extend([
                ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D9EAF7")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, HexColor("#1F4E78")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ])
        table.setStyle(TableStyle(commands))
        return table

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(HexColor("#B7C9D6"))
        canvas.line(margin, 10 * mm, width - margin, 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawString(margin, 6 * mm, f"{report.district_name.title()} District | {target_mandal.title()} Mandal | {report.report_date:%d-%m-%Y}")
        canvas.drawRightString(width - margin, 6 * mm, f"Page {document.page}")
        canvas.restoreState()

    # Filtered metrics for target mandal
    submitted_gps = [r for r in mandal_gps if r.get("submitted")]
    pending_gps = [r for r in mandal_gps if r.get("is_pending")]
    after_9_gps = [r for r in mandal_gps if r.get("after_9")]
    leave_gps = [r for r in mandal_gps if r.get("on_leave")]
    meeting_gps = [r for r in mandal_gps if r.get("meeting_training")]
    dsr_eligible_gps = [r for r in mandal_gps if r.get("dsr_eligible")]
    dsr_entered_gps = [r for r in mandal_gps if r.get("dsr_entered")]
    dsr_pending_gps = [r for r in mandal_gps if r.get("dsr_eligible") and not r.get("dsr_entered")]

    story: list[Any] = []
    # PAGE 1: Mandal Abstract & Exception Lists
    story.extend([
        Paragraph(f"{report.district_name.upper()} DISTRICT", styles["MandalReportTitle"]),
        Paragraph(f"{target_mandal.upper()} MANDAL &mdash; ATTENDANCE &amp; DSR REPORT", styles["MandalReportTitle"]),
        Paragraph(
            f"Report Date: {report.report_date:%d-%m-%Y} | Total GPs: {len(mandal_gps)} | "
            f"Attendance Submitted: {len(submitted_gps)} | Pending: {len(pending_gps)}",
            styles["MandalReportSubtitle"],
        ),
    ])

    # 1. Mandal Abstract Summary
    story.append(Paragraph("1. Mandal Abstract Summary", styles["MandalSectionTitle"]))
    total_gp_cnt = len(mandal_gps)
    before_9_cnt = len(submitted_gps) - len(after_9_gps)
    before_9_pct = (before_9_cnt / total_gp_cnt * 100) if total_gp_cnt else 0.0
    dsr_pct = (len(dsr_entered_gps) / len(dsr_eligible_gps) * 100) if dsr_eligible_gps else 0.0

    summary_headers = ["Indicator", "Count / Value", "Indicator", "Count / Value"]
    summary_widths = [45 * mm, 48 * mm, 45 * mm, available_width - 138 * mm]
    summary_rows = [
        ["Total Gram Panchayats", str(total_gp_cnt), "Submitted Before 9 AM", f"{before_9_cnt} ({before_9_pct:.2f}%)"],
        ["Submitted After 9 AM", f'<font color="#C00000"><b>{len(after_9_gps)}</b></font>' if after_9_gps else "0", "PS on Leave", str(len(leave_gps))],
        ["PS in Meeting / Training", str(len(meeting_gps)), "Attendance Pending", f'<font color="#C00000"><b>{len(pending_gps)}</b></font>' if pending_gps else "0"],
        ["Present PS (DSR Eligible)", str(len(dsr_eligible_gps)), "DSR Submitted", f"{len(dsr_entered_gps)} ({dsr_pct:.2f}%)"],
        ["DSR Pending", f'<font color="#C00000"><b>{len(dsr_pending_gps)}</b></font>' if dsr_pending_gps else "0", "Overall Attendance %", f"{(len(submitted_gps) / total_gp_cnt * 100):.2f}%" if total_gp_cnt else "0%"],
    ]
    summary_table = make_table(summary_headers, summary_rows, summary_widths, left_columns=(0, 2))
    story.append(summary_table)
    story.append(Spacer(1, 6))

    # 2. Attendance Pending GPs List
    story.append(Paragraph(f"2. Attendance Pending GPs (Total: {len(pending_gps)})", styles["MandalSectionTitle"]))
    pending_headers = ["Sl. No.", "Gram Panchayat Name", "Attendance Status"]
    pending_widths = [14 * mm, 95 * mm, available_width - 109 * mm]
    pending_table_rows: list[list[Any]] = []
    for idx, r in enumerate(pending_gps, start=1):
        pending_table_rows.append([
            idx, r["gp"],
            '<font color="#C00000"><b>Attendance Pending</b></font>',
        ])
    if not pending_table_rows:
        pending_table_rows = [["-", "All Gram Panchayats have submitted morning attendance.", "-"]]
    pending_tbl = make_table(pending_headers, pending_table_rows, pending_widths, left_columns=(1,))

    if not pending_gps:
        pending_tbl.setStyle(TableStyle([("SPAN", (1, 1), (-1, 1)), ("ALIGN", (1, 1), (-1, 1), "LEFT")]))
    story.append(pending_tbl)
    story.append(Spacer(1, 6))

    # 3. DSR Pending GPs List
    story.append(Paragraph(f"3. DSR Pending GPs (Total: {len(dsr_pending_gps)})", styles["MandalSectionTitle"]))
    dsrp_headers = ["Sl. No.", "Gram Panchayat Name", "Attendance Status", "Attendance Time", "DSR Status"]
    dsrp_widths = [12 * mm, 56 * mm, 40 * mm, 38 * mm, available_width - 146 * mm]
    dsrp_table_rows: list[list[Any]] = []
    for idx, r in enumerate(dsr_pending_gps, start=1):
        dsrp_table_rows.append([
            idx, r["gp"],
            r.get("status") or "Present",
            r.get("time_only") or "-",
            '<font color="#C00000"><b>DSR not entered</b></font>',
        ])
    if not dsrp_table_rows:
        dsrp_table_rows = [["-", "All eligible Gram Panchayats have entered DSR.", "-", "-", "-"]]
    dsrp_tbl = make_table(dsrp_headers, dsrp_table_rows, dsrp_widths, left_columns=(1,))
    if not dsr_pending_gps:
        dsrp_tbl.setStyle(TableStyle([("SPAN", (1, 1), (-1, 1)), ("ALIGN", (1, 1), (-1, 1), "LEFT")]))
    story.append(dsrp_tbl)
    story.append(Spacer(1, 6))

    # 4. GPs Submitted Attendance After 9 AM
    story.append(Paragraph(f"4. GPs Submitted Attendance After 9 AM (Total: {len(after_9_gps)})", styles["MandalSectionTitle"]))
    after9_headers = ["Sl. No.", "Gram Panchayat Name", "Attendance Time", "Attendance Status"]
    after9_widths = [14 * mm, 95 * mm, 45 * mm, available_width - 154 * mm]
    after9_table_rows: list[list[Any]] = []
    for idx, r in enumerate(after_9_gps, start=1):
        after9_table_rows.append([
            idx, r["gp"],
            f'<font color="#C00000"><b>{r.get("time_only")}</b></font>',
            r.get("status") or "Present",
        ])
    if not after9_table_rows:
        after9_table_rows = [["-", "No Gram Panchayats submitted attendance after 9 AM.", "-", "-"]]
    after9_tbl = make_table(after9_headers, after9_table_rows, after9_widths, left_columns=(1,))

    if not after_9_gps:
        after9_tbl.setStyle(TableStyle([("SPAN", (1, 1), (-1, 1)), ("ALIGN", (1, 1), (-1, 1), "LEFT")]))
    story.append(after9_tbl)

    # PAGE 2: Full GP Attendance and DSR Status
    story.append(PageBreak())
    story.extend([
        Paragraph(f"{report.district_name.upper()} DISTRICT", styles["MandalReportTitle"]),
        Paragraph(f"{target_mandal.upper()} MANDAL &mdash; GP ATTENDANCE &amp; DSR REPORT", styles["MandalReportTitle"]),
        Paragraph(
            f"Report Date: {report.report_date:%d-%m-%Y} | Total GPs: {len(mandal_gps)} | "
            f"Attendance Submitted: {len(submitted_gps)} | Pending: {len(pending_gps)}",
            styles["MandalReportSubtitle"],
        ),
        Paragraph("5. Gram Panchayat Attendance & DSR Status", styles["MandalSectionTitle"]),
    ])

    gp_headers = [
        "Sl. No.", "Gram Panchayat Name", "Attendance Status", "Attendance Time", "DSR Entry Status",
    ]
    gp_widths = [12 * mm, 60 * mm, 38 * mm, 38 * mm, available_width - 148 * mm]
    gp_rows: list[list[Any]] = []
    for idx, r in enumerate(mandal_gps, start=1):
        if r.get("is_pending"):
            status_text = '<font color="#C00000"><b>Attendance Pending</b></font>'
        elif r.get("on_leave"):
            status_text = "On Leave"
        elif r.get("meeting_training"):
            status_text = "Meeting / Training"
        elif r.get("after_9"):
            status_text = '<font color="#C00000"><b>Present (After 9 AM)</b></font>'
        else:
            status_text = r.get("status") or "Present"

        # Rule: if submitted after 9 AM, color text in red
        time_raw = r.get("time_only") or ""
        if r.get("after_9") and time_raw:
            time_display = f'<font color="#C00000"><b>{time_raw}</b></font>'
        else:
            time_display = time_raw or "-"

        # DSR entry status
        if r.get("dsr_entered"):
            dsr_display = "Entered"
        elif r.get("dsr_eligible"):
            dsr_display = '<font color="#C00000"><b>DSR not entered</b></font>'
        else:
            dsr_display = "-"

        gp_rows.append([idx, r["gp"], status_text, time_display, dsr_display])

    story.append(make_table(gp_headers, gp_rows, gp_widths, left_columns=(1,)))

    doc = SimpleDocTemplate(
        str(output), pagesize=A4, rightMargin=margin, leftMargin=margin,
        topMargin=12 * mm, bottomMargin=13 * mm,
        title=f"{target_mandal.title()} Mandal GP Attendance Report",
        author=f"{report.district_name.title()} District",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PS attendance PDF report")
    parser.add_argument("input_file", help="Path to attendance raw-data file")
    parser.add_argument("--presentees", default=None, help="Optional path to Presentees Excel/CSV file")
    parser.add_argument("--absentees", default=None, help="Optional path to Absentees Excel/CSV file")
    parser.add_argument("--output", default=None, help="Optional output PDF path")
    args = parser.parse_args()
    source = Path(args.input_file)
    presentees_source = (Path(args.presentees).name, Path(args.presentees).read_bytes()) if args.presentees else None
    absentees_source = (Path(args.absentees).name, Path(args.absentees).read_bytes()) if args.absentees else None
    try:
        report = process_attendance_file(
            source.name,
            source.read_bytes(),
            presentees_source=presentees_source,
            absentees_source=absentees_source,
        )
        destination = Path(args.output) if args.output else Path(
            f"{report.district_name.replace(' ', '_')}_PS_Attendance_Report_{report.report_date:%d-%b-%Y}.pdf"
        )
        generate_pdf(report, destination)
    except InputValidationError as exc:
        parser.error(str(exc))
    print(f"PDF report created: {destination}")
    print(f"District: {report.district_name}")
    print(f"Unique GPs: {report.unique_gp_count:,}; duplicate LGD rows excluded: {report.duplicate_lgd_rows:,}")
    print(f"Totals: {report.totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

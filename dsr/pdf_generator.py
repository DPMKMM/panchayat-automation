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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
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
    cutoff_time_str: str = "09:00"
    cutoff_label: str = "9 AM"
    sort_by: str = "before_9"
    generated_at: datetime | None = None
    generated_time_str: str = ""

    def __post_init__(self) -> None:
        if not self.generated_time_str:
            gen_dt = self.generated_at or datetime.now()
            self.generated_time_str = gen_dt.strftime("%I:%M %p")

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
            "cutoff_time": self.cutoff_time_str,
            "cutoff_label": self.cutoff_label,
            "sort_by": self.sort_by,
            "generated_time": self.generated_time_str,
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
    if isinstance(value, str) and re.match(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", value):
        parsed_iso = pd.to_datetime(value, errors="coerce")
        if not pd.isna(parsed_iso):
            return parsed_iso
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
    cutoff_time: str | time | None = None,
    sort_by: str = "before_9",
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

    # Parse user-selected attendance cutoff time (defaults to 09:00 AM)
    if isinstance(cutoff_time, time):
        cutoff = cutoff_time
    elif isinstance(cutoff_time, str) and cutoff_time.strip():
        s = cutoff_time.strip().upper()
        try:
            if "AM" in s or "PM" in s:
                cutoff = datetime.strptime(s, "%I:%M %p").time()
            elif ":" in s:
                parts = s.split(":")
                cutoff = time(int(parts[0]), int(parts[1]))
            else:
                cutoff = time(int(s), 0)
        except Exception:
            cutoff = time(9, 0)
    else:
        cutoff = time(9, 0)

    if cutoff.minute == 0:
        cutoff_label = cutoff.strftime("%I %p").lstrip("0")
    else:
        cutoff_label = cutoff.strftime("%I:%M %p").lstrip("0")
    cutoff_time_str = cutoff.strftime("%H:%M")

    def is_before_cutoff(stamp: Any) -> bool:
        if pd.isna(stamp):
            return False
        return stamp.time() < cutoff

    records["before_9"] = records["submitted"] & records["parsed_timestamp"].map(is_before_cutoff)
    records["after_9"] = records["submitted"] & records["parsed_timestamp"].map(
        lambda value: (not pd.isna(value)) and value.time() >= cutoff
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

    # Merge DSR metrics into mandal_rows so all sorting options operate seamlessly
    dsr_by_mandal = {
        item["mandal"].strip().casefold(): item for item in dsr_mandal_rows
    }
    for item in mandal_rows:
        dsr_item = dsr_by_mandal.get(item["mandal"].strip().casefold(), {})
        item["present_ps"] = dsr_item.get("present_ps", 0)
        item["dsr_entered"] = dsr_item.get("dsr_entered", 0)
        item["dsr_pct"] = dsr_item.get("dsr_pct", 0.0)
        item["dsr_pending"] = dsr_item.get("dsr_pending", 0)

    # Apply 5 User Sorting Options:
    # 1. Sort based on before 9 AM or entered time (Punctuality %)
    # 2. Sort based overall attendance percentage
    # 3. Sort based on Dsr Percentage
    # 4. Based on no of GPs Attendance pending
    # 5. Based on no of GPs DSR Pending
    sort_by_norm = (sort_by or "before_9").strip().lower()
    if "overall" in sort_by_norm or "attendance_pct" in sort_by_norm or "att_pct" in sort_by_norm:
        mandal_rows.sort(key=lambda item: (item["attendance_pct"], item["mandal"].casefold()))
    elif "dsr_pct" in sort_by_norm or "dsr_percentage" in sort_by_norm or "dsr_percent" in sort_by_norm:
        mandal_rows.sort(key=lambda item: (item.get("dsr_pct", 0.0), item["mandal"].casefold()))
    elif "att_pending" in sort_by_norm or "attendance_pending" in sort_by_norm or "gps_att_pending" in sort_by_norm:
        mandal_rows.sort(key=lambda item: (-item["pending"], item["mandal"].casefold()))
    elif "dsr_pending" in sort_by_norm or "gps_dsr_pending" in sort_by_norm:
        mandal_rows.sort(key=lambda item: (-item.get("dsr_pending", 0), item["mandal"].casefold()))
    else:
        # Default: Sort based on punctuality % before entered cutoff time
        mandal_rows.sort(key=lambda item: (item["before_9_pct"], item["mandal"].casefold()))

    for index, item in enumerate(mandal_rows, start=1):
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
        cutoff_time_str=cutoff_time_str,
        cutoff_label=cutoff_label,
        sort_by=sort_by_norm,
    )


def process_attendance_file(
    filename: str,
    raw_bytes: bytes,
    presentees_source: tuple[str, bytes] | None = None,
    absentees_source: tuple[str, bytes] | None = None,
    ps_directory: dict[str, dict[str, str]] | None = None,
    cutoff_time: str | time | None = None,
    sort_by: str = "before_9",
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
        cutoff_time=cutoff_time,
        sort_by=sort_by,
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
        if self.height >= 17.5:
            font_size = 7.0
            text_offset = 8.8
            bar_h = 4.2
            bar_y = 2.6
        elif self.height > 16:
            font_size = 6.5
            text_offset = 8.0
            bar_h = 4.0
            bar_y = 2.4
        else:
            font_size = 6.0
            text_offset = 7.0
            bar_h = 3.5
            bar_y = 1.5
        self.canv.setFont("Helvetica-Bold", font_size)
        self.canv.setFillColor(HexColor("#1F2937"))
        text_y = self.height - text_offset
        self.canv.drawCentredString(self.width / 2, text_y, f"{self.percent:.2f}%")
        self.canv.setFillColor(HexColor("#E8EDF3"))
        self.canv.roundRect(0, bar_y, self.width, bar_h, 1.5, fill=1, stroke=0)
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
            self.canv.roundRect(0, bar_y, fill_width, bar_h, 1.5, fill=1, stroke=0)
        self.canv.restoreState()


def generate_pdf(report: ReportData, output_path: str | Path) -> Path:
    """Create a professional, printable A4 report with Landscape Page 1 and Portrait subsequent pages."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    land_w, default_land_h = landscape(A4)
    port_w, port_h = A4
    margin_land = 8 * mm
    margin_port = 12 * mm
    available_land_width = land_w - 2 * margin_land
    available_width = port_w - 2 * margin_port

    # Dynamically compute Landscape Page 1 height & row distribution based on mandal count
    # Guarantees the combined abstract table NEVER breaks across pages and fills A4 cleanly!
    num_mandals = len(report.mandal_rows)
    min_estimated_table_h = 15 * mm + (num_mandals * 5.6 * mm) + 6.0 * mm
    if report.duplicate_lgd_rows or report.missing_lgd_rows:
        min_estimated_table_h += 12 * mm
    required_land_h = min_estimated_table_h + 53 * mm
    dynamic_land_h = max(default_land_h, required_land_h)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CombinedTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=13, leading=15, alignment=TA_CENTER, textColor=HexColor("#17365D"), spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="CombinedSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8, leading=10, alignment=TA_CENTER, textColor=HexColor("#444444"), spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="HSuper", fontName="Helvetica-Bold", fontSize=7.2, leading=8.5,
        alignment=TA_CENTER, textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="HSub", fontName="Helvetica-Bold", fontSize=6.2, leading=7.2,
        alignment=TA_CENTER, textColor=colors.white, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="CombCellCenter", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.6, leading=7.8, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="CombCellLeft", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.6, leading=7.8, alignment=TA_LEFT, wordWrap="CJK",
    ))
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
        w, _ = canvas._pagesize
        foot_margin = margin_land if w > 600 else margin_port
        canvas.setStrokeColor(HexColor("#B7C9D6"))
        canvas.line(foot_margin, 8 * mm, w - foot_margin, 8 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#555555"))
        foot_time = f" {report.generated_time_str}" if getattr(report, "generated_time_str", "") else ""
        canvas.drawString(foot_margin, 4.5 * mm, f"{report.district_name.title()} District | PS Attendance & DSR Report | {report.report_date:%d-%m-%Y}{foot_time} | e-Panchayat Automation")
        canvas.drawRightString(w - foot_margin, 4.5 * mm, f"Page {document.page}")
        canvas.restoreState()

    story: list[Any] = []

    # ========================================================
    # PAGE 1 (LANDSCAPE): COMBINED ATTENDANCE & DSR ABSTRACT
    # ========================================================
    p_comb_title = Paragraph(
        f"1. {report.district_name.upper()} DISTRICT - MANDAL-WISE ATTENDANCE &amp; DSR ABSTRACT REPORT",
        styles["CombinedTitle"],
    )
    dsr_tot = report.dsr_district_total
    gen_time_part = f" | Generated Time: {report.generated_time_str}" if getattr(report, "generated_time_str", "") else ""
    p_comb_sub = Paragraph(
        f"Report Date: {report.report_date:%d-%m-%Y}{gen_time_part} | Total GPs: {report.unique_gp_count:,} | PS Present: {dsr_tot['present_ps']:,} | Total DSR Entered: {dsr_tot['dsr_entered']:,}",
        styles["CombinedSubtitle"],
    )
    story.append(p_comb_title)
    story.append(p_comb_sub)

    validation_notes: list[Any] = []
    if report.duplicate_lgd_rows:
        validation_notes.append(Spacer(1, 2))
        validation_notes.append(Paragraph(
            f"Validation: Excluded {report.duplicate_lgd_rows} duplicate LGD row(s).", styles["Note"],
        ))
    if report.missing_lgd_rows:
        validation_notes.append(Spacer(1, 1))
        validation_notes.append(Paragraph(
            f"Validation: Excluded {report.missing_lgd_rows} source row(s) without a Panchayat LGD code.",
            styles["Note"],
        ))

    # 14 column widths scaled to available landscape width (Includes Total PS Submitted before Overall Att. %)
    raw_widths = [9 * mm, 32 * mm, 12 * mm, 16 * mm, 21 * mm, 15 * mm, 21 * mm, 12 * mm, 13 * mm, 15 * mm, 14 * mm, 15 * mm, 15 * mm, 22 * mm]
    scale_land = available_land_width / sum(raw_widths)
    comb_widths = [w * scale_land for w in raw_widths]

    comb_headers_row0 = [
        Paragraph("Sl.<br/>No.", styles["HSuper"]),
        Paragraph("Mandal Name", styles["HSuper"]),
        Paragraph("Total<br/>GPs", styles["HSuper"]),
        Paragraph("PS ATTENDANCE ABSTRACT", styles["HSuper"]),
        "", "", "", "", "", "",
        Paragraph("DSR ABSTRACT REPORT", styles["HSuper"]),
        "", "", "",
    ]

    comb_headers_row1 = [
        "", "", "",
        Paragraph(f"Submitted<br/>&lt; {report.cutoff_label}", styles["HSub"]),
        Paragraph(f"&lt; {report.cutoff_label}<br/>%", styles["HSub"]),
        Paragraph("Total PS<br/>Submitted", styles["HSub"]),
        Paragraph("Overall<br/>Att. %", styles["HSub"]),
        Paragraph("On<br/>Leave", styles["HSub"]),
        Paragraph("Trg /<br/>Mtg", styles["HSub"]),
        Paragraph("Att.<br/>Pending", styles["HSub"]),
        Paragraph("PS<br/>Present", styles["HSub"]),
        Paragraph("DSR<br/>Entered", styles["HSub"]),
        Paragraph("DSR<br/>Pending", styles["HSub"]),
        Paragraph("% DSR<br/>Submitted", styles["HSub"]),
    ]

    comb_table_style = TableStyle([
        # Spans for Common columns
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (2, 1)),
        # Super-headers
        ("SPAN", (3, 0), (9, 0)),
        ("SPAN", (10, 0), (13, 0)),
        # Header background colors
        ("BACKGROUND", (0, 0), (2, 1), HexColor("#17365D")),
        ("BACKGROUND", (3, 0), (9, 0), HexColor("#0C3829")),
        ("BACKGROUND", (3, 1), (9, 1), HexColor("#165B43")),
        ("BACKGROUND", (10, 0), (13, 0), HexColor("#1E3A8A")),
        ("BACKGROUND", (10, 1), (13, 1), HexColor("#2563EB")),
        # Alignment & Padding
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("ROWBACKGROUNDS", (0, 2), (-1, -2), [colors.white, HexColor("#F8FAFC")]),
        # Total row
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D9EAF7")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, HexColor("#17365D")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ])

    # Measure exact top overhead, validation notes, and table header row heights so row heights
    # fill the remaining Page 1 height automatically without wasting page space or spilling to Page 2.
    _, title_h = p_comb_title.wrap(available_land_width, 500)
    _, sub_h = p_comb_sub.wrap(available_land_width, 500)
    non_table_h = title_h + p_comb_title.getSpaceAfter() + sub_h + p_comb_sub.getSpaceAfter()
    for flow in validation_notes:
        _, fh = flow.wrap(available_land_width, 500)
        non_table_h += fh + (flow.getSpaceAfter() if hasattr(flow, "getSpaceAfter") else 0)

    probe_hdr_table = Table([comb_headers_row0, comb_headers_row1], colWidths=comb_widths)
    probe_hdr_table.setStyle(comb_table_style)
    probe_hdr_table.wrap(available_land_width, 500)
    hdr_heights = list(probe_hdr_table._rowHeights)
    hdr_total_h = sum(hdr_heights)

    body_row_count = num_mandals + 1  # mandal data rows + DISTRICT TOTAL row
    actual_land_frame_h = dynamic_land_h - 18 * mm
    avail_for_body = max(body_row_count * 15.5, actual_land_frame_h - non_table_h - hdr_total_h - 6.0)
    target_row_h = min(32.0, avail_for_body / max(1, body_row_count))

    # Scale body typography & PercentBar height proportionally to row height
    if target_row_h >= 20.5:
        comb_font_size, comb_leading = 7.4, 8.8
    elif target_row_h >= 17.5:
        comb_font_size, comb_leading = 7.0, 8.2
    else:
        comb_font_size, comb_leading = 6.6, 7.8

    styles["CombCellCenter"].fontSize = comb_font_size
    styles["CombCellCenter"].leading = comb_leading
    styles["CombCellLeft"].fontSize = comb_font_size
    styles["CombCellLeft"].leading = comb_leading
    pbar_height = max(13.0, min(20.0, target_row_h - 3.6))

    dsr_by_mandal = {
        item["mandal"].strip().casefold(): item for item in report.dsr_mandal_rows
    }

    comb_table_rows: list[list[Any]] = [comb_headers_row0, comb_headers_row1]
    body_natural_heights: list[float] = []
    for idx, item in enumerate(report.mandal_rows, start=1):
        m_name = item["mandal"]
        dsr_item = dsr_by_mandal.get(m_name.strip().casefold(), {})

        att_submitted = item.get("attendance_submitted", 0)
        att_pending = item["pending"]
        att_pending_str = f'<font color="#C00000"><b>{att_pending}</b></font>' if att_pending > 0 else str(att_pending)

        dsr_present = dsr_item.get("present_ps", 0)
        dsr_entered = dsr_item.get("dsr_entered", 0)
        dsr_pending = dsr_item.get("dsr_pending", 0)
        dsr_pct = dsr_item.get("dsr_pct", 0.0)
        dsr_pending_str = f'<font color="#C00000"><b>{dsr_pending}</b></font>' if dsr_pending > 0 else str(dsr_pending)

        p_mandal = Paragraph(safe(m_name), styles["CombCellLeft"])
        _, mh = p_mandal.wrap(max(10.0, comb_widths[1] - 2.4), 200)
        body_natural_heights.append(max(pbar_height + 2.8, mh + 2.8))

        row = [
            Paragraph(str(idx), styles["CombCellCenter"]),
            p_mandal,
            Paragraph(str(item["total_gps"]), styles["CombCellCenter"]),
            Paragraph(str(item["before_9"]), styles["CombCellCenter"]),
            PercentBar(item["before_9_pct"], comb_widths[4] - 4, height=pbar_height),
            Paragraph(str(att_submitted), styles["CombCellCenter"]),
            PercentBar(item["attendance_pct"], comb_widths[6] - 4, height=pbar_height),
            Paragraph(str(item["on_leave"]), styles["CombCellCenter"]),
            Paragraph(str(item["meeting_training"]), styles["CombCellCenter"]),
            Paragraph(att_pending_str, styles["CombCellCenter"]),
            Paragraph(str(dsr_present), styles["CombCellCenter"]),
            Paragraph(str(dsr_entered), styles["CombCellCenter"]),
            Paragraph(dsr_pending_str, styles["CombCellCenter"]),
            PercentBar(dsr_pct, comb_widths[13] - 4, height=pbar_height),
        ]
        comb_table_rows.append(row)

    total = report.district_total
    dsr_total = report.dsr_district_total

    tot_att_submitted = total.get("attendance_submitted", 0)
    tot_att_pending = total["pending"]
    tot_att_pending_str = f'<font color="#C00000"><b>{tot_att_pending}</b></font>' if tot_att_pending > 0 else f'<b>{tot_att_pending}</b>'

    tot_dsr_pending = dsr_total["dsr_pending"]
    tot_dsr_pending_str = f'<font color="#C00000"><b>{tot_dsr_pending}</b></font>' if tot_dsr_pending > 0 else f'<b>{tot_dsr_pending}</b>'

    body_natural_heights.append(pbar_height + 3.2)
    comb_total_row = [
        "",
        Paragraph("<b>DISTRICT TOTAL</b>", styles["CombCellLeft"]),
        Paragraph(f"<b>{total['total_gps']}</b>", styles["CombCellCenter"]),
        Paragraph(f"<b>{total['before_9']}</b>", styles["CombCellCenter"]),
        PercentBar(total["before_9_pct"], comb_widths[4] - 4, height=pbar_height),
        Paragraph(f"<b>{tot_att_submitted}</b>", styles["CombCellCenter"]),
        PercentBar(total["attendance_pct"], comb_widths[6] - 4, height=pbar_height),
        Paragraph(f"<b>{total['on_leave']}</b>", styles["CombCellCenter"]),
        Paragraph(f"<b>{total['meeting_training']}</b>", styles["CombCellCenter"]),
        Paragraph(tot_att_pending_str, styles["CombCellCenter"]),
        Paragraph(f"<b>{dsr_total['present_ps']}</b>", styles["CombCellCenter"]),
        Paragraph(f"<b>{dsr_total['dsr_entered']}</b>", styles["CombCellCenter"]),
        Paragraph(tot_dsr_pending_str, styles["CombCellCenter"]),
        PercentBar(dsr_total["dsr_pct"], comb_widths[13] - 4, height=pbar_height),
    ]
    comb_table_rows.append(comb_total_row)

    body_row_heights = [max(target_row_h, nh) for nh in body_natural_heights]
    total_needed_table_h = hdr_total_h + sum(body_row_heights)
    if total_needed_table_h + non_table_h + 6.0 > actual_land_frame_h:
        dynamic_land_h = total_needed_table_h + non_table_h + 6.0 + 18 * mm

    comb_row_heights = hdr_heights + body_row_heights
    comb_table = Table(comb_table_rows, colWidths=comb_widths, rowHeights=comb_row_heights, repeatRows=2, splitByRow=1)
    comb_table.setStyle(comb_table_style)
    story.append(comb_table)

    story.extend(validation_notes)

    # ========================================================
    # PAGE 2+ (PORTRAIT): DETAIL SECTIONS 2 THROUGH 6
    # ========================================================
    story.append(NextPageTemplate("Portrait"))
    story.append(PageBreak())
    story.append(Paragraph("2. ATTENDANCE PENDING GPs", styles["SectionTitle"]))
    story.append(Paragraph(f"Total pending GPs: {len(report.pending_rows):,}", styles["ReportSubtitle"]))
    pending_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat",
        "Panchayat Secretary Name", "Nature of\nPosting", "Mobile Number",
    ]
    pending_widths = [10 * mm, 28 * mm, 36 * mm, 44 * mm, 34 * mm, available_width - 152 * mm]
    pending_table_rows: list[list[Any]] = [
        [
            idx,
            item["mandal"],
            item["gp"],
            _clean_name(item.get("ps_name")) or "-",
            item.get("nature_of_posting") or "-",
            item.get("mobile") or "-",
        ]
        for idx, item in enumerate(report.pending_rows, start=1)
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

    # 3. DSR PENDING GPs (with Attendance Time and 'DSR not entered' in RED)
    story.append(PageBreak())
    story.append(Paragraph("3. DSR PENDING GPs", styles["SectionTitle"]))
    story.append(Paragraph(
        f"DSR Pending GPs: {len(report.dsr_pending_rows):,}",
        styles["ReportSubtitle"],
    ))
    dsr_pending_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat", "Attendance Status", "Attendance Time", "DSR Status",
    ]
    dsr_pending_widths = [10 * mm, 32 * mm, 38 * mm, 42 * mm, 32 * mm, available_width - 154 * mm]
    dsr_pending_table_rows: list[list[Any]] = []
    for idx, item in enumerate(report.dsr_pending_rows, start=1):
        raw_time = item.get("time_only") or _format_time_only(item.get("timestamp")) or "-"
        dsr_status_display = '<font color="#C00000"><b>DSR not entered</b></font>'
        dsr_pending_table_rows.append([
            idx,
            item["mandal"],
            item["gp"],
            item.get("attendance_status", "Present"),
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
                idx,
                item["mandal"],
                item["gp"],
                _clean_name(item.get("ps_name")) or "-",
                item.get("nature_of_posting") or "-",
                item.get("mobile") or "-",
                item.get("status") or "-",
            ]
            for idx, item in enumerate(rows, start=1)
        ]
        if not table_rows:
            table_rows = [["-", "-", "No records found for this section.", "-", "-", "-", "-"]]
        table = make_table(headers, table_rows, col_widths, left_columns=(1, 2, 3, 4))
        if not rows:
            table.setStyle(TableStyle([("SPAN", (2, 1), (-1, 1)), ("ALIGN", (2, 1), (-1, 1), "LEFT")]))
        story.append(table)

    append_contact_list_section("4. SECRETARIES REPORTED AS LEAVE", "Total Secretaries on leave", report.leave_rows)
    append_contact_list_section(
        "5. SECRETARIES REPORTED AS TRAINING / MEETING", "Total training/meeting records", report.meeting_training_rows,
    )

    # 6. GPs THAT SUBMITTED ATTENDANCE AFTER {cutoff} (with PS Name, Nature of Posting, Mobile Number, Time in Red)
    story.append(PageBreak())
    story.append(Paragraph(f"6. GPs THAT SUBMITTED ATTENDANCE AFTER {report.cutoff_label.upper()}", styles["SectionTitle"]))
    story.append(Paragraph(f"Total GPs after {report.cutoff_label}: {len(report.after_9_rows):,}", styles["ReportSubtitle"]))
    after_9_headers = [
        "Sl. No.", "Mandal", "Gram Panchayat",
        "Panchayat Secretary Name", "Nature of\nPosting", "Mobile Number",
        "Attendance\nTime", "Attendance\nStatus",
    ]
    after_9_widths = [
        9 * mm, 24 * mm, 28 * mm, 36 * mm, 22 * mm, 25 * mm, 24 * mm, available_width - 168 * mm,
    ]
    after_9_table_rows: list[list[Any]] = []
    for idx, item in enumerate(report.after_9_rows, start=1):
        raw_time = item.get("time_only") or _format_time_only(item.get("timestamp")) or "-"
        time_display = f'<font color="#C00000"><b>{raw_time}</b></font>' if raw_time != "-" else "-"
        after_9_table_rows.append([
            idx,
            item["mandal"],
            item["gp"],
            _clean_name(item.get("ps_name")) or "-",
            item.get("nature_of_posting") or "-",
            item.get("mobile") or "-",
            time_display,
            item.get("status") or "Present",
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

    frame_land = Frame(
        margin_land, 10 * mm, available_land_width, dynamic_land_h - 18 * mm,
        id="F_Landscape", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0,
    )
    frame_port = Frame(
        margin_port, 12 * mm, available_width, port_h - 22 * mm,
        id="F_Portrait", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0,
    )

    doc = BaseDocTemplate(
        str(output),
        title=f"{report.district_name.title()} District PS Attendance & DSR Report",
        author=f"{report.district_name.title()} District",
    )
    tmpl_land = PageTemplate(id="Landscape", frames=[frame_land], pagesize=(land_w, dynamic_land_h), onPage=footer)
    tmpl_port = PageTemplate(id="Portrait", frames=[frame_port], pagesize=A4, onPage=footer)
    doc.addPageTemplates([tmpl_land, tmpl_port])
    doc.build(story)
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
        canvas.drawString(margin, 6 * mm, f"{report.district_name.title()} District | {target_mandal.title()} Mandal | {report.report_date:%d-%m-%Y} | e-Panchayat Automation")
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
        Paragraph(f"{target_mandal.upper()} MANDAL - ATTENDANCE &amp; DSR REPORT", styles["MandalReportTitle"]),
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
        ["Total Gram Panchayats", str(total_gp_cnt), f"Submitted Before {report.cutoff_label}", f"{before_9_cnt} ({before_9_pct:.2f}%)"],
        [f"Submitted After {report.cutoff_label}", f'<font color="#C00000"><b>{len(after_9_gps)}</b></font>' if after_9_gps else "0", "PS on Leave", str(len(leave_gps))],
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

    # 4. GPs Submitted Attendance After Cutoff Time
    story.append(Paragraph(f"4. GPs Submitted Attendance After {report.cutoff_label} (Total: {len(after_9_gps)})", styles["MandalSectionTitle"]))
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
        Paragraph(f"{target_mandal.upper()} MANDAL - GP ATTENDANCE &amp; DSR REPORT", styles["MandalReportTitle"]),
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

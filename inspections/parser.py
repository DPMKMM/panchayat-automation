"""Universal parser for GM-R 39.1 weekly Excel / HTML-table / XML / CSV downloads."""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from inspections.models import (
    InspectionRecord,
    get_designation_spec,
)


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", "nat"):
        return ""
    return re.sub(r"\s+", " ", s)


def _norm_header(val: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _clean_text(val).lower())


def _is_summary_or_blank_unit(val: str) -> bool:
    low = val.strip().lower()
    if not low or low in ("-", "--", "na", "n/a", "select"):
        return True
    if low == "total" or low.startswith("total ") or "grand total" in low or low.startswith("sub total"):
        return True
    return False


def _table_score(df: pd.DataFrame) -> tuple[int, int, int]:
    """Score extracted tables so data tables with real headers always beat banner tables (even with 1 row)."""
    if df is None or df.empty:
        return (0, 0, 0)
    header_keywords = (
        "finalsubmitstatus",
        "submitstatus",
        "panchayatname",
        "mandalname",
        "divisionname",
        "districtname",
        "dateofinspection",
        "inspectionfromdate",
        "inspectiontodate",
        "attendencedatetime",
        "attendancedatetime",
        "sno",
        "slno",
    )
    keyword_hits = 0
    for idx in range(min(8, len(df))):
        row_norms = [_norm_header(v) for v in df.iloc[idx].tolist()]
        hits = sum(1 for cell in row_norms if cell and any(kw in cell for kw in header_keywords))
        if hits > keyword_hits:
            keyword_hits = hits

    # Count rows that have >= 3 distinct non-empty cell values (ignores colspan banner rows)
    distinct_data_rows = 0
    for idx in range(len(df)):
        vals = {_clean_text(v) for v in df.iloc[idx].tolist() if _clean_text(v)}
        if len(vals) >= 3:
            distinct_data_rows += 1

    return (1 if keyword_hits >= 2 else 0, keyword_hits, distinct_data_rows * max(1, df.shape[1]))


def _normalize_table_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure tables whose <th> row was promoted into df.columns keep headers as row 0."""
    clean = df.fillna("")
    cols = list(clean.columns)
    has_string_headers = not isinstance(clean.columns, pd.RangeIndex) and any(
        isinstance(c, str) and not c.startswith("Unnamed:") and _clean_text(c)
        for c in cols
    )
    if has_string_headers:
        hdr_row = pd.DataFrame([[_clean_text(c) for c in cols]])
        body = clean.copy()
        body.columns = list(range(len(cols)))
        return pd.concat([hdr_row, body], ignore_index=True).fillna("")
    return clean.set_axis(list(range(clean.shape[1])), axis=1)


def _pick_best_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    cleaned = [_normalize_table_df(t) for t in tables if t is not None and not t.empty]
    if not cleaned:
        return pd.DataFrame()
    return max(cleaned, key=_table_score)


def _read_raw_tables(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    """Read raw portal Excel (.xls HTML-table, BIFF .xls, .xlsx, XML, or CSV) into a DataFrame."""
    if not raw_bytes:
        return pd.DataFrame()

    head_low = raw_bytes[:4096].decode("utf-8", errors="ignore").lower()
    fname_low = (filename or "").lower()

    # 1. HTML-backed .xls exports (standard EPTS ASP.NET Excel export format)
    if "<table" in head_low or "<html" in head_low or "<div" in head_low or fname_low.endswith((".html", ".htm")):
        html_text = raw_bytes.decode("utf-8", errors="ignore")
        try:
            tables = pd.read_html(io.StringIO(html_text), header=None)
            if tables:
                return _pick_best_table(tables)
        except Exception:
            pass

    # 2. Zip / OOXML (.xlsx)
    if raw_bytes[:2] == b"PK" or fname_low.endswith(".xlsx"):
        try:
            df = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=0, header=None, engine="openpyxl")
            return df.fillna("")
        except Exception:
            pass

    # 3. OLE2 legacy BIFF (.xls)
    if raw_bytes[:4] == b"\xd0\xcf\x11\xe0" or fname_low.endswith(".xls"):
        try:
            df = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=0, header=None, engine="xlrd")
            return df.fillna("")
        except Exception:
            try:
                tables = pd.read_html(io.StringIO(raw_bytes.decode("utf-8", errors="ignore")), header=None)
                if tables:
                    return _pick_best_table(tables)
            except Exception:
                pass

    # 4. XML SpreadsheetML fallback
    if "<?xml" in head_low or "<workbook" in head_low:
        try:
            from xml.etree import ElementTree as ET

            root = ET.fromstring(raw_bytes)
            rows_out: list[list[str]] = []
            for row_el in root.iter():
                if row_el.tag.endswith("Row"):
                    r_vals: list[str] = []
                    for cell in row_el:
                        if cell.tag.endswith("Cell"):
                            txt = "".join(t.text or "" for t in cell.iter() if t.tag.endswith("Data"))
                            r_vals.append(txt.strip())
                    if any(r_vals):
                        rows_out.append(r_vals)
            if rows_out:
                return pd.DataFrame(rows_out).fillna("")
        except Exception:
            pass

    # 5. CSV / TSV fallback
    try:
        text = raw_bytes.decode("utf-8-sig", errors="ignore")
        sep = "\t" if text.count("\t") > text.count(",") else ","
        return pd.read_csv(io.StringIO(text), header=None, sep=sep).fillna("")
    except Exception:
        return pd.DataFrame()


def _detect_header_row_index(raw_df: pd.DataFrame) -> int:
    """Locate the table header row skipping portal title banners."""
    max_scan = min(20, len(raw_df))
    best_idx = 0
    best_score = -1
    keywords = (
        "finalsubmitstatus",
        "submitstatus",
        "mandal",
        "division",
        "district",
        "panchayat",
        "grampanchayat",
        "designation",
        "slno",
        "sno",
    )
    for idx in range(max_scan):
        row_vals = [_norm_header(v) for v in raw_df.iloc[idx].tolist()]
        score = sum(1 for v in row_vals if v and any(kw in v for kw in keywords))
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def _find_col(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    norm_headers = [_norm_header(h) for h in headers]
    for cand in candidates:
        c_norm = _norm_header(cand)
        for idx, h in enumerate(norm_headers):
            if h == c_norm:
                return idx
    for cand in candidates:
        c_norm = _norm_header(cand)
        for idx, h in enumerate(norm_headers):
            if c_norm and c_norm in h:
                return idx
    return None


def parse_inspection_file(
    filename: str,
    raw_bytes: bytes,
    designation: str,
    week_label: str = "",
) -> dict[str, Any]:
    """Parse one weekly GM-R 39.1 export and filter strictly for Final Submit Status == 'Submitted'."""
    spec = get_designation_spec(designation)
    canon_desig = spec["designation"]
    group_level = spec["group_level"]

    raw_df = _read_raw_tables(filename, raw_bytes)
    if raw_df.empty:
        return {
            "submitted_records": [],
            "observed_units": set(),
            "district_names": set(),
            "detected_weeks": [],
            "raw_row_count": 0,
            "submitted_row_count": 0,
            "excluded_non_submitted_count": 0,
        }

    hdr_idx = _detect_header_row_index(raw_df)
    headers = [_clean_text(v) for v in raw_df.iloc[hdr_idx].tolist()]
    body_df = raw_df.iloc[hdr_idx + 1:].reset_index(drop=True)

    col_status = _find_col(
        headers,
        (
            "Final Submit Status",
            "Final Status",
            "Submit Status",
            "Final Submission Status",
            "Submission Status",
        ),
    )
    col_mandal = _find_col(headers, ("Mandal Name", "Mandal", "Name of Mandal"))
    col_mandal_lgd = _find_col(headers, ("Mandal LGD Code", "LGD Code", "Mandal Code"))
    col_division = _find_col(
        headers,
        ("Division Name", "Division", "Sub Division", "DLPO Division", "Revenue Division"),
    )
    col_district = _find_col(headers, ("District Name", "District", "Dist Name"))
    col_gp = _find_col(headers, ("Panchayat Name", "Gram Panchayat Name", "Gram Panchayat", "GP Name", "Panchayat"))
    col_gp_id = _find_col(headers, ("Panchayat Id", "GP Id", "Panchayat Code"))
    col_attendance = _find_col(headers, ("Attendence Date-Time", "Attendance Date-Time", "Attendance DateTime"))
    col_from_date = _find_col(headers, ("Inspection From Date", "From Date", "Week From"))
    col_to_date = _find_col(headers, ("Inspection To Date", "To Date", "Week To"))
    col_officer = _find_col(
        headers,
        ("Officer Name", "Inspecting Officer", "Name of the Officer", "Employee Name", "Officer", "Emp Name"),
    )
    col_date = _find_col(
        headers,
        ("Date of Inspection", "Inspection Date", "Visited Date", "Entry Date", "Submitted Date"),
    )
    col_desig = _find_col(headers, ("Designation", "Officer Designation"))

    submitted_records: list[InspectionRecord] = []
    observed_units: set[str] = set()
    district_names: set[str] = set()
    detected_weeks: list[str] = []
    seen_weeks: set[str] = set()
    raw_row_count = 0
    excluded_non_submitted = 0

    for _, row in body_df.iterrows():
        cells = [_clean_text(v) for v in row.tolist()]
        if not any(cells):
            continue

        dist_val = cells[col_district] if col_district is not None and col_district < len(cells) else ""
        div_val = cells[col_division] if col_division is not None and col_division < len(cells) else ""
        mandal_val = cells[col_mandal] if col_mandal is not None and col_mandal < len(cells) else ""
        mandal_lgd_val = cells[col_mandal_lgd] if col_mandal_lgd is not None and col_mandal_lgd < len(cells) else ""
        gp_val = cells[col_gp] if col_gp is not None and col_gp < len(cells) else ""
        gp_id_val = cells[col_gp_id] if col_gp_id is not None and col_gp_id < len(cells) else ""
        att_val = cells[col_attendance] if col_attendance is not None and col_attendance < len(cells) else ""
        from_dt_val = cells[col_from_date] if col_from_date is not None and col_from_date < len(cells) else ""
        to_dt_val = cells[col_to_date] if col_to_date is not None and col_to_date < len(cells) else ""
        officer_val = cells[col_officer] if col_officer is not None and col_officer < len(cells) else ""
        date_val = cells[col_date] if col_date is not None and col_date < len(cells) else ""
        status_val = cells[col_status] if col_status is not None and col_status < len(cells) else ""
        row_desig = cells[col_desig] if col_desig is not None and col_desig < len(cells) else canon_desig

        # Skip summary rows ("Total", "Grand Total") or repeated header rows
        if any(
            v.strip().lower() in ("total", "grand total", "sub total", "sl.no", "sl no", "s.no")
            for v in cells[:3]
            if v
        ):
            continue
        if col_status is not None and _norm_header(status_val) == "finalsubmitstatus":
            continue

        if group_level == "mandal":
            unit_name = mandal_val or div_val or dist_val
        elif group_level == "division":
            unit_name = div_val or mandal_val or dist_val
        else:
            unit_name = dist_val or div_val or mandal_val

        if _is_summary_or_blank_unit(unit_name):
            continue

        # Derive week range from Inspection From Date / Inspection To Date when present
        row_week = ""
        if from_dt_val and to_dt_val:
            row_week = f"{from_dt_val} to {to_dt_val}"
        elif from_dt_val:
            row_week = from_dt_val
        if row_week and row_week not in seen_weeks:
            seen_weeks.add(row_week)
            detected_weeks.append(row_week)

        # Normalize casing for display consistency
        unit_clean = _clean_text(unit_name).title() if unit_name.isupper() else _clean_text(unit_name)
        dist_clean = _clean_text(dist_val).title() if dist_val.isupper() else _clean_text(dist_val)
        div_clean = _clean_text(div_val).title() if div_val.isupper() else _clean_text(div_val)
        mandal_clean = _clean_text(mandal_val).title() if mandal_val.isupper() else _clean_text(mandal_val)

        raw_row_count += 1
        observed_units.add(unit_clean)
        if dist_clean:
            district_names.add(dist_clean)

        # Strict Rule: Consider ONLY Final Submit Status == 'Submitted'
        if status_val.strip().casefold() != "submitted":
            excluded_non_submitted += 1
            continue

        # Count Entered / Not Entered parameter columns if present
        entered_cnt = 0
        param_total = 0
        for c_idx, cell_txt in enumerate(cells):
            if c_idx == col_status:
                continue
            low_cell = cell_txt.strip().lower()
            if low_cell == "entered":
                entered_cnt += 1
                param_total += 1
            elif low_cell == "not entered":
                param_total += 1
        checklist_str = f"{entered_cnt}/{param_total} Entered" if param_total > 0 else ""

        effective_week = (week_label or "").strip() or row_week or filename
        effective_officer = officer_val or (f"Attendance: {att_val}" if att_val else canon_desig)

        submitted_records.append(
            InspectionRecord(
                week_label=effective_week,
                designation=row_desig or canon_desig,
                district_name=dist_clean,
                division_name=div_clean,
                mandal_name=mandal_clean,
                gp_name=gp_val,
                officer_name=effective_officer,
                inspection_date=date_val,
                final_submit_status="Submitted",
                unit_name=unit_clean,
                mandal_lgd_code=mandal_lgd_val,
                panchayat_id=gp_id_val,
                attendance_datetime=att_val,
                inspection_from_date=from_dt_val,
                inspection_to_date=to_dt_val,
                checklist_entered=checklist_str,
            )
        )

    return {
        "submitted_records": submitted_records,
        "observed_units": observed_units,
        "district_names": district_names,
        "detected_weeks": detected_weeks,
        "raw_row_count": raw_row_count,
        "submitted_row_count": len(submitted_records),
        "excluded_non_submitted_count": excluded_non_submitted,
    }

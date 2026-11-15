"""
mobile_updation/service.py - Pending Mobile Number Assessments (Lookup) Processing Engine
Telangana e-Panchayat House Tax Demand Register vs Mobile Numbers Updated Report Reconciliation
"""

from __future__ import annotations

import csv
import io
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from uuid import uuid4

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def clean_asmt_no(val: Any) -> str:
    """Normalizes Assessment Number by stripping trailing .0, spaces, and formatting."""
    if val is None:
        return ""
    s = str(val).strip()
    s = re.sub(r"\.0$", "", s).strip()
    # Normalize scientific notation e.g. 1.23E+03 if needed
    try:
        if "." in s and ("e" in s.lower() or s.replace(".", "").isdigit()):
            f = float(s)
            if f.is_integer():
                s = str(int(f))
    except Exception:
        pass
    return s.strip()


def parse_demand_register_bytes(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses Demand Register file supporting two exact e-Panchayat formats:
    1. HTML-disguised .xls files (starts with <div or <table with </tr> delimiters).
    2. Standard .xlsx Demand Register (e.g., RNPDR26-27.xlsx).
    """
    ext = Path(filename).suffix.lower()
    raw_head = file_bytes[:1024].decode("utf-8", errors="ignore").lower().strip()
    is_html_disguised = ("<html" in raw_head or "<table" in raw_head or "<div" in raw_head)

    records: List[Dict[str, Any]] = []
    seen_asmts: Set[str] = set()

    if is_html_disguised or ext == ".xls":
        # Format 1: HTML-disguised .xls table parsing
        text = file_bytes.decode("utf-8", errors="ignore")
        # Split by </tr> (case-insensitive)
        row_chunks = re.split(r"</\s*tr\s*>", text, flags=re.I)
        for chunk in row_chunks:
            if not chunk or "<td" not in chunk.lower():
                continue
            # Extract <td> content
            tds = re.findall(r"<td[^>]*>(.*?)</td>", chunk, flags=re.DOTALL | re.I)
            if not tds:
                continue
            cells = [re.sub(r"&nbsp;|<[^>]+>", "", cell).strip() for cell in tds]
            if not cells:
                continue
            # Row 0 must be numeric (SL.No)
            sl_no_raw = cells[0].replace(".", "").strip()
            if not sl_no_raw.isdigit():
                continue

            # Column mapping:
            # 0 -> SL.No, 1 -> ASMTNo, 3 -> House Number, 4 -> Owner Name, 6 -> MobileNo
            asmt_raw = cells[1] if len(cells) > 1 else ""
            house_no = cells[3] if len(cells) > 3 else "--"
            owner_name = cells[4] if len(cells) > 4 else "--"
            mob_no = cells[6] if len(cells) > 6 else ""

            asmt_clean = clean_asmt_no(asmt_raw)
            if not asmt_clean or asmt_clean in seen_asmts:
                continue
            seen_asmts.add(asmt_clean)

            records.append({
                "sl_no": int(sl_no_raw) if sl_no_raw.isdigit() else len(records) + 1,
                "asmt_clean": asmt_clean,
                "assessment_number": asmt_clean,
                "house_number": house_no or "--",
                "owner_name": owner_name or "--",
                "demand_mobile": mob_no or "",
            })

    if not records:
        # Format 2: Standard .xlsx (or fallback via openpyxl)
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                header_row_idx = -1
                col_sl = -1
                col_asmt = -1
                col_house = -1
                col_owner = -1
                col_mob = -1

                for idx, r in enumerate(rows[:10]):
                    r_str = [str(c or "").lower().strip() for c in r]
                    if any("sl" in c or "s.no" in c for c in r_str) and any("asmt" in c or "assessment" in c for c in r_str):
                        header_row_idx = idx
                        for c_idx, c_val in enumerate(r_str):
                            if ("sl" in c_val or "s.no" in c_val) and col_sl == -1:
                                col_sl = c_idx
                            elif ("asmt" in c_val or "assessment" in c_val) and "old" not in c_val and "prev" not in c_val and col_asmt == -1:
                                col_asmt = c_idx
                            elif ("house" in c_val or "door" in c_val or "h.no" in c_val) and col_house == -1:
                                col_house = c_idx
                            elif ("owner" in c_val or "name" in c_val) and "father" not in c_val and "husband" not in c_val and "mandal" not in c_val and "panchayat" not in c_val and col_owner == -1:
                                col_owner = c_idx
                            elif ("mobile" in c_val or "phone" in c_val) and col_mob == -1:
                                col_mob = c_idx
                        break

                # If any key column not found by header text, use standard e-Panchayat indices
                if header_row_idx == -1:
                    header_row_idx = 0
                if col_sl == -1:
                    col_sl = 0
                if col_asmt == -1:
                    col_asmt = 1
                if col_house == -1:
                    col_house = 3
                if col_owner == -1:
                    col_owner = 4
                if col_mob == -1:
                    col_mob = 6

                for r in rows[header_row_idx + 1:]:
                    if not r or len(r) <= col_asmt:
                        continue
                    sl_val = str(r[col_sl] if col_sl != -1 and col_sl < len(r) and r[col_sl] is not None else "").strip()
                    # Filter: numeric SL.No only (skips subheaders and TOTAL footer)
                    clean_sl = re.sub(r"\D+", "", sl_val)
                    if not clean_sl:
                        continue

                    asmt_raw = str(r[col_asmt] if col_asmt < len(r) and r[col_asmt] is not None else "").strip()
                    asmt_clean = clean_asmt_no(asmt_raw)
                    if not asmt_clean or asmt_clean.upper() in ("TOTAL", "GRAND TOTAL") or asmt_clean in seen_asmts:
                        continue
                    seen_asmts.add(asmt_clean)

                    house_no = str(r[col_house] if col_house != -1 and col_house < len(r) and r[col_house] is not None else "").strip()
                    owner = str(r[col_owner] if col_owner != -1 and col_owner < len(r) and r[col_owner] is not None else "").strip()
                    mob = str(r[col_mob] if col_mob != -1 and col_mob < len(r) and r[col_mob] is not None else "").strip()

                    records.append({
                        "sl_no": int(clean_sl) if clean_sl.isdigit() else len(records) + 1,
                        "asmt_clean": asmt_clean,
                        "assessment_number": asmt_clean,
                        "house_number": house_no or "--",
                        "owner_name": owner or "--",
                        "demand_mobile": mob or "",
                    })
        except Exception as exc:
            pass

    return records


def parse_updated_report_bytes(file_bytes: bytes) -> Tuple[Dict[str, str], Set[str], Dict[str, str]]:
    """
    Parses the Mobile Numbers Updated Report (.xlsx, .csv, or HTML table).
    Explicitly locates the header row where a cell equals "Assessment Number"
    (row index 6 / Excel row 7), reads the dataframe using that header row, and
    extracts df_up["Assessment Number"] (Column B / index 1), NEVER S.No. (Column A / index 0).
    Normalizes Assessment Number as string: .astype(str).str.replace(r"\\.0$", "", regex=True).str.strip().

    Returns:
    - metadata: {"district": ..., "mandal": ..., "gram_panchayat": ...}
    - updated_asmt_set: set of normalized Assessment Numbers
    - asmt_to_mobile: map of Assessment Number -> updated mobile number
    """
    metadata: Dict[str, str] = {
        "district": "",
        "mandal": "",
        "gram_panchayat": "",
    }
    updated_asmt_set: Set[str] = set()
    asmt_to_mobile: Dict[str, str] = {}

    if not file_bytes:
        return metadata, updated_asmt_set, asmt_to_mobile

    # Attempt parsing using pandas first
    try:
        raw_head = file_bytes[:1024].decode("utf-8", errors="ignore").lower().strip()
        is_html = ("<html" in raw_head or "<table" in raw_head or "<div" in raw_head)

        if is_html:
            dfs = pd.read_html(io.BytesIO(file_bytes), header=None)
            df_raw = dfs[0] if dfs else pd.DataFrame()
        else:
            try:
                df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
            except Exception:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), header=None)

        if not df_raw.empty:
            # 1. Locate header row where any cell equals "Assessment Number" (case-insensitive)
            header_idx = None
            for idx in range(min(25, len(df_raw))):
                row_vals = [
                    str(v).strip().lower()
                    for v in df_raw.iloc[idx].dropna()
                    if str(v).lower() != "nan"
                ]
                if any(
                    v in ("assessment number", "assessment no", "asmt no", "asmtno", "assessmentnum")
                    for v in row_vals
                ):
                    header_idx = idx
                    break

            # 2. Extract metadata from top rows (above header row)
            scan_limit = header_idx if header_idx is not None else min(10, len(df_raw))
            for idx in range(scan_limit):
                row_cells = [
                    str(v).strip()
                    for v in df_raw.iloc[idx].dropna()
                    if str(v).lower() != "nan"
                ]
                line_str = " ".join(row_cells)
                m_dist = re.search(r"District\s*:\s*([A-Za-z\s]+?)(?:Division|Mandal|$|,|\|)", line_str, re.I)
                if m_dist and not metadata["district"]:
                    metadata["district"] = m_dist.group(1).strip()
                m_mandal = re.search(r"Mandal\s*:\s*([A-Za-z\s]+?)(?:Gram|GP|$|,|\|)", line_str, re.I)
                if m_mandal and not metadata["mandal"]:
                    metadata["mandal"] = m_mandal.group(1).strip()
                m_gp = re.search(r"(?:Gram\s*Panchayat|GP)\s*:\s*([A-Za-z\s]+?)(?:Date|Generated|$|,|\|)", line_str, re.I)
                if m_gp and not metadata["gram_panchayat"]:
                    metadata["gram_panchayat"] = m_gp.group(1).strip()

            # 3. Read dataframe using header row and extract df_up["Assessment Number"]
            if header_idx is not None:
                header_row = [str(c).strip() for c in df_raw.iloc[header_idx]]
                df_up = df_raw.iloc[header_idx + 1:].copy()
                df_up.columns = header_row

                # Find "Assessment Number" column explicitly - NEVER select Column 0 (S.No.)
                asmt_col = None
                for col in df_up.columns:
                    clean_col = re.sub(r"[^a-z0-9]", "", str(col).lower())
                    if clean_col in ("assessmentnumber", "asmtno", "assessmentno", "asmtnumber"):
                        asmt_col = col
                        break

                # Fallback to Column B (index 1) if not found by name, NEVER Column A (index 0)
                if asmt_col is None and len(df_up.columns) > 1:
                    asmt_col = df_up.columns[1]

                # Identify Mobile column (New Mobile Number preferred, else Mobile Number)
                mob_col = None
                for cand in ("new mobile number", "newmobilenumber", "mobilenumber", "mobile no", "mobile", "phone"):
                    for col in df_up.columns:
                        if cand in re.sub(r"[^a-z0-9]", "", str(col).lower()):
                            mob_col = col
                            break
                    if mob_col:
                        break

                if asmt_col is not None:
                    # Normalize Assessment Number as string: .astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                    asmt_series = df_up[asmt_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

                    if mob_col is not None:
                        mob_series = df_up[mob_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                    else:
                        mob_series = pd.Series([""] * len(df_up), index=df_up.index)

                    for asmt_val, mob_val in zip(asmt_series, mob_series):
                        asmt_clean = clean_asmt_no(asmt_val)
                        if not asmt_clean or asmt_clean.upper() in ("TOTAL", "GRAND TOTAL", "NAN", "NONE", "--", "NA"):
                            continue
                        updated_asmt_set.add(asmt_clean)
                        asmt_to_mobile[asmt_clean] = mob_val if mob_val and mob_val.lower() != "nan" else ""

                    if updated_asmt_set:
                        return metadata, updated_asmt_set, asmt_to_mobile
    except Exception:
        pass

    # Fallback to openpyxl row parsing if pandas fails
    try:
        raw_head = file_bytes[:1024].decode("utf-8", errors="ignore").lower().strip()
        is_html = ("<html" in raw_head or "<table" in raw_head or "<div" in raw_head)
        rows: List[List[Any]] = []
        if is_html:
            text = file_bytes.decode("utf-8", errors="ignore")
            row_chunks = re.split(r"</\s*tr\s*>", text, flags=re.I)
            for chunk in row_chunks:
                if not chunk or ("<td" not in chunk.lower() and "<th" not in chunk.lower()):
                    continue
                cells_match = re.findall(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", chunk, flags=re.DOTALL | re.I)
                if cells_match:
                    rows.append([re.sub(r"&nbsp;|<[^>]+>", "", c).strip() for c in cells_match])
        else:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
                ws = wb.active
                rows = [list(r) for r in ws.iter_rows(values_only=True)]
            except Exception:
                text = file_bytes.decode("utf-8", errors="ignore")
                rows = [list(r) for r in csv.reader(io.StringIO(text))]

        if not rows:
            return metadata, updated_asmt_set, asmt_to_mobile

        for r in rows[:8]:
            line_str = " ".join(str(c or "") for c in r if str(c or "").lower() != "none")
            m_dist = re.search(r"District\s*:\s*([A-Za-z\s]+?)(?:Division|Mandal|$|,|\|)", line_str, re.I)
            if m_dist and not metadata["district"]:
                metadata["district"] = m_dist.group(1).strip()
            m_mandal = re.search(r"Mandal\s*:\s*([A-Za-z\s]+?)(?:Gram|GP|$|,|\|)", line_str, re.I)
            if m_mandal and not metadata["mandal"]:
                metadata["mandal"] = m_mandal.group(1).strip()
            m_gp = re.search(r"(?:Gram\s*Panchayat|GP)\s*:\s*([A-Za-z\s]+?)(?:Date|Generated|$|,|\|)", line_str, re.I)
            if m_gp and not metadata["gram_panchayat"]:
                metadata["gram_panchayat"] = m_gp.group(1).strip()

        header_idx = -1
        col_asmt = -1
        col_mob = -1

        for idx, r in enumerate(rows[:25]):
            r_norm = [re.sub(r"[^a-z0-9]", "", str(c or "").lower()) for c in r]
            for c_idx, c_clean in enumerate(r_norm):
                if c_clean in ("assessmentnumber", "asmtno", "assessmentno", "asmtnumber"):
                    header_idx = idx
                    col_asmt = c_idx
                elif "newmobile" in c_clean or ("mobile" in c_clean and col_mob == -1) or ("phone" in c_clean and col_mob == -1):
                    col_mob = c_idx
            if header_idx != -1 and col_asmt > 0:
                break

        # Explicitly ensure Assessment Number is never Column 0 (S.No.)
        if col_asmt <= 0:
            header_idx = 6 if len(rows) > 6 else 0
            col_asmt = 1
            col_mob = 5

        for r in rows[header_idx + 1:]:
            if not r or len(r) <= col_asmt:
                continue
            asmt_clean = clean_asmt_no(r[col_asmt])
            if not asmt_clean or asmt_clean.upper() in ("TOTAL", "GRAND TOTAL", "--", "NA", "NONE"):
                continue
            mob_raw = str(r[col_mob] or "").strip() if col_mob != -1 and col_mob < len(r) and r[col_mob] is not None else ""
            updated_asmt_set.add(asmt_clean)
            asmt_to_mobile[asmt_clean] = mob_raw
    except Exception:
        pass

    return metadata, updated_asmt_set, asmt_to_mobile


def perform_pending_lookup(
    demand_records: List[Dict[str, Any]],
    updated_asmt_set: Set[str],
    asmt_to_mobile: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Performs anti-join to detect pending assessments.
    Returns:
    - pending_records: records in demand not present in updated_asmt_set
    - full_reconciliation: all demand records matched against updated status
    """
    pending_records: List[Dict[str, Any]] = []
    full_reconciliation: List[Dict[str, Any]] = []

    for r in demand_records:
        asmt = r["asmt_clean"]
        is_updated = asmt in updated_asmt_set
        upd_mob = asmt_to_mobile.get(asmt, "")

        reconciled_item = {
            "sl_no": r["sl_no"],
            "assessment_number": r["assessment_number"],
            "house_number": r["house_number"],
            "owner_name": r["owner_name"],
            "demand_mobile": r["demand_mobile"],
            "updated_mobile": upd_mob,
            "status": "Updated" if is_updated else "Pending",
        }
        full_reconciliation.append(reconciled_item)

        if not is_updated:
            pending_records.append({
                "sl_no": len(pending_records) + 1,
                "assessment_number": r["assessment_number"],
                "house_number": r["house_number"],
                "owner_name": r["owner_name"],
                "remarks": "Pending",
            })

    return pending_records, full_reconciliation


def generate_lookup_excel_workbook(
    metadata: Dict[str, str],
    pending_records: List[Dict[str, Any]],
    full_reconciliation: List[Dict[str, Any]],
    total_demand: int,
    total_updated: int,
) -> io.BytesIO:
    """
    Generates the styled 2-sheet Excel workbook:
    - Sheet 1: Pending Assessments
    - Sheet 2: Full Lookup Reconciliation
    """
    wb = openpyxl.Workbook()

    # Brand Colors & Styles
    header_fill = PatternFill(start_color="064E3B", end_color="064E3B", fill_type="solid")  # Government Dark Forest Green
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="064E3B")
    subtitle_font = Font(name="Calibri", size=10, bold=True, color="374151")
    footer_font = Font(name="Calibri", size=11, bold=True, color="991B1B")

    pending_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")  # Red Tint
    pending_font = Font(name="Calibri", size=10, bold=True, color="991B1B")
    updated_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # Green Tint
    updated_font = Font(name="Calibri", size=10, bold=True, color="15803D")

    border_thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    border_double = Border(
        top=Side(style="thin", color="991B1B"),
        bottom=Side(style="double", color="991B1B"),
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
    )

    district = metadata.get("district") or "District"
    mandal = metadata.get("mandal") or "Mandal"
    gp = metadata.get("gram_panchayat") or "Gram Panchayat"

    # =========================================================================
    # SHEET 1: Pending Assessments
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Pending Assessments"

    # Title Banner
    ws1.merge_cells("A1:E1")
    t1 = ws1["A1"]
    t1.value = f"PENDING MOBILE NUMBER ASSESSMENTS · {gp.upper()} GP"
    t1.font = title_font
    t1.alignment = Alignment(horizontal="center", vertical="center")

    ws1.merge_cells("A2:E2")
    t2 = ws1["A2"]
    t2.value = f"Mandal: {mandal} | District: {district} | Report Date: {time.strftime('%d/%m/%Y')}"
    t2.font = subtitle_font
    t2.alignment = Alignment(horizontal="center", vertical="center")

    # Metric Row
    ws1.merge_cells("A3:E3")
    t3 = ws1["A3"]
    t3.value = f"Total Demand Assessments: {total_demand} | Updated: {total_updated} | Pending Seeding: {len(pending_records)}"
    t3.font = Font(name="Calibri", size=10, bold=True, color="047857")
    t3.alignment = Alignment(horizontal="center", vertical="center")

    ws1.append([])  # Blank Row 4

    headers1 = ["S.No", "Assessment Number", "Owner Name", "House Number", "Remarks"]
    ws1.append(headers1)
    h_row = 5
    for c_idx in range(1, len(headers1) + 1):
        cell = ws1.cell(row=h_row, column=c_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    start_row = 6
    if pending_records:
        for p in pending_records:
            ws1.append([
                p["sl_no"],
                p["assessment_number"],
                p["owner_name"],
                p["house_number"],
                p["remarks"],
            ])
            cur = ws1.max_row
            for col in range(1, 6):
                c = ws1.cell(row=cur, column=col)
                c.border = border_thin
                if col in (1, 2, 4):
                    c.alignment = Alignment(horizontal="center")
            # Style Remarks badge
            rem_cell = ws1.cell(row=cur, column=5)
            rem_cell.fill = pending_fill
            rem_cell.font = pending_font
            rem_cell.alignment = Alignment(horizontal="center")

        # Total Footer Row with Formula
        end_row = ws1.max_row
        ws1.append(["TOTAL PENDING", f"=COUNTA(B{start_row}:B{end_row})", "", "", "PENDING"])
        f_row = ws1.max_row
        ws1.merge_cells(f"C{f_row}:D{f_row}")
        for col in range(1, 6):
            fc = ws1.cell(row=f_row, column=col)
            fc.font = footer_font
            fc.border = border_double
            if col in (1, 2, 5):
                fc.alignment = Alignment(horizontal="center")
    else:
        # Green confirmation banner if 0 pending records
        ws1.merge_cells("A6:E6")
        succ_cell = ws1["A6"]
        succ_cell.value = "✓ EXCELLENT: 100% Mobile Numbers are Seeded & Updated. Zero Pending Assessments."
        succ_cell.fill = updated_fill
        succ_cell.font = Font(name="Calibri", size=11, bold=True, color="15803D")
        succ_cell.alignment = Alignment(horizontal="center", vertical="center")
        succ_cell.border = border_thin

    # Column widths for Sheet 1
    col_w1 = [8, 22, 34, 18, 16]
    for idx, w in enumerate(col_w1, 1):
        ws1.column_dimensions[get_column_letter(idx)].width = w

    # =========================================================================
    # SHEET 2: Full Lookup Reconciliation
    # =========================================================================
    ws2 = wb.create_sheet(title="Full Lookup Reconciliation")

    # Title
    ws2.merge_cells("A1:G1")
    ws2["A1"].value = f"FULL LOOKUP RECONCILIATION · {gp.upper()} GP"
    ws2["A1"].font = title_font
    ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws2.merge_cells("A2:G2")
    ws2["A2"].value = f"Demand Register vs Mobile Numbers Updated Report | Mandal: {mandal} | District: {district}"
    ws2["A2"].font = subtitle_font
    ws2["A2"].alignment = Alignment(horizontal="center", vertical="center")

    # Top KPI Summary Cards with formulas
    kpi_headers = ["Total Assessments", "Updated Count", "Pending Count", "Seeding Rate (%)"]
    ws2.append([])  # Row 3
    ws2.append(["", "Metric", "Formula Value", "", "", "", ""])

    headers2 = [
        "S.No",
        "Assessment Number",
        "Owner Name",
        "House Number",
        "Demand Mobile No",
        "Updated Mobile No",
        "Reconciliation Status",
    ]
    ws2.append(headers2)
    h2_row = 5
    for c_idx in range(1, len(headers2) + 1):
        cell = ws2.cell(row=h2_row, column=c_idx)
        cell.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Executive Navy Blue
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    s2_start = 6
    for rec in full_reconciliation:
        ws2.append([
            rec["sl_no"],
            rec["assessment_number"],
            rec["owner_name"],
            rec["house_number"],
            rec["demand_mobile"],
            rec["updated_mobile"],
            rec["status"],
        ])
        cur_row = ws2.max_row
        for col in range(1, 8):
            c = ws2.cell(row=cur_row, column=col)
            c.border = border_thin
            if col in (1, 2, 4, 5, 6):
                c.alignment = Alignment(horizontal="center")

        st_cell = ws2.cell(row=cur_row, column=7)
        if rec["status"] == "Updated":
            st_cell.fill = updated_fill
            st_cell.font = updated_font
        else:
            st_cell.fill = pending_fill
            st_cell.font = pending_font
        st_cell.alignment = Alignment(horizontal="center")

    # Column widths for Sheet 2
    col_w2 = [8, 22, 34, 18, 20, 20, 22]
    for idx, w in enumerate(col_w2, 1):
        ws2.column_dimensions[get_column_letter(idx)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def generate_lookup_pdf_report(
    metadata: Dict[str, str],
    pending_records: List[Dict[str, Any]],
    total_demand: int,
    total_updated: int,
) -> io.BytesIO:
    """Generates an executive Portrait A4 PDF for Pending Mobile Number Assessments."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#064E3B"),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4B5563"),
        alignment=1,
    )
    kpi_title_style = ParagraphStyle(
        "KPITitle",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#4B5563"),
        alignment=1,
    )
    kpi_val_style = ParagraphStyle(
        "KPIVal",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=colors.HexColor("#064E3B"),
        alignment=1,
    )
    th_style = ParagraphStyle(
        "TH",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    td_style = ParagraphStyle(
        "TD",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1F2937"),
    )
    td_center = ParagraphStyle(
        "TDC",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        alignment=1,
        textColor=colors.HexColor("#1F2937"),
    )

    story = []

    gp = metadata.get("gram_panchayat") or "Gram Panchayat"
    mandal = metadata.get("mandal") or "Mandal"
    district = metadata.get("district") or "District"

    story.append(Paragraph("TELANGANA PANCHAYAT RAJ &amp; RURAL DEVELOPMENT", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"PENDING MOBILE NUMBER ASSESSMENTS (LOOKUP) · {gp.upper()} GP, {mandal.upper()} MANDAL, {district.upper()} DISTRICT", subtitle_style))
    story.append(Spacer(1, 8))

    # KPI Summary Cards Table (Width: 136 + 137 + 137 + 137 = 547 pt)
    kpis = [
        [
            Paragraph("Demand Register Total", kpi_title_style),
            Paragraph("Mobile Updated", kpi_title_style),
            Paragraph("Pending Assessments", kpi_title_style),
            Paragraph("Coverage %", kpi_title_style),
        ],
        [
            Paragraph(f"{total_demand:,}", kpi_val_style),
            Paragraph(f"{total_updated:,}", ParagraphStyle("K1", parent=kpi_val_style, textColor=colors.HexColor("#15803D"))),
            Paragraph(f"{len(pending_records):,}", ParagraphStyle("K2", parent=kpi_val_style, textColor=colors.HexColor("#B91C1C"))),
            Paragraph(f"{round((total_updated / total_demand * 100), 1) if total_demand else 0.0}%", ParagraphStyle("K3", parent=kpi_val_style, textColor=colors.HexColor("#0D9488"))),
        ],
    ]
    t_kpis = Table(kpis, colWidths=[136, 137, 137, 137])
    t_kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 10))

    # Pending Records Table (Width: 32 + 95 + 250 + 95 + 75 = 547 pt)
    table_data = [[
        Paragraph("S.No", th_style),
        Paragraph("Assessment Number", th_style),
        Paragraph("Owner Name", th_style),
        Paragraph("House Number", th_style),
        Paragraph("Remarks", th_style),
    ]]

    if pending_records:
        for p in pending_records:
            rem_p = Paragraph("<font color='#B91C1C'><b>Pending</b></font>", td_center)
            table_data.append([
                Paragraph(str(p.get("sl_no", "")), td_center),
                Paragraph(str(p.get("assessment_number", "")), td_center),
                Paragraph(str(p.get("owner_name", "")), td_style),
                Paragraph(str(p.get("house_number", "")), td_center),
                rem_p,
            ])
    else:
        table_data.append([
            Paragraph("1", td_center),
            Paragraph("--", td_center),
            Paragraph("All assessments updated! 100% mobile number seeding achieved.", td_style),
            Paragraph("--", td_center),
            Paragraph("<font color='#15803D'><b>Complete</b></font>", td_center),
        ])

    col_widths = [32, 95, 250, 95, 75]
    t_records = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_records.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064E3B")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]))
    story.append(t_records)

    doc.build(story)
    buf.seek(0)
    return buf


_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def process_pending_mobile_assessments(
    demand_bytes: bytes,
    demand_filename: str,
    updated_bytes: bytes,
    updated_filename: str,
    owner_user_id: str = "",
) -> Dict[str, Any]:
    """
    Core entrypoint: orchestrates parsing, lookup anti-join, Excel and PDF deliverable generation,
    and caches the artifacts purely in-memory.
    """
    demand_records = parse_demand_register_bytes(demand_bytes, demand_filename)
    if not demand_records:
        raise ValueError(
            "Could not parse valid records from Demand Register. "
            "Please ensure you uploaded a valid e-Panchayat Demand Register (.xls or .xlsx)."
        )

    metadata, updated_asmt_set, asmt_to_mobile = parse_updated_report_bytes(updated_bytes)
    if not updated_asmt_set:
        raise ValueError(
            "Could not locate updated assessments in the Mobile Numbers Updated Report. "
            "Please ensure you uploaded the official e-Panchayat Mobile Numbers Updated Report (.xlsx)."
        )

    pending_records, full_reconciliation = perform_pending_lookup(
        demand_records=demand_records,
        updated_asmt_set=updated_asmt_set,
        asmt_to_mobile=asmt_to_mobile,
    )

    total_demand = len(demand_records)
    total_pending = len(pending_records)
    total_updated = total_demand - total_pending
    coverage_pct = round((total_updated / total_demand * 100), 1) if total_demand else 0.0

    excel_buf = generate_lookup_excel_workbook(
        metadata=metadata,
        pending_records=pending_records,
        full_reconciliation=full_reconciliation,
        total_demand=total_demand,
        total_updated=total_updated,
    )

    pdf_buf = generate_lookup_pdf_report(
        metadata=metadata,
        pending_records=pending_records,
        total_demand=total_demand,
        total_updated=total_updated,
    )

    job_id = uuid4().hex
    gp = metadata.get("gram_panchayat") or "GP"
    safe_gp = re.sub(r"[^A-Za-z0-9_-]", "_", gp).strip("_") or "Gram_Panchayat"
    date_str = time.strftime("%d_%m_%Y")

    excel_filename = f"{safe_gp}_Pending_Mobile_Assessments_{date_str}.xlsx"
    pdf_filename = f"{safe_gp}_Pending_Mobile_Assessments_{date_str}.pdf"

    job_entry = {
        "job_id": job_id,
        "owner_user_id": owner_user_id,
        "created_at": time.time(),
        "metadata": metadata,
        "total_demand": total_demand,
        "total_updated": total_updated,
        "total_pending": total_pending,
        "coverage_pct": coverage_pct,
        "excel_bytes": excel_buf.getvalue(),
        "excel_filename": excel_filename,
        "pdf_bytes": pdf_buf.getvalue(),
        "pdf_filename": pdf_filename,
        "pending_records": pending_records,
        "full_reconciliation": full_reconciliation,
    }

    with _LOCK:
        # Cleanup expired jobs older than 24 hours (86400s)
        now = time.time()
        expired = [k for k, v in _JOBS.items() if now - v.get("created_at", 0) > 86400]
        for exp_k in expired:
            _JOBS.pop(exp_k, None)
        _JOBS[job_id] = job_entry

    return {
        "success": True,
        "job_id": job_id,
        "token": job_id,
        "download_token": job_id,
        "total_demand": total_demand,
        "total_updated": total_updated,
        "total_pending": total_pending,
        "coverage_pct": coverage_pct,
        "metadata": metadata,
        "preview": pending_records,
        "total_preview_count": len(pending_records),
        "excel_download_url": f"/api/manual-reports/pending-mobile-assessments/download-excel?token={job_id}",
        "pdf_download_url": f"/api/manual-reports/pending-mobile-assessments/download-pdf?token={job_id}",
        "download_filenames": {
            "excel": excel_filename,
            "pdf": pdf_filename,
        },
    }


def get_job_entry(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        return _JOBS.get(job_id)


def get_job_artifact(job_id: str, kind: str) -> Tuple[str, bytes, str]:
    """
    Retrieves the generated artifact (excel or pdf) by job_id.
    Returns: (filename, file_bytes, mime_type)
    """
    entry = get_job_entry(job_id)
    if not entry:
        raise FileNotFoundError(
            "Report session has expired or is invalid. Please generate the pending list again."
        )

    kind_clean = (kind or "").strip().lower()
    if kind_clean in ("excel", "xlsx"):
        return (
            entry["excel_filename"],
            entry["excel_bytes"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif kind_clean in ("pdf",):
        return (
            entry["pdf_filename"],
            entry["pdf_bytes"],
            "application/pdf",
        )
    else:
        raise ValueError(f"Unsupported artifact kind: {kind}")


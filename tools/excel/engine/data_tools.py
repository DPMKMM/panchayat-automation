"""
Data Manipulation, Cleaning, Reshaping & Comparison Tools
Supports:
  - Combine & Compare (Merge, Compare, Compare Columns, Splitter, Split by Column, Combine Columns)
  - Clean Up (Data Cleaner, Remove/Find Duplicates, Remove Blank Rows, Remove Formatting, Text to Number, Find & Replace)
  - Sort & Reshape (Sort & Filter, Filter Rows, Text to Columns, Column Extractor, Data Extractor, Unpivot, Transpose, Date Converter, Column Letters, Row Shading)
"""

import os
import re
import csv
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter, column_index_from_string


def _load_sheet(src_path: str):
    wb = openpyxl.load_workbook(src_path)
    return wb, wb.active


# ==========================================
# 1. COMBINE & COMPARE
# ==========================================

def merge_workbooks(file_paths: List[str], dest_path: str, mode: str = "sheets") -> None:
    """
    mode='sheets': Each file becomes a sheet (or sheets are copied).
    mode='stack': Rows of same columns are stacked vertically.
    """
    wb_out = openpyxl.Workbook()
    wb_out.remove(wb_out.active)

    if mode == "stack":
        ws_out = wb_out.create_sheet(title="Merged_Data")
        header_written = False
        current_row = 1
        for fp in file_paths:
            wb_in = openpyxl.load_workbook(fp, data_only=True)
            for sheet in wb_in.worksheets:
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    continue
                start_idx = 0
                if not header_written:
                    ws_out.append([c if c is not None else "" for c in rows[0]])
                    header_written = True
                    start_idx = 1
                elif rows[0] == list(ws_out.iter_rows(values_only=True))[0]:
                    start_idx = 1 # Skip duplicate header

                for r in rows[start_idx:]:
                    if any(c is not None for c in r):
                        ws_out.append([c if c is not None else "" for c in r])
    else:
        # Each workbook gets its own sheet
        for f_idx, fp in enumerate(file_paths, 1):
            wb_in = openpyxl.load_workbook(fp, data_only=True)
            fname = Path(fp).stem[:20]
            for s_idx, sheet in enumerate(wb_in.worksheets):
                title = f"{fname}_{sheet.title}"[:31]
                ws_out = wb_out.create_sheet(title=title)
                for r in sheet.iter_rows(values_only=True):
                    ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def compare_workbooks(path1: str, path2: str, dest_path: str) -> Dict[str, Any]:
    """Compares two Excel files and generates a visual diff report with highlighted changes."""
    wb1 = openpyxl.load_workbook(path1, data_only=True)
    wb2 = openpyxl.load_workbook(path2, data_only=True)
    ws1 = wb1.active
    ws2 = wb2.active

    rows1 = list(ws1.iter_rows(values_only=True))
    rows2 = list(ws2.iter_rows(values_only=True))

    wb_diff = openpyxl.Workbook()
    ws_diff = wb_diff.active
    ws_diff.title = "Comparison_Diff"

    yellow_fill = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid") # Changed
    green_fill = PatternFill(start_color="BBF7D0", end_color="BBF7D0", fill_type="solid")  # Added in file 2
    red_fill = PatternFill(start_color="FECACA", end_color="FECACA", fill_type="solid")    # Missing in file 2

    max_r = max(len(rows1), len(rows2))
    max_c = max(max(len(r) for r in rows1) if rows1 else 0, max(len(r) for r in rows2) if rows2 else 0)

    diff_count = 0
    for r_idx in range(max_r):
        r1 = rows1[r_idx] if r_idx < len(rows1) else []
        r2 = rows2[r_idx] if r_idx < len(rows2) else []
        for c_idx in range(max_c):
            v1 = r1[c_idx] if c_idx < len(r1) else None
            v2 = r2[c_idx] if c_idx < len(r2) else None

            cell = ws_diff.cell(row=r_idx + 1, column=c_idx + 1)
            if v1 == v2:
                cell.value = v2
            else:
                diff_count += 1
                if v1 is None:
                    cell.value = f"[+]: {v2}"
                    cell.fill = green_fill
                elif v2 is None:
                    cell.value = f"[-]: {v1}"
                    cell.fill = red_fill
                else:
                    cell.value = f"{v1} -> {v2}"
                    cell.fill = yellow_fill

    wb_diff.save(dest_path)
    return {"differences_found": diff_count}


def compare_columns(src_path: str, dest_path: str, col1_idx: int = 1, col2_idx: int = 2) -> None:
    """Compares two columns in the same sheet and writes a match/diff status column."""
    wb, ws = _load_sheet(src_path)
    match_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    mismatch_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    out_col = ws.max_column + 1
    ws.cell(row=1, column=out_col, value="Comparison Status")
    for r in range(2, ws.max_row + 1):
        v1 = ws.cell(row=r, column=col1_idx).value
        v2 = ws.cell(row=r, column=col2_idx).value
        res_cell = ws.cell(row=r, column=out_col)
        if str(v1).strip() == str(v2).strip():
            res_cell.value = "Match"
            res_cell.fill = match_fill
        else:
            res_cell.value = "Mismatch"
            res_cell.fill = mismatch_fill
    wb.save(dest_path)


def split_workbook_sheets(src_path: str, output_zip_path: str) -> int:
    """Splits each sheet of a workbook into its own separate .xlsx file bundled in a .zip."""
    wb = openpyxl.load_workbook(src_path, data_only=True)
    tmp_dir = Path(output_zip_path).parent / f"split_{Path(src_path).stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    for sheet in wb.worksheets:
        new_wb = openpyxl.Workbook()
        new_ws = new_wb.active
        new_ws.title = sheet.title[:31]
        for r in sheet.iter_rows(values_only=True):
            new_ws.append([c if c is not None else "" for c in r])
        safe_name = re.sub(r'[:\\/?*\[\]]', '_', sheet.title)[:31]
        fpath = tmp_dir / f"{safe_name}.xlsx"
        new_wb.save(str(fpath))
        created_files.append(fpath)

    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in created_files:
            zf.write(f, arcname=f.name)
            os.remove(f)

    if tmp_dir.exists():
        tmp_dir.rmdir()

    return len(created_files)


def split_by_column(src_path: str, dest_path: str, col_idx: int = 1) -> None:
    """Splits rows into separate sheets based on the distinct values of a specified column."""
    wb = openpyxl.load_workbook(src_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.save(dest_path)
        return

    headers = rows[0]
    data_rows = rows[1:]

    groups = {}
    for r in data_rows:
        key = str(r[col_idx - 1] if col_idx - 1 < len(r) else "").strip() or "Uncategorized"
        groups.setdefault(key, []).append(r)

    wb_out = openpyxl.Workbook()
    wb_out.remove(wb_out.active)

    for key, r_list in groups.items():
        safe_sheet = re.sub(r'[:\\/?*\[\]]', '_', key)[:31]
        ws_out = wb_out.create_sheet(title=safe_sheet)
        ws_out.append(headers)
        for r in r_list:
            ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def combine_columns(src_path: str, dest_path: str, col_indices: List[int], separator: str = " ", new_col_name: str = "Combined") -> None:
    """Concatenates multiple columns into a new column."""
    wb, ws = _load_sheet(src_path)
    out_col = ws.max_column + 1
    ws.cell(row=1, column=out_col, value=new_col_name)

    for r in range(2, ws.max_row + 1):
        vals = [str(ws.cell(row=r, column=c).value or "") for c in col_indices]
        ws.cell(row=r, column=out_col, value=separator.join(filter(None, vals)))

    wb.save(dest_path)


# ==========================================
# 2. CLEAN UP
# ==========================================

def remove_duplicates(src_path: str, dest_path: str, subset_cols: Optional[List[int]] = None) -> int:
    """Removes duplicate rows from the active sheet."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.save(dest_path)
        return 0

    header = rows[0]
    seen = set()
    unique_rows = [header]
    duplicates_count = 0

    for r in rows[1:]:
        if subset_cols:
            key = tuple(r[c - 1] if c - 1 < len(r) else None for c in subset_cols)
        else:
            key = tuple(r)

        if key in seen:
            duplicates_count += 1
        else:
            seen.add(key)
            unique_rows.append(r)

    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title
    for r in unique_rows:
        ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)
    return duplicates_count


def find_duplicates(src_path: str, dest_path: str, col_idx: int = 1) -> int:
    """Highlights duplicate entries in a specific column in yellow without deleting them."""
    wb, ws = _load_sheet(src_path)
    yellow = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")

    counts = {}
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=col_idx).value or "").strip()
        if val:
            counts[val] = counts.get(val, 0) + 1

    dup_count = 0
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=col_idx).value or "").strip()
        if val and counts.get(val, 0) > 1:
            ws.cell(row=r, column=col_idx).fill = yellow
            dup_count += 1

    wb.save(dest_path)
    return dup_count


def remove_blank_rows(src_path: str, dest_path: str) -> int:
    """Removes all completely empty rows and blank trailing columns."""
    wb, ws = _load_sheet(src_path)
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title

    removed = 0
    for r in ws.iter_rows(values_only=True):
        if any(c is not None and str(c).strip() != "" for c in r):
            ws_out.append(list(r))
        else:
            removed += 1

    wb_out.save(dest_path)
    return removed


def remove_formatting(src_path: str, dest_path: str) -> None:
    """Strips all colors, fonts, borders, alignments, leaving plain raw tabular data."""
    wb = openpyxl.load_workbook(src_path, data_only=True)
    wb_out = openpyxl.Workbook()
    wb_out.remove(wb_out.active)

    for sheet in wb.worksheets:
        ws_out = wb_out.create_sheet(title=sheet.title)
        for r in sheet.iter_rows(values_only=True):
            ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def text_to_number(src_path: str, dest_path: str) -> int:
    """Converts numbers stored as text (e.g. '1234') into native numeric cells."""
    wb, ws = _load_sheet(src_path)
    converted = 0
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                s = cell.value.strip().replace(',', '')
                # Avoid converting phone numbers or postal codes with leading 0
                if s.startswith('0') and len(s) > 1 and not s.startswith('0.'):
                    continue
                try:
                    if '.' in s:
                        cell.value = float(s)
                        converted += 1
                    elif s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                        cell.value = int(s)
                        converted += 1
                except ValueError:
                    pass

    wb.save(dest_path)
    return converted


def find_and_replace(src_path: str, dest_path: str, find_val: str, replace_val: str) -> int:
    """Replaces all occurrences of a string across all cells."""
    wb = openpyxl.load_workbook(src_path)
    count = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and find_val in cell.value:
                    cell.value = cell.value.replace(find_val, replace_val)
                    count += 1
    wb.save(dest_path)
    return count


def data_cleaner(src_path: str, dest_path: str) -> None:
    """Trims whitespace, replaces tabs/newlines, strips non-printable control chars."""
    wb = openpyxl.load_workbook(src_path)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cell.value)
                    cell.value = cleaned.strip()
    wb.save(dest_path)


# ==========================================
# 3. SORT & RESHAPE
# ==========================================

def sort_and_filter(src_path: str, dest_path: str, sort_col_idx: int = 1, reverse: bool = False) -> None:
    """Sorts data rows by specified column index."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) <= 2:
        wb.save(dest_path)
        return

    header = rows[0]
    data = rows[1:]

    def sort_key(r):
        v = r[sort_col_idx - 1] if sort_col_idx - 1 < len(r) else None
        if v is None: return ""
        try: return float(v)
        except (ValueError, TypeError): return str(v).lower()

    data.sort(key=sort_key, reverse=reverse)

    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title
    ws_out.append(header)
    for r in data:
        ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def filter_rows(src_path: str, dest_path: str, col_idx: int = 1, condition: str = "contains", query: str = "") -> int:
    """Filters rows matching condition."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.save(dest_path)
        return 0

    header = rows[0]
    matched = [header]

    q_lower = query.lower()
    for r in rows[1:]:
        val = str(r[col_idx - 1] if col_idx - 1 < len(r) else "").strip().lower()
        keep = False
        if condition == "contains" and q_lower in val:
            keep = True
        elif condition == "equals" and val == q_lower:
            keep = True
        elif condition == "starts_with" and val.startswith(q_lower):
            keep = True
        elif condition == "not_empty" and val != "":
            keep = True

        if keep:
            matched.append(r)

    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title
    for r in matched:
        ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)
    return len(matched) - 1


def text_to_columns(src_path: str, dest_path: str, col_idx: int = 1, delimiter: str = ",") -> None:
    """Splits a single column by delimiter into multiple adjacent columns."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.save(dest_path)
        return

    new_rows = []
    for r in rows:
        r_list = list(r)
        val = str(r_list[col_idx - 1] if col_idx - 1 < len(r_list) else "")
        split_parts = val.split(delimiter)
        # Replace original cell with split parts
        expanded = r_list[:col_idx - 1] + split_parts + r_list[col_idx:]
        new_rows.append(expanded)

    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title
    for r in new_rows:
        ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def column_extractor(src_path: str, dest_path: str, keep_indices: List[int]) -> None:
    """Keeps only selected columns and removes everything else."""
    wb, ws = _load_sheet(src_path)
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title

    for r in ws.iter_rows(values_only=True):
        row_subset = [r[idx - 1] if idx - 1 < len(r) else "" for idx in keep_indices]
        ws_out.append(row_subset)

    wb_out.save(dest_path)


def transpose(src_path: str, dest_path: str) -> None:
    """Swaps rows and columns."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.save(dest_path)
        return

    transposed = list(zip(*rows))
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = ws.title
    for r in transposed:
        ws_out.append([c if c is not None else "" for c in r])

    wb_out.save(dest_path)


def unpivot(src_path: str, dest_path: str, id_cols: List[int], val_col_name: str = "Attribute", num_col_name: str = "Value") -> None:
    """Unpivots wide format into long format (key-value)."""
    wb, ws = _load_sheet(src_path)
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.save(dest_path)
        return

    header = rows[0]
    id_headers = [header[i - 1] for i in id_cols]
    pivot_cols = [i for i in range(len(header)) if (i + 1) not in id_cols]

    out_header = id_headers + [val_col_name, num_col_name]
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "Unpivoted"
    ws_out.append(out_header)

    for r in rows[1:]:
        ids = [r[i - 1] if i - 1 < len(r) else "" for i in id_cols]
        for p_idx in pivot_cols:
            attr_name = header[p_idx]
            attr_val = r[p_idx] if p_idx < len(r) else ""
            ws_out.append(ids + [attr_name, attr_val])

    wb_out.save(dest_path)


def row_shading(src_path: str, dest_path: str, hex_color: str = "F1F5F9") -> None:
    """Applies alternating zebra row shading for clean visual formatting."""
    wb, ws = _load_sheet(src_path)
    fill = PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
    for r_idx, row in enumerate(ws.iter_rows(min_row=2), 2):
        if r_idx % 2 == 0:
            for cell in row:
                cell.fill = fill
    wb.save(dest_path)


def date_converter(src_path: str, dest_path: str, col_idx: int = 1, out_format: str = "%Y-%m-%d") -> int:
    """Normalizes varied date formats into ISO standard YYYY-MM-DD."""
    import datetime
    wb, ws = _load_sheet(src_path)
    converted = 0
    common_formats = ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d"]

    for r in range(2, ws.max_row + 1):
        cell = ws.cell(row=r, column=col_idx)
        val = str(cell.value or "").strip()
        if not val: continue

        for fmt in common_formats:
            try:
                dt = datetime.datetime.strptime(val, fmt)
                cell.value = dt.strftime(out_format)
                converted += 1
                break
            except ValueError:
                continue

    wb.save(dest_path)
    return converted


def column_letters(query: str) -> str:
    """Helper: converts column number to Excel letter (e.g. 28 -> AB) or vice versa."""
    q = query.strip()
    if q.isdigit():
        return get_column_letter(int(q))
    else:
        return str(column_index_from_string(q.upper()))

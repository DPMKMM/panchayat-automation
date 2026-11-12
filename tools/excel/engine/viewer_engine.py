"""
In-Browser Spreadsheet Viewer & Editor Engine
Parses any spreadsheet format (XLSX, XLS, CSV, TSV, XLSB, ODS) into interactive JSON data.
Also handles saving edited data back into a valid .xlsx file.
"""

import os
import csv
import json
from pathlib import Path
from typing import Dict, Any, List

import openpyxl

try:
    import pyxlsb
    PYXLSB_AVAILABLE = True
except ImportError:
    PYXLSB_AVAILABLE = False


def load_file_for_viewer(file_path: str, max_rows: int = 500) -> Dict[str, Any]:
    """Parses any spreadsheet format (XLS, XLSX, CSV, TSV, XLSB, ODS, web HTML/XML) into grid JSON."""
    display_name = os.path.basename(file_path)
    ext = Path(file_path).suffix.lower()

    # CSV / TSV
    if ext in ('.csv', '.tsv', '.txt'):
        from tools.excel.converter_web import _read_text_auto
        delimiter = '\t' if ext == '.tsv' else ','
        rows = []
        text = _read_text_auto(file_path)
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        for idx, r in enumerate(reader):
            if idx >= max_rows:
                break
            rows.append([str(c) for c in r])
        return {
            "filename": display_name,
            "sheets": [{"name": "Data", "rows": rows, "total_rows": len(rows), "total_cols": max(len(r) for r in rows) if rows else 0}]
        }

    # XLSB
    if ext == '.xlsb' and PYXLSB_AVAILABLE:
        sheets_data = []
        with pyxlsb.open_workbook(file_path) as wb:
            for sname in wb.sheets:
                rows = []
                with wb.get_sheet(sname) as sheet:
                    for idx, row in enumerate(sheet):
                        if idx >= max_rows:
                            break
                        rows.append([str(c.v) if c.v is not None else "" for c in row])
                sheets_data.append({
                    "name": sname,
                    "rows": rows,
                    "total_rows": len(rows),
                    "total_cols": max(len(r) for r in rows) if rows else 0
                })
        return {"filename": display_name, "sheets": sheets_data}

    # Normalize .xls, web HTML/XML .xls, .ods, or extensionless mobile uploads to readable .xlsx
    from tools.excel.converter_web import normalize_to_xlsx
    load_path = normalize_to_xlsx(file_path, Path(file_path).parent, idx=99)

    wb = openpyxl.load_workbook(load_path, data_only=True)
    sheets_data = []
    for ws in wb.worksheets:
        rows = []
        for idx, r in enumerate(ws.iter_rows(values_only=True)):
            if idx >= max_rows:
                break
            rows.append([str(c) if c is not None else "" for c in r])
        sheets_data.append({
            "name": ws.title,
            "rows": rows,
            "total_rows": len(rows),
            "total_cols": max(len(r) for r in rows) if rows else 0
        })

    if load_path != file_path and os.path.exists(load_path):
        try:
            os.remove(load_path)
        except Exception:
            pass

    return {
        "filename": display_name,
        "sheets": sheets_data
    }


def save_edited_grid(sheets_data: List[Dict[str, Any]], dest_path: str) -> None:
    """Takes edited grid rows from the browser and saves them back to a standard .xlsx workbook."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for sheet in sheets_data:
        title = sheet.get("name", "Sheet")[:31]
        ws = wb.create_sheet(title=title)
        rows = sheet.get("rows", [])
        for r in rows:
            ws.append([c if c is not None else "" for c in r])

    wb.save(dest_path)

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
    """Parses any spreadsheet format and returns interactive grid JSON."""
    ext = Path(file_path).suffix.lower()

    # CSV / TSV
    if ext in ('.csv', '.tsv', '.txt'):
        delimiter = '\t' if ext == '.tsv' else ','
        rows = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f, delimiter=delimiter)
            for idx, r in enumerate(reader):
                if idx >= max_rows:
                    break
                rows.append([str(c) for c in r])
        return {
            "filename": os.path.basename(file_path),
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
        return {"filename": os.path.basename(file_path), "sheets": sheets_data}

    # For .xls (legacy / web table), if openpyxl fails, use PythonEngine / BeautifulSoup
    if ext == '.xls':
        from tools.excel.converter_web import detect_file_format, PythonEngine
        fmt = detect_file_format(file_path)
        tmp_xlsx = file_path + ".viewer_tmp.xlsx"
        try:
            PythonEngine.convert_file(file_path, tmp_xlsx)
            file_path = tmp_xlsx
        except Exception:
            pass

    # Standard XLSX / XLSM
    wb = openpyxl.load_workbook(file_path, data_only=True)
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

    # Clean up temp xlsx if created
    if os.path.exists(file_path) and file_path.endswith(".viewer_tmp.xlsx"):
        try: os.remove(file_path)
        except Exception: pass

    return {
        "filename": os.path.basename(file_path),
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

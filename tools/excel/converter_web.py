"""
Server-side conversion engine for Linux VPS and Windows servers.
Supports:
  - LibreOffice headless (standard on Linux VPS / Docker)
  - Windows Excel COM (if hosted on Windows Server with Office)
  - Pure Python engine (BeautifulSoup4 + openpyxl + xlrd)
"""

import os
import sys
import re
import csv
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict

# Detect available external tools
SOFFICE_BIN = shutil.which("libreoffice") or shutil.which("soffice")

# Openpyxl and BeautifulSoup
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from bs4 import BeautifulSoup

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False

try:
    import win32com.client
    import pythoncom
    EXCEL_COM_AVAILABLE = True
except ImportError:
    EXCEL_COM_AVAILABLE = False


def detect_file_format(file_path: str) -> str:
    """Detect whether file is HTML disguised as .xls, binary BIFF8, or XML."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 'empty'
        
    with open(file_path, 'rb') as f:
        header = f.read(2048)

    if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return 'biff8'

    text_sample = header.decode('utf-8', errors='ignore').strip().lower()

    if '<?xml' in text_sample and ('urn:schemas-microsoft-com:office:spreadsheet' in text_sample or '<workbook' in text_sample):
        return 'xml_ss'

    if any(tag in text_sample for tag in ['<html', '<table', '<tr', '<td', '<body', '<thead', '<!doctype html', '<div', '<style']):
        return 'html'

    if '\t' in text_sample or ',' in text_sample:
        return 'csv'

    return 'unknown'


class LibreOfficeEngine:
    """Uses headless LibreOffice on Linux VPS to convert files with 100% fidelity."""

    @classmethod
    def is_available(cls) -> bool:
        return SOFFICE_BIN is not None

    @classmethod
    def convert_file(cls, src_path: str, dest_path: str) -> None:
        if not cls.is_available():
            raise RuntimeError("LibreOffice binary not found on system PATH.")

        src_abs = os.path.abspath(src_path)
        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        os.makedirs(dest_dir, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_out:
            # libreoffice --headless --convert-to xlsx --outdir <tmp_out> <src_abs>
            cmd = [
                SOFFICE_BIN,
                "--headless",
                "--convert-to", "xlsx",
                "--outdir", tmp_out,
                src_abs
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if res.returncode != 0:
                raise RuntimeError(f"LibreOffice conversion failed: {res.stderr.decode('utf-8', errors='ignore')}")

            # Find generated .xlsx in tmp_out
            generated = list(Path(tmp_out).glob("*.xlsx"))
            if not generated:
                raise RuntimeError("LibreOffice completed but no .xlsx file was produced.")

            shutil.move(str(generated[0]), dest_path)


class PythonEngine:
    """Pure Python engine for fast, zero-dependency conversion."""

    @staticmethod
    def _parse_value(text: str) -> Any:
        if not text:
            return ""
        val = text.strip()
        if not val:
            return ""
        if val.startswith('0') and len(val) > 1 and not val.startswith('0.'):
            return val
        if val.isdigit() and len(val) > 15:
            return val
        if val.isdigit() or (val.startswith('-') and val[1:].isdigit()):
            try: return int(val)
            except ValueError: pass
        try:
            if re.match(r'^-?\d+(\.\d+)?$', val):
                return float(val)
        except ValueError:
            pass
        return val

    @classmethod
    def convert_html(cls, src_path: str, dest_path: str) -> None:
        content = ""
        for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'utf-16']:
            try:
                with open(src_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        soup = BeautifulSoup(content, 'html.parser')

        sheet_name = "Sheet1"
        name_match = re.search(r'<x:Name>([^<]+)</x:Name>', content, re.IGNORECASE)
        if name_match:
            sheet_name = re.sub(r'[:\\/?*\[\]]', '_', name_match.group(1).strip())[:31]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        tables = soup.find_all('table')
        if not tables:
            lines = [line.strip() for line in soup.get_text().splitlines() if line.strip()]
            for r_idx, line in enumerate(lines, 1):
                ws.cell(row=r_idx, column=1, value=line)
            wb.save(dest_path)
            return

        header_fill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="1F2937")
        body_font = Font(name="Segoe UI", size=10, color="111827")
        thin_border = Border(
            left=Side(style='thin', color="D1D5DB"),
            right=Side(style='thin', color="D1D5DB"),
            top=Side(style='thin', color="D1D5DB"),
            bottom=Side(style='thin', color="D1D5DB")
        )

        current_row = 1
        for table in tables:
            occupied = set()
            rows = table.find_all('tr')
            for tr in rows:
                col_idx = 1
                cells = tr.find_all(['td', 'th'])
                if not cells:
                    continue

                for cell in cells:
                    while (current_row, col_idx) in occupied:
                        col_idx += 1

                    rowspan = 1
                    colspan = 1
                    try: rowspan = max(1, int(cell.get('rowspan', 1)))
                    except (ValueError, TypeError): pass
                    try: colspan = max(1, int(cell.get('colspan', 1)))
                    except (ValueError, TypeError): pass

                    raw_text = cell.get_text(separator=" ", strip=True)
                    val = cls._parse_value(raw_text)

                    c = ws.cell(row=current_row, column=col_idx, value=val)
                    c.border = thin_border

                    is_header = cell.name == 'th' or tr.find_parent('thead') is not None
                    if is_header:
                        c.font = header_font
                        c.fill = header_fill
                        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    else:
                        c.font = body_font
                        c.alignment = Alignment(vertical="center")

                    for r_offset in range(rowspan):
                        for c_offset in range(colspan):
                            occupied.add((current_row + r_offset, col_idx + c_offset))

                    if rowspan > 1 or colspan > 1:
                        ws.merge_cells(
                            start_row=current_row,
                            start_column=col_idx,
                            end_row=current_row + rowspan - 1,
                            end_column=col_idx + colspan - 1
                        )

                    col_idx += colspan
                current_row += 1
            current_row += 2

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col[:100]:
                if cell.value:
                    val_str = str(cell.value)
                    if len(val_str) > max_len and len(val_str) < 60:
                        max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

        wb.save(dest_path)

    @classmethod
    def convert_biff8(cls, src_path: str, dest_path: str) -> None:
        if not XLRD_AVAILABLE:
            raise RuntimeError("xlrd library is required to read binary .xls")
        rb = xlrd.open_workbook(src_path)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        for sheet_idx in range(rb.nsheets):
            rs = rb.sheet_by_index(sheet_idx)
            safe_title = re.sub(r'[:\\/?*\[\]]', '_', rs.name)[:31]
            ws = wb.create_sheet(title=safe_title)
            for r in range(rs.nrows):
                row_vals = rs.row_values(r)
                for c, val in enumerate(row_vals):
                    ws.cell(row=r + 1, column=c + 1, value=val)

        wb.save(dest_path)

    @classmethod
    def convert_file(cls, src_path: str, dest_path: str) -> None:
        fmt = detect_file_format(src_path)
        if fmt == 'biff8':
            cls.convert_biff8(src_path, dest_path)
        else:
            cls.convert_html(src_path, dest_path)


def convert_file_universal(src_path: str, dest_path: str, engine_pref: str = "auto") -> Tuple[bool, str]:
    """
    Universal conversion function.
    Tries LibreOffice (Linux VPS) or Excel COM (Windows), falling back cleanly to PythonEngine.
    """
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(dest_dir, exist_ok=True)

    # 1. LibreOffice (Primary on Linux VPS)
    if engine_pref in ("auto", "libreoffice") and LibreOfficeEngine.is_available():
        try:
            LibreOfficeEngine.convert_file(src_path, dest_path)
            return True, "Converted with LibreOffice Engine"
        except Exception as e:
            if engine_pref == "libreoffice":
                return False, f"LibreOffice failed: {e}"

    # 2. Windows Excel COM (if hosted on Windows Server)
    if engine_pref in ("auto", "excel") and EXCEL_COM_AVAILABLE:
        try:
            pythoncom.CoInitialize()
            excel = win32com.client.DispatchEx('Excel.Application')
            excel.Visible = False
            excel.DisplayAlerts = False
            try:
                wb = excel.Workbooks.Open(os.path.abspath(src_path))
                wb.SaveAs(os.path.abspath(dest_path), 51)
                wb.Close(False)
                return True, "Converted with Excel COM Engine"
            finally:
                excel.Quit()
                pythoncom.CoUninitialize()
        except Exception as e:
            if engine_pref == "excel":
                return False, f"Excel COM failed: {e}"

    # 3. Pure Python Engine (Always available anywhere)
    try:
        PythonEngine.convert_file(src_path, dest_path)
        return True, "Converted with Python Engine"
    except Exception as e:
        return False, f"Python engine failed: {e}"

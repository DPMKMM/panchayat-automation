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
import zipfile
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict

# Detect available external tools
SOFFICE_BIN = shutil.which("libreoffice") or shutil.which("soffice")

# Openpyxl, BeautifulSoup, and safe XML parser
import openpyxl
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from bs4 import BeautifulSoup
import defusedxml.ElementTree as SafeET

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


def _sanitize_excel_value(val: Any) -> Any:
    """Strip illegal XML 1.0 control characters before writing into openpyxl cells."""
    if isinstance(val, str):
        return ILLEGAL_CHARACTERS_RE.sub("", val)
    return val


def _read_text_auto(file_path: str) -> str:
    """Read text file using BOM detection with multi-encoding fallback (UTF-16/UTF-8/CP1252)."""
    with open(file_path, 'rb') as f:
        raw = f.read()

    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            return raw.decode('utf-16')
        except UnicodeDecodeError:
            pass
    if raw.startswith(b'\xef\xbb\xbf'):
        try:
            return raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            pass

    for enc in ['utf-8', 'cp1252', 'latin-1', 'utf-16']:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='ignore')


def detect_file_format(file_path: str) -> str:
    """Detect spreadsheet container/content format via magic bytes and header inspection."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 'empty'

    with open(file_path, 'rb') as f:
        header = f.read(16384)

    if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return 'biff8'

    if header.startswith(b'%PDF-'):
        return 'pdf'

    if header.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'RIFF')):
        return 'image'

    if header.startswith((b'PK\x03\x04', b'PK\x05\x06')):
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, 'r') as zf:
                    names = {n.lower() for n in zf.namelist()}
                if 'xl/workbook.xml' in names or any(n.startswith('xl/') for n in names):
                    return 'xlsx'
                if 'content.xml' in names or 'mimetype' in names:
                    return 'ods'
        except zipfile.BadZipFile:
            pass

    if header.startswith((b'\xff\xfe', b'\xfe\xff')):
        text_sample = header.decode('utf-16', errors='ignore').strip().lower()
    else:
        text_sample = header.decode('utf-8', errors='ignore').strip().lower()

    if ('urn:schemas-microsoft-com:office:spreadsheet' in text_sample) or (
        '<workbook' in text_sample and ('<?xml' in text_sample or 'xmlns' in text_sample)
    ):
        return 'xml_ss'

    html_markers = (
        '<html', '<!doctype', '<table', '<tr', '<td', '<th',
        '<thead', '<tbody', '<body', 'urn:schemas-microsoft-com:office:excel',
    )
    if any(tag in text_sample for tag in html_markers):
        return 'html'

    first_lines = [ln for ln in text_sample.splitlines() if ln.strip()][:5]
    if first_lines:
        if any('\t' in ln for ln in first_lines):
            return 'tsv'
        if any(',' in ln for ln in first_lines):
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
        content = _read_text_auto(src_path)
        soup = BeautifulSoup(content, 'html.parser')

        sheet_name = "Sheet1"
        name_match = re.search(r'<x:Name>([^<]+)</x:Name>', content, re.IGNORECASE)
        if name_match:
            sheet_name = re.sub(r'[:\\/?*\[\]]', '_', name_match.group(1).strip())[:31] or "Sheet1"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        tables = soup.find_all('table')
        if not tables:
            lines = [line.strip() for line in soup.get_text().splitlines() if line.strip()]
            for r_idx, line in enumerate(lines, 1):
                ws.cell(row=r_idx, column=1, value=_sanitize_excel_value(line))
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
                    try:
                        rowspan = max(1, int(cell.get('rowspan', 1)))
                    except (ValueError, TypeError):
                        pass
                    try:
                        colspan = max(1, int(cell.get('colspan', 1)))
                    except (ValueError, TypeError):
                        pass

                    raw_text = cell.get_text(separator=" ", strip=True)
                    val = _sanitize_excel_value(cls._parse_value(raw_text))

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
                        try:
                            ws.merge_cells(
                                start_row=current_row,
                                start_column=col_idx,
                                end_row=current_row + rowspan - 1,
                                end_column=col_idx + colspan - 1
                            )
                        except ValueError:
                            pass

                    col_idx += colspan
                current_row += 1
            current_row += 2

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col[:100]:
                if cell.value:
                    val_str = str(cell.value)
                    if 0 < len(val_str) < 60 and len(val_str) > max_len:
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
            safe_title = re.sub(r'[:\\/?*\[\]]', '_', rs.name)[:31] or f"Sheet{sheet_idx + 1}"
            if safe_title in wb.sheetnames:
                safe_title = f"{safe_title[:25]}_{sheet_idx + 1}"
            ws = wb.create_sheet(title=safe_title)
            for r in range(rs.nrows):
                for c in range(rs.ncols):
                    cell_obj = rs.cell(r, c)
                    val = cell_obj.value
                    if cell_obj.ctype == xlrd.XL_CELL_DATE and isinstance(val, (int, float)):
                        try:
                            val = xlrd.xldate_as_datetime(val, rb.datemode)
                        except Exception:
                            pass
                    ws.cell(row=r + 1, column=c + 1, value=_sanitize_excel_value(val))

        if not wb.sheetnames:
            wb.create_sheet(title="Sheet1")
        wb.save(dest_path)

    @classmethod
    def convert_xlsx(cls, src_path: str, dest_path: str) -> None:
        """Load and normalize modern .xlsx/.xlsm workbooks safely without self-clobbering."""
        try:
            wb = openpyxl.load_workbook(src_path, data_only=False)
            tmp_out = dest_path + ".tmp.xlsx"
            wb.save(tmp_out)
            os.replace(tmp_out, dest_path)
            return
        except Exception:
            if os.path.abspath(src_path) != os.path.abspath(dest_path):
                shutil.copy2(src_path, dest_path)
                return
            raise

    @classmethod
    def convert_xml_spreadsheet(cls, src_path: str, dest_path: str) -> None:
        """Convert Excel 2003 XML SpreadsheetML (.xls/.xml) exports into .xlsx."""
        content = _read_text_auto(src_path)
        root = SafeET.fromstring(content.encode('utf-8', errors='ignore'))

        def _local_tag(el) -> str:
            return el.tag.split('}')[-1].lower() if isinstance(el.tag, str) else ''

        def _attr_ci(el, name: str) -> Optional[str]:
            lname = name.lower()
            for k, v in el.attrib.items():
                if k.split('}')[-1].lower() == lname:
                    return v
            return None

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        worksheets = [el for el in root.iter() if _local_tag(el) == 'worksheet']
        for idx, ws_el in enumerate(worksheets or [root]):
            raw_name = _attr_ci(ws_el, 'Name') or f"Sheet{idx + 1}"
            safe_title = re.sub(r'[:\\/?*\[\]]', '_', raw_name)[:31] or f"Sheet{idx + 1}"
            if safe_title in wb.sheetnames:
                safe_title = f"{safe_title[:25]}_{idx + 1}"
            ws = wb.create_sheet(title=safe_title)

            row_num = 1
            for row_el in [el for el in ws_el.iter() if _local_tag(el) == 'row']:
                r_idx_attr = _attr_ci(row_el, 'Index')
                if r_idx_attr and r_idx_attr.isdigit():
                    row_num = int(r_idx_attr)
                col_num = 1
                for cell_el in row_el:
                    if _local_tag(cell_el) != 'cell':
                        continue
                    c_idx_attr = _attr_ci(cell_el, 'Index')
                    if c_idx_attr and c_idx_attr.isdigit():
                        col_num = int(c_idx_attr)
                    data_el = next((ch for ch in cell_el if _local_tag(ch) == 'data'), None)
                    raw_text = (data_el.text if data_el is not None else cell_el.text) or ""
                    val = _sanitize_excel_value(cls._parse_value(raw_text))
                    ws.cell(row=row_num, column=col_num, value=val)
                    merge_across = _attr_ci(cell_el, 'MergeAcross')
                    col_num += 1 + (int(merge_across) if merge_across and merge_across.isdigit() else 0)
                row_num += 1

        if not wb.sheetnames:
            wb.create_sheet(title="Sheet1")
        wb.save(dest_path)

    @classmethod
    def convert_delimited(cls, src_path: str, dest_path: str, delimiter: str = ',') -> None:
        """Convert CSV/TSV text disguised as .xls into a clean multi-column .xlsx."""
        content = _read_text_auto(src_path)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        for r_idx, row in enumerate(reader, 1):
            for c_idx, cell_val in enumerate(row, 1):
                ws.cell(row=r_idx, column=c_idx, value=_sanitize_excel_value(cls._parse_value(cell_val)))
        wb.save(dest_path)

    @classmethod
    def convert_file(cls, src_path: str, dest_path: str) -> None:
        fmt = detect_file_format(src_path)
        if fmt == 'empty':
            raise ValueError("Uploaded file is empty (0 bytes).")
        if fmt == 'pdf':
            raise ValueError("Uploaded file is a PDF document, not an Excel spreadsheet.")
        if fmt == 'image':
            raise ValueError("Uploaded file is an image, not an Excel spreadsheet.")

        same_path = os.path.abspath(src_path) == os.path.abspath(dest_path)
        target = dest_path + ".conv_tmp.xlsx" if same_path else dest_path

        if fmt == 'xlsx':
            cls.convert_xlsx(src_path, target)
        elif fmt == 'biff8':
            cls.convert_biff8(src_path, target)
        elif fmt == 'xml_ss':
            cls.convert_xml_spreadsheet(src_path, target)
        elif fmt == 'tsv':
            cls.convert_delimited(src_path, target, delimiter='\t')
        elif fmt == 'csv':
            cls.convert_delimited(src_path, target, delimiter=',')
        else:
            cls.convert_html(src_path, target)

        if same_path and os.path.exists(target):
            os.replace(target, dest_path)


def convert_file_universal(src_path: str, dest_path: str, engine_pref: str = "auto") -> Tuple[bool, str]:
    """
    Universal conversion function.
    Handles legacy BIFF8 .xls, web HTML/XML/TSV/CSV .xls exports, and modern .xlsx files.
    """
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(dest_dir, exist_ok=True)

    fmt = detect_file_format(src_path)
    if fmt in ('empty', 'pdf', 'image'):
        reasons = {
            'empty': 'Uploaded file is empty (0 bytes).',
            'pdf': 'Uploaded file is a PDF document, not an Excel spreadsheet.',
            'image': 'Uploaded file is an image, not an Excel spreadsheet.',
        }
        return False, reasons[fmt]

    if fmt == 'xlsx' and engine_pref == "auto":
        try:
            PythonEngine.convert_xlsx(src_path, dest_path)
            return True, "Validated & converted modern .xlsx workbook"
        except Exception:
            pass

    # 1. LibreOffice (Primary on Linux VPS for .xls / .ods)
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


def normalize_to_xlsx(src_path: str, work_dir: Path, idx: int = 0) -> str:
    """Ensure any spreadsheet input (.xls, web HTML/XML .xls, .csv/.tsv, .xlsx) is a valid .xlsx path."""
    fmt = detect_file_format(src_path)
    if fmt == 'xlsx':
        return src_path
    out_xlsx = work_dir / f"__norm_{idx}.xlsx"
    if fmt == 'ods':
        from tools.excel.engine import formats_converter
        formats_converter.ods_to_excel(src_path, str(out_xlsx))
        return str(out_xlsx)
    ok, msg = convert_file_universal(src_path, str(out_xlsx))
    if not ok:
        raise ValueError(msg)
    return str(out_xlsx)

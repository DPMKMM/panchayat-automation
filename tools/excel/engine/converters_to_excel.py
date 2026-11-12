"""
Converters TO Excel (.xlsx)
Supports: Word, PDF, XML, TXT, JSON, CSV, TSV, HTML, Markdown, SQL, YAML, Image
"""

import os
import re
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Dict

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Word
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# PDF
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# YAML
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# BeautifulSoup
from bs4 import BeautifulSoup


def _style_header_row(ws, row_idx=1, bg_color="2563EB", text_color="FFFFFF"):
    fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
    font = Font(name="Segoe UI", size=10, bold=True, color=text_color)
    thin = Side(style='thin', color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for cell in ws[row_idx]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border


def _autofit_columns(ws, max_cols=30):
    for col in ws.iter_cols(max_col=max_cols):
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col[:100]:
            if cell.value is not None:
                s = str(cell.value)
                if len(s) > max_len and len(s) < 80:
                    max_len = len(s)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 11)


def word_to_excel(src_path: str, dest_path: str) -> None:
    """Extracts tables and structured paragraphs from Word (.docx) to Excel."""
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not installed.")
    doc = docx.Document(src_path)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    if not doc.tables:
        ws = wb.create_sheet(title="Document Text")
        r = 1
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                ws.cell(row=r, column=1, value=text)
                r += 1
        _autofit_columns(ws)
        wb.save(dest_path)
        return

    for t_idx, table in enumerate(doc.tables):
        sheet_name = f"Table_{t_idx + 1}"[:31]
        ws = wb.create_sheet(title=sheet_name)
        for r_idx, row in enumerate(table.rows, 1):
            for c_idx, cell in enumerate(row.cells, 1):
                ws.cell(row=r_idx, column=c_idx, value=cell.text.strip())
        _style_header_row(ws, 1)
        _autofit_columns(ws)

    wb.save(dest_path)


def pdf_to_excel(src_path: str, dest_path: str) -> None:
    """Extracts text lines and tabular data from PDF pages into Excel."""
    if not PYPDF_AVAILABLE:
        raise RuntimeError("pypdf is not installed.")
    reader = pypdf.PdfReader(src_path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF Data"

    current_row = 1
    for p_num, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Check if line looks like space/tab-separated table
            parts = re.split(r'\t+|\s{2,}', line)
            if len(parts) > 1:
                for c_idx, part in enumerate(parts, 1):
                    ws.cell(row=current_row, column=c_idx, value=part.strip())
            else:
                ws.cell(row=current_row, column=1, value=line)
            current_row += 1

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def xml_to_excel(src_path: str, dest_path: str) -> None:
    """Parses XML nodes into tabular rows in Excel."""
    tree = ET.parse(src_path)
    root = tree.getroot()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = root.tag[:31]

    # Find repetitive child elements
    records = []
    headers = []

    # If root has children with subchildren, treats each child as a record
    children = list(root)
    if children and any(len(c) > 0 for c in children):
        for c in children:
            row_dict = {}
            for sub in c:
                row_dict[sub.tag] = sub.text.strip() if sub.text else ""
                if sub.tag not in headers:
                    headers.append(sub.tag)
            records.append(row_dict)
    else:
        # Flat list or attributes
        for c in children:
            row_dict = c.attrib.copy()
            if c.text and c.text.strip():
                row_dict[c.tag] = c.text.strip()
            for k in row_dict.keys():
                if k not in headers:
                    headers.append(k)
            records.append(row_dict)

    if not headers:
        headers = ["Element", "Text", "Attributes"]
        ws.append(headers)
        for elem in root.iter():
            ws.append([elem.tag, elem.text.strip() if elem.text else "", str(elem.attrib)])
    else:
        ws.append(headers)
        for r in records:
            ws.append([r.get(h, "") for h in headers])

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def txt_to_excel(src_path: str, dest_path: str, delimiter: str = None) -> None:
    """Converts delimited or plain text into Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Text Data"

    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(4096)
        f.seek(0)
        if not delimiter:
            if '\t' in sample: delimiter = '\t'
            elif '|' in sample: delimiter = '|'
            elif ';' in sample: delimiter = ';'
            elif ',' in sample: delimiter = ','
            else: delimiter = None

        if delimiter:
            reader = csv.reader(f, delimiter=delimiter)
            for r_idx, row in enumerate(reader, 1):
                for c_idx, val in enumerate(row, 1):
                    ws.cell(row=r_idx, column=c_idx, value=val.strip())
        else:
            for r_idx, line in enumerate(f, 1):
                ws.cell(row=r_idx, column=1, value=line.strip())

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def json_to_excel(src_path: str, dest_path: str) -> None:
    """Flattens JSON array or object hierarchy into Excel table."""
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "JSON Data"

    if isinstance(data, dict):
        # Could be a wrapper object containing a list, or a single dictionary
        list_keys = [k for k, v in data.items() if isinstance(v, list)]
        if list_keys:
            data = data[list_keys[0]]
        else:
            data = [data]

    if isinstance(data, list) and data and isinstance(data[0], dict):
        # Collect all unique keys
        headers = []
        for item in data:
            if isinstance(item, dict):
                for k in item.keys():
                    if k not in headers:
                        headers.append(k)
        ws.append(headers)
        for item in data:
            if isinstance(item, dict):
                row = [str(item.get(h, "")) if isinstance(item.get(h), (dict, list)) else item.get(h, "") for h in headers]
                ws.append(row)
            else:
                ws.append([item])
    elif isinstance(data, list):
        ws.append(["Value"])
        for v in data:
            ws.append([str(v)])
    else:
        ws.append(["Key", "Value"])
        ws.append(["Data", str(data)])

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def csv_to_excel(src_path: str, dest_path: str) -> None:
    txt_to_excel(src_path, dest_path, delimiter=',')


def tsv_to_excel(src_path: str, dest_path: str) -> None:
    txt_to_excel(src_path, dest_path, delimiter='\t')


def markdown_to_excel(src_path: str, dest_path: str) -> None:
    """Parses Markdown tables into Excel rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Markdown Table"

    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    current_row = 1
    in_table = False
    for line in lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            # Ignore markdown separator line like |---|---|
            if re.match(r'^\|[\s\-:|]+\|$', line):
                continue
            parts = [p.strip() for p in line[1:-1].split('|')]
            for c_idx, val in enumerate(parts, 1):
                ws.cell(row=current_row, column=c_idx, value=val)
            current_row += 1
            in_table = True
        elif line:
            if not in_table:
                ws.cell(row=current_row, column=1, value=line)
                current_row += 1

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def sql_to_excel(src_path: str, dest_path: str) -> None:
    """Parses SQL INSERT statements into an Excel table."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SQL Data"

    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Match INSERT INTO table (col1, col2) VALUES (val1, val2)
    inserts = re.findall(r'INSERT\s+INTO\s+[`"\'\w]+\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)', content, re.IGNORECASE)
    if inserts:
        headers = [c.strip().strip('`"\' ') for c in inserts[0][0].split(',')]
        ws.append(headers)
        for _, val_str in inserts:
            vals = [v.strip().strip("'\" ") for v in val_str.split(',')]
            ws.append(vals)
    else:
        # Match VALUES only: VALUES (a, b, c), (d, e, f)
        val_rows = re.findall(r'\(([^)]+)\)', content)
        for r_idx, v_str in enumerate(val_rows, 1):
            vals = [v.strip().strip("'\" ") for v in v_str.split(',')]
            for c_idx, val in enumerate(vals, 1):
                ws.cell(row=r_idx, column=c_idx, value=val)

    _style_header_row(ws, 1)
    _autofit_columns(ws)
    wb.save(dest_path)


def yaml_to_excel(src_path: str, dest_path: str) -> None:
    """Converts YAML file to Excel."""
    if not YAML_AVAILABLE:
        raise RuntimeError("pyyaml is not installed.")
    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = yaml.safe_load(f)

    # Re-use json logic
    tmp_json = dest_path + ".tmp.json"
    with open(tmp_json, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    json_to_excel(tmp_json, dest_path)
    if os.path.exists(tmp_json):
        os.remove(tmp_json)


def image_to_excel(src_path: str, dest_path: str) -> None:
    """Embeds an image into an Excel workbook sheet."""
    from openpyxl.drawing.image import Image as OpenpyxlImage
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Image"
    ws.cell(row=1, column=1, value="Embedded Image Source:")
    ws.cell(row=1, column=2, value=os.path.basename(src_path))
    img = OpenpyxlImage(src_path)
    ws.add_image(img, "B3")
    wb.save(dest_path)

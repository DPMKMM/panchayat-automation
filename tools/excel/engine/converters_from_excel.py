"""
Converters FROM Excel (.xlsx / .xls)
Supports: Word, PDF, ICS, CSV, JSON, Image, Markdown, XML, HTML, SQL, vCard, LaTeX, YAML, TSV
"""

import os
import re
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any

import openpyxl
from PIL import Image, ImageDraw, ImageFont

# Word
try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# YAML
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# ReportLab for PDF
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _read_sheet_rows(src_path: str) -> List[List[Any]]:
    """Reads all rows from active sheet of xlsx."""
    wb = openpyxl.load_workbook(src_path, data_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(values_only=True):
        if any(c is not None for c in r):
            rows.append([str(c) if c is not None else "" for c in r])
    return rows


def excel_to_word(src_path: str, dest_path: str) -> None:
    """Exports Excel sheet into a formatted Word (.docx) table."""
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not installed.")

    rows = _read_sheet_rows(src_path)
    if not rows:
        rows = [["Empty Table"]]

    doc = docx.Document()
    title_p = doc.add_heading(Path(src_path).stem.replace('_', ' ').title(), level=1)
    
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = 'Table Grid'

    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = str(val)
            if r_idx == 0:
                # Header styling
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    doc.save(dest_path)


def excel_to_pdf(src_path: str, dest_path: str) -> None:
    """Exports Excel sheet to a formatted PDF table."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab is not installed.")

    rows = _read_sheet_rows(src_path)
    if not rows:
        rows = [["Empty Table"]]

    # Cap columns to fit PDF page width
    max_cols = min(len(rows[0]), 12)
    trimmed_rows = [r[:max_cols] for r in rows[:150]] # max 150 rows per page limit

    doc = SimpleDocTemplate(dest_path, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph(f"<b>{Path(src_path).stem}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    t = Table(trimmed_rows, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(t)
    doc.build(elements)


def excel_to_csv(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    with open(dest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def excel_to_tsv(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    with open(dest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(rows)


def excel_to_json(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    if not rows:
        data = []
    elif len(rows) == 1:
        data = [{"column": val} for val in rows[0]]
    else:
        headers = [h or f"Column_{i+1}" for i, h in enumerate(rows[0])]
        data = []
        for r in rows[1:]:
            item = {}
            for i, h in enumerate(headers):
                item[h] = r[i] if i < len(r) else ""
            data.append(item)

    with open(dest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def excel_to_yaml(src_path: str, dest_path: str) -> None:
    if not YAML_AVAILABLE:
        raise RuntimeError("pyyaml is not installed.")
    tmp_json = dest_path + ".tmp.json"
    excel_to_json(src_path, tmp_json)
    with open(tmp_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    with open(dest_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, sort_keys=False)
    if os.path.exists(tmp_json):
        os.remove(tmp_json)


def excel_to_markdown(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    if not rows:
        content = "| Empty |\n|---|\n"
    else:
        header = "| " + " | ".join(rows[0]) + " |\n"
        separator = "| " + " | ".join(["---"] * len(rows[0])) + " |\n"
        body = "".join(["| " + " | ".join(r) + " |\n" for r in rows[1:]])
        content = header + separator + body

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)


def excel_to_html(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    html_lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 2rem; background: #f8fafc; }",
        "table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }",
        "th { background: #2563eb; color: white; font-weight: 600; text-align: left; padding: 12px 16px; border: 1px solid #cbd5e1; }",
        "td { padding: 10px 16px; border: 1px solid #e2e8f0; color: #1e293b; }",
        "tr:nth-child(even) { background: #f8fafc; }",
        "tr:hover { background: #f1f5f9; }",
        "</style></head><body>",
        f"<h2>{Path(src_path).stem}</h2>",
        "<table>"
    ]
    if rows:
        html_lines.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in rows[0]) + "</tr></thead><tbody>")
        for r in rows[1:]:
            html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
        html_lines.append("</tbody>")
    html_lines.append("</table></body></html>")

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_lines))


def excel_to_xml(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    root = ET.Element("Workbook")
    if rows:
        headers = [re.sub(r'\W+', '_', h) or f"Col_{i+1}" for i, h in enumerate(rows[0])]
        table_node = ET.SubElement(root, "Table")
        for r in rows[1:]:
            row_node = ET.SubElement(table_node, "Row")
            for i, val in enumerate(r):
                tag = headers[i] if i < len(headers) else f"Col_{i+1}"
                col_node = ET.SubElement(row_node, tag)
                col_node.text = str(val)

    tree = ET.ElementTree(root)
    tree.write(dest_path, encoding='utf-8', xml_declaration=True)


def excel_to_sql(src_path: str, dest_path: str, table_name: str = None) -> None:
    rows = _read_sheet_rows(src_path)
    t_name = table_name or re.sub(r'\W+', '_', Path(src_path).stem) or "my_table"

    lines = []
    if not rows:
        lines.append(f"-- Empty table: {t_name}")
    else:
        headers = [re.sub(r'\W+', '_', h) or f"col_{i+1}" for i, h in enumerate(rows[0])]
        cols_def = ", ".join(f"`{h}` TEXT" for h in headers)
        lines.append(f"CREATE TABLE IF NOT EXISTS `{t_name}` ({cols_def});\n")

        for r in rows[1:]:
            vals = []
            for v in r:
                escaped = str(v).replace("'", "''")
                vals.append(f"'{escaped}'")
            cols_str = ", ".join(f"`{h}`" for h in headers)
            vals_str = ", ".join(vals)
            lines.append(f"INSERT INTO `{t_name}` ({cols_str}) VALUES ({vals_str});")

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def excel_to_latex(src_path: str, dest_path: str) -> None:
    rows = _read_sheet_rows(src_path)
    if not rows:
        content = "% Empty table"
    else:
        num_cols = len(rows[0])
        col_align = " | ".join(["l"] * num_cols)
        lines = [
            "\\begin{table}[h!]",
            "\\centering",
            f"\\begin{{tabular}}{{| {col_align} |}}",
            "\\hline"
        ]
        # Escape special latex chars
        def esc(s):
            return re.sub(r'([&%$#_{}~^\\])', r'\\\1', str(s))

        lines.append(" & ".join(esc(c) for c in rows[0]) + " \\\\ \\hline")
        for r in rows[1:]:
            lines.append(" & ".join(esc(c) for c in r) + " \\\\")
        lines.append("\\hline")
        lines.append("\\end{tabular}")
        lines.append(f"\\caption{{{Path(src_path).stem}}}")
        lines.append("\\end{table}")
        content = "\n".join(lines)

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)


def excel_to_vcard(src_path: str, dest_path: str) -> None:
    """Converts rows with name, phone, email into standard .vcf vCards."""
    rows = _read_sheet_rows(src_path)
    if not rows or len(rows) < 2:
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write("")
        return

    headers = [h.lower() for h in rows[0]]
    # Map column indices
    name_idx = next((i for i, h in enumerate(headers) if 'name' in h), 0)
    phone_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ['phone', 'mobile', 'cell', 'tel'])), None)
    email_idx = next((i for i, h in enumerate(headers) if 'email' in h or 'mail' in h), None)
    org_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ['org', 'company', 'office', 'mandal', 'district'])), None)

    vcards = []
    for r in rows[1:]:
        name = r[name_idx] if name_idx < len(r) else "Contact"
        phone = r[phone_idx] if (phone_idx is not None and phone_idx < len(r)) else ""
        email = r[email_idx] if (email_idx is not None and email_idx < len(r)) else ""
        org = r[org_idx] if (org_idx is not None and org_idx < len(r)) else ""

        vc = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}", f"N:{name};;;;"]
        if phone: vc.append(f"TEL;TYPE=CELL:{phone}")
        if email: vc.append(f"EMAIL:{email}")
        if org: vc.append(f"ORG:{org}")
        vc.append("END:VCARD")
        vcards.append("\n".join(vc))

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(vcards))


def excel_to_ics(src_path: str, dest_path: str) -> None:
    """Converts rows with dates/events into standard iCalendar (.ics) format."""
    rows = _read_sheet_rows(src_path)
    if not rows or len(rows) < 2:
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
        return

    headers = [h.lower() for h in rows[0]]
    date_idx = next((i for i, h in enumerate(headers) if 'date' in h or 'time' in h or 'day' in h), 0)
    summary_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ['event', 'title', 'summary', 'name', 'status'])), 1 if len(headers) > 1 else 0)

    events = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Excel Web Suite//Calendar Exporter//EN"
    ]
    import datetime
    today_str = datetime.datetime.now().strftime("%Y%m%d")

    for idx, r in enumerate(rows[1:], 1):
        dt_val = re.sub(r'\D', '', str(r[date_idx]))[:8] if date_idx < len(r) else today_str
        if len(dt_val) < 8:
            dt_val = today_str
        summary = str(r[summary_idx]) if summary_idx < len(r) else f"Event {idx}"

        events.extend([
            "BEGIN:VEVENT",
            f"UID:event-{idx}-{today_str}@excelsuite.local",
            f"DTSTAMP:{today_str}T090000Z",
            f"DTSTART;VALUE=DATE:{dt_val}",
            f"SUMMARY:{summary}",
            "END:VEVENT"
        ])
    events.append("END:VCALENDAR")

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(events))


def excel_to_image(src_path: str, dest_path: str) -> None:
    """Renders Excel sheet to a high-contrast clean table PNG image."""
    rows = _read_sheet_rows(src_path)[:60] # max 60 rows preview
    if not rows:
        rows = [["Empty Table"]]

    # Calculate dimensions
    num_cols = min(len(rows[0]), 10)
    col_width = 160
    row_height = 36
    img_w = num_cols * col_width + 40
    img_h = (len(rows) + 1) * row_height + 40

    img = Image.new("RGB", (img_w, img_h), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Header background
    draw.rectangle([20, 20, img_w - 20, 20 + row_height], fill="#2563EB")

    y = 20
    for r_idx, row in enumerate(rows):
        is_header = r_idx == 0
        bg = "#2563EB" if is_header else ("#F8FAFC" if r_idx % 2 == 0 else "#FFFFFF")
        if not is_header:
            draw.rectangle([20, y, img_w - 20, y + row_height], fill=bg)

        # Draw cell texts and column gridlines
        x = 20
        for c_idx in range(num_cols):
            val = str(row[c_idx]) if c_idx < len(row) else ""
            if len(val) > 18:
                val = val[:16] + ".."
            text_color = "#FFFFFF" if is_header else "#1E293B"
            draw.text((x + 8, y + 10), val, fill=text_color)
            draw.line([(x, y), (x, y + row_height)], fill="#CBD5E1", width=1)
            x += col_width

        draw.line([(img_w - 20, y), (img_w - 20, y + row_height)], fill="#CBD5E1", width=1)
        draw.line([(20, y), (img_w - 20, y)], fill="#CBD5E1", width=1)
        y += row_height

    draw.line([(20, y), (img_w - 20, y)], fill="#CBD5E1", width=1)
    img.save(dest_path, "PNG")

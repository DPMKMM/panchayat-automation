"""PDF, Consolidated Excel, and CSV report generators for GM-R 39.1 Inspections."""

from __future__ import annotations

import csv
import html
import io
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.branding import apply_openpyxl_branding
from inspections.models import InspectionReport


def _safe_xml(text: Any) -> str:
    return html.escape("" if text is None else str(text))


def generate_inspections_pdf(report: InspectionReport, output_path: str | Path) -> Path:
    """Create executive A4 Landscape PDF strictly matching: Sl No | Mandal/Division/District | Target | Completed | Balance | % Completed."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = landscape(A4)
    margin = 12 * mm
    avail_w = page_w - 2 * margin

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InspTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=14, leading=17, alignment=TA_CENTER, textColor=HexColor("#17365D"), spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="InspSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11.5, alignment=TA_CENTER, textColor=HexColor("#334155"), spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="InspHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=10.5, alignment=TA_CENTER, textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="InspHdrLeft", parent=styles["InspHdr"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="InspCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.3, leading=10.5, alignment=TA_CENTER, textColor=HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name="InspCellLeft", parent=styles["InspCell"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="InspNote", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.8, leading=10, textColor=HexColor("#475569"),
    ))

    def _footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#B7C9D6"))
        canvas.line(margin, 9 * mm, page_w - margin, 9 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#475569"))
        canvas.drawString(
            margin,
            5 * mm,
            f"{report.district_name} District | GM-R 39.1 {report.designation} Inspections ({report.group_label}-wise) | {report.generated_time_str} | e-Panchayat Automation",
        )
        canvas.drawRightString(page_w - margin, 5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    headers = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
    col_widths = [
        18 * mm,
        avail_w - (18 + 30 + 32 + 30 + 36) * mm,
        30 * mm,
        32 * mm,
        30 * mm,
        36 * mm,
    ]

    table_data: list[list[Any]] = [[
        Paragraph(_safe_xml(h), styles["InspHdrLeft"] if idx == 1 else styles["InspHdr"])
        for idx, h in enumerate(headers)
    ]]

    if not report.abstract_rows:
        table_data.append([
            Paragraph("-", styles["InspCell"]),
            Paragraph("No submitted inspection records found for the selected designation and week range.", styles["InspCellLeft"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0.00%", styles["InspCell"]),
        ])
    else:
        for row in report.abstract_rows:
            bal_html = (
                f'<font color="#C00000"><b>{row.balance:,}</b></font>'
                if row.balance > 0
                else '<font color="#047857"><b>0</b></font>'
            )
            pct_color = "#047857" if row.pct_completed >= 100.0 else ("#B45309" if row.pct_completed >= 50.0 else "#C00000")
            table_data.append([
                Paragraph(str(row.serial), styles["InspCell"]),
                Paragraph(_safe_xml(row.unit_name), styles["InspCellLeft"]),
                Paragraph(f"{row.target:,}", styles["InspCell"]),
                Paragraph(f"<b>{row.completed:,}</b>", styles["InspCell"]),
                Paragraph(bal_html, styles["InspCell"]),
                Paragraph(f'<font color="{pct_color}"><b>{row.pct_completed:.2f}%</b></font>', styles["InspCell"]),
            ])

    # Total Summary Row
    table_data.append([
        Paragraph("", styles["InspCell"]),
        Paragraph("<b>TOTAL</b>", styles["InspCellLeft"]),
        Paragraph(f"<b>{report.total_target:,}</b>", styles["InspCell"]),
        Paragraph(f"<b>{report.total_completed:,}</b>", styles["InspCell"]),
        Paragraph(f"<b>{report.total_balance:,}</b>", styles["InspCell"]),
        Paragraph(f"<b>{report.total_pct_completed:.2f}%</b>", styles["InspCell"]),
    ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F4E78")),
        ("GRID", (0, 0), (-1, -1), 0.45, HexColor("#94A3B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, HexColor("#EAF2F8")]),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D9EAF7")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.0, HexColor("#1F4E78")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))

    period_str = (
        f"{report.from_week} to {report.to_week}"
        if report.from_week != report.to_week
        else report.from_week
    )
    story = [
        Paragraph(
            f"{_safe_xml(report.district_name.upper())} DISTRICT — GRAM PANCHAYAT INSPECTIONS ABSTRACT REPORT (GM-R 39.1)",
            styles["InspTitle"],
        ),
        Paragraph(
            f"Officer Designation: <b>{_safe_xml(report.designation_title)}</b> | "
            f"Grouping: <b>{_safe_xml(report.group_label)}-wise</b> | "
            f"Weeks: <b>{_safe_xml(period_str)}</b> ({len(report.weeks_selected)} Week(s))<br/>"
            f"Target Rule: <b>{_safe_xml(report.target_rule_desc)}</b> | "
            f"Filter: <b>Final Submit Status = Submitted Only</b> | Generated: {_safe_xml(report.generated_time_str)}",
            styles["InspSubtitle"],
        ),
        tbl,
        Spacer(1, 8),
        Paragraph(
            f"Audit Summary: Consolidated {len(report.weeks_selected)} week(s) | "
            f"Raw Records Scanned: {report.raw_row_count:,} | "
            f"Submitted Considered: {report.submitted_row_count:,} | "
            f"Non-Submitted Excluded: {report.excluded_non_submitted_count:,}",
            styles["InspNote"],
        ),
    ]

    doc = SimpleDocTemplate(
        str(out),
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=14 * mm,
        title=f"{report.district_name} District {report.designation} GP Inspections Abstract Report",
        author="e-Panchayat Automation",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return out


def generate_inspections_excel(report: InspectionReport, output_path: str | Path) -> Path:
    """Create multi-sheet branded Excel workbook (Abstract + Submitted Inspections Data)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inspection Abstract"

    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    tot_fill = PatternFill("solid", fgColor="D9EAF7")
    alt_fill = PatternFill("solid", fgColor="EAF2F8")

    ws.merge_cells("A1:F1")
    ws["A1"] = f"{report.district_name.upper()} DISTRICT - GRAM PANCHAYAT INSPECTIONS ABSTRACT (GM-R 39.1)"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="17365D")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    period_str = (
        f"{report.from_week} to {report.to_week}"
        if report.from_week != report.to_week
        else report.from_week
    )
    ws.merge_cells("A2:F2")
    ws["A2"] = (
        f"Designation: {report.designation} | {report.target_rule_desc} | "
        f"Weeks: {period_str} | Final Submit Status: Submitted Only"
    )
    ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="334155")
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    headers = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
    ws.append([])  # row 3 blank spacer
    ws.append(headers)  # row 4 header
    for col_idx in range(1, 7):
        cell = ws.cell(row=4, column=col_idx)
        cell.fill = hdr_fill
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="left" if col_idx == 2 else "center", vertical="center")
        cell.border = border

    row_cursor = 5
    for r in report.abstract_rows:
        ws.append([r.serial, r.unit_name, r.target, r.completed, r.balance, r.pct_completed])
        for col_idx in range(1, 7):
            c = ws.cell(row=row_cursor, column=col_idx)
            c.border = border
            c.font = Font(name="Calibri", size=10)
            c.alignment = Alignment(horizontal="left" if col_idx == 2 else "center", vertical="center")
            if (row_cursor - 5) % 2 == 1:
                c.fill = alt_fill
            if col_idx == 6:
                c.number_format = '0.00"%"'
        row_cursor += 1

    ws.append(["", "TOTAL", report.total_target, report.total_completed, report.total_balance, report.total_pct_completed])
    for col_idx in range(1, 7):
        c = ws.cell(row=row_cursor, column=col_idx)
        c.fill = tot_fill
        c.border = border
        c.font = Font(name="Calibri", size=10, bold=True, color="0F172A")
        c.alignment = Alignment(horizontal="left" if col_idx == 2 else "center", vertical="center")
        if col_idx == 6:
            c.number_format = '0.00"%"'

    col_widths = {"A": 9, "B": 30, "C": 14, "D": 14, "E": 14, "F": 16}
    for letter, width in col_widths.items():
        ws.column_dimensions[letter].width = width

    # Sheet 2: Consolidated Submitted Inspection Records
    ws_data = wb.create_sheet("Submitted Inspections Data")
    data_headers = [
        "Sl No", "Week", "Designation", "District", "Division",
        "Mandal", "Gram Panchayat", "Inspecting Officer", "Inspection Date", "Final Submit Status",
    ]
    ws_data.append(data_headers)
    for col_idx in range(1, len(data_headers) + 1):
        c = ws_data.cell(row=1, column=col_idx)
        c.fill = hdr_fill
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border

    for idx, rec in enumerate(report.submitted_records, start=1):
        ws_data.append([
            idx,
            rec.week_label,
            rec.designation,
            rec.district_name,
            rec.division_name,
            rec.mandal_name,
            rec.gp_name,
            rec.officer_name,
            rec.inspection_date,
            rec.final_submit_status,
        ])
    for col in ws_data.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws_data.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 36)

    apply_openpyxl_branding(wb)
    wb.save(str(out))
    return out


def generate_inspections_csv(report: InspectionReport) -> bytes:
    """Export abstract table as UTF-8 CSV matching exact requested columns."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"])
    for r in report.abstract_rows:
        writer.writerow([r.serial, r.unit_name, r.target, r.completed, r.balance, f"{r.pct_completed:.2f}"])
    writer.writerow(["", "TOTAL", report.total_target, report.total_completed, report.total_balance, f"{report.total_pct_completed:.2f}"])
    return buf.getvalue().encode("utf-8-sig")

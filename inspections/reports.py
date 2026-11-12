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
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.branding import apply_openpyxl_branding
from inspections.models import InspectionReport, format_month_range_from_weeks


def _safe_xml(text: Any) -> str:
    return html.escape("" if text is None else str(text))


def _format_district_title(district_name: str) -> str:
    clean = (district_name or "District").strip()
    if "district" in clean.lower():
        return clean
    return f"{clean} District"


def _format_period_label(from_week: str, to_week: str) -> str:
    f_w = (from_week or "").strip()
    t_w = (to_week or "").strip()
    if not f_w:
        return t_w
    if not t_w or f_w == t_w:
        return f_w
    return f"{f_w}  ->  {t_w}"


def _tier_hex(pct: float) -> str:
    if pct >= 100.0:
        return "#059669"
    if pct >= 60.0:
        return "#0284C7"
    if pct >= 35.0:
        return "#D97706"
    return "#DC2626"


def _make_insp_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InspBannerTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=12.2, leading=14.5, alignment=TA_CENTER, textColor=colors.white, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="InspBannerSub", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.0, leading=10.5, alignment=TA_CENTER, textColor=HexColor("#FDE68A"),
    ))
    styles.add(ParagraphStyle(
        name="InspMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.0, leading=11.5, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="InspHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.0, leading=10, alignment=TA_CENTER, textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="InspHdrLeft", parent=styles["InspHdr"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="InspCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.0, leading=10, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="InspCellLeft", parent=styles["InspCell"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="InspKpiLbl", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=6.8, leading=8.5, alignment=TA_CENTER, textColor=HexColor("#475569"),
    ))
    styles.add(ParagraphStyle(
        name="InspKpiVal", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=11.5, leading=13.5, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="InspNote", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.5, leading=10, textColor=HexColor("#475569"),
    ))
    styles.add(ParagraphStyle(
        name="InspSecHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9.6, leading=12.0, alignment=TA_LEFT, textColor=colors.white,
    ))
    return styles


def _build_kpi_strip_table(report: InspectionReport, avail_w: float, styles: Any) -> Table:
    plural_lbl = "MANDALS" if report.group_label == "Mandal" else ("DIVISIONS" if report.group_label == "Division" else "DISTRICTS")
    pct_hex = _tier_hex(report.total_pct_completed)
    kpi_w = avail_w / 5.0
    kpi_tbl = Table(
        [[
            [Paragraph(f"TOTAL {plural_lbl}", styles["InspKpiLbl"]), Paragraph(f'<font color="#1E3A8A"><b>{len(report.abstract_rows)}</b></font>', styles["InspKpiVal"])],
            [Paragraph("TOTAL TARGET", styles["InspKpiLbl"]), Paragraph(f'<font color="#0F172A"><b>{report.total_target:,}</b></font>', styles["InspKpiVal"])],
            [Paragraph("COMPLETED", styles["InspKpiLbl"]), Paragraph(f'<font color="#059669"><b>{report.total_completed:,}</b></font>', styles["InspKpiVal"])],
            [Paragraph("BALANCE PENDING", styles["InspKpiLbl"]), Paragraph(f'<font color="#DC2626"><b>{report.total_balance:,}</b></font>', styles["InspKpiVal"])],
            [Paragraph("% COMPLETED", styles["InspKpiLbl"]), Paragraph(f'<font color="{pct_hex}"><b>{report.total_pct_completed:.2f}%</b></font>', styles["InspKpiVal"])],
        ]],
        colWidths=[kpi_w] * 5,
    )
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor("#EEF2FF")),
        ("LINEABOVE", (0, 0), (0, 0), 2.2, HexColor("#3B82F6")),
        ("BACKGROUND", (1, 0), (1, 0), HexColor("#F8FAFC")),
        ("LINEABOVE", (1, 0), (1, 0), 2.2, HexColor("#64748B")),
        ("BACKGROUND", (2, 0), (2, 0), HexColor("#ECFDF5")),
        ("LINEABOVE", (2, 0), (2, 0), 2.2, HexColor("#10B981")),
        ("BACKGROUND", (3, 0), (3, 0), HexColor("#FEF2F2")),
        ("LINEABOVE", (3, 0), (3, 0), 2.2, HexColor("#EF4444")),
        ("BACKGROUND", (4, 0), (4, 0), HexColor("#F0F9FF")),
        ("LINEABOVE", (4, 0), (4, 0), 2.2, HexColor("#0284C7")),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return kpi_tbl


def _build_unit_abstract_table(
    rows: list[Any],
    total_target: int,
    total_completed: int,
    total_balance: int,
    total_pct_completed: float,
    group_label: str,
    total_label: str,
    avail_w: float,
    styles: Any,
) -> Table:
    headers = ["Sl No", group_label, "Target", "Completed", "Balance", "% Completed"]
    col_widths = [
        14 * mm,
        avail_w - (14 + 24 + 26 + 24 + 28) * mm,
        24 * mm,
        26 * mm,
        24 * mm,
        28 * mm,
    ]
    table_data: list[list[Any]] = [[
        Paragraph(_safe_xml(h), styles["InspHdrLeft"] if idx == 1 else styles["InspHdr"])
        for idx, h in enumerate(headers)
    ]]
    if not rows:
        table_data.append([
            Paragraph("-", styles["InspCell"]),
            Paragraph("No submitted inspection records found for the selected criteria.", styles["InspCellLeft"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph('<font color="#DC2626"><b>0.00%</b></font>', styles["InspCell"]),
        ])
    else:
        for row in rows:
            bal_html = (
                f'<font color="#DC2626"><b>{row.balance:,}</b></font>'
                if row.balance > 0
                else '<font color="#059669"><b>0</b></font>'
            )
            pct_hex = _tier_hex(row.pct_completed)
            table_data.append([
                Paragraph(str(row.serial), styles["InspCell"]),
                Paragraph(f"<b>{_safe_xml(row.unit_name)}</b>", styles["InspCellLeft"]),
                Paragraph(f"{row.target:,}", styles["InspCell"]),
                Paragraph(f'<font color="#065F46"><b>{row.completed:,}</b></font>', styles["InspCell"]),
                Paragraph(bal_html, styles["InspCell"]),
                Paragraph(f'<font color="{pct_hex}"><b>{row.pct_completed:.2f}%</b></font>', styles["InspCell"]),
            ])

    tot_pct_hex = _tier_hex(total_pct_completed)
    table_data.append([
        Paragraph("", styles["InspCell"]),
        Paragraph(f"<b>{_safe_xml(total_label)}</b>", styles["InspCellLeft"]),
        Paragraph(f"<b>{total_target:,}</b>", styles["InspCell"]),
        Paragraph(f'<font color="#065F46"><b>{total_completed:,}</b></font>', styles["InspCell"]),
        Paragraph(f'<font color="#991B1B"><b>{total_balance:,}</b></font>', styles["InspCell"]),
        Paragraph(f'<font color="{tot_pct_hex}"><b>{total_pct_completed:.2f}%</b></font>', styles["InspCell"]),
    ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F4C5C")),
        ("GRID", (0, 0), (-1, -1), 0.45, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, HexColor("#F0F9FF")]),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D1FAE5")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, HexColor("#064E3B")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    return tbl


def generate_inspections_pdf(report: InspectionReport, output_path: str | Path) -> Path:
    """Create colorful Portrait A4 PDF matching: Sl No | Mandal/Division/District | Target | Completed | Balance | % Completed."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    margin = 10 * mm
    avail_w = page_w - 2 * margin
    styles = _make_insp_styles()

    dist_heading = _format_district_title(report.district_name)
    period_str = _format_period_label(report.from_week, report.to_week)
    month_range = format_month_range_from_weeks(report.from_week, report.to_week)

    def _footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#10B981"))
        canvas.setLineWidth(0.75)
        canvas.line(margin, 9 * mm, page_w - margin, 9 * mm)
        canvas.setFont("Helvetica", 7.3)
        canvas.setFillColor(HexColor("#475569"))
        canvas.drawString(
            margin,
            5 * mm,
            f"{dist_heading} | {report.designation} Inspections | Report Generated On: {report.generated_time_str} | Panchayat-Automation",
        )
        canvas.drawRightString(page_w - margin, 5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    banner_tbl = Table(
        [
            [Paragraph(f"{_safe_xml(dist_heading.upper())} — {report.designation}s GRAM PANCHAYAT INSPECTIONS ABSTRACT REPORT", styles["InspBannerTitle"])],
        ],
        colWidths=[avail_w],
    )
    banner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#064E3B")),
        ("LINEBELOW", (0, 0), (-1, 0), 2.5, HexColor("#F59E0B")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    month_line = f"Period: <b>{_safe_xml(month_range)}</b> | " if month_range else ""
    meta_tbl = Table(
        [[
            Paragraph(
                f"{month_line}Weeks: <b>{_safe_xml(period_str)}</b> ({len(report.weeks_selected)} Week(s))<br/>"
                f"<b>{_safe_xml(report.target_rule_desc)}</b> | "
                f"Report Generated On: <b>{_safe_xml(report.generated_time_str)}</b>",
                styles["InspMeta"],
            )
        ]],
        colWidths=[avail_w],
    )
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ECFDF5")),
        ("BOX", (0, 0), (-1, -1), 0.75, HexColor("#6EE7B7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    kpi_tbl = _build_kpi_strip_table(report, avail_w, styles)
    tbl = _build_unit_abstract_table(
        rows=report.abstract_rows,
        total_target=report.total_target,
        total_completed=report.total_completed,
        total_balance=report.total_balance,
        total_pct_completed=report.total_pct_completed,
        group_label=report.group_label,
        total_label="TOTAL",
        avail_w=avail_w,
        styles=styles,
    )

    story: list[Any] = [
        banner_tbl,
        Spacer(1, 5),
        meta_tbl,
        Spacer(1, 6),
        kpi_tbl,
        Spacer(1, 7),
        tbl,
    ]

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=13 * mm,
        title=f"{dist_heading} {report.designation} GP Inspections Abstract Report",
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

    dist_heading = _format_district_title(report.district_name)
    ws.merge_cells("A1:F1")
    ws["A1"] = f"{dist_heading.upper()} - {report.designation}s GRAM PANCHAYAT INSPECTIONS ABSTRACT"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="17365D")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    period_str = _format_period_label(report.from_week, report.to_week)
    month_range = format_month_range_from_weeks(report.from_week, report.to_week)
    month_part = f"Period: {month_range} | " if month_range else ""
    ws.merge_cells("A2:F2")
    ws["A2"] = (
        f"Designation: {report.designation} | {month_part}{report.target_rule_desc} | "
        f"Weeks: {period_str} | Report Generated On: {report.generated_time_str}"
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
        "Mandal", "Gram Panchayat", "Panchayat ID", "Date of Inspection",
        "Attendance Date-Time", "Checklist Status", "Inspecting Officer / Note", "Final Submit Status",
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
            rec.panchayat_id,
            rec.inspection_date,
            rec.attendance_datetime,
            rec.checklist_entered,
            rec.officer_name,
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


def generate_monthwise_inspections_pdf(report: InspectionReport, output_path: str | Path) -> Path:
    """Create colorful Portrait A4 PDF with Consolidated Report page + Month-Wise Summary + Per-Month Abstracts (no bars)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    margin = 10 * mm
    avail_w = page_w - 2 * margin
    styles = _make_insp_styles()

    dist_heading = _format_district_title(report.district_name)
    period_str = _format_period_label(report.from_week, report.to_week)
    month_range = format_month_range_from_weeks(report.from_week, report.to_week)
    sections = list(report.monthly_sections or [])

    def _footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#10B981"))
        canvas.setLineWidth(0.75)
        canvas.line(margin, 9 * mm, page_w - margin, 9 * mm)
        canvas.setFont("Helvetica", 7.3)
        canvas.setFillColor(HexColor("#475569"))
        canvas.drawString(
            margin,
            5 * mm,
            f"{dist_heading} | {report.designation} Consolidated & Month-Wise Report | Report Generated On: {report.generated_time_str} | Panchayat-Automation",
        )
        canvas.drawRightString(page_w - margin, 5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    # Page 1: Consolidated Abstract Report Page
    cons_banner_tbl = Table(
        [
            [Paragraph(f"{_safe_xml(dist_heading.upper())} — {report.designation}s CONSOLIDATED GP INSPECTIONS ABSTRACT REPORT", styles["InspBannerTitle"])],
        ],
        colWidths=[avail_w],
    )
    cons_banner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#064E3B")),
        ("LINEBELOW", (0, 0), (-1, 0), 2.5, HexColor("#F59E0B")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    month_line = f"Period: <b>{_safe_xml(month_range)}</b> | " if month_range else ""
    cons_meta_tbl = Table(
        [[
            Paragraph(
                f"{month_line}Weeks: <b>{_safe_xml(period_str)}</b> ({len(report.weeks_selected)} Week(s))<br/>"
                f"<b>{_safe_xml(report.target_rule_desc)}</b> | "
                f"Report Generated On: <b>{_safe_xml(report.generated_time_str)}</b>",
                styles["InspMeta"],
            )
        ]],
        colWidths=[avail_w],
    )
    cons_meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ECFDF5")),
        ("BOX", (0, 0), (-1, -1), 0.75, HexColor("#6EE7B7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    cons_kpi_tbl = _build_kpi_strip_table(report, avail_w, styles)
    cons_unit_tbl = _build_unit_abstract_table(
        rows=report.abstract_rows,
        total_target=report.total_target,
        total_completed=report.total_completed,
        total_balance=report.total_balance,
        total_pct_completed=report.total_pct_completed,
        group_label=report.group_label,
        total_label="CONSOLIDATED TOTAL",
        avail_w=avail_w,
        styles=styles,
    )

    story: list[Any] = [
        cons_banner_tbl,
        Spacer(1, 5),
        cons_meta_tbl,
        Spacer(1, 6),
        cons_kpi_tbl,
        Spacer(1, 7),
        cons_unit_tbl,
    ]

    # Page 2: Month-Wise Summary Page (Monday-Start Week Allocation Rules)
    story.append(PageBreak())
    mw_banner_tbl = Table(
        [
            [Paragraph(f"{_safe_xml(dist_heading.upper())} — {report.designation}s MONTH-WISE INSPECTIONS SUMMARY", styles["InspBannerTitle"])],
            [Paragraph(f"{_safe_xml(report.designation_title)}  •  Monday-Start Week Allocation", styles["InspBannerSub"])],
        ],
        colWidths=[avail_w],
    )
    mw_banner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#1E3A8A")),
        ("LINEBELOW", (0, 1), (-1, 1), 2.5, HexColor("#F59E0B")),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))

    mw_meta_tbl = Table(
        [[
            Paragraph(
                f"Period: <b>{_safe_xml(month_range or 'Selected Period')}</b> | "
                f"Months: <b>{len(sections)}</b> | Total Weeks: <b>{len(report.weeks_selected)}</b> | "
                f"Report Generated On: <b>{_safe_xml(report.generated_time_str)}</b><br/>"
                "Week Allocation Rule: First Monday starts month; each Mon–Sun week is assigned strictly to its Monday's month.",
                styles["InspMeta"],
            )
        ]],
        colWidths=[avail_w],
    )
    mw_meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 0.75, HexColor("#93C5FD")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))

    sum_col_w = [
        10 * mm,
        21 * mm,
        13 * mm,
        avail_w - (10 + 21 + 13 + 18 + 20 + 20 + 18 + 24) * mm,
        18 * mm,
        20 * mm,
        20 * mm,
        18 * mm,
        24 * mm,
    ]
    sum_headers = ["Sl No", "Month", "Weeks", "Monday-Allocated Weeks", "Unit Tgt", "Target", "Completed", "Balance", "% Completed"]
    sum_rows: list[list[Any]] = [[
        Paragraph(_safe_xml(h), styles["InspHdrLeft"] if idx in (1, 3) else styles["InspHdr"])
        for idx, h in enumerate(sum_headers)
    ]]

    if not sections:
        sum_rows.append([
            Paragraph("-", styles["InspCell"]),
            Paragraph("-", styles["InspCellLeft"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("No monthly week data available.", styles["InspCellLeft"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph("0", styles["InspCell"]),
            Paragraph('<font color="#DC2626"><b>0.00%</b></font>', styles["InspCell"]),
        ])
    else:
        for idx, sec in enumerate(sections, start=1):
            weeks_desc = f"{sec.weeks_included[0]} -> {sec.weeks_included[-1]}" if len(sec.weeks_included) > 1 else (sec.weeks_included[0] if sec.weeks_included else "-")
            sec_pct_hex = _tier_hex(sec.total_pct_completed)
            sum_rows.append([
                Paragraph(str(idx), styles["InspCell"]),
                Paragraph(f"<b>{_safe_xml(sec.month_label)}</b>", styles["InspCellLeft"]),
                Paragraph(str(sec.week_count), styles["InspCell"]),
                Paragraph(_safe_xml(weeks_desc), styles["InspCellLeft"]),
                Paragraph(f"{sec.target_per_unit:,}", styles["InspCell"]),
                Paragraph(f"{sec.total_target:,}", styles["InspCell"]),
                Paragraph(f'<font color="#065F46"><b>{sec.total_completed:,}</b></font>', styles["InspCell"]),
                Paragraph(f'<font color="{"#DC2626" if sec.total_balance > 0 else "#059669"}"><b>{sec.total_balance:,}</b></font>', styles["InspCell"]),
                Paragraph(f'<font color="{sec_pct_hex}"><b>{sec.total_pct_completed:.2f}%</b></font>', styles["InspCell"]),
            ])
        sum_tot_t = sum(s.total_target for s in sections)
        sum_tot_c = sum(s.total_completed for s in sections)
        sum_tot_b = sum(s.total_balance for s in sections)
        sum_tot_p = round((sum_tot_c / sum_tot_t) * 100.0, 2) if sum_tot_t > 0 else 0.0
        sum_tot_hex = _tier_hex(sum_tot_p)
        sum_rows.append([
            Paragraph("", styles["InspCell"]),
            Paragraph("<b>TOTAL</b>", styles["InspCellLeft"]),
            Paragraph(f"<b>{sum(s.week_count for s in sections)}</b>", styles["InspCell"]),
            Paragraph("All Selected Months", styles["InspCellLeft"]),
            Paragraph("-", styles["InspCell"]),
            Paragraph(f"<b>{sum_tot_t:,}</b>", styles["InspCell"]),
            Paragraph(f'<font color="#065F46"><b>{sum_tot_c:,}</b></font>', styles["InspCell"]),
            Paragraph(f'<font color="#991B1B"><b>{sum_tot_b:,}</b></font>', styles["InspCell"]),
            Paragraph(f'<font color="{sum_tot_hex}"><b>{sum_tot_p:.2f}%</b></font>', styles["InspCell"]),
        ])

    sum_tbl = Table(sum_rows, colWidths=sum_col_w, repeatRows=1, hAlign="LEFT", splitByRow=1)
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F4C5C")),
        ("GRID", (0, 0), (-1, -1), 0.45, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, HexColor("#F0F9FF")]),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D1FAE5")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.1, HexColor("#064E3B")),
    ]))

    story.extend([mw_banner_tbl, Spacer(1, 5), mw_meta_tbl, Spacer(1, 6), sum_tbl])

    # Pages 3+: Individual Month Breakdown Pages
    for sec in sections:
        story.append(PageBreak())
        sec_hdr_tbl = Table(
            [[
                Paragraph(
                    f"{_safe_xml(sec.month_label)} — {_safe_xml(sec.target_rule_desc)}<br/>"
                    f"Weeks ({sec.week_count}): {_safe_xml(', '.join(sec.weeks_included))}",
                    styles["InspSecHdr"],
                )
            ]],
            colWidths=[avail_w],
        )
        sec_hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#1E3A8A")),
            ("LINEBELOW", (0, 0), (-1, -1), 2.2, HexColor("#F59E0B")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))

        u_tbl = _build_unit_abstract_table(
            rows=sec.abstract_rows,
            total_target=sec.total_target,
            total_completed=sec.total_completed,
            total_balance=sec.total_balance,
            total_pct_completed=sec.total_pct_completed,
            group_label=report.group_label,
            total_label=f"TOTAL ({sec.month_label})",
            avail_w=avail_w,
            styles=styles,
        )
        story.extend([sec_hdr_tbl, Spacer(1, 6), u_tbl])

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=13 * mm,
        title=f"{dist_heading} {report.designation} Consolidated & Month-Wise GP Inspections Report",
        author="e-Panchayat Automation",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return out


def generate_monthwise_inspections_excel(report: InspectionReport, output_path: str | Path) -> Path:
    """Create multi-sheet Month-Wise Inspection Workbook using strict Monday-start week rules."""
    from inspections.models import assign_week_to_month, format_month_key_label

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Month-Wise Summary"

    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor="0F4C5C")
    tot_fill = PatternFill("solid", fgColor="D1FAE5")
    alt_fill = PatternFill("solid", fgColor="F0F9FF")

    dist_heading = _format_district_title(report.district_name)
    month_range = format_month_range_from_weeks(report.from_week, report.to_week)
    sections = list(report.monthly_sections or [])

    ws.merge_cells("A1:I1")
    ws["A1"] = f"{dist_heading.upper()} - {report.designation}s MONTH-WISE GRAM PANCHAYAT INSPECTIONS ABSTRACT"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="064E3B")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:I2")
    ws["A2"] = (
        f"Designation: {report.designation} | Period: {month_range or 'Selected'} | "
        f"Monday-Start Week Allocation | Report Generated On: {report.generated_time_str}"
    )
    ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="334155")
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    sum_headers = [
        "Sl No", "Month", "Weeks Count", "Monday-Allocated Weeks",
        "Target / Unit", "Total Target", "Completed", "Balance", "% Completed",
    ]
    ws.append([])
    ws.append(sum_headers)
    for col_idx in range(1, 10):
        c = ws.cell(row=4, column=col_idx)
        c.fill = hdr_fill
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="left" if col_idx in (2, 4) else "center", vertical="center")
        c.border = border

    r_cur = 5
    for idx, sec in enumerate(sections, start=1):
        ws.append([
            idx,
            sec.month_label,
            sec.week_count,
            ", ".join(sec.weeks_included),
            sec.target_per_unit,
            sec.total_target,
            sec.total_completed,
            sec.total_balance,
            sec.total_pct_completed,
        ])
        for col_idx in range(1, 10):
            c = ws.cell(row=r_cur, column=col_idx)
            c.border = border
            c.font = Font(name="Calibri", size=10)
            c.alignment = Alignment(horizontal="left" if col_idx in (2, 4) else "center", vertical="center")
            if idx % 2 == 0:
                c.fill = alt_fill
            if col_idx == 9:
                c.number_format = '0.00"%"'
        r_cur += 1

    tot_w = sum(s.week_count for s in sections)
    tot_t = sum(s.total_target for s in sections)
    tot_c = sum(s.total_completed for s in sections)
    tot_b = sum(s.total_balance for s in sections)
    tot_p = round((tot_c / tot_t) * 100.0, 2) if tot_t > 0 else 0.0
    ws.append(["", "TOTAL", tot_w, "All Selected Months", "", tot_t, tot_c, tot_b, tot_p])
    for col_idx in range(1, 10):
        c = ws.cell(row=r_cur, column=col_idx)
        c.fill = tot_fill
        c.border = border
        c.font = Font(name="Calibri", size=10, bold=True, color="0F172A")
        c.alignment = Alignment(horizontal="left" if col_idx in (2, 4) else "center", vertical="center")
        if col_idx == 9:
            c.number_format = '0.00"%"'

    for letter, width in {"A": 8, "B": 14, "C": 13, "D": 48, "E": 13, "F": 13, "G": 13, "H": 13, "I": 14}.items():
        ws.column_dimensions[letter].width = width

    # Sheet 2: Consolidated Abstract (All Selected Weeks Combined)
    ws_cons = wb.create_sheet("Consolidated Abstract")
    ws_cons.merge_cells("A1:F1")
    ws_cons["A1"] = f"{dist_heading.upper()} - CONSOLIDATED ABSTRACT ({report.target_rule_desc})"
    ws_cons["A1"].font = Font(name="Calibri", size=12, bold=True, color="064E3B")
    ws_cons["A2"] = f"Period: {month_range or 'Selected'} | Weeks: {_format_period_label(report.from_week, report.to_week)} | Report Generated On: {report.generated_time_str}"
    ws_cons.append([])
    c_hdrs = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
    ws_cons.append(c_hdrs)
    for col_idx in range(1, 7):
        c = ws_cons.cell(row=4, column=col_idx)
        c.fill = hdr_fill
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c.border = border
    for r in report.abstract_rows:
        ws_cons.append([r.serial, r.unit_name, r.target, r.completed, r.balance, r.pct_completed])
    ws_cons.append(["", "CONSOLIDATED TOTAL", report.total_target, report.total_completed, report.total_balance, report.total_pct_completed])
    for letter, width in {"A": 8, "B": 28, "C": 12, "D": 13, "E": 12, "F": 14}.items():
        ws_cons.column_dimensions[letter].width = width

    # Sheet 3: Unit x Month Comparison Matrix
    ws_mx = wb.create_sheet("Unit x Month Matrix")
    mx_hdrs = ["Sl No", report.group_label]
    for sec in sections:
        mx_hdrs.extend([f"{sec.month_label} Tgt", f"{sec.month_label} Comp"])
    mx_hdrs.extend(["Total Target", "Total Completed", "Balance", "% Completed"])
    ws_mx.append(mx_hdrs)
    for col_idx in range(1, len(mx_hdrs) + 1):
        c = ws_mx.cell(row=1, column=col_idx)
        c.fill = hdr_fill
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="left" if col_idx == 2 else "center", vertical="center")
        c.border = border

    sec_maps = [{r.unit_name.casefold(): r for r in sec.abstract_rows} for sec in sections]
    for idx, base_row in enumerate(report.abstract_rows, start=1):
        ukey = base_row.unit_name.casefold()
        row_vals: list[Any] = [idx, base_row.unit_name]
        for smap in sec_maps:
            mr = smap.get(ukey)
            row_vals.extend([mr.target if mr else 0, mr.completed if mr else 0])
        row_vals.extend([base_row.target, base_row.completed, base_row.balance, base_row.pct_completed])
        ws_mx.append(row_vals)

    for col in ws_mx.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws_mx.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 11), 32)

    # Individual Per-Month Abstract Sheets
    for sec in sections:
        sh_name = sec.month_label[:31]
        ws_m = wb.create_sheet(sh_name)
        ws_m.merge_cells("A1:F1")
        ws_m["A1"] = f"{dist_heading.upper()} - {sec.month_label.upper()} ({sec.target_rule_desc})"
        ws_m["A1"].font = Font(name="Calibri", size=12, bold=True, color="064E3B")
        ws_m["A2"] = f"Weeks ({sec.week_count}): {', '.join(sec.weeks_included)} | Report Generated On: {report.generated_time_str}"
        ws_m.append([])
        m_hdrs = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
        ws_m.append(m_hdrs)
        for col_idx in range(1, 7):
            c = ws_m.cell(row=4, column=col_idx)
            c.fill = hdr_fill
            c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
            c.border = border
        for r in sec.abstract_rows:
            ws_m.append([r.serial, r.unit_name, r.target, r.completed, r.balance, r.pct_completed])
        ws_m.append(["", "TOTAL", sec.total_target, sec.total_completed, sec.total_balance, sec.total_pct_completed])
        for letter, width in {"A": 8, "B": 28, "C": 12, "D": 13, "E": 12, "F": 14}.items():
            ws_m.column_dimensions[letter].width = width

    # Final Sheet: Submitted Records with Monday-Allocated Month
    ws_data = wb.create_sheet("Submitted Inspections Data")
    d_hdrs = [
        "Sl No", "Allocated Month", "Week", "Designation", "District", "Division",
        "Mandal", "Gram Panchayat", "Panchayat ID", "Date of Inspection", "Final Submit Status",
    ]
    ws_data.append(d_hdrs)
    for col_idx in range(1, len(d_hdrs) + 1):
        c = ws_data.cell(row=1, column=col_idx)
        c.fill = hdr_fill
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    for idx, rec in enumerate(report.submitted_records, start=1):
        ym = assign_week_to_month(rec.week_label) or assign_week_to_month(rec.inspection_date)
        m_lbl = format_month_key_label(ym) if ym else ""
        ws_data.append([
            idx, m_lbl, rec.week_label, rec.designation, rec.district_name, rec.division_name,
            rec.mandal_name, rec.gp_name, rec.panchayat_id, rec.inspection_date, rec.final_submit_status,
        ])
    for col in ws_data.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws_data.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 34)

    apply_openpyxl_branding(wb)
    wb.save(str(out))
    return out


def generate_monthwise_inspections_csv(report: InspectionReport) -> bytes:
    """Export Month-Wise breakdown CSV using strict Monday-start week allocation rules."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Month", "Weeks Count", "Included Weeks", "Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"])
    for sec in report.monthly_sections or []:
        w_str = "; ".join(sec.weeks_included)
        for r in sec.abstract_rows:
            writer.writerow([sec.month_label, sec.week_count, w_str, r.serial, r.unit_name, r.target, r.completed, r.balance, f"{r.pct_completed:.2f}"])
        writer.writerow([sec.month_label, sec.week_count, w_str, "", "MONTH TOTAL", sec.total_target, sec.total_completed, sec.total_balance, f"{sec.total_pct_completed:.2f}"])
    return buf.getvalue().encode("utf-8-sig")

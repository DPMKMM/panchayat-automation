"""PDF, Consolidated Excel, and CSV report generators for GM-R 39.1 Inspections."""

from __future__ import annotations

import csv
import html
import io
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.graphics.shapes import Drawing, Line, Rect, String as ShapeString
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
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


class _PctBarFlowable(Flowable):
    """Compact colored horizontal progress bar + bold percentage label inside table cells."""

    def __init__(self, pct: float, width: float = 34 * mm, height: float = 12.0, bold: bool = True):
        super().__init__()
        self.pct = float(pct or 0.0)
        self.width = width
        self.height = height
        self.bold = bold

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        bar_w = max(14 * mm, self.width - 14.5 * mm)
        bar_h = 5.5
        bar_x = 1.0
        bar_y = (self.height - bar_h) / 2.0

        # Track
        c.setFillColor(HexColor("#E2E8F0"))
        c.setStrokeColor(HexColor("#CBD5E1"))
        c.setLineWidth(0.35)
        c.roundRect(bar_x, bar_y, bar_w, bar_h, 2.2, stroke=1, fill=1)

        # Colored fill capped visually at 100%
        fill_ratio = max(0.0, min(1.0, self.pct / 100.0))
        fill_w = bar_w * fill_ratio
        color_hex = _tier_hex(self.pct)
        if fill_w > 0.6:
            c.setFillColor(HexColor(color_hex))
            c.roundRect(bar_x, bar_y, fill_w, bar_h, 2.2, stroke=0, fill=1)

        c.setFont("Helvetica-Bold" if self.bold else "Helvetica", 7.6)
        c.setFillColor(HexColor(color_hex))
        c.drawRightString(self.width - 1.0, (self.height - 6.0) / 2.0, f"{self.pct:.2f}%")
        c.restoreState()


def _build_inspections_bar_chart(report: InspectionReport, avail_w: float) -> Drawing:
    """Render a colorful horizontal achievement bar chart across Mandals/Divisions/Districts for A4 PDF."""
    rows = list(report.abstract_rows or [])
    row_h = 13.0
    top_pad = 22.0
    bot_pad = 16.0
    chart_h = top_pad + bot_pad + max(1, len(rows)) * row_h

    d = Drawing(avail_w, chart_h)
    # Soft card background
    d.add(Rect(0, 0, avail_w, chart_h, fillColor=HexColor("#F8FAFC"), strokeColor=HexColor("#CBD5E1"), strokeWidth=0.6, rx=4, ry=4))

    label_w = 48 * mm
    right_lbl_w = 28 * mm
    plot_x = label_w + 4 * mm
    plot_w = max(40 * mm, avail_w - plot_x - right_lbl_w - 4 * mm)
    max_pct = max([100.0] + [float(r.pct_completed or 0.0) for r in rows])

    # Vertical reference gridlines (0%, 25%, 50%, 75%, 100%)
    for tick in (0, 25, 50, 75, 100):
        tx = plot_x + plot_w * min(1.0, tick / max_pct)
        d.add(Line(tx, bot_pad - 2, tx, chart_h - top_pad + 4, strokeColor=HexColor("#E2E8F0"), strokeWidth=0.5))
        d.add(ShapeString(tx - 5, 5, f"{tick}%", fontName="Helvetica", fontSize=6.8, fillColor=HexColor("#64748B")))

    d.add(
        ShapeString(
            6 * mm,
            chart_h - 14,
            f"{report.group_label}-Wise Achievement % Bars ({report.designation})",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            fillColor=HexColor("#064E3B"),
        )
    )

    for idx, r in enumerate(rows):
        y_center = chart_h - top_pad - (idx + 0.5) * row_h
        name_txt = r.unit_name if len(r.unit_name) <= 23 else (r.unit_name[:21] + "..")
        d.add(ShapeString(5 * mm, y_center - 2.5, name_txt, fontName="Helvetica-Bold", fontSize=7.2, fillColor=HexColor("#1E293B")))

        bar_y = y_center - 3.8
        bar_h = 7.6
        d.add(Rect(plot_x, bar_y, plot_w, bar_h, fillColor=HexColor("#E2E8F0"), strokeWidth=0, rx=2, ry=2))

        ratio = max(0.0, min(1.0, float(r.pct_completed or 0.0) / max_pct))
        bw = plot_w * ratio
        c_hex = _tier_hex(r.pct_completed)
        if bw > 0.5:
            d.add(Rect(plot_x, bar_y, bw, bar_h, fillColor=HexColor(c_hex), strokeWidth=0, rx=2, ry=2))

        stat_lbl = f"{r.completed}/{r.target} ({r.pct_completed:.1f}%)"
        d.add(ShapeString(plot_x + plot_w + 3 * mm, y_center - 2.5, stat_lbl, fontName="Helvetica-Bold", fontSize=7.0, fillColor=HexColor(c_hex)))

    return d


def generate_inspections_pdf(report: InspectionReport, output_path: str | Path) -> Path:
    """Create colorful portrait A4 PDF matching: Sl No | Mandal/Division/District | Target | Completed | Balance | % Completed + visual bars."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    margin = 10 * mm
    avail_w = page_w - 2 * margin

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InspBannerTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=15, alignment=TA_CENTER, textColor=colors.white, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="InspBannerSub", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.2, leading=10.5, alignment=TA_CENTER, textColor=HexColor("#FDE68A"),
    ))
    styles.add(ParagraphStyle(
        name="InspMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.0, leading=11.5, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="InspHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.2, leading=10, alignment=TA_CENTER, textColor=colors.white,
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
            f"{dist_heading} | GM-R 39.1 {report.designation} Inspections | Report Generated On: {report.generated_time_str} | e-Panchayat Automation",
        )
        canvas.drawRightString(page_w - margin, 5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    # Colorful Executive Banner Table
    banner_tbl = Table(
        [
            [Paragraph(f"{_safe_xml(dist_heading.upper())} — GRAM PANCHAYAT INSPECTIONS ABSTRACT REPORT", styles["InspBannerTitle"])],
            [Paragraph(f"GM-R 39.1 { _safe_xml(report.designation_title) }  •  Final Submit Status: Submitted Only", styles["InspBannerSub"])],
        ],
        colWidths=[avail_w],
    )
    banner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#064E3B")),
        ("LINEBELOW", (0, 1), (-1, 1), 2.5, HexColor("#F59E0B")),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))

    # Metadata Summary Card (No 'Grouping: Mandal-wise', includes From Month to To Month + Report Generated On)
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

    # Colorful 5-Card KPI Strip
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

    headers = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
    # Portrait A4 available width = 190mm
    bar_col_w = 40 * mm
    col_widths = [
        13 * mm,
        avail_w - (13 + 22 + 24 + 22 + 40) * mm,
        22 * mm,
        24 * mm,
        22 * mm,
        bar_col_w,
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
            _PctBarFlowable(0.0, width=bar_col_w - 6),
        ])
    else:
        for row in report.abstract_rows:
            bal_html = (
                f'<font color="#DC2626"><b>{row.balance:,}</b></font>'
                if row.balance > 0
                else '<font color="#059669"><b>0</b></font>'
            )
            table_data.append([
                Paragraph(str(row.serial), styles["InspCell"]),
                Paragraph(f"<b>{_safe_xml(row.unit_name)}</b>", styles["InspCellLeft"]),
                Paragraph(f"{row.target:,}", styles["InspCell"]),
                Paragraph(f'<font color="#065F46"><b>{row.completed:,}</b></font>', styles["InspCell"]),
                Paragraph(bal_html, styles["InspCell"]),
                _PctBarFlowable(row.pct_completed, width=bar_col_w - 6),
            ])

    # Total Summary Row with total progress bar
    table_data.append([
        Paragraph("", styles["InspCell"]),
        Paragraph("<b>TOTAL</b>", styles["InspCellLeft"]),
        Paragraph(f"<b>{report.total_target:,}</b>", styles["InspCell"]),
        Paragraph(f'<font color="#065F46"><b>{report.total_completed:,}</b></font>', styles["InspCell"]),
        Paragraph(f'<font color="#991B1B"><b>{report.total_balance:,}</b></font>', styles["InspCell"]),
        _PctBarFlowable(report.total_pct_completed, width=bar_col_w - 6, bold=True),
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

    story: list[Any] = [
        banner_tbl,
        Spacer(1, 5),
        meta_tbl,
        Spacer(1, 6),
        kpi_tbl,
        Spacer(1, 7),
        tbl,
    ]

    if report.abstract_rows:
        story.append(Spacer(1, 9))
        story.append(KeepTogether([_build_inspections_bar_chart(report, avail_w)]))

    story.append(Spacer(1, 7))
    story.append(
        Paragraph(
            f"Audit Summary: Consolidated {len(report.weeks_selected)} week(s) | "
            f"Raw Records Scanned: {report.raw_row_count:,} | "
            f"Submitted Considered: {report.submitted_row_count:,} | "
            f"Non-Submitted Excluded: {report.excluded_non_submitted_count:,}",
            styles["InspNote"],
        )
    )

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
    ws["A1"] = f"{dist_heading.upper()} - GRAM PANCHAYAT INSPECTIONS ABSTRACT (GM-R 39.1)"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="17365D")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    period_str = _format_period_label(report.from_week, report.to_week)
    month_range = format_month_range_from_weeks(report.from_week, report.to_week)
    month_part = f"Period: {month_range} | " if month_range else ""
    ws.merge_cells("A2:F2")
    ws["A2"] = (
        f"Designation: {report.designation} | {month_part}{report.target_rule_desc} | "
        f"Weeks: {period_str} | Final Submit Status: Submitted Only | Report Generated On: {report.generated_time_str}"
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

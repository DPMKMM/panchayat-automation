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


def _build_monthly_summary_bar_chart(sections: list[Any], designation: str, avail_w: float) -> Drawing:
    """Render colorful Month-to-Month horizontal achievement % bar chart on A4."""
    row_h = 15.0
    top_pad = 22.0
    bot_pad = 16.0
    chart_h = top_pad + bot_pad + max(1, len(sections)) * row_h

    d = Drawing(avail_w, chart_h)
    d.add(Rect(0, 0, avail_w, chart_h, fillColor=HexColor("#F8FAFC"), strokeColor=HexColor("#CBD5E1"), strokeWidth=0.6, rx=4, ry=4))

    label_w = 42 * mm
    right_lbl_w = 34 * mm
    plot_x = label_w + 4 * mm
    plot_w = max(40 * mm, avail_w - plot_x - right_lbl_w - 4 * mm)
    max_pct = max([100.0] + [float(s.total_pct_completed or 0.0) for s in sections])

    for tick in (0, 25, 50, 75, 100):
        tx = plot_x + plot_w * min(1.0, tick / max_pct)
        d.add(Line(tx, bot_pad - 2, tx, chart_h - top_pad + 4, strokeColor=HexColor("#E2E8F0"), strokeWidth=0.5))
        d.add(ShapeString(tx - 5, 5, f"{tick}%", fontName="Helvetica", fontSize=6.8, fillColor=HexColor("#64748B")))

    d.add(
        ShapeString(
            6 * mm,
            chart_h - 14,
            f"Month-Wise Achievement % Bars ({designation} • Monday-Start Week Rule)",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            fillColor=HexColor("#064E3B"),
        )
    )

    for idx, s in enumerate(sections):
        y_center = chart_h - top_pad - (idx + 0.5) * row_h
        lbl = f"{s.month_label} ({s.week_count}w)"
        d.add(ShapeString(5 * mm, y_center - 2.5, lbl, fontName="Helvetica-Bold", fontSize=7.4, fillColor=HexColor("#1E293B")))

        bar_y = y_center - 4.0
        bar_h = 8.0
        d.add(Rect(plot_x, bar_y, plot_w, bar_h, fillColor=HexColor("#E2E8F0"), strokeWidth=0, rx=2, ry=2))

        bw = plot_w * max(0.0, min(1.0, float(s.total_pct_completed or 0.0) / max_pct))
        c_hex = _tier_hex(s.total_pct_completed)
        if bw > 0.5:
            d.add(Rect(plot_x, bar_y, bw, bar_h, fillColor=HexColor(c_hex), strokeWidth=0, rx=2, ry=2))

        stat_lbl = f"{s.total_completed}/{s.total_target} ({s.total_pct_completed:.1f}%)"
        d.add(ShapeString(plot_x + plot_w + 3 * mm, y_center - 2.5, stat_lbl, fontName="Helvetica-Bold", fontSize=7.1, fillColor=HexColor(c_hex)))

    return d


def _build_section_bar_chart(sec: Any, group_label: str, designation: str, avail_w: float) -> Drawing:
    """Render unit-level horizontal bar chart for a single MonthInspectionSection."""
    class _Proxy:
        pass
    p = _Proxy()
    p.abstract_rows = sec.abstract_rows
    p.group_label = group_label
    p.designation = f"{designation} • {sec.month_label}"
    return _build_inspections_bar_chart(p, avail_w)  # type: ignore[arg-type]


def generate_monthwise_inspections_pdf(report: InspectionReport, output_path: str | Path) -> Path:
    """Create colorful Portrait A4 Month-Wise Inspection Report PDF using strict Monday-start week rules."""
    from reportlab.platypus import PageBreak

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    margin = 10 * mm
    avail_w = page_w - 2 * margin

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MWBannerTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=12.0, leading=14.5, alignment=TA_CENTER, textColor=colors.white, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="MWBannerSub", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.0, leading=10.5, alignment=TA_CENTER, textColor=HexColor("#FDE68A"),
    ))
    styles.add(ParagraphStyle(
        name="MWMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.8, leading=11.0, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="MWHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7.8, leading=9.5, alignment=TA_CENTER, textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="MWHdrLeft", parent=styles["MWHdr"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="MWCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.7, leading=9.5, alignment=TA_CENTER, textColor=HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        name="MWCellLeft", parent=styles["MWCell"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="MWSecHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10.0, leading=12.5, alignment=TA_LEFT, textColor=colors.white,
    ))

    dist_heading = _format_district_title(report.district_name)
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
            f"{dist_heading} | GM-R 39.1 {report.designation} Month-Wise Report | Report Generated On: {report.generated_time_str} | e-Panchayat Automation",
        )
        canvas.drawRightString(page_w - margin, 5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    banner_tbl = Table(
        [
            [Paragraph(f"{_safe_xml(dist_heading.upper())} — MONTH-WISE GRAM PANCHAYAT INSPECTIONS REPORT", styles["MWBannerTitle"])],
            [Paragraph(f"GM-R 39.1 {_safe_xml(report.designation_title)}  •  Final Submit Status: Submitted Only", styles["MWBannerSub"])],
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

    meta_tbl = Table(
        [[
            Paragraph(
                f"Period: <b>{_safe_xml(month_range or 'Selected Period')}</b> | "
                f"Months: <b>{len(sections)}</b> | Total Weeks: <b>{len(report.weeks_selected)}</b> | "
                f"Report Generated On: <b>{_safe_xml(report.generated_time_str)}</b><br/>"
                "Week Allocation Rule: First Monday starts month; each Mon–Sun week is assigned strictly to its Monday's month.",
                styles["MWMeta"],
            )
        ]],
        colWidths=[avail_w],
    )
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ECFDF5")),
        ("BOX", (0, 0), (-1, -1), 0.75, HexColor("#6EE7B7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))

    # Month-Wise Summary Table
    sum_bar_w = 34 * mm
    sum_col_w = [
        10 * mm,
        21 * mm,
        13 * mm,
        avail_w - (10 + 21 + 13 + 18 + 19 + 19 + 18 + 34) * mm,
        18 * mm,
        19 * mm,
        19 * mm,
        18 * mm,
        sum_bar_w,
    ]
    # Ensure flexible middle column stays readable on 190mm A4
    if sum_col_w[3] < 36 * mm:
        diff = 36 * mm - sum_col_w[3]
        sum_col_w[3] = 36 * mm
        sum_col_w[8] = max(28 * mm, sum_col_w[8] - diff)

    sum_headers = ["Sl No", "Month", "Weeks", "Monday-Allocated Weeks", "Unit Tgt", "Target", "Completed", "Balance", "% Completed"]
    sum_rows: list[list[Any]] = [[
        Paragraph(_safe_xml(h), styles["MWHdrLeft"] if idx in (1, 3) else styles["MWHdr"])
        for idx, h in enumerate(sum_headers)
    ]]

    if not sections:
        sum_rows.append([
            Paragraph("-", styles["MWCell"]),
            Paragraph("-", styles["MWCellLeft"]),
            Paragraph("0", styles["MWCell"]),
            Paragraph("No monthly week data available.", styles["MWCellLeft"]),
            Paragraph("0", styles["MWCell"]),
            Paragraph("0", styles["MWCell"]),
            Paragraph("0", styles["MWCell"]),
            Paragraph("0", styles["MWCell"]),
            _PctBarFlowable(0.0, width=sum_col_w[8] - 4),
        ])
    else:
        for idx, sec in enumerate(sections, start=1):
            weeks_desc = f"{sec.weeks_included[0]} -> {sec.weeks_included[-1]}" if len(sec.weeks_included) > 1 else (sec.weeks_included[0] if sec.weeks_included else "-")
            sum_rows.append([
                Paragraph(str(idx), styles["MWCell"]),
                Paragraph(f"<b>{_safe_xml(sec.month_label)}</b>", styles["MWCellLeft"]),
                Paragraph(str(sec.week_count), styles["MWCell"]),
                Paragraph(_safe_xml(weeks_desc), styles["MWCellLeft"]),
                Paragraph(f"{sec.target_per_unit:,}", styles["MWCell"]),
                Paragraph(f"{sec.total_target:,}", styles["MWCell"]),
                Paragraph(f'<font color="#065F46"><b>{sec.total_completed:,}</b></font>', styles["MWCell"]),
                Paragraph(f'<font color="{"#DC2626" if sec.total_balance > 0 else "#059669"}"><b>{sec.total_balance:,}</b></font>', styles["MWCell"]),
                _PctBarFlowable(sec.total_pct_completed, width=sum_col_w[8] - 4),
            ])
        sum_tot_t = sum(s.total_target for s in sections)
        sum_tot_c = sum(s.total_completed for s in sections)
        sum_tot_b = sum(s.total_balance for s in sections)
        sum_tot_p = round((sum_tot_c / sum_tot_t) * 100.0, 2) if sum_tot_t > 0 else 0.0
        sum_rows.append([
            Paragraph("", styles["MWCell"]),
            Paragraph("<b>TOTAL</b>", styles["MWCellLeft"]),
            Paragraph(f"<b>{sum(s.week_count for s in sections)}</b>", styles["MWCell"]),
            Paragraph("All Selected Months", styles["MWCellLeft"]),
            Paragraph("-", styles["MWCell"]),
            Paragraph(f"<b>{sum_tot_t:,}</b>", styles["MWCell"]),
            Paragraph(f'<font color="#065F46"><b>{sum_tot_c:,}</b></font>', styles["MWCell"]),
            Paragraph(f'<font color="#991B1B"><b>{sum_tot_b:,}</b></font>', styles["MWCell"]),
            _PctBarFlowable(sum_tot_p, width=sum_col_w[8] - 4, bold=True),
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

    story: list[Any] = [banner_tbl, Spacer(1, 5), meta_tbl, Spacer(1, 6), sum_tbl]
    if sections:
        story.append(Spacer(1, 8))
        story.append(KeepTogether([_build_monthly_summary_bar_chart(sections, report.designation, avail_w)]))

    # Per-Month Abstract Breakdown Sections
    unit_bar_w = 40 * mm
    unit_col_w = [13 * mm, avail_w - (13 + 22 + 24 + 22 + 40) * mm, 22 * mm, 24 * mm, 22 * mm, unit_bar_w]

    for sec in sections:
        story.append(PageBreak())
        sec_hdr_tbl = Table(
            [[
                Paragraph(
                    f"{_safe_xml(sec.month_label)} — {_safe_xml(sec.target_rule_desc)}  |  "
                    f"Weeks ({sec.week_count}): {_safe_xml(', '.join(sec.weeks_included))}",
                    styles["MWSecHdr"],
                )
            ]],
            colWidths=[avail_w],
        )
        sec_hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#1E3A8A")),
            ("LINEBELOW", (0, 0), (-1, -1), 2.0, HexColor("#F59E0B")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))

        u_headers = ["Sl No", report.group_label, "Target", "Completed", "Balance", "% Completed"]
        u_rows: list[list[Any]] = [[
            Paragraph(_safe_xml(h), styles["MWHdrLeft"] if idx == 1 else styles["MWHdr"])
            for idx, h in enumerate(u_headers)
        ]]
        for r in sec.abstract_rows:
            bal_html = f'<font color="#DC2626"><b>{r.balance:,}</b></font>' if r.balance > 0 else '<font color="#059669"><b>0</b></font>'
            u_rows.append([
                Paragraph(str(r.serial), styles["MWCell"]),
                Paragraph(f"<b>{_safe_xml(r.unit_name)}</b>", styles["MWCellLeft"]),
                Paragraph(f"{r.target:,}", styles["MWCell"]),
                Paragraph(f'<font color="#065F46"><b>{r.completed:,}</b></font>', styles["MWCell"]),
                Paragraph(bal_html, styles["MWCell"]),
                _PctBarFlowable(r.pct_completed, width=unit_bar_w - 6),
            ])
        u_rows.append([
            Paragraph("", styles["MWCell"]),
            Paragraph(f"<b>TOTAL ({_safe_xml(sec.month_label)})</b>", styles["MWCellLeft"]),
            Paragraph(f"<b>{sec.total_target:,}</b>", styles["MWCell"]),
            Paragraph(f'<font color="#065F46"><b>{sec.total_completed:,}</b></font>', styles["MWCell"]),
            Paragraph(f'<font color="#991B1B"><b>{sec.total_balance:,}</b></font>', styles["MWCell"]),
            _PctBarFlowable(sec.total_pct_completed, width=unit_bar_w - 6, bold=True),
        ])

        u_tbl = Table(u_rows, colWidths=unit_col_w, repeatRows=1, hAlign="LEFT", splitByRow=1)
        u_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F4C5C")),
            ("GRID", (0, 0), (-1, -1), 0.45, HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, HexColor("#F0F9FF")]),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#D1FAE5")),
            ("LINEABOVE", (0, -1), (-1, -1), 1.1, HexColor("#064E3B")),
        ]))

        story.append(sec_hdr_tbl)
        story.append(Spacer(1, 6))
        story.append(u_tbl)
        if sec.abstract_rows:
            story.append(Spacer(1, 8))
            story.append(KeepTogether([_build_section_bar_chart(sec, report.group_label, report.designation, avail_w)]))

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=13 * mm,
        title=f"{dist_heading} {report.designation} Month-Wise GP Inspections Report",
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
    ws["A1"] = f"{dist_heading.upper()} - MONTH-WISE GRAM PANCHAYAT INSPECTIONS ABSTRACT (GM-R 39.1)"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="064E3B")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:I2")
    ws["A2"] = (
        f"Designation: {report.designation} | Period: {month_range or 'Selected'} | "
        f"Monday-Start Week Allocation | Final Submit Status: Submitted Only | Report Generated On: {report.generated_time_str}"
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

    # Sheet 2: Unit x Month Comparison Matrix
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

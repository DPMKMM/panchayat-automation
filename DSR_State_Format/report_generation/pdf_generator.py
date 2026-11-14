"""
DSR State Format - Official Government Landscape PDF Generator
==============================================================
Generates the official 14-column "Mandal wise Status of Panchayat Secretaries
Attendance With Time" PDF matching the reference government report format.
"""

from __future__ import annotations

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from DSR_State_Format.calculations.aggregator import StateFormatReport


def generate_state_format_pdf(report: StateFormatReport, output_path: Path) -> Path:
    """
    Renders StateFormatReport to official Landscape A4 PDF.
    Guarantees exact 14-column layout matching government reference.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = landscape(A4)
    # Margins: 27 pt left/right, 20 pt top/bottom
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(page_width, page_height),
        leftMargin=27,
        rightMargin=27,
        topMargin=20,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()

    title_district = ParagraphStyle(
        "PDFDistTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e293b"),
    )
    title_main = ParagraphStyle(
        "PDFMainTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#990000"),
    )
    title_sub = ParagraphStyle(
        "PDFSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#003399"),
    )
    footer_style = ParagraphStyle(
        "PDFFooter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b"),
    )

    story = []

    # 1. District Header
    dist_str = f"District Name: {report.district_name}"
    story.append(Paragraph(dist_str, title_district))
    story.append(Spacer(1, 2))

    # 2. Main Title
    main_title = "Mandal wise Status of Panchayat Secretaries Attendance With Time"
    story.append(Paragraph(main_title, title_main))
    story.append(Spacer(1, 2))

    # 3. Subtitle (Date and Time)
    date_display = report.report_date.strftime("%d %B %Y")
    time_display = report.generated_at.strftime("%I:%M %p")
    sub_title = f"{date_display} - @ {time_display}"
    story.append(Paragraph(sub_title, title_sub))
    story.append(Spacer(1, 8))

    # 4. Table Construction
    col_widths = [
        26,   # 1: Sl. No.
        112,  # 2: Mandal Name
        50,   # 3: Total No. of GPs
        60,   # 4: No.of PS in which full time working
        46,   # 5: 6 AM - 9 AM
        46,   # 6: 9 AM - 10 AM
        46,   # 7: 10 AM - 11 AM
        48,   # 8: 11 AM - 12 Noon
        46,   # 9: After 12 Noon
        70,   # 10: % of PS Reported before 9 AM ↓
        62,   # 11: Total No.of PSs attended GP
        65,   # 12: No.of PSs reported to Mtg / Trngs today
        55,   # 13: No.of PSs on Leave Today
        55,   # 14: No.of PS Not reported
    ]

    # Cell paragraph styles
    th_style = ParagraphStyle(
        "THStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    th_style_pct = ParagraphStyle(
        "THStylePct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0369a1"),
    )
    td_num_style = ParagraphStyle(
        "TDNum",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    td_txt_style = ParagraphStyle(
        "TDTxt",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=8.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0f172a"),
    )
    td_pct_style = ParagraphStyle(
        "TDPct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#c00000"),
    )
    tot_txt_style = ParagraphStyle(
        "TotTxt",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    tot_pct_style = ParagraphStyle(
        "TotPct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#c00000"),
    )

    table_data = []

    # Header Row 0
    table_data.append([
        Paragraph("Sl.<br/>No.", th_style),
        Paragraph("Mandal Name", th_style),
        Paragraph("Total<br/>No. of GPs", th_style),
        Paragraph("No.of PS in<br/>which full time<br/>working", th_style),
        Paragraph("No.of Panchayat Secretaries reported", th_style),
        "", "", "", "", "", "", "", "", ""
    ])

    # Header Row 1
    table_data.append([
        "", "", "", "",
        Paragraph("6 AM -<br/>9 AM", th_style),
        Paragraph("9 AM -<br/>10 AM", th_style),
        Paragraph("10 AM -<br/>11 AM", th_style),
        Paragraph("11 AM -<br/>12 Noon", th_style),
        Paragraph("After<br/>12 Noon", th_style),
        Paragraph("% of PS<br/>Reported<br/>before 9 AM<br/>↓", th_style_pct),
        Paragraph("Total No.of<br/>PSs attended<br/>GP", th_style),
        Paragraph("No.of PSs<br/>reported to<br/>Mtg / Trngs<br/>today", th_style),
        Paragraph("No.of PSs on<br/>Leave Today", th_style),
        Paragraph("No.of PS Not<br/>reported", th_style),
    ])

    # Header Row 2 (Column numbers 1 to 14)
    table_data.append([
        Paragraph("1", th_style),
        Paragraph("2", th_style),
        Paragraph("3", th_style),
        Paragraph("4", th_style),
        Paragraph("5", th_style),
        Paragraph("6", th_style),
        Paragraph("7", th_style),
        Paragraph("8", th_style),
        Paragraph("9", th_style),
        Paragraph("10", th_style_pct),
        Paragraph("11", th_style),
        Paragraph("12", th_style),
        Paragraph("13", th_style),
        Paragraph("14", th_style),
    ])

    # Data Rows
    for row in report.mandal_rows:
        pct_val = f"{row['pct_before_9']:.2f}"
        table_data.append([
            Paragraph(str(row["sl_no"]), td_num_style),
            Paragraph(str(row["mandal_name"]), td_txt_style),
            Paragraph(str(row["tot_gps"]), td_num_style),
            Paragraph(str(row["full_time"]), td_num_style),
            Paragraph(str(row["b_6_9"]) if row["b_6_9"] > 0 else "", td_num_style),
            Paragraph(str(row["b_9_10"]) if row["b_9_10"] > 0 else "", td_num_style),
            Paragraph(str(row["b_10_11"]) if row["b_10_11"] > 0 else "", td_num_style),
            Paragraph(str(row["b_11_12"]) if row["b_11_12"] > 0 else "", td_num_style),
            Paragraph(str(row["b_after_12"]) if row["b_after_12"] > 0 else "", td_num_style),
            Paragraph(pct_val, td_pct_style),
            Paragraph(str(row["attended_gp"]) if row["attended_gp"] > 0 else "", td_num_style),
            Paragraph(str(row["mtg_trng"]) if row["mtg_trng"] > 0 else "", td_num_style),
            Paragraph(str(row["leave"]) if row["leave"] > 0 else "", td_num_style),
            Paragraph(str(row["not_reported"]), td_num_style),
        ])

    # Total Row
    tot = report.total_row
    tot_pct_val = f"{tot['pct_before_9']:.2f}"
    table_data.append([
        Paragraph("Total", tot_txt_style),
        "",
        Paragraph(str(tot["tot_gps"]), tot_txt_style),
        Paragraph(str(tot["full_time"]), tot_txt_style),
        Paragraph(str(tot["b_6_9"]), tot_txt_style),
        Paragraph(str(tot["b_9_10"]), tot_txt_style),
        Paragraph(str(tot["b_10_11"]), tot_txt_style),
        Paragraph(str(tot["b_11_12"]), tot_txt_style),
        Paragraph(str(tot["b_after_12"]), tot_txt_style),
        Paragraph(tot_pct_val, tot_pct_style),
        Paragraph(str(tot["attended_gp"]), tot_txt_style),
        Paragraph(str(tot["mtg_trng"]), tot_txt_style),
        Paragraph(str(tot["leave"]), tot_txt_style),
        Paragraph(str(tot["not_reported"]), tot_txt_style),
    ])

    # Percentage Row
    pct_r = report.percentage_row
    table_data.append([
        Paragraph("Percentage", tot_txt_style),
        "",
        "",
        "",
        Paragraph(f"{pct_r['b_6_9']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['b_9_10']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['b_10_11']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['b_11_12']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['b_after_12']:.2f}", tot_pct_style),
        "",
        Paragraph(f"{pct_r['attended_gp']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['mtg_trng']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['leave']:.2f}", tot_pct_style),
        Paragraph(f"{pct_r['not_reported']:.2f}", tot_pct_style),
    ])

    # Table Styles
    num_data_rows = len(report.mandal_rows)
    tot_idx = 3 + num_data_rows
    pct_idx = tot_idx + 1

    t_style = [
        # Grid lines everywhere
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#000000")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        # Header Spans
        ("SPAN", (0, 0), (0, 1)),  # Sl. No.
        ("SPAN", (1, 0), (1, 1)),  # Mandal Name
        ("SPAN", (2, 0), (2, 1)),  # Total GPs
        ("SPAN", (3, 0), (3, 1)),  # Full Time PS
        ("SPAN", (4, 0), (13, 0)), # No. of PS reported
        # Header Backgrounds
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#ebf3fa")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e2e8f0")),
        # Column 9 (% before 9 AM) special styling
        ("BACKGROUND", (9, 1), (9, 2), colors.HexColor("#e0f2fe")),
        ("BACKGROUND", (9, 3), (9, tot_idx), colors.HexColor("#e0f2fe")),
        # Total Row Span and Background
        ("SPAN", (0, tot_idx), (1, tot_idx)),
        ("BACKGROUND", (0, tot_idx), (-1, tot_idx), colors.HexColor("#ebf3fa")),
        # Percentage Row Span and Background
        ("SPAN", (0, pct_idx), (1, pct_idx)),
        ("BACKGROUND", (0, pct_idx), (-1, pct_idx), colors.HexColor("#f8fafc")),
        ("BACKGROUND", (9, pct_idx), (9, pct_idx), colors.HexColor("#e0f2fe")),
    ]

    tab = Table(table_data, colWidths=col_widths, style=TableStyle(t_style), repeatRows=3)
    story.append(tab)

    # 5. Footer
    story.append(Spacer(1, 8))
    footer_text = "Panchayat-Automation — Simplifying Panchayat Administration through Smart Reporting and Automation"
    story.append(Paragraph(footer_text, footer_style))

    doc.build(story)
    return output_path

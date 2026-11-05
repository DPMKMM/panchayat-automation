"""PDF Generator for GP Balance Entry Report (GM-R 14.2).

Produces an executive landscape PDF report matching Telangana PR&RD standards:
  - KPI Summary Badges (Total Mandals, Total GPs, Entered, Pending, % Completed)
  - Mandal Summary Abstract with % Data Entered
  - Pending Gram Panchayats Action List with Missing Accounts details
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from gp_balance_models import DistrictBalanceReport


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4B5563"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(825, 12, page_text)
        self.drawString(16, 12, "Telangana PR & RD Department — GP Balance Entry Monitoring Portal (GM-R 14.2)")
        self.restoreState()


def format_display_timestamp(dt_str: str) -> str:
    from datetime import datetime
    if not dt_str:
        return datetime.now().strftime("%d-%B-%Y %I:%M %p")
    for fmt in ("%d-%b-%Y %I:%M %p", "%d-%B-%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(dt_str.strip(), fmt).strftime("%d-%B-%Y %I:%M %p")
        except Exception:
            pass
    return datetime.now().strftime("%d-%B-%Y %I:%M %p")


def generate_balance_pdf(report: DistrictBalanceReport, target: Optional[Union[Path, str, io.BytesIO]] = None) -> bytes:
    if isinstance(target, Path):
        dest_filename = str(target)
        dest = dest_filename
        buffer = None
    elif target is None or isinstance(target, io.BytesIO):
        buffer = io.BytesIO() if target is None else target
        dest = buffer
    else:
        dest = str(target)
        buffer = None

    # Page setup: Landscape A4 (841.89 x 595.27 pt) - maximized space with clean 16pt margins
    page_width, page_height = landscape(A4)
    margin = 16
    content_width = page_width - (2 * margin)

    doc = SimpleDocTemplate(
        dest,
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=14,
        bottomMargin=22,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0C3829"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#165B43"),
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=9.5,
        alignment=1,
        textColor=colors.HexColor("#4E6B60"),
    )

    kpi_label_style = ParagraphStyle(
        "KPILabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#374151"),
    )
    kpi_val_style = ParagraphStyle(
        "KPIVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=14.5,
        alignment=1,
        textColor=colors.HexColor("#0C3829"),
    )
    kpi_entered_style = ParagraphStyle(
        "KPIValEntered",
        parent=kpi_val_style,
        textColor=colors.HexColor("#059669"),
    )
    kpi_pending_style = ParagraphStyle(
        "KPIValPending",
        parent=kpi_val_style,
        textColor=colors.HexColor("#DC2626"),
    )

    th_style = ParagraphStyle(
        "TableHeaderSuper",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.2,
        alignment=1,
        textColor=colors.white,
    )
    th_sub_style = ParagraphStyle(
        "TableHeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=7.8,
        alignment=1,
        textColor=colors.white,
    )
    td_left = ParagraphStyle(
        "TableDataLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=0,
        textColor=colors.HexColor("#132A22"),
    )
    td_center = ParagraphStyle(
        "TableDataCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#132A22"),
    )
    td_bold_center = ParagraphStyle(
        "TableDataBoldCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#132A22"),
    )
    td_pending_center = ParagraphStyle(
        "TableDataPendingCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#DC2626"),
    )
    td_success_center = ParagraphStyle(
        "TableDataSuccessCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#059669"),
    )
    td_pending_left = ParagraphStyle(
        "TableDataPendingLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=0,
        textColor=colors.HexColor("#DC2626"),
    )
    td_status_done = ParagraphStyle(
        "TDStatusDone",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#059669"),
    )
    td_status_pending = ParagraphStyle(
        "TDStatusPending",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#DC2626"),
    )

    flowables = []

    # 1. Header Banner with User-Specified Title
    gen_time_str = format_display_timestamp(report.generated_at)
    import re
    clean_dist = re.sub(r"^[\s\-–—:]+", "", report.district_name or "").strip()
    clean_dist = re.sub(r"\bDISTRICT\b", "", clean_dist, flags=re.IGNORECASE).strip()
    clean_dist = re.sub(r"\s+", " ", clean_dist).strip()

    dist_banner = f"<br/>- {clean_dist.upper()} DISTRICT" if clean_dist and clean_dist.lower() != "district" else ""

    flowables.append(Paragraph(
        f"Data Entry Status Report on Balances in GP Accounts as on {gen_time_str}{dist_banner}",
        title_style,
    ))
    flowables.append(Spacer(1, 3))
    flowables.append(Paragraph(
        f"Thursday Balance Update Date: <b>{report.report_date_str}</b> | Portal GM-R 14.2 | PMAGY Excluded (Not maintained in district)",
        meta_style,
    ))
    flowables.append(Spacer(1, 6))

    # 2. Executive KPI Cards (Clean 2-row table preventing any label/value overlap)
    kpi_data = [
        [
            Paragraph("TOTAL MANDALS", kpi_label_style),
            Paragraph("TOTAL GPs", kpi_label_style),
            Paragraph("DATA ENTERED", kpi_label_style),
            Paragraph("PENDING GPs", kpi_label_style),
            Paragraph("COMPLIANCE %", kpi_label_style),
        ],
        [
            Paragraph(f"{report.total_mandals}", kpi_val_style),
            Paragraph(f"{report.total_gps}", kpi_val_style),
            Paragraph(f"{report.total_entered_gps}", kpi_entered_style),
            Paragraph(f"{report.total_not_entered_gps}", kpi_pending_style),
            Paragraph(f"{report.overall_pct_entered:.1f}%", kpi_val_style),
        ],
    ]
    kpi_widths = [content_width / 5] * 5
    t_kpi = Table(kpi_data, colWidths=kpi_widths, rowHeights=[14, 18])
    t_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#167451")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A7F3D0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    flowables.append(t_kpi)
    flowables.append(Spacer(1, 7))

    # 3. Mandal Summary Table (Full page width utilization & increased header heights)
    widths = [
        24,   # 0: S.No
        118,  # 1: Mandal Name
        42,   # 2: Total GPs
        44,   # 3: GPs Entered
        46,   # 4: GPs Not Entered
        46,   # 5: % Data Entered
        36,   # 6: GP PD Upd
        34,   # 7: GP PD Pnd
        38,   # 8: TG-bPASS Upd
        36,   # 9: TG-bPASS Pend
        38,   # 10: 15th FC Tied Upd
        36,   # 11: 15th FC Tied Pend
        38,   # 12: 15th FC Untied Upd
        36,   # 13: 15th FC Untied Pend
        36,   # 14: VWSC Upd
        34,   # 15: VWSC Pend
        38,   # 16: MGNREGS Upd
        36,   # 17: MGNREGS Pend
        62,   # 18: Status (Spacious width prevents text wrapping or overlap)
    ]

    # Distribute any fractional points to Mandal Name so table spans 100% of landscape content width
    total_w = sum(widths)
    if content_width > total_w:
        widths[1] += round(content_width - total_w, 1)
    elif total_w > content_width:
        widths[1] -= round(total_w - content_width, 1)

    hdr_row1 = [
        Paragraph("S.No", th_style),
        Paragraph("Mandal Name", th_style),
        Paragraph("Total<br/>GPs", th_style),
        Paragraph("GPs<br/>Entered", th_style),
        Paragraph("GPs Not<br/>Entered", th_style),
        Paragraph("% Data<br/>Entered", th_style),
        Paragraph("GP PD Account", th_style), "",
        Paragraph("State Matching<br/>(TG-bPASS)", th_style), "",
        Paragraph("15th FC Tied", th_style), "",
        Paragraph("15th FC Untied", th_style), "",
        Paragraph("VWSC (SBM)", th_style), "",
        Paragraph("MGNREGS (Mat)", th_style), "",
        Paragraph("Status", th_style),
    ]

    hdr_row2 = [
        "", "", "", "", "", "",
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style),
        "",
    ]

    table_data = [hdr_row1, hdr_row2]
    # Header heights: Super-header 26pt, Sub-header 16pt (Total 42pt)
    row_heights = [26, 16]
    table_styles = [
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (2, 1)),
        ("SPAN", (3, 0), (3, 1)),
        ("SPAN", (4, 0), (4, 1)),
        ("SPAN", (5, 0), (5, 1)),
        ("SPAN", (6, 0), (7, 0)),
        ("SPAN", (8, 0), (9, 0)),
        ("SPAN", (10, 0), (11, 0)),
        ("SPAN", (12, 0), (13, 0)),
        ("SPAN", (14, 0), (15, 0)),
        ("SPAN", (16, 0), (17, 0)),
        ("SPAN", (18, 0), (18, 1)),
        # Seamless solid dark green for all spanned columns from top to bottom
        ("BACKGROUND", (0, 0), (5, 1), colors.HexColor("#0C3829")),
        ("BACKGROUND", (18, 0), (18, 1), colors.HexColor("#0C3829")),
        # Super-headers for account columns
        ("BACKGROUND", (6, 0), (17, 0), colors.HexColor("#0C3829")),
        # Sub-headers for Upd / Pnd
        ("BACKGROUND", (6, 1), (17, 1), colors.HexColor("#165B43")),
        # Header alignment: strictly centered horizontally and middle vertically
        ("ALIGN", (0, 0), (-1, 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Data alignment: S.No centered, Mandal Name left, all data columns CENTERED
        ("ALIGN", (0, 2), (0, -1), "CENTER"),
        ("ALIGN", (1, 2), (1, -1), "LEFT"),
        ("ALIGN", (2, 2), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("GRID", (0, 0), (-1, 1), 0.5, colors.HexColor("#062B1F")),
    ]

    data_row_h = 14.5 if len(report.mandals) > 20 else 15.5
    for idx, m in enumerate(report.mandals, start=1):
        r_idx = len(table_data)
        bg = colors.HexColor("#F8FAFC") if idx % 2 == 0 else colors.white
        pending_cnt = max(m.not_entered_gps, len(m.pending_gps), m.gp_pd_pending, m.tgbpass_pending, m.fc15_tied_pending, m.fc15_untied_pending, m.vwsc_pending, m.mgnregs_pending) if m.has_pending else 0
        status_text = "100% Done" if not m.has_pending else f"{max(1, pending_cnt)} Pending"
        status_style = td_status_done if not m.has_pending else td_status_pending

        row = [
            Paragraph(str(idx), td_center),
            Paragraph(m.mandal_name, td_left),
            Paragraph(str(m.total_gps), td_bold_center),
            Paragraph(str(m.entered_gps), td_success_center if m.entered_gps == m.total_gps else td_center),
            Paragraph(str(m.not_entered_gps), td_pending_center if m.not_entered_gps > 0 else td_center),
            Paragraph(f"{m.pct_entered:.1f}%", td_bold_center),
            Paragraph(str(m.gp_pd_updated), td_center),
            Paragraph(str(m.gp_pd_pending), td_pending_center if m.gp_pd_pending > 0 else td_center),
            Paragraph(str(m.tgbpass_updated), td_center),
            Paragraph(str(m.tgbpass_pending), td_pending_center if m.tgbpass_pending > 0 else td_center),
            Paragraph(str(m.fc15_tied_updated), td_center),
            Paragraph(str(m.fc15_tied_pending), td_pending_center if m.fc15_tied_pending > 0 else td_center),
            Paragraph(str(m.fc15_untied_updated), td_center),
            Paragraph(str(m.fc15_untied_pending), td_pending_center if m.fc15_untied_pending > 0 else td_center),
            Paragraph(str(m.vwsc_updated), td_center),
            Paragraph(str(m.vwsc_pending), td_pending_center if m.vwsc_pending > 0 else td_center),
            Paragraph(str(m.mgnregs_updated), td_center),
            Paragraph(str(m.mgnregs_pending), td_pending_center if m.mgnregs_pending > 0 else td_center),
            Paragraph(status_text, status_style),
        ]
        table_data.append(row)
        row_heights.append(data_row_h)
        table_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), bg))

    # Total Row
    tot_idx = len(table_data)
    tot_status_text = f"<b>{report.total_not_entered_gps} Pending</b>" if report.total_not_entered_gps > 0 else "<b>100% Done</b>"
    tot_status_style = td_status_pending if report.total_not_entered_gps > 0 else td_status_done
    tot_row = [
        Paragraph("", td_center),
        Paragraph("<b>DISTRICT TOTAL</b>", td_left),
        Paragraph(f"<b>{report.total_gps}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_entered_gps}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_not_entered_gps}</b>", td_pending_center if report.total_not_entered_gps > 0 else td_bold_center),
        Paragraph(f"<b>{report.overall_pct_entered:.1f}%</b>", td_bold_center),
        Paragraph(f"<b>{sum(m.gp_pd_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_gp_pd_pending}</b>", td_pending_center if report.total_gp_pd_pending > 0 else td_bold_center),
        Paragraph(f"<b>{sum(m.tgbpass_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_tgbpass_pending}</b>", td_pending_center if report.total_tgbpass_pending > 0 else td_bold_center),
        Paragraph(f"<b>{sum(m.fc15_tied_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_fc15_tied_pending}</b>", td_pending_center if report.total_fc15_tied_pending > 0 else td_bold_center),
        Paragraph(f"<b>{sum(m.fc15_untied_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_fc15_untied_pending}</b>", td_pending_center if report.total_fc15_untied_pending > 0 else td_bold_center),
        Paragraph(f"<b>{sum(m.vwsc_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_vwsc_pending}</b>", td_pending_center if report.total_vwsc_pending > 0 else td_bold_center),
        Paragraph(f"<b>{sum(m.mgnregs_updated for m in report.mandals)}</b>", td_bold_center),
        Paragraph(f"<b>{report.total_mgnregs_pending}</b>", td_pending_center if report.total_mgnregs_pending > 0 else td_bold_center),
        Paragraph(tot_status_text, tot_status_style),
    ]
    table_data.append(tot_row)
    row_heights.append(16)
    table_styles.extend([
        ("BACKGROUND", (0, tot_idx), (-1, tot_idx), colors.HexColor("#FEF3C7")),
        ("LINEABOVE", (0, tot_idx), (-1, tot_idx), 1, colors.HexColor("#0C3829")),
        ("LINEBELOW", (0, tot_idx), (-1, tot_idx), 1.5, colors.HexColor("#0C3829")),
    ])

    t_mandal = Table(table_data, colWidths=widths, rowHeights=row_heights, repeatRows=2)
    t_mandal.setStyle(TableStyle(table_styles))
    flowables.append(t_mandal)

    # 4. Pending Gram Panchayats Section (if any)
    if report.pending_gps_all:
        flowables.append(PageBreak())
        flowables.append(Paragraph("LIST OF PENDING GRAM PANCHAYATS", title_style))
        flowables.append(Spacer(1, 3))
        flowables.append(Paragraph(
            f"The following {len(report.pending_gps_all)} Gram Panchayat(s) have not completed Thursday balance entries for one or more active accounts.",
            subtitle_style,
        ))
        flowables.append(Spacer(1, 8))

        p_widths = [28, 120, 160, 60, 0]
        p_widths[4] = content_width - sum(p_widths[:4])

        p_table = [
            [
                Paragraph("S.No", th_style),
                Paragraph("Mandal Name", th_style),
                Paragraph("Gram Panchayat Name", th_style),
                Paragraph("Status", th_style),
                Paragraph("Missing Account(s) (Marked 'No')", th_style),
            ]
        ]
        p_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C3829")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D4E0DA")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]

        for p_idx, gp in enumerate(report.pending_gps_all, start=1):
            curr_row = len(p_table)
            bg = colors.HexColor("#FEE2E2") if p_idx % 2 == 1 else colors.HexColor("#FFF1F2")
            missing_txt = ", ".join(gp.missing_accounts) if gp.missing_accounts else "Data Not Entered"

            p_table.append([
                Paragraph(str(p_idx), td_center),
                Paragraph(gp.mandal_name, td_left),
                Paragraph(gp.panchayat_name, td_left),
                Paragraph("Pending", td_pending_center),
                Paragraph(missing_txt, td_pending_left),
            ])
            p_styles.append(("BACKGROUND", (0, curr_row), (-1, curr_row), bg))

        t_pending = Table(p_table, colWidths=p_widths, repeatRows=1)
        t_pending.setStyle(TableStyle(p_styles))
        flowables.append(t_pending)

    doc.build(flowables, canvasmaker=NumberedCanvas)

    if buffer is not None:
        return buffer.getvalue()
    elif isinstance(target, (str, Path)):
        return Path(target).read_bytes()
    return b""

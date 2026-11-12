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

try:
    from gp_balance.models import DistrictBalanceReport
except (ImportError, ModuleNotFoundError):
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
        self.drawString(16, 12, "GP Balance Entry Monitoring | Panchayat-Automation")
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


def generate_balance_pdf(report: DistrictBalanceReport, target: Optional[Union[Path, str, io.BytesIO]] = None, mandal_name: Optional[str] = None) -> bytes:
    if mandal_name and mandal_name.strip():
        return generate_mandal_balance_pdf(report, target, mandal_name=mandal_name.strip())
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

    dist_prefix = f"{clean_dist.title()} District - " if clean_dist and clean_dist.lower() != "district" else ""

    flowables.append(Paragraph(
        f"{dist_prefix}Data Entry Status Report on Balances in GP Accounts as on {gen_time_str}",
        title_style,
    ))
    flowables.append(Spacer(1, 3))
    flowables.append(Paragraph(
        f"Thursday Balance Update Date: <b>{report.report_date_str}</b>",
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

    # 3. Mandal Summary Table (Full page width utilization & dynamic account columns)
    include_pmagy = bool(getattr(report, "include_pmagy", False))
    accounts_pdf = [
        ("GP PD Account", "gp_pd_updated", "gp_pd_pending", "total_gp_pd_pending", (36, 34) if not include_pmagy else (33, 31)),
        ("State Matching<br/>(TG-bPASS)", "tgbpass_updated", "tgbpass_pending", "total_tgbpass_pending", (38, 36) if not include_pmagy else (35, 33)),
        ("15th FC Tied", "fc15_tied_updated", "fc15_tied_pending", "total_fc15_tied_pending", (38, 36) if not include_pmagy else (35, 33)),
        ("15th FC Untied", "fc15_untied_updated", "fc15_untied_pending", "total_fc15_untied_pending", (38, 36) if not include_pmagy else (35, 33)),
    ]
    if include_pmagy:
        accounts_pdf.append(("PMAGY<br/>(Adarsh)", "pmagy_updated", "pmagy_pending", "total_pmagy_pending", (33, 31)))
    accounts_pdf.extend([
        ("VWSC (SBM)", "vwsc_updated", "vwsc_pending", "total_vwsc_pending", (36, 34) if not include_pmagy else (33, 31)),
        ("MGNREGS (Mat)", "mgnregs_updated", "mgnregs_pending", "total_mgnregs_pending", (38, 36) if not include_pmagy else (35, 33)),
    ])

    widths = [
        24 if not include_pmagy else 22,    # S.No
        118 if not include_pmagy else 100,  # Mandal Name
        42 if not include_pmagy else 38,    # Total GPs
        44 if not include_pmagy else 40,    # GPs Entered
        46 if not include_pmagy else 42,    # GPs Not Entered
        46 if not include_pmagy else 42,    # % Data Entered
    ]
    for _, _, _, _, (w_u, w_p) in accounts_pdf:
        widths.extend([w_u, w_p])
    widths.append(62 if not include_pmagy else 56)  # Status

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
    ]
    hdr_row2 = ["", "", "", "", "", ""]
    span_cmds = [
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (2, 1)),
        ("SPAN", (3, 0), (3, 1)),
        ("SPAN", (4, 0), (4, 1)),
        ("SPAN", (5, 0), (5, 1)),
    ]
    c_idx = 6
    for label, _, _, _, _ in accounts_pdf:
        hdr_row1.extend([Paragraph(label, th_style), ""])
        hdr_row2.extend([Paragraph("Upd", th_sub_style), Paragraph("Pnd", th_sub_style)])
        span_cmds.append(("SPAN", (c_idx, 0), (c_idx + 1, 0)))
        c_idx += 2
    status_col_idx = c_idx
    hdr_row1.append(Paragraph("Status", th_style))
    hdr_row2.append("")
    span_cmds.append(("SPAN", (status_col_idx, 0), (status_col_idx, 1)))

    table_data = [hdr_row1, hdr_row2]
    # Header heights: Super-header 26pt, Sub-header 16pt (Total 42pt)
    row_heights = [26, 16]
    table_styles = span_cmds + [
        # Seamless solid dark green for all spanned columns from top to bottom
        ("BACKGROUND", (0, 0), (5, 1), colors.HexColor("#0C3829")),
        ("BACKGROUND", (status_col_idx, 0), (status_col_idx, 1), colors.HexColor("#0C3829")),
        # Super-headers for account columns
        ("BACKGROUND", (6, 0), (status_col_idx - 1, 0), colors.HexColor("#0C3829")),
        # Sub-headers for Upd / Pnd
        ("BACKGROUND", (6, 1), (status_col_idx - 1, 1), colors.HexColor("#165B43")),
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
        acc_pend_vals = [getattr(m, p_attr, 0) for _, _, p_attr, _, _ in accounts_pdf]
        pending_cnt = max([m.not_entered_gps, len(m.pending_gps), *acc_pend_vals]) if m.has_pending else 0
        status_text = "100% Done" if not m.has_pending else f"{max(1, pending_cnt)} Pending"
        status_style = td_status_done if not m.has_pending else td_status_pending

        row = [
            Paragraph(str(idx), td_center),
            Paragraph(m.mandal_name, td_left),
            Paragraph(str(m.total_gps), td_bold_center),
            Paragraph(str(m.entered_gps), td_success_center if m.entered_gps == m.total_gps else td_center),
            Paragraph(str(m.not_entered_gps), td_pending_center if m.not_entered_gps > 0 else td_center),
            Paragraph(f"{m.pct_entered:.1f}%", td_bold_center),
        ]
        for _, u_attr, p_attr, _, _ in accounts_pdf:
            u_val = getattr(m, u_attr, 0)
            p_val = getattr(m, p_attr, 0)
            row.append(Paragraph(str(u_val), td_center))
            row.append(Paragraph(str(p_val), td_pending_center if p_val > 0 else td_center))
        row.append(Paragraph(status_text, status_style))

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
    ]
    for _, u_attr, _, tot_p_attr, _ in accounts_pdf:
        u_sum = sum(getattr(m, u_attr, 0) for m in report.mandals)
        p_sum = getattr(report, tot_p_attr, 0)
        tot_row.append(Paragraph(f"<b>{u_sum}</b>", td_bold_center))
        tot_row.append(Paragraph(f"<b>{p_sum}</b>", td_pending_center if p_sum > 0 else td_bold_center))
    tot_row.append(Paragraph(tot_status_text, tot_status_style))
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


def generate_mandal_balance_pdf(report: DistrictBalanceReport, target: Optional[Union[Path, str, io.BytesIO]] = None, mandal_name: Optional[str] = None) -> bytes:
    """Generates an executive Gram Panchayat wise Thursday Balance PDF report for a single Mandal."""
    if isinstance(target, Path):
        dest = str(target)
        buffer = None
    elif target is None or isinstance(target, io.BytesIO):
        buffer = io.BytesIO() if target is None else target
        dest = buffer
    else:
        dest = str(target)
        buffer = None

    req_name = (mandal_name or "").strip().casefold()
    target_m = None
    for m in report.mandals:
        if m.mandal_name.strip().casefold() == req_name:
            target_m = m
            break
    if not target_m and report.mandals:
        target_m = report.mandals[0]

    m_name = target_m.mandal_name if target_m else (mandal_name or "Mandal")
    tot_gps = target_m.total_gps if target_m else 0
    ent_gps = target_m.entered_gps if target_m else 0
    not_ent = target_m.not_entered_gps if target_m else 0
    pct_ent = target_m.pct_entered if target_m else 0.0

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
    title_style = ParagraphStyle("MTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#0C3829"))
    subtitle_style = ParagraphStyle("MSubtitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, alignment=1, textColor=colors.HexColor("#165B43"))
    meta_style = ParagraphStyle("MMeta", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5, alignment=1, textColor=colors.HexColor("#4E6B60"))

    kpi_lbl = ParagraphStyle("MKPILabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, alignment=1, textColor=colors.HexColor("#374151"))
    kpi_val = ParagraphStyle("MKPIVal", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#0C3829"))

    th_s = ParagraphStyle("MTH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, alignment=1, textColor=colors.white)
    td_l = ParagraphStyle("MTDL", parent=styles["Normal"], fontName="Helvetica", fontSize=6.5, leading=8, alignment=0, textColor=colors.HexColor("#1F2937"))
    td_c = ParagraphStyle("MTDC", parent=styles["Normal"], fontName="Helvetica", fontSize=6.5, leading=8, alignment=1, textColor=colors.HexColor("#1F2937"))
    td_done = ParagraphStyle("MTDDone", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, alignment=1, textColor=colors.HexColor("#059669"))
    td_pend = ParagraphStyle("MTDPend", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, alignment=1, textColor=colors.HexColor("#DC2626"))

    flowables = []
    flowables.append(Paragraph("TELANGANA STATE E-PANCHAYAT (ePTS) AUTOMATION PLATFORM", title_style))
    flowables.append(Spacer(1, 2))
    flowables.append(Paragraph(f"GRAM PANCHAYAT BANK BALANCE ENTRY REPORT — {m_name.upper()} MANDAL", subtitle_style))
    flowables.append(Spacer(1, 2))
    gen_time = format_display_timestamp(report.generated_at)
    include_pmagy = bool(getattr(report, "include_pmagy", False))
    pmagy_note = "PMAGY Included" if include_pmagy else "PMAGY Excluded"
    flowables.append(Paragraph(f"Mandal: <b>{m_name}</b> | District: <b>{report.district_name}</b> | Thursday Date: <b>{report.report_date_str}</b> | {pmagy_note} | Compiled: {gen_time}", meta_style))
    flowables.append(Spacer(1, 6))

    # KPI Summary Cards for Mandal
    kpi_card_w = (content_width - (3 * 8)) / 4.0
    kpi_table_data = [
        [
            Paragraph("TOTAL GRAM PANCHAYATS", kpi_lbl),
            Paragraph("COMPLETED GPs (100%)", kpi_lbl),
            Paragraph("PENDING GPs", kpi_lbl),
            Paragraph("COMPLIANCE RATE", kpi_lbl),
        ],
        [
            Paragraph(str(tot_gps), kpi_val),
            Paragraph(f"<font color='#059669'>{ent_gps}</font>", kpi_val),
            Paragraph(f"<font color='#DC2626'>{not_ent}</font>", kpi_val),
            Paragraph(f"<font color='{'#059669' if pct_ent >= 90 else ('#0284C7' if pct_ent >= 75 else '#D97706')}'>{pct_ent:.1f}%</font>", kpi_val),
        ],
    ]
    kpi_table = Table(kpi_table_data, colWidths=[kpi_card_w]*4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0FDF4")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#DCFCE7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#FEE2E2")),
        ("BACKGROUND", (3, 0), (3, -1), colors.HexColor("#FEF3C7")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    flowables.append(kpi_table)
    flowables.append(Spacer(1, 6))

    # Detailed GP Table
    mandal_acc_cols = [
        ("GP PD", "gp_pd", "gp_pd_updated", 38 if not include_pmagy else 35),
        ("TG-bPASS", "tgbpass", "tgbpass_updated", 42 if not include_pmagy else 39),
        ("15th Tied", "fc15_tied", "fc15_tied_updated", 42 if not include_pmagy else 39),
        ("15th Untied", "fc15_untied", "fc15_untied_updated", 44 if not include_pmagy else 40),
    ]
    if include_pmagy:
        mandal_acc_cols.append(("PMAGY", "pmagy", "pmagy_updated", 36))
    mandal_acc_cols.extend([
        ("VWSC", "vwsc", "vwsc_updated", 38 if not include_pmagy else 35),
        ("MGNREGS", "mgnregs", "mgnregs_updated", 45 if not include_pmagy else 40),
    ])

    col_w = [
        22,
        115 if not include_pmagy else 105,
        52 if not include_pmagy else 48,
    ] + [w for _, _, _, w in mandal_acc_cols] + [
        140 if not include_pmagy else 128,
        0,
    ]
    col_w[-1] = content_width - sum(col_w[:-1])

    hdr = [
        Paragraph("S.No", th_s),
        Paragraph("Gram Panchayat Name", th_s),
        Paragraph("Status", th_s),
    ] + [Paragraph(lbl, th_s) for lbl, _, _, _ in mandal_acc_cols] + [
        Paragraph("Missing Bank Account(s)", th_s),
        Paragraph("Panchayat Secretary & Phone", th_s),
    ]
    t_data = [hdr]
    t_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C3829")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D4E0DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]

    gps_to_render = (target_m.all_gps if target_m and target_m.all_gps else (target_m.pending_gps if target_m else []))
    for idx, gp in enumerate(gps_to_render, start=1):
        row_idx = len(t_data)
        is_p = gp.is_pending
        bg = colors.HexColor("#FEE2E2") if is_p else (colors.HexColor("#F9FAFB") if idx % 2 == 1 else colors.white)

        status_p = Paragraph("Pending", td_pend) if is_p else Paragraph("100% Done", td_done)
        missing_str = ", ".join(gp.missing_accounts) if gp.missing_accounts else ("Data Not Entered" if is_p else "—")
        missing_p = Paragraph(missing_str, td_pend if is_p else td_c)

        sec_contact = f"{gp.secretary_name or 'PS'}" + (f" ({gp.secretary_phone})" if gp.secretary_phone and gp.secretary_phone != '—' else "")

        def _ac_cell(v: str):
            is_y = str(v).strip().lower() in ("yes", "1", "true", "done", "y")
            return Paragraph("Yes", td_done) if is_y else Paragraph("No", td_pend)

        t_data.append(
            [
                Paragraph(str(idx), td_c),
                Paragraph(f"<b>{gp.panchayat_name}</b>", td_l),
                status_p,
            ]
            + [_ac_cell(getattr(gp, attr, "Yes")) for _, attr, _, _ in mandal_acc_cols]
            + [missing_p, Paragraph(sec_contact, td_l)]
        )
        t_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))

    # Summary Row
    summary_row_idx = len(t_data)
    t_data.append(
        [
            Paragraph("TOTAL", th_s),
            Paragraph(f"<b>{m_name} Mandal ({tot_gps} GPs)</b>", th_s),
            Paragraph(f"<b>{ent_gps}/{tot_gps}</b>", th_s),
        ]
        + [Paragraph(f"<b>{getattr(target_m, upd_attr, 0) if target_m else 0}</b>", th_s) for _, _, upd_attr, _ in mandal_acc_cols]
        + [
            Paragraph(f"<b>Pending GPs: {not_ent}</b>", th_s),
            Paragraph(f"<b>Compliance: {pct_ent:.1f}%</b>", th_s),
        ]
    )
    t_styles.append(("BACKGROUND", (0, summary_row_idx), (-1, summary_row_idx), colors.HexColor("#0C3829")))

    table = Table(t_data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(t_styles))
    flowables.append(table)

    doc.build(flowables, canvasmaker=NumberedCanvas)

    if buffer is not None:
        return buffer.getvalue()
    elif isinstance(target, (str, Path)):
        return Path(target).read_bytes()
    return b""

"""Generate pixel-accurate Gram Panchayat Wise DCB PDF report matching official department format."""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String

try:
    from dcb import service as tax_service
except (ImportError, ModuleNotFoundError):
    import tax_service


def format_indian_currency(val: float | int | str) -> str:
    """Format a number into Indian comma notation (e.g., 1,97,509)."""
    try:
        n = int(round(float(val)))
    except (ValueError, TypeError):
        return str(val) if val is not None else "0"
    if n == 0:
        return "0"
    is_neg = n < 0
    s = str(abs(n))
    if len(s) <= 3:
        res = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        res = ",".join(groups) + "," + last3
    return f"-{res}" if is_neg else res


def get_gradient_color(pct: float | int) -> tuple[str, str]:
    """Return (bg_hex, text_hex) for a smooth 3-color Green -> Yellow -> Red gradient scale.
    Highest collection (100%) = Green (#16A34A)
    Medium collection (50%) = Yellow (#EAB308)
    Lowest collection (0%) = Red (#DC2626)
    """
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (ValueError, TypeError):
        p = 0.0

    if p <= 50.0:
        t = p / 50.0
        # Red (220, 38, 38) -> Yellow (234, 179, 8)
        r = int(220 + t * (234 - 220))
        g = int(38 + t * (179 - 38))
        b = int(38 + t * (8 - 38))
    else:
        t = (p - 50.0) / 50.0
        # Yellow (234, 179, 8) -> Green (22, 163, 74)
        r = int(234 + t * (22 - 234))
        g = int(179 + t * (163 - 179))
        b = int(8 + t * (74 - 8))

    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    text_color = "#000000" if lum > 0.55 else "#FFFFFF"
    hex_bg = f"#{r:02X}{g:02X}{b:02X}"
    return hex_bg, text_color


def make_pct_flowable(pct: float | int, h_row: float, font_size: float = 7.0) -> Drawing:
    """Create a 'line column type' meter for the % column in PDF:
    Displays the bold percentage text with a proportional progress line bar underneath.
    """
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (ValueError, TypeError):
        p = 0
    bg_hex, _ = get_gradient_color(p)
    w_draw = 33.0
    h_draw = max(13.0, min(h_row - 2.0, 19.0))
    d = Drawing(w_draw, h_draw)

    text_y = h_draw / 2.0 + 1.2
    bar_y = max(1.5, h_draw / 2.0 - 5.2)
    bar_h = 3.2

    # Percentage number
    d.add(String(w_draw / 2.0, text_y, f"{p:.1f}%", fontName="Helvetica-Bold", fontSize=font_size, textAnchor="middle", fillColor=colors.HexColor("#111827")))
    # Track line
    d.add(Rect(0, bar_y, w_draw, bar_h, fillColor=colors.HexColor("#E2E8F0"), strokeColor=None, rx=1.5, ry=1.5))
    # Filled progress bar line
    bar_w = max(0.0, min(w_draw, w_draw * (p / 100.0)))
    if bar_w > 0:
        d.add(Rect(0, bar_y, max(bar_w, 1.5), bar_h, fillColor=colors.HexColor(bg_hex), strokeColor=None, rx=1.5, ry=1.5))
    return d


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y' on every page."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#222222"))
        page_str = f"Page {self._pageNumber} of {page_count}"
        # Landscape A4 width is 841.89 pt
        self.setFillColor(colors.HexColor("#475569"))
        self.setFont("Helvetica", 7.2)
        self.drawString(24, 16, "e-Panchayat Automation")
        self.drawRightString(841.89 - 24, 16, "Simplifying Panchayat Administration through Smart Reporting and Automation.")
        self.setFillColor(colors.HexColor("#222222"))
        self.setFont("Helvetica", 8)
        self.drawCentredString(841.89 / 2.0, 16, page_str)
        self.restoreState()


def get_or_generate_dcb_pdf(
    district_name: str = "Khammam",
    mandal_name: Optional[str] = None,
    force_regenerate: bool = True,
    report_date_str: Optional[str] = None,
) -> tuple[str, bytes]:
    """Return filename and bytes of the generated DCB report for the district / mandal."""
    safe_dist = district_name.strip().replace(" ", "_").title()
    safe_mandal = ""
    is_single_mandal = bool(mandal_name and mandal_name.strip().lower() not in ("all", "all mandals", ""))
    if is_single_mandal and mandal_name:
        safe_mandal = "_" + mandal_name.strip().replace(" ", "_").title()

    import sys
    try:
        from core.config import REPORTS_DIR as reports_dir
    except Exception:
        reports_dir = Path(__file__).resolve().parent.parent / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    india_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = india_now.strftime("%d-%m-%Y")
    pdf_filename = f"{safe_dist}{safe_mandal}_House_Tax_DCB_Report_{date_str}.pdf"
    pdf_path = reports_dir / pdf_filename

    if not force_regenerate and pdf_path.exists() and pdf_path.stat().st_size > 1000:
        return pdf_filename, pdf_path.read_bytes()

    content = generate_dcb_pdf(
        district_name=district_name,
        mandal_name=mandal_name,
        output_path_or_buffer=pdf_path,
        report_date_str=report_date_str,
    )
    return pdf_filename, content


def generate_dcb_pdf(
    district_name: str = "Khammam",
    mandal_name: Optional[str] = None,
    output_path_or_buffer: Any = None,
    report_date_str: Optional[str] = None,
    df_source: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate the official landscape Gram Panchayat Wise DCB PDF report.
    Returns bytes and writes to output_path_or_buffer if provided.
    """
    df = df_source if df_source is not None else tax_service.get_df()

    if district_name and district_name.lower() not in ("all", "all districts"):
        df_dist = df[df["district"].str.lower() == district_name.strip().lower()].copy()
    else:
        df_dist = df.copy()

    is_single_mandal = bool(mandal_name and mandal_name.strip().lower() not in ("all", "all mandals", ""))
    if is_single_mandal and mandal_name:
        df_dist = df_dist[df_dist["mandal"].str.lower() == mandal_name.strip().lower()].copy()

    if report_date_str is None:
        report_date_str = datetime.now().strftime("%d-%b-%Y")

    # Document setup: Landscape A4 with 24pt left/right margins, 22pt top, 28pt bottom
    buffer = io.BytesIO()
    target = output_path_or_buffer if isinstance(output_path_or_buffer, (str, Path)) else buffer

    doc = SimpleDocTemplate(
        str(target) if isinstance(target, (str, Path)) else target,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=16,
        bottomMargin=22,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DCBTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        alignment=1,  # Centered
        textColor=colors.HexColor("#0B5ED7"),
        spaceAfter=6,
    )

    cell_hdr_style = ParagraphStyle(
        "DCBCellHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,  # Center
        textColor=colors.black,
    )

    cell_body_left = ParagraphStyle(
        "DCBCellBodyLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        alignment=0,  # Left
        textColor=colors.black,
    )

    cell_body_right = ParagraphStyle(
        "DCBCellBodyRight",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        alignment=2,  # Right
        textColor=colors.black,
    )

    cell_body_center = ParagraphStyle(
        "DCBCellBodyCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        alignment=1,  # Center
        textColor=colors.black,
    )

    cell_pct_style = ParagraphStyle(
        "DCBCellPct",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=1,  # Center
        textColor=colors.white,
    )

    cell_total_label = ParagraphStyle(
        "DCBCellTotalLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=0,
        textColor=colors.black,
    )

    cell_total_num = ParagraphStyle(
        "DCBCellTotalNum",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=2,
        textColor=colors.black,
    )

    # Column widths summing to 794 pt (fits 841.89 pt page with 24 pt margins)
    col_widths = [28, 82, 110, 54, 60, 64, 56, 60, 64, 54, 60, 64, 38]

    headers = [
        "S No",
        "Mandal Name",
        "Panchayat Name",
        "Demand\nArreas",
        "Demand\nCurrent",
        "Demand\nTotal",
        "Collection\nArrears",
        "Collection\nCurrent",
        "Collection\nTotal",
        "Balance\nArrears",
        "Balance\nCurrent",
        "Balance\nTotal",
        "%",
    ]

    header_row = [Paragraph(h.replace("\n", "<br/>"), cell_hdr_style) for h in headers]

    flowables = []

    # Title text based on District level vs Mandal level
    if is_single_mandal and mandal_name:
        clean_mandal = mandal_name.strip().title()
        title_text = f"{clean_mandal} Mandal - Gram Panchayat Wise DCB status as on {report_date_str}"
    else:
        clean_dist = district_name.strip().title() if district_name and district_name.lower() not in ("all", "all districts") else "State"
        title_text = f"{clean_dist} District - Gram Panchayat Wise DCB status as on {report_date_str}"

    # Group by Mandal
    mandals = sorted(df_dist["mandal"].unique())
    is_first_page = True

    # PAGE 1: MANDAL-WISE ABSTRACT TABLE (For District-Level Reports)
    if not is_single_mandal and len(mandals) > 1:
        abstract_title = f"{clean_dist} District - Mandal Wise House Tax DCB Abstract as on {report_date_str}"
        flowables.append(Paragraph(abstract_title, title_style))
        flowables.append(Spacer(1, 4))

        abs_col_widths = [28, 120, 44, 58, 62, 66, 58, 62, 66, 58, 62, 66, 44]
        abs_headers = [
            "S No",
            "Mandal Name",
            "Total\nGPs",
            "Demand\nArrears",
            "Demand\nCurrent",
            "Demand\nTotal",
            "Collection\nArrears",
            "Collection\nCurrent",
            "Collection\nTotal",
            "Balance\nArrears",
            "Balance\nCurrent",
            "Balance\nTotal",
            "%",
        ]
        abs_header_row = [Paragraph(h.replace("\n", "<br/>"), cell_hdr_style) for h in abs_headers]
        abs_table_data = [abs_header_row]

        dist_d_arr = 0
        dist_d_cur = 0
        dist_d_tot = 0
        dist_c_arr = 0
        dist_c_cur = 0
        dist_c_tot = 0
        dist_b_arr = 0
        dist_b_cur = 0
        dist_b_tot = 0
        dist_gps_tot = 0

        h_abs_row = 19.5 if len(mandals) <= 22 else max(15.0, (500.0 - 24.0) / (len(mandals) + 2))
        abs_row_heights = [24.0]

        abs_table_styles = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#333333")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("ALIGN", (3, 0), (-2, -1), "RIGHT"),
            ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        ]

        # Collect mandal statistics for abstract table
        abs_mandals = []
        for m_name in mandals:
            m_sub = df_dist[df_dist["mandal"] == m_name]
            m_gps = len(m_sub)
            m_d_arr = int(m_sub["demand_arrear"].sum())
            m_d_cur = int(m_sub["demand_current"].sum())
            m_d_tot = int(m_sub["demand_total"].sum())
            m_c_arr = int(m_sub["collection_arrear"].sum())
            m_c_cur = int(m_sub["collection_current"].sum())
            m_c_tot = int(m_sub["collection_total"].sum())
            m_b_arr = int(m_sub["balance_arrear"].sum())
            m_b_cur = int(m_sub["balance_current"].sum())
            m_b_tot = int(m_sub["balance_total"].sum())
            m_pct_float = (m_c_tot / m_d_tot * 100.0) if m_d_tot > 0 else 0.0
            m_pct = round(m_pct_float, 1)
            abs_mandals.append({
                "name": m_name,
                "gps": m_gps,
                "d_arr": m_d_arr,
                "d_cur": m_d_cur,
                "d_tot": m_d_tot,
                "c_arr": m_c_arr,
                "c_cur": m_c_cur,
                "c_tot": m_c_tot,
                "b_arr": m_b_arr,
                "b_cur": m_b_cur,
                "b_tot": m_b_tot,
                "pct_float": m_pct_float,
                "pct": m_pct,
            })

        # Sort mandal abstract by % Collected ascending: lowest collected mandal on top
        abs_mandals.sort(key=lambda x: (x["pct_float"], x["d_tot"], x["name"]))

        for idx, m_stat in enumerate(abs_mandals, start=1):
            m_name = m_stat["name"]
            m_gps = m_stat["gps"]
            m_d_arr = m_stat["d_arr"]
            m_d_cur = m_stat["d_cur"]
            m_d_tot = m_stat["d_tot"]
            m_c_arr = m_stat["c_arr"]
            m_c_cur = m_stat["c_cur"]
            m_c_tot = m_stat["c_tot"]
            m_b_arr = m_stat["b_arr"]
            m_b_cur = m_stat["b_cur"]
            m_b_tot = m_stat["b_tot"]
            m_pct_float = m_stat["pct_float"]
            m_pct = m_stat["pct"]

            dist_d_arr += m_d_arr
            dist_d_cur += m_d_cur
            dist_d_tot += m_d_tot
            dist_c_arr += m_c_arr
            dist_c_cur += m_c_cur
            dist_c_tot += m_c_tot
            dist_b_arr += m_b_arr
            dist_b_cur += m_b_cur
            dist_b_tot += m_b_tot
            dist_gps_tot += m_gps

            m_bg_hex, m_fg_hex = get_gradient_color(m_pct_float)
            m_pct_style = ParagraphStyle(
                f"AbsPct_{idx}",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=9,
                alignment=1,
                textColor=colors.HexColor(m_fg_hex),
            )

            r_idx = len(abs_table_data)
            bg_color = colors.HexColor("#F8FAFC") if idx % 2 == 0 else colors.white

            abs_row = [
                Paragraph(str(idx), cell_body_center),
                Paragraph(f"<b>{m_name}</b>", cell_body_left),
                Paragraph(str(m_gps), cell_body_center),
                Paragraph(format_indian_currency(m_d_arr), cell_body_right),
                Paragraph(format_indian_currency(m_d_cur), cell_body_right),
                Paragraph(format_indian_currency(m_d_tot), cell_body_right),
                Paragraph(format_indian_currency(m_c_arr), cell_body_right),
                Paragraph(format_indian_currency(m_c_cur), cell_body_right),
                Paragraph(format_indian_currency(m_c_tot), cell_body_right),
                Paragraph(format_indian_currency(m_b_arr), cell_body_right),
                Paragraph(format_indian_currency(m_b_cur), cell_body_right),
                Paragraph(format_indian_currency(m_b_tot), cell_body_right),
                Paragraph(f"{m_pct_float:.1f}%", m_pct_style),
            ]
            abs_table_data.append(abs_row)
            abs_row_heights.append(h_abs_row)
            abs_table_styles.append(("BACKGROUND", (0, r_idx), (-2, r_idx), bg_color))
            abs_table_styles.append(("BACKGROUND", (-1, r_idx), (-1, r_idx), colors.HexColor(m_bg_hex)))

        # District Total Row
        dist_pct_float = (dist_c_tot / dist_d_tot * 100.0) if dist_d_tot > 0 else 0.0
        d_bg_hex, d_fg_hex = get_gradient_color(dist_pct_float)
        d_pct_style = ParagraphStyle(
            "DistTotPct",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9.5,
            alignment=1,
            textColor=colors.HexColor(d_fg_hex),
        )

        tot_r_idx = len(abs_table_data)
        dist_tot_row = [
            Paragraph("", cell_total_label),
            Paragraph("<b>DISTRICT TOTAL</b>", cell_total_label),
            Paragraph(f"<b>{dist_gps_tot}</b>", cell_total_label),
            Paragraph(format_indian_currency(dist_d_arr), cell_total_num),
            Paragraph(format_indian_currency(dist_d_cur), cell_total_num),
            Paragraph(format_indian_currency(dist_d_tot), cell_total_num),
            Paragraph(format_indian_currency(dist_c_arr), cell_total_num),
            Paragraph(format_indian_currency(dist_c_cur), cell_total_num),
            Paragraph(format_indian_currency(dist_c_tot), cell_total_num),
            Paragraph(format_indian_currency(dist_b_arr), cell_total_num),
            Paragraph(format_indian_currency(dist_b_cur), cell_total_num),
            Paragraph(format_indian_currency(dist_b_tot), cell_total_num),
            Paragraph(f"{dist_pct_float:.1f}%", d_pct_style),
        ]
        abs_table_data.append(dist_tot_row)
        abs_row_heights.append(h_abs_row + 2.0)
        abs_table_styles.extend([
            ("BACKGROUND", (0, tot_r_idx), (-2, tot_r_idx), colors.HexColor("#FEF3C7")),
            ("BACKGROUND", (-1, tot_r_idx), (-1, tot_r_idx), colors.HexColor(d_bg_hex)),
            ("LINEABOVE", (0, tot_r_idx), (-1, tot_r_idx), 1.2, colors.HexColor("#1E293B")),
            ("LINEBELOW", (0, tot_r_idx), (-1, tot_r_idx), 1.5, colors.HexColor("#1E293B")),
        ])

        t_abs = Table(abs_table_data, colWidths=abs_col_widths, rowHeights=abs_row_heights, repeatRows=1)
        t_abs.setStyle(TableStyle(abs_table_styles))
        flowables.append(t_abs)
        is_first_page = False

    # Row capacity per page
    # Page 1 has title so max rows is 22; subsequent pages have no title so max rows is 24
    for m_idx, mandal_name in enumerate(mandals):
        m_df = df_dist[df_dist["mandal"] == mandal_name].copy()
        # Sort GPs within mandal by percentage descending, then demand_total descending
        m_df = m_df.sort_values(by=["calc_percentage", "demand_total", "panchayat"], ascending=[False, False, True])

        # Calculate mandal totals
        tot_d_arr = m_df["demand_arrear"].sum()
        tot_d_cur = m_df["demand_current"].sum()
        tot_d_tot = m_df["demand_total"].sum()
        tot_c_arr = m_df["collection_arrear"].sum()
        tot_c_cur = m_df["collection_current"].sum()
        tot_c_tot = m_df["collection_total"].sum()
        tot_b_arr = m_df["balance_arrear"].sum()
        tot_b_cur = m_df["balance_current"].sum()
        tot_b_tot = m_df["balance_total"].sum()
        tot_pct_float = (tot_c_tot / tot_d_tot * 100.0) if tot_d_tot > 0 else 0.0
        tot_bg_hex, tot_fg_hex = get_gradient_color(tot_pct_float)
        tot_pct_style = ParagraphStyle(
            f"TotPct_{m_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            alignment=1,
            textColor=colors.HexColor(tot_fg_hex),
        )

        total_row = [
            Paragraph("", cell_total_label),
            Paragraph(f"{mandal_name} Total", cell_total_label),
            Paragraph("", cell_total_label),
            Paragraph(format_indian_currency(tot_d_arr), cell_total_num),
            Paragraph(format_indian_currency(tot_d_cur), cell_total_num),
            Paragraph(format_indian_currency(tot_d_tot), cell_total_num),
            Paragraph(format_indian_currency(tot_c_arr), cell_total_num),
            Paragraph(format_indian_currency(tot_c_cur), cell_total_num),
            Paragraph(format_indian_currency(tot_c_tot), cell_total_num),
            Paragraph(format_indian_currency(tot_b_arr), cell_total_num),
            Paragraph(format_indian_currency(tot_b_cur), cell_total_num),
            Paragraph(format_indian_currency(tot_b_tot), cell_total_num),
            Paragraph(f"{tot_pct_float:.1f}%", tot_pct_style),
        ]

        # Chunk the mandal rows into pages using best fit
        # Below 25 to 28 GPs -> single page. Around 40 GPs -> 2 pages.
        gp_records = m_df.to_dict(orient="records")
        total_gps = len(gp_records)
        num_pages_mandal = max(1, math.ceil(total_gps / 28))
        gps_per_page = math.ceil(total_gps / num_pages_mandal)

        cursor = 0
        for page_idx in range(num_pages_mandal):
            if not is_first_page:
                flowables.append(PageBreak())
            is_first_page = False

            # Every page displays the official title with District or Mandal Name
            flowables.append(Paragraph(title_text, title_style))

            is_last_chunk_of_mandal = (page_idx == num_pages_mandal - 1)
            chunk_size = total_gps - cursor if is_last_chunk_of_mandal else gps_per_page
            chunk = gp_records[cursor : cursor + chunk_size]

            # Calculate exact available vertical height to fill the entire page space
            avail_h = 555.27 - 28.0 - 14.0
            h_hdr = 22.0
            n_data_and_total = len(chunk) + (1 if is_last_chunk_of_mandal else 0)
            h_row = (avail_h - h_hdr) / float(n_data_and_total)

            # Proportional font size and leading based on expanded row height
            if h_row >= 24.0:
                f_sz = 8.2
                f_lead = 9.8
            elif h_row >= 20.0:
                f_sz = 7.6
                f_lead = 9.0
            else:
                f_sz = 7.0
                f_lead = 8.2

            cur_cell_left = ParagraphStyle(f"CBL_{m_idx}_{page_idx}", parent=styles["Normal"], fontName="Helvetica", fontSize=f_sz, leading=f_lead, alignment=0, textColor=colors.black)
            cur_cell_right = ParagraphStyle(f"CBR_{m_idx}_{page_idx}", parent=styles["Normal"], fontName="Helvetica", fontSize=f_sz, leading=f_lead, alignment=2, textColor=colors.black)
            cur_cell_center = ParagraphStyle(f"CBC_{m_idx}_{page_idx}", parent=styles["Normal"], fontName="Helvetica", fontSize=f_sz, leading=f_lead, alignment=1, textColor=colors.black)

            tot_cell_label = ParagraphStyle(f"TL_{m_idx}_{page_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=f_sz, leading=f_lead, alignment=0, textColor=colors.black)
            tot_cell_num = ParagraphStyle(f"TN_{m_idx}_{page_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=f_sz, leading=f_lead, alignment=2, textColor=colors.black)

            table_data = [header_row]
            row_heights = [h_hdr]
            table_styles = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#333333")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
            ]

            for idx, r in enumerate(chunk):
                s_no = cursor + idx + 1
                pct_val = float(r.get("calc_percentage", 0.0))
                row_bg_hex, row_fg_hex = get_gradient_color(pct_val)
                row_pct_style = ParagraphStyle(
                    f"RowPct_{s_no}_{cursor}_{idx}",
                    parent=styles["Normal"],
                    fontName="Helvetica-Bold",
                    fontSize=f_sz + 0.3,
                    leading=f_lead,
                    alignment=1,
                    textColor=colors.HexColor(row_fg_hex),
                )

                row_idx = len(table_data)
                row = [
                    Paragraph(str(s_no), cur_cell_center),
                    Paragraph(r.get("mandal", ""), cur_cell_left),
                    Paragraph(r.get("panchayat", ""), cur_cell_left),
                    Paragraph(format_indian_currency(r.get("demand_arrear", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("demand_current", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("demand_total", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("collection_arrear", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("collection_current", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("collection_total", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("balance_arrear", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("balance_current", 0)), cur_cell_right),
                    Paragraph(format_indian_currency(r.get("balance_total", 0)), cur_cell_right),
                    Paragraph(f"{pct_val:.1f}%", row_pct_style),
                ]
                table_data.append(row)
                row_heights.append(h_row)
                table_styles.append(("BACKGROUND", (12, row_idx), (12, row_idx), colors.HexColor(row_bg_hex)))

            if is_last_chunk_of_mandal:
                tot_idx = len(table_data)
                cur_total_row = [
                    Paragraph("", tot_cell_label),
                    Paragraph(f"{mandal_name} Total", tot_cell_label),
                    Paragraph("", tot_cell_label),
                    Paragraph(format_indian_currency(tot_d_arr), tot_cell_num),
                    Paragraph(format_indian_currency(tot_d_cur), tot_cell_num),
                    Paragraph(format_indian_currency(tot_d_tot), tot_cell_num),
                    Paragraph(format_indian_currency(tot_c_arr), tot_cell_num),
                    Paragraph(format_indian_currency(tot_c_cur), tot_cell_num),
                    Paragraph(format_indian_currency(tot_c_tot), tot_cell_num),
                    Paragraph(format_indian_currency(tot_b_arr), tot_cell_num),
                    Paragraph(format_indian_currency(tot_b_cur), tot_cell_num),
                    Paragraph(format_indian_currency(tot_b_tot), tot_cell_num),
                    Paragraph(f"{tot_pct_float:.1f}%", tot_pct_style),
                ]
                table_data.append(cur_total_row)
                row_heights.append(h_row)
                table_styles.append(("SPAN", (0, tot_idx), (1, tot_idx)))  # Span S.No and Mandal Name
                table_styles.append(("BACKGROUND", (12, tot_idx), (12, tot_idx), colors.HexColor(tot_bg_hex)))

            t = Table(table_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
            t.setStyle(TableStyle(table_styles))
            flowables.append(t)

            cursor += chunk_size

    if not flowables:
        flowables.append(Paragraph("No House Tax DCB records found for the selected filter.", title_style))

    doc.build(flowables, canvasmaker=NumberedCanvas)

    if isinstance(target, io.BytesIO):
        return target.getvalue()
    elif isinstance(target, (str, Path)):
        return Path(target).read_bytes()
    return buffer.getvalue()
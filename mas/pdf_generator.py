"""High-Density Vector ReportLab PDF Generator for MAS Consolidated Report.

Layout:
- A4 Landscape (841.89pt x 595.28pt)
- Dynamic Page 1 Fit: Single-page Mandal Abstract across all 18 modules + Overall %.
- Page 2+: GP-Wise Pending Action Plan Table (with 100%-compliant fallback card or optional omission in abstract_only mode).
- Canonical e-Panchayat Automation footer.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.branding import PLATFORM_NAME, TAGLINE
from mas.models import ALL_18_MODULES, normalize_district_and_slug

logger = logging.getLogger(__name__)

# Color Palette
CLR_HEADER_DARK = colors.HexColor("#0C3829")
CLR_HEADER_EXCL = colors.HexColor("#B45309")
CLR_OVERALL_COL = colors.HexColor("#065F46")
CLR_ZEBRA = colors.HexColor("#F8FAFC")
CLR_TOTAL_BG = colors.HexColor("#FEF3C7")
CLR_RED_BG = colors.HexColor("#FEE2E2")
CLR_RED_TXT = colors.HexColor("#991B1B")
CLR_GREEN_BG = colors.HexColor("#DCFCE7")
CLR_GREEN_TXT = colors.HexColor("#166534")
CLR_AMBER_BG = colors.HexColor("#FEF9C3")
CLR_AMBER_TXT = colors.HexColor("#92400E")
CLR_GRID = colors.HexColor("#CBD5E1")
CLR_DARK_TXT = colors.HexColor("#0F172A")


class NumberedCanvas(canvas.Canvas):
    """Canvas subclass appending Page X of Y and canonical platform footer cleanly."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count: int):
        width, _height = landscape(A4)
        self.saveState()
        self.setStrokeColor(CLR_GRID)
        self.setLineWidth(0.5)
        self.line(18, 22, width - 18, 22)
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#475569"))
        ts = datetime.now().strftime("%d-%b-%Y %I:%M %p")
        self.drawString(
            18,
            12,
            f"{PLATFORM_NAME} — {TAGLINE} | GM-R 5.24 + 5.23 Matrix ({ts})",
        )
        self.drawRightString(width - 18, 12, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def compute_mandal_abstract_table_layout(
    n_mandals: int,
    available_height_pt: float = 415.0,
) -> Dict[str, Any]:
    """Compute exact row height & font scaling so every district fits cleanly on Page 1."""
    n = max(1, int(n_mandals))
    row_h = min(19.0, max(10.5, (available_height_pt - 34.0) / (n + 1)))
    header_h = min(38.0, max(28.0, available_height_pt - (n + 1) * row_h))
    font_size = 7.8 if row_h >= 16.0 else (7.0 if row_h >= 13.0 else 6.2)
    return {
        "header_height": round(header_h, 2),
        "row_height": round(row_h, 2),
        "row_heights": [round(header_h, 2)] + [round(row_h, 2)] * (n + 1),
        "font_size": font_size,
        "compact": row_h < 13.5,
    }


def _completion_color(pct: float) -> colors.Color:
    if pct >= 100.0:
        return CLR_GREEN_TXT
    return CLR_RED_TXT


def generate_mas_consolidated_pdf(
    mandals_abstract: List[Dict[str, Any]],
    total_row: Dict[str, Any],
    pending_action_list: List[Dict[str, Any]],
    excluded_modules: List[str],
    output_path: Path,
    month: str = "July",
    year: int = 2026,
    district_name: str = "Khammam",
    include_gp_data: bool = True,
) -> Path:
    """Build A4 Landscape Consolidated PDF for MAS GM-R 5.24 + GM-R 5.23."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_district, _ = normalize_district_and_slug(district_name)

    page_w, page_h = landscape(A4)
    left_margin = 16
    right_margin = 16
    top_margin = 16
    bottom_margin = 28

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=f"{clean_district} District - MAS Consolidated Report ({month} {year})",
        author=PLATFORM_NAME,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "MasTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        textColor=colors.white,
        leading=15,
        alignment=TA_LEFT,
    )
    style_sub = ParagraphStyle(
        "MasSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.0,
        textColor=colors.HexColor("#D1FAE5"),
        leading=10,
        alignment=TA_LEFT,
    )
    style_kpi = ParagraphStyle(
        "MasKpi",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=CLR_DARK_TXT,
        leading=11,
        alignment=TA_CENTER,
    )
    style_th = ParagraphStyle(
        "MasTh",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.2,
        textColor=colors.white,
        leading=7.2,
        alignment=TA_CENTER,
    )
    style_th_left = ParagraphStyle(
        "MasThLeft",
        parent=style_th,
        alignment=TA_LEFT,
    )
    style_sec_hdr = ParagraphStyle(
        "MasSecHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=CLR_HEADER_DARK,
        leading=13,
    )
    style_cell_left = ParagraphStyle(
        "MasCellLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.4,
        textColor=CLR_DARK_TXT,
        leading=9.5,
        alignment=TA_LEFT,
    )
    style_cell_center = ParagraphStyle(
        "MasCellCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.4,
        textColor=CLR_DARK_TXT,
        leading=9.5,
        alignment=TA_CENTER,
    )

    usable_w = page_w - left_margin - right_margin
    excluded_set = set(excluded_modules or [])
    n_included = int(total_row.get("included_modules_count", len(ALL_18_MODULES) - len(excluded_set)))
    n_mandals = len(mandals_abstract)
    total_gps = int(total_row.get("No of GPs", 0))
    overall_pct = total_row.get("Overall % Entered", 0.0)
    tot_updated = int(total_row.get("No of Updated", 0))
    tot_fields = int(total_row.get("Total Fields", 0))
    pending_mandals_cnt = len(
        [
            m for m in mandals_abstract
            if any(
                (not m.get("modules", {}).get(lbl, {}).get("is_excluded", False))
                and int(m.get("modules", {}).get(lbl, {}).get("Not Entered", 0) or 0) > 0
                for lbl, _ in ALL_18_MODULES
            )
        ]
    )

    elements: List[Any] = []

    # ------------------------------------------------------------------
    # PAGE 1: Header Banner + KPI Summary + Full 18-Module Mandal Table
    # ------------------------------------------------------------------
    banner_tbl = Table(
        [
            [
                Paragraph(
                    f"<b>{clean_district} District - Monthly Activity Statement (MAS) Abstract ({month} {year})</b>",
                    style_title,
                ),
                Paragraph(
                    f"<b>Overall: {overall_pct}%</b><br/><font size='7'>GM-R 5.24 + GM-R 5.23</font>",
                    ParagraphStyle("BStat", parent=style_sub, alignment=TA_CENTER, fontSize=10, textColor=colors.white),
                ),
            ],
            [
                Paragraph(
                    "18-Indicator Executive Matrix (17 MAS Indicators + Birth Details)",
                    style_sub,
                ),
                "",
            ],
        ],
        colWidths=[usable_w - 130, 130],
    )
    banner_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CLR_HEADER_DARK),
                ("SPAN", (1, 0), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(banner_tbl)
    elements.append(Spacer(1, 5))

    # 5 KPI Cards Row
    if (not include_gp_data) and pending_mandals_cnt > 0:
        kpi5_label = f"<font color='#64748B' size='6.5'>PENDING STATUS</font><br/><font color='#B45309'><b>{pending_mandals_cnt} Mandals</b></font>"
    else:
        pending_gp_cnt = len(pending_action_list or [])
        kpi5_label = (
            f"<font color='#64748B' size='6.5'>PENDING ACTION GPs</font><br/><font color='#991B1B'><b>{pending_gp_cnt} Pending GPs</b></font>"
            if pending_gp_cnt > 0
            else "<font color='#64748B' size='6.5'>PENDING ACTION GPs</font><br/><font color='#166534'><b>0 (All Compliant)</b></font>"
        )

    kpi_cells = [
        Paragraph(f"<font color='#64748B' size='6.5'>DISTRICT OVERALL %</font><br/><font color='#065F46'><b>{overall_pct}%</b></font>", style_kpi),
        Paragraph(f"<font color='#64748B' size='6.5'>UPDATED / TOTAL FIELDS</font><br/><b>{tot_updated:,} / {tot_fields:,}</b>", style_kpi),
        Paragraph(f"<font color='#64748B' size='6.5'>DISTRICT COVERAGE</font><br/><b>{n_mandals} Mandals · {total_gps:,} GPs</b>", style_kpi),
        Paragraph(f"<font color='#64748B' size='6.5'>INCLUDED MODULE BASE</font><br/><b>{n_included} / 18 Modules</b>", style_kpi),
        Paragraph(kpi5_label, style_kpi),
    ]
    kpi_tbl = Table([kpi_cells], colWidths=[usable_w / 5.0] * 5, rowHeights=[28])
    kpi_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.7, CLR_GRID),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, CLR_GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(kpi_tbl)
    elements.append(Spacer(1, 5))

    # Full 18-Module Table (22 Columns)
    layout = compute_mandal_abstract_table_layout(n_mandals)
    font_sz = layout["font_size"]

    short_labels = {
        "Nursery": "Nursery",
        "Plantation": "Plant.",
        "Vaikunta Dhamam": "Vaikunta<br/>Dhamam",
        "Dump Yard": "Dump<br/>Yard",
        "Water Supply": "Water<br/>Supply",
        "GP Meetings": "GP<br/>Meet.",
        "Gram Sabha": "Gram<br/>Sabha",
        "Record Maintenance": "Record<br/>Maint.",
        "Approvals and Certificates": "Approv.<br/>& Cert.",
        "Deaths": "Deaths",
        "Recipts": "Receipts",
        "Expenditure": "Expend.",
        "Cheque Details": "Cheque<br/>Details",
        "Salary Details": "Salary<br/>Details",
        "VWSC Bank Balance": "VWSC<br/>Bal.",
        "MGNRE Bank Balance": "MGNRE<br/>Bal.",
        "Payment of Electricity": "CC<br/>Charges",
        "Birth Details": "Birth<br/>Details",
    }

    header_row = [
        Paragraph("S<br/>No", style_th),
        Paragraph("Mandal Name", style_th_left),
        Paragraph("GPs", style_th),
        Paragraph(f"Overall<br/>% ({n_included})", style_th),
    ]
    for label, _ in ALL_18_MODULES:
        sl = short_labels.get(label, label)
        if label in excluded_set:
            header_row.append(Paragraph(f"{sl}<br/><font size='5' color='#FEF08A'>[Excl]</font>", style_th))
        else:
            header_row.append(Paragraph(sl, style_th))

    table_rows: List[List[Any]] = [header_row]
    for m in mandals_abstract:
        row: List[Any] = [
            str(m.get("S No", "")),
            str(m.get("Mandal Name", "")),
            str(m.get("No of GPs", "")),
            f"{m.get('Overall % Entered', 0)}%",
        ]
        mods = m.get("modules", {})
        for label, _ in ALL_18_MODULES:
            row.append(mods.get(label, {}).get("formatted_compact", "-"))
        table_rows.append(row)

    # District Total Row
    t_row: List[Any] = [
        "Tot",
        "District Total",
        str(total_row.get("No of GPs", "")),
        f"{total_row.get('Overall % Entered', 0)}%",
    ]
    t_mods = total_row.get("modules", {})
    for label, _ in ALL_18_MODULES:
        t_row.append(t_mods.get(label, {}).get("formatted_compact", "-"))
    table_rows.append(t_row)

    # Column widths summing strictly to usable_w (~809.89 pt)
    fixed_w = [22, 82, 24, 42]  # = 170 pt
    remaining_w = usable_w - sum(fixed_w)
    mod_col_w = remaining_w / 18.0
    col_widths = fixed_w + [mod_col_w] * 18

    abstract_tbl = Table(table_rows, colWidths=col_widths, rowHeights=layout["row_heights"], repeatRows=1)

    tbl_cmds: List[Tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), CLR_HEADER_DARK),
        ("BACKGROUND", (3, 0), (3, 0), CLR_OVERALL_COL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTNAME", (1, 1), (1, -2), "Helvetica-Bold"),
        ("FONTNAME", (3, 1), (3, -2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), font_sz),
        ("GRID", (0, 0), (-1, -1), 0.4, CLR_GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        # Total Row styling
        ("BACKGROUND", (0, -1), (-1, -1), CLR_TOTAL_BG),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1.3, CLR_DARK_TXT),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, CLR_DARK_TXT),
    ]

    # Zebra striping + conditional red text & colors on Pending rows/cells & Excluded module columns
    for r_idx, m in enumerate(mandals_abstract, start=1):
        if r_idx % 2 == 0:
            tbl_cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), CLR_ZEBRA))
        pct_val = float(m.get("Overall % Entered", 100.0))
        mods = m.get("modules", {})
        row_has_pending = pct_val < 100.0 or any(
            (lbl not in excluded_set) and int((mods.get(lbl) or {}).get("Not Entered", 0) or 0) > 0
            for lbl, _ in ALL_18_MODULES
        )
        if row_has_pending:
            tbl_cmds.append(("TEXTCOLOR", (0, r_idx), (1, r_idx), CLR_RED_TXT))
            tbl_cmds.append(("TEXTCOLOR", (3, r_idx), (3, r_idx), CLR_RED_TXT))
        else:
            tbl_cmds.append(("TEXTCOLOR", (3, r_idx), (3, r_idx), _completion_color(pct_val)))

        for m_idx, (label, _) in enumerate(ALL_18_MODULES):
            c_idx = 4 + m_idx
            mod_data = mods.get(label, {})
            is_excl = label in excluded_set
            not_ent = int(mod_data.get("Not Entered", 0) or 0)
            if is_excl:
                tbl_cmds.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), CLR_AMBER_BG))
                tbl_cmds.append(("TEXTCOLOR", (c_idx, r_idx), (c_idx, r_idx), CLR_AMBER_TXT))
            elif not_ent > 0:
                tbl_cmds.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), CLR_RED_BG))
                tbl_cmds.append(("TEXTCOLOR", (c_idx, r_idx), (c_idx, r_idx), CLR_RED_TXT))
                tbl_cmds.append(("FONTNAME", (c_idx, r_idx), (c_idx, r_idx), "Helvetica-Bold"))

    # Highlight excluded headers and total cells (plus red text for any pending in Total row)
    tot_pct_val = float(total_row.get("Overall % Entered", 100.0))
    tot_has_pending = tot_pct_val < 100.0 or any(
        (lbl not in excluded_set) and int((t_mods.get(lbl) or {}).get("Not Entered", 0) or 0) > 0
        for lbl, _ in ALL_18_MODULES
    )
    tbl_cmds.append(("TEXTCOLOR", (3, -1), (3, -1), CLR_RED_TXT if tot_has_pending else CLR_GREEN_TXT))
    for m_idx, (label, _) in enumerate(ALL_18_MODULES):
        c_idx = 4 + m_idx
        if label in excluded_set:
            tbl_cmds.append(("BACKGROUND", (c_idx, 0), (c_idx, 0), CLR_HEADER_EXCL))
            tbl_cmds.append(("BACKGROUND", (c_idx, -1), (c_idx, -1), colors.HexColor("#FDE68A")))
            tbl_cmds.append(("TEXTCOLOR", (c_idx, -1), (c_idx, -1), CLR_AMBER_TXT))
        elif int((t_mods.get(label) or {}).get("Not Entered", 0) or 0) > 0:
            tbl_cmds.append(("TEXTCOLOR", (c_idx, -1), (c_idx, -1), CLR_RED_TXT))

    abstract_tbl.setStyle(TableStyle(tbl_cmds))
    elements.append(abstract_tbl)

    # ------------------------------------------------------------------
    # PAGE 2+: GP-Wise Pending Action List (when include_gp_data is True)
    # ------------------------------------------------------------------
    if include_gp_data:
        elements.append(PageBreak())
        p_count = len(pending_action_list)
        sec_banner = Table(
            [
                [
                    Paragraph(
                        f"GP-Wise Pending Action Plan — {clean_district} District ({month} {year})",
                        ParagraphStyle("PHdr", parent=style_sec_hdr, textColor=colors.white),
                    ),
                    Paragraph(
                        f"<b>{p_count} Action GP(s)</b>",
                        ParagraphStyle("PCnt", parent=style_sub, alignment=TA_CENTER, fontSize=9.5, textColor=colors.white),
                    ),
                ]
            ],
            colWidths=[usable_w - 130, 130],
        )
        sec_banner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CLR_HEADER_DARK if p_count == 0 else colors.HexColor("#991B1B")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(sec_banner)
        elements.append(Spacer(1, 8))

        if p_count == 0:
            ok_card = Table(
                [
                    [
                        Paragraph(
                            f"<b>100% FULLY COMPLIANT — ZERO PENDING GPs</b><br/>"
                            f"<font size='8.5' color='#166534'>All {total_gps:,} Gram Panchayats across {n_mandals} Mandals have completed entry for all {n_included} included modules in {month} {year}.</font>",
                            ParagraphStyle("OkMsg", parent=style_kpi, fontSize=11, textColor=CLR_GREEN_TXT, leading=16),
                        )
                    ]
                ],
                colWidths=[usable_w],
                rowHeights=[70],
            )
            ok_card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), CLR_GREEN_BG),
                        ("BOX", (0, 0), (-1, -1), 1.2, CLR_GREEN_TXT),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            elements.append(ok_card)
        else:
            p_header = [
                Paragraph("S No", style_th),
                Paragraph("Mandal", style_th_left),
                Paragraph("Gram Panchayat", style_th_left),
                Paragraph("Pending Count", style_th),
                Paragraph("Pending Module(s)", style_th_left),
                Paragraph(f"Completed / {n_included}", style_th),
                Paragraph("Completion %", style_th),
                Paragraph("Action Required", style_th_left),
            ]
            p_rows: List[List[Any]] = [p_header]
            for idx, item in enumerate(pending_action_list, start=1):
                p_rows.append(
                    [
                        Paragraph(str(idx), style_cell_center),
                        Paragraph(f"<b>{item.get('Mandal', '')}</b>", style_cell_left),
                        Paragraph(f"<b>{item.get('Gram_Panchayat', '')}</b>", style_cell_left),
                        Paragraph(f"<font color='#991B1B'><b>{item.get('Pending_Count', 0)} Pending</b></font>", style_cell_center),
                        Paragraph(str(item.get("Pending_Modules", "")), style_cell_left),
                        Paragraph(f"{item.get('Completed_Count', 0)} / {n_included}", style_cell_center),
                        Paragraph(f"<b>{item.get('Completion_Rate', '0%')}</b>", style_cell_center),
                        Paragraph(str(item.get("Action_Required", "Immediate follow-up by MPO / PS")), style_cell_left),
                    ]
                )

            p_widths = [28, 86, 122, 60, 270, 56, 56, usable_w - 678]
            p_tbl = Table(p_rows, colWidths=p_widths, repeatRows=1)
            p_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), CLR_HEADER_DARK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.45, CLR_GRID),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
            for r_idx in range(1, len(p_rows)):
                if r_idx % 2 == 0:
                    p_cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), CLR_ZEBRA))
            p_tbl.setStyle(TableStyle(p_cmds))
            elements.append(p_tbl)

    doc.build(elements, canvasmaker=NumberedCanvas)
    logger.info("[+] Generated MAS Consolidated PDF (%d mandals, %d pending GPs): %s", n_mandals, len(pending_action_list or []), output_path)
    return output_path

"""PDF, Excel, and CSV generators for the Multi-Days DSR Module (no graphs)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.branding import PLATFORM_NAME, TAGLINE, apply_openpyxl_branding
from multiday_dsr.processor import MultiDayDsrResult, classify_time_style, highlight_percentage

_NAVY = HexColor("#0c3829")
_SLATE = HexColor("#1e293b")
_MUTED = HexColor("#475569")
_ALT_ROW = HexColor("#f8fafc")
_BORDER = HexColor("#cbd5e1")
_HEADER_FILL = HexColor("#0f4c3a")

_THIN_SIDE = Side(style="thin", color="CBD5E1")
_EXCEL_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)


def _fmt_cell(val: Any, is_pct: bool = False) -> str:
    if pd.isna(val):
        return ""
    if is_pct:
        try:
            return f"{float(val):.2f}%"
        except Exception:
            return str(val)
    return str(val)


def _df_to_pdf_table(
    df: pd.DataFrame,
    col_widths: list[float],
    pct_cols: set[str],
    left_cols: set[str],
    styles: dict[str, ParagraphStyle],
    time_cols: set[str] | None = None,
) -> Table:
    cols = list(df.columns)
    t_cols = time_cols or set()
    hdr_row = [Paragraph(html.escape(c), styles["th"]) for c in cols]
    data: list[list[Any]] = [hdr_row]
    ts_cmds: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("REPEATROWS", (0, 0), (-1, 0)),
    ]

    for r_idx, (_, row) in enumerate(df.iterrows(), start=1):
        bg_row = _ALT_ROW if r_idx % 2 == 0 else colors.white
        ts_cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), bg_row))
        cells = []
        for c_idx, col_name in enumerate(cols):
            val = row[col_name]
            is_pct = col_name in pct_cols
            txt = html.escape(_fmt_cell(val, is_pct=is_pct))
            if col_name == "Before 9 AM %":
                hl = highlight_percentage(val)
                if hl["bg"]:
                    ts_cmds.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), HexColor(hl["bg"])))
                p_style = ParagraphStyle(
                    f"pct_{r_idx}_{c_idx}",
                    parent=styles["td_c"],
                    textColor=HexColor(hl["fg"]),
                    fontName="Helvetica-Bold",
                )
                cells.append(Paragraph(txt, p_style))
            elif col_name in t_cols:
                st = classify_time_style(val)
                if st["bg"]:
                    ts_cmds.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), HexColor(st["bg"])))
                p_style = ParagraphStyle(
                    f"tm_{r_idx}_{c_idx}",
                    parent=styles["td_c"],
                    textColor=HexColor(st["fg"]),
                    fontName="Helvetica-Bold" if col_name == "Average Time" else "Helvetica",
                )
                cells.append(Paragraph(txt, p_style))
            elif col_name in left_cols:
                cells.append(Paragraph(txt, styles["td_l"]))
            else:
                cells.append(Paragraph(txt, styles["td_c"]))
        data.append(cells)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(ts_cmds))
    return tbl


def generate_multiday_dsr_pdf(
    result: MultiDayDsrResult,
    output_path: str | Path,
    include_time_matrix: bool = True,
) -> Path:
    """Compile colorful Landscape A4 Multi-Days DSR PDF (no graphs) with abstract + optional exact time matrix."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, _ = landscape(A4)
    usable_w = page_w - 20 * mm

    styles = {
        "banner_title": ParagraphStyle(
            "banner_title", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=colors.white, alignment=TA_LEFT
        ),
        "banner_sub": ParagraphStyle(
            "banner_sub", fontName="Helvetica", fontSize=8.5, leading=11, textColor=HexColor("#d1fae5"), alignment=TA_LEFT
        ),
        "sec": ParagraphStyle(
            "sec", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=_NAVY, spaceBefore=6, spaceAfter=4
        ),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8, leading=10, textColor=_MUTED),
        "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.white, alignment=TA_CENTER),
        "td_c": ParagraphStyle("td_c", fontName="Helvetica", fontSize=7, leading=8.5, textColor=_SLATE, alignment=TA_CENTER),
        "td_l": ParagraphStyle("td_l", fontName="Helvetica", fontSize=7, leading=8.5, textColor=_SLATE, alignment=TA_LEFT),
    }

    def _draw_footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        canvas.drawString(10 * mm, 6 * mm, f"{PLATFORM_NAME} — {TAGLINE}")
        canvas.drawRightString(page_w - 10 * mm, 6 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=12 * mm,
        title=f"Multi-Days DSR Report - {result.dist_name}",
    )

    gen_str = result.generated_at.strftime("%d-%m-%Y %I:%M %p")
    banner = Table(
        [
            [Paragraph(f"MULTIPLE DAYS PS ATTENDANCE & DSR ABSTRACT — {html.escape(result.dist_name.upper())}", styles["banner_title"])],
            [Paragraph(
                f"Period: {html.escape(result.start_date)} to {html.escape(result.end_date)}  |  "
                f"Reporting Days: {result.total_reporting_days}  |  Mandals: {result.mandal_count}  |  Total GPs: {result.total_gps}  |  "
                f"Report Generated On: {html.escape(gen_str)}",
                styles["banner_sub"],
            )],
        ],
        colWidths=[usable_w],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story: list[Any] = [banner, Spacer(1, 6)]

    # 1. District Level (Date-Wise) — 14 columns
    story.append(Paragraph("1. District Level — Date-Wise Attendance & DSR Summary", styles["sec"]))
    dist_widths = [
        usable_w * r
        for r in (0.04, 0.085, 0.07, 0.075, 0.065, 0.065, 0.065, 0.065, 0.075, 0.075, 0.075, 0.075, 0.085, 0.085)
    ]
    story.append(
        _df_to_pdf_table(
            result.district,
            dist_widths,
            pct_cols={"Before 9 AM %", "After 9 AM %"},
            left_cols=set(),
            styles=styles,
        )
    )
    story.append(PageBreak())

    # 2. Mandal Level (Mandal + Date-Wise) — 15 columns
    story.append(Paragraph("2. Mandal Level — Mandal & Date-Wise Attendance & DSR Summary", styles["sec"]))
    mandal_widths = [
        usable_w * r
        for r in (0.038, 0.125, 0.078, 0.06, 0.068, 0.06, 0.058, 0.058, 0.058, 0.065, 0.065, 0.065, 0.065, 0.068, 0.069)
    ]
    story.append(
        _df_to_pdf_table(
            result.mandal,
            mandal_widths,
            pct_cols={"Before 9 AM %", "After 9 AM %"},
            left_cols={"Mandal Name"},
            styles=styles,
        )
    )
    story.append(PageBreak())

    # 3. GP Level (Period Summary) — 15 columns
    story.append(Paragraph("3. Gram Panchayat Level — Period Attendance & DSR Summary", styles["sec"]))
    gp_widths = [
        usable_w * r
        for r in (0.036, 0.105, 0.115, 0.062, 0.065, 0.055, 0.055, 0.055, 0.055, 0.065, 0.065, 0.065, 0.065, 0.068, 0.069)
    ]
    story.append(
        _df_to_pdf_table(
            result.gp_summary,
            gp_widths,
            pct_cols={"Before 9 AM %", "After 9 AM %"},
            left_cols={"Mandal Name", "Panchayat Name"},
            styles=styles,
        )
    )

    # 4. Day-Wise Exact Attendance Time + Status Counts + Average Time & No. of Days Before 9 AM
    if include_time_matrix and not result.time_matrix.empty:
        tm_df = result.time_matrix
        fixed_left = ["S.No", "Mandal Name", "Panchayat Name"]
        summary_right = [
            "Present",
            "On Leave",
            "Not Marked Attendance",
            "Training / Meeting",
            "Average Time",
            "No. of Days Before 9 AM",
        ]
        date_cols = [c for c in tm_df.columns if c not in fixed_left and c not in summary_right]
        chunk_size = 10
        date_chunks = [date_cols[i : i + chunk_size] for i in range(0, max(1, len(date_cols)), chunk_size)] or [[]]

        for slice_idx, d_chunk in enumerate(date_chunks, start=1):
            story.append(PageBreak())
            suffix = f" (Part {slice_idx}/{len(date_chunks)})" if len(date_chunks) > 1 else ""
            story.append(
                Paragraph(
                    f"4. Gram Panchayat Day-Wise Exact Attendance Time, Status Counts, Average Time & Before 9 AM Days{suffix}",
                    styles["sec"],
                )
            )
            sub_cols = fixed_left + d_chunk + summary_right
            sub_df = tm_df[sub_cols]
            w_sno = usable_w * 0.032
            w_mandal = usable_w * 0.095
            w_gp = usable_w * 0.11
            w_cnt = usable_w * 0.048  # x4 = 0.192
            w_avg = usable_w * 0.055
            w_b9 = usable_w * 0.058
            rem_w = usable_w - (w_sno + w_mandal + w_gp + w_cnt * 4 + w_avg + w_b9)
            w_day = rem_w / max(1, len(d_chunk)) if d_chunk else 0
            sub_widths = (
                [w_sno, w_mandal, w_gp]
                + [w_day] * len(d_chunk)
                + [w_cnt, w_cnt, w_cnt, w_cnt, w_avg, w_b9]
            )
            story.append(
                _df_to_pdf_table(
                    sub_df,
                    sub_widths,
                    pct_cols=set(),
                    left_cols={"Mandal Name", "Panchayat Name"},
                    styles=styles,
                    time_cols=set(d_chunk) | {"Average Time"},
                )
            )

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return out


def _write_styled_sheet(
    ws: Any,
    title: str,
    subtitle: str,
    df: pd.DataFrame,
    pct_cols: set[str],
    left_cols: set[str],
    time_cols: set[str] | None = None,
) -> None:
    cols = list(df.columns)
    max_col = max(1, len(cols))

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_col)
    c1 = ws.cell(row=1, column=1, value=title)
    c1.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    c1.fill = PatternFill(start_color="0C3829", end_color="0C3829", fill_type="solid")
    c1.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_col)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = Font(name="Calibri", size=10, italic=True, color="1E293B")
    c2.fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    c2.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 19

    hdr_row_idx = 4
    ws.row_dimensions[hdr_row_idx].height = 24
    for col_idx, col_name in enumerate(cols, start=1):
        cell = ws.cell(row=hdr_row_idx, column=col_idx, value=col_name)
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="0F4C3A", end_color="0F4C3A", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _EXCEL_BORDER

    for r_offset, (_, row) in enumerate(df.iterrows(), start=1):
        excel_row = hdr_row_idx + r_offset
        row_bg = "F8FAFC" if r_offset % 2 == 0 else "FFFFFF"
        for col_idx, col_name in enumerate(cols, start=1):
            val = row[col_name]
            clean_val = "" if pd.isna(val) else val.item() if hasattr(val, "item") else val
            cell = ws.cell(row=excel_row, column=col_idx, value=clean_val)
            cell.border = _EXCEL_BORDER
            cell.alignment = Alignment(
                horizontal="left" if col_name in left_cols else "center",
                vertical="center",
            )
            if col_name == "Before 9 AM %":
                hl = highlight_percentage(clean_val)
                bg_hex = hl["bg"].lstrip("#") if hl["bg"] else row_bg
                fg_hex = hl["fg"].lstrip("#")
                cell.fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
                cell.font = Font(name="Calibri", size=10, bold=True, color=fg_hex)
                cell.number_format = "0.00"
            elif col_name in (time_cols or set()):
                st = classify_time_style(clean_val)
                bg_hex = st["bg"].lstrip("#") if st["bg"] else row_bg
                fg_hex = st["fg"].lstrip("#")
                cell.fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
                cell.font = Font(name="Calibri", size=10, bold=(col_name == "Average Time"), color=fg_hex)
            elif col_name in pct_cols:
                cell.fill = PatternFill(start_color=row_bg, end_color=row_bg, fill_type="solid")
                cell.font = Font(name="Calibri", size=10, color="1E293B")
                cell.number_format = "0.00"
            else:
                cell.fill = PatternFill(start_color=row_bg, end_color=row_bg, fill_type="solid")
                cell.font = Font(name="Calibri", size=10, color="1E293B")

    ws.freeze_panes = f"A{hdr_row_idx + 1}"
    for col_idx, col_name in enumerate(cols, start=1):
        max_len = max([len(str(col_name))] + [len(str(v)) for v in df[col_name].head(60).tolist()])
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 4, 11), 36)


def generate_multiday_dsr_excel(
    result: MultiDayDsrResult,
    output_path: str | Path,
    include_time_matrix: bool = True,
) -> Path:
    """Create Multi-Days DSR Excel workbook with highlight_percentage & optional Day-Wise Exact Time."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    gen_str = result.generated_at.strftime("%d-%m-%Y %I:%M %p")
    subtitle = (
        f"District: {result.dist_name} | Period: {result.start_date} to {result.end_date} | "
        f"Days: {result.total_reporting_days} | Mandals: {result.mandal_count} | "
        f"Total GPs: {result.total_gps} | Generated On: {gen_str}"
    )

    ws_dist = wb.active
    ws_dist.title = "District Level"
    _write_styled_sheet(
        ws_dist,
        f"District Level — Date-Wise Attendance & DSR ({result.dist_name})",
        subtitle,
        result.district,
        pct_cols={"Before 9 AM %", "After 9 AM %"},
        left_cols=set(),
    )

    ws_mandal = wb.create_sheet("Mandal Level")
    _write_styled_sheet(
        ws_mandal,
        f"Mandal Level — Mandal & Date-Wise Attendance & DSR ({result.dist_name})",
        subtitle,
        result.mandal,
        pct_cols={"Before 9 AM %", "After 9 AM %"},
        left_cols={"Mandal Name"},
    )

    ws_gp = wb.create_sheet("GP Level Summary")
    _write_styled_sheet(
        ws_gp,
        f"GP Level — Period Attendance & DSR Summary ({result.dist_name})",
        subtitle,
        result.gp_summary,
        pct_cols={"Before 9 AM %", "After 9 AM %"},
        left_cols={"Mandal Name", "Panchayat Name"},
    )

    if include_time_matrix and not result.time_matrix.empty:
        tm_df = result.time_matrix
        fixed_cols = {
            "S.No",
            "Mandal Name",
            "Panchayat Name",
            "Present",
            "On Leave",
            "Not Marked Attendance",
            "Training / Meeting",
            "No. of Days Before 9 AM",
        }
        t_cols = {c for c in tm_df.columns if c not in fixed_cols}
        ws_tm = wb.create_sheet("Day-Wise Exact Time")
        _write_styled_sheet(
            ws_tm,
            f"Day-Wise Exact Attendance Time, Average Time & Before 9 AM Days ({result.dist_name})",
            subtitle,
            tm_df,
            pct_cols=set(),
            left_cols={"Mandal Name", "Panchayat Name"},
            time_cols=t_cols,
        )

    ws_master = wb.create_sheet("Master Data")
    _write_styled_sheet(
        ws_master,
        f"Master Raw Source Data ({result.dist_name})",
        subtitle,
        result.master_data,
        pct_cols=set(),
        left_cols={"District Name", "Mandal Name", "Panchayat Name"},
    )

    apply_openpyxl_branding(wb)
    wb.save(out)
    return out


def generate_multiday_dsr_csv(result: MultiDayDsrResult, level: str = "district") -> bytes:
    """Serialize requested Multi-Days DSR table (`district`, `mandal`, `gp`, `time_matrix`, `master`) as UTF-8 CSV."""
    key = (level or "district").strip().lower()
    if key == "mandal":
        df = result.mandal
    elif key in ("gp", "gp_summary"):
        df = result.gp_summary
    elif key in ("time_matrix", "exact_time", "time"):
        df = result.time_matrix
    elif key == "master":
        df = result.master_data
    else:
        df = result.district
    return df.to_csv(index=False).encode("utf-8-sig")

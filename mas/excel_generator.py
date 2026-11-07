"""Excel Workbook Generator for Monthly Activity Statement (MAS) and Births Register Module.

Produces a formatted, executive multi-sheet workbook matching Telangana PR&RD departmental standards:
  - Sheet 1: GM-R_5.24_MAS_Summary (The exact 58-column Two-Tier Executive Matrix with 18 indicators,
             Entered / Not Entered / % Entered triplets, Executive Navy headers, and Refined Indicator Highlights)
  - Sheet 2: GM-R_5.23_Births_Register (Total GPs, Entered, Not Entered, Total Births, % Achievement)
  - Sheet 3: Pending_GPs_Action_List (Actionable 4-column call-list of exact GPs and missing activities)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from mas.models import (
    OFFICIAL_MAS_REPORT_ACTIVITIES,
    DistrictMASReport,
    GPMASDetail,
    normalize_activity_key,
)


def format_pending_activities(gp: GPMASDetail) -> str:
    """Formats pending activities list into a single comma-separated line combining MAS & Births."""
    if not gp.missing_activities:
        if not gp.entered:
            return "All Monthly Activities & Births Register Not Entered"
        return "Data Entry Pending Review"

    formatted: list[str] = []
    has_birth = False
    for act in gp.missing_activities:
        norm = normalize_activity_key(act)
        if norm == "Birth details":
            has_birth = True
        else:
            formatted.append(act)

    if has_birth:
        formatted.append("Births Register")

    if len(formatted) == 1 and formatted[0] == "Births Register":
        return "Births Register Data Entry Pending"

    if len(formatted) >= 18:
        return "All Monthly Activities & Births Register Not Entered"

    return ", ".join(formatted)


def _style_range(ws, min_col, min_row, max_col, max_row, font=None, fill=None, border=None, alignment=None):
    """Applies styles to every cell in a range including merged cells."""
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            if font:
                cell.font = font
            if fill:
                cell.fill = fill
            if border:
                cell.border = border
            if alignment:
                cell.alignment = alignment


def generate_mas_excel(report: DistrictMASReport, output_path: Optional[Path] = None) -> bytes:
    """Generates an executive multi-sheet Excel workbook for MAS & Births reporting."""
    wb = Workbook()

    # -------------------------------------------------------------------------
    # EXECUTIVE INSTITUTIONAL DESIGN SYSTEM
    # -------------------------------------------------------------------------
    # Typography
    font_title = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=9.5, color="E2E8F0")
    font_hdr_tier1 = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_overall_hdr = Font(name="Calibri", size=10, bold=True, color="FCD34D")  # Warm Gold
    font_sub_hdr = Font(name="Calibri", size=9, bold=True, color="334155")
    font_pct_hdr = Font(name="Calibri", size=9, bold=True, color="1E40AF")

    font_data = Font(name="Calibri", size=9.5, color="0F172A")
    font_data_bold = Font(name="Calibri", size=9.5, bold=True, color="0F172A")
    font_total = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_total_gold = Font(name="Calibri", size=10, bold=True, color="FCD34D")

    # Header Fills
    fill_navy = PatternFill(start_color="0F2942", end_color="0F2942", fill_type="solid")        # Deep Midnight Navy
    fill_sub_hdr = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")      # Clean Light Slate
    fill_pct_hdr = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")      # Soft Sky Blue

    # Data Rows Alternating Zebra
    fill_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    fill_odd = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    # Refined Indicator Badges (Soft Tints with Dark Readable Text)
    fill_green = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")        # Soft Emerald (100%)
    font_green = Font(name="Calibri", size=9.5, bold=True, color="065F46")

    fill_amber = PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid")        # Soft Warm Amber (>0% and <100%)
    font_amber = Font(name="Calibri", size=9.5, bold=True, color="92400E")

    fill_red = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")          # Soft Rose (0%)
    font_red = Font(name="Calibri", size=9.5, bold=True, color="991B1B")

    fill_ovr = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")          # Soft Blue
    font_ovr = Font(name="Calibri", size=9.5, bold=True, color="1E40AF")

    fill_total = PatternFill(start_color="0F2942", end_color="0F2942", fill_type="solid")        # Deep Midnight Navy

    # Borders
    thin = Side(border_style="thin", color="CBD5E1")
    border_cell = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_total = Border(
        left=thin,
        right=thin,
        top=Side(border_style="thin", color="0F2942"),
        bottom=Side(border_style="double", color="0F2942"),
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    clean_dist = (report.district_name or "").strip()
    if clean_dist.upper().endswith("DISTRICT"):
        clean_dist = clean_dist[:-8].strip()
    dist_suffix = f" — {clean_dist.upper()} DISTRICT" if clean_dist and clean_dist.lower() != "district" else ""

    # =========================================================================
    # SHEET 1: GM-R 5.24 MAS EXECUTIVE TWO-TIER SUMMARY (58 COLUMNS)
    # =========================================================================
    ws1 = wb.active
    ws1.title = "GM-R_5.24_MAS_Summary"
    ws1.views.sheetView[0].showGridLines = True

    total_cols = 4 + (len(OFFICIAL_MAS_REPORT_ACTIVITIES) * 3)  # 4 base + 18*3 = 58 columns
    max_col_letter = get_column_letter(total_cols)

    # Title & Metadata Banner
    ws1.merge_cells(f"A1:{max_col_letter}1")
    t1 = ws1["A1"]
    t1.value = f"MONTHLY ACTIVITY STATEMENT (GM-R 5.24) & BIRTHS REGISTER (GM-R 5.23) REPORT{dist_suffix}"
    t1.font = font_title
    t1.fill = fill_navy
    t1.alignment = align_center
    ws1.row_dimensions[1].height = 26
    _style_range(ws1, 1, 1, total_cols, 1, font=font_title, fill=fill_navy, alignment=align_center)

    ws1.merge_cells(f"A2:{max_col_letter}2")
    t2 = ws1["A2"]
    t2.value = (
        f"REPORTING YEAR: {report.financial_year} | "
        f"MONTH: {report.month_name} | "
        f"GENERATED: {report.generated_at}"
    )
    t2.font = font_sub
    t2.fill = fill_navy
    t2.alignment = align_center
    ws1.row_dimensions[2].height = 20
    _style_range(ws1, 1, 2, total_cols, 2, font=font_sub, fill=fill_navy, alignment=align_center)

    ws1.row_dimensions[3].height = 6  # Spacer row

    # -------------------------------------------------------------------------
    # TWO-TIER TABLE HEADERS (Rows 4 and 5)
    # -------------------------------------------------------------------------
    ws1.row_dimensions[4].height = 28
    ws1.row_dimensions[5].height = 22

    # Col 1: S.No (merged A4:A5)
    ws1.merge_cells("A4:A5")
    ws1["A4"] = "S.No"
    _style_range(ws1, 1, 4, 1, 5, font=font_hdr_tier1, fill=fill_navy, border=border_cell, alignment=align_center)

    # Col 2: Mandal Name (merged B4:B5)
    ws1.merge_cells("B4:B5")
    ws1["B4"] = "Mandal Name"
    _style_range(ws1, 2, 4, 2, 5, font=font_hdr_tier1, fill=fill_navy, border=border_cell, alignment=align_center)

    # Col 3: No of GPs (merged C4:C5)
    ws1.merge_cells("C4:C5")
    ws1["C4"] = "No of GPs"
    _style_range(ws1, 3, 4, 3, 5, font=font_hdr_tier1, fill=fill_navy, border=border_cell, alignment=align_center)

    # Col 4: Overall % Entered (merged D4:D5)
    ws1.merge_cells("D4:D5")
    ws1["D4"] = "Overall % Entered"
    _style_range(ws1, 4, 4, 4, 5, font=font_overall_hdr, fill=fill_navy, border=border_cell, alignment=align_center)

    # Columns 5 to 58: 18 Activities with 3 sub-columns each
    for act_idx, act_name in enumerate(OFFICIAL_MAS_REPORT_ACTIVITIES):
        start_c = 5 + (act_idx * 3)
        end_c = start_c + 2

        # Tier 1 Header (Activity Name merged across 3 columns)
        ws1.merge_cells(start_row=4, start_column=start_c, end_row=4, end_column=end_c)
        ws1.cell(row=4, column=start_c, value=act_name)
        _style_range(ws1, start_c, 4, end_c, 4, font=font_hdr_tier1, fill=fill_navy, border=border_cell, alignment=align_center)

        # Tier 2 Sub-headers (Entered, Not Entered, % Entered)
        c_ent = ws1.cell(row=5, column=start_c, value="Entered")
        c_ent.font = font_sub_hdr
        c_ent.fill = fill_sub_hdr
        c_ent.border = border_cell
        c_ent.alignment = align_center

        c_not = ws1.cell(row=5, column=start_c + 1, value="Not Entered")
        c_not.font = font_sub_hdr
        c_not.fill = fill_sub_hdr
        c_not.border = border_cell
        c_not.alignment = align_center

        # Refined Soft Sky Blue fill for % Entered column
        c_pct = ws1.cell(row=5, column=start_c + 2, value="% Entered")
        c_pct.font = font_pct_hdr
        c_pct.fill = fill_pct_hdr
        c_pct.border = border_cell
        c_pct.alignment = align_center

    # -------------------------------------------------------------------------
    # DATA ROWS (Row 6 onwards)
    # -------------------------------------------------------------------------
    current_row = 6
    clean_mandals = [m for m in report.mandals if m.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")]

    for m_idx, m in enumerate(clean_mandals):
        ws1.row_dimensions[current_row].height = 20
        row_bg = fill_even if m_idx % 2 == 0 else fill_odd

        # Col 1: S.No
        c_sno = ws1.cell(row=current_row, column=1, value=m.s_no)
        c_sno.font = font_data
        c_sno.fill = row_bg
        c_sno.alignment = align_center
        c_sno.border = border_cell

        # Col 2: Mandal Name
        c_name = ws1.cell(row=current_row, column=2, value=m.mandal_name)
        c_name.font = font_data_bold
        c_name.fill = row_bg
        c_name.alignment = align_left
        c_name.border = border_cell

        # Col 3: No of GPs
        c_tot = ws1.cell(row=current_row, column=3, value=m.total_gps)
        c_tot.font = font_data
        c_tot.fill = row_bg
        c_tot.alignment = align_center
        c_tot.border = border_cell

        # Col 4: Overall % Entered
        ovr_val = m.overall_pct_entered if m.overall_pct_entered > 0 else m.pct_completed
        c_ovr = ws1.cell(row=current_row, column=4, value=f"{ovr_val:.1f}")
        c_ovr.alignment = align_center
        c_ovr.border = border_cell
        c_ovr.fill = fill_ovr
        c_ovr.font = font_ovr

        # Columns 5 to 58: 18 Activity triplets
        for act_idx, act_name in enumerate(OFFICIAL_MAS_REPORT_ACTIVITIES):
            start_c = 5 + (act_idx * 3)
            entered, not_entered, pct = m.get_activity_stats(act_name)

            # Entered
            c_e = ws1.cell(row=current_row, column=start_c, value=entered)
            c_e.font = font_data
            c_e.fill = row_bg
            c_e.alignment = align_center
            c_e.border = border_cell

            # Not Entered
            c_ne = ws1.cell(row=current_row, column=start_c + 1, value=not_entered)
            c_ne.font = font_data
            c_ne.fill = row_bg
            c_ne.alignment = align_center
            c_ne.border = border_cell

            # % Entered (Refined Badge Highlight)
            c_p = ws1.cell(row=current_row, column=start_c + 2, value=f"{pct:.1f}")
            c_p.alignment = align_center
            c_p.border = border_cell
            if pct >= 100.0:
                c_p.fill = fill_green
                c_p.font = font_green
            elif pct > 0.0:
                c_p.fill = fill_amber
                c_p.font = font_amber
            else:
                c_p.fill = fill_red
                c_p.font = font_red

        current_row += 1

    # -------------------------------------------------------------------------
    # DISTRICT TOTAL ROW (Deep Midnight Navy with White and Gold)
    # -------------------------------------------------------------------------
    ws1.row_dimensions[current_row].height = 24

    c_tot_sno = ws1.cell(row=current_row, column=1, value="")
    c_tot_sno.fill = fill_total
    c_tot_sno.border = border_total

    c_tot_name = ws1.cell(row=current_row, column=2, value="DISTRICT TOTAL")
    c_tot_name.font = font_total
    c_tot_name.alignment = align_left
    c_tot_name.fill = fill_total
    c_tot_name.border = border_total

    c_tot_gps = ws1.cell(row=current_row, column=3, value=report.total_gps)
    c_tot_gps.font = font_total
    c_tot_gps.alignment = align_center
    c_tot_gps.fill = fill_total
    c_tot_gps.border = border_total

    dist_ovr = report.overall_pct_entered if report.overall_pct_entered > 0 else report.overall_pct
    c_tot_ovr = ws1.cell(row=current_row, column=4, value=f"{dist_ovr:.1f}")
    c_tot_ovr.alignment = align_center
    c_tot_ovr.fill = fill_total
    c_tot_ovr.font = font_total_gold
    c_tot_ovr.border = border_total

    # 18 Activity District Totals
    for act_idx, act_name in enumerate(OFFICIAL_MAS_REPORT_ACTIVITIES):
        start_c = 5 + (act_idx * 3)
        dist_ent, dist_not, dist_pct = report.get_activity_totals(act_name)

        c_de = ws1.cell(row=current_row, column=start_c, value=dist_ent)
        c_de.font = font_total
        c_de.alignment = align_center
        c_de.fill = fill_total
        c_de.border = border_total

        c_dne = ws1.cell(row=current_row, column=start_c + 1, value=dist_not)
        c_dne.font = font_total
        c_dne.alignment = align_center
        c_dne.fill = fill_total
        c_dne.border = border_total

        c_dp = ws1.cell(row=current_row, column=start_c + 2, value=f"{dist_pct:.1f}")
        c_dp.alignment = align_center
        c_dp.fill = fill_total
        c_dp.font = font_total_gold
        c_dp.border = border_total

    # -------------------------------------------------------------------------
    # COLUMN WIDTHS & FREEZE PANES
    # -------------------------------------------------------------------------
    ws1.column_dimensions["A"].width = 7.0
    ws1.column_dimensions["B"].width = 26.0
    ws1.column_dimensions["C"].width = 11.0
    ws1.column_dimensions["D"].width = 15.0

    for act_idx in range(len(OFFICIAL_MAS_REPORT_ACTIVITIES)):
        start_c = 5 + (act_idx * 3)
        ws1.column_dimensions[get_column_letter(start_c)].width = 9.5
        ws1.column_dimensions[get_column_letter(start_c + 1)].width = 11.5
        ws1.column_dimensions[get_column_letter(start_c + 2)].width = 11.5

    # Freeze panes at E6 (Keeps S.No, Mandal Name, No of GPs, Overall % and Headers fixed)
    ws1.freeze_panes = "E6"

    # =========================================================================
    # SHEET 2: GM-R 5.23 BIRTHS REGISTER
    # =========================================================================
    ws2 = wb.create_sheet(title="GM-R_5.23_Births_Register")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:G1")
    t21 = ws2["A1"]
    t21.value = f"REPORT ON BIRTHS REGISTER IN GP (GM-R 5.23){dist_suffix}"
    t21.font = font_title
    t21.fill = fill_navy
    t21.alignment = align_center
    ws2.row_dimensions[1].height = 28

    ws2.merge_cells("A2:G2")
    t22 = ws2["A2"]
    t22.value = (
        f"REPORTING YEAR: {report.financial_year} | "
        f"MONTH: {report.month_name} | "
        f"GENERATED: {report.generated_at}"
    )
    t22.font = font_sub
    t22.fill = fill_navy
    t22.alignment = align_center
    ws2.row_dimensions[2].height = 20

    # KPI Row
    ws2.merge_cells("A3:B3")
    ws2["A3"] = f"Total GPs: {report.total_gps}"
    ws2["A3"].font = font_data_bold
    ws2["A3"].fill = fill_sub_hdr
    ws2["A3"].alignment = align_center
    ws2["A3"].border = border_cell
    ws2["B3"].border = border_cell

    ws2["C3"] = f"Entered GPs: {report.total_birth_entered_gps}"
    ws2["C3"].font = font_green
    ws2["C3"].fill = fill_green
    ws2["C3"].alignment = align_center
    ws2["C3"].border = border_cell

    ws2["D3"] = f"Not Entered: {report.total_birth_pending_gps}"
    ws2["D3"].font = font_red
    ws2["D3"].fill = fill_red
    ws2["D3"].alignment = align_center
    ws2["D3"].border = border_cell

    ws2["E3"] = f"Total Births: {report.total_district_births}"
    ws2["E3"].font = font_data_bold
    ws2["E3"].fill = fill_sub_hdr
    ws2["E3"].alignment = align_center
    ws2["E3"].border = border_cell

    ws2.merge_cells("F3:G3")
    ws2["F3"] = f"Achievement: {report.births_overall_pct:.1f}%"
    ws2["F3"].font = font_ovr
    ws2["F3"].fill = fill_ovr
    ws2["F3"].alignment = align_center
    ws2["F3"].border = border_cell
    ws2["G3"].border = border_cell
    ws2.row_dimensions[3].height = 22

    headers2 = ["S.No", "Mandal Name", "Total GPs", "Entered GPs", "Not Entered", "Total Births Registered", "% Achievement"]
    for col_idx, h_text in enumerate(headers2, start=1):
        cell = ws2.cell(row=5, column=col_idx, value=h_text)
        cell.font = font_hdr_tier1
        cell.fill = fill_navy
        cell.alignment = align_center
        cell.border = border_cell
    ws2.row_dimensions[5].height = 24

    r2_curr = 6
    clean_birth_mandals = [bm for bm in report.birth_mandals if bm.mandal_name.strip().upper() not in ("TOTAL", "GRAND TOTAL")]
    for b_idx, bm in enumerate(clean_birth_mandals):
        row_bg = fill_even if b_idx % 2 == 0 else fill_odd

        c_sno = ws2.cell(row=r2_curr, column=1, value=bm.s_no)
        c_name = ws2.cell(row=r2_curr, column=2, value=bm.mandal_name)
        c_tot = ws2.cell(row=r2_curr, column=3, value=bm.total_gps)
        c_ent = ws2.cell(row=r2_curr, column=4, value=bm.entered_gps)
        c_not = ws2.cell(row=r2_curr, column=5, value=bm.not_entered_gps)
        c_brt = ws2.cell(row=r2_curr, column=6, value=bm.total_births)
        c_pct = ws2.cell(row=r2_curr, column=7, value=f"{bm.pct_entered:.1f}%")

        c_sno.alignment = align_center
        c_name.alignment = align_left
        c_tot.alignment = align_center
        c_ent.alignment = align_center
        c_not.alignment = align_center
        c_brt.alignment = align_center
        c_pct.alignment = align_center

        for cell in (c_sno, c_name, c_tot, c_ent, c_not, c_brt, c_pct):
            cell.font = font_data
            cell.fill = row_bg
            cell.border = border_cell

        if bm.not_entered_gps > 0:
            c_not.font = font_red
            c_not.fill = fill_red

        if bm.pct_entered >= 100.0:
            c_pct.font = font_green
            c_pct.fill = fill_green
        elif bm.pct_entered < 50.0:
            c_pct.font = font_red
            c_pct.fill = fill_red
        else:
            c_pct.font = font_amber
            c_pct.fill = fill_amber

        r2_curr += 1

    # Births Total Row
    ws2.row_dimensions[r2_curr].height = 24
    tot_cells2 = [
        ws2.cell(row=r2_curr, column=1, value=""),
        ws2.cell(row=r2_curr, column=2, value="DISTRICT TOTAL"),
        ws2.cell(row=r2_curr, column=3, value=report.total_gps),
        ws2.cell(row=r2_curr, column=4, value=report.total_birth_entered_gps),
        ws2.cell(row=r2_curr, column=5, value=report.total_birth_pending_gps),
        ws2.cell(row=r2_curr, column=6, value=report.total_district_births),
        ws2.cell(row=r2_curr, column=7, value=f"{report.births_overall_pct:.1f}%"),
    ]
    for idx_c, cell in enumerate(tot_cells2, start=1):
        cell.font = font_total_gold if idx_c == 7 else font_total
        cell.fill = fill_total
        cell.border = border_total
        cell.alignment = align_left if idx_c == 2 else align_center

    ws2.column_dimensions["A"].width = 8
    ws2.column_dimensions["B"].width = 26
    ws2.column_dimensions["C"].width = 14
    ws2.column_dimensions["D"].width = 14
    ws2.column_dimensions["E"].width = 14
    ws2.column_dimensions["F"].width = 22
    ws2.column_dimensions["G"].width = 16

    # =========================================================================
    # SHEET 3: PENDING GPs ACTION LIST
    # =========================================================================
    ws3 = wb.create_sheet(title="Pending_GPs_Action_List")
    ws3.views.sheetView[0].showGridLines = True

    ws3.merge_cells("A1:D1")
    t31 = ws3["A1"]
    t31.value = f"ACTIONABLE PENDING GRAM PANCHAYATS CALL-LIST{dist_suffix}"
    t31.font = font_title
    t31.fill = fill_navy
    t31.alignment = align_center
    ws3.row_dimensions[1].height = 28

    ws3.merge_cells("A2:D2")
    t32 = ws3["A2"]
    t32.value = (
        f"REPORTING YEAR: {report.financial_year} | "
        f"MONTH: {report.month_name} | "
        f"TOTAL PENDING GPs: {report.total_pending_gps}"
    )
    t32.font = font_sub
    t32.fill = fill_navy
    t32.alignment = align_center
    ws3.row_dimensions[2].height = 20

    headers3 = [
        "S.No",
        "Mandal Name",
        "Gram Panchayat Name",
        "Pending Monthly Activities",
    ]
    for col_idx, h_text in enumerate(headers3, start=1):
        cell = ws3.cell(row=4, column=col_idx, value=h_text)
        cell.font = font_hdr_tier1
        cell.fill = fill_navy
        cell.alignment = align_center
        cell.border = border_cell
    ws3.row_dimensions[4].height = 24

    r3_curr = 5
    if report.all_pending_gps:
        seq = 1
        for gp in report.all_pending_gps:
            row_bg = fill_even if seq % 2 != 0 else fill_odd

            c_sno = ws3.cell(row=r3_curr, column=1, value=seq)
            c_mnd = ws3.cell(row=r3_curr, column=2, value=gp.mandal_name)
            c_gp = ws3.cell(row=r3_curr, column=3, value=gp.panchayat_name)

            miss_str = format_pending_activities(gp)
            c_act = ws3.cell(row=r3_curr, column=4, value=miss_str)

            c_sno.alignment = align_center
            c_mnd.alignment = align_left
            c_gp.alignment = align_left
            c_act.alignment = align_left

            for cell in (c_sno, c_mnd, c_gp, c_act):
                cell.font = font_data
                cell.border = border_cell
                cell.fill = row_bg

            c_act.font = Font(name="Calibri", size=9.5, bold=True, color="991B1B")
            r3_curr += 1
            seq += 1
    else:
        ws3.merge_cells("A5:D5")
        no_pend = ws3["A5"]
        no_pend.value = "100% COMPLIANCE ACHIEVED: Zero Pending Gram Panchayats across all Activities!"
        no_pend.font = font_green
        no_pend.alignment = align_center
        no_pend.fill = fill_green
        _style_range(ws3, 1, 5, 4, 5, border=border_cell)

    ws3.column_dimensions["A"].width = 8
    ws3.column_dimensions["B"].width = 24
    ws3.column_dimensions["C"].width = 28
    ws3.column_dimensions["D"].width = 75

    # Finalize Output
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

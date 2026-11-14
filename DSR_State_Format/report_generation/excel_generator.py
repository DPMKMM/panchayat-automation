"""
DSR State Format - Official Excel Report Generator
==================================================
Generates openpyxl workbook matching the official 14-column State Format
with headers, formatting, formulas/values, borders, and column styling.
"""

from __future__ import annotations

from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from DSR_State_Format.calculations.aggregator import StateFormatReport


def generate_state_format_excel(report: StateFormatReport, output_path: Path) -> Path:
    """
    Renders StateFormatReport to an Excel (.xlsx) workbook.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "PS Attendance State Format"
    ws.views.sheetView[0].showGridLines = True

    # Styling elements
    font_title_dist = Font(name="Calibri", size=12, bold=True, color="1E293B")
    font_title_main = Font(name="Calibri", size=15, bold=True, color="990000")
    font_title_sub = Font(name="Calibri", size=11, bold=True, color="003399")

    font_th = Font(name="Calibri", size=10, bold=True, color="0F172A")
    font_th_pct = Font(name="Calibri", size=10, bold=True, color="0369A1")
    font_td = Font(name="Calibri", size=10, color="0F172A")
    font_pct = Font(name="Calibri", size=10, bold=True, color="C00000")
    font_tot = Font(name="Calibri", size=10, bold=True, color="0F172A")

    fill_th = PatternFill(fill_type="solid", start_color="EBF3FA", end_color="EBF3FA")
    fill_th_num = PatternFill(fill_type="solid", start_color="E2E8F0", end_color="E2E8F0")
    fill_pct_col = PatternFill(fill_type="solid", start_color="E0F2FE", end_color="E0F2FE")
    fill_tot = PatternFill(fill_type="solid", start_color="EBF3FA", end_color="EBF3FA")
    fill_pct_row = PatternFill(fill_type="solid", start_color="F8FAFC", end_color="F8FAFC")

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    thin_border_side = Side(border_style="thin", color="000000")
    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )

    # 1. District Title
    ws.merge_cells("A1:N1")
    cell_a1 = ws["A1"]
    cell_a1.value = f"District Name: {report.district_name}"
    cell_a1.font = font_title_dist
    cell_a1.alignment = align_center

    # 2. Main Title
    ws.merge_cells("A2:N2")
    cell_a2 = ws["A2"]
    cell_a2.value = "Mandal wise Status of Panchayat Secretaries Attendance With Time"
    cell_a2.font = font_title_main
    cell_a2.alignment = align_center

    # 3. Subtitle (Date and Time)
    date_display = report.report_date.strftime("%d %B %Y")
    time_display = report.generated_at.strftime("%I:%M %p")
    ws.merge_cells("A3:N3")
    cell_a3 = ws["A3"]
    cell_a3.value = f"{date_display} - @ {time_display}"
    cell_a3.font = font_title_sub
    cell_a3.alignment = align_center

    # Row 4 is spacing
    ws.row_dimensions[4].height = 6

    # 4. Table Headers (Rows 5, 6, 7)
    ws.merge_cells("A5:A6")
    ws["A5"] = "Sl.\nNo."
    ws.merge_cells("B5:B6")
    ws["B5"] = "Mandal Name"
    ws.merge_cells("C5:C6")
    ws["C5"] = "Total\nNo. of GPs"
    ws.merge_cells("D5:D6")
    ws["D5"] = "No.of PS in\nwhich full time\nworking"

    ws.merge_cells("E5:N5")
    ws["E5"] = "No.of Panchayat Secretaries reported"

    ws["E6"] = "6 AM -\n9 AM"
    ws["F6"] = "9 AM -\n10 AM"
    ws["G6"] = "10 AM -\n11 AM"
    ws["H6"] = "11 AM -\n12 Noon"
    ws["I6"] = "After\n12 Noon"
    ws["J6"] = "% of PS\nReported\nbefore 9 AM\n↓"
    ws["K6"] = "Total No.of\nPSs attended\nGP"
    ws["L6"] = "No.of PSs\nreported to\nMtg / Trngs\ntoday"
    ws["M6"] = "No.of PSs on\nLeave Today"
    ws["N6"] = "No.of PS Not\nreported"

    # Style Header Rows 5 and 6
    for r in range(5, 7):
        for col_idx in range(1, 15):
            c = ws.cell(row=r, column=col_idx)
            c.font = font_th_pct if col_idx == 10 else font_th
            c.fill = fill_pct_col if col_idx == 10 else fill_th
            c.alignment = align_center
            c.border = cell_border

    # Row 7: Column numbers 1 to 14
    for col_idx in range(1, 15):
        c = ws.cell(row=7, column=col_idx, value=col_idx)
        c.font = font_th_pct if col_idx == 10 else font_th
        c.fill = fill_pct_col if col_idx == 10 else fill_th_num
        c.alignment = align_center
        c.border = cell_border

    current_row = 8

    # 5. Data Rows
    for row in report.mandal_rows:
        ws.cell(row=current_row, column=1, value=row["sl_no"]).alignment = align_center
        ws.cell(row=current_row, column=2, value=row["mandal_name"]).alignment = align_left
        ws.cell(row=current_row, column=3, value=row["tot_gps"]).alignment = align_center
        ws.cell(row=current_row, column=4, value=row["full_time"]).alignment = align_center

        ws.cell(row=current_row, column=5, value=row["b_6_9"] if row["b_6_9"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=6, value=row["b_9_10"] if row["b_9_10"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=7, value=row["b_10_11"] if row["b_10_11"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=8, value=row["b_11_12"] if row["b_11_12"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=9, value=row["b_after_12"] if row["b_after_12"] > 0 else "").alignment = align_center

        pct_cell = ws.cell(row=current_row, column=10, value=row["pct_before_9"])
        pct_cell.number_format = "0.00"
        pct_cell.font = font_pct
        pct_cell.fill = fill_pct_col
        pct_cell.alignment = align_center

        ws.cell(row=current_row, column=11, value=row["attended_gp"] if row["attended_gp"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=12, value=row["mtg_trng"] if row["mtg_trng"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=13, value=row["leave"] if row["leave"] > 0 else "").alignment = align_center
        ws.cell(row=current_row, column=14, value=row["not_reported"]).alignment = align_center

        for col_idx in range(1, 15):
            c = ws.cell(row=current_row, column=col_idx)
            c.border = cell_border
            if col_idx != 10:
                c.font = font_td

        current_row += 1

    # 6. Total Row
    tot = report.total_row
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
    tot_label = ws.cell(row=current_row, column=1, value="Total")
    tot_label.font = font_tot
    tot_label.alignment = align_center

    ws.cell(row=current_row, column=3, value=tot["tot_gps"]).alignment = align_center
    ws.cell(row=current_row, column=4, value=tot["full_time"]).alignment = align_center
    ws.cell(row=current_row, column=5, value=tot["b_6_9"]).alignment = align_center
    ws.cell(row=current_row, column=6, value=tot["b_9_10"]).alignment = align_center
    ws.cell(row=current_row, column=7, value=tot["b_10_11"]).alignment = align_center
    ws.cell(row=current_row, column=8, value=tot["b_11_12"]).alignment = align_center
    ws.cell(row=current_row, column=9, value=tot["b_after_12"]).alignment = align_center

    tot_pct_cell = ws.cell(row=current_row, column=10, value=tot["pct_before_9"])
    tot_pct_cell.number_format = "0.00"
    tot_pct_cell.font = font_pct
    tot_pct_cell.fill = fill_pct_col
    tot_pct_cell.alignment = align_center

    ws.cell(row=current_row, column=11, value=tot["attended_gp"]).alignment = align_center
    ws.cell(row=current_row, column=12, value=tot["mtg_trng"]).alignment = align_center
    ws.cell(row=current_row, column=13, value=tot["leave"]).alignment = align_center
    ws.cell(row=current_row, column=14, value=tot["not_reported"]).alignment = align_center

    for col_idx in range(1, 15):
        c = ws.cell(row=current_row, column=col_idx)
        c.fill = fill_pct_col if col_idx == 10 else fill_tot
        c.border = cell_border
        if col_idx != 10:
            c.font = font_tot

    current_row += 1

    # 7. Percentage Row
    pct_r = report.percentage_row
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
    pct_label = ws.cell(row=current_row, column=1, value="Percentage")
    pct_label.font = font_tot
    pct_label.alignment = align_center

    for col_idx in (3, 4, 10):
        c = ws.cell(row=current_row, column=col_idx, value="")
        c.border = cell_border
        c.fill = fill_pct_col if col_idx == 10 else fill_pct_row

    for col_idx, key in (
        (5, "b_6_9"),
        (6, "b_9_10"),
        (7, "b_10_11"),
        (8, "b_11_12"),
        (9, "b_after_12"),
        (11, "attended_gp"),
        (12, "mtg_trng"),
        (13, "leave"),
        (14, "not_reported"),
    ):
        c = ws.cell(row=current_row, column=col_idx, value=pct_r[key])
        c.number_format = "0.00"
        c.font = font_pct
        c.fill = fill_pct_row
        c.alignment = align_center
        c.border = cell_border

    # Adjust Column Widths
    col_widths = {
        "A": 7,
        "B": 22,
        "C": 12,
        "D": 15,
        "E": 11,
        "F": 11,
        "G": 11,
        "H": 12,
        "I": 11,
        "J": 16,
        "K": 14,
        "L": 15,
        "M": 13,
        "N": 13,
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    # Freeze header rows up to data rows (freeze at row 8)
    ws.freeze_panes = "A8"

    wb.save(str(output_path))
    return output_path

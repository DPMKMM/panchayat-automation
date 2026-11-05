"""Excel Generator for GP Balance Entry Report (GM-R 14.2).

Produces an executive multi-sheet workbook:
  - Sheet 1: Mandal_Summary (with % Data Entered, Account-wise Updated & Pending)
  - Sheet 2: Pending_GPs_Action_List (Actionable list of exact GPs and missing accounts)
"""

import io
from pathlib import Path
from typing import Optional
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from gp_balance_models import DistrictBalanceReport


def generate_balance_excel(report: DistrictBalanceReport, output_path: Optional[Path] = None) -> bytes:
    wb = Workbook()

    # Common Styles
    font_title = Font(name="Calibri", size=15, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=11, bold=True, color="D1FAE5")
    font_sec = Font(name="Calibri", size=10, italic=True, color="333333")
    font_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_hdr_sub = Font(name="Calibri", size=9, bold=True, color="0C3829")
    font_data = Font(name="Calibri", size=10, color="132A22")
    font_bold = Font(name="Calibri", size=10, bold=True, color="132A22")
    font_pending = Font(name="Calibri", size=10, bold=True, color="DC2626")
    font_success = Font(name="Calibri", size=10, bold=True, color="059669")

    fill_header = PatternFill(start_color="0C3829", end_color="0C3829", fill_type="solid")
    fill_header_sub = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    fill_total = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    fill_alt = PatternFill(start_color="F9FBF9", end_color="F9FBF9", fill_type="solid")
    fill_pending = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    fill_complete = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

    thin = Side(border_style="thin", color="D4E0DA")
    border_cell = Border(left=thin, right=thin, top=thin, bottom=thin)
    thick_bottom = Border(left=thin, right=thin, top=thin, bottom=Side(border_style="medium", color="0C3829"))

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # =========================================================
    # SHEET 1: MANDAL SUMMARY
    # =========================================================
    ws1 = wb.active
    ws1.title = "Mandal_Summary"
    ws1.views.sheetView[0].showGridLines = True

    clean_dist = (report.district_name or "").strip()
    if clean_dist.upper().endswith("DISTRICT"):
        clean_dist = clean_dist[:-8].strip()
    dist_suffix = f" - {clean_dist.upper()} DISTRICT" if clean_dist and clean_dist.lower() != "district" else ""
    # Title Banner
    ws1.merge_cells("A1:Q1")
    t1 = ws1["A1"]
    t1.value = f"Data Entry Status Report on Balances in GP Accounts{dist_suffix}"
    t1.font = font_title
    t1.fill = fill_header
    t1.alignment = align_center
    ws1.row_dimensions[1].height = 28

    ws1.merge_cells("A2:Q2")
    t2 = ws1["A2"]
    t2_dist = f" - {clean_dist.upper()} DISTRICT" if clean_dist and clean_dist.lower() != "district" else ""
    t2.value = f"STATUS REPORT ON DATA ENTERED GPs (GM-R 14.2){t2_dist} | BALANCE DATE: {report.report_date_str}"
    t2.font = font_sub
    t2.fill = fill_header
    t2.alignment = align_center
    ws1.row_dimensions[2].height = 22

    ws1.merge_cells("A3:Q3")
    t3 = ws1["A3"]
    t3.value = (
        f"Generated: {report.generated_at} | Rule: Total GPs - Updated GPs = Pending | "
        f"PMAGY account excluded (Not applicable in district)"
    )
    t3.font = font_sec
    t3.alignment = align_center
    ws1.row_dimensions[3].height = 18

    # Row 4: Super Headers
    headers_row4 = [
        ("A4:A5", "S.No"),
        ("B4:B5", "Mandal Name"),
        ("C4:C5", "Total No. of GPs"),
        ("D4:D5", "No. of GPs Entered Data"),
        ("E4:E5", "No. of GPs not Entered Data"),
        ("F4:F5", "% Data Entered"),
        ("G4:H4", "GP PD Account (General/15FC/SFC)"),
        ("I4:J4", "State Matching Grant (TG-bPASS)"),
        ("K4:L4", "15th FC Grant - Tied"),
        ("M4:N4", "15th FC Grant - Untied"),
        ("O4:P4", "VWSC (SBM)"),
        ("Q4:R4", "MGNREGS (Material)"),
        ("S4:S5", "Mandal Status"),
    ]

    for cell_range, title in headers_row4:
        ws1.merge_cells(cell_range)
        top_cell = ws1[cell_range.split(":")[0]]
        top_cell.value = title
        top_cell.font = font_hdr
        top_cell.fill = fill_header
        top_cell.alignment = align_center

    # Row 5: Sub-headers for Updated / Pending
    sub_cols = [
        ("G5", "Updated"), ("H5", "Pending"),
        ("I5", "Updated"), ("J5", "Pending"),
        ("K5", "Updated"), ("L5", "Pending"),
        ("M5", "Updated"), ("N5", "Pending"),
        ("O5", "Updated"), ("P5", "Pending"),
        ("Q5", "Updated"), ("R5", "Pending"),
    ]
    for cell_ref, text in sub_cols:
        c = ws1[cell_ref]
        c.value = text
        c.font = font_hdr_sub
        c.fill = fill_header_sub
        c.alignment = align_center
        c.border = border_cell

    ws1.row_dimensions[4].height = 20
    ws1.row_dimensions[5].height = 16
    for row in range(4, 6):
        for col in range(1, 20):
            ws1.cell(row=row, column=col).border = border_cell

    # Populate Mandal Data
    current_row = 6
    for idx, m in enumerate(report.mandals, start=1):
        bg = fill_alt if idx % 2 == 0 else PatternFill(fill_type=None)
        status_fill = fill_complete if not m.has_pending else fill_pending
        status_font = font_success if not m.has_pending else font_pending
        pending_cnt = max(m.not_entered_gps, len(m.pending_gps), m.gp_pd_pending, m.tgbpass_pending, m.fc15_tied_pending, m.fc15_untied_pending, m.vwsc_pending, m.mgnregs_pending) if m.has_pending else 0
        status_text = "100% Done" if not m.has_pending else f"{max(1, pending_cnt)} Pending"

        row_vals = [
            (idx, align_center, font_data, bg),
            (m.mandal_name, align_left, font_bold, bg),
            (m.total_gps, align_right, font_bold, bg),
            (m.entered_gps, align_right, font_success if m.entered_gps == m.total_gps else font_data, bg),
            (m.not_entered_gps, align_right, font_pending if m.not_entered_gps > 0 else font_data, bg),
            (f"{m.pct_entered:.1f}%", align_right, font_bold, bg),
            (m.gp_pd_updated, align_right, font_data, bg),
            (m.gp_pd_pending, align_right, font_pending if m.gp_pd_pending > 0 else font_data, bg),
            (m.tgbpass_updated, align_right, font_data, bg),
            (m.tgbpass_pending, align_right, font_pending if m.tgbpass_pending > 0 else font_data, bg),
            (m.fc15_tied_updated, align_right, font_data, bg),
            (m.fc15_tied_pending, align_right, font_pending if m.fc15_tied_pending > 0 else font_data, bg),
            (m.fc15_untied_updated, align_right, font_data, bg),
            (m.fc15_untied_pending, align_right, font_pending if m.fc15_untied_pending > 0 else font_data, bg),
            (m.vwsc_updated, align_right, font_data, bg),
            (m.vwsc_pending, align_right, font_pending if m.vwsc_pending > 0 else font_data, bg),
            (m.mgnregs_updated, align_right, font_data, bg),
            (m.mgnregs_pending, align_right, font_pending if m.mgnregs_pending > 0 else font_data, bg),
            (status_text, align_center, status_font, status_fill),
        ]

        for col_idx, (val, al, fnt, fill) in enumerate(row_vals, start=1):
            cell = ws1.cell(row=current_row, column=col_idx, value=val)
            cell.alignment = al
            cell.font = fnt
            if fill.fill_type:
                cell.fill = fill
            cell.border = border_cell

        ws1.row_dimensions[current_row].height = 20
        current_row += 1

    # Totals Row
    ws1.cell(row=current_row, column=1, value="").border = thick_bottom
    tot_lbl = ws1.cell(row=current_row, column=2, value="DISTRICT TOTAL")
    tot_lbl.font = font_bold
    tot_lbl.alignment = align_left
    tot_lbl.fill = fill_total
    tot_lbl.border = thick_bottom

    tot_cols = [
        (3, report.total_gps),
        (4, report.total_entered_gps),
        (5, report.total_not_entered_gps),
        (6, f"{report.overall_pct_entered:.1f}%"),
        (7, sum(m.gp_pd_updated for m in report.mandals)),
        (8, report.total_gp_pd_pending),
        (9, sum(m.tgbpass_updated for m in report.mandals)),
        (10, report.total_tgbpass_pending),
        (11, sum(m.fc15_tied_updated for m in report.mandals)),
        (12, report.total_fc15_tied_pending),
        (13, sum(m.fc15_untied_updated for m in report.mandals)),
        (14, report.total_fc15_untied_pending),
        (15, sum(m.vwsc_updated for m in report.mandals)),
        (16, report.total_vwsc_pending),
        (17, sum(m.mgnregs_updated for m in report.mandals)),
        (18, report.total_mgnregs_pending),
        (19, f"{report.total_not_entered_gps} Total Pending" if report.total_not_entered_gps > 0 else "100% Completed"),
    ]

    for col_idx, val in tot_cols:
        cell = ws1.cell(row=current_row, column=col_idx, value=val)
        cell.font = font_bold
        cell.alignment = align_right if col_idx != 19 else align_center
        cell.fill = fill_total
        cell.border = thick_bottom

    ws1.row_dimensions[current_row].height = 22

    # Column widths (Status column decreased to 12)
    col_widths = {
        1: 6, 2: 20, 3: 12, 4: 12, 5: 12, 6: 12,
        7: 10, 8: 9, 9: 10, 10: 9, 11: 10, 12: 9,
        13: 10, 14: 9, 15: 10, 16: 9, 17: 10, 18: 9, 19: 12,
    }
    for col_idx, w in col_widths.items():
        ws1.column_dimensions[get_column_letter(col_idx)].width = w

    # =========================================================
    # SHEET 2: PENDING GRAM PANCHAYATS ACTION LIST
    # =========================================================
    ws2 = wb.create_sheet(title="Pending_GPs_Action_List")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:G1")
    p1 = ws2["A1"]
    p1_dist = f"{clean_dist.upper()} DISTRICT — " if clean_dist and clean_dist.lower() != "district" else ""
    p1.value = f"{p1_dist}GRAM PANCHAYAT LEVEL PENDING BALANCE ACTION LIST"
    p1.font = font_title
    p1.fill = fill_header
    p1.alignment = align_center
    ws2.row_dimensions[1].height = 28

    ws2.merge_cells("A2:G2")
    p2 = ws2["A2"]
    p2.value = f"Thursday Balance Update Date: {report.report_date_str} | Generated: {report.generated_at}"
    p2.font = font_sub
    p2.fill = fill_header
    p2.alignment = align_center
    ws2.row_dimensions[2].height = 20

    headers_p = [
        "S.No", "Mandal Name", "Panchayat Name", "Entry Status",
        "Missing Account(s) (Marked 'No')", "Panchayat Secretary Name", "Secretary Mobile"
    ]
    for col_idx, h in enumerate(headers_p, start=1):
        cell = ws2.cell(row=4, column=col_idx, value=h)
        cell.font = font_hdr
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_cell
    ws2.row_dimensions[4].height = 24

    if not report.pending_gps_all:
        ws2.merge_cells("A5:G5")
        c = ws2["A5"]
        c.value = "🎉 ALL GRAM PANCHAYATS HAVE COMPLETED DATA ENTRY! ZERO PENDING GPs."
        c.font = font_success
        c.alignment = align_center
        c.fill = fill_complete
        ws2.row_dimensions[5].height = 30
    else:
        for idx, gp in enumerate(report.pending_gps_all, start=1):
            r = 4 + idx
            bg = fill_alt if idx % 2 == 0 else PatternFill(fill_type=None)
            missing_txt = ", ".join(gp.missing_accounts) if gp.missing_accounts else "Data Not Entered"

            row_p = [
                (idx, align_center, font_data),
                (gp.mandal_name, align_left, font_bold),
                (gp.panchayat_name, align_left, font_bold),
                ("Pending Entry", align_center, font_pending),
                (missing_txt, align_left, font_pending),
                (gp.secretary_name or "PS", align_left, font_data),
                (gp.secretary_phone or "-", align_center, font_data),
            ]
            for col_idx, (val, al, fnt) in enumerate(row_p, start=1):
                cell = ws2.cell(row=r, column=col_idx, value=val)
                cell.alignment = al
                cell.font = fnt
                if bg.fill_type:
                    cell.fill = bg
                cell.border = border_cell
            ws2.row_dimensions[r].height = 20

    ws2.column_dimensions["A"].width = 7
    ws2.column_dimensions["B"].width = 20
    ws2.column_dimensions["C"].width = 24
    ws2.column_dimensions["D"].width = 16
    ws2.column_dimensions["E"].width = 44
    ws2.column_dimensions["F"].width = 24
    ws2.column_dimensions["G"].width = 18

    # Save
    buf = io.BytesIO()
    wb.save(buf)
    content = buf.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

    return content

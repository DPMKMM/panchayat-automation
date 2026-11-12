"""Excel (5-sheet styled workbook), CSV, JSON, Markdown & PDF deliverable exporter for MAS."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.branding import PLATFORM_NAME, TAGLINE, apply_openpyxl_branding
from mas.models import ALL_18_MODULES, normalize_district_and_slug
from mas.pdf_generator import generate_mas_consolidated_pdf

logger = logging.getLogger(__name__)


def generate_abstract_markdown(
    mandals_abstract: List[Dict[str, Any]],
    total_row: Dict[str, Any],
    pending_action_list: List[Dict[str, Any]],
    excluded_modules: List[str],
    month: str = "July",
    year: int = 2026,
    district_name: str = "Khammam",
    include_gp_data: bool = True,
) -> str:
    """Build clean Markdown summary matching MAS GM-R 5.24 + GM-R 5.23 matrix."""
    clean_district, _ = normalize_district_and_slug(district_name)
    excl_str = ", ".join(excluded_modules) if excluded_modules else "None (All 18 Included)"
    n_incl = total_row.get("included_modules_count", 18)

    lines = [
        f"# {clean_district} District - Consolidated MAS Mandal & GP Abstract ({month} {year})",
        f"**Platform:** {PLATFORM_NAME} — *{TAGLINE}*",
        f"**Source:** Live EPTS Webscrape (`GM-R 5.24` 17 Indicators + `GM-R 5.23` Birth Details)",
        f"**Excluded Modules from % Calculation:** `{excl_str}`",
        f"**District Overall Completion ({n_incl} Included Modules):** **{total_row['Overall % Entered']}%** ({total_row['No of Updated']:,} / {total_row['Total Fields']:,} Fields Updated across {total_row['No of GPs']} GPs)",
        "",
        "> **Format Note:** Module columns display `Not Updated / Updated` (e.g. `0 / 22` = 0 Pending, 22 Entered).",
        "",
        "## Mandal-Wise Compact Abstract (All 18 Modules)",
        "",
    ]

    headers = ["S No", "Mandal Name", "No of GPs", f"Overall % ({n_incl} Mod)"] + [
        f"{lbl} [Excl]" if lbl in excluded_modules else lbl for lbl, _ in ALL_18_MODULES
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for m in mandals_abstract:
        row_vals = [str(m["S No"]), f"**{m['Mandal Name']}**", str(m["No of GPs"]), f"**{m['Overall % Entered']}%**"]
        for lbl, _ in ALL_18_MODULES:
            row_vals.append(m["modules"][lbl]["formatted_compact"])
        lines.append("| " + " | ".join(row_vals) + " |")

    tot_vals = [
        "**Total**",
        "**District Total**",
        f"**{total_row['No of GPs']}**",
        f"**{total_row['Overall % Entered']}%**",
    ]
    for lbl, _ in ALL_18_MODULES:
        tot_vals.append(f"**{total_row['modules'][lbl]['formatted_compact']}**")
    lines.append("| " + " | ".join(tot_vals) + " |")

    lines.extend(["", "---", ""])
    if include_gp_data:
        lines.extend([
            f"## Gram Panchayats Pending Entry ({len(pending_action_list)} GPs Requiring Action)",
            "",
        ])
        if pending_action_list:
            lines.append("| S No | Mandal | Gram Panchayat | Pending Count | Pending Module(s) | Completed / Total | Completion % |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for item in pending_action_list:
                lines.append(
                    f"| {item['S No']} | {item['Mandal']} | **{item['Gram_Panchayat']}** | **{item['Pending_Count']} Pending** | {item['Pending_Modules']} | {item['Completed_Count']} / {n_incl} | **{item['Completion_Rate']}** |"
                )
        else:
            lines.append("**All Gram Panchayats in the district are 100% compliant!** Zero pending entries found.")
    else:
        lines.extend([
            "## Report Mode: Mandal Abstract Only",
            "GP-wise drill-down was skipped for faster execution. Select **Mandal Abstract & GP-Wise Data** when individual pending GP lists are required.",
        ])

    return "\n".join(lines)


def _export_styled_excel(
    excel_path: Path,
    mandals_abstract: List[Dict[str, Any]],
    total_row: Dict[str, Any],
    compact_rows: List[Dict[str, Any]],
    pending_action_list: List[Dict[str, Any]],
    joined_records: List[Dict[str, Any]],
    excluded_modules: List[str],
    month: str,
    year: int,
    clean_district: str,
) -> None:
    """Create the 5-sheet professionally styled openpyxl MAS workbook with canonical branding."""
    df_compact = pd.DataFrame(compact_rows)
    df_pending = pd.DataFrame(pending_action_list)
    df_joined = pd.DataFrame(joined_records)

    wb = openpyxl.Workbook()
    ws_abs = wb.active
    ws_abs.title = "Mandal_Abstract"

    header_fill = PatternFill(start_color="0C3829", end_color="0C3829", fill_type="solid")
    sub_fill = PatternFill(start_color="165B43", end_color="165B43", fill_type="solid")
    excl_fill = PatternFill(start_color="B45309", end_color="B45309", fill_type="solid")
    total_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    red_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    font_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10, color="111827")
    font_bold = Font(name="Calibri", size=10, bold=True, color="0C3829")
    font_red = Font(name="Calibri", size=10, bold=True, color="B91C1C")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws_abs.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4 + len(ALL_18_MODULES))
    c_title = ws_abs.cell(
        row=1,
        column=1,
        value=f"{clean_district} District - Monthly Activity Statement (MAS) Abstract ({month} {year}) | Overall: {total_row['Overall % Entered']}%",
    )
    c_title.font = font_title
    c_title.fill = header_fill
    c_title.alignment = Alignment(horizontal="center", vertical="center")
    ws_abs.row_dimensions[1].height = 28

    excl_str = ", ".join(excluded_modules) if excluded_modules else "None (All 18 Included)"
    ws_abs.merge_cells(start_row=2, start_column=1, end_row=2, end_column=4 + len(ALL_18_MODULES))
    c_sub = ws_abs.cell(
        row=2,
        column=1,
        value=(
            f"Excluded from %: {excl_str} | Formula: Sum(Updated)/({total_row['included_modules_count']} x GPs) | "
            f"Format: Not Updated / Updated (0/22 = 0 Pending)"
        ),
    )
    c_sub.font = Font(name="Calibri", size=9, italic=True, color="D1FAE5")
    c_sub.fill = sub_fill
    c_sub.alignment = Alignment(horizontal="center", vertical="center")
    ws_abs.row_dimensions[2].height = 20

    abs_headers = ["S No", "Mandal Name", "No of GPs", f"Overall % ({total_row['included_modules_count']} Mod)"] + [
        f"{lbl} [Excl]" if lbl in excluded_modules else lbl for lbl, _ in ALL_18_MODULES
    ]
    for col_idx, h_text in enumerate(abs_headers, 1):
        cell = ws_abs.cell(row=3, column=col_idx, value=h_text)
        cell.font = font_hdr
        is_excl_col = col_idx > 4 and ALL_18_MODULES[col_idx - 5][0] in excluded_modules
        cell.fill = excl_fill if is_excl_col else header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws_abs.row_dimensions[3].height = 32

    excluded_set = set(excluded_modules or [])
    for r_offset, row_data in enumerate(compact_rows):
        r_num = 4 + r_offset
        is_tot = row_data["S No"] == "Total"
        vals = [
            row_data["S No"],
            row_data["Mandal Name"],
            row_data["No of GPs"],
            f"{row_data['Overall % Entered']}%",
        ] + [row_data[lbl] for lbl, _ in ALL_18_MODULES]

        row_has_pending = float(row_data.get("Overall % Entered", 100.0)) < 100.0 or any(
            (lbl not in excluded_set)
            and " / " in str(row_data.get(lbl, ""))
            and not str(row_data.get(lbl, "")).startswith("0 /")
            for lbl, _ in ALL_18_MODULES
        )

        for col_idx, val in enumerate(vals, 1):
            cell = ws_abs.cell(row=r_num, column=col_idx, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left" if col_idx == 2 else "center", vertical="center")
            mod_label = ALL_18_MODULES[col_idx - 5][0] if col_idx > 4 else ""
            is_excl_col = col_idx > 4 and mod_label in excluded_set
            is_mod_pending = (not is_excl_col) and col_idx > 4 and " / " in str(val) and not str(val).startswith("0 /")

            if is_tot:
                cell.fill = PatternFill(start_color="FDE68A", end_color="FDE68A", fill_type="solid") if is_excl_col else total_fill
                cell.font = font_red if ((col_idx == 4 and row_has_pending) or is_mod_pending) else font_bold
            else:
                if r_offset % 2 == 1:
                    cell.fill = zebra_fill
                if is_excl_col:
                    cell.fill = PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid")
                    cell.font = Font(name="Calibri", size=10, color="92400E")
                elif is_mod_pending:
                    cell.fill = red_fill
                    cell.font = font_red
                elif row_has_pending and col_idx in (1, 2, 4):
                    cell.font = font_red
                else:
                    cell.font = font_bold if col_idx == 4 else font_data

    ws_abs.column_dimensions["A"].width = 7
    ws_abs.column_dimensions["B"].width = 22
    ws_abs.column_dimensions["C"].width = 11
    ws_abs.column_dimensions["D"].width = 15
    for idx in range(5, 5 + len(ALL_18_MODULES)):
        ws_abs.column_dimensions[get_column_letter(idx)].width = 16

    # Sheet 2: Detailed 58 Columns (3 cols per module: Entered, Not Entered, % Entered)
    ws_det = wb.create_sheet("Mandal_58_Col_Detail")
    det_headers = ["S No", "Mandal Name", "No of GPs", "Overall % Entered"]
    for lbl, _ in ALL_18_MODULES:
        det_headers.extend([f"{lbl}_Entered", f"{lbl}_NotEntered", f"{lbl}_Pct%"])
    for col_idx, h in enumerate(det_headers, 1):
        c = ws_det.cell(row=1, column=col_idx, value=h)
        c.font = font_hdr
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    for r_idx, m in enumerate(mandals_abstract + [total_row], 2):
        row_vals = [m["S No"], m["Mandal Name"], m["No of GPs"], m["Overall % Entered"]]
        for lbl, _ in ALL_18_MODULES:
            row_vals.extend([m["modules"][lbl]["Entered"], m["modules"][lbl]["Not Entered"], m["modules"][lbl]["% Entered"]])
        for c_idx, val in enumerate(row_vals, 1):
            cell = ws_det.cell(row=r_idx, column=c_idx, value=val)
            cell.border = thin_border
            if m["S No"] == "Total":
                cell.fill = total_fill
                cell.font = font_bold

    # Sheet 3: Pending GPs Action List
    ws_pend = wb.create_sheet("Pending_GPs_Action_List")
    pend_cols = (
        list(df_pending.columns)
        if not df_pending.empty
        else ["S No", "Mandal", "Gram_Panchayat", "Pending_Count", "Pending_Modules", "Completed_Count", "Completion_Rate", "Action_Required"]
    )
    for col_idx, h in enumerate(pend_cols, 1):
        c = ws_pend.cell(row=1, column=col_idx, value=h)
        c.font = font_hdr
        c.fill = header_fill
        c.border = thin_border
    for r_idx, row_rec in enumerate(pending_action_list, 2):
        for col_idx, col_key in enumerate(pend_cols, 1):
            c = ws_pend.cell(row=r_idx, column=col_idx, value=row_rec.get(col_key, ""))
            c.border = thin_border
            if col_key == "Pending_Count":
                c.font = font_red
    ws_pend.column_dimensions["A"].width = 7
    ws_pend.column_dimensions["B"].width = 18
    ws_pend.column_dimensions["C"].width = 25
    ws_pend.column_dimensions["D"].width = 14
    ws_pend.column_dimensions["E"].width = 45
    ws_pend.column_dimensions["H"].width = 30

    # Sheet 4: Full GP Joined Records
    ws_gp = wb.create_sheet("Full_GP_18_Module_Records")
    gp_cols = list(df_joined.columns) if not df_joined.empty else []
    for col_idx, h in enumerate(gp_cols, 1):
        c = ws_gp.cell(row=1, column=col_idx, value=h)
        c.font = font_hdr
        c.fill = header_fill
    for r_idx, row_rec in enumerate(joined_records, 2):
        for col_idx, col_key in enumerate(gp_cols, 1):
            ws_gp.cell(row=r_idx, column=col_idx, value=row_rec.get(col_key, ""))

    # Sheet 5: Formula & Exclusions Metadata
    ws_meta = wb.create_sheet("Methodology_And_Exclusions")
    ws_meta.append(["Parameter", "Value"])
    ws_meta.append(["Platform", PLATFORM_NAME])
    ws_meta.append(["District", clean_district])
    ws_meta.append(["Reporting Period", f"{month} {year}"])
    ws_meta.append(["Data Source", "Live EPTS Portal GM-R 5.24 + GM-R 5.23"])
    ws_meta.append(["Included Modules Count", total_row["included_modules_count"]])
    ws_meta.append(["Excluded Modules", excl_str])
    ws_meta.append(["District Overall % Entered", f"{total_row['Overall % Entered']}%"])
    ws_meta.append(["Total Updated Fields (Included)", total_row["No of Updated"]])
    ws_meta.append(["Total Possible Fields (Included)", total_row["Total Fields"]])
    ws_meta.append(["Total Pending Action GPs", len(pending_action_list)])
    ws_meta.append(["Formula", f"Sum(Updated in Included Modules) / ({total_row['included_modules_count']} Modules x GPs) x 100"])

    apply_openpyxl_branding(wb)
    wb.save(excel_path)
    _ = df_compact  # keep helper structure explicit


def export_all_deliverables(
    mandals_abstract: List[Dict[str, Any]],
    total_row: Dict[str, Any],
    joined_records: List[Dict[str, Any]],
    pending_action_list: List[Dict[str, Any]],
    excluded_modules: List[str],
    output_dir: Path,
    month: str = "July",
    year: int = 2026,
    district_name: str = "Khammam",
    include_gp_data: bool = True,
) -> Dict[str, str]:
    """Export Excel (5-sheet styled), CSVs, JSON, Markdown, and PDFs cleanly inside ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_district, dist_slug = normalize_district_and_slug(district_name)
    month_tag = f"{month.capitalize()}_{year}"
    base_name = f"{dist_slug}_MAS_18_Modules_{month_tag}"

    # 1. Compact Abstract CSV
    compact_rows = []
    for m in mandals_abstract + [total_row]:
        r = {
            "S No": m["S No"],
            "Mandal Name": m["Mandal Name"],
            "No of GPs": m["No of GPs"],
            "Overall % Entered": m["Overall % Entered"],
        }
        for lbl, _ in ALL_18_MODULES:
            r[lbl] = m["modules"][lbl]["formatted_compact"]
        compact_rows.append(r)
    compact_csv_path = output_dir / f"{base_name}_Compact.csv"
    pd.DataFrame(compact_rows).to_csv(compact_csv_path, index=False)

    # 2. Full 58-column CSV
    detail_rows = []
    for m in mandals_abstract + [total_row]:
        r = {
            "S No": m["S No"],
            "Mandal Name": m["Mandal Name"],
            "No of GPs": m["No of GPs"],
            "Overall % Entered": m["Overall % Entered"],
        }
        for lbl, _ in ALL_18_MODULES:
            r[f"{lbl}_Entered"] = m["modules"][lbl]["Entered"]
            r[f"{lbl}_NotEntered"] = m["modules"][lbl]["Not Entered"]
            r[f"{lbl}_Pct"] = m["modules"][lbl]["% Entered"]
        detail_rows.append(r)
    full_csv_path = output_dir / f"{base_name}_58Cols.csv"
    pd.DataFrame(detail_rows).to_csv(full_csv_path, index=False)

    # 3. Full GP Joined CSV
    joined_gp_csv_path = output_dir / f"{dist_slug}_Joined_MAS_Births_Full_GP_{month_tag}.csv"
    pd.DataFrame(joined_records).to_csv(joined_gp_csv_path, index=False)

    # 4. Pending Action List CSV
    pending_csv_path = output_dir / f"{dist_slug}_MAS_Pending_GPs_Action_List_{month_tag}.csv"
    pd.DataFrame(pending_action_list).to_csv(pending_csv_path, index=False)

    # 5. Master JSON
    master_json = {
        "district": clean_district,
        "month": month.capitalize(),
        "year": year,
        "report_type": "abstract_and_gp" if include_gp_data else "abstract_only",
        "include_gp_data": include_gp_data,
        "total_gps": len(joined_records) or int(total_row.get("No of GPs") or 0),
        "pending_gps_count": len(pending_action_list),
        "included_modules_count": total_row["included_modules_count"],
        "excluded_modules": excluded_modules,
        "district_overall_pct": total_row["Overall % Entered"],
        "mandals_abstract": mandals_abstract,
        "total_row": total_row,
        "pending_action_list": pending_action_list,
    }
    json_path = output_dir / f"{dist_slug}_MAS_Consolidated_Master_{month_tag}.json"
    json_path.write_text(json.dumps(master_json, indent=2), encoding="utf-8")

    # 6. Styled Multi-Sheet Excel Workbook
    excel_path = output_dir / f"{dist_slug}_MAS_Consolidated_Master_{month_tag}.xlsx"
    _export_styled_excel(
        excel_path=excel_path,
        mandals_abstract=mandals_abstract,
        total_row=total_row,
        compact_rows=compact_rows,
        pending_action_list=pending_action_list,
        joined_records=joined_records,
        excluded_modules=excluded_modules,
        month=month,
        year=year,
        clean_district=clean_district,
    )

    # 7. Markdown Report
    md_text = generate_abstract_markdown(
        mandals_abstract,
        total_row,
        pending_action_list,
        excluded_modules,
        month=month,
        year=year,
        district_name=clean_district,
        include_gp_data=include_gp_data,
    )
    md_path = output_dir / f"{dist_slug}_MAS_18_Modules_Abstract_{month_tag}.md"
    md_path.write_text(md_text, encoding="utf-8")

    # 8A. Mandal Abstract PDF (Single-Page Portrait-Fitted Landscape Abstract ONLY)
    abstract_pdf_path = output_dir / f"{dist_slug}_MAS_Mandal_Abstract_{month_tag}.pdf"
    generate_mas_consolidated_pdf(
        mandals_abstract=mandals_abstract,
        total_row=total_row,
        pending_action_list=pending_action_list,
        excluded_modules=excluded_modules,
        output_path=abstract_pdf_path,
        month=month,
        year=year,
        district_name=clean_district,
        include_gp_data=False,
    )

    # 8B. Full Combined Mandal + GP Pending Action Plan PDF (when include_gp_data is True)
    files_map: Dict[str, str] = {
        "excel": str(excel_path),
        "abstract_pdf": str(abstract_pdf_path),
        "compact_csv": str(compact_csv_path),
        "full_csv": str(full_csv_path),
        "joined_csv": str(joined_gp_csv_path),
        "pending_csv": str(pending_csv_path),
        "json": str(json_path),
        "markdown": str(md_path),
    }

    if include_gp_data:
        pdf_path = output_dir / f"{dist_slug}_MAS_Consolidated_Report_{month_tag}.pdf"
        generate_mas_consolidated_pdf(
            mandals_abstract=mandals_abstract,
            total_row=total_row,
            pending_action_list=pending_action_list,
            excluded_modules=excluded_modules,
            output_path=pdf_path,
            month=month,
            year=year,
            district_name=clean_district,
            include_gp_data=True,
        )
        files_map["pdf"] = str(pdf_path)

    return files_map

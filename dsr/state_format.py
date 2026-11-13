"""State Government format for Mandal-wise PS Attendance with Time.

Generates the 14-column official State Government reporting table:
1. Sl. No.
2. Mandal Name
3. Total No. of GPs
4. No.of PS in which full time working
5. 6 AM - 9 AM
6. 9 AM - 10 AM
7. 10 AM - 11 AM
8. 11 AM - 12 Noon
9. After 12 Noon
10. % of PS Reported before 9 AM ↓
11. Total No.of PSs attended GP
12. No.of PSs reported to Mtg / Trngs today
13. No.of PSs on Leave Today
14. No.of PS Not reported
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dsr.pdf_generator import (
    _clean_lgd,
    _clean_mobile,
    _clean_name,
    _clean_string,
    _is_present_status,
    _parse_timestamp,
    load_ps_directory_cache,
    read_source_file,
)

logger = logging.getLogger(__name__)


@dataclass
class StateFormatRow:
    sl_no: Any  # int or str e.g. 1 or ""
    mandal_name: str
    total_gps: int
    full_time_working: int
    b_6_9: int
    b_9_10: int
    b_10_11: int
    b_11_12: int
    b_after_12: int
    pct_before_9: float
    total_attended: int
    meeting_training: int
    on_leave: int
    not_reported: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StateFormatReport:
    district_name: str
    report_date: date
    report_date_str: str  # e.g. "10 November 2026"
    generated_time_str: str  # e.g. "07:00 PM"
    subtitle: str  # e.g. "10 November 2026 - @ 07:00 PM"
    exclude_incharge: bool
    total_gps: int
    total_working_ps: int
    total_attended: int
    overall_pct_before_9: float
    rows: list[StateFormatRow]
    total_row: StateFormatRow

    def to_dict(self) -> dict[str, Any]:
        return {
            "district_name": self.district_name,
            "report_date": self.report_date.isoformat(),
            "report_date_str": self.report_date_str,
            "generated_time_str": self.generated_time_str,
            "subtitle": self.subtitle,
            "exclude_incharge": self.exclude_incharge,
            "total_gps": self.total_gps,
            "total_working_ps": self.total_working_ps,
            "total_attended": self.total_attended,
            "overall_pct_before_9": self.overall_pct_before_9,
            "rows": [r.to_dict() for r in self.rows],
            "total_row": self.total_row.to_dict(),
        }


def _classify_arrival_bucket(dt: Any) -> str:
    """Classify attendance arrival timestamp into hourly buckets.
    
    Before 9 AM (Col 5): all arrivals with time < 09:00:00 (including before 06:00 AM)
    9 AM - 10 AM (Col 6): 09:00:00 to 09:59:59
    10 AM - 11 AM (Col 7): 10:00:00 to 10:59:59
    11 AM - 12 Noon (Col 8): 11:00:00 to 11:59:59
    After 12 Noon (Col 9): >= 12:00:00
    """
    if pd.isna(dt) or dt is None or dt == "":
        return "6_9"
    try:
        if isinstance(dt, time):
            minute_of_day = dt.hour * 60 + dt.minute
        else:
            ts = pd.Timestamp(dt)
            minute_of_day = ts.hour * 60 + ts.minute

        # Strictly consider all arrivals before 9:00 AM (< 540 minutes from midnight).
        # Any punch before 6:00 AM (e.g. 5:15 AM, 5:30 AM, 5:45 AM) is fully credited here.
        if minute_of_day < 540:
            return "6_9"
        elif 540 <= minute_of_day < 600:  # 9:00 to 9:59
            return "9_10"
        elif 600 <= minute_of_day < 660:  # 10:00 to 10:59
            return "10_11"
        elif 660 <= minute_of_day < 720:  # 11:00 to 11:59
            return "11_12"
        else:  # 12:00 PM and later
            return "after_12"
    except Exception:
        # Fallback to string regex if Timestamp parsing threw an exception
        try:
            s = str(dt).strip()
            match = re.search(r"(\d{1,2}):(\d{2})", s)
            if match:
                h = int(match.group(1))
                m = int(match.group(2))
                if "pm" in s.lower() and h < 12:
                    h += 12
                elif "am" in s.lower() and h == 12:
                    h = 0
                minute_of_day = h * 60 + m
                if minute_of_day < 540:
                    return "6_9"
                elif 540 <= minute_of_day < 600:
                    return "9_10"
                elif 600 <= minute_of_day < 660:
                    return "10_11"
                elif 660 <= minute_of_day < 720:
                    return "11_12"
                else:
                    return "after_12"
        except Exception:
            pass
        return "6_9"


def parse_state_format_data(
    raw_bytes: bytes,
    filename: str,
    ps_directory: dict[str, dict[str, str]] | None = None,
    exclude_incharge: bool = False,
    report_date_override: date | None = None,
    generated_at_override: datetime | None = None,
) -> StateFormatReport:
    """Parse raw attendance file and compute 14-column State Format metrics."""
    df = read_source_file(filename, raw_bytes)
    df["Panchayat LGD"] = df["Panchayat LGD"].map(_clean_lgd)
    df["Mandal Name"] = df["Mandal Name"].map(_clean_string)
    df["Panchayat Name"] = df["Panchayat Name"].map(_clean_string)
    df["First Attendence Status"] = df["First Attendence Status"].map(_clean_string)
    df["Second Attendence Status"] = df["Second Attendence Status"].map(_clean_string)
    df["_timestamp"] = df["First Attendence Datetime"].map(_parse_timestamp)

    valid = df.loc[df["Panchayat LGD"].ne("")].copy()
    if valid.empty:
        raise ValueError("No valid GP records with Panchayat LGD found in the uploaded file.")

    # Detect district name
    district_name = "Khammam"
    if "District Name" in valid.columns:
        d_series = valid["District Name"].dropna().map(_clean_string)
        d_series = d_series[d_series != ""]
        if not d_series.empty:
            district_name = _clean_name(d_series.mode().iloc[0]) or "Khammam"

    # Determine report date
    rep_date = report_date_override
    if not rep_date:
        valid_ts = valid["_timestamp"].dropna()
        if not valid_ts.empty:
            try:
                rep_date = valid_ts.dt.date.mode().iloc[0]
            except Exception:
                pass
    if not rep_date:
        match = re.search(r"(\d{1,2})[-_ ]([A-Za-z]{3})[-_ ](\d{4})", filename)
        if match:
            try:
                rep_date = datetime.strptime(match.group(0).replace("_", "-"), "%d-%b-%Y").date()
            except ValueError:
                pass
    if not rep_date:
        rep_date = date.today()
    now_dt = generated_at_override or datetime.now()
    date_str = rep_date.strftime("%d %B %Y")
    time_str = now_dt.strftime("%I:%M %p")
    subtitle = f"{date_str} - @ {time_str}"

    # Ensure directory is loaded: prioritize date-specific cache for this exact target date
    if not ps_directory:
        date_iso = rep_date.isoformat()
        date_cache_file = Path(f"data/ps_directory_cache_{date_iso}.json")
        if date_cache_file.exists():
            ps_directory = load_ps_directory_cache(date_cache_file)
        if not ps_directory:
            cache_file = Path("data/ps_directory_cache.json")
            ps_directory = load_ps_directory_cache(cache_file)

    # Deduplicate by Panchayat LGD (one record per GP)
    unique_gps: list[dict[str, Any]] = []
    directory = ps_directory or {}

    for lgd, group in valid.groupby("Panchayat LGD", sort=False, dropna=False):
        chosen = group.loc[group["First Attendence Status"].ne("")]
        row = chosen.iloc[0] if not chosen.empty else group.iloc[0]

        lgd_str = str(lgd)
        dir_info = directory.get(lgd_str, {})
        nature_of_posting = (
            _clean_name(dir_info.get("nature_of_posting", ""))
            or _clean_name(row.get("Nature of Posting", ""))
        )
        is_incharge = "incharge" in nature_of_posting.casefold() or "additional charge" in nature_of_posting.casefold()

        mandal_name = _clean_name(row.get("Mandal Name", "")) or "(Unspecified)"
        gp_name = _clean_name(row.get("Panchayat Name", ""))

        first_st = str(row.get("First Attendence Status", "")).strip()
        second_st = str(row.get("Second Attendence Status", "")).strip()
        combined_st = f"{first_st} {second_st}".lower()

        # Attendance classification
        is_present = _is_present_status(first_st) or _is_present_status(second_st)
        is_meeting_training = ("meeting" in combined_st or "training" in combined_st) and not is_present
        is_leave = "leave" in combined_st and not (is_present or is_meeting_training)
        is_not_reported = not (is_present or is_meeting_training or is_leave)
        is_reported = is_present or is_meeting_training

        # Arrival bucket classification (for all reported PS: both GP attended and Meeting/Training)
        arrival_bucket = ""
        if is_reported:
            ts_val = row.get("_timestamp")
            if pd.isna(ts_val) or ts_val is None:
                sec_ts = row.get("Second Attendence Datetime")
                if sec_ts and not pd.isna(sec_ts):
                    ts_val = _parse_timestamp(sec_ts)
            arrival_bucket = _classify_arrival_bucket(ts_val)

        # Full time working PS status
        is_full_time = not is_incharge

        unique_gps.append({
            "lgd": lgd_str,
            "mandal": mandal_name,
            "gp": gp_name,
            "is_incharge": is_incharge,
            "is_full_time": is_full_time,
            "is_present": is_present,
            "arrival_bucket": arrival_bucket,
            "is_meeting_training": is_meeting_training,
            "is_leave": is_leave,
            "is_not_reported": is_not_reported,
            "is_reported": is_reported,
        })

    if not unique_gps:
        raise ValueError("No eligible GP records found.")

    records_df = pd.DataFrame(unique_gps)

    # Group by Mandal
    mandal_list: list[StateFormatRow] = []
    for mandal, m_group in records_df.groupby("mandal", sort=False):
        # Total No. of GPs (Col 3) is always the complete GP count; never exclude incharge from Col 3
        total_gps = len(m_group)
        full_time = int(m_group["is_full_time"].sum())

        # If user chooses to exclude incharge, only evaluate full-time regular PS for attendance (Cols 5-14)
        if exclude_incharge:
            eval_mask = m_group["is_full_time"]
        else:
            eval_mask = pd.Series(True, index=m_group.index)
        
        b_6_9 = int(((m_group["arrival_bucket"] == "6_9") & m_group["is_reported"] & eval_mask).sum())
        b_9_10 = int(((m_group["arrival_bucket"] == "9_10") & m_group["is_reported"] & eval_mask).sum())
        b_10_11 = int(((m_group["arrival_bucket"] == "10_11") & m_group["is_reported"] & eval_mask).sum())
        b_11_12 = int(((m_group["arrival_bucket"] == "11_12") & m_group["is_reported"] & eval_mask).sum())
        b_after_12 = int(((m_group["arrival_bucket"] == "after_12") & m_group["is_reported"] & eval_mask).sum())
        
        # Col 11: Total No.of PSs attended GP (physically attended the Gram Panchayat)
        total_attended_gp = int((m_group["is_present"] & eval_mask).sum())
        # Col 12: No.of PSs reported to Mtg / Trngs today
        mtg_trng = int((m_group["is_meeting_training"] & eval_mask).sum())
        # Col 13: No.of PSs on Leave Today
        on_leave = int((m_group["is_leave"] & eval_mask).sum())
        # Col 14: No.of PS Not reported
        not_rep = int((m_group["is_not_reported"] & eval_mask).sum())

        # Percentage before 9 AM (Col 10):
        # User defined formula: (6 AM - 9 AM) / No.of PS in which full time working * 100
        # If incharge is excluded, denominator is full_time (Col 4).
        # If incharge is included, denominator is total_gps (Col 3).
        if exclude_incharge:
            denominator = full_time if full_time > 0 else total_gps
        else:
            denominator = total_gps if total_gps > 0 else full_time
        pct_b9 = round(min(100.0, (b_6_9 / denominator * 100)), 2) if denominator > 0 else 0.0

        mandal_list.append(StateFormatRow(
            sl_no=0,
            mandal_name=mandal,
            total_gps=total_gps,
            full_time_working=full_time,
            b_6_9=b_6_9,
            b_9_10=b_9_10,
            b_10_11=b_10_11,
            b_11_12=b_11_12,
            b_after_12=b_after_12,
            pct_before_9=pct_b9,
            total_attended=total_attended_gp,
            meeting_training=mtg_trng,
            on_leave=on_leave,
            not_reported=not_rep,
        ))

    # Sort descending by % of PS Reported before 9 AM ↓ (Col 10)
    mandal_list.sort(key=lambda r: (r.pct_before_9, r.b_6_9, r.total_attended), reverse=True)

    # Assign Sl. No. (1, 2, 3...)
    for idx, r in enumerate(mandal_list, start=1):
        r.sl_no = idx

    # Calculate District Total Row
    tot_gps = sum(r.total_gps for r in mandal_list)
    tot_ft = sum(r.full_time_working for r in mandal_list)
    tot_6_9 = sum(r.b_6_9 for r in mandal_list)
    tot_9_10 = sum(r.b_9_10 for r in mandal_list)
    tot_10_11 = sum(r.b_10_11 for r in mandal_list)
    tot_11_12 = sum(r.b_11_12 for r in mandal_list)
    tot_aft12 = sum(r.b_after_12 for r in mandal_list)
    tot_att = sum(r.total_attended for r in mandal_list)
    tot_mtg = sum(r.meeting_training for r in mandal_list)
    tot_leave = sum(r.on_leave for r in mandal_list)
    tot_not_rep = sum(r.not_reported for r in mandal_list)

    if exclude_incharge:
        tot_denom = tot_ft if tot_ft > 0 else tot_gps
    else:
        tot_denom = tot_gps if tot_gps > 0 else tot_ft
    overall_pct_b9 = round(min(100.0, (tot_6_9 / tot_denom * 100)), 2) if tot_denom > 0 else 0.0

    total_row = StateFormatRow(
        sl_no="",
        mandal_name="Total",
        total_gps=tot_gps,
        full_time_working=tot_ft,
        b_6_9=tot_6_9,
        b_9_10=tot_9_10,
        b_10_11=tot_10_11,
        b_11_12=tot_11_12,
        b_after_12=tot_aft12,
        pct_before_9=overall_pct_b9,
        total_attended=tot_att,
        meeting_training=tot_mtg,
        on_leave=tot_leave,
        not_reported=tot_not_rep,
    )

    return StateFormatReport(
        district_name=district_name,
        report_date=rep_date,
        report_date_str=date_str,
        generated_time_str=time_str,
        subtitle=subtitle,
        exclude_incharge=exclude_incharge,
        total_gps=tot_gps,
        total_working_ps=tot_ft,
        total_attended=tot_att,
        overall_pct_before_9=overall_pct_b9,
        rows=mandal_list,
        total_row=total_row,
    )


def generate_state_format_pdf(report: StateFormatReport, output_path: str | Path) -> Path:
    """Generate official landscape PDF matching media_1794551547618_ce08bf3e.png format."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Landscape A4: 297mm x 210mm
    doc = SimpleDocTemplate(
        str(out),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story: list[Any] = []

    # Title: Red Bold, Centered
    title_style = ParagraphStyle(
        "StateFormatTitle",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=HexColor("#990000"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    story.append(Paragraph("Mandal wise Status of Panchayat Secretaries Attendance With Time", title_style))

    # Subtitle: Blue Bold, Centered
    sub_style = ParagraphStyle(
        "StateFormatSubtitle",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=HexColor("#003399"),
        alignment=TA_CENTER,
        spaceAfter=7,
    )
    story.append(Paragraph(report.subtitle, sub_style))

    # Build 14-Column Table Data
    # Row 0: Tier 1 Header
    hdr_row0 = [
        "Sl.\nNo.",
        "Mandal Name",
        "Total No.\nof GPs",
        "No.of PS\nin which\nfull time\nworking",
        "No.of Panchayat Secretaries reported",
        "", "", "", "", "", "", "", "", "",
    ]
    # Row 1: Tier 2 Header
    hdr_row1 = [
        "", "", "", "",
        "6 AM -\n9 AM",
        "9 AM -\n10 AM",
        "10 AM -\n11 AM",
        "11 AM -\n12 Noon",
        "After 12\nNoon",
        "% of PS\nReported\nbefore 9 AM\n↓",
        "Total No.of\nPSs attended\nGP",
        "No.of PSs\nreported to\nMtg / Trngs\ntoday",
        "No.of PSs\non Leave\nToday",
        "No.of PS\nNot\nreported",
    ]
    # Row 2: Column numbers 1 to 14
    hdr_row2 = [str(i) for i in range(1, 15)]

    table_data = [hdr_row0, hdr_row1, hdr_row2]

    # Data rows
    for r in report.rows:
        pct_display = f"{r.pct_before_9:.2f}%" if r.pct_before_9 > 0 else "0.00%"
        table_data.append([
            str(r.sl_no),
            r.mandal_name,
            str(r.total_gps),
            str(r.full_time_working),
            str(r.b_6_9),
            str(r.b_9_10),
            str(r.b_10_11),
            str(r.b_11_12),
            str(r.b_after_12),
            pct_display,
            str(r.total_attended),
            str(r.meeting_training),
            str(r.on_leave),
            str(r.not_reported),
        ])

    # Total Row
    tot = report.total_row
    tot_pct_display = f"{tot.pct_before_9:.2f}%" if tot.pct_before_9 > 0 else "0.00%"
    table_data.append([
        "",
        "Total",
        str(tot.total_gps),
        str(tot.full_time_working),
        str(tot.b_6_9),
        str(tot.b_9_10),
        str(tot.b_10_11),
        str(tot.b_11_12),
        str(tot.b_after_12),
        tot_pct_display,
        str(tot.total_attended),
        str(tot.meeting_training),
        str(tot.on_leave),
        str(tot.not_reported),
    ])

    # Table Column Widths (Sum = 277mm max available)
    col_widths = [
        10 * mm,  # 1: Sl. No.
        36 * mm,  # 2: Mandal Name
        18 * mm,  # 3: Total GPs
        22 * mm,  # 4: Full time working
        18 * mm,  # 5: 6-9 AM
        18 * mm,  # 6: 9-10 AM
        18 * mm,  # 7: 10-11 AM
        18 * mm,  # 8: 11-12 Noon
        18 * mm,  # 9: After 12 Noon
        23 * mm,  # 10: % before 9 AM
        21 * mm,  # 11: Total Attended
        22 * mm,  # 12: Mtg / Trng
        18 * mm,  # 13: Leave
        17 * mm,  # 14: Not Reported
    ]

    total_rows = len(table_data)
    total_data_row_idx = total_rows - 1

    t_style = TableStyle([
        # Header spans
        ("SPAN", (0, 0), (0, 1)),  # Sl. No.
        ("SPAN", (1, 0), (1, 1)),  # Mandal Name
        ("SPAN", (2, 0), (2, 1)),  # Total GPs
        ("SPAN", (3, 0), (3, 1)),  # Full time working
        ("SPAN", (4, 0), (13, 0)),  # Group header across 10 cols

        # Background Colors
        ("BACKGROUND", (0, 0), (-1, 2), HexColor("#EBF3FA")),  # Soft blue state header
        ("BACKGROUND", (0, total_data_row_idx), (-1, total_data_row_idx), HexColor("#F1F5F9")),  # Total row light fill

        # Alignment
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 3), (1, -1), "LEFT"),  # Mandal name left aligned
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # Fonts & Sizes
        ("FONTNAME", (0, 0), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 2), 7.5),
        ("LEADING", (0, 0), (-1, 2), 9.0),

        ("FONTNAME", (0, 3), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 3), (-1, -2), 7.5),
        ("LEADING", (0, 3), (-1, -2), 8.8),

        ("FONTNAME", (0, total_data_row_idx), (-1, total_data_row_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, total_data_row_idx), (-1, total_data_row_idx), 8.0),

        # Grid Borders
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#334155")),
        ("LINEBELOW", (0, 2), (-1, 2), 1.0, HexColor("#1E293B")),
        ("LINEABOVE", (0, total_data_row_idx), (-1, total_data_row_idx), 1.0, HexColor("#1E293B")),
        ("LINEBELOW", (0, total_data_row_idx), (-1, total_data_row_idx), 1.2, HexColor("#1E293B")),

        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
    ])

    report_table = Table(table_data, colWidths=col_widths, repeatRows=3, style=t_style)
    story.append(report_table)

    story.append(Spacer(1, 4 * mm))

    # Standardized Footer requested by user
    footer_text = (
        "Panchayat-Automation — Simplifying Panchayat Administration through Smart Reporting and Automation"
    )
    if report.exclude_incharge:
        footer_text += " | Incharge GPs Excluded (Regular Full-Time PS Only)"
    footer_style = ParagraphStyle(
        "StateFormatFooter",
        fontName="Helvetica",
        fontSize=7.2,
        leading=9,
        textColor=HexColor("#64748B"),
        alignment=TA_CENTER,
    )
    story.append(Paragraph(footer_text, footer_style))

    doc.build(story)
    return out


def generate_state_format_excel(report: StateFormatReport, output_path: str | Path) -> Path:
    """Generate official Excel spreadsheet matching media_1794551547618_ce08bf3e.png format."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "State Attendance Format"
    ws.views.sheetView[0].showGridLines = True

    # Palette
    title_font = Font(name="Calibri", size=13, bold=True, color="990000")
    sub_font = Font(name="Calibri", size=11, bold=True, color="003399")
    header_fill = PatternFill(start_color="EBF3FA", end_color="EBF3FA", fill_type="solid")
    header_font = Font(name="Calibri", size=9.5, bold=True, color="000000")
    num_hdr_font = Font(name="Calibri", size=9, bold=True, color="333333")
    data_font = Font(name="Calibri", size=9.5, color="000000")
    total_font = Font(name="Calibri", size=10, bold=True, color="000000")
    total_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border_side = Side(border_style="thin", color="334155")
    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )
    double_bottom = Side(border_style="double", color="1E293B")
    thick_top = Side(border_style="medium", color="1E293B")
    total_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thick_top,
        bottom=double_bottom,
    )

    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    # Row 1: Title
    ws.merge_cells("A1:N1")
    title_cell = ws["A1"]
    title_cell.value = "Mandal wise Status of Panchayat Secretaries Attendance With Time"
    title_cell.font = title_font
    title_cell.alignment = center_align
    ws.row_dimensions[1].height = 24

    # Row 2: Subtitle
    ws.merge_cells("A2:N2")
    sub_cell = ws["A2"]
    sub_cell.value = report.subtitle
    sub_cell.font = sub_font
    sub_cell.alignment = center_align
    ws.row_dimensions[2].height = 20

    # Row 3: Blank separator
    ws.row_dimensions[3].height = 8

    # Row 4 & 5: Tiered Header
    headers_r4 = [
        "Sl. No.", "Mandal Name", "Total No. of GPs", "No.of PS in which full time working",
        "No.of Panchayat Secretaries reported", "", "", "", "", "", "", "", "", ""
    ]
    headers_r5 = [
        "", "", "", "",
        "6 AM - 9 AM", "9 AM - 10 AM", "10 AM - 11 AM", "11 AM - 12 Noon", "After 12 Noon",
        "% of PS Reported before 9 AM ↓", "Total No.of PSs attended GP",
        "No.of PSs reported to Mtg / Trngs today", "No.of PSs on Leave Today", "No.of PS Not reported"
    ]
    headers_r6 = [str(i) for i in range(1, 15)]

    ws.append(headers_r4)  # Row 4
    ws.append(headers_r5)  # Row 5
    ws.append(headers_r6)  # Row 6

    # Merges for Header
    ws.merge_cells("A4:A5")
    ws.merge_cells("B4:B5")
    ws.merge_cells("C4:C5")
    ws.merge_cells("D4:D5")
    ws.merge_cells("E4:N4")

    ws.row_dimensions[4].height = 24
    ws.row_dimensions[5].height = 28
    ws.row_dimensions[6].height = 18

    for r_num in (4, 5, 6):
        for col_num in range(1, 15):
            c = ws.cell(row=r_num, column=col_num)
            c.fill = header_fill
            c.font = num_hdr_font if r_num == 6 else header_font
            c.alignment = center_align
            c.border = cell_border

    # Data Rows (Row 7 onwards)
    current_row = 7
    for r in report.rows:
        row_vals = [
            r.sl_no,
            r.mandal_name,
            r.total_gps,
            r.full_time_working,
            r.b_6_9,
            r.b_9_10,
            r.b_10_11,
            r.b_11_12,
            r.b_after_12,
            f"{r.pct_before_9:.2f}%",
            r.total_attended,
            r.meeting_training,
            r.on_leave,
            r.not_reported,
        ]
        ws.append(row_vals)
        ws.row_dimensions[current_row].height = 19
        for col_num in range(1, 15):
            c = ws.cell(row=current_row, column=col_num)
            c.font = data_font
            c.border = cell_border
            if col_num == 2:
                c.alignment = left_align
            elif col_num == 10:
                c.alignment = right_align
            else:
                c.alignment = center_align
        current_row += 1

    # Total Row
    tot = report.total_row
    tot_vals = [
        "",
        "Total",
        tot.total_gps,
        tot.full_time_working,
        tot.b_6_9,
        tot.b_9_10,
        tot.b_10_11,
        tot.b_11_12,
        tot.b_after_12,
        f"{tot.pct_before_9:.2f}%",
        tot.total_attended,
        tot.meeting_training,
        tot.on_leave,
        tot.not_reported,
    ]
    ws.append(tot_vals)
    ws.row_dimensions[current_row].height = 22
    for col_num in range(1, 15):
        c = ws.cell(row=current_row, column=col_num)
        c.font = total_font
        c.fill = total_fill
        c.border = total_border
        if col_num == 2:
            c.alignment = left_align
        elif col_num == 10:
            c.alignment = right_align
        else:
            c.alignment = center_align
    current_row += 1

    # Footer Row
    current_row += 1
    ws.merge_cells(f"A{current_row}:N{current_row}")
    footer_cell = ws[f"A{current_row}"]
    footer_text = "Panchayat-Automation — Simplifying Panchayat Administration through Smart Reporting and Automation"
    if report.exclude_incharge:
        footer_text += " | Incharge GPs Excluded (Regular Full-Time PS Only)"
    footer_cell.value = footer_text
    footer_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")
    footer_cell.alignment = center_align

    # Column Widths
    col_widths = {
        "A": 8,   # Sl. No.
        "B": 22,  # Mandal Name
        "C": 15,  # Total GPs
        "D": 18,  # Full time working
        "E": 14,  # 6-9 AM
        "F": 14,  # 9-10 AM
        "G": 14,  # 10-11 AM
        "H": 15,  # 11-12 Noon
        "I": 15,  # After 12 Noon
        "J": 18,  # % before 9 AM
        "K": 17,  # Total Attended
        "L": 19,  # Mtg / Trng
        "M": 15,  # Leave
        "N": 15,  # Not Reported
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    wb.save(str(out))
    return out

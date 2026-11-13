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
    percentage_row: dict[str, Any] | None = None

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
            "percentage_row": self.percentage_row,
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
    exclude_incharge: bool = True,
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

    # Ensure directory is loaded: prioritize date-specific online download data for this exact target date.
    # Never fall back to stale offline master cache files (e.g. data/ps_directory_cache.json).
    if not ps_directory:
        date_iso = rep_date.isoformat()
        date_cache_file = Path(f"data/ps_directory_cache_{date_iso}.json")
        if date_cache_file.exists():
            ps_directory = load_ps_directory_cache(date_cache_file)
        else:
            ps_directory = {}

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
        posting_lower = nature_of_posting.casefold()

        # Classify Nature of Posting across the 4 portal variants:
        # 1. Regular
        # 2. Incharge
        # 3. Fully Additional Charge (or Full Additional Charge)
        # 4. Blank (missing / empty / unassigned)
        # Requirement: While preparing the report, consider ONLY Regular.
        # Incharge, Fully Additional Charge, and Blank are NOT Regular.
        if (
            not posting_lower
            or posting_lower in {"nan", "none", "null", "na", "-", "."}
            or "incharge" in posting_lower
            or "charge" in posting_lower
            or "additional" in posting_lower
        ):
            is_regular = False
        elif "regular" in posting_lower:
            is_regular = True
        else:
            is_regular = False

        is_full_time = is_regular
        is_incharge = not is_regular

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
        is_reported = is_present or is_meeting_training or is_leave

        # Arrival bucket classification (for all reported PS: GP attended, Meeting/Training, and On Leave)
        arrival_bucket = ""
        if is_leave:
            # In official state reporting, secretaries on approved leave have notified
            # their absence prior to duty and are credited as reported in the before 9 AM (6-9 AM) bucket.
            arrival_bucket = "6_9"
        elif is_reported:
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
        
        b_6_9 = int(((m_group["arrival_bucket"] == "6_9") & eval_mask).sum())
        b_9_10 = int(((m_group["arrival_bucket"] == "9_10") & eval_mask).sum())
        b_10_11 = int(((m_group["arrival_bucket"] == "10_11") & eval_mask).sum())
        b_11_12 = int(((m_group["arrival_bucket"] == "11_12") & eval_mask).sum())
        b_after_12 = int(((m_group["arrival_bucket"] == "after_12") & eval_mask).sum())
        
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

    # Calculate Percentage Row (bottom summary row matching official state format)
    denom = tot_ft if exclude_incharge and tot_ft > 0 else (tot_gps if tot_gps > 0 else 1)
    percentage_row = {
        "sl_no": "",
        "mandal_name": "Percentage",
        "total_gps": "",
        "full_time_working": "",
        "b_6_9": round(tot_6_9 / denom * 100, 2) if denom > 0 else 0.0,
        "b_9_10": round(tot_9_10 / denom * 100, 2) if denom > 0 else 0.0,
        "b_10_11": round(tot_10_11 / denom * 100, 2) if denom > 0 else 0.0,
        "b_11_12": round(tot_11_12 / denom * 100, 2) if denom > 0 else 0.0,
        "b_after_12": round(tot_aft12 / denom * 100, 2) if denom > 0 else 0.0,
        "pct_before_9": "",
        "total_attended": round(tot_att / denom * 100, 2) if denom > 0 else 0.0,
        "meeting_training": round(tot_mtg / denom * 100, 2) if denom > 0 else 0.0,
        "on_leave": round(tot_leave / denom * 100, 2) if denom > 0 else 0.0,
        "not_reported": round(tot_not_rep / denom * 100, 2) if denom > 0 else 0.0,
    }

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
        percentage_row=percentage_row,
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

    # Line 1: District Name (Maroon/Red bold, Centered)
    dist_style = ParagraphStyle(
        "StateFormatDistrict",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=HexColor("#990000"),
        alignment=TA_CENTER,
        spaceAfter=1.5,
    )
    story.append(Paragraph(f"District Name: {report.district_name}", dist_style))

    # Line 2: Report Title (Maroon/Red bold, Centered)
    title_style = ParagraphStyle(
        "StateFormatTitle",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=HexColor("#990000"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    story.append(Paragraph("Mandal wise Status of Panchayat Secretaries Attendance With Time", title_style))

    # Line 3: Subtitle / Timestamp (Blue bold, Centered)
    sub_style = ParagraphStyle(
        "StateFormatSubtitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=HexColor("#003399"),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    story.append(Paragraph(report.subtitle, sub_style))

    # Build 14-Column Table Data
    # Row 0: Tier 1 Header
    hdr_row0 = [
        "Sl.\nNo.",
        "Mandal Name",
        "Total\nNo. of GPs",
        "No.of PS in\nwhich full time\nworking",
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
        "No.of PSs on\nLeave Today",
        "No.of PS Not\nreported",
    ]
    # Row 2: Column numbers matching manual government reporting format
    hdr_row2 = ["1", "2", "3", "", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]

    table_data = [hdr_row0, hdr_row1, hdr_row2]

    # Data rows: Blanks for zero counts in columns 6, 7, 8, 9, 12, 13
    for r in report.rows:
        pct_display = f"{r.pct_before_9:.2f}"
        table_data.append([
            str(r.sl_no),
            r.mandal_name,
            str(r.total_gps),
            str(r.full_time_working),
            str(r.b_6_9) if r.b_6_9 > 0 else "",
            str(r.b_9_10) if r.b_9_10 > 0 else "",
            str(r.b_10_11) if r.b_10_11 > 0 else "",
            str(r.b_11_12) if r.b_11_12 > 0 else "",
            str(r.b_after_12) if r.b_after_12 > 0 else "",
            pct_display,
            str(r.total_attended) if r.total_attended > 0 else "",
            str(r.meeting_training) if r.meeting_training > 0 else "",
            str(r.on_leave) if r.on_leave > 0 else "",
            str(r.not_reported),
        ])

    # Total Row
    tot = report.total_row
    tot_pct_display = f"{tot.pct_before_9:.2f}"
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

    # Percentage Row (Bottom row summary matching official state format)
    has_percentage_row = bool(report.percentage_row)
    if has_percentage_row:
        p = report.percentage_row  # type: ignore[assignment]
        table_data.append([
            "",
            "Percentage",
            "",
            "",
            f"{p['b_6_9']:.2f}",
            f"{p['b_9_10']:.2f}",
            f"{p['b_10_11']:.2f}",
            f"{p['b_11_12']:.2f}",
            f"{p['b_after_12']:.2f}",
            "",
            f"{p['total_attended']:.2f}",
            f"{p['meeting_training']:.2f}",
            f"{p['on_leave']:.2f}",
            f"{p['not_reported']:.2f}",
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
    total_data_row_idx = total_rows - 2 if has_percentage_row else total_rows - 1

    t_style_cmds = [
        # Header spans
        ("SPAN", (0, 0), (0, 1)),  # Sl. No.
        ("SPAN", (1, 0), (1, 1)),  # Mandal Name
        ("SPAN", (2, 0), (2, 1)),  # Total GPs
        ("SPAN", (3, 0), (3, 1)),  # Full time working
        ("SPAN", (4, 0), (13, 0)),  # Group header across 10 cols

        # Background Colors
        ("BACKGROUND", (0, 0), (-1, 2), HexColor("#D9E8F5")),  # State light ice blue header

        # Alignment
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 3), (1, -1), "LEFT"),  # Mandal name left aligned
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # Fonts & Sizes
        ("FONTNAME", (0, 0), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 2), 7.2),
        ("LEADING", (0, 0), (-1, 2), 8.8),

        ("FONTNAME", (0, 3), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 3), (-1, -1), 7.5),
        ("LEADING", (0, 3), (-1, -1), 8.8),

        # Highlight % column (Col index 9) in Red Bold for data rows & Total row
        ("TEXTCOLOR", (9, 3), (9, total_data_row_idx), HexColor("#C00000")),
        ("FONTNAME", (9, 3), (9, total_data_row_idx), "Helvetica-Bold"),

        # Total Row Bold
        ("FONTNAME", (0, total_data_row_idx), (-1, total_data_row_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, total_data_row_idx), (-1, total_data_row_idx), 7.8),

        # Grid Borders
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#334155")),
        ("LINEBELOW", (0, 2), (-1, 2), 1.0, HexColor("#000000")),
        ("LINEABOVE", (0, total_data_row_idx), (-1, total_data_row_idx), 1.0, HexColor("#000000")),

        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
    ]

    if has_percentage_row:
        pct_row_idx = total_rows - 1
        t_style_cmds.extend([
            ("FONTNAME", (0, pct_row_idx), (-1, pct_row_idx), "Helvetica-Bold"),
            ("FONTSIZE", (0, pct_row_idx), (-1, pct_row_idx), 7.8),
            ("TEXTCOLOR", (0, pct_row_idx), (-1, pct_row_idx), HexColor("#C00000")),
            ("LINEBELOW", (0, total_data_row_idx), (-1, total_data_row_idx), 0.5, HexColor("#000000")),
            ("LINEBELOW", (0, pct_row_idx), (-1, pct_row_idx), 1.2, HexColor("#000000")),
        ])
    else:
        t_style_cmds.append(("LINEBELOW", (0, total_data_row_idx), (-1, total_data_row_idx), 1.2, HexColor("#000000")))

    t_style = TableStyle(t_style_cmds)
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

    # Row 1: District Name
    ws.merge_cells("A1:N1")
    dist_cell = ws["A1"]
    dist_cell.value = f"District Name: {report.district_name}"
    dist_cell.font = title_font
    dist_cell.alignment = center_align
    ws.row_dimensions[1].height = 22

    # Row 2: Title
    ws.merge_cells("A2:N2")
    title_cell = ws["A2"]
    title_cell.value = "Mandal wise Status of Panchayat Secretaries Attendance With Time"
    title_cell.font = title_font
    title_cell.alignment = center_align
    ws.row_dimensions[2].height = 22

    # Row 3: Subtitle
    ws.merge_cells("A3:N3")
    sub_cell = ws["A3"]
    sub_cell.value = report.subtitle
    sub_cell.font = sub_font
    sub_cell.alignment = center_align
    ws.row_dimensions[3].height = 19

    # Row 4: Blank separator
    ws.row_dimensions[4].height = 6

    # Row 5 & 6: Tiered Header
    headers_r5 = [
        "Sl. No.", "Mandal Name", "Total No. of GPs", "No.of PS in which full time working",
        "No.of Panchayat Secretaries reported", "", "", "", "", "", "", "", "", ""
    ]
    headers_r6 = [
        "", "", "", "",
        "6 AM - 9 AM", "9 AM - 10 AM", "10 AM - 11 AM", "11 AM - 12 Noon", "After 12 Noon",
        "% of PS Reported before 9 AM ↓", "Total No.of PSs attended GP",
        "No.of PSs reported to Mtg / Trngs today", "No.of PSs on Leave Today", "No.of PS Not reported"
    ]
    # Row 7: Column numbers matching manual government report format
    headers_r7 = ["1", "2", "3", "", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]

    ws.append(headers_r5)  # Row 5
    ws.append(headers_r6)  # Row 6
    ws.append(headers_r7)  # Row 7

    # Merges for Header
    ws.merge_cells("A5:A6")
    ws.merge_cells("B5:B6")
    ws.merge_cells("C5:C6")
    ws.merge_cells("D5:D6")
    ws.merge_cells("E5:N5")

    ws.row_dimensions[5].height = 24
    ws.row_dimensions[6].height = 28
    ws.row_dimensions[7].height = 18

    for r_num in (5, 6, 7):
        for col_num in range(1, 15):
            c = ws.cell(row=r_num, column=col_num)
            c.fill = header_fill
            c.font = num_hdr_font if r_num == 7 else header_font
            c.alignment = center_align
            c.border = cell_border

    # Data Rows (Row 8 onwards)
    current_row = 8
    red_pct_font = Font(name="Calibri", size=9.5, bold=True, color="C00000")
    for r in report.rows:
        row_vals = [
            r.sl_no,
            r.mandal_name,
            r.total_gps,
            r.full_time_working,
            r.b_6_9 if r.b_6_9 > 0 else "",
            r.b_9_10 if r.b_9_10 > 0 else "",
            r.b_10_11 if r.b_10_11 > 0 else "",
            r.b_11_12 if r.b_11_12 > 0 else "",
            r.b_after_12 if r.b_after_12 > 0 else "",
            f"{r.pct_before_9:.2f}",
            r.total_attended if r.total_attended > 0 else "",
            r.meeting_training if r.meeting_training > 0 else "",
            r.on_leave if r.on_leave > 0 else "",
            r.not_reported,
        ]
        ws.append(row_vals)
        ws.row_dimensions[current_row].height = 19
        for col_num in range(1, 15):
            c = ws.cell(row=current_row, column=col_num)
            c.font = red_pct_font if col_num == 10 else data_font
            c.border = cell_border
            if col_num == 2:
                c.alignment = left_align
            elif col_num == 10:
                c.alignment = center_align
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
        f"{tot.pct_before_9:.2f}",
        tot.total_attended,
        tot.meeting_training,
        tot.on_leave,
        tot.not_reported,
    ]
    ws.append(tot_vals)
    ws.row_dimensions[current_row].height = 22
    for col_num in range(1, 15):
        c = ws.cell(row=current_row, column=col_num)
        c.font = Font(name="Calibri", size=10, bold=True, color="C00000" if col_num == 10 else "000000")
        c.fill = total_fill
        c.border = total_border
        if col_num == 2:
            c.alignment = left_align
        else:
            c.alignment = center_align
    current_row += 1

    # Percentage Row (Bottom row summary matching official state format)
    if report.percentage_row:
        p = report.percentage_row
        pct_row_vals = [
            "",
            "Percentage",
            "",
            "",
            f"{p['b_6_9']:.2f}",
            f"{p['b_9_10']:.2f}",
            f"{p['b_10_11']:.2f}",
            f"{p['b_11_12']:.2f}",
            f"{p['b_after_12']:.2f}",
            "",
            f"{p['total_attended']:.2f}",
            f"{p['meeting_training']:.2f}",
            f"{p['on_leave']:.2f}",
            f"{p['not_reported']:.2f}",
        ]
        ws.append(pct_row_vals)
        ws.row_dimensions[current_row].height = 22
        pct_font = Font(name="Calibri", size=10, bold=True, color="C00000")
        for col_num in range(1, 15):
            c = ws.cell(row=current_row, column=col_num)
            c.font = pct_font
            c.fill = total_fill
            c.border = total_border
            if col_num == 2:
                c.alignment = left_align
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

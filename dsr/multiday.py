"""Multiple Days PS Attendance & DSR Consolidation Engine (PDF & Excel).

Reuses validated GM-R 1.2.7 / 1.2.11 / 1.2.10 parsing from `dsr.pdf_generator`
to aggregate attendance punctuality, DSR completion, and recurring exceptions
across multiple dates or multiple daily portal spreadsheets.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date, datetime, time
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
from dsr.pdf_generator import (
    InputValidationError,
    PercentBar,
    ReportData,
    _clean_string,
    _parse_timestamp,
    analyze_attendance,
    merge_ps_directories,
    parse_ps_directory_file,
    read_source_file,
)


@dataclass
class MultiDayDateSummary:
    serial: int
    report_date: date
    date_label: str
    source_filename: str
    total_gps: int
    submitted: int
    attendance_pct: float
    before_cutoff: int
    before_cutoff_pct: float
    after_cutoff: int
    on_leave: int
    meeting_training: int
    pending: int
    present_ps: int
    dsr_entered: int
    dsr_pct: float
    dsr_pending: int


@dataclass
class MultiDayReportData:
    district_name: str
    mandal_filter: str
    start_date: date
    end_date: date
    days_count: int
    cutoff_time_str: str
    cutoff_label: str
    unique_gp_count: int
    date_summaries: list[MultiDayDateSummary] = field(default_factory=list)
    mandal_summaries: list[dict[str, Any]] = field(default_factory=list)
    gp_summaries: list[dict[str, Any]] = field(default_factory=list)
    defaulter_rows: list[dict[str, Any]] = field(default_factory=list)
    overall_totals: dict[str, Any] = field(default_factory=dict)
    generated_time_str: str = ""

    def __post_init__(self) -> None:
        if not self.generated_time_str:
            self.generated_time_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")


def _extract_single_day_reports(
    daily_sources: list[tuple[str, bytes]],
    combined_dir: dict[str, dict[str, str]],
    cutoff_time: str | time | None,
) -> list[tuple[str, ReportData]]:
    """Parse one or more files into chronological (label, ReportData) slices."""
    if not daily_sources:
        raise InputValidationError("Please upload at least one GM-R 1.2.7 attendance spreadsheet.")

    results: list[tuple[str, ReportData]] = []
    if len(daily_sources) == 1:
        filename, raw_bytes = daily_sources[0]
        frame = read_source_file(filename, raw_bytes)
        if "First Attendence Datetime" in frame.columns:
            stamps = frame["First Attendence Datetime"].map(_parse_timestamp)
            valid_dates = sorted({d.date() for d in stamps.dropna() if hasattr(d, "date")})
            if len(valid_dates) >= 2:
                date_series = stamps.map(lambda v: v.date() if pd.notna(v) and hasattr(v, "date") else None)
                for dt_val in valid_dates:
                    sub = frame.loc[date_series == dt_val].copy()
                    if not sub.empty:
                        rep = analyze_attendance(
                            sub,
                            filename=filename,
                            ps_directory=combined_dir,
                            cutoff_time=cutoff_time,
                            sort_by="before_9",
                        )
                        rep.report_date = dt_val
                        results.append((f"{filename} ({dt_val:%d-%b-%Y})", rep))
        if not results:
            rep = analyze_attendance(
                frame,
                filename=filename,
                ps_directory=combined_dir,
                cutoff_time=cutoff_time,
                sort_by="before_9",
            )
            results.append((filename, rep))
    else:
        for filename, raw_bytes in daily_sources:
            frame = read_source_file(filename, raw_bytes)
            rep = analyze_attendance(
                frame,
                filename=filename,
                ps_directory=combined_dir,
                cutoff_time=cutoff_time,
                sort_by="before_9",
            )
            results.append((filename, rep))

    results.sort(key=lambda item: (item[1].report_date, item[0].casefold()))
    return results


def _filter_report_mandal(rep: ReportData, mandal_filter: str) -> ReportData:
    """Restrict single-day ReportData metrics to one Mandal when requested."""
    clean_m = mandal_filter.strip()
    if not clean_m:
        return rep

    target_cf = clean_m.casefold()
    matched_gp_rows = [
        r for r in (rep.all_gp_rows or [])
        if _clean_string(r.get("mandal")).casefold() == target_cf
    ]
    if not matched_gp_rows:
        # Try partial substring match only if unique mandal matches
        mandal_names = sorted({
            _clean_string(r.get("mandal"))
            for r in (rep.all_gp_rows or [])
            if target_cf in _clean_string(r.get("mandal")).casefold()
        })
        if len(mandal_names) == 1:
            exact_cf = mandal_names[0].casefold()
            matched_gp_rows = [
                r for r in (rep.all_gp_rows or [])
                if _clean_string(r.get("mandal")).casefold() == exact_cf
            ]

    if not matched_gp_rows:
        raise InputValidationError(
            f"Mandal '{clean_m}' was not found in the uploaded attendance files."
        )

    matched_mandals = [
        m for m in rep.mandal_rows
        if m["mandal"].strip().casefold() == matched_gp_rows[0]["mandal"].strip().casefold()
    ]
    matched_dsr = [
        m for m in rep.dsr_mandal_rows
        if m["mandal"].strip().casefold() == matched_gp_rows[0]["mandal"].strip().casefold()
    ]

    total_gps = len(matched_gp_rows)
    att_sub = sum(1 for r in matched_gp_rows if r.get("submitted"))
    before_c = sum(1 for r in matched_gp_rows if r.get("before_9"))
    on_leave = sum(1 for r in matched_gp_rows if r.get("on_leave"))
    mtg = sum(1 for r in matched_gp_rows if r.get("meeting_training"))
    pending = sum(1 for r in matched_gp_rows if r.get("is_pending"))
    pres_ps = sum(1 for r in matched_gp_rows if r.get("dsr_eligible"))
    dsr_ent = sum(1 for r in matched_gp_rows if r.get("dsr_entered"))
    dsr_pend = sum(1 for r in matched_gp_rows if r.get("dsr_eligible") and not r.get("dsr_entered"))

    return ReportData(
        district_name=rep.district_name,
        report_date=rep.report_date,
        source_row_count=len(matched_gp_rows),
        unique_gp_count=total_gps,
        missing_lgd_rows=0,
        duplicate_lgd_rows=0,
        conflicts=[],
        mandal_rows=matched_mandals,
        district_total={
            "total_gps": total_gps,
            "attendance_submitted": att_sub,
            "attendance_pct": (att_sub / total_gps * 100.0) if total_gps else 0.0,
            "before_9": before_c,
            "before_9_pct": (before_c / total_gps * 100.0) if total_gps else 0.0,
            "on_leave": on_leave,
            "meeting_training": mtg,
            "pending": pending,
        },
        pending_rows=[r for r in rep.pending_rows if r["mandal"].casefold() == matched_gp_rows[0]["mandal"].casefold()],
        leave_rows=[r for r in rep.leave_rows if r["mandal"].casefold() == matched_gp_rows[0]["mandal"].casefold()],
        meeting_training_rows=[r for r in rep.meeting_training_rows if r["mandal"].casefold() == matched_gp_rows[0]["mandal"].casefold()],
        after_9_rows=[r for r in rep.after_9_rows if r["mandal"].casefold() == matched_gp_rows[0]["mandal"].casefold()],
        dsr_mandal_rows=matched_dsr,
        dsr_district_total={
            "total_gps": total_gps,
            "present_ps": pres_ps,
            "dsr_entered": dsr_ent,
            "dsr_pct": (dsr_ent / pres_ps * 100.0) if pres_ps else 0.0,
            "dsr_pending": dsr_pend,
        },
        dsr_pending_rows=[r for r in rep.dsr_pending_rows if r["mandal"].casefold() == matched_gp_rows[0]["mandal"].casefold()],
        all_gp_rows=matched_gp_rows,
        cutoff_time_str=rep.cutoff_time_str,
        cutoff_label=rep.cutoff_label,
        sort_by=rep.sort_by,
    )


def process_multiday_attendance_files(
    daily_sources: list[tuple[str, bytes]],
    presentees_source: tuple[str, bytes] | None = None,
    absentees_source: tuple[str, bytes] | None = None,
    ps_directory: dict[str, dict[str, str]] | None = None,
    mandal_name: str = "",
    cutoff_time: str | time | None = "09:00",
) -> MultiDayReportData:
    """Aggregate attendance & DSR metrics across multiple days / files."""
    dir_sources: list[tuple[str, bytes]] = []
    if presentees_source and presentees_source[1]:
        dir_sources.append(presentees_source)
    if absentees_source and absentees_source[1]:
        dir_sources.append(absentees_source)

    parsed_dir: dict[str, dict[str, str]] = {}
    for src_name, src_bytes in dir_sources:
        parsed_dir = merge_ps_directories(parsed_dir, parse_ps_directory_file(src_name, src_bytes))
    combined_dir = merge_ps_directories(parsed_dir, ps_directory or {})

    raw_slices = _extract_single_day_reports(daily_sources, combined_dir, cutoff_time)
    clean_mandal = (mandal_name or "").strip()
    day_slices: list[tuple[str, ReportData]] = [
        (lbl, _filter_report_mandal(rep, clean_mandal))
        for lbl, rep in raw_slices
    ]

    first_rep = day_slices[0][1]
    district_name = first_rep.district_name
    mandal_filter_canonical = (
        day_slices[0][1].all_gp_rows[0]["mandal"]
        if clean_mandal and day_slices[0][1].all_gp_rows
        else clean_mandal
    )

    date_labels: list[str] = []
    seen_labels: dict[str, int] = {}
    date_summaries: list[MultiDayDateSummary] = []

    mandal_acc: dict[str, dict[str, Any]] = {}
    gp_acc: dict[str, dict[str, Any]] = {}

    for idx, (src_name, rep) in enumerate(day_slices, start=1):
        base_lbl = f"{rep.report_date:%d-%b-%Y}"
        count = seen_labels.get(base_lbl, 0) + 1
        seen_labels[base_lbl] = count
        col_lbl = base_lbl if count == 1 else f"{base_lbl} #{count}"
        date_labels.append(col_lbl)

        dt = rep.district_total
        dsrt = rep.dsr_district_total
        date_summaries.append(
            MultiDayDateSummary(
                serial=idx,
                report_date=rep.report_date,
                date_label=col_lbl,
                source_filename=Path(src_name).name,
                total_gps=int(dt["total_gps"]),
                submitted=int(dt["attendance_submitted"]),
                attendance_pct=float(dt["attendance_pct"]),
                before_cutoff=int(dt["before_9"]),
                before_cutoff_pct=float(dt["before_9_pct"]),
                after_cutoff=len(rep.after_9_rows),
                on_leave=int(dt["on_leave"]),
                meeting_training=int(dt["meeting_training"]),
                pending=int(dt["pending"]),
                present_ps=int(dsrt["present_ps"]),
                dsr_entered=int(dsrt["dsr_entered"]),
                dsr_pct=float(dsrt["dsr_pct"]),
                dsr_pending=int(dsrt["dsr_pending"]),
            )
        )

        # Accumulate Mandal metrics
        for m in rep.mandal_rows:
            m_name = m["mandal"]
            m_key = m_name.strip().casefold()
            acc = mandal_acc.setdefault(
                m_key,
                {
                    "mandal": m_name,
                    "max_gps": 0,
                    "days_tracked": 0,
                    "att_pct_sum": 0.0,
                    "before_pct_sum": 0.0,
                    "dsr_pct_sum": 0.0,
                    "total_gps_sum": 0,
                    "submitted_sum": 0,
                    "before_sum": 0,
                    "pending_sum": 0,
                    "after_sum": 0,
                    "present_ps_sum": 0,
                    "dsr_entered_sum": 0,
                    "dsr_pending_sum": 0,
                },
            )
            acc["days_tracked"] += 1
            acc["max_gps"] = max(acc["max_gps"], int(m.get("total_gps", 0)))
            acc["total_gps_sum"] += int(m.get("total_gps", 0))
            acc["submitted_sum"] += int(m.get("attendance_submitted", 0))
            acc["before_sum"] += int(m.get("before_9", 0))
            acc["pending_sum"] += int(m.get("pending", 0))
            acc["after_sum"] += int(
                max(0, int(m.get("attendance_submitted", 0)) - int(m.get("before_9", 0)) - int(m.get("on_leave", 0)) - int(m.get("meeting_training", 0)))
            )
            acc["present_ps_sum"] += int(m.get("present_ps", 0))
            acc["dsr_entered_sum"] += int(m.get("dsr_entered", 0))
            acc["dsr_pending_sum"] += int(m.get("dsr_pending", 0))
            acc["att_pct_sum"] += float(m.get("attendance_pct", 0.0))
            acc["before_pct_sum"] += float(m.get("before_9_pct", 0.0))
            acc["dsr_pct_sum"] += float(m.get("dsr_pct", 0.0))

        # Accumulate GP metrics
        for gp_row in rep.all_gp_rows or []:
            lgd = str(gp_row.get("lgd") or f"{gp_row.get('mandal')}|{gp_row.get('gp')}")
            gp_entry = gp_acc.setdefault(
                lgd,
                {
                    "lgd": lgd,
                    "mandal": gp_row.get("mandal", ""),
                    "gp": gp_row.get("gp", ""),
                    "ps_name": gp_row.get("ps_name", ""),
                    "mobile": gp_row.get("mobile", ""),
                    "nature_of_posting": gp_row.get("nature_of_posting", ""),
                    "designation": gp_row.get("designation", ""),
                    "days_tracked": 0,
                    "days_submitted": 0,
                    "days_before_cutoff": 0,
                    "days_after_cutoff": 0,
                    "days_leave": 0,
                    "days_pending": 0,
                    "days_dsr_eligible": 0,
                    "days_dsr_entered": 0,
                    "days_dsr_pending": 0,
                    "day_status_map": {},
                },
            )
            if not gp_entry["ps_name"] and gp_row.get("ps_name"):
                gp_entry["ps_name"] = gp_row["ps_name"]
            if not gp_entry["mobile"] and gp_row.get("mobile"):
                gp_entry["mobile"] = gp_row["mobile"]
            if not gp_entry["nature_of_posting"] and gp_row.get("nature_of_posting"):
                gp_entry["nature_of_posting"] = gp_row["nature_of_posting"]
            if not gp_entry["designation"] and gp_row.get("designation"):
                gp_entry["designation"] = gp_row["designation"]

            gp_entry["days_tracked"] += 1
            if gp_row.get("submitted"):
                gp_entry["days_submitted"] += 1
            if gp_row.get("before_9"):
                gp_entry["days_before_cutoff"] += 1
            if gp_row.get("after_9"):
                gp_entry["days_after_cutoff"] += 1
            if gp_row.get("on_leave") or gp_row.get("meeting_training"):
                gp_entry["days_leave"] += 1
            if gp_row.get("is_pending"):
                gp_entry["days_pending"] += 1
            if gp_row.get("dsr_eligible"):
                gp_entry["days_dsr_eligible"] += 1
            if gp_row.get("dsr_entered"):
                gp_entry["days_dsr_entered"] += 1
            if gp_row.get("dsr_eligible") and not gp_row.get("dsr_entered"):
                gp_entry["days_dsr_pending"] += 1

            # Compact readable status token for matrix column
            if gp_row.get("is_pending"):
                tok = "Pending"
            elif gp_row.get("on_leave"):
                tok = "Leave"
            elif gp_row.get("meeting_training"):
                tok = "Mtg/Trg"
            elif gp_row.get("before_9"):
                tok = "On-Time" if not (gp_row.get("dsr_eligible") and not gp_row.get("dsr_entered")) else "On-Time (No DSR)"
            elif gp_row.get("after_9"):
                tok = "Late" if not (gp_row.get("dsr_eligible") and not gp_row.get("dsr_entered")) else "Late (No DSR)"
            else:
                tok = "Submitted"
            gp_entry["day_status_map"][col_lbl] = tok

    mandal_summaries: list[dict[str, Any]] = []
    for acc in mandal_acc.values():
        g_sum = max(1, acc["total_gps_sum"])
        ps_sum = acc["present_ps_sum"]
        mandal_summaries.append(
            {
                "mandal": acc["mandal"],
                "total_gps": acc["max_gps"],
                "days_tracked": acc["days_tracked"],
                "avg_attendance_pct": acc["submitted_sum"] / g_sum * 100.0,
                "avg_before_cutoff_pct": acc["before_sum"] / g_sum * 100.0,
                "avg_dsr_pct": (acc["dsr_entered_sum"] / ps_sum * 100.0) if ps_sum else 0.0,
                "total_pending_instances": acc["pending_sum"],
                "total_after_cutoff_instances": acc["after_sum"],
                "total_dsr_pending_instances": acc["dsr_pending_sum"],
            }
        )
    mandal_summaries.sort(key=lambda r: (r["avg_before_cutoff_pct"], r["mandal"].casefold()))
    for idx, row in enumerate(mandal_summaries, start=1):
        row["serial"] = idx

    gp_summaries: list[dict[str, Any]] = []
    for entry in gp_acc.values():
        dt_cnt = max(1, entry["days_tracked"])
        dsr_el = entry["days_dsr_eligible"]
        gp_summaries.append(
            {
                "lgd": entry["lgd"],
                "mandal": entry["mandal"],
                "gp": entry["gp"],
                "ps_name": entry["ps_name"],
                "mobile": entry["mobile"],
                "nature_of_posting": entry["nature_of_posting"],
                "designation": entry["designation"],
                "days_tracked": entry["days_tracked"],
                "days_submitted": entry["days_submitted"],
                "days_before_cutoff": entry["days_before_cutoff"],
                "days_after_cutoff": entry["days_after_cutoff"],
                "days_leave": entry["days_leave"],
                "days_pending": entry["days_pending"],
                "days_dsr_eligible": dsr_el,
                "days_dsr_entered": entry["days_dsr_entered"],
                "days_dsr_pending": entry["days_dsr_pending"],
                "attendance_pct": entry["days_submitted"] / dt_cnt * 100.0,
                "before_cutoff_pct": entry["days_before_cutoff"] / dt_cnt * 100.0,
                "dsr_pct": (entry["days_dsr_entered"] / dsr_el * 100.0) if dsr_el else 0.0,
                "day_statuses": [entry["day_status_map"].get(lbl, "-") for lbl in date_labels],
            }
        )
    gp_summaries.sort(key=lambda r: (r["mandal"].casefold(), r["gp"].casefold()))
    for idx, row in enumerate(gp_summaries, start=1):
        row["serial"] = idx

    defaulters = [
        dict(r)
        for r in gp_summaries
        if r["days_pending"] > 0 or r["days_after_cutoff"] > 0 or r["days_dsr_pending"] > 0
    ]
    defaulters.sort(
        key=lambda r: (
            -r["days_pending"],
            -r["days_after_cutoff"],
            -r["days_dsr_pending"],
            r["mandal"].casefold(),
            r["gp"].casefold(),
        )
    )
    for idx, row in enumerate(defaulters, start=1):
        row["serial"] = idx

    tot_gps_all_days = sum(d.total_gps for d in date_summaries) or 1
    tot_present_ps_all = sum(d.present_ps for d in date_summaries)
    overall_totals = {
        "total_gps": len(gp_summaries),
        "days_count": len(date_summaries),
        "avg_att_pct": sum(d.submitted for d in date_summaries) / tot_gps_all_days * 100.0,
        "avg_before_pct": sum(d.before_cutoff for d in date_summaries) / tot_gps_all_days * 100.0,
        "avg_dsr_pct": (sum(d.dsr_entered for d in date_summaries) / tot_present_ps_all * 100.0) if tot_present_ps_all else 0.0,
        "total_pending_instances": sum(d.pending for d in date_summaries),
        "total_after_instances": sum(d.after_cutoff for d in date_summaries),
        "total_dsr_pending_instances": sum(d.dsr_pending for d in date_summaries),
        "defaulter_gps_count": len(defaulters),
        "date_labels": date_labels,
    }

    return MultiDayReportData(
        district_name=district_name,
        mandal_filter=mandal_filter_canonical,
        start_date=date_summaries[0].report_date,
        end_date=date_summaries[-1].report_date,
        days_count=len(date_summaries),
        cutoff_time_str=first_rep.cutoff_time_str,
        cutoff_label=first_rep.cutoff_label,
        unique_gp_count=len(gp_summaries),
        date_summaries=date_summaries,
        mandal_summaries=mandal_summaries,
        gp_summaries=gp_summaries,
        defaulter_rows=defaulters,
        overall_totals=overall_totals,
    )


def generate_multiday_pdf(report: MultiDayReportData, output_path: str | Path) -> Path:
    """Compile a landscape Executive Multiple-Days PS Attendance & DSR PDF report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A4)
    margin = 10 * mm

    doc = SimpleDocTemplate(
        str(output),
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=11 * mm,
        bottomMargin=13 * mm,
        title=f"{report.district_name} Multiple Days DSR & Attendance Report",
        author=PLATFORM_NAME,
    )

    title_style = ParagraphStyle(
        "MDTitle", fontName="Helvetica-Bold", fontSize=14, leading=17,
        alignment=TA_CENTER, textColor=HexColor("#0C3829"),
    )
    sub_style = ParagraphStyle(
        "MDSub", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
        alignment=TA_CENTER, textColor=HexColor("#167451"),
    )
    sec_style = ParagraphStyle(
        "MDSec", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
        alignment=TA_LEFT, textColor=HexColor("#0C3829"), spaceBefore=6, spaceAfter=4,
    )
    cell_hdr = ParagraphStyle(
        "MDHdr", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
        alignment=TA_CENTER, textColor=colors.white,
    )
    cell_txt = ParagraphStyle(
        "MDTxt", fontName="Helvetica", fontSize=7.4, leading=9.4,
        alignment=TA_LEFT, textColor=HexColor("#111827"),
    )
    cell_num = ParagraphStyle(
        "MDNum", fontName="Helvetica", fontSize=7.4, leading=9.4,
        alignment=TA_CENTER, textColor=HexColor("#111827"),
    )
    cell_bold = ParagraphStyle(
        "MDBold", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
        alignment=TA_CENTER, textColor=HexColor("#0C3829"),
    )

    story: list[Any] = []
    scope_txt = f" ({report.mandal_filter} Mandal)" if report.mandal_filter else ""
    date_span = (
        f"{report.start_date:%d-%b-%Y}"
        if report.start_date == report.end_date
        else f"{report.start_date:%d-%b-%Y} to {report.end_date:%d-%b-%Y}"
    )

    story.append(Paragraph(
        f"{html.escape(report.district_name.upper())} DISTRICT{html.escape(scope_txt)} &middot; "
        f"MULTIPLE DAYS PS ATTENDANCE &amp; DSR CONSOLIDATED REPORT",
        title_style,
    ))
    story.append(Paragraph(
        f"Period: {html.escape(date_span)} ({report.days_count} Days) &bull; Cutoff Time: {html.escape(report.cutoff_label)} "
        f"&bull; Unique GPs: {report.unique_gp_count} &bull; Generated: {html.escape(report.generated_time_str)}",
        sub_style,
    ))
    story.append(Spacer(1, 5))

    # Overall KPI Summary Banner Table
    ot = report.overall_totals
    avail_w = page_w - (2 * margin)
    kpi_data = [[
        Paragraph(f"<b>Days Analyzed</b><br/>{ot['days_count']}", cell_bold),
        Paragraph(f"<b>Unique Gram Panchayats</b><br/>{ot['total_gps']}", cell_bold),
        Paragraph(f"<b>Avg Attendance %</b><br/>{ot['avg_att_pct']:.2f}%", cell_bold),
        Paragraph(f"<b>Avg Before {html.escape(report.cutoff_label)} %</b><br/>{ot['avg_before_pct']:.2f}%", cell_bold),
        Paragraph(f"<b>Avg DSR Entered %</b><br/>{ot['avg_dsr_pct']:.2f}%", cell_bold),
        Paragraph(f"<b>Att. Pending Instances</b><br/>{ot['total_pending_instances']}", cell_bold),
        Paragraph(f"<b>DSR Pending Instances</b><br/>{ot['total_dsr_pending_instances']}", cell_bold),
    ]]
    kpi_tbl = Table(kpi_data, colWidths=[avail_w / 7.0] * 7)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ECFDF5")),
        ("BOX", (0, 0), (-1, -1), 1.0, HexColor("#167451")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, HexColor("#A7F3D0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 6))

    # Section 1: Day-by-Day Attendance & DSR Trend
    story.append(Paragraph("1. Day-by-Day Attendance &amp; DSR Trend", sec_style))
    d_headers = [
        Paragraph("S.No", cell_hdr),
        Paragraph("Date", cell_hdr),
        Paragraph("Total GPs", cell_hdr),
        Paragraph("Submitted", cell_hdr),
        Paragraph("Att %", cell_hdr),
        Paragraph(f"Before {html.escape(report.cutoff_label)}", cell_hdr),
        Paragraph("Punctuality %", cell_hdr),
        Paragraph("After Cutoff", cell_hdr),
        Paragraph("Leave/Mtg", cell_hdr),
        Paragraph("Att Pending", cell_hdr),
        Paragraph("Present PS", cell_hdr),
        Paragraph("DSR Entered", cell_hdr),
        Paragraph("DSR %", cell_hdr),
        Paragraph("DSR Pending", cell_hdr),
    ]
    d_rows: list[list[Any]] = [d_headers]
    for ds in report.date_summaries:
        d_rows.append([
            Paragraph(str(ds.serial), cell_num),
            Paragraph(f"<b>{html.escape(ds.date_label)}</b>", cell_txt),
            Paragraph(str(ds.total_gps), cell_num),
            Paragraph(str(ds.submitted), cell_num),
            PercentBar(ds.attendance_pct, width=48, height=15),
            Paragraph(str(ds.before_cutoff), cell_num),
            PercentBar(ds.before_cutoff_pct, width=48, height=15),
            Paragraph(str(ds.after_cutoff), cell_num),
            Paragraph(str(ds.on_leave + ds.meeting_training), cell_num),
            Paragraph(f"<b>{ds.pending}</b>" if ds.pending else "0", cell_num),
            Paragraph(str(ds.present_ps), cell_num),
            Paragraph(str(ds.dsr_entered), cell_num),
            PercentBar(ds.dsr_pct, width=48, height=15),
            Paragraph(f"<b>{ds.dsr_pending}</b>" if ds.dsr_pending else "0", cell_num),
        ])

    d_widths = [
        avail_w * w for w in (
            0.04, 0.11, 0.06, 0.07, 0.095, 0.075, 0.095, 0.07, 0.065, 0.07, 0.065, 0.065, 0.095, 0.075
        )
    ]
    d_tbl = Table(d_rows, colWidths=d_widths, repeatRows=1)
    d_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0C3829")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(d_tbl)
    story.append(Spacer(1, 8))

    # Section 2: Mandal Consolidated Multi-Day Abstract
    story.append(Paragraph("2. Mandal-Wise Consolidated Multi-Day Abstract", sec_style))
    m_headers = [
        Paragraph("S.No", cell_hdr),
        Paragraph("Mandal Name", cell_hdr),
        Paragraph("GPs", cell_hdr),
        Paragraph("Days", cell_hdr),
        Paragraph("Avg Attendance %", cell_hdr),
        Paragraph(f"Avg Before {html.escape(report.cutoff_label)} %", cell_hdr),
        Paragraph("Avg DSR %", cell_hdr),
        Paragraph("Att. Pending (Total Days)", cell_hdr),
        Paragraph("After Cutoff (Total Days)", cell_hdr),
        Paragraph("DSR Pending (Total Days)", cell_hdr),
    ]
    m_rows: list[list[Any]] = [m_headers]
    for mr in report.mandal_summaries:
        m_rows.append([
            Paragraph(str(mr["serial"]), cell_num),
            Paragraph(f"<b>{html.escape(str(mr['mandal']))}</b>", cell_txt),
            Paragraph(str(mr["total_gps"]), cell_num),
            Paragraph(str(mr["days_tracked"]), cell_num),
            PercentBar(mr["avg_attendance_pct"], width=58, height=15),
            PercentBar(mr["avg_before_cutoff_pct"], width=58, height=15),
            PercentBar(mr["avg_dsr_pct"], width=58, height=15),
            Paragraph(str(mr["total_pending_instances"]), cell_num),
            Paragraph(str(mr["total_after_cutoff_instances"]), cell_num),
            Paragraph(str(mr["total_dsr_pending_instances"]), cell_num),
        ])

    m_widths = [
        avail_w * w for w in (0.045, 0.215, 0.055, 0.055, 0.125, 0.125, 0.125, 0.085, 0.085, 0.085)
    ]
    m_tbl = Table(m_rows, colWidths=m_widths, repeatRows=1)
    m_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0C3829")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(m_tbl)

    # Section 3: Habitual Defaulters & Pending / Late Exceptions Across Dates
    story.append(PageBreak())
    story.append(Paragraph(
        f"3. Recurring Exceptions &amp; Defaulter GPs Across {report.days_count} Day(s) ({len(report.defaulter_rows)} GPs)",
        sec_style,
    ))
    if not report.defaulter_rows:
        story.append(Paragraph("No recurring attendance pending, late, or DSR pending exceptions found across uploaded files.", cell_txt))
    else:
        def_headers = [
            Paragraph("S.No", cell_hdr),
            Paragraph("Mandal Name", cell_hdr),
            Paragraph("Panchayat Name", cell_hdr),
            Paragraph("PS Name", cell_hdr),
            Paragraph("Mobile", cell_hdr),
            Paragraph("Posting", cell_hdr),
            Paragraph("Days", cell_hdr),
            Paragraph("Att Pend Days", cell_hdr),
            Paragraph("Late Days", cell_hdr),
            Paragraph("DSR Pend Days", cell_hdr),
            Paragraph("Punctuality %", cell_hdr),
        ]
        def_rows: list[list[Any]] = [def_headers]
        for dr in report.defaulter_rows:
            def_rows.append([
                Paragraph(str(dr["serial"]), cell_num),
                Paragraph(html.escape(str(dr["mandal"])), cell_txt),
                Paragraph(html.escape(str(dr["gp"])), cell_txt),
                Paragraph(html.escape(str(dr["ps_name"] or "-")), cell_txt),
                Paragraph(html.escape(str(dr["mobile"] or "-")), cell_num),
                Paragraph(html.escape(str(dr["nature_of_posting"] or "-")), cell_num),
                Paragraph(str(dr["days_tracked"]), cell_num),
                Paragraph(f"<font color='#B91C1C'><b>{dr['days_pending']}</b></font>" if dr["days_pending"] else "0", cell_num),
                Paragraph(f"<font color='#D97706'><b>{dr['days_after_cutoff']}</b></font>" if dr["days_after_cutoff"] else "0", cell_num),
                Paragraph(f"<font color='#991B1B'><b>{dr['days_dsr_pending']}</b></font>" if dr["days_dsr_pending"] else "0", cell_num),
                PercentBar(dr["before_cutoff_pct"], width=52, height=14),
            ])
        def_widths = [
            avail_w * w for w in (0.04, 0.13, 0.15, 0.15, 0.095, 0.08, 0.05, 0.065, 0.065, 0.07, 0.105)
        ]
        def_tbl = Table(def_rows, colWidths=def_widths, repeatRows=1)
        def_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#991B1B")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#FEF2F2")]),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#FECACA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(def_tbl)

    def _draw_footer(canvas_obj, _doc) -> None:
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 7.5)
        canvas_obj.setFillColor(HexColor("#0C3829"))
        canvas_obj.drawString(margin, 6.5 * mm, f"{PLATFORM_NAME}  |  {TAGLINE}")
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(HexColor("#475569"))
        canvas_obj.drawRightString(page_w - margin, 6.5 * mm, f"Page {_doc.page}")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return output


def generate_multiday_excel(report: MultiDayReportData, output_path: str | Path) -> Path:
    """Compile a multi-sheet styled Excel (.xlsx) workbook for Multiple Days DSR."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    hdr_fill = PatternFill(start_color="0C3829", end_color="0C3829", fill_type="solid")
    hdr_font = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10, color="0F172A")
    alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin = Side(border_style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _write_sheet(ws: Any, headers: list[str], rows: list[list[Any]]) -> None:
        ws.views.sheetView[0].showGridLines = True
        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=col_idx, value=h)
            c.font = hdr_font
            c.fill = hdr_fill
            c.border = border
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 24
        for r_idx, r_vals in enumerate(rows, start=2):
            for c_idx, val in enumerate(r_vals, start=1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = body_font
                c.border = border
                if r_idx % 2 == 1:
                    c.fill = alt_fill
                c.alignment = Alignment(
                    horizontal="left" if isinstance(val, str) and not val.isdigit() else "center",
                    vertical="center",
                )
            ws.row_dimensions[r_idx].height = 19
        for col_idx, h in enumerate(headers, start=1):
            max_len = max([len(str(h))] + [len(str(r[col_idx - 1])) for r in rows if col_idx - 1 < len(r)])
            ws.column_dimensions[get_column_letter(col_idx)].width = min(36, max(12, max_len + 4))
        ws.freeze_panes = "A2"

    # Sheet 1: Date Trend
    ws_date = wb.active
    ws_date.title = "Date Trend"
    _write_sheet(
        ws_date,
        [
            "S.No", "Date", "Source File", "Total GPs", "Submitted", "Attendance %",
            f"Before {report.cutoff_label}", "Punctuality %", "After Cutoff",
            "On Leave", "Meeting/Training", "Att Pending", "Present PS",
            "DSR Entered", "DSR %", "DSR Pending",
        ],
        [
            [
                ds.serial, ds.date_label, ds.source_filename, ds.total_gps, ds.submitted,
                round(ds.attendance_pct, 2), ds.before_cutoff, round(ds.before_cutoff_pct, 2),
                ds.after_cutoff, ds.on_leave, ds.meeting_training, ds.pending,
                ds.present_ps, ds.dsr_entered, round(ds.dsr_pct, 2), ds.dsr_pending,
            ]
            for ds in report.date_summaries
        ],
    )

    # Sheet 2: Mandal Consolidated
    ws_mandal = wb.create_sheet("Mandal Consolidated")
    _write_sheet(
        ws_mandal,
        [
            "S.No", "Mandal Name", "Total GPs", "Days Analyzed", "Avg Attendance %",
            f"Avg Before {report.cutoff_label} %", "Avg DSR %",
            "Att Pending Instances", "After Cutoff Instances", "DSR Pending Instances",
        ],
        [
            [
                mr["serial"], mr["mandal"], mr["total_gps"], mr["days_tracked"],
                round(mr["avg_attendance_pct"], 2), round(mr["avg_before_cutoff_pct"], 2),
                round(mr["avg_dsr_pct"], 2), mr["total_pending_instances"],
                mr["total_after_cutoff_instances"], mr["total_dsr_pending_instances"],
            ]
            for mr in report.mandal_summaries
        ],
    )

    # Sheet 3: Habitual Defaulters
    ws_def = wb.create_sheet("Habitual Defaulters")
    _write_sheet(
        ws_def,
        [
            "S.No", "LGD Code", "Mandal Name", "Panchayat Name", "PS Name", "Mobile",
            "Posting Nature", "Days Analyzed", "Att Pending Days", "Late Days",
            "DSR Pending Days", "Attendance %", "Punctuality %",
        ],
        [
            [
                dr["serial"], dr["lgd"], dr["mandal"], dr["gp"], dr["ps_name"],
                dr["mobile"], dr["nature_of_posting"], dr["days_tracked"],
                dr["days_pending"], dr["days_after_cutoff"], dr["days_dsr_pending"],
                round(dr["attendance_pct"], 2), round(dr["before_cutoff_pct"], 2),
            ]
            for dr in report.defaulter_rows
        ],
    )

    # Sheet 4: GP Day-by-Day Matrix
    ws_gp = wb.create_sheet("GP Day Matrix")
    date_labels = report.overall_totals.get("date_labels", [])
    _write_sheet(
        ws_gp,
        [
            "S.No", "LGD Code", "Mandal Name", "Panchayat Name", "PS Name", "Mobile",
            "Days", "On-Time", "Late", "Pending", "DSR Entered", "DSR Pending", *date_labels,
        ],
        [
            [
                gr["serial"], gr["lgd"], gr["mandal"], gr["gp"], gr["ps_name"], gr["mobile"],
                gr["days_tracked"], gr["days_before_cutoff"], gr["days_after_cutoff"],
                gr["days_pending"], gr["days_dsr_entered"], gr["days_dsr_pending"],
                *gr["day_statuses"],
            ]
            for gr in report.gp_summaries
        ],
    )

    apply_openpyxl_branding(wb)
    wb.save(output)
    return output

"""Domain models, designation rules, week parsing, and target calculations for GM-R 39.1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

SUPPORTED_DESIGNATIONS: tuple[str, ...] = (
    "MPO",
    "MPDO",
    "DLPO",
    "DPO",
    "CEO",
    "Deputy CEO",
)

# Canonical designation rules from inspection specification:
# - Grouping column: Mandal for MPO & MPDO, Division for DLPO, District for DPO/CEO/Deputy CEO
# - Targets: MPO Weekly 4 (and MPDO Weekly 4), DLPO Monthly 10, DPO Monthly 5 (CEO/Deputy CEO Monthly 5)
DESIGNATION_SPECS: dict[str, dict[str, Any]] = {
    "MPO": {
        "designation": "MPO",
        "full_title": "Mandal Panchayat Officer (MPO)",
        "group_level": "mandal",
        "group_label": "Mandal",
        "period_type": "weekly",
        "target_per_period": 4,
    },
    "MPDO": {
        "designation": "MPDO",
        "full_title": "Mandal Parishad Development Officer (MPDO)",
        "group_level": "mandal",
        "group_label": "Mandal",
        "period_type": "weekly",
        "target_per_period": 4,
    },
    "DLPO": {
        "designation": "DLPO",
        "full_title": "Divisional Panchayat Officer (DLPO)",
        "group_level": "division",
        "group_label": "Division",
        "period_type": "monthly",
        "target_per_period": 10,
    },
    "DPO": {
        "designation": "DPO",
        "full_title": "District Panchayat Officer (DPO)",
        "group_level": "district",
        "group_label": "District",
        "period_type": "monthly",
        "target_per_period": 5,
    },
    "CEO": {
        "designation": "CEO",
        "full_title": "Chief Executive Officer (CEO)",
        "group_level": "district",
        "group_label": "District",
        "period_type": "monthly",
        "target_per_period": 5,
    },
    "Deputy CEO": {
        "designation": "Deputy CEO",
        "full_title": "Deputy Chief Executive Officer (Deputy CEO)",
        "group_level": "district",
        "group_label": "District",
        "period_type": "monthly",
        "target_per_period": 5,
    },
}

_DESIGNATION_ALIASES: dict[str, str] = {
    "mpo": "MPO",
    "mandalpanchayatofficer": "MPO",
    "eoprrd": "MPO",
    "mpdo": "MPDO",
    "dlpo": "DLPO",
    "divisionalpanchayatofficer": "DLPO",
    "dpo": "DPO",
    "districtpanchayatofficer": "DPO",
    "ceo": "CEO",
    "deputyceo": "Deputy CEO",
    "dyceo": "Deputy CEO",
    "deputyceozp": "Deputy CEO",
}

_DATE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\b(\d{2}-\d{2}-\d{4})\b", ("%d-%m-%Y",)),
    (r"\b(\d{2}/\d{2}/\d{4})\b", ("%d/%m/%Y",)),
    (r"\b(\d{2}-[A-Za-z]{3}-\d{4})\b", ("%d-%b-%Y",)),
    (r"\b(\d{4}-\d{2}-\d{2})\b", ("%Y-%m-%d",)),
)


def normalize_designation(value: str | None) -> str:
    """Resolve user or portal designation string into canonical designation key."""
    raw = str(value or "").strip()
    if not raw:
        return "MPO"
    for canon in SUPPORTED_DESIGNATIONS:
        if raw.casefold() == canon.casefold():
            return canon
    compact = re.sub(r"[^a-z0-9]", "", raw.lower())
    if compact in _DESIGNATION_ALIASES:
        return _DESIGNATION_ALIASES[compact]
    # Substring fallback matching longer keys first so Deputy CEO precedes CEO
    for canon in sorted(SUPPORTED_DESIGNATIONS, key=len, reverse=True):
        if canon.lower() in raw.lower():
            return canon
    raise ValueError(
        f"Unsupported Officer Designation '{raw}'. Supported options: {', '.join(SUPPORTED_DESIGNATIONS)}."
    )


def get_designation_spec(designation: str | None) -> dict[str, Any]:
    """Return grouping and target metadata for the requested designation."""
    canon = normalize_designation(designation)
    return dict(DESIGNATION_SPECS[canon])


def extract_week_dates(week_label: str) -> tuple[date | None, date | None]:
    """Extract (start_date, end_date) from Monday-Saturday portal week labels."""
    text = str(week_label or "").strip()
    if not text:
        return None, None
    found: list[tuple[int, date]] = []
    for regex, fmts in _DATE_PATTERNS:
        for match in re.finditer(regex, text):
            token = match.group(1)
            for fmt in fmts:
                try:
                    found.append((match.start(), datetime.strptime(token, fmt).date()))
                    break
                except ValueError:
                    continue
    found.sort(key=lambda item: item[0])
    dates = [d for _, d in found]
    if not dates:
        return None, None
    if len(dates) == 1:
        return dates[0], dates[0]
    return dates[0], dates[-1]


def get_week_monday_date(week_label: str) -> date | None:
    """Return the Monday start date of a week string using strict Monday-to-Sunday rules."""
    start_dt, end_dt = extract_week_dates(week_label)
    dt = start_dt or end_dt
    if not dt:
        return None
    return dt - timedelta(days=dt.weekday())


def assign_week_to_month(week_label: str) -> tuple[int, int] | None:
    """Assign a week strictly to the calendar (year, month) in which its Monday falls.

    Example: '2026-08-31 to 2026-09-05' has Monday 2026-08-31 -> (2026, 8) (August 2026).
    Never splits across two months or uses majority-of-days / midpoint.
    """
    mon = get_week_monday_date(week_label)
    if not mon:
        return None
    return (mon.year, mon.month)


def get_calendar_month_mondays(year: int, month: int) -> list[tuple[date, date]]:
    """Return all (Monday, Sunday) weeks for a calendar month starting at its first Monday."""
    first_day = date(int(year), int(month), 1)
    days_to_first_mon = (0 - first_day.weekday()) % 7
    cur_mon = first_day + timedelta(days=days_to_first_mon)
    weeks: list[tuple[date, date]] = []
    while cur_mon.month == int(month) and cur_mon.year == int(year):
        weeks.append((cur_mon, cur_mon + timedelta(days=6)))
        cur_mon += timedelta(days=7)
    return weeks


def parse_month_key(val: str | None) -> tuple[int, int] | None:
    """Parse 'YYYY-MM' or 'Aug 2026' or 'August 2026' into (year, month)."""
    clean = str(val or "").strip()
    if not clean:
        return None
    m_ym = re.match(r"^(\d{4})[-/](\d{1,2})$", clean)
    if m_ym:
        y, mo = int(m_ym.group(1)), int(m_ym.group(2))
        if 1 <= mo <= 12:
            return (y, mo)
    for fmt in ("%b %Y", "%B %Y", "%b-%Y", "%B-%Y", "%m-%Y", "%m/%Y"):
        try:
            dt = datetime.strptime(clean, fmt).date()
            return (dt.year, dt.month)
        except ValueError:
            continue
    return assign_week_to_month(clean)


def format_month_key_label(ym: tuple[int, int]) -> str:
    return date(ym[0], ym[1], 1).strftime("%b %Y")


def count_distinct_week_months(week_labels: list[str] | tuple[str, ...]) -> int:
    """Count distinct calendar months using strictly each week's Monday start date (minimum 1)."""
    if not week_labels:
        return 1
    months: set[tuple[int, int]] = set()
    for lbl in week_labels:
        ym = assign_week_to_month(lbl)
        if ym is not None:
            months.add(ym)
    if months:
        return max(1, len(months))
    return max(1, (len(week_labels) + 3) // 4)


def format_month_range_from_weeks(from_week: str, to_week: str = "") -> str:
    """Derive 'From Month to To Month' (e.g. 'Apr 2026 to Nov 2026') using Monday-start month allocation."""
    ym_from = assign_week_to_month(from_week)
    ym_to = assign_week_to_month(to_week or from_week) or ym_from
    if not ym_from:
        return ""
    from_m = format_month_key_label(ym_from)
    to_m = format_month_key_label(ym_to or ym_from)
    if from_m == to_m:
        return from_m
    return f"{from_m} to {to_m}"


def compute_designation_target(
    designation: str | None,
    week_labels: list[str] | tuple[str, ...] | None = None,
    week_count: int | None = None,
    target_override: int | None = None,
) -> tuple[int, str]:
    """Compute per-unit target and human-readable formula description."""
    spec = get_designation_spec(designation)
    n_weeks = max(1, int(week_count if week_count is not None else (len(week_labels) if week_labels else 1)))
    if target_override is not None and int(target_override) > 0:
        val = int(target_override)
        return val, f"{spec['designation']}s Inspection Target: Custom {val}"

    per_period = int(spec["target_per_period"])
    if spec["period_type"] == "weekly":
        target = per_period * n_weeks
        return target, f"{spec['designation']}s Inspection Target: Weekly {per_period} x {n_weeks} Week(s) = {target}"

    n_months = count_distinct_week_months(list(week_labels or [])) if week_labels else max(1, (n_weeks + 3) // 4)
    target = per_period * n_months
    return target, f"{spec['designation']}s Inspection Target: Monthly {per_period} x {n_months} Month(s) = {target}"


@dataclass
class InspectionRecord:
    """Single normalized GM-R 39.1 inspection row after Final Submit Status parsing."""

    week_label: str
    designation: str
    district_name: str
    division_name: str
    mandal_name: str
    gp_name: str
    officer_name: str
    inspection_date: str
    final_submit_status: str
    unit_name: str
    mandal_lgd_code: str = ""
    panchayat_id: str = ""
    attendance_datetime: str = ""
    inspection_from_date: str = ""
    inspection_to_date: str = ""
    checklist_entered: str = ""


@dataclass
class InspectionAbstractRow:
    """Aggregated abstract row matching: Sl No, Mandal/Division/District, Target, Completed, Balance, % Completed."""

    serial: int
    unit_name: str
    target: int
    completed: int
    balance: int
    pct_completed: float


@dataclass
class MonthInspectionSection:
    """Single calendar month abstract calculated using strict Monday-start week allocation rules."""

    year: int
    month: int
    month_key: str
    month_label: str
    weeks_included: list[str]
    week_count: int
    target_per_unit: int
    target_rule_desc: str
    abstract_rows: list[InspectionAbstractRow] = field(default_factory=list)
    total_target: int = 0
    total_completed: int = 0
    total_balance: int = 0
    total_pct_completed: float = 0.0
    raw_row_count: int = 0
    submitted_row_count: int = 0
    excluded_non_submitted_count: int = 0


@dataclass
class InspectionReport:
    """Complete consolidated GM-R 39.1 Inspection report for a designation and week range."""

    designation: str
    designation_title: str
    group_level: str
    group_label: str
    district_name: str
    from_week: str
    to_week: str
    weeks_selected: list[str]
    target_per_unit: int
    target_rule_desc: str
    generated_at: datetime
    abstract_rows: list[InspectionAbstractRow] = field(default_factory=list)
    total_target: int = 0
    total_completed: int = 0
    total_balance: int = 0
    total_pct_completed: float = 0.0
    submitted_records: list[InspectionRecord] = field(default_factory=list)
    raw_row_count: int = 0
    submitted_row_count: int = 0
    excluded_non_submitted_count: int = 0
    week_download_logs: list[dict[str, Any]] = field(default_factory=list)
    monthly_sections: list[MonthInspectionSection] = field(default_factory=list)

    @property
    def generated_time_str(self) -> str:
        return self.generated_at.strftime("%d-%b-%Y %I:%M %p")

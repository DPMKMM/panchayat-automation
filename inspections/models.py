"""Domain models, designation rules, week parsing, and target calculations for GM-R 39.1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
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


def count_distinct_week_months(week_labels: list[str] | tuple[str, ...]) -> int:
    """Count distinct calendar months represented by the selected week labels (minimum 1)."""
    if not week_labels:
        return 1
    months: set[tuple[int, int]] = set()
    for lbl in week_labels:
        start_dt, end_dt = extract_week_dates(lbl)
        if start_dt and end_dt:
            mid_dt = start_dt + (end_dt - start_dt) // 2
            months.add((mid_dt.year, mid_dt.month))
        elif start_dt:
            months.add((start_dt.year, start_dt.month))
    if months:
        return max(1, len(months))
    return max(1, (len(week_labels) + 3) // 4)


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
        return val, f"Custom Target: {val}"

    per_period = int(spec["target_per_period"])
    if spec["period_type"] == "weekly":
        target = per_period * n_weeks
        return target, f"{spec['designation']}: Weekly {per_period} x {n_weeks} Week(s) = {target}"

    n_months = count_distinct_week_months(list(week_labels or [])) if week_labels else max(1, (n_weeks + 3) // 4)
    target = per_period * n_months
    return target, f"{spec['designation']}: Monthly {per_period} x {n_months} Month(s) = {target}"


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

    @property
    def generated_time_str(self) -> str:
        return self.generated_at.strftime("%d-%b-%Y %I:%M %p")

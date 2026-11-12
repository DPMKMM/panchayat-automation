"""Holiday identification and working days calculation rules for Automated Multiple Days DSR.

Calculation Rules:
1. Sundays: Automatically excluded across the entire selected date range.
2. Second Saturdays: Automatically excluded across every month in the date range
   (strictly identified as any Saturday falling on day 8 through 14 of the calendar month).
3. Public Holidays: Manually selected public holidays are excluded from downloading.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from Auto_Multi_DSR.models import DateAnalysis


def parse_date_input(val: str | date) -> date:
    """Parse various string representations into a Python date object."""
    if isinstance(val, date):
        return val
    clean = str(val or "").strip()
    if not clean:
        raise ValueError("Empty date value provided.")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d-%B-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: '{val}'. Expected YYYY-MM-DD or DD-MM-YYYY.")


def format_portal_date(d: date) -> str:
    """Format date to DD-MMM-YYYY (e.g. 02-Nov-2026) required by e-Panchayat portal."""
    return d.strftime("%d-%b-%Y")


def format_display_date(d: date) -> str:
    """Format date to DD-MM-YYYY (e.g. 02-11-2026) for standard dashboard displays."""
    return d.strftime("%d-%m-%Y")


def is_sunday(d: date) -> bool:
    """Check if date is a Sunday (weekday() == 6 in Python date)."""
    return d.weekday() == 6


def is_second_saturday(d: date) -> bool:
    """Check if date is the Second Saturday of its month.

    In any month:
    - Days 1 to 7 contain the 1st Saturday.
    - Days 8 to 14 contain the 2nd Saturday.
    """
    return d.weekday() == 5 and (8 <= d.day <= 14)


def analyze_working_days(
    start_date_raw: str | date,
    end_date_raw: str | date,
    public_holidays_raw: Iterable[str | date] | None = None,
) -> DateAnalysis:
    """Analyze date range and compute working days, automatically excluding Sundays,

    Second Saturdays, and any user-specified public holidays.
    """
    d_start = parse_date_input(start_date_raw)
    d_end = parse_date_input(end_date_raw)

    if d_start > d_end:
        d_start, d_end = d_end, d_start

    pub_holidays_set: set[date] = set()
    if public_holidays_raw:
        for ph in public_holidays_raw:
            try:
                pub_holidays_set.add(parse_date_input(ph))
            except Exception:
                continue

    total_calendar_days = (d_end - d_start).days + 1
    working_days: list[str] = []
    working_day_items: list[dict[str, str]] = []
    excluded_sundays: list[str] = []
    excluded_second_saturdays: list[str] = []
    excluded_public_holidays: list[str] = []
    holiday_map: dict[str, str] = {}

    curr = d_start
    while curr <= d_end:
        iso_str = curr.strftime("%Y-%m-%d")
        disp_str = format_display_date(curr)
        portal_str = format_portal_date(curr)
        day_name = curr.strftime("%A")

        if is_sunday(curr):
            excluded_sundays.append(iso_str)
            holiday_map[iso_str] = f"Sunday ({disp_str})"
        elif is_second_saturday(curr):
            excluded_second_saturdays.append(iso_str)
            holiday_map[iso_str] = f"Second Saturday ({disp_str})"
        elif curr in pub_holidays_set:
            excluded_public_holidays.append(iso_str)
            holiday_map[iso_str] = f"Public Holiday ({disp_str})"
        else:
            working_days.append(iso_str)
            working_day_items.append({
                "iso": iso_str,
                "display": disp_str,
                "portal": portal_str,
                "day_name": day_name,
            })
        curr += timedelta(days=1)

    return DateAnalysis(
        start_date=d_start.strftime("%Y-%m-%d"),
        end_date=d_end.strftime("%Y-%m-%d"),
        total_calendar_days=total_calendar_days,
        working_days=working_days,
        working_day_items=working_day_items,
        excluded_sundays=excluded_sundays,
        excluded_second_saturdays=excluded_second_saturdays,
        excluded_public_holidays=excluded_public_holidays,
        holiday_map=holiday_map,
    )

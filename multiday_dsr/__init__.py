"""Dedicated Multiple Days DSR & Attendance Analytics Module (Manual Reports)."""

from multiday_dsr.processor import MultiDayDsrResult, classify_time_style, highlight_percentage, process_dsr

__all__ = ["MultiDayDsrResult", "classify_time_style", "highlight_percentage", "process_dsr"]

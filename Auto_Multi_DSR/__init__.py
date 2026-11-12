"""Automated Multiple Days DSR & PS Attendance Reports Module.

Independently developed in Auto_Multi_DSR to automatically iterate user-selected
date ranges, exclude Sundays, Second Saturdays, and public holidays, download daily
GM-R 1.2.7 Raw Data from the Telangana e-Panchayat portal, consolidate date-wise,
and compile multi-level abstract PDFs and multi-sheet Excel workbooks.
"""

from Auto_Multi_DSR.holidays import analyze_working_days, is_second_saturday, is_sunday
from Auto_Multi_DSR.models import DateAnalysis, DownloadDayStatus, AutoMultiDsrJobRecord

__all__ = [
    "analyze_working_days",
    "is_sunday",
    "is_second_saturday",
    "DateAnalysis",
    "DownloadDayStatus",
    "AutoMultiDsrJobRecord",
]

"""Data structures and representations for Automated Multiple Days DSR reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class DateAnalysis:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    total_calendar_days: int
    working_days: list[str]  # List of YYYY-MM-DD strings
    working_day_items: list[dict[str, str]] = field(default_factory=list)
    excluded_sundays: list[str] = field(default_factory=list)
    excluded_second_saturdays: list[str] = field(default_factory=list)
    excluded_public_holidays: list[str] = field(default_factory=list)
    holiday_map: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_calendar_days": self.total_calendar_days,
            "working_days_count": len(self.working_days),
            "working_days": list(self.working_days),
            "working_day_items": list(self.working_day_items),
            "excluded_sundays_count": len(self.excluded_sundays),
            "excluded_sundays": list(self.excluded_sundays),
            "excluded_second_saturdays_count": len(self.excluded_second_saturdays),
            "excluded_second_saturdays": list(self.excluded_second_saturdays),
            "excluded_public_holidays_count": len(self.excluded_public_holidays),
            "excluded_public_holidays": list(self.excluded_public_holidays),
            "total_excluded_holidays": (
                len(self.excluded_sundays)
                + len(self.excluded_second_saturdays)
                + len(self.excluded_public_holidays)
            ),
            "holiday_map": dict(self.holiday_map),
        }


@dataclass
class DownloadDayStatus:
    date_str: str          # YYYY-MM-DD
    display_date: str      # DD-MM-YYYY
    portal_date: str       # DD-MMM-YYYY
    status: str = "pending"  # pending | downloading | success | failed | retrying
    attempts: int = 0
    filename: str = ""
    file_size: int = 0
    error: str = ""
    raw_bytes: bytes = b""

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "date": self.date_str,
            "display_date": self.display_date,
            "portal_date": self.portal_date,
            "status": self.status,
            "attempts": self.attempts,
            "filename": self.filename,
            "file_size": self.file_size,
            "error": self.error,
        }


@dataclass
class AutoMultiDsrJobRecord:
    job_id: str
    session_id: str
    district_name: str
    user_id: str
    start_date: str
    end_date: str
    date_analysis: DateAnalysis
    status: str = "queued"  # queued | running | completed | failed
    current_date: str = ""
    progress_pct: int = 0
    download_logs: list[dict[str, Any]] = field(default_factory=list)
    successful_dates: list[str] = field(default_factory=list)
    failed_dates: list[str] = field(default_factory=list)
    report_data: dict[str, Any] | None = None
    pdf_filenames: dict[str, str] = field(default_factory=dict)
    pdf_paths: dict[str, str] = field(default_factory=dict)
    excel_filename: str = ""
    excel_path: str = ""
    result: Any = field(default=None, repr=False)
    error: str | None = None
    started_at: float = 0.0
    completed_at: float | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "district_name": self.district_name,
            "user_id": self.user_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status,
            "current_date": self.current_date,
            "progress_pct": self.progress_pct,
            "total_working_days": len(self.date_analysis.working_days),
            "completed_count": len(self.successful_dates),
            "failed_count": len(self.failed_dates),
            "successful_dates": list(self.successful_dates),
            "failed_dates": list(self.failed_dates),
            "download_logs": list(self.download_logs),
            "date_analysis": self.date_analysis.to_dict(),
            "report_data": self.report_data,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "download_urls": {
                "pdf": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-pdf?level=all",
                "pdf_district": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-pdf?level=district",
                "pdf_mandal": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-pdf?level=mandal",
                "pdf_gp": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-pdf?level=gp",
                "pdf_time_matrix": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-pdf?level=time_matrix",
                "excel": f"/api/auto-multi-dsr/jobs/{self.job_id}/download-excel",
            } if self.status == "completed" else {},
        }

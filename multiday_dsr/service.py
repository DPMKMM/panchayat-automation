"""Session/job store and orchestration for the Multi-Days DSR Manual Reports module."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from core.config import get_reports_dir
from multiday_dsr.processor import MultiDayDsrResult, classify_time_style, highlight_percentage, process_dsr
from multiday_dsr.reports import (
    generate_multiday_dsr_excel,
    generate_multiday_dsr_pdf,
)

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _df_to_records(df: pd.DataFrame, include_time_styles: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fixed_non_time = {
        "S.No",
        "Mandal Name",
        "Panchayat Name",
        "Present",
        "On Leave",
        "Not Marked Attendance",
        "Training / Meeting",
        "No. of Days Before 9 AM",
    }
    for _, r in df.iterrows():
        item: dict[str, Any] = {}
        t_styles: dict[str, dict[str, str]] = {}
        for col in df.columns:
            v = r[col]
            if pd.isna(v):
                item[col] = ""
            elif hasattr(v, "item"):
                item[col] = v.item()
            else:
                item[col] = v
            if include_time_styles and col not in fixed_non_time:
                t_styles[col] = classify_time_style(item[col])
        item["_before9_style"] = highlight_percentage(item.get("Before 9 AM %"))
        if include_time_styles:
            item["_time_styles"] = t_styles
        rows.append(item)
    return rows


def analyze_uploaded_files(
    files_payload: list[tuple[str, bytes]],
    owner_user_id: str = "",
    include_time_matrix: bool = True,
) -> dict[str, Any]:
    """Run process_dsr on uploaded files, persist PDF & Excel deliverables, and return JSON payload."""
    result: MultiDayDsrResult = process_dsr(files_payload)
    job_id = uuid4().hex

    reports_dir = get_reports_dir()
    safe_dist = re.sub(r"[^A-Za-z0-9_-]", "_", result.dist_name or "District").strip("_") or "District"
    ts_download = result.generated_at.strftime("%d-%m-%Y %I:%M %p")
    ts_disk = result.generated_at.strftime("%d-%m-%Y_%I-%M_%p")

    pdf_filenames = {
        "all": f"{safe_dist}_MultiDays_DSR_Full_Report_{ts_download}.pdf",
        "district": f"{safe_dist}_MultiDays_DSR_District_Level_{ts_download}.pdf",
        "mandal": f"{safe_dist}_MultiDays_DSR_Mandal_Level_{ts_download}.pdf",
        "gp": f"{safe_dist}_MultiDays_DSR_GP_Summary_{ts_download}.pdf",
        "time_matrix": f"{safe_dist}_MultiDays_DSR_Exact_Time_{ts_download}.pdf",
    }
    excel_filename = f"{safe_dist}_MultiDays_DSR_Report_{ts_download}.xlsx"

    pdf_paths = {
        lvl: reports_dir / f"{job_id[:10]}_{safe_dist}_MultiDays_DSR_{lvl}_{ts_disk}.pdf"
        for lvl in pdf_filenames
    }
    excel_path = reports_dir / f"{job_id[:10]}_{safe_dist}_MultiDays_DSR_{ts_disk}.xlsx"

    # Build Full Combined PDF and Excel eagerly; individual level PDFs build eagerly or on-demand
    generate_multiday_dsr_pdf(result, pdf_paths["all"], include_time_matrix=include_time_matrix, level="all")
    generate_multiday_dsr_excel(result, excel_path, include_time_matrix=include_time_matrix)

    dist_rows = _df_to_records(result.district)
    mandal_rows = _df_to_records(result.mandal)
    gp_rows = _df_to_records(result.gp_summary)
    tm_rows = _df_to_records(result.time_matrix, include_time_styles=True) if include_time_matrix else []

    tot_reported = int(result.district["Total Reported"].sum()) if not result.district.empty else 0
    tot_before9 = int(result.district["Before 9 AM"].sum()) if not result.district.empty else 0
    overall_before9_pct = round((tot_before9 / tot_reported) * 100, 2) if tot_reported > 0 else 0.0

    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "owner_user_id": owner_user_id,
            "result": result,
            "include_time_matrix": include_time_matrix,
            "pdf_paths": {k: str(v) for k, v in pdf_paths.items()},
            "pdf_filenames": pdf_filenames,
            "excel_path": str(excel_path),
            "excel_filename": excel_filename,
        }

    return {
        "success": True,
        "job_id": job_id,
        "include_time_matrix": include_time_matrix,
        "summary": {
            "dist_name": result.dist_name,
            "mandal_name": result.mandal_name,
            "mandal_count": result.mandal_count,
            "total_gps": result.total_gps,
            "total_reporting_days": result.total_reporting_days,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "raw_row_count": len(result.master_data),
            "overall_before9_pct": overall_before9_pct,
            "generated_on": ts_download,
        },
        "district_columns": list(result.district.columns),
        "mandal_columns": list(result.mandal.columns),
        "gp_columns": list(result.gp_summary.columns),
        "time_matrix_columns": list(result.time_matrix.columns) if include_time_matrix else [],
        "district_rows": dist_rows,
        "mandal_rows": mandal_rows,
        "gp_rows": gp_rows,
        "time_matrix_rows": tm_rows,
        "download_filenames": {
            "pdf": pdf_filenames["all"],
            "pdf_district": pdf_filenames["district"],
            "pdf_mandal": pdf_filenames["mandal"],
            "pdf_gp": pdf_filenames["gp"],
            "pdf_time_matrix": pdf_filenames["time_matrix"],
            "excel": excel_filename,
        },
        "download_urls": {
            "pdf": f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level=all",
            "pdf_district": f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level=district",
            "pdf_mandal": f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level=mandal",
            "pdf_gp": f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level=gp",
            "pdf_time_matrix": f"/api/multiday-dsr/jobs/{job_id}/download-pdf?level=time_matrix",
            "excel": f"/api/multiday-dsr/jobs/{job_id}/download-excel",
        },
    }


def get_job_entry(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _JOBS.get(job_id)


def get_job_artifact(job_id: str, kind: str, level: str = "all") -> tuple[str, bytes, str]:
    entry = get_job_entry(job_id)
    if not entry:
        raise FileNotFoundError("Multi-Days DSR job not found or expired. Please re-upload files.")

    if kind == "pdf":
        lvl = (level or "all").strip().lower()
        if lvl in ("exact_time", "time"):
            lvl = "time_matrix"
        if lvl not in entry["pdf_paths"]:
            lvl = "all"
        p = Path(entry["pdf_paths"][lvl])
        if not p.exists():
            generate_multiday_dsr_pdf(
                entry["result"],
                p,
                include_time_matrix=bool(entry.get("include_time_matrix", True)),
                level=lvl,
            )
        return entry["pdf_filenames"][lvl], p.read_bytes(), "application/pdf"

    if kind == "excel":
        p = Path(entry["excel_path"])
        if not p.exists():
            raise FileNotFoundError("Generated Multi-Days DSR Excel file is no longer available.")
        return (
            entry["excel_filename"],
            p.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    raise ValueError(f"Unsupported artifact kind: {kind}")

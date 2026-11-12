"""Session/job store and orchestration for the Multi-Days DSR Manual Reports module."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from core.config import get_reports_dir
from multiday_dsr.processor import MultiDayDsrResult, highlight_percentage, process_dsr
from multiday_dsr.reports import (
    generate_multiday_dsr_csv,
    generate_multiday_dsr_excel,
    generate_multiday_dsr_pdf,
)

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        item: dict[str, Any] = {}
        for col in df.columns:
            v = r[col]
            if pd.isna(v):
                item[col] = ""
            elif hasattr(v, "item"):
                item[col] = v.item()
            else:
                item[col] = v
        item["_before9_style"] = highlight_percentage(item.get("Before 9 AM %"))
        rows.append(item)
    return rows


def analyze_uploaded_files(
    files_payload: list[tuple[str, bytes]],
    owner_user_id: str = "",
) -> dict[str, Any]:
    """Run process_dsr on uploaded files, persist PDF/Excel/CSVs, and return JSON payload."""
    result: MultiDayDsrResult = process_dsr(files_payload)
    job_id = uuid4().hex

    reports_dir = get_reports_dir()
    safe_dist = re.sub(r"[^A-Za-z0-9_-]", "_", result.dist_name or "District").strip("_") or "District"
    ts_download = result.generated_at.strftime("%d-%m-%Y %I:%M %p")
    ts_disk = result.generated_at.strftime("%d-%m-%Y_%I-%M_%p")

    pdf_filename = f"{safe_dist}_MultiDays_DSR_Report_{ts_download}.pdf"
    excel_filename = f"{safe_dist}_MultiDays_DSR_Report_{ts_download}.xlsx"
    csv_district_name = f"{safe_dist}_MultiDays_DSR_District_{ts_download}.csv"
    csv_mandal_name = f"{safe_dist}_MultiDays_DSR_Mandal_{ts_download}.csv"
    csv_gp_name = f"{safe_dist}_MultiDays_DSR_GP_Summary_{ts_download}.csv"

    pdf_path = reports_dir / f"{job_id[:10]}_{safe_dist}_MultiDays_DSR_{ts_disk}.pdf"
    excel_path = reports_dir / f"{job_id[:10]}_{safe_dist}_MultiDays_DSR_{ts_disk}.xlsx"

    generate_multiday_dsr_pdf(result, pdf_path)
    generate_multiday_dsr_excel(result, excel_path)

    dist_rows = _df_to_records(result.district)
    mandal_rows = _df_to_records(result.mandal)
    gp_rows = _df_to_records(result.gp_summary)

    tot_reported = int(result.district["Total Reported"].sum()) if not result.district.empty else 0
    tot_before9 = int(result.district["Before 9 AM"].sum()) if not result.district.empty else 0
    overall_before9_pct = round((tot_before9 / tot_reported) * 100, 2) if tot_reported > 0 else 0.0

    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "owner_user_id": owner_user_id,
            "result": result,
            "pdf_path": str(pdf_path),
            "pdf_filename": pdf_filename,
            "excel_path": str(excel_path),
            "excel_filename": excel_filename,
            "csv_bytes": {
                "district": (csv_district_name, generate_multiday_dsr_csv(result, "district")),
                "mandal": (csv_mandal_name, generate_multiday_dsr_csv(result, "mandal")),
                "gp": (csv_gp_name, generate_multiday_dsr_csv(result, "gp")),
            },
        }

    return {
        "success": True,
        "job_id": job_id,
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
        "district_rows": dist_rows,
        "mandal_rows": mandal_rows,
        "gp_rows": gp_rows,
        "download_filenames": {
            "pdf": pdf_filename,
            "excel": excel_filename,
            "csv_district": csv_district_name,
            "csv_mandal": csv_mandal_name,
            "csv_gp": csv_gp_name,
        },
        "download_urls": {
            "pdf": f"/api/multiday-dsr/jobs/{job_id}/download-pdf",
            "excel": f"/api/multiday-dsr/jobs/{job_id}/download-excel",
            "csv_district": f"/api/multiday-dsr/jobs/{job_id}/download-csv?level=district",
            "csv_mandal": f"/api/multiday-dsr/jobs/{job_id}/download-csv?level=mandal",
            "csv_gp": f"/api/multiday-dsr/jobs/{job_id}/download-csv?level=gp",
        },
    }


def get_job_entry(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _JOBS.get(job_id)


def get_job_artifact(job_id: str, kind: str, level: str = "district") -> tuple[str, bytes, str]:
    entry = get_job_entry(job_id)
    if not entry:
        raise FileNotFoundError("Multi-Days DSR job not found or expired. Please re-upload files.")

    if kind == "pdf":
        p = Path(entry["pdf_path"])
        if not p.exists():
            raise FileNotFoundError("Generated Multi-Days DSR PDF file is no longer available.")
        return entry["pdf_filename"], p.read_bytes(), "application/pdf"

    if kind == "excel":
        p = Path(entry["excel_path"])
        if not p.exists():
            raise FileNotFoundError("Generated Multi-Days DSR Excel file is no longer available.")
        return (
            entry["excel_filename"],
            p.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if kind == "csv":
        lvl = (level or "district").strip().lower()
        if lvl not in entry["csv_bytes"]:
            lvl = "district"
        fname, raw = entry["csv_bytes"][lvl]
        return fname, raw, "text/csv; charset=utf-8"

    raise ValueError(f"Unsupported artifact kind: {kind}")

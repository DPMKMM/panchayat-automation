"""
DSR State Format - Service Orchestrator
=======================================
Coordinates the automated 3-report portal download pipeline via the existing Playwright engine,
runs enrichment, calculates official metrics, and generates PDF & Excel reports.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

from dsr.auto_download import download_single_report_with_menu, format_portal_date
from dsr.service import (
    get_or_create_session,
    ensure_active_bot,
    run_in_session_thread,
    _is_bot_alive,
    _save_bot_storage_state,
)
from dsr.pdf_generator import read_source_file

from DSR_State_Format.consolidation.lookup_builder import build_secretary_lookup
from DSR_State_Format.processing.data_enricher import enrich_raw_data
from DSR_State_Format.calculations.aggregator import compute_mandal_metrics, StateFormatReport
from DSR_State_Format.report_generation.pdf_generator import generate_state_format_pdf
from DSR_State_Format.report_generation.excel_generator import generate_state_format_excel

logger = logging.getLogger("dsr_state_format")

MODULE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = MODULE_DIR / "output"
TEMP_DIR = MODULE_DIR / "temp_downloads"
LOGS_DIR = MODULE_DIR / "logs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def generate_state_format_report(
    session_id: str = "",
    date_str: str = "",
    force_fresh: bool = True,
) -> dict[str, Any]:
    """
    Entry point called by the FastAPI router.
    Schedules execution on the dedicated single-thread session runner.
    """
    session = get_or_create_session(session_id)
    with session["lock"]:
        return run_in_session_thread(
            session,
            _generate_state_format_impl,
            session,
            date_str,
            force_fresh,
        )


def _generate_state_format_impl(
    session: dict[str, Any],
    date_str: str = "",
    force_fresh: bool = True,
) -> dict[str, Any]:
    """
    Live download execution inside the authenticated session thread:
    1. Clean session download directory (strictly fresh data rule)
    2. Download GM-R 1.2.7 (Raw Data)
    3. Download GM-R 1.2.11 (Presentees)
    4. Download GM-R 1.2.10 (Absentees)
    5. Consolidate, enrich, aggregate metrics
    6. Generate official PDF and Excel
    """
    is_auth = session.get("status") == "authenticated"
    if not is_auth:
        raise PermissionError(
            "e-Panchayat session is not logged in. Please complete Department Login & OTP first."
        )

    sid = session["session_id"]
    bot = session.get("bot")

    if not _is_bot_alive(bot):
        bot = ensure_active_bot(session)

    if not _is_bot_alive(bot):
        raise PermissionError(
            "e-Panchayat browser session is not active. Please complete Department Login & OTP."
        )

    portal_date_fmt = format_portal_date(date_str)
    dl_dir: Path = session["downloads_dir"]
    dl_dir.mkdir(parents=True, exist_ok=True)

    # Clean old downloads in this session's folder (never reuse offline cached data)
    for old_f in dl_dir.iterdir():
        if old_f.is_file():
            try:
                old_f.unlink()
            except Exception:
                pass

    downloaded_files: dict[str, Path] = {}

    try:
        logger.info("[%s] State Format: Step 1 - Downloading GM-R 1.2.7 DSR Raw Data...", sid[:6])
        p1 = download_single_report_with_menu(bot, "1.2.7", portal_date_fmt)
        if p1 and p1.exists() and p1.stat().st_size > 0:
            downloaded_files["raw_dsr"] = p1
        else:
            raise FileNotFoundError(f"Could not download GM-R 1.2.7 for date {portal_date_fmt}")

        logger.info("[%s] State Format: Step 2 - Downloading GM-R 1.2.11 Presentees...", sid[:6])
        try:
            p2 = download_single_report_with_menu(bot, "1.2.11", portal_date_fmt)
            if p2 and p2.exists() and p2.stat().st_size > 0:
                downloaded_files["presentees"] = p2
        except Exception as e:
            logger.warning("[%s] Note on GM-R 1.2.11 Presentees download: %s", sid[:6], e)

        logger.info("[%s] State Format: Step 3 - Downloading GM-R 1.2.10 Absentees...", sid[:6])
        try:
            p3 = download_single_report_with_menu(bot, "1.2.10", portal_date_fmt)
            if p3 and p3.exists() and p3.stat().st_size > 0:
                downloaded_files["absentees"] = p3
        except Exception as e:
            logger.warning("[%s] Note on GM-R 1.2.10 Absentees download: %s", sid[:6], e)

        _save_bot_storage_state(session, bot)
    except Exception as exc:
        logger.error("[%s] State Format download pipeline error: %s", sid[:6], exc)
        raise

    raw_path = downloaded_files.get("raw_dsr")
    if not raw_path or not raw_path.exists():
        raise FileNotFoundError(f"No DSR Raw Data file was downloaded for date '{portal_date_fmt}'.")

    p_file = downloaded_files.get("presentees")
    a_file = downloaded_files.get("absentees")

    pres_bytes = p_file.read_bytes() if p_file and p_file.exists() and p_file.stat().st_size > 0 else None
    pres_name = p_file.name if p_file else ""

    abs_bytes = a_file.read_bytes() if a_file and a_file.exists() and a_file.stat().st_size > 0 else None
    abs_name = a_file.name if a_file else ""

    return process_and_generate_reports(
        raw_bytes=raw_path.read_bytes(),
        raw_filename=raw_path.name,
        presentees_bytes=pres_bytes,
        presentees_filename=pres_name,
        absentees_bytes=abs_bytes,
        absentees_filename=abs_name,
        session=session,
    )


def process_and_generate_reports(
    raw_bytes: bytes,
    raw_filename: str,
    presentees_bytes: bytes | None = None,
    presentees_filename: str = "",
    absentees_bytes: bytes | None = None,
    absentees_filename: str = "",
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Parses downloaded or uploaded files, enriches with Secretary directory,
    computes 14-column mandal metrics, and writes PDF and Excel files to OUTPUT_DIR.
    """
    raw_df = read_source_file(raw_filename, raw_bytes)
    sec_lookup = build_secretary_lookup(
        presentees_bytes=presentees_bytes,
        presentees_filename=presentees_filename,
        absentees_bytes=absentees_bytes,
        absentees_filename=absentees_filename,
    )

    enriched_df = enrich_raw_data(raw_df, sec_lookup)

    now_dt = datetime.now()
    report = compute_mandal_metrics(
        enriched_df,
        district_name=enriched_df["district_name"].dropna().iloc[0] if "district_name" in enriched_df and not enriched_df["district_name"].dropna().empty else "Khammam",
        report_date=report_date_from_df(enriched_df, now_dt),
        generated_at=now_dt,
    )

    clean_dist = re.sub(r"[^A-Za-z0-9_-]", "_", report.district_name)
    date_file_str = report.report_date.strftime("%d-%b-%Y")
    time_file_str = now_dt.strftime("%I-%M-%p")

    pdf_filename = f"{clean_dist}_State_Format_DSR_Report_{date_file_str}_{time_file_str}.pdf"
    excel_filename = f"{clean_dist}_State_Format_DSR_Report_{date_file_str}_{time_file_str}.xlsx"

    pdf_path = OUTPUT_DIR / pdf_filename
    excel_path = OUTPUT_DIR / excel_filename

    generate_state_format_pdf(report, pdf_path)
    generate_state_format_excel(report, excel_path)

    if session:
        session["state_format_pdf"] = str(pdf_path)
        session["state_format_excel"] = str(excel_path)
        session["state_format_pdf_filename"] = pdf_filename
        session["state_format_excel_filename"] = excel_filename

    resp = report.to_dict()
    resp["status"] = "ok"
    resp["success"] = True
    resp["district"] = report.district_name
    resp["date"] = resp.get("report_date_str", report.report_date.strftime("%d-%b-%Y"))
    resp["time"] = resp.get("generated_time_display", now_dt.strftime("%I:%M %p"))
    resp["pdf_filename"] = pdf_filename
    resp["excel_filename"] = excel_filename
    resp["pdf_download_url"] = "/api/state-format/download-pdf"
    resp["excel_download_url"] = "/api/state-format/download-excel"
    resp["pdf_url"] = "/api/state-format/download-pdf"
    resp["excel_url"] = "/api/state-format/download-excel"
    resp["mandals"] = report.mandal_rows
    resp["totals"] = report.total_row
    resp["percentages"] = report.percentage_row
    resp["data"] = {
        "district": report.district_name,
        "date_str": resp.get("report_date_display", report.report_date.strftime("%d %B %Y")),
        "time_str": resp.get("generated_time_display", now_dt.strftime("%I:%M %p")),
        "mandals": report.mandal_rows,
        "totals": report.total_row,
        "percentages": report.percentage_row,
    }

    return resp


def report_date_from_df(df: pd.DataFrame, fallback_now: datetime) -> Any:
    """Extract report date from reporting_datetime or fallback to now."""
    if "reporting_datetime" in df.columns:
        valid_dts = [
            d for d in df["reporting_datetime"]
            if d is not None and not pd.isna(d) and hasattr(d, "date")
        ]
        for dt_val in valid_dts:
            try:
                res_d = dt_val.date()
                if res_d is not None and not pd.isna(res_d):
                    return res_d
            except Exception:
                continue
    return fallback_now.date()

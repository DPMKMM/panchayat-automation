"""
DSR State Format - Data Enrichment & Secretary Classification
=============================================================
Enriches GM-R 1.2.7 DSR RAW DATA with Secretary Lookup details.
Extracts reporting timestamps and maps attendance statuses.
"""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any
import pandas as pd

from DSR_State_Format.consolidation.lookup_builder import clean_lgd, clean_name, clean_string, is_regular_ps


def parse_timestamp(value: Any) -> datetime | None:
    """Parse portal datetime string into Python datetime object."""
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", ""}:
        return None
    # Common portal formats: "12-Nov-2026 08:47", "12-Nov-2026 08:47:12", "12/11/2026 08:47"
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        # Fallback to pandas parser
        ts = pd.to_datetime(text, errors="coerce")
        if pd.notna(ts):
            return ts.to_pydatetime()
    except Exception:
        pass
    return None


def standardize_status(raw_status: Any) -> str:
    """Classify status into: 'Present', 'Meeting', 'Leave', or 'Not Reported'."""
    if pd.isna(raw_status) or raw_status is None:
        return "Not Reported"
    s = str(raw_status).strip().lower()
    if not s or s in {"nan", "none", "null", "-", "unsubmitted", "not submitted", "absent"}:
        return "Not Reported"
    if "leave" in s:
        return "Leave"
    if "meeting" in s or "trng" in s or "training" in s:
        return "Meeting"
    if "present" in s:
        return "Present"
    return "Not Reported"


def enrich_raw_data(
    raw_df: pd.DataFrame,
    secretary_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """
    Enriches GM-R 1.2.7 DSR Raw Data with secretary details and parsed attendance metrics.
    Ensures 1 row per unique Panchayat LGD Code.
    """
    df = raw_df.copy()

    # Identify primary columns
    col_map = {}
    for col in df.columns:
        norm = re.sub(r"[^a-zA-Z0-9]", "", str(col).lower())
        if norm in ("panchayatlgd", "panchayatlgdcode", "lgdcode", "lgd"):
            col_map[col] = "lgd_code"
        elif norm in ("mandalname", "mandal"):
            col_map[col] = "mandal_name"
        elif norm in ("panchayatname", "gpname", "panchayat"):
            col_map[col] = "gp_name"
        elif norm in ("districtname", "district"):
            col_map[col] = "district_name"
        elif norm in ("firstattendancestatus", "firstattendencestatus"):
            col_map[col] = "first_status"
        elif norm in ("firstattendancedatetime", "firstattendencedatetime"):
            col_map[col] = "first_datetime"
        elif norm in ("secondattendancestatus", "secondattendencestatus"):
            col_map[col] = "second_status"
        elif norm in ("secondattendancedatetime", "secondattendencedatetime"):
            col_map[col] = "second_datetime"
        elif norm in ("dsrstatus", "dsrentrystatus"):
            col_map[col] = "dsr_status"
        elif norm in ("dsrsubmiteddatetime", "dsrsubmitteddatetime", "dsrdatetime"):
            col_map[col] = "dsr_datetime"

    if col_map:
        df = df.rename(columns=col_map)

    # Clean LGD codes
    if "lgd_code" not in df.columns:
        raise ValueError("GM-R 1.2.7 Raw Data must contain 'Panchayat LGD' column.")

    df["lgd_code"] = df["lgd_code"].apply(clean_lgd)
    # Filter out empty LGDs
    df = df[df["lgd_code"] != ""].copy()

    # Deduplicate by LGD code to ensure 1 unique record per GP
    df = df.drop_duplicates(subset=["lgd_code"], keep="first").copy()

    # Clean names
    df["mandal_name"] = df["mandal_name"].apply(clean_name) if "mandal_name" in df.columns else ""
    df["gp_name"] = df["gp_name"].apply(clean_name) if "gp_name" in df.columns else ""
    df["district_name"] = df["district_name"].apply(clean_name) if "district_name" in df.columns else ""

    # Enrich from Secretary Lookup
    ps_names = []
    mobiles = []
    postings = []
    is_regs = []
    emp_ids = []
    designations = []

    for lgd in df["lgd_code"]:
        sec = secretary_lookup.get(lgd)
        if sec:
            ps_names.append(sec.get("ps_name", ""))
            mobiles.append(sec.get("mobile", ""))
            post = sec.get("nature_of_posting", "")
            postings.append(post)
            is_regs.append(sec.get("is_regular", is_regular_ps(post)))
            emp_ids.append(sec.get("emp_id", ""))
            designations.append(sec.get("designation", ""))
        else:
            ps_names.append("")
            mobiles.append("")
            postings.append("")
            is_regs.append(False)
            emp_ids.append("")
            designations.append("")

    df["ps_name"] = ps_names
    df["mobile"] = mobiles
    df["nature_of_posting"] = postings
    df["is_regular"] = is_regs
    df["emp_id"] = emp_ids
    df["designation"] = designations

    # Parse reporting datetimes
    dt_first = df["first_datetime"].apply(parse_timestamp) if "first_datetime" in df.columns else pd.Series([None] * len(df))
    dt_second = df["second_datetime"].apply(parse_timestamp) if "second_datetime" in df.columns else pd.Series([None] * len(df))

    # Effective reporting datetime: primary is first, fallback is second
    effective_dt = []
    for f_dt, s_dt in zip(dt_first, dt_second):
        if f_dt is not None:
            effective_dt.append(f_dt)
        elif s_dt is not None:
            effective_dt.append(s_dt)
        else:
            effective_dt.append(None)

    df["reporting_datetime"] = effective_dt
    df["reporting_time"] = [dt.time() if dt is not None else None for dt in effective_dt]

    # Standardize attendance status
    stat_first = df["first_status"].apply(standardize_status) if "first_status" in df.columns else pd.Series(["Not Reported"] * len(df))
    stat_second = df["second_status"].apply(standardize_status) if "second_status" in df.columns else pd.Series(["Not Reported"] * len(df))

    final_status = []
    for s1, s2 in zip(stat_first, stat_second):
        if s1 != "Not Reported":
            final_status.append(s1)
        elif s2 != "Not Reported":
            final_status.append(s2)
        else:
            final_status.append("Not Reported")

    df["attendance_status"] = final_status

    return df

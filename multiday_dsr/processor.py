"""Core processor for Multi-Days DSR & Attendance consolidation.

Implements the user-provided `process_dsr` algorithm cleanly across HTML table[1]
exports (.xls), Excel (.xlsx), and CSV files, ignoring matplotlib charts as requested.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

IST = timezone(timedelta(hours=5, minutes=30))

REQUIRED_COLUMNS = [
    "District Name",
    "Mandal Name",
    "Panchayat Name",
    "Panchayat LGD",
    "First Attendence Status",
    "First Attendence Datetime",
    "DSR Entry Status",
    "DSR Submited Datetime",
]

COUNT_COLUMNS = [
    "Reported",
    "Present",
    "OnLeave",
    "Training",
    "Meeting",
    "DSR Entered",
    "Before 9 AM",
    "After 9 AM",
]


@dataclass
class MultiDayDsrResult:
    master_data: pd.DataFrame
    district: pd.DataFrame
    mandal: pd.DataFrame
    gp_summary: pd.DataFrame
    time_matrix: pd.DataFrame
    start_date: str
    end_date: str
    dist_name: str
    mandal_name: str
    mandal_count: int
    total_gps: int
    total_reporting_days: int
    generated_at: datetime


def classify_time_style(val: Any, cutoff: time | None = None) -> dict[str, str]:
    """Return styling metadata for exact attendance timestamps vs 09:00 AM cutoff."""
    s = str(val or "").strip()
    if not s or s == "-":
        return {"bg": "", "fg": "#64748b", "css": "color:#64748b;"}
    lim = cutoff or time(9, 0, 0)
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            t_val = datetime.strptime(s, fmt).time()
            if t_val < lim:
                return {"bg": "#dcfce7", "fg": "#166534", "css": "background-color:#dcfce7; color:#166534;"}
            return {"bg": "#fee2e2", "fg": "#991b1b", "css": "background-color:#fee2e2; color:#991b1b;"}
        except ValueError:
            continue
    # Non-time status label (e.g., On Leave, Training, Meeting)
    return {"bg": "#fef3c7", "fg": "#92400e", "css": "background-color:#fef3c7; color:#92400e;"}


def highlight_percentage(val: Any) -> dict[str, str]:
    """Return CSS/openpyxl/ReportLab styling metadata matching the user's thresholds."""
    try:
        num = float(val)
    except (TypeError, ValueError):
        return {"bg": "", "fg": "#1e293b", "css": ""}
    if pd.isna(num):
        return {"bg": "", "fg": "#1e293b", "css": ""}
    if num == 0:
        return {"bg": "#f8d7da", "fg": "#721c24", "css": "background-color:#f8d7da; color:#721c24;"}
    if 1 <= num <= 49.9999:
        return {"bg": "#f5c6cb", "fg": "#721c24", "css": "background-color:#f5c6cb; color:#721c24;"}
    if 50 <= num <= 74.9999:
        return {"bg": "#fff3cd", "fg": "#856404", "css": "background-color:#fff3cd; color:#856404;"}
    if 75 <= num <= 90.9999:
        return {"bg": "#ffeeba", "fg": "#856404", "css": "background-color:#ffeeba; color:#856404;"}
    if 91 <= num <= 99.9999:
        return {"bg": "#c3e6cb", "fg": "#155724", "css": "background-color:#c3e6cb; color:#155724;"}
    if num >= 100:
        return {"bg": "#28a745", "fg": "#ffffff", "css": "background-color:#28a745; color:#ffffff;"}
    return {"bg": "", "fg": "#1e293b", "css": ""}


def _clean_col_header(col: Any) -> str:
    if isinstance(col, tuple):
        parts = [str(p).strip() for p in col if str(p).strip() and "unnamed" not in str(p).lower()]
        return " ".join(parts).strip()
    return str(col).strip()


def _promote_header_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns match standard EPTS headers when read_html places headers in row 0."""
    df = df.copy()
    df.columns = [_clean_col_header(c) for c in df.columns]
    cols_low = {c.lower() for c in df.columns}
    if "district name" in cols_low and "mandal name" in cols_low:
        return df
    # Scan top rows for header row containing District Name & Panchayat Name
    for idx in range(min(5, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[idx].tolist()]
        row_low = {v.lower() for v in row_vals}
        if "district name" in row_low and "mandal name" in row_low:
            new_df = df.iloc[idx + 1 :].copy()
            new_df.columns = row_vals
            return new_df.reset_index(drop=True)
    return df


def _read_single_source(item: str | Path | tuple[str, bytes]) -> pd.DataFrame | None:
    """Read table[1] (or best matching sheet/CSV table) from a file path or (filename, bytes)."""
    if isinstance(item, tuple):
        fname, raw = item
        bio = io.BytesIO(raw)
        fname_low = fname.lower()
    else:
        p = Path(item)
        fname = p.name
        raw = p.read_bytes()
        bio = io.BytesIO(raw)
        fname_low = fname.lower()

    head_low = raw[:4096].decode("utf-8", errors="ignore").lower()
    is_html = "<table" in head_low or "<html" in head_low or "<!doctype" in head_low

    if is_html:
        try:
            tables = pd.read_html(io.BytesIO(raw))
            if len(tables) > 1:
                cand = _promote_header_if_needed(tables[1])
                if any("panchayat" in str(c).lower() for c in cand.columns):
                    return cand
            for tbl in tables:
                cand = _promote_header_if_needed(tbl)
                if {"district name", "mandal name"}.issubset({str(c).lower() for c in cand.columns}):
                    return cand
        except Exception:
            pass

    if fname_low.endswith(".csv"):
        try:
            return _promote_header_if_needed(pd.read_csv(io.BytesIO(raw)))
        except Exception:
            return None

    # Excel (.xlsx or binary .xls)
    for engine in ("openpyxl", "xlrd", None):
        try:
            bio.seek(0)
            df = pd.read_excel(bio, engine=engine) if engine else pd.read_excel(bio)
            cand = _promote_header_if_needed(df)
            if not cand.empty:
                return cand
        except Exception:
            continue

    # Last fallback: try read_html directly on path/bytes
    try:
        tables = pd.read_html(io.BytesIO(raw))
        if len(tables) > 1:
            return _promote_header_if_needed(tables[1])
        if tables:
            return _promote_header_if_needed(tables[0])
    except Exception:
        return None
    return None


def _normalize_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common column spelling variants onto the user's exact REQUIRED_COLUMNS."""
    out = df.copy()
    col_map = {str(c).strip().lower(): str(c).strip() for c in out.columns}
    aliases = {
        "District Name": ["district name", "district"],
        "Mandal Name": ["mandal name", "mandal"],
        "Panchayat Name": ["panchayat name", "gram panchayat", "gp name"],
        "Panchayat LGD": ["panchayat lgd", "lgd code", "lgd"],
        "First Attendence Status": ["first attendence status", "first attendance status", "attendance status"],
        "First Attendence Datetime": ["first attendence datetime", "first attendance datetime", "attendance datetime"],
        "DSR Entry Status": ["dsr entry status", "dsr status"],
        "DSR Submited Datetime": ["dsr submited datetime", "dsr submitted datetime", "dsr datetime"],
    }
    rename_dict: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        if canonical in out.columns:
            continue
        for c_low in candidates:
            if c_low in col_map:
                rename_dict[col_map[c_low]] = canonical
                break
    if rename_dict:
        out = out.rename(columns=rename_dict)
    # Optional DSR timestamp column may be absent in minimal exports; create blank if missing
    if "DSR Submited Datetime" not in out.columns and "DSR Entry Status" in out.columns:
        out["DSR Submited Datetime"] = ""
    return out


def process_dsr(
    file_paths: list[str | Path | tuple[str, bytes]],
    cutoff_time: time | None = None,
) -> MultiDayDsrResult:
    """Execute the exact Multi-Days DSR logic on uploaded files (without matplotlib graphs)."""
    if not file_paths:
        raise ValueError("Please upload at least one daily GM-R 1.2.7 report file.")

    all_dfs: list[pd.DataFrame] = []
    for item in file_paths:
        tbl = _read_single_source(item)
        if tbl is not None and not tbl.empty:
            all_dfs.append(_normalize_aliases(tbl))

    if not all_dfs:
        raise ValueError("No valid HTML table[1] or tabular data was found in the uploaded files.")

    source = pd.concat(all_dfs, ignore_index=True)

    missing = [col for col in REQUIRED_COLUMNS if col not in source.columns]
    if missing:
        raise ValueError(f"Missing required columns in source data: {missing}")

    df = source[REQUIRED_COLUMNS].copy()
    for txt_col in ("District Name", "Mandal Name", "Panchayat Name"):
        df[txt_col] = df[txt_col].fillna("").astype(str).str.strip()
    df["Panchayat LGD"] = df["Panchayat LGD"].astype(str).str.strip()
    df = df[df["District Name"].ne("") & df["Mandal Name"].ne("")].copy()

    master_data = df.copy()
    parsed_master_dt = pd.to_datetime(master_data["First Attendence Datetime"], errors="coerce", dayfirst=True)
    if parsed_master_dt.notna().any():
        start_date = parsed_master_dt.min().strftime("%d-%m-%Y")
        end_date = parsed_master_dt.max().strftime("%d-%m-%Y")
    else:
        dsr_fallback_dt = pd.to_datetime(master_data["DSR Submited Datetime"], errors="coerce", dayfirst=True)
        if not dsr_fallback_dt.notna().any():
            raise ValueError("No reporting dates could be identified. Check the attendance/DSR datetime columns.")
        start_date = dsr_fallback_dt.min().strftime("%d-%m-%Y")
        end_date = dsr_fallback_dt.max().strftime("%d-%m-%Y")

    dist_vals = [v for v in master_data["District Name"].dropna().unique() if str(v).strip()]
    dist_name = str(dist_vals[0]).strip() if dist_vals else "District"
    mandal_un = [v for v in master_data["Mandal Name"].dropna().unique() if str(v).strip()]
    mandal_name = str(mandal_un[0]).strip() if mandal_un else "Mandal"
    mandal_count = len(mandal_un)

    df["Attendance DT"] = pd.to_datetime(df["First Attendence Datetime"], errors="coerce", dayfirst=True)
    df["DSR DT"] = pd.to_datetime(df["DSR Submited Datetime"], errors="coerce", dayfirst=True)

    df["Report Date"] = df["Attendance DT"].dt.normalize()
    df["Report Date"] = df["Report Date"].fillna(df["DSR DT"].dt.normalize())

    df["Attendance Status"] = df["First Attendence Status"].fillna("").astype(str).str.strip()
    df["DSR Entry Status"] = df["DSR Entry Status"].fillna("").astype(str).str.strip()
    df["Attendance Time"] = df["Attendance DT"].dt.strftime("%H:%M:%S")

    # GP master across ALL uploaded rows before removing missing-date rows
    gp_master = (
        df[["District Name", "Mandal Name", "Panchayat Name", "Panchayat LGD"]]
        .dropna(subset=["Panchayat LGD"])
        .copy()
    )
    gp_master = gp_master[gp_master["Panchayat LGD"].ne("") & gp_master["Panchayat LGD"].ne("nan")]
    gp_master = gp_master.drop_duplicates(subset=["Panchayat LGD"]).copy()

    df = df[df["Report Date"].notna()].copy()
    if df.empty:
        raise ValueError("No reporting dates could be identified. Check the attendance/DSR datetime columns.")

    df = df.sort_values(["Report Date", "Panchayat LGD"])
    df = df.drop_duplicates(subset=["Panchayat LGD", "Report Date"], keep="last").copy()

    dates = sorted(df["Report Date"].dropna().unique())
    total_gps = int(gp_master["Panchayat LGD"].nunique())
    total_reporting_days = len(dates)

    # Attendance & DSR flags
    status = df["Attendance Status"].str.lower()
    df["Present"] = status.eq("present").astype(int)
    df["OnLeave"] = status.isin(["on leave", "onleave"]).astype(int)
    df["Training"] = status.str.startswith("training").astype(int)
    df["Meeting"] = status.str.startswith("meeting").astype(int)
    df["Reported"] = df["Attendance Status"].ne("").astype(int)

    nine_am = cutoff_time or datetime.strptime("09:00:00", "%H:%M:%S").time()
    df["Before 9 AM"] = (df["Attendance DT"].notna() & (df["Attendance DT"].dt.time < nine_am)).astype(int)
    df["After 9 AM"] = (df["Attendance DT"].notna() & (df["Attendance DT"].dt.time >= nine_am)).astype(int)
    df["DSR Entered"] = df["DSR Entry Status"].str.lower().eq("entered").astype(int)

    def _summarize(grouped: Any) -> pd.DataFrame:
        return grouped[COUNT_COLUMNS].sum().reset_index()

    def _add_punctuality_pcts(table_df: pd.DataFrame) -> None:
        denom = table_df["Reported"].astype(float).where(table_df["Reported"] > 0)
        table_df["Before 9 AM %"] = ((table_df["Before 9 AM"].astype(float) / denom) * 100.0).fillna(0.0).round(2)
        table_df["After 9 AM %"] = ((table_df["After 9 AM"].astype(float) / denom) * 100.0).fillna(0.0).round(2)

    # 1. District Level: Date-wise
    district = _summarize(df.groupby("Report Date", dropna=False))
    district["No. of GPs"] = total_gps
    district["Not Reported"] = district["No. of GPs"] - district["Reported"]
    _add_punctuality_pcts(district)
    district = district.rename(columns={"Report Date": "Date", "Reported": "Total Reported"})
    district = district[
        [
            "Date",
            "No. of GPs",
            "Total Reported",
            "Present",
            "OnLeave",
            "Training",
            "Meeting",
            "Not Reported",
            "DSR Entered",
            "Before 9 AM",
            "After 9 AM",
            "Before 9 AM %",
            "After 9 AM %",
        ]
    ].sort_values("Date").copy()
    district["Date"] = pd.to_datetime(district["Date"]).dt.strftime("%d-%m-%Y")
    district.insert(0, "S.No", range(1, len(district) + 1))

    # 2. Mandal Level: Mandal + Date-wise
    mandal = _summarize(df.groupby(["Mandal Name", "Report Date"], dropna=False))
    mandal_gp_counts = gp_master.groupby("Mandal Name")["Panchayat LGD"].nunique().rename("No. of GPs")
    mandal_calendar = pd.MultiIndex.from_product(
        [sorted(mandal_gp_counts.index.tolist()), dates],
        names=["Mandal Name", "Report Date"],
    ).to_frame(index=False)
    mandal = mandal_calendar.merge(mandal, on=["Mandal Name", "Report Date"], how="left")
    for col in COUNT_COLUMNS:
        mandal[col] = mandal[col].fillna(0).astype(int)
    mandal = mandal.merge(mandal_gp_counts, on="Mandal Name", how="left")
    mandal["No. of GPs"] = mandal["No. of GPs"].fillna(0).astype(int)
    mandal["Not Reported"] = mandal["No. of GPs"] - mandal["Reported"]
    _add_punctuality_pcts(mandal)
    mandal = mandal.rename(columns={"Report Date": "Date", "Reported": "Total Reported"})
    mandal = mandal[
        [
            "Mandal Name",
            "Date",
            "No. of GPs",
            "Total Reported",
            "Present",
            "OnLeave",
            "Training",
            "Meeting",
            "Not Reported",
            "DSR Entered",
            "Before 9 AM",
            "After 9 AM",
            "Before 9 AM %",
            "After 9 AM %",
        ]
    ].sort_values(["Mandal Name", "Date"]).copy()
    mandal["Date"] = pd.to_datetime(mandal["Date"]).dt.strftime("%d-%m-%Y")
    mandal.insert(0, "S.No", range(1, len(mandal) + 1))

    # 3. GP Level: GP-wise period summary
    gp_summary = _summarize(df.groupby(["Mandal Name", "Panchayat Name", "Panchayat LGD"], dropna=False))
    gp_summary = gp_master[["Mandal Name", "Panchayat Name", "Panchayat LGD"]].merge(
        gp_summary,
        on=["Mandal Name", "Panchayat Name", "Panchayat LGD"],
        how="left",
    )
    for col in COUNT_COLUMNS:
        gp_summary[col] = gp_summary[col].fillna(0).astype(int)

    gp_summary["Total Reporting Days"] = total_reporting_days
    gp_summary["Not Reported days"] = gp_summary["Total Reporting Days"] - gp_summary["Reported"]
    _add_punctuality_pcts(gp_summary)
    gp_summary = gp_summary.rename(
        columns={
            "Reported": "No. of Days Reported",
            "DSR Entered": "No. of Days DSR Entered",
            "Before 9 AM": "No. of Days Before 9 AM Reported",
            "After 9 AM": "No. of Days After 9 AM Reported",
        }
    )
    gp_summary = gp_summary[
        [
            "Mandal Name",
            "Panchayat Name",
            "Total Reporting Days",
            "No. of Days Reported",
            "Present",
            "OnLeave",
            "Training",
            "Meeting",
            "Not Reported days",
            "No. of Days DSR Entered",
            "No. of Days Before 9 AM Reported",
            "No. of Days After 9 AM Reported",
            "Before 9 AM %",
            "After 9 AM %",
        ]
    ].sort_values(["Mandal Name", "Panchayat Name"]).copy()
    gp_summary.insert(0, "S.No", range(1, len(gp_summary) + 1))

    # 4. Day-Wise Exact Attendance Time Matrix + Status Counts + Average Time & No. of Days Before 9 AM
    date_labels = [pd.to_datetime(d).strftime("%d-%m-%Y") for d in dates]
    # Tuple per (lgd, date): (display_str, sec_mid, is_b9, is_present, is_onleave, is_tm, is_reported)
    cell_lookup: dict[tuple[str, str], tuple[str, int | None, int, int, int, int, int]] = {}
    for lgd_raw, r_dt, att_dt, att_st_raw in df[
        ["Panchayat LGD", "Report Date", "Attendance DT", "Attendance Status"]
    ].itertuples(index=False, name=None):
        lgd = str(lgd_raw).strip()
        d_lbl = pd.to_datetime(r_dt).strftime("%d-%m-%Y")
        st_lbl = str(att_st_raw or "").strip()
        st_low = st_lbl.lower()
        is_pres = int(st_low == "present")
        is_leave = int(st_low in ("on leave", "onleave"))
        is_tm = int(st_low.startswith("training") or st_low.startswith("meeting"))
        is_rep = int(st_lbl != "")
        if pd.notna(att_dt):
            exact_str = att_dt.strftime("%H:%M")
            sec_mid = att_dt.hour * 3600 + att_dt.minute * 60 + att_dt.second
            is_b9 = int(att_dt.time() < nine_am)
            cell_lookup[(lgd, d_lbl)] = (exact_str, sec_mid, is_b9, is_pres, is_leave, is_tm, is_rep)
        else:
            cell_lookup[(lgd, d_lbl)] = (st_lbl if st_lbl else "-", None, 0, is_pres, is_leave, is_tm, is_rep)

    gp_sorted = gp_master.sort_values(["Mandal Name", "Panchayat Name"]).reset_index(drop=True)
    tm_rows: list[dict[str, Any]] = []
    for idx, gp_row in enumerate(gp_sorted[["Mandal Name", "Panchayat Name", "Panchayat LGD"]].itertuples(index=False, name=None), start=1):
        m_name = str(gp_row[0]).strip()
        gp_name = str(gp_row[1]).strip()
        lgd = str(gp_row[2]).strip()
        item: dict[str, Any] = {
            "S.No": idx,
            "Mandal Name": m_name,
            "Panchayat Name": gp_name,
        }
        secs_list: list[int] = []
        b9_count = 0
        pres_count = 0
        leave_count = 0
        tm_count = 0
        rep_count = 0
        for d_lbl in date_labels:
            val_str, sec_mid, is_b9, is_pres, is_leave, is_tm, is_rep = cell_lookup.get(
                (lgd, d_lbl), ("-", None, 0, 0, 0, 0, 0)
            )
            item[d_lbl] = val_str
            if sec_mid is not None:
                secs_list.append(sec_mid)
            b9_count += is_b9
            pres_count += is_pres
            leave_count += is_leave
            tm_count += is_tm
            rep_count += is_rep

        item["Present"] = pres_count
        item["On Leave"] = leave_count
        item["Not Marked Attendance"] = max(0, total_reporting_days - rep_count)
        item["Training / Meeting"] = tm_count
        if secs_list:
            avg_s = int(round(sum(secs_list) / len(secs_list)))
            hh, rem = divmod(avg_s, 3600)
            mm = rem // 60
            item["Average Time"] = datetime(2000, 1, 1, hh % 24, mm).strftime("%H:%M")
        else:
            item["Average Time"] = "-"
        item["No. of Days Before 9 AM"] = b9_count
        tm_rows.append(item)

    tm_summary_cols = [
        "Present",
        "On Leave",
        "Not Marked Attendance",
        "Training / Meeting",
        "Average Time",
        "No. of Days Before 9 AM",
    ]
    tm_cols = ["S.No", "Mandal Name", "Panchayat Name"] + date_labels + tm_summary_cols
    time_matrix = pd.DataFrame(tm_rows, columns=tm_cols)

    return MultiDayDsrResult(
        master_data=master_data.reset_index(drop=True),
        district=district.reset_index(drop=True),
        mandal=mandal.reset_index(drop=True),
        gp_summary=gp_summary.reset_index(drop=True),
        time_matrix=time_matrix.reset_index(drop=True),
        start_date=start_date,
        end_date=end_date,
        dist_name=dist_name,
        mandal_name=mandal_name,
        mandal_count=mandal_count,
        total_gps=total_gps,
        total_reporting_days=total_reporting_days,
        generated_at=datetime.now(IST),
    )

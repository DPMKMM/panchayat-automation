"""Service to fetch, clean, consolidate, and export Telangana ePanchayat House Tax DCB data."""

from __future__ import annotations

import io
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
import pandas as pd

logger = logging.getLogger("epmis_tax_service")

URL_ALL_GP_DATA = "https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp"
URL_DISTRICT_LIVE = "https://epanchayat.telangana.gov.in/epmis/epmisPRHTAXDCBLive.jsp"

_LIVE_BYTES_CACHE: Optional[bytes] = None
_LAST_FETCH_TIME: float = 0.0


def download_portal_raw_data() -> bytes:
    """Download fresh raw Excel data directly from Telangana epanchayat portal."""
    global _LIVE_BYTES_CACHE, _LAST_FETCH_TIME
    logger.info("Connecting to Telangana portal to fetch fresh live DCB data: %s", URL_ALL_GP_DATA)
    with httpx.Client(verify=False, timeout=60.0) as client:
        resp = client.get(URL_ALL_GP_DATA, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        resp.raise_for_status()
        content = resp.content
        if len(content) < 50_000:
            raise ValueError(f"Portal returned invalid or empty data ({len(content)} bytes)")

        _LIVE_BYTES_CACHE = content
        _LAST_FETCH_TIME = time.time()
        logger.info("Successfully fetched live portal DCB data: %d bytes", len(content))
        return content


def get_raw_data_bytes(force_download: bool = False) -> bytes:
    """Always fetch live real-time data from portal. Short 2-minute memory cache prevents duplicate downloads during rapid page navigation."""
    global _LIVE_BYTES_CACHE, _LAST_FETCH_TIME

    # If force_download is requested, or cache is older than 2 minutes, fetch live from portal
    if not force_download and _LIVE_BYTES_CACHE and (time.time() - _LAST_FETCH_TIME < 120):
        return _LIVE_BYTES_CACHE

    try:
        return download_portal_raw_data()
    except Exception as exc:
        logger.error("Live portal download attempt failed: %s", exc)
        raise RuntimeError(f"Could not fetch live data from Telangana e-Panchayat portal: {exc}") from exc


def parse_and_clean_data(raw_bytes: Optional[bytes] = None) -> pd.DataFrame:
    """Parse raw bytes into a clean, strongly-typed pandas DataFrame."""
    if raw_bytes is None:
        raw_bytes = get_raw_data_bytes()

    # Raw file has a title row on line 0, actual headers on line 1
    df = pd.read_excel(io.BytesIO(raw_bytes), skiprows=1)

    # Standardize column names
    col_map = {
        "SNO": "sno",
        "DIST_NAME": "district",
        "MAND_NAME": "mandal",
        "OFFICE_TITTLE": "panchayat",
        "Total_GPs": "total_gps",
        "Enabled_GPs": "enabled_gps",
        "Not_Enabled_GPs": "not_enabled_gps",
        "Current_FY_GPs": "current_fy_gps",
        "Backlog_GPs": "backlog_gps",
        "Assessment_Records": "assessments",
        "Demand_Arrear": "demand_arrear",
        "Demand_Current": "demand_current",
        "Demand_Total": "demand_total",
        "Collection_Arrear": "collection_arrear",
        "Collection_Current": "collection_current",
        "Collection_Total": "collection_total",
        "Write_Off": "write_off",
        "Percentage": "percentage",
        "Balance_Arrear": "balance_arrear",
        "Balance_Current": "balance_current",
        "Balance_Total": "balance_total",
    }
    df = df.rename(columns=col_map)

    # Filter out any non-data or blank district rows
    df = df.dropna(subset=["district", "mandal", "panchayat"]).copy()
    df["district"] = df["district"].astype(str).str.strip()
    df["mandal"] = df["mandal"].astype(str).str.strip()
    df["panchayat"] = df["panchayat"].astype(str).str.strip()

    # Numeric columns to sanitize
    numeric_cols = [
        "total_gps", "enabled_gps", "not_enabled_gps", "current_fy_gps", "backlog_gps",
        "assessments", "demand_arrear", "demand_current", "demand_total",
        "collection_arrear", "collection_current", "collection_total", "write_off",
        "percentage", "balance_arrear", "balance_current", "balance_total"
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Re-calculate correct collection percentage where demand_total > 0
    pct = (df["collection_total"] / df["demand_total"].replace(0, float("nan")) * 100).fillna(0.0)
    df["calc_percentage"] = pct.astype(float).round(1)

    return df


_DF_CACHE: Optional[pd.DataFrame] = None


def get_df(force_reload: bool = False) -> pd.DataFrame:
    global _DF_CACHE
    if _DF_CACHE is None or force_reload or (_LAST_FETCH_TIME and (time.time() - _LAST_FETCH_TIME > 120)):
        raw = get_raw_data_bytes(force_download=force_reload)
        _DF_CACHE = parse_and_clean_data(raw)
    return _DF_CACHE


def get_districts_list() -> List[Dict[str, Any]]:
    """Return all districts with summary count."""
    df = get_df()
    grouped = df.groupby("district").agg(
        mandals_count=("mandal", "nunique"),
        gps_count=("panchayat", "count"),
        total_demand=("demand_total", "sum"),
        total_collection=("collection_total", "sum"),
        total_balance=("balance_total", "sum"),
    ).reset_index()

    pct = (grouped["total_collection"] / grouped["total_demand"].replace(0, float("nan")) * 100).fillna(0.0)
    grouped["percentage"] = pct.astype(float).round(1)
    grouped = grouped.sort_values(by="district")
    return grouped.to_dict(orient="records")


def get_mandals_for_district(district_name: str) -> List[str]:
    """Return sorted unique mandals for a district."""
    df = get_df()
    if not district_name or district_name.lower() in ("all", "all districts"):
        return sorted(df["mandal"].unique().tolist())
    match = df[df["district"].str.lower() == district_name.strip().lower()]
    return sorted(match["mandal"].unique().tolist())


def get_filtered_data(district_name: Optional[str] = None, mandal_name: Optional[str] = None) -> Dict[str, Any]:
    """Return filtered records along with aggregate summary totals and mandal summaries."""
    df = get_df()
    filtered = df.copy()

    if district_name and district_name.lower() not in ("all", "all districts"):
        filtered = filtered[filtered["district"].str.lower() == district_name.strip().lower()]

    if mandal_name and mandal_name.lower() not in ("all", "all mandals"):
        filtered = filtered[filtered["mandal"].str.lower() == mandal_name.strip().lower()]

    filtered = filtered.sort_values(by=["district", "mandal", "panchayat"])

    tot_demand = float(filtered["demand_total"].sum())
    tot_coll = float(filtered["collection_total"].sum())
    tot_bal = float(filtered["balance_total"].sum())
    tot_records = int(filtered["assessments"].sum())
    tot_gps = len(filtered)
    tot_mandals = int(filtered["mandal"].nunique())
    overall_pct = round((tot_coll / tot_demand * 100), 2) if tot_demand > 0 else 0.0

    # Mandal-wise grouped abstract
    mandal_groups = filtered.groupby(["district", "mandal"]).agg(
        total_gps=("panchayat", "count"),
        assessments=("assessments", "sum"),
        demand_arrear=("demand_arrear", "sum"),
        demand_current=("demand_current", "sum"),
        demand_total=("demand_total", "sum"),
        collection_arrear=("collection_arrear", "sum"),
        collection_current=("collection_current", "sum"),
        collection_total=("collection_total", "sum"),
        write_off=("write_off", "sum"),
        balance_arrear=("balance_arrear", "sum"),
        balance_current=("balance_current", "sum"),
        balance_total=("balance_total", "sum"),
    ).reset_index()

    pct_mandal = (mandal_groups["collection_total"] / mandal_groups["demand_total"].replace(0, float("nan")) * 100).fillna(0.0)
    mandal_groups["percentage"] = pct_mandal.astype(float).round(1)
    # Sort Mandal-wise consolidated abstract in ascending order based on % Collection
    mandal_groups = mandal_groups.sort_values(by=["percentage", "demand_total"], ascending=[True, True])
    mandal_rows = mandal_groups.to_dict(orient="records")

    records = filtered.to_dict(orient="records")

    return {
        "summary": {
            "district": district_name or "All Districts",
            "mandal": mandal_name or "All Mandals",
            "total_mandals": tot_mandals,
            "total_gps": tot_gps,
            "total_assessments": tot_records,
            "total_demand": tot_demand,
            "total_collection": tot_coll,
            "total_balance": tot_bal,
            "overall_percentage": overall_pct,
            "demand_arrear": float(filtered["demand_arrear"].sum()),
            "demand_current": float(filtered["demand_current"].sum()),
            "collection_arrear": float(filtered["collection_arrear"].sum()),
            "collection_current": float(filtered["collection_current"].sum()),
            "balance_arrear": float(filtered["balance_arrear"].sum()),
            "balance_current": float(filtered["balance_current"].sum()),
        },
        "mandal_abstract": mandal_rows,
        "records": records,
    }


def generate_consolidated_excel(district_name: Optional[str] = None) -> bytes:
    """Generate a clean, professional multi-sheet Excel file.
    Sheet 1: Mandal Summary Abstract (Consolidated)
    Sheet 2: Detailed Gram Panchayat DCB
    """
    df = get_df()
    if district_name and district_name.lower() not in ("all", "all districts"):
        df_sub = df[df["district"].str.lower() == district_name.strip().lower()].copy()
    else:
        df_sub = df.copy()

    # Create Mandal-wise Abstract
    mandal_summary = df_sub.groupby(["district", "mandal"]).agg(
        Total_GPs=("panchayat", "count"),
        Total_Assessments=("assessments", "sum"),
        Demand_Arrear=("demand_arrear", "sum"),
        Demand_Current=("demand_current", "sum"),
        Demand_Total=("demand_total", "sum"),
        Collection_Arrear=("collection_arrear", "sum"),
        Collection_Current=("collection_current", "sum"),
        Collection_Total=("collection_total", "sum"),
        Write_Off=("write_off", "sum"),
        Balance_Arrear=("balance_arrear", "sum"),
        Balance_Current=("balance_current", "sum"),
        Balance_Total=("balance_total", "sum"),
    ).reset_index()

    pct_m = (mandal_summary["Collection_Total"] / mandal_summary["Demand_Total"].replace(0, float("nan")) * 100).fillna(0.0)
    mandal_summary["Collection_Percent"] = pct_m.astype(float).round(1)
    mandal_summary = mandal_summary.sort_values(by=["Collection_Percent", "Demand_Total"], ascending=[True, True])

    # Detailed GP columns
    detail_df = df_sub[[
        "district", "mandal", "panchayat", "assessments",
        "demand_arrear", "demand_current", "demand_total",
        "collection_arrear", "collection_current", "collection_total",
        "write_off", "calc_percentage", "balance_arrear", "balance_current", "balance_total"
    ]].copy()
    detail_df.columns = [
        "District", "Mandal", "Gram Panchayat", "Assessment Count",
        "Demand Arrear (Rs)", "Demand Current (Rs)", "Demand Total (Rs)",
        "Collection Arrear (Rs)", "Collection Current (Rs)", "Collection Total (Rs)",
        "Write Off (Rs)", "Collection %", "Balance Arrear (Rs)", "Balance Current (Rs)", "Balance Total (Rs)"
    ]

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        mandal_summary.to_excel(writer, sheet_name="Mandal Abstract", index=False)
        detail_df.to_excel(writer, sheet_name="GP Wise DCB Detail", index=False)

    return out.getvalue()


def generate_consolidated_csv(district_name: Optional[str] = None) -> bytes:
    """Generate consolidated CSV for the Gram Panchayat DCB detail."""
    df = get_df()
    if district_name and district_name.lower() not in ("all", "all districts"):
        df_sub = df[df["district"].str.lower() == district_name.strip().lower()].copy()
    else:
        df_sub = df.copy()

    detail_df = df_sub[[
        "district", "mandal", "panchayat", "assessments",
        "demand_arrear", "demand_current", "demand_total",
        "collection_arrear", "collection_current", "collection_total",
        "write_off", "calc_percentage", "balance_arrear", "balance_current", "balance_total"
    ]].copy()
    detail_df.columns = [
        "District", "Mandal", "Gram Panchayat", "Assessment Count",
        "Demand Arrear (Rs)", "Demand Current (Rs)", "Demand Total (Rs)",
        "Collection Arrear (Rs)", "Collection Current (Rs)", "Collection Total (Rs)",
        "Write Off (Rs)", "Collection %", "Balance Arrear (Rs)", "Balance Current (Rs)", "Balance Total (Rs)"
    ]

    return detail_df.to_csv(index=False).encode("utf-8")

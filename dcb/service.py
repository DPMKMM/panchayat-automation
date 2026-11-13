"""Demand Collection Balance (DCB) Service for Telangana ePanchayat House Tax.

All data is scraped live from the official Telangana e-Panchayat web portal:
https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp

No offline Excel/CSV seed files are used. All datasets are dynamically scraped,
sanitized in-memory, and cached for fast sub-second responsiveness.
"""

from __future__ import annotations

import io
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx
import pandas as pd

from core.config import URL_ALL_GP_DATA, DCB_PORTAL_PROXY_URL, DCB_PORTAL_PROXY_TOKEN

logger = logging.getLogger("dcb_service")

_DF_CACHE: Optional[pd.DataFrame] = None
_LIVE_BYTES_CACHE: Optional[bytes] = None
_LAST_FETCH_TIME: float = 0.0
CACHE_TTL_SECONDS = 300.0  # 5 minutes in-memory cache TTL


def download_portal_raw_data() -> bytes:
    """Download fresh raw DCB data directly from Telangana e-Panchayat web portal or configured proxy."""
    global _LIVE_BYTES_CACHE, _LAST_FETCH_TIME

    if DCB_PORTAL_PROXY_URL:
        if not DCB_PORTAL_PROXY_TOKEN:
            raise RuntimeError("DCB_PORTAL_PROXY_TOKEN is required when DCB_PORTAL_PROXY_URL is set.")
        request_url = f"{DCB_PORTAL_PROXY_URL}/v1/dcb/raw"
        logger.info("Scraping live DCB data through configured proxy: %s", request_url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.ms-excel,application/octet-stream,*/*",
            "Authorization": f"Bearer {DCB_PORTAL_PROXY_TOKEN}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    else:
        request_url = URL_ALL_GP_DATA
        logger.info("Connecting directly to Telangana e-Panchayat portal for live DCB scrape: %s", URL_ALL_GP_DATA)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.ms-excel,application/octet-stream,*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

    with httpx.Client(verify=False, timeout=60.0, follow_redirects=True) as client:
        resp = client.get(request_url, headers=headers)
        resp.raise_for_status()
        content = resp.content
        if len(content) < 50_000:
            raise ValueError(f"Portal returned invalid or incomplete data ({len(content)} bytes)")

        _LIVE_BYTES_CACHE = content
        _LAST_FETCH_TIME = time.time()
        logger.info("Successfully scraped live portal DCB data: %d bytes", len(content))
        return content


def get_raw_data_bytes(force_download: bool = False) -> bytes:
    """Fetch live data bytes with in-memory caching."""
    global _LIVE_BYTES_CACHE, _LAST_FETCH_TIME

    if not force_download and _LIVE_BYTES_CACHE and (time.time() - _LAST_FETCH_TIME < CACHE_TTL_SECONDS):
        return _LIVE_BYTES_CACHE

    try:
        return download_portal_raw_data()
    except Exception as exc:
        logger.warning("Live portal scrape attempt encountered error: %s", exc)
        if _LIVE_BYTES_CACHE:
            logger.info("Serving active in-memory cached raw bytes (%d bytes)", len(_LIVE_BYTES_CACHE))
            return _LIVE_BYTES_CACHE
        raise RuntimeError(f"Could not connect to Telangana e-Panchayat portal: {exc}") from exc


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names, trim strings, and cast numeric fields."""
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

    num_cols = [
        "assessments",
        "demand_arrear",
        "demand_current",
        "demand_total",
        "collection_arrear",
        "collection_current",
        "collection_total",
        "write_off",
        "percentage",
        "balance_arrear",
        "balance_current",
        "balance_total",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Calculate exact collection percentage rounded to 1 decimal place
    calc_pct = (df["collection_total"] / df["demand_total"].replace(0, float("nan")) * 100).replace([float("inf"), -float("inf")], 0.0).fillna(0.0)
    df["calc_percentage"] = calc_pct.astype(float).round(1)
    df["percentage"] = df["calc_percentage"]

    # Filter out empty or header artifact rows
    df = df[df["district"].str.len() > 1]
    df = df[~df["district"].str.lower().str.contains("total|sno|district", na=False)]
    return df


def parse_and_clean_data(raw_bytes: Optional[bytes] = None) -> pd.DataFrame:
    """Parse raw bytes scraped from e-Panchayat web portal into a clean DataFrame."""
    if raw_bytes is None:
        raw_bytes = get_raw_data_bytes()

    try:
        df = pd.read_excel(io.BytesIO(raw_bytes), skiprows=1)
    except Exception:
        # Fallback to HTML table parser if returned as HTML format
        tables = pd.read_html(io.BytesIO(raw_bytes))
        df = tables[0] if tables else pd.DataFrame()

    return _sanitize_df(df)


def get_df(force_reload: bool = False) -> pd.DataFrame:
    """Retrieve the active live DCB DataFrame with in-memory caching."""
    global _DF_CACHE
    if force_reload or _DF_CACHE is None or (time.time() - _LAST_FETCH_TIME >= CACHE_TTL_SECONDS):
        logger.info("Scraping fresh live DCB data from epanchayat.telangana.gov.in (in-memory)...")
        raw = get_raw_data_bytes(force_download=force_reload)
        _DF_CACHE = parse_and_clean_data(raw)
        logger.info("Successfully loaded fresh live DCB dataset: %d GP rows", len(_DF_CACHE))
    return _DF_CACHE


def _resolve_df(df_source: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Use supplied DataFrame directly or fetch cached live DCB DataFrame."""
    if df_source is not None:
        return df_source
    return get_df()


def get_districts_list() -> List[Dict[str, Any]]:
    """Return all districts in Telangana with GP counts scraped live."""
    df = get_df()
    grouped = df.groupby("district").agg(
        gps_count=("panchayat", "count"),
        total_demand=("demand_total", "sum"),
        total_collection=("collection_total", "sum")
    ).reset_index()

    pct = (grouped["total_collection"] / grouped["total_demand"].replace(0, float("nan")) * 100).fillna(0.0)
    grouped["percentage"] = pct.astype(float).round(1)

    result = []
    for _, row in grouped.iterrows():
        result.append({
            "district": row["district"],
            "gps_count": int(row["gps_count"]),
            "demand": float(row["total_demand"]),
            "collection": float(row["total_collection"]),
            "percentage": float(row["percentage"])
        })
    return sorted(result, key=lambda x: x["district"])


def get_mandals_for_district(district_name: str) -> List[str]:
    """Return list of mandals for a district."""
    df = get_df()
    match = df[df["district"].str.lower() == district_name.strip().lower()]
    mandals = sorted(match["mandal"].unique().tolist())
    return mandals


def get_filtered_data(
    district_name: Optional[str] = None,
    mandal_name: Optional[str] = None,
    df_source: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Filter live or uploaded dataset by district and mandal, computing summaries and mandal abstract."""
    df = _resolve_df(df_source)

    if district_name and district_name.lower() not in ("all", "all districts"):
        filtered = df[df["district"].str.lower() == district_name.strip().lower()].copy()
    else:
        filtered = df.copy()

    if mandal_name and mandal_name.lower() not in ("all", "all mandals"):
        target_m = mandal_name.strip().lower()
        m_series = filtered["mandal"].str.lower()
        exact = filtered[m_series == target_m]
        if not exact.empty:
            filtered = exact.copy()
        else:
            clean_target = target_m.replace("oo", "u").replace("ee", "i").rstrip("u").rstrip("y")
            fuzzy = filtered[m_series.str.replace("oo", "u").str.replace("ee", "i").str.rstrip("u").str.rstrip("y") == clean_target]
            if not fuzzy.empty:
                filtered = fuzzy.copy()
            else:
                prefix = filtered[m_series.str.startswith(target_m[:4])]
                if not prefix.empty:
                    filtered = prefix.copy()
                else:
                    filtered = filtered[m_series == target_m].copy()

    # Sort detailed GP records: first alphabetically by Mandal, then ascending by % Collection
    filtered = filtered.sort_values(
        by=["mandal", "calc_percentage", "demand_total"],
        ascending=[True, True, True]
    )

    tot_mandals = int(filtered["mandal"].nunique())
    tot_gps = int(len(filtered))
    tot_records = int(filtered["assessments"].sum())
    tot_demand = float(filtered["demand_total"].sum())
    tot_coll = float(filtered["collection_total"].sum())
    tot_bal = float(filtered["balance_total"].sum())

    overall_pct = round((tot_coll / tot_demand * 100), 1) if tot_demand > 0 else 0.0

    # Build Mandal Abstract table
    mandal_groups = filtered.groupby("mandal").agg(
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

    pct_series = (mandal_groups["collection_total"] / mandal_groups["demand_total"].replace(0, float("nan")) * 100).fillna(0.0)
    mandal_groups["percentage"] = pct_series.astype(float).round(1)

    # Sort abstract in ascending order based on % Collection
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


def generate_consolidated_excel(
    district_name: Optional[str] = None,
    df_source: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate dynamic multi-sheet Excel file from live or uploaded DCB data."""
    df = _resolve_df(df_source)
    if district_name and district_name.lower() not in ("all", "all districts"):
        df_sub = df[df["district"].str.lower() == district_name.strip().lower()].copy()
    else:
        df_sub = df.copy()

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
    from core.branding import apply_openpyxl_branding
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        mandal_summary.to_excel(writer, sheet_name="Mandal Abstract", index=False)
        detail_df.to_excel(writer, sheet_name="GP Wise DCB Detail", index=False)
        apply_openpyxl_branding(writer.book)

    return out.getvalue()


def generate_consolidated_csv(
    district_name: Optional[str] = None,
    df_source: Optional[pd.DataFrame] = None,
) -> bytes:
    """Generate dynamic CSV file from live or uploaded DCB data."""
    df = _resolve_df(df_source)
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

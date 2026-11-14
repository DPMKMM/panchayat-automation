"""
DSR State Format - Mandal-Wise Calculations & District Aggregation
=================================================================
Calculates 14-column official State Format metrics:
- Time buckets (6-9 AM, 9-10 AM, 10-11 AM, 11-12 Noon, After 12 Noon)
- Punctuality percentage before 9 AM
- Attended GP, Meeting/Training, Leave, Not Reported
- Mandal sorting, District Total row, District Percentage row
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any
import pandas as pd


@dataclass
class StateFormatReport:
    district_name: str
    report_date: date
    generated_at: datetime
    mandal_rows: list[dict[str, Any]]
    total_row: dict[str, Any]
    percentage_row: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "district_name": self.district_name,
            "report_date": self.report_date.isoformat(),
            "report_date_str": self.report_date.strftime("%d-%b-%Y"),
            "report_date_display": self.report_date.strftime("%d %B %Y"),
            "generated_at": self.generated_at.isoformat(),
            "generated_time_display": self.generated_at.strftime("%I:%M %p"),
            "mandal_rows": self.mandal_rows,
            "total_row": self.total_row,
            "percentage_row": self.percentage_row,
            "metadata": self.metadata,
        }


def compute_mandal_metrics(
    enriched_df: pd.DataFrame,
    district_name: str = "Khammam",
    report_date: date | None = None,
    generated_at: datetime | None = None,
) -> StateFormatReport:
    """
    Computes all 14-column mandal metrics, sorts mandals by % before 9 AM descending,
    and computes the official District Total and District Percentage rows.
    """
    gen_dt = generated_at or datetime.now()
    rep_date = report_date or gen_dt.date()

    if enriched_df.empty:
        empty_tot = {
            "sl_no": "Total",
            "s_no": "Total",
            "mandal_name": "Total",
            "tot_gps": 0,
            "total_gps": 0,
            "full_time": 0,
            "full_time_working_ps": 0,
            "b_6_9": 0,
            "reported_6_9_am": 0,
            "b_9_10": 0,
            "reported_9_10_am": 0,
            "b_10_11": 0,
            "reported_10_11_am": 0,
            "b_11_12": 0,
            "reported_11_12_noon": 0,
            "b_after_12": 0,
            "reported_after_12_noon": 0,
            "pct_before_9": 0.0,
            "pct_reported_before_9_am": 0.0,
            "attended_gp": 0,
            "total_attended_gp": 0,
            "mtg_trng": 0,
            "reported_meeting_training": 0,
            "leave": 0,
            "on_leave": 0,
            "not_reported": 0,
        }
        empty_pct = {
            "sl_no": "Percentage",
            "s_no": "Percentage",
            "mandal_name": "Percentage",
            "tot_gps": "",
            "total_gps": "",
            "full_time": "",
            "full_time_working_ps": "",
            "b_6_9": 0.0,
            "reported_6_9_am": 0.0,
            "b_9_10": 0.0,
            "reported_9_10_am": 0.0,
            "b_10_11": 0.0,
            "reported_10_11_am": 0.0,
            "b_11_12": 0.0,
            "reported_11_12_noon": 0.0,
            "b_after_12": 0.0,
            "reported_after_12_noon": 0.0,
            "pct_before_9": "",
            "pct_reported_before_9_am": "",
            "attended_gp": 0.0,
            "total_attended_gp": 0.0,
            "mtg_trng": 0.0,
            "reported_meeting_training": 0.0,
            "leave": 0.0,
            "on_leave": 0.0,
            "not_reported": 0.0,
        }
        return StateFormatReport(
            district_name=district_name,
            report_date=rep_date,
            generated_at=gen_dt,
            mandal_rows=[],
            total_row=empty_tot,
            percentage_row=empty_pct,
            metadata={"total_records": 0, "regular_count": 0},
        )

    # Derive district name from data if available
    if "district_name" in enriched_df.columns:
        cand_dist = enriched_df["district_name"].dropna().unique()
        if len(cand_dist) > 0 and cand_dist[0]:
            district_name = cand_dist[0]

    # Group by Mandal Name
    mandal_groups = enriched_df.groupby("mandal_name")

    raw_mandal_rows: list[dict[str, Any]] = []

    for mandal_name, grp in mandal_groups:
        if not mandal_name:
            continue
        tot_gps = len(grp)

        # Filter strictly for full-time working (Regular) PS
        reg_grp = grp[grp["is_regular"] == True].copy()
        full_time = len(reg_grp)

        # Time categories for full-time working PS who reported:
        # 6 AM - 9 AM: reporting time < 09:00:00 (marking window starts at 6 AM)
        # 9 AM - 10 AM: 09:00:00 <= reporting time < 10:00:00
        # 10 AM - 11 AM: 10:00:00 <= reporting time < 11:00:00
        # 11 AM - 12 Noon: 11:00:00 <= reporting time < 12:00:00
        # After 12 Noon: reporting time >= 12:00:00
        b_6_9 = 0
        b_9_10 = 0
        b_10_11 = 0
        b_11_12 = 0
        b_after_12 = 0

        # Status categories
        attended_gp = 0
        mtg_trng = 0
        leave = 0
        not_reported = 0

        for _, row in reg_grp.iterrows():
            status = row.get("attendance_status", "Not Reported")
            r_time = row.get("reporting_time")

            # Status classification
            if status == "Present":
                attended_gp += 1
            elif status == "Meeting":
                mtg_trng += 1
            elif status == "Leave":
                leave += 1
            else:
                not_reported += 1

            # Time classification (applies to anyone who reported in the app)
            has_valid_time = (
                r_time is not None
                and not pd.isna(r_time)
                and hasattr(r_time, "hour")
                and isinstance(getattr(r_time, "hour", None), int)
            )
            if status != "Not Reported" and has_valid_time:
                h = r_time.hour
                if h < 9:
                    b_6_9 += 1
                elif h == 9:
                    b_9_10 += 1
                elif h == 10:
                    b_10_11 += 1
                elif h == 11:
                    b_11_12 += 1
                else:
                    b_after_12 += 1
            elif status != "Not Reported" and not has_valid_time:
                # Reported status exists but timestamp unparsed; default to 6-9 AM window
                b_6_9 += 1

        # Percentage reported before 9 AM: (b_6_9 / full_time) * 100
        pct_before_9 = round((b_6_9 / full_time * 100.0), 2) if full_time > 0 else 0.0

        raw_mandal_rows.append({
            "mandal_name": mandal_name,
            "tot_gps": tot_gps,
            "total_gps": tot_gps,
            "full_time": full_time,
            "full_time_working_ps": full_time,
            "b_6_9": b_6_9,
            "reported_6_9_am": b_6_9,
            "b_9_10": b_9_10,
            "reported_9_10_am": b_9_10,
            "b_10_11": b_10_11,
            "reported_10_11_am": b_10_11,
            "b_11_12": b_11_12,
            "reported_11_12_noon": b_11_12,
            "b_after_12": b_after_12,
            "reported_after_12_noon": b_after_12,
            "pct_before_9": pct_before_9,
            "pct_reported_before_9_am": pct_before_9,
            "attended_gp": attended_gp,
            "total_attended_gp": attended_gp,
            "mtg_trng": mtg_trng,
            "reported_meeting_training": mtg_trng,
            "leave": leave,
            "on_leave": leave,
            "not_reported": not_reported,
        })

    # Sort mandals descending by % before 9 AM, then alphabetically by Mandal Name
    sorted_mandals = sorted(
        raw_mandal_rows,
        key=lambda r: (-r["pct_before_9"], r["mandal_name"]),
    )

    # Assign sequential Sl. No. (1..N) with both 'sl_no' and 's_no'
    for idx, r in enumerate(sorted_mandals, start=1):
        r["sl_no"] = idx
        r["s_no"] = idx

    # Calculate District Total Row
    tot_gps_sum = sum(r["tot_gps"] for r in sorted_mandals)
    full_time_sum = sum(r["full_time"] for r in sorted_mandals)
    b_6_9_sum = sum(r["b_6_9"] for r in sorted_mandals)
    b_9_10_sum = sum(r["b_9_10"] for r in sorted_mandals)
    b_10_11_sum = sum(r["b_10_11"] for r in sorted_mandals)
    b_11_12_sum = sum(r["b_11_12"] for r in sorted_mandals)
    b_after_12_sum = sum(r["b_after_12"] for r in sorted_mandals)
    attended_gp_sum = sum(r["attended_gp"] for r in sorted_mandals)
    mtg_trng_sum = sum(r["mtg_trng"] for r in sorted_mandals)
    leave_sum = sum(r["leave"] for r in sorted_mandals)
    not_reported_sum = sum(r["not_reported"] for r in sorted_mandals)

    dist_pct_before_9 = (
        round((b_6_9_sum / full_time_sum * 100.0), 2) if full_time_sum > 0 else 0.0
    )

    total_row = {
        "sl_no": "Total",
        "s_no": "Total",
        "mandal_name": "Total",
        "tot_gps": tot_gps_sum,
        "total_gps": tot_gps_sum,
        "full_time": full_time_sum,
        "full_time_working_ps": full_time_sum,
        "b_6_9": b_6_9_sum,
        "reported_6_9_am": b_6_9_sum,
        "b_9_10": b_9_10_sum,
        "reported_9_10_am": b_9_10_sum,
        "b_10_11": b_10_11_sum,
        "reported_10_11_am": b_10_11_sum,
        "b_11_12": b_11_12_sum,
        "reported_11_12_noon": b_11_12_sum,
        "b_after_12": b_after_12_sum,
        "reported_after_12_noon": b_after_12_sum,
        "pct_before_9": dist_pct_before_9,
        "pct_reported_before_9_am": dist_pct_before_9,
        "attended_gp": attended_gp_sum,
        "total_attended_gp": attended_gp_sum,
        "mtg_trng": mtg_trng_sum,
        "reported_meeting_training": mtg_trng_sum,
        "leave": leave_sum,
        "on_leave": leave_sum,
        "not_reported": not_reported_sum,
    }

    # Calculate District Percentage Row (denominator is full_time_sum)
    denom = float(full_time_sum) if full_time_sum > 0 else 1.0

    percentage_row = {
        "sl_no": "Percentage",
        "s_no": "Percentage",
        "mandal_name": "Percentage",
        "tot_gps": "",
        "total_gps": "",
        "full_time": "",
        "full_time_working_ps": "",
        "b_6_9": round((b_6_9_sum / denom * 100.0), 2),
        "reported_6_9_am": round((b_6_9_sum / denom * 100.0), 2),
        "b_9_10": round((b_9_10_sum / denom * 100.0), 2),
        "reported_9_10_am": round((b_9_10_sum / denom * 100.0), 2),
        "b_10_11": round((b_10_11_sum / denom * 100.0), 2),
        "reported_10_11_am": round((b_10_11_sum / denom * 100.0), 2),
        "b_11_12": round((b_11_12_sum / denom * 100.0), 2),
        "reported_11_12_noon": round((b_11_12_sum / denom * 100.0), 2),
        "b_after_12": round((b_after_12_sum / denom * 100.0), 2),
        "reported_after_12_noon": round((b_after_12_sum / denom * 100.0), 2),
        "pct_before_9": "",
        "pct_reported_before_9_am": "",
        "attended_gp": round((attended_gp_sum / denom * 100.0), 2),
        "total_attended_gp": round((attended_gp_sum / denom * 100.0), 2),
        "mtg_trng": round((mtg_trng_sum / denom * 100.0), 2),
        "reported_meeting_training": round((mtg_trng_sum / denom * 100.0), 2),
        "leave": round((leave_sum / denom * 100.0), 2),
        "on_leave": round((leave_sum / denom * 100.0), 2),
        "not_reported": round((not_reported_sum / denom * 100.0), 2),
    }

    metadata = {
        "total_records": len(enriched_df),
        "regular_count": full_time_sum,
        "incharge_count": len(enriched_df[enriched_df["is_regular"] == False]),
        "mandals_count": len(sorted_mandals),
    }

    return StateFormatReport(
        district_name=district_name,
        report_date=rep_date,
        generated_at=gen_dt,
        mandal_rows=sorted_mandals,
        total_row=total_row,
        percentage_row=percentage_row,
        metadata=metadata,
    )

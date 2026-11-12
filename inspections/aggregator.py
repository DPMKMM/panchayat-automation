"""Consolidates weekly GM-R 39.1 files into Mandal / Division / District abstracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from inspections.models import (
    InspectionAbstractRow,
    InspectionRecord,
    InspectionReport,
    compute_designation_target,
    get_designation_spec,
)
from inspections.parser import parse_inspection_file


def consolidate_inspection_files(
    week_files: list[dict[str, Any]],
    designation: str,
    weeks_selected: list[str] | None = None,
    district_name: str = "",
    known_units: list[str] | None = None,
    target_override: int | None = None,
) -> InspectionReport:
    """Consolidate 1+ weekly Excel downloads into a unified InspectionReport.

    Each entry in `week_files` is a dict containing:
      - `week_label`: str
      - `filename`: str (optional when empty/no-data week)
      - `raw_bytes`: bytes (empty bytes when portal returned no records for that week)
      - `status`: optional log status
    """
    spec = get_designation_spec(designation)
    canon_desig = spec["designation"]

    all_submitted: list[InspectionRecord] = []
    seen_record_keys: set[tuple[str, str, str, str, str, str]] = set()
    observed_units: dict[str, str] = {}
    observed_districts: set[str] = set()
    detected_weeks_all: list[str] = []
    seen_detected_weeks: set[str] = set()
    raw_total = 0
    excluded_total = 0
    week_logs: list[dict[str, Any]] = []

    if known_units:
        for u in known_units:
            clean = str(u or "").strip()
            if clean:
                observed_units.setdefault(clean.casefold(), clean)

    for wf in week_files:
        w_label = str(wf.get("week_label") or "").strip()
        fname = str(wf.get("filename") or "").strip()
        raw_bytes = wf.get("raw_bytes") or b""

        if not raw_bytes:
            week_logs.append({
                "week": w_label,
                "filename": fname,
                "status": wf.get("status") or "no_data",
                "raw_rows": 0,
                "submitted_rows": 0,
            })
            continue

        parsed = parse_inspection_file(
            filename=fname or f"{canon_desig}_{w_label}.xls",
            raw_bytes=raw_bytes,
            designation=canon_desig,
            week_label=w_label,
        )
        for dw in parsed.get("detected_weeks", []):
            if dw not in seen_detected_weeks:
                seen_detected_weeks.add(dw)
                detected_weeks_all.append(dw)

        for rec in parsed["submitted_records"]:
            rec_key = (
                rec.district_name.casefold(),
                rec.mandal_name.casefold(),
                rec.panchayat_id or rec.gp_name.casefold(),
                rec.week_label.casefold(),
                rec.inspection_date.casefold(),
                rec.attendance_datetime.casefold(),
            )
            if rec_key not in seen_record_keys:
                seen_record_keys.add(rec_key)
                all_submitted.append(rec)

        raw_total += parsed["raw_row_count"]
        excluded_total += parsed["excluded_non_submitted_count"]
        for u in parsed["observed_units"]:
            observed_units.setdefault(u.casefold(), u)
        observed_districts.update(parsed["district_names"])

        week_logs.append({
            "week": w_label or (", ".join(parsed.get("detected_weeks", [])) if parsed.get("detected_weeks") else fname),
            "filename": fname,
            "status": "downloaded",
            "raw_rows": parsed["raw_row_count"],
            "submitted_rows": parsed["submitted_row_count"],
            "excluded_rows": parsed["excluded_non_submitted_count"],
        })

    from inspections.models import extract_week_dates

    explicit_weeks = [str(w).strip() for w in (weeks_selected or []) if str(w).strip()]
    if explicit_weeks:
        effective_weeks = sorted(
            explicit_weeks,
            key=lambda w: (extract_week_dates(w)[0] or datetime.max.date(), w),
        )
    elif detected_weeks_all:
        effective_weeks = sorted(
            detected_weeks_all,
            key=lambda w: (extract_week_dates(w)[0] or datetime.max.date(), w),
        )
    else:
        effective_weeks = [
            str(wf.get("week_label") or wf.get("filename") or "Week").strip()
            for wf in week_files
        ] or ["Selected Period"]

    target_per_unit, target_rule_desc = compute_designation_target(
        canon_desig,
        week_labels=effective_weeks,
        week_count=len(effective_weeks),
        target_override=target_override,
    )

    resolved_district = (
        district_name.strip()
        or (sorted(observed_districts)[0] if observed_districts else "District")
    )

    # For DPO / CEO / Deputy CEO grouped at District level, ensure the district itself is present
    if spec["group_level"] == "district" and not observed_units and resolved_district:
        observed_units[resolved_district.casefold()] = resolved_district

    # Count ONLY Final Submit Status == 'Submitted' per grouping unit (Mandal / Division / District)
    counts_by_key: dict[str, int] = {}
    for rec in all_submitted:
        key = rec.unit_name.casefold()
        observed_units.setdefault(key, rec.unit_name)
        counts_by_key[key] = counts_by_key.get(key, 0) + 1

    # Build abstract rows sorted ascending by % Completed (lagging units first), then alphabetically
    unsorted_rows: list[tuple[float, str, int, int, int]] = []
    for key, display_unit in observed_units.items():
        completed = counts_by_key.get(key, 0)
        balance = max(0, target_per_unit - completed)
        pct = round((completed / target_per_unit) * 100.0, 2) if target_per_unit > 0 else 0.0
        unsorted_rows.append((pct, display_unit, target_per_unit, completed, balance))

    unsorted_rows.sort(key=lambda r: (r[0], r[1].casefold()))

    abstract_rows: list[InspectionAbstractRow] = [
        InspectionAbstractRow(
            serial=idx,
            unit_name=unit_name,
            target=tgt,
            completed=comp,
            balance=bal,
            pct_completed=pct,
        )
        for idx, (pct, unit_name, tgt, comp, bal) in enumerate(unsorted_rows, start=1)
    ]

    tot_target = sum(r.target for r in abstract_rows)
    tot_completed = sum(r.completed for r in abstract_rows)
    tot_balance = sum(r.balance for r in abstract_rows)
    tot_pct = round((tot_completed / tot_target) * 100.0, 2) if tot_target > 0 else 0.0

    return InspectionReport(
        designation=canon_desig,
        designation_title=spec["full_title"],
        group_level=spec["group_level"],
        group_label=spec["group_label"],
        district_name=resolved_district,
        from_week=effective_weeks[0],
        to_week=effective_weeks[-1],
        weeks_selected=effective_weeks,
        target_per_unit=target_per_unit,
        target_rule_desc=target_rule_desc,
        generated_at=datetime.now(),
        abstract_rows=abstract_rows,
        total_target=tot_target,
        total_completed=tot_completed,
        total_balance=tot_balance,
        total_pct_completed=tot_pct,
        submitted_records=all_submitted,
        raw_row_count=raw_total,
        submitted_row_count=len(all_submitted),
        excluded_non_submitted_count=excluded_total,
        week_download_logs=week_logs,
    )

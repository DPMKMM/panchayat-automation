"""Business logic & pipeline orchestration for MAS Consolidated Reporting (GM-R 5.24 + 5.23)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_reports_dir
from mas import automation as mas_automation
from mas.excel_generator import export_all_deliverables
from mas.models import (
    ALL_18_MODULES,
    build_module_options,
    make_unique_key,
    normalize_district_and_slug,
    resolve_excluded_set,
)

logger = logging.getLogger(__name__)


def get_available_mas_modules() -> List[Dict[str, Any]]:
    """Return UI filter options for all 18 MAS indicators."""
    return build_module_options()


def join_reports(
    gmr_524_data: dict,
    gmr_523_lookup: dict,
    excluded_modules: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Join GM-R 5.24 17-module records and GM-R 5.23 Births records across GPs."""
    if excluded_modules is None:
        excluded_modules = []

    normalized_excluded = resolve_excluded_set(excluded_modules)

    gmr_524_gps = gmr_524_data.get("gram_panchayats", [])
    births_lookup = gmr_523_lookup.get("lookup", gmr_523_lookup)

    joined_records: List[Dict[str, Any]] = []
    pending_action_list: List[Dict[str, Any]] = []
    unmatched_524 = 0

    for gp in gmr_524_gps:
        mandal = gp.get("Mandal", "")
        gp_name = gp.get("Gram_Panchayat", "")
        ukey = gp.get("Unique_Key") or make_unique_key(mandal, gp_name)

        birth_info = births_lookup.get(ukey)
        if not birth_info:
            unmatched_524 += 1
            birth_status = gp.get("Births_Data_Entered") or "Entered"
            bal_gps = 0 if birth_status == "Entered" else 1
            bal_births = 0
        else:
            birth_status = birth_info.get("births_data_entered", "Entered")
            bal_gps = birth_info.get("balance_gps_data_to_enter", 0)
            bal_births = birth_info.get("balance_to_be_entered", 0)

        merged_gp = {
            "Unique_Key": ukey,
            "Mandal": mandal,
            "GP_SNo": gp.get("GP_SNo"),
            "Gram_Panchayat": gp_name,
            "MAS_Nursery": gp.get("MAS_Nursery"),
            "MAS_Plantation": gp.get("MAS_Plantation"),
            "MAS_Vaikunta Dhamam": gp.get("MAS_Vaikunta Dhamam"),
            "MAS_Dump Yard": gp.get("MAS_Dump Yard"),
            "MAS_Water Supply": gp.get("MAS_Water Supply"),
            "MAS_GP Meeting": gp.get("MAS_GP Meeting"),
            "MAS_Gram Sabha": gp.get("MAS_Gram Sabha"),
            "MAS_Record Maintenance": gp.get("MAS_Record Maintenance"),
            "MAS_Approvals & Certificates": gp.get("MAS_Approvals & Certificates"),
            "MAS_Deaths": gp.get("MAS_Deaths"),
            "MAS_Receipts": gp.get("MAS_Receipts"),
            "MAS_Expenditure": gp.get("MAS_Expenditure"),
            "MAS_Cheque Details": gp.get("MAS_Cheque Details"),
            "MAS_Salary Details": gp.get("MAS_Salary Details"),
            "MAS_VWSC & EGS Balance": gp.get("MAS_VWSC & EGS Balance"),
            "MAS_MGNREGA Balance": gp.get("MAS_MGNREGA Balance"),
            "MAS_Electricity Payment": gp.get("MAS_Electricity Payment"),
            "Births_Data_Entered": birth_status,
            "Births_GP_Balance": bal_gps,
            "Births_Pending_Count": bal_births,
        }

        included_modules = [(label, col) for label, col in ALL_18_MODULES if label not in normalized_excluded]
        total_incl = len(included_modules) or 18
        pending_mods = [label for label, col in included_modules if merged_gp.get(col) not in ("Completed", "Entered")]

        completed_cnt = total_incl - len(pending_mods)
        comp_rate = round((completed_cnt / total_incl) * 100, 2)

        merged_gp["Activities_Completed"] = completed_cnt
        merged_gp["Total_Activities"] = total_incl
        merged_gp["Completion_Rate"] = comp_rate
        merged_gp["Compliance_Status"] = "Compliant" if not pending_mods else "Action Required"
        merged_gp["Pending_Modules_List"] = pending_mods
        joined_records.append(merged_gp)

        if pending_mods:
            pending_action_list.append(
                {
                    "S No": len(pending_action_list) + 1,
                    "Mandal": mandal,
                    "Gram_Panchayat": gp_name,
                    "Pending_Count": len(pending_mods),
                    "Pending_Modules": ", ".join(pending_mods),
                    "Completed_Count": completed_cnt,
                    "Total_Activities": total_incl,
                    "Completion_Rate": f"{comp_rate}%",
                    "Action_Required": "Immediate follow-up by MPO / PS",
                }
            )

    logger.info("Joined %d GP records cleanly (Unmatched in 5.23: %d).", len(joined_records), unmatched_524)
    return joined_records, pending_action_list, []


def build_full_18_module_abstract(
    joined_records: List[Dict[str, Any]],
    mandal_birth_bal: Optional[Dict[str, int]] = None,
    excluded_modules: Optional[List[str]] = None,
    scraped_mandal_abstract: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    """Compute per-mandal and district-total 18-module matrix honoring excluded modules."""
    if mandal_birth_bal is None:
        mandal_birth_bal = {}

    normalized_excluded = resolve_excluded_set(excluded_modules)
    included_labels = [label for label, _ in ALL_18_MODULES if label not in normalized_excluded]
    n_included = len(included_labels)
    if n_included == 0:
        n_included = len(ALL_18_MODULES)
        normalized_excluded = set()

    mandals_data: List[Dict[str, Any]] = []
    tot_district_updated = 0
    tot_district_fields = 0
    module_district_totals = {label: {"Entered": 0, "Not Entered": 0} for label, _ in ALL_18_MODULES}

    if scraped_mandal_abstract:
        for i, m in enumerate(scraped_mandal_abstract, 1):
            m_name = m["mandal_name"]
            n_gps = m["no_of_gps"]
            raw_mods = m.get("modules", {})
            m_updated = 0
            m_possible = 0

            m_dict: Dict[str, Any] = {
                "S No": i,
                "Mandal Name": m_name,
                "No of GPs": n_gps,
                "modules": {},
            }

            for label, _ in ALL_18_MODULES:
                is_excl = label in normalized_excluded
                mod_info = raw_mods.get(label)
                if not mod_info:
                    for k, v in raw_mods.items():
                        if (
                            k.lower() == label.lower()
                            or (label == "Recipts" and k.lower() == "receipts")
                            or (label == "Receipts" and k.lower() == "recipts")
                        ):
                            mod_info = v
                            break
                if not mod_info:
                    mod_info = {"entered": n_gps, "not_entered": 0, "pct": 100.0}

                ent = mod_info.get("entered", 0)
                not_ent = mod_info.get("not_entered", 0)
                mod_total = ent + not_ent
                pct = mod_info.get("pct") if "pct" in mod_info else (round((ent / mod_total * 100), 2) if mod_total > 0 else 100.0)

                if not is_excl:
                    m_updated += ent
                    m_possible += mod_total

                m_dict["modules"][label] = {
                    "Entered": ent,
                    "Not Entered": not_ent,
                    "% Entered": pct,
                    "formatted_compact": f"{not_ent} / {ent}",
                    "is_excluded": is_excl,
                }
                module_district_totals[label]["Entered"] += ent
                module_district_totals[label]["Not Entered"] += not_ent

            overall_pct = round((m_updated / m_possible * 100), 2) if m_possible > 0 else 100.0
            m_dict["Total Fields"] = m_possible
            m_dict["No of Updated"] = m_updated
            m_dict["Overall % Entered"] = overall_pct
            m_dict["Included Modules Count"] = n_included
            m_dict["Excluded Modules"] = sorted(list(normalized_excluded))

            tot_district_updated += m_updated
            tot_district_fields += m_possible
            mandals_data.append(m_dict)
    else:
        import pandas as pd

        df = pd.DataFrame(joined_records)
        mandal_groups = df.groupby("Mandal")
        for i, m_name in enumerate(sorted(df["Mandal"].unique()), 1):
            grp = mandal_groups.get_group(m_name)
            n_gps = len(grp)
            m_updated = 0
            m_possible = 0

            m_dict = {
                "S No": i,
                "Mandal Name": m_name,
                "No of GPs": n_gps,
                "modules": {},
            }

            for label, col in ALL_18_MODULES:
                is_excl = label in normalized_excluded
                if label == "Birth Details" and m_name in mandal_birth_bal:
                    not_ent = mandal_birth_bal.get(m_name, 0)
                    ent = n_gps - not_ent
                else:
                    ent = len(grp[grp[col].isin(["Completed", "Entered"])])
                    not_ent = n_gps - ent

                mod_total = ent + not_ent
                pct = round((ent / mod_total * 100), 2) if mod_total > 0 else 100.0

                if not is_excl:
                    m_updated += ent
                    m_possible += mod_total

                m_dict["modules"][label] = {
                    "Entered": ent,
                    "Not Entered": not_ent,
                    "% Entered": pct,
                    "formatted_compact": f"{not_ent} / {ent}",
                    "is_excluded": is_excl,
                }
                module_district_totals[label]["Entered"] += ent
                module_district_totals[label]["Not Entered"] += not_ent

            overall_pct = round((m_updated / m_possible * 100), 2) if m_possible > 0 else 100.0
            m_dict["Total Fields"] = m_possible
            m_dict["No of Updated"] = m_updated
            m_dict["Overall % Entered"] = overall_pct
            m_dict["Included Modules Count"] = n_included
            m_dict["Excluded Modules"] = sorted(list(normalized_excluded))

            tot_district_updated += m_updated
            tot_district_fields += m_possible
            mandals_data.append(m_dict)

    district_overall_pct = round((tot_district_updated / tot_district_fields * 100), 2) if tot_district_fields > 0 else 100.0
    total_row = {
        "S No": "Total",
        "Mandal Name": "District Total",
        "No of GPs": sum(m["No of GPs"] for m in mandals_data) or len(joined_records),
        "Total Fields": tot_district_fields,
        "No of Updated": tot_district_updated,
        "Overall % Entered": district_overall_pct,
        "included_modules_count": n_included,
        "excluded_modules": sorted(list(normalized_excluded)),
        "modules": {},
    }

    for label, _ in ALL_18_MODULES:
        ent = module_district_totals[label]["Entered"]
        not_ent = module_district_totals[label]["Not Entered"]
        mod_tot = ent + not_ent
        pct = round((ent / mod_tot * 100), 2) if mod_tot > 0 else 100.0
        total_row["modules"][label] = {
            "Entered": ent,
            "Not Entered": not_ent,
            "% Entered": pct,
            "formatted_compact": f"{not_ent} / {ent}",
            "is_excluded": label in normalized_excluded,
        }

    return mandals_data, total_row, sorted(list(normalized_excluded))


def _resolve_output_dir(session_id: Optional[str] = None, output_dir: Optional[Path] = None) -> Path:
    if output_dir is not None:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    base = get_reports_dir()
    if session_id:
        safe_sid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(session_id)).strip("_")[:48] or "default"
        p = base / f"mas_{safe_sid}"
        p.mkdir(parents=True, exist_ok=True)
        return p
    base.mkdir(parents=True, exist_ok=True)
    return base


def generate_consolidated_report(
    excluded_modules: Optional[List[str]] = None,
    month: str = "July",
    year: int = 2026,
    page=None,
    strict_live: bool = False,
    district_name: str = "Khammam",
    report_type: str = "abstract_and_gp",
    session_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """End-to-end MAS report consolidation and deliverable export."""
    if excluded_modules is None:
        excluded_modules = []

    clean_dist, _ = normalize_district_and_slug(district_name)
    include_gp_data = str(report_type or "abstract_and_gp").strip().lower() != "abstract_only"

    live_data = mas_automation.get_or_create_monthly_data(
        month=month,
        year=year,
        page=page,
        excluded_modules=excluded_modules,
        force_refresh=strict_live,
        strict_live=strict_live,
        district_name=clean_dist,
        include_gp_data=include_gp_data,
    )

    scraped_abs = live_data.get("mandal_abstract")
    all_gps = live_data.get("all_gps", [])
    pending_action_list = live_data.get("pending_action_list", [])
    births_map = live_data.get("births_map", {})
    mandal_birth_bal = {k: int(v.get("balance_gps", 0)) for k, v in births_map.items()}

    if not include_gp_data:
        pending_action_list = []

    mandals_abstract, total_row, norm_excluded = build_full_18_module_abstract(
        all_gps,
        mandal_birth_bal=mandal_birth_bal,
        excluded_modules=excluded_modules,
        scraped_mandal_abstract=scraped_abs,
    )

    pending_mandals_count = sum(
        1
        for m in mandals_abstract
        if any(
            (not mod_info.get("is_excluded", False)) and int(mod_info.get("Not Entered", 0) or 0) > 0
            for mod_info in m.get("modules", {}).values()
        )
    )

    target_dir = _resolve_output_dir(session_id=session_id, output_dir=output_dir)
    files = export_all_deliverables(
        mandals_abstract=mandals_abstract,
        total_row=total_row,
        joined_records=all_gps,
        pending_action_list=pending_action_list,
        excluded_modules=norm_excluded,
        output_dir=target_dir,
        month=month,
        year=year,
        district_name=clean_dist,
        include_gp_data=include_gp_data,
    )

    return {
        "success": True,
        "status": "success",
        "district": clean_dist,
        "month": month.capitalize(),
        "year": year,
        "report_type": "abstract_and_gp" if include_gp_data else "abstract_only",
        "include_gp_data": include_gp_data,
        "data_source": live_data.get("data_source", "live"),
        "total_gps": len(all_gps) or int(total_row.get("No of GPs") or 0),
        "total_mandals": len(mandals_abstract),
        "pending_mandals_count": pending_mandals_count,
        "pending_gps_count": len(pending_action_list),
        "included_modules_count": total_row["included_modules_count"],
        "total_modules": len(ALL_18_MODULES),
        "excluded_modules": norm_excluded,
        "district_overall_pct": total_row["Overall % Entered"],
        "total_updated_fields": total_row["No of Updated"],
        "total_possible_fields": total_row["Total Fields"],
        "mandals": mandals_abstract,
        "total_row": total_row,
        "pending_action_list": pending_action_list,
        "files": files,
    }


def run_pipeline(
    *,
    bot: Any = None,
    session: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    month: str = "July",
    year: int = 2026,
    financial_year: Optional[str] = None,
    excluded_modules: Optional[List[str]] = None,
    report_type: str = "abstract_and_gp",
    district_name: Optional[str] = None,
    officer_id: Optional[str] = None,
    strict_live: bool = True,
) -> Dict[str, Any]:
    """Run MAS pipeline directly on the shared authenticated ``bot.page`` without opening a second browser."""
    eff_year = year
    if financial_year and str(financial_year).strip().isdigit():
        eff_year = int(str(financial_year).strip())

    sess = session or {}
    eff_district = (
        district_name
        or sess.get("district_name")
        or "Khammam"
    ).strip() or "Khammam"
    eff_officer = (
        officer_id
        or sess.get("user_id")
        or "Officer"
    ).strip() or "Officer"
    bot_page = getattr(bot, "page", None) if bot is not None else None

    result = generate_consolidated_report(
        excluded_modules=excluded_modules,
        month=month,
        year=eff_year,
        page=bot_page,
        strict_live=strict_live,
        district_name=eff_district,
        report_type=report_type,
        session_id=session_id,
    )

    if isinstance(session, dict) and isinstance(result.get("files"), dict):
        session["mas_files"] = dict(result["files"])

    result["officer"] = eff_officer
    return result

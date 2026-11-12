"""FastAPI Router for House Tax Demand Collection Balance (DCB) endpoints."""

from __future__ import annotations

from typing import Any, List
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from core.branding import apply_subpage_console_branding
from core.dependencies import enforce_department_api_access, extract_epts_session_id, resolve_platform_scope
from dcb.html import TAX_PAGE_HTML
from dcb import service as tax_service
from dcb import pdf_generator as dcb_pdf_generator
from dcb import powerbi_pdf_generator


def _enforce_dcb_scope_access(request: Request) -> None:
    """Enforce centralized Stage-1 + Stage-2 auth when accessed from Console scope."""
    if resolve_platform_scope(request) == "console":
        enforce_department_api_access(request)


def _resolve_mandal(request: Request, mandal: str = "all") -> tuple[str, bool, str]:
    sid = extract_epts_session_id(request)
    user_level = "district"
    mandal_name = ""
    try:
        from dsr.service import get_or_create_session
        sess = get_or_create_session(sid)
        user_level = sess.get("user_level", "district")
        mandal_name = sess.get("mandal_name", "").strip()
    except Exception:
        pass

    is_mandal = (user_level == "mandal") or bool(mandal_name)
    if is_mandal and mandal_name and (not mandal or mandal.lower() in ("all", "all mandals")):
        return mandal_name, True, user_level
    return mandal, is_mandal, user_level

router = APIRouter(tags=["Demand Collection Balance (DCB)"])


@router.get("/reports/tax-dcb", response_class=HTMLResponse, include_in_schema=False)
def tax_dcb_page(request: Request, district: str = "Khammam") -> HTMLResponse:
    """Renders the interactive House Tax DCB Web Dashboard."""
    return HTMLResponse(apply_subpage_console_branding(TAX_PAGE_HTML, request))


@router.get("/api/tax/districts")
def get_tax_districts(request: Request) -> List[dict[str, Any]]:
    """Returns all districts in Telangana scraped live with GP counts."""
    _enforce_dcb_scope_access(request)
    return tax_service.get_districts_list()


@router.get("/api/tax/mandals")
def get_tax_mandals(request: Request, district: str = "Khammam") -> List[str]:
    """Returns list of mandals for a specific district."""
    _enforce_dcb_scope_access(request)
    return tax_service.get_mandals_for_district(district)


@router.get("/api/tax/data")
def get_tax_data(request: Request, district: str = "Khammam", mandal: str = "all") -> dict[str, Any]:
    """Returns summary statistics, mandal abstract table, and GP records."""
    _enforce_dcb_scope_access(request)
    target_mandal, is_mandal, u_level = _resolve_mandal(request, mandal)
    res = tax_service.get_filtered_data(district, target_mandal)
    res["is_mandal_level"] = is_mandal
    res["user_level"] = u_level
    if is_mandal:
        res["mandal_name"] = target_mandal
        res["mandal_abstract"] = []  # Suppress abstract for mandal-level
        res["mandal_rows"] = []  # Multi-mandal comparison table suppressed for mandal-level officers
    return res


@router.get("/api/tax/report.pdf")
def view_tax_pdf(request: Request, district: str = "Khammam", mandal: str = "all") -> Response:
    """Generates and previews the official landscape DCB PDF report inline."""
    _enforce_dcb_scope_access(request)
    target_mandal, _, _ = _resolve_mandal(request, mandal)
    filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, target_mandal)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/api/tax/download-pdf")
def download_tax_pdf(request: Request, district: str = "Khammam", mandal: str = "all") -> Response:
    """Downloads the official landscape DCB PDF report."""
    _enforce_dcb_scope_access(request)
    target_mandal, _, _ = _resolve_mandal(request, mandal)
    filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, target_mandal)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/tax/powerbi-report.pdf")
def download_powerbi_pdf(request: Request, district: str = "Khammam", mandal: str = "all", force: bool = True) -> Response:
    """Generates and downloads the executive Power BI Visual PDF report."""
    _enforce_dcb_scope_access(request)
    target_mandal, _, _ = _resolve_mandal(request, mandal)
    filename, pdf_bytes = powerbi_pdf_generator.get_or_generate_powerbi_pdf(district, target_mandal, force_regenerate=force)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/tax/download")
def download_tax_data(request: Request, district: str = "Khammam", format: str = "xlsx") -> Response:
    """Dynamically exports live scraped DCB dataset as Excel or CSV."""
    _enforce_dcb_scope_access(request)
    safe_dist = district.strip().replace(" ", "_")
    if format.lower() == "csv":
        csv_bytes = tax_service.generate_consolidated_csv(district)
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_dist}_House_Tax_DCB.csv"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    excel_bytes = tax_service.generate_consolidated_excel(district)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_dist}_House_Tax_DCB.xlsx"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/api/tax/refresh")
def refresh_tax_data(request: Request) -> dict[str, Any]:
    """Force re-scrapes live fresh DCB data directly from the Telangana epanchayat portal."""
    _enforce_dcb_scope_access(request)
    df = tax_service.get_df(force_reload=True)
    return {"status": "ok", "total_gps": len(df), "message": "Fresh DCB data successfully scraped from live portal."}

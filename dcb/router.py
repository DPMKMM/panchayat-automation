"""FastAPI Router for House Tax Demand Collection Balance (DCB) endpoints."""

from __future__ import annotations

from typing import Any, List
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

from dcb.html import TAX_PAGE_HTML
from dcb import service as tax_service
from dcb import pdf_generator as dcb_pdf_generator
from dcb import powerbi_pdf_generator

router = APIRouter(tags=["Demand Collection Balance (DCB)"])


@router.get("/reports/tax-dcb", response_class=HTMLResponse, include_in_schema=False)
def tax_dcb_page(district: str = "Khammam") -> HTMLResponse:
    """Renders the interactive House Tax DCB Web Dashboard."""
    return HTMLResponse(TAX_PAGE_HTML)


@router.get("/api/tax/districts")
def get_tax_districts() -> List[dict[str, Any]]:
    """Returns all districts in Telangana scraped live with GP counts."""
    return tax_service.get_districts_list()


@router.get("/api/tax/mandals")
def get_tax_mandals(district: str = "Khammam") -> List[str]:
    """Returns list of mandals for a specific district."""
    return tax_service.get_mandals_for_district(district)


@router.get("/api/tax/data")
def get_tax_data(district: str = "Khammam", mandal: str = "all") -> dict[str, Any]:
    """Returns summary statistics, mandal abstract table, and GP records."""
    return tax_service.get_filtered_data(district, mandal)


@router.get("/api/tax/report.pdf")
def view_tax_pdf(district: str = "Khammam", mandal: str = "all") -> Response:
    """Generates and previews the official landscape DCB PDF report inline."""
    filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, mandal)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/api/tax/download-pdf")
def download_tax_pdf(district: str = "Khammam", mandal: str = "all") -> Response:
    """Downloads the official landscape DCB PDF report."""
    filename, pdf_bytes = dcb_pdf_generator.get_or_generate_dcb_pdf(district, mandal)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/tax/powerbi-report.pdf")
def download_powerbi_pdf(district: str = "Khammam", mandal: str = "all", force: bool = True) -> Response:
    """Generates and downloads the executive Power BI Visual PDF report."""
    filename, pdf_bytes = powerbi_pdf_generator.get_or_generate_powerbi_pdf(district, mandal, force_regenerate=force)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/api/tax/download")
def download_tax_data(district: str = "Khammam", format: str = "xlsx") -> Response:
    """Dynamically exports live scraped DCB dataset as Excel or CSV."""
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
def refresh_tax_data() -> dict[str, Any]:
    """Force re-scrapes live fresh DCB data directly from the Telangana epanchayat portal."""
    df = tax_service.get_df(force_reload=True)
    return {"status": "ok", "total_gps": len(df), "message": "Fresh DCB data successfully scraped from live portal."}

from fastapi.testclient import TestClient
from pypdf import PdfReader
import io
import app

client = TestClient(app.app)


def test_tax_page_route():
    resp = client.get("/reports/tax-dcb?district=Adilabad")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Gram Panchayat Wise DCB Status" in resp.text


def test_tax_districts_api():
    resp = client.get("/api/tax/districts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 31
    dist_names = [d["district"] for d in data]
    assert "Adilabad" in dist_names
    assert "Adilabad" in dist_names


def test_tax_mandals_api():
    resp = client.get("/api/tax/mandals?district=Adilabad")
    assert resp.status_code == 200
    mandals = resp.json()
    assert isinstance(mandals, list)
    assert len(mandals) == 20
    assert "Bonakal" in mandals
    assert "Chinthakani" in mandals


def test_tax_data_api():
    resp = client.get("/api/tax/data?district=Adilabad&mandal=all")
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert body["summary"]["district"] == "Adilabad"
    assert body["summary"]["total_gps"] == 571
    assert body["summary"]["total_mandals"] == 20
    assert len(body["records"]) == 571
    assert len(body["mandal_abstract"]) == 20


def test_tax_pdf_generation_endpoint():
    resp = client.get("/api/tax/report.pdf?district=Adilabad")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 50_000

    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 27


def test_tax_single_mandal_pdf_endpoint():
    resp = client.get("/api/tax/report.pdf?district=Adilabad&mandal=Bonakal")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1


def test_tax_excel_download_endpoint():
    resp = client.get("/api/tax/download?district=Adilabad&format=xlsx")
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert len(resp.content) > 10_000


def test_tax_csv_download_endpoint():
    resp = client.get("/api/tax/download?district=Adilabad&format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.splitlines()
    assert len(lines) > 500


def test_power_bi_visual_report_html_elements():
    resp = client.get("/reports/tax-dcb?district=Adilabad")
    assert resp.status_code == 200
    html = resp.text
    # Verify Power BI elements
    assert "pbi-district-view" in html
    assert "pbi-mandal-view" in html
    assert "pbi-dist-table" in html
    assert "pbi-mandal-table" in html
    assert "chart-dist-clustered" in html
    assert "chart-dist-ranking" in html
    assert "chart-dist-donut" in html
    assert "svg-dist-gauge" in html
    assert "chart-mandal-ranking" in html
    assert "chart-mandal-dcb" in html
    assert "svg-mandal-gauge" in html
    assert "downloadPowerBiPdf" in html
    assert "Download Power BI Report (PDF)" in html
    assert "pbi-mandal-slicer-select" in html


def test_power_bi_pdf_endpoint_single_mandal():
    resp = client.get("/api/tax/powerbi-report.pdf?district=Adilabad&mandal=Bonakal")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1


def test_power_bi_pdf_endpoint_district_all_mandals():
    resp = client.get("/api/tax/powerbi-report.pdf?district=Adilabad&mandal=all")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 21

"""End-to-end tests for integrated Excel & Data Studio and All-in-One PDF Studio tools."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import openpyxl
import pymupdf
from fastapi.testclient import TestClient
from PIL import Image

from app import app
from core.branding import PLATFORM_NAME, TAGLINE

client = TestClient(app)


def _make_pdf_bytes(text: str, num_pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for idx in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{text} - Page {idx + 1}", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (240, 160), color=(24, 118, 79))
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_portal_health_and_tools_cards_wired():
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert "TOOLS" in health["modules"]

    html = client.get("/").text
    assert 'id="card-choose-tools"' in html
    assert 'id="tools-modules-section"' in html
    assert 'id="card-tool-excel"' in html
    assert 'id="card-tool-pdf"' in html
    assert 'href="/tools/excel"' in html
    assert 'href="/tools/pdf"' in html
    assert 'id="card-tools-under-prep"' not in html


def test_excel_studio_page_and_catalog():
    resp = client.get("/tools/excel")
    assert resp.status_code == 200
    html = resp.text
    assert PLATFORM_NAME in html
    assert TAGLINE in html
    assert "<footer" in html
    assert 'id="mostUsedSection"' in html
    assert 'id="mostUsedGrid"' in html
    assert "/api/tools/excel/execute" in html
    assert "/api/tools/excel/viewer/load" in html
    assert "/api/tools/excel/viewer/save" in html
    assert "alert(" not in html
    assert "Panchayat-Automation" not in html

    health_resp = client.get("/api/tools/excel/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["tools_count"] >= 60

    cat_resp = client.get("/api/tools/excel/catalog")
    assert cat_resp.status_code == 200
    payload = cat_resp.json()
    assert len(payload["categories"]) >= 9
    assert payload["categories"][0]["id"] == "most_used"
    assert payload["categories"][0]["name"] == "Most Used"
    assert len(payload["tools"]) >= 60
    by_id = {t["id"]: t for t in payload["tools"]}
    for tool_id, expected_cat in [("xls_to_xlsx", "formats"), ("pdf_to_excel", "to_excel"), ("image_to_excel", "to_excel")]:
        assert by_id[tool_id]["category"] == expected_cat
        assert by_id[tool_id]["most_used"] is True


def test_excel_execute_csv_html_viewer_and_download_guard():
    # 1. CSV -> Excel conversion + Download
    csv_data = b"Mandal,GPs,Pct\nBonakal,22,100%\nChinthakani,26,100%\n"
    exec_resp = client.post(
        "/api/tools/excel/execute",
        data={"tool_id": "csv_to_excel"},
        files={"files": ("mandals.csv", csv_data, "text/csv")},
    )
    assert exec_resp.status_code == 200, exec_resp.text
    res_json = exec_resp.json()
    assert res_json["success"] is True
    assert res_json["download_url"].startswith("/api/tools/excel/download/")

    dl = client.get(res_json["download_url"])
    assert dl.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(dl.content))
    ws = wb.active
    assert ws.cell(1, 1).value == "Mandal"
    assert ws.cell(2, 1).value == "Bonakal"

    # 2. HTML-disguised .xls -> .xlsx conversion
    html_xls = b"<html><body><table><tr><th>GP</th><th>Count</th></tr><tr><td>Rayannapet</td><td>15</td></tr></table></body></html>"
    html_resp = client.post(
        "/api/tools/excel/execute",
        data={"tool_id": "html_to_excel"},
        files={"files": ("report.xls", html_xls, "application/vnd.ms-excel")},
    )
    assert html_resp.status_code == 200, html_resp.text
    html_dl = client.get(html_resp.json()["download_url"])
    assert html_dl.status_code == 200
    wb2 = openpyxl.load_workbook(io.BytesIO(html_dl.content))
    assert wb2.active.max_row >= 2

    # 3. Interactive Viewer Load + Edit + Save + Traversal guard
    load_resp = client.post(
        "/api/tools/excel/viewer/load",
        files={"file": ("mandals.xlsx", dl.content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert load_resp.status_code == 200, load_resp.text
    grid = load_resp.json()
    assert grid["session_id"]
    grid["sheets"][0]["rows"][1][0] = "Bonakal Updated"

    save_resp = client.post("/api/tools/excel/viewer/save", json=grid)
    assert save_resp.status_code == 200, save_resp.text
    edited_dl = client.get(save_resp.json()["download_url"])
    assert edited_dl.status_code == 200
    wb3 = openpyxl.load_workbook(io.BytesIO(edited_dl.content))
    assert wb3.active.cell(2, 1).value == "Bonakal Updated"

    bad_dl = client.get("/api/tools/excel/download/../app.py")
    assert bad_dl.status_code in (400, 404)


def test_pdf_studio_page_and_all_core_endpoints():
    page_resp = client.get("/tools/pdf")
    assert page_resp.status_code == 200
    html = page_resp.text
    assert PLATFORM_NAME in html
    assert TAGLINE in html
    assert "<footer" in html
    assert "/api/tools/pdf/merge" in html
    assert "/api/tools/pdf/pdf-to-word" in html
    assert "alert(" not in html
    assert "Panchayat-Automation" not in html

    health_resp = client.get("/api/tools/pdf/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["tools_count"] == 14

    pdf_a = _make_pdf_bytes("First Document")
    pdf_b = _make_pdf_bytes("Second Document")

    # Merge -> 2 pages
    merge_resp = client.post(
        "/api/tools/pdf/merge",
        files=[
            ("files", ("a.pdf", pdf_a, "application/pdf")),
            ("files", ("b.pdf", pdf_b, "application/pdf")),
        ],
    )
    assert merge_resp.status_code == 200, merge_resp.text
    merged_doc = pymupdf.open(stream=merge_resp.content, filetype="pdf")
    assert len(merged_doc) == 2
    merged_doc.close()

    # Split page 1 cleanly
    split_resp = client.post(
        "/api/tools/pdf/split",
        files={"file": ("merged.pdf", merge_resp.content, "application/pdf")},
        data={"split_type": "range", "range_mode": "custom", "ranges_json": '[{"from": 1, "to": 1}]', "merge_ranges": "true"},
    )
    assert split_resp.status_code == 200, split_resp.text
    split_doc = pymupdf.open(stream=split_resp.content, filetype="pdf")
    assert len(split_doc) == 1
    assert "First Document" in split_doc[0].get_text()
    split_doc.close()

    # Rotate 90 degrees
    rot_resp = client.post(
        "/api/tools/pdf/rotate",
        files={"file": ("a.pdf", pdf_a, "application/pdf")},
        data={"angle": "90"},
    )
    assert rot_resp.status_code == 200
    rot_doc = pymupdf.open(stream=rot_resp.content, filetype="pdf")
    assert rot_doc[0].rotation == 90
    rot_doc.close()

    # Organize: delete page 1 so Second Document becomes page 1
    org_resp = client.post(
        "/api/tools/pdf/organize",
        files={"file": ("merged.pdf", merge_resp.content, "application/pdf")},
        data={"delete_pages": "1"},
    )
    assert org_resp.status_code == 200
    org_doc = pymupdf.open(stream=org_resp.content, filetype="pdf")
    assert len(org_doc) == 1
    assert "Second Document" in org_doc[0].get_text()
    org_doc.close()

    # Compress PDF
    comp_resp = client.post(
        "/api/tools/pdf/compress",
        files={"file": ("a.pdf", pdf_a, "application/pdf")},
        data={"compress_mode": "ratio", "ratio": "50"},
    )
    assert comp_resp.status_code == 200
    assert comp_resp.content.startswith(b"%PDF")

    # PDF to Markdown
    md_resp = client.post(
        "/api/tools/pdf/pdf-to-markdown",
        files={"file": ("a.pdf", pdf_a, "application/pdf")},
    )
    assert md_resp.status_code == 200
    assert "First Document" in md_resp.content.decode("utf-8", errors="ignore")

    # Images to PDF
    img_resp = client.post(
        "/api/tools/pdf/images-to-pdf",
        files=[("files", ("sample.png", _make_png_bytes(), "image/png"))],
    )
    assert img_resp.status_code == 200
    img_doc = pymupdf.open(stream=img_resp.content, filetype="pdf")
    assert len(img_doc) == 1
    img_doc.close()

    # PDF to Images (2-page PDF -> ZIP)
    p2i_resp = client.post(
        "/api/tools/pdf/pdf-to-images",
        files={"file": ("merged.pdf", merge_resp.content, "application/pdf")},
        data={"dpi": "72"},
    )
    assert p2i_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(p2i_resp.content)) as zf:
        assert any(name.endswith(".png") for name in zf.namelist())

    # Protect + Unlock round-trip
    prot_resp = client.post(
        "/api/tools/pdf/protect",
        files={"file": ("a.pdf", pdf_a, "application/pdf")},
        data={"password": "epanchayat123"},
    )
    assert prot_resp.status_code == 200
    wrong_unlock = client.post(
        "/api/tools/pdf/unlock",
        files={"file": ("prot.pdf", prot_resp.content, "application/pdf")},
        data={"password": "wrong"},
    )
    assert wrong_unlock.status_code == 401
    good_unlock = client.post(
        "/api/tools/pdf/unlock",
        files={"file": ("prot.pdf", prot_resp.content, "application/pdf")},
        data={"password": "epanchayat123"},
    )
    assert good_unlock.status_code == 200
    un_doc = pymupdf.open(stream=good_unlock.content, filetype="pdf")
    assert "First Document" in un_doc[0].get_text()
    un_doc.close()

    # PDF to Word
    docx_resp = client.post(
        "/api/tools/pdf/pdf-to-word",
        files={"file": ("a.pdf", pdf_a, "application/pdf")},
    )
    assert docx_resp.status_code == 200
    assert docx_resp.content[:2] == b"PK"


def test_dockerfile_and_requirements_include_tools():
    root = Path(__file__).resolve().parent.parent
    dockerfile_text = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=appuser:appuser tools/ ./tools/" in dockerfile_text

    req_text = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    for pkg in ("pymupdf4llm", "pdf2docx", "rapidocr-onnxruntime", "beautifulsoup4", "python-docx", "pyxlsb", "odfpy"):
        assert pkg in req_text

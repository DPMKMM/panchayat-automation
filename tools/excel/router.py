"""
Excel & Data Studio Router for e-Panchayat Automation Tools Module.
Provides 70+ spreadsheet conversion, cleaning, reshaping, financial, and interactive editor tools.
"""

import os
import io
import re
import sys
import json
import uuid
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from core.branding import PLATFORM_NAME, render_canonical_footer_html
from tools.excel.converter_web import convert_file_universal, LibreOfficeEngine, normalize_to_xlsx
import tools.excel.engine.converters_to_excel as to_excel
import tools.excel.engine.converters_from_excel as from_excel
import tools.excel.engine.formats_converter as formats_conv
import tools.excel.engine.bank_quickbooks as bank_qb
import tools.excel.engine.data_tools as data_tools
import tools.excel.engine.viewer_engine as viewer_engine

APP_TITLE = "Excel & Data Studio"
NAVBAR_TITLE = PLATFORM_NAME
STORAGE_DIR = Path(tempfile.gettempdir()) / "epanchayat_xls_tools"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(tags=["tools-excel"])


def _safe_name(raw: Optional[str], fallback: str = "file") -> str:
    cleaned = Path(str(raw or fallback)).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9_.() -]", "_", cleaned).lstrip(".")
    return cleaned if cleaned and cleaned not in {".", ".."} else fallback

# Tool Definitions matching the user specifications (Most Used first, then 8 categories)
CATEGORIES = [
    {"id": "most_used", "name": "Most Used", "icon": "⭐"},
    {"id": "all", "name": "All Tools", "icon": "⚡"},
    {"id": "to_excel", "name": "To Excel", "icon": "📥"},
    {"id": "from_excel", "name": "From Excel", "icon": "📤"},
    {"id": "formats", "name": "Formats & CSV", "icon": "🔄"},
    {"id": "banking", "name": "Bank & QuickBooks", "icon": "🏦"},
    {"id": "open_edit", "name": "Open & Edit", "icon": "✏️"},
    {"id": "combine_compare", "name": "Combine & Compare", "icon": "🧩"},
    {"id": "clean_up", "name": "Clean Up", "icon": "🧹"},
    {"id": "sort_reshape", "name": "Sort & Reshape", "icon": "📐"},
]

TOOLS = [
    # To Excel
    {"id": "word_to_excel", "name": "Word to Excel", "category": "to_excel", "desc": "Extract tables and text from Word (.docx) into .xlsx", "accept": ".docx"},
    {"id": "pdf_to_excel", "name": "PDF to Excel", "category": "to_excel", "most_used": True, "most_used_rank": 2, "desc": "Extract tables and text from .pdf into .xlsx", "accept": ".pdf"},
    {"id": "xml_to_excel", "name": "XML to Excel", "category": "to_excel", "desc": "Parse structured XML data into .xlsx rows", "accept": ".xml"},
    {"id": "txt_to_excel", "name": "TXT to Excel", "category": "to_excel", "desc": "Convert delimited or text files to .xlsx", "accept": ".txt"},
    {"id": "json_to_excel", "name": "JSON to Excel", "category": "to_excel", "desc": "Flatten JSON arrays or objects into .xlsx", "accept": ".json"},
    {"id": "csv_to_excel", "name": "CSV to Excel", "category": "to_excel", "desc": "Convert CSV files into formatted .xlsx", "accept": ".csv"},
    {"id": "image_to_excel", "name": "Image to Excel", "category": "to_excel", "most_used": True, "most_used_rank": 3, "desc": "Embed or extract image table to .xlsx", "accept": ".png,.jpg,.jpeg,.webp"},
    {"id": "html_to_excel", "name": "HTML to Excel", "category": "to_excel", "desc": "Convert HTML tables to formatted .xlsx", "accept": ".html,.htm"},
    {"id": "markdown_to_excel", "name": "Markdown to Excel", "category": "to_excel", "desc": "Convert Markdown tables to .xlsx", "accept": ".md,.markdown"},
    {"id": "sql_to_excel", "name": "SQL to Excel", "category": "to_excel", "desc": "Convert SQL INSERT statements to .xlsx", "accept": ".sql"},
    {"id": "yaml_to_excel", "name": "YAML to Excel", "category": "to_excel", "desc": "Convert YAML hierarchy to .xlsx", "accept": ".yaml,.yml"},
    {"id": "tsv_to_excel", "name": "TSV to Excel", "category": "to_excel", "desc": "Convert tab-separated files to .xlsx", "accept": ".tsv"},

    # From Excel
    {"id": "excel_to_word", "name": "Excel to Word", "category": "from_excel", "desc": "Export Excel sheets to Word table (.docx)", "accept": ".xlsx,.xls"},
    {"id": "excel_to_pdf", "name": "Excel to PDF", "category": "from_excel", "desc": "Export Excel sheets to clean printable PDF", "accept": ".xlsx,.xls"},
    {"id": "excel_to_ics", "name": "Excel to ICS", "category": "from_excel", "desc": "Export event rows to iCalendar (.ics)", "accept": ".xlsx,.xls,.csv"},
    {"id": "excel_to_csv", "name": "Excel to CSV", "category": "from_excel", "desc": "Export Excel sheets to standard CSV", "accept": ".xlsx,.xls"},
    {"id": "excel_to_json", "name": "Excel to JSON", "category": "from_excel", "desc": "Export rows to JSON array of objects", "accept": ".xlsx,.xls"},
    {"id": "excel_to_image", "name": "Excel to Image", "category": "from_excel", "desc": "Render Excel sheets as high-res PNG image", "accept": ".xlsx,.xls"},
    {"id": "excel_to_markdown", "name": "Excel to Markdown", "category": "from_excel", "desc": "Export Excel table to Markdown format", "accept": ".xlsx,.xls"},
    {"id": "excel_to_xml", "name": "Excel to XML", "category": "from_excel", "desc": "Export Excel rows to structured XML", "accept": ".xlsx,.xls"},
    {"id": "excel_to_html", "name": "Excel to HTML", "category": "from_excel", "desc": "Export Excel sheets to responsive HTML table", "accept": ".xlsx,.xls"},
    {"id": "excel_to_sql", "name": "Excel to SQL", "category": "from_excel", "desc": "Generate SQL CREATE & INSERT statements", "accept": ".xlsx,.xls"},
    {"id": "excel_to_vcard", "name": "Excel to vCard", "category": "from_excel", "desc": "Export contact rows to vCards (.vcf)", "accept": ".xlsx,.xls,.csv"},
    {"id": "excel_to_latex", "name": "Excel to LaTeX", "category": "from_excel", "desc": "Generate LaTeX tabular code", "accept": ".xlsx,.xls"},
    {"id": "excel_to_yaml", "name": "Excel to YAML", "category": "from_excel", "desc": "Export Excel rows to YAML records", "accept": ".xlsx,.xls"},
    {"id": "excel_to_tsv", "name": "Excel to TSV", "category": "from_excel", "desc": "Export Excel sheets to tab-separated text", "accept": ".xlsx,.xls"},

    # Formats & CSV
    {"id": "xls_to_xlsx", "name": "XLS to XLSX", "category": "formats", "most_used": True, "most_used_rank": 1, "desc": "Convert legacy/web .xls & .xlsx files cleanly for Mobile & Sheets", "accept": ".xls,.xlsx"},
    {"id": "numbers_to_excel", "name": "Numbers to Excel", "category": "formats", "desc": "Convert Apple Numbers files to .xlsx", "accept": ".numbers"},
    {"id": "xlsb_to_xlsx", "name": "XLSB to XLSX", "category": "formats", "desc": "Convert Excel Binary Workbook (.xlsb) to .xlsx", "accept": ".xlsb"},
    {"id": "xlsx_to_xls", "name": "XLSX to XLS", "category": "formats", "desc": "Convert between XLSX and legacy/web XLS spreadsheets", "accept": ".xlsx,.xls"},
    {"id": "ods_to_excel", "name": "ODS to Excel", "category": "formats", "desc": "Convert OpenDocument Spreadsheet to .xlsx", "accept": ".ods"},
    {"id": "json_to_csv", "name": "JSON to CSV", "category": "formats", "desc": "Flatten JSON files directly to CSV", "accept": ".json"},
    {"id": "xml_to_csv", "name": "XML to CSV", "category": "formats", "desc": "Convert XML records directly to CSV", "accept": ".xml"},

    # Bank & QuickBooks
    {"id": "statement_to_excel", "name": "Statement to Excel", "category": "banking", "desc": "Parse bank statement text/CSV to clean Excel", "accept": ".txt,.csv,.log"},
    {"id": "statement_to_csv", "name": "Statement to CSV", "category": "banking", "desc": "Parse bank statement to standard CSV", "accept": ".txt,.csv"},
    {"id": "csv_to_qbo", "name": "CSV to QBO", "category": "banking", "desc": "Convert CSV bank transactions to QuickBooks Online QBO", "accept": ".csv"},
    {"id": "csv_to_iif", "name": "CSV to IIF", "category": "banking", "desc": "Convert CSV transactions to QuickBooks Desktop IIF", "accept": ".csv"},
    {"id": "ofx_to_excel", "name": "OFX to Excel", "category": "banking", "desc": "Convert OFX/QBO bank feeds to Excel table", "accept": ".ofx,.qbo"},
    {"id": "ofx_to_csv", "name": "OFX to CSV", "category": "banking", "desc": "Convert OFX/QBO bank feeds to standard CSV", "accept": ".ofx,.qbo"},

    # Open & Edit
    {"id": "excel_editor", "name": "Excel Editor", "category": "open_edit", "desc": "Interactive in-browser spreadsheet editor", "accept": ".xlsx,.xls,.csv,.xlsb,.xlsm,.ods"},
    {"id": "excel_viewer", "name": "Excel Viewer", "category": "open_edit", "desc": "View any Excel spreadsheet in your browser", "accept": ".xlsx,.xls,.xlsm"},
    {"id": "xlsx_viewer", "name": "XLSX Viewer", "category": "open_edit", "desc": "Instant XLSX reader and previewer", "accept": ".xlsx"},
    {"id": "xlsm_viewer", "name": "XLSM Viewer", "category": "open_edit", "desc": "Preview macro-enabled Excel spreadsheets", "accept": ".xlsm"},
    {"id": "xlsb_viewer", "name": "XLSB Viewer", "category": "open_edit", "desc": "Preview binary Excel spreadsheets in-browser", "accept": ".xlsb"},
    {"id": "xls_viewer", "name": "XLS Viewer", "category": "open_edit", "desc": "Preview legacy, web-exported .xls or .xlsx files", "accept": ".xls,.xlsx"},
    {"id": "csv_viewer", "name": "CSV Viewer", "category": "open_edit", "desc": "Fast CSV table preview with column sorting", "accept": ".csv,.tsv"},
    {"id": "csv_editor", "name": "CSV Editor", "category": "open_edit", "desc": "Edit CSV files directly in browser and save", "accept": ".csv,.tsv"},

    # Combine & Compare
    {"id": "merge_excel", "name": "Merge", "category": "combine_compare", "desc": "Combine multiple Excel workbooks or sheets", "accept": ".xlsx,.xls,.csv", "multiple": True},
    {"id": "compare_excel", "name": "Compare", "category": "combine_compare", "desc": "Diff two Excel workbooks with visual highlights", "accept": ".xlsx,.xls", "multiple": True},
    {"id": "compare_columns", "name": "Compare Columns", "category": "combine_compare", "desc": "Compare two columns and flag matches/mismatches", "accept": ".xlsx,.xls,.csv"},
    {"id": "splitter", "name": "Splitter", "category": "combine_compare", "desc": "Split workbook sheets into separate files", "accept": ".xlsx,.xls"},
    {"id": "split_by_column", "name": "Split by Column", "category": "combine_compare", "desc": "Split rows into sheets by distinct column values", "accept": ".xlsx,.xls"},
    {"id": "combine_columns", "name": "Combine Columns", "category": "combine_compare", "desc": "Merge multiple columns with custom delimiter", "accept": ".xlsx,.xls,.csv"},

    # Clean Up
    {"id": "data_cleaner", "name": "Data Cleaner", "category": "clean_up", "desc": "Trim whitespace and fix broken encodings", "accept": ".xlsx,.xls,.csv"},
    {"id": "remove_duplicates", "name": "Remove Duplicates", "category": "clean_up", "desc": "Delete duplicate rows automatically", "accept": ".xlsx,.xls,.csv"},
    {"id": "find_duplicates", "name": "Find Duplicates", "category": "clean_up", "desc": "Highlight duplicate rows without deleting", "accept": ".xlsx,.xls,.csv"},
    {"id": "remove_blank_rows", "name": "Remove Blank Rows", "category": "clean_up", "desc": "Strip empty rows and trailing blank columns", "accept": ".xlsx,.xls,.csv"},
    {"id": "remove_formatting", "name": "Remove Formatting", "category": "clean_up", "desc": "Strip all styling, leaving pure clean data", "accept": ".xlsx,.xls"},
    {"id": "text_to_number", "name": "Text to Number", "category": "clean_up", "desc": "Convert text-formatted numbers to real numbers", "accept": ".xlsx,.xls,.csv"},
    {"id": "find_replace", "name": "Find & Replace", "category": "clean_up", "desc": "Batch find & replace text across all cells", "accept": ".xlsx,.xls,.csv"},

    # Sort & Reshape
    {"id": "sort_filter", "name": "Sort & Filter", "category": "sort_reshape", "desc": "Sort rows ascending/descending by column", "accept": ".xlsx,.xls,.csv"},
    {"id": "filter_rows", "name": "Filter Rows", "category": "sort_reshape", "desc": "Filter rows matching query or conditions", "accept": ".xlsx,.xls,.csv"},
    {"id": "text_to_columns", "name": "Text to Columns", "category": "sort_reshape", "desc": "Split a column into multiple by delimiter", "accept": ".xlsx,.xls,.csv"},
    {"id": "column_extractor", "name": "Column Extractor", "category": "sort_reshape", "desc": "Keep only specified columns and delete rest", "accept": ".xlsx,.xls,.csv"},
    {"id": "data_extractor", "name": "Data Extractor", "category": "sort_reshape", "desc": "Extract specific row ranges or data blocks", "accept": ".xlsx,.xls,.csv"},
    {"id": "unpivot", "name": "Unpivot", "category": "sort_reshape", "desc": "Melt wide tables into key-value long format", "accept": ".xlsx,.xls,.csv"},
    {"id": "transpose", "name": "Transpose", "category": "sort_reshape", "desc": "Swap rows and columns seamlessly", "accept": ".xlsx,.xls,.csv"},
    {"id": "date_converter", "name": "Date Converter", "category": "sort_reshape", "desc": "Normalize varied date formats to ISO YYYY-MM-DD", "accept": ".xlsx,.xls,.csv"},
    {"id": "column_letters", "name": "Column Letters", "category": "sort_reshape", "desc": "Convert column numbers to letters (e.g. 28 -> AB)", "accept": "text"},
    {"id": "row_shading", "name": "Row Shading", "category": "sort_reshape", "desc": "Apply alternating zebra row colors", "accept": ".xlsx,.xls"}
]


@router.get("/api/tools/excel/health")
def health():
    return {
        "status": "healthy",
        "tools_count": len(TOOLS),
        "libreoffice_available": LibreOfficeEngine.is_available()
    }


@router.get("/api/tools/excel/catalog")
def list_tools():
    return {"categories": CATEGORIES, "tools": TOOLS}


@router.get("/tools/excel", response_class=HTMLResponse, include_in_schema=False)
def index_page():
    tools_json = json.dumps(TOOLS)
    categories_json = json.dumps(CATEGORIES)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{APP_TITLE} | {NAVBAR_TITLE}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-light: #eff6ff;
      --success: #10b981;
      --slate-50: #f8fafc;
      --slate-100: #f1f5f9;
      --slate-200: #e2e8f0;
      --slate-300: #cbd5e1;
      --slate-400: #94a3b8;
      --slate-600: #475569;
      --slate-700: #334155;
      --slate-800: #1e293b;
      --slate-900: #0f172a;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--slate-50);
      color: var(--slate-900);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--slate-200);
      padding: 0.85rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 50;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 800;
      font-size: 1.2rem;
      color: var(--slate-900);
      text-decoration: none;
    }}
    .brand-icon {{
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.15rem;
    }}
    .header-nav a {{
      color: var(--slate-600);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 500;
      margin-left: 1.25rem;
      transition: color 0.15s;
    }}
    .header-nav a:hover {{ color: var(--primary); }}

    /* Main Container */
    main {{
      max-width: 1280px;
      width: 100%;
      margin: 2rem auto;
      padding: 0 1.5rem;
      flex: 1;
    }}

    .hero {{
      text-align: center;
      margin-bottom: 2rem;
    }}
    .hero h1 {{
      font-size: 2.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--slate-900);
      margin-bottom: 0.5rem;
    }}
    .hero p {{
      color: var(--slate-600);
      font-size: 1.05rem;
      max-width: 700px;
      margin: 0 auto;
    }}

    /* Search & Filter Bar */
    .search-box {{
      max-width: 600px;
      margin: 1.5rem auto 1.5rem auto;
      position: relative;
    }}
    .search-input {{
      width: 100%;
      padding: 0.85rem 1rem 0.85rem 2.85rem;
      font-size: 0.95rem;
      border: 1px solid var(--slate-300);
      border-radius: 12px;
      background: #ffffff;
      outline: none;
      transition: all 0.15s;
      box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .search-input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(37,99,235,0.15);
    }}
    .search-icon {{
      position: absolute;
      left: 1rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--slate-400);
      font-size: 1.1rem;
    }}

    /* Category Tabs */
    .tabs {{
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
      padding-bottom: 0.5rem;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid var(--slate-200);
    }}
    .tab-btn {{
      background: none;
      border: none;
      padding: 0.6rem 1rem;
      border-radius: 8px;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--slate-600);
      cursor: pointer;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s;
    }}
    .tab-btn:hover {{
      background: var(--slate-100);
      color: var(--slate-900);
    }}
    .tab-btn.active {{
      background: var(--primary);
      color: #ffffff;
    }}

    /* Tool Grid */
    .tool-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 1.25rem;
    }}
    .tool-card {{
      background: #ffffff;
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      padding: 1.25rem;
      cursor: pointer;
      transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }}
    .tool-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 10px 20px -5px rgba(0,0,0,0.06);
      border-color: var(--primary);
    }}
    .tool-header {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.5rem;
    }}
    .tool-icon-badge {{
      width: 40px;
      height: 40px;
      border-radius: 8px;
      background: var(--primary-light);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      flex-shrink: 0;
    }}
    .tool-name {{
      font-weight: 700;
      font-size: 1rem;
      color: var(--slate-800);
    }}
    .tool-desc {{
      font-size: 0.825rem;
      color: var(--slate-600);
      line-height: 1.4;
      margin-bottom: 1rem;
    }}
    .tool-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-top: 1px solid var(--slate-100);
      padding-top: 0.75rem;
      font-size: 0.75rem;
      color: var(--slate-400);
      font-weight: 600;
    }}
    .most-used-section {{
      margin-bottom: 1.75rem;
      padding: 1rem 1.25rem 1.25rem;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 14px;
    }}
    .most-used-title {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.95rem;
      font-weight: 800;
      color: #92400e;
      margin-bottom: 0.85rem;
    }}
    .tool-card.most-used-card {{
      position: relative;
      padding-top: 2.35rem;
      border-color: #f59e0b;
      box-shadow: 0 4px 12px rgba(245, 158, 11, 0.12);
    }}
    .most-used-badge {{
      position: absolute;
      top: 0.65rem;
      right: 0.75rem;
      background: #fef3c7;
      color: #b45309;
      border: 1px solid #fcd34d;
      border-radius: 9999px;
      font-size: 0.68rem;
      font-weight: 700;
      padding: 0.18rem 0.5rem;
      white-space: nowrap;
    }}

    /* Modal / Action Runner */
    .modal-backdrop {{
      display: none;
      position: fixed;
      top: 0; left: 0;
      width: 100vw; height: 100vh;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      z-index: 100;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }}
    .modal-box {{
      background: #ffffff;
      border-radius: 16px;
      max-width: 640px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      padding: 2rem;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
      position: relative;
    }}
    .modal-close {{
      position: absolute;
      top: 1.25rem; right: 1.25rem;
      background: var(--slate-100);
      border: none;
      width: 32px; height: 32px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 1rem;
      color: var(--slate-600);
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    /* Dropzone in Modal */
    .modal-dropzone {{
      border: 2px dashed var(--slate-300);
      border-radius: 12px;
      padding: 2.5rem 1.5rem;
      text-align: center;
      background: var(--slate-50);
      cursor: pointer;
      position: relative;
      margin: 1.25rem 0;
    }}
    .modal-dropzone.dragover {{
      border-color: var(--primary);
      background: var(--primary-light);
    }}
    .modal-dropzone input[type="file"] {{
      position: absolute;
      top: 0; left: 0; width: 100%; height: 100%;
      opacity: 0; cursor: pointer;
      z-index: 2;
    }}

    .btn-action {{
      width: 100%;
      background: var(--primary);
      color: white;
      border: none;
      padding: 0.85rem;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.95rem;
      cursor: pointer;
      transition: background 0.15s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
    }}
    .btn-action:hover {{ background: var(--primary-hover); }}
    .btn-action:disabled {{ background: var(--slate-300); cursor: not-allowed; }}

    /* Spreadsheet Viewer / Editor Modal */
    .editor-modal {{
      display: none;
      position: fixed;
      top: 0; left: 0;
      width: 100vw; height: 100vh;
      background: #ffffff;
      z-index: 110;
      flex-direction: column;
    }}
    .editor-bar {{
      background: var(--slate-800);
      color: white;
      padding: 0.75rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .editor-grid {{
      flex: 1;
      overflow: auto;
      padding: 1rem;
    }}
    .grid-table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 0.85rem;
    }}
    .grid-table th, .grid-table td {{
      border: 1px solid var(--slate-300);
      padding: 6px 12px;
      white-space: nowrap;
    }}
    .grid-table th {{
      background: var(--slate-100);
      font-weight: 600;
      color: var(--slate-700);
    }}
    .grid-table td[contenteditable="true"]:focus {{
      outline: 2px solid var(--primary);
      background: #eff6ff;
    }}

    footer {{
      background: #ffffff;
      border-top: 1px solid var(--slate-200);
      text-align: center;
      padding: 1.5rem;
      color: var(--slate-600);
      font-size: 0.825rem;
    }}
  </style>
</head>
<body>

  <header>
    <a href="/tools" class="brand">
      <div class="brand-icon">📊</div>
      <span>{NAVBAR_TITLE} &middot; Excel &amp; Data Studio</span>
    </a>
    <div class="header-nav" style="display:flex; gap:1rem; align-items:center;">
      <a href="/tools">&larr; Back to Tools</a>
      <a href="/">🏠 Portal Home</a>
    </div>
  </header>

  <main>
    <div class="hero">
      <h1>All-in-One Excel & Spreadsheet Suite</h1>
      <p>70+ specialized tools to convert, compare, clean, reshape, edit, and export spreadsheets on your private cloud.</p>
    </div>

    <!-- Search Box -->
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="searchInput" class="search-input" placeholder="Search any tool (e.g., PDF to Excel, Splitter, QBO, Deduplicate)...">
    </div>

    <!-- Category Tabs -->
    <div class="tabs" id="tabs"></div>

    <!-- Most Used Copy pinned at Top for Easy Identification -->
    <div id="mostUsedSection" class="most-used-section">
      <div class="most-used-title">
        <span>⭐</span>
        <span>Most Used</span>
      </div>
      <div class="tool-grid" id="mostUsedGrid"></div>
    </div>

    <!-- Tools Grid -->
    <div class="tool-grid" id="toolsGrid"></div>
  </main>

  <!-- Universal Tool Execution Modal -->
  <div class="modal-backdrop" id="toolModal">
    <div class="modal-box">
      <button class="modal-close" onclick="closeToolModal()">✕</button>
      <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
        <span id="modalIcon" style="font-size: 1.75rem;">⚡</span>
        <h2 id="modalTitle" style="font-size: 1.35rem; font-weight: 800; color: var(--slate-900);">Tool Title</h2>
      </div>
      <p id="modalDesc" style="color: var(--slate-600); font-size: 0.9rem; margin-bottom: 1rem;"></p>

      <!-- Dynamic parameters -->
      <div id="modalParams" style="margin-bottom: 1rem; display: none;"></div>

      <div class="modal-dropzone" id="modalDropzone">
        <input type="file" id="modalFileInput">
        <div style="font-size: 2.25rem; margin-bottom: 0.5rem;">📂</div>
        <div style="font-weight: 700; color: var(--slate-800);" id="modalDzText">Drop file here or tap to select</div>
        <div style="font-size: 0.78rem; color: var(--slate-500); margin-top: 0.35rem;" id="modalAcceptHint"></div>
        <div style="font-size: 0.8rem; color: var(--slate-400); margin-top: 0.25rem;" id="modalFileSelected"></div>
      </div>

      <button class="btn-action" id="modalRunBtn" disabled onclick="executeCurrentTool()">
        <span>Run Tool</span>
      </button>

      <div id="modalResult" style="margin-top: 1.25rem; display: none;"></div>
    </div>
  </div>

  <!-- Interactive Spreadsheet Viewer & Editor -->
  <div class="editor-modal" id="editorModal">
    <div class="editor-bar">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span style="font-size: 1.25rem;">📊</span>
        <span id="editorFilename" style="font-weight: 700;">Spreadsheet Editor</span>
      </div>
      <div style="display: flex; gap: 0.75rem;">
        <button class="btn-action" style="padding: 0.4rem 0.85rem; font-size: 0.85rem; background: var(--success);" onclick="saveAndDownloadEditor()">
          💾 Save & Download (.XLSX)
        </button>
        <button class="btn-action" style="padding: 0.4rem 0.85rem; font-size: 0.85rem; background: #ef4444;" onclick="closeEditor()">
          ✕ Close
        </button>
      </div>
    </div>
    <div id="editorStatusBanner" style="display:none; background:#fee2e2; color:#991b1b; padding:0.75rem 1.25rem; font-weight:600; font-size:0.875rem; border-bottom:1px solid #fecaca;"></div>
    <div class="editor-grid" id="editorGrid"></div>
  </div>

  {render_canonical_footer_html("background:white; border-top:1px solid var(--slate-200); padding:1.5rem 2rem; margin-top:2rem; color:var(--slate-500);")}

  <script>
    const tools = {tools_json};
    const categories = {categories_json};

    let activeCategory = 'all';
    let currentTool = null;
    let selectedFile = null;
    let editorData = null;

    // Render Category Tabs
    const tabsContainer = document.getElementById('tabs');
    categories.forEach(cat => {{
      const btn = document.createElement('button');
      btn.className = `tab-btn ${{cat.id === 'all' ? 'active' : ''}}`;
      btn.dataset.categoryId = cat.id;
      btn.innerHTML = `<span>${{cat.icon}}</span> ${{cat.name}}`;
      btn.onclick = () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCategory = cat.id;
        renderTools(document.getElementById('searchInput').value);
      }};
      tabsContainer.appendChild(btn);
    }});

    function createToolCard(t, highlightMostUsed = false) {{
      const card = document.createElement('div');
      card.className = highlightMostUsed ? 'tool-card most-used-card' : 'tool-card';
      card.dataset.toolId = t.id;
      card.onclick = () => openToolModal(t);

      const catObj = categories.find(c => c.id === t.category) || {{ icon: '📊' }};
      const badgeHtml = highlightMostUsed ? '<span class="most-used-badge">⭐ Most Used</span>' : '';

      card.innerHTML = `
        <div>
          <div class="tool-header">
            <div class="tool-icon-badge">${{catObj.icon}}</div>
            <div class="tool-name">${{t.name}}</div>
            ${{badgeHtml}}
          </div>
          <div class="tool-desc">${{t.desc}}</div>
        </div>
        <div class="tool-footer">
          <span>${{t.accept || 'Any spreadsheet'}}</span>
          <span style="color: var(--primary);">Open &rarr;</span>
        </div>
      `;
      return card;
    }}

    // Render Tools Grid + Pinned Most Used Section
    const mostUsedSection = document.getElementById('mostUsedSection');
    const mostUsedGrid = document.getElementById('mostUsedGrid');
    const toolsGrid = document.getElementById('toolsGrid');

    function renderTools(query = '') {{
      const q = query.toLowerCase().trim();
      const mostUsedTools = tools
        .filter(t => !!t.most_used)
        .sort((a, b) => (a.most_used_rank || 999) - (b.most_used_rank || 999));

      if (mostUsedSection && mostUsedGrid) {{
        mostUsedGrid.innerHTML = '';
        if (activeCategory === 'all' && !q && mostUsedTools.length > 0) {{
          mostUsedSection.style.display = 'block';
          mostUsedTools.forEach(t => mostUsedGrid.appendChild(createToolCard(t, true)));
        }} else {{
          mostUsedSection.style.display = 'none';
        }}
      }}

      toolsGrid.innerHTML = '';
      const filtered = tools.filter(t => {{
        const matchCat =
          activeCategory === 'all' ||
          (activeCategory === 'most_used' ? !!t.most_used : t.category === activeCategory);
        const matchQuery = (!q || t.name.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q));
        return matchCat && matchQuery;
      }});
      if (activeCategory === 'most_used') {{
        filtered.sort((a, b) => (a.most_used_rank || 999) - (b.most_used_rank || 999));
      }}

      filtered.forEach(t => {{
        toolsGrid.appendChild(createToolCard(t, activeCategory === 'most_used'));
      }});
    }}

    renderTools();

    // Search filter
    document.getElementById('searchInput').addEventListener('input', (e) => {{
      renderTools(e.target.value);
    }});

    // Tool Modal Handling
    const toolModal = document.getElementById('toolModal');
    const modalFileInput = document.getElementById('modalFileInput');

    function openToolModal(tool) {{
      currentTool = tool;
      selectedFile = null;
      document.getElementById('modalTitle').textContent = tool.name;
      document.getElementById('modalDesc').textContent = tool.desc;
      document.getElementById('modalFileSelected').textContent = '';
      document.getElementById('modalResult').style.display = 'none';
      document.getElementById('modalRunBtn').disabled = true;

      const acceptHintEl = document.getElementById('modalAcceptHint');
      if (acceptHintEl) {{
        const fmtText = (tool.accept && tool.accept !== 'text') ? tool.accept.replace(/,/g, ', ') : 'Spreadsheet / Data file';
        acceptHintEl.textContent = 'Supported: ' + fmtText + ' (mobile Downloads, File Manager & web exports)';
      }}

      // Leave input accept unrestricted so Android Downloads / File Manager never grey out web-downloaded .xls files
      modalFileInput.removeAttribute('accept');
      modalFileInput.multiple = !!tool.multiple;
      modalFileInput.value = '';

      // Handle specific tool parameters (e.g. Find & Replace)
      const paramsDiv = document.getElementById('modalParams');
      paramsDiv.innerHTML = '';
      if (tool.id === 'find_replace') {{
        paramsDiv.style.display = 'block';
        paramsDiv.innerHTML = `
          <div style="display: flex; gap: 0.5rem;">
            <input type="text" id="findVal" placeholder="Find text..." style="flex:1; padding: 0.5rem; border:1px solid #cbd5e1; border-radius:6px;">
            <input type="text" id="replaceVal" placeholder="Replace with..." style="flex:1; padding: 0.5rem; border:1px solid #cbd5e1; border-radius:6px;">
          </div>
        `;
      }} else {{
        paramsDiv.style.display = 'none';
      }}

      toolModal.style.display = 'flex';
    }}

    function closeToolModal() {{
      toolModal.style.display = 'none';
      modalFileInput.value = '';
    }}

    modalFileInput.addEventListener('click', () => {{
      modalFileInput.value = '';
    }});

    modalFileInput.addEventListener('change', (e) => {{
      if (e.target.files.length > 0) {{
        selectedFile = e.target.files;
        const names = Array.from(selectedFile).map(f => f.name).join(', ');
        document.getElementById('modalFileSelected').textContent = 'Selected: ' + names;
        document.getElementById('modalRunBtn').disabled = false;
      }}
    }});

    // Execute Tool Function
    async function executeCurrentTool() {{
      if (!selectedFile || selectedFile.length === 0) return;

      const runBtn = document.getElementById('modalRunBtn');
      const resDiv = document.getElementById('modalResult');
      runBtn.disabled = true;
      runBtn.innerHTML = '<span>⏳ Processing...</span>';

      // If viewer/editor tool, launch interactive grid
      if (currentTool.category === 'open_edit') {{
        const launched = await launchSpreadsheetEditor(selectedFile[0]);
        runBtn.disabled = false;
        runBtn.innerHTML = '<span>Run Tool</span>';
        if (launched) {{
          closeToolModal();
        }}
        return;
      }}

      const formData = new FormData();
      Array.from(selectedFile).forEach(f => formData.append('files', f));
      formData.append('tool_id', currentTool.id);

      if (currentTool.id === 'find_replace') {{
        formData.append('find_val', document.getElementById('findVal')?.value || '');
        formData.append('replace_val', document.getElementById('replaceVal')?.value || '');
      }}

      try {{
        const resp = await fetch('/api/tools/excel/execute', {{
          method: 'POST',
          body: formData
        }});

        if (!resp.ok) {{
          const err = await resp.json().catch(() => ({{ detail: 'Operation failed' }}));
          throw new Error(err.detail || 'Execution failed');
        }}

        const data = await resp.json();
        resDiv.style.display = 'block';
        resDiv.innerHTML = `
          <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 1rem; border-radius: 8px;">
            <div style="font-weight: 700; color: #166534; margin-bottom: 0.5rem;">✅ Operation Complete!</div>
            <a href="${{data.download_url}}" download="${{data.filename}}" style="background: #10b981; color: white; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">
              ⬇️ Download ${{data.filename}}
            </a>
          </div>
        `;
      }} catch (err) {{
        resDiv.style.display = 'block';
        resDiv.innerHTML = `<div style="color: #ef4444; font-weight: 600;">❌ Error: ${{err.message}}</div>`;
      }} finally {{
        runBtn.disabled = false;
        runBtn.innerHTML = '<span>Run Tool</span>';
      }}
    }}

    // In-browser Spreadsheet Editor / Viewer
    async function launchSpreadsheetEditor(file) {{
      const formData = new FormData();
      formData.append('file', file);
      try {{
        const resp = await fetch('/api/tools/excel/viewer/load', {{ method: 'POST', body: formData }});
        if (!resp.ok) {{
          const err = await resp.json().catch(() => ({{ detail: 'Failed to load file into viewer.' }}));
          const resDiv = document.getElementById('modalResult');
          resDiv.style.display = 'block';
          resDiv.innerHTML = `<div style="color: #ef4444; font-weight: 600;">❌ ${{err.detail || 'Failed to load file into viewer.'}}</div>`;
          return false;
        }}
        const banner = document.getElementById('editorStatusBanner');
        if (banner) {{ banner.style.display = 'none'; banner.textContent = ''; }}
        editorData = await resp.json();
        document.getElementById('editorFilename').textContent = editorData.filename;
        renderEditorGrid(editorData.sheets[0]);
        document.getElementById('editorModal').style.display = 'flex';
        return true;
      }} catch (err) {{
        const resDiv = document.getElementById('modalResult');
        resDiv.style.display = 'block';
        resDiv.innerHTML = `<div style="color: #ef4444; font-weight: 600;">❌ Error: ${{err.message || 'Failed to load file into viewer.'}}</div>`;
        return false;
      }}
    }}

    function renderEditorGrid(sheet) {{
      const grid = document.getElementById('editorGrid');
      let html = '<table class="grid-table"><thead><tr><th>#</th>';
      const maxCols = sheet.total_cols || (sheet.rows[0]?.length || 0);
      for (let c = 0; c < maxCols; c++) {{
        html += `<th>${{String.fromCharCode(65 + (c % 26))}}${{c >= 26 ? Math.floor(c/26) : ''}}</th>`;
      }}
      html += '</tr></thead><tbody>';

      sheet.rows.forEach((row, rIdx) => {{
        html += `<tr><th>${{rIdx + 1}}</th>`;
        for (let c = 0; c < maxCols; c++) {{
          const val = row[c] !== undefined ? row[c] : '';
          html += `<td contenteditable="true" data-row="${{rIdx}}" data-col="${{c}}">${{val}}</td>`;
        }}
        html += '</tr>';
      }});
      html += '</tbody></table>';
      grid.innerHTML = html;

      // Event listener for in-place cell editing
      grid.querySelectorAll('td[contenteditable="true"]').forEach(cell => {{
        cell.addEventListener('blur', (e) => {{
          const r = parseInt(e.target.getAttribute('data-row'));
          const c = parseInt(e.target.getAttribute('data-col'));
          if (editorData.sheets[0].rows[r]) {{
            editorData.sheets[0].rows[r][c] = e.target.textContent;
          }}
        }});
      }});
    }}

    async function saveAndDownloadEditor() {{
      const resp = await fetch('/api/tools/excel/viewer/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(editorData)
      }});
      if (resp.ok) {{
        const data = await resp.json();
        window.location.href = data.download_url;
      }} else {{
        const banner = document.getElementById('editorStatusBanner');
        if (banner) {{ banner.textContent = '❌ Failed to save edited spreadsheet.'; banner.style.display = 'block'; }}
      }}
    }}

    function closeEditor() {{
      const banner = document.getElementById('editorStatusBanner');
      if (banner) {{ banner.style.display = 'none'; banner.textContent = ''; }}
      document.getElementById('editorModal').style.display = 'none';
    }}

    (function () {{
      const tModal = document.getElementById('toolModal');
      if (tModal) {{
        tModal.addEventListener('click', (e) => {{
          if (e.target === tModal) closeToolModal();
        }});
      }}
      document.addEventListener('keydown', (e) => {{
        if (e.key !== 'Escape') return;
        const edModal = document.getElementById('editorModal');
        if (edModal && edModal.style.display === 'flex') {{
          closeEditor();
          return;
        }}
        if (tModal && tModal.style.display === 'flex') {{
          closeToolModal();
        }}
      }});
      try {{
        const sp = new URLSearchParams(window.location.search || '');
        const siteVal = (sp.get('site') || '').trim().toLowerCase();
        if (siteVal === 'console' || siteVal === 'reports' || siteVal === 'portal') {{
          document.querySelectorAll('a[href]').forEach((a) => {{
            const href = a.getAttribute('href') || '';
            if (!href.startsWith('/') || href.startsWith('//') || href.startsWith('/api/')) return;
            const parsed = new URL(href, window.location.origin);
            if (!parsed.searchParams.has('site')) {{
              parsed.searchParams.set('site', siteVal);
              a.setAttribute('href', parsed.pathname + parsed.search + parsed.hash);
            }}
          }});
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>"""


# ==========================================
# UNIVERSAL TOOL DISPATCH ROUTE
# ==========================================

_XLSX_REQUIRED_TOOLS = {
    "excel_to_word", "excel_to_pdf", "excel_to_csv", "excel_to_tsv",
    "excel_to_json", "excel_to_yaml", "excel_to_markdown", "excel_to_html",
    "excel_to_xml", "excel_to_sql", "excel_to_latex", "excel_to_vcard",
    "excel_to_ics", "excel_to_image",
    "merge_excel", "compare_excel", "compare_columns", "splitter",
    "split_by_column", "combine_columns",
    "remove_duplicates", "find_duplicates", "remove_blank_rows",
    "remove_formatting", "text_to_number", "find_replace", "data_cleaner",
    "sort_filter", "filter_rows", "text_to_columns", "column_extractor",
    "transpose", "unpivot", "row_shading", "date_converter",
}


def _run_universal(src: str, out_file: Path) -> None:
    ok, msg = convert_file_universal(src, str(out_file))
    if not ok:
        raise ValueError(msg)


@router.post("/api/tools/excel/execute")
async def execute_tool_endpoint(
    tool_id: str = Form(...),
    files: List[UploadFile] = File(...),
    find_val: Optional[str] = Form(None),
    replace_val: Optional[str] = Form(None)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    session_id = str(uuid.uuid4())
    session_dir = STORAGE_DIR / session_id
    input_dir = session_dir / "_input"
    input_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    first_safe_name = "file"
    for idx, f in enumerate(files):
        safe_fname = _safe_name(f.filename, "file")
        if idx == 0:
            first_safe_name = safe_fname
        fpath = input_dir / f"{idx}_{safe_fname}"
        with open(fpath, "wb") as fp:
            shutil.copyfileobj(f.file, fp)
        if fpath.stat().st_size == 0:
            raise HTTPException(status_code=400, detail=f"Uploaded file '{safe_fname}' is empty (0 bytes).")
        saved_paths.append(str(fpath))

    src = saved_paths[0]
    base_name = Path(first_safe_name).stem or "file"

    try:
        if tool_id in _XLSX_REQUIRED_TOOLS:
            saved_paths = [normalize_to_xlsx(p, input_dir, idx) for idx, p in enumerate(saved_paths)]
            src = saved_paths[0]

        # Group 1: TO EXCEL
        if tool_id == "word_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.word_to_excel(src, str(out_file))
        elif tool_id == "pdf_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.pdf_to_excel(src, str(out_file))
        elif tool_id == "xml_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.xml_to_excel(src, str(out_file))
        elif tool_id == "txt_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.txt_to_excel(src, str(out_file))
        elif tool_id == "json_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.json_to_excel(src, str(out_file))
        elif tool_id == "csv_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.csv_to_excel(src, str(out_file))
        elif tool_id == "tsv_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.tsv_to_excel(src, str(out_file))
        elif tool_id == "html_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            _run_universal(src, out_file)
        elif tool_id == "markdown_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.markdown_to_excel(src, str(out_file))
        elif tool_id == "sql_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.sql_to_excel(src, str(out_file))
        elif tool_id == "yaml_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.yaml_to_excel(src, str(out_file))
        elif tool_id == "image_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            to_excel.image_to_excel(src, str(out_file))

        # Group 2: FROM EXCEL
        elif tool_id == "excel_to_word":
            out_file = session_dir / f"{base_name}.docx"
            from_excel.excel_to_word(src, str(out_file))
        elif tool_id == "excel_to_pdf":
            out_file = session_dir / f"{base_name}.pdf"
            from_excel.excel_to_pdf(src, str(out_file))
        elif tool_id == "excel_to_csv":
            out_file = session_dir / f"{base_name}.csv"
            from_excel.excel_to_csv(src, str(out_file))
        elif tool_id == "excel_to_tsv":
            out_file = session_dir / f"{base_name}.tsv"
            from_excel.excel_to_tsv(src, str(out_file))
        elif tool_id == "excel_to_json":
            out_file = session_dir / f"{base_name}.json"
            from_excel.excel_to_json(src, str(out_file))
        elif tool_id == "excel_to_yaml":
            out_file = session_dir / f"{base_name}.yaml"
            from_excel.excel_to_yaml(src, str(out_file))
        elif tool_id == "excel_to_markdown":
            out_file = session_dir / f"{base_name}.md"
            from_excel.excel_to_markdown(src, str(out_file))
        elif tool_id == "excel_to_html":
            out_file = session_dir / f"{base_name}.html"
            from_excel.excel_to_html(src, str(out_file))
        elif tool_id == "excel_to_xml":
            out_file = session_dir / f"{base_name}.xml"
            from_excel.excel_to_xml(src, str(out_file))
        elif tool_id == "excel_to_sql":
            out_file = session_dir / f"{base_name}.sql"
            from_excel.excel_to_sql(src, str(out_file))
        elif tool_id == "excel_to_latex":
            out_file = session_dir / f"{base_name}.tex"
            from_excel.excel_to_latex(src, str(out_file))
        elif tool_id == "excel_to_vcard":
            out_file = session_dir / f"{base_name}.vcf"
            from_excel.excel_to_vcard(src, str(out_file))
        elif tool_id == "excel_to_ics":
            out_file = session_dir / f"{base_name}.ics"
            from_excel.excel_to_ics(src, str(out_file))
        elif tool_id == "excel_to_image":
            out_file = session_dir / f"{base_name}.png"
            from_excel.excel_to_image(src, str(out_file))

        # Group 3: FORMATS & CSV
        elif tool_id in ("xls_to_xlsx", "xlsx_to_xls"):
            out_file = session_dir / f"{base_name}.xlsx"
            _run_universal(src, out_file)
        elif tool_id == "xlsb_to_xlsx":
            out_file = session_dir / f"{base_name}.xlsx"
            formats_conv.xlsb_to_xlsx(src, str(out_file))
        elif tool_id == "ods_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            formats_conv.ods_to_excel(src, str(out_file))
        elif tool_id == "numbers_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            formats_conv.numbers_to_excel(src, str(out_file))
        elif tool_id == "json_to_csv":
            out_file = session_dir / f"{base_name}.csv"
            formats_conv.json_to_csv(src, str(out_file))
        elif tool_id == "xml_to_csv":
            out_file = session_dir / f"{base_name}.csv"
            formats_conv.xml_to_csv(src, str(out_file))

        # Group 4: BANK & QUICKBOOKS
        elif tool_id == "statement_to_excel":
            out_file = session_dir / f"{base_name}_Statement.xlsx"
            bank_qb.statement_to_excel(src, str(out_file))
        elif tool_id == "statement_to_csv":
            out_file = session_dir / f"{base_name}_Statement.csv"
            bank_qb.statement_to_csv(src, str(out_file))
        elif tool_id == "csv_to_qbo":
            out_file = session_dir / f"{base_name}.qbo"
            bank_qb.csv_to_qbo(src, str(out_file))
        elif tool_id == "csv_to_iif":
            out_file = session_dir / f"{base_name}.iif"
            bank_qb.csv_to_iif(src, str(out_file))
        elif tool_id == "ofx_to_excel":
            out_file = session_dir / f"{base_name}.xlsx"
            bank_qb.ofx_to_excel(src, str(out_file))
        elif tool_id == "ofx_to_csv":
            out_file = session_dir / f"{base_name}.csv"
            bank_qb.ofx_to_csv(src, str(out_file))

        # Group 5: COMBINE & COMPARE
        elif tool_id == "merge_excel":
            out_file = session_dir / "Merged_Workbook.xlsx"
            data_tools.merge_workbooks(saved_paths, str(out_file))
        elif tool_id == "compare_excel":
            if len(saved_paths) < 2:
                raise HTTPException(status_code=400, detail="Compare requires two Excel files.")
            out_file = session_dir / "Comparison_Report.xlsx"
            data_tools.compare_workbooks(saved_paths[0], saved_paths[1], str(out_file))
        elif tool_id == "compare_columns":
            out_file = session_dir / f"{base_name}_Compared.xlsx"
            data_tools.compare_columns(src, str(out_file), 1, 2)
        elif tool_id == "splitter":
            out_file = session_dir / f"{base_name}_Split_Sheets.zip"
            data_tools.split_workbook_sheets(src, str(out_file))
        elif tool_id == "split_by_column":
            out_file = session_dir / f"{base_name}_SplitByCol.xlsx"
            data_tools.split_by_column(src, str(out_file), 1)
        elif tool_id == "combine_columns":
            out_file = session_dir / f"{base_name}_CombinedCols.xlsx"
            data_tools.combine_columns(src, str(out_file), [1, 2])

        # Group 6: CLEAN UP
        elif tool_id == "remove_duplicates":
            out_file = session_dir / f"{base_name}_Deduplicated.xlsx"
            data_tools.remove_duplicates(src, str(out_file))
        elif tool_id == "find_duplicates":
            out_file = session_dir / f"{base_name}_DuplicatesHighlighted.xlsx"
            data_tools.find_duplicates(src, str(out_file))
        elif tool_id == "remove_blank_rows":
            out_file = session_dir / f"{base_name}_CleanRows.xlsx"
            data_tools.remove_blank_rows(src, str(out_file))
        elif tool_id == "remove_formatting":
            out_file = session_dir / f"{base_name}_RawData.xlsx"
            data_tools.remove_formatting(src, str(out_file))
        elif tool_id == "text_to_number":
            out_file = session_dir / f"{base_name}_NumbersFixed.xlsx"
            data_tools.text_to_number(src, str(out_file))
        elif tool_id == "find_replace":
            out_file = session_dir / f"{base_name}_Replaced.xlsx"
            data_tools.find_and_replace(src, str(out_file), find_val or "", replace_val or "")
        elif tool_id == "data_cleaner":
            out_file = session_dir / f"{base_name}_Cleaned.xlsx"
            data_tools.data_cleaner(src, str(out_file))

        # Group 7: SORT & RESHAPE
        elif tool_id == "sort_filter":
            out_file = session_dir / f"{base_name}_Sorted.xlsx"
            data_tools.sort_and_filter(src, str(out_file), 1)
        elif tool_id == "filter_rows":
            out_file = session_dir / f"{base_name}_Filtered.xlsx"
            data_tools.filter_rows(src, str(out_file), 1, "not_empty")
        elif tool_id == "text_to_columns":
            out_file = session_dir / f"{base_name}_SplitCols.xlsx"
            data_tools.text_to_columns(src, str(out_file), 1, ",")
        elif tool_id == "column_extractor":
            out_file = session_dir / f"{base_name}_Extracted.xlsx"
            data_tools.column_extractor(src, str(out_file), [1, 2, 3])
        elif tool_id == "transpose":
            out_file = session_dir / f"{base_name}_Transposed.xlsx"
            data_tools.transpose(src, str(out_file))
        elif tool_id == "unpivot":
            out_file = session_dir / f"{base_name}_Unpivoted.xlsx"
            data_tools.unpivot(src, str(out_file), [1])
        elif tool_id == "row_shading":
            out_file = session_dir / f"{base_name}_ZebraShaded.xlsx"
            data_tools.row_shading(src, str(out_file))
        elif tool_id == "date_converter":
            out_file = session_dir / f"{base_name}_DatesNormalized.xlsx"
            data_tools.date_converter(src, str(out_file), 1)
        else:
            out_file = session_dir / f"{base_name}.xlsx"
            _run_universal(src, out_file)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool failed: {str(e)}")

    if not out_file.exists():
        raise HTTPException(status_code=500, detail="Output file was not generated.")

    return {
        "success": True,
        "filename": out_file.name,
        "download_url": f"/api/tools/excel/download/{session_id}/{out_file.name}"
    }


# ==========================================
# VIEWER & EDITOR API
# ==========================================

@router.post("/api/tools/excel/viewer/load")
async def viewer_load_endpoint(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = STORAGE_DIR / session_id
    input_dir = session_dir / "_input"
    input_dir.mkdir(parents=True, exist_ok=True)
    fpath = input_dir / _safe_name(file.filename, "grid_file")
    with open(fpath, "wb") as fp:
        shutil.copyfileobj(file.file, fp)
    if fpath.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    try:
        grid_data = viewer_engine.load_file_for_viewer(str(fpath))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load file: {str(e)}")
    grid_data["session_id"] = session_id
    return grid_data


@router.post("/api/tools/excel/viewer/save")
async def viewer_save_endpoint(payload: Dict[str, Any] = Body(...)):
    session_id = _safe_name(payload.get("session_id"), "") if payload.get("session_id") else str(uuid.uuid4())
    session_dir = STORAGE_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    dest = session_dir / f"Edited_{_safe_name(payload.get('filename'), 'spreadsheet.xlsx')}"
    if not str(dest).endswith('.xlsx'):
        dest = dest.with_suffix('.xlsx')

    viewer_engine.save_edited_grid(payload.get("sheets", []), str(dest))
    return {
        "success": True,
        "download_url": f"/api/tools/excel/download/{session_id}/{dest.name}"
    }


@router.get("/api/tools/excel/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    safe_session = _safe_name(session_id, "")
    safe_filename = _safe_name(filename, "")
    if not safe_session or not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid download path.")
    base_dir = STORAGE_DIR.resolve()
    file_path = (base_dir / safe_session / safe_filename).resolve()
    if not file_path.is_relative_to(base_dir) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File expired or not found.")

    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
    )




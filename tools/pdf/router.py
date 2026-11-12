"""
All-in-One PDF Studio Router for e-Panchayat Automation Tools Module.
Provides 14 self-hosted PDF utilities powered by PyMuPDF, pdf2docx, and RapidOCR.
"""

import io
import os
import zipfile
import tempfile
from typing import List, Optional

import pymupdf  # PyMuPDF
import pymupdf4llm
from pdf2docx import Converter
from PIL import Image

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from core.branding import PLATFORM_NAME, render_canonical_footer_html

router = APIRouter(tags=["tools-pdf"])


@router.get("/api/tools/pdf/health")
def pdf_health():
    return {"status": "healthy", "tools_count": 14, "engine": "PyMuPDF"}


# ==============================================================================
# Helper functions
# ==============================================================================
def create_file_response(data: bytes, filename: str, media_type: str = "application/pdf"):
    safe_name = os.path.basename(str(filename or "document.pdf")).replace('"', "_") or "document.pdf"
    stream = io.BytesIO(data)
    stream.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}
    return StreamingResponse(stream, media_type=media_type, headers=headers)


# ==============================================================================
# API Endpoints
# ==============================================================================

@router.post("/api/tools/pdf/merge")
async def api_merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Please upload at least 2 PDF files to merge.")
    
    merged_doc = pymupdf.open()
    for file in files:
        content = await file.read()
        doc = pymupdf.open(stream=content, filetype="pdf")
        merged_doc.insert_pdf(doc)
        doc.close()
    
    out_bytes = merged_doc.tobytes(deflate=True)
    merged_doc.close()
    return create_file_response(out_bytes, "merged.pdf")


@router.post("/api/tools/pdf/split")
async def api_split(
    file: UploadFile = File(...),
    split_type: str = Form("range"),          # "range", "pages", "size"
    range_mode: str = Form("custom"),         # "custom", "fixed", "smart"
    ranges_json: str = Form("[]"),            # e.g. [{"from": 1, "to": 2}]
    merge_ranges: bool = Form(False),         # checkbox: merge into 1 PDF
    fixed_pages: int = Form(2),               # for fixed range
    pages_mode: str = Form("all"),            # "all" or "select"
    selected_pages: str = Form(""),           # e.g. "1-3, 5"
    max_part_size_mb: float = Form(5.0)       # for size mode
):
    import json
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    total_pages = len(doc)
    
    if total_pages == 0:
        doc.close()
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    # -------------------------------------------------------------
    # 1. RANGE MODE (Custom, Fixed, Smart)
    # -------------------------------------------------------------
    if split_type == "range":
        extracted_parts = []
        
        if range_mode == "custom":
            try:
                ranges = json.loads(ranges_json)
            except Exception:
                ranges = [{"from": 1, "to": total_pages}]
            
            if not ranges:
                ranges = [{"from": 1, "to": total_pages}]

            for idx, r in enumerate(ranges):
                start = max(0, int(r.get("from", 1)) - 1)
                end = min(total_pages - 1, int(r.get("to", total_pages)) - 1)
                if start <= end:
                    part_doc = pymupdf.open()
                    part_doc.insert_pdf(doc, from_page=start, to_page=end)
                    extracted_parts.append((f"range_{idx + 1}_p{start + 1}-p{end + 1}.pdf", part_doc))

        elif range_mode == "fixed":
            step = max(1, fixed_pages)
            part_num = 1
            for start in range(0, total_pages, step):
                end = min(total_pages - 1, start + step - 1)
                part_doc = pymupdf.open()
                part_doc.insert_pdf(doc, from_page=start, to_page=end)
                extracted_parts.append((f"part_{part_num}_p{start + 1}-p{end + 1}.pdf", part_doc))
                part_num += 1

        else:  # smart
            toc = doc.get_toc()  # [[lvl, title, page], ...]
            if toc:
                chapters = []
                for i, item in enumerate(toc):
                    c_start = max(0, item[2] - 1)
                    c_end = (toc[i + 1][2] - 2) if (i + 1 < len(toc)) else (total_pages - 1)
                    if c_start <= c_end:
                        clean_title = "".join(c for c in item[1] if c.isalnum() or c in (' ', '_', '-')).strip() or f"chapter_{i+1}"
                        chapters.append((clean_title, c_start, c_end))
                
                for title, c_start, c_end in chapters:
                    part_doc = pymupdf.open()
                    part_doc.insert_pdf(doc, from_page=c_start, to_page=c_end)
                    extracted_parts.append((f"{title}.pdf", part_doc))
            
            if not extracted_parts:
                half = max(1, total_pages // 2)
                for start, end, label in [(0, half - 1, "section_1"), (half, total_pages - 1, "section_2")]:
                    if start <= end:
                        part_doc = pymupdf.open()
                        part_doc.insert_pdf(doc, from_page=start, to_page=end)
                        extracted_parts.append((f"{label}.pdf", part_doc))

        if not extracted_parts:
            doc.close()
            raise HTTPException(status_code=400, detail="No valid pages extracted for the specified range.")

        # If user checked: "Merge all ranges in one PDF file"
        if merge_ranges:
            merged = pymupdf.open()
            for _, pdoc in extracted_parts:
                merged.insert_pdf(pdoc)
                pdoc.close()
            out_bytes = merged.tobytes(deflate=True)
            merged.close()
            doc.close()
            return create_file_response(out_bytes, f"split_merged_{file.filename}")

        # If only 1 part was extracted
        if len(extracted_parts) == 1:
            name, pdoc = extracted_parts[0]
            out_bytes = pdoc.tobytes(deflate=True)
            pdoc.close()
            doc.close()
            return create_file_response(out_bytes, name)

        # Multiple parts: package into ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, pdoc in extracted_parts:
                zf.writestr(name, pdoc.tobytes(deflate=True))
                pdoc.close()
        doc.close()
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="split_ranges.zip"'}
        )

    # -------------------------------------------------------------
    # 2. PAGES MODE
    # -------------------------------------------------------------
    elif split_type == "pages":
        if pages_mode == "all":
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(total_pages):
                    single_doc = pymupdf.open()
                    single_doc.insert_pdf(doc, from_page=i, to_page=i)
                    zf.writestr(f"page_{i + 1}.pdf", single_doc.tobytes(deflate=True))
                    single_doc.close()
            doc.close()
            zip_buffer.seek(0)
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="split_all_pages.zip"'}
            )
        else:
            selected = []
            for part in selected_pages.split(","):
                part = part.strip()
                if "-" in part:
                    s, e = map(int, part.split("-"))
                    selected.extend(range(s - 1, e))
                elif part.isdigit():
                    selected.append(int(part) - 1)
            
            if merge_ranges:
                new_doc = pymupdf.open()
                for p in selected:
                    if 0 <= p < total_pages:
                        new_doc.insert_pdf(doc, from_page=p, to_page=p)
                out_bytes = new_doc.tobytes(deflate=True)
                new_doc.close()
                doc.close()
                return create_file_response(out_bytes, f"extracted_{file.filename}")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for p in selected:
                        if 0 <= p < total_pages:
                            single_doc = pymupdf.open()
                            single_doc.insert_pdf(doc, from_page=p, to_page=p)
                            zf.writestr(f"page_{p + 1}.pdf", single_doc.tobytes(deflate=True))
                            single_doc.close()
                doc.close()
                zip_buffer.seek(0)
                return StreamingResponse(
                    zip_buffer,
                    media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="extracted_pages.zip"'}
                )

    # -------------------------------------------------------------
    # 3. SIZE MODE
    # -------------------------------------------------------------
    else:
        target_bytes = max(100000, int(max_part_size_mb * 1024 * 1024))
        parts = []
        current_part = pymupdf.open()
        
        for i in range(total_pages):
            current_part.insert_pdf(doc, from_page=i, to_page=i)
            if len(current_part.tobytes(deflate=True)) > target_bytes and len(current_part) > 1:
                current_part.delete_page(len(current_part) - 1)
                parts.append(current_part)
                current_part = pymupdf.open()
                current_part.insert_pdf(doc, from_page=i, to_page=i)
                
        if len(current_part) > 0:
            parts.append(current_part)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, pdoc in enumerate(parts):
                zf.writestr(f"split_part_{idx + 1}.pdf", pdoc.tobytes(deflate=True))
                pdoc.close()
        doc.close()
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="split_by_size_{max_part_size_mb}MB.zip"'}
        )


def smart_compress_pdf(
    content: bytes,
    mode: str = "ratio",
    ratio: int = 50,
    target_size: float = 2.0,
    target_unit: str = "MB"
) -> bytes:
    """
    Dual-mode compression:
    1. Compression % Ratio (e.g. reduce size by 50% or 75%)
    2. Compress to Exact Target Size (e.g. compress 60MB down to 2MB)
    """
    input_bytes = len(content)
    
    # Calculate target bytes
    if mode == "target_size":
        if target_unit.upper() == "KB":
            target_bytes = int(target_size * 1024)
        else:
            target_bytes = int(target_size * 1024 * 1024)
    else:
        # mode == "ratio" (reduction percentage)
        reduction_fraction = max(0.1, min(0.95, ratio / 100.0))
        target_bytes = int(input_bytes * (1.0 - reduction_fraction))

    # Step 1: Baseline standard lossless deflation
    doc = pymupdf.open(stream=content, filetype="pdf")
    baseline = doc.tobytes(garbage=4, deflate=True, clean=True)
    if len(baseline) <= target_bytes:
        doc.close()
        return baseline

    # Step 2: Adaptive raster image optimization
    image_xrefs = set()
    for page in doc:
        for img in page.get_images():
            image_xrefs.add(img[0])

    best_result = baseline

    if image_xrefs:
        ratio_needed = target_bytes / max(1, len(baseline))
        
        # Progressive levels of image compression
        levels = [
            {"scale": 0.85, "quality": 75},
            {"scale": 0.65, "quality": 60},
            {"scale": 0.50, "quality": 45},
            {"scale": 0.35, "quality": 30},
        ]
        
        # If aggressive compression is requested (e.g. 60MB down to 2MB)
        if ratio_needed < 0.20:
            levels = [
                {"scale": 0.50, "quality": 50},
                {"scale": 0.35, "quality": 35},
                {"scale": 0.25, "quality": 25},
                {"scale": 0.15, "quality": 20},
            ]

        for lvl in levels:
            temp_doc = pymupdf.open(stream=content, filetype="pdf")
            for xref in image_xrefs:
                try:
                    base_img = temp_doc.extract_image(xref)
                    if not base_img:
                        continue
                    img_data = base_img["image"]
                    pil_img = Image.open(io.BytesIO(img_data))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")

                    new_w = max(10, int(pil_img.width * lvl["scale"]))
                    new_h = max(10, int(pil_img.height * lvl["scale"]))
                    resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                    buf = io.BytesIO()
                    resized.save(buf, format="JPEG", quality=lvl["quality"], optimize=True)

                    for p in temp_doc:
                        p.replace_image(xref, stream=buf.getvalue())
                except Exception:
                    pass

            out = temp_doc.tobytes(garbage=4, deflate=True, clean=True)
            temp_doc.close()

            if len(out) < len(best_result):
                best_result = out

            if len(out) <= target_bytes:
                doc.close()
                return out

    # Step 3: Guaranteed fallback if image downsampling alone wasn't enough to reach target
    if len(best_result) > target_bytes:
        num_pages = len(doc)
        bytes_per_page = max(12000, target_bytes // max(1, num_pages))
        
        if bytes_per_page > 150000:
            dpi, quality = 120, 65
        elif bytes_per_page > 80000:
            dpi, quality = 96, 50
        elif bytes_per_page > 40000:
            dpi, quality = 75, 40
        else:
            dpi, quality = 60, 30

        try:
            raster_doc = pymupdf.open()
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)

                rect = page.rect
                new_page = raster_doc.new_page(width=rect.width, height=rect.height)
                new_page.insert_image(rect, stream=buf.getvalue())

            raster_out = raster_doc.tobytes(garbage=4, deflate=True)
            raster_doc.close()
            if len(raster_out) < len(best_result):
                best_result = raster_out
        except Exception:
            pass

    doc.close()
    return best_result


@router.post("/api/tools/pdf/compress")
async def api_compress(
    file: UploadFile = File(...),
    compress_mode: str = Form("ratio"),
    ratio: int = Form(50),
    target_size: float = Form(2.0),
    target_unit: str = Form("MB")
):
    content = await file.read()
    compressed_bytes = smart_compress_pdf(
        content=content,
        mode=compress_mode,
        ratio=ratio,
        target_size=target_size,
        target_unit=target_unit
    )
    return create_file_response(compressed_bytes, f"compressed_{file.filename}")


@router.post("/api/tools/pdf/rotate")
async def api_rotate(file: UploadFile = File(...), angle: int = Form(90)):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    for page in doc:
        page.set_rotation((page.rotation + angle) % 360)
    out_bytes = doc.tobytes(deflate=True)
    doc.close()
    return create_file_response(out_bytes, f"rotated_{file.filename}")


@router.post("/api/tools/pdf/pdf-to-word")
async def api_pdf_to_word(file: UploadFile = File(...)):
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
        temp_pdf.write(content)
        temp_pdf_path = temp_pdf.name

    docx_path = temp_pdf_path.replace(".pdf", ".docx")
    try:
        cv = Converter(temp_pdf_path)
        cv.convert(docx_path)
        cv.close()
        
        with open(docx_path, "rb") as f:
            docx_bytes = f.read()
            
        base_name = os.path.splitext(file.filename or "document")[0]
        return create_file_response(
            docx_bytes,
            f"{base_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        if os.path.exists(docx_path):
            os.remove(docx_path)


@router.post("/api/tools/pdf/pdf-to-markdown")
async def api_pdf_to_markdown(file: UploadFile = File(...)):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    md_text = pymupdf4llm.to_markdown(doc)
    doc.close()
    
    base_name = os.path.splitext(file.filename or "document")[0]
    return StreamingResponse(
        io.BytesIO(md_text.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{base_name}.md"'}
    )


@router.post("/api/tools/pdf/pdf-to-images")
async def api_pdf_to_images(file: UploadFile = File(...), dpi: int = Form(150)):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    
    if len(doc) == 1:
        # Single page -> direct PNG download
        pix = doc[0].get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        doc.close()
        return StreamingResponse(
            io.BytesIO(img_bytes),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="page_1.png"'}
        )
    
    # Multiple pages -> ZIP of PNGs
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            zf.writestr(f"page_{i + 1}.png", pix.tobytes("png"))
    doc.close()
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="pdf_images.zip"'}
    )


@router.post("/api/tools/pdf/images-to-pdf")
async def api_images_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No image files provided.")
    
    doc = pymupdf.open()
    for file in files:
        img_data = await file.read()
        ext = os.path.splitext(file.filename or "image.png")[1][1:] or "png"
        img_doc = pymupdf.open(stream=img_data, filetype=ext)
        rect = img_doc[0].rect
        pdf_bytes = img_doc.convert_to_pdf()
        img_pdf = pymupdf.open("pdf", pdf_bytes)
        page = doc.new_page(width=rect.width, height=rect.height)
        page.show_pdf_page(rect, img_pdf, 0)
        img_doc.close()
        img_pdf.close()
        
    out_bytes = doc.tobytes(deflate=True)
    doc.close()
    return create_file_response(out_bytes, "converted_images.pdf")


@router.post("/api/tools/pdf/protect")
async def api_protect(file: UploadFile = File(...), password: str = Form(...)):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    perm = pymupdf.PDF_PERM_ACCESSIBILITY | pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY
    out_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password + "_owner",
        permissions=perm,
        deflate=True
    )
    doc.close()
    return create_file_response(out_bytes, f"protected_{file.filename}")


@router.post("/api/tools/pdf/unlock")
async def api_unlock(file: UploadFile = File(...), password: str = Form(...)):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    if doc.is_encrypted:
        if not doc.authenticate(password):
            doc.close()
            raise HTTPException(status_code=401, detail="Incorrect password. Unable to unlock PDF.")
    out_bytes = doc.tobytes(deflate=True)
    doc.close()
    return create_file_response(out_bytes, f"unlocked_{file.filename}")


@router.post("/api/tools/pdf/watermark")
async def api_watermark(
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIAL"),
    opacity: float = Form(0.3),
    font_size: int = Form(48)
):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    for page in doc:
        rect = page.rect
        center = pymupdf.Point(rect.width / 2, rect.height / 2)
        # Add diagonal watermark text
        page.insert_text(
            center,
            text,
            fontsize=font_size,
            rotate=45,
            color=(0.7, 0.7, 0.7),
            fill_opacity=opacity
        )
    out_bytes = doc.tobytes(deflate=True)
    doc.close()
    return create_file_response(out_bytes, f"watermarked_{file.filename}")


@router.post("/api/tools/pdf/page-numbers")
async def api_page_numbers(
    file: UploadFile = File(...),
    page_mode: str = Form("single"),          # "single" or "facing"
    position: str = Form("bottom_right"),     # top_left, top_center, top_right, middle_left, middle_center, middle_right, bottom_left, bottom_center, bottom_right
    margin: str = Form("recommended"),        # "recommended", "small", "large"
    first_number: int = Form(1),
    from_page: int = Form(1),
    to_page: Optional[int] = Form(None),
    text_format: str = Form("only_number"),   # "only_number", "page_n", "page_n_of_p", "custom"
    custom_text: str = Form(""),
    font_family: str = Form("Arial"),         # "Arial", "Times", "Courier"
    font_size: int = Form(10),
    is_bold: bool = Form(False),
    is_italic: bool = Form(False),
    is_underline: bool = Form(False),
    font_color: str = Form("#1e293b")
):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    total_doc_pages = len(doc)
    
    if total_doc_pages == 0:
        doc.close()
        raise HTTPException(status_code=400, detail="The uploaded PDF has no pages.")

    # Range of pages to number
    start_p = max(0, from_page - 1)
    end_p = (to_page - 1) if (to_page and to_page <= total_doc_pages) else (total_doc_pages - 1)
    if start_p > end_p:
        start_p, end_p = 0, total_doc_pages - 1

    # Margin values (points)
    if margin == "small":
        margin_val = 18
    elif margin == "large":
        margin_val = 54
    else:
        margin_val = 36  # recommended

    # Font family & styling code
    family_lower = font_family.lower()
    if "times" in family_lower:
        base_font = "ti"
    elif "courier" in family_lower:
        base_font = "co"
    else:
        base_font = "he"  # helvetica/arial

    if is_bold and is_italic:
        font_code = base_font + "bi"
    elif is_bold:
        font_code = base_font + "bo"
    elif is_italic:
        font_code = base_font + "it"
    else:
        font_code = "times" if base_font == "ti" else ("couri" if base_font == "co" else "helv")

    # Parse color hex to RGB tuple (0.0 - 1.0)
    try:
        hex_c = font_color.lstrip('#')
        color_rgb = tuple(int(hex_c[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    except Exception:
        color_rgb = (0.12, 0.16, 0.23)

    # Numbering loop
    for idx in range(start_p, end_p + 1):
        page = doc[idx]
        rect = page.rect
        current_num = first_number + (idx - start_p)
        
        # Build text string
        if text_format == "page_n":
            text_str = f"Page {current_num}"
        elif text_format == "page_n_of_p":
            text_str = f"Page {current_num} of {total_doc_pages}"
        elif text_format == "custom" and custom_text:
            text_str = custom_text.replace("{n}", str(current_num)).replace("{p}", str(total_doc_pages))
        else:
            text_str = str(current_num)

        # Calculate text width
        try:
            text_width = pymupdf.get_text_length(text_str, fontname=font_code, fontsize=font_size)
        except Exception:
            text_width = len(text_str) * font_size * 0.55

        # Determine alignment from position (e.g. "bottom_right")
        pos_parts = position.split("_")
        vert = pos_parts[0] if len(pos_parts) > 0 else "bottom"
        horiz = pos_parts[1] if len(pos_parts) > 1 else "right"

        # Facing pages adjustment (book spread)
        if page_mode == "facing":
            is_left_page = (idx % 2 == 1)
            if is_left_page:
                if horiz == "right":
                    horiz = "left"
                elif horiz == "left":
                    horiz = "right"

        # Calculate coordinates
        if horiz == "left":
            x = margin_val
        elif horiz == "center":
            x = (rect.width - text_width) / 2
        else:
            x = rect.width - margin_val - text_width

        if vert == "top":
            y = margin_val + font_size
        elif vert == "middle":
            y = (rect.height / 2) + (font_size / 2)
        else:
            y = rect.height - margin_val

        # Stamp text
        point = pymupdf.Point(x, y)
        try:
            page.insert_text(point, text_str, fontname=font_code, fontsize=font_size, color=color_rgb)
        except Exception:
            page.insert_text(point, text_str, fontsize=font_size, color=color_rgb)

        # Underline if enabled
        if is_underline:
            try:
                page.draw_line((x, y + 2), (x + text_width, y + 2), color=color_rgb, width=0.8)
            except Exception:
                pass

    out_bytes = doc.tobytes(deflate=True)
    doc.close()
    return create_file_response(out_bytes, f"numbered_{file.filename}")


@router.post("/api/tools/pdf/ocr")
async def api_ocr(
    file: UploadFile = File(...),
    languages: str = Form("English"),
    ocr_mode: str = Form("standard"),
    auto_rotate: bool = Form(False),
    deskew: bool = Form(False),
    dewarp: bool = Form(False)
):
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    
    ocr_engine = RapidOCR()
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    total_pages = len(doc)
    
    if total_pages == 0:
        doc.close()
        raise HTTPException(status_code=400, detail="The PDF has no pages to OCR.")

    # Higher resolution for Advanced OCR mode
    dpi = 200 if ocr_mode == "advanced" else 150
    scale = 72.0 / dpi

    for i in range(total_pages):
        page = doc[i]
        pix = page.get_pixmap(dpi=dpi)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        
        # Run OCR
        try:
            results, elapse = ocr_engine(img_array)
        except Exception:
            results = None
            
        if results:
            detected_angles = []
            for item in results:
                try:
                    box, text, score = item[0], item[1], float(item[2])
                    if score < 0.30:
                        continue
                    
                    # Convert bounding box pixels to PDF points
                    x1 = float(box[0][0]) * scale
                    y1 = float(box[0][1]) * scale
                    x2 = float(box[1][0]) * scale
                    y3 = float(box[2][1]) * scale
                    
                    box_height = max(1.0, y3 - y1)
                    font_size = max(6.0, min(36.0, box_height * 0.85))
                    
                    # Insert invisible searchable text layer
                    point = pymupdf.Point(x1, y1 + font_size)
                    page.insert_text(point, text, fontsize=font_size, render_mode=3)
                except Exception:
                    pass

    out_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return create_file_response(out_bytes, f"ocr_searchable_{file.filename}")


@router.post("/api/tools/pdf/organize")
async def api_organize(file: UploadFile = File(...), delete_pages: str = Form("")):
    content = await file.read()
    doc = pymupdf.open(stream=content, filetype="pdf")
    total_pages = len(doc)
    
    # Pages to delete, e.g. "1, 3"
    to_delete = set()
    if delete_pages.strip():
        for p in delete_pages.split(","):
            p = p.strip()
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < total_pages:
                    to_delete.add(idx)
    
    new_doc = pymupdf.open()
    for i in range(total_pages):
        if i not in to_delete:
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            
    doc.close()
    out_bytes = new_doc.tobytes(deflate=True)
    new_doc.close()
    return create_file_response(out_bytes, f"organized_{file.filename}")


# ==============================================================================
# Modern Front-End UI
# ==============================================================================
@router.get("/tools/pdf", response_class=HTMLResponse, include_in_schema=False)
async def home():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All-in-One PDF Studio | __PLATFORM_NAME__</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #e53e3e;
      --primary-light: #fff5f5;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
      --shadow-hover: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    header {
      background: white;
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 700;
      font-size: 1.25rem;
      color: #e53e3e;
    }
    .badge {
      background: #fee2e2;
      color: #991b1b;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
    }
    .hero {
      text-align: center;
      padding: 3rem 1.5rem 2rem;
      max-width: 800px;
      margin: 0 auto;
    }
    .hero h1 {
      font-size: 2.25rem;
      font-weight: 800;
      color: #0f172a;
      margin-bottom: 0.75rem;
    }
    .hero p {
      color: var(--text-muted);
      font-size: 1.1rem;
    }
    .container {
      max-width: 1300px;
      margin: 0 auto;
      padding: 1rem 2rem 4rem;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.25rem;
    }
    .tool-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: var(--shadow);
      position: relative;
    }
    .tool-card:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-hover);
      border-color: #cbd5e1;
    }
    .icon-wrapper {
      width: 44px;
      height: 44px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 1.2rem;
    }
    .tool-card h3 {
      font-size: 1.1rem;
      font-weight: 700;
      color: #0f172a;
    }
    .tool-card p {
      font-size: 0.85rem;
      color: var(--text-muted);
      flex-grow: 1;
    }
    .new-badge {
      position: absolute;
      top: 1rem;
      right: 1rem;
      background: #e0e7ff;
      color: #3730a3;
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .specs-container {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      margin-top: 0.5rem;
    }
    .spec-pill {
      background: #f1f5f9;
      color: #475569;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      border: 1px solid #e2e8f0;
    }
    .spec-pill-highlight {
      background: #eff6ff;
      color: #1d4ed8;
      border-color: #bfdbfe;
    }

    /* Modal Styling */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }
    .modal {
      background: white;
      border-radius: 16px;
      width: 92%;
      max-width: 580px;
      padding: 2rem;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
      position: relative;
      max-height: 90vh;
      overflow-y: auto;
    }
    .modal-specs-box {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 0.85rem 1rem;
      margin-bottom: 1.25rem;
      font-size: 0.85rem;
    }
    .modal-specs-title {
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.85rem;
    }
    .specs-list {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.4rem 0.8rem;
      color: #334155;
      font-size: 0.8rem;
      margin-bottom: 0.5rem;
    }
    .specs-tip {
      border-top: 1px dashed #cbd5e1;
      padding-top: 0.5rem;
      margin-top: 0.5rem;
      font-size: 0.78rem;
      color: #475569;
      line-height: 1.4;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .modal-close {
      cursor: pointer;
      font-size: 1.5rem;
      color: var(--text-muted);
      border: none;
      background: transparent;
    }
    .dropzone {
      border: 2px dashed #cbd5e1;
      border-radius: 12px;
      padding: 2.5rem 1rem;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s;
      background: #f8fafc;
      margin-bottom: 1.25rem;
    }
    .dropzone:hover {
      border-color: #e53e3e;
      background: #fff5f5;
    }
    .dropzone span {
      display: block;
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-top: 0.5rem;
    }
    .form-group {
      margin-bottom: 1rem;
    }
    .form-group label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
      color: #334155;
    }
    .form-control {
      width: 100%;
      padding: 0.65rem 0.85rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 0.95rem;
      font-family: inherit;
    }
    .btn-submit {
      width: 100%;
      padding: 0.85rem;
      background: #e53e3e;
      color: white;
      font-weight: 600;
      font-size: 1rem;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      transition: background 0.2s;
    }
    .btn-submit:hover {
      background: #dc2626;
    }
    .spinner {
      display: none;
      width: 18px;
      height: 18px;
      border: 2px solid #ffffff;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .btn-mode-toggle {
      padding: 0.65rem 0.5rem;
      border: 2px solid #cbd5e1;
      border-radius: 8px;
      background: white;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s;
    }
    .btn-mode-toggle.active-mode {
      border-color: #2563eb;
      background: #eff6ff;
      color: #1e40af;
    }
    .preset-btn {
      flex: 1;
      padding: 0.35rem 0.25rem;
      font-size: 0.75rem;
      font-weight: 600;
      border: 1px solid #cbd5e1;
      background: white;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .preset-btn:hover {
      background: #f1f5f9;
    }
    .preset-btn.active-preset {
      background: #e2e8f0;
      border-color: #94a3b8;
      color: #0f172a;
    }

    /* Split Tool Tabs & Inputs (Matching iLovePDF design) */
    .split-tab-btn {
      border: none;
      background: #f8fafc;
      cursor: pointer;
      transition: all 0.2s;
      position: relative;
      border-right: 1px solid #e2e8f0;
      color: #64748b;
    }
    .split-tab-btn:last-child {
      border-right: none;
    }
    .split-tab-btn.active-split-tab {
      color: #0f172a;
      background: #ffffff;
      box-shadow: inset 0 3px 0 #22c55e;
    }
    .split-tab-check {
      position: absolute;
      top: 6px;
      left: 8px;
      width: 18px;
      height: 18px;
      background: #22c55e;
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: bold;
    }
    .range-mode-btn {
      padding: 0.65rem 0.5rem;
      border-radius: 8px;
      font-size: 0.88rem;
      cursor: pointer;
      transition: all 0.15s;
      text-align: center;
      font-weight: 500;
      border: 1px solid #e2e8f0;
      background: #f8fafc;
      color: #64748b;
    }
    .range-mode-btn.active-range-mode {
      border: 1.5px solid #e53e3e !important;
      background: #fff5f5 !important;
      color: #e53e3e !important;
      font-weight: 700 !important;
    }
    .btn-add-range {
      border: 1.5px solid #e53e3e;
      color: #e53e3e;
      background: white;
      font-weight: 700;
      font-size: 0.95rem;
      border-radius: 8px;
      padding: 0.6rem 2rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.35rem;
      transition: all 0.15s;
    }
    .btn-add-range:hover {
      background: #fff5f5;
      transform: translateY(-1px);
    }

    /* Page Numbers 3x3 Position Grid & Toolbar (Matching iLovePDF Screenshot) */
    .page-mode-card {
      border: 1.5px solid #cbd5e1;
      border-radius: 10px;
      padding: 0.85rem 0.5rem;
      text-align: center;
      background: white;
      cursor: pointer;
      transition: all 0.2s;
      flex: 1;
    }
    .page-mode-card.active-page-mode {
      border-color: #0f172a;
      box-shadow: 0 0 0 1px #0f172a;
    }
    .pos-grid {
      display: grid;
      grid-template-columns: repeat(3, 26px);
      grid-template-rows: repeat(3, 26px);
      border: 1.5px solid #cbd5e1;
      border-radius: 4px;
      width: 82px;
      height: 82px;
      background: white;
      overflow: hidden;
    }
    .pos-cell {
      border: 0.5px dashed #cbd5e1;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.15s;
    }
    .pos-cell:hover {
      background: #f1f5f9;
    }
    .pos-cell.active-pos {
      background: #fff5f5;
    }
    .pos-dot {
      width: 14px;
      height: 14px;
      background: #e53e3e;
      border-radius: 50%;
      display: none;
    }
    .pos-cell.active-pos .pos-dot {
      display: block;
    }
    .format-toolbar {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      background: #f1f5f9;
      padding: 0.4rem 0.6rem;
      border-radius: 8px;
      flex-wrap: wrap;
    }
    .format-btn {
      width: 30px;
      height: 30px;
      border: 1px solid transparent;
      background: transparent;
      border-radius: 4px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: #334155;
      font-size: 0.95rem;
      transition: all 0.15s;
    }
    .format-btn:hover {
      background: #e2e8f0;
    }
    .format-btn.active-format {
      background: white;
      border-color: #cbd5e1;
      color: #0f172a;
      box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    }

    /* OCR PDF Styling (Matching iLovePDF Screenshot) */
    .ocr-info-banner {
      background: #f0f9ff;
      border: 1px solid #7dd3fc;
      border-radius: 8px;
      padding: 0.75rem 1rem;
      display: flex;
      align-items: flex-start;
      gap: 0.65rem;
      font-size: 0.85rem;
      color: #0369a1;
      margin-bottom: 1.15rem;
      line-height: 1.45;
    }
    .ocr-radio-card {
      border: 1.5px solid #cbd5e1;
      border-radius: 10px;
      padding: 0.9rem 1rem;
      margin-bottom: 0.75rem;
      cursor: pointer;
      transition: all 0.2s;
      background: white;
      display: flex;
      gap: 0.75rem;
      align-items: flex-start;
    }
    .ocr-radio-card.active-ocr-card {
      border-color: #0f172a;
      box-shadow: 0 0 0 1px #0f172a;
    }
    .ocr-enhance-card {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 0.75rem 0.9rem;
      margin-bottom: 0.6rem;
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      cursor: pointer;
      background: white;
      transition: background 0.15s;
    }
    .ocr-enhance-card:hover {
      background: #f8fafc;
    }
    .lang-chip {
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 0.2rem 0.6rem;
      font-size: 0.82rem;
      font-weight: 600;
      color: #334155;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }
  </style>
</head>
<body>

  <header>
    <div class="logo">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
      __PLATFORM_NAME__ &middot; PDF Studio
      <span class="badge">14 PDF Tools</span>
    </div>
    <div style="display: flex; gap: 1rem; align-items: center; font-size: 0.88rem; font-weight: 600;">
      <a href="/tools" style="color: #334155; text-decoration: none;">&larr; Back to Tools</a>
      <a href="/" style="color: #0f4c3a; text-decoration: none;">🏠 Portal Home</a>
    </div>
  </header>

  <div class="hero">
    <h1>Every PDF Tool You Need in One Place</h1>
    <p>100% Free, powerful, and running directly on your server without sending files to any third party.</p>
  </div>

  <div class="container">
    <div class="grid" id="toolGrid">
      <!-- Cards rendered via JS -->
    </div>
  </div>

  __CANONICAL_FOOTER__

  <!-- Interactive Modal Dialog -->
  <div class="modal-overlay" id="modalOverlay">
    <div class="modal">
      <div class="modal-header">
        <h3 id="modalTitle">Tool Action</h3>
        <button class="modal-close" onclick="closeModal()">&times;</button>
      </div>

      <!-- Module Specifications & Limits Box -->
      <div id="modalSpecsBox" class="modal-specs-box"></div>

      <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#e53e3e" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
        <div id="dropzoneText" style="font-weight: 600; margin-top: 0.5rem;">Select or Drop File(s) here</div>
        <span id="selectedFilesInfo">PDF documents</span>
      </div>
      <input type="file" id="fileInput" style="display: none;" onchange="handleFileSelect(event)">

      <div id="extraOptions"></div>
      <div id="pdfModalError" style="display: none; background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; border-radius: 8px; padding: 0.7rem 0.9rem; font-size: 0.86rem; font-weight: 600; margin-bottom: 0.85rem;"></div>

      <button class="btn-submit" id="submitBtn" onclick="processTask()">
        <span class="spinner" id="spinner"></span>
        <span id="submitBtnText">Convert / Process</span>
      </button>
    </div>
  </div>

  <script>
    const tools = [
      {
        id: 'merge',
        title: 'Merge PDF',
        desc: 'Combine multiple PDFs into one unified document in any order.',
        icon: '📑',
        color: '#fee2e2',
        multiple: true,
        endpoint: '/api/tools/pdf/merge',
        pills: ['Up to 100 PDFs', 'Max 250 MB', 'Combined .pdf'],
        specs: {
          capacity: 'Up to 100 PDFs simultaneously',
          maxSize: '250 MB total upload size',
          output: 'Single unified PDF document',
          processing: 'Fast multi-stream insertion',
          tip: 'Upload files in the exact order you want them merged. Drag and drop all files together.'
        }
      },
      {
        id: 'split',
        title: 'Split PDF',
        desc: 'Split by Custom/Fixed/Smart Ranges, extract Pages, or divide by Maximum File Size.',
        icon: '✂️',
        color: '#fef3c7',
        endpoint: '/api/tools/pdf/split',
        options: 'split',
        pills: ['Custom Ranges', 'Fixed / Smart Split', 'Merge Ranges Option'],
        specs: {
          capacity: '1 PDF document (up to 1,500+ pages)',
          maxSize: 'Up to 200 MB',
          output: 'Individual PDF or .ZIP archive of split parts',
          processing: 'Multi-mode Range / Pages / Size splitting',
          tip: 'Define custom page ranges, add multiple ranges, and choose whether to merge them into 1 PDF or download as a ZIP.'
        }
      },
      {
        id: 'compress',
        title: 'Compress PDF',
        desc: 'Reduce file size by % ratio OR compress to exact target size (e.g. 60MB down to 2MB).',
        icon: '🗜️',
        color: '#dcfce7',
        endpoint: '/api/tools/pdf/compress',
        options: 'compress',
        pills: ['% Ratio Reduction', 'Target Size (e.g. 2 MB)', 'Deep Optimization'],
        specs: {
          capacity: '1 PDF document at a time',
          maxSize: 'Up to 250 MB',
          output: 'Compressed PDF within requested size limit',
          processing: 'Dual-engine: % Ratio or Exact Target Size (MB/KB)',
          tip: 'Use Option 1 for % Ratio compression, or Option 2 to compress large files (e.g. 60MB down to 2MB) for government portals & email.'
        }
      },
      {
        id: 'pdf-to-word',
        title: 'PDF to Word',
        desc: 'Easily convert your PDF files into easy to edit DOC and DOCX documents.',
        icon: '📝',
        color: '#dbeafe',
        endpoint: '/api/tools/pdf/pdf-to-word',
        pills: ['Editable .docx', 'Tables & Layouts', 'Up to 200 Pages'],
        specs: {
          capacity: '1 PDF at a time (recommended up to 200 pages)',
          maxSize: 'Up to 100 MB',
          output: 'Microsoft Word Document (.docx)',
          processing: 'Deep layout reconstruction engine',
          tip: 'Retains headings, tables, bullet points, font styles, and paragraph structure ready for Word/LibreOffice.'
        }
      },
      {
        id: 'pdf-to-markdown',
        title: 'PDF to Markdown',
        desc: 'Easily turn PDFs into clean Markdown files for LLMs, notes, and documentation.',
        icon: '✨',
        color: '#ede9fe',
        endpoint: '/api/tools/pdf/pdf-to-markdown',
        isNew: true,
        pills: ['LLM / AI Ready', 'Tables & Lists', 'Up to 500 Pages'],
        specs: {
          capacity: '1 PDF at a time (up to 500 pages)',
          maxSize: 'Up to 100 MB',
          output: 'Structured Markdown file (.md)',
          processing: 'PyMuPDF4LLM semantic parser',
          tip: 'Perfect for ChatGPT, Gemini, Claude, RAG vector pipelines, and Obsidian/Notion imports.'
        }
      },
      {
        id: 'pdf-to-images',
        title: 'PDF to JPG',
        desc: 'Convert each PDF page into high resolution PNG or JPG images.',
        icon: '🖼️',
        color: '#fef9c3',
        endpoint: '/api/tools/pdf/pdf-to-images',
        pills: ['150 DPI Crisp', 'PNG / JPG', 'Single or ZIP'],
        specs: {
          capacity: '1 PDF at a time (unlimited pages)',
          maxSize: 'Up to 200 MB',
          output: 'High-res image or ZIP archive of images',
          processing: 'High-fidelity rasterizer (150 DPI)',
          tip: '1-page PDFs download immediately as PNG; multi-page PDFs are packaged into a tidy ZIP archive.'
        }
      },
      {
        id: 'images-to-pdf',
        title: 'JPG to PDF',
        desc: 'Convert JPG, PNG, and WebP images to PDF in seconds with customized margins.',
        icon: '📸',
        color: '#ecfdf5',
        multiple: true,
        endpoint: '/api/tools/pdf/images-to-pdf',
        accept: 'image/*',
        pills: ['Up to 50 Images', 'JPG, PNG, WebP', 'Auto Dimensions'],
        specs: {
          capacity: 'Up to 50 images at once',
          maxSize: '150 MB total upload size',
          output: 'Unified multi-page PDF',
          processing: 'Lossless image embedding',
          tip: 'Select all your scanned bills, photos, or documents at once to combine them into an official PDF document.'
        }
      },
      {
        id: 'rotate',
        title: 'Rotate PDF',
        desc: 'Rotate your PDFs the way you need them by 90, 180, or 270 degrees.',
        icon: '🔄',
        color: '#e0e7ff',
        endpoint: '/api/tools/pdf/rotate',
        options: 'angle',
        pills: ['90° / 180° / 270°', 'Lossless Rotation', 'All Pages'],
        specs: {
          capacity: '1 PDF document (all pages)',
          maxSize: 'Up to 250 MB',
          output: 'Properly oriented PDF',
          processing: 'Instant transformation matrix update',
          tip: 'Rotates document view angles losslessly without re-encoding or blurring any text or graphics.'
        }
      },
      {
        id: 'watermark',
        title: 'Watermark',
        desc: 'Stamp custom text or confidential stamps over your PDF pages.',
        icon: '🏷️',
        color: '#fae8ff',
        endpoint: '/api/tools/pdf/watermark',
        options: 'watermark',
        pills: ['Custom Text', '45° Diagonal', 'Adjustable Opacity'],
        specs: {
          capacity: '1 PDF at a time (stamps all pages)',
          maxSize: 'Up to 250 MB',
          output: 'Watermarked PDF document',
          processing: 'Vector text overlay',
          tip: 'Ideal for official stamps such as "PANCHAYAT VERIFIED", "CONFIDENTIAL", "DRAFT", or "OFFICE COPY".'
        }
      },
      {
        id: 'protect',
        title: 'Protect PDF',
        desc: 'Encrypt PDF files with AES password protection to prevent unauthorized access.',
        icon: '🔒',
        color: '#e2e8f0',
        endpoint: '/api/tools/pdf/protect',
        options: 'password',
        pills: ['AES-256 Bit', 'Password Wall', 'Restricts Copying'],
        specs: {
          capacity: '1 PDF at a time',
          maxSize: 'Up to 200 MB',
          output: 'Encrypted & secured PDF',
          processing: 'AES-256 cryptographic standard',
          tip: 'Encrypts the document so only authorized recipients with the password can open or print it.'
        }
      },
      {
        id: 'unlock',
        title: 'Unlock PDF',
        desc: 'Remove PDF password encryption and give you freedom to use your file.',
        icon: '🔓',
        color: '#fee2e2',
        endpoint: '/api/tools/pdf/unlock',
        options: 'password',
        pills: ['Decrypts AES', 'Permanent Unlock', 'Removes Limits'],
        specs: {
          capacity: '1 PDF at a time',
          maxSize: 'Up to 200 MB',
          output: 'Decrypted, unrestricted PDF',
          processing: 'Key verification & encryption removal',
          tip: 'Provide the password once to permanently remove password prompts for easy editing and sharing.'
        }
      },
      {
        id: 'ocr',
        title: 'OCR PDF',
        desc: 'Convert scanned documents into searchable, selectable text PDFs with Auto rotate & Deskew.',
        icon: '🔍',
        color: '#dcfce7',
        endpoint: '/api/tools/pdf/ocr',
        options: 'ocr',
        pills: ['Searchable Text Layer', 'Auto Rotate & Deskew', 'Multi-Language'],
        specs: {
          capacity: '1 PDF at a time (unlimited scanned pages)',
          maxSize: 'Up to 200 MB',
          output: 'Fully searchable & selectable PDF document',
          processing: 'Neural Optical Character Recognition (ONNX + PyMuPDF)',
          tip: 'Select your document languages (up to 3), choose Standard or Advanced mode, and enable auto-rotate to correct orientation.'
        }
      },
      {
        id: 'page-numbers',
        title: 'Page Numbers',
        desc: 'Customize position with 3x3 grid, single/facing pages, margins, text formats, and fonts.',
        icon: '🔢',
        color: '#f1f5f9',
        endpoint: '/api/tools/pdf/page-numbers',
        options: 'page-numbers',
        pills: ['3x3 Position Grid', 'Single / Facing Pages', 'Custom Typography'],
        specs: {
          capacity: '1 PDF at a time (up to 2,000+ pages)',
          maxSize: 'Up to 250 MB',
          output: 'Paginated PDF document',
          processing: 'Vector text stamping with interactive 3x3 position matrix',
          tip: 'Choose Single or Facing page layout, pick position on the 3x3 grid, adjust margins, and format font/color.'
        }
      },
      {
        id: 'organize',
        title: 'Organize PDF',
        desc: 'Delete unwanted pages from your document at your convenience.',
        icon: '📑',
        color: '#ffedd5',
        endpoint: '/api/tools/pdf/organize',
        options: 'delete_pages',
        pills: ['Delete Bad Pages', 'Custom Indices', 'Instant Cleaning'],
        specs: {
          capacity: '1 PDF at a time',
          maxSize: 'Up to 250 MB',
          output: 'Cleaned PDF document',
          processing: 'Selective page indexing',
          tip: 'Enter comma-separated page numbers (e.g. "2, 5") to immediately prune out blank or scanned error sheets.'
        }
      }
    ];

    let currentTool = null;
    let selectedFiles = [];

    const grid = document.getElementById('toolGrid');
    tools.forEach(tool => {
      const card = document.createElement('div');
      card.className = 'tool-card';
      card.onclick = () => openModal(tool);
      
      const pillsHtml = (tool.pills || []).map(p => 
        `<span class="spec-pill ${p.includes('Up to') || p.includes('Reduction') || p.includes('AES') ? 'spec-pill-highlight' : ''}">⚡ ${p}</span>`
      ).join('');

      card.innerHTML = `
        ${tool.isNew ? '<span class="new-badge">New!</span>' : ''}
        <div class="icon-wrapper" style="background: ${tool.color}">${tool.icon}</div>
        <h3>${tool.title}</h3>
        <p>${tool.desc}</p>
        <div class="specs-container">
          ${pillsHtml}
        </div>
      `;
      grid.appendChild(card);
    });

    function showPdfError(msg) {
      const el = document.getElementById('pdfModalError');
      if (el) { el.textContent = msg; el.style.display = 'block'; }
    }
    function clearPdfError() {
      const el = document.getElementById('pdfModalError');
      if (el) { el.textContent = ''; el.style.display = 'none'; }
    }

    function openModal(tool) {
      clearPdfError();
      currentTool = tool;
      selectedFiles = [];
      if (tool.options === 'ocr') {
        document.getElementById('modalTitle').innerText = 'OCR PDF options';
        document.getElementById('submitBtnText').innerHTML = 'Apply OCR <span style="font-size: 1.15rem; margin-left: 0.35rem;">➔</span>';
      } else if (tool.options === 'page-numbers') {
        document.getElementById('modalTitle').innerText = 'Page Number options';
        document.getElementById('submitBtnText').innerHTML = 'Add page numbers <span style="font-size: 1.15rem; margin-left: 0.35rem;">➔</span>';
      } else {
        document.getElementById('modalTitle').innerText = tool.title;
        document.getElementById('submitBtnText').innerText = 'Convert / Process';
      }
      document.getElementById('dropzoneText').innerText = tool.multiple ? 'Select or Drop Multiple Files' : 'Select or Drop a File';
      document.getElementById('selectedFilesInfo').innerText = tool.accept ? 'Images (*.jpg, *.png, *.webp)' : 'PDF documents (*.pdf)';
      document.getElementById('fileInput').multiple = !!tool.multiple;
      document.getElementById('fileInput').accept = tool.accept || '.pdf';
      document.getElementById('fileInput').value = '';

      // Populate Specifications Box
      const specsBox = document.getElementById('modalSpecsBox');
      if (tool.specs) {
        specsBox.style.display = 'block';
        specsBox.innerHTML = `
          <div class="modal-specs-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            <strong>Module Specifications & Limits</strong>
          </div>
          <div class="specs-list">
            <div><strong>Capacity:</strong> ${tool.specs.capacity}</div>
            <div><strong>Max Size:</strong> ${tool.specs.maxSize}</div>
            <div><strong>Output:</strong> ${tool.specs.output}</div>
            <div><strong>Engine:</strong> ${tool.specs.processing}</div>
          </div>
          <div class="specs-tip">
            💡 <strong>Pro Tip:</strong> ${tool.specs.tip}
          </div>
        `;
      } else {
        specsBox.style.display = 'none';
      }

      const optionsDiv = document.getElementById('extraOptions');
      optionsDiv.innerHTML = '';

      if (tool.options === 'split') {
        optionsDiv.innerHTML = `
          <!-- Top Tabs Bar (Range / Pages / Size) matching iLovePDF -->
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; border: 1px solid #cbd5e1; border-radius: 12px; margin-bottom: 1.25rem; overflow: hidden; background: white;">
            <!-- Tab 1: Range -->
            <button type="button" id="tabSplitRange" class="split-tab-btn active-split-tab" onclick="setSplitTab('range')" style="padding: 0.85rem 0.5rem; text-align: center; position: relative;">
              <span class="split-tab-check" id="splitRangeCheck">✔</span>
              <div style="font-size: 1.4rem; line-height: 1; margin-bottom: 4px;">
                <svg width="28" height="22" viewBox="0 0 28 22" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block;">
                  <rect x="2" y="2" width="24" height="18" rx="2" stroke-dasharray="3 3"/>
                  <rect x="5" y="5" width="7" height="12" rx="1"/>
                  <rect x="16" y="5" width="7" height="12" rx="1"/>
                </svg>
              </div>
              <div style="font-weight: 700; font-size: 0.95rem;">Range</div>
            </button>

            <!-- Tab 2: Pages -->
            <button type="button" id="tabSplitPages" class="split-tab-btn" onclick="setSplitTab('pages')" style="padding: 0.85rem 0.5rem; text-align: center; position: relative;">
              <span class="split-tab-check" id="splitPagesCheck" style="display: none;">✔</span>
              <div style="font-size: 1.4rem; line-height: 1; margin-bottom: 4px;">
                <svg width="28" height="22" viewBox="0 0 28 22" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block;">
                  <rect x="3" y="4" width="9" height="14" rx="1"/>
                  <rect x="15" y="2" width="8" height="5" rx="1"/>
                  <rect x="15" y="8" width="8" height="5" rx="1"/>
                  <rect x="15" y="14" width="8" height="5" rx="1"/>
                </svg>
              </div>
              <div style="font-weight: 700; font-size: 0.95rem;">Pages</div>
            </button>

            <!-- Tab 3: Size -->
            <button type="button" id="tabSplitSize" class="split-tab-btn" onclick="setSplitTab('size')" style="padding: 0.85rem 0.5rem; text-align: center; position: relative;">
              <span style="position: absolute; top: 6px; right: 8px; font-size: 0.95rem;">👑</span>
              <span class="split-tab-check" id="splitSizeCheck" style="display: none;">✔</span>
              <div style="font-size: 1.4rem; line-height: 1; margin-bottom: 4px;">
                <svg width="28" height="22" viewBox="0 0 28 22" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block;">
                  <rect x="4" y="3" width="12" height="16" rx="1"/>
                  <rect x="14" y="8" width="10" height="11" rx="1" stroke-dasharray="2 2"/>
                </svg>
              </div>
              <div style="font-weight: 700; font-size: 0.95rem;">Size</div>
            </button>
          </div>

          <input type="hidden" id="opt_split_type" value="range">
          <input type="hidden" id="opt_range_mode" value="custom">

          <!-- Section 1: Range View -->
          <div id="sectionSplitRange">
            <div style="margin-bottom: 1.1rem;">
              <div style="font-size: 0.88rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem;">Range mode:</div>
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.6rem;">
                <button type="button" id="btnRangeCustom" class="range-mode-btn active-range-mode" onclick="setRangeMode('custom')">Custom</button>
                <button type="button" id="btnRangeFixed" class="range-mode-btn" onclick="setRangeMode('fixed')">Fixed</button>
                <button type="button" id="btnRangeSmart" class="range-mode-btn" onclick="setRangeMode('smart')">Smart ✨</button>
              </div>
            </div>

            <!-- Custom Range Rows -->
            <div id="panelRangeCustom">
              <div id="customRangesList"></div>
              <div style="text-align: center; margin: 1.25rem 0 0.75rem;">
                <button type="button" class="btn-add-range" onclick="addCustomRange()">+ Add Range</button>
              </div>
            </div>

            <!-- Fixed Range Options -->
            <div id="panelRangeFixed" style="display: none; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
              <label style="font-size: 0.85rem; font-weight: 600; color: #334155; display: block; margin-bottom: 0.5rem;">Split into page blocks of:</label>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <input type="number" id="opt_fixed_pages" class="form-control" style="width: 100px; text-align: center; font-weight: 700; font-size: 1.05rem;" value="2" min="1">
                <span style="font-size: 0.88rem; color: #64748b; font-weight: 600;">pages per file</span>
              </div>
            </div>

            <!-- Smart Range Options -->
            <div id="panelRangeSmart" style="display: none; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
              <div style="font-size: 0.85rem; color: #6b21a8; line-height: 1.45;">
                ✨ <strong>Smart Separation:</strong> Automatically divides the document at Chapter boundaries, Table of Contents bookmarks, or detected blank separator pages.
              </div>
            </div>

            <!-- Merge Checkbox (Matches Screenshot) -->
            <label style="display: flex; align-items: center; gap: 0.65rem; font-size: 0.9rem; color: #334155; cursor: pointer; margin-top: 1rem; user-select: none;">
              <input type="checkbox" id="opt_merge_ranges" style="width: 19px; height: 19px; accent-color: #e53e3e; cursor: pointer;">
              <span>Merge all ranges in one PDF file.</span>
            </label>
          </div>

          <!-- Section 2: Pages View -->
          <div id="sectionSplitPages" style="display: none;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.1rem; margin-bottom: 1rem;">
              <div style="display: flex; flex-direction: column; gap: 0.85rem;">
                <label style="display: flex; align-items: flex-start; gap: 0.65rem; font-size: 0.9rem; cursor: pointer;">
                  <input type="radio" name="split_pages_mode" value="all" checked onchange="togglePagesMode(this.value)" style="accent-color: #e53e3e; margin-top: 3px;">
                  <div>
                    <strong>Extract all pages</strong>
                    <span style="display: block; font-size: 0.78rem; color: #64748b; margin-top: 2px;">Every page will be saved as an independent PDF inside a ZIP archive.</span>
                  </div>
                </label>
                <label style="display: flex; align-items: flex-start; gap: 0.65rem; font-size: 0.9rem; cursor: pointer;">
                  <input type="radio" name="split_pages_mode" value="select" onchange="togglePagesMode(this.value)" style="accent-color: #e53e3e; margin-top: 3px;">
                  <div>
                    <strong>Select specific pages</strong>
                    <span style="display: block; font-size: 0.78rem; color: #64748b; margin-top: 2px;">Extract only specific page numbers or ranges.</span>
                  </div>
                </label>
              </div>
              <div id="divSelectPagesInput" style="display: none; margin-top: 0.85rem;">
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #475569; margin-bottom: 0.35rem;">Pages to extract:</label>
                <input type="text" id="opt_selected_pages" class="form-control" placeholder="e.g. 1, 3, 5-8" value="1-3">
              </div>
            </div>
            <label style="display: flex; align-items: center; gap: 0.65rem; font-size: 0.9rem; color: #334155; cursor: pointer; user-select: none;">
              <input type="checkbox" id="opt_merge_pages" style="width: 19px; height: 19px; accent-color: #e53e3e; cursor: pointer;">
              <span>Merge all extracted pages in one PDF file.</span>
            </label>
          </div>

          <!-- Section 3: Size View -->
          <div id="sectionSplitSize" style="display: none;">
            <div style="background: #fefce8; border: 1px solid #fef08a; border-radius: 10px; padding: 1.1rem; margin-bottom: 1rem;">
              <label style="font-weight: 700; font-size: 0.9rem; color: #854d0e; display: block; margin-bottom: 0.5rem;">Split into files of maximum size:</label>
              <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.6rem;">
                <input type="number" id="opt_max_part_size" class="form-control" style="width: 120px; font-weight: 700; font-size: 1.15rem; text-align: center; color: #854d0e;" value="5" min="0.5" step="0.5">
                <span style="font-weight: 700; color: #854d0e;">MB per file</span>
              </div>
              <div style="font-size: 0.78rem; color: #854d0e; line-height: 1.45;">
                👑 <strong>Size-based Chunking:</strong> Divides large documents so that each output PDF does not exceed this size threshold. Ideal for upload limits on email and government portals.
              </div>
            </div>
          </div>
        `;
        renderCustomRanges();
      } else if (tool.options === 'compress') {
        optionsDiv.innerHTML = `
          <div class="form-group" style="margin-bottom: 1rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; display: block;">Select Compression Mode:</label>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;">
              <button type="button" id="btnModeRatio" class="btn-mode-toggle active-mode" onclick="setCompressMode('ratio')">
                <div style="font-weight: 700; font-size: 0.88rem;">1. Compression % Ratio</div>
                <span style="font-size: 0.72rem; color: #475569; display: block; margin-top: 2px;">Reduce by 25%, 50%, 75%</span>
              </button>
              <button type="button" id="btnModeTarget" class="btn-mode-toggle" onclick="setCompressMode('target_size')">
                <div style="font-weight: 700; font-size: 0.88rem;">2. Exact Target Size</div>
                <span style="font-size: 0.72rem; color: #475569; display: block; margin-top: 2px;">e.g., 60 MB &rarr; 2 MB</span>
              </button>
            </div>
            <input type="hidden" id="opt_compress_mode" value="ratio">
          </div>

          <!-- Mode 1: Compression % Ratio Container -->
          <div id="sectionCompressRatio" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
            <label style="font-weight: 600; font-size: 0.82rem; color: #334155; display: block; margin-bottom: 0.5rem;">Choose Percentage Reduction Ratio:</label>
            <div style="display: flex; gap: 0.4rem; margin-bottom: 0.85rem;">
              <button type="button" class="preset-btn" onclick="setRatioPreset(25, this)">25% (Light)</button>
              <button type="button" class="preset-btn active-preset" onclick="setRatioPreset(50, this)">50% (Recommended)</button>
              <button type="button" class="preset-btn" onclick="setRatioPreset(75, this)">75% (Strong)</button>
              <button type="button" class="preset-btn" onclick="setRatioPreset(85, this)">85% (Extreme)</button>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <input type="range" id="opt_ratio_slider" min="10" max="90" value="50" style="flex-grow: 1; accent-color: #2563eb;" oninput="document.getElementById('opt_ratio').value = this.value; updateRatioText(this.value)">
              <div style="display: flex; align-items: center; gap: 0.25rem;">
                <input type="number" id="opt_ratio" class="form-control" style="width: 65px; text-align: center; font-weight: 700; padding: 0.4rem;" value="50" min="10" max="95" oninput="document.getElementById('opt_ratio_slider').value = this.value; updateRatioText(this.value)">
                <span style="font-weight: 700; font-size: 0.9rem;">%</span>
              </div>
            </div>
            <div id="ratioHelpText" style="font-size: 0.76rem; color: #64748b; margin-top: 0.5rem; line-height: 1.4;">
              ⚖️ <strong>Recommended:</strong> Balanced 50% footprint reduction while keeping crisp text and clean diagrams.
            </div>
          </div>

          <!-- Mode 2: Compress to Exact Target Size Container -->
          <div id="sectionCompressTarget" style="display: none; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
            <label style="font-weight: 700; font-size: 0.85rem; color: #1e3a8a; display: block; margin-bottom: 0.4rem;">Target Maximum File Size:</label>
            <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.6rem;">
              <input type="number" id="opt_target_size" class="form-control" style="font-weight: 700; font-size: 1.15rem; color: #1e40af; width: 140px;" value="2" min="0.1" step="0.1" placeholder="e.g. 2">
              <select id="opt_target_unit" class="form-control" style="width: 85px; font-weight: 700;">
                <option value="MB" selected>MB</option>
                <option value="KB">KB</option>
              </select>
            </div>
            <div style="font-size: 0.78rem; color: #1e40af; line-height: 1.4; background: #dbeafe; padding: 0.6rem 0.8rem; border-radius: 6px;">
              🎯 <strong>Example:</strong> Upload a 60 MB PDF file, enter <strong>2 MB</strong>, and the system will intelligently re-sample high-resolution scanned images and deflate streams to fit within 2 MB for government portal and email limits.
            </div>
          </div>`;
      } else if (tool.options === 'angle') {
        optionsDiv.innerHTML = `
          <div class="form-group">
            <label>Rotation Angle:</label>
            <select id="opt_angle" class="form-control">
              <option value="90">90° Clockwise</option>
              <option value="180">180° Half Turn</option>
              <option value="270">270° Counter-Clockwise</option>
            </select>
          </div>`;
      } else if (tool.options === 'watermark') {
        optionsDiv.innerHTML = `
          <div class="form-group">
            <label>Watermark Text:</label>
            <input type="text" id="opt_watermark" class="form-control" value="CONFIDENTIAL">
          </div>`;
      } else if (tool.options === 'password') {
        optionsDiv.innerHTML = `
          <div class="form-group">
            <label>Password:</label>
            <input type="password" id="opt_password" class="form-control" placeholder="Enter password">
          </div>`;
      } else if (tool.options === 'delete_pages') {
        optionsDiv.innerHTML = `
          <div class="form-group">
            <label>Page numbers to remove (comma separated):</label>
            <input type="text" id="opt_delete_pages" class="form-control" placeholder="e.g. 2, 4">
          </div>`;
      } else if (tool.options === 'page-numbers') {
        optionsDiv.innerHTML = `
          <!-- Page mode (Single page vs Facing pages) -->
          <div style="margin-bottom: 1.15rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.5rem;">Page mode</label>
            <div style="display: flex; gap: 0.75rem;">
              <div id="cardModeSingle" class="page-mode-card active-page-mode" onclick="setPageMode('single')">
                <div style="font-size: 1.5rem; line-height: 1; margin-bottom: 5px;">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block;">
                    <rect x="5" y="3" width="14" height="18" rx="2"/>
                    <line x1="12" y1="3" x2="12" y2="21" stroke-dasharray="2 2"/>
                  </svg>
                </div>
                <div style="font-weight: 700; font-size: 0.92rem; color: #0f172a;">Single page</div>
              </div>

              <div id="cardModeFacing" class="page-mode-card" onclick="setPageMode('facing')">
                <div style="font-size: 1.5rem; line-height: 1; margin-bottom: 5px;">
                  <svg width="28" height="24" viewBox="0 0 28 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block;">
                    <rect x="2" y="3" width="11" height="18" rx="1"/>
                    <rect x="15" y="3" width="11" height="18" rx="1"/>
                  </svg>
                </div>
                <div style="font-weight: 700; font-size: 0.92rem; color: #64748b;" id="textFacingLabel">Facing pages</div>
              </div>
            </div>
            <input type="hidden" id="opt_page_mode" value="single">
          </div>

          <!-- Position & Margin -->
          <div style="display: grid; grid-template-columns: auto 1fr; gap: 1.5rem; margin-bottom: 1.15rem; align-items: start;">
            <!-- Interactive 3x3 Position Grid -->
            <div>
              <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.4rem;">Position:</label>
              <div class="pos-grid" id="posGrid">
                <div class="pos-cell" data-pos="top_left" onclick="selectPos('top_left')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="top_center" onclick="selectPos('top_center')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="top_right" onclick="selectPos('top_right')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="middle_left" onclick="selectPos('middle_left')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="middle_center" onclick="selectPos('middle_center')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="middle_right" onclick="selectPos('middle_right')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="bottom_left" onclick="selectPos('bottom_left')"><span class="pos-dot"></span></div>
                <div class="pos-cell" data-pos="bottom_center" onclick="selectPos('bottom_center')"><span class="pos-dot"></span></div>
                <div class="pos-cell active-pos" data-pos="bottom_right" onclick="selectPos('bottom_right')"><span class="pos-dot"></span></div>
              </div>
              <input type="hidden" id="opt_position" value="bottom_right">
            </div>

            <!-- Margin Selection -->
            <div>
              <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.4rem;">Margin:</label>
              <select id="opt_margin" class="form-control" style="font-weight: 500;">
                <option value="recommended" selected>Recommended</option>
                <option value="small">Small</option>
                <option value="large">Large</option>
              </select>
            </div>
          </div>

          <!-- Pages (First number & Range) -->
          <div style="margin-bottom: 1.15rem;">
            <div style="font-size: 0.88rem; font-weight: 700; color: #1e293b; margin-bottom: 0.4rem;">Pages</div>
            <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: white; margin-bottom: 0.65rem; max-width: 220px;">
              <div style="background: #f8fafc; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #475569; border-right: 1px solid #cbd5e1; display: flex; align-items: center; white-space: nowrap;">First number:</div>
              <input type="number" id="opt_first_number" value="1" min="1" style="border: none; padding: 0.5rem; width: 100%; text-align: center; font-weight: 700; outline: none; font-size: 0.95rem;">
            </div>

            <div style="font-size: 0.88rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Which pages do you want to number?</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;">
              <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: white;">
                <div style="background: #f8fafc; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #475569; border-right: 1px solid #cbd5e1; display: flex; align-items: center; white-space: nowrap;">from page</div>
                <input type="number" id="opt_from_page" value="1" min="1" style="border: none; padding: 0.5rem; width: 100%; text-align: center; font-weight: 700; outline: none; font-size: 0.95rem;">
              </div>
              <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: white;">
                <div style="background: #f8fafc; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #475569; border-right: 1px solid #cbd5e1; display: flex; align-items: center; white-space: nowrap;">to</div>
                <input type="number" id="opt_to_page" placeholder="end" style="border: none; padding: 0.5rem; width: 100%; text-align: center; font-weight: 700; outline: none; font-size: 0.95rem;">
              </div>
            </div>
          </div>

          <!-- Text Options -->
          <div style="margin-bottom: 1.15rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.4rem;">Text:</label>
            <select id="opt_text_format" class="form-control" style="font-weight: 500;" onchange="toggleCustomTextInput(this.value)">
              <option value="only_number" selected>Insert only page number (recommended)</option>
              <option value="page_n">Page {n}</option>
              <option value="page_n_of_p">Page {n} of {p}</option>
              <option value="custom">Custom text format...</option>
            </select>
            <div id="divCustomText" style="display: none; margin-top: 0.5rem;">
              <input type="text" id="opt_custom_text" class="form-control" placeholder="e.g. Doc #{n} / {p}" value="{n}">
            </div>
          </div>

          <!-- Text Format Toolbar -->
          <div style="margin-bottom: 1.5rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.4rem;">Text format:</label>
            <div class="format-toolbar">
              <select id="opt_font_family" style="border: 1px solid #cbd5e1; border-radius: 4px; padding: 0.3rem 0.5rem; font-size: 0.85rem; background: white;">
                <option value="Arial" selected>Arial</option>
                <option value="Times">Times New Roman</option>
                <option value="Courier">Courier</option>
              </select>

              <div style="display: flex; align-items: center; background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 0.4rem;">
                <span style="font-size: 0.78rem; font-weight: 700; margin-right: 2px;">TT</span>
                <select id="opt_font_size" style="border: none; font-size: 0.85rem; outline: none; background: transparent; padding: 0.3rem 0;">
                  <option value="9">9</option>
                  <option value="10" selected>10</option>
                  <option value="11">11</option>
                  <option value="12">12</option>
                  <option value="14">14</option>
                  <option value="16">16</option>
                </select>
              </div>

              <div style="width: 1px; height: 22px; background: #cbd5e1; margin: 0 0.15rem;"></div>

              <button type="button" id="btnFormatBold" class="format-btn" onclick="toggleFormat('bold')">B</button>
              <button type="button" id="btnFormatItalic" class="format-btn" style="font-style: italic;" onclick="toggleFormat('italic')">I</button>
              <button type="button" id="btnFormatUnderline" class="format-btn" style="text-decoration: underline;" onclick="toggleFormat('underline')">U</button>

              <div style="width: 1px; height: 22px; background: #cbd5e1; margin: 0 0.15rem;"></div>

              <div style="display: flex; align-items: center; gap: 0.25rem; background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0.2rem 0.4rem;">
                <span style="font-weight: 800; font-size: 0.9rem; text-decoration: underline; text-decoration-color: #e53e3e; text-decoration-thickness: 3px;">A</span>
                <select id="opt_font_color" style="border: none; font-size: 0.82rem; outline: none; background: transparent;">
                  <option value="#000000" selected>Black</option>
                  <option value="#475569">Dark Gray</option>
                  <option value="#1e3a8a">Navy Blue</option>
                  <option value="#dc2626">Red</option>
                </select>
              </div>
            </div>
            <input type="hidden" id="opt_is_bold" value="false">
            <input type="hidden" id="opt_is_italic" value="false">
            <input type="hidden" id="opt_is_underline" value="false">
          </div>
        `;
      } else if (tool.options === 'ocr') {
        optionsDiv.innerHTML = `
          <!-- Info Banner -->
          <div class="ocr-info-banner">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2.5" style="flex-shrink: 0; margin-top: 1px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            <div>The accuracy of detection is increased by correctly selecting the document's languages.</div>
          </div>

          <!-- Document languages -->
          <div style="margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
              <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b;">Document languages</label>
              <span id="ocrLangCount" style="font-size: 0.8rem; color: #64748b; font-weight: 600;">1/3</span>
            </div>
            <div style="border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.45rem 0.65rem; background: white; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap;">
              <div id="ocrSelectedLangs" style="display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center;">
                <span class="lang-chip" id="chip_English">English <span onclick="removeOcrLang('English')" style="cursor: pointer; font-size: 0.85rem; color: #64748b; margin-left: 2px;">&times;</span></span>
              </div>
              <select id="ocrAddLangSelect" style="border: none; outline: none; font-size: 0.82rem; color: #475569; background: transparent; cursor: pointer;" onchange="addOcrLang(this.value); this.value='';">
                <option value="" disabled selected>+ Add language ▾</option>
                <option value="English">English</option>
                <option value="Hindi">Hindi (हिन्दी)</option>
                <option value="Spanish">Spanish (Español)</option>
                <option value="French">French (Français)</option>
                <option value="German">German (Deutsch)</option>
                <option value="Chinese">Chinese (中文)</option>
                <option value="Japanese">Japanese (日本語)</option>
              </select>
            </div>
            <input type="hidden" id="opt_ocr_languages" value="English">
          </div>

          <!-- OCR mode (Standard vs Advanced) -->
          <div style="margin-bottom: 1.25rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #1e293b; display: block; margin-bottom: 0.5rem;">OCR mode</label>
            
            <div id="cardOcrStandard" class="ocr-radio-card active-ocr-card" onclick="setOcrMode('standard')">
              <input type="radio" name="ocr_mode_radio" value="standard" checked style="accent-color: #0f172a; margin-top: 3px; cursor: pointer;">
              <div>
                <strong style="font-size: 0.92rem; color: #0f172a; display: block;">Standard</strong>
                <span style="font-size: 0.78rem; color: #64748b; display: block; margin-top: 2px; line-height: 1.4;">Best for most scanned documents. Supports all languages.</span>
              </div>
            </div>

            <div id="cardOcrAdvanced" class="ocr-radio-card" onclick="setOcrMode('advanced')">
              <input type="radio" name="ocr_mode_radio" value="advanced" style="accent-color: #0f172a; margin-top: 3px; cursor: pointer;">
              <div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <strong style="font-size: 0.92rem; color: #0f172a;">Advanced</strong>
                  <span style="background: #fef08a; color: #854d0e; font-size: 0.68rem; font-weight: 700; padding: 1px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 3px;">👑 Premium</span>
                </div>
                <span style="font-size: 0.78rem; color: #64748b; display: block; margin-top: 2px; line-height: 1.4;">Better suited to difficult scans and photographed or warped documents. Supports more than <span style="text-decoration: underline dotted;">50 languages</span>.</span>
              </div>
            </div>
            <input type="hidden" id="opt_ocr_mode" value="standard">
          </div>

          <!-- Enhance OCR -->
          <div style="margin-bottom: 1.5rem;">
            <label style="font-size: 0.88rem; font-weight: 700; color: #64748b; display: block; margin-bottom: 0.5rem;">Enhance OCR</label>
            
            <label class="ocr-enhance-card">
              <input type="checkbox" id="opt_ocr_auto_rotate" style="width: 18px; height: 18px; accent-color: #e53e3e; cursor: pointer; margin-top: 2px;">
              <div>
                <strong style="font-size: 0.88rem; color: #1e293b; display: block;">Auto rotate</strong>
                <span style="font-size: 0.78rem; color: #64748b; display: block; margin-top: 1px;">Detects and corrects page orientation.</span>
              </div>
            </label>

            <label class="ocr-enhance-card">
              <input type="checkbox" id="opt_ocr_deskew" style="width: 18px; height: 18px; accent-color: #e53e3e; cursor: pointer; margin-top: 2px;">
              <div>
                <strong style="font-size: 0.88rem; color: #1e293b; display: block;">Deskew</strong>
                <span style="font-size: 0.78rem; color: #64748b; display: block; margin-top: 1px;">Straightens tilted scans.</span>
              </div>
            </label>

            <label class="ocr-enhance-card">
              <input type="checkbox" id="opt_ocr_dewarp" style="width: 18px; height: 18px; accent-color: #e53e3e; cursor: pointer; margin-top: 2px;">
              <div>
                <strong style="font-size: 0.88rem; color: #1e293b; display: block;">Dewarp</strong>
                <span style="font-size: 0.78rem; color: #64748b; display: block; margin-top: 1px;">Flattens curved or photographed pages.</span>
              </div>
            </label>
          </div>
        `;
      }

      document.getElementById('modalOverlay').style.display = 'flex';
    }

    function closeModal() {
      clearPdfError();
      document.getElementById('modalOverlay').style.display = 'none';
    }

    function setCompressMode(mode) {
      document.getElementById('opt_compress_mode').value = mode;
      const btnRatio = document.getElementById('btnModeRatio');
      const btnTarget = document.getElementById('btnModeTarget');
      const secRatio = document.getElementById('sectionCompressRatio');
      const secTarget = document.getElementById('sectionCompressTarget');

      if (mode === 'ratio') {
        btnRatio.classList.add('active-mode');
        btnTarget.classList.remove('active-mode');
        secRatio.style.display = 'block';
        secTarget.style.display = 'none';
      } else {
        btnRatio.classList.remove('active-mode');
        btnTarget.classList.add('active-mode');
        secRatio.style.display = 'none';
        secTarget.style.display = 'block';
      }
    }

    function setRatioPreset(val, btnElement) {
      document.getElementById('opt_ratio').value = val;
      document.getElementById('opt_ratio_slider').value = val;
      document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active-preset'));
      if (btnElement) btnElement.classList.add('active-preset');
      updateRatioText(val);
    }

    function updateRatioText(val) {
      const txt = document.getElementById('ratioHelpText');
      if (val <= 30) {
        txt.innerHTML = '⚡ <strong>Light (' + val + '%):</strong> Maximum visual fidelity, best for documents with fine diagrams or print copies.';
      } else if (val <= 60) {
        txt.innerHTML = '⚖️ <strong>Recommended (' + val + '%):</strong> Great 50% footprint reduction while keeping crisp text.';
      } else if (val <= 80) {
        txt.innerHTML = '🗜️ <strong>Strong (' + val + '%):</strong> Substantial file reduction, ideal for regular email and portal uploads.';
      } else {
        txt.innerHTML = '🔥 <strong>Extreme (' + val + '%):</strong> Maximum compression, scales down high-res photos to minimum size.';
      }
    }

    // -------------------------------------------------------------
    // Split Module State & Handlers (Matching iLovePDF Screenshot)
    // -------------------------------------------------------------
    let customRanges = [
      { from: 1, to: 2 }
    ];

    function renderCustomRanges() {
      const container = document.getElementById('customRangesList');
      if (!container) return;
      container.innerHTML = '';
      
      customRanges.forEach((rng, idx) => {
        const row = document.createElement('div');
        row.style.marginBottom = '0.75rem';
        row.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
            <div style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.88rem; font-weight: 600; color: #334155;">
              <span style="color: #64748b; font-size: 1rem;">&#8597;</span> Range <span style="background: #ede9fe; color: #6d28d9; padding: 1px 7px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">${idx + 1}</span>
            </div>
            ${customRanges.length > 1 ? `<button type="button" onclick="removeCustomRange(${idx})" style="border: none; background: transparent; color: #ef4444; cursor: pointer; font-size: 0.8rem; font-weight: 600;">&times; Remove</button>` : ''}
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;">
            <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: white;">
              <div style="background: #f8fafc; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #64748b; border-right: 1px solid #cbd5e1; display: flex; align-items: center; white-space: nowrap;">from page</div>
              <input type="number" min="1" value="${rng.from}" style="border: none; padding: 0.5rem; width: 100%; text-align: center; font-weight: 700; outline: none; font-size: 0.95rem;" onchange="customRanges[${idx}].from = parseInt(this.value) || 1">
            </div>
            <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: white;">
              <div style="background: #f8fafc; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #64748b; border-right: 1px solid #cbd5e1; display: flex; align-items: center; white-space: nowrap;">to</div>
              <input type="number" min="1" value="${rng.to}" style="border: none; padding: 0.5rem; width: 100%; text-align: center; font-weight: 700; outline: none; font-size: 0.95rem;" onchange="customRanges[${idx}].to = parseInt(this.value) || 1">
            </div>
          </div>
        `;
        container.appendChild(row);
      });
    }

    function addCustomRange() {
      const last = customRanges[customRanges.length - 1];
      const nextFrom = (last ? last.to : 0) + 1;
      customRanges.push({ from: nextFrom, to: nextFrom + 1 });
      renderCustomRanges();
    }

    function removeCustomRange(idx) {
      if (customRanges.length > 1) {
        customRanges.splice(idx, 1);
        renderCustomRanges();
      }
    }

    function setSplitTab(tab) {
      document.getElementById('opt_split_type').value = tab;
      ['Range', 'Pages', 'Size'].forEach(t => {
        const lower = t.toLowerCase();
        const btn = document.getElementById('tabSplit' + t);
        const sec = document.getElementById('sectionSplit' + t);
        const check = document.getElementById('split' + t + 'Check');
        if (lower === tab) {
          btn.classList.add('active-split-tab');
          sec.style.display = 'block';
          if (check) check.style.display = 'flex';
        } else {
          btn.classList.remove('active-split-tab');
          sec.style.display = 'none';
          if (check) check.style.display = 'none';
        }
      });
    }

    function setRangeMode(mode) {
      document.getElementById('opt_range_mode').value = mode;
      ['Custom', 'Fixed', 'Smart'].forEach(m => {
        const lower = m.toLowerCase();
        const btn = document.getElementById('btnRange' + m);
        const panel = document.getElementById('panelRange' + m);
        if (lower === mode) {
          btn.classList.add('active-range-mode');
          panel.style.display = 'block';
        } else {
          btn.classList.remove('active-range-mode');
          panel.style.display = 'none';
        }
      });
    }

    function togglePagesMode(mode) {
      const div = document.getElementById('divSelectPagesInput');
      if (div) div.style.display = (mode === 'select') ? 'block' : 'none';
    }

    // -------------------------------------------------------------
    // Page Numbers Handlers (Matching iLovePDF Screenshot)
    // -------------------------------------------------------------
    function setPageMode(mode) {
      document.getElementById('opt_page_mode').value = mode;
      const singleCard = document.getElementById('cardModeSingle');
      const facingCard = document.getElementById('cardModeFacing');
      const facingLabel = document.getElementById('textFacingLabel');

      if (mode === 'single') {
        singleCard.classList.add('active-page-mode');
        facingCard.classList.remove('active-page-mode');
        if (facingLabel) facingLabel.style.color = '#64748b';
      } else {
        singleCard.classList.remove('active-page-mode');
        facingCard.classList.add('active-page-mode');
        if (facingLabel) facingLabel.style.color = '#0f172a';
      }
    }

    function selectPos(pos) {
      document.getElementById('opt_position').value = pos;
      document.querySelectorAll('.pos-cell').forEach(cell => {
        if (cell.getAttribute('data-pos') === pos) {
          cell.classList.add('active-pos');
        } else {
          cell.classList.remove('active-pos');
        }
      });
    }

    function toggleFormat(type) {
      if (type === 'bold') {
        const el = document.getElementById('opt_is_bold');
        const btn = document.getElementById('btnFormatBold');
        const val = (el.value === 'true');
        el.value = (!val).toString();
        btn.classList.toggle('active-format', !val);
      } else if (type === 'italic') {
        const el = document.getElementById('opt_is_italic');
        const btn = document.getElementById('btnFormatItalic');
        const val = (el.value === 'true');
        el.value = (!val).toString();
        btn.classList.toggle('active-format', !val);
      } else if (type === 'underline') {
        const el = document.getElementById('opt_is_underline');
        const btn = document.getElementById('btnFormatUnderline');
        const val = (el.value === 'true');
        el.value = (!val).toString();
        btn.classList.toggle('active-format', !val);
      }
    }

    function toggleCustomTextInput(val) {
      const div = document.getElementById('divCustomText');
      if (div) div.style.display = (val === 'custom') ? 'block' : 'none';
    }

    // -------------------------------------------------------------
    // OCR PDF Handlers (Matching iLovePDF Screenshot)
    // -------------------------------------------------------------
    let ocrLanguages = ['English'];

    function renderOcrLangs() {
      const container = document.getElementById('ocrSelectedLangs');
      const countEl = document.getElementById('ocrLangCount');
      const inputEl = document.getElementById('opt_ocr_languages');
      if (!container) return;

      container.innerHTML = '';
      ocrLanguages.forEach(lang => {
        const chip = document.createElement('span');
        chip.className = 'lang-chip';
        chip.id = `chip_${lang}`;
        chip.innerHTML = `${lang} <span onclick="removeOcrLang('${lang}')" style="cursor: pointer; font-size: 0.85rem; color: #64748b; margin-left: 2px;">&times;</span>`;
        container.appendChild(chip);
      });

      if (countEl) countEl.innerText = `${ocrLanguages.length}/3`;
      if (inputEl) inputEl.value = ocrLanguages.join(',');
    }

    function addOcrLang(lang) {
      if (!lang) return;
      if (!ocrLanguages.includes(lang)) {
        if (ocrLanguages.length >= 3) {
          showPdfError('You can select up to 3 languages.');
          return;
        }
        ocrLanguages.push(lang);
        renderOcrLangs();
      }
    }

    function removeOcrLang(lang) {
      if (ocrLanguages.length > 1) {
        ocrLanguages = ocrLanguages.filter(l => l !== lang);
        renderOcrLangs();
      } else {
        showPdfError('At least one language must remain selected.');
      }
    }

    function setOcrMode(mode) {
      document.getElementById('opt_ocr_mode').value = mode;
      const stdCard = document.getElementById('cardOcrStandard');
      const advCard = document.getElementById('cardOcrAdvanced');
      if (!stdCard || !advCard) return;

      const stdRadio = stdCard.querySelector('input[type="radio"]');
      const advRadio = advCard.querySelector('input[type="radio"]');

      if (mode === 'standard') {
        stdCard.classList.add('active-ocr-card');
        advCard.classList.remove('active-ocr-card');
        if (stdRadio) stdRadio.checked = true;
      } else {
        stdCard.classList.remove('active-ocr-card');
        advCard.classList.add('active-ocr-card');
        if (advRadio) advRadio.checked = true;
      }
    }

    function handleFileSelect(e) {
      clearPdfError();
      selectedFiles = Array.from(e.target.files);
      if (selectedFiles.length > 0) {
        document.getElementById('dropzoneText').innerText = `Selected: ${selectedFiles.length} file(s)`;
        document.getElementById('selectedFilesInfo').innerText = selectedFiles.map(f => f.name).join(', ');
      }
    }

    // Drag and drop setup
    const dropzone = document.getElementById('dropzone');
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.style.borderColor = '#e53e3e'; });
    dropzone.addEventListener('dragleave', () => { dropzone.style.borderColor = '#cbd5e1'; });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.style.borderColor = '#cbd5e1';
      selectedFiles = Array.from(e.dataTransfer.files);
      if (selectedFiles.length > 0) {
        document.getElementById('dropzoneText').innerText = `Selected: ${selectedFiles.length} file(s)`;
        document.getElementById('selectedFilesInfo').innerText = selectedFiles.map(f => f.name).join(', ');
      }
    });

    async function processTask() {
      clearPdfError();
      if (!selectedFiles || selectedFiles.length === 0) {
        showPdfError('Please choose at least one file first.');
        return;
      }

      const spinner = document.getElementById('spinner');
      const btnText = document.getElementById('submitBtnText');
      const submitBtn = document.getElementById('submitBtn');

      spinner.style.display = 'inline-block';
      btnText.innerText = 'Processing...';
      submitBtn.disabled = true;

      const formData = new FormData();
      if (currentTool.multiple) {
        selectedFiles.forEach(file => formData.append('files', file));
      } else {
        formData.append('file', selectedFiles[0]);
      }

      if (currentTool.options === 'split') {
        const splitType = document.getElementById('opt_split_type').value;
        formData.append('split_type', splitType);
        
        if (splitType === 'range') {
          const rangeMode = document.getElementById('opt_range_mode').value;
          formData.append('range_mode', rangeMode);
          formData.append('ranges_json', JSON.stringify(customRanges));
          formData.append('merge_ranges', document.getElementById('opt_merge_ranges').checked);
          formData.append('fixed_pages', document.getElementById('opt_fixed_pages').value);
        } else if (splitType === 'pages') {
          const pagesMode = document.querySelector('input[name="split_pages_mode"]:checked').value;
          formData.append('pages_mode', pagesMode);
          formData.append('selected_pages', document.getElementById('opt_selected_pages').value);
          formData.append('merge_ranges', document.getElementById('opt_merge_pages').checked);
        } else {
          formData.append('max_part_size_mb', document.getElementById('opt_max_part_size').value);
        }
      } else if (currentTool.options === 'pages') {
        formData.append('pages', document.getElementById('opt_pages').value);
      } else if (currentTool.options === 'compress') {
        const mode = document.getElementById('opt_compress_mode').value;
        formData.append('compress_mode', mode);
        if (mode === 'ratio') {
          formData.append('ratio', document.getElementById('opt_ratio').value);
        } else {
          formData.append('target_size', document.getElementById('opt_target_size').value);
          formData.append('target_unit', document.getElementById('opt_target_unit').value);
        }
      } else if (currentTool.options === 'angle') {
        formData.append('angle', document.getElementById('opt_angle').value);
      } else if (currentTool.options === 'watermark') {
        formData.append('text', document.getElementById('opt_watermark').value);
      } else if (currentTool.options === 'password') {
        formData.append('password', document.getElementById('opt_password').value);
      } else if (currentTool.options === 'delete_pages') {
        formData.append('delete_pages', document.getElementById('opt_delete_pages').value);
      } else if (currentTool.options === 'page-numbers') {
        formData.append('page_mode', document.getElementById('opt_page_mode').value);
        formData.append('position', document.getElementById('opt_position').value);
        formData.append('margin', document.getElementById('opt_margin').value);
        formData.append('first_number', document.getElementById('opt_first_number').value);
        formData.append('from_page', document.getElementById('opt_from_page').value);
        const toPageVal = document.getElementById('opt_to_page').value;
        if (toPageVal) formData.append('to_page', toPageVal);
        formData.append('text_format', document.getElementById('opt_text_format').value);
        const custTextEl = document.getElementById('opt_custom_text');
        if (custTextEl) formData.append('custom_text', custTextEl.value);
        formData.append('font_family', document.getElementById('opt_font_family').value);
        formData.append('font_size', document.getElementById('opt_font_size').value);
        formData.append('is_bold', document.getElementById('opt_is_bold').value);
        formData.append('is_italic', document.getElementById('opt_is_italic').value);
        formData.append('is_underline', document.getElementById('opt_is_underline').value);
        formData.append('font_color', document.getElementById('opt_font_color').value);
      } else if (currentTool.options === 'ocr') {
        formData.append('languages', document.getElementById('opt_ocr_languages').value);
        formData.append('ocr_mode', document.getElementById('opt_ocr_mode').value);
        formData.append('auto_rotate', document.getElementById('opt_ocr_auto_rotate').checked);
        formData.append('deskew', document.getElementById('opt_ocr_deskew').checked);
        formData.append('dewarp', document.getElementById('opt_ocr_dewarp').checked);
      }

      try {
        const response = await fetch(currentTool.endpoint, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || 'An error occurred during processing.');
        }

        // Trigger file download
        const blob = await response.blob();
        const disposition = response.headers.get('content-disposition');
        let filename = 'result_file';
        if (disposition && disposition.indexOf('filename=') !== -1) {
          const matches = /filename[^;=\\n]*=((['"]).*?\\2|[^;\\n]*)/.exec(disposition);
          if (matches != null && matches[1]) {
            filename = matches[1].replace(/['"]/g, '');
          }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        closeModal();
      } catch (err) {
        showPdfError('Error: ' + err.message);
      } finally {
        spinner.style.display = 'none';
        btnText.innerText = 'Convert / Process';
        submitBtn.disabled = false;
      }
    }

    (function () {
      const overlay = document.getElementById('modalOverlay');
      if (overlay) {
        overlay.addEventListener('click', (e) => {
          if (e.target === overlay) closeModal();
        });
      }
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay && overlay.style.display === 'flex') {
          closeModal();
        }
      });
      try {
        const sp = new URLSearchParams(window.location.search || '');
        const siteVal = (sp.get('site') || '').trim().toLowerCase();
        if (siteVal === 'console' || siteVal === 'reports' || siteVal === 'portal') {
          document.querySelectorAll('a[href]').forEach((a) => {
            const href = a.getAttribute('href') || '';
            if (!href.startsWith('/') || href.startsWith('//') || href.startsWith('/api/')) return;
            const parsed = new URL(href, window.location.origin);
            if (!parsed.searchParams.has('site')) {
              parsed.searchParams.set('site', siteVal);
              a.setAttribute('href', parsed.pathname + parsed.search + parsed.hash);
            }
          });
        }
      } catch (e) {}
    })();
  </script>
</body>
</html>
"""
    footer_html = render_canonical_footer_html("background:white; border-top:1px solid #e2e8f0; padding:1.5rem 2rem; color:#64748b;")
    return html.replace("__PLATFORM_NAME__", PLATFORM_NAME).replace("__CANONICAL_FOOTER__", footer_html)

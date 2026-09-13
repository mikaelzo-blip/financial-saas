"""PDF rasterization module using pypdfium2.

Provides bounded, page-by-page rendering of PDF pages to PIL Images at configurable DPI,
ensuring memory remains strictly bounded even for multipage documents.
"""
from pathlib import Path
from typing import Generator
from PIL import Image
import pypdfium2 as pdfium

from src.services.documents.exceptions import PdfRenderError, InvalidFileError


def open_pdf_document(path: Path | bytes) -> pdfium.PdfDocument:
    """Opens a PDF document safely using pypdfium2."""
    try:
        if isinstance(path, Path):
            return pdfium.PdfDocument(str(path))
        return pdfium.PdfDocument(path)
    except Exception as exc:
        err_msg = str(exc).lower()
        if "password" in err_msg or "encrypted" in err_msg:
            raise InvalidFileError("Password-protected PDF cannot be processed") from exc
        raise InvalidFileError(f"Corrupted or unreadable PDF: {exc}") from exc


def render_pdf_page_to_image(
    doc: pdfium.PdfDocument,
    page_index: int,
    dpi: int = 200,
) -> Image.Image:
    """Renders a single PDF page to a PIL Image at specified DPI.
    
    Standard PDF coordinate system is 72 points per inch.
    Scale factor = dpi / 72.0 (e.g. 200 DPI -> ~2.778 scale).
    """
    try:
        page = doc.get_page(page_index)
        scale = max(72, dpi) / 72.0
        # render returns a PdfBitmap which can convert directly to PIL Image
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        return image
    except Exception as exc:
        raise PdfRenderError(f"Failed to rasterize PDF page {page_index + 1}: {exc}") from exc


def iter_pdf_pages_as_images(
    path: Path,
    max_pages: int = 50,
    dpi: int = 200,
) -> Generator[tuple[int, Image.Image], None, None]:
    """Generates (page_number_1_indexed, PIL_Image) one page at a time.
    
    Ensures memory is strictly bounded and deterministic page ordering (1, 2, ..., N).
    """
    doc = open_pdf_document(path)
    try:
        total_pages = len(doc)
        limit = min(total_pages, max_pages)
        for i in range(limit):
            img = render_pdf_page_to_image(doc, i, dpi=dpi)
            yield i + 1, img
    finally:
        doc.close()

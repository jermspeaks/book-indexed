"""
Extract TOC and index raw text from a PDF using PyMuPDF (fitz).
User specifies TOC page range and index page range via CLI.
"""
from pathlib import Path
from typing import Any


def extract_pdf(
    pdf_path: str | Path,
    toc_start_page: int,
    toc_end_page: int,
    index_start_page: int,
    index_end_page: int,
) -> dict[str, Any]:
    """
    Extract raw text from TOC and index page ranges.
    Returns:
        toc_raw: str
        index_raw: str
        page_count: int
    """
    import fitz  # PyMuPDF

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    page_count = len(doc)

    def extract_range(start: int, end: int) -> str:
        if start < 1:
            start = 1
        if end > page_count:
            end = page_count
        if start > end:
            return ""
        parts = []
        for i in range(start - 1, end):
            page = doc[i]
            parts.append(page.get_text("text"))
        return "\n".join(parts)

    toc_raw = extract_range(toc_start_page, toc_end_page)
    index_raw = extract_range(index_start_page, index_end_page)
    doc.close()

    return {
        "toc_raw": toc_raw,
        "index_raw": index_raw,
        "page_count": page_count,
    }

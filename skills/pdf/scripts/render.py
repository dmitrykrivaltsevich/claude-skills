#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Render PDF pages to high-DPI PNG images — outputs JSON manifest to stdout.

This script bridges binary PDF and LLM vision. Two primary uses:

1. **OCR via LLM vision**: scanned PDFs with no text layer get rendered to
   high-resolution PNGs. The LLM reads them via its multimodal vision, which
   handles complex layouts, tables, handwriting, and diagrams better than
   traditional OCR engines.

2. **Visual QA**: after write.py produces a PDF, render a page to verify the
   output looks correct before delivering to the user.

Default DPI is 400 — high enough for the LLM to read small text clearly.

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition

# Default rendering resolution.
# 400 DPI gives the LLM enough detail to read small text and table cells
# while keeping file sizes reasonable (~1-3 MB per page for typical A4).
DEFAULT_DPI = 400  # dots per inch — balances quality vs file size for LLM vision


@precondition(
    lambda pdf_path, **_: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path, **_: os.path.isfile(pdf_path),
    "PDF path does not exist",
)
@precondition(
    lambda pdf_path, output_dir, dpi=DEFAULT_DPI, **_: dpi >= 72,
    "DPI must be >= 72",
)
def render_pages(
    pdf_path: str,
    output_dir: str,
    page_start: int | None = None,
    page_end: int | None = None,
    dpi: int = DEFAULT_DPI,
) -> dict:
    """Render PDF pages to PNG images at the specified DPI."""
    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        start = (page_start - 1) if page_start else 0
        end = page_end if page_end else total_pages

        # Zoom factor: pymupdf default is 72 DPI
        zoom = dpi / 72
        mat = pymupdf.Matrix(zoom, zoom)

        pages = []
        for i in range(start, min(end, total_pages)):
            print(f"Rendering page {i + 1}/{total_pages} at {dpi} DPI...", file=sys.stderr)
            page = doc[i]
            pix = page.get_pixmap(matrix=mat)

            filename = f"page_{i + 1:04d}.png"
            filepath = os.path.join(output_dir, filename)
            pix.save(filepath)

            file_size = os.path.getsize(filepath)
            pages.append({
                "number": i + 1,
                "path": filepath,
                "width": pix.width,
                "height": pix.height,
                "file_size_bytes": file_size,
            })

        return {
            "file_path": pdf_path,
            "output_dir": output_dir,
            "dpi": dpi,
            "total_pages_in_pdf": total_pages,
            "pages_rendered": len(pages),
            "pages": pages,
        }
    finally:
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render PDF pages to PNG images")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output-dir", required=True, help="Directory to save PNGs")
    parser.add_argument("--page-start", type=int, default=None, help="First page (1-based)")
    parser.add_argument("--page-end", type=int, default=None, help="Last page (1-based)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="Resolution (default: 400)")
    args = parser.parse_args()

    try:
        result = render_pages(args.pdf_path, args.output_dir, args.page_start, args.page_end, args.dpi)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

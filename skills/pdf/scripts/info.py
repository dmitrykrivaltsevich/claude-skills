#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyMuPDF >= 1.25",
# ]
# ///
"""PDF metadata and structural analysis — outputs JSON to stdout.

Extracts title, author, page count, TOC, and per-page analysis
(has_text, has_images, dimensions). The LLM uses this to decide
which pages to read, render, or extract images from.

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(__file__))
from contracts import check_file_readable, precondition


@precondition(
    lambda pdf_path: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path: check_file_readable(pdf_path),
    "PDF file is not readable",
)
def get_info(pdf_path: str) -> dict:
    """Extract metadata, TOC, and per-page structural analysis."""
    doc = pymupdf.open(pdf_path)
    try:
        meta = doc.metadata or {}
        toc_raw = doc.get_toc()
        toc = [
            {"level": entry[0], "title": entry[1], "page": entry[2]}
            for entry in toc_raw
        ]

        pages = []
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text("text").strip()
            images = page.get_images()
            pages.append({
                "number": i + 1,
                "has_text": len(text) > 0,
                "has_images": len(images) > 0,
                "width": round(page.rect.width, 1),
                "height": round(page.rect.height, 1),
                "word_count": len(text.split()) if text else 0,
            })

        file_size = os.path.getsize(pdf_path)

        return {
            "file_path": pdf_path,
            "file_size_bytes": file_size,
            "page_count": len(doc),
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "toc": toc,
            "pages": pages,
        }
    finally:
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract PDF metadata and structure")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    args = parser.parse_args()

    try:
        result = get_info(args.pdf_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

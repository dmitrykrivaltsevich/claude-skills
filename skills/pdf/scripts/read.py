#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyMuPDF >= 1.25",
#   "pymupdf4llm >= 0.0.17",
# ]
# ///
"""Extract PDF pages as markdown — outputs JSON to stdout.

Uses pymupdf4llm for high-quality markdown conversion that preserves
headings, tables, lists, and layout structure. Supports page ranges
for working with large documents (thousands of pages).

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pymupdf
import pymupdf4llm

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition


@precondition(
    lambda pdf_path, **_: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path, **_: os.path.isfile(pdf_path),
    "PDF path does not exist",
)
@precondition(
    lambda pdf_path, page_start=1, **_: page_start >= 1,
    "page_start must be >= 1",
)
@precondition(
    lambda pdf_path, page_start=1, page_end=None, **_: page_end is None or page_end >= page_start,
    "page_end must be >= start",
)
def read_pages(
    pdf_path: str,
    page_start: int = 1,
    page_end: int | None = None,
) -> dict:
    """Extract pages as markdown with word counts."""
    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)

        # Clamp end to actual page count
        effective_end = min(page_end, total_pages) if page_end is not None else total_pages

        # pymupdf4llm uses 0-based page indices
        page_indices = list(range(page_start - 1, effective_end))

        pages = []
        for idx in page_indices:
            print(f"Reading page {idx + 1}/{total_pages}...", file=sys.stderr)
            md = pymupdf4llm.to_markdown(
                pdf_path,
                pages=[idx],
            )
            word_count = len(md.split()) if md.strip() else 0
            pages.append({
                "number": idx + 1,
                "markdown": md,
                "word_count": word_count,
            })

        return {
            "file_path": pdf_path,
            "total_pages": total_pages,
            "pages_returned": f"{page_start}-{effective_end}",
            "pages": pages,
        }
    finally:
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract PDF pages as markdown")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, default=1, help="First page (1-based)")
    parser.add_argument("--page-end", type=int, default=None, help="Last page (1-based, inclusive)")
    args = parser.parse_args()

    try:
        result = read_pages(args.pdf_path, args.page_start, args.page_end)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

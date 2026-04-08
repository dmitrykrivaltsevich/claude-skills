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

For large page ranges, use --output to write JSON to a file instead of
stdout (avoids terminal truncation). A compact summary is printed to
stdout when --output is used.

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
from contracts import check_file_readable, precondition


@precondition(
    lambda pdf_path, **_: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path, **_: check_file_readable(pdf_path),
    "PDF file is not readable",
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
    """Extract pages as markdown with word counts.

    Uses batched extraction via page_chunks for efficiency — opens the
    PDF once and extracts all requested pages in a single call.
    """
    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)

        # Clamp end to actual page count
        effective_end = min(page_end, total_pages) if page_end is not None else total_pages

        # pymupdf4llm uses 0-based page indices
        page_indices = list(range(page_start - 1, effective_end))

        print(
            f"Reading pages {page_start}-{effective_end} of {total_pages}...",
            file=sys.stderr,
        )

        # Batch extract all pages at once — much faster than per-page calls
        # because the PDF is opened/parsed only once.
        chunks = pymupdf4llm.to_markdown(
            doc,
            pages=page_indices,
            page_chunks=True,
        )

        # Sort by page number — page_chunks may return out of order
        chunks.sort(key=lambda c: c["metadata"]["page_number"])

        pages = []
        for chunk in chunks:
            md = chunk["text"]
            word_count = len(md.split()) if md.strip() else 0
            pages.append({
                "number": chunk["metadata"]["page_number"],  # already 1-based
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
    parser.add_argument(
        "--output", default=None,
        help="Write full JSON to this file instead of stdout. "
             "A compact summary is printed to stdout. "
             "Use for large page ranges to avoid terminal truncation.",
    )
    args = parser.parse_args()

    try:
        result = read_pages(args.pdf_path, args.page_start, args.page_end)

        if args.output:
            # Write full JSON to file, print compact summary to stdout
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            total_words = sum(p["word_count"] for p in result["pages"])
            summary = {
                "file_path": result["file_path"],
                "total_pages": result["total_pages"],
                "pages_returned": result["pages_returned"],
                "page_count": len(result["pages"]),
                "total_words": total_words,
                "output_file": args.output,
                "pages": [
                    {"number": p["number"], "word_count": p["word_count"]}
                    for p in result["pages"]
                ],
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

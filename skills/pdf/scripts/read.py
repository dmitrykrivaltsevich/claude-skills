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
stdout (avoids terminal truncation). A compact artifact envelope is
printed to stdout when --output is used.

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys

import pymupdf
import pymupdf4llm

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
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
        # Keep stdout clean for JSON output by routing parser messages to stderr.
        pymupdf.set_messages(stream=sys.stderr)

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
        parser_logs = io.StringIO()
        with contextlib.redirect_stdout(parser_logs):
            chunks = pymupdf4llm.to_markdown(
                doc,
                pages=page_indices,
                page_chunks=True,
            )
        parser_output = parser_logs.getvalue().strip()
        if parser_output:
            print(parser_output, file=sys.stderr)

        # Sort by page number — page_chunks may return out of order
        chunks.sort(key=lambda c: c["metadata"].get("page_number", c["metadata"].get("page", 0)))

        pages = []
        for chunk in chunks:
            md = chunk["text"]
            word_count = len(md.split()) if md.strip() else 0
            page_number = chunk["metadata"].get("page_number", chunk["metadata"].get("page", 0))
            pages.append({
                "number": page_number,  # already 1-based
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract PDF pages as markdown")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, default=1, help="First page (1-based)")
    parser.add_argument("--page-end", type=int, default=None, help="Last page (1-based, inclusive)")
    parser.add_argument(
        "--output", default=None,
        help="Write full JSON to this file instead of stdout. "
               "A compact artifact envelope is printed to stdout. "
             "Use for large page ranges to avoid terminal truncation.",
    )
    args = parser.parse_args(argv)

    try:
        result = read_pages(args.pdf_path, args.page_start, args.page_end)

        emit_json_result(result, output_path=args.output, artifact_kind="pdf-read")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

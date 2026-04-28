#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Full-text search within a PDF — outputs JSON to stdout.

Searches for a text query across all pages (or a page range) and returns
matches with page numbers and surrounding context. The LLM uses this to
locate relevant sections before calling read.py for full extraction.

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import check_file_readable, precondition

# Characters of context to extract around each match.
# Enough for the LLM to judge relevance without reading the full page.
CONTEXT_CHARS = 200  # ~2 sentences of surrounding text


@precondition(
    lambda pdf_path, **_: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path, **_: check_file_readable(pdf_path),
    "PDF file is not readable",
)
@precondition(
    lambda pdf_path, query, **_: query.strip() != "",
    "Search query must not be empty",
)
def search_pdf(
    pdf_path: str,
    query: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> dict:
    """Search for text in PDF, returning matches with context."""
    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        start = (page_start - 1) if page_start else 0
        end = page_end if page_end else total_pages

        matches = []
        for i in range(start, min(end, total_pages)):
            page = doc[i]
            hits = page.search_for(query)
            if hits:
                # Get full page text for context extraction
                full_text = page.get_text("text")
                for hit_rect in hits:
                    # Extract context around the match position
                    query_lower = query.lower()
                    text_lower = full_text.lower()
                    pos = text_lower.find(query_lower)
                    if pos >= 0:
                        ctx_start = max(0, pos - CONTEXT_CHARS // 2)
                        ctx_end = min(len(full_text), pos + len(query) + CONTEXT_CHARS // 2)
                        context = full_text[ctx_start:ctx_end].strip()
                    else:
                        context = full_text[:CONTEXT_CHARS].strip()

                    matches.append({
                        "page": i + 1,
                        "context": context,
                        "rect": {
                            "x0": round(hit_rect.x0, 1),
                            "y0": round(hit_rect.y0, 1),
                            "x1": round(hit_rect.x1, 1),
                            "y1": round(hit_rect.y1, 1),
                        },
                    })

        return {
            "query": query,
            "total_matches": len(matches),
            "total_pages": total_pages,
            "matches": matches,
        }
    finally:
        doc.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Search text within a PDF")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("query", help="Text to search for")
    parser.add_argument("--page-start", type=int, default=None, help="First page (1-based)")
    parser.add_argument("--page-end", type=int, default=None, help="Last page (1-based)")
    parser.add_argument(
        "--output",
        default=None,
        help="Write full JSON to this file and print a compact artifact envelope to stdout",
    )
    args = parser.parse_args(argv)

    try:
        result = search_pdf(args.pdf_path, args.query, args.page_start, args.page_end)
        emit_json_result(result, output_path=args.output, artifact_kind="pdf-search")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typst >= 0.12",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Compile Typst source to PDF — outputs JSON result to stdout.

The LLM generates Typst markup, writes it to a .typ file, then calls this
script to compile it. On success, the output PDF path and page count are
returned. On failure, compilation errors are returned so the LLM can fix
the source and retry (feedback loop).

PyMuPDF is used to count pages in the output PDF.

Progress/errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import typst
import pymupdf

sys.path.insert(0, os.path.dirname(__file__))
from contracts import check_file_readable, precondition


@precondition(
    lambda source_path, **_: source_path.strip() != "",
    "Source path must not be empty",
)
@precondition(
    lambda source_path, **_: check_file_readable(source_path),
    "Source file is not readable",
)
@precondition(
    lambda source_path, output_path, **_: output_path.strip() != "",
    "Output path must not be empty",
)
def compile_pdf(source_path: str, output_path: str) -> dict:
    """Compile a Typst source file to PDF."""
    warnings = []
    errors = []

    try:
        print(f"Compiling {source_path}...", file=sys.stderr)
        pdf_bytes = typst.compile(source_path)

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        # Count pages using pymupdf
        doc = pymupdf.open(output_path)
        page_count = len(doc)
        doc.close()

        file_size = os.path.getsize(output_path)

        return {
            "success": True,
            "pdf_path": output_path,
            "page_count": page_count,
            "file_size_bytes": file_size,
            "warnings": warnings,
            "errors": [],
        }
    except Exception as e:
        error_msg = str(e)
        errors.append(error_msg)
        print(f"Compilation error: {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "pdf_path": output_path,
            "page_count": 0,
            "file_size_bytes": 0,
            "warnings": warnings,
            "errors": errors,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Typst source to PDF")
    parser.add_argument("source_path", help="Path to the .typ source file")
    parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    args = parser.parse_args()

    try:
        result = compile_pdf(args.source_path, args.output)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["success"]:
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

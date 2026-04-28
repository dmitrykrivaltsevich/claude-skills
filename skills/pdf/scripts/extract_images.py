#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Extract embedded images from PDF pages — outputs JSON manifest to stdout.

Pulls images embedded in the PDF (photographs, diagrams, charts) and saves
them to a directory. Preserves original format when possible (JPEG stays JPEG),
falls back to PNG for other formats.

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

# Minimum image dimension in pixels to extract.
# Filters out tiny decorative images (bullets, icons, line art).
MIN_IMAGE_DIM = 32  # px — images smaller than this in any dimension are likely decorative


@precondition(
    lambda pdf_path, **_: pdf_path.strip() != "",
    "PDF path must not be empty",
)
@precondition(
    lambda pdf_path, **_: check_file_readable(pdf_path),
    "PDF file is not readable",
)
def extract_images(
    pdf_path: str,
    output_dir: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> dict:
    """Extract embedded images from PDF pages to output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        start = (page_start - 1) if page_start else 0
        end = page_end if page_end else total_pages

        images = []
        img_counter = 0

        for page_idx in range(start, min(end, total_pages)):
            page = doc[page_idx]
            image_list = page.get_images()

            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    print(f"Warning: could not extract image xref={xref} on page {page_idx + 1}", file=sys.stderr)
                    continue

                if not base_image:
                    continue

                width = base_image["width"]
                height = base_image["height"]

                # Skip tiny decorative images
                if width < MIN_IMAGE_DIM or height < MIN_IMAGE_DIM:
                    continue

                img_bytes = base_image["image"]
                ext = base_image.get("ext", "png")
                img_counter += 1
                filename = f"page{page_idx + 1}_img{img_counter}.{ext}"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                images.append({
                    "page": page_idx + 1,
                    "path": filepath,
                    "width": width,
                    "height": height,
                    "format": ext,
                    "file_size_bytes": len(img_bytes),
                })

        return {
            "file_path": pdf_path,
            "output_dir": output_dir,
            "total_images": len(images),
            "images": images,
        }
    finally:
        doc.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract images from PDF")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output-dir", required=True, help="Directory to save images")
    parser.add_argument("--page-start", type=int, default=None, help="First page (1-based)")
    parser.add_argument("--page-end", type=int, default=None, help="Last page (1-based)")
    parser.add_argument(
        "--output",
        default=None,
        help="Write full JSON to this file and print a compact artifact envelope to stdout",
    )
    args = parser.parse_args(argv)

    try:
        result = extract_images(args.pdf_path, args.output_dir, args.page_start, args.page_end)
        emit_json_result(result, output_path=args.output, artifact_kind="pdf-extract-images")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Pillow >= 10.1",
#   "ddgs >= 6.0",
# ]
# ///
"""DuckDuckGo visual search — analyze images and find similar ones.

Outputs JSON to stdout.  Progress/errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import precondition
from search import search_image

# Camera filename prefixes that carry no semantic content.
_CAMERA_PREFIX_RE = re.compile(
    r"^(IMG|DSC|DSCN?|DCIM|P|GOPR|GoPro|DJI|VID|MOV|MVI|PANO|"
    r"Screenshot|Screen[\s_-]*Shot|Capture|Photo|Image|Untitled)[_\-\s]*",
    re.IGNORECASE,
)
# Pure timestamp patterns (no semantic value).
_TIMESTAMP_RE = re.compile(
    r"^\d{4}[-_]?\d{2}[-_]?\d{2}[-_T]?\d{2}[-_:]?\d{2}[-_:]?\d{0,6}$"
)
_DATE_ONLY_RE = re.compile(r"^\d{4}[-_]?\d{2}[-_]?\d{2}$")


def _extract_image_metadata(image_path: str) -> dict:
    """Extract rich metadata from an image file, including EXIF text fields.

    Returns a dict with dimensions, format, and any textual EXIF metadata
    (descriptions, keywords, subjects) that could form a useful search query.
    """
    path = Path(image_path)
    metadata: dict = {}

    with Image.open(path) as img:
        metadata["width"] = img.size[0]
        metadata["height"] = img.size[1]
        metadata["format"] = img.format
        metadata["mode"] = img.mode
        metadata["file_size_bytes"] = path.stat().st_size

        if hasattr(img, "info") and "dpi" in img.info:
            metadata["dpi"] = img.info["dpi"]

        # EXIF data — use public API (works for JPEG, TIFF, WebP, etc.)
        try:
            exif = img.getexif()
        except Exception:
            exif = {}

        # Key text fields in EXIF
        exif_text = {
            270: "image_description",  # ImageDescription
            315: "artist",             # Artist
        }
        for tag_id, key in exif_text.items():
            val = exif.get(tag_id)
            if isinstance(val, str) and val.strip():
                metadata[key] = val.strip()

        # Windows XP metadata (stored as UTF-16LE bytes in JPEG)
        xp_fields = {
            40091: "xp_title",
            40092: "xp_comment",
            40093: "xp_author",
            40094: "xp_keywords",
            40095: "xp_subject",
        }
        for tag_id, key in xp_fields.items():
            val = exif.get(tag_id)
            if val:
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-16-le").rstrip("\x00")
                    except Exception:
                        continue
                if isinstance(val, str) and val.strip():
                    metadata[key] = val.strip()

        # GPS presence flag (the LLM can ask the user for context)
        if 34853 in exif:
            metadata["has_gps"] = True

    return metadata


def _build_query_from_image(image_path: str, metadata: dict) -> str:
    """Build the best possible search query from image metadata.

    Priority:
      1. EXIF text (description, subject, keywords, title, comment)
      2. Smart filename parsing (strip camera prefixes + timestamps)
      3. Empty string if nothing useful remains

    Returns:
        Query string, or empty string if no useful query can be formed.
    """
    # Priority 1: EXIF text metadata
    for field in (
        "image_description",
        "xp_subject",
        "xp_keywords",
        "xp_title",
        "xp_comment",
    ):
        val = metadata.get(field, "")
        if val and len(val.strip()) >= 3:
            return val.strip()[:200]

    # Priority 2: Smart filename parsing
    stem = Path(image_path).stem
    cleaned = _CAMERA_PREFIX_RE.sub("", stem)
    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()

    # If what remains is just a timestamp, it's useless
    no_spaces = cleaned.replace(" ", "")
    if _TIMESTAMP_RE.match(no_spaces) or _DATE_ONLY_RE.match(no_spaces):
        return ""

    # If what remains has fewer than 2 alphabetic characters, it's useless
    alpha_only = re.sub(r"[^a-zA-Z]", "", cleaned)
    if len(alpha_only) < 2:
        return ""

    return cleaned[:200]


@precondition(
    lambda image_path: Path(image_path).is_file(),
    "image_path must point to an existing file",
)
def get_image_info(image_path: str) -> dict:
    """Read image metadata using Pillow.

    Args:
        image_path: Path to an existing image file.

    Returns:
        Dictionary with image dimensions, format, mode, and file size.
    """
    path = Path(image_path)
    with Image.open(path) as img:
        info = {
            "path": str(path.resolve()),
            "width": img.size[0],
            "height": img.size[1],
            "format": img.format,
            "mode": img.mode,
            "file_size_bytes": path.stat().st_size,
        }
        if hasattr(img, "info") and "dpi" in img.info:
            info["dpi"] = img.info["dpi"]
        return info


@precondition(
    lambda image_path: Path(image_path).is_file(),
    "image_path must point to an existing file",
)
def find_similar_images(image_path: str) -> dict:
    """Find similar images using metadata-driven search.

    Extracts EXIF metadata and filename cues to build a search query.
    Returns image metadata, the query used, and search results as a
    structured dict.  If no useful query can be formed, returns metadata
    with empty results and a diagnostic message so the LLM can ask the
    user to describe the image.

    Args:
        image_path: Path to an existing image file.

    Returns:
        Dict with ``image_metadata``, ``query_used``, ``results``,
        and optionally ``diagnostic``.
    """
    metadata = _extract_image_metadata(image_path)
    query = _build_query_from_image(image_path, metadata)

    result: dict = {
        "image_metadata": metadata,
        "query_used": query,
        "results": [],
    }

    if query:
        result["results"] = search_image(query)
    else:
        result["diagnostic"] = (
            "No useful search query could be derived from the filename or EXIF "
            "metadata.  Provide a text description of the image content for a "
            "targeted search."
        )

    return result


def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo visual search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Get image metadata")
    analyze_parser.add_argument(
        "--image-path", "-i", required=True, help="Path to image file"
    )
    analyze_parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )

    find_parser = subparsers.add_parser("find_similar", help="Find similar images")
    find_parser.add_argument(
        "--image-path", "-i", required=True, help="Path to image file"
    )
    find_parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        info = get_image_info(args.image_path)
        print(f"Image analysis: {info['path']}", file=sys.stderr)
        emit_json_result(
            info,
            output_path=args.output,
            artifact_kind="duckduckgo-image-analysis",
        )

    elif args.command == "find_similar":
        result = find_similar_images(args.image_path)
        n = len(result["results"])
        print(f"Found {n} similar images.", file=sys.stderr)
        emit_json_result(
            result,
            output_path=args.output,
            artifact_kind="duckduckgo-similar-images",
        )


if __name__ == "__main__":
    main()

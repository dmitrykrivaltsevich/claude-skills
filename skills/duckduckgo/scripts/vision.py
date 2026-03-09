#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Pillow >= 10.1",
#   "ddgs >= 6.0",
# ]
# ///
"""DuckDuckGo visual search — analyze images and find similar ones."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition
from search import search_image


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
def find_similar_images(image_path: str) -> list[dict]:
    """Find similar images by searching DuckDuckGo with the filename as query.

    Args:
        image_path: Path to the reference image.

    Returns:
        List of image result dicts from DuckDuckGo image search.
    """
    stem = Path(image_path).stem
    # Use filename (without extension) as search query, replacing separators with spaces
    query = stem.replace("_", " ").replace("-", " ").strip()
    if len(query) < 2:
        query = "image"
    return search_image(query)


def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo visual search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Get image metadata")
    analyze_parser.add_argument(
        "--image-path", "-i", required=True, help="Path to image file"
    )

    find_parser = subparsers.add_parser("find_similar", help="Find similar images")
    find_parser.add_argument(
        "--image-path", "-i", required=True, help="Path to image file"
    )

    args = parser.parse_args()

    if args.command == "analyze":
        info = get_image_info(args.image_path)
        print(f"Image: {info['path']}")
        print(f"Size: {info['width']}x{info['height']}")
        print(f"Format: {info['format']}")
        print(f"Mode: {info['mode']}")
        print(f"File size: {info['file_size_bytes']} bytes")
        if "dpi" in info:
            print(f"DPI: {info['dpi']}")

    elif args.command == "find_similar":
        results = find_similar_images(args.image_path)
        print(f"Found {len(results)} similar images:")
        for i, r in enumerate(results[:10], 1):
            print(f"\n{i}. {r.get('title', 'Unknown')}")
            if r.get("image"):
                print(f"   {r['image']}")
            if r.get("source"):
                print(f"   Source: {r['source']}")


if __name__ == "__main__":
    main()

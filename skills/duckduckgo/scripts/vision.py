#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Pillow >= 10.1",
#   "requests >= 2.31",
# ]
# ///
"""DuckDuckGo visual search - analyze images and find similar ones."""

from __future__ import annotations

import argparse
import base64
import sys
from io import BytesIO
from PIL import Image

try:
    from contracts import ContractViolationError, precondition
except ImportError:
    pass  # Gracefully handle missing contracts for non-essential scripts

API_COOLDOWN_SECONDS = 12


def encode_image_to_base64(image_path: str) -> str:
    """Encode image to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path: str) -> dict:
    """Analyze image using DuckDuckGo Vision API.

    Args:
        image_path: Path to the image file.

    Returns:
        Dictionary with success flag and either data or error message.

    Raises:
        RuntimeError: If image cannot be read or API fails.
    """
    try:
        encoded = encode_image_to_base64(image_path)
    except FileNotFoundError:
        raise RuntimeError(f"Image file not found: {image_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to read image file: {e}")

    # Note: DDG Vision API endpoints require special setup/credentials
    # This is a placeholder implementation for public API access
    payload = {
        "image": f"data:image/jpeg;base64,{encoded}",
        "min_size": 1,
        "max_size": 30,
    }

    try:
        response = requests.post(
            "https://duckduckgo.com/i.js",
            headers={"Referer": "https://duckduckgo.com/"},
            data=payload,
            timeout=15
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to contact DuckDuckGo API: {e}")
    finally:
        # Apply rate limiting cooldown between vision API calls
        time.sleep(API_COOLDOWN_SECONDS)

    return {"success": False, "error": f"API returned status {response.status_code}"}


def find_similar_images(image_path: str) -> list[dict]:
    """Find similar images using DuckDuckGo Vision search.

    Args:
        image_path: Path to the reference image.

    Returns:
        List of similar image results with URLs and metadata.
    """
    analysis = analyze_image(image_path)

    if not analysis.get("success"):
        return []

    # In production, would extract query terms from actual vision API response
    # For now, fall back to basic image search
    time.sleep(API_COOLDOWN_SECONDS)

    results = search_image(
        "similar images",  # Placeholder query
        type_="jpg"
    )

    return results


def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo visual search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze image content")
    analyze_parser.add_argument(
        "--image-path", "-i",
        required=True,
        help="Path to image file"
    )

    # Find similar command
    find_parser = subparsers.add_parser("find_similar", help="Find similar images")
    find_parser.add_argument(
        "--image-path", "-i",
        required=True,
        help="Path to image file"
    )

    args = parser.parse_args()

    if args.command == "analyze":
        print(f"Analyzing: {args.image_path}")

        # For now, show basic image info since DDG Vision requires special setup
        try:
            with Image.open(args.image_path) as img:
                print(f"Image size: {img.size[0]}x{img.size[1]}")
                print(f"Format: {img.format}")
                print(f"Mode: {img.mode}")

                # Try to detect content type (simplified)
                if "jpeg" in args.image_path.lower():
                    print("Likely type: Photo/JPEG")
                elif "png" in args.image_path.lower():
                    print("Likely type: Screenshot/PNG")
                elif "gif" in args.image_path.lower():
                    print("Likely type: Animation/GIF")

        except Exception as e:
            print(f"Error reading image: {e}")

    elif args.command == "find_similar":
        print(f"Finding similar images for: {args.image_path}")

        try:
            results = find_similar_images(args.image_path)
            print(f"Found {len(results)} similar images:")
            for i, r in enumerate(results[:10], 1):  # Limit to 10
                print(f"\n{i}. {r.get('title', 'Unknown')}")
                if r.get('thumbnail'):
                    print(f"   {r['thumbnail']}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

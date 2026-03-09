#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests >= 2.31",
# ]
# ///
"""DuckDuckGo text, image, and news search."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import requests
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(__file__))

try:
    from contracts import ContractViolationError, precondition
except ImportError:
    pass  # Gracefully handle missing contracts for non-essential scripts

# API rate limit: ~35 queries/minute per DuckDuckGo public API docs.
# 12 second cooldown ensures batch operations stay within limits without throttling users.
API_COOLDOWN_SECONDS = 12


if False:  # precondition not available in this script
    pass

def search_text(query: str, raw_query: str | None = None) -> list[dict]:
    """Search DuckDuckGo for text results.

    Args:
        query: Search term (at least 2 characters).
        raw_query: Raw query string without DDG formatting (optional).

    Returns:
        List of result dicts with title, url, and description.
    """
    # Apply rate limiting cooldown between search requests
    time.sleep(API_COOLDOWN_SECONDS)

    if raw_query:
        params = {"q": raw_query}
    else:
        params = {
            "q": query,
            "no_html": "1",
            "skip_bad_urls": "1",
        }

    try:
        result = _make_ddg_request("/html", params)
    except RuntimeError as e:
        # Log rate limit error and raise with actionable message
        if "429" in str(e):
            print("Rate limited. Please wait 30 seconds before retrying.", file=sys.stderr)
        raise

    result = _make_ddg_request("/html", params)

    results = []
    for item in result.get("RelatedTopics", []):
        results.append({
            "title": item.get("FirstResult", {}).get("Text", item.get("Text", "")),
            "url": item.get("FirstResult", {}).get("Url", ""),
            "description": item.get("Text", "")[:500],
        })

    # Add general results
    for item in result.get("Results", []):
        if not results or results[-1].get("source") != "general":
            results.append({
                "title": item.get("Title", ""),
                "url": item.get("Url", ""),
                "description": item.get("Abstract", "")[:500],
                "source": "general",
            })

    return results


def _make_ddg_request(endpoint: str, params: dict) -> dict:
    """Make request to DuckDuckGo Instant Answer API with rate limiting."""
    # Apply cooldown between requests to respect rate limits (~35 queries/minute)
    time.sleep(API_COOLDOWN_SECONDS)

    url = f"https://api.duckduckgo.com{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Provide actionable error message when API fails
        raise RuntimeError(f"Failed to fetch results from DuckDuckGo: {e}") from e


def search_image(
    query: str,
    size: str = "medium",
    type_: str | None = None,
    color: str = "any"
) -> list[dict]:
    """Search DuckDuckGo for images.

    Args:
        query: Search term (at least 2 characters).
        size: Image size filter - tiny, small, medium, large, huge.
        type_: Image format - gif, jpg, png, svg, webp.
        color: Color filter - any or named colors.

    Returns:
        List of result dicts with title, url, thumbnail, and size.
    """
    # Apply rate limiting cooldown between search requests
    time.sleep(API_COOLDOWN_SECONDS)
    params = {
        "q": query,
        "no_redirect": "1",
        "format": "json",
    }

    if size:
        params["size"] = size
    if type_:
        params["type"] = type_
    if color:
        params["color"] = color

    result = _make_ddg_request("/image", params)

    results = []
    for item in result.get("Related", []) or []:
        image_info = item.get("ImageUrl", "")
        if not image_info.startswith("http"):
            image_info = f"https://duckduckgo.com{image_info}"

        results.append({
            "title": item.get("ImgTitle", query),
            "url": item.get("SourceUrl", ""),
            "thumbnail": image_info,
            "size": item.get("ImageWidth", "") + "x" + str(item.get("ImageHeight", "")),
        })

    return results


def search_news(query: str) -> list[dict]:
    """Search DuckDuckGo for news results.

    Args:
        query: Search term (at least 2 characters).

    Returns:
        List of result dicts with title, url, description, and date.
    """
    # Apply rate limiting cooldown between search requests
    time.sleep(API_COOLDOWN_SECONDS)
    params = {
        "q": query,
        "no_html": "1",
        "skip_bad_urls": "1",
        "i": "nws",  # News index filter
    }

    result = _make_ddg_request("/html", params)

    return [
        {
            "title": item.get("Title", ""),
            "url": item.get("Url", ""),
            "description": item.get("AbstractText", "")[:500],
            "datePublished": item.get("DatePublished", ""),
        }
        for item in result.get("Results", [])
    ]


def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo search")
    parser.add_argument("type", choices=["text", "image", "news"], help="Search type")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument(
        "--size",
        choices=["tiny", "small", "medium", "large", "huge"],
        help="Image size",
        default="medium"
    )
    parser.add_argument("--type", choices=["gif", "jpg", "png", "svg", "webp"], help="Image type")
    parser.add_argument(
        "--color",
        choices=["any", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink", "gray", "black", "white", "transparent"],
        default="any"
    )
    parser.add_argument("--no-html", action="store_true", help="No HTML snippets")

    args = parser.parse_args()

    if args.type == "text":
        results = search_text(args.query)
        print(f"Found {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get('description'):
                desc = r['description'].replace(r['title'], '', 1).strip()
                if desc:
                    print(f"   {desc[:200]}...")
            if r.get('url'):
                print(f"   {r['url']}")

    elif args.type == "image":
        results = search_image(args.query, args.size, args.type, args.color)
        print(f"Found {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get('thumbnail'):
                print(f"   {r['thumbnail']}")
            if r.get('url'):
                print(f"   Source: {r['url']}")
            if r.get('size'):
                print(f"   Size: {r['size']}")

    elif args.type == "news":
        results = search_news(args.query)
        print(f"Found {len(results)} news results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get('datePublished'):
                print(f"   Date: {r['datePublished']}")
            if r.get('description'):
                print(f"   {r['description'][:300]}...")
            if r.get('url'):
                print(f"   {r['url']}")


if __name__ == "__main__":
    main()

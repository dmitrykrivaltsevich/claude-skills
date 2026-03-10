#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
# ]
# ///
"""DuckDuckGo text, image, and news search — outputs JSON to stdout.

This script is a **data-gathering facility** for the LLM.  It handles the DDG
API call and returns structured JSON so the LLM can filter, rank, summarise,
and present results according to the user's actual intent.

Progress / error messages go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from ddgs import DDGS

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition

# Default result counts — overridable at runtime via --max-results.
DEFAULT_TEXT_RESULTS = 9
DEFAULT_IMAGE_RESULTS = 30
DEFAULT_NEWS_RESULTS = 9


@precondition(
    lambda query, **_: len(query.strip()) >= 2,
    "Query must be at least 2 characters",
)
def search_text(query: str, max_results: int = DEFAULT_TEXT_RESULTS) -> list[dict]:
    """Search DuckDuckGo for text results.

    Args:
        query: Search term (at least 2 characters).
        max_results: Maximum number of results to return.

    Returns:
        List of result dicts with title, url, and description.
    """
    ddgs = DDGS()
    raw = ddgs.text(query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "description": r.get("body", "")[:500],
        }
        for r in raw
    ]


@precondition(
    lambda query, **_: len(query.strip()) >= 2,
    "Query must be at least 2 characters",
)
def search_image(
    query: str,
    size: str | None = None,
    type_: str | None = None,
    color: str | None = None,
    max_results: int = DEFAULT_IMAGE_RESULTS,
) -> list[dict]:
    """Search DuckDuckGo for images.

    Args:
        query: Search term (at least 2 characters).
        size: Image size filter — Small, Medium, Large, Wallpaper.
        type_: Image type — photo, clipart, gif, transparent, line.
        color: Color filter — color, Monochrome, Red, Orange, etc.
        max_results: Maximum number of results to return.

    Returns:
        List of result dicts with title, image url, thumbnail, and source.
    """
    ddgs = DDGS()
    kwargs: dict = {"max_results": max_results}
    if size:
        kwargs["size"] = size
    if type_:
        kwargs["type_image"] = type_
    if color:
        kwargs["color"] = color
    raw = ddgs.images(query, **kwargs)
    return [
        {
            "title": r.get("title", query),
            "url": r.get("url", ""),
            "image": r.get("image", ""),
            "thumbnail": r.get("thumbnail", ""),
            "source": r.get("source", ""),
        }
        for r in raw
    ]


@precondition(
    lambda query, **_: len(query.strip()) >= 2,
    "Query must be at least 2 characters",
)
def search_news(query: str, max_results: int = DEFAULT_NEWS_RESULTS) -> list[dict]:
    """Search DuckDuckGo for news results.

    Args:
        query: Search term (at least 2 characters).
        max_results: Maximum number of results to return.

    Returns:
        List of result dicts with title, url, description, date, and source.
    """
    ddgs = DDGS()
    raw = ddgs.news(query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("body", "")[:500],
            "date": r.get("date", ""),
            "source": r.get("source", ""),
        }
        for r in raw
    ]


def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo search — outputs JSON")
    parser.add_argument("type", choices=["text", "image", "news"], help="Search type")
    parser.add_argument("--query", "-q", required=True, help="Search query (min 2 chars)")
    parser.add_argument("--max-results", "-n", type=int, default=None, help="Maximum number of results to return")
    parser.add_argument("--size", help="Image size: Small, Medium, Large, Wallpaper")
    parser.add_argument(
        "--type", dest="image_type",
        help="Image type: photo, clipart, gif, transparent, line",
    )
    parser.add_argument("--color", help="Color filter: color, Monochrome, Red, Orange, etc.")

    args = parser.parse_args()

    if args.type == "text":
        kwargs = {"max_results": args.max_results} if args.max_results is not None else {}
        results = search_text(args.query, **kwargs)

    elif args.type == "image":
        img_kwargs: dict = {}
        if args.max_results is not None:
            img_kwargs["max_results"] = args.max_results
        results = search_image(args.query, args.size, args.image_type, args.color, **img_kwargs)

    elif args.type == "news":
        news_kwargs = {"max_results": args.max_results} if args.max_results is not None else {}
        results = search_news(args.query, **news_kwargs)

    print(f"Found {len(results)} results.", file=sys.stderr)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=None)
    print(file=sys.stdout)  # trailing newline


if __name__ == "__main__":
    main()

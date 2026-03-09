#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "duckduckgo-search >= 6.0",
# ]
# ///
"""DuckDuckGo text, image, and news search."""

from __future__ import annotations

import argparse
import os
import sys

from duckduckgo_search import DDGS

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition

# Maximum text results per query — DDG rarely returns more via Instant Answer API.
MAX_TEXT_RESULTS = 9
# Maximum image results per query — keeps response size manageable for LLM context.
MAX_IMAGE_RESULTS = 30
# Maximum news results per query — matches typical DDG news page count.
MAX_NEWS_RESULTS = 9


@precondition(
    lambda query, **_: len(query.strip()) >= 2,
    "Query must be at least 2 characters",
)
def search_text(query: str) -> list[dict]:
    """Search DuckDuckGo for text results.

    Args:
        query: Search term (at least 2 characters).

    Returns:
        List of result dicts with title, url, and description.
    """
    ddgs = DDGS()
    raw = ddgs.text(query, max_results=MAX_TEXT_RESULTS)
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
) -> list[dict]:
    """Search DuckDuckGo for images.

    Args:
        query: Search term (at least 2 characters).
        size: Image size filter — Small, Medium, Large, Wallpaper.
        type_: Image type — photo, clipart, gif, transparent, line.
        color: Color filter — color, Monochrome, Red, Orange, etc.

    Returns:
        List of result dicts with title, image url, thumbnail, and source.
    """
    ddgs = DDGS()
    kwargs: dict = {"max_results": MAX_IMAGE_RESULTS}
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
def search_news(query: str) -> list[dict]:
    """Search DuckDuckGo for news results.

    Args:
        query: Search term (at least 2 characters).

    Returns:
        List of result dicts with title, url, description, date, and source.
    """
    ddgs = DDGS()
    raw = ddgs.news(query, max_results=MAX_NEWS_RESULTS)
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
    parser = argparse.ArgumentParser(description="DuckDuckGo search")
    parser.add_argument("type", choices=["text", "image", "news"], help="Search type")
    parser.add_argument("--query", "-q", required=True, help="Search query (min 2 chars)")
    parser.add_argument("--size", help="Image size: Small, Medium, Large, Wallpaper")
    parser.add_argument(
        "--type", dest="image_type",
        help="Image type: photo, clipart, gif, transparent, line",
    )
    parser.add_argument("--color", help="Color filter: color, Monochrome, Red, Orange, etc.")

    args = parser.parse_args()

    if args.type == "text":
        results = search_text(args.query)
        print(f"Found {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get("description"):
                print(f"   {r['description'][:200]}")
            if r.get("url"):
                print(f"   {r['url']}")

    elif args.type == "image":
        results = search_image(args.query, args.size, args.image_type, args.color)
        print(f"Found {len(results)} images:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get("image"):
                print(f"   {r['image']}")
            if r.get("source"):
                print(f"   Source: {r['source']}")

    elif args.type == "news":
        results = search_news(args.query)
        print(f"Found {len(results)} news results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            if r.get("date"):
                print(f"   Date: {r['date']}")
            if r.get("description"):
                print(f"   {r['description'][:300]}")
            if r.get("url"):
                print(f"   {r['url']}")


if __name__ == "__main__":
    main()

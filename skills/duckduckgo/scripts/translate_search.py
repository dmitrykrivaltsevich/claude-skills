#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
# ]
# ///
"""Multi-region parallel search — outputs JSON with region tags.

Searches the same or translated queries across multiple DDG regions in parallel.
The LLM provides the translated queries; this script handles parallel execution
and region/language tagging.

Input format for queries: ``"region:query"`` (e.g. ``"fr-fr:intelligence artificielle"``).
If no region prefix, uses ``"wt-wt"`` (worldwide).

Output: JSON array to stdout.  Progress to stderr.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys

from ddgs import DDGS

sys.path.insert(0, os.path.dirname(__file__))
from contracts import precondition

# Common DDG region codes → human-readable language labels.
REGION_LABELS: dict[str, str] = {
    "wt-wt": "worldwide",
    "us-en": "English (US)",
    "uk-en": "English (UK)",
    "fr-fr": "French",
    "de-de": "German",
    "es-es": "Spanish (Spain)",
    "es-xl": "Spanish (LatAm)",
    "it-it": "Italian",
    "pt-br": "Portuguese (Brazil)",
    "pt-pt": "Portuguese (Portugal)",
    "nl-nl": "Dutch",
    "pl-pl": "Polish",
    "ru-ru": "Russian",
    "ja-jp": "Japanese",
    "ko-kr": "Korean",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ar-xa": "Arabic",
    "hi-in": "Hindi",
    "tr-tr": "Turkish",
    "sv-se": "Swedish",
    "no-no": "Norwegian",
    "da-dk": "Danish",
    "fi-fi": "Finnish",
}

# Workers — bounded for DDG rate limits (~35 queries/min).
_WORKERS = 6  # each region query is independent

# Default results per query — moderate since we search multiple regions.
_PER_QUERY = 15


def _parse_query(raw: str) -> tuple[str, str]:
    """Parse ``'region:query'`` format.  Default region is ``'wt-wt'``."""
    match = re.match(r"^([a-z]{2}-[a-z]{2}):(.+)$", raw.strip(), re.IGNORECASE)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return "wt-wt", raw.strip()


def _search_region(
    query: str,
    region: str,
    search_type: str,
    max_results: int,
) -> list[dict]:
    """Search DDG with a specific region code."""
    ddgs = DDGS()
    kwargs: dict = {"max_results": max_results, "region": region}

    try:
        if search_type == "news":
            raw = ddgs.news(query, **kwargs)
        else:
            raw = ddgs.text(query, **kwargs)
    except Exception:
        return []

    label = REGION_LABELS.get(region, region)
    results: list[dict] = []
    for r in raw:
        result: dict = {
            "title": r.get("title", ""),
            "url": r.get("url") or r.get("href", ""),
            "description": (r.get("body", "") or "")[:500],
            "region": region,
            "language": label,
        }
        if search_type == "news":
            result["date"] = r.get("date", "")
            result["source"] = r.get("source", "")
        results.append(result)

    return results


@precondition(
    lambda queries, **_: len(queries) >= 1,
    "At least one query is required",
)
def multi_region_search(
    queries: list[str],
    search_type: str = "news",
    max_results: int = _PER_QUERY,
) -> list[dict]:
    """Search multiple region:query pairs in parallel.

    Args:
        queries: List of ``"region:query"`` strings.
        search_type: ``"news"`` or ``"text"``.
        max_results: Results per query.

    Returns:
        Flat list of results, each tagged with region/language.
    """
    parsed = [_parse_query(q) for q in queries]
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        futures = {
            ex.submit(_search_region, query, region, search_type, max_results): (region, query)
            for region, query in parsed
        }
        for fut in concurrent.futures.as_completed(futures, timeout=60):
            try:
                results = fut.result(timeout=10)
                for r in results:
                    norm = re.sub(r"^https?://(www\.)?", "", r["url"]).rstrip("/")
                    if norm not in seen_urls:
                        seen_urls.add(norm)
                        all_results.append(r)
            except Exception:
                pass

    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-region search — parallel queries across DDG regions."
    )
    parser.add_argument(
        "queries", nargs="+",
        help='Queries in "region:text" format (e.g. "fr-fr:intelligence artificielle")',
    )
    parser.add_argument(
        "--type", dest="search_type", choices=["news", "text"], default="news",
        help="Search type (default: news)",
    )
    parser.add_argument(
        "--max-results", "-n", type=int, default=_PER_QUERY,
        help=f"Results per query (default {_PER_QUERY})",
    )
    args = parser.parse_args()

    print(f"Searching {len(args.queries)} queries across regions…", file=sys.stderr)
    results = multi_region_search(
        args.queries,
        search_type=args.search_type,
        max_results=args.max_results,
    )
    print(f"Found {len(results)} unique results.", file=sys.stderr)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=None)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()

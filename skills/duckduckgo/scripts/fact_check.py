#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
# ]
# ///
"""Cross-reference a claim across source tiers — outputs JSON for LLM analysis.

Searches the same claim/headline across multiple source tiers (wires,
broadsheets, broadcast, independent, social) and returns structured results
for each tier.  The LLM assesses credibility, identifies agreement/divergence,
and synthesises a verdict.

Output: JSON object to stdout.  Progress to stderr.
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

# Source tiers for cross-referencing — ordered by editorial reliability.
# Each tier targets specific outlets via ``site:`` queries.
SOURCE_TIERS: dict[str, list[str]] = {
    "wires": [
        "site:reuters.com",
        "site:apnews.com",
    ],
    "broadsheets": [
        "site:nytimes.com",
        "site:washingtonpost.com",
        "site:theguardian.com",
        "site:ft.com",
        "site:bbc.com",
    ],
    "broadcast": [
        "site:cnn.com",
        "site:nbcnews.com",
        "site:abcnews.go.com",
        "site:pbs.org",
    ],
    "finance": [
        "site:bloomberg.com",
        "site:cnbc.com",
        "site:wsj.com",
    ],
    "investigation": [
        "site:propublica.org",
        "site:theintercept.com",
        "site:bellingcat.com",
    ],
    "independent": [
        "site:substack.com",
        "site:medium.com",
    ],
    "social": [
        "site:reddit.com",
        "site:news.ycombinator.com",
    ],
}

# Max results per site query — kept low per-site, breadth across tiers matters more.
_PER_SITE = 5  # 5 results per site × multiple sites per tier ≈ reasonable coverage

# Workers — bounded for DDG rate limits (~35 queries/min).
_WORKERS = 8  # 8 workers × concurrent queries stays within budget


def _search_tier(claim: str, tier_name: str, sites: list[str]) -> dict:
    """Search a claim across all sites in a tier, return structured results."""
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for site_query in sites:
        query = f"{claim} {site_query}"
        try:
            raw = DDGS().news(query, max_results=_PER_SITE)
        except Exception:
            raw = []

        for r in raw:
            url = (r.get("url", "") or "").strip()
            norm_url = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)
            all_results.append({
                "title": r.get("title", ""),
                "url": url,
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "description": (r.get("body", "") or "")[:500],
            })

    return {
        "tier": tier_name,
        "result_count": len(all_results),
        "results": all_results,
    }


@precondition(
    lambda claim, **_: len(claim.strip()) >= 5,
    "Claim must be at least 5 characters",
)
def cross_reference(
    claim: str,
    tiers: list[str] | None = None,
    _executor_class: type | None = None,
) -> dict:
    """Search a claim across source tiers in parallel.

    Args:
        claim: The headline or claim to verify (min 5 characters).
        tiers: Tier names to check (default: all tiers).
        _executor_class: Override executor (tests pass ThreadPoolExecutor
            so mocks work within the same process).

    Returns:
        Structured dict with per-tier results and summary counts.
    """
    selected = tiers or list(SOURCE_TIERS)
    tier_data = [(t, SOURCE_TIERS[t]) for t in selected if t in SOURCE_TIERS]
    executor_cls = _executor_class or concurrent.futures.ProcessPoolExecutor

    results: list[dict] = []
    with executor_cls(max_workers=_WORKERS) as ex:
        futures = {
            ex.submit(_search_tier, claim, name, sites): name
            for name, sites in tier_data
        }
        for fut in concurrent.futures.as_completed(futures, timeout=60):
            tier_name = futures[fut]
            try:
                results.append(fut.result(timeout=10))
            except Exception:
                results.append({
                    "tier": tier_name,
                    "result_count": 0,
                    "results": [],
                    "error": "Search failed",
                })

    # Preserve tier ordering from SOURCE_TIERS
    tier_order = list(SOURCE_TIERS)
    results.sort(
        key=lambda r: tier_order.index(r["tier"]) if r["tier"] in tier_order else 999,
    )

    total_results = sum(r["result_count"] for r in results)
    tiers_with_coverage = sum(1 for r in results if r["result_count"] > 0)

    return {
        "claim": claim,
        "tiers_checked": len(results),
        "tiers_with_coverage": tiers_with_coverage,
        "total_results": total_results,
        "tiers": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-reference a claim across source tiers."
    )
    parser.add_argument(
        "claim",
        help="Headline or claim to verify (min 5 characters)",
    )
    parser.add_argument(
        "--tiers", "-t", nargs="*",
        help=f"Tiers to check (default: all). Choices: {list(SOURCE_TIERS)}",
    )
    args = parser.parse_args()

    print(f"Cross-referencing: {args.claim}", file=sys.stderr)
    result = cross_reference(args.claim, tiers=args.tiers)
    print(
        f"Found {result['total_results']} results across "
        f"{result['tiers_with_coverage']}/{result['tiers_checked']} tiers.",
        file=sys.stderr,
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=None)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()

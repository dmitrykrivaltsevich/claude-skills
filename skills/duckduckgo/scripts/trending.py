#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
# ]
# ///
"""Gather trend data for topics — outputs JSON for LLM analysis.

For each supplied topic, runs DDG news searches at two time windows (24h and 7d)
and collects result counts, source diversity, and sample headlines.  The LLM
determines velocity and trending status from this raw data.

Two modes:
  --topics "AI" "climate" — measure named topics
  --discover             — auto-discover trending topics via DDG suggestions

Output: JSON array to stdout.  Progress to stderr.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

from ddgs import DDGS

from artifact_output import emit_json_result

# Discovery seeds — broad categories that surface whatever is generating
# the most coverage right now.
DISCOVER_SEEDS = [
    "breaking news",
    "world news",
    "technology news",
    "science news",
    "business news",
    "politics news",
    "health news",
    "climate news",
    "sports news",
    "entertainment news",
]

# Workers for parallel topic queries — bounded to stay within DDG rate limits
# (~35 queries/minute).  Each topic uses 2–3 queries, so 6 workers ≈ 18 peak.
_WORKERS = 6

# Results per DDG query — enough to measure breadth without hitting rate limits.
_PER_QUERY = 25  # 25 is DDG's practical max for news


def _gather_topic_data(topic: str) -> dict:
    """Gather trend data for a single topic.

    Runs news searches at two time windows plus DDG suggestions.
    Returns a structured dict with counts and samples.
    """
    # Separate instances per call — DDG sessions are lightweight
    try:
        news_24h = DDGS().news(topic, max_results=_PER_QUERY, timelimit="d")
    except Exception:
        news_24h = []

    try:
        news_7d = DDGS().news(topic, max_results=_PER_QUERY, timelimit="w")
    except Exception:
        news_7d = []

    try:
        raw_suggestions = DDGS().suggestions(topic)
        related = [
            s.get("phrase", "")
            for s in raw_suggestions
            if s.get("phrase", "").lower() != topic.lower()
        ]
    except Exception:
        related = []

    sources_24h = list({r.get("source", "") for r in news_24h if r.get("source")})
    headlines_24h = [r.get("title", "") for r in news_24h[:5] if r.get("title")]
    dates = [r.get("date", "") for r in news_24h if r.get("date")]

    return {
        "topic": topic,
        "news_24h_count": len(news_24h),
        "news_7d_count": len(news_7d),
        "sources_24h": sources_24h,
        "source_count_24h": len(sources_24h),
        "sample_headlines": headlines_24h,
        "related_queries": related[:10],
        "date_range": {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None,
        },
    }


def _discover_topics() -> list[str]:
    """Auto-discover current trending topics via DDG suggestions on seed queries."""
    topics: set[str] = set()

    for seed in DISCOVER_SEEDS:
        try:
            suggestions = DDGS().suggestions(seed)
            for s in suggestions:
                phrase = s.get("phrase", "").strip()
                if phrase and phrase.lower() != seed.lower():
                    topics.add(phrase)
        except Exception:
            continue

    return sorted(topics)


def gather_trends(
    topics: list[str],
    _executor_class: type | None = None,
) -> list[dict]:
    """Gather trend data for all topics in parallel.

    Args:
        _executor_class: Override executor (tests pass ThreadPoolExecutor
            so mocks work within the same process).
    """
    results: list[dict] = []
    max_workers = min(_WORKERS, len(topics))
    executor_cls = _executor_class or concurrent.futures.ProcessPoolExecutor

    with executor_cls(max_workers=max_workers) as ex:
        future_to_topic = {
            ex.submit(_gather_topic_data, t): t for t in topics
        }
        for fut in concurrent.futures.as_completed(future_to_topic, timeout=90):
            topic = future_to_topic[fut]
            try:
                data = fut.result(timeout=15)
                results.append(data)
            except Exception:
                results.append({
                    "topic": topic,
                    "news_24h_count": 0,
                    "news_7d_count": 0,
                    "sources_24h": [],
                    "source_count_24h": 0,
                    "sample_headlines": [],
                    "related_queries": [],
                    "date_range": {"earliest": None, "latest": None},
                    "error": "Failed to gather data",
                })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gather trend data for topics — outputs JSON for LLM analysis."
    )
    parser.add_argument(
        "--topics", "-t", nargs="+",
        help="Topics to measure (e.g. 'AI regulation' 'climate summit')",
    )
    parser.add_argument(
        "--discover", "-d", action="store_true",
        help="Auto-discover trending topics via DDG suggestions",
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )
    args = parser.parse_args()

    if args.discover:
        print("Discovering trending topics…", file=sys.stderr)
        topics = _discover_topics()
        if not topics:
            print("No topics discovered.", file=sys.stderr)
            emit_json_result([], output_path=args.output, artifact_kind="duckduckgo-trending-results")
            return
        print(f"Discovered {len(topics)} candidate topics.", file=sys.stderr)
    elif args.topics:
        topics = args.topics
    else:
        parser.error("Provide --topics or --discover")

    print(f"Gathering trend data for {len(topics)} topics…", file=sys.stderr)
    results = gather_trends(topics)

    print(f"Done. {len(results)} topics analysed.", file=sys.stderr)
    emit_json_result(
        results,
        output_path=args.output,
        artifact_kind="duckduckgo-trending-results",
    )


if __name__ == "__main__":
    main()

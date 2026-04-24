#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
# ]
# ///
"""Persistent topic monitor — tracks new articles, outputs only unseen results.

Maintains a JSON state file of previously seen URLs.  On each run, searches DDG
for the topic, filters out already-seen URLs, appends new results to the state
file, and outputs only the new results as JSON to stdout.

Output: JSON object to stdout (with ``new_results`` array).  Progress to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ddgs import DDGS

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import precondition

# Default state directory — user-scoped cache.
_STATE_DIR = Path.home() / ".cache" / "duckduckgo-skill" / "monitor"

# Default results per query — generous to catch as many new articles as possible.
_DEFAULT_RESULTS = 25  # practical DDG max for news


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication — strips protocol and www."""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


@precondition(
    lambda topic, **_: len(topic.strip()) >= 2,
    "Topic must be at least 2 characters",
)
def monitor_topic(
    topic: str,
    state_file: Path | None = None,
    max_results: int = _DEFAULT_RESULTS,
    search_type: str = "news",
) -> dict:
    """Search for a topic and return only new (previously unseen) results.

    Args:
        topic: Search query (min 2 characters).
        state_file: Path to JSON state file.  Created if missing.
        max_results: Max DDG results to fetch.
        search_type: ``"news"`` or ``"text"``.

    Returns:
        Dict with new_results, total_seen, and state_file path.
    """
    if state_file is None:
        safe_name = re.sub(r"[^\w\-]", "_", topic.lower())[:60]
        state_file = _STATE_DIR / f"{safe_name}.json"

    # Load existing state
    seen_urls: set[str] = set()
    if state_file.exists():
        try:
            existing = json.loads(state_file.read_text(encoding="utf-8"))
            seen_urls = {_normalize_url(r["url"]) for r in existing if r.get("url")}
        except (json.JSONDecodeError, KeyError):
            seen_urls = set()

    # Search DDG
    ddgs = DDGS()
    try:
        if search_type == "news":
            raw = ddgs.news(topic, max_results=max_results)
        else:
            raw = ddgs.text(topic, max_results=max_results)
    except Exception as exc:
        sys.exit(f"ERROR: DDG search failed — {exc}")

    # Filter to new results only
    new_results: list[dict] = []
    for r in raw:
        url = (r.get("url") or r.get("href") or "").strip()
        norm = _normalize_url(url)
        if norm and norm not in seen_urls:
            seen_urls.add(norm)
            new_results.append({
                "title": r.get("title", ""),
                "url": url,
                "description": (r.get("body", "") or "")[:500],
                "date": r.get("date", ""),
                "source": r.get("source", ""),
            })

    # Append new results to state file
    if new_results:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        existing_data: list[dict] = []
        if state_file.exists():
            try:
                existing_data = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                existing_data = []
        existing_data.extend(new_results)
        state_file.write_text(
            json.dumps(existing_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "new_count": len(new_results),
        "total_seen": len(seen_urls),
        "state_file": str(state_file),
        "new_results": new_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor a topic — output only new results."
    )
    parser.add_argument(
        "topic",
        help="Topic to monitor (min 2 characters)",
    )
    parser.add_argument(
        "--state-file", "-s", type=Path,
        help="Path to JSON state file (default: ~/.cache/duckduckgo-skill/monitor/<topic>.json)",
    )
    parser.add_argument(
        "--max-results", "-n", type=int, default=_DEFAULT_RESULTS,
        help=f"Max results to fetch (default {_DEFAULT_RESULTS})",
    )
    parser.add_argument(
        "--type", dest="search_type", choices=["news", "text"], default="news",
        help="Search type (default: news)",
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )
    args = parser.parse_args()

    print(f"Monitoring: {args.topic}", file=sys.stderr)
    result = monitor_topic(
        args.topic,
        state_file=args.state_file,
        max_results=args.max_results,
        search_type=args.search_type,
    )

    print(
        f"Found {result['new_count']} new articles "
        f"(total seen: {result['total_seen']}).",
        file=sys.stderr,
    )
    emit_json_result(
        result,
        output_path=args.output,
        artifact_kind="duckduckgo-monitor-results",
    )


if __name__ == "__main__":
    main()

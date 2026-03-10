#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
#   "python-dateutil >= 2.8",
#   "httpx >= 0.27",
#   "beautifulsoup4 >= 4.12",
# ]
# ///
"""Fetch news from many sources in parallel and output structured JSON.

This script is a **data-gathering facility** for the LLM.  It handles what the
LLM cannot: bulk parallel HTTP requests across 60+ DDG queries without being
blocked, author metadata extraction, and URL-level deduplication.

The LLM receives the raw JSON array and handles the intelligence work:
  • semantic deduplication (same story, different wording)
  • story clustering ("5 outlets cover X")
  • context-aware ranking based on the user's actual intent
  • presentation tailored to the conversation

Output: a JSON array on stdout where each element is:
  { title, url, source, date, description, author, query_group }

Progress messages go to stderr so they don't pollute the JSON.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from datetime import datetime, timezone
from typing import List

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from dateutil import parser as dateparser

# ---------------------------------------------------------------------------
# Page-metadata author extraction (JSON-LD → OpenGraph → <meta name=author>)
# ---------------------------------------------------------------------------
_META_FETCH_TIMEOUT = 5.0   # seconds per article; short to keep total time bounded
_META_USER_AGENT = "Mozilla/5.0 (compatible; NewsRanker/1.0 +https://github.com)"
_META_WORKERS = 12


def _author_from_jsonld(soup: BeautifulSoup) -> str:
    """Try every JSON-LD block and return the first author name found."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        # normalise to a flat list of candidate objects
        candidates: list[dict] = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = data.get("@graph", [data])
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") not in (
                "NewsArticle", "Article", "BlogPosting",
                "ReportageNewsArticle", "TechArticle",
            ):
                continue
            author = obj.get("author", {})
            if isinstance(author, str) and author:
                return author
            if isinstance(author, dict):
                name = author.get("name", "").strip()
                if name:
                    return name
            if isinstance(author, list):
                names = [a.get("name", "").strip() for a in author
                         if isinstance(a, dict) and a.get("name")]
                if names:
                    return " and ".join(names[:2])
    return ""


def _author_from_og_meta(soup: BeautifulSoup) -> str:
    """Try Open Graph article:author and <meta name=author>."""
    for attrs in (
        {"property": "article:author"},
        {"property": "og:author"},
        {"name": "author"},
        {"name": "Author"},
        {"itemprop": "author"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag:
            val = (tag.get("content") or "").strip()
            # Skip bare URLs — some sites put profile links here
            if val and not val.startswith("http"):
                return val
    # rel=author link text as last resort
    link = soup.find("a", rel="author")
    if link:
        val = link.get_text(strip=True)
        if val and len(val.split()) <= 6:
            return val
    return ""


def fetch_author_from_metadata(url: str) -> str:
    """GET the article page, parse structured metadata, return author or ''."""
    if not url:
        return ""
    try:
        resp = httpx.get(
            url,
            timeout=_META_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": _META_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en",
            },
        )
        if resp.status_code != 200:
            return ""
        # Parse only the <head> portion — author metadata is always there
        # and we avoid downloading/parsing megabyte bodies.
        raw_head = resp.text[:60_000]
        soup = BeautifulSoup(raw_head, "html.parser")
        return _author_from_jsonld(soup) or _author_from_og_meta(soup)
    except Exception:
        return ""


def enrich_authors(stories: list[dict], max_fetch: int = 40) -> None:
    """Parallel metadata fetch for top stories that have no author yet.

    Fetches are limited to `max_fetch` stories and use a short per-request
    timeout so a handful of slow/blocked URLs don't delay the whole output.
    """
    targets = [s for s in stories[:max_fetch] if not s.get("author") and s.get("url")]
    if not targets:
        return
    print(f"Fetching author metadata for {len(targets)} articles…")
    with concurrent.futures.ThreadPoolExecutor(max_workers=_META_WORKERS) as ex:
        future_to_story = {
            ex.submit(fetch_author_from_metadata, s["url"]): s for s in targets
        }
        for fut in concurrent.futures.as_completed(future_to_story, timeout=30):
            story = future_to_story[fut]
            try:
                author = fut.result(timeout=6)
                if author:
                    story["author"] = author
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Comprehensive query catalogue — each group targets a different slice of the
# information ecosystem so that important stories bubble up regardless of topic.
# ---------------------------------------------------------------------------
QUERY_GROUPS: dict[str, list[str]] = {
    # Broad sweep — seeds the pool with high-volume, cross-domain coverage
    "broad": [
        "world news today",
        "breaking news",
        "top stories",
        "international news",
    ],
    # Wire services — highest factual authority, cited by all other outlets
    "wires": [
        "site:reuters.com",
        "site:apnews.com",
    ],
    # Anglophone newspapers of record
    "print": [
        "site:nytimes.com",
        "site:theguardian.com",
        "site:washingtonpost.com",
        "site:ft.com",
        "site:wsj.com",
        "site:economist.com",
        "site:theatlantic.com",
        "site:newyorker.com",
    ],
    # Broadcast / digital-native news
    "broadcast": [
        "site:bbc.com",
        "site:cnn.com",
        "site:nbcnews.com",
        "site:cbsnews.com",
        "site:abcnews.go.com",
        "site:pbs.org/newshour",
        "site:sky.com/news",
    ],
    # Finance & business
    "finance": [
        "site:bloomberg.com",
        "site:cnbc.com",
        "site:marketwatch.com",
        "site:fortune.com",
        "site:businessinsider.com",
    ],
    # Policy, politics, investigations
    "policy": [
        "site:politico.com",
        "site:axios.com",
        "site:vox.com",
        "site:foreignaffairs.com",
        "site:propublica.org",
        "site:theintercept.com",
    ],
    # Technology
    "tech": [
        "site:techcrunch.com",
        "site:arstechnica.com",
        "site:theverge.com",
        "site:wired.com",
        "site:slashdot.org",
        "site:thenextweb.com",
        "site:zdnet.com",
        "site:venturebeat.com",
    ],
    # Science & academic
    "science": [
        "site:nature.com",
        "site:science.org",
        "site:newscientist.com",
        "site:scientificamerican.com",
        "site:acm.org",
        "site:ieee.org",
        "site:arxiv.org",
        "site:phys.org",
    ],
    # International / non-English press (English editions)
    "international": [
        "site:spiegel.de/international",
        "site:lemonde.fr/en",
        "site:elpais.com/usa",
        "site:japan-forward.com",
        "site:hindustantimes.com",
        "site:aljazeera.com",
        "site:france24.com",
        "site:dw.com/en",
    ],
    # Social aggregators & community signals
    "social": [
        "site:reddit.com/r/worldnews",
        "site:reddit.com/r/news",
        "site:news.ycombinator.com",
    ],
    # Independent / newsletter / long-read
    "independent": [
        "site:substack.com",
        "site:medium.com",
        "site:bellingcat.com",
    ],
}

# Per-outlet prominence score (0–1).  Reflects editorial standards + global
# reach.  Social / aggregator sources get a boost for cross-source signal only.
KNOWN_PROMINENCE: dict[str, float] = {
    # Wire services — top tier
    "reuters": 1.0,
    "associated press": 1.0,
    "ap news": 1.0,
    # Financial tier-1
    "bloomberg": 0.97,
    "financial times": 0.97,
    "ft.com": 0.97,
    "wsj": 0.95,
    "wall street journal": 0.95,
    # Newspapers of record
    "nytimes": 0.95,
    "new york times": 0.95,
    "washington post": 0.93,
    "the guardian": 0.92,
    "bbc": 0.92,
    "economist": 0.94,
    "the atlantic": 0.88,
    "new yorker": 0.87,
    # Broadcast / digital-native
    "cnn": 0.85,
    "nbc": 0.84,
    "abc news": 0.84,
    "cbs news": 0.83,
    "pbs": 0.83,
    "sky news": 0.82,
    # Finance & business
    "cnbc": 0.82,
    "fortune": 0.78,
    "marketwatch": 0.78,
    "business insider": 0.72,
    # Policy / investigations
    "politico": 0.82,
    "axios": 0.80,
    "vox": 0.76,
    "foreign affairs": 0.85,
    "propublica": 0.85,
    "the intercept": 0.75,
    # Tech press
    "ars technica": 0.82,
    "wired": 0.80,
    "the verge": 0.78,
    "techcrunch": 0.75,
    "thenextweb": 0.70,
    "zdnet": 0.68,
    "venturebeat": 0.68,
    "slashdot": 0.65,
    # Science / academic
    "nature": 0.96,
    "science": 0.95,
    "new scientist": 0.85,
    "scientific american": 0.88,
    "acm": 0.82,
    "ieee": 0.82,
    "arxiv": 0.70,
    "phys.org": 0.72,
    # International press
    "spiegel": 0.85,
    "le monde": 0.85,
    "el pais": 0.82,
    "france24": 0.80,
    "dw": 0.80,
    "hindustan times": 0.72,
    "al jazeera": 0.65,
    "aljazeera": 0.65,
    # Opinion-heavy / partisan
    "fox": 0.62,
    "msnbc": 0.65,
    # Independents
    "bellingcat": 0.80,
    "substack": 0.50,
    "medium": 0.45,
}


# Byline patterns found in wire/newspaper article bodies:
#   "By Jane Smith"  /  "By Jane Smith,"  /  "By Jane Smith and John Doe"
#   "By Jane Smith | Reuters"  /  "By Jane Smith\nNEW YORK, March 9 (Reuters)"
# Each name word: starts uppercase, ≤20 chars, letters/hyphens/apostrophes/accents only.
# The word boundary (?=[\s,.|(\n]) prevents consuming run-on dateline text like
# "QueenNEW YORK" where the city is concatenated to the surname.
_NW = r"[A-Z][a-zA-Z\u00c0-\u024f'-]{0,19}"
# \x20 = literal space only — stops capture at newline so "By Jack Queen\nNEW YORK"
# doesn't bleed the city into the name group.
_BYLINE_RE = re.compile(
    r"^\s*By\x20+"
    r"(" + _NW + r"(?:\x20+" + _NW + r"){1,4})"
    r"(?:\x20+and\x20+(" + _NW + r"(?:\x20+" + _NW + r"){1,4}))?",
    re.MULTILINE,
)
_MONTHS = {
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    "January", "February", "March", "April", "June", "July", "August",
    "September", "October", "November", "December",
}
_ALLCAPS_OR_MONTH = re.compile(r"^[A-Z]{2,}")


def _chop_dateline(token: str) -> str:
    """Strip fused dateline suffix from a name token.

    E.g. "QueenNEW" -> "Queen", "WolfeMarch" -> "Wolfe"
    Safe for Mc/Mac prefixes: "McCoy" -> "McCoy".
    """
    m = re.search(r"(?<=[a-z])(?=[A-Z])", token)
    if not m:
        return token
    tail = token[m.start():]
    if _ALLCAPS_OR_MONTH.match(tail) or any(tail.startswith(mo) for mo in _MONTHS):
        return token[: m.start()]
    return token


def extract_byline(body: str) -> str:
    """Return author name(s) parsed from the article body, or empty string."""
    if not body:
        return ""
    # Only look in the first 300 chars — bylines are always near the top
    head = body[:300]
    m = _BYLINE_RE.search(head)
    if not m:
        return ""

    def clean(raw: str) -> str:
        tokens = raw.strip().split()
        out = []
        for tok in tokens:
            # Drop ALL-CAPS tokens — these are city/dateline words ("NEW", "YORK")
            if tok.isupper() and len(tok) > 1:
                break
            # Chop dateline suffix fused to a name token ("QueenNEW" → "Queen")
            cleaned = _chop_dateline(tok).rstrip(".,- ")
            if cleaned:
                out.append(cleaned)
        return " ".join(out)

    name = clean(m.group(1))
    if m.group(2):
        name += " and " + clean(m.group(2))
    if not name or len(name.split()) > 6:
        return ""
    return name


def source_prominence(source: str) -> float:
    """Return 0–1 prominence score for an outlet.  Exposed so the LLM can
    reference it, but the LLM is expected to apply its own judgement."""
    s = (source or "").lower()
    for k, v in KNOWN_PROMINENCE.items():
        if k in s:
            return v
    return 0.35  # unknown outlet baseline


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _build_query_map(groups: list[str]) -> dict[str, str]:
    """Return {query: group_name} for the selected groups."""
    qmap: dict[str, str] = {}
    for g in groups:
        for q in QUERY_GROUPS.get(g, []):
            qmap[q] = g
    return qmap


def fetch_news(
    query_map: dict[str, str],
    per_query: int = 20,
) -> list[dict]:
    """Fetch news for all queries in parallel, each with its own DDGS instance.

    Returns a flat list of article dicts, each tagged with ``query_group``.
    """
    queries = list(query_map)

    def fetch_one(q: str) -> list:
        try:
            return DDGS().news(q, max_results=per_query)
        except Exception:
            return []

    results: list[dict] = []
    seen_urls: set[str] = set()  # URL-level dedup — exact same article
    max_workers = min(12, len(queries))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_q = {ex.submit(fetch_one, q): q for q in queries}
        for fut in concurrent.futures.as_completed(future_to_q, timeout=90):
            q = future_to_q[fut]
            try:
                raw = fut.result(timeout=12)
            except Exception:
                raw = []
            group = query_map.get(q, "")
            for r in raw:
                url = (r.get("url", "") or "").strip()
                # Skip exact-URL duplicates so the LLM doesn't waste context
                norm_url = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
                if norm_url in seen_urls:
                    continue
                seen_urls.add(norm_url)
                results.append(
                    {
                        "title": r.get("title", "") or "",
                        "url": url,
                        "source": r.get("source", "") or "",
                        "date": r.get("date", "") or "",
                        "description": (r.get("body", "") or "")[:1200],
                        "author": (
                            r.get("author", "")
                            or extract_byline(r.get("body", "") or "")
                        ),
                        "query_group": group,
                    }
                )
    return results


# ---------------------------------------------------------------------------
# Entry point — output JSON to stdout, progress to stderr
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch news from many sources and output structured JSON."
    )
    parser.add_argument(
        "--per-query", "-n", type=int, default=20,
        help="Max results per DDG query (default 20)",
    )
    parser.add_argument(
        "--groups", "-g", nargs="*", default=None,
        help=(
            "Source groups to query (default: all).  "
            f"Choices: {list(QUERY_GROUPS)}"
        ),
    )
    parser.add_argument(
        "--queries", "-q", nargs="*", default=None,
        help="Additional free-form DDG news queries (mixed with groups)",
    )
    parser.add_argument(
        "--enrich-authors", "-a", action="store_true", default=False,
        help="Fetch page metadata to fill in missing author names (adds ~10–20 s)",
    )
    parser.add_argument(
        "--max-enrich", type=int, default=60,
        help="Max articles to fetch author metadata for (default 60)",
    )
    args = parser.parse_args()

    # Build the query map from selected groups
    selected_groups = args.groups or list(QUERY_GROUPS)
    query_map = _build_query_map(selected_groups)

    # Add any free-form queries under a "custom" pseudo-group
    if args.queries:
        for q in args.queries:
            query_map[q] = "custom"

    if not query_map:
        print("No queries to run.", file=sys.stderr)
        sys.exit(1)

    print(
        f"Fetching from {len(query_map)} queries across "
        f"{len(selected_groups)} groups…",
        file=sys.stderr,
    )
    results = fetch_news(query_map, per_query=args.per_query)

    if not results:
        print("No results found.", file=sys.stderr)
        json.dump([], sys.stdout)
        return

    print(f"Collected {len(results)} unique articles.", file=sys.stderr)

    # Optional author enrichment via page metadata
    if args.enrich_authors:
        enrich_authors(results, max_fetch=args.max_enrich)

    # Emit JSON to stdout — the LLM reads this and does the smart work
    json.dump(results, sys.stdout, ensure_ascii=False, indent=None)
    print(file=sys.stdout)  # trailing newline


if __name__ == "__main__":
    main()

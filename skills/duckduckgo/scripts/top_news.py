#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ddgs >= 6.0",
#   "python-dateutil >= 2.8",
# ]
# ///
"""Fetch comprehensive global news via DuckDuckGo and rank by impact.

Covers: mainstream news wires, print media, broadcast, tech/science blogs,
academic publishers, finance, international & regional press, and social
aggregators (Reddit, Hacker News).

Impact metric (equal weights A + B + C):
  A — cross-source frequency: how many independent queries surfaced the story
  B — recency + prominence: freshness × outlet authority
  C — engagement proxy: keyword signals (breaking, exclusive, fatalities, ...)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import textwrap
from datetime import datetime, timezone
from typing import List

from ddgs import DDGS
from dateutil import parser as dateparser

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
    s = (source or "").lower()
    for k, v in KNOWN_PROMINENCE.items():
        if k in s:
            return v
    return 0.35  # unknown outlet baseline


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_news(queries: List[str], per_query: int = 20) -> List[dict]:
    """Fetch news for all queries in parallel, each with its own DDGS instance."""

    def fetch_one(q: str) -> list:
        try:
            # Each thread gets its own client to avoid shared-state races
            return DDGS().news(q, max_results=per_query)
        except Exception:
            return []

    results: list[dict] = []
    max_workers = min(12, len(queries))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_q = {ex.submit(fetch_one, q): q for q in queries}
        for fut in concurrent.futures.as_completed(future_to_q, timeout=90):
            q = future_to_q[fut]
            try:
                raw = fut.result(timeout=12)
            except Exception:
                raw = []
            for r in raw:
                results.append(
                    {
                        "query": q,
                        "title": r.get("title", "") or "",
                        "url": r.get("url", "") or "",
                        "description": (r.get("body", "") or "")[:1200],
                        "date": r.get("date", "") or "",
                        "source": r.get("source", "") or "",
                        "author": r.get("author", "") or extract_byline(r.get("body", "") or ""),
                    }
                )
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", t or "")).strip().lower()


def normalize_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def parse_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return dateparser.parse(s)
    except Exception:
        return None


def fmt_date(s: str) -> str:
    d = parse_date(s)
    if d:
        return d.strftime("%b %d, %Y %H:%M UTC").replace(" 0", " ")
    return s or "—"


def compute_scores(items: List[dict]) -> List[dict]:
    # Cluster by normalised title so the same story from many outlets merges
    clusters: dict[str, list[dict]] = {}
    for it in items:
        key = normalize_title(it["title"])[:120]
        if not key:
            key = normalize_url(it.get("url", ""))[:120]
        if not key:
            continue
        clusters.setdefault(key, []).append(it)

    scored: list[dict] = []
    now = datetime.now(timezone.utc)
    max_mentions = max((len(v) for v in clusters.values()), default=1)

    for _key, group in clusters.items():
        canonical = group[0].copy()
        mentions = len(group)

        # A — cross-source frequency
        sources_score = mentions / max_mentions

        # B — recency (decays linearly over 7 days)
        dates = [parse_date(g.get("date", "")) for g in group]
        dates_valid = [d for d in dates if d is not None]
        if dates_valid:
            most_recent = max(dates_valid)
            hours_old = (now - most_recent).total_seconds() / 3600.0
            recency_score = max(0.0, 1.0 - hours_old / (24 * 7))
            # store the best date back on the canonical item for display
            canonical["date"] = most_recent.isoformat()
        else:
            recency_score = 0.1

        # B — prominence: best outlet across all group items
        prominence_score = max(source_prominence(g.get("source", "")) for g in group)

        # collect all sources in the group for display
        canonical["all_sources"] = sorted(
            {g.get("source", "") for g in group if g.get("source")}
        )

        # C — engagement keyword proxy
        engagement = 0.0
        txt = (canonical.get("title", "") + " " + canonical.get("description", "")).lower()
        if "breaking" in txt:
            engagement += 0.30
        if "exclusive" in txt:
            engagement += 0.20
        if any(w in txt for w in ("killed", "dead", "dies", "disaster", "crisis", "war", "attack")):
            engagement += 0.10
        if any(w in txt for w in ("record", "historic", "milestone", "landmark")):
            engagement += 0.05
        engagement = min(1.0, engagement)

        # Combined score — equal weights A + B + C
        b = (recency_score + prominence_score) / 2.0
        total = (sources_score + b + ((engagement + b) / 2.0)) / 3.0

        canonical.update(
            {
                "mentions": mentions,
                "sources_score": round(sources_score, 3),
                "recency_score": round(recency_score, 3),
                "prominence_score": round(prominence_score, 3),
                "engagement": round(engagement, 3),
                "impact": round(total, 4),
            }
        )
        scored.append(canonical)

    scored.sort(key=lambda x: x["impact"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
SEP = "─" * 72


def print_story(rank: int, s: dict) -> None:
    title = s.get("title", "(no title)")
    source = s.get("source", "")
    all_srcs = s.get("all_sources", [])
    date_str = fmt_date(s.get("date", ""))
    url = s.get("url", "")
    description = s.get("description", "")
    author = s.get("author", "")

    # Build a tidy 1-2 sentence summary from the description,
    # skipping any leading byline line ("By Name ...") so it doesn't duplicate
    body_lines = description.strip().splitlines()
    if body_lines and _BYLINE_RE.match(body_lines[0]):
        body_lines = body_lines[1:]
    clean_body = " ".join(body_lines).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean_body)
    summary = " ".join(sentences[:2]).strip()
    if summary and len(summary) > 280:
        summary = summary[:277] + "…"

    # Build the source line
    src_display = source
    if all_srcs and len(all_srcs) > 1:
        extras = [s2 for s2 in all_srcs if s2 != source][:3]
        src_display = source + (f"  +also: {', '.join(extras)}" if extras else "")

    impact_line = (
        f"Impact {s['impact']:.4f}  "
        f"[freq={s['sources_score']:.2f}  "
        f"recent={s['recency_score']:.2f}  "
        f"prominence={s['prominence_score']:.2f}  "
        f"engagement={s['engagement']:.2f}  "
        f"mentions={s['mentions']}]"
    )

    print(SEP)
    # Wrap long titles at 70 chars
    wrapped = textwrap.fill(f"#{rank}  {title}", width=70, subsequent_indent="    ")
    print(wrapped)
    print(f"  Source : {src_display}")
    if author:
        print(f"  Author : {author}")
    print(f"  Date   : {date_str}")
    if summary:
        wrapped_sum = textwrap.fill(summary, width=68, initial_indent="  Summary: ", subsequent_indent="           ")
        print(wrapped_sum)
    print(f"  {impact_line}")
    print(f"  Link   : {url}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Top global news ranked by impact")
    parser.add_argument("--per-query", "-n", type=int, default=20,
                        help="Max results per query (default 20 — keeps rate limits safe)")
    parser.add_argument("--top", "-t", type=int, default=20,
                        help="Number of top stories to display")
    parser.add_argument("--groups", "-g", nargs="*", default=None,
                        help="Query groups to use (default: all). "
                             f"Choices: {list(QUERY_GROUPS)}")
    args = parser.parse_args()

    selected_groups = args.groups or list(QUERY_GROUPS)
    queries: list[str] = []
    for g in selected_groups:
        if g in QUERY_GROUPS:
            queries.extend(QUERY_GROUPS[g])
        else:
            print(f"Warning: unknown group '{g}', skipping")

    if not queries:
        print("No queries to run.")
        return

    print(f"Fetching from {len(queries)} queries across {len(selected_groups)} groups…")
    raw = fetch_news(queries, per_query=args.per_query)
    if not raw:
        print("No results found.")
        return

    print(f"Collected {len(raw)} raw items — scoring & deduplicating…\n")
    scored = compute_scores(raw)
    top = scored[: args.top]

    print(f"{SEP}\n  TOP {args.top} GLOBAL STORIES BY IMPACT  —  {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}\n{SEP}")
    for i, s in enumerate(top, 1):
        print_story(i, s)
    print(SEP)


if __name__ == "__main__":
    main()

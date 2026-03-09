---
name: duckduckgo
description: Searches the internet via DuckDuckGo for text, image, news, and comprehensive ranked global news; downloads web pages as txt, md, or pdf. Use when the user asks to search the web, find images, look up current news on a specific topic, wants a ranked overview of the most impactful global stories right now, or wants to save/download/archive a URL. Scripts — search.py (text/image/news), vision.py (visual analysis), top_news.py (comprehensive ranked world news with author + summary), download.py (fetch URL → txt/md/pdf).
allowed-tools:
  - Bash(uv run *)
  - open_browser_page
user-invocable: true
---

# DuckDuckGo Search Skill

## Script Decision Guide

Use this table to pick the right script **before** running anything:

| User says… | Script | Why |
|---|---|---|
| "search for X", "find pages about X", "look up X" | `search.py text` | General web search |
| "find images of X", "show me pictures of X" | `search.py image` | Image search |
| "news about X", "latest on X", "what happened with X" | `search.py news` | Targeted news on a specific topic |
| "top news", "what's happening in the world", "world news", "most important stories", "news digest", "daily briefing", "rank news by impact" | `top_news.py` | Comprehensive multi-source ranked news |
| "save this page", "download this article", "fetch this URL", "archive this link", "save as pdf/markdown/text", "get me the content of this page" | `download.py` | Fetch URL and save as file |
| "analyse this image", "what is in this image" | `vision.py analyze` | Image content analysis |
| "find images similar to this", "reverse image search" | `vision.py find_similar` | Visual similarity search |

**Key distinction — `search.py news` vs `top_news.py`:**
- `search.py news` → one query, returns raw results for a *specific topic*. Fast, ~1–2 s.
- `top_news.py` → 62+ queries across 11 source groups, deduplicates, scores by cross-source frequency + recency + prominence + engagement, enriches with page metadata for author names. Use when the user wants a *comprehensive, ranked world news digest*. Takes ~30–60 s.

## Quick Start

```bash
# Text search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query" [--max-results N]

# Image search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--size size] [--type type] [--color color] [--max-results N]

# News on a specific topic:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query" [--max-results N]

# Download a URL as txt, md, or pdf:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> [--format txt|md|pdf] [--output PATH]

# Comprehensive ranked world news digest (top 20 by impact):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py [--top N] [--per-query N] [--groups GROUP …]

# Visual search / image analysis:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH
```

## `download.py` — Fetch a URL and Save to File

Fetches any public web page and saves it locally.

```bash
# Save as Markdown (default filename derived from URL):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py https://example.com/article --format md

# Save as PDF with explicit output path:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py https://example.com/article --format pdf --output ~/Desktop/article.pdf

# Save as plain text:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py https://example.com/article --output article.txt
```

**Format selection**: pass `--format txt|md|pdf`, or let the extension of `--output` decide. Defaults to `txt`.

**LLM trigger phrases**: "save this page", "download this article", "fetch URL as PDF", "archive this link", "save as markdown", "get me the content of X"

**Notes**: removes nav/footer/script noise; paywalled pages return only publicly visible content.

## `top_news.py` — Comprehensive Ranked News

Sources span 11 groups (62+ queries): wire services (Reuters, AP), print (NYT, Guardian, FT, WSJ, Economist, Atlantic, New Yorker), broadcast (BBC, CNN, NBC, CBS, ABC, PBS, Sky), finance (Bloomberg, CNBC), policy (Politico, Axios, Vox, Foreign Affairs, ProPublica), tech (TechCrunch, Ars Technica, The Verge, Wired, Slashdot), science/academic (Nature, Science, New Scientist, Scientific American, ACM, IEEE, arXiv), international (Spiegel, Le Monde, El País, France24, DW, Hindustan Times, Al Jazeera), social (Reddit r/worldnews, r/news, Hacker News), independent (Bellingcat, Substack, Medium).

**Impact score** (all equal weight):
- **A — frequency**: how many distinct queries surfaced the story
- **B — recency × prominence**: freshness (7-day linear decay) × outlet authority score
- **C — engagement proxy**: keyword signals (`breaking`, `exclusive`, crisis/fatality words)

**Author enrichment pipeline**: DDG body byline regex → page metadata fetch (JSON-LD `NewsArticle.author` → Open Graph `article:author` → `<meta name="author">` → `rel="author"` link). Shown only when confidently extracted; never fabricated.

**Output per story**: rank, title, source (+ cross-outlet picks), author (when found), date (UTC), 1–2 sentence summary, impact breakdown, link.

**Useful flags**:
```bash
--top 20          # how many stories to show (default 20)
--per-query 20    # DDG results per query (default 20; raise to 40 for broader pool)
--groups tech science  # restrict to specific source groups
```
Available groups: `broad`, `wires`, `print`, `broadcast`, `finance`, `policy`, `tech`, `science`, `international`, `social`, `independent`.

## Image Display

VS Code Copilot does NOT render inline images (`![](url)` or `<img>` tags). When the user asks to **show/display images**:
1. Present results as a numbered markdown list with clickable `[title](url)` links.
2. Open the first 3 images in the browser using `open_browser_page` so the user can see them.

Do NOT use `![alt](url)` syntax — it does not display in Copilot chat.

## Limitations

- **Rate limit**: ~35 queries/minute for `search.py`; `top_news.py` uses parallel workers and respects this automatically.
- **`search.py` defaults**: 9 text/news results, 30 images — override with `--max-results N`.
- **Author coverage**: wire-service and open-access articles yield authors reliably; paywalled pages (WSJ, FT, NYT) usually block metadata fetch — shown as no Author line.
- **No login required** — public API only.

## Technical Details

- **Libraries** — `ddgs` (DDG API), `httpx` + `beautifulsoup4` + `truststore` (metadata fetch and download), `html2text` + `fpdf2` (format conversion in `download.py`), `python-dateutil`
- **Python** ≥3.11, PEP 723 inline metadata in every script
- **Runtime** — `uv run --no-config` for isolated execution

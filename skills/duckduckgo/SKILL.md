---
name: duckduckgo
description: Searches the internet via DuckDuckGo and downloads web pages. Scripts output JSON to stdout so the LLM does the ranking, dedup, clustering, and presentation. Use when the user asks to search the web, find images, look up news, wants a comprehensive multi-source news digest, or wants to download/archive a URL. Scripts — search.py (text/image/news JSON), top_news.py (multi-source news JSON), download.py (fetch URL → txt/md/pdf), vision.py (visual analysis).
allowed-tools:
  - Bash(uv run *)
  - open_browser_page
user-invocable: true
---

# DuckDuckGo Search Skill

## Architecture — Scripts Are Data Pipes, LLM Is the Brain

Scripts handle what the LLM cannot: parallel HTTP requests, DDG API calls, rate-limit management, SSL, and structured metadata extraction. They output **JSON to stdout** (progress to stderr).

The LLM handles what scripts cannot: semantic deduplication, story clustering ("5 outlets cover X"), context-aware ranking based on the user's actual request, follow-up research via `download.py`, and tailored presentation.

**Workflow pattern**: gather data → LLM analyses → (optionally) dig deeper → present to user.

## Script Decision Guide

| User says… | Script | What it returns |
|---|---|---|
| "search for X", "find pages about X" | `search.py text` | JSON array of `{title, url, description}` |
| "find images of X", "show me pictures" | `search.py image` | JSON array of `{title, url, image, thumbnail, source}` |
| "news about X", "latest on X" | `search.py news` | JSON array of `{title, url, description, date, source}` |
| "top news", "world news", "news digest", "what's happening" | `top_news.py` | JSON array from 62+ parallel queries across 11 source groups |
| "top AI news", "news about climate from all sources" | `top_news.py --groups tech --queries "AI breakthroughs"` | Combine groups + custom queries |
| "save/download/archive this page" | `download.py` | Saved file (txt/md/pdf) |
| "analyse/describe this image" | `vision.py analyze` | Analysis text |
| "find similar images" | `vision.py find_similar` | Similar image results |

## Quick Start

```bash
# Text search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query" [--max-results N]

# News search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query" [--max-results N]

# Image search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--max-results N]

# Multi-source news sweep — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py [--groups GROUP …] [--queries "Q1" "Q2" …] [--per-query N] [--enrich-authors]

# Download a URL:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> [--format txt|md|pdf] [--output PATH]

# Visual search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH
```

## How the LLM Should Use These

### Single-topic research
1. Run `search.py news --query "topic" --max-results 20` — get JSON
2. Read the JSON, deduplicate semantically, rank by relevance to the user's question
3. If a story needs deeper reading, use `download.py <url> --format md` to fetch full text
4. Synthesise and present

### Comprehensive news digest
1. Run `top_news.py` (all groups) or `top_news.py --groups tech science --queries "AI regulation"` for a focused sweep
2. Receive hundreds of articles as JSON with `{title, url, source, date, description, author, query_group}`
3. Cluster by topic (same event covered by different outlets → one story with multiple sources)
4. Rank by the user's stated criteria (impact, recency, topic relevance, etc.)
5. For important stories, optionally `download.py` the top URLs to read the full article
6. Present with source attribution, clustering ("also covered by…"), dates, and summaries

### Deep research / spider mode
1. Start with `search.py text` or `top_news.py` to discover relevant URLs
2. Use `download.py --format md` to fetch each promising link as markdown
3. Read the downloaded content, extract key facts, discover new leads
4. Run further `search.py` queries based on what was learned
5. Synthesise findings across all sources

## Presentation Rules — MANDATORY

When presenting search or news results, ALWAYS include **every** field the JSON returned. NEVER drop fields to make a narrower table.

**Required columns for news results** (table or list):
- **#** — rank position
- **Date** — human-readable
- **Title** — as a clickable markdown link: `[Title](url)`
- **Source** — publication/outlet name from the `source` field
- **Summary** — the `description` field, 1–2 sentences. This is the most valuable field for the user — it tells them what the article says without clicking.
- **Author** — when present in JSON (e.g. from `--enrich-authors`). Omit column if no results have it.

**Required columns for text search results**:
- **Title** — clickable link
- **Summary** — the `description` field
- **Site** — domain extracted from URL

**After the table**, add a "Key themes" section that clusters results by topic and highlights patterns across sources.

NEVER present a table with only title + date + source. The `description` field exists in every result — use it.

## `top_news.py` — Multi-Source News Fetcher

Queries 11 source groups (62+ queries) in parallel via DDG News API:

| Group | Outlets |
|---|---|
| `broad` | "world news today", "breaking news", "top stories", "international news" |
| `wires` | Reuters, AP |
| `print` | NYT, Guardian, WashPost, FT, WSJ, Economist, Atlantic, New Yorker |
| `broadcast` | BBC, CNN, NBC, CBS, ABC, PBS, Sky |
| `finance` | Bloomberg, CNBC, MarketWatch, Fortune, Business Insider |
| `policy` | Politico, Axios, Vox, Foreign Affairs, ProPublica, The Intercept |
| `tech` | TechCrunch, Ars Technica, The Verge, Wired, Slashdot, TNW, ZDNet, VentureBeat |
| `science` | Nature, Science, New Scientist, SciAm, ACM, IEEE, arXiv, Phys.org |
| `international` | Spiegel, Le Monde, El País, Japan Forward, Hindustan Times, Al Jazeera, France24, DW |
| `social` | Reddit r/worldnews, r/news, Hacker News |
| `independent` | Substack, Medium, Bellingcat |

**Flags**:
- `--groups tech science` — restrict to specific groups
- `--queries "AI boom" "LLM safety"` — add free-form queries (tagged `query_group: "custom"`)
- `--per-query 20` — DDG results per query (default 20)
- `--enrich-authors` — fetch page metadata (JSON-LD/OG) for author names (adds ~10–20 s)
- `--max-enrich 60` — cap how many articles get metadata fetch

**Output**: JSON array, URL-deduplicated.  Each element:
```json
{"title": "…", "url": "…", "source": "Reuters", "date": "2026-03-10T…", "description": "…", "author": "Jane Smith", "query_group": "wires"}
```

## `download.py` — Fetch URL to File

Fetches any public web page, strips noise (nav/scripts/ads), saves as txt, md, or pdf.

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> --format md
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> --format pdf --output ~/Desktop/article.pdf
```

PDF uses Computer Modern fonts (Knuth-style typography). Format auto-inferred from `--output` extension.

## Image Display

VS Code Copilot does NOT render `![](url)` or `<img>`. Present image results as clickable `[title](url)` links and open the first 3 via `open_browser_page`.

## Limitations

- **Rate limit**: ~35 queries/minute; `top_news.py` uses parallel workers within this budget
- **Paywalled pages**: `download.py` returns only publicly visible content
- **Author coverage**: `--enrich-authors` works for wire/open-access articles; paywalled sites block metadata
- **No login required** — public API only

## Technical Details

- **Libraries** — `ddgs` (DDG API), `httpx` + `beautifulsoup4` (metadata + download), `truststore` (macOS SSL), `html2text` + `fpdf2` (format conversion), `python-dateutil`
- **Python** ≥3.11, PEP 723 inline metadata in every script
- **Runtime** — `uv run --no-config` for isolated execution
- **Output** — `search.py` and `top_news.py` emit JSON to stdout; progress/errors go to stderr

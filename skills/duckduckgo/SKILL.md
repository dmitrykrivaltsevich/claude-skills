---
name: duckduckgo
description: Searches the internet via DuckDuckGo and downloads web pages. Scripts output JSON to stdout so the LLM does the ranking, dedup, clustering, and presentation. Use when the user asks to search the web, find images, look up news, wants a news digest, wants to download/archive a URL, wants to detect trending topics, verify claims across sources, monitor topics for new articles, or search across languages/regions. Scripts — search.py, top_news.py, download.py, vision.py, trending.py, fact_check.py, monitor.py, translate_search.py.
allowed-tools:
  - Bash(uv run *)
  - open_browser_page
user-invocable: true
---

# DuckDuckGo Search Skill

## Contents

1. [Architecture](#architecture--scripts-are-data-pipes-llm-is-the-brain)
2. [Script Decision Guide](#script-decision-guide)
3. [Quick Start](#quick-start)
4. [Time Filtering](#time-filtering--timelimit)
5. [Workflow Patterns](#how-the-llm-should-use-these)
6. [Presentation Rules](#presentation-rules--mandatory)
7. [top_news.py Details](#top_newspy--multi-source-news-fetcher)
8. [download.py Details](#downloadpy--fetch-url-to-file)
9. [Image Display](#image-display)
10. [Limitations](#limitations)
11. [Technical Details](#technical-details)

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
| "analyse/describe this image" | `vision.py analyze` | Image metadata JSON |
| "find similar images" | `vision.py find_similar` | Metadata + image results JSON |
| "what's trending", "trending topics" | `trending.py --discover` | Per-topic trend data JSON |
| "is X trending", "how hot is Y" | `trending.py --topics "X" "Y"` | Per-topic trend data JSON |
| "is this true", "verify this claim" | `fact_check.py "claim"` | Per-tier cross-reference JSON |
| "watch this topic", "any new articles on X" | `monitor.py "topic"` | New-only results JSON |
| "search in French/German/etc." | `translate_search.py` | Region-tagged results JSON |

## Quick Start

```bash
# Text search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query" [--max-results N] [--timelimit d|w|m|y]

# News search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query" [--max-results N] [--timelimit d|w|m|y]

# Image search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--max-results N] [--timelimit Day|Week|Month|Year]

# Multi-source news sweep — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py [--groups GROUP …] [--queries "Q1" "Q2" …] [--per-query N] [--timelimit d|w|m|y] [--enrich-authors]

# Download a URL:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> [--format txt|md|pdf] [--output PATH]

# Visual search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH

# Trend detection:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --topics "AI regulation" "climate summit"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --discover

# Claim cross-referencing:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "Ukraine ceasefire agreement"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "claim text" --tiers wires broadsheets

# Topic monitoring:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/monitor.py "AI safety" [--state-file PATH] [--type news|text]

# Multi-region search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/translate_search.py "fr-fr:intelligence artificielle" "de-de:künstliche Intelligenz" "us-en:artificial intelligence"
```

## Time Filtering — `--timelimit`

All search scripts support `--timelimit` to restrict results by recency:

| User says… | `--timelimit` value |
|---|---|
| "past 24 hours", "today", "yesterday" | `d` |
| "this week", "past few days", "past 7 days" | `w` |
| "this month", "past few weeks", "past 30 days" | `m` |
| "this year", "past few months", "past year" | `y` |
| "old articles", "from 2020", "5 years ago" | omit timelimit — filter by date in results JSON |
| no time constraint mentioned | omit `--timelimit` (default: no filter) |

For **image search**, use capitalized values: `Day`, `Week`, `Month`, `Year`.

For periods the API doesn't directly support ("past 3 months", "2019–2021"), omit `--timelimit` and filter the returned JSON by the `date` field.

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

### Trend detection
1. Run `trending.py --discover` to auto-discover trending topics, or `--topics "X" "Y"` for specific ones
2. Receive per-topic JSON: `news_24h_count`, `news_7d_count`, `sources_24h`, `sample_headlines`, `related_queries`
3. Compute velocity: topics where `24h_count / 7d_count` is high are accelerating
4. Present: "These 3 stories are blowing up right now" with source counts and date ranges
5. Optionally `download.py` top headlines for full-text analysis

### Claim verification
1. Run `fact_check.py "claim text"` — searches across 7 tiers (wires, broadsheets, broadcast, finance, investigation, independent, social)
2. Receive per-tier results: which outlets cover it, their headlines, descriptions
3. Assess: wire coverage = strong signal; broadsheet-only = developing; social-only = unverified
4. Present tier-by-tier comparison with agreement/divergence analysis

### Topic monitoring
1. Run `monitor.py "topic"` — it tracks seen URLs in a state file
2. On first run: all results are "new"; on subsequent runs: only unseen articles appear
3. Present: "3 new articles since your last check" with the new results
4. State file location: `~/.cache/duckduckgo-skill/monitor/<topic>.json` (or custom via `--state-file`)

### Multi-language research
1. The LLM translates the user's query into target languages
2. Run `translate_search.py "fr-fr:query_fr" "de-de:query_de" "us-en:query_en"`
3. Results are tagged with `region` and `language` for attribution
4. Cross-compare: stories that appear in multiple language editions are high-signal

### Deep research / spider mode
1. Start with `search.py text` or `top_news.py` to discover relevant URLs
2. Use `download.py --format md` to fetch each promising link as markdown
3. Read the downloaded content, extract key facts, discover new leads
4. Run further `search.py` queries based on what was learned
5. Synthesise findings across all sources

### Technical / vendor / niche topic research — CRITICAL

Generic queries return noise (e.g. "database news" → DNA databases, law enforcement). For ANY specialized domain the LLM MUST decompose the topic into precise queries BEFORE calling scripts.

**Decomposition pattern** — the LLM already knows every domain's landscape. Before running anything, enumerate from its own knowledge:
1. **Major vendors & players** in the space (10–20+)
2. **Key product/project names** distinct from vendor names
3. **Niche trade publications** that cover this domain (use as `site:` queries)
4. **Sub-categories & adjacent terms** (the domain's taxonomy)
5. **Action qualifiers**: "release", "announcement", "update", "launch", "acquisition", "benchmark", "migration", "open source"

**Execution pattern:**
1. Run `top_news.py --groups tech science finance --queries "VendorA" "VendorB" "ProductX announcement" "site:tradepub.com topic" ... --timelimit m` — pack as many targeted queries as needed via `--queries` (each becomes a separate DDG query)
2. Assess coverage — if key vendors/products are missing from results, run follow-up `search.py news` and `search.py text` queries for those specific gaps
3. Use `search.py text` (not just `news`) to catch blog posts, release notes, changelogs, and engineering docs

**Rules:**
- NEVER search for a bare domain word alone — always qualify with specific entity names, product names, or "technology"/"engineering"
- Use `site:` queries for niche trade publications the general news groups miss
- When results are thin, broaden with adjacent terms from the domain's taxonomy
- The more specific the queries, the better the signal — 20 precise queries beat 3 generic ones

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
- `--timelimit d|w|m|y` — restrict news to past day/week/month/year
- `--enrich-authors` — fetch page metadata (JSON-LD/OG) for author names (adds ~10–20 s)
- `--max-enrich 60` — cap how many articles get metadata fetch

**Output**: JSON array, URL-deduplicated.  Each element:
```json
{"title": "…", "url": "…", "source": "Reuters", "date": "2026-03-10T…", "description": "…", "author": "Jane Smith", "query_group": "wires"}
```

## `download.py` — Fetch URL to File

Fetches any public web page, strips noise (nav/scripts/ads), saves as txt, md, or pdf.

Uses `curl_cffi` with Chrome TLS fingerprint impersonation — bypasses Cloudflare and similar bot-detection. On 403/401/451, automatically falls back to Wayback Machine, then Google Cache.

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

- **Libraries** — `ddgs` (DDG API), `curl_cffi` (Chrome TLS impersonation), `httpx` + `beautifulsoup4` (metadata + archive fallbacks), `truststore` (macOS SSL), `html2text` + `fpdf2` (format conversion), `python-dateutil`, `Pillow` (image metadata)
- **Python** ≥3.11, PEP 723 inline metadata in every script
- **Runtime** — `uv run --no-config` for isolated execution
- **Output** — all scripts emit JSON to stdout; progress/errors go to stderr

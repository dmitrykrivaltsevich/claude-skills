---
name: duckduckgo
description: Searches the internet via DuckDuckGo and downloads web pages. Scripts output JSON to stdout so the LLM does the ranking, dedup, clustering, and presentation. Use when the user asks to search the web, find images, look up news, wants a news digest, wants to download/archive a URL, wants to reopen a saved page by heading/chunk/lines, wants to detect trending topics, verify claims across sources, monitor topics for new articles, or search across languages/regions. Scripts — search.py, top_news.py, download.py, page_query.py, vision.py, trending.py, fact_check.py, monitor.py, translate_search.py.
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
5. [State/Environment Surface](#stateenvironment-surface--default-mode)
6. [Workflow Patterns](#how-the-llm-should-use-these)
7. [Presentation Rules](#presentation-rules--mandatory)
8. [top_news.py Details](#top_newspy--multi-source-news-fetcher)
9. [download.py Details](#downloadpy--fetch-url-to-file)
10. [Image Display](#image-display)
11. [Limitations](#limitations)
12. [Technical Details](#technical-details)

## Architecture — Scripts Are Data Pipes, LLM Is the Brain

Scripts handle what the LLM cannot: parallel HTTP requests, DDG API calls, rate-limit management, SSL, and structured metadata extraction. They output **JSON to stdout** (progress to stderr).

The LLM handles what scripts cannot: semantic deduplication, story clustering ("5 outlets cover X"), context-aware ranking based on the user's actual request, follow-up research via `download.py`, and tailored presentation.

**Workflow pattern**: capture broad results into external state/environment → narrow to a small working set → (optionally) dig deeper on that working set → present to user.

## Script Decision Guide

| User says… | Script | What it returns |
|---|---|---|
| "search for X", "find pages about X" | `search.py text` | JSON array of `{title, url, description}` |
| "find images of X", "show me pictures" | `search.py image` | JSON array of `{title, url, image, thumbnail, source}` |
| "news about X", "latest on X" | `search.py news` | JSON array of `{title, url, description, date, source}` |
| "top news", "world news", "news digest", "what's happening" | `top_news.py` | JSON array from 62+ parallel queries across 11 source groups |
| "top AI news", "news about climate from all sources" | `top_news.py --groups tech --queries "AI breakthroughs"` | Combine groups + custom queries |
| "save/download/archive this page" | `download.py` | Saved file (txt/md/pdf) |
| "reopen this downloaded page", "read the Transport section", "show lines 80-120" | `page_query.py` | JSON object with one heading, chunk, or line-range slice |
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
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query" --output /tmp/search.json

# News search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query" [--max-results N] [--timelimit d|w|m|y]

# Image search — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--max-results N] [--timelimit Day|Week|Month|Year]

# Multi-source news sweep — returns JSON:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py [--groups GROUP …] [--queries "Q1" "Q2" …] [--per-query N] [--timelimit d|w|m|y] [--enrich-authors]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups tech science --output /tmp/top-news.json

# Download a URL:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py <url> [--format txt|md|pdf] [--output PATH]

# Reopen only one slice from a downloaded markdown page:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --heading "Pricing"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --chunk 2 --chunk-size 40
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --start-line 80 --end-line 120

# Visual search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH

# Trend detection:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --topics "AI regulation" "climate summit"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --discover

# Claim cross-referencing:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "Ukraine ceasefire agreement"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "claim text" --tiers wires broadsheets
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "claim text" --output /tmp/fact-check.json

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

## State/Environment Surface — Default Mode

Treat DuckDuckGo results as external state/environment, not as transcript memory.

**Recommended state/environment layout** for any non-trivial search:
- **Discovery file**: `/tmp/ddg-<topic>-discovery.json` — raw search/news/trend/fact-check output
- **Working-set file**: `/tmp/ddg-<topic>-working-set.json` — shortlist, clusters, or support matrix
- **Page directory**: `/tmp/ddg-<topic>/pages/` — downloaded markdown or PDF pages
- **Synthesis notes**: `/tmp/ddg-<topic>-notes.md` or `/tmp/ddg-<topic>-notes.json`

For any broad search, news sweep, trend scan, fact-check, or multi-language query:

1. **Capture discovery into external state/environment first.** Do NOT let a large raw result set become the thing you carry in the transcript.
2. **Create a working-set file** before any deeper reasoning. The working set should usually be one of:
   - 10–15 URLs for single-topic research
   - 5–10 story clusters for news digests
   - 3–8 candidate topics for trend work
   - a per-tier support matrix for claim verification
3. **Deep-read from the working-set file only.** Use `download.py` or follow-up search on the shortlisted items, one item or a tiny batch at a time.
  Reopen downloaded markdown with `page_query.py` by heading, chunk, or line range rather than rereading the full page.
4. **Write synthesis from the working set and downloaded pages, not from the full discovery file.**

**Native artifact mode** for scripts that output large JSON:

```bash
# Broad discovery goes to a file, not into the transcript:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "topic" --max-results 20 --output /tmp/ddg-topic-discovery.json

# Multi-source sweep goes to a file first:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups tech science --output /tmp/ddg-tech-discovery.json
```

When `--output` is used, stdout should contain only a compact artifact envelope. Reopen the saved file, not the prior transcript payload.

Carry forward only compact artifacts such as:
- working-set path plus 1–2 line summary
- URL shortlist with one-line reasons
- story cluster map (`story -> representative URLs + supporting sources`)
- support matrix (`tier -> supporting URLs / conflicting URLs / unknowns`)
- unresolved question list

Do NOT carry forward:
- raw JSON dumps from large result sets
- dozens of article descriptions inline when only a shortlist is needed
- previously downloaded full pages once a compact note or cluster summary exists

`monitor.py` already exposes a persistent state/environment surface via `--state-file`. Prefer that model whenever a topic will be revisited.

## How the LLM Should Use These

### Single-topic research
1. Run `search.py news --query "topic" --max-results 20 --output /tmp/ddg-<topic>-discovery.json`
2. Reopen only enough of that discovery file to build `/tmp/ddg-<topic>-working-set.json`
3. If a story needs deeper reading, use `download.py <url> --format md --output /tmp/ddg-<topic>/pages/<slug>.md` for only the shortlisted URLs, one by one or in tiny batches
4. Use `page_query.py` on those downloaded markdown files to reopen only the specific section, chunk, or line range needed for extraction
5. Synthesise and present from the working-set file plus any downloaded page slices

### Comprehensive news digest
1. Run `top_news.py` (all groups) or `top_news.py --groups tech science --queries "AI regulation" --output /tmp/ddg-news-discovery.json`
2. Build `/tmp/ddg-news-working-set.json` containing 5–10 story clusters with representative URLs and supporting outlets
3. Rank the clusters by the user's stated criteria (impact, recency, topic relevance, etc.)
4. For important stories, optionally `download.py` only the top 1–2 URLs per cluster to read the full article
5. Present with source attribution, clustering ("also covered by…"), dates, and summaries

### Trend detection
1. Run `trending.py --discover --output /tmp/ddg-trending-discovery.json`, or `trending.py --topics "X" "Y" --output /tmp/ddg-trending-discovery.json`
2. Build `/tmp/ddg-trending-working-set.json` containing only the few candidate topics worth carrying forward
3. Compute velocity: topics where `24h_count / 7d_count` is high are accelerating
4. Present: "These 3 stories are blowing up right now" with source counts and date ranges
5. Optionally `download.py` top headlines for only the top candidates

### Claim verification
1. Run `fact_check.py "claim text" --output /tmp/ddg-claim-discovery.json` — searches across 7 tiers
2. Build `/tmp/ddg-claim-working-set.json` as a support matrix: `tier -> support / contradiction / absence`
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
4. Cross-compare and keep only the cross-language clusters or the few region-specific outliers worth deeper reading

### Deep research / spider mode
1. Start with `search.py text` or `top_news.py` and capture broad results into `/tmp/ddg-<topic>-discovery.json` via `--output`
2. Convert that discovery set into `/tmp/ddg-<topic>-working-set.json`, a queue of promising URLs with a short reason for each
3. Use `download.py --format md` to fetch only the next 1–3 URLs from the queue
4. Use `page_query.py` to reopen only the heading, chunk, or line range you need from each downloaded page
5. Read the sliced content, extract key facts, and update the working-set file or notes file
6. Run further `search.py` queries based on what was learned, again capturing them to discovery files first
7. Synthesise findings across the working-set artifacts, not from the full crawl history

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
2. Convert the results into a gap list and a shortlist before further searching
3. Assess coverage — if key vendors/products are missing from the shortlist, run follow-up `search.py news` and `search.py text` queries for those specific gaps, again capturing results to discovery files first
4. Use `search.py text` (not just `news`) to catch blog posts, release notes, changelogs, and engineering docs

**Rules:**
- NEVER search for a bare domain word alone — always qualify with specific entity names, product names, or "technology"/"engineering"
- Use `site:` queries for niche trade publications the general news groups miss
- When results are thin, broaden with adjacent terms from the domain's taxonomy
- The more specific the queries, the better the signal — 20 precise queries beat 3 generic ones
- Broad discovery is allowed; broad carry-state is not. Always narrow to a small working set before downloading or synthesising.
- The transcript is not the search state/environment. The search state/environment lives in your discovery files, working-set files, downloaded pages, and monitor state files.

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
| `broadcast_diverse` | Fox News, NY Post, Daily Mail, Washington Examiner, National Review |
| `finance` | Bloomberg, CNBC, MarketWatch, Fortune, Business Insider |
| `policy` | Politico, Axios, Vox, Foreign Affairs, ProPublica, The Intercept |
| `tech` | TechCrunch, Ars Technica, The Verge, Wired, Slashdot, TNW, ZDNet, VentureBeat |
| `tech_primary` | Apple Newsroom, Google Blog, Microsoft Blogs, Amazon News, Meta News, OpenAI Blog, Anthropic News, NVIDIA |
| `tech_engineering` | GitHub Blog, Meta Engineering, Netflix Tech, Cloudflare Blog, AWS Blogs, GCP Blog, Azure Blog, Uber Engineering |
| `tech_ai` | OpenAI, Anthropic, Hugging Face, DeepMind, Meta AI, Stability AI |
| `tech_security` | KrebsOnSecurity, BleepingComputer, The Hacker News, Dark Reading, The Record |
| `tech_products` | Product Hunt, Indie Hackers |
| `tech_asia` | TechNode, Tech in Asia, Rest of World, Tech.eu |
| `science` | Nature, Science, New Scientist, SciAm, ACM, IEEE, arXiv, Phys.org |
| `health` | WHO, CDC, NIH, Lancet, NEJM, BMJ, STAT News, KFF Health News |
| `sports` | ESPN, BBC Sport, Sky Sports, The Athletic, Yahoo Sports |
| `environment` | Carbon Brief, Inside Climate News, E&E News, Grist, Climate Home |
| `entertainment` | Variety, Hollywood Reporter, Deadline, Rolling Stone, Pitchfork |
| `international` | Spiegel, Le Monde, France24, DW, El País Intl, Al Jazeera, Haaretz, Arab News, SCMP, Japan Times, Korea Herald, Straits Times, Hindustan Times, ABC AU, Daily Maverick, Nation Africa, Buenos Aires Herald |
| `institutional` | WHO, UN News, EU Newsroom, State Dept, White House |
| `social` | Reddit r/worldnews, r/news, Hacker News |
| `independent` | Substack, Medium, Bellingcat |

**Flags**:
- `--groups tech science` — restrict to specific groups
- `--queries "AI boom" "LLM safety"` — add free-form queries (tagged `query_group: "custom"`)
- `--per-query 20` — DDG results per query (default 20)
- `--timelimit d|w|m|y` — restrict news to past day/week/month/year
- `--region us-en|uk-en|de-de|…` — DDG region code (default: user's locale; `wt-wt` for worldwide)
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

# Reopen a saved markdown page without rereading the full file:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --heading "Conclusion"
```

PDF uses Computer Modern fonts (Knuth-style typography). Format auto-inferred from `--output` extension.

After saving markdown with `download.py --format md`, use `page_query.py` to reopen only the relevant heading, chunk, or line range from that saved page.

## Image Display

VS Code Copilot does NOT render `![](url)` or `<img>`. Present image results as clickable `[title](url)` links and open the first 3 via `open_browser_page`.

## Limitations

- **Rate limit**: ~35 queries/minute; `top_news.py` uses parallel workers within this budget
- **Paywalled pages**: `download.py` returns only publicly visible content
- **Author coverage**: `--enrich-authors` works for wire/open-access articles; paywalled sites block metadata
- **No login required** — public API only

## Source Bias Notes

The default source pool has known biases the LLM should compensate for:

| Bias type | Default behavior | How to compensate |
|-----------|-----------------|-------------------|
| **Geographic** | ~60% US/UK sources | Add `--groups international` or use `translate_search.py` for non-Western coverage |
| **Political** | Center to center-left editorial lean | Add `--groups broadcast_diverse` for right-leaning perspectives |
| **Topic** | Tech/policy heavy; health/sports/environment underrepresented | Explicitly include `health`, `sports`, `environment`, `entertainment` groups |
| **Source type** | Journalism heavy; misses primary sources | Use `tech_primary`, `tech_engineering`, `institutional` for direct announcements |

**For balanced coverage**, expand beyond defaults:
```bash
# Politically balanced news sweep:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups wires print broadcast broadcast_diverse international

# Comprehensive tech coverage (primary + journalism + security):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups tech tech_primary tech_engineering tech_ai tech_security tech_asia

# Health-focused sweep:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups health science wires
```

## Technical Details

- **Libraries** — `ddgs` (DDG API), `curl_cffi` (Chrome TLS impersonation), `httpx` + `beautifulsoup4` (metadata + archive fallbacks), `truststore` (macOS SSL), `html2text` + `fpdf2` (format conversion), `python-dateutil`, `Pillow` (image metadata)
- **Python** ≥3.11, PEP 723 inline metadata in every script
- **Runtime** — `uv run --no-config` for isolated execution
- **Output** — all scripts emit JSON to stdout; progress/errors go to stderr

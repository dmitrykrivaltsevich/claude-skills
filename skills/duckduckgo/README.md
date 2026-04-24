# DuckDuckGo Search Skill

Search the internet via DuckDuckGo's public APIs for text results, images, news, and more. No authentication required.

The recommended workflow is staged and file-backed: search broadly, capture the raw result set into external state/environment via each script's native `--output` mode, narrow to a small shortlist or cluster map, then deepen only on the shortlisted URLs. When a shortlisted URL is downloaded as markdown, reopen only the needed section with `page_query.py` instead of rereading the whole file.

## Operations

| Script | Purpose |
|--------|---------|
| `search.py` | Text, image, and news search with query parameters |
| `top_news.py` | Multi-source news sweep (62+ queries across 11 source groups) |
| `download.py` | Fetch any URL and save as txt, md, or pdf |
| `page_query.py` | Reopen a downloaded markdown/text page by heading, chunk, or line range |
| `vision.py` | Visual search — analyze image metadata &amp; find similar images |
| `trending.py` | Trend detection — measure topic velocity and discover what's accelerating |
| `fact_check.py` | Cross-reference a claim across source tiers (wires → broadsheets → social) |
| `monitor.py` | Persistent topic watch — track seen URLs, output only new articles |
| `translate_search.py` | Multi-region parallel search with language tags |

### Text Search

```bash
# Simple keyword search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "machine learning applications"

```

### Image Search

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "circuit board diagram" \
  --size large \
  --type png \
  --color white
```

Size options: `Small`, `Medium`, `Large`, `Wallpaper`
Type options: `photo`, `clipart`, `gif`, `transparent`, `line`
Color options: `color`, `Monochrome`, `Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `Black`, `Gray`, `Teal`, `White`

### News Search

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "AI breakthrough 2026"
```

### Visual Search

```bash
# Find images similar to this file:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path path/to/image.jpg

# Analyze image and get metadata (JSON):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path path/to/image.jpg
```

### Multi-Source News Sweep

```bash
# Fetch news from 62+ queries across all source groups:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py

# Restrict to specific groups + add custom queries:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/top_news.py --groups tech science --queries "AI safety"
```

### Download / Archive URL

```bash
# Save any URL as markdown:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py https://example.com/article --format md

# Save as PDF with Computer Modern typography:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/download.py https://example.com/article --format pdf --output ~/Desktop/article.pdf
```

### Page Slice Query

```bash
# Reopen only one section from a saved markdown page:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --heading "Pricing"

# Reopen a fixed-size chunk:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --chunk 2 --chunk-size 40

# Reopen an exact line range:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/page_query.py --file /tmp/article.md --start-line 80 --end-line 120
```

### Trend Detection

```bash
# Measure trend velocity for specific topics:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --topics "AI regulation" "climate summit"

# Auto-discover trending topics:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trending.py --discover
```

### Claim Cross-Referencing

```bash
# Verify a claim across source tiers (wires, broadsheets, broadcast, etc.):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "Ukraine ceasefire agreement"

# Check specific tiers only:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/fact_check.py "claim text" --tiers wires broadsheets
```

### Topic Monitoring

```bash
# Monitor a topic — outputs only NEW articles since last run:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/monitor.py "AI safety"

# Use a custom state file:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/monitor.py "climate policy" --state-file ~/my-watch.json
```

### Multi-Region Search

```bash
# Search the same topic in multiple languages/regions:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/translate_search.py \
  "fr-fr:intelligence artificielle" \
  "de-de:künstliche Intelligenz" \
  "us-en:artificial intelligence"
```

## Architecture

```
duckduckgo/
  SKILL.md                    # Claude runtime instructions (frontmatter + ops)
  README.md                   # This file - user documentation
  scripts/
    search.py                 # Text, image, news search
    top_news.py               # Multi-source news sweep (62+ parallel queries)
    download.py               # Fetch URL → txt/md/pdf
    page_query.py             # Reopen one slice from a saved markdown/text page
    vision.py                 # Visual search and image metadata
    trending.py               # Trend detection and topic velocity
    fact_check.py             # Cross-source claim verification
    monitor.py                # Persistent topic monitoring
    translate_search.py       # Multi-region parallel search
    contracts.py              # Design-by-contract decorators
  tests/                      # Unit tests for all scripts
```

## Technical Details

- **Python** ≥3.11 — all scripts use PEP 723 inline metadata
- **Runtime** — `uv run` for isolated, sandboxed execution (no global installs)
- **Library** — `ddgs` (DDG API), `curl_cffi` (Cloudflare bypass), `httpx` + `beautifulsoup4`, `Pillow`, `html2text`, `fpdf2`
- **No authentication required**

## Testing

```bash
# Run all tests:
uv run --no-config --with pytest --with "ddgs>=6.0" --with Pillow --with beautifulsoup4 --with html2text --with httpx --with truststore --with python-dateutil pytest tests/ -v
```
